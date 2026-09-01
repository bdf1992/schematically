
'use strict';
// 0.1 Beta concern: editor utility kernel — history, selection sets, clipboard,
// hosting settle, object state, search, view appearance, checkpoints and rate.

const selectedComponentIds=new Set();
let semanticClipboard=null;
let marqueeGesture=null;
let quickSearchActive=false;
let quickSearchMatches=[];
let appearanceMode='system';

function entityEditorState(entity){
  if(!entity)return {pinned:false,locked:false,hidden:false,opacity:1,rate:1};
  if(!entity.editor||typeof entity.editor!=='object')entity.editor={};
  entity.editor.pinned=!!entity.editor.pinned;
  entity.editor.locked=!!entity.editor.locked;
  entity.editor.hidden=!!entity.editor.hidden;
  entity.editor.opacity=Math.max(.08,Math.min(1,Number(entity.editor.opacity)||1));
  entity.editor.rate=Math.max(.1,Math.min(8,Number(entity.editor.rate)||1));
  return entity.editor;
}
function isEntityLocked(entity){return !!entityEditorState(entity).locked}
function isEntityPinned(entity){return !!entityEditorState(entity).pinned}
function isEffectivelyHidden(node){
  if(!node)return false;
  if(entityEditorState(node).hidden)return true;
  let cur=parentComponent(node),seen=new Set();
  while(cur&&!seen.has(cur.id)){if(entityEditorState(cur).hidden)return true;seen.add(cur.id);cur=parentComponent(cur)}
  return false;
}
function mutationBlocked(entity,label='Edit'){
  if(!entity)return false;
  if(isEntityLocked(entity)){statusEl.textContent=`Locked · ${label} refused`;return true}
  return false;
}
function selectedComponentArray(){return [...selectedComponentIds].map(id=>nodes.find(n=>n.id===id)).filter(Boolean)}
function selectedRootComponents(){
  const ids=new Set(selectedComponentIds);
  return selectedComponentArray().filter(n=>{let p=parentComponent(n);while(p){if(ids.has(p.id))return false;p=parentComponent(p)}return true});
}
function setComponentSelection(ids,primary=null){
  selectedComponentIds.clear();
  for(const id of ids||[])if(nodes.some(n=>n.id===id))selectedComponentIds.add(id);
  selected=primary&&selectedComponentIds.has(primary)?primary:([...selectedComponentIds].at(-1)||null);
  refreshComponentSelectionProjection();
}
function refreshComponentSelectionProjection(){
  document.querySelectorAll('.node').forEach(el=>el.classList.toggle('selected',selectedComponentIds.has(el.dataset.id)));
  if(selectedComponentIds.size>1)statusEl.textContent=`${selectedComponentIds.size} Components selected`;
}
function clearComponentSelectionSet(){selectedComponentIds.clear()}

