'use strict';
// The sim surface (contract 08 of the one-runtime plan): dev's simulation API (src/07-graph-core.js
// at 7b939e3, createSimulation, runScenario, createSession and tools) over one state-space run.
// Time is in milliseconds here and in ticks in the run; every step is the engine's step, every input
// the engine's addInput, resume or reconcile, and every view is read from the run's records and
// ledger. Nothing in the engine is changed or reached past its exports; the run stays plain JSON.
(function(root,factory){
  let S=root.SovSchematicStateSpace,Data=root.SovSchematicData,Canonical=root.SovSchematicCanonical,nodePacks=null,graph=()=>root.SovSchematicGraph;
  if(typeof module!=='undefined'&&module.exports){
    if(!Canonical)Canonical=require('./03-canonical.js');
    if(!Data){require('./06-attachment-core.js');Data=require('./05-data-core.js')}
    if(!S)S=require('./07-state-space.js');
    // Under node the packs are data/*.pack.json beside this module, in file-name order, as mcp/server.mjs reads them.
    nodePacks=()=>{const fs=require('fs'),path=require('path'),dir=path.join(__dirname,'..','data');
      return fs.readdirSync(dir).filter(n=>n.endsWith('.pack.json')).sort().map(n=>JSON.parse(fs.readFileSync(path.join(dir,n),'utf8')))};
    graph=()=>root.SovSchematicGraph||require('./07-graph-core.js');
  }
  const api=factory(S,Data,Canonical,nodePacks,graph);
  root.SovSchematicSimSurface=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(S,Data,Canonical,nodePacks,graph){
  if(!S)throw new Error('SovSchematicStateSpace (src/07-state-space.js) is required');
  if(!Data)throw new Error('SovSchematicData core is required');
  if(!Canonical)throw new Error('SovSchematicCanonical core is required');
  const clone=v=>v==null?v:JSON.parse(JSON.stringify(v));
  const isObject=v=>!!v&&typeof v==='object'&&!Array.isArray(v);
  function refusal(code,message,extra={}){return {ok:false,code,message,...extra}}
  // A continuous level in a record is an integer 0..LEVEL, the engine's fixed point (2^20, see
  // src/07-state-space.js "No floating point in a run"); a binary one is a boolean. Views give dev's 0..1.
  const LEVEL=1<<20;
  const levelValue=v=>v===true?1:v===false||v==null?0:typeof v==='number'?v/LEVEL:0;
  // A surface run is never stopped by the engine's event budget: maxEvents, until and advance bound it.
  const BUDGET=Number.MAX_SAFE_INTEGER;
  const MESSAGE='message';

  // Packs: options.packs when given; under node data/*.pack.json; in the browser the build's sov-packs tag.
  function defaultPacks(){
    if(nodePacks)return nodePacks();
    const tag=typeof document!=='undefined'&&document.getElementById?document.getElementById('sov-packs'):null;
    if(!tag)return [];
    try{return JSON.parse(tag.textContent||'[]')}catch(_){return []}
  }
  function loadPacks(raw){
    const out=[],errors=[];
    for(const p of Array.isArray(raw)?raw:[]){const r=S.loadPack(p);if(r.ok)out.push(r.pack);else errors.push(...r.errors)}
    return {packs:out,errors};
  }

  // The tick a run takes next, as the engine's nextTick reads it: tick 0 before the first, else the
  // earliest pending item or queue head; null when nothing is due.
  function nextTick(run){
    let t=run.tick===null?0:null;
    for(const item of run.pending)if(t===null||item.at<t)t=item.at;
    for(const q of Object.values(run.queues||{}))if(S.queueItems(q).length&&(t===null||q.next<t))t=q.next;
    return t;
  }
  const pendingCount=run=>run.pending.length+Object.values(run.queues||{}).reduce((n,q)=>n+S.queueItems(q).length,0);
  const ceilDiv=(a,b)=>Math.ceil(Math.max(0,Number(a)||0)/b);

  // CLOCK_HAS_NO_PERIOD, checked before the run starts (7b939e3 lines 290-292): a declared clock
  // needs periodMs above 0, and a clock card needs a declared clock.
  function clockRefusal(doc){
    for(const c of doc.components||[]){
      const clock=isObject(c.config?.signal)&&isObject(c.config.signal.clock)?c.config.signal.clock:null;
      if((clock&&!(Number(clock.periodMs)>0))||(c.symbolId==='clock'&&!clock))return refusal('CLOCK_HAS_NO_PERIOD',`Clock ${c.config?.label||c.id} needs config.signal.clock.periodMs above 0`,{node:c.id});
    }
    return null;
  }

  // createSimulation(doc, {handlers, effects, restore, packs, tickMs, seed}): seed is the run's
  // merge-draw seed (default '0', the engine's), so a caller can see both outcomes of a recorded draw.
  function createSimulation(input,options={}){
    const o=isObject(options)?options:{};
    let doc;
    try{doc=Data.makeDocument(clone(input||{}))}catch(e){return refusal('DOCUMENT_INVALID',String(e?.message||e))}
    const noPeriod=clockRefusal(doc);if(noPeriod)return noPeriod;
    const loaded=loadPacks(o.packs!==undefined?o.packs:defaultPacks());
    if(loaded.errors.length)return refusal('PACK_INVALID',`the packs do not load: ${loaded.errors.map(e=>`${e.subject}: ${e.message}`).join('; ')}`,{refusals:loaded.errors});
    const packs=loaded.packs,handlers=Object.assign({},o.handlers||{});
    const metaTick=Number(doc.meta?.tickMs);
    const tickMs=o.tickMs!==undefined?o.tickMs:(Number.isSafeInteger(metaTick)&&metaTick>0?metaTick:undefined);
    const restored=isObject(o.restore)&&isObject(o.restore.run);
    // Inputs given before the first tick are the run's start inputs: the run is started again with
    // them, so an explicit set at tick 0 replaces the declared starting level instead of colliding with it.
    let startInputs=restored?clone(o.restore.startInputs||[]):[];
    const internal=new Set(restored?o.restore.internal||[]:[]);
    let time=restored?Number(o.restore.time)||0:0;
    const start=()=>{
      const r=S.startRun({doc,packs,handlers,inputs:startInputs,budget:BUDGET,...(tickMs!==undefined?{tickMs}:{}),...(o.seed!==undefined?{seed:o.seed}:{}),...(isObject(o.effects)?{effects:clone(o.effects)}:{})});
      if(!r.ok&&r.code==='ZERO_DELAY_CYCLE')return refusal('ZERO_LATENCY_CYCLE','A message cycle must take time: give a wire latencyMs above 0 or pass through a buffer or hold',{cycles:r.cycles});
      return r;
    };
    let run;
    if(restored)run=clone(o.restore.run);
    else{const r=start();if(!r.ok)return r;run=r.run}
    const TICK=run.tickMs;
    const tickAt=ms=>ceilDiv(ms,TICK);

    // One input: before the first tick it joins the start inputs (the run is started again); after
    // it, the engine's addInput. Returns {ok, seq} with the input's ledger seq, or the refusal.
    function give(x){
      if(run.tick===null){
        const trial=[...startInputs,x];
        const before=startInputs;startInputs=trial;
        const r=start();
        if(!r.ok){startInputs=before;return r}
        run=r.run;
        const body=Canonical.canonicalize(x);
        // The seq of this input's entry: the last entry equal to it (equal inputs are interchangeable).
        let seq=null;for(const e of run.ledger)if(e.kind==='input'&&Canonical.canonicalize(e.body)===body)seq=e.seq;
        return {ok:true,seq};
      }
      return S.addInput(run,x);
    }
    const componentOf=id=>run.doc.components.find(c=>c.id===id)||null;
    // The port a message is put in at: out, else the first port that emits, else the first.
    function portOf(id){
      let specs=[];try{specs=Data.canonicalAttachmentPointDescriptors(componentOf(id)).filter(Boolean)}catch(_){specs=[]}
      const flow=s=>s.flow||s.defaultFlow||'duplex';
      const pick=specs.find(s=>s.id==='out')||specs.find(s=>['out','duplex'].includes(flow(s)))||specs[0];
      return pick?pick.id:null;
    }

    // ---- Views, read from the run's records and ledger, cached until the run moves.
    let cache=null;
    function views(){
      const key=`${run.records.length}:${run.ledger.length}:${internal.size}:${run.tick}`;
      if(cache&&cache.key===key)return cache;
      const v={key,messages:new Map(),order:[],log:[],refusals:[],receipts:[],series:{},edges:[],level:{}};
      // The point whose records are a node's level: a device's first output, an asserted card's first out, any port of a Point.
      const levelPoint={};
      for(const [id,c] of Object.entries(run.components)){
        if(c.role==='device'&&c.outputs?.length)levelPoint[id]=c.outputs[0];
        else if(c.asserted?.outs?.length)levelPoint[id]=c.asserted.outs[0];
        else if(c.role==='point')levelPoint[id]='*';
      }
      const causeOf=rule=>rule==='input'?'set':rule==='clock'?'clock':rule==='asserted'?'message':'derived';
      // Ledger entries (resume, reconcile) are logged after the records of the tick they follow.
      const ledgerEvents=[];
      for(const e of run.ledger){
        if(e.kind==='reconcile')ledgerEvents.push({after:e.body.after,event:{event:'effect-reconciled',effectKey:e.body.effectKey,confirmed:!!e.body.confirmed}});
        if(e.kind==='resume')ledgerEvents.push({after:e.body.after,resume:e.body});
      }
      let li=0;
      const parkedAt={};
      const flushLedger=t=>{
        while(li<ledgerEvents.length&&(ledgerEvents[li].after===null||t===null||ledgerEvents[li].after<t)){
          const x=ledgerEvents[li++],at=x.after===null?0:x.after*TICK;
          if(x.event)v.log.push({at,...x.event});
          else{const p=parkedAt[x.resume.parkId]||{};v.log.push({at,event:'resumed',node:p.node??null,messageId:p.messageId??null,parkId:x.resume.parkId,decision:x.resume.decision})}
        }
      };
      // A clock with cycles that has nothing more scheduled has stopped, after its last record.
      const stopped={};
      for(const [k,src] of Object.entries(run.clocks||{})){
        if(!src.clock.cycles)continue;
        if(run.pending.some(p=>p.kind==='clock'&&p.entity===src.entity&&p.point===src.point))continue;
        stopped[`${src.entity}\u0000${src.point}`]=src.entity;
      }
      const lastClockRecord={};
      run.records.forEach((r,i)=>{const s=r.subject;if(r.provenance.rule==='clock'&&stopped[`${s.entity}\u0000${s.point}`])lastClockRecord[`${s.entity}\u0000${s.point}`]=i});
      const stopAfter=new Map(Object.entries(lastClockRecord).map(([k,i])=>[i,stopped[k]]));
      run.records.forEach((r,i)=>{
        const s=r.subject,t=r.time.logical,at=t*TICK;
        flushLedger(t);
        if(r.form==='message'){
          const m=r.value;if(internal.has(m.root))return;
          let msg=v.messages.get(m.id);
          if(!msg){msg={id:m.id,root:m.root,parent:m.parent,principal:r.principal??null,channel:m.channel,payload:clone(m.payload),origin:m.origin,at,status:'live',hops:[]};v.messages.set(m.id,msg);v.order.push(m.id)}
          msg.payload=clone(m.payload);msg.channel=m.channel;if(r.principal!=null)msg.principal=r.principal;
          if(r.observable==='receipt'){v.receipts.push({at,kind:'receipt',node:s.entity,messageId:m.id,root:m.root,channel:m.channel,payload:clone(m.payload)});return}
          const h=r.hop;if(!h)return;
          const hop={at,node:s.entity,event:h.event};
          if(h.wire)hop.wireId=h.wire;if(h.to)hop.to=h.to;if(h.reason)hop.reason=h.reason;if(h.parkId)hop.parkId=h.parkId;if(h.effectKey)hop.effectKey=h.effectKey;
          if(h.event==='arrived')hop.port=s.point;
          msg.hops.push(hop);
          msg.status=['injected','arrived','sent','crossed','released','resumed','edge'].includes(h.event)?'live':h.event==='waiting'?'joined':h.event;
          const base={messageId:m.id,node:s.entity};
          switch(h.event){
            case 'injected':v.log.push({at,event:'injected',messageId:m.id,node:s.entity,channel:m.channel});break;
            case 'sent':v.log.push({at,event:'sent',messageId:m.id,from:s.entity,to:h.to,wireId:h.wire});break;
            case 'arrived':v.log.push({at,event:'arrived',messageId:m.id,node:s.entity,port:s.point,wireId:h.wire});break;
            case 'refused':v.log.push({at,event:'refused',...base,reason:h.reason});v.refusals.push({at,messageId:m.id,root:m.root,node:s.entity,reason:h.reason});break;
            case 'delivered':case 'absorbed':case 'asserted':v.log.push({at,event:h.event,...base});break;
            case 'observed':v.log.push({at,event:'observed',...base});v.receipts.push({at,kind:'observation',node:s.entity,messageId:m.id,root:m.root,channel:m.channel,payload:clone(m.payload)});break;
            case 'controlled':{const open=isObject(m.payload)&&'open' in m.payload?!!m.payload.open:true;v.log.push({at,event:'controlled',...base},{at,event:'control',node:s.entity,open});break}
            case 'edge':v.log.push({at,event:'edge-message',...base,polarity:m.payload?.polarity});break;
            case 'replayed':v.log.push({at,event:'effect-replayed',...base,effectKey:h.effectKey});break;
            case 'handled':if(h.effectKey)v.log.push({at,event:'effect-confirmed',...base,effectKey:h.effectKey});break;
            case 'ambiguous':v.log.push({at,event:'effect-ambiguous',...base,effectKey:h.effectKey,error:h.reason});break;
            case 'parked':parkedAt[h.parkId]={node:s.entity,messageId:m.id};v.log.push({at,event:'parked',...base,parkId:h.parkId});break;
            case 'released':v.log.push({at,event:'released',...base});break;
            case 'joined':v.log.push({at,event:'joined',...base,from:r.provenance.inputs.length?[m.parent]:[]});break;
            default:break;
          }
          return;
        }
        if(r.level===true){v.refusals.push({at,level:true,node:s.entity,reason:r.value});v.log.push({at,event:'refused',node:s.entity,reason:r.value,level:true});return}
        if(r.form!=='binary'&&r.form!=='continuous')return;
        if(s.channel===MESSAGE||r.provenance.rule==='overridden')return;
        const lp=levelPoint[s.entity];
        if(lp===undefined||(lp!=='*'&&lp!==s.point))return;
        const value=levelValue(r.value),old=v.level[s.entity]??0;
        if(value!==old){
          const polarity=value>old?'+':'-',edge={at,node:s.entity,from:old,to:value,polarity,cause:causeOf(r.provenance.rule)};
          v.edges.push(edge);v.log.push({at,event:'edge',node:s.entity,from:old,to:value,polarity,cause:edge.cause});
        }
        v.level[s.entity]=value;
        if(stopAfter.has(i))v.log.push({at,event:'clock-stopped',node:stopAfter.get(i)});
      });
      flushLedger(null);
      cache=v;return v;
    }
    const kindOf=id=>{const c=run.components[id]||{};if(c.asserted)return c.asserted.kind;if(c.role==='device'&&c.combine)return run.definitions[c.definition]?.parameters?.kind||'binary';return 'binary'};
    const modeOf=id=>run.components[id]?.asserted?'asserted':'derived';
    const msOf=t=>t==null?t:t*TICK;
    const effectView=e=>({...clone(e),...(e.at!=null?{at:msOf(e.at)}:{}),...(e.confirmedAt!=null?{confirmedAt:msOf(e.confirmedAt)}:{})});
    const progress=(processed,extra={})=>({ok:true,processed,time,pending:pendingCount(run),...extra});

    // One engine step; the surface's time follows the tick it processed.
    function stepOnce(){
      const r=S.step(run);
      if(!r.ok)return r;
      if(r.tick!==null)time=Math.max(time,r.tick*TICK);
      return r;
    }
    function steps(n){
      let done=0;
      while(done<n){const r=stepOnce();if(!r.ok)return r;if(r.tick===null)break;done++}
      return progress(done);
    }
    function set(nodeId,value,at=null){
      const c=run.components[nodeId];if(!c)return refusal('UNKNOWN_NODE',`No component ${nodeId}`);
      if(!c.asserted)return refusal('DERIVED_SIGNAL',`${componentOf(nodeId)?.config?.label||nodeId} is derived from its inputs; only an asserted signal is set`);
      const v=Math.max(0,Math.min(1,Number(value)||0));
      if(v!==0&&v!==1&&c.asserted.kind==='continuous')return refusal('LEVEL_FRACTION',`${nodeId} is continuous: this runtime sets an asserted level to 0 or 1 only (a run records no floating point)`,{node:nodeId,value});
      const high=c.asserted.kind==='continuous'?v>=1:v*LEVEL>=c.asserted.threshold,tick=at==null?tickAt(time):at;
      const was=views().level[nodeId]??0;
      for(const point of c.asserted.outs){const r=give({entity:nodeId,point,channel:'main',value:high,at:tick});if(!r.ok)return r}
      cache=null;
      return {ok:true,node:nodeId,value:high?1:0,changed:(high?1:0)!==was,at:tick*TICK};
    }
    function inject(nodeId,{channel=null,payload=null,at=null,principal=null}={}){
      if(!run.components[nodeId])return refusal('UNKNOWN_NODE',`No component ${nodeId}`);
      const point=portOf(nodeId);if(!point)return refusal('NO_PORT',`${nodeId} has no port to put a message in at`);
      const tick=tickAt(at==null?time:Math.max(time,Number(at)));
      const r=give({entity:nodeId,point,channel:MESSAGE,value:{channel:channel??null,payload:payload===undefined?null:clone(payload),principal:principal??null},at:tick});
      if(!r.ok)return r;
      cache=null;
      return {ok:true,messageId:`m-${r.seq}`};
    }
    const sim={
      inject,
      // step(n): n ticks of the run; tick(): the next tick.
      step(n=1){return steps(Math.max(1,Number(n)||1))},
      tick(){return steps(1)},
      run({until=Infinity,maxEvents=10000}={}){
        let done=0;const cap=Number(maxEvents)||10000;
        for(;;){
          const t=nextTick(run);
          if(t===null||t*TICK>until||done>=cap)break;
          const r=stepOnce();if(!r.ok)return r;if(r.tick===null)break;done++;
        }
        if(until!==Infinity&&Number.isFinite(until))time=Math.max(time,until);
        const capped=done>=cap&&nextTick(run)!==null;
        return {ok:!capped,processed:done,time,pending:pendingCount(run),parked:Object.keys(run.parked||{}).length,...(capped?{code:'MAX_EVENTS',message:`stopped after ${cap} ticks`}:{})};
      },
      // Time is the driver: every tick due up to time + ms is processed, then time is that target.
      advance(ms){
        const target=time+Math.max(0,Number(ms)||0);let done=0;
        for(;;){const t=nextTick(run);if(t===null||t*TICK>target)break;const r=stepOnce();if(!r.ok)return r;if(r.tick===null)break;done++}
        time=target;
        return progress(done,{parked:Object.keys(run.parked||{}).length});
      },
      set(nodeId,value){return set(nodeId,value)},
      // An operation at a time (ms): {set:{node,value}} | {toggle:{node}} | {inject:{node,channel,payload,principal}}.
      at(when,action={}){
        const t=Math.max(time,Number(when)||0);
        if(action.inject)return inject(action.inject.node,{...action.inject,at:t});
        if(!(action.set||action.toggle))return refusal('BAD_ACTION','An action is {set}, {toggle} or {inject}');
        const id=(action.set||action.toggle).node,c=run.components[id];if(!c)return refusal('UNKNOWN_NODE',`No component ${id}`);
        if(!c.asserted)return refusal('DERIVED_SIGNAL',`${id} is derived; only an asserted signal is set`);
        if(action.set){const r=set(id,action.set.value,tickAt(t));return r.ok?{ok:true,at:r.at}:r}
        // A toggle reads the level when it happens: a message {toggle: true} to the card, which the
        // engine turns into the new level; the message is the surface's own and no view shows it.
        const point=c.asserted.outs[0]||portOf(id);if(!point)return refusal('NO_PORT',`${id} has no port`);
        const r=give({entity:id,point,channel:MESSAGE,value:{channel:null,payload:{toggle:true},principal:null},at:tickAt(t)});
        if(!r.ok)return r;
        internal.add(`m-${r.seq}`);cache=null;
        return {ok:true,at:tickAt(t)*TICK};
      },
      levels(){const lv=views().level;return Object.fromEntries(run.doc.components.map(c=>[c.id,{value:lv[c.id]??0,kind:kindOf(c.id),mode:modeOf(c.id)}]))},
      edges({node=null,since=null}={}){return {ok:true,edges:views().edges.filter(e=>(!node||e.node===node)&&(since==null||e.at>=since)).map(clone)}},
      parked(){return Object.values(run.parked||{}).sort((x,y)=>x.id<y.id?-1:x.id>y.id?1:0).map(p=>({id:p.id,node:p.entity,messageId:p.messageId,wireId:p.via??null,at:msOf(p.at),prompt:p.prompt??null}))},
      resume(parkId,{decision='approve',payload,reason}={}){
        const r=S.resume(run,parkId,{decision,...(payload!==undefined?{payload}:{}),...(reason!=null?{reason}:{})});
        cache=null;return r.ok?{ok:true,decision:r.decision}:r;
      },
      reconcile(effectKey,{confirmed,result=null}={}){const r=S.reconcile(run,effectKey,{confirmed:!!confirmed,result});cache=null;return r},
      trace(messageId){const m=views().messages.get(messageId);if(!m)return refusal('UNKNOWN_MESSAGE',`No message ${messageId}`);return {ok:true,message:clone(m)}},
      lineage(rootId){const v=views();return {ok:true,root:rootId,messages:v.order.map(id=>v.messages.get(id)).filter(m=>m.root===rootId).map(m=>({id:m.id,parent:m.parent,status:m.status,last:clone(m.hops.at(-1))}))}},
      taps(nodeId){const v=views();return {ok:true,node:nodeId,arrivals:v.order.map(id=>v.messages.get(id)).filter(m=>m.hops.some(h=>h.node===nodeId&&h.event==='arrived')).map(m=>({id:m.id,root:m.root,channel:m.channel,payload:clone(m.payload),status:m.status}))}},
      effects(){return Object.fromEntries(Object.entries(run.effects||{}).map(([k,e])=>[k,effectView(e)]))},
      refusals(){return clone(views().refusals)},
      receipts(){return clone(views().receipts)},
      log(){return clone(views().log)},
      state(){const v=views();return {time,pending:pendingCount(run),parked:Object.keys(run.parked||{}).length,messages:v.messages.size,refusals:v.refusals.length,effects:Object.keys(run.effects||{}).length,edges:v.edges.length,high:Object.values(v.level).filter(x=>x>0).length}},
      // A copy of the run, with the surface's time; createSimulation(doc, {restore}) continues from it.
      snapshot(){return {run:clone(run),time,startInputs:clone(startInputs),internal:[...internal]}},
      // A declarative handler is kept in the run (plain JSON); a function can be given only before the first tick.
      setHandler(name,spec){
        if(typeof spec==='function'){
          if(run.tick!==null)return refusal('HANDLER_AFTER_START',`a function handler is given before the first tick; ${name} comes after it`);
          handlers[name]=spec;const r=start();if(!r.ok)return r;run=r.run;cache=null;return {ok:true,name};
        }
        handlers[name]=spec;run.handlers[name]=clone(spec);cache=null;return {ok:true,name};
      },
      // The run itself, for a caller that reads its records or its trace (the canvas, contract 09).
      currentRun:()=>run
    };
    return {ok:true,sim};
  }

  // ---- Scenarios (7b939e3 lines 605-643), over the surface.
  function runScenario(doc,scenario,options={}){
    const sc=isObject(scenario?.data)?scenario.data:scenario;
    if(!isObject(sc)||!Array.isArray(sc.steps))return refusal('BAD_SCENARIO','A scenario needs steps[]');
    const handlers={...(sc.handlers||{}),...(options.handlers||{})};
    const base={handlers,...(options.packs!==undefined?{packs:options.packs}:{})};
    let made=createSimulation(doc,base);if(!made.ok)return made;
    let sim=made.sim;const notes=[];
    for(const [i,step] of sc.steps.entries()){
      if(step.inject){const r=sim.inject(step.inject.node,step.inject);if(!r.ok)return {...r,step:i}}
      else if(step.resume){
        const p=sim.parked().find(x=>!step.resume.node||x.node===step.resume.node);
        if(!p)return refusal('NOTHING_PARKED',`step ${i}: nothing parked${step.resume.node?' at '+step.resume.node:''}`,{step:i,log:sim.log()});
        sim.resume(p.id,step.resume);
      }
      else if(step.restart){
        // Kill and restart the engine from its snapshot, as a process restart would.
        made=createSimulation(doc,{...base,restore:sim.snapshot()});if(!made.ok)return made;sim=made.sim;notes.push({step:i,restarted:true});
      }
      else if(step.reconcile)sim.reconcile(step.reconcile.effectKey,step.reconcile);
      else if(step.set){const r=sim.set(step.set.node,step.set.value);if(!r.ok)return {...r,step:i}}
      else if(step.at){const {time,...action}=step.at;const r=sim.at(time,action);if(!r.ok)return {...r,step:i}}
      if(step.advance!=null)sim.advance(step.advance);
      else if(step.tick!=null){for(let k=0;k<(Number(step.tick)||1);k++)sim.tick()}
      else if(step.run||step.inject||step.resume||step.restart||step.reconcile||step.set)sim.run(step.run||{});
    }
    const checks=[],exp=sc.expect||{};
    for(const [node,n] of Object.entries(exp.taps||{})){const actual=sim.taps(node).arrivals.length;checks.push({name:`taps ${node}`,expected:n,actual,pass:actual===n})}
    if(exp.levelRefusals!=null){const actual=sim.refusals().filter(r=>r.level).length;checks.push({name:'level refusals',expected:exp.levelRefusals,actual,pass:actual===exp.levelRefusals})}
    if(exp.refusals!=null){const actual=sim.refusals().filter(r=>!r.level).length;checks.push({name:'refusals',expected:exp.refusals,actual,pass:actual===exp.refusals})}
    if(exp.parked!=null){const actual=sim.parked().length;checks.push({name:'parked',expected:exp.parked,actual,pass:actual===exp.parked})}
    for(const [status,n] of Object.entries(exp.effects||{})){const actual=Object.values(sim.effects()).filter(e=>e.status===status).length;checks.push({name:`effects ${status}`,expected:n,actual,pass:actual===n})}
    const levels=sim.levels();
    for(const [node,v] of Object.entries(exp.levels||{})){const actual=levels[node]?.value;checks.push({name:`level ${node}`,expected:v,actual,pass:actual!=null&&Math.abs(actual-v)<1e-6})}
    for(const [node,want] of Object.entries(exp.edges||{}))for(const [pol,n] of Object.entries(want)){const actual=sim.edges({node}).edges.filter(e=>e.polarity===pol).length;checks.push({name:`edges ${node} ${pol}`,expected:n,actual,pass:actual===n})}
    for(const [event,n] of Object.entries(exp.events||{})){const actual=sim.log().filter(e=>e.event===event).length;checks.push({name:`events ${event}`,expected:n,actual,pass:actual===n})}
    return {ok:checks.every(c=>c.pass),scenario:scenario?.id||sc.id||null,checks,state:sim.state(),refusals:sim.refusals(),receipts:sim.receipts(),notes};
  }

  // ---- One session, one dispatch (7b939e3 lines 645-683): the browser API, HTTP and MCP serve it alike.
  function scenariosOf(doc){return (doc?.references||[]).filter(r=>r.kind==='scenario')}
  function createSession(){
    let sim=null,startedAt=null,startedRevision=null;
    const need=()=>sim?null:refusal('NO_SIMULATION','Start a simulation first (schematic.sim.start)');
    const actions={
      'graph.query':(doc,a)=>graph().query(doc,a.verb,a.args||{}),
      'sim.start':(doc,a)=>{
        let handlers=isObject(a.handlers)?a.handlers:{};
        if(a.scenarioId){const sc=scenariosOf(doc).find(r=>r.id===a.scenarioId);if(!sc)return refusal('UNKNOWN_SCENARIO',`No scenario ${a.scenarioId}`);handlers={...(sc.data?.handlers||{}),...handlers}}
        const made=createSimulation(doc,{handlers});if(!made.ok)return made;
        sim=made.sim;startedAt=new Date().toISOString();startedRevision=doc.revision??null;
        return {ok:true,startedAt,revision:startedRevision,handlers:Object.keys(handlers),state:sim.state()};
      },
      'sim.stop':()=>{const was=!!sim;sim=null;return {ok:true,stopped:was}},
      'sim.inject':(doc,a)=>need()||sim.inject(a.node,a),
      'sim.set':(doc,a)=>need()||sim.set(a.node,a.value),
      'sim.at':(doc,a)=>need()||sim.at(a.time,a),
      'sim.advance':(doc,a)=>need()||sim.advance(a.ms),
      'sim.tick':(doc,a)=>{const n=need();if(n)return n;let r;for(let k=0;k<(Number(a.n)||1);k++)r=sim.tick();return r},
      'sim.step':(doc,a)=>need()||sim.step(Number(a.n)||1),
      'sim.run':(doc,a)=>need()||sim.run({until:a.until==null?Infinity:Number(a.until),maxEvents:Number(a.maxEvents)||10000}),
      'sim.resume':(doc,a)=>need()||sim.resume(a.parkId,a),
      'sim.reconcile':(doc,a)=>need()||sim.reconcile(a.effectKey,a),
      'sim.inspect':(doc,a)=>{
        const n=need();if(n)return n;
        const what=a.what||'state',stale=startedRevision!=null&&doc.revision!==startedRevision;
        const views={state:()=>({ok:true,...sim.state(),stale,startedAt,revision:startedRevision}),parked:()=>({ok:true,parked:sim.parked()}),log:()=>({ok:true,log:sim.log()}),effects:()=>({ok:true,effects:sim.effects()}),refusals:()=>({ok:true,refusals:sim.refusals()}),receipts:()=>({ok:true,receipts:sim.receipts()}),trace:()=>sim.trace(a.id),levels:()=>({ok:true,time:sim.state().time,levels:sim.levels()}),edges:()=>sim.edges({node:a.id||null,since:a.since??null}),taps:()=>sim.taps(a.id),lineage:()=>sim.lineage(a.id),snapshot:()=>({ok:true,snapshot:sim.snapshot()})};
        return views[what]?views[what]():refusal('UNKNOWN_VIEW',`Unknown view ${what}`,{views:Object.keys(views)});
      },
      'sim.scenario':(doc,a)=>{
        const sc=a.scenario||scenariosOf(doc).find(r=>r.id===a.id);
        if(!sc)return refusal('UNKNOWN_SCENARIO',`No scenario ${a.id}`,{scenarios:scenariosOf(doc).map(r=>r.id)});
        return runScenario(doc,sc,{handlers:isObject(a.handlers)?a.handlers:{}});
      },
      'sim.scenarios':(doc)=>({ok:true,scenarios:scenariosOf(doc).map(r=>({id:r.id,label:r.label}))})
    };
    return {execute(name,doc,args={}){const fn=actions[String(name).replace(/^schematic\./,'')];if(!fn)return refusal('UNKNOWN_TOOL',`Unknown tool ${name}`);return fn(doc,isObject(args)?args:{})},names:Object.keys(actions).map(n=>'schematic.'+n)};
  }
  // The same schematic.graph.query and 14 schematic.sim.* tools as src/07-graph-core.js; step counts ticks.
  function tools(){
    const obj=(properties,required=[])=>({type:'object',properties,required,additionalProperties:false});
    const verbs=graph().queries;
    return [
      {name:'schematic.graph.query',description:`Read-only graph query. verb: ${verbs.join(' | ')}. args e.g. {from,to} for paths/cut, {from,channel} for reach (channel is optional: it follows only Wires whose two bound ports share that channel, so it crosses a boundary Point only where its self declares the channel), {componentId} for boundary, {format: jgf|dot|graphml} for export.`,inputSchema:obj({verb:{type:'string',enum:verbs},args:{type:'object'}},['verb'])},
      {name:'schematic.sim.start',description:'Start a message simulation over the current document. handlers maps a handler name to {kind: stub | fixture}; scenarioId borrows a saved scenario\'s handlers. A handler a node names but nobody registered refuses its messages.',inputSchema:obj({handlers:{type:'object'},scenarioId:{type:'string'}})},
      {name:'schematic.sim.stop',description:'Discard the running simulation.',inputSchema:obj({})},
      {name:'schematic.sim.inject',description:'Emit a message from a component (it leaves by that component\'s outgoing wires). principal names who acts; a plane with an ACL checks it at its boundary.',inputSchema:obj({node:{type:'string'},channel:{type:'string'},payload:{},at:{type:'number'},principal:{type:'string'}},['node'])},
      {name:'schematic.sim.set',description:'Assert a signal: set a lever, source or other asserted node to a level (binary 0|1, continuous 0..1). A derived signal is refused: it is computed from its inputs.',inputSchema:obj({node:{type:'string'},value:{type:'number',minimum:0,maximum:1}},['node','value'])},
      {name:'schematic.sim.at',description:'Schedule an operation at a simulation time (ms): {set:{node,value}} | {toggle:{node}} | {inject:{node,channel,payload,principal}}.',inputSchema:obj({time:{type:'number'},set:{type:'object'},toggle:{type:'object'},inject:{type:'object'}},['time'])},
      {name:'schematic.sim.advance',description:'Drive the clock: advance simulation time by ms, processing everything due (clocks, levels, messages).',inputSchema:obj({ms:{type:'number',minimum:0}},['ms'])},
      {name:'schematic.sim.tick',description:'Take the next instant n times: process every event due at the next scheduled time.',inputSchema:obj({n:{type:'integer',minimum:1}})},
      {name:'schematic.sim.step',description:'Process the next n ticks: each tick is one instant of the run, everything due in it.',inputSchema:obj({n:{type:'integer',minimum:1}})},
      {name:'schematic.sim.run',description:'Process events until the queue is empty, a time is reached, or maxEvents.',inputSchema:obj({until:{type:'number'},maxEvents:{type:'integer',minimum:1}})},
      {name:'schematic.sim.resume',description:'Resume a message parked at a human step: decision approve | reject, optional payload merged in.',inputSchema:obj({parkId:{type:'string'},decision:{type:'string',enum:['approve','reject']},payload:{},reason:{type:'string'}},['parkId'])},
      {name:'schematic.sim.reconcile',description:'Settle an ambiguous effect: confirmed true records it as done (it will not repeat), false clears it for retry.',inputSchema:obj({effectKey:{type:'string'},confirmed:{type:'boolean'},result:{}},['effectKey','confirmed'])},
      {name:'schematic.sim.inspect',description:'Read simulation state. what: state | levels | edges | parked | log | effects | refusals | receipts | trace | taps | lineage | snapshot; id names the message (trace, lineage) or component (taps, edges).',inputSchema:obj({what:{type:'string'},id:{type:'string'}})},
      {name:'schematic.sim.scenario',description:'Run a saved scenario (document.references kind scenario) or an inline one in a fresh engine and return its checks as evidence.',inputSchema:obj({id:{type:'string'},scenario:{type:'object'},handlers:{type:'object'}})},
      {name:'schematic.sim.scenarios',description:'List the scenarios saved in the document.',inputSchema:obj({})}
    ];
  }

  return {createSimulation,runScenario,createSession,tools,LEVEL};
});
