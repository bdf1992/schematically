'use strict';
// 0.1 Beta concern: Component drag, Port wiring, and connection gesture lifecycles.

let dragVisualFrame=0;
function scheduleDragVisualRefresh(){
  if(dragVisualFrame)return;
  dragVisualFrame=requestAnimationFrame(()=>{
    dragVisualFrame=0;
    renderWires();
  });
}
function flushDragVisualRefresh(){
  if(dragVisualFrame){cancelAnimationFrame(dragVisualFrame);dragVisualFrame=0}
  renderWires();
}

let componentTransformGesture=null;
let componentTransformFrame=0;
function transformMinimumSize(node){
  let minW=80,minH=64;
  const p=componentConfig(node).presentation;
  for(const child of descendantsOf(node.id)){
    // Points stuck to the boundary ride the edge; they do not constrain the interior.
    if(['edge','path'].includes(componentPlacement(child).kind))continue;
    const size=componentSize(child);
    minW=Math.max(minW,2*(Math.abs(child.x-node.x)+size.w/2+p.padding));
    minH=Math.max(minH,2*(Math.abs(child.y-node.y)+size.h/2+p.padding));
  }
  return {w:Math.min(520,minW),h:Math.min(420,minH)};
}
function scheduleComponentTransformProjection(){
  if(componentTransformFrame)return;
  componentTransformFrame=requestAnimationFrame(()=>{
    componentTransformFrame=0;
    routeCache.clear();arrowPoseCache.clear();render();setSelectionBarSuppressed(true);
  });
}
function beginComponentTransform(e,n,kind){
  e.preventDefault();e.stopPropagation();
  if(isEntityLocked(n)||isEntityPinned(n)){statusEl.textContent=isEntityLocked(n)?'Locked · resize refused':'Pinned · resize refused';return}
  setHistoryHint('Resize Component');
  if(activeNodeDragState)finishActiveNodeDrag(null,{force:true,reason:'transform handoff'});
  cancelWireDrag();
  if(keyboardMoveNodeId)finishKeyboardMove({});
  const p=componentConfig(n).presentation;
  const start=svgPoint(e.clientX,e.clientY);
  componentTransformGesture={node:n,kind,pointerId:e.pointerId,start,startSize:{w:p.size.w,h:p.size.h},ratio:p.size.w/Math.max(1,p.size.h)};
  selectNode(n.id,{focus:false});
  setSelectionBarSuppressed(true);
  workspace.classList.add('transforming-node');
  statusEl.textContent=kind==='x'?'Resize width':kind==='y'?'Resize height':'Resize';
}
function updateComponentTransform(e){
  const t=componentTransformGesture;if(!t||e.pointerId!==t.pointerId)return;
  e.preventDefault();
  const q=svgPoint(e.clientX,e.clientY),dx=q.x-t.start.x,dy=q.y-t.start.y;
  const p=componentConfig(t.node).presentation,min=transformMinimumSize(t.node);
  let w=t.startSize.w,h=t.startSize.h;
  if(t.kind==='x'||t.kind==='xy')w=Math.max(min.w,Math.min(520,t.startSize.w+dx*2));
  if(t.kind==='y'||t.kind==='xy')h=Math.max(min.h,Math.min(420,t.startSize.h+dy*2));
  if(t.kind==='xy'&&e.shiftKey){
    const byW=w/t.ratio,byH=h*t.ratio;
    if(Math.abs(dx)>=Math.abs(dy))h=Math.max(min.h,Math.min(420,byW));
    else w=Math.max(min.w,Math.min(520,byH));
  }
  p.size.w=w;p.size.h=h;
  scheduleComponentTransformProjection();
}
function finishComponentTransform(e){
  const t=componentTransformGesture;if(!t||(e&&e.pointerId!=null&&e.pointerId!==t.pointerId))return;
  const p=componentConfig(t.node).presentation;
  p.size.w=Math.max(transformMinimumSize(t.node).w,Math.round(p.size.w/8)*8);
  p.size.h=Math.max(transformMinimumSize(t.node).h,Math.round(p.size.h/8)*8);
  componentTransformGesture=null;
  if(componentTransformFrame){cancelAnimationFrame(componentTransformFrame);componentTransformFrame=0}
  workspace.classList.remove('transforming-node');
  routeCache.clear();arrowPoseCache.clear();render();selectNode(t.node.id,{focus:false});restoreSelectionBarAfterGesture();
  statusEl.textContent='Select';scheduleHistoryCapture();
}
window.addEventListener('pointermove',updateComponentTransform,true);
window.addEventListener('pointerup',finishComponentTransform,true);
window.addEventListener('pointercancel',finishComponentTransform,true);

