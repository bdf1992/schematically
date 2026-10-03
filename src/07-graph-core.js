'use strict';
// 0.1 concern: graph reading of a document (queries, junction flow) and the discrete-event
// message simulation. No DOM; shared by the browser API and the MCP/HTTP server.
// Specified in GRAPH-MODEL.md.
(function(root,factory){
  let Data=root.SovSchematicData,Model=root.SovSchematicSignalModel,surface=()=>root.SovSchematicSimSurface;
  if(!Model&&typeof module!=='undefined'&&module.exports)Model=require('./04-signal-model.js');
  if(!Data&&typeof module!=='undefined'&&module.exports){require('./06-attachment-core.js');Data=require('./05-data-core.js')}
  // Under node, createSimulation/runScenario/createSession/tools delegate to the sim surface
  // (src/07-state-surface.js, contract 09 of the one-runtime plan), required at call time so
  // the two modules' mutual require does not run at load time.
  if(typeof module!=='undefined'&&module.exports)surface=()=>root.SovSchematicSimSurface||require('./07-state-surface.js');
  const api=factory(Data,Model,surface);
  root.SovSchematicGraph=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(Data,Model,surface){
  if(!Data)throw new Error('SovSchematicData core is required');
  if(!Model)throw new Error('SovSchematicSignalModel (src/04-signal-model.js) is required');
  const clone=Data.clone;
  const isObject=v=>!!v&&typeof v==='object'&&!Array.isArray(v);
  const POLICIES=['fanout','distribute','merge','join','select'];

  function refusal(code,message,extra={}){return {ok:false,code,message,...extra}}

  // ---- Graph reading -------------------------------------------------------------------
  // Passability and the signal model live in src/04-signal-model.js, shared with the state-space
  // runtime; they are re-exported here under the same names.
  const {DEFAULT_LATENCY_MS,COMBINES,activeConnection,canEmit,canReceive,accessAllows,signalConfig}=Model;
  function wireDirection(w){const d=w.config?.direction;return ['none','forward','reverse','duplex'].includes(d)?d:(w.duplex?'duplex':'forward')}
  function flowConfig(component){
    const f=isObject(component.config?.flow)?component.config.flow:{};
    return {declared:POLICIES.includes(f.policy),policy:POLICIES.includes(f.policy)?f.policy:'fanout',by:['round-robin','channel','key'].includes(f.by)?f.by:'round-robin',key:typeof f.key==='string'?f.key:null,rate:isObject(f.rate)?f.rate:null,capacity:Number.isFinite(Number(f.capacity))?Number(f.capacity):null,releaseMs:Number.isFinite(Number(f.releaseMs))?Math.max(0,Number(f.releaseMs)):null};
  }

  // Access control on a plane: config.acl = {default: deny|allow, entries: [{principal, allow, deny}]}.
  // A principal pattern is exact, 'prefix:*' or '*'. Order does not matter: a matching deny
  // refuses, else a matching allow admits, else the default decides (deny unless declared).
  const ACL_OPS=['enter','exit','read','write'];
  function aclConfig(c){
    const a=c.config?.acl;if(!isObject(a))return null;
    const list=v=>Array.isArray(v)?v.map(String).filter(x=>ACL_OPS.includes(x)):[];
    return {default:a.default==='allow'?'allow':'deny',entries:(Array.isArray(a.entries)?a.entries:[]).filter(isObject).map(e=>({principal:String(e.principal??''),allow:list(e.allow),deny:list(e.deny)}))};
  }
  function principalMatches(pattern,principal){
    if(principal==null||principal==='')return false;
    if(pattern==='*')return true;
    return pattern.endsWith('*')?String(principal).startsWith(pattern.slice(0,-1)):pattern===String(principal);
  }
  function aclDecide(plane,principal,op){
    const acl=plane.acl;if(!acl)return {ok:true};
    const name=plane.label||plane.id;
    if(principal==null||principal==='')return {ok:false,reason:`acl: no principal may ${op} ${name} anonymously`};
    const matching=acl.entries.filter(e=>principalMatches(e.principal,principal));
    const denied=matching.find(e=>e.deny.includes(op));
    if(denied)return {ok:false,reason:`acl: ${principal} is denied ${op} on ${name}`,entry:denied.principal};
    const allowed=matching.find(e=>e.allow.includes(op));
    if(allowed)return {ok:true,entry:allowed.principal};
    return acl.default==='allow'?{ok:true}:{ok:false,reason:`acl: ${principal} may not ${op} ${name}`};
  }

  // The graph is derived from the normalized document on every call; it is never stored.
  function build(input){
    const doc=Data.makeDocument(clone(input||{}));
    const N=(typeof globalThis!=='undefined'?globalThis:{}).SovSchematicNotation,resolved=N?N.resolve(doc):null,notation=resolved?.ok?resolved.notation:null;
    const nodes=new Map(),arcs=[],blocked=[],ends=new Map();
    for(const c of doc.components){
      nodes.set(c.id,{id:c.id,symbolId:c.symbolId,label:c.config?.label||'',parentId:c.parentId||null,canvasId:c.canvasId||Data.GLOBAL_CANVAS_ID,
        dimension:Number(c.form?.dimension??2),signalMode:c.config?.signalMode||null,flow:flowConfig(c),
        behavior:isObject(c.config?.behavior)?clone(c.config.behavior):{},ports:c.config?.ports||{},placement:c.placement||null,
        signal:signalConfig(c,notation?.glyphs?.[c.symbolId]||null),principal:typeof c.config?.principal==='string'&&c.config.principal?c.config.principal:null,acl:aclConfig(c),
        interior:Data.componentCanvasId(c),open:c.form?.regions?.interior?.state==='open'});
      ends.set(c.id,0);
    }
    for(const w of doc.wires){
      const aBound=!!w.a&&nodes.has(w.a)&&!Data.isFreeEndpoint(w.aAttachment),bBound=!!w.b&&nodes.has(w.b)&&!Data.isFreeEndpoint(w.bAttachment);
      if(aBound)ends.set(w.a,ends.get(w.a)+1);if(bBound)ends.set(w.b,ends.get(w.b)+1);
      if(!aBound||!bBound){blocked.push({wireId:w.id,reason:'free end'});continue}
      const dir=wireDirection(w),cfg=w.config||{};
      const latency=Number.isFinite(Number(cfg.latencyMs))?Math.max(0,Number(cfg.latencyMs)):DEFAULT_LATENCY_MS;
      const accepts=Array.isArray(cfg.accepts)?cfg.accepts.map(String):null;
      const legs=[];
      if(dir==='forward'||dir==='duplex')legs.push(['a','b','forwardOperation']);
      if(dir==='reverse'||dir==='duplex')legs.push(['b','a','reverseOperation']);
      if(dir==='none')blocked.push({wireId:w.id,reason:'direction none'});
      for(const [s,t,opKey] of legs){
        const from=w[s],to=w[t],fromPort=w[s+'Side'],toPort=w[t+'Side'];
        const fp=nodes.get(from).ports[fromPort],tp=nodes.get(to).ports[toPort];
        const op=['read','write'].includes(cfg[opKey])?cfg[opKey]:'none';
        // The same passability rule as the derived signal (src/25-signal.js wireDirectionActive).
        const reason=!canEmit(fp,fromPort)?`${from}.${fromPort} cannot emit`:!canReceive(tp,toPort)?`${to}.${toPort} cannot receive`:(!accessAllows(fp,op)||!accessAllows(tp,op))?`access refuses ${op}`:null;
        if(reason){blocked.push({wireId:w.id,from,to,reason});continue}
        // The channels the two bound ports actually share (Attachment.channelIds, matched by
        // id): what a reach query with a channel argument follows, independent of a wire's own
        // `accepts` declaration, which still governs simulation routing at a junction.
        const channels=Data.sharedChannelIds(doc,from,fromPort,to,toPort);
        arcs.push({wireId:w.id,canvasId:w.canvasId||Data.GLOBAL_CANVAS_ID,from,fromPort,to,toPort,latencyMs:latency,accepts,channels,operation:op,control:activeConnection(tp,toPort)?.flow==='control'||toPort==='control'});
      }
    }
    const out=new Map(),inc=new Map();
    for(const id of nodes.keys()){out.set(id,[]);inc.set(id,[])}
    for(const a of arcs){out.get(a.from).push(a);inc.get(a.to).push(a)}
    const wireCanvas=new Map(doc.wires.map(w=>[w.id,w.canvasId||Data.GLOBAL_CANVAS_ID]));
    return {doc,nodes,arcs,blocked,out,in:inc,ends,wireCanvas};
  }
  // The plane whose boundary a node stands on: the host of a boundary Point, or the node
  // itself when it has an interior. A turn at that node from one side to the other is a crossing.
  function crossingAt(g,nodeId,inWire,outCanvas){
    const n=g.nodes.get(nodeId);if(!n||inWire==null)return null;
    const plane=n.placement?.kind==='edge'?g.nodes.get(n.placement.hostId):(n.open?n:null);
    if(!plane)return null;
    const side=c=>c===plane.interior?'in':'out',a=side(g.wireCanvas.get(inWire)),b=side(outCanvas);
    return a===b?null:{plane,op:a==='out'?'enter':'exit'};
  }

  function junctions(g){
    return [...g.nodes.values()].filter(n=>g.ends.get(n.id)>=3).map(n=>({id:n.id,label:n.label,ends:g.ends.get(n.id),policy:n.flow.policy,declared:n.flow.declared,incoming:g.in.get(n.id).length,outgoing:g.out.get(n.id).length}));
  }
  // With a channel, reach follows only a Wire whose two bound ports share that channel id
  // (the arc's `channels`, from Data.sharedChannelIds): a hosted boundary Point that declares
  // the channel passes it through, one that does not (or carries only `main`) blocks it. The
  // result names the channel it followed (null when none was given).
  function reach(g,from,{channel=null}={}){
    if(!g.nodes.has(from))return refusal('UNKNOWN_NODE',`No component ${from}`);
    const seen=new Set([from]),queue=[from],via=[];
    while(queue.length){const id=queue.shift();for(const a of g.out.get(id)){if(a.control)continue;if(channel&&!(a.channels||[]).includes(channel))continue;via.push(a.wireId);if(!seen.has(a.to)){seen.add(a.to);queue.push(a.to)}}}
    seen.delete(from);return {ok:true,from,channel,nodes:[...seen],wires:[...new Set(via)]};
  }
  function paths(g,a,b,{limit=20}={}){
    if(!g.nodes.has(a)||!g.nodes.has(b))return refusal('UNKNOWN_NODE','Both ends must be components');
    const found=[],stack=[[a,[a],[]]];
    while(stack.length&&found.length<limit){
      const [id,nodes,wires]=stack.pop();
      if(id===b&&nodes.length>1){found.push({nodes,wires});continue}
      for(const arc of [...g.out.get(id)].reverse())if(!nodes.includes(arc.to)||(arc.to===b&&a===b))stack.push([arc.to,[...nodes,arc.to],[...wires,arc.wireId]]);
    }
    return {ok:true,from:a,to:b,paths:found,truncated:found.length>=limit};
  }
  // Elementary cycles, each reported once from its smallest member.
  function cycles(g,{limit=100}={}){
    const ids=[...g.nodes.keys()].sort(),rank=new Map(ids.map((id,i)=>[id,i])),found=[];
    for(const start of ids){
      const stack=[[start,[start],[]]];
      while(stack.length&&found.length<limit){
        const [id,nodes,arcs]=stack.pop();
        for(const arc of g.out.get(id)){
          if(rank.get(arc.to)<rank.get(start))continue;
          if(arc.to===start){const timed=arcs.concat(arc).some(x=>x.latencyMs>0)||nodes.some(n=>['buffer','hold'].includes(g.nodes.get(n).symbolId));found.push({nodes,wires:arcs.concat(arc).map(x=>x.wireId),timed});continue}
          if(!nodes.includes(arc.to))stack.push([arc.to,[...nodes,arc.to],arcs.concat(arc)]);
        }
      }
    }
    return {ok:true,cycles:found,truncated:found.length>=limit};
  }
  function order(g){
    const indeg=new Map([...g.nodes.keys()].map(id=>[id,0]));
    for(const a of g.arcs)indeg.set(a.to,indeg.get(a.to)+1);
    const queue=[...indeg].filter(([,d])=>d===0).map(([id])=>id).sort(),out=[];
    while(queue.length){const id=queue.shift();out.push(id);for(const a of g.out.get(id)){indeg.set(a.to,indeg.get(a.to)-1);if(indeg.get(a.to)===0){queue.push(a.to);queue.sort()}}}
    if(out.length<g.nodes.size)return refusal('CYCLE','No topological order: the graph has a cycle',{members:[...indeg].filter(([,d])=>d>0).map(([id])=>id).sort()});
    return {ok:true,order:out};
  }
  // Minimum set of wires whose removal separates a from b (unit capacity per wire leg).
  function cut(g,a,b){
    if(!g.nodes.has(a)||!g.nodes.has(b)||a===b)return refusal('UNKNOWN_NODE','Two distinct components are required');
    const cap=new Map(),adj=new Map(),key=(u,v)=>u+'\u0000'+v,legs=new Map();
    const add=(u,v,wireId)=>{if(!adj.has(u))adj.set(u,new Set());if(!adj.has(v))adj.set(v,new Set());adj.get(u).add(v);adj.get(v).add(u);cap.set(key(u,v),(cap.get(key(u,v))||0)+1);if(!cap.has(key(v,u)))cap.set(key(v,u),0);if(!legs.has(key(u,v)))legs.set(key(u,v),[]);legs.get(key(u,v)).push(wireId)};
    for(const arc of g.arcs)add(arc.from,arc.to,arc.wireId);
    let flow=0;
    for(;;){
      const prev=new Map([[a,null]]),queue=[a];
      while(queue.length&&!prev.has(b)){const u=queue.shift();for(const v of adj.get(u)||[])if(!prev.has(v)&&cap.get(key(u,v))>0){prev.set(v,u);queue.push(v)}}
      if(!prev.has(b))break;
      for(let v=b;prev.get(v)!==null;v=prev.get(v)){const u=prev.get(v);cap.set(key(u,v),cap.get(key(u,v))-1);cap.set(key(v,u),cap.get(key(v,u))+1)}
      flow++;
    }
    const side=new Set([a]),queue=[a];
    while(queue.length){const u=queue.shift();for(const v of adj.get(u)||[])if(!side.has(v)&&cap.get(key(u,v))>0){side.add(v);queue.push(v)}}
    const wires=new Set();for(const arc of g.arcs)if(side.has(arc.from)&&!side.has(arc.to))wires.add(arc.wireId);
    return {ok:true,from:a,to:b,size:flow,wires:[...wires].sort()};
  }
  function boundary(g,componentId){
    const c=g.doc.components.find(x=>x.id===componentId);if(!c)return refusal('UNKNOWN_NODE',`No component ${componentId}`);
    const points=[];
    for(const [portId,port] of Object.entries(c.config?.ports||{}))points.push({componentId,portId,face:port.face||'external',flow:activeConnection(port,portId)?.flow,schema:activeConnection(port,portId)?.schema??port.schema??null,exposed:Data.portExposedCanvasIds(g.doc,componentId,portId)});
    for(const p of g.doc.components)if(p.placement?.kind==='edge'&&p.placement.hostId===componentId)for(const [portId,port] of Object.entries(p.config?.ports||{}))points.push({componentId:p.id,portId,hosted:true,face:port.face||'external',flow:activeConnection(port,portId)?.flow,schema:activeConnection(port,portId)?.schema??port.schema??null,exposed:Data.portExposedCanvasIds(g.doc,p.id,portId)});
    return {ok:true,componentId,points};
  }
  function untyped(g){
    const used=new Set();for(const w of g.doc.wires){if(w.a)used.add(w.a+'.'+w.aSide);if(w.b)used.add(w.b+'.'+w.bSide)}
    const list=[];
    for(const c of g.doc.components)for(const [portId,port] of Object.entries(c.config?.ports||{}))if(used.has(c.id+'.'+portId)&&(activeConnection(port)?.schema??port.schema)==null)list.push({componentId:c.id,portId});
    return {ok:true,points:list};
  }
  function exportGraph(g,format='jgf'){
    const js=junctions(g),jset=new Set(js.map(j=>j.id));
    const nodes=[...g.nodes.values()].map(n=>({id:n.id,label:n.label||n.symbolId,symbolId:n.symbolId,parentId:n.parentId,junction:jset.has(n.id)}));
    const edges=g.arcs.map(a=>({id:`${a.wireId}:${a.from}:${a.to}`,wireId:a.wireId,source:a.from,target:a.to,sourcePort:a.fromPort,targetPort:a.toPort,latencyMs:a.latencyMs,accepts:a.accepts}));
    if(format==='jgf')return {ok:true,format,graph:{graph:{id:g.doc.id,directed:true,label:g.doc.meta?.title||g.doc.id,
      nodes:Object.fromEntries(nodes.map(n=>[n.id,{label:n.label,metadata:{symbolId:n.symbolId,parentId:n.parentId,junction:n.junction}}])),
      edges:edges.map(e=>({source:e.source,target:e.target,directed:true,metadata:{wireId:e.wireId,sourcePort:e.sourcePort,targetPort:e.targetPort,latencyMs:e.latencyMs,accepts:e.accepts}}))}}};
    const esc=s=>String(s).replace(/[&<>"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[ch]);
    if(format==='dot'){
      const q=s=>'"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"')+'"';
      const lines=[`digraph ${q(g.doc.id)} {`,'  rankdir=LR;'];
      for(const n of nodes)lines.push(`  ${q(n.id)} [label=${q(n.label)}${n.junction?', shape=point':''}];`);
      for(const e of edges)lines.push(`  ${q(e.source)} -> ${q(e.target)} [label=${q(e.wireId)}];`);
      lines.push('}');return {ok:true,format,text:lines.join('\n')+'\n'};
    }
    if(format==='graphml'){
      const lines=['<?xml version="1.0" encoding="UTF-8"?>','<graphml xmlns="http://graphml.graphdrawing.org/xmlns">','  <key id="label" for="node" attr.name="label" attr.type="string"/>','  <key id="junction" for="node" attr.name="junction" attr.type="boolean"/>','  <key id="wire" for="edge" attr.name="wire" attr.type="string"/>',`  <graph id="${esc(g.doc.id)}" edgedefault="directed">`];
      for(const n of nodes)lines.push(`    <node id="${esc(n.id)}"><data key="label">${esc(n.label)}</data><data key="junction">${n.junction}</data></node>`);
      for(const e of edges)lines.push(`    <edge id="${esc(e.id)}" source="${esc(e.source)}" target="${esc(e.target)}"><data key="wire">${esc(e.wireId)}</data></edge>`);
      lines.push('  </graph>','</graphml>');return {ok:true,format,text:lines.join('\n')+'\n'};
    }
    return refusal('UNKNOWN_FORMAT',`Unknown export format ${format}; use jgf, dot or graphml`);
  }

  const QUERIES={
    junctions:(g)=>({ok:true,junctions:junctions(g)}),
    reach:(g,a)=>reach(g,a.from,a),
    paths:(g,a)=>paths(g,a.from,a.to,a),
    cycles:(g,a)=>cycles(g,a),
    order:(g)=>order(g),
    cut:(g,a)=>cut(g,a.from,a.to),
    boundary:(g,a)=>boundary(g,a.componentId),
    untyped:(g)=>untyped(g),
    blocked:(g)=>({ok:true,blocked:g.blocked}),
    acl:(g,a)=>{
      if(a.componentId&&a.op){const plane=g.nodes.get(a.componentId);if(!plane)return refusal('UNKNOWN_NODE',`No component ${a.componentId}`);if(!ACL_OPS.includes(a.op))return refusal('UNKNOWN_OP',`op is one of ${ACL_OPS.join(', ')}`);return {ok:true,componentId:a.componentId,principal:a.principal??null,op:a.op,...aclDecide(plane,a.principal,a.op)}}
      return {ok:true,planes:[...g.nodes.values()].filter(n=>n.acl).map(n=>({id:n.id,label:n.label,acl:n.acl})),principals:[...g.nodes.values()].filter(n=>n.principal).map(n=>({id:n.id,principal:n.principal}))};
    },
    signals:(g)=>({ok:true,signals:[...g.nodes.values()].map(n=>({id:n.id,label:n.label,mode:n.signal.mode,kind:n.signal.kind,combine:n.signal.mode==='derived'?n.signal.combine:null,value:n.signal.mode==='asserted'?n.signal.value:null,clock:n.signal.clock,on:n.signal.on,emits:n.signal.emits,declared:n.signal.declared}))}),
    export:(g,a)=>exportGraph(g,a.format||'jgf')
  };
  function query(doc,verb,args={}){
    const fn=QUERIES[verb];if(!fn)return refusal('UNKNOWN_QUERY',`Unknown graph query ${verb}`,{verbs:Object.keys(QUERIES)});
    return fn(build(doc),isObject(args)?args:{});
  }

  // ---- One runtime (contract 09 of the one-runtime plan): createSimulation, runScenario,
  // createSession and tools delegate to SovSchematicSimSurface (src/07-state-surface.js, over
  // the state-space engine) so callers and suites keep their names. The message engine and its
  // helpers (callHandler, createSimulation, runScenario, createSession, tools, scenariosOf,
  // readPath, fnv, the COMBINE table, waveAt, nextClockTime) lived here through contract 09 at
  // 7b939e3; contract 10 deleted them. See docs/residuals/2026-09-26-one-runtime.md.
  const createSimulation=(...a)=>surface().createSimulation(...a);
  const runScenario=(...a)=>surface().runScenario(...a);
  const createSession=(...a)=>surface().createSession(...a);
  const tools=(...a)=>surface().tools(...a);

  return {POLICIES,DEFAULT_LATENCY_MS,COMBINES,signalConfig,activeConnection,canEmit,canReceive,accessAllows,build,query,queries:Object.keys(QUERIES),createSimulation,runScenario,createSession,tools,aclConfig,aclDecide,crossingAt};
});
