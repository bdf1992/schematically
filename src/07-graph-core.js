'use strict';
// 0.1 concern: graph reading of a document (queries, junction flow) and the discrete-event
// message simulation. No DOM; shared by the browser API and the MCP/HTTP server.
// Specified in GRAPH-MODEL.md.
(function(root,factory){
  let Data=root.SovSchematicData;
  if(!Data&&typeof module!=='undefined'&&module.exports){require('./06-attachment-core.js');Data=require('./05-data-core.js')}
  const api=factory(Data);
  root.SovSchematicGraph=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(Data){
  if(!Data)throw new Error('SovSchematicData core is required');
  const clone=Data.clone;
  const isObject=v=>!!v&&typeof v==='object'&&!Array.isArray(v);
  const DEFAULT_LATENCY_MS=10;
  const POLICIES=['fanout','distribute','merge','join','select'];

  function refusal(code,message,extra={}){return {ok:false,code,message,...extra}}

  // ---- Graph reading -------------------------------------------------------------------
  // A port authored without connections takes the data core's default for its id, the same
  // default the editor normalizes to, so the simulation and the signal view agree.
  const DEFAULT_FLOW={in:'in',out:'out',control:'control'};
  function activeConnection(port,portId){
    if(isObject(port)&&port.side==='point'&&!(Array.isArray(port.connections)&&port.connections.length))return {flow:port.flow||'duplex',access:port.access||'read-write'};
    if(!isObject(port))return null;
    const list=Array.isArray(port.connections)?port.connections:[];
    return list[Math.max(0,Math.min(list.length-1,Number(port.activeConnection)||0))]||{flow:port.flow||DEFAULT_FLOW[portId]||'duplex',access:port.access||'read-write'};
  }
  const canEmit=(p,id)=>{const c=activeConnection(p,id);return !!c&&(c.flow==='out'||c.flow==='duplex')};
  const canReceive=(p,id)=>{const c=activeConnection(p,id);return !!c&&(c.flow==='in'||c.flow==='duplex'||c.flow==='control')};
  const accessAllows=(p,op)=>{if(op==='none')return true;const a=activeConnection(p)?.access||'read-write';return a==='read-write'||a===op};
  function wireDirection(w){const d=w.config?.direction;return ['none','forward','reverse','duplex'].includes(d)?d:(w.duplex?'duplex':'forward')}
  function flowConfig(component){
    const f=isObject(component.config?.flow)?component.config.flow:{};
    return {declared:POLICIES.includes(f.policy),policy:POLICIES.includes(f.policy)?f.policy:'fanout',by:['round-robin','channel','key'].includes(f.by)?f.by:'round-robin',key:typeof f.key==='string'?f.key:null,rate:isObject(f.rate)?f.rate:null,capacity:Number.isFinite(Number(f.capacity))?Number(f.capacity):null,releaseMs:Number.isFinite(Number(f.releaseMs))?Math.max(0,Number(f.releaseMs)):null};
  }

  // Signal (SIGNAL-MODEL in GRAPH-MODEL.md §7). A level is binary {0,1} or continuous [0,1].
  // Asserted: declared state, changed only by an operation (a lever, a source, a clock).
  // Derived: computed from inputs as they change over time. Without config.signal the
  // legacy signalMode decides, with the editor's default (absent = source).
  const COMBINES=['or','and','not','max','min','mean','sum'];
  const WAVES=['square','saw','triangle','sine'];
  function signalConfig(c){
    const raw=isObject(c.config?.signal)?c.config.signal:null,legacy=c.config?.signalMode;
    const clockRaw=isObject(raw?.clock)?raw.clock:null;
    const assertedSymbol=c.symbolId==='lever'||c.symbolId==='clock';
    const mode=raw&&['asserted','derived'].includes(raw.mode)?raw.mode:(clockRaw||assertedSymbol?'asserted':raw?'derived':(legacy==='relay'||legacy==='passive')?'derived':'asserted');
    const wave=clockRaw&&WAVES.includes(clockRaw.wave)?clockRaw.wave:'square';
    const kind=raw&&['binary','continuous'].includes(raw.kind)?raw.kind:(clockRaw&&wave!=='square'?'continuous':'binary');
    const value=Number.isFinite(Number(raw?.value))?Math.max(0,Math.min(1,Number(raw.value))):(raw||assertedSymbol?0:(mode==='asserted'?1:0));
    const combine=raw&&COMBINES.includes(raw.combine)?raw.combine:(kind==='continuous'?'max':'or');
    const clock=clockRaw?{periodMs:Number(clockRaw.periodMs),phaseMs:Math.max(0,Number(clockRaw.phaseMs)||0),duty:Number.isFinite(Number(clockRaw.duty))?Math.max(0,Math.min(1,Number(clockRaw.duty))):.5,wave,
      sampleMs:Number(clockRaw.sampleMs)>0?Number(clockRaw.sampleMs):null,cycles:Number(clockRaw.cycles)>0?Math.floor(Number(clockRaw.cycles)):null}:null;
    return {mode,kind,value,combine,clock,declared:!!raw,
      threshold:Number.isFinite(Number(raw?.threshold))?Number(raw.threshold):.5,
      epsilon:Number(raw?.epsilon)>0?Number(raw.epsilon):.001,
      on:['+','-','±'].includes(raw?.on)?raw.on:null,channel:typeof raw?.channel==='string'?raw.channel:'edge',
      emits:raw?.emits===false?false:!(legacy==='passive'&&!raw)};
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
    const nodes=new Map(),arcs=[],blocked=[],ends=new Map();
    for(const c of doc.components){
      nodes.set(c.id,{id:c.id,symbolId:c.symbolId,label:c.config?.label||'',parentId:c.parentId||null,canvasId:c.canvasId||Data.GLOBAL_CANVAS_ID,
        dimension:Number(c.form?.dimension??2),signalMode:c.config?.signalMode||null,flow:flowConfig(c),
        behavior:isObject(c.config?.behavior)?clone(c.config.behavior):{},ports:c.config?.ports||{},placement:c.placement||null,
        signal:signalConfig(c),principal:typeof c.config?.principal==='string'&&c.config.principal?c.config.principal:null,acl:aclConfig(c),
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
        arcs.push({wireId:w.id,canvasId:w.canvasId||Data.GLOBAL_CANVAS_ID,from,fromPort,to,toPort,latencyMs:latency,accepts,operation:op,control:activeConnection(tp,toPort)?.flow==='control'||toPort==='control'});
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
  function reach(g,from,{channel=null}={}){
    if(!g.nodes.has(from))return refusal('UNKNOWN_NODE',`No component ${from}`);
    const seen=new Set([from]),queue=[from],via=[];
    while(queue.length){const id=queue.shift();for(const a of g.out.get(id)){if(a.control)continue;if(channel&&a.accepts&&!a.accepts.includes(channel))continue;via.push(a.wireId);if(!seen.has(a.to)){seen.add(a.to);queue.push(a.to)}}}
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

  // ---- Simulation ----------------------------------------------------------------------
  function readPath(obj,path){if(!path)return undefined;let v=obj;for(const k of String(path).split('.')){if(v==null)return undefined;v=v[k]}return v}
  function fnv(s){let h=0x811c9dc5;for(const ch of String(s)){h^=ch.charCodeAt(0);h=Math.imul(h,0x01000193)>>>0}return h}

  // Declarative handlers work in simulation and in saved scenarios; functions are for code callers.
  // {kind:'stub'} passes through · {kind:'fixture', key, responses:{value: output}, otherwise?, merge?}
  // An output is {payload?, channel?, port?} | [outputs] | {refuse: reason} | {absorb: true}.
  function callHandler(spec,msg,ctx){
    if(typeof spec==='function')return spec(clone(msg),ctx);
    if(!isObject(spec))return {refuse:'handler is not callable'};
    if(spec.kind==='stub')return {payload:msg.payload};
    if(spec.kind==='fixture'){
      const k=readPath(msg,spec.key);const hit=isObject(spec.responses)&&Object.prototype.hasOwnProperty.call(spec.responses,String(k))?spec.responses[String(k)]:spec.otherwise;
      if(hit===undefined)return {refuse:`fixture has no response for ${spec.key}=${JSON.stringify(k)}`};
      const out=clone(hit);
      // merge:true lays the response over the incoming payload instead of replacing it.
      if(spec.merge&&isObject(out)&&isObject(out.payload)&&isObject(msg.payload))out.payload={...clone(msg.payload),...out.payload};
      return out;
    }
    return {refuse:`unknown handler kind ${spec.kind}`};
  }

  function createSimulation(doc,options={}){
    const g=build(doc);
    const zero=cycles(g).cycles.filter(c=>!c.timed);
    if(zero.length)return refusal('ZERO_LATENCY_CYCLE','A message cycle must take time: give a wire latencyMs above 0 or pass through a buffer or hold',{cycles:zero});
    const handlers=Object.assign({},options.handlers||{});
    for(const n of g.nodes.values())if(n.signal.clock&&!(n.signal.clock.periodMs>0))return refusal('CLOCK_HAS_NO_PERIOD',`Clock ${n.label||n.id} needs config.signal.clock.periodMs above 0`,{node:n.id});
    for(const n of g.nodes.values())if(n.symbolId==='clock'&&!n.signal.clock)return refusal('CLOCK_HAS_NO_PERIOD',`Clock ${n.label||n.id} needs config.signal.clock.periodMs above 0`,{node:n.id});
    const restored=isObject(options.restore);
    const s=restored?clone(options.restore):{time:0,seq:0,msgSeq:0,parkSeq:0,queue:[],messages:{},log:[],refusals:[],receipts:[],parked:{},effects:{},state:{},levels:{},inputs:{},levelVia:{},levelPrincipal:{},edges:[]};
    // Effect ledger outlives the run when handed in: replay identity is durable, the engine is not.
    if(isObject(options.effects))s.effects=clone(options.effects);

    const nodeState=id=>s.state[id]||(s.state[id]={});
    const log=(event,fields)=>{s.log.push({at:s.time,event,...fields})};
    function newMessage(base,parent=null){
      const id=`m${++s.msgSeq}`;
      const m={id,root:parent?parent.root:id,parent:parent?parent.id:null,principal:base.principal??parent?.principal??null,channel:base.channel??parent?.channel??null,payload:clone(base.payload??parent?.payload??null),origin:parent?parent.origin:base.origin,at:s.time,status:'live',hops:parent?clone(parent.hops):[]};
      s.messages[id]=m;return m;
    }
    function schedule(at,event){
      const e={at,seq:++s.seq,...event};let lo=0,hi=s.queue.length;
      while(lo<hi){const mid=(lo+hi)>>1;if(s.queue[mid].at<=at)lo=mid+1;else hi=mid}
      s.queue.splice(lo,0,e);
    }
    function hop(m,node,event,extra={}){m.hops.push({at:s.time,node,event,...extra})}
    function refuse(m,node,reason){m.status='refused';hop(m,node,'refused',{reason});s.refusals.push({at:s.time,messageId:m.id,root:m.root,node,reason});log('refused',{messageId:m.id,node,reason})}
    function finish(m,node,status){m.status=status;hop(m,node,status);log(status,{messageId:m.id,node})}

    function outgoing(nodeId,m,viaWire,port){
      return g.out.get(nodeId).filter(a=>a.wireId!==viaWire&&(port==null||a.fromPort===port)&&(!m.channel||!a.accepts||a.accepts.includes(m.channel)));
    }
    // The wire a message last arrived by at a node: the side it turns from.
    function arrivedBy(m,nodeId){for(let i=m.hops.length-1;i>=0;i--){const h=m.hops[i];if(h.node===nodeId&&h.event==='arrived')return h.wireId;if(h.node!==nodeId)break}return null}
    function send(m,arc){
      const copy=newMessage({},m);
      const cross=crossingAt(g,arc.from,arrivedBy(m,arc.from),arc.canvasId);
      if(cross){
        for(const op of [cross.op,...(arc.operation!=='none'?[arc.operation]:[])]){
          const d=aclDecide(cross.plane,copy.principal,op);
          if(!d.ok){hop(copy,arc.from,'sent',{wireId:arc.wireId,to:arc.to});refuse(copy,arc.from,d.reason);return null}
        }
        hop(copy,arc.from,'crossed',{plane:cross.plane.id,op:cross.op,principal:copy.principal});
      }
      hop(copy,arc.from,'sent',{wireId:arc.wireId,to:arc.to});
      log('sent',{messageId:copy.id,from:arc.from,to:arc.to,wireId:arc.wireId});
      schedule(s.time+arc.latencyMs,{kind:'arrive',messageId:copy.id,node:arc.to,port:arc.toPort,wireId:arc.wireId});
      return copy;
    }
    // Apply the junction policy to one message leaving a node.
    function forward(node,m,viaWire,port=null){
      const arcs=outgoing(node.id,m,viaWire,port);
      if(!arcs.length){
        // A sink delivers; a node with outgoing ends that all refuse the channel refuses, never drops.
        if(outgoing(node.id,{channel:null},viaWire,port).length)return refuse(m,node.id,`no end accepts channel ${m.channel}`);
        finish(m,node.id,'delivered');return;
      }
      const policy=node.flow.policy,st=nodeState(node.id);
      let chosen=arcs;
      if(policy==='distribute'){
        if(node.flow.by==='channel'){chosen=arcs.filter(a=>a.accepts&&m.channel&&a.accepts.includes(m.channel));if(!chosen.length)return refuse(m,node.id,`no end declares channel ${m.channel}`);chosen=[chosen[0]]}
        else if(node.flow.by==='key'){const k=readPath(m,node.flow.key);if(k===undefined)return refuse(m,node.id,`message has no key ${node.flow.key}`);chosen=[arcs[fnv(JSON.stringify(k))%arcs.length]]}
        else{st.rr=(st.rr||0);chosen=[arcs[st.rr%arcs.length]];st.rr++}
      }
      if(policy==='select')return refuse(m,node.id,'select needs a handler (config.behavior.handler)');
      if(node.principal)m.principal=node.principal; // a participant acts in its own name
      m.status='forwarded';hop(m,node.id,'forwarded',{policy,declared:node.flow.declared,to:chosen.map(a=>a.to)});
      for(const a of chosen)send(m,a);
    }
    function emitOutputs(node,m,viaWire,result){
      const outs=Array.isArray(result)?result:[result];
      if(!outs.length){finish(m,node.id,'absorbed');return}
      m.status='handled';hop(m,node.id,'handled',{outputs:outs.length});
      for(const o of outs){
        if(!isObject(o))continue;
        const child=newMessage({channel:o.channel??m.channel,payload:o.payload!==undefined?o.payload:m.payload},m);
        forward(node,child,viaWire,o.port??null);
      }
    }
    function runHandler(node,m,viaWire,name){
      const spec=handlers[name];
      if(spec===undefined){refuse(m,node.id,`no handler registered: ${name}`);return {refused:true}}
      let result;
      try{result=callHandler(spec,m,{node:node.id,time:s.time,state:nodeState(node.id)})}
      catch(e){return {error:String(e?.message||e)}}
      if(result==null||result.absorb){finish(m,node.id,'absorbed');return {absorbed:true}}
      if(result.refuse){refuse(m,node.id,String(result.refuse));return {refused:true}}
      return {result};
    }

    function arrive(ev){
      const m=s.messages[ev.messageId],node=g.nodes.get(ev.node);if(!m||!node)return;
      hop(m,node.id,'arrived',{port:ev.port,wireId:ev.wireId});
      log('arrived',{messageId:m.id,node:node.id,port:ev.port,wireId:ev.wireId});
      const st=nodeState(node.id),sym=node.symbolId,b=node.behavior;
      const arc=ev.wireId?g.arcs.find(a=>a.wireId===ev.wireId&&a.to===node.id):null;
      if(arc?.control){
        const open=isObject(m.payload)&&'open' in m.payload?!!m.payload.open:true;
        st.open=open;finish(m,node.id,'controlled');log('control',{node:node.id,open});return;
      }
      // An asserted signal is changed by an operation: a message may set or toggle it.
      if(node.signal.mode==='asserted'&&isObject(m.payload)&&('set' in m.payload||m.payload.toggle)){
        const v=m.payload.toggle?1-(s.levels[node.id]??0):Number(m.payload.set);
        setLevel(node,v,'message');finish(m,node.id,'asserted');return;
      }
      if(sym==='refuse')return refuse(m,node.id,'REFUSE terminal');
      if(sym==='observe'){finish(m,node.id,'observed');s.receipts.push({at:s.time,kind:'observation',node:node.id,messageId:m.id,root:m.root,channel:m.channel,payload:clone(m.payload)});return}
      if(sym==='receipt')s.receipts.push({at:s.time,kind:'receipt',node:node.id,messageId:m.id,root:m.root,channel:m.channel,payload:clone(m.payload)});
      if(sym==='hold')st.value=clone(m.payload);
      if(sym==='switch'&&!st.open)return refuse(m,node.id,'switch is closed');
      if(sym==='gate'&&!b.handler){
        const controlled=g.in.get(node.id).some(a=>a.control);
        if(!controlled)return refuse(m,node.id,'gate has no condition: wire its control point or name a handler');
        if(!st.open)return refuse(m,node.id,'gate is closed: no control has opened it');
      }
      if(sym==='limit'){
        const r=node.flow.rate;if(!r||!(r.count>0)||!(r.windowMs>0))return refuse(m,node.id,'limit has no rate (config.flow.rate {count, windowMs})');
        st.window=(st.window||[]).filter(t=>t>s.time-r.windowMs);
        if(st.window.length>=r.count)return refuse(m,node.id,`limit ${r.count} per ${r.windowMs}ms exceeded`);
        st.window.push(s.time);
      }
      if(sym==='buffer'){
        st.queue=st.queue||[];
        if(node.flow.capacity!=null&&st.queue.length>=node.flow.capacity)return refuse(m,node.id,`buffer full (${node.flow.capacity})`);
        st.queue.push({messageId:m.id,wireId:ev.wireId});m.status='buffered';hop(m,node.id,'buffered');
        if(!st.releasing){st.releasing=true;schedule(s.time+(node.flow.releaseMs??DEFAULT_LATENCY_MS),{kind:'release',node:node.id})}
        return;
      }
      if(node.flow.policy==='join'){
        const incoming=[...new Set(g.in.get(node.id).filter(a=>!a.control).map(a=>a.wireId))];
        st.join=st.join||{};(st.join[ev.wireId]=st.join[ev.wireId]||[]).push(m.id);
        m.status='joined';hop(m,node.id,'waiting');
        if(!incoming.every(w=>(st.join[w]||[]).length))return;
        const parts={},taken=[];for(const w of incoming){const id=st.join[w].shift();parts[w]=clone(s.messages[id].payload);taken.push(id)}
        const joined=newMessage({channel:m.channel,payload:{parts},origin:m.origin},m);joined.joined=taken;
        log('joined',{node:node.id,messageId:joined.id,from:taken});
        return continueAt(node,joined,null);
      }
      if(b.human){
        const parkId=`p${++s.parkSeq}`;s.parked[parkId]={id:parkId,node:node.id,messageId:m.id,wireId:ev.wireId,at:s.time,prompt:b.human.prompt||null};
        m.status='parked';hop(m,node.id,'parked',{parkId});log('parked',{node:node.id,messageId:m.id,parkId});return;
      }
      continueAt(node,m,ev.wireId);
    }
    // After intake: effect mediation, handler, then the flow policy.
    function continueAt(node,m,viaWire){
      const b=node.behavior;
      if(b.effect){
        const key=readPath(m,b.effect.key);
        if(key===undefined||key===null||key==='')return refuse(m,node.id,`effect has no identity (${b.effect.key})`);
        const ek=`${node.id}:${typeof key==='string'?key:JSON.stringify(key)}`,prior=s.effects[ek];
        if(prior&&prior.status==='confirmed'){m.status='replayed';hop(m,node.id,'replayed',{effectKey:ek});log('effect-replayed',{node:node.id,messageId:m.id,effectKey:ek});return}
        if(prior&&prior.status==='ambiguous')return refuse(m,node.id,`effect ${ek} is ambiguous: reconcile before retrying`);
        s.effects[ek]={key:ek,node:node.id,status:'attempted',at:s.time,messageId:m.id};
        const out=b.handler?runHandler(node,m,viaWire,b.handler):{result:{payload:m.payload}};
        if(out.error){s.effects[ek].status='ambiguous';s.effects[ek].error=out.error;m.status='ambiguous';hop(m,node.id,'ambiguous',{effectKey:ek,error:out.error});log('effect-ambiguous',{node:node.id,messageId:m.id,effectKey:ek,error:out.error});return}
        if(out.refused||out.absorbed){delete s.effects[ek];return}
        Object.assign(s.effects[ek],{status:'confirmed',confirmedAt:s.time,result:clone(out.result)});
        log('effect-confirmed',{node:node.id,messageId:m.id,effectKey:ek});
        return emitOutputs(node,m,viaWire,out.result);
      }
      if(b.handler){
        const out=runHandler(node,m,viaWire,b.handler);
        if(out.error)return refuse(m,node.id,`handler ${b.handler} failed: ${out.error}`);
        if(!out.result)return;
        if(node.symbolId==='gate'&&!Array.isArray(out.result)&&out.result.pass===false)return refuse(m,node.id,out.result.reason||'gate refused');
        return emitOutputs(node,m,viaWire,out.result);
      }
      if(node.signalMode==='passive')return finish(m,node.id,'absorbed');
      forward(node,m,viaWire);
    }
    function release(ev){
      const node=g.nodes.get(ev.node),st=nodeState(ev.node);const item=(st.queue||[]).shift();
      if(item){const m=s.messages[item.messageId];hop(m,node.id,'released');log('released',{node:node.id,messageId:m.id});continueAt(node,m,item.wireId)}
      if((st.queue||[]).length)schedule(s.time+(node.flow.releaseMs??DEFAULT_LATENCY_MS),{kind:'release',node:ev.node});else st.releasing=false;
    }

    // ---- Levels: state that changes over time, and the edges (+ rising, − falling) it makes.
    const quantize=(node,v)=>{v=Math.max(0,Math.min(1,Number(v)||0));return node.signal.kind==='binary'?(v>=node.signal.threshold?1:0):v};
    function setLevel(node,v,cause){
      const old=s.levels[node.id]??0;v=quantize(node,v);
      if(Math.abs(v-old)<=(node.signal.kind==='binary'?0:node.signal.epsilon))return false;
      s.levels[node.id]=v;
      const polarity=v>old?'+':'-',edge={at:s.time,node:node.id,from:old,to:v,polarity,cause};
      s.edges.push(edge);log('edge',{node:node.id,from:old,to:v,polarity,cause});
      if(node.signal.on&&(node.signal.on==='±'||node.signal.on===polarity)){
        // An edge may start work: it leaves the node as a message, like an inject.
        const m=newMessage({channel:node.signal.channel,payload:{node:node.id,polarity,from:old,to:v,at:s.time},origin:node.id,principal:node.principal});
        hop(m,node.id,'edge',{polarity});log('edge-message',{messageId:m.id,node:node.id,polarity});continueAt(node,m,null);
      }
      if(node.signal.emits)for(const a of g.out.get(node.id)){
        const principal=node.principal??s.levelPrincipal[node.id]??null;
        const cross=crossingAt(g,node.id,s.levelVia[node.id]??null,a.canvasId);
        if(cross){const d=aclDecide(cross.plane,principal,cross.op);if(!d.ok){s.refusals.push({at:s.time,level:true,node:node.id,wireId:a.wireId,reason:d.reason});log('refused',{node:node.id,wireId:a.wireId,reason:d.reason,level:true});continue}}
        schedule(s.time+a.latencyMs,{kind:'level',node:a.to,wireId:a.wireId,value:v,principal});
      }
      return true;
    }
    const COMBINE={or:v=>Math.max(0,...v),max:v=>Math.max(0,...v),and:v=>v.length?Math.min(...v):0,min:v=>v.length?Math.min(...v):0,
      not:v=>1-Math.max(0,...v),mean:v=>v.length?v.reduce((a,b)=>a+b,0)/v.length:0,sum:v=>Math.min(1,v.reduce((a,b)=>a+b,0))};
    function recompute(node){
      const inputs=s.inputs[node.id]||{},arcs=g.in.get(node.id);
      const data=arcs.filter(a=>!a.control).map(a=>inputs[a.wireId]??0),control=arcs.filter(a=>a.control).map(a=>inputs[a.wireId]??0);
      const enabled=!control.length||Math.max(...control)>=node.signal.threshold;
      return setLevel(node,enabled?COMBINE[node.signal.combine](data):0,'derived');
    }
    function levelArrive(ev){
      const node=g.nodes.get(ev.node);if(!node)return;
      (s.inputs[node.id]||(s.inputs[node.id]={}))[ev.wireId]=ev.value;
      s.levelVia[node.id]=ev.wireId;s.levelPrincipal[node.id]=ev.principal;
      if(node.signal.mode==='derived')recompute(node);
    }
    function waveAt(c,t){
      if(t<c.phaseMs)return 0;
      const u=(((t-c.phaseMs)/c.periodMs)%1+1)%1;
      return c.wave==='square'?(u<c.duty?1:0):c.wave==='saw'?u:c.wave==='triangle'?(u<.5?2*u:2-2*u):.5-.5*Math.cos(2*Math.PI*u);
    }
    function nextClockTime(c,t){
      if(t<c.phaseMs)return c.phaseMs;
      if(c.wave!=='square')return t+(c.sampleMs||c.periodMs/16);
      const k=Math.floor((t-c.phaseMs)/c.periodMs),start=c.phaseMs+k*c.periodMs,fall=start+c.duty*c.periodMs;
      return t<fall&&fall>t?fall:start+c.periodMs;
    }
    function clockTick(ev){
      const node=g.nodes.get(ev.node),c=node?.signal.clock;if(!c)return;
      if(c.cycles&&s.time>=c.phaseMs+c.cycles*c.periodMs){setLevel(node,0,'clock');log('clock-stopped',{node:node.id});return}
      setLevel(node,waveAt(c,s.time),'clock');
      schedule(Math.max(s.time+1e-9,nextClockTime(c,s.time)),{kind:'clock',node:node.id});
    }
    function runAction(ev){
      const a=ev.action||{};
      if(a.set){const node=g.nodes.get(a.set.node);if(node)sim.set(a.set.node,a.set.value)}
      else if(a.toggle){sim.set(a.toggle.node,1-(s.levels[a.toggle.node]??0))}
    }
    if(!restored){
      // Power on: asserted levels drive out at time 0; clocks start their schedule.
      for(const n of g.nodes.values()){
        if(n.signal.clock)schedule(0,{kind:'clock',node:n.id});
        else if(n.signal.mode==='asserted'&&n.signal.value>0)schedule(0,{kind:'action',action:{set:{node:n.id,value:n.signal.value}}});
      }
    }

    const sim={
      inject(nodeId,{channel=null,payload=null,at=null,principal=null}={}){
        if(!g.nodes.has(nodeId))return refusal('UNKNOWN_NODE',`No component ${nodeId}`);
        const m=newMessage({channel,payload,origin:nodeId,principal});
        hop(m,nodeId,'injected');log('injected',{messageId:m.id,node:nodeId,channel});
        schedule(at==null?s.time:Math.max(s.time,Number(at)),{kind:'inject',messageId:m.id,node:nodeId});
        return {ok:true,messageId:m.id};
      },
      step(n=1){
        let done=0;
        while(done<n&&s.queue.length){
          const ev=s.queue.shift();s.time=Math.max(s.time,ev.at);done++;
          if(ev.kind==='arrive')arrive(ev);
          else if(ev.kind==='inject'){const m=s.messages[ev.messageId],node=g.nodes.get(ev.node);continueAt(node,m,null)}
          else if(ev.kind==='release')release(ev);
          else if(ev.kind==='level')levelArrive(ev);
          else if(ev.kind==='clock')clockTick(ev);
          else if(ev.kind==='action')runAction(ev);
        }
        return {ok:true,processed:done,time:s.time,pending:s.queue.length};
      },
      run({until=Infinity,maxEvents=10000}={}){
        let done=0;
        while(s.queue.length&&s.queue[0].at<=until&&done<maxEvents){sim.step(1);done++}
        if(until!==Infinity&&Number.isFinite(until))s.time=Math.max(s.time,until);
        return {ok:done<maxEvents||!s.queue.length,processed:done,time:s.time,pending:s.queue.length,parked:Object.keys(s.parked).length,...(done>=maxEvents&&s.queue.length?{code:'MAX_EVENTS',message:`stopped after ${maxEvents} events`}:{})};
      },
      // Time is the driver: advance the clock, or take the next instant with everything due in it.
      advance(ms){const until=s.time+Math.max(0,Number(ms)||0);return sim.run({until})},
      tick(){if(!s.queue.length)return {ok:true,processed:0,time:s.time,pending:0};const t=s.queue[0].at;let n=0;while(s.queue.length&&s.queue[0].at===t){sim.step(1);n++}return {ok:true,processed:n,time:s.time,pending:s.queue.length}},
      set(nodeId,value){
        const node=g.nodes.get(nodeId);if(!node)return refusal('UNKNOWN_NODE',`No component ${nodeId}`);
        if(node.signal.mode!=='asserted')return refusal('DERIVED_SIGNAL',`${node.label||nodeId} is derived from its inputs; only an asserted signal is set`);
        const changed=setLevel(node,value,'set');return {ok:true,node:nodeId,value:s.levels[nodeId]??0,changed};
      },
      // Schedule an operation at a time: {set:{node,value}} | {toggle:{node}} | {inject:{node,channel,payload,principal}}.
      at(time,action={}){
        const t=Math.max(s.time,Number(time)||0);
        if(action.inject){const r=sim.inject(action.inject.node,{...action.inject,at:t});return r}
        if(!(action.set||action.toggle))return refusal('BAD_ACTION','An action is {set}, {toggle} or {inject}');
        const id=(action.set||action.toggle).node;if(!g.nodes.has(id))return refusal('UNKNOWN_NODE',`No component ${id}`);
        if(g.nodes.get(id).signal.mode!=='asserted')return refusal('DERIVED_SIGNAL',`${id} is derived; only an asserted signal is set`);
        schedule(t,{kind:'action',action:clone(action)});return {ok:true,at:t};
      },
      levels:()=>Object.fromEntries([...g.nodes.values()].map(n=>[n.id,{value:s.levels[n.id]??0,kind:n.signal.kind,mode:n.signal.mode}])),
      edges({node=null,since=null}={}){return {ok:true,edges:s.edges.filter(e=>(!node||e.node===node)&&(since==null||e.at>=since)).map(clone)}},
      parked:()=>Object.values(s.parked).map(clone),
      resume(parkId,{decision='approve',payload,reason}={}){
        const p=s.parked[parkId];if(!p)return refusal('UNKNOWN_PARK',`Nothing parked as ${parkId}`);
        delete s.parked[parkId];const m=s.messages[p.messageId],node=g.nodes.get(p.node);
        log('resumed',{node:node.id,messageId:m.id,parkId,decision});
        if(decision!=='approve'){refuse(m,node.id,reason||`rejected at ${node.label||node.id}`);return {ok:true,decision}}
        if(payload!==undefined)m.payload=isObject(m.payload)&&isObject(payload)?{...m.payload,...clone(payload)}:clone(payload);
        hop(m,node.id,'resumed',{decision});
        continueAt(node,m,p.wireId);return {ok:true,decision};
      },
      reconcile(effectKey,{confirmed,result=null}={}){
        const e=s.effects[effectKey];if(!e||e.status!=='ambiguous')return refusal('NOT_AMBIGUOUS',`Effect ${effectKey} is not awaiting reconciliation`);
        if(confirmed){Object.assign(e,{status:'confirmed',confirmedAt:s.time,result:clone(result),reconciled:true})}else delete s.effects[effectKey];
        log('effect-reconciled',{effectKey,confirmed:!!confirmed});return {ok:true,effectKey,status:confirmed?'confirmed':'cleared'};
      },
      trace(messageId){const m=s.messages[messageId];if(!m)return refusal('UNKNOWN_MESSAGE',`No message ${messageId}`);return {ok:true,message:clone(m)}},
      lineage(rootId){return {ok:true,root:rootId,messages:Object.values(s.messages).filter(m=>m.root===rootId).map(m=>({id:m.id,parent:m.parent,status:m.status,last:m.hops.at(-1)}))}},
      taps(nodeId){return {ok:true,node:nodeId,arrivals:Object.values(s.messages).filter(m=>m.hops.some(h=>h.node===nodeId&&h.event==='arrived')).map(m=>({id:m.id,root:m.root,channel:m.channel,payload:clone(m.payload),status:m.status}))}},
      effects:()=>clone(s.effects),
      refusals:()=>clone(s.refusals),
      receipts:()=>clone(s.receipts),
      log:()=>clone(s.log),
      state:()=>({time:s.time,pending:s.queue.length,parked:Object.keys(s.parked).length,messages:Object.keys(s.messages).length,refusals:s.refusals.length,effects:Object.keys(s.effects).length,edges:s.edges.length,high:Object.values(s.levels).filter(v=>v>0).length}),
      // The full engine state as JSON; restore it with createSimulation(doc, {restore}).
      snapshot:()=>clone(s),
      setHandler(name,spec){handlers[name]=spec;return {ok:true,name}}
    };
    return {ok:true,sim};
  }

  // ---- Scenarios -----------------------------------------------------------------------
  // {handlers, steps:[{inject:{node,channel,payload}} | {run:{until}} | {resume:{node, decision, payload}}
  //   | {restart:true} | {reconcile:{effectKey, confirmed}}], expect:{taps:{node:n}, refusals:n, effects:{confirmed:n}, parked:n}}
  function runScenario(doc,scenario,options={}){
    const sc=isObject(scenario?.data)?scenario.data:scenario;
    if(!isObject(sc)||!Array.isArray(sc.steps))return refusal('BAD_SCENARIO','A scenario needs steps[]');
    const handlers={...(sc.handlers||{}),...(options.handlers||{})};
    let made=createSimulation(doc,{handlers});if(!made.ok)return made;
    let sim=made.sim;const notes=[];
    for(const [i,step] of sc.steps.entries()){
      if(step.inject){const r=sim.inject(step.inject.node,step.inject);if(!r.ok)return {...r,step:i}}
      else if(step.resume){
        const p=sim.parked().find(x=>!step.resume.node||x.node===step.resume.node);
        if(!p)return refusal('NOTHING_PARKED',`step ${i}: nothing parked${step.resume.node?' at '+step.resume.node:''}`,{step:i,log:sim.log()});
        sim.resume(p.id,step.resume);
      }
      else if(step.restart){
        // Kill and restart the engine from its durable snapshot, as a process restart would.
        made=createSimulation(doc,{handlers,restore:sim.snapshot()});if(!made.ok)return made;sim=made.sim;notes.push({step:i,restarted:true});
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

  // ---- One session, one dispatch: served identically by the browser API, HTTP and MCP -----
  function scenariosOf(doc){return (doc?.references||[]).filter(r=>r.kind==='scenario')}
  function createSession(){
    let sim=null,startedAt=null,startedRevision=null;
    const need=()=>sim?null:refusal('NO_SIMULATION','Start a simulation first (schematic.sim.start)');
    const actions={
      'graph.query':(doc,a)=>query(doc,a.verb,a.args||{}),
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
  function tools(){
    const obj=(properties,required=[])=>({type:'object',properties,required,additionalProperties:false});
    return [
      {name:'schematic.graph.query',description:`Read-only graph query. verb: ${Object.keys(QUERIES).join(' | ')}. args e.g. {from,to} for paths/cut/reach, {componentId} for boundary, {format: jgf|dot|graphml} for export.`,inputSchema:obj({verb:{type:'string',enum:Object.keys(QUERIES)},args:{type:'object'}},['verb'])},
      {name:'schematic.sim.start',description:'Start a message simulation over the current document. handlers maps a handler name to {kind: stub | fixture}; scenarioId borrows a saved scenario\'s handlers. A handler a node names but nobody registered refuses its messages.',inputSchema:obj({handlers:{type:'object'},scenarioId:{type:'string'}})},
      {name:'schematic.sim.stop',description:'Discard the running simulation.',inputSchema:obj({})},
      {name:'schematic.sim.inject',description:'Emit a message from a component (it leaves by that component\'s outgoing wires). principal names who acts; a plane with an ACL checks it at its boundary.',inputSchema:obj({node:{type:'string'},channel:{type:'string'},payload:{},at:{type:'number'},principal:{type:'string'}},['node'])},
      {name:'schematic.sim.set',description:'Assert a signal: set a lever, source or other asserted node to a level (binary 0|1, continuous 0..1). A derived signal is refused: it is computed from its inputs.',inputSchema:obj({node:{type:'string'},value:{type:'number',minimum:0,maximum:1}},['node','value'])},
      {name:'schematic.sim.at',description:'Schedule an operation at a simulation time (ms): {set:{node,value}} | {toggle:{node}} | {inject:{node,channel,payload,principal}}.',inputSchema:obj({time:{type:'number'},set:{type:'object'},toggle:{type:'object'},inject:{type:'object'}},['time'])},
      {name:'schematic.sim.advance',description:'Drive the clock: advance simulation time by ms, processing everything due (clocks, levels, messages).',inputSchema:obj({ms:{type:'number',minimum:0}},['ms'])},
      {name:'schematic.sim.tick',description:'Take the next instant n times: process every event due at the next scheduled time.',inputSchema:obj({n:{type:'integer',minimum:1}})},
      {name:'schematic.sim.step',description:'Process the next n events.',inputSchema:obj({n:{type:'integer',minimum:1}})},
      {name:'schematic.sim.run',description:'Process events until the queue is empty, a time is reached, or maxEvents.',inputSchema:obj({until:{type:'number'},maxEvents:{type:'integer',minimum:1}})},
      {name:'schematic.sim.resume',description:'Resume a message parked at a human step: decision approve | reject, optional payload merged in.',inputSchema:obj({parkId:{type:'string'},decision:{type:'string',enum:['approve','reject']},payload:{},reason:{type:'string'}},['parkId'])},
      {name:'schematic.sim.reconcile',description:'Settle an ambiguous effect: confirmed true records it as done (it will not repeat), false clears it for retry.',inputSchema:obj({effectKey:{type:'string'},confirmed:{type:'boolean'},result:{}},['effectKey','confirmed'])},
      {name:'schematic.sim.inspect',description:'Read simulation state. what: state | levels | edges | parked | log | effects | refusals | receipts | trace | taps | lineage | snapshot; id names the message (trace, lineage) or component (taps, edges).',inputSchema:obj({what:{type:'string'},id:{type:'string'}})},
      {name:'schematic.sim.scenario',description:'Run a saved scenario (document.references kind scenario) or an inline one in a fresh engine and return its checks as evidence.',inputSchema:obj({id:{type:'string'},scenario:{type:'object'},handlers:{type:'object'}})},
      {name:'schematic.sim.scenarios',description:'List the scenarios saved in the document.',inputSchema:obj({})}
    ];
  }

  return {POLICIES,DEFAULT_LATENCY_MS,build,query,queries:Object.keys(QUERIES),createSimulation,runScenario,createSession,tools};
});