const HOST_ADOPT_DWELL=280;
function hostCandidateKey(candidate){return candidate?`${candidate.kind}:${candidate.entity?.id||''}`:''}
function clearHostCandidateArm(state,{keepGhost=false}={}){
  if(!state)return;if(state.hostDwellTimer){clearTimeout(state.hostDwellTimer);state.hostDwellTimer=null}
  state.hostCandidate=null;state.hostCandidateKey='';state.hostReady=false;if(!keepGhost)clearSettleHostGhost();
}
function armHostCandidate(state,candidate){
  if(!state)return;const key=hostCandidateKey(candidate);
  if(key===state.hostCandidateKey){if(state.hostReady&&candidate)showSettleHostGhost(candidate,state.node);return}
  if(state.hostDwellTimer){clearTimeout(state.hostDwellTimer);state.hostDwellTimer=null}
  state.hostCandidate=candidate||null;state.hostCandidateKey=key;state.hostReady=false;clearSettleHostGhost();
  if(!candidate)return;
  if(candidate.canvasId===state.originCanvasId){state.hostReady=true;showSettleHostGhost(candidate,state.node);return}
  state.hostDwellTimer=setTimeout(()=>{
    state.hostDwellTimer=null;if(activeNodeDragState!==state||state.hostCandidateKey!==key)return;
    state.hostReady=true;showSettleHostGhost(state.hostCandidate,state.node);statusEl.textContent='Release → settle';
  },HOST_ADOPT_DWELL);
}
function clearNodeDragVisualState(){
  document.querySelectorAll('.node.scope-drop-target,.wire-group.scope-drop-target').forEach(el=>el.classList.remove('scope-drop-target'));
  workspace.classList.remove('dragging-node');document.querySelectorAll('.node.dragging').forEach(el=>el.classList.remove('dragging'));
}
function beginActiveNodeDrag(e,g,n){
  e.preventDefault();e.stopPropagation();
  if(isEntityLocked(n)||isEntityPinned(n)){statusEl.textContent=isEntityLocked(n)?'Locked · move refused':'Pinned · move refused';selectNode(n.id,{focus:false});return}
  if(!selectedComponentIds.has(n.id)){selectNode(n.id,{focus:false})}
  setHistoryHint(selectedComponentIds.size>1?'Move selection':'Move Component');
  if(activeNodeDragState)finishActiveNodeDrag(null,{force:true,reason:'recovered stale drag'});
  if(keyboardMoveNodeId)finishKeyboardMove({});if(settleTimer){clearTimeout(settleTimer);settleTimer=null}
  activeNodeDrag=n.id;captureDragSnapshots(n.id);workspace.classList.add('dragging-node');g.classList.add('dragging');
  selectNode(n.id,{focus:false});setSelectionBarSuppressed(true);
  const startPointer=svgPoint(e.clientX,e.clientY);
  const roots=selectedComponentIds.has(n.id)?selectedRootComponents():[n];
  const moved=new Set([n.id,...descendantsOf(n.id).map(x=>x.id)]),groupOrigins=[];
  for(const root of roots){for(const item of [root,...descendantsOf(root.id)]){if(moved.has(item.id))continue;moved.add(item.id);groupOrigins.push({node:item,x:item.x,y:item.y})}}
  activeNodeDragState={id:n.id,node:n,el:g,pointerId:e.pointerId,startPointer:{x:startPointer.x,y:startPointer.y},pointer:{x:startPointer.x,y:startPointer.y},origin:{x:n.x,y:n.y},originCanvasId:n.canvasId||GLOBAL_CANVAS_ID,descendantOrigins:descendantsOf(n.id).map(child=>({node:child,x:child.x,y:child.y})),groupOrigins,groupRootIds:roots.map(x=>x.id),modifiers:modifierSnapshot(e),startedAt:performance.now(),hostCandidate:null,hostCandidateKey:'',hostReady:false,hostDwellTimer:null};
  try{workspace.setPointerCapture(e.pointerId)}catch(_){}
  applyNodeDragPosition(activeNodeDragState);scheduleDragVisualRefresh();
}
function updateActiveNodeDrag(e){
  const state=activeNodeDragState;if(!state||e.pointerId!==state.pointerId)return;e.preventDefault();
  const p=svgPoint(e.clientX,e.clientY);state.pointer={x:p.x,y:p.y};state.modifiers=modifierSnapshot(e);applyNodeDragPosition(state);
  document.querySelectorAll('.node.scope-drop-target,.wire-group.scope-drop-target').forEach(el=>el.classList.remove('scope-drop-target'));
  const n=state.node,target=componentHostCandidateAtPoint(n,n.x,n.y);
  if(target?.kind==='component')document.querySelector(`.node[data-id="${target.entity.id}"]`)?.classList.add('scope-drop-target');
  if(target?.kind==='wire')workspace.querySelector(`.wire-group[data-wire-id="${target.entity.id}"]`)?.classList.add('scope-drop-target');
  armHostCandidate(state,target);
  if(settleTimer){clearTimeout(settleTimer);settleTimer=null}scheduleDragVisualRefresh();scheduleDragSettle(state.modifiers);
}
function finishActiveNodeDrag(e=null,{force=false,reason=''}={}){
  const state=activeNodeDragState;if(!state)return;if(!force&&e?.pointerId!=null&&e.pointerId!==state.pointerId)return;
  const pointerId=state.pointerId;let fault=null;
  try{
    if(settleTimer){clearTimeout(settleTimer);settleTimer=null}
    settleActiveComponent(e||state.modifiers);
    for(const id of state.groupRootIds||[state.node.id]){
      const root=nodes.find(n=>n.id===id);if(!root)continue;const beforeCanvas=root.canvasId||GLOBAL_CANVAS_ID;
      let candidate;
      if(root.id===state.node.id){
        candidate=state.hostReady?state.hostCandidate:null;
        if(!candidate){const current=componentHostCandidateAtPoint(root);if(current?.canvasId===state.originCanvasId)candidate=current}
        applyComponentHost(root,candidate);
      }else candidate=updateContainmentFor(root);
      const afterCanvas=root.canvasId||GLOBAL_CANVAS_ID;if(beforeCanvas!==afterCanvas)setHistoryHint(candidate?.kind==='wire'?'Settle Component on Wire':candidate?.kind==='component'?'Settle Component in Component':'Detach Component')
    }
    clearHostCandidateArm(state);settleDraggedRoutes();
  }catch(err){fault=err;console.error('Recovered Component drag failure',err)}
  finally{
    if(settleTimer){clearTimeout(settleTimer);settleTimer=null}
    clearHostCandidateArm(state);clearNodeDragVisualState();clearSettleHostGhost();
    activeNodeDragState=null;activeNodeDrag=null;dragRouteSnapshots.clear();
    try{if(workspace.hasPointerCapture?.(pointerId))workspace.releasePointerCapture(pointerId)}catch(_){}
    try{flushDragVisualRefresh()}catch(err){console.error('Drag projection recovery failed',err)}
    restoreSelectionBarAfterGesture();scheduleHistoryCapture();
  }
  statusEl.textContent=fault?'Recovered drag error · ready':reason?`Select · ${reason}`:'Select';
}
function bindNode(g,n){
  g.addEventListener('pointerdown',e=>{
    if(e.target.closest('.point-grip')){
      // 0D grip: move the Point (settle onto a Path, Plane boundary, Wire, or interior).
      if(e.shiftKey){selectNode(n.id,{focus:false,additive:true,toggle:true});if(!selectedComponentIds.has(n.id))return}
      else if(!selectedComponentIds.has(n.id))selectNode(n.id,{focus:false});
      beginActiveNodeDrag(e,g,n);return;
    }
    const port=e.target.closest('.port-hit');if(port){beginWireDrag(e,n,port.dataset.point||port.dataset.side,g);return}
    const transform=e.target.closest('.transform-handle,.transform-handle-halo');if(transform){beginComponentTransform(e,n,transform.dataset.transform);return}
    if(e.shiftKey){selectNode(n.id,{focus:false,additive:true,toggle:true});if(!selectedComponentIds.has(n.id))return}
    else if(!selectedComponentIds.has(n.id))selectNode(n.id,{focus:false});
    beginActiveNodeDrag(e,g,n);
  });
  g.addEventListener('click',e=>{if(!e.target.closest('.point-grip')&&e.target.closest('.port-hit,.transform-handle,.transform-handle-halo')){e.preventDefault();e.stopPropagation();return}e.stopPropagation();if(!e.shiftKey&&selectedComponentIds.size<=1)selectNode(n.id)});
  g.addEventListener('dblclick',e=>{if(!e.target.closest('.point-grip')&&e.target.closest('.port-hit,.transform-handle,.transform-handle-halo'))return;e.preventDefault();e.stopPropagation();focusComponent(n)});
}
window.addEventListener('pointermove',updateActiveNodeDrag,true);
window.addEventListener('pointerup',e=>finishActiveNodeDrag(e),true);
window.addEventListener('pointercancel',e=>finishActiveNodeDrag(e,{force:true,reason:'pointer cancelled'}),true);
workspace.addEventListener('lostpointercapture',()=>{if(activeNodeDragState)finishActiveNodeDrag(null,{force:true,reason:'capture recovered'})});
window.addEventListener('blur',()=>{if(activeNodeDragState)finishActiveNodeDrag(null,{force:true,reason:'focus recovered'})});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&activeNodeDragState)finishActiveNodeDrag(null,{force:true,reason:'visibility recovered'})});
workspace.addEventListener('pointerdown',e=>{if(activeNodeDragState&&activeNodeDragState.pointerId!==e.pointerId)finishActiveNodeDrag(null,{force:true,reason:'stale gesture recovered'})},true);
window.addEventListener('pointermove',e=>{if(activeNodeDragState&&e.pointerId===activeNodeDragState.pointerId&&e.pointerType==='mouse'&&e.buttons===0)finishActiveNodeDrag(null,{force:true,reason:'missed release recovered'})},true);
window.addEventListener('mouseup',()=>{if(activeNodeDragState)finishActiveNodeDrag(null,{force:true,reason:'mouseup recovered'})},true);
window.addEventListener('error',()=>{if(activeNodeDragState)finishActiveNodeDrag(null,{force:true,reason:'runtime error recovered'})});
window.addEventListener('unhandledrejection',()=>{if(activeNodeDragState)finishActiveNodeDrag(null,{force:true,reason:'runtime rejection recovered'})});