// --- History ---------------------------------------------------------------
const historyState={undo:[],redo:[],baseline:null,timer:null,hint:'Edit',replaying:false,max:120};
function historyDocument(){return SovSchematicData.makeDocument(SovSchematicData.clone(diagram))}
function historyFingerprintOf(doc){
  const d=SovSchematicData.clone(doc);d.revision=0;
  if(d.meta){delete d.meta.updatedAt;delete d.meta.savedAt}
  return JSON.stringify(d);
}
function setHistoryHint(label){if(label)historyState.hint=String(label).slice(0,80)}
function initializeHistory(){historyState.baseline=historyDocument();historyState.undo=[];historyState.redo=[];updateHistoryUI()}
function scheduleHistoryCapture(label=null){
  if(historyState.replaying)return;
  if(label)setHistoryHint(label);
  if(historyState.timer)clearTimeout(historyState.timer);
  historyState.timer=setTimeout(()=>commitHistoryCapture(),320);
}
function commitHistoryCapture(label=null){
  if(historyState.timer){clearTimeout(historyState.timer);historyState.timer=null}
  if(historyState.replaying)return false;
  const current=historyDocument();
  if(!historyState.baseline){historyState.baseline=current;return false}
  if(historyFingerprintOf(current)===historyFingerprintOf(historyState.baseline))return false;
  historyState.undo.push({label:label||historyState.hint||'Edit',at:new Date().toISOString(),document:historyState.baseline});
  if(historyState.undo.length>historyState.max)historyState.undo.splice(0,historyState.undo.length-historyState.max);
  historyState.baseline=current;historyState.redo=[];historyState.hint='Edit';updateHistoryUI();return true;
}
function restoreHistoryDocument(doc){
  historyState.replaying=true;
  try{replaceRuntimeDocument(doc)}finally{historyState.replaying=false}
  historyState.baseline=historyDocument();persistenceFingerprint=semanticFingerprint();updateHistoryUI();renderObjectsPanel();
}
function undoHistory(){
  commitHistoryCapture();const item=historyState.undo.pop();if(!item){statusEl.textContent='Nothing to undo';return false}
  historyState.redo.push({label:item.label,at:new Date().toISOString(),document:historyDocument()});restoreHistoryDocument(item.document);statusEl.textContent=`Undo · ${item.label}`;return true;
}
function redoHistory(){
  commitHistoryCapture();const item=historyState.redo.pop();if(!item){statusEl.textContent='Nothing to redo';return false}
  historyState.undo.push({label:item.label,at:new Date().toISOString(),document:historyDocument()});restoreHistoryDocument(item.document);statusEl.textContent=`Redo · ${item.label}`;return true;
}
function historyList(){return historyState.undo.map((x,i)=>({index:i,label:x.label,at:x.at}))}
function updateHistoryUI(){
  const undo=document.getElementById('editUndoBtn'),redo=document.getElementById('editRedoBtn'),quickUndo=document.getElementById('quickUndoBtn'),quickRedo=document.getElementById('quickRedoBtn');
  if(undo)undo.disabled=!historyState.undo.length;if(redo)redo.disabled=!historyState.redo.length;
  if(quickUndo)quickUndo.disabled=!historyState.undo.length;if(quickRedo)quickRedo.disabled=!historyState.redo.length;
  const list=document.getElementById('historyList');if(list){list.replaceChildren();for(const item of historyState.undo.slice(-12).reverse()){const row=document.createElement('div');row.className='history-row';row.textContent=item.label;list.appendChild(row)}if(!list.children.length)list.textContent='No edits yet'}
}

// --- Checkpoints -----------------------------------------------------------
function checkpointStore(){diagram.meta=diagram.meta||{};if(!Array.isArray(diagram.meta.checkpoints))diagram.meta.checkpoints=[];return diagram.meta.checkpoints}
function checkpointSnapshot(){const doc=historyDocument();doc.meta=doc.meta||{};doc.meta.checkpoints=[];return doc}
function createCheckpoint(name=null){
  commitHistoryCapture();const store=checkpointStore();const label=String(name||`Checkpoint ${store.length+1}`).trim()||`Checkpoint ${store.length+1}`;
  const cp={id:`cp-${Date.now()}-${Math.random().toString(36).slice(2,6)}`,name:label,createdAt:new Date().toISOString(),revision:diagram.revision||0,document:checkpointSnapshot()};
  setHistoryHint(`Checkpoint · ${label}`);store.push(cp);scheduleHistoryCapture();renderCheckpointList();updateFileReadout?.();statusEl.textContent=`Checkpoint · ${label}`;return SovSchematicData.clone(cp);
}
function listCheckpoints(){return checkpointStore().map(({document,...meta})=>SovSchematicData.clone(meta))}
function restoreCheckpoint(id){
  const store=checkpointStore(),cp=store.find(x=>x.id===id);if(!cp)throw new Error('Checkpoint not found');
  commitHistoryCapture();const preserved=SovSchematicData.clone(store);setHistoryHint(`Restore checkpoint · ${cp.name}`);
  historyState.replaying=true;try{replaceRuntimeDocument(cp.document);diagram.meta=diagram.meta||{};diagram.meta.checkpoints=preserved}finally{historyState.replaying=false}
  historyState.baseline=historyDocument();scheduleHistoryCapture();renderCheckpointList();statusEl.textContent=`Restored · ${cp.name}`;return snapshotDocument();
}
function renderCheckpointList(){
  const list=document.getElementById('checkpointList');if(!list)return;list.replaceChildren();
  for(const cp of checkpointStore().slice().reverse()){
    const b=document.createElement('button');b.type='button';b.className='checkpoint-row';b.innerHTML=`<span>${escapeXML(cp.name)}</span><small>r${cp.revision}</small>`;b.addEventListener('click',()=>restoreCheckpoint(cp.id));list.appendChild(b);
  }
  if(!list.children.length){const e=document.createElement('div');e.className='empty-mini';e.textContent='No checkpoints';list.appendChild(e)}
}

