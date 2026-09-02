'use strict';
// 0.1 Beta concern: Palette drag, camera, pan, grid, keyboard movement, and containment geometry.

function svgToWorkspacePixel(x,y){
  const pt=workspace.createSVGPoint();pt.x=x;pt.y=y;
  const screen=pt.matrixTransform(workspace.getScreenCTM());
  const wrap=document.querySelector('.workspace-wrap').getBoundingClientRect();
  return {x:screen.x-wrap.left,y:screen.y-wrap.top};
}


function canvasContainsClientPoint(x,y){const r=workspace.getBoundingClientRect();return x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom}
function removePaletteFloat(){
  // Recovery invariant: a tray drag may own at most one floating ghost.
  document.querySelectorAll('.palette-drag-float').forEach(el=>el.remove());
  if(paletteDrag)paletteDrag.floatEl=null;
}
function clearPaletteDropGhost(){paletteDropLayer.replaceChildren()}
function cleanupPaletteGesture({status='Select'}={}){
  if(paletteDrag?.holdTimer){
    clearTimeout(paletteDrag.holdTimer);
    paletteDrag.holdTimer=null;
  }
  removePaletteFloat();
  clearPaletteDropGhost();
  document.querySelectorAll('.symbol-card.drag-source').forEach(el=>el.classList.remove('drag-source'));
  paletteDrag=null;
  if(status!==null)statusEl.textContent=status;
}
function makePaletteFloat(symbolId){
  removePaletteFloat();
  const s=byId(symbolId),el=document.createElement('div');
  el.className='palette-drag-float';
  el.dataset.paletteGhost='true';
  el.innerHTML=`${glyph(symbolId)}<b>${s.name}</b>`;
  document.body.appendChild(el);
  return el;
}
function drawPaletteDropGhost(symbolId,p){
  const s=byId(symbolId),preset=SovSchematicData.templatePreset(symbolId),dim=preset?.form?.dimension??2;
  paletteDropLayer.replaceChildren();
  const g=document.createElementNS('http://www.w3.org/2000/svg','g');
  g.setAttribute('class','component-drop-ghost');
  g.setAttribute('transform',`translate(${p.x} ${p.y})`);
  // The ghost has the dimension of what will be placed: a dot, a segment, or a surface.
  if(dim===0)g.innerHTML=`<circle class="body" r="8"/><text x="0" y="24" text-anchor="middle">${escapeXML(s.name)}</text>`;
  else if(dim===1){const half=(preset?.presentation?.size?.w||240)/2;g.innerHTML=`<line class="body" x1="${-half}" y1="0" x2="${half}" y2="0"/><text x="0" y="20" text-anchor="middle">${escapeXML(s.name)}</text>`}
  else{const w=preset?.presentation?.size?.w||112,h=preset?.presentation?.size?.h||84;g.innerHTML=`<rect class="body" x="${-w/2}" y="${-h/2}" width="${w}" height="${h}" rx="8"/>
    ${preset?'':`<use class="glyph" href="#sym-${symbolId}" x="-40" y="-29" width="80" height="54"/>`}
    <text x="0" y="${h/2-10}" text-anchor="middle">${escapeXML(s.name)}</text>`}
  paletteDropLayer.appendChild(g);
}
function updatePaletteDrag(x,y){
  if(!paletteDrag?.active)return;
  paletteDrag.lastClient={x,y};
  const over=canvasContainsClientPoint(x,y);
  paletteDrag.overCanvas=over;

  if(over){
    removePaletteFloat();
    // Held/ghost position is raw pointer position. Grid is release-only.
    drawPaletteDropGhost(paletteDrag.symbolId,svgPoint(x,y));
    statusEl.textContent='Ghost free · release to settle';
  }else{
    clearPaletteDropGhost();
    if(!paletteDrag.floatEl)paletteDrag.floatEl=makePaletteFloat(paletteDrag.symbolId);
    paletteDrag.floatEl.style.left=`${x}px`;
    paletteDrag.floatEl.style.top=`${y}px`;
    statusEl.textContent='Drag component onto canvas';
  }
}
function beginPaletteDrag(){
  if(!paletteDrag||paletteDrag.active)return;
  paletteDrag.active=true;
  paletteDrag.button.classList.add('drag-source');
  updatePaletteDrag(paletteDrag.lastClient.x,paletteDrag.lastClient.y);
}
function canPlaceComponentOnActiveCanvas(){return true}
function finishPaletteGesture(e,cancelled=false){
  if(!paletteDrag)return;

  const session=paletteDrag;
  if(session.holdTimer){
    clearTimeout(session.holdTimer);
    session.holdTimer=null;
  }
  const active=session.active;
  const symbolId=session.symbolId;
  const over=active&&session.overCanvas&&canvasContainsClientPoint(e.clientX,e.clientY);

  // Clear visual/session state before creation causes any synchronous UI work.
  cleanupPaletteGesture({status:null});

  try{
    if(!cancelled&&!canPlaceComponentOnActiveCanvas()){statusEl.textContent='1D canvas accepts Wire Parts, not Components';return}
    if(!cancelled&&over){
      const q=svgPoint(e.clientX,e.clientY);
      addNode(symbolId,q.x,q.y,e);
    }else if(!cancelled&&!active){
      addNode(symbolId);
    }
    statusEl.textContent='Select';
  }catch(err){
    console.error(err);
    statusEl.textContent='Placement failed · see console';
    throw err;
  }
}
function bindPaletteComponent(button,symbolId){
  button.addEventListener('pointerdown',e=>{
    if(e.button!==0)return;
    e.preventDefault();
    e.stopPropagation();

    // Starting a new gesture is a hard recovery boundary.
    cleanupPaletteGesture({status:null});

    paletteDrag={
      button,
      symbolId,
      pointerId:e.pointerId,
      startClient:{x:e.clientX,y:e.clientY},
      lastClient:{x:e.clientX,y:e.clientY},
      active:false,
      overCanvas:false,
      floatEl:null,
      holdTimer:null
    };

    paletteDrag.holdTimer=setTimeout(()=>{
      if(paletteDrag&&paletteDrag.pointerId===e.pointerId)beginPaletteDrag();
    },PALETTE_HOLD_DELAY);
  });
}
function handlePalettePointerMove(e){
  if(!paletteDrag||paletteDrag.pointerId!==e.pointerId)return;

  paletteDrag.lastClient={x:e.clientX,y:e.clientY};
  const dx=e.clientX-paletteDrag.startClient.x;
  const dy=e.clientY-paletteDrag.startClient.y;

  if(!paletteDrag.active&&Math.hypot(dx,dy)>=PALETTE_DRAG_THRESHOLD){
    if(paletteDrag.holdTimer){
      clearTimeout(paletteDrag.holdTimer);
      paletteDrag.holdTimer=null;
    }
    beginPaletteDrag();
  }

  if(paletteDrag.active){
    e.preventDefault();
    updatePaletteDrag(e.clientX,e.clientY);
  }
}
function handlePalettePointerUp(e){
  if(!paletteDrag||paletteDrag.pointerId!==e.pointerId)return;
  e.preventDefault();
  finishPaletteGesture(e,false);
}
function handlePalettePointerCancel(e){
  if(!paletteDrag||paletteDrag.pointerId!==e.pointerId)return;
  finishPaletteGesture(e,true);
}