function growBlankFromConnection(sourceNode,sourcePointId,P,mods){
  const source=nodes.find(n=>n.id===sourceNode),sourceSpec=source?Attachment.resolveSpec(source,sourcePointId):null;
  if(!source||!sourceSpec){statusEl.textContent='Attachment no longer exists';return null}
  const sourceCompat=sourceSpec.compatId;

  // Release is a settle event, so the new Blank may align to the current grid.
  const blank=addNode('blank',P.x,P.y,mods,{render:false,select:false});

  // Direction is derived from the canonical attachment descriptor. Gesture code
  // must never reinterpret self/start/end/left/right/top with its own Port rules.
  let connected=false;
  if(sourceCompat==='out'){
    connected=addConnection(sourceNode,sourceSpec.id,blank.id,'left');
  }else if(sourceCompat==='in'){
    connected=addConnection(blank.id,'right',sourceNode,sourceSpec.id);
  }else{
    connected=addConnection(blank.id,'right',sourceNode,sourceSpec.id);
  }
  if(!connected){
    const i=nodes.findIndex(n=>n.id===blank.id);if(i>=0)nodes.splice(i,1);
    render();statusEl.textContent='Boundary blocks growth onto another surface';return null;
  }

  render();
  selectNode(blank.id);

  // Type is the first decision for a newly grown component.
  requestAnimationFrame(()=>{
    try{barComponentType.focus({preventScroll:true})}catch(_){barComponentType.focus()}
  });
  statusEl.textContent='Choose component type';
}

