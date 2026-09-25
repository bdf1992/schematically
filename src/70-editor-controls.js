'use strict';
// 0.1 Beta concern: Contextual editor mutations and selected-surface control bindings.

function mutateSelectedPresentation(mutator,{reroute=false}={}){
  const n=nodes.find(n=>n.id===selected);if(!n||mutationBlocked(n,'settings edit'))return;setHistoryHint('Edit Component settings');
  const preserveEditorFocus=isEditableTarget(document.activeElement);
  const p=componentConfig(n).presentation;mutator(p,n);componentConfig(n);
  if(reroute){routeCache.clear();arrowPoseCache.clear()}
  render();selectNode(n.id,{focus:!preserveEditorFocus});scheduleHistoryCapture();
  openSelectionSettings('component');syncComponentVisualPanel(n);
}
visualGraphicMode.addEventListener('change',()=>mutateSelectedPresentation(p=>{p.graphic.kind=visualGraphicMode.value;visualSvgRow.hidden=p.graphic.kind!=='custom'}));
visualLabelMode.addEventListener('change',()=>mutateSelectedPresentation(p=>p.labelMode=visualLabelMode.value));
visualWidth.addEventListener('change',()=>mutateSelectedPresentation(p=>p.size.w=Number(visualWidth.value)||112,{reroute:true}));
visualHeight.addEventListener('change',()=>mutateSelectedPresentation(p=>p.size.h=Number(visualHeight.value)||84,{reroute:true}));
visualInteriorColor.addEventListener('click',()=>openColorSlotPanel('component-interior'));
visualText.addEventListener('input',()=>mutateSelectedPresentation(p=>p.text=visualText.value));
visualSvgMarkup.addEventListener('input',()=>mutateSelectedPresentation(p=>{p.graphic.svg=visualSvgMarkup.value;p.graphic.kind='custom';visualGraphicMode.value='custom'}));
barPortSide.addEventListener('change',()=>{
  const info=selectedPortInfo();if(!info)return;
  // Attachment geometry is derived from the host topology; side is not independent authored truth.
  const side=info.point?.side||Attachment.resolveSpec(info.owner,info.pointId)?.side||'point';
  barPortSide.value=side;
  statusEl.textContent='0D attachment position is derived from its host form';
});
// Place a point on a line or across a band: a boundary Point's placement, or a card port's config.
function setSectionPosition(owner,compat,value){
  if(!owner||mutationBlocked(owner,'Change position'))return false;
  const [kind,i]=String(value).split(':'),at=kind==='through'?{through:Number(i)}:{line:Number(i)};
  setHistoryHint('Change position on the boundary');
  if(componentForm(owner).dimension===0&&componentPlacement(owner).kind==='edge')owner.placement.at=at;
  else{const p=componentConfig(owner).ports[compat];if(!p)return false;p.at=at}
  // Which side a point reaches is decided by where it sits; wires follow the new exposure.
  syncAllNodeBoundaryContext();routeCache.clear();arrowPoseCache.clear();render();scheduleHistoryCapture();return true;
}
barPortPosition?.addEventListener('change',()=>{const info=selectedPortInfo();if(!info)return;setSectionPosition(info.owner,Attachment.resolveSpec(info.owner,info.pointId)?.compatId||'out',barPortPosition.value);selectPortRef(selectedPortInfo()||info)});
formPointPosition?.addEventListener('change',()=>{const n=nodes.find(x=>x.id===selected);if(!n)return;setSectionPosition(n,'out',formPointPosition.value);selectNode(n.id,{focus:false});openSelectionSettings('component');syncComponentVisualPanel(n)});
barPortFace.addEventListener('change',()=>{
  const info=selectedPortInfo();if(!info||mutationBlocked(info.owner,'Change Port face'))return;setHistoryHint('Change Port face');
  info.port.face=barPortFace.value;
  componentConfig(info.owner);
  routeCache.clear();arrowPoseCache.clear();render();selectPortRef(selectedPortInfo()||info);
});
barPortFlow.addEventListener('change',()=>{
  const info=selectedPortInfo();if(!info||mutationBlocked(info.owner,'Change Port direction'))return;setHistoryHint('Change Port direction');
  normalizePortConnections(info.port);
  const connection=info.port.connections[info.port.activeConnection];
  connection.flow=barPortFlow.value;
  componentConfig(info.owner);
  renderWires();selectPortRef(selectedPortInfo()||info);
});
barPortAccess.addEventListener('change',()=>{
  const info=selectedPortInfo();if(!info||mutationBlocked(info.owner,'Change Port access'))return;setHistoryHint('Change Port access');
  normalizePortConnections(info.port);
  const connection=info.port.connections[info.port.activeConnection];
  connection.access=barPortAccess.value;
  componentConfig(info.owner);
  render();selectPortRef(selectedPortInfo()||info);scheduleHistoryCapture();
});
barPortLabel.addEventListener('input',()=>{
  const info=selectedPortInfo();if(!info||mutationBlocked(info.owner,'Edit Port label'))return;setHistoryHint('Edit Port label');
  info.port.label=barPortLabel.value.slice(0,24);
  componentConfig(info.owner);
  render();selectPortRef(selectedPortInfo()||info,{focus:false});
});
barPortColorSlot.addEventListener('click',()=>openColorSlotPanel('port'));
function deleteSelected(){
  cancelWireDrag();
  if(!selected)return;
  // Flush any pending edit first so deletion always has a distinct pre-delete snapshot.
  commitHistoryCapture();

  if(typeof selected==='string'&&selected.startsWith('wire:')){
    const i=Number(selected.split(':')[1]);
    if(Number.isInteger(i)&&i>=0&&i<wires.length){if(isEntityLocked(wires[i])){statusEl.textContent='Locked · delete refused';return}setHistoryHint('Delete Wire');SovSchematicData.remove(diagram,'wire',wires[i].id)}
  }else if(isAttachmentSelectionValue(selected)){
    // Canonical attachment points are structural topology of the current host form.
    // Delete does not silently change dimensional cardinality.
    statusEl.textContent='Attachment point is structural';
    return;
  }else{
    const ids=selectedComponentIds.size?[...selectedComponentIds]:[selected];
    const targets=ids.map(id=>nodes.find(n=>n.id===id)).filter(Boolean);
    if(targets.some(isEntityLocked)){statusEl.textContent='Locked · delete refused';return}
    setHistoryHint(targets.length>1?'Delete selection':'Delete Component');
    for(const root of targets.filter(n=>!targets.some(other=>other.id!==n.id&&isDescendantOf(n.id,other.id))))SovSchematicData.remove(diagram,'component',root.id);
    clearComponentSelectionSet();syncAllNodeBoundaryContext();
  }

  routeCache.clear();arrowPoseCache.clear();dragRouteSnapshots.clear();
  selected=null;hideSelectionBar();refreshCanvasScopeControl();render();selectNode(null);commitHistoryCapture();
}