// --- Clipboard -------------------------------------------------------------
function collectSelectionSubtree(){
  const roots=selectedRootComponents();if(!roots.length&&typeof selected==='string'&&!selected.startsWith('wire:')&&!isAttachmentSelectionValue(selected)){const n=nodes.find(n=>n.id===selected);if(n)roots.push(n)}
  const ids=new Set();for(const root of roots){ids.add(root.id);for(const d of descendantsOf(root.id))ids.add(d.id)}
  return {roots,ids,components:nodes.filter(n=>ids.has(n.id)).map(SovSchematicData.clone),wires:wires.filter(w=>ids.has(w.a)&&ids.has(w.b)).map(SovSchematicData.clone)};
}
function copySelection(){
  const data=collectSelectionSubtree();if(!data.components.length){statusEl.textContent='Nothing to copy';return null}
  semanticClipboard={schema:'soveraeign.schematic/clipboard@0.1',createdAt:new Date().toISOString(),rootIds:data.roots.map(x=>x.id),components:data.components,wires:data.wires};
  statusEl.textContent=`Copied · ${data.components.length} Component${data.components.length===1?'':'s'}`;updateEditMenuState();return SovSchematicData.clone(semanticClipboard);
}
function pasteClipboard({offset=32}={}){
  if(!semanticClipboard?.components?.length){statusEl.textContent='Clipboard empty';return []}
  setHistoryHint('Paste');const idMap=new Map(),created=[];
  const comps=semanticClipboard.components.slice().sort((a,b)=>nodeDepth(a)-nodeDepth(b));
  for(const old of comps){
    const value=SovSchematicData.clone(old);delete value.id;
    value.x=Number(old.x||0)+offset;value.y=Number(old.y||0)+offset;
    if(old.parentId&&idMap.has(old.parentId)){value.parentId=idMap.get(old.parentId);value.canvasId=`canvas:component:${value.parentId}`}else{value.parentId=null;value.canvasId=GLOBAL_CANVAS_ID;value.placement={kind:'surface',x:value.x,y:value.y}};
    const fresh=SovSchematicData.makeComponent(diagram,value);nodes.push(fresh);idMap.set(old.id,fresh.id);created.push(fresh);
  }
  for(const old of semanticClipboard.wires||[]){
    if(!idMap.has(old.a)||!idMap.has(old.b))continue;
    const value=SovSchematicData.clone(old);delete value.id;value.a=idMap.get(old.a);value.b=idMap.get(old.b);
    try{wires.push(SovSchematicData.makeWire(diagram,value))}catch(_){ }
  }
  syncAllNodeBoundaryContext();setComponentSelection(created.filter(n=>semanticClipboard.rootIds.includes([...idMap.entries()].find(([,v])=>v===n.id)?.[0])).map(n=>n.id),created.at(-1)?.id);routeCache.clear();arrowPoseCache.clear();render();scheduleHistoryCapture();statusEl.textContent=`Pasted · ${created.length} Component${created.length===1?'':'s'}`;return created;
}
function cutSelection(){if(!copySelection())return;setHistoryHint('Cut');deleteSelected();scheduleHistoryCapture()}
function duplicateSelection(){if(!copySelection())return [];return pasteClipboard({offset:24})}
function updateEditMenuState(){const p=document.getElementById('editPasteBtn');if(p)p.disabled=!semanticClipboard}