function beginWireDrag(e,n,side,g){
  e.preventDefault();
  e.stopPropagation();
  if(isEntityLocked(n)){statusEl.textContent='Locked · wiring refused';return}
  cancelWireDrag();

  const A=portPos(n,side);
  const ghost=document.createElementNS('http://www.w3.org/2000/svg','path');
  ghost.setAttribute('class','ghost-wire');
  const end=document.createElementNS('http://www.w3.org/2000/svg','circle');
  end.setAttribute('class','ghost-end');
  end.setAttribute('r','6');

  ghostLayer.appendChild(ghost);
  ghostLayer.appendChild(end);
  ghost.style.display='none';
  end.style.display='none';

  wireDrag={
    pointerId:e.pointerId,
    sourceNode:n.id,
    sourceSide:side,
    A,
    ghost,
    end,
    snap:null,
    sourceEl:g,
    startClient:{x:e.clientX,y:e.clientY},
    startTime:performance.now(),
    moved:false,
    blankDwellTimer:null,
    blankAnchor:null,
    blankReady:false,
    blankGhost:null
  };

  g.classList.add('wiring-source');
  setSelectionBarSuppressed(true);
  statusEl.textContent='Port armed · click to edit · drag to wire';
}
const WIRE_BLANK_DWELL_MS=360;
const WIRE_BLANK_DWELL_TOLERANCE=10;
function clearWireBlankCandidate(){
  if(!wireDrag)return;
  if(wireDrag.blankDwellTimer){clearTimeout(wireDrag.blankDwellTimer);wireDrag.blankDwellTimer=null}
  wireDrag.blankReady=false;wireDrag.blankAnchor=null;
  wireDrag.blankGhost?.remove();wireDrag.blankGhost=null;
}
function showWireBlankGhost(P){
  if(!wireDrag)return;
  wireDrag.blankGhost?.remove();
  const g=document.createElementNS('http://www.w3.org/2000/svg','g');g.setAttribute('class','wire-blank-ghost');g.setAttribute('transform',`translate(${P.x} ${P.y})`);
  const r=document.createElementNS('http://www.w3.org/2000/svg','rect');r.setAttribute('class','body');r.setAttribute('x','-56');r.setAttribute('y','-42');r.setAttribute('width','112');r.setAttribute('height','84');r.setAttribute('rx','9');g.appendChild(r);
  for(const line of [[-10,0,10,0],[0,-10,0,10]]){const l=document.createElementNS('http://www.w3.org/2000/svg','line');l.setAttribute('class','plus');l.setAttribute('x1',line[0]);l.setAttribute('y1',line[1]);l.setAttribute('x2',line[2]);l.setAttribute('y2',line[3]);g.appendChild(l)}
  const label=document.createElementNS('http://www.w3.org/2000/svg','text');label.setAttribute('text-anchor','middle');label.setAttribute('x','0');label.setAttribute('y','29');label.textContent='NEW COMPONENT';g.appendChild(label);
  ghostLayer.appendChild(g);wireDrag.blankGhost=g;
}
function armWireBlankCandidate(P){
  if(!wireDrag)return;
  const prev=wireDrag.blankAnchor;
  if(prev&&Math.hypot(P.x-prev.x,P.y-prev.y)<=WIRE_BLANK_DWELL_TOLERANCE)return;
  clearWireBlankCandidate();wireDrag.blankAnchor={x:P.x,y:P.y};
  wireDrag.blankDwellTimer=setTimeout(()=>{
    if(!wireDrag||wireDrag.snap)return;
    wireDrag.blankReady=true;wireDrag.blankDwellTimer=null;showWireBlankGhost(wireDrag.blankAnchor);statusEl.textContent='Release → new Component';
  },WIRE_BLANK_DWELL_MS);
}
function wirePointerMove(e){
  if(!wireDrag||e.pointerId!==wireDrag.pointerId)return;
  if(!wireDrag.moved){
    const dx=e.clientX-wireDrag.startClient.x,dy=e.clientY-wireDrag.startClient.y;
    const dt=performance.now()-wireDrag.startTime;
    if(Math.hypot(dx,dy)<PORT_DRAG_THRESHOLD || dt<PORT_DRAG_ARM_DELAY)return;
    wireDrag.moved=true;
    wireDrag.ghost.style.display='';
    wireDrag.end.style.display='';
    workspace.classList.add('wiring');
  }
  updateWireDrag(e);
}
function wirePointerUp(e){
  if(!wireDrag || e.pointerId!==wireDrag.pointerId)return;
  e.preventDefault();

  const snap=wireDrag.snap;
  const sourceNode=wireDrag.sourceNode;
  const sourceSide=wireDrag.sourceSide;
  const moved=wireDrag.moved;
  const blankReady=wireDrag.blankReady;
  const dropPoint=svgPoint(e.clientX,e.clientY);
  const droppedOnCanvas=canvasContainsClientPoint(e.clientX,e.clientY);

  finishWireDrag();

  if(!moved){
    selectPort(sourceNode,sourceSide);
    statusEl.textContent='Port selected';
    return;
  }

  if(snap){
    addConnection(sourceNode,sourceSide,snap.node,snap.side);
    renderWires();
    return;
  }

  if(droppedOnCanvas&&blankReady){
    growBlankFromConnection(sourceNode,sourceSide,dropPoint,e);
    return;
  }
  if(droppedOnCanvas&&!blankReady){statusEl.textContent='No Component created · hold briefly for ghost';}

  renderWires();
}
function wirePointerCancel(e){
  if(wireDrag&&e.pointerId===wireDrag.pointerId)finishWireDrag();
}
function updateWireDrag(e){
  if(!wireDrag)return;
  const P=svgPoint(e.clientX,e.clientY);
  const snap=findSnapTarget(P,wireDrag.sourceNode,wireDrag.sourceSide); wireDrag.snap=snap;
  clearSnapTargets();
  let B=P, bSide='in';
  if(snap){
    clearWireBlankCandidate();
    const target=nodes.find(n=>n.id===snap.node); B=portPos(target,snap.side); bSide=snap.side;
    const hit=document.querySelector(`.node[data-id="${snap.node}"] .port-hit[data-side="${snap.side}"]`);
    if(hit) hit.classList.add('snap-target');
    statusEl.textContent=`Release → ${target.label||byId(target.symbolId).name}`;
  } else {
    armWireBlankCandidate(P);
    statusEl.textContent=wireDrag.blankReady?'Release → new Component':'Hold briefly to grow Component';
  }
  const occupied=[];
  wires.forEach((w,i)=>{
    const WA=carrierEndpointPos(w,'a'), WB=carrierEndpointPos(w,'b');
    if(!WA||!WB) return;
    const pts=stableRouteForWire(i,w,WA,WB,occupied);
    occupied.push(...routeSegments(pts));
  });
  wireDrag.ghost.setAttribute('d',routePath(
    wireDrag.A,B,wireDrag.sourceSide,bSide,
    wireDrag.sourceNode,
    snap ? snap.node : null,
    wires.length,
    occupied
  ));
  wireDrag.end.setAttribute('cx',B.x); wireDrag.end.setAttribute('cy',B.y);
}
function findSnapTarget(P,sourceNode,sourceSide){
  let best=null,bestD=SNAP_RADIUS;
  for(const n of nodes){
    if(n.id===sourceNode||isEntityLocked(n))continue;
    for(const side of componentAttachmentPointIds(n)){
      const reach=connectionReachability(sourceNode,sourceSide,n.id,side);
      if(!reach.ok)continue;
      const Q=portPos(n,side),d=Math.hypot(P.x-Q.x,P.y-Q.y);
      if(d<bestD){bestD=d;best={node:n.id,side,canvasId:reach.canvasId}}
    }
  }
  return best;
}
function clearSnapTargets(){document.querySelectorAll('.port-hit.snap-target').forEach(x=>x.classList.remove('snap-target'))}
function finishWireDrag(){
  if(!wireDrag)return;
  const g=wireDrag.sourceEl;
  if(g)g.classList.remove('wiring-source');
  if(wireDrag.blankDwellTimer)clearTimeout(wireDrag.blankDwellTimer);
  wireDrag.blankGhost?.remove();
  wireDrag.ghost?.remove();
  wireDrag.end?.remove();
  clearSnapTargets();
  workspace.classList.remove('wiring');
  wireDrag=null;
  statusEl.textContent='Ready';
  restoreSelectionBarAfterGesture();
}
function cancelWireDrag(){ if(wireDrag) finishWireDrag(); }

