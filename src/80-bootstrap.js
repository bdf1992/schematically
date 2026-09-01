'use strict';
// 0.1 Beta concern: Global focus, palette/grid/zoom, deletion, keyboard commands, and startup.

selectionBar.addEventListener('keydown',e=>{
  if(isEditableTarget(e.target))e.stopPropagation();
});
selectionBar.addEventListener('keyup',e=>{
  if(isEditableTarget(e.target))e.stopPropagation();
});
selectionSettingsPanel.addEventListener('keydown',e=>{
  if(isEditableTarget(e.target))e.stopPropagation();
});
selectionSettingsPanel.addEventListener('keyup',e=>{
  if(isEditableTarget(e.target))e.stopPropagation();
});
selectionBar.addEventListener('focusin',e=>{
  if(isEditableTarget(e.target))setCanvasKeyboardActive(false);
});
selectionBar.addEventListener('focusout',()=>{
  queueMicrotask(()=>{
    if(!isEditableTarget(document.activeElement))setCanvasKeyboardActive(!!selected);
  });
});
workspace.addEventListener('pointerdown',()=>setCanvasKeyboardActive(true));
document.querySelector('.workspace-wrap').addEventListener('pointerdown',e=>{
  if(e.target.closest('.selection-bar'))return;
  setCanvasKeyboardActive(true);
});

const editBtn=document.getElementById('editBtn'),editMenu=document.getElementById('editMenu'),viewBtn=document.getElementById('viewBtn'),viewMenu=document.getElementById('viewMenu'),helpBtn=document.getElementById('helpBtn'),shortcutHelp=document.getElementById('shortcutHelp');
function setUtilityMenu(which,open){for(const [btn,menu] of [[editBtn,editMenu],[viewBtn,viewMenu]]){const on=menu===which&&open;menu.hidden=!on;btn?.setAttribute('aria-expanded',String(on))}if(open&&shortcutHelp)shortcutHelp.hidden=true}
editBtn?.addEventListener('click',e=>{e.stopPropagation();setUtilityMenu(editMenu,editMenu.hidden)});viewBtn?.addEventListener('click',e=>{e.stopPropagation();setUtilityMenu(viewMenu,viewMenu.hidden)});editMenu?.addEventListener('click',e=>e.stopPropagation());viewMenu?.addEventListener('click',e=>e.stopPropagation());helpBtn?.addEventListener('click',e=>{e.stopPropagation();shortcutHelp.hidden=!shortcutHelp.hidden;setUtilityMenu(null,false);helpBtn.setAttribute('aria-expanded',String(!shortcutHelp.hidden))});shortcutHelp?.addEventListener('click',e=>e.stopPropagation());
// Capture phase: canvas/palette gestures stopPropagation on pointerdown, which must not veto menu dismissal.
document.addEventListener('pointerdown',e=>{if(editMenu&&!editMenu.hidden&&!editMenu.contains(e.target)&&!editBtn?.contains(e.target))setUtilityMenu(editMenu,false);if(viewMenu&&!viewMenu.hidden&&!viewMenu.contains(e.target)&&!viewBtn?.contains(e.target))setUtilityMenu(viewMenu,false);if(shortcutHelp&&!shortcutHelp.hidden&&!shortcutHelp.contains(e.target)&&e.target!==helpBtn){shortcutHelp.hidden=true;helpBtn?.setAttribute('aria-expanded','false')}},true);
document.getElementById('editUndoBtn')?.addEventListener('click',undoHistory);document.getElementById('editRedoBtn')?.addEventListener('click',redoHistory);document.getElementById('editCutBtn')?.addEventListener('click',cutSelection);document.getElementById('editCopyBtn')?.addEventListener('click',copySelection);document.getElementById('editPasteBtn')?.addEventListener('click',()=>pasteClipboard());document.getElementById('editDuplicateBtn')?.addEventListener('click',duplicateSelection);document.getElementById('checkpointCreateBtn')?.addEventListener('click',()=>createCheckpoint());document.getElementById('viewObjectsBtn')?.addEventListener('click',()=>{selectNode(null);document.querySelector('.inspector')?.scrollTo({top:0,behavior:'smooth'})});document.getElementById('viewFocusBtn')?.addEventListener('click',()=>{const n=nodes.find(n=>n.id===selected);if(n)focusComponent(n)});
document.getElementById('quickUndoBtn')?.addEventListener('click',undoHistory);document.getElementById('quickRedoBtn')?.addEventListener('click',redoHistory);document.getElementById('quickCheckpointBtn')?.addEventListener('click',()=>createCheckpoint());