// --- Focus / search / objects ---------------------------------------------
function focusComponent(node){
  if(!node)return;const size=componentSize(node),wrap=workspace.getBoundingClientRect(),aspect=(wrap.width||1)/(wrap.height||1);let w=Math.max(220,size.w*2.4),h=Math.max(170,size.h*2.4);if(w/h>aspect)h=w/aspect;else w=h*aspect;const z=Math.max(MIN_ZOOM,Math.min(MAX_ZOOM,BASE_VIEW.w/w));camera={x:node.x-(BASE_VIEW.w/z)/2,y:node.y-(BASE_VIEW.h/z)/2,w:BASE_VIEW.w/z,h:BASE_VIEW.h/z};applyCamera();selectNode(node.id,{focus:false});statusEl.textContent=`Focus · ${componentDisplayName(node)}`;
}
function openQuickSearch(seed=''){
  const overlay=document.getElementById('quickSearch'),input=document.getElementById('quickSearchInput');if(!overlay||!input)return;
  quickSearchActive=true;overlay.hidden=false;input.value=seed;updateQuickSearch(seed);requestAnimationFrame(()=>input.focus({preventScroll:true}));
}
function closeQuickSearch(){quickSearchActive=false;quickSearchMatches=[];const overlay=document.getElementById('quickSearch');if(overlay)overlay.hidden=true;document.querySelectorAll('.search-dim,.search-match').forEach(el=>el.classList.remove('search-dim','search-match'));activateCanvasKeyboard()}
function quickCommands(){return [
  {name:'Fit diagram',run:()=>fitDiagram()},{name:'Toggle flow',run:()=>{showFlow=!showFlow;workspace.classList.toggle('show-flow',showFlow);flowBtn.classList.toggle('active',showFlow)}},
  {name:'Create checkpoint',run:()=>createCheckpoint()},{name:'Dark mode',run:()=>{appearanceMode='dark';applyAppearanceMode()}},{name:'Light mode',run:()=>{appearanceMode='light';applyAppearanceMode()}}
]}
function updateQuickSearch(query=''){
  const q=String(query).trim().toLowerCase(),results=document.getElementById('quickSearchResults');if(!results)return;results.replaceChildren();
  quickSearchMatches=q?nodes.filter(n=>!isEffectivelyHidden(n)&&[n.id,n.symbolId,componentConfig(n).label,byId(n.symbolId)?.name].some(v=>String(v||'').toLowerCase().includes(q))):[];
  document.querySelectorAll('.node').forEach(el=>{const match=quickSearchMatches.some(n=>n.id===el.dataset.id);el.classList.toggle('search-match',!!q&&match);el.classList.toggle('search-dim',!!q&&!match)});
  for(const n of quickSearchMatches.slice(0,10)){const b=document.createElement('button');b.type='button';b.className='search-result';b.innerHTML=`<b>${escapeXML(componentDisplayName(n))}</b><small>${escapeXML(n.symbolId)} · ${escapeXML(n.id)}</small>`;b.addEventListener('click',()=>{closeQuickSearch();focusComponent(n)});results.appendChild(b)}
  for(const c of quickCommands().filter(c=>q&&c.name.toLowerCase().includes(q)).slice(0,5)){const b=document.createElement('button');b.type='button';b.className='search-result command';b.innerHTML=`<b>› ${escapeXML(c.name)}</b>`;b.addEventListener('click',()=>{closeQuickSearch();c.run()});results.appendChild(b)}
  if(!results.children.length){const e=document.createElement('div');e.className='search-empty';e.textContent=q?'No matches':'Type a component, id, or command';results.appendChild(e)}
}
function renderObjectsPanel(){
  const list=document.getElementById('objectsList');if(!list)return;list.replaceChildren();
  const sorted=[...nodes].sort((a,b)=>nodeDepth(a)-nodeDepth(b)||String(a.id).localeCompare(String(b.id)));
  for(const n of sorted){const st=entityEditorState(n),row=document.createElement('button');row.type='button';row.className='object-row'+(st.hidden?' is-hidden':'')+(st.locked?' is-locked':'')+(st.pinned?' is-pinned':'');row.style.paddingLeft=`${8+nodeDepth(n)*14}px`;row.innerHTML=`<span>${escapeXML(componentDisplayName(n))}</span><small>${st.pinned?'◆ ':''}${st.locked?'🔒 ':''}${st.hidden?'hidden':n.symbolId}</small>`;row.addEventListener('click',()=>{if(st.hidden){st.hidden=false;setHistoryHint('Show object');render();scheduleHistoryCapture()}selectNode(n.id)});row.addEventListener('dblclick',()=>focusComponent(n));list.appendChild(row)}
  const hiddenCount=nodes.filter(n=>entityEditorState(n).hidden).length;const count=document.getElementById('hiddenObjectCount');if(count)count.textContent=hiddenCount?String(hiddenCount):'';
  if(!list.children.length){const e=document.createElement('div');e.className='empty-mini';e.textContent='No objects';list.appendChild(e)}
}