// A tray drag is tracked by the window after pointer-down instead of by the
// source card. This prevents orphan ghosts when pointer capture is interrupted.
window.addEventListener('pointermove',handlePalettePointerMove,true);
window.addEventListener('pointerup',handlePalettePointerUp,true);
window.addEventListener('pointercancel',handlePalettePointerCancel,true);
window.addEventListener('blur',()=>{
  if(paletteDrag)cleanupPaletteGesture({status:'Select'});
});
document.addEventListener('visibilitychange',()=>{
  if(document.hidden&&paletteDrag)cleanupPaletteGesture({status:'Select'});
});


for (const [group, ids] of Object.entries(GROUPS)) {
  const section=document.createElement('div'); section.className='section';
  section.dataset.group=group.toLowerCase();
  section.innerHTML=`<h2>${group}</h2><div class="symbol-grid${group==='Primitives'?' primitive-grid':''}"></div>`;
  const grid=section.querySelector('.symbol-grid');
  ids.forEach(id=>{
    const s=byId(id), b=document.createElement('button'),preset=SovSchematicData.templatePreset(id);
    b.type='button'; b.className='symbol-card'+(preset?' primitive':'');b.dataset.symbolId=id;
    const caption=preset?`${preset.form.dimension}D · ${s.role}`:`${s.family} · ${s.diagram_class}`;
    b.innerHTML=glyph(id)+`<b>${s.name}</b><small>${caption}</small>`;
    bindPaletteComponent(b,id);
    grid.appendChild(b);
  });
  palette.appendChild(section);
}

function svgPoint(cx,cy){
  const pt=workspace.createSVGPoint(); pt.x=cx; pt.y=cy;
  return pt.matrixTransform(workspace.getScreenCTM().inverse());
}
function currentZoom(){
  return BASE_VIEW.w / camera.w;
}
function applyCamera(){
  workspace.setAttribute('viewBox',`${camera.x} ${camera.y} ${camera.w} ${camera.h}`);
  zoomReadout.textContent=`${Math.round(currentZoom()*100)}%`;
  requestAnimationFrame(positionSelectionBar);
}
function setPanMode(active){
  document.querySelector('.workspace-wrap')?.classList.toggle('pan-mode',!!active);
}
function beginPanGesture(e){
  if(e.button===0&&e.target===workspace&&e.shiftKey&&typeof beginMarqueeGesture==='function'){beginMarqueeGesture(e);return}
  const wantsMiddle=e.button===1;
  const wantsSpace=e.button===0&&spacePanHeld;
  const wantsBackground=e.button===0&&e.target===workspace;
  if(!wantsMiddle&&!wantsSpace&&!wantsBackground)return;
  if(!wantsBackground && isEditableTarget(e.target))return;

  e.preventDefault();
  e.stopImmediatePropagation();

  cancelWireDrag();
  if(paletteDrag)cleanupPaletteGesture({status:null});

  const rect=workspace.getBoundingClientRect();
  panDrag={
    pointerId:e.pointerId,
    startClient:{x:e.clientX,y:e.clientY},
    startCamera:{...camera},
    unitsX:camera.w/Math.max(1,rect.width),
    unitsY:camera.h/Math.max(1,rect.height),
    blankTapClear:wantsBackground,
    moved:false
  };
  document.querySelector('.workspace-wrap')?.classList.add('panning');
  setSelectionBarSuppressed(true);
  statusEl.textContent='Pan armed';
}
function movePanGesture(e){
  if(!panDrag||e.pointerId!==panDrag.pointerId)return;
  e.preventDefault();
  const dx=e.clientX-panDrag.startClient.x;
  const dy=e.clientY-panDrag.startClient.y;
  if(Math.hypot(dx,dy)>=BG_PAN_THRESHOLD)panDrag.moved=true;
  camera={
    ...panDrag.startCamera,
    x:panDrag.startCamera.x-dx*panDrag.unitsX,
    y:panDrag.startCamera.y-dy*panDrag.unitsY
  };
  applyCamera();
}
function finishPanGesture(e=null){
  if(!panDrag)return;
  if(e&&e.pointerId!==panDrag.pointerId)return;
  const shouldClear=panDrag.blankTapClear && !panDrag.moved;
  panDrag=null;
  document.querySelector('.workspace-wrap')?.classList.remove('panning');
  statusEl.textContent='Ready';
  if(shouldClear){selected=null;selectNode(null)}
  restoreSelectionBarAfterGesture();
}

