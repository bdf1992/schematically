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
barPatternColorSlot.addEventListener('click',()=>openColorSlotPanel('pattern'));
barPatternLabel.addEventListener('input',()=>{
  const record=selectedPatternRecord();if(!record)return;
  renamePattern(record.id,barPatternLabel.value);
});
barPatternOpen.addEventListener('click',()=>{
  const record=selectedPatternRecord();
  if(record){togglePatternOpen(record.id);return}
  // Once open, a part is what is selected, so the button closes the Pattern it belongs to.
  const node=nodes.find(n=>n.id===selected);const group=patternOf(node);
  if(group)togglePatternOpen(group.id);
});
barPatternRelease.addEventListener('click',()=>{
  const record=selectedPatternRecord();if(!record)return;
  releasePattern(record.id);
});

function deleteSelected(){
  cancelWireDrag();
  if(!selected)return;
  // Flush any pending edit first so deletion always has a distinct pre-delete snapshot.
  commitHistoryCapture();

  if(typeof selected==='string'&&selected.startsWith('pattern:')){
    // Deleting a Pattern deletes the Pattern: the parts belong to it, so they go too.
    // RELEASE is the way to keep the forms and lose only the grouping.
    const record=selectedPatternRecord();
    if(record){
      const memberNodes=patternMemberNodes(record.id),memberWires=patternMemberWires(record.id);
      if([...memberNodes,...memberWires].some(isEntityLocked)){statusEl.textContent='Locked · delete refused';return}
      setHistoryHint(`Delete ${patternDisplayName(record)}`);
      for(const wire of memberWires)SovSchematicData.remove(diagram,'wire',wire.id);
      for(const root of memberNodes.filter(n=>!memberNodes.some(other=>other.id!==n.id&&isDescendantOf(n.id,other.id))))
        SovSchematicData.remove(diagram,'component',root.id);
      const index=patternRecords.findIndex(p=>p.id===record.id);
      if(index>=0)patternRecords.splice(index,1);
      openPatternIds.delete(record.id);
      clearComponentSelectionSet();syncAllNodeBoundaryContext();
    }
  }else if(typeof selected==='string'&&selected.startsWith('wire:')){
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

// The dimension control changes the dimension. Clicking steps up the ladder and
// wraps; shift steps back. The Form panel is still reachable from the gear, so this
// button no longer spends a click getting to a setting it can just be.
barFormState.addEventListener('click',event=>{
  if(selectedSurfaceKind()!=='component')return;
  const n=nodes.find(n=>n.id===selected);if(!n)return;
  const from=componentForm(n).dimension;
  const to=event.shiftKey?previousDimension(from):nextDimension(from);
  setSelectedComponentDimension(to);
});

// Retyping across dimensions changes which attachment points exist, so a Wire that
// ends on one that is about to disappear would be orphaned. Refuse instead, name the
// count, and leave the form alone: dropping a person's connections silently to honour
// a click on a dimension button is the worse of the two behaviours.
function setSelectedComponentDimension(dimension){
  const n=nodes.find(n=>n.id===selected);if(!n)return false;
  const current=componentForm(n).dimension;
  if(dimension===current)return true;
  const surviving=new Set(Attachment.pointIds({...n,form:{...componentForm(n),dimension}}));
  const orphaned=wiresOnComponent(n).filter(w=>{
    for(const end of ['a','b']){
      if(w[end]!==n.id)continue;
      const pointId=Attachment.pointId(n,end==='a'?w.aAttachment?.pointId||w.aSide:w.bAttachment?.pointId||w.bSide);
      if(pointId&&!surviving.has(pointId))return true;
    }
    return false;
  });
  if(orphaned.length){
    statusEl.textContent=`${dimension}D drops ${orphaned.length===1?'a point a Wire ends on':`points ${orphaned.length} Wires end on`} · detach first`;
    return false;
  }
  updateSelectedComponentForm(f=>{f.dimension=dimension;f.body.kind=['point','path','surface','volume'][dimension]});
  statusEl.textContent=`${dimension}D · ${DIMENSION_NAMES[dimension]}`;
  return true;
}
function updateSelectedComponentForm(mutator){
  const n=nodes.find(n=>n.id===selected);if(!n||mutationBlocked(n,'Form edit'))return;setHistoryHint('Edit Component Form');
  const f=componentForm(n),beforeOpen=f.regions.interior.state==='open',beforeDimension=f.dimension;mutator(f,n);
  if(f.dimension<SURFACE_DIMENSION)f.regions.interior.state='closed';componentForm(n);
  if(beforeOpen&&f.regions.interior.state==='closed'){
    const fallback=n.canvasId||GLOBAL_CANVAS_ID;
    for(const child of nodes.filter(q=>parentComponent(q)?.id===n.id)){child.canvasId=fallback;child.parentId=canvasOwnerComponentId(fallback);syncNodeBoundaryContext(child)}
  }
  if(beforeDimension!==f.dimension)SovSchematicData.reconcileComponentWirePorts(diagram,n.id);
  componentConfig(n);
  routeCache.clear();arrowPoseCache.clear();render();selectNode(n.id,{focus:false});scheduleHistoryCapture();
}
formDimension.addEventListener('change',()=>{
  // The select and the bar button are the same act, so they answer to the same rule.
  if(!setSelectedComponentDimension(Number(formDimension.value))){
    const n=nodes.find(n=>n.id===selected);if(n)formDimension.value=String(componentForm(n).dimension);
  }
});
pointsBuiltinToggle.addEventListener('click',()=>{
  // Built-in 2D points are template data. Removing them is refused while a Wire still
  // ends on one, so the change never silently orphans a carrier.
  const n=nodes.find(n=>n.id===selected);if(!n||mutationBlocked(n,'Built-in points edit'))return;
  const next=Attachment.attachmentDefaults(n)==='none'?'standard':'none';
  if(next==='none'&&wiresOnBuiltinPoints(n).length){statusEl.textContent='Detach Wires from built-in points first';return}
  setHistoryHint(next==='none'?'Remove built-in points':'Add built-in points');
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