paletteBtn.addEventListener('click',e=>{
  e.stopPropagation();setPalettePanel(paletteSettings.hidden);
});
paletteSettings.addEventListener('click',e=>e.stopPropagation());
colorThemeInput.addEventListener('change',()=>{
  colorEngine.theme=colorThemeInput.value;applyColorEngine();
});
colorPaletteInput.addEventListener('change',()=>{
  colorEngine.palette=colorPaletteInput.value;applyColorEngine();
});
diffuseSignalsInput.addEventListener('change',()=>{
  colorEngine.diffuse=diffuseSignalsInput.checked;render();restoreSelectedSurface();
});

gridBtn.addEventListener('click',e=>{
  e.stopPropagation();
  setPalettePanel(false);
  setGridPanel(gridSettings.hidden);
});
gridSettings.addEventListener('click',e=>e.stopPropagation());
document.addEventListener('pointerdown',e=>{
  if(!gridSettings.hidden && !gridSettings.contains(e.target) && e.target!==gridBtn)setGridPanel(false);
  if(!paletteSettings.hidden && !paletteSettings.contains(e.target) && e.target!==paletteBtn)setPalettePanel(false);
  if(!colorSlotPanel.hidden && !selectionBar.contains(e.target))closeColorSlotPanel();
});
gridVisibleInput.addEventListener('change',()=>{
  canvasGridVisible=gridVisibleInput.checked;
  applyGridSettings();
});
gridSnapInput.addEventListener('change',()=>{
  canvasSnapEnabled=gridSnapInput.checked;
  applyGridSettings();
  if(activeNodeDragState) refreshActiveNodeDragFromModifiers(activeNodeDragState.modifiers);
});
gridSizeInput.addEventListener('change',()=>{
  const next=Number(gridSizeInput.value);
  canvasGridSize=[12,16,24,32,48].includes(next)?next:24;
  applyGridSettings();
  if(activeNodeDragState) refreshActiveNodeDragFromModifiers(activeNodeDragState.modifiers);
});

zoomOutBtn.addEventListener('click',()=>{zoomAt(1/1.25);setCanvasKeyboardActive(true)});
zoomInBtn.addEventListener('click',()=>{zoomAt(1.25);setCanvasKeyboardActive(true)});
resetZoomBtn.addEventListener('click',()=>{resetZoom();setCanvasKeyboardActive(true)});
fitBtn.addEventListener('click',()=>{fitDiagram();setCanvasKeyboardActive(true)});

workspace.addEventListener('wheel',e=>{
  e.preventDefault();
  const factor=e.deltaY<0?1.12:1/1.12;
  zoomAt(factor,e.clientX,e.clientY);
},{passive:false});

flowBtn.addEventListener('click',()=>{
  showFlow=!showFlow; window.addEventListener('resize',()=>requestAnimationFrame(positionSelectionBar));
workspace.classList.toggle('show-flow',showFlow); flowBtn.classList.toggle('active',showFlow);
});