// --- Carrier end handles ------------------------------------------------------
// Dragging a Path end rebinds it: release on an attachment point binds, release
// anywhere else leaves the end free at that spot. The other end constrains which
// points are legal (they must share its exposed surface); with the other end free
// the carrier adopts the surface of the point it is bound to.
let carrierEndDrag=null;
function findCarrierSnapTarget(w,end,P){
  const other=end==='a'?'b':'a',otherEp=carrierEndpoint(w,other);
  const allowed=otherEp?.kind==='bound'?new Set(portExposedCanvasIds(otherEp.node,otherEp.pointId)):null;
  let best=null,bestD=SNAP_RADIUS;
  for(const n of nodes){
    if(isEntityLocked(n)||isEffectivelyHidden(n))continue;
    for(const pointId of componentAttachmentPointIds(n)){
      if(otherEp?.kind==='bound'&&n.id===otherEp.node.id&&pointId===otherEp.pointId)continue;
      if(allowed&&!portExposedCanvasIds(n,pointId).some(c=>allowed.has(c)))continue;
      const Q=portPos(n,pointId),d=Math.hypot(P.x-Q.x,P.y-Q.y);
      if(d<bestD){bestD=d;best={node:n.id,side:pointId}}
    }
  }
  return best;
}
function bindCarrierEnd(w,end,nodeId,pointId){SovSchematicData.bindWireEndpoint(diagram,w,end,nodeId,pointId);return w}
function freeCarrierEnd(w,end,P){SovSchematicData.freeWireEndpoint(diagram,w,end,P.x,P.y);return w}
function beginCarrierEndDrag(e,i,end){
  const w=wires[i];if(!w)return;e.preventDefault();e.stopPropagation();
  if(isEntityLocked(w)||isEntityPinned(w)){statusEl.textContent=isEntityLocked(w)?'Locked · rebind refused':'Pinned · rebind refused';selectWire(i,{focus:false});return}
  cancelWireDrag();if(activeNodeDragState)finishActiveNodeDrag(null,{force:true,reason:'carrier handoff'});
  const ghost=document.createElementNS('http://www.w3.org/2000/svg','path');ghost.setAttribute('class','ghost-wire');
  const dot=document.createElementNS('http://www.w3.org/2000/svg','circle');dot.setAttribute('class','ghost-end');dot.setAttribute('r','6');
  ghostLayer.appendChild(ghost);ghostLayer.appendChild(dot);ghost.style.display='none';dot.style.display='none';
  carrierEndDrag={pointerId:e.pointerId,i,end,other:end==='a'?'b':'a',ghost,dot,snap:null,moved:false,startClient:{x:e.clientX,y:e.clientY}};
  selectWire(i,{focus:false});setSelectionBarSuppressed(true);
  statusEl.textContent='Path end armed · drag to rebind';
}
function carrierEndPointerMove(e){
  const d=carrierEndDrag;if(!d||e.pointerId!==d.pointerId)return;
  if(!d.moved){if(Math.hypot(e.clientX-d.startClient.x,e.clientY-d.startClient.y)<6)return;d.moved=true;d.ghost.style.display='';d.dot.style.display='';workspace.classList.add('wiring');setHistoryHint('Rebind Path end')}
  e.preventDefault();
  const w=wires[d.i];if(!w){finishCarrierEndDrag();return}
  const P=svgPoint(e.clientX,e.clientY),snap=findCarrierSnapTarget(w,d.end,P);d.snap=snap;clearSnapTargets();
  const B=snap?portPos(nodes.find(n=>n.id===snap.node),snap.side):P;
  if(snap)document.querySelector(`.node[data-id="${snap.node}"] .port-hit[data-point="${snap.side}"]`)?.classList.add('snap-target');
  const otherEp=carrierEndpoint(w,d.other);
  if(otherEp){
    const from=d.other==='a',occupied=[];
    wires.forEach((x,j)=>{if(j===d.i)return;const XA=carrierEndpointPos(x,'a'),XB=carrierEndpointPos(x,'b');if(XA&&XB)occupied.push(...routeSegments(stableRouteForWire(j,x,XA,XB,occupied)))});
    const A=from?otherEp.pos:B,Z=from?B:otherEp.pos;
    d.ghost.setAttribute('d',routePath(A,Z,from?(otherEp.compatId||null):(snap?.side||null),from?(snap?.side||null):(otherEp.compatId||null),from?(otherEp.node?.id||null):(snap?.node||null),from?(snap?.node||null):(otherEp.node?.id||null),d.i,occupied));
  }
  d.dot.setAttribute('cx',B.x);d.dot.setAttribute('cy',B.y);
  statusEl.textContent=snap?`Release → bind to ${componentDisplayName(nodes.find(n=>n.id===snap.node))}`:'Release → free end';
}
function carrierEndPointerUp(e){
  const d=carrierEndDrag;if(!d||e.pointerId!==d.pointerId)return;e.preventDefault();
  const w=wires[d.i],moved=d.moved,snap=d.snap,P=svgPoint(e.clientX,e.clientY);
  finishCarrierEndDrag();
  if(!w)return;
  if(!moved){selectWire(d.i);return}
  try{
    if(snap){bindCarrierEnd(w,d.end,snap.node,snap.side);statusEl.textContent='Path end bound'}
    else{freeCarrierEnd(w,d.end,P);statusEl.textContent='Path end freed'}
  }catch(error){statusEl.textContent=error.message}
  routeCache.delete(d.i);arrowPoseCache.clear();render();selectWire(d.i,{focus:false});scheduleHistoryCapture();
}
function finishCarrierEndDrag(){
  const d=carrierEndDrag;if(!d)return;
  d.ghost?.remove();d.dot?.remove();clearSnapTargets();workspace.classList.remove('wiring');carrierEndDrag=null;restoreSelectionBarAfterGesture();
}
window.addEventListener('pointermove',carrierEndPointerMove,true);
window.addEventListener('pointerup',carrierEndPointerUp,true);
window.addEventListener('pointercancel',e=>{if(carrierEndDrag&&e.pointerId===carrierEndDrag.pointerId)finishCarrierEndDrag()},true);
window.addEventListener('blur',()=>finishCarrierEndDrag());