function clampZoom(z){
  return Math.max(MIN_ZOOM,Math.min(MAX_ZOOM,z));
}
function zoomAt(factor,clientX=null,clientY=null){
  const oldZoom=currentZoom();
  const newZoom=clampZoom(oldZoom*factor);
  if(Math.abs(newZoom-oldZoom)<.0001)return;

  const anchor = (clientX==null || clientY==null)
    ? {x:camera.x+camera.w/2,y:camera.y+camera.h/2}
    : svgPoint(clientX,clientY);

  const newW=BASE_VIEW.w/newZoom;
  const newH=BASE_VIEW.h/newZoom;
  const rx=(anchor.x-camera.x)/camera.w;
  const ry=(anchor.y-camera.y)/camera.h;

  camera={
    x:anchor.x-rx*newW,
    y:anchor.y-ry*newH,
    w:newW,
    h:newH
  };
  applyCamera();
}
function resetZoom(){
  camera={...BASE_VIEW};
  applyCamera();
}
function activeCanvasNodeIds(canvasId=selectedCanvasContextId()){
  if(canvasId===GLOBAL_CANVAS_ID)return new Set(nodes.filter(n=>(n.canvasId||GLOBAL_CANVAS_ID)===GLOBAL_CANVAS_ID).map(n=>n.id));
  const d=canvasDescriptorById(canvasId);if(!d)return new Set();
  if(d.ownerKind==='component')return new Set(nodes.filter(n=>(n.canvasId||GLOBAL_CANVAS_ID)===canvasId).map(n=>n.id));
  if(d.ownerKind==='wire'){const w=wires.find(w=>w.id===d.ownerId);return new Set(w?[w.a,w.b].filter(Boolean):[])}
  return new Set();
}
function activeCanvasWireSet(canvasId=selectedCanvasContextId()){
  if(canvasId===GLOBAL_CANVAS_ID)return new Set(wires.filter(w=>(w.canvasId||GLOBAL_CANVAS_ID)===GLOBAL_CANVAS_ID).map(w=>w.id));
  const d=canvasDescriptorById(canvasId);if(!d)return new Set();
  if(d.ownerKind==='wire')return new Set([d.ownerId]);
  return new Set(wires.filter(w=>(w.canvasId||GLOBAL_CANVAS_ID)===canvasId).map(w=>w.id));
}
function nodeVisibleInActiveCanvas(){return true}
function wireVisibleInActiveCanvas(){return true}
function diagramBounds(canvasId=selectedCanvasContextId()){
  const nodeIds=activeCanvasNodeIds(canvasId),scopedNodes=nodes.filter(n=>nodeIds.has(n.id));
  const d=canvasDescriptorById(canvasId);
  if(d?.ownerKind==='component'){
    const owner=nodes.find(n=>n.id===d.ownerId);if(owner&&!scopedNodes.includes(owner))scopedNodes.unshift(owner);
  }
  if(!scopedNodes.length&&canvasId===GLOBAL_CANVAS_ID)return null;
  let l=Infinity,r=-Infinity,t=Infinity,b=-Infinity;
  for(const n of scopedNodes){const size=componentSize(n);l=Math.min(l,n.x-size.w/2);r=Math.max(r,n.x+size.w/2);t=Math.min(t,n.y-size.h/2);b=Math.max(b,n.y+size.h/2)}
  const wireIds=activeCanvasWireSet(canvasId),occupied=[];
  wires.forEach((w,i)=>{if(!wireIds.has(w.id))return;const A=carrierEndpointPos(w,'a'),B=carrierEndpointPos(w,'b');if(!A||!B)return;const points=stableRouteForWire(i,w,A,B,occupied);occupied.push(...routeSegments(points));for(const q of points){l=Math.min(l,q.x);r=Math.max(r,q.x);t=Math.min(t,q.y);b=Math.max(b,q.y)}});
  return Number.isFinite(l)?{l,r,t,b}:null;
}
function fitDiagram(){
  const b=diagramBounds();
  if(!b){resetZoom();return}
  const pad=70;
  const contentW=Math.max(160,b.r-b.l+pad*2);
  const contentH=Math.max(120,b.b-b.t+pad*2);
  const svgRect=workspace.getBoundingClientRect();
  const aspect=(svgRect.width>0&&svgRect.height>0)?svgRect.width/svgRect.height:BASE_VIEW.w/BASE_VIEW.h;
  let w=contentW,h=contentH;
  if(w/h>aspect) h=w/aspect; else w=h*aspect;
  const z=clampZoom(BASE_VIEW.w/w);
  w=BASE_VIEW.w/z; h=BASE_VIEW.h/z;
  camera={
    x:(b.l+b.r)/2-w/2,
    y:(b.t+b.b)/2-h/2,
    w,h
  };
  applyCamera();
}
function dragSnapStep(mods){
  if(!canvasSnapEnabled || mods?.altKey) return 0;
  if(mods?.ctrlKey || mods?.metaKey) return canvasGridSize*2;
  if(mods?.shiftKey) return Math.max(4,canvasGridSize/2);
  return canvasGridSize;
}
function snapCoord(v, step){
  return step>0 ? Math.round(v/step)*step : v;
}
function snapModeLabel(step){
  if(step===0) return 'free settle';
  return `settles to ${step}`;
}
function applyGridSettings(){
  document.documentElement.style.setProperty('--canvas-grid-size',`${canvasGridSize}px`);
  workspace.classList.toggle('grid-hidden',!canvasGridVisible);
  gridVisibleInput.checked=canvasGridVisible;
  gridSnapInput.checked=canvasSnapEnabled;
  gridSizeInput.value=String(canvasGridSize);
  gridBtn.classList.toggle('active',!gridSettings.hidden);
}
function setGridPanel(open){
  gridSettings.hidden=!open;
  gridBtn.setAttribute('aria-expanded',String(open));
  gridBtn.classList.toggle('active',open);
}
function modifierSnapshot(mods){
  return {
    altKey:!!mods?.altKey,
    shiftKey:!!mods?.shiftKey,
    ctrlKey:!!mods?.ctrlKey,
    metaKey:!!mods?.metaKey
  };
}
function applyNodeDragPosition(state){
  if(!state) return;
  const dx=state.pointer.x-state.startPointer.x,dy=state.pointer.y-state.startPointer.y;
  const rawX = state.origin.x + dx;
  const rawY = state.origin.y + dy;
  state.node.x = rawX;
  state.node.y = rawY;
  state.el.setAttribute('transform', `translate(${state.node.x} ${state.node.y})`);
  moveDescendantsWithState(state,dx,dy);
  for(const item of state.groupOrigins||[]){item.node.x=item.x+dx;item.node.y=item.y+dy;const el=document.querySelector(`.node[data-id="${item.node.id}"]`);if(el)el.setAttribute('transform',`translate(${item.node.x} ${item.node.y})`)}
  const step=dragSnapStep(state.modifiers);
  statusEl.textContent = `Held freely · ${snapModeLabel(step)} on release`;
}
function settleActiveComponent(mods=null){
  const node = activeNodeDragState?.node || nodes.find(n=>n.id===activeNodeDrag);
  if(!node) return;

  const effective = modifierSnapshot(mods || activeNodeDragState?.modifiers || {});
  const step = dragSnapStep(effective);
  const before={x:node.x,y:node.y};
  if(step>0){
    node.x=snapCoord(node.x,step);
    node.y=snapCoord(node.y,step);
  }
  const settleDx=node.x-before.x,settleDy=node.y-before.y;
  if((settleDx||settleDy)&&activeNodeDragState){
    for(const item of [...(activeNodeDragState.descendantOrigins||[]),...(activeNodeDragState.groupOrigins||[])]){item.node.x+=settleDx;item.node.y+=settleDy;const cel=document.querySelector(`.node[data-id=\"${item.node.id}\"]`);if(cel)cel.setAttribute('transform',`translate(${item.node.x} ${item.node.y})`)}
  }

  const el=document.querySelector(`.node[data-id="${node.id}"]`);
  if(el) el.setAttribute('transform',`translate(${node.x} ${node.y})`);

  // If a pointer drag remains active after an idle settle, rebase the drag
  // around the snapped position so resuming movement is continuous.
  if(activeNodeDragState){
    activeNodeDragState.origin={x:node.x,y:node.y};
    activeNodeDragState.descendantOrigins=(activeNodeDragState.descendantOrigins||[]).map(item=>({node:item.node,x:item.node.x,y:item.node.y}));
    activeNodeDragState.groupOrigins=(activeNodeDragState.groupOrigins||[]).map(item=>({node:item.node,x:item.node.x,y:item.node.y}));
    activeNodeDragState.startPointer={
      x:activeNodeDragState.pointer.x,
      y:activeNodeDragState.pointer.y
    };
  }
}
function refreshActiveNodeDragFromModifiers(mods){
  if(!activeNodeDragState) return;
  activeNodeDragState.modifiers=modifierSnapshot(mods);
  if(settleTimer){clearTimeout(settleTimer);settleTimer=null}
  statusEl.textContent=`Held freely · ${snapModeLabel(dragSnapStep(activeNodeDragState.modifiers))} on release`;
  scheduleDragSettle(activeNodeDragState.modifiers);
}
function isEditableTarget(target){
  return !!target?.closest?.('input,textarea,select,[contenteditable="true"]');
}
function setCanvasKeyboardActive(active=true){
  canvasKeyboardActive=!!active;
  document.querySelector('.workspace-wrap')?.classList.toggle('keyboard-active',canvasKeyboardActive);
}
function activateCanvasKeyboard(){
  setCanvasKeyboardActive(true);
  try{workspace.focus({preventScroll:true})}catch(_){workspace.focus()}
}
function shortcutCode(e){
  return e.code || e.key;
}
function isZoomInKey(e){
  const code=shortcutCode(e);
  return code==='NumpadAdd' || code==='Equal' || e.key==='+';
}
function isZoomOutKey(e){
  const code=shortcutCode(e);
  return code==='NumpadSubtract' || code==='Minus' || e.key==='-';
}
function keyboardMoveStep(e){
  if(e.altKey || !canvasSnapEnabled) return 1;
  if(e.ctrlKey || e.metaKey) return canvasGridSize*2;
  if(e.shiftKey) return Math.max(1,canvasGridSize/2);
  return canvasGridSize;
}
function beginKeyboardMove(node){
  if(!node) return;
  if(keyboardMoveNodeId===node.id) return;

  if(keyboardMoveNodeId) finishKeyboardMove({});
  keyboardMoveNodeId=node.id;
  activeNodeDrag=node.id;
  captureDragSnapshots(node.id);
  workspace.classList.add('dragging-node');
}
function moveSelectedByArrow(e){
  if(typeof selected!=='string' || selected.startsWith('wire:')) return false;
  const node=nodes.find(n=>n.id===selected);
  if(!node) return false;
  if(isEntityLocked(node)||isEntityPinned(node)){statusEl.textContent=isEntityLocked(node)?'Locked · move refused':'Pinned · move refused';return true}

  beginKeyboardMove(node);

  const step=keyboardMoveStep(e);let dx=0,dy=0;
  if(e.key==='ArrowLeft'){node.x-=step;dx=-step}
  if(e.key==='ArrowRight'){node.x+=step;dx=step}
  if(e.key==='ArrowUp'){node.y-=step;dy=-step}
  if(e.key==='ArrowDown'){node.y+=step;dy=step}
  for(const child of descendantsOf(node.id)){child.x+=dx;child.y+=dy;const cel=document.querySelector(`.node[data-id="${child.id}"]`);if(cel)cel.setAttribute('transform',`translate(${child.x} ${child.y})`)}

  const el=document.querySelector(`.node[data-id="${node.id}"]`);
  if(el) el.setAttribute('transform',`translate(${node.x} ${node.y})`);

  statusEl.textContent=`Keyboard move · ${step}px`;
  renderWires();
  positionSelectionBar();

  if(keyboardSettleTimer) clearTimeout(keyboardSettleTimer);
  keyboardSettleTimer=setTimeout(()=>finishKeyboardMove(e),ROUTE_SETTLE_DELAY);
  return true;
}
function finishKeyboardMove(mods){
  if(!keyboardMoveNodeId) return;
  if(keyboardSettleTimer){clearTimeout(keyboardSettleTimer);keyboardSettleTimer=null}

  // Arrow-key steps are intentionally aligned to the selected grid unless Alt
  // was used. Settling still applies the same rule for consistency.
  settleActiveComponent(mods);
  const movedNode=nodes.find(n=>n.id===keyboardMoveNodeId);if(movedNode)updateContainmentFor(movedNode);
  settleDraggedRoutes();

  keyboardMoveNodeId=null;
  activeNodeDrag=null;
  dragRouteSnapshots.clear();
  workspace.classList.remove('dragging-node');
  statusEl.textContent='Select';
  renderWires();
  positionSelectionBar();
}


