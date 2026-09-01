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
  const kind=selectedSurfaceKind();if(kind!=='component')return;
  openSelectionSettings('component');formSettings.open=true;formSettings.scrollIntoView({block:'nearest'});
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
formDimension.addEventListener('change',()=>updateSelectedComponentForm(f=>{f.dimension=Number(formDimension.value);f.body.kind=['point','path','surface'][f.dimension]}));
formBodyKind.addEventListener('change',()=>updateSelectedComponentForm(f=>{f.body.kind=formBodyKind.value;f.dimension={point:0,path:1,surface:2}[f.body.kind]??2}));
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
  const ports={out:{side:'point',face:'external',label:'',connectionCount:1,activeConnection:0,connections:[{id:'connection-1',name:'Connection 1',colorSlot:channel.colorSlot,flow:cfg.direction==='duplex'?'duplex':'out',access:'read-write'}]}};
  const point=SovSchematicData.makeComponent(diagram,{symbolId:'port',x,y,canvasId:wireCanvas(w).id,placement:{kind:'wire',wireId:w.id,t},form:{dimension:0,body:{kind:'point',material:'generic',thickness:0},frame:{mode:'none',thickness:0,depth:0},regions:{interior:{state:'closed'}}},config:{label:'',colorSlot:channel.colorSlot,signalMode:'relay',presentation:{graphic:{kind:'none',ref:'sym-port',svg:''},labelMode:'none',backdrop:'none'},ports}});
  nodes.push(point);syncNodeBoundaryContext(point);render();selectPort(point.id,'self');scheduleHistoryCapture();statusEl.textContent='Attachment point added';
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
