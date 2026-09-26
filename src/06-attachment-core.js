'use strict';
// 0.1 Beta concern: canonical 0D attachment-point topology and compatibility mapping.
// This module is intentionally pure: no DOM, routing, rendering, or editor state.
(function(root,factory){
  const api=factory();
  root.SovSchematicAttachment=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  const VALID_DIMENSIONS=new Set([0,1,2]);
  function intrinsicDimension(entity){
    const d=Number(entity?.form?.dimension);
    return VALID_DIMENSIONS.has(d)?d:2;
  }
  function hostDimension(entity){
    const placement=entity?.placement||{};
    if(placement.kind==='wire'||String(entity?.canvasId||'').startsWith('canvas:wire:'))return 1;
    if(placement.kind==='edge'||placement.kind==='path')return 1;
    return 2;
  }
  // A 2D Component's ports are declared data, never assumed here. Under
  // `config.attachmentDefaults='standard'` (explicit or implied) it exposes its
  // template's declared ports, then its authored `config.attachmentPoints` as
  // additions; under 'none' the authored list is the complete set. The data core
  // registers the template lookup (`useTemplatePorts`), so this module holds no
  // port set of its own and stays free of DOM, rendering and editor state.
  const ATTACHMENT_DEFAULT_MODES=new Set(['standard','none']);
  const PORT_SIDES=['left','right','top','bottom'];
  const PORT_FLOWS=['in','out','control','duplex','trigger'];
  const DEFAULT_CHANNELS=[{id:'main'}];
  let templatePortsOf=()=>[];
  function useTemplatePorts(lookup){templatePortsOf=typeof lookup==='function'?lookup:()=>[];return templatePortsOf}
  function attachmentDefaults(entity){
    const mode=entity?.config?.attachmentDefaults;
    return ATTACHMENT_DEFAULT_MODES.has(mode)?mode:'standard';
  }
  // Absent channels read as the one default channel, `main`. A channel's `merge` (the
  // merge@1 parameters for same-tick fan-in) is carried as written; the data core checks
  // it on edit and the state space reports it at load.
  function portChannels(port){
    const out=[],seen=new Set();
    for(const c of Array.isArray(port?.channels)?port.channels:[]){
      const id=String(c?.id??'').trim();if(!id||seen.has(id))continue;
      seen.add(id);const channel={id};
      if(c&&typeof c==='object'&&c.merge!==undefined)channel.merge=JSON.parse(JSON.stringify(c.merge));
      out.push(channel);
    }
    return out.length?out:DEFAULT_CHANNELS.map(c=>({...c}));
  }
  function channelIds(spec){return portChannels(spec).map(c=>c.id)}
  // Connectivity follows the lower-dimensional host when a richer form is settled onto it.
  // A 2D ACT hosted by a Wire therefore exposes only the Wire-aligned 1D endpoints.
  function effectiveDimension(entity){return Math.min(intrinsicDimension(entity),hostDimension(entity))}
  function declaredSpec(raw,{authored=false}={}){
    if(!raw||typeof raw!=='object')return null;
    const id=String(raw.id||'').trim();if(!id)return null;
    const side=PORT_SIDES.includes(raw.side)?raw.side:null;if(!side)return null;
    const compatId=String(raw.compatId||id).trim()||id;
    const t=Math.max(0,Math.min(1,Number.isFinite(Number(raw.t))?Number(raw.t):.5));
    // `flow` is the direction; legacy `defaultFlow` is read only when `flow` is absent.
    const flowRaw=raw.flow!==undefined?raw.flow:raw.defaultFlow;
    const flow=PORT_FLOWS.includes(flowRaw)?flowRaw:'duplex';
    const spec={id,compatId,side,role:'boundary',defaultFlow:flow,flow,t,channels:portChannels(raw)};
    if(typeof raw.label==='string'&&raw.label)spec.label=raw.label;
    if(authored)spec.authored=true;
    return spec;
  }
  function templatePointSpecs(entity){
    if(attachmentDefaults(entity)==='none')return [];
    // A glyph that declares its terminals as points (NOTATION-MODEL.md §2) gives the card one
    // point per terminal: a two-input gate has two inputs.
    const glyphPoints=(typeof globalThis!=='undefined'?globalThis:{}).SovSchematicNotation?.pointsFor?.(entity?.symbolId);
    // A terminal is shaped like a declared template port: its flow is its default flow, on `main`.
    if(glyphPoints)return glyphPoints.map(p=>({...p,role:'boundary',flow:p.defaultFlow,channels:[{id:'main'}]}));
    const declared=templatePortsOf(entity?.symbolId,entity);
    return (Array.isArray(declared)?declared:[]).map(raw=>declaredSpec(raw)).filter(Boolean);
  }
  // A Point (0D) has one port, `self`. It may declare it, to give it channels and merges, as a
  // single `config.attachmentPoints` entry `{id: 'self', flow?, channels}` with no side or t (a
  // placeholder side/t, as the first runtime wrote, is read the same way and cleaned on load).
  function selfDeclaration(entity){
    const list=Array.isArray(entity?.config?.attachmentPoints)?entity.config.attachmentPoints:[];
    const raw=list.find(p=>p&&typeof p==='object'&&String(p.id??'').trim()==='self');
    if(!raw)return null;
    const declared={id:'self'};
    if(PORT_FLOWS.includes(raw.flow))declared.flow=raw.flow;
    declared.channels=portChannels(raw);
    return declared;
  }
  function basePointSpecs(d,entity=null){
    if(d===0){
      const spec={id:'self',compatId:'out',side:'point',role:'self',defaultFlow:'duplex',t:.5},declared=selfDeclaration(entity);
      if(declared){spec.channels=declared.channels;if(declared.flow){spec.flow=declared.flow;spec.defaultFlow=declared.flow}}
      return [spec];
    }
    if(d===1)return [
      {id:'start',compatId:'in',side:'left',role:'endpoint',defaultFlow:'in',t:0},
      {id:'end',compatId:'out',side:'right',role:'endpoint',defaultFlow:'out',t:1}
    ];
    return templatePointSpecs(entity);
  }
  function customPointSpecs(entity,d,base,{keepCollisions=false}={}){
    // Authored ports: additions to the template's under 'standard', the whole set under
    // 'none'. Only a 2D surface exposes them. An entry that names no valid side is not
    // exposed. An entry whose id is already taken (as an id or a compatId) is dropped,
    // unless `keepCollisions` asks it kept: it is then exposed under a fresh id
    // (`<id>~2`, `<id>~3`, ...: the first not taken), tagged `originalId` so a caller
    // (load cleaning) can decide whether a bound Wire still needs it. A compatId already
    // taken falls back to the entry's own id.
    if(d!==2)return [];
    const authored=Array.isArray(entity?.config?.attachmentPoints)?entity.config.attachmentPoints:[];
    const used=new Set(base.flatMap(x=>[x.id,x.compatId]));
    const out=[];
    for(const raw of authored){
      const spec=declaredSpec(raw,{authored:true});if(!spec)continue;
      if(used.has(spec.id)){
        if(!keepCollisions)continue;
        const originalId=spec.id;
        let n=2,candidate=`${originalId}~${n}`;
        while(used.has(candidate))candidate=`${originalId}~${++n}`;
        spec.id=candidate;spec.originalId=originalId;
      }
      if(used.has(spec.compatId)||spec.compatId===spec.id)spec.compatId=spec.id;
      out.push(spec);
      used.add(spec.id);used.add(spec.compatId);
    }
    return out;
  }
  // The authored ports a 2D surface of this record exposes, whatever its current host.
  // `{keepCollisions:true}` keeps a colliding entry under a fresh id (`originalId` marks
  // it) instead of dropping it; load cleaning uses this to decide, per Wire, whether the
  // entry is still needed.
  function authoredPointSpecs(entity,opts){return customPointSpecs(entity,2,templatePointSpecs(entity),opts)}
  // A 2D boundary point may be moved anywhere on its host's perimeter:
  // `config.ports[compatId].boundary = {side, t}` places it; `placed` records that the
  // position is authored, so no default (such as a glyph's axis) overrides it.
  const SIDES=new Set(['left','right','top','bottom']);
  function placedBoundary(entity,spec){
    const b=entity?.config?.ports?.[spec.compatId]?.boundary;
    if(!b||typeof b!=='object'||!SIDES.has(b.side))return spec;
    const t=Math.max(0,Math.min(1,Number.isFinite(Number(b.t))?Number(b.t):.5));
    return {...spec,side:b.side,t,placed:true};
  }
  function pointSpecs(entity){
    const d=effectiveDimension(entity),base=basePointSpecs(d,entity);
    const specs=[...base,...customPointSpecs(entity,d,base)];
    return d===2?specs.map(spec=>spec.role==='boundary'?placedBoundary(entity,spec):spec):specs;
  }
  function builtinPointIds(entity){return basePointSpecs(effectiveDimension(entity),entity).map(x=>x.id)}
  function pointIds(entity){return pointSpecs(entity).map(x=>x.id)}
  function resolveSpec(entity,id){
    const value=String(id??'');
    const specs=pointSpecs(entity);
    return specs.find(x=>x.id===value||x.compatId===value)||null;
  }
  function pointId(entity,id){return resolveSpec(entity,id)?.id||null}
  function compatId(entity,id){return resolveSpec(entity,id)?.compatId||null}
  function defaultCompatId(entity,preference='end'){
    const specs=pointSpecs(entity);
    return (preference==='start'?specs[0]:specs.at(-1))?.compatId||null;
  }
  function descriptor(entity,id,legacyPorts={}){
    const spec=resolveSpec(entity,id);if(!spec)return null;
    const config=legacyPorts?.[spec.compatId]||null;
    return {...spec,kind:'attachment-point',dimension:0,ownerKind:'component',ownerId:entity?.id||null,config};
  }
  function descriptors(entity,legacyPorts={}){return pointSpecs(entity).map(spec=>descriptor(entity,spec.id,legacyPorts))}
  function normalizeOwnedPoint(record,{ownerKind='wire',ownerId=null,t=.5}={}){
    const point=record||{};point.kind='attachment-point';point.type='point';point.dimension=0;point.ownerKind=ownerKind;point.ownerId=ownerId;
    if(!point.placement||typeof point.placement!=='object')point.placement={kind:ownerKind==='wire'?'wire':'self',t};
    if(ownerKind==='wire'){point.placement.kind='wire';point.placement.t=Math.max(.04,Math.min(.96,Number(point.placement.t??point.t??t)||t));point.t=point.placement.t}
    return point;
  }
  function wireEndpointRef(wire,end,components=[]){
    const componentId=end==='a'?wire?.a:wire?.b;
    const component=components.find?.(x=>x.id===componentId)||null;
    if(!component)return null;
    const stored=end==='a'?wire?.aAttachment:wire?.bAttachment;
    const legacy=end==='a'?wire?.aSide:wire?.bSide;
    const spec=resolveSpec(component,stored?.pointId||legacy)||pointSpecs(component)[end==='a'?pointSpecs(component).length-1:0];
    if(!spec)return null; // the component exposes no attachment point for this endpoint
    return {componentId,pointId:spec.id,compatId:spec.compatId,spec};
  }
  function syncWireEndpoint(wire,end,component,id){
    const spec=resolveSpec(component,id)||pointSpecs(component)[end==='a'?pointSpecs(component).length-1:0];
    if(!spec)return null; // leave the stored reference untouched; validation reports it as unreachable
    const key=end==='a'?'aAttachment':'bAttachment';
    wire[key]={kind:'attachment-ref',componentId:component.id,pointId:spec.id};
    if(end==='a')wire.aSide=spec.compatId;else wire.bSide=spec.compatId;
    return wire[key];
  }
  return {PORT_SIDES,PORT_FLOWS,useTemplatePorts,selfDeclaration,portChannels,channelIds,declaredSpec,templatePointSpecs,authoredPointSpecs,intrinsicDimension,hostDimension,effectiveDimension,attachmentDefaults,pointSpecs,builtinPointIds,pointIds,resolveSpec,pointId,compatId,defaultCompatId,descriptor,descriptors,normalizeOwnedPoint,wireEndpointRef,syncWireEndpoint};
});