function handleCanvasKeydown(e){
  if(isEditableTarget(e.target))return;
  const code=shortcutCode(e),mod=e.ctrlKey||e.metaKey;

  // Escape must dismiss open header menus even when focus sits on the menu button, before the canvas-focus guard.
  if(code==='Escape'){
    const fileOpen=typeof fileMenu!=='undefined'&&fileMenu&&!fileMenu.hidden;
    const utilityOpen=(editMenu&&!editMenu.hidden)||(viewMenu&&!viewMenu.hidden)||(shortcutHelp&&!shortcutHelp.hidden);
    if(fileOpen||utilityOpen){
      if(fileOpen&&typeof setFileMenu==='function')setFileMenu(false);
      setUtilityMenu(null,false);
      if(shortcutHelp){shortcutHelp.hidden=true;helpBtn?.setAttribute('aria-expanded','false')}
      e.preventDefault();
      return;
    }
  }

  // Document-level edit shortcuts must survive selection bars disappearing after a mutation.
  if(mod&&!e.altKey){
    if(code==='KeyZ'){e.preventDefault();e.stopPropagation();if(e.shiftKey)redoHistory();else undoHistory();return}
    if(code==='KeyY'){e.preventDefault();e.stopPropagation();redoHistory();return}
    if(code==='KeyC'){e.preventDefault();e.stopPropagation();copySelection();return}
    if(code==='KeyX'){e.preventDefault();e.stopPropagation();cutSelection();return}
    if(code==='KeyV'){e.preventDefault();e.stopPropagation();pasteClipboard();return}
    if(code==='KeyD'){e.preventDefault();e.stopPropagation();duplicateSelection();return}
    if(code==='KeyA'){e.preventDefault();e.stopPropagation();setComponentSelection(nodes.filter(n=>!isEffectivelyHidden(n)).map(n=>n.id),nodes.at(-1)?.id);if(selected)selectNode(selected,{focus:false,preserveSet:true});return}
  }
  if(!canvasKeyboardActive && document.activeElement!==workspace)return;
  if(quickSearchActive){return}
  if(!selected&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&typeof e.key==='string'&&e.key.length===1&&e.key.trim()){e.preventDefault();e.stopPropagation();openQuickSearch(e.key);return}
  if(code==='Slash'&&e.shiftKey){e.preventDefault();shortcutHelp.hidden=!shortcutHelp.hidden;return}

  if(code==='Space'){
    spacePanHeld=true;
    document.querySelector('.workspace-wrap')?.classList.add('space-pan');
    e.preventDefault();
    return;
  }


  if(activeNodeDragState && [
    'ShiftLeft','ShiftRight','AltLeft','AltRight',
    'ControlLeft','ControlRight','MetaLeft','MetaRight'
  ].includes(code)){
    e.preventDefault();
    refreshActiveNodeDragFromModifiers(e);
    return;
  }

  if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(code)){
    if(moveSelectedByArrow(e)){
      e.preventDefault();
      e.stopPropagation();
    }
    return;
  }

  if(code==='Delete'||code==='Backspace'){
    if(selected){
      e.preventDefault();e.stopPropagation();deleteSelected();
    }
    return;
  }

  if(code==='Enter'){const n=nodes.find(n=>n.id===selected);if(n){e.preventDefault();focusComponent(n)}return}

  if(code==='Home'){
    e.preventDefault();e.stopPropagation();
    if(e.shiftKey)resetZoom();else fitDiagram();
    return;
  }

  if(isZoomInKey(e)){
    e.preventDefault();e.stopPropagation();zoomAt(1.25);
    return;
  }

  if(isZoomOutKey(e)){
    e.preventDefault();e.stopPropagation();zoomAt(1/1.25);
    return;
  }

  if(code==='Digit0'||code==='Numpad0'){
    e.preventDefault();e.stopPropagation();resetZoom();
    return;
  }

  if(code==='KeyF'){
    e.preventDefault();e.stopPropagation();fitDiagram();
    return;
  }

  if(code==='Escape'){
    if(quickSearchActive)closeQuickSearch();if(shortcutHelp)shortcutHelp.hidden=true;setUtilityMenu(null,false);
    if(activeNodeDragState)finishActiveNodeDrag(null,{force:true,reason:'cancelled'});
    if(keyboardMoveNodeId)finishKeyboardMove(e);
    if(paletteDrag)cleanupPaletteGesture({status:null});
    finishPanGesture();
    cancelWireDrag();
    statusEl.textContent='Ready';
    e.preventDefault();
  }
}
function handleCanvasKeyup(e){
  if(isEditableTarget(e.target))return;
  if(!canvasKeyboardActive && document.activeElement!==workspace)return;

  const code=shortcutCode(e);

  if(code==='Space'){
    spacePanHeld=false;
    document.querySelector('.workspace-wrap')?.classList.remove('space-pan');
    e.preventDefault();
    return;
  }


  if(activeNodeDragState && [
    'ShiftLeft','ShiftRight','AltLeft','AltRight',
    'ControlLeft','ControlRight','MetaLeft','MetaRight'
  ].includes(code)){
    e.preventDefault();
    refreshActiveNodeDragFromModifiers(e);
    return;
  }

  if(keyboardMoveNodeId&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(code)){
    e.preventDefault();
    finishKeyboardMove(e);
  }
}
window.addEventListener('keydown',handleCanvasKeydown,true);
window.addEventListener('keyup',handleCanvasKeyup,true);
window.addEventListener('resize',()=>requestAnimationFrame(positionSelectionBar));
workspace.classList.toggle('show-flow',showFlow);
flowBtn.classList.toggle('active',showFlow);
refreshCanvasScopeControl();
applyGridSettings();
applyCamera();
applyColorEngine();


if(typeof initializePersistenceTracking==='function')initializePersistenceTracking();
if(typeof initializeEditorKernel==='function')initializeEditorKernel();
