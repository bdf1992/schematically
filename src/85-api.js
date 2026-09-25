'use strict';
// 0.1 Beta concern: browser API adapter over the canonical CRUD/document core.

function normalizeRuntimeAfterCrud(){
  for(const n of nodes){ensureComponentStructure(n);componentCanvas(n)}
  // Boundary context must be final before attachment descriptors are projected;
  // otherwise render() would rewrite descriptor external types and become a
  // hidden second semantic mutation after the CRUD receipt is issued.
  syncAllNodeBoundaryContext();
  for(const n of nodes)componentConfig(n);
  for(const w of wires){wireCanvas(w);connectionConfig(w)}
  routeCache.clear();arrowPoseCache.clear();dragRouteSnapshots.clear();
  persistenceFingerprint=semanticFingerprint();
  updateRevisionReadout();
  render();
}
function runtimeCrud(operation){
  const mutates=['create','update','delete'].includes(operation.op);
  if(mutates)commitHistoryCapture();
  const receipt=SovSchematicData.applyOperation(diagram,operation);
  if(receipt.ok&&mutates){
    normalizeRuntimeAfterCrud();
    const resource=String(operation.resource||'item'),verb=operation.op==='create'?'Create':operation.op==='update'?'Update':'Delete';
    commitHistoryCapture(`${verb} ${resource[0]?.toUpperCase()||''}${resource.slice(1)}`);
    try{saveWorkspaceToStorage(LOCAL_RECOVERY_KEY,{explicit:false})}catch(_){ }
  }
  return SovSchematicData.clone(receipt);
}
// Graph queries and the message simulation read the live document; one session per page.
const graphSession=SovSchematicGraph.createSession();
function graphCall(name,args={}){return SovSchematicData.clone(graphSession.execute(name,snapshotDocument(),args))}
function apiOperation(op,resource,resourceId,value,patch,query){return runtimeCrud({schema:SovSchematicData.OPERATION_SCHEMA,id:`browser-${Date.now()}-${Math.random().toString(36).slice(2,7)}`,op,resource,resourceId,value,patch,query})}

