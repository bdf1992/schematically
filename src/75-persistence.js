'use strict';
// 0.1 Beta concern: file lifecycle, recovery, package formats, and document rehydration.

const LOCAL_RECOVERY_KEY='soveraeign.schematic.recovery@0.1';
const LEGACY_LOCAL_SAVE_KEY='soveraeign.schematic.saved@0.1';
let persistenceTimer=null;
let persistenceFingerprint=null;
let currentFileHandle=null;
let currentFileName='Untitled.sov';
let currentFileFormat='document';
let lastFileFingerprint=null;

function snapshotDocument(){
  const doc=SovSchematicData.makeDocument(SovSchematicData.clone(diagram));
  doc.meta=doc.meta||{};
  doc.meta.title=doc.meta.title||'Soveraeign Schematic';
  return doc;
}
function semanticFingerprint(){
  const doc=snapshotDocument();
  doc.revision=0;
  if(doc.meta){delete doc.meta.updatedAt;delete doc.meta.savedAt}
  return JSON.stringify(doc);
}
function captureWorkspace(){
  return {
    schema:SovSchematicData.WORKSPACE_SCHEMA,
    document:snapshotDocument(),
    view:{
      camera:{...camera},
      grid:{visible:canvasGridVisible,snap:canvasSnapEnabled,size:canvasGridSize},
      showFlow,
      colorEngine:SovSchematicData.clone(colorEngine),
      appearanceMode,
      globalRate:globalTimeScale()
    }
  };
}
function updateRevisionReadout(){
  if(documentRevisionReadout)documentRevisionReadout.value=String(diagram.revision||0);
  updateFileReadout();
}
function commitDocumentRevisionIfChanged(){
  const next=semanticFingerprint();
  if(persistenceFingerprint===null){persistenceFingerprint=next;updateRevisionReadout();return false}
  if(next===persistenceFingerprint){updateRevisionReadout();return false}
  SovSchematicData.touch(diagram);
  persistenceFingerprint=semanticFingerprint();
  updateRevisionReadout();
  return true;
}
function saveWorkspaceToStorage(key=LEGACY_LOCAL_SAVE_KEY,{explicit=true}={}){
  commitDocumentRevisionIfChanged();
  const workspace=captureWorkspace();
  workspace.document.meta=workspace.document.meta||{};
  if(explicit)workspace.document.meta.savedAt=new Date().toISOString();
  try{localStorage.setItem(key,JSON.stringify(workspace))}
  catch(error){
    if(explicit)throw error;
    console.warn('Recovery storage unavailable',error);
  }
  persistenceFingerprint=semanticFingerprint();
  updateRevisionReadout();
  return workspace;
}
function scheduleLocalAutosave(){
  updateFileReadout();if(typeof scheduleHistoryCapture==='function')scheduleHistoryCapture();
  if(persistenceTimer)clearTimeout(persistenceTimer);
  persistenceTimer=setTimeout(()=>{
    if(activeNodeDragState||wireDrag||componentTransformGesture){scheduleLocalAutosave();return}
    try{saveWorkspaceToStorage(LOCAL_RECOVERY_KEY,{explicit:false})}catch(error){console.warn('Recovery save failed',error)}
  },420);
}
function syncRuntimeAfterDocumentReplace(){
  let maxSeq=0;
  for(const n of nodes){
    const m=String(n.id||'').match(/^c(\d+)$/);if(m)maxSeq=Math.max(maxSeq,Number(m[1]));
    ensureComponentStructure(n);componentCanvas(n);
  }
  syncAllNodeBoundaryContext();
  for(const n of nodes)componentConfig(n);
  for(const w of wires){wireCanvas(w);connectionConfig(w)}
  seq=Math.max(seq,maxSeq+1);
  routeCache.clear();arrowPoseCache.clear();dragRouteSnapshots.clear();
  selected=null;hideSelectionBar();
  persistenceFingerprint=semanticFingerprint();
  updateRevisionReadout();
  render();selectNode(null);if(typeof initializeHistory==='function'&&!historyState.replaying)initializeHistory();
}
function replaceRuntimeDocument(input){
  const doc=input?.schema===SovSchematicData.WORKSPACE_SCHEMA?input.document:input;
  const normalized=SovSchematicData.makeDocument(SovSchematicData.clone(doc));
  const valid=SovSchematicData.validateDocument(normalized);
  if(!valid.ok)throw new Error(valid.errors.join('; '));
  SovSchematicData.replaceDocument(diagram,normalized);
  syncRuntimeAfterDocumentReplace();
  return snapshotDocument();
}
function applyWorkspace(bundle){
  if(!bundle||bundle.schema!==SovSchematicData.WORKSPACE_SCHEMA)return replaceRuntimeDocument(bundle);
  replaceRuntimeDocument(bundle.document);
  const view=bundle.view||{};
  if(view.camera){camera={...BASE_VIEW,...view.camera};applyCamera()}
  if(view.grid){
    canvasGridVisible=view.grid.visible!==false;canvasSnapEnabled=view.grid.snap!==false;
    canvasGridSize=[12,16,24,32,48].includes(Number(view.grid.size))?Number(view.grid.size):24;applyGridSettings();
  }
  if(typeof view.showFlow==='boolean'){showFlow=view.showFlow;document.getElementById('workspace')?.classList.toggle('show-flow',showFlow);flowBtn?.classList.toggle('active',showFlow)}
  if(view.colorEngine&&typeof view.colorEngine==='object'){Object.assign(colorEngine,view.colorEngine);applyColorEngine()}
  if(view.appearanceMode){appearanceMode=view.appearanceMode;applyAppearanceMode()}
  if(view.globalRate!=null){diagram.meta=diagram.meta||{};diagram.meta.timeScale=Number(view.globalRate)||1}
  render();
  return captureWorkspace();
}
function loadWorkspaceFromStorage(key=LEGACY_LOCAL_SAVE_KEY){
  const raw=localStorage.getItem(key);if(!raw)throw new Error('No saved schematic found');
  return applyWorkspace(JSON.parse(raw));
}
function downloadJsonDocument(){
  saveWorkspaceToStorage(LOCAL_RECOVERY_KEY,{explicit:false});
  const doc=snapshotDocument();
  const blob=new Blob([JSON.stringify(doc,null,2)],{type:'application/json'}),a=document.createElement('a');
  a.href=URL.createObjectURL(blob);a.download=`${doc.id||'schematic'}.sov-schematic.json`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),500);
}
async function importJsonFile(file){
  if(!file)throw new Error('No file selected');
  const parsed=JSON.parse(await file.text());
  if(parsed.schema===SovSchematicData.WORKSPACE_SCHEMA)applyWorkspace(parsed);else replaceRuntimeDocument(parsed);
  saveWorkspaceToStorage(LOCAL_RECOVERY_KEY,{explicit:false});
  return snapshotDocument();
}
function sanitizeFileBase(value){
  const base=String(value||'Untitled').replace(/\.(sovpak|sov|json)$/i,'').trim()||'Untitled';
  return base.replace(/[\\/:*?"<>|]+/g,'-').replace(/\s+/g,' ').slice(0,80)||'Untitled';
}
function fileBaseName(){
  const metaTitle=diagram.meta?.title;
  const current=sanitizeFileBase(currentFileName);
  if(current&&current.toLowerCase()!=='untitled')return current;
  return sanitizeFileBase(metaTitle||diagram.id||'Untitled');
}
function preferredExtension(format=currentFileFormat){return format==='package'?'.sovpak':'.sov'}
function suggestedFileName(format=currentFileFormat){return `${fileBaseName()}${preferredExtension(format)}`}
function documentFileText(){
  commitDocumentRevisionIfChanged();
  return JSON.stringify(snapshotDocument(),null,2);
}
function collectPackageTemplates(){
  return (GROUPS.Components||[]).map(symbolId=>{
    const symbol=byId(symbolId);
    return {
      id:`component:${symbolId}`,
      kind:'component',
      symbolId,
      name:symbol?.name||symbolId,
      family:symbol?.family||null,
      role:symbol?.role||null,
      meaning:symbol?.meaning||'',
      properties:SovSchematicData.clone(symbol?.properties||[])
    };
  });
}
function collectPackageAssets(){
  const assets=[];
  for(const component of nodes){
    const graphic=component.config?.presentation?.graphic;
    if(graphic?.kind==='custom'&&typeof graphic.svg==='string'&&graphic.svg.trim()){
      assets.push({id:`component:${component.id}:graphic`,kind:'svg',mime:'image/svg+xml',ownerId:component.id,text:graphic.svg});
    }
  }
  return assets;
}
function snapshotPackage(){
  commitDocumentRevisionIfChanged();
  const workspace=captureWorkspace();
  return SovSchematicData.makePackage({
    document:workspace.document,
    workspace:{view:workspace.view},
    templates:collectPackageTemplates(),
    assets:collectPackageAssets(),
    manifest:{title:workspace.document.meta?.title||fileBaseName()}
  });
}
function packageFileText(){return JSON.stringify(snapshotPackage(),null,2)}
function fileTextForFormat(format){return format==='package'?packageFileText():documentFileText()}
function mimeForFormat(format){return format==='package'?'application/vnd.soveraeign.schematic-package+json':'application/vnd.soveraeign.schematic+json'}
function isFileDirty(){return lastFileFingerprint===null||semanticFingerprint()!==lastFileFingerprint}
function updateFileReadout(){
  const dirty=isFileDirty();
  if(fileNameReadout)fileNameReadout.textContent=currentFileName||suggestedFileName(currentFileFormat);
  if(fileStateReadout)fileStateReadout.textContent=lastFileFingerprint===null?'Unsaved':dirty?'Modified':`Saved · r${diagram.revision||0}`;
  if(fileBtn){fileBtn.classList.toggle('modified',dirty);fileBtn.title=dirty?'File · unsaved changes':'File'}
}
function markFileSaved(name,format,handle=null){
  currentFileName=name||suggestedFileName(format);
  currentFileFormat=format||'document';
  currentFileHandle=handle||null;
  lastFileFingerprint=semanticFingerprint();
  updateFileReadout();
}
function triggerDownload(text,name,mime){
  const blob=new Blob([text],{type:mime});
  const url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),700);
}
async function writeFileHandle(handle,text){
  const writable=await handle.createWritable();
  await writable.write(text);
  await writable.close();
}
async function saveSchematicFile({saveAs=false,format=currentFileFormat}={}){
  const targetFormat=format==='package'?'package':'document';
  const text=fileTextForFormat(targetFormat);
  const mime=mimeForFormat(targetFormat);
  const suggested=targetFormat===currentFileFormat?currentFileName:suggestedFileName(targetFormat);

  if(!saveAs&&currentFileHandle&&targetFormat===currentFileFormat){
    await writeFileHandle(currentFileHandle,text);
    markFileSaved(currentFileHandle.name||suggested,targetFormat,currentFileHandle);
    return {mode:'handle',name:currentFileName,format:targetFormat};
  }

  if(typeof window.showSaveFilePicker==='function'){
    const ext=preferredExtension(targetFormat);
    try{
      const handle=await window.showSaveFilePicker({
        suggestedName:suggested.endsWith(ext)?suggested:`${sanitizeFileBase(suggested)}${ext}`,
        types:[{description:targetFormat==='package'?'SOV Schematic Package':'SOV Schematic',accept:{[mime]:[ext]}}]
      });
      await writeFileHandle(handle,text);
      markFileSaved(handle.name||suggested,targetFormat,handle);
      return {mode:'handle',name:currentFileName,format:targetFormat};
    }catch(error){if(error?.name==='AbortError')return {mode:'cancelled'};throw error}
  }

  const name=suggested.endsWith(preferredExtension(targetFormat))?suggested:suggestedFileName(targetFormat);
  triggerDownload(text,name,mime);
  markFileSaved(name,targetFormat,null);
  return {mode:'download',name,format:targetFormat};
}
function applyPackage(bundle){
  const check=SovSchematicData.validatePackage(bundle);
  if(!check.ok)throw new Error(check.errors.join('; '));
  const workspace={schema:SovSchematicData.WORKSPACE_SCHEMA,document:bundle.document,view:bundle.workspace?.view||{}};
  return applyWorkspace(workspace);
}
function parseFilePayload(text){
  let parsed;
  try{parsed=JSON.parse(text)}catch(_){throw new Error('File is not valid SOV/JSON data')}
  if(parsed?.schema===SovSchematicData.PACKAGE_SCHEMA)return {format:'package',payload:parsed};
  if(parsed?.schema===SovSchematicData.DOCUMENT_SCHEMA)return {format:'document',payload:parsed};
  if(parsed?.schema===SovSchematicData.WORKSPACE_SCHEMA)return {format:'workspace',payload:parsed};
  throw new Error(`Unsupported file schema: ${parsed?.schema||'missing'}`);
}
function applyOpenedPayload(parsed,name='Untitled.sov',handle=null){
  const {format,payload}=parsed;
  if(format==='package')applyPackage(payload);
  else if(format==='workspace')applyWorkspace(payload);
  else replaceRuntimeDocument(payload);
  currentFileFormat=format==='package'?'package':'document';
  currentFileName=name||suggestedFileName(currentFileFormat);
  currentFileHandle=handle;
  lastFileFingerprint=semanticFingerprint();
  saveWorkspaceToStorage(LOCAL_RECOVERY_KEY,{explicit:false});
  updateFileReadout();
  return snapshotDocument();
}
async function openFileObject(file,handle=null){
  if(!file)throw new Error('No file selected');
  const parsed=parseFilePayload(await file.text());
  return applyOpenedPayload(parsed,file.name||'Untitled.sov',handle);
}
function confirmDiscardIfDirty(action='continue'){
  if(!isFileDirty())return true;
  return window.confirm(`Unsaved changes will be discarded. ${action}?`);
}
async function chooseOpenFile(){
  if(typeof window.showOpenFilePicker==='function'){
    try{
      const [handle]=await window.showOpenFilePicker({
        multiple:false,
        types:[{description:'SOV Schematic files',accept:{'application/vnd.soveraeign.schematic+json':['.sov'],'application/vnd.soveraeign.schematic-package+json':['.sovpak'],'application/json':['.json']}}]
      });
      if(!handle)return;
      if(!confirmDiscardIfDirty('Open another file'))return;
      await openFileObject(await handle.getFile(),handle);
      statusEl.textContent=`Opened · ${currentFileName}`;
      return;
    }catch(error){if(error?.name==='AbortError')return;console.warn('Native open failed; falling back to file input',error)}
  }
  fileOpenInput?.click();
}
function newSchematic(){
  if(!confirmDiscardIfDirty('Create a new schematic'))return false;
  const doc=SovSchematicData.makeDocument({id:`schematic-${Date.now()}`,meta:{title:'Untitled'}});
  replaceRuntimeDocument(doc);
  currentFileHandle=null;currentFileName='Untitled.sov';currentFileFormat='document';lastFileFingerprint=null;
  saveWorkspaceToStorage(LOCAL_RECOVERY_KEY,{explicit:false});
  updateFileReadout();
  statusEl.textContent='New schematic';
  return true;
}
function restoreRecovery(){
  if(!confirmDiscardIfDirty('Restore browser recovery'))return false;
  const raw=localStorage.getItem(LOCAL_RECOVERY_KEY)||localStorage.getItem(LEGACY_LOCAL_SAVE_KEY);if(!raw)throw new Error('No recovery snapshot found');
  applyWorkspace(JSON.parse(raw));
  currentFileHandle=null;currentFileName='Recovered.sov';currentFileFormat='document';lastFileFingerprint=null;
  updateFileReadout();
  statusEl.textContent='Recovery restored · save to keep it';
  return true;
}
function exportSvgFile(){
  cancelWireDrag();
  const clone=workspace.cloneNode(true);
  clone.querySelector('#ghostLayer')?.replaceChildren();clone.querySelector('#paletteDropLayer')?.replaceChildren();
  clone.querySelectorAll('.selected,.snap-target,.wiring-source').forEach(x=>x.classList.remove('selected','snap-target','wiring-source'));
  const defs=document.querySelector('.hidden-symbols defs').cloneNode(true);clone.insertBefore(defs,clone.firstChild);
  triggerDownload(new XMLSerializer().serializeToString(clone),`${fileBaseName()}.svg`,'image/svg+xml');
}
function setFileMenu(open){
  if(!fileMenu)return;
  fileMenu.hidden=!open;fileBtn?.setAttribute('aria-expanded',String(open));
  if(open){
    updateFileReadout();
    try{if(typeof setPaletteSettings==='function')setPaletteSettings(false)}catch(_){}
    try{if(typeof setGridSettings==='function')setGridSettings(false)}catch(_){}
  }
}
function initializePersistenceTracking(){
  persistenceFingerprint=semanticFingerprint();
  lastFileFingerprint=null;
  updateRevisionReadout();
}