// --- Appearance / rate -----------------------------------------------------
function globalTimeScale(){diagram.meta=diagram.meta||{};const n=Number(diagram.meta.timeScale);return Math.max(.1,Math.min(8,Number.isFinite(n)?n:1))}
function setGlobalTimeScale(value){diagram.meta=diagram.meta||{};diagram.meta.timeScale=Math.max(.1,Math.min(8,Number(value)||1));setHistoryHint('Change global rate');render();scheduleHistoryCapture()}
function packetRateForWire(w,direction='forward'){
  const source=nodes.find(n=>n.id===(direction==='reverse'?w.b:w.a));return globalTimeScale()*entityEditorState(source).rate*entityEditorState(w).rate;
}
function resolveAppearanceMode(){if(appearanceMode!=='system')return appearanceMode;return matchMedia?.('(prefers-color-scheme: dark)').matches?'dark':'light'}
function applyAppearanceMode(){const resolved=resolveAppearanceMode();document.documentElement.dataset.appearance=resolved;document.documentElement.style.setProperty('--canvas-tone',canvasTone(colorEngine.theme,resolved));const input=document.getElementById('appearanceMode');if(input)input.value=appearanceMode;try{localStorage.setItem('soveraeign.schematic.appearance',appearanceMode)}catch(_){}refreshPaletteDerivedColors?.();renderPalettePreview?.();render?.();restoreSelectedSurface?.();statusEl.textContent=`View · ${resolved}`}