const SovSchematicAPI={
  version:'0.1',
  formats:()=>({document:SovSchematicData.DOCUMENT_SCHEMA,workspace:SovSchematicData.WORKSPACE_SCHEMA,package:SovSchematicData.PACKAGE_SCHEMA,operation:SovSchematicData.OPERATION_SCHEMA,receipt:SovSchematicData.RECEIPT_SCHEMA}),
  document:{
    get:()=>snapshotDocument(),
    replace:(doc)=>{const value=replaceRuntimeDocument(doc);saveWorkspaceToStorage(LOCAL_RECOVERY_KEY,{explicit:false});return value},
    saveRecovery:()=>saveWorkspaceToStorage(LOCAL_RECOVERY_KEY,{explicit:false}),
    restoreRecovery:()=>restoreRecovery()
  },
  file:{
    info:()=>({name:currentFileName,format:currentFileFormat,dirty:isFileDirty(),revision:diagram.revision}),
    document:()=>snapshotDocument(),
    package:()=>snapshotPackage(),
    parse:(text)=>parseFilePayload(text),
    open:(payload,name='API.sov')=>applyOpenedPayload(typeof payload==='string'?parseFilePayload(payload):{format:payload?.schema===SovSchematicData.PACKAGE_SCHEMA?'package':payload?.schema===SovSchematicData.WORKSPACE_SCHEMA?'workspace':'document',payload},name,null)
  },
  list:(resource,query={})=>apiOperation('list',resource,null,null,null,query),
  get:(resource,id)=>apiOperation('read',resource,id),
  create:(resource,value)=>apiOperation('create',resource,null,value),
  update:(resource,id,patch)=>apiOperation('update',resource,id,null,patch),
  delete:(resource,id)=>apiOperation('delete',resource,id),
  execute:(operation)=>runtimeCrud(operation),
  history:{list:()=>historyList(),undo:()=>undoHistory(),redo:()=>redoHistory()},
  checkpoints:{list:()=>listCheckpoints(),create:(name)=>createCheckpoint(name),restore:(id)=>restoreCheckpoint(id)},
  selection:{components:()=>[...selectedComponentIds],copy:()=>copySelection(),paste:()=>pasteClipboard(),duplicate:()=>duplicateSelection()},
  view:{colour:()=>({theme:colorEngine.theme,palette:colorEngine.palette,palettes:['okabe-ito',...Object.keys(BASE_PALETTES).filter(k=>k!=='okabe-ito'),'mono','custom']}),setColour:({theme,palette}={})=>{if(theme)colorEngine.theme=theme;if(palette)colorEngine.palette=palette;applyColorEngine();return {theme:colorEngine.theme,palette:colorEngine.palette}},paletteAudit:()=>SovSchematicData.clone(paletteAudit()),appearance:()=>appearanceMode,setAppearance:(mode)=>{appearanceMode=mode;applyAppearanceMode();return appearanceMode},globalRate:()=>globalTimeScale(),setGlobalRate:(value)=>{setGlobalTimeScale(value);return globalTimeScale()}},
  render:{
    svg:(options={})=>renderStandaloneSvg(options),
    png:(options={})=>renderStandalonePng(options)
  },
  layout:{
    list:()=>SovSchematicData.clone(runLayoutOp('list')),
    active:()=>activeLayoutId(),
    switch:(id)=>SovSchematicData.clone(switchLayout(id)),
    create:(options={})=>SovSchematicData.clone(runLayoutOp('create',options,'New layout')),
    rename:(view,name)=>SovSchematicData.clone(runLayoutOp('rename',{view,name},'Rename layout')),
    delete:(view)=>{if(view===activeLayoutId())switchLayout(SovSchematicLayout.defaultId(diagram));return SovSchematicData.clone(runLayoutOp('delete',{view},'Delete layout'))},
    setDefault:(view)=>SovSchematicData.clone(runLayoutOp('set-default',{view},'Make default layout')),
    unplaced:()=>layoutUnplacedIds(),
    move:(id,to={})=>SovSchematicData.clone(runLayoutOp('move',{...to,id},'Move')),
    place:(id,options={})=>SovSchematicData.clone(runLayoutOp('place',{...options,id},'Place')),
    align:(ids,options={})=>SovSchematicData.clone(runLayoutOp('align',{...options,ids},'Align')),
    distribute:(ids,options={})=>SovSchematicData.clone(runLayoutOp('distribute',{...options,ids},'Distribute')),
    route:(wireId,spec=null)=>SovSchematicData.clone(runLayoutOp('route',{wireId,...(spec||{mode:'auto'})},'Route')),
    apply:(options={})=>SovSchematicData.clone(runLayoutOp('apply',{engine:'layered',...options},'Arrange layout')),
    metrics:(options={})=>SovSchematicData.clone(options.static===false?layoutMetrics(options):withPictureLabels(()=>layoutMetrics(options))),
    contrast:(options={})=>SovSchematicData.clone(options.static===false?contrastAudit(options):withPictureLabels(()=>contrastAudit(options))),
    rubric:()=>SovSchematicData.clone(LAYOUT_RUBRIC)
  },
  clock:{
    play:()=>simPlay(),pause:()=>simPause(),step:()=>SovSchematicData.clone(simStep()),advance:(ms)=>SovSchematicData.clone(simAdvance(ms)),
    reset:()=>simReset(),setSpeed:(x)=>{simClock.speed=Number(x)||1;const sel=document.getElementById('simSpeed');if(sel)sel.value=String(simClock.speed);return simClock.speed},
    toggle:(id)=>SovSchematicData.clone(simToggleLever(id)),send:(id)=>SovSchematicData.clone(simSend(id)),
    inspect:(what,id)=>{const r=simClock.run;if(!r)return {ok:false,code:'NO_SIMULATION',message:'The clock is stopped'};const v={taps:()=>r.taps(id),edges:()=>r.edges({node:id||null}),log:()=>({ok:true,log:r.log()}),refusals:()=>({ok:true,refusals:r.refusals()}),effects:()=>({ok:true,effects:r.effects()})}[what];return v?SovSchematicData.clone(v()):{ok:false,code:'UNKNOWN_VIEW',message:`Unknown view ${what}`}},resume:(parkId,decision='approve')=>SovSchematicData.clone(simResume(parkId,decision)),
    state:()=>simClock.run?{...SovSchematicData.clone(simClock.run.state()),playing:simClock.playing,speed:simClock.speed,stubbed:[...simClock.stubbed],levels:SovSchematicData.clone(simClock.run.levels()),parked:SovSchematicData.clone(simClock.run.parked())}:{running:false,note:simClock.note}
  },
  graph:{
    query:(verb,args={})=>graphCall('schematic.graph.query',{verb,args}),
    verbs:()=>[...SovSchematicGraph.queries]
  },
  sim:{
    start:(options={})=>graphCall('schematic.sim.start',options),
    stop:()=>graphCall('schematic.sim.stop'),
    inject:(node,message={})=>graphCall('schematic.sim.inject',{...message,node}),
    step:(n=1)=>graphCall('schematic.sim.step',{n}),
    set:(node,value)=>graphCall('schematic.sim.set',{node,value}),
    at:(time,action={})=>graphCall('schematic.sim.at',{...action,time}),
    advance:(ms)=>graphCall('schematic.sim.advance',{ms}),
    tick:(n=1)=>graphCall('schematic.sim.tick',{n}),
    run:(options={})=>graphCall('schematic.sim.run',options),
    resume:(parkId,options={})=>graphCall('schematic.sim.resume',{...options,parkId}),
    reconcile:(effectKey,options={})=>graphCall('schematic.sim.reconcile',{...options,effectKey}),
    inspect:(what='state',id)=>graphCall('schematic.sim.inspect',{what,id}),
    scenario:(idOrScenario,handlers)=>graphCall('schematic.sim.scenario',typeof idOrScenario==='string'?{id:idOrScenario,handlers}:{scenario:idOrScenario,handlers}),
    scenarios:()=>graphCall('schematic.sim.scenarios')
  },
  tools:()=>[...SovSchematicData.operationTools(),...SovSchematicGraph.tools()]
};
window.SovSchematicAPI=SovSchematicAPI;
