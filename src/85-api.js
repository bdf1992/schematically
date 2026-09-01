'use strict';
// 0.1 Beta concern: browser API adapter over the canonical CRUD/document core.

function normalizeRuntimeAfterCrud(){
  for(const n of nodes){ensureComponentStructure(n);componentCanvas(n);componentConfig(n)}
  for(const w of wires){wireCanvas(w);connectionConfig(w)}
  syncAllNodeBoundaryContext();
  routeCache.clear();arrowPoseCache.clear();dragRouteSnapshots.clear();
  persistenceFingerprint=semanticFingerprint();
  updateRevisionReadout();
  render();
}
function runtimeMutationTarget(operation){
  if(!['update','delete'].includes(operation.op))return null;
  if(operation.resource==='component')return nodes.find(n=>n.id===operation.resourceId)||null;
  if(operation.resource==='wire')return wires.find(w=>w.id===operation.resourceId)||null;
  return null;
}
function refusedApiReceipt(operation,message){return {schema:SovSchematicData.RECEIPT_SCHEMA,operationId:operation.id||null,ok:false,revisionBefore:diagram.revision,revisionAfter:diagram.revision,result:null,error:{message}}}
function runtimeCrud(operation){
  const target=runtimeMutationTarget(operation);
  if(target&&isEntityLocked(target))return refusedApiReceipt(operation,'Locked entity is immutable');
  if(operation.op==='create'&&operation.resource==='wire'){
    const a=nodes.find(n=>n.id===operation.value?.a),b=nodes.find(n=>n.id===operation.value?.b);
    if((a&&isEntityLocked(a))||(b&&isEntityLocked(b)))return refusedApiReceipt(operation,'Locked Component ports cannot accept new Wires');
  }
  const receipt=SovSchematicData.applyOperation(diagram,operation);
  if(receipt.ok&&['create','update','delete'].includes(operation.op)){
    normalizeRuntimeAfterCrud();
    try{saveWorkspaceToStorage(LOCAL_RECOVERY_KEY,{explicit:false})}catch(_){ }
  }
  return SovSchematicData.clone(receipt);
}
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
  tools:()=>SovSchematicData.operationTools()
};
window.SovSchematicAPI=SovSchematicAPI;