// --- Utility settings ------------------------------------------------------
function selectedUtilityEntity(kind=selectedSurfaceKind()){
  if(kind==='component')return nodes.find(n=>n.id===selected)||null;
  if(kind==='wire')return selectedConnection?.()||null;
  if(kind==='port'){const info=selectedPortInfo();return info?.owner||null}
  return null;
}
function syncEntityUtilityPanel(kind){
  const entity=selectedUtilityEntity(kind),panel=document.getElementById('entityUtilityFields');if(!panel)return;panel.hidden=!entity;if(!entity)return;
  const state=entityEditorState(entity),pin=document.getElementById('entityPin'),lock=document.getElementById('entityLock'),hidden=document.getElementById('entityHidden'),opacity=document.getElementById('entityOpacity'),rate=document.getElementById('entityRate');
  pin.checked=state.pinned;pin.disabled=kind!=='component'||state.locked;lock.checked=state.locked;hidden.checked=state.hidden;opacity.value=String(state.opacity);opacity.disabled=state.locked;rate.value=String(state.rate);rate.disabled=state.locked;
  panel.dataset.ownerKind=kind;
}
function bindUtilitySettings(){
  const pin=document.getElementById('entityPin'),lock=document.getElementById('entityLock'),hidden=document.getElementById('entityHidden'),opacity=document.getElementById('entityOpacity'),rate=document.getElementById('entityRate');
  pin?.addEventListener('change',()=>{const e=selectedUtilityEntity();if(!e)return;setHistoryHint(pin.checked?'Pin':'Unpin');entityEditorState(e).pinned=pin.checked;render();scheduleHistoryCapture();restoreSelectedSurface()});
  lock?.addEventListener('change',()=>{const e=selectedUtilityEntity();if(!e)return;setHistoryHint(lock.checked?'Lock':'Unlock');entityEditorState(e).locked=lock.checked;render();scheduleHistoryCapture();restoreSelectedSurface()});
  hidden?.addEventListener('change',()=>{const e=selectedUtilityEntity();if(!e)return;setHistoryHint(hidden.checked?'Hide':'Show');entityEditorState(e).hidden=hidden.checked;render();scheduleHistoryCapture();if(hidden.checked){selected=null;clearComponentSelectionSet();selectNode(null)}else restoreSelectedSurface()});
  opacity?.addEventListener('input',()=>{const e=selectedUtilityEntity();if(!e||isEntityLocked(e))return;entityEditorState(e).opacity=Number(opacity.value);setHistoryHint('Change opacity');render();scheduleHistoryCapture()});
  rate?.addEventListener('change',()=>{const e=selectedUtilityEntity();if(!e||isEntityLocked(e))return;entityEditorState(e).rate=Number(rate.value);setHistoryHint('Change rate');render();scheduleHistoryCapture();restoreSelectedSurface()});
}

// --- Marquee selection -----------------------------------------------------
function beginMarqueeGesture(e){
  if(e.button!==0)return false;e.preventDefault();e.stopImmediatePropagation();const p=svgPoint(e.clientX,e.clientY),rect=document.createElementNS('http://www.w3.org/2000/svg','rect');rect.setAttribute('class','marquee-rect');ghostLayer.appendChild(rect);marqueeGesture={pointerId:e.pointerId,start:p,current:p,rect};setSelectionBarSuppressed(true);statusEl.textContent='Marquee select';return true;
}
function updateMarqueeGesture(e){if(!marqueeGesture||e.pointerId!==marqueeGesture.pointerId)return;e.preventDefault();const p=svgPoint(e.clientX,e.clientY);marqueeGesture.current=p;const x=Math.min(p.x,marqueeGesture.start.x),y=Math.min(p.y,marqueeGesture.start.y),w=Math.abs(p.x-marqueeGesture.start.x),h=Math.abs(p.y-marqueeGesture.start.y);for(const [k,v] of Object.entries({x,y,width:w,height:h}))marqueeGesture.rect.setAttribute(k,String(v))}
function finishMarqueeGesture(e){if(!marqueeGesture||(e&&e.pointerId!==marqueeGesture.pointerId))return;const g=marqueeGesture,loX=Math.min(g.start.x,g.current.x),hiX=Math.max(g.start.x,g.current.x),loY=Math.min(g.start.y,g.current.y),hiY=Math.max(g.start.y,g.current.y);const ids=nodes.filter(n=>!isEffectivelyHidden(n)&&n.x>=loX&&n.x<=hiX&&n.y>=loY&&n.y<=hiY).map(n=>n.id);g.rect.remove();marqueeGesture=null;setComponentSelection(ids,ids.at(-1)||null);if(selected)selectNode(selected,{focus:false,preserveSet:true});else selectNode(null);restoreSelectionBarAfterGesture()}
window.addEventListener('pointermove',updateMarqueeGesture,true);window.addEventListener('pointerup',finishMarqueeGesture,true);window.addEventListener('pointercancel',finishMarqueeGesture,true);

