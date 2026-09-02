'use strict';
// 0.1 Beta concern: transport-neutral document formats + canonical CRUD semantics.
// This file intentionally has no DOM dependencies and is shared by browser and MCP adapters.
(function(root,factory){
  let Attachment=root.SovSchematicAttachment;
  if(!Attachment&&typeof module!=='undefined'&&module.exports)Attachment=require('./06-attachment-core.js');
  const api=factory(Attachment);
  root.SovSchematicData=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(Attachment){
  if(!Attachment)throw new Error('SovSchematicAttachment core is required');
  const DOCUMENT_SCHEMA='soveraeign.schematic/document@0.1';
  const WORKSPACE_SCHEMA='soveraeign.schematic/workspace@0.1';
  const PACKAGE_SCHEMA='soveraeign.schematic/package@0.1';
  const OPERATION_SCHEMA='soveraeign.schematic/operation@0.1';
  const RECEIPT_SCHEMA='soveraeign.schematic/receipt@0.1';
  const GLOBAL_CANVAS_ID='canvas:global';
  const RESOURCE_KEYS={component:'components',wire:'wires',reference:'references'};
  // Dimensional primitives. A template preset is applied only where the caller
  // supplied nothing, so authored records always win over the preset.
  const LEGACY_SYMBOL_IDS={port:'point'};
  const TEMPLATE_PRESETS={
    point:{form:{dimension:0},presentation:{graphic:{kind:'none'},labelMode:'none',backdrop:'none'},signalMode:'relay'},
    // The palette Path is a carrier: a Wire with two free ends. `symbolId:'path'` on a
    // component record is the static 1D role (a rail that hosts Points).
    path:{carrier:true,form:{dimension:1},presentation:{graphic:{kind:'none'},labelMode:'none',size:{w:240,h:64}}},
    plane:{form:{dimension:2,regions:{interior:{state:'open'}}},attachmentDefaults:'none',presentation:{graphic:{kind:'none'},labelMode:'none',size:{w:320,h:220}}}
  };
  // Loading a file applies the same preset rule as makeComponent: a preset field fills in
  // only where the record supplied nothing, so a sparse authored Plane or Point loads the
  // way an API-created one is born, and a full saved record is left exactly as written.
  function applyTemplatePreset(component){
    const preset=templatePreset(component.symbolId);if(!preset)return component;
    if(!isObject(component.form)&&isObject(preset.form))component.form=clone(preset.form);
    if(!isObject(component.config))component.config={};
    const config=component.config;
    if(!['source','relay','passive'].includes(config.signalMode)&&preset.signalMode)config.signalMode=preset.signalMode;
    if(!isObject(config.presentation)&&isObject(preset.presentation))config.presentation=clone(preset.presentation);
    if(!['standard','none'].includes(config.attachmentDefaults)&&preset.attachmentDefaults&&preset.attachmentDefaults!=='standard')config.attachmentDefaults=preset.attachmentDefaults;
    return component;
  }
  function normalizeSymbolId(value){const id=String(value||'blank')||'blank';return LEGACY_SYMBOL_IDS[id]||id}
  function templatePreset(symbolId){return clone(TEMPLATE_PRESETS[normalizeSymbolId(symbolId)]||null)}
  function isPrimitiveSymbol(symbolId){return Object.prototype.hasOwnProperty.call(TEMPLATE_PRESETS,normalizeSymbolId(symbolId))}

  const clone=value=>value==null?value:JSON.parse(JSON.stringify(value));
  const isObject=value=>!!value&&typeof value==='object'&&!Array.isArray(value);
  const nowIso=()=>new Date().toISOString();
  const cleanString=(value,fallback='')=>typeof value==='string'?value:fallback;
  const num=(value,fallback=0)=>Number.isFinite(Number(value))?Number(value):fallback;

  function nextId(items,prefix){
    let max=0;
    for(const item of items||[]){
      const m=String(item?.id||'').match(new RegExp('^'+prefix+'(\\d+)$'));
      if(m)max=Math.max(max,Number(m[1]));
    }
    return prefix+(max+1);
  }
  function makeDocument(input={}){
    const doc={
      schema:DOCUMENT_SCHEMA,
      id:cleanString(input.id,'schematic-1'),
      revision:Math.max(0,Math.trunc(num(input.revision,0))),
      meta:isObject(input.meta)?clone(input.meta):{},
      canvas:{id:GLOBAL_CANVAS_ID,scope:'global',dimension:2,state:'open'},
      components:Array.isArray(input.components)?clone(input.components):[],
      wires:Array.isArray(input.wires)?clone(input.wires):Array.isArray(input.connections)?clone(input.connections):[],
      references:Array.isArray(input.references)?clone(input.references):[],
      layout:isObject(input.layout)?clone(input.layout):{}
    };
    if(input.canvas&&isObject(input.canvas))doc.canvas={...doc.canvas,...clone(input.canvas),id:GLOBAL_CANVAS_ID,scope:'global',dimension:2,state:'open'};
    doc.meta.updatedAt=cleanString(doc.meta.updatedAt,nowIso());
    return normalizeDocument(doc);
  }
  function normalizeDocument(input){
    const doc=input&&isObject(input)?input:{};
    doc.schema=DOCUMENT_SCHEMA;
    doc.id=cleanString(doc.id,'schematic-1');
    doc.revision=Math.max(0,Math.trunc(num(doc.revision,0)));
    if(!isObject(doc.meta))doc.meta={};
    if(!isObject(doc.canvas))doc.canvas={};
    Object.assign(doc.canvas,{id:GLOBAL_CANVAS_ID,scope:'global',dimension:2,state:'open'});
    if(!Array.isArray(doc.components))doc.components=[];
    if(!Array.isArray(doc.wires))doc.wires=Array.isArray(doc.connections)?doc.connections:[];
    if(!Array.isArray(doc.references))doc.references=[];
    if(!isObject(doc.layout))doc.layout={};
    for(const component of doc.components){
      normalizeComponentIdentity(component);
      applyTemplatePreset(component);
      component.form=normalizeComponentForm(component.form,component.canvas);
      if(!isObject(component.canvas))component.canvas={};
      component.canvas.id=`canvas:component:${component.id||'unknown'}`;component.canvas.scope='local';component.canvas.dimension=component.form.dimension;component.canvas.state=component.form.regions.interior.state;
      ensureAttachmentPortConfigs(component);
      const ports=component?.config?.ports;
      if(!isObject(ports))continue;
      for(const port of Object.values(ports)){
        if(!isObject(port))continue;
        if(Array.isArray(port.connections))for(const connection of port.connections){
          if(!['none','read','write','read-write'].includes(connection.access))connection.access='read-write';
        }
        if(!['none','read','write','read-write'].includes(port.access))port.access=Array.isArray(port.connections)&&port.connections[port.activeConnection||0]?.access||'read-write';
      }
    }
    for(const wire of doc.wires){
      normalizeWireEndpoints(doc,wire,{strict:false});
      normalizeWireForm(wire);
      // A carrier runs on the surface its ends share. A file may leave that out; derive it
      // the way wire.create does. An unreachable pair stays as written for validation to report.
      if(!cleanString(wire.canvasId)){try{wire.canvasId=carrierCanvasId(doc,wire,null)}catch(_){wire.canvasId=null}}
      if(!isObject(wire.config))wire.config={};
      if(!['none','read','write'].includes(wire.config.forwardOperation))wire.config.forwardOperation='none';
      if(!['none','read','write'].includes(wire.config.reverseOperation))wire.config.reverseOperation='none';
    }
    migrateLegacyWirePointAttachments(doc);
    if('connections' in doc)delete doc.connections;
    return doc;
  }
  function makePackage(input={}){
    const document=makeDocument(clone(input.document||input.workspace?.document||{}));
    const view=isObject(input.workspace?.view)?clone(input.workspace.view):isObject(input.view)?clone(input.view):{};
    const manifest=isObject(input.manifest)?clone(input.manifest):{};
    const timestamp=nowIso();
    return {
      schema:PACKAGE_SCHEMA,
      version:1,
      manifest:{
        id:cleanString(manifest.id,`${document.id||'schematic'}-package`),
        title:cleanString(manifest.title,document.meta?.title||document.id||'Soveraeign Schematic'),
        entry:'document',
        createdAt:cleanString(manifest.createdAt,timestamp),
        updatedAt:timestamp,
        generator:cleanString(manifest.generator,'SOV Schematic 0.1 Beta.24')
      },
      document,
      workspace:{view},
      templates:Array.isArray(input.templates)?clone(input.templates):[],
      assets:Array.isArray(input.assets)?clone(input.assets):[],
      meta:isObject(input.meta)?clone(input.meta):{}
    };
  }
  function validatePackage(input){
    const errors=[];
    if(!isObject(input))return {ok:false,errors:['package must be an object']};
    if(input.schema!==PACKAGE_SCHEMA)errors.push(`schema must equal ${PACKAGE_SCHEMA}`);
    const documentCheck=validateDocument(input.document||{});
    errors.push(...documentCheck.errors.map(error=>`document: ${error}`));
    if(input.workspace!=null&&!isObject(input.workspace))errors.push('workspace must be an object');
    if(input.templates!=null&&!Array.isArray(input.templates))errors.push('templates must be an array');
    if(input.assets!=null&&!Array.isArray(input.assets))errors.push('assets must be an array');
    return {ok:errors.length===0,errors};
  }
  function documentFromFilePayload(input){
    if(!isObject(input))throw new Error('File payload must be an object');
    if(input.schema===PACKAGE_SCHEMA){
      const check=validatePackage(input);if(!check.ok)throw new Error(check.errors.join('; '));
      return makeDocument(clone(input.document));
    }
    if(input.schema===WORKSPACE_SCHEMA)return makeDocument(clone(input.document));
    if(input.schema===DOCUMENT_SCHEMA)return makeDocument(clone(input));
    throw new Error(`Unsupported file schema: ${input.schema||'missing'}`);
  }
  function componentCanvasId(component){
    return component?.canvas?.id||`canvas:component:${component?.id||'unknown'}`;
  }
  function containingCanvasId(component){return component?.canvasId||GLOBAL_CANVAS_ID}
  // A default point contract is minimal: one connection, outside face, no label.
  // Port-level mirrors (flow/access/colorSlot/channel*) are runtime projections and
  // are not part of the default record.
  function defaultPointContract(side,flow){
    return {side,face:'external',label:'',connectionCount:1,activeConnection:0,connections:[{id:'connection-1',name:'Connection 1',colorSlot:0,flow,access:'read-write'}]};
  }
  const STANDARD_POINT_FLOWS={in:['left','in'],out:['right','out'],control:['top','control']};
  function defaultPortForSpec(spec){
    const standard=STANDARD_POINT_FLOWS[spec.compatId];
    if(standard)return defaultPointContract(spec.side||standard[0],standard[1]);
    return defaultPointContract(spec.side,spec.defaultFlow||'duplex');
  }
  // Only the points the effective dimension actually exposes get a contract.
  // A 0D Point owns `out` (its `self`), a 1D Path `in`/`out`, a standard 2D
  // surface `in`/`out`/`control`; a surface with attachmentDefaults='none' owns
  // only what its data-declared boundary points require.
  function ensureAttachmentPortConfigs(component){
    if(!isObject(component.config))component.config={};
    if(!isObject(component.config.ports))component.config.ports={};
    for(const spec of Attachment.pointSpecs(component)){
      if(!isObject(component.config.ports[spec.compatId]))component.config.ports[spec.compatId]=defaultPortForSpec(spec);
      component.config.ports[spec.compatId].side=spec.side;
    }
    return component;
  }
  function normalizeComponentIdentity(component){
    component.symbolId=normalizeSymbolId(component.symbolId||component.type);
    component.type=component.symbolId==='blank'?null:component.symbolId;
    if(!isObject(component.config))component.config={};
    if(!['standard','none'].includes(component.config.attachmentDefaults))delete component.config.attachmentDefaults;
    if(!Array.isArray(component.config.attachmentPoints))delete component.config.attachmentPoints;
    const graphic=component.config.presentation?.graphic;
    if(isObject(graphic)&&graphic.ref==='sym-port')graphic.ref='sym-point';
    if(isObject(component.boundary?.inside)&&component.boundary.inside.type==='port')component.boundary.inside.type='point';
    return component;
  }
  function isLegacyWirePointAttachment(part){
    return !!part&&['port','point','attachment-point'].includes(String(part.kind||part.type||''));
  }
  function hostedPointComponentFromLegacyAttachment(doc,wire,part){
    const id=cleanString(part.componentId,nextId(doc.components,'c'));
    const existing=doc.components.find(c=>c.id===id);if(existing)return existing;
    const cfg=isObject(part.config)?clone(part.config):{};
    const t=Math.max(.02,Math.min(.98,num(part.placement?.t??part.t,.5)));
    const ports={out:{...defaultPointContract('point','duplex'),...cfg,side:'point'}};
    const active=Array.isArray(ports.out.connections)?ports.out.connections[Math.max(0,Math.min(ports.out.connections.length-1,ports.out.activeConnection||0))]:null;
    const colorSlot=Math.max(0,Math.trunc(num(active?.colorSlot??cfg.colorSlot,0)));
    const point=makeComponent(doc,{
      id,symbolId:'point',x:0,y:0,canvasId:`canvas:wire:${wire.id}`,
      placement:{kind:'wire',wireId:wire.id,t,sourceAttachmentId:part.id||null},
      config:{label:cleanString(cfg.label,''),colorSlot,signalMode:'relay',presentation:{graphic:{kind:'none'},labelMode:cleanString(cfg.label,'')?'outside':'none',interiorColorSlot:colorSlot,backdrop:'none'},ports}
    });
    doc.components.push(point);return point;
  }
  function migrateLegacyWirePointAttachments(doc){
    for(const wire of doc.wires){
      if(!Array.isArray(wire.attachments)||!wire.attachments.length)continue;
      const keep=[];
      for(const part of wire.attachments){
        if(isLegacyWirePointAttachment(part))hostedPointComponentFromLegacyAttachment(doc,wire,part);else keep.push(part);
      }
      wire.attachments=keep;
    }
    return doc;
  }
  function canonicalAttachmentPointIdsForComponent(component){return Attachment.pointIds(component)}
  function canonicalAttachmentPointDescriptors(component){return Attachment.descriptors(component,component?.config?.ports||{})}
  function canonicalPortIdsForComponent(component){return Attachment.pointSpecs(component).map(spec=>spec.compatId)}
  function canonicalPortIdForComponent(component,portId){
    const spec=Attachment.resolveSpec(component,portId);
    if(spec)return spec.compatId;
    return Attachment.defaultCompatId(component,cleanString(portId,'')==='in'?'start':'end');
  }
  function reconcileComponentWirePorts(doc,componentId){
    const component=doc.components.find(c=>c.id===componentId);if(!component)return [];
    const changed=[];
    for(const wire of doc.wires||[]){
      let dirty=false;
      if(wire.a===componentId){const before=wire.aSide;Attachment.syncWireEndpoint(wire,'a',component,wire.aAttachment?.pointId||wire.aSide);if(before!==wire.aSide)dirty=true}
      if(wire.b===componentId){const before=wire.bSide;Attachment.syncWireEndpoint(wire,'b',component,wire.bAttachment?.pointId||wire.bSide);if(before!==wire.bSide)dirty=true}
      if(dirty){const reach=connectionReachability(doc,wire.a,wire.aSide,wire.b,wire.bSide);if(reach.ok)wire.canvasId=reach.canvasId;changed.push(wire.id)}
    }
    return changed;
  }
  function normalizeComponentForm(value={},legacyCanvas=null){
    const form=isObject(value)?clone(value):{};
    const legacyOpen=legacyCanvas?.state==='open';
    const rawDimension=Number(form.dimension);
    const dimension=[0,1,2].includes(rawDimension)?rawDimension:2; // Legacy 3D migrates to 2D until spatial volume is earned.
    const defaultKind=['point','path','surface'][dimension];
    if(!isObject(form.body))form.body={};
    form.dimension=dimension;
    form.body.kind=['point','path','surface'].includes(form.body.kind)?form.body.kind:defaultKind;
    form.body.material=cleanString(form.body.material,'generic')||'generic';
    form.body.thickness=Math.max(0,num(form.body.thickness,0));
    if(!isObject(form.frame))form.frame={};
    form.frame.mode=['none','frame','shell'].includes(form.frame.mode)?form.frame.mode:'none';
    form.frame.thickness=Math.max(0,num(form.frame.thickness,form.frame.mode==='none'?0:12));
    form.frame.depth=Math.max(0,num(form.frame.depth,0));
    if(!isObject(form.regions))form.regions={};
    if(!isObject(form.regions.interior))form.regions.interior={};
    if(!['open','closed'].includes(form.regions.interior.state))form.regions.interior.state=legacyOpen?'open':'closed';
    if(dimension<2)form.regions.interior.state='closed';
    return form;
  }
  function makeComponent(doc,value={}){
    const symbolId=normalizeSymbolId(value.symbolId||value.type);
    const preset=templatePreset(symbolId)||{};
    const id=cleanString(value.id,nextId(doc.components,'c'));
    const canvasId=cleanString(value.canvasId,GLOBAL_CANVAS_ID);
    const form=normalizeComponentForm(isObject(value.form)?value.form:preset.form,value.canvas);
    const config={
      label:cleanString(value.config?.label||value.label,''),
      colorSlot:Math.max(0,Math.trunc(num(value.config?.colorSlot,0))),
      signalMode:['source','relay','passive'].includes(value.config?.signalMode)?value.config.signalMode:(preset.signalMode||'source'),
      presentation:isObject(value.config?.presentation)?clone(value.config.presentation):(preset.presentation?clone(preset.presentation):{}),
      ports:isObject(value.config?.ports)?clone(value.config.ports):{}
    };
    // An authored choice stays on the runtime record either way, so a later normalization
    // pass cannot replace a Plane's authored 'standard' with its preset 'none'.
    const attachmentDefaults=['standard','none'].includes(value.config?.attachmentDefaults)?value.config.attachmentDefaults:preset.attachmentDefaults;
    if(attachmentDefaults==='none'||value.config?.attachmentDefaults==='standard')config.attachmentDefaults=attachmentDefaults;
    if(Array.isArray(value.config?.attachmentPoints)&&value.config.attachmentPoints.length)config.attachmentPoints=clone(value.config.attachmentPoints);
    const component={
      id,
      type:symbolId==='blank'?null:symbolId,
      symbolId,
      x:num(value.x,120),y:num(value.y,120),
      canvasId,
      canvas:{id:`canvas:component:${id}`,scope:'local',dimension:form.dimension,state:form.regions.interior.state,ownerKind:'component',ownerId:id},
      form,
      config,
      editor:isObject(value.editor)?clone(value.editor):{pinned:false,locked:false,hidden:false,opacity:1,rate:1},
      parentId:value.parentId??null,
      placement:isObject(value.placement)?clone(value.placement):{kind:canvasId.startsWith('canvas:wire:')?'wire':'surface',...(canvasId.startsWith('canvas:wire:')?{wireId:canvasId.slice('canvas:wire:'.length),t:.5}:{x:num(value.x,120),y:num(value.y,120)})},
      incomplete:symbolId==='blank'
    };
    if(isObject(value.boundary))component.boundary=clone(value.boundary);
    if(isObject(value.parts))component.parts=clone(value.parts);
    return ensureAttachmentPortConfigs(component);
  }
  // Saved records carry authored truth only. Everything below is regenerated on load:
  // local canvas descriptors, boundary/parts projections, port-level mirrors of the
  // active connection, realized palette colors, and presentation layout hints.
  const DERIVED_PORT_KEYS=['channelCount','activeChannel','channel','channels','colorSlot','color','flow','access','side'];
  const DERIVED_PRESENTATION_KEYS=['svgRef','internalLayout','portTopology','boundaryColorMode','boundaryShape'];
  function compactComponent(component){
    const c=clone(component);
    delete c.canvas;delete c.boundary;delete c.parts;delete c.type;delete c.incomplete;
    if(isObject(c.config)){
      delete c.config.color;
      // 'none' is always stored; 'standard' only where it overrides a preset of 'none' (a Plane).
      if(c.config.attachmentDefaults==='standard'&&(templatePreset(c.symbolId)?.attachmentDefaults||'standard')==='standard')delete c.config.attachmentDefaults;
      if(Array.isArray(c.config.attachmentPoints)&&!c.config.attachmentPoints.length)delete c.config.attachmentPoints;
      if(isObject(c.config.presentation))for(const key of DERIVED_PRESENTATION_KEYS)delete c.config.presentation[key];
      if(isObject(c.config.ports))for(const port of Object.values(c.config.ports)){
        if(!isObject(port))continue;
        if(Array.isArray(port.connections)&&port.connections.length){
          for(const key of DERIVED_PORT_KEYS)delete port[key];
          for(const connection of port.connections)if(isObject(connection)){delete connection.color;delete connection.name}
        }
      }
    }
    if(isObject(c.placement)&&c.placement.kind==='surface')delete c.placement;
    return c;
  }
  function compactWire(wire){
    const w=clone(wire);
    delete w.canvas;delete w.duplex;
    if(Array.isArray(w.attachments)&&!w.attachments.length)delete w.attachments;
    if(isObject(w.config))delete w.config._legacyColorMigrated;
    return w;
  }
  function compactDocument(input){
    const doc=clone(input);
    delete doc.canvas;
    doc.components=(doc.components||[]).map(compactComponent);
    doc.wires=(doc.wires||[]).map(compactWire);
    if(isObject(doc.meta)&&Array.isArray(doc.meta.checkpoints))doc.meta.checkpoints=doc.meta.checkpoints.map(cp=>isObject(cp)&&isObject(cp.document)?{...cp,document:compactDocument(cp.document)}:cp);
    return doc;
  }
  function attachmentPointConfig(doc,componentId,pointId){
    const component=doc.components.find(c=>c.id===componentId);if(!component)return null;
    const spec=Attachment.resolveSpec(component,pointId);if(!spec)return null;
    return component?.config?.ports?.[spec.compatId]||null;
  }
  const portConfig=attachmentPointConfig;
  function attachmentHostSurfaces(doc,component){
    const placement=component?.placement||{};
    if(placement.kind==='wire'||String(component?.canvasId||'').startsWith('canvas:wire:')){
      const wireId=placement.wireId||String(component.canvasId||'').slice('canvas:wire:'.length);
      const host=doc.wires.find(w=>w.id===wireId);
      return {inside:`canvas:wire:${wireId}`,outside:host?.canvasId||GLOBAL_CANVAS_ID};
    }
    if(['edge','path'].includes(placement.kind)&&placement.hostId){
      const host=doc.components.find(c=>c.id===placement.hostId);
      if(host)return {inside:componentCanvasId(host),outside:containingCanvasId(host)};
    }
    return {outside:containingCanvasId(component),inside:componentCanvasId(component)};
  }
  function portExposedCanvasIds(doc,componentId,portId){
    const component=doc.components.find(c=>c.id===componentId);if(!component)return [];
    const port=attachmentPointConfig(doc,componentId,portId);if(!port)return [];
    const face=port.face||'external',surfaces=attachmentHostSurfaces(doc,component);
    if(face==='internal')return [surfaces.inside];
    if(face==='both')return [...new Set([surfaces.outside,surfaces.inside])];
    return [surfaces.outside];
  }
  function connectionReachability(doc,a,aSide,b,bSide){
    const aSet=portExposedCanvasIds(doc,a,aSide),bSet=new Set(portExposedCanvasIds(doc,b,bSide));
    const shared=aSet.filter(x=>bSet.has(x));
    if(!shared.length)return {ok:false,canvasId:null,reason:'Boundary blocks implicit reach-through'};
    shared.sort((x,y)=>(x===GLOBAL_CANVAS_ID?1:0)-(y===GLOBAL_CANVAS_ID?1:0));
    return {ok:true,canvasId:shared[0]};
  }
  // A Wire is a carrier Path: a 1D form whose two ends are each bound to an attachment
  // point (`{kind:'attachment-ref',componentId,pointId}`) or free (`{kind:'free',x,y}`).
  // `a`/`aSide` and `b`/`bSide` are the bound-end projections the document schema names;
  // they are null for a free end.
  function isFreeEndpoint(att){return isObject(att)&&att.kind==='free'}
  function wireEndBound(wire,end){return !isFreeEndpoint(wire?.[end+'Attachment'])&&!!wire?.[end]}
  function normalizeWireEndpoints(doc,wire,{strict=true}={}){
    for(const end of ['a','b']){
      const key=end+'Attachment',sideKey=end+'Side',att=wire[key];
      if(isFreeEndpoint(att)){wire[key]={kind:'free',x:num(att.x,0),y:num(att.y,0)};wire[end]=null;wire[sideKey]=null;continue}
      const componentId=cleanString(wire[end])||cleanString(att?.componentId);
      const component=componentId?doc.components.find(c=>c.id===componentId):null;
      if(!component){
        if(strict)throw new Error(componentId?'wire endpoint component not found':'wire.create requires each end to be bound (a/aSide) or free ({kind:"free",x,y})');
        continue;
      }
      const input=att?.pointId??wire[sideKey]??Attachment.defaultCompatId(component,end==='a'?'end':'start');
      const spec=Attachment.resolveSpec(component,input);
      if(!spec){if(strict)throw new Error(`wire.create invalid attachment ${input} for ${Attachment.effectiveDimension(component)}D component`);continue}
      wire[end]=component.id;Attachment.syncWireEndpoint(wire,end,component,spec.id);
    }
    return wire;
  }
  function normalizeWireForm(wire){
    if(!isObject(wire.form))wire.form={};
    wire.form.dimension=1;
    if(!isObject(wire.form.body))wire.form.body={};
    wire.form.body.kind='path';
    wire.form.body.material=cleanString(wire.form.body.material,'generic')||'generic';
    wire.form.body.thickness=Math.max(0,num(wire.form.body.thickness,0));
    wire.role='carrier';
    return wire;
  }
  // The surface a carrier runs on: shared by both bound ends, adopted from a single bound
  // end (preferring the current surface when it is exposed), or wherever it was placed.
  function carrierCanvasId(doc,wire,preferred=null){
    const aBound=wireEndBound(wire,'a'),bBound=wireEndBound(wire,'b');
    if(aBound&&bBound){const reach=connectionReachability(doc,wire.a,wire.aSide,wire.b,wire.bSide);if(!reach.ok)throw new Error(reach.reason);return reach.canvasId}
    const bound=aBound?'a':bBound?'b':null;
    if(bound){
      const exposed=portExposedCanvasIds(doc,wire[bound],wire[bound+'Side']);
      if(!exposed.length)throw new Error('wire endpoint exposes no surface');
      return exposed.includes(preferred)?preferred:exposed[0];
    }
    return cleanString(preferred,'')||GLOBAL_CANVAS_ID;
  }
  function bindWireEndpoint(doc,wire,end,componentId,pointId){
    const component=doc.components.find(c=>c.id===componentId);if(!component)throw new Error('wire endpoint component not found');
    assertCarrierEndpointAccepts(doc,componentId);
    const spec=Attachment.resolveSpec(component,pointId);if(!spec)throw new Error(`invalid attachment ${pointId}`);
    const before={a:wire.a,aSide:wire.aSide,b:wire.b,bSide:wire.bSide,aAttachment:clone(wire.aAttachment),bAttachment:clone(wire.bAttachment),canvasId:wire.canvasId};
    wire[end]=component.id;Attachment.syncWireEndpoint(wire,end,component,spec.id);
    try{wire.canvasId=carrierCanvasId(doc,wire,wire.canvasId)}catch(error){Object.assign(wire,before);throw error}
    return wire;
  }
  function freeWireEndpoint(doc,wire,end,x,y){
    wire[end+'Attachment']={kind:'free',x:num(x,0),y:num(y,0)};wire[end]=null;wire[end+'Side']=null;
    wire.canvasId=carrierCanvasId(doc,wire,wire.canvasId);
    return wire;
  }
  function makeWire(doc,value={}){
    const id=cleanString(value.id,nextId(doc.wires,'k'));
    const wire={id,a:cleanString(value.a)||null,b:cleanString(value.b)||null,aSide:value.aSide??null,bSide:value.bSide??null,aAttachment:isObject(value.aAttachment)?clone(value.aAttachment):null,bAttachment:isObject(value.bAttachment)?clone(value.bAttachment):null};
    if(!wire.a&&!wire.aAttachment&&!wire.b&&!wire.bAttachment)throw new Error('wire.create requires a and b component ids, or free endpoints');
    for(const end of ['a','b'])if(!wire[end]&&!wire[end+'Attachment'])throw new Error(`wire.create requires ${end} (component id) or ${end}Attachment`);
    normalizeWireEndpoints(doc,wire,{strict:true});
    const canvasId=carrierCanvasId(doc,wire,cleanString(value.canvasId,'')||null);
    return normalizeWireForm({
      ...wire,canvasId,
      canvas:{id:`canvas:wire:${id}`,scope:'local',dimension:1,state:'open',ownerKind:'wire',ownerId:id},
      form:isObject(value.form)?clone(value.form):{dimension:1,body:{kind:'path',material:'generic',thickness:0}},
      lane:Math.max(0,Math.trunc(num(value.lane,doc.wires.length))),
      net:Math.max(0,Math.trunc(num(value.net,doc.wires.length))),
      config:{direction:['none','forward','reverse','duplex'].includes(value.config?.direction)?value.config.direction:'forward',reciprocity:['none','expected','required'].includes(value.config?.reciprocity)?value.config.reciprocity:'none',forwardOperation:['none','read','write'].includes(value.config?.forwardOperation)?value.config.forwardOperation:'none',reverseOperation:['none','read','write'].includes(value.config?.reverseOperation)?value.config.reverseOperation:'none',aConnectionIndex:Math.max(0,Math.trunc(num(value.config?.aConnectionIndex,0))),bConnectionIndex:Math.max(0,Math.trunc(num(value.config?.bConnectionIndex,0))),aChannelMarker:cleanString(value.config?.aChannelMarker,'1'),bChannelMarker:cleanString(value.config?.bChannelMarker,'1'),label:cleanString(value.config?.label,'')},
      editor:isObject(value.editor)?clone(value.editor):{pinned:false,locked:false,hidden:false,opacity:1,rate:1},
      attachments:Array.isArray(value.attachments)?clone(value.attachments):[],duplex:value.config?.direction==='duplex'
    });
  }
  function makeReference(doc,value={}){
    return {id:cleanString(value.id,nextId(doc.references,'r')),kind:cleanString(value.kind,'reference'),label:cleanString(value.label,''),target:value.target??null,data:isObject(value.data)?clone(value.data):{}};
  }
  function resourceArray(doc,resource){
    const key=RESOURCE_KEYS[resource];if(!key)throw new Error(`Unsupported resource: ${resource}`);return doc[key];
  }
  function deepMerge(target,patch){
    if(!isObject(patch))return clone(patch);
    const out=isObject(target)?target:{};
    for(const [k,v] of Object.entries(patch)){
      if(k==='id')continue;
      out[k]=isObject(v)?deepMerge(isObject(out[k])?out[k]:{},v):clone(v);
    }
    return out;
  }
  function list(doc,resource,query={}){
    let items=resourceArray(doc,resource);
    const allowed=['canvasId','symbolId','type','kind','parentId'];
    for(const key of allowed)if(query[key]!==undefined)items=items.filter(x=>x?.[key]===query[key]);
    return clone(items);
  }
  function read(doc,resource,id){const item=resourceArray(doc,resource).find(x=>x.id===id);return item?clone(item):null}
  function isLocked(record){return record?.editor?.locked===true}
  function assertUnlocked(record,label='entity'){if(isLocked(record))throw new Error(`Locked ${label} is immutable`)}
  function assertCarrierEndpointAccepts(doc,componentId){
    const component=doc.components.find(c=>c.id===componentId);
    if(component&&isLocked(component))throw new Error('Locked Component attachments cannot accept new Wires');
  }
  function create(doc,resource,value={}){
    const arr=resourceArray(doc,resource);
    if(resource==='wire'){assertCarrierEndpointAccepts(doc,value?.a);assertCarrierEndpointAccepts(doc,value?.b)}
    const record=resource==='component'?makeComponent(doc,value):resource==='wire'?makeWire(doc,value):makeReference(doc,value);
    if(arr.some(x=>x.id===record.id))throw new Error(`${resource} id already exists: ${record.id}`);
    arr.push(record);return clone(record);
  }
  function update(doc,resource,id,patch={}){
    const arr=resourceArray(doc,resource),index=arr.findIndex(x=>x.id===id);if(index<0)throw new Error(`${resource} not found: ${id}`);
    const current=arr[index];assertUnlocked(current,resource);
    const candidate=deepMerge(clone(current),patch);candidate.id=id;
    if(resource==='component'){
      normalizeComponentIdentity(candidate);
      candidate.canvas=candidate.canvas||{};candidate.canvas.id=`canvas:component:${id}`;candidate.canvas.ownerId=id;
      candidate.form=normalizeComponentForm(candidate.form,candidate.canvas);candidate.canvas.state=candidate.form.regions.interior.state;
      ensureAttachmentPortConfigs(candidate);
      if(candidate.config?.presentation?.size){candidate.config.presentation.size.w=Math.max(80,num(candidate.config.presentation.size.w,112));candidate.config.presentation.size.h=Math.max(64,num(candidate.config.presentation.size.h,84));}
    }else if(resource==='wire'){
      // A patch may rebind an end (a/aSide or aAttachment ref) or free it (aAttachment {kind:'free'}).
      for(const end of ['a','b']){
        const key=end+'Attachment',patched=patch?.[key];
        if(isObject(patched)&&patched.kind==='free'){candidate[key]={kind:'free',x:num(patched.x,current[key]?.x),y:num(patched.y,current[key]?.y)};continue}
        const idChanged=patch?.[end]!==undefined&&patch[end]!==current[end];
        const sideChanged=patch?.[end+'Side']!==undefined&&patch[end+'Side']!==current[end+'Side'];
        const pointChanged=isObject(patched)&&!!patched.pointId&&patched.pointId!==current[key]?.pointId;
        if(idChanged||sideChanged||pointChanged){
          if(!pointChanged)candidate[key]=null; // resolve the end again from a/aSide
          if(idChanged)candidate[end]=patch[end];
        }
      }
      normalizeWireEndpoints(doc,candidate,{strict:true});
      const aChanged=candidate.a!==current.a||candidate.aSide!==current.aSide||candidate.aAttachment?.pointId!==current.aAttachment?.pointId;
      const bChanged=candidate.b!==current.b||candidate.bSide!==current.bSide||candidate.bAttachment?.pointId!==current.bAttachment?.pointId;
      if(aChanged)assertCarrierEndpointAccepts(doc,candidate.a);if(bChanged)assertCarrierEndpointAccepts(doc,candidate.b);
      candidate.canvasId=carrierCanvasId({...doc,wires:doc.wires.map((w,i)=>i===index?candidate:w)},candidate,cleanString(patch?.canvasId,'')||current.canvasId||null);
      candidate.canvas=candidate.canvas||{};candidate.canvas.id=`canvas:wire:${id}`;candidate.canvas.ownerId=id;candidate.canvas.dimension=1;candidate.canvas.state='open';
      normalizeWireForm(candidate);
      candidate.duplex=candidate.config?.direction==='duplex';
    }
    arr[index]=candidate;
    if(resource==='component')reconcileComponentWirePorts(doc,id);
    if(resource==='wire')migrateLegacyWirePointAttachments(doc);
    return clone(arr[index]);
  }
  function remove(doc,resource,id){
    const arr=resourceArray(doc,resource),index=arr.findIndex(x=>x.id===id);if(index<0)return null;
    const removed=arr[index];assertUnlocked(removed,resource);
    if(resource==='component'){
      const containing=removed.canvasId||GLOBAL_CANVAS_ID;
      for(const child of doc.components)if(child.canvasId===componentCanvasId(removed)){child.canvasId=containing;child.parentId=removed.parentId??null;child.placement={kind:'surface',x:child.x,y:child.y};}
      for(let i=doc.wires.length-1;i>=0;i--)if(doc.wires[i].a===id||doc.wires[i].b===id)remove(doc,'wire',doc.wires[i].id);
    }else if(resource==='wire'){
      const hostedCanvas=`canvas:wire:${id}`;
      for(const component of doc.components)if(component.canvasId===hostedCanvas){component.canvasId=GLOBAL_CANVAS_ID;component.parentId=null;component.placement={kind:'surface',x:component.x,y:component.y};}
    }
    arr.splice(index,1);return clone(removed);
  }
  function touch(doc){doc.revision=Math.max(0,Math.trunc(num(doc.revision,0)))+1;doc.meta=doc.meta||{};doc.meta.updatedAt=nowIso();return doc.revision}
  function makeReceipt(op,ok,result,revisionBefore,error=null){return {schema:RECEIPT_SCHEMA,operationId:op.id||null,ok,revisionBefore,revisionAfter:result?.revisionAfter??revisionBefore,result:result?.value??result??null,error:error?{message:String(error.message||error)}:null}}
  // ifRevision is the document revision the caller observed. Absent/null/undefined means
  // no check is made; a mismatch on a mutating op refuses the write before it happens.
  function applyOperation(document,operation={}){
    const op={schema:OPERATION_SCHEMA,id:operation.id||`op-${Date.now()}`,op:operation.op,resource:operation.resource,resourceId:operation.resourceId??operation.idValue??null,value:clone(operation.value),patch:clone(operation.patch),query:clone(operation.query||{}),ifRevision:operation.ifRevision};
    // Check the raw revision before normalizeDocument touches anything: normalization backfills
    // legacy shapes in place, and a refused write must leave the document exactly as it was.
    const rawRevision=Math.max(0,Math.trunc(num(document?.revision,0)));
    if(typeof op.ifRevision==='number'&&op.ifRevision!==rawRevision&&['create','update','delete'].includes(op.op)){
      return {schema:RECEIPT_SCHEMA,operationId:op.id,ok:false,revisionBefore:rawRevision,revisionAfter:rawRevision,result:null,error:{message:`Stale revision: expected ${op.ifRevision}, document is at ${rawRevision}`}};
    }
    const doc=normalizeDocument(document);
    const before=doc.revision;
    try{
      let value,mutates=false;
      switch(op.op){
        case 'list':value=list(doc,op.resource,op.query);break;
        case 'read':value=read(doc,op.resource,op.resourceId);break;
        case 'create':value=create(doc,op.resource,op.value||{});mutates=true;break;
        case 'update':value=update(doc,op.resource,op.resourceId,op.patch||{});mutates=true;break;
        case 'delete':value=remove(doc,op.resource,op.resourceId);mutates=value!==null;break;
        default:throw new Error(`Unsupported CRUD op: ${op.op}`);
      }
      if(mutates)touch(doc);
      return {schema:RECEIPT_SCHEMA,operationId:op.id,ok:true,revisionBefore:before,revisionAfter:doc.revision,result:value,error:null};
    }catch(error){return {schema:RECEIPT_SCHEMA,operationId:op.id,ok:false,revisionBefore:before,revisionAfter:doc.revision,result:null,error:{message:String(error.message||error)}}}
  }
  function replaceDocument(target,input){
    const incoming=makeDocument(clone(input));
    const components=target.components,wires=target.wires,references=target.references;
    components.splice(0,components.length,...incoming.components);
    wires.splice(0,wires.length,...incoming.wires);
    references.splice(0,references.length,...incoming.references);
    target.schema=DOCUMENT_SCHEMA;target.id=incoming.id;target.revision=incoming.revision;target.meta=incoming.meta;target.canvas=incoming.canvas;target.layout=incoming.layout;
    return target;
  }
  function validateDocument(input){
    const errors=[];
    if(!isObject(input))return {ok:false,errors:['document must be an object']};
    if(input.schema!==DOCUMENT_SCHEMA)errors.push(`schema must equal ${DOCUMENT_SCHEMA}`);
    if(!Array.isArray(input.components))errors.push('components must be an array');
    if(!Array.isArray(input.wires))errors.push('wires must be an array');
    if(!Array.isArray(input.references))errors.push('references must be an array');
    const ids=new Set();
    for(const [kind,items] of [['component',input.components||[]],['wire',input.wires||[]],['reference',input.references||[]]])for(const item of items){if(!item?.id)errors.push(`${kind} missing id`);else if(ids.has(`${kind}:${item.id}`))errors.push(`duplicate ${kind} id: ${item.id}`);else ids.add(`${kind}:${item.id}`)}
    const componentIds=new Set((input.components||[]).map(x=>x.id));
    for(const wire of input.wires||[]){
      const aFree=isFreeEndpoint(wire.aAttachment),bFree=isFreeEndpoint(wire.bAttachment);
      if(!aFree&&!componentIds.has(wire.a))errors.push(`wire ${wire.id||'?'} missing endpoint component: ${wire.a}`);
      if(!bFree&&!componentIds.has(wire.b))errors.push(`wire ${wire.id||'?'} missing endpoint component: ${wire.b}`);
      if(!aFree&&!bFree&&componentIds.has(wire.a)&&componentIds.has(wire.b)){
        const reach=connectionReachability(input,wire.a,wire.aSide,wire.b,wire.bSide);if(!reach.ok)errors.push(`wire ${wire.id||'?'}: ${reach.reason}`);
      }
      for(const key of ['forwardOperation','reverseOperation'])if(wire.config?.[key]!=null&&!['none','read','write'].includes(wire.config[key]))errors.push(`wire ${wire.id||'?'} invalid ${key}: ${wire.config[key]}`);
    }
    return {ok:errors.length===0,errors};
  }
  function operationTools(){
    const resourceSchema={type:'string',enum:['component','wire','reference']};
    return [
      {name:'schematic.list',description:'List schematic resources.',inputSchema:{type:'object',properties:{resource:resourceSchema,query:{type:'object'}},required:['resource'],additionalProperties:false}},
      {name:'schematic.get',description:'Read one schematic resource by id.',inputSchema:{type:'object',properties:{resource:resourceSchema,id:{type:'string'}},required:['resource','id'],additionalProperties:false}},
      {name:'schematic.create',description:'Create a component, wire, or reference.',inputSchema:{type:'object',properties:{resource:resourceSchema,value:{type:'object'},ifRevision:{type:'number',description:'Document revision the caller observed; refused if the document has moved on.'}},required:['resource','value'],additionalProperties:false}},
      {name:'schematic.update',description:'Patch a component, wire, or reference.',inputSchema:{type:'object',properties:{resource:resourceSchema,id:{type:'string'},patch:{type:'object'},ifRevision:{type:'number',description:'Document revision the caller observed; refused if the document has moved on.'}},required:['resource','id','patch'],additionalProperties:false}},
      {name:'schematic.delete',description:'Delete a component, wire, or reference.',inputSchema:{type:'object',properties:{resource:resourceSchema,id:{type:'string'},ifRevision:{type:'number',description:'Document revision the caller observed; refused if the document has moved on.'}},required:['resource','id'],additionalProperties:false}},
      {name:'schematic.document.get',description:'Return the entire schematic document.',inputSchema:{type:'object',properties:{},additionalProperties:false}},
      {name:'schematic.document.replace',description:'Replace the entire schematic document after validation.',inputSchema:{type:'object',properties:{document:{type:'object'}},required:['document'],additionalProperties:false}}
    ];
  }
  return {DOCUMENT_SCHEMA,WORKSPACE_SCHEMA,PACKAGE_SCHEMA,OPERATION_SCHEMA,RECEIPT_SCHEMA,GLOBAL_CANVAS_ID,RESOURCE_KEYS,clone,makeDocument,normalizeDocument,compactDocument,compactComponent,compactWire,validateDocument,makePackage,validatePackage,documentFromFilePayload,replaceDocument,makeComponent,makeWire,makeReference,normalizeSymbolId,templatePreset,isPrimitiveSymbol,isFreeEndpoint,wireEndBound,normalizeWireEndpoints,carrierCanvasId,bindWireEndpoint,freeWireEndpoint,componentCanvasId,containingCanvasId,canonicalAttachmentPointIdsForComponent,canonicalAttachmentPointDescriptors,canonicalPortIdsForComponent,canonicalPortIdForComponent,reconcileComponentWirePorts,attachmentPointConfig,attachmentHostSurfaces,portExposedCanvasIds,connectionReachability,migrateLegacyWirePointAttachments,list,read,create,update,remove,applyOperation,operationTools,touch};
});
