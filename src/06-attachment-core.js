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
  // 2D built-in points (left/right/top) are template defaults, not an ontology.
  // `config.attachmentDefaults='none'` exposes no built-ins: the surface is then
  // attachable only through hosted 0D Points and data-declared boundary points.
  const ATTACHMENT_DEFAULT_MODES=new Set(['standard','none']);
  function attachmentDefaults(entity){
    const mode=entity?.config?.attachmentDefaults;
    return ATTACHMENT_DEFAULT_MODES.has(mode)?mode:'standard';
  }
  // Connectivity follows the lower-dimensional host when a richer form is settled onto it.
  // A 2D ACT hosted by a Wire therefore exposes only the Wire-aligned 1D endpoints.
  function effectiveDimension(entity){return Math.min(intrinsicDimension(entity),hostDimension(entity))}
  function basePointSpecs(d,entity=null){
    if(d===0)return [{id:'self',compatId:'out',side:'point',role:'self',defaultFlow:'duplex',t:.5}];
    if(d===1)return [
      {id:'start',compatId:'in',side:'left',role:'endpoint',defaultFlow:'in',t:0},
      {id:'end',compatId:'out',side:'right',role:'endpoint',defaultFlow:'out',t:1}
    ];
    if(attachmentDefaults(entity)==='none')return [];
    return [
      {id:'left',compatId:'in',side:'left',role:'boundary',defaultFlow:'in',t:.5},
      {id:'right',compatId:'out',side:'right',role:'boundary',defaultFlow:'out',t:.5},
      {id:'top',compatId:'control',side:'top',role:'boundary',defaultFlow:'control',t:.5}
    ];
  }
  function customPointSpecs(entity,d,base){
    // 0.1 RC seam: built-in dimensional points are defaults, not a permanent
    // cardinality ceiling. Full cell/facet grammar remains post-RC; a 2D
    // template may already declare extra boundary attachment points as data.
    if(d!==2)return [];
    const authored=Array.isArray(entity?.config?.attachmentPoints)?entity.config.attachmentPoints:[];
    const usedIds=new Set(base.map(x=>x.id)),usedCompat=new Set(base.map(x=>x.compatId));
    const out=[];
    for(const raw of authored){
      if(!raw||typeof raw!=='object')continue;
      const id=String(raw.id||'').trim();if(!id||usedIds.has(id))continue;
      const side=['left','right','top','bottom'].includes(raw.side)?raw.side:null;if(!side)continue;
      let compatId=String(raw.compatId||id).trim()||id;
      if(usedCompat.has(compatId))compatId=id;
      if(usedCompat.has(compatId))continue;
      const t=Math.max(0,Math.min(1,Number.isFinite(Number(raw.t))?Number(raw.t):.5));
      const defaultFlow=['in','out','control','duplex','trigger'].includes(raw.defaultFlow)?raw.defaultFlow:'duplex';
      out.push({id,compatId,side,role:'boundary',defaultFlow,t,authored:true});
      usedIds.add(id);usedCompat.add(compatId);
    }
    return out;
  }
  function pointSpecs(entity){
    const d=effectiveDimension(entity),base=basePointSpecs(d,entity);
    return [...base,...customPointSpecs(entity,d,base)];
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
  return {intrinsicDimension,hostDimension,effectiveDimension,attachmentDefaults,pointSpecs,builtinPointIds,pointIds,resolveSpec,pointId,compatId,defaultCompatId,descriptor,descriptors,normalizeOwnedPoint,wireEndpointRef,syncWireEndpoint};
});
