'use strict';
// 0.1 Beta concern: Component, Port, Wire, containment, and normalization model.

const byId=id=>SYMBOLS.find(s=>s.id===id);
const Attachment=SovSchematicAttachment;
function componentAttachmentPointIds(n){return Attachment.pointIds(n)}
function componentAttachmentPoints(n){return Attachment.descriptors(n,componentConfig(n).ports)}
function componentAttachmentPoint(n,id){const spec=Attachment.resolveSpec(n,id);if(!spec)return null;return {...spec,config:componentConfig(n).ports[spec.compatId]}}
function componentPortIds(n){return componentAttachmentPointIds(n)} // compatibility alias; values are canonical 0D point ids.
function componentPortCount(n){return componentAttachmentPointIds(n).length}
function isAttachmentSelectionValue(value){return typeof value==='string'&&(value.startsWith('point:')||value.startsWith('port:'))}
function localCanvasId(kind,id){return `canvas:${kind}:${id}`}
function canvasDimensionForKind(kind,entity=null){if(kind==='wire')return 1;if(kind==='port')return 0;if(kind==='component'){const d=Number(entity?.form?.dimension);return [0,1,2].includes(d)?d:2}return 2}
function ensureEntityCanvas(entity,kind,{defaultState=null}={}){
  if(!entity)return null;
  const legacyContains=!!entity.config?.presentation?.contains;
  if(!entity.canvas||typeof entity.canvas!=='object')entity.canvas={};
  entity.canvas.id=localCanvasId(kind,entity.id);
  entity.canvas.scope='local';
  entity.canvas.dimension=canvasDimensionForKind(kind,entity);
  if(!['open','closed'].includes(entity.canvas.state))entity.canvas.state=defaultState||(kind==='wire'?'open':legacyContains?'open':'closed');
  return entity.canvas;
}
function componentCanvas(node){return ensureEntityCanvas(node,'component')}
function wireCanvas(wire){return ensureEntityCanvas(wire,'wire',{defaultState:'open'})}
function canvasDescriptorById(id){
  if(!id||id===GLOBAL_CANVAS_ID)return {id:GLOBAL_CANVAS_ID,scope:'global',dimension:2,state:'open',ownerKind:'root',ownerId:null,label:'Global'};
  const component=nodes.find(n=>componentCanvas(n).id===id);
  if(component)return {...componentCanvas(component),ownerKind:'component',ownerId:component.id,label:(component.config?.label||byId(component.symbolId)?.name||component.id)};
  const wire=wires.find(w=>wireCanvas(w).id===id);
  if(wire)return {...wireCanvas(wire),ownerKind:'wire',ownerId:wire.id,label:(wire.config?.label||wire.id)};
  return null;
}
function availableCanvasDescriptors(){
  const result=[canvasDescriptorById(GLOBAL_CANVAS_ID)];
  for(const n of nodes){const c=componentCanvas(n);if(c.state==='open')result.push(canvasDescriptorById(c.id))}
  for(const w of wires){const c=wireCanvas(w);if(c.state==='open')result.push(canvasDescriptorById(c.id))}
  return result.filter(Boolean);
}
function canvasOwnerComponentId(canvasId){const d=canvasDescriptorById(canvasId);return d?.ownerKind==='component'?d.ownerId:null}
function canvasOwnerWireId(canvasId){const d=canvasDescriptorById(canvasId);return d?.ownerKind==='wire'?d.ownerId:null}
function canvasParentId(canvasId){
  const d=canvasDescriptorById(canvasId);if(!d||d.scope==='global')return null;
  if(d.ownerKind==='component'){const owner=nodes.find(n=>n.id===d.ownerId);return owner?.canvasId||GLOBAL_CANVAS_ID}
  return GLOBAL_CANVAS_ID;
}
function entityCanvasStateLabel(entity,kind){const c=ensureEntityCanvas(entity,kind);return `${c.state==='open'?'Open':'Closed'} · Local · ${c.dimension}D`}
function componentContainingCanvasId(node){return node?.canvasId||GLOBAL_CANVAS_ID}
function portExposedCanvasIds(node,portId){
  return node?SovSchematicData.portExposedCanvasIds(diagram,node.id,portId):[];
}
function portExposesCanvas(node,portId,canvasId){return portExposedCanvasIds(node,portId).includes(canvasId)}
function connectionCanvasId(a,aSide,b,bSide){
  return SovSchematicData.connectionReachability(diagram,a,aSide,b,bSide).canvasId;
}
function connectionReachability(a,aSide,b,bSide){
  return SovSchematicData.connectionReachability(diagram,a,aSide,b,bSide);
}
const escapeXML=s=>(s||'').replace(/[<>&"']/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&apos;'}[c]));
function glyph(id){ return `<svg viewBox="0 0 96 64"><use href="#sym-${id}"/></svg>`; }
function ensureComponentStructure(n){
  if(!n.boundary){
    n.boundary={
      kind:'boundary',
      shape:'blank',
      inside:{type:n.symbolId==='blank'?null:n.symbolId},
      outside:{type:'canvas'}
    };
  }
  if(!n.boundary.inside)n.boundary.inside={type:n.symbolId==='blank'?null:n.symbolId};
  if(!n.boundary.outside)n.boundary.outside={type:'canvas'};
  if(!('type' in n.boundary.inside))n.boundary.inside.type=n.symbolId==='blank'?null:n.symbolId;
  if(!n.boundary.outside.type)n.boundary.outside.type='canvas';
  if(!n.boundary.shape)n.boundary.shape='blank';

  const insideType=n.boundary.inside.type;
  n.type=insideType;
  n.symbolId=insideType||'blank';
  n.incomplete=insideType==null;

  if(!n.parts)n.parts={};
  if(!n.parts.points)n.parts.points={};
  if(!n.parts.ports)n.parts.ports={}; // compatibility projection only
  return n;
}
// The data core owns a contract's connections and their defaults (SovSchematicData.normalizePortConnections);
// the editor adds only the realized palette colours, which are appearance, not record.
function normalizePortConnections(port,defaultFlow='duplex',defaultSlot=0){
  SovSchematicData.normalizePortConnections(port,defaultFlow,defaultSlot);
  for(const connection of port.connections)connection.color=slotColor(connection.colorSlot);
  port.color=port.connections[port.activeConnection].color;
  return port;
}
function portConnection(port,index=port.activeConnection??0){
  normalizePortConnections(port);
  const i=Math.max(0,Math.min(port.connectionCount-1,Number(index)||0));
  return port.connections[i];
}
// Temporary aliases keep old render paths deterministic during this migration.
const normalizePortChannels=normalizePortConnections;
const activePortChannel=portConnection;
function portFlowLabel(flow){
  return ({in:'Input',out:'Output',duplex:'Input + Output',control:'Trigger'})[flow]||'Input + Output';
}
function portAccessLabel(access){
  return ({none:'None',read:'Read',write:'Write','read-write':'Read + Write'})[access]||'Read + Write';
}
function accessAllows(access,operation){
  if(operation==='none')return true;
  return access==='read-write'||access===operation;
}
function portAllowsAccess(port,operation){
  return accessAllows(portConnection(port).access,operation);
}
function componentSignalLabel(mode){
  return ({source:'Source',relay:'On input',passive:'Passive'})[mode]||'Source';
}
function normalizeSignalMode(cfg){
  if(!['source','relay','passive'].includes(cfg.signalMode))cfg.signalMode='source';
  return cfg.signalMode;
}
function portCanReceive(port){
  const flow=portConnection(port).flow;
  return flow==='in' || flow==='duplex' || flow==='control';
}
function portCanEmit(port){
  const flow=portConnection(port).flow;
  return flow==='out' || flow==='duplex';
}
function endpointAttachmentPoint(w,end){
  if(SovSchematicData.isFreeEndpoint(w?.[end+'Attachment']))return null;
  const ref=Attachment.wireEndpointRef(w,end,nodes);if(!ref)return null;
  const node=nodes.find(n=>n.id===ref.componentId);if(!node)return null;
  return {...ref,node,config:componentConfig(node).ports[ref.compatId]};
}
// A carrier end is bound to a component's attachment point or free in world space.
function carrierEndpoint(w,end){
  const att=w?.[end+'Attachment'];
  if(SovSchematicData.isFreeEndpoint(att))return {kind:'free',pos:{x:Number(att.x)||0,y:Number(att.y)||0},node:null,pointId:null};
  const bound=endpointAttachmentPoint(w,end);
  if(!bound)return null;
  return {kind:'bound',node:bound.node,pointId:bound.pointId,compatId:bound.compatId,pos:portPos(bound.node,bound.pointId)};
}
function carrierEndpointPos(w,end){return carrierEndpoint(w,end)?.pos||null}
function carrierEndBound(w,end){return carrierEndpoint(w,end)?.kind==='bound'}
function carrierIsRenderable(w){
  for(const end of ['a','b']){const ep=carrierEndpoint(w,end);if(!ep)return false;if(ep.kind==='bound'&&isEffectivelyHidden(ep.node))return false}
  return true;
}
function endpointPortConfig(w,end){return endpointAttachmentPoint(w,end)?.config||null}
function endpointAllowsReceive(w,end){
  const p=endpointPortConfig(w,end);
  return !!p && portCanReceive(p);
}
function endpointAllowsEmit(w,end){
  const p=endpointPortConfig(w,end);
  return !!p && portCanEmit(p);
}
function endpointAllowsAccess(w,end,operation){
  const p=endpointPortConfig(w,end);
  return !!p && portAllowsAccess(p,operation);
}
function wireOperation(w,direction){
  const cfg=connectionConfig(w);
  const key=direction==='reverse'?'reverseOperation':'forwardOperation';
  return ['none','read','write'].includes(cfg[key])?cfg[key]:'none';
}
function wireOperationLabel(operation){
  return ({none:'Signal',read:'Read',write:'Write'})[operation]||'Signal';
}
function setEndpointConnectionFlow(w,end,flow){
  const p=endpointPortConfig(w,end);
  if(!p)return false;
  normalizePortConnections(p);
  const i=endpointConnectionIndex(w,end);
  if(!p.connections[i])return false;
  p.connections[i].flow=flow;
  return true;
}
function ensureDuplexEndpointFlows(w){
  if(w?.config?.direction!=='duplex')return false;
  const a=setEndpointConnectionFlow(w,'a','duplex');
  const b=setEndpointConnectionFlow(w,'b','duplex');
  return a&&b;
}

function wirePartPortConfig(w,part){
  if(!part.config)part.config={};
  Attachment.normalizeOwnedPoint(part,{ownerKind:'wire',ownerId:w.id,t:part.t??.5});
  part.legacyKind='port';
  part.canvasId=wireCanvas(w).id;

  // Determine the inherited default channel color directly from the parent
  // Wire's endpoint Port. Do not call connectionConfig()/wireChannelFor()
  // here; Wire normalization itself normalizes owned Parts.
  const sourcePort=endpointPortConfig(w,'a');
  const inheritedSlot=sourcePort
    ? portConnection(sourcePort,endpointConnectionIndex(w,'a')).colorSlot
    : 0;

  normalizePortConnections(part.config,'duplex',inheritedSlot);
  if(typeof part.config.label!=='string')part.config.label='';
  if(!['external','internal','both'].includes(part.config.face))part.config.face='external';
  return part.config;
}
// The Form's defaults and bounds are the data core's (normalizeFormInPlace); 3D is deferred to
// the post-Beta Space model.
function componentForm(n){
  if(!n.form||typeof n.form!=='object')n.form={};
  const legacy=componentCanvas(n),f=SovSchematicData.normalizeFormInPlace(n.form,legacy);
  legacy.state=f.regions.interior.state;legacy.dimension=f.dimension; // compatibility projection only
  return f;
}
function formDimensionLabel(f){return `${f.dimension}D · ${f.body.kind[0].toUpperCase()+f.body.kind.slice(1)}`}
function formHostsChildren(n){const f=componentForm(n);return f.dimension===2&&f.regions.interior.state==='open'}
function componentHostDescriptor(n){return canvasDescriptorById(n?.canvasId||GLOBAL_CANVAS_ID)||canvasDescriptorById(GLOBAL_CANVAS_ID)}
function componentHostedOnWire(n){return componentHostDescriptor(n)?.ownerKind==='wire'}
// The placement a host gives a component is the data core's (normalizePlacement).
function componentPlacement(n){return SovSchematicData.normalizePlacement(diagram,n)}
function componentIsPoint(n){return componentForm(n).dimension===0}
function componentIsPath(n){return componentForm(n).dimension===1}
function componentIsSurface(n){return componentForm(n).dimension===2}
// A primitive shows no type name of its own; only an authored label is drawn.
function componentTypeCaption(n,s=byId(n.symbolId)){return isPrimitiveSymbol(n.symbolId)?'':(s?.name||'')}
// Wires whose endpoint sits on one of this component's built-in points. Used to refuse
// attachment-default or type changes that would silently orphan a carrier.
function wiresOnBuiltinPoints(n){
  const ids=new Set(Attachment.builtinPointIds(n));
  return wires.filter(w=>(w.a===n.id&&ids.has(Attachment.pointId(n,w.aAttachment?.pointId||w.aSide)))||(w.b===n.id&&ids.has(Attachment.pointId(n,w.bAttachment?.pointId||w.bSide))));
}
function componentHostedOnComponentPath(n){return componentPlacement(n).kind==='path'}
function componentHostedOnComponentEdge(n){return componentPlacement(n).kind==='edge'}
function componentBackdropMode(n){
  const p=componentConfig(n).presentation;
  if(!['auto','none','body','frame'].includes(p.backdrop))p.backdrop='auto';
  return p.backdrop==='auto'?(componentHostedOnWire(n)?'none':'body'):p.backdrop;
}
// The record's defaults and bounds are the data core's (applyComponentDefaults, which also makes
// every exposed port's contract). The editor adds only projections the saved form strips: the
// realized colours, and the parts/boundary descriptors below.
function componentConfig(n){
  ensureComponentStructure(n);
  SovSchematicData.applyComponentDefaults(n);
  componentCanvas(n);componentForm(n);
  n.config.color=slotColor(n.config.colorSlot);
  const specs=Attachment.pointSpecs(n);
  const canonicalPointIds=new Set(specs.map(spec=>spec.id));
  if(!n.parts.points)n.parts.points={};
  for(const stale of Object.keys(n.parts.points))if(!canonicalPointIds.has(stale))delete n.parts.points[stale];
  n.parts.ports={}; // compatibility projection only; populated from authoritative point descriptors below.
  for(const spec of specs){
    const p=n.config.ports[spec.compatId];
    const active=activePortChannel(p); // realizes the connections' colours
    const point={
      kind:'attachment-point',dimension:0,id:spec.id,compatId:spec.compatId,role:spec.role,
      ownerKind:'component',ownerId:n.id,
      placement:{kind:spec.role==='self'?'self':'boundary',side:spec.side,t:Number.isFinite(Number(spec.t))?Number(spec.t):.5},side:spec.side,
      connectionCount:p.connectionCount,connections:p.connections.map(connection=>({...connection})),activeConnection:p.activeConnection,
      label:p.label,face:p.face,color:active.color,colorSlot:active.colorSlot,flow:active.flow,access:active.access,
      internal:{type:n.boundary.inside.type,channel:active.name,flow:active.flow,access:active.access},
      external:{type:n.boundary.outside.type,channel:active.name,flow:active.flow,access:active.access}
    };
    n.parts.points[spec.id]=point;
    n.parts.ports[spec.compatId]={...point,kind:'port',id:spec.compatId,pointId:spec.id};
  }
  return n.config;
}
function endpointConnectionCount(w,end){
  const port=endpointPortConfig(w,end);
  normalizePortConnections(port||{});
  return Math.max(1,port?.connectionCount||1);
}
// The index (bounded by the end's connection count, the former shared binding migrated) is the data core's.
function endpointConnectionIndex(w,end){return connectionConfig(w)[end==='a'?'aConnectionIndex':'bConnectionIndex']}
function endpointConnection(w,end){
  const port=endpointPortConfig(w,end);
  if(!port)return {id:'connection-1',name:'Connection 1',colorSlot:0,color:slotColor(0),flow:'duplex'};
  return {...portConnection(port,endpointConnectionIndex(w,end))};
}
function wireIOEnds(w){
  const direction=connectionConfig(w).direction;
  if(direction==='reverse')return {out:'b',in:'a'};
  return {out:'a',in:'b'};
}
function normalizeChannelMarker(value,fallback='1'){
  const s=String(value??'').trim();
  return (s||fallback).slice(0,12);
}
function wireEndpointMarker(w,end){return connectionConfig(w)[end==='a'?'aChannelMarker':'bChannelMarker']} // trimmed, at most 12, '1' when blank (data core)
function wireMarkerSummaryForPort(nodeId,pointId){
  const node=nodes.find(n=>n.id===nodeId),spec=node?Attachment.resolveSpec(node,pointId):null,compatId=spec?.compatId||pointId;
  return wires.filter(w=>(w.a===nodeId&&w.aSide===compatId)||(w.b===nodeId&&w.bSide===compatId)).map(w=>
    (w.a===nodeId&&w.aSide===compatId)?wireEndpointMarker(w,'a'):wireEndpointMarker(w,'b')
  );
}
function endpointMarkerDisplay(w,end){
  return wireEndpointMarker(w,end)||'1';
}
function wireOutConnection(w){
  return endpointConnection(w,wireIOEnds(w).out);
}
function wireInConnection(w){
  return endpointConnection(w,wireIOEnds(w).in);
}
function wireBoundaryColors(w){
  return {
    a:endpointConnection(w,'a').color,
    b:endpointConnection(w,'b').color
  };
}
// A Wire's defaults and bounds, its connection indexes and markers, a legacy colour and a duplex
// Wire's end flows are the data core's (applyWireDefaults); the editor adds its canvas descriptor.
function connectionConfig(w){
  wireCanvas(w);
  SovSchematicData.applyWireDefaults(diagram,w);
  return w.config;
}

function pointAlongPolyline(points,t=.5){
  if(!points?.length)return null;
  if(points.length===1)return {...points[0]};
  const segs=[];let total=0;
  for(let i=0;i<points.length-1;i++){
    const L=segmentLength(points[i],points[i+1]);segs.push(L);total+=L;
  }
  let target=Math.max(0,Math.min(1,t))*total,acc=0;
  for(let i=0;i<segs.length;i++){
    if(acc+segs[i]>=target){
      const A=points[i],B=points[i+1];
      const q=(target-acc)/Math.max(1e-6,segs[i]);
      return {x:A.x+(B.x-A.x)*q,y:A.y+(B.y-A.y)*q};
    }
    acc+=segs[i];
  }
  return {...points[points.length-1]};
}
function wirePartPoint(w,part){
  const i=wires.indexOf(w);
  const A=carrierEndpointPos(w,'a'),B=carrierEndpointPos(w,'b');
  if(!A||!B)return null;
  const points=stableRouteForWire(i,w,A,B,[]);
  return pointAlongPolyline(points,part?.t??part?.placement?.t??.5);
}
function connectionMidpoint(w,i){
  const A=carrierEndpointPos(w,'a'),B=carrierEndpointPos(w,'b');
  if(!A||!B)return null;
  const occupied=[];
  const points=stableRouteForWire(i,w,A,B,occupied);
  if(points.length<2)return null;
  let total=0;
  const lens=[];
  for(let k=0;k<points.length-1;k++){
    const L=segmentLength(points[k],points[k+1]);lens.push(L);total+=L;
  }
  let target=total/2,acc=0;
  for(let k=0;k<lens.length;k++){
    if(acc+lens[k]>=target){
      const A=points[k],B=points[k+1],t=(target-acc)/Math.max(1,lens[k]);
      return {x:A.x+(B.x-A.x)*t,y:A.y+(B.y-A.y)*t};
    }
    acc+=lens[k];
  }
  return points[Math.floor(points.length/2)];
}
