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
function normalizePortConnections(port,defaultFlow='duplex',defaultSlot=0){
  // Migrate the prior channel vocabulary without losing authored state.
  if(!Number.isInteger(port.connectionCount)){
    port.connectionCount=Number.isInteger(port.channelCount)?port.channelCount:1;
  }
  port.connectionCount=Math.max(1,Math.min(8,port.connectionCount));

  if(!Array.isArray(port.connections)){
    port.connections=Array.isArray(port.channels)?port.channels.map(ch=>({...ch})):[];
  }

  if(!port.connections.length){
    port.connections.push({
      id:'connection-1',
      name:'Connection 1',
      colorSlot:normalizeSlot(port.colorSlot,defaultSlot),
      flow:['in','out','duplex','control'].includes(port.flow)?port.flow:defaultFlow,
      access:['none','read','write','read-write'].includes(port.access)?port.access:'read-write'
    });
  }

  while(port.connections.length<port.connectionCount){
    const i=port.connections.length;
    port.connections.push({
      id:`connection-${i+1}`,
      name:`Connection ${i+1}`,
      colorSlot:defaultSlot,
      flow:defaultFlow,
      access:'read-write'
    });
  }
  port.connections=port.connections.slice(0,port.connectionCount);

  if(typeof port.label!=='string')port.label='';
  port.connections.forEach((connection,i)=>{
    connection.id=`connection-${i+1}`;
    connection.name=`Connection ${i+1}`;
    connection.colorSlot=normalizeSlot(connection.colorSlot,defaultSlot);
    if(!['in','out','duplex','control'].includes(connection.flow))connection.flow=defaultFlow;
    if(!['none','read','write','read-write'].includes(connection.access))connection.access='read-write';
    connection.color=slotColor(connection.colorSlot);
  });

  if(!Number.isInteger(port.activeConnection)){
    port.activeConnection=Number.isInteger(port.activeChannel)?port.activeChannel:0;
  }
  port.activeConnection=Math.max(0,Math.min(port.connectionCount-1,port.activeConnection));

  const active=port.connections[port.activeConnection];

  // Compatibility projection while the old property names disappear.
  port.channelCount=port.connectionCount;
  port.channels=port.connections;
  port.activeChannel=port.activeConnection;
  port.channel=active.name;
  port.colorSlot=active.colorSlot;
  port.color=active.color;
  port.flow=active.flow;
  port.access=active.access;
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
function componentForm(n){
  if(!n.form)n.form={};
  const f=n.form,legacy=componentCanvas(n),dim=Number(f.dimension);
  f.dimension=[0,1,2].includes(dim)?dim:2; // 3D is deferred to the post-Beta Space model.
  if(!f.body)f.body={};
  const defaultKind=['point','path','surface'][f.dimension];
  if(!['point','path','surface'].includes(f.body.kind))f.body.kind=defaultKind;
  if(typeof f.body.material!=='string'||!f.body.material)f.body.material='generic';
  f.body.thickness=Math.max(0,Math.min(128,Number(f.body.thickness)||0));
  if(!f.frame)f.frame={};
  if(!['none','frame','shell'].includes(f.frame.mode))f.frame.mode='none';
  f.frame.thickness=Math.max(0,Math.min(64,Number(f.frame.thickness)||(f.frame.mode==='none'?0:12)));
  f.frame.depth=Math.max(0,Math.min(128,Number(f.frame.depth)||0));
  if(!f.regions)f.regions={};if(!f.regions.interior)f.regions.interior={};
  if(!['open','closed'].includes(f.regions.interior.state))f.regions.interior.state=legacy.state==='open'?'open':'closed';
  if(f.dimension<2)f.regions.interior.state='closed';
  legacy.state=f.regions.interior.state;legacy.dimension=f.dimension; // compatibility projection only
  return f;
}
function formDimensionLabel(f){return `${f.dimension}D · ${f.body.kind[0].toUpperCase()+f.body.kind.slice(1)}`}
function formHostsChildren(n){const f=componentForm(n);return f.dimension===2&&f.regions.interior.state==='open'}
function componentHostDescriptor(n){return canvasDescriptorById(n?.canvasId||GLOBAL_CANVAS_ID)||canvasDescriptorById(GLOBAL_CANVAS_ID)}
function componentHostedOnWire(n){return componentHostDescriptor(n)?.ownerKind==='wire'}
function componentPlacement(n){
  const host=componentHostDescriptor(n);
  if(!n.placement||typeof n.placement!=='object')n.placement=host?.ownerKind==='wire'?{kind:'wire',wireId:host.ownerId,t:.5}:{kind:'surface',x:n.x,y:n.y};
  if(host?.ownerKind==='wire'){
    n.placement.kind='wire';n.placement.wireId=host.ownerId;n.placement.t=Math.max(.02,Math.min(.98,Number(n.placement.t)||.5));
  }else if(host?.ownerKind==='component'&&['path','edge'].includes(n.placement.kind)){
    n.placement.hostId=host.ownerId;n.placement.t=Math.max(0,Math.min(1,Number(n.placement.t)||.5));
  }else{
    n.placement.kind='surface';n.placement.x=Number(n.x)||0;n.placement.y=Number(n.y)||0;delete n.placement.wireId;delete n.placement.hostId;delete n.placement.t;delete n.placement.side;
  }
  return n.placement;
}
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
function componentConfig(n){
  ensureComponentStructure(n);
  if(!n.config)n.config={};
  if(typeof n.config.label!=='string')n.config.label=n.label||'';
  if(!n.config.presentation)n.config.presentation={};
  const presentation=n.config.presentation;
  if(!presentation.graphic)presentation.graphic={kind:'symbol',ref:presentation.svgRef||`sym-${n.symbolId||'blank'}`,svg:''};
  if(!['symbol','custom','none'].includes(presentation.graphic.kind))presentation.graphic.kind='symbol';
  if(typeof presentation.graphic.ref!=='string')presentation.graphic.ref=`sym-${n.symbolId||'blank'}`;
  if(typeof presentation.graphic.svg!=='string')presentation.graphic.svg='';
  if(!presentation.size)presentation.size={w:112,h:84};
  presentation.size.w=Math.max(80,Math.min(520,Number(presentation.size.w)||112));
  presentation.size.h=Math.max(64,Math.min(420,Number(presentation.size.h)||84));
  if(!['boundary','inside','outside','none'].includes(presentation.labelMode))presentation.labelMode='boundary';
  if(!Number.isInteger(presentation.interiorColorSlot))presentation.interiorColorSlot=n.config.colorSlot??0;
  presentation.interiorColorSlot=normalizeSlot(presentation.interiorColorSlot,0);
  if(typeof presentation.text!=='string')presentation.text='';
  const form=componentForm(n);
  if('contains' in presentation)delete presentation.contains; // legacy only; Form interior owns hosting state.
  if(typeof presentation.padding!=='number')presentation.padding=16;
  presentation.padding=Math.max(8,Math.min(36,presentation.padding));
  if(!['auto','none','body','frame'].includes(presentation.backdrop))presentation.backdrop='auto';
  if(!Number.isInteger(n.config.colorSlot)){
    n.config.colorSlot=/^#[0-9a-fA-F]{6}$/.test(n.config.color||'')?nearestSlot(n.config.color):0;
  }
  n.config.colorSlot=normalizeSlot(n.config.colorSlot,0);
  n.config.color=slotColor(n.config.colorSlot);
  normalizeSignalMode(n.config);
  if(!n.config.ports)n.config.ports={};
  const defaults={
    in:{side:'left',channel:'signal',color:'#171715',flow:'in'},
    out:{side:'right',channel:'signal',color:'#171715',flow:'out'},
    control:{side:'top',channel:'control',color:'#6c6c65',flow:'control'}
  };
  const specs=Attachment.pointSpecs(n);
  const canonicalPointIds=new Set(specs.map(spec=>spec.id));
  if(!n.parts.points)n.parts.points={};
  for(const stale of Object.keys(n.parts.points))if(!canonicalPointIds.has(stale))delete n.parts.points[stale];
  n.parts.ports={}; // compatibility projection only; populated from authoritative point descriptors below.
  // Only points the effective dimension exposes get a contract. Authored contracts for
  // points a dimension change hid are left in place so switching back restores them.
  const configuredCompatIds=new Set(specs.map(spec=>spec.compatId));
  for(const compatId of configuredCompatIds){
    const spec=specs.find(item=>item.compatId===compatId);
    const fallback=defaults[compatId]||{side:spec?.side||'point',channel:'signal',color:'#171715',flow:spec?.defaultFlow||'duplex'};
    const p=n.config.ports[compatId]||(n.config.ports[compatId]={});
    if(typeof p.label!=='string')p.label='';
    if(!['external','internal','both'].includes(p.face))p.face='external';
    if(!['left','right','top','bottom','point'].includes(p.side))p.side=fallback.side;
    normalizePortChannels(p,fallback.flow,0);
  }
  for(const spec of specs){
    const p=n.config.ports[spec.compatId];
    // Geometry belongs to the canonical attachment descriptor, not stale authored side metadata.
    p.side=spec.side;
    const active=activePortChannel(p);
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
function endpointConnectionIndex(w,end){
  const cfg=w.config||(w.config={});
  const key=end==='a'?'aConnectionIndex':'bConnectionIndex';

  // Migrate the former single shared binding to both endpoints.
  if(!Number.isInteger(cfg[key])){
    cfg[key]=Number.isInteger(cfg.channelIndex)?cfg.channelIndex:0;
  }
  cfg[key]=Math.max(0,Math.min(endpointConnectionCount(w,end)-1,cfg[key]));
  return cfg[key];
}
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
function wireEndpointMarker(w,end){
  const cfg=connectionConfig(w);
  const key=end==='a'?'aChannelMarker':'bChannelMarker';
  if(typeof cfg[key]!=='string'||!cfg[key].trim())cfg[key]='1';
  cfg[key]=normalizeChannelMarker(cfg[key],'1');
  return cfg[key];
}
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
function connectionConfig(w){
  wireCanvas(w);
  // A Wire is a carrier Path: 1D Form, carrier role, ends bound or free.
  if(!w.form||typeof w.form!=='object')w.form={};w.form.dimension=1;
  if(!w.form.body||typeof w.form.body!=='object')w.form.body={};w.form.body.kind='path';
  if(typeof w.form.body.material!=='string'||!w.form.body.material)w.form.body.material='generic';
  w.form.body.thickness=Math.max(0,Math.min(128,Number(w.form.body.thickness)||0));
  w.role='carrier';
  for(const end of ['a','b'])if(SovSchematicData.isFreeEndpoint(w[end+'Attachment'])){w[end]=null;w[end==='a'?'aSide':'bSide']=null}
  if(!w.config)w.config={};
  if(!['none','forward','reverse','duplex'].includes(w.config.direction))w.config.direction=w.duplex?'duplex':'forward';
  if(!['none','expected','required'].includes(w.config.reciprocity))w.config.reciprocity='none';
  if(typeof w.config.label!=='string')w.config.label='';
  if(!['none','read','write'].includes(w.config.forwardOperation))w.config.forwardOperation='none';
  if(!['none','read','write'].includes(w.config.reverseOperation))w.config.reverseOperation='none';

  endpointConnectionIndex(w,'a');
  endpointConnectionIndex(w,'b');
  if(typeof w.config.aChannelMarker!=='string')w.config.aChannelMarker='1';
  if(typeof w.config.bChannelMarker!=='string')w.config.bChannelMarker='1';

  // Legacy Wire color migrates only to the A-side Connection once.
  if(Number.isInteger(w.config.colorSlot)&&!w.config._legacyColorMigrated){
    const p=endpointPortConfig(w,'a');
    if(p){
      normalizePortConnections(p);
      const i=endpointConnectionIndex(w,'a');
      p.connections[i].colorSlot=normalizeSlot(w.config.colorSlot,0);
      p.connections[i].color=slotColor(p.connections[i].colorSlot);
    }
    w.config._legacyColorMigrated=true;
  }

  delete w.config.channelIndex;
  delete w.config.colorSlot;
  delete w.config.color;
  delete w.config.channel;

  if(!Array.isArray(w.attachments))w.attachments=[]; // non-point legacy/extension parts only; point attachments migrate in Data Core.
  w.duplex=w.config.direction==='duplex';
  if(w.duplex)ensureDuplexEndpointFlows(w);
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