barFormState.addEventListener('click',()=>{
  const kind=selectedSurfaceKind();
  if(kind==='component'){
    openSelectionSettings('component');formSettings.open=true;formSettings.scrollIntoView({block:'nearest'});
  }else if(kind==='wire'){
    openSelectionSettings('wire');wireSettingsFields.scrollIntoView({block:'nearest'});
  }
});
function updateSelectedComponentForm(mutator){
  const n=nodes.find(n=>n.id===selected);if(!n||mutationBlocked(n,'Form edit'))return;setHistoryHint('Edit Component Form');
  const f=componentForm(n),beforeOpen=f.regions.interior.state==='open',beforeDimension=f.dimension;mutator(f,n);
  if(f.dimension<2)f.regions.interior.state='closed';componentForm(n);
  if(beforeOpen&&f.regions.interior.state==='closed'){
    const fallback=n.canvasId||GLOBAL_CANVAS_ID;
    for(const child of nodes.filter(q=>parentComponent(q)?.id===n.id)){child.canvasId=fallback;child.parentId=canvasOwnerComponentId(fallback);syncNodeBoundaryContext(child)}
  }
  if(beforeDimension!==f.dimension)SovSchematicData.reconcileComponentWirePorts(diagram,n.id);
  componentConfig(n);
  routeCache.clear();arrowPoseCache.clear();render();selectNode(n.id,{focus:false});scheduleHistoryCapture();
}
formSection.addEventListener('change',()=>updateSelectedComponentForm(f=>{const v=formSection.value;if(v==='derived')delete f.section;else if(v!=='custom')f.section=SovSchematicData.sectionPreset(v,2)}));
barWireSection?.addEventListener('change',()=>{
  const w=mutableSelectedConnection('Wire section');if(!w)return;const v=barWireSection.value;
  if(!w.form||typeof w.form!=='object')w.form={dimension:1};
  if(v==='line')delete w.form.section;else if(v!=='custom')w.form.section=SovSchematicData.sectionPreset(v,1);
  routeCache.clear();renderWires();const i=wires.indexOf(w);selectWire(i,{focus:false});scheduleHistoryCapture();
});
formDimension.addEventListener('change',()=>updateSelectedComponentForm(f=>{f.dimension=Number(formDimension.value);f.body.kind=['point','path','surface'][f.dimension]}));
formAttachments.addEventListener('change',()=>{
  // Built-in 2D points are template defaults. Turning them off is refused while a Wire
  // still ends on one, so the change never silently orphans a carrier.
  const n=nodes.find(n=>n.id===selected);if(!n||mutationBlocked(n,'Attachment defaults edit'))return;
  const next=formAttachments.value==='none'?'none':'standard';
  if(next==='none'&&Attachment.attachmentDefaults(n)!=='none'&&wiresOnBuiltinPoints(n).length){formAttachments.value=Attachment.attachmentDefaults(n);statusEl.textContent='Detach Wires from built-in points first';return}
  setHistoryHint('Change attachment defaults');
  if(next==='none')n.config.attachmentDefaults='none';else delete n.config.attachmentDefaults;
  SovSchematicData.reconcileComponentWirePorts(diagram,n.id);componentConfig(n);
  routeCache.clear();arrowPoseCache.clear();render();selectNode(n.id,{focus:false});scheduleHistoryCapture();
});
formMaterial.addEventListener('change',()=>updateSelectedComponentForm(f=>{f.body.material=formMaterial.value}));
formBodyThickness.addEventListener('change',()=>updateSelectedComponentForm(f=>{f.body.thickness=Math.max(0,Number(formBodyThickness.value)||0)}));
formInteriorState.addEventListener('change',()=>updateSelectedComponentForm(f=>{f.regions.interior.state=formInteriorState.value}));
formFrameMode.addEventListener('change',()=>updateSelectedComponentForm(f=>{f.frame.mode=formFrameMode.value;if(f.frame.mode!=='none'&&!f.frame.thickness)f.frame.thickness=12}));
formFrameThickness.addEventListener('change',()=>updateSelectedComponentForm(f=>{f.frame.thickness=Math.max(0,Number(formFrameThickness.value)||0)}));
formFrameDepth.addEventListener('change',()=>updateSelectedComponentForm(f=>{f.frame.depth=Math.max(0,Number(formFrameDepth.value)||0)}));
barSelectionSettings.addEventListener('click',()=>{
  const kind=selectedSurfaceKind();if(!kind)return;
  if(selectionSettingsPanel.hidden)openSelectionSettings(kind);else closeSelectionSettings();
});
barDeleteSelection.addEventListener('click',deleteSelected);