const POINT_EXTENT=24; // a 0D form occupies a fixed small footprint; presentation.size does not apply to it
function componentSize(n){
  const p=componentConfig(n).presentation;
  if(componentForm(n).dimension===0)return {w:POINT_EXTENT,h:POINT_EXTENT};
  return {w:p.size.w,h:p.size.h};
}
function componentBounds(n,pad=0){
  const {w,h}=componentSize(n);
  return {l:n.x-w/2-pad,r:n.x+w/2+pad,t:n.y-h/2-pad,b:n.y+h/2+pad};
}
function pointInsideComponent(x,y,n,pad=0){
  const R=componentBounds(n,pad);
  return x>R.l&&x<R.r&&y>R.t&&y<R.b;
}
function componentAcceptsChildren(n){return formHostsChildren(n)}
function parentComponent(node){const ownerId=canvasOwnerComponentId(node?.canvasId||GLOBAL_CANVAS_ID);return ownerId?nodes.find(n=>n.id===ownerId)||null:null}
function componentDisplayName(node){
  if(!node)return '—';
  return componentConfig(node).label||byId(node.symbolId).name||node.id;
}
function componentScopePath(node){
  if(!node)return 'world';const host=componentHostDescriptor(node);
  if(host?.ownerKind==='wire')return `world / Wire ${host.label||host.ownerId} / ${componentDisplayName(node)}`;
  const path=[];let cur=node,seen=new Set();while(cur&&!seen.has(cur.id)){seen.add(cur.id);path.unshift(componentDisplayName(cur));cur=parentComponent(cur)}return ['world',...path].join(' / ');
}
function syncNodeBoundaryContext(node){
  if(!node)return;
  ensureComponentStructure(node);
  if(!node.canvasId)node.canvasId=node.parentId?localCanvasId('component',node.parentId):GLOBAL_CANVAS_ID;
  const parent=parentComponent(node),host=canvasDescriptorById(node.canvasId||GLOBAL_CANVAS_ID);
  node.parentId=parent?.id||null;node.boundary.inside.type=node.symbolId==='blank'?null:node.symbolId;node.type=node.boundary.inside.type;
  node.boundary.outside.type=parent?(parent.boundary.inside.type||parent.symbolId||'component'):host?.ownerKind==='wire'?'wire':'world';componentPlacement(node);
}
function syncAllNodeBoundaryContext(){
  const ordered=[...nodes].sort((a,b)=>nodeDepth(a)-nodeDepth(b));ordered.forEach(syncNodeBoundaryContext);ordered.forEach(syncComponentAttachedPose);
}
function setActiveCanvas(){
  // Compatibility no-op: Canvas is inferred from selection/spatial containment, not entered as a mode.
  refreshCanvasScopeControl();
}
function clearActiveCanvas(){
  const canvasId=selectedCanvasContextId(),d=canvasDescriptorById(canvasId)||canvasDescriptorById(GLOBAL_CANVAS_ID);
  if(d.scope==='global'){
    nodes.splice(0,nodes.length);wires.splice(0,wires.length);diagram.references.splice(0,diagram.references.length);
  }else if(d.ownerKind==='component'){
    const removeIds=new Set(nodes.filter(n=>(n.canvasId||GLOBAL_CANVAS_ID)===canvasId).map(n=>n.id));
    for(let i=wires.length-1;i>=0;i--)if((wires[i].canvasId||GLOBAL_CANVAS_ID)===canvasId||removeIds.has(wires[i].a)||removeIds.has(wires[i].b))wires.splice(i,1);
    for(let i=nodes.length-1;i>=0;i--)if(removeIds.has(nodes[i].id))nodes.splice(i,1);
  }else if(d.ownerKind==='wire'){
    const hostedIds=nodes.filter(n=>(n.canvasId||GLOBAL_CANVAS_ID)===d.id).map(n=>n.id);
    for(const id of hostedIds)SovSchematicData.remove(diagram,'component',id);
    const w=wires.find(w=>w.id===d.ownerId);if(w&&Array.isArray(w.attachments))w.attachments.splice(0,w.attachments.length);
  }
  routeCache.clear();arrowPoseCache.clear();dragRouteSnapshots.clear();selected=null;hideSelectionBar();refreshCanvasScopeControl();render();selectNode(null);
}
function nodeDepth(n){
  let depth=0,cur=n,seen=new Set();
  while(cur){const parent=parentComponent(cur);if(!parent||seen.has(parent.id))break;seen.add(parent.id);cur=parent;depth++}

  return depth;
}
function descendantsOf(parentId){
  const out=[];const queue=[parentId];
  while(queue.length){
    const id=queue.shift();
    nodes.filter(n=>n.parentId===id).forEach(child=>{out.push(child);queue.push(child.id)});
  }
  return out;
}
function isDescendantOf(nodeId,parentId){
  let cur=nodes.find(n=>n.id===nodeId),seen=new Set();
  while(cur){const parent=parentComponent(cur);if(!parent||seen.has(parent.id))break;if(parent.id===parentId)return true;seen.add(parent.id);cur=parent}

  return false;
}
const INLINE_TERMINAL_Y={act:32,hold:32,buffer:32,gate:32,switch:38,limit:32,observe:42,receipt:24};
function componentInlineTerminalY(node){return INLINE_TERMINAL_Y[node?.symbolId]??null}
function componentInlineGraphicBox(node){
  const p=componentConfig(node).presentation,size=p.size;
  const w=Math.min(size.w*.72,108),h=Math.min(size.h*.55,70),x=-w/2;
  if(componentHostedOnWire(node)){
    const axis=componentInlineTerminalY(node);
    return {x,y:axis==null?-h/2:-(axis/64)*h,w,h};
  }
  let y=-Math.min(size.h*.34,38),hh=h;
  if(componentAcceptsChildren(node)){y=-size.h/2+18;hh=Math.min(52,size.h*.32)}
  return {x,y,w,h:hh};
}
function componentInlineTerminalHalfSpan(node){
  const axis=componentInlineTerminalY(node);if(axis==null)return 0;
  const box=componentInlineGraphicBox(node);
  return box.w*(.5-8/96);
}
function componentHostAngle(node){return Number(wireHostPoseCache.get(node?.id)?.angle)||0}
function rotateVectorByDegrees(x,y,angle){const r=angle*Math.PI/180,c=Math.cos(r),s=Math.sin(r);return{x:x*c-y*s,y:x*s+y*c}}
function componentPortLocalPosition(n,pointId){
  const size=componentSize(n),spec=Attachment.resolveSpec(n,pointId);if(!spec)return{x:0,y:0};
  const cfg=componentConfig(n),pcfg=cfg.ports[spec.compatId],effective=Attachment.effectiveDimension(n);
  if(effective===0)return{x:0,y:0};
  if(effective===1){
    const half=componentHostedOnWire(n)?Math.max(18,componentInlineTerminalHalfSpan(n)):size.w/2;
    return spec.id==='start'?{x:-half,y:0}:{x:half,y:0};
  }
  const face=pcfg?.face||'external',faceOffset=face==='internal'?-4:face==='both'?0:4,t=Math.max(0,Math.min(1,Number.isFinite(Number(spec.t))?Number(spec.t):.5));
  const alongX=-size.w/2+size.w*t,alongY=-size.h/2+size.h*t;
  if(spec.side==='left')return{x:-size.w/2-faceOffset,y:alongY};
  if(spec.side==='right')return{x:size.w/2+faceOffset,y:alongY};
  if(spec.side==='top')return{x:alongX,y:-size.h/2-faceOffset};
  if(spec.side==='bottom')return{x:alongX,y:size.h/2+faceOffset};
  return{x:0,y:0};
}
function renderedWirePath(w){return workspace.querySelector(`.wire-group[data-wire-id="${w.id}"] .wire`)}
function pathTangentAngleAtLength(path,length){
  if(!path?.getTotalLength)return 0;const L=path.getTotalLength(),eps=Math.max(.35,Math.min(2,L/500));
  const here=path.getPointAtLength(Math.max(0,Math.min(L,length)));
  const next=path.getPointAtLength(Math.min(L,length+eps));
  const prev=path.getPointAtLength(Math.max(0,length-eps));
  let dx=next.x-here.x,dy=next.y-here.y;
  if(Math.hypot(dx,dy)<.05){dx=here.x-prev.x;dy=here.y-prev.y}
  let angle=Math.atan2(dy,dx)*180/Math.PI;
  // A hosted Component inherits the Wire's axis, not its flow direction.
  // Canonicalizing to [-90,90] keeps labels/glyphs upright on reverse segments.
  while(angle>90)angle-=180;while(angle<-90)angle+=180;
  return angle;
}
function nearestPointOnSvgPath(path,x,y){
  if(!path?.getTotalLength)return null;const L=path.getTotalLength();if(!Number.isFinite(L)||L<=0)return null;
  let best={distance:Infinity,length:0,x:0,y:0};const samples=Math.max(18,Math.min(96,Math.ceil(L/18)));
  for(let i=0;i<=samples;i++){const len=L*i/samples,q=path.getPointAtLength(len),d=Math.hypot(q.x-x,q.y-y);if(d<best.distance)best={distance:d,length:len,x:q.x,y:q.y}}
  let step=L/samples;for(let pass=0;pass<5;pass++){const start=Math.max(0,best.length-step),end=Math.min(L,best.length+step);for(let i=0;i<=8;i++){const len=start+(end-start)*i/8,q=path.getPointAtLength(len),d=Math.hypot(q.x-x,q.y-y);if(d<best.distance)best={distance:d,length:len,x:q.x,y:q.y}}step/=3}
  return {...best,t:Math.max(.02,Math.min(.98,best.length/L)),pathLength:L,angle:pathTangentAngleAtLength(path,best.length)};
}
function nearestPointOnComponentPath(host,x,y){
  if(!host||!componentIsPath(host))return null;const half=Math.max(24,componentSize(host).w/2),angle=componentHostAngle(host),r=-angle*Math.PI/180,dx=x-host.x,dy=y-host.y;
  const lx=dx*Math.cos(r)-dy*Math.sin(r),ly=dx*Math.sin(r)+dy*Math.cos(r),clamped=Math.max(-half,Math.min(half,lx)),t=(clamped+half)/(half*2),world=rotateVectorByDegrees(clamped,0,angle);
  return {x:host.x+world.x,y:host.y+world.y,t,distance:Math.hypot(lx-clamped,ly),angle};
}
function nearestPointOnComponentEdge(host,x,y){
  if(!host||!componentIsSurface(host))return null;const {w,h}=componentSize(host),angle=componentHostAngle(host),r=-angle*Math.PI/180,dx=x-host.x,dy=y-host.y;
  const lx=dx*Math.cos(r)-dy*Math.sin(r),ly=dx*Math.sin(r)+dy*Math.cos(r),hw=w/2,hh=h/2;
  const candidates=[{side:'top',x:Math.max(-hw,Math.min(hw,lx)),y:-hh,angle:0,t:(Math.max(-hw,Math.min(hw,lx))+hw)/w},{side:'bottom',x:Math.max(-hw,Math.min(hw,lx)),y:hh,angle:0,t:(Math.max(-hw,Math.min(hw,lx))+hw)/w},{side:'left',x:-hw,y:Math.max(-hh,Math.min(hh,ly)),angle:90,t:(Math.max(-hh,Math.min(hh,ly))+hh)/h},{side:'right',x:hw,y:Math.max(-hh,Math.min(hh,ly)),angle:90,t:(Math.max(-hh,Math.min(hh,ly))+hh)/h}];
  let best=null;for(const c of candidates){const d=Math.hypot(lx-c.x,ly-c.y);if(!best||d<best.distance)best={...c,distance:d}}const world=rotateVectorByDegrees(best.x,best.y,angle);return {...best,x:host.x+world.x,y:host.y+world.y,angle:angle+best.angle};
}
function syncComponentAttachedPose(node){
  const placement=componentPlacement(node);if(!['path','edge'].includes(placement.kind))return;const host=nodes.find(n=>n.id===placement.hostId)||parentComponent(node);if(!host)return;let q=null;
  if(placement.kind==='path'){const half=Math.max(24,componentSize(host).w/2),local=-half+half*2*placement.t,world=rotateVectorByDegrees(local,0,componentHostAngle(host));q={x:host.x+world.x,y:host.y+world.y,angle:componentHostAngle(host)}}
  else{const {w,h}=componentSize(host),side=placement.side||'top',u=Math.max(0,Math.min(1,placement.t));let lx=0,ly=0,a=0;if(side==='top'||side==='bottom'){lx=-w/2+w*u;ly=side==='top'?-h/2:h/2}else{lx=side==='left'?-w/2:w/2;ly=-h/2+h*u;a=90}const world=rotateVectorByDegrees(lx,ly,componentHostAngle(host));q={x:host.x+world.x,y:host.y+world.y,angle:componentHostAngle(host)+a}}
  node.x=q.x;node.y=q.y;wireHostPoseCache.set(node.id,{...q,hostId:host.id,t:placement.t});
}
function componentHostCandidateAtPoint(node,x=node.x,y=node.y){
  if(!node)return null;const dim=componentForm(node).dimension,ownedIds=new Set([node.id,...descendantsOf(node.id).map(n=>n.id)]);let best=null;const consider=c=>{if(c&&(!best||c.placement.distance<best.placement.distance))best=c};
  const interiorHost=()=>{
    const candidates=nodes.filter(candidate=>candidate.id!==node.id&&componentAcceptsChildren(candidate)&&!isEntityLocked(candidate)&&!isDescendantOf(candidate.id,node.id)&&pointInsideComponent(x,y,candidate,-componentConfig(candidate).presentation.padding)).sort((a,b)=>{const A=componentSize(a),B=componentSize(b);return A.w*A.h-B.w*B.h});
    return candidates[0]?{kind:'component',entity:candidates[0],canvasId:componentCanvas(candidates[0]).id,placement:{distance:0}}:null;
  };
  if(dim===0){
    // A Point sticks to the nearest 1D carrier or 2D boundary within reach; otherwise it
    // settles into an open interior like any other Component.
    for(const w of wires){if(entityEditorState(w).hidden||ownedIds.has(w.a)||ownedIds.has(w.b))continue;const q=nearestPointOnSvgPath(renderedWirePath(w),x,y);if(q&&q.distance<=24)consider({kind:'wire',entity:w,canvasId:wireCanvas(w).id,placement:q})}
    for(const host of nodes){if(host.id===node.id||ownedIds.has(host.id)||isEntityLocked(host)||isEffectivelyHidden(host))continue;if(componentIsPath(host)){const q=nearestPointOnComponentPath(host,x,y);if(q&&q.distance<=24)consider({kind:'path',entity:host,canvasId:componentCanvas(host).id,placement:q})}else if(componentIsSurface(host)){const q=nearestPointOnComponentEdge(host,x,y);if(q&&q.distance<=20)consider({kind:'edge',entity:host,canvasId:componentCanvas(host).id,placement:q})}}
    return best||interiorHost();
  }
  const interior=interiorHost();if(interior)return interior;
  for(const w of wires){if(entityEditorState(w).hidden||ownedIds.has(w.a)||ownedIds.has(w.b))continue;const q=nearestPointOnSvgPath(renderedWirePath(w),x,y);if(q&&q.distance<=24)consider({kind:'wire',entity:w,canvasId:wireCanvas(w).id,placement:q})}
  return best;
}
function applyComponentHost(node,candidate){
  if(!node)return null;
  if(candidate?.kind==='component'){
    node.canvasId=candidate.canvasId;node.parentId=candidate.entity.id;node.placement={kind:'surface',x:node.x,y:node.y};wireHostPoseCache.delete(node.id)
  }else if(candidate?.kind==='wire'){
    node.canvasId=candidate.canvasId;node.parentId=null;node.placement={kind:'wire',wireId:candidate.entity.id,t:candidate.placement.t};node.x=candidate.placement.x;node.y=candidate.placement.y;
    wireHostPoseCache.set(node.id,{x:node.x,y:node.y,angle:Number(candidate.placement.angle)||0,wireId:candidate.entity.id,t:node.placement.t})
  }else if(candidate?.kind==='path'){
    node.canvasId=candidate.canvasId;node.parentId=candidate.entity.id;node.placement={kind:'path',hostId:candidate.entity.id,t:candidate.placement.t};node.x=candidate.placement.x;node.y=candidate.placement.y;wireHostPoseCache.set(node.id,{x:node.x,y:node.y,angle:Number(candidate.placement.angle)||0,hostId:candidate.entity.id,t:node.placement.t})
  }else if(candidate?.kind==='edge'){
    node.canvasId=candidate.canvasId;node.parentId=candidate.entity.id;node.placement={kind:'edge',hostId:candidate.entity.id,side:candidate.placement.side,t:candidate.placement.t};node.x=candidate.placement.x;node.y=candidate.placement.y;wireHostPoseCache.set(node.id,{x:node.x,y:node.y,angle:Number(candidate.placement.angle)||0,hostId:candidate.entity.id,t:node.placement.t,side:node.placement.side})
  }else{
    node.canvasId=GLOBAL_CANVAS_ID;node.parentId=null;node.placement={kind:'surface',x:node.x,y:node.y};wireHostPoseCache.delete(node.id)
  }
  syncNodeBoundaryContext(node);for(const child of descendantsOf(node.id))syncNodeBoundaryContext(child);return candidate;
}
function updateContainmentFor(node){if(!node)return null;return applyComponentHost(node,componentHostCandidateAtPoint(node))}
function moveDescendantsWithState(state,dx,dy){
  for(const item of state.descendantOrigins||[]){
    item.node.x=item.x+dx;item.node.y=item.y+dy;
    const el=document.querySelector(`.node[data-id="${item.node.id}"]`);
    if(el)el.setAttribute('transform',`translate(${item.node.x} ${item.node.y})`);
  }
}
function portLayout(n){
  const result={},angle=componentHostAngle(n);
  for(const id of componentPortIds(n)){
    const local=componentPortLocalPosition(n,id),rot=componentHostedOnWire(n)?rotateVectorByDegrees(local.x,local.y,angle):local;
    result[id]={x:n.x+rot.x,y:n.y+rot.y};
  }
  return result;
}
function portPos(n,pointId){const spec=Attachment.resolveSpec(n,pointId);return portLayout(n)[spec?.id||pointId]||{x:n.x,y:n.y}}
function physicalPortSide(n,pointId){return Attachment.resolveSpec(n,pointId)?.side||'right'}
function portNormal(side){
  if(side==='left')return{x:-1,y:0};if(side==='top')return{x:0,y:-1};if(side==='bottom')return{x:0,y:1};return{x:1,y:0};
}
// `inward` says which side of a boundary the carrier is on (true: the interior), for a
// boundary-hosted Point and for a 2D form's own boundary point alike. Without it the
// point's face decides.
function stubPos(P,portId,d=26,node=null,inward=null){
  let side,face='external';
  if(node){side=physicalPortSide(node,portId);face=componentAttachmentPoint(node,portId)?.config?.face||'external'}else side=portId==='in'?'left':portId==='control'?'top':'right';
  const placement=node?componentPlacement(node):null;
  if(placement?.kind==='edge'){
    // A Point stuck to a boundary leaves along that boundary's normal, into whichever surface carries the Wire.
    const host=nodes.find(h=>h.id===placement.hostId);
    const normal=rotateVectorByDegrees(portNormal(placement.side).x,portNormal(placement.side).y,host?componentHostAngle(host):0);
    const sign=(inward==null?face==='internal':inward)?-1:1;return{x:P.x+normal.x*d*sign,y:P.y+normal.y*d*sign};
  }
  let normal=portNormal(side);if(node&&componentHostedOnWire(node))normal=rotateVectorByDegrees(normal.x,normal.y,componentHostAngle(node));
  const sign=(inward==null?face==='internal':inward)?-1:1;return{x:P.x+normal.x*d*sign,y:P.y+normal.y*d*sign};
}
// True when a Wire runs on the interior surface behind the boundary its endpoint sits on: the
// host of a boundary-hosted Point, or the 2D form itself for one of its own boundary points
// (built-in or data-declared). Null when the endpoint has no boundary of its own.
function wireEndpointInward(w,node){
  if(!w||!node)return null;const surface=w.canvasId||GLOBAL_CANVAS_ID;const placement=componentPlacement(node);
  if(placement.kind==='edge'){const host=nodes.find(h=>h.id===placement.hostId);return !!host&&surface===componentCanvas(host).id}
  if(componentForm(node).dimension===2)return surface===componentCanvas(node).id;
  return null;
}
