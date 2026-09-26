'use strict';
// Logic runtime shared by the editor and Node: a document as a circuit, run by events.
// A port of scripts/logic_sov.py, kept equal to it event for event (tests/logic_core_parity_qa.py):
// the same flattening of composites, net numbering, (time, sequence) event order, power-on
// rule and refusals. No DOM. Composites are resolved by a caller-supplied `resolve(name, from)`
// returning {key, document} or null, so the editor and a file system both fit.
(function(root,factory){
  const api=factory();
  root.SovSchematicLogic=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  const PACK_SCHEMA='soveraeign.schematic/logic-pack@0.0-draft';
  const KINDS=['table','sequential','threshold','compare','hysteresis'];
  const LEVEL_KINDS=new Set(['threshold','compare','hysteresis']);

  class LogicRefusal extends Error{
    constructor(code,reason,next=''){super(`${code}: ${reason}`);this.code=code;this.reason=reason;this.next_operation=next}
    asDict(){return {refused:this.code,reason:this.reason,next_operation:this.next_operation}}
  }
  const refuse=(code,reason,next='')=>{throw new LogicRefusal(code,reason,next)};

  // ------------------------------------------------------------------ the pack

  function rows(name,list,nKey,nVal,what){
    const table=new Map();
    for(const row of list){
      const i=row.indexOf(':'),key=(i<0?row:row.slice(0,i)).split('|').join(''),val=i<0?'':row.slice(i+1);
      if(key.length!==nKey||val.length!==nVal||/[^01]/.test(key+val))refuse('BAD_ROW',`gate ${name}: ${what} row '${row}' does not fit ${nKey} bits in and ${nVal} out`);
      if(table.has(key))refuse('DUPLICATE_ROW',`gate ${name}: ${what} key '${key}' appears twice`);
      table.set(key,[...val].map(Number));
    }
    if(table.size!==2**nKey)refuse('INCOMPLETE_TABLE',`gate ${name}: ${table.size} ${what} rows for ${nKey} bits; a table must say what happens for all ${2**nKey}`);
    return table;
  }
  function loadPack(pack){
    if(pack?.schema!==PACK_SCHEMA)refuse('SCHEMA',`expected ${PACK_SCHEMA}, found ${JSON.stringify(pack?.schema)}`);
    const gates={};
    for(const [name,g] of Object.entries(pack.gates)){
      const kind=g.kind||'table';
      if(!KINDS.includes(kind))refuse('UNKNOWN_KIND',`gate ${name}: kind '${kind}'; expected one of ${KINDS.join(', ')}`);
      const ins=[...g.inputs],outs=[...g.outputs];
      const gate={kind,inputs:ins,outputs:outs,params:{...(g.params||{})},delay:Math.trunc(Number(g.delay??pack.default_delay??1))};
      if(kind==='table')gate.table=rows(name,g.table,ins.length,outs.length,'truth');
      else if(kind==='sequential'){
        const state=[...g.state],clock=g.clock??null;
        if(clock!==null&&!ins.includes(clock))refuse('BAD_CLOCK',`gate ${name}: clock '${clock}' is not one of its inputs`);
        const data=ins.filter(p=>p!==clock);
        Object.assign(gate,{state,clock,edge:g.edge||'rising',data,
          next:rows(name,g.next,state.length+data.length,state.length,'next-state'),
          out:rows(name,g.output,state.length,outs.length,'output'),
          initial:[...(g.initial??'0'.repeat(state.length))].map(Number)});
      }else if(kind==='hysteresis')gate.initial=[Number(g.initial??'0')];
      gates[name]=gate;
    }
    return gates;
  }
  function resolveParams(name,gate,logic){
    const params={...gate.params};
    for(const k of Object.keys(logic))if(k in gate.params)params[k]=logic[k];
    if(gate.kind==='threshold'&&(params.weights||[]).length!==gate.inputs.length)refuse('BAD_PARAMS',`${name}: ${(params.weights||[]).length} weights for ${gate.inputs.length} inputs`);
    if(gate.kind==='hysteresis'&&!(Number(params.low)<=Number(params.high)))refuse('BAD_PARAMS',`${name}: low ${params.low} is above high ${params.high}; the band would be empty`,'set low <= high (equal makes a plain comparator)');
    return params;
  }
  function resting(g,values){
    const kind=g.def.kind;
    if(kind==='sequential')return [...g.def.out.get(g.state.join(''))];
    if(kind==='hysteresis')return [g.state[0],1-g.state[0]];
    return evaluate(g,values);
  }
  function evaluate(g,values){
    const d=g.def,kind=d.kind;
    if(kind==='table')return [...d.table.get(values.map(String).join(''))];
    if(kind==='threshold'){let s=0;g.params.weights.forEach((w,i)=>{if(i<values.length)s+=w*values[i]});return [Number(s>=g.params.theta)]}
    if(kind==='compare')return [Number(values[0]>=g.params.theta)];
    if(kind==='hysteresis'){
      const x=values[0];
      if(x>=g.params.high)g.state=[1];else if(x<=g.params.low)g.state=[0];
      return [g.state[0],1-g.state[0]];
    }
    const named=Object.fromEntries(d.inputs.map((p,i)=>[p,values[i]]));
    let step=true;
    if(d.clock!==null){
      const now=named[d.clock],before=g.prevClock;g.prevClock=now;
      step=d.edge==='rising'?(before===0&&now===1):(before===1&&now===0);
    }
    if(step)g.state=[...d.next.get(g.state.join('')+d.data.map(p=>String(named[p])).join(''))];
    return [...d.out.get(g.state.join(''))];
  }

  // ------------------------------------------------------------------ flattening

  // A terminal is (component id, pin); ordered as Python orders the tuple.
  const T=(id,pin)=>id+'\u0000'+pin;
  const split=t=>{const i=t.indexOf('\u0000');return [t.slice(0,i),t.slice(i+1)]};
  const cmp=(a,b)=>{const [a0,a1]=split(a),[b0,b1]=split(b);return a0<b0?-1:a0>b0?1:a1<b1?-1:a1>b1?1:0};
  class Nets{
    constructor(){this.parent=new Map()}
    find(t){if(!this.parent.has(t))this.parent.set(t,t);while(this.parent.get(t)!==t){this.parent.set(t,this.parent.get(this.parent.get(t)));t=this.parent.get(t)}return t}
    join(a,b){const ra=this.find(a),rb=this.find(b);if(ra!==rb){const lo=cmp(ra,rb)<0?ra:rb,hi=lo===ra?rb:ra;this.parent.set(hi,lo)}}
  }
  function pinsOfDocument(doc){
    const ins=[],outs=[];
    for(const c of doc?.components||[]){const l=(c.config||{}).logic||{};if(l.kind==='input')ins.push(l.name);else if(l.kind==='output')outs.push(l.name)}
    return [ins,outs];
  }
  const baseName=key=>String(key).split(/[\\/]/).pop();

  // A min-heap of events ordered by (time, sequence).
  class Heap{
    constructor(){this.a=[]}
    get size(){return this.a.length}
    peek(){return this.a[0]}
    less(x,y){return x[0]<y[0]||(x[0]===y[0]&&x[1]<y[1])}
    push(v){const a=this.a;a.push(v);let i=a.length-1;while(i>0){const p=(i-1)>>1;if(!this.less(a[i],a[p]))break;[a[i],a[p]]=[a[p],a[i]];i=p}}
    pop(){const a=this.a,top=a[0],last=a.pop();if(a.length){a[0]=last;let i=0;for(;;){const l=2*i+1,r=l+1;let m=i;if(l<a.length&&this.less(a[l],a[m]))m=l;if(r<a.length&&this.less(a[r],a[m]))m=r;if(m===i)break;[a[i],a[m]]=[a[m],a[i]];i=m}}return top}
  }

  class Circuit{
    // `document` is the top document; `key` names it for composite resolution and messages.
    constructor(document,{pack,resolve=()=>null,key='document.sov',eventBudget=200000}={}){
      if(!pack)refuse('NO_PACK','a circuit needs the logic pack');
      this.pack=pack;this.key=key;this.resolve=resolve;this.eventBudget=eventBudget;
      this.nets=new Nets();this.gates=[];this.inputs=new Map();this.outputs=new Map();this.drivers=new Map();this.levels=new Map();
      this.addDocument(document,key,'',[],true);
      this.finish();
    }
    addDocument(doc,key,prefix,stack,top){
      if(stack.includes(key))refuse('COMPOSITE_CYCLE',[...stack,key].map(baseName).join(' -> ')+' uses itself');
      if(!doc)refuse('NO_COMPOSITE',`${baseName(key)} does not exist`,`open it beside ${baseName(stack[stack.length-1]||this.key)}, or add it with logic.composites.add(name, document)`);
      stack=[...stack,key];
      const pins=new Map(),points=new Set();
      for(const c of doc.components||[]){
        const cid=prefix+c.id,cfg=c.config||{},logic=cfg.logic;
        const declared=new Set((cfg.attachmentPoints||[]).filter(p=>p&&typeof p==='object').map(p=>p.id));
        if(c.symbolId==='point'){points.add(cid);continue}
        if(!logic)continue;
        if(logic.kind==='input'){
          pins.set(logic.name,T(cid,'out'));
          if(top){this.inputs.set(logic.name,T(cid,'out'));this.levels.set(logic.name,(logic.type||'bit')==='level');this.addDriver(T(cid,'out'),`input ${logic.name}`)}
        }else if(logic.kind==='output'){
          pins.set(logic.name,T(cid,'in'));
          if(top)this.outputs.set(logic.name,T(cid,'in'));
        }else if('gate' in logic){
          const name=logic.gate;
          if(!(name in this.pack))refuse('UNKNOWN_GATE',`${cid} names gate '${name}', which the pack does not define`,`add ${name} to packs/logic/gates.json or use one of: ${Object.keys(this.pack).sort().join(', ')}`);
          const g=this.pack[name],missing=[...g.inputs,...g.outputs].filter(p=>!declared.has(p));
          if(missing.length)refuse('MISSING_PIN',`${cid} is a ${name} gate but declares no attachment point for ${missing.join(', ')}`,`add config.attachmentPoints with ids ${JSON.stringify(missing)}`);
          const gate={id:cid,gate:name,def:g,ins:g.inputs.map(p=>T(cid,p)),outs:g.outputs.map(p=>T(cid,p)),delay:Math.trunc(Number(logic.delay??g.delay)),
            params:resolveParams(cid,g,logic),state:g.initial?[...g.initial]:[],prevClock:0};
          this.gates.push(gate);
          for(const t of gate.outs)this.addDriver(t,`${name} ${cid}`);
        }else if('composite' in logic){
          const found=this.resolve(logic.composite,key);
          const [ins,outs]=pinsOfDocument(found?.document);
          const missing=[...ins,...outs].filter(p=>!declared.has(p));
          if(found&&missing.length)refuse('MISSING_PIN',`${cid} uses ${logic.composite} but declares no attachment point for ${missing.join(', ')}`,`add config.attachmentPoints with ids ${JSON.stringify(missing)}`);
          const inner=this.addDocument(found?.document,found?.key??logic.composite,cid+'.',stack,false);
          for(const [name,terminal] of inner)this.nets.join(T(cid,name),terminal);
        }else refuse('UNKNOWN_LOGIC',`${cid} has logic ${JSON.stringify(logic)}; expected kind input/output, gate or composite`);
      }
      for(const w of doc.wires||[]){
        const a=T(prefix+w.a,points.has(prefix+w.a)?'out':w.aSide),b=T(prefix+w.b,points.has(prefix+w.b)?'out':w.bSide);
        this.nets.join(a,b);
      }
      return pins;
    }
    addDriver(t,who){if(!this.drivers.has(t))this.drivers.set(t,[]);this.drivers.get(t).push(who)}
    finish(){
      this.netOf=new Map();const roots=new Map();
      const all=[...this.nets.parent.keys(),...this.gates.flatMap(g=>[...g.ins,...g.outs]),...this.inputs.values(),...this.outputs.values()];
      for(const t of all){const r=this.nets.find(t);if(!roots.has(r))roots.set(r,roots.size);this.netOf.set(t,roots.get(r))}
      this.nNets=roots.size;
      this.netNames=new Map();
      for(const t of [...this.netOf.keys()].sort(cmp)){const i=this.netOf.get(t);if(!this.netNames.has(i))this.netNames.set(i,split(t).join('.'))}
      const driven=new Map();
      for(const [t,who] of this.drivers){const n=this.netOf.get(t);if(!driven.has(n))driven.set(n,[]);driven.get(n).push(...who)}
      for(const [net,who] of driven)if(who.length>1)refuse('MULTIPLE_DRIVERS',`net ${this.netNames.get(net)} is driven by ${who.join(' and ')}`,'give each output its own net');
      const loads=[...this.gates.flatMap(g=>g.ins.map(t=>[g.id,t])),...[...this.outputs].map(([n,t])=>[`output ${n}`,t])];
      for(const [who,t] of loads)if(!driven.has(this.netOf.get(t)))refuse('UNDRIVEN',`${who} reads ${split(t).join('.')}, which nothing drives`,'wire an input, a gate output or a constant (true/false) to it');
      const levelNets=new Set([...this.inputs].filter(([n])=>this.levels.get(n)).map(([,t])=>this.netOf.get(t)));
      for(const g of this.gates){
        if(LEVEL_KINDS.has(g.def.kind))continue;
        for(const t of g.ins)if(levelNets.has(this.netOf.get(t)))refuse('LEVEL_INTO_BINARY',`${g.id} (${g.gate}) reads a level on ${split(t)[1]}; ${g.gate} takes bits`,'put a compare or hysteresis gate between them');
      }
      this.fanout=new Map();
      this.gates.forEach((g,gi)=>{
        g.inNets=g.ins.map(t=>this.netOf.get(t));g.outNets=g.outs.map(t=>this.netOf.get(t));
        for(const n of new Set(g.inNets)){if(!this.fanout.has(n))this.fanout.set(n,[]);this.fanout.get(n).push(gi)}
      });
      this.value=new Array(this.nNets).fill(0);
      this.powerOn();
      this.time=0;this.sequence=0;this.started=false;this.events=[];
    }
    powerOn(){
      for(const g of this.gates)if(g.def.kind==='sequential'||g.def.kind==='hysteresis'||!g.inNets.length)
        resting(g,g.inNets.map(n=>this.value[n])).forEach((out,i)=>{this.value[g.outNets[i]]=out});
      for(const g of this.gates){const clock=g.def.clock;if(clock!=null)g.prevClock=this.value[g.inNets[g.def.inputs.indexOf(clock)]]}
    }
    apply(vector,{record=false}={}){
      for(const [name,v] of Object.entries(vector)){
        if(!this.inputs.has(name))refuse('UNKNOWN_INPUT',`'${name}' is not an input of ${baseName(this.key)}; inputs are ${[...this.inputs.keys()].sort().join(', ')}`);
        if(!this.levels.get(name)&&v!==0&&v!==1)refuse('NOT_A_BIT',`${name}=${v}: ${name} is a bit input`,`declare ${name} "type": "level"`);
      }
      const queue=new Heap(),pending=new Map(),start=this.time;
      const schedule=(t,net,value,cause)=>{this.sequence+=1;queue.push([t,this.sequence,net,value,cause]);pending.set(net,value)};
      for(const name of Object.keys(vector).sort()){
        const net=this.netOf.get(this.inputs.get(name)),v=Number(vector[name]);
        if(this.value[net]!==v||!this.started)schedule(this.time,net,v,`input ${name}`);
      }
      let toEval=new Set(this.started?[]:this.gates.map((_,i)=>i));
      this.started=true;
      let transitions=0,seen=0,lastChange=start;const toggles=new Map();
      while(queue.size||toEval.size){
        if(toEval.size&&(!queue.size||queue.peek()[0]>this.time)){
          for(const gi of [...toEval].sort((a,b)=>a-b)){
            const g=this.gates[gi];
            evaluate(g,g.inNets.map(n=>this.value[n])).forEach((out,i)=>{
              const net=g.outNets[i],now=pending.has(net)?pending.get(net):this.value[net];
              if(now!==out)schedule(this.time+g.delay,net,out,g.id);
            });
          }
          toEval=new Set();continue;
        }
        const [t,,net,value,cause]=queue.pop();
        this.time=t;
        if(pending.get(net)===value&&!queue.a.some(q=>q[2]===net))pending.delete(net);
        seen+=1;
        if(seen>this.eventBudget){
          const busy=[...toggles.keys()].filter(n=>toggles.get(n)>2).sort((a,b)=>toggles.get(b)-toggles.get(a)||(this.netNames.get(a)<this.netNames.get(b)?-1:this.netNames.get(a)>this.netNames.get(b)?1:0)).slice(0,6);
          refuse('UNSETTLED',`${baseName(this.key)} did not settle within ${this.eventBudget} events; still changing: ${busy.map(n=>this.netNames.get(n)).join(', ')}`,'break the feedback loop, or drive a latch out of its forbidden state one input at a time');
        }
        if(this.value[net]===value)continue;
        this.value[net]=value;transitions+=1;toggles.set(net,(toggles.get(net)||0)+1);lastChange=t;
        if(record)this.events.push({t,seq:this.sequence,net:this.netNames.get(net),value,cause});
        for(const gi of this.fanout.get(net)||[])toEval.add(gi);
      }
      const outputs={};for(const name of [...this.outputs.keys()].sort())outputs[name]=this.value[this.netOf.get(this.outputs.get(name))];
      return {outputs,settle:lastChange-start,transitions,time:this.time};
    }
    pulse(clock,vector={}){
      const first=this.apply(vector),rise=this.apply({[clock]:1}),fall=this.apply({[clock]:0});
      return {outputs:fall.outputs,settle:rise.settle,transitions:first.transitions+rise.transitions+fall.transitions,time:this.time};
    }
    truthTable(){
      const names=[...this.inputs.keys()].sort(),out=[];
      for(let m=0;m<2**names.length;m++){
        const inputs={};names.forEach((n,i)=>{inputs[n]=(m>>(names.length-1-i))&1});
        out.push({inputs,...this.apply(inputs)});
      }
      return out;
    }
    // The value on the net at a terminal of the top document, or null when the circuit has no such terminal.
    valueAt(id,pin){const n=this.netOf.get(T(id,pin));return n===undefined?null:this.value[n]}
    // Each top-level wire's net value and the pins at its ends (what export_svg's logic_state gives).
    wireState(doc){
      const points=new Set((doc.components||[]).filter(c=>c.symbolId==='point').map(c=>c.id)),wires={};
      for(const w of doc.wires||[]){
        const aPin=points.has(w.a)?'out':w.aSide,bPin=points.has(w.b)?'out':w.bSide,value=this.valueAt(w.a,aPin);
        if(value===null)continue;
        wires[w.id]={value,a:`${w.a}.${aPin}`,b:`${w.b}.${bPin}`};
      }
      return wires;
    }
  }
  // Is this document a logic circuit at all (any component declaring config.logic)?
  const isLogicDocument=doc=>(doc?.components||[]).some(c=>c?.config?.logic);
  // One stateless run, the shape the editor API (logic.run) and MCP (schematic.logic.run) share:
  // {steps: [{set: {...}, pulse?: 'CLK'}], record?} -> per step outputs, settle, transitions and
  // time; then every top-level wire's value and, with record, every event. `vector` alone is
  // one step. Inputs a step does not name keep their value; before the first step every net is 0.
  function run(document,request={},options={}){
    try{
      if(!isLogicDocument(document))refuse('NOT_LOGIC','the document declares no config.logic on any component','open a logic document, e.g. examples/logic/half-adder.sov');
      const steps=Array.isArray(request.steps)?request.steps:[{set:request.vector||{}}];
      const c=new Circuit(document,options),record=!!request.record,out=[];
      for(const step of steps){
        if(!step||typeof step!=='object')refuse('BAD_STEP','each step is an object {set, pulse?}');
        const r=step.pulse?c.pulse(String(step.pulse),step.set||{}):c.apply(step.set||{},{record});
        out.push({set:step.set||{},...(step.pulse?{pulse:step.pulse}:{}),...r});
      }
      return {ok:true,inputs:[...c.inputs.keys()].sort(),levels:[...c.levels].filter(([,v])=>v).map(([k])=>k).sort(),
        outputs:[...c.outputs.keys()].sort(),steps:out,wires:c.wireState(document),...(record?{events:c.events}:{})};
    }catch(e){
      if(e instanceof LogicRefusal)return {ok:false,...e.asDict()};
      throw e;
    }
  }
  return {PACK_SCHEMA,LogicRefusal,loadPack,Circuit,isLogicDocument,run};
});