function selectedConnection(){
  if(typeof selected!=='string'||!selected.startsWith('wire:'))return null;
  return wires[Number(selected.split(':')[1])]||null;
}
function mutableSelectedConnection(label='Wire edit'){const w=selectedConnection();if(!w||mutationBlocked(w,label))return null;setHistoryHint(label);return w}
barConnectionDirection.addEventListener('change',()=>{
  const w=mutableSelectedConnection('Change Wire direction');if(!w)return;
  const cfg=connectionConfig(w);cfg.direction=barConnectionDirection.value;w.duplex=cfg.direction==='duplex';if(w.duplex)ensureDuplexEndpointFlows(w);
  arrowPoseCache.clear();render();
  const i=Number(selected.split(':')[1]);selectWire(i);scheduleHistoryCapture();
});
barConnectionReciprocity.addEventListener('change',()=>{
  const w=mutableSelectedConnection('Change Wire reciprocity');if(!w)return;
  connectionConfig(w).reciprocity=barConnectionReciprocity.value;renderWires();
  const i=Number(selected.split(':')[1]);selectWire(i);scheduleHistoryCapture();
});
barWirePrimaryOperation.addEventListener('change',()=>{
  const w=mutableSelectedConnection('Change packet operation');if(!w)return;
  const cfg=connectionConfig(w);
  const key=cfg.direction==='reverse'?'reverseOperation':'forwardOperation';
  cfg[key]=barWirePrimaryOperation.value;renderWires();
  const i=Number(selected.split(':')[1]);selectWire(i);scheduleHistoryCapture();
});
barWireReturnOperation.addEventListener('change',()=>{
  const w=mutableSelectedConnection('Change return packet operation');if(!w)return;
  const cfg=connectionConfig(w);
  const key=cfg.direction==='reverse'?'forwardOperation':'reverseOperation';
  cfg[key]=barWireReturnOperation.value;renderWires();
  const i=Number(selected.split(':')[1]);selectWire(i);scheduleHistoryCapture();
});
barAddWirePortBtn.addEventListener('click',()=>{
  const w=mutableSelectedConnection('Add attachment point');if(!w)return;
  const cfg=connectionConfig(w),hosted=nodes.filter(n=>(n.canvasId||GLOBAL_CANVAS_ID)===wireCanvas(w).id&&componentForm(n).dimension===0);
  const offsets=[0,.14,-.14,.28,-.28,.38,-.38],t=Math.max(.08,Math.min(.92,.5+(offsets[hosted.length]??0)));
  const channel=wireOutConnection(w),path=renderedWirePath(w);let x=0,y=0;
  if(path){const q=path.getPointAtLength(path.getTotalLength()*t);x=q.x;y=q.y}
  const ports={out:{side:'point',face:'external',label:'',connectionCount:1,activeConnection:0,connections:[{id:'connection-1',colorSlot:channel.colorSlot,flow:cfg.direction==='duplex'?'duplex':'out',access:'read-write'}]}};
  // A Wire tap is an ordinary Point primitive hosted by the Wire; the preset supplies its 0D Form.
  const point=SovSchematicData.makeComponent(diagram,{symbolId:'point',x,y,canvasId:wireCanvas(w).id,placement:{kind:'wire',wireId:w.id,t},config:{colorSlot:channel.colorSlot,ports}});
  nodes.push(point);syncNodeBoundaryContext(point);render();selectPort(point.id,'self');scheduleHistoryCapture();statusEl.textContent='Point added to Wire';
});
barConnectionLabel.addEventListener('input',()=>{
  const w=mutableSelectedConnection('Edit Wire label');if(!w)return;
  connectionConfig(w).label=barConnectionLabel.value;refreshCanvasScopeControl();renderWires();
  const i=Number(selected.split(':')[1]);
  cLabel.textContent=barConnectionLabel.value||'—';
  positionSelectionBar();
});
barWireOutMarker.addEventListener('input',()=>{
  const w=selectedConnection();if(!w)return;
  const io=wireIOEnds(w);
  connectionConfig(w)[io.out==='a'?'aChannelMarker':'bChannelMarker']=normalizeChannelMarker(barWireOutMarker.value,'1');
  renderWires();
  const i=Number(selected.split(':')[1]);selectWire(i,{focus:false});scheduleHistoryCapture();
});
barWireInMarker.addEventListener('input',()=>{
  const w=selectedConnection();if(!w)return;
  const io=wireIOEnds(w);
  connectionConfig(w)[io.in==='a'?'aChannelMarker':'bChannelMarker']=normalizeChannelMarker(barWireInMarker.value,'1');
  renderWires();
  const i=Number(selected.split(':')[1]);selectWire(i,{focus:false});scheduleHistoryCapture();
});

