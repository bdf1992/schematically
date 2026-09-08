'use strict';
// Transport-neutral Boolean/finite-state execution. See LOGIC-RUNTIME.md.
(function(root){
  const D=root.SovSchematicData;
  const SCHEMA='soveraeign.schematic/run@0.1';
  const FILE_SCHEMA='soveraeign.schematic/run-file@0.1';
  const LIMIT=20000, PENDING=5000;
  const clone=D.clone;
  const fail=(code,message)=>{const e=new Error(message);e.code=code;throw e};
  const need=(ok,code,message)=>{if(!ok)fail(code,message)};
  const canonical=x=>JSON.stringify(sort(x));
  function sort(x){
    if(Array.isArray(x))return x.map(sort);
    if(x&&typeof x==='object')return Object.fromEntries(Object.keys(x).sort().map(k=>[k,sort(x[k])]));
    return x;
  }
  const bit=x=>x===0||x===1;
  function integer(x,min,max,name){need(Number.isSafeInteger(x)&&x>=min&&x<=max,'INVALID_NUMBER',name);return x}
  function names(xs){
    need(Array.isArray(xs)&&xs.every(x=>typeof x==='string'&&/^[A-Za-z][\w.-]{0,63}$/.test(x)&&!['__proto__','constructor','prototype'].includes(x))&&new Set(xs).size===xs.length,'INVALID_NAMES','Unique bounded identifiers required');return xs;
  }
  function definition(raw){
    need(raw&&['source','table'].includes(raw.kind),'INVALID_DEFINITION','Expected source or table definition');
    const d=clone(raw);d.inputs=names(d.inputs||[]);d.outputs=names(d.outputs||[]);d.state=names(d.state||[]);
    need(new Set([...d.inputs,...d.outputs]).size===d.inputs.length+d.outputs.length,'INVALID_DEFINITION','Input/output names overlap');
    need(d.outputs.length<=8&&d.inputs.length+d.state.length<=8,'CAPACITY','Definition exceeds eight bits');
    need(Array.isArray(d.initial)&&d.initial.every(bit),'INVALID_DEFINITION','Initial bits required');
    if(d.kind==='source'){
      need(!d.inputs.length&&!d.state.length&&d.outputs.length===1&&d.initial.length===1,'INVALID_DEFINITION','Source needs one output and initial bit');
    }else{
      const width=d.inputs.length+d.state.length, rows=2**width;
      need(d.initial.length===d.state.length&&Array.isArray(d.table)&&d.table.length===rows,'INVALID_TABLE','Complete table and initial memory required');
      const seen=new Set();
      for(const row of d.table){
        need(Array.isArray(row)&&row.length===width+d.outputs.length+d.state.length&&row.every(bit),'INVALID_TABLE','Wrong row width or non-bit');
        const key=row.slice(0,width).join('');need(!seen.has(key),'INVALID_TABLE','Duplicate input/state row');seen.add(key);
      }
    }
    return d;
  }
  function compile(input){
    const doc=D.makeDocument(clone(input)),valid=D.validateDocument(doc);
    need(valid.ok,'INVALID_DOCUMENT',valid.errors.join('; '));
    const spec=doc.meta?.logic;
    need(spec?.schema==='soveraeign.schematic/logic@0.1'&&spec.definitions,'NO_LOGIC','Document has no logic definitions');
    const components=doc.components.filter(c=>c.config?.logic);
    need(components.length>0&&components.length<=256&&doc.wires.length<=4096,'CAPACITY','Expected 1–256 runtime components and at most 4096 carriers');
    const nodes=components.map(c=>{
      names([c.id]);const d=definition(spec.definitions[c.config.logic.definition]);
      const ports={};
      for(const p of [...d.inputs,...d.outputs]){
        need([...D.canonicalAttachmentPointIdsForComponent(c),...D.canonicalPortIdsForComponent(c)].includes(p),'INVALID_PORT',`${c.id}.${p} is not an attachment`);
        const compat=D.canonicalPortIdForComponent(c,p);
        need(compat&&D.attachmentPointConfig(doc,c.id,compat),'INVALID_PORT',`${c.id}.${p} is not an attachment`);
        need(!Object.values(ports).includes(compat),'INVALID_PORT','Aliases share one attachment');ports[p]=compat;
      }
      return {id:c.id,definition:d,ports,delay:integer(c.config.logic.delay??0,0,1000000,'component delay')};
    }).sort((a,b)=>a.id<b.id?-1:a.id>b.id?1:0);
    const byId=new Map(nodes.map(n=>[n.id,n])),edges=[],drivers=new Set();
    for(const w of [...doc.wires].sort((a,b)=>a.id<b.id?-1:a.id>b.id?1:0)){
      if(!byId.has(w.a)&&!byId.has(w.b))continue;
      const cfg=w.config||{},direction=cfg.direction||'forward';
      if(direction==='none')continue;
      need(['forward','reverse'].includes(direction),'UNSUPPORTED_DIRECTION',`Runtime carrier ${w.id} must be one-way`);
      const from=direction==='forward'?'a':'b',to=from==='a'?'b':'a';
      const source=byId.get(w[from]),target=byId.get(w[to]);
      need(source&&target,'UNBOUND_RUNTIME_PATH',`Both ends of ${w.id} must name runtime components`);
      const output=source.definition.outputs.find(p=>source.ports[p]===w[from+'Side']);
      const inputName=target.definition.inputs.find(p=>target.ports[p]===w[to+'Side']);
      need(output&&inputName,'INVALID_DIRECTION',`${w.id} must connect a declared output to input`);
      for(const [end,isSource] of [[from,true],[to,false]]){
        const port=D.attachmentPointConfig(doc,w[end],w[end+'Side']);
        need((cfg[end+'ConnectionIndex']||0)===0&&port?.connections?.length===1,'UNSUPPORTED_CHANNEL','Runtime uses one connection per attachment');
        const flow=port.connections[0].flow;
        need((isSource?['out','duplex']:['in','control','duplex']).includes(flow),'FLOW_REFUSED',`${w.id} endpoint flow refuses propagation`);
      }
      need(!cfg[direction+'Operation']||cfg[direction+'Operation']==='none','EXTERNAL_EFFECT_REFUSED','Logic does not execute read/write operations');
      need(D.connectionReachability(doc,w.a,w.aSide,w.b,w.bSide).ok,'BOUNDARY_REFUSED',w.id);
      const driver=canonical([target.id,inputName]);need(!drivers.has(driver),'MULTIPLE_DRIVERS',driver);drivers.add(driver);
      edges.push({id:w.id,from:source.id,output,to:target.id,input:inputName,delay:integer(cfg.logic?.delay??1,0,1000000,'carrier delay')});
    }
    return {schema:'soveraeign.schematic/program@0.1',documentId:doc.id,nodes,edges};
  }
  function rowFor(node,state){
    const d=node.definition,key=[...d.inputs.map(p=>state.inputs[p]),...state.memory];
    return d.table.find(row=>key.every((v,i)=>v===row[i])).slice(key.length);
  }
  function enqueue(s,event){
    need(s.queue.length<PENDING,'CAPACITY','Pending event capacity reached');
    integer(event.time,0,Number.MAX_SAFE_INTEGER,'logical time');
    s.queue.push({...event,sequence:s.sequence++});
    s.queue.sort((a,b)=>a.time-b.time||a.sequence-b.sequence);
  }
  function emit(s,node,output,value){
    for(const edge of s.program.edges)if(edge.from===node.id&&edge.output===output)
      enqueue(s,{kind:'arrival',time:s.time+node.delay+edge.delay,component:edge.to,port:edge.input,value,wire:edge.id});
  }
  function evaluate(s,node,initial=false){
    const state=s.values[node.id],d=node.definition;
    const row=d.kind==='source'?d.initial:rowFor(node,state);
    if(d.kind==='table'&&!initial)state.memory=row.slice(d.outputs.length);
    d.outputs.forEach((p,i)=>{if(initial||state.outputs[p]!==row[i]){state.outputs[p]=row[i];emit(s,node,p,row[i])}});
  }
  function start(program){
    const s={schema:SCHEMA,program:clone(program),time:0,sequence:0,processed:0,status:'READY',values:{},queue:[],trace:[],commands:[]};
    for(const n of program.nodes)s.values[n.id]={inputs:Object.fromEntries(n.definition.inputs.map(p=>[p,0])),outputs:{},memory:n.definition.kind==='table'?[...n.definition.initial]:[]};
    for(const n of program.nodes)evaluate(s,n,true);
    s.status=s.queue.length?'READY':'QUIESCENT';return s;
  }
  function advance(s,budget){
    let count=0;
    while(s.queue.length&&count<budget){
      need(s.processed<LIMIT,'CAPACITY','Run event capacity reached; export and start a new run');
      const event=s.queue.shift(),node=s.program.nodes.find(n=>n.id===event.component),state=s.values[node.id];
      s.time=event.time;const before=clone(state);
      if(event.kind==='source'){
        if(state.outputs[event.port]!==event.value){state.outputs[event.port]=event.value;emit(s,node,event.port,event.value)}
      }else{
        const changed=state.inputs[event.port]!==event.value;state.inputs[event.port]=event.value;
        if(changed)evaluate(s,node);
      }
      s.trace.push({index:s.processed++,event,before,after:clone(state)});count++;
    }
    s.status=s.queue.length?'PAUSED_BUDGET':'QUIESCENT';
  }
  function command(s,request){
    need(s.commands.length<LIMIT,'CAPACITY','Command capacity reached');
    let cmd;
    if(request.action==='input'){
      const node=s.program.nodes.find(n=>n.id===request.component);
      need(node?.definition.kind==='source','NOT_SOURCE','Input must name a source component');
      need(bit(request.value),'INVALID_VALUE','Input must be 0 or 1');
      const time=integer(request.time??s.time,s.time,Number.MAX_SAFE_INTEGER,'input time');
      cmd={action:'input',component:node.id,value:request.value,time};
      enqueue(s,{kind:'source',time,component:node.id,port:node.definition.outputs[0],value:request.value,wire:null});s.status='READY';
    }else{
      need(['step','run'].includes(request.action),'UNKNOWN_ACTION','Unknown runtime command');
      const budget=request.action==='step'?1:integer(request.budget??100,1,1000,'event budget');
      cmd={action:request.action,...(request.action==='run'?{budget}:{})};advance(s,budget);
    }
    s.commands.push(cmd);return s;
  }
  function restore(program,snapshot){
    need(snapshot?.schema===SCHEMA&&canonical(snapshot.program)===canonical(program),'STALE_DEFINITION','Run does not match this executable diagram');
    need(Array.isArray(snapshot.commands)&&snapshot.commands.length<=LIMIT,'INVALID_SNAPSHOT','Invalid command history');
    const rebuilt=start(program);
    for(const cmd of snapshot.commands)command(rebuilt,cmd);
    need(canonical(rebuilt)===canonical(snapshot),'REPLAY_MISMATCH','Saved state, queue or trace differs from replay');return rebuilt;
  }
  function execute(doc,current,request={}){
    request=request||{};
    try{
      const program=compile(doc);let session;
      if(request.action==='start')session=start(program);
      else if(request.action==='restore')session=restore(program,request.session);
      else{
        need(current?.schema===SCHEMA,'NO_RUN','Start or restore a run first');
        need(canonical(current.program)===canonical(program),'STALE_DEFINITION','Executable diagram changed; start a new run');
        if(request.action==='replay')session=restore(program,current);
        else{session=clone(current);if(request.action!=='get')command(session,request)}
      }
      return {ok:true,session,receipt:{schema:'soveraeign.schematic/run-receipt@0.1',action:request.action,status:session.status,time:session.time,processed:session.processed,pending:session.queue.length,error:null}};
    }catch(error){return {ok:false,session:current,receipt:{schema:'soveraeign.schematic/run-receipt@0.1',action:request.action,error:{code:error.code||'INVALID_RUNTIME',message:error.message}}}}
  }
  function tools(){return [{name:'schematic.runtime',description:'Start, inspect, input, step, run, replay or restore a deterministic local logic run. No external effects.',inputSchema:{type:'object',properties:{action:{enum:['start','get','input','step','run','replay','restore']},component:{type:'string'},value:{enum:[0,1]},time:{type:'integer',minimum:0},budget:{type:'integer',minimum:1,maximum:1000},session:{type:'object'}},required:['action'],additionalProperties:false}}]}
  root.SovSchematicLogic={SCHEMA,FILE_SCHEMA,compile,execute,canonical,tools};
})(typeof globalThis!=='undefined'?globalThis:this);