if(fileBtn)fileBtn.addEventListener('click',event=>{event.stopPropagation();setFileMenu(fileMenu.hidden)});
if(fileMenu)fileMenu.addEventListener('click',event=>event.stopPropagation());
if(fileNewBtn)fileNewBtn.addEventListener('click',()=>{setFileMenu(false);newSchematic()});
if(fileOpenBtn)fileOpenBtn.addEventListener('click',()=>{setFileMenu(false);chooseOpenFile()});
if(fileOpenInput)fileOpenInput.addEventListener('change',async()=>{
  try{
    const file=fileOpenInput.files?.[0];
    if(!file)return;
    if(!confirmDiscardIfDirty('Open another file'))return;
    await openFileObject(file,null);statusEl.textContent=`Opened · ${currentFileName}`;
  }catch(error){statusEl.textContent=`Open failed · ${error.message}`}
  finally{fileOpenInput.value=''}
});
if(fileSaveBtn)fileSaveBtn.addEventListener('click',async()=>{
  setFileMenu(false);
  try{const result=await saveSchematicFile({saveAs:false});if(result.mode!=='cancelled')statusEl.textContent=`Saved · ${result.name}`}
  catch(error){statusEl.textContent=`Save failed · ${error.message}`}
});
if(fileSaveAsBtn)fileSaveAsBtn.addEventListener('click',async()=>{
  setFileMenu(false);
  try{const result=await saveSchematicFile({saveAs:true,format:currentFileFormat});if(result.mode!=='cancelled')statusEl.textContent=`Saved as · ${result.name}`}
  catch(error){statusEl.textContent=`Save failed · ${error.message}`}
});
if(fileExportPakBtn)fileExportPakBtn.addEventListener('click',async()=>{
  setFileMenu(false);
  try{
    const name=`${fileBaseName()}.sovpak`;
    triggerDownload(packageFileText(),name,mimeForFormat('package'));
    statusEl.textContent=`Package exported · ${name}`;
  }catch(error){statusEl.textContent=`Package failed · ${error.message}`}
});
if(fileExportSvgBtn)fileExportSvgBtn.addEventListener('click',()=>{setFileMenu(false);exportSvgFile();statusEl.textContent='SVG exported'});
if(fileRestoreRecoveryBtn)fileRestoreRecoveryBtn.addEventListener('click',()=>{
  setFileMenu(false);
  try{restoreRecovery()}catch(error){statusEl.textContent=error.message}
});
document.addEventListener('pointerdown',event=>{if(fileMenu&&!fileMenu.hidden&&!fileMenu.contains(event.target)&&event.target!==fileBtn)setFileMenu(false)});
document.addEventListener('keydown',event=>{
  if(!(event.ctrlKey||event.metaKey)||event.altKey)return;
  const key=String(event.key||'').toLowerCase();
  if(key==='s'){
    event.preventDefault();
    saveSchematicFile({saveAs:event.shiftKey}).then(result=>{if(result.mode!=='cancelled')statusEl.textContent=`Saved · ${result.name}`}).catch(error=>statusEl.textContent=`Save failed · ${error.message}`);
  }else if(key==='o'){
    event.preventDefault();chooseOpenFile();
  }else if(key==='n'){
    event.preventDefault();newSchematic();
  }
});
