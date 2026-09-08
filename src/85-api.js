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
function apiOperation(op,resource,resourceId,value,patch,query){return runtimeCrud({schema:SovSchematicData.OPERATION_SCHEMA,id:`browser-${Date.now()}-${Math.random().toString(36).slice(2,7)}`,op,resource,resourceId,value,patch,query})}

let logicSession=null;
let logicVisualSession=null;
function prepareLogicProjection(){
  logicVisualSession=null;
  if(!logicSession)return;
  try{if(SovSchematicLogic.canonical(SovSchematicLogic.compile(diagram))===SovSchematicLogic.canonical(logicSession.program))logicVisualSession=logicSession}catch(_){ }
}
function logicWireValue(w,direction){
  if(!nodes.some(n=>(n.id===w.a||n.id===w.b)&&n.config?.logic))return null;
  const edge=logicVisualSession?.program.edges.find(e=>e.id===w.id);
  if(!edge)return false;
  const expected=edge.from===w.a?'forward':'reverse';
  return direction===expected&&logicVisualSession.values[edge.from].outputs[edge.output]===1;
}
function renderLogicProjection(){
  for(const g of nodesG.querySelectorAll('[data-id]')){
    const state=logicVisualSession?.values[g.dataset.id];g.classList.toggle('logic-high',!!state&&[...Object.values(state.outputs),...Object.values(state.inputs)].some(Boolean));
  }
  for(const g of wiresG.querySelectorAll('[data-wire-id]'))g.classList.toggle('logic-pending',!!logicVisualSession?.queue.some(e=>e.wire===g.dataset.wireId));
}
function executeLogic(request){
  const result=SovSchematicLogic.execute(snapshotDocument(),logicSession,request);
  if(result.ok){logicSession=result.session;if(!['get','replay'].includes(request.action))render()}
  window.dispatchEvent(new CustomEvent('schematic-runtime',{detail:result}));
  return SovSchematicData.clone(result);
}

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
    open:(payload,name='API.sov')=>applyOpenedPayload(typeof payload==='string'?parseFilePayload(payload):{format:payload?.schema===SovSchematicLogic.FILE_SCHEMA?'run':payload?.schema===SovSchematicData.PACKAGE_SCHEMA?'package':payload?.schema===SovSchematicData.WORKSPACE_SCHEMA?'workspace':'document',payload},name,null)
  },
  list:(resource,query={})=>apiOperation('list',resource,null,null,null,query),
  get:(resource,id)=>apiOperation('read',resource,id),
  create:(resource,value)=>apiOperation('create',resource,null,value),
  update:(resource,id,patch)=>apiOperation('update',resource,id,null,patch),
  delete:(resource,id)=>apiOperation('delete',resource,id),
  execute:(operation)=>runtimeCrud(operation),
  runtime:{execute:executeLogic,get:()=>executeLogic({action:'get'}),file:()=>snapshotLogicRun(),save:()=>saveLogicRun()},
  history:{list:()=>historyList(),undo:()=>undoHistory(),redo:()=>redoHistory()},
  checkpoints:{list:()=>listCheckpoints(),create:(name)=>createCheckpoint(name),restore:(id)=>restoreCheckpoint(id)},
  selection:{components:()=>[...selectedComponentIds],copy:()=>copySelection(),paste:()=>pasteClipboard(),duplicate:()=>duplicateSelection()},
  view:{appearance:()=>appearanceMode,setAppearance:(mode)=>{appearanceMode=mode;applyAppearanceMode();return appearanceMode},globalRate:()=>globalTimeScale(),setGlobalRate:(value)=>{setGlobalTimeScale(value);return globalTimeScale()}},
  tools:()=>[...SovSchematicData.operationTools(),...SovSchematicLogic.tools()]
};
window.SovSchematicAPI=SovSchematicAPI;
