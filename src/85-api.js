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
  view:{appearance:()=>appearanceMode,setAppearance:(mode)=>{appearanceMode=mode;applyAppearanceMode();return appearanceMode},globalRate:()=>globalTimeScale(),setGlobalRate:(value)=>{setGlobalTimeScale(value);return globalTimeScale()}},
  layout:{
    metrics:(options={})=>SovSchematicData.clone(layoutMetrics(options)),
    rubric:()=>SovSchematicData.clone(LAYOUT_RUBRIC)
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