// --- Settle host ghost -----------------------------------------------------
function clearSettleHostGhost(){document.querySelectorAll('.settle-host-ghost').forEach(x=>x.remove())}
function showSettleHostGhost(candidate,child){
  clearSettleHostGhost();if(!candidate)return;const g=document.createElementNS('http://www.w3.org/2000/svg','g');g.setAttribute('class',`settle-host-ghost ${candidate.kind}-host`);
  if(candidate.kind==='component'){const host=candidate.entity,size=componentSize(host);g.setAttribute('transform',`translate(${host.x} ${host.y})`);const r=document.createElementNS('http://www.w3.org/2000/svg','rect');r.setAttribute('x',String(-size.w/2+10));r.setAttribute('y',String(-size.h/2+10));r.setAttribute('width',String(size.w-20));r.setAttribute('height',String(size.h-20));r.setAttribute('rx','8');g.appendChild(r);const label=document.createElementNS('http://www.w3.org/2000/svg','text');label.setAttribute('x','0');label.setAttribute('y',String(-size.h/2+25));label.setAttribute('text-anchor','middle');label.textContent=`Release to host ${componentDisplayName(child)}`;g.appendChild(label)}
  else if(['wire','path','edge'].includes(candidate.kind)){const q=candidate.placement;g.setAttribute('transform',`translate(${q.x} ${q.y}) rotate(${Number(q.angle)||0})`);const r=document.createElementNS('http://www.w3.org/2000/svg','rect');r.setAttribute('x','-30');r.setAttribute('y','-18');r.setAttribute('width','60');r.setAttribute('height','36');r.setAttribute('rx','9');g.appendChild(r);const axis=document.createElementNS('http://www.w3.org/2000/svg','line');axis.setAttribute('class','settle-wire-axis');axis.setAttribute('x1','-42');axis.setAttribute('x2','42');axis.setAttribute('y1','0');axis.setAttribute('y2','0');g.appendChild(axis);const label=document.createElementNS('http://www.w3.org/2000/svg','text');label.setAttribute('x','0');label.setAttribute('y','-24');label.setAttribute('text-anchor','middle');label.textContent=`Release onto ${candidate.entity.config?.label||candidate.entity.id}`;g.appendChild(label)}
  ghostLayer.appendChild(g);
}

function initializeEditorKernel(){
  try{appearanceMode=localStorage.getItem('soveraeign.schematic.appearance')||'system'}catch(_){appearanceMode='system'}applyAppearanceMode();renderCheckpointList();initializeHistory();bindUtilitySettings();renderObjectsPanel();updateEditMenuState();
  const search=document.getElementById('quickSearchInput');search?.addEventListener('input',()=>updateQuickSearch(search.value));search?.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();closeQuickSearch()}else if(e.key==='Enter'){e.preventDefault();const n=quickSearchMatches[0];if(n){closeQuickSearch();focusComponent(n)}}});
  const appearance=document.getElementById('appearanceMode');appearance?.addEventListener('change',()=>{appearanceMode=appearance.value;applyAppearanceMode()});
  document.getElementById('globalRate')?.addEventListener('change',e=>setGlobalTimeScale(e.target.value));
  if(document.getElementById('globalRate'))document.getElementById('globalRate').value=String(globalTimeScale());
  matchMedia?.('(prefers-color-scheme: dark)')?.addEventListener?.('change',()=>{if(appearanceMode==='system')applyAppearanceMode()});
}