// Port gestures are tracked globally after pointer-down. This gives a plain
// click a reliable selection path and keeps a real drag alive even when the
// pointer leaves the component.
window.addEventListener('pointermove',e=>{
  if(wireDrag&&e.pointerId===wireDrag.pointerId)wirePointerMove(e);
},true);
window.addEventListener('pointerup',e=>{
  if(wireDrag&&e.pointerId===wireDrag.pointerId)wirePointerUp(e);
},true);
window.addEventListener('pointercancel',e=>{
  if(wireDrag&&e.pointerId===wireDrag.pointerId)wirePointerCancel(e);
},true);
window.addEventListener('blur',()=>{
  if(wireDrag)finishWireDrag();
});


workspace.addEventListener('pointerdown',beginPanGesture,true);
window.addEventListener('pointermove',movePanGesture,true);
window.addEventListener('pointerup',finishPanGesture,true);
window.addEventListener('pointercancel',finishPanGesture,true);
window.addEventListener('blur',()=>finishPanGesture());

workspace.addEventListener('pointerdown',e=>{if(e.target===workspace && !panDrag&&!e.shiftKey&&!marqueeGesture){selected=null;selectNode(null)}});
barComponentType.addEventListener('change',()=>{
  const n=nodes.find(n=>n.id===selected);if(!n||mutationBlocked(n,'type change'))return;setHistoryHint('Change Component type');
  const next=barComponentType.value;
  if(!GROUPS.Components.includes(next)&&!GROUPS.Primitives.includes(next)){barComponentType.value=n.symbolId;return}

  // A Path is a carrier drawn from the palette; a Component is not retyped into one (#19).
  const preset=SovSchematicData.templatePreset(next);
  if(preset?.carrier){barComponentType.value=n.symbolId;statusEl.textContent='Draw a Path from the palette';return}

  // Retyping applies the whole target preset (or the standard Component Form). Refuse
  // when a Wire already ends on a built-in point the new attachment set would remove.
  const f=componentForm(n),nextDimension=preset?.form?.dimension??2,nextDefaults=preset?.attachmentDefaults||'standard';
  const wouldRemoveBuiltins=f.dimension!==nextDimension||(nextDefaults==='none'&&Attachment.attachmentDefaults(n)!=='none');
  if(wouldRemoveBuiltins&&wiresOnBuiltinPoints(n).length){barComponentType.value=n.symbolId;statusEl.textContent='Detach Wires from built-in points first';return}
  const beforeOpen=formHostsChildren(n);
  SovSchematicData.applySymbol(n,next);
  if(beforeOpen&&!formHostsChildren(n)){const fallback=n.canvasId||GLOBAL_CANVAS_ID;for(const child of nodes.filter(q=>parentComponent(q)?.id===n.id)){child.canvasId=fallback;child.parentId=canvasOwnerComponentId(fallback);syncNodeBoundaryContext(child)}}
  SovSchematicData.reconcileComponentWirePorts(diagram,n.id);
  ensureComponentStructure(n);

  // Type changes type the INSIDE of the existing boundary. Identity,
  // boundary, owned Parts, position, configuration, and topology remain.
  routeCache.clear();
  arrowPoseCache.clear();
  render();
  selectNode(n.id);scheduleHistoryCapture();
});
barComponentLabel.addEventListener('input',()=>{
  const n=nodes.find(n=>n.id===selected);if(!n||mutationBlocked(n,'label edit'))return;setHistoryHint('Edit Component label');
  const cfg=componentConfig(n),before=cfg.label;cfg.label=barComponentLabel.value;SovSchematicData.adoptLabelMode(n,before);
  refreshCanvasScopeControl();render();selectNode(n.id,{focus:false});scheduleHistoryCapture();
});
barComponentSignalMode.addEventListener('change',()=>{
  const n=nodes.find(n=>n.id===selected);if(!n||mutationBlocked(n,'signal change'))return;setHistoryHint('Change signal mode');
  const cfg=componentConfig(n);cfg.signalMode=barComponentSignalMode.value;
  render();selectNode(n.id,{focus:false});scheduleHistoryCapture();
});
barComponentColorSlot.addEventListener('click',()=>openColorSlotPanel('component'));