// Access: who a component acts as, and a plane's access list (GRAPH-MODEL.md, access control).
// Edits are ordinary config edits: one history step, refused on a locked component.
const ACL_OPS_UI=['enter','exit','read','write'];
function updateSelectedComponentConfig(label,mutator){
  const n=nodes.find(n=>n.id===selected);if(!n||mutationBlocked(n,label))return;setHistoryHint(label);
  mutator(componentConfig(n),n);render();selectNode(n.id,{focus:false});scheduleHistoryCapture();
  openSelectionSettings('component');syncComponentVisualPanel(n);
}
function syncAccessPanel(n){
  const cfg=componentConfig(n),f=componentForm(n),plane=f.dimension===2&&f.regions.interior.state==='open';
  accessPrincipal.value=typeof cfg.principal==='string'?cfg.principal:'';
  accessAclBlock.hidden=!plane;
  const acl=cfg.acl&&typeof cfg.acl==='object'?cfg.acl:null;
  accessAclMode.value=acl?(acl.default==='allow'?'allow':'deny'):'none';
  accessAddEntry.hidden=!acl;
  accessEntries.replaceChildren();
  if(acl?.entries?.length){
    const head=document.createElement('div');head.className='access-entry access-head';
    for(const t of ['principal',...ACL_OPS_UI,'']){const s=document.createElement('span');s.textContent=t;head.appendChild(s)}
    accessEntries.appendChild(head);
  }
  for(const [i,e] of (acl?.entries||[]).entries()){
    const row=document.createElement('div');row.className='access-entry';
    const who=document.createElement('input');who.type='text';who.value=e.principal||'';who.placeholder='principal';who.spellcheck=false;who.setAttribute('aria-label','Principal pattern');
    who.addEventListener('change',()=>updateSelectedComponentConfig('Edit access list',c=>{c.acl.entries[i].principal=who.value.trim()}));
    row.appendChild(who);
    for(const op of ACL_OPS_UI){
      const sel=document.createElement('select');sel.title=op;sel.setAttribute('aria-label',`${op} for ${e.principal||'principal'}`);
      for(const [v,t,title] of [['','·','not stated'],['allow','✓','allow'],['deny','✗','deny']]){const o=document.createElement('option');o.value=v;o.textContent=t;o.title=`${op}: ${title}`;sel.appendChild(o)}
      sel.value=(e.deny||[]).includes(op)?'deny':(e.allow||[]).includes(op)?'allow':'';sel.dataset.state=sel.value||'none';
      sel.addEventListener('change',()=>updateSelectedComponentConfig('Edit access list',c=>{const en=c.acl.entries[i];en.allow=(en.allow||[]).filter(x=>x!==op);en.deny=(en.deny||[]).filter(x=>x!==op);if(sel.value)en[sel.value].push(op)}));
      row.appendChild(sel);
    }
    const del=document.createElement('button');del.type='button';del.className='btn';del.textContent='×';del.title='Remove this principal';
    del.addEventListener('click',()=>updateSelectedComponentConfig('Edit access list',c=>{c.acl.entries.splice(i,1)}));row.appendChild(del);
    accessEntries.appendChild(row);
  }
}
accessPrincipal.addEventListener('change',()=>updateSelectedComponentConfig('Edit principal',c=>{const v=accessPrincipal.value.trim();if(v)c.principal=v;else delete c.principal}));
accessAclMode.addEventListener('change',()=>updateSelectedComponentConfig('Edit access list',c=>{
  const v=accessAclMode.value;if(v==='none'){delete c.acl;return}
  c.acl=c.acl&&typeof c.acl==='object'?c.acl:{entries:[]};c.acl.default=v;if(!Array.isArray(c.acl.entries))c.acl.entries=[];
}));
accessAddEntry.addEventListener('click',()=>updateSelectedComponentConfig('Edit access list',c=>{c.acl.entries.push({principal:'',allow:['enter'],deny:[]})}));
