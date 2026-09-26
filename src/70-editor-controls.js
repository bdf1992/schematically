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
// Direction and label are the port's own values, written as the Ports panel writes them (see
// setComponentPortFlow / setComponentPortLabel below). A 1D endpoint declares nothing, so only its
// contract changes there.
barPortFlow.addEventListener('change',()=>{
  const info=selectedPortInfo();if(!info)return;
  setComponentPortFlow(info.owner,info.pointId,barPortFlow.value,reselectPort(info));
});
barPortAccess.addEventListener('change',()=>{
  const info=selectedPortInfo();if(!info||mutationBlocked(info.owner,'Change Port access'))return;setHistoryHint('Change Port access');
  normalizePortConnections(info.port);
  const connection=info.port.connections[info.port.activeConnection];
  connection.access=barPortAccess.value;
  componentConfig(info.owner);
  render();selectPortRef(selectedPortInfo()||info);scheduleHistoryCapture();
});
// The bar's label commits once, when it is left (Tab, Enter, or a click elsewhere, even one that
// changes the selection), to the port it was editing: the target is captured when editing starts.
let barLabelEdit=null;
function barLabelTarget(){const info=selectedPortInfo();return info?{componentId:info.owner.id,pointId:info.pointId,value:null}:null}
function commitBarLabel(){
  const edit=barLabelEdit;barLabelEdit=null;if(!edit||edit.value===null)return;
  const n=nodes.find(x=>x.id===edit.componentId);if(!n){statusEl.textContent=`Port edit dropped: ${edit.componentId} no longer exists`;return}
  setComponentPortLabel(n,edit.pointId,edit.value,ok=>{const again=selectedPortInfo();if(again&&again.owner.id===n.id&&again.pointId===edit.pointId)selectPortRef(again,{focus:false})});
}
barPortLabel.addEventListener('focus',()=>{barLabelEdit=barLabelTarget()});
barPortLabel.addEventListener('input',()=>{if(!barLabelEdit)barLabelEdit=barLabelTarget();if(barLabelEdit)barLabelEdit.value=barPortLabel.value});
barPortLabel.addEventListener('change',commitBarLabel);
barPortLabel.addEventListener('blur',commitBarLabel);
// No port edit is pending when another handler runs: a pointerdown anywhere but the focused port
// field (the panel's or the bar's label) blurs it first, in the capture phase, so its edit commits
// (its change, and the bar label's blur) before the click can change the selection, start a drag,
// undo, save or delete.
window.addEventListener('pointerdown',e=>{
  const field=document.activeElement;
  if(!field||field===e.target||field.contains?.(e.target))return;
  if(field===barPortLabel||portsList.contains(field))field.blur();
  if(barLabelEdit)commitBarLabel();
},true);
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
    // A deleted Component's interior falls back to its canvas: the hosting concern (30-canvas.js)
    // checks every Component that would fall back before anything is deleted.
    const roots=targets.filter(n=>!targets.some(other=>other.id!==n.id&&isDescendantOf(n.id,other.id)));
    const refusal=componentHostPlanRefusal(roots.flatMap(root=>componentFallbackPlan(root)).filter(step=>!roots.includes(step.node)));
    if(refusal){statusEl.textContent=refusal;return}
    setHistoryHint(targets.length>1?'Delete selection':'Delete Component');
    for(const root of roots)SovSchematicData.remove(diagram,'component',root.id);
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
  const n=nodes.find(n=>n.id===selected);if(!n||mutationBlocked(n,'Form edit'))return;
  // Everything is decided on a trial first. A Component bound to a definition keeps the ports the
  // definition gave it: a Form edit that would change them (a change of dimension) is refused by the
  // data core's owned-port rule. When the edit closes the interior, its Components fall back to this
  // Component's canvas, decided and checked by the hosting concern (30-canvas.js).
  const trial=SovSchematicData.clone(n);mutator(trial.form,trial);if(Number(trial.form.dimension)<2)trial.form.regions.interior.state='closed';
  const beforeOpen=componentForm(n).regions.interior.state==='open';
  const plan=beforeOpen&&trial.form.regions.interior.state==='closed'?componentFallbackPlan(n):[];
  try{
    if(componentDefinitionOwner(n))SovSchematicData.assertDefinitionPortsKept(n,{form:trial.form},trial);
    const refusal=componentHostPlanRefusal(plan);if(refusal)throw new Error(refusal);
  }catch(error){syncComponentVisualPanel(n);statusEl.textContent=error.message;return}
  setHistoryHint('Edit Component Form');
  const f=componentForm(n),beforeDimension=f.dimension;mutator(f,n);
  if(f.dimension<2)f.regions.interior.state='closed';componentForm(n);
  applyComponentHostPlan(plan);
  if(beforeDimension!==f.dimension)SovSchematicData.reconcileComponentWirePorts(diagram,n.id);
  componentConfig(n);
  routeCache.clear();arrowPoseCache.clear();render();selectNode(n.id,{focus:false});scheduleHistoryCapture();
}
formDimension.addEventListener('change',()=>updateSelectedComponentForm(f=>{f.dimension=Number(formDimension.value);f.body.kind=['point','path','surface'][f.dimension]}));
formAttachments.addEventListener('change',()=>{
  // Built-in 2D points are template defaults. Turning them off is refused while a Wire
  // still ends on one, so the change never silently orphans a carrier.
  const n=nodes.find(n=>n.id===selected);if(!n||mutationBlocked(n,'Attachment defaults edit'))return;
  const next=formAttachments.value==='none'?'none':'standard';
  if(next==='none'&&Attachment.attachmentDefaults(n)!=='none'&&wiresOnBuiltinPoints(n).length){formAttachments.value=Attachment.attachmentDefaults(n);statusEl.textContent='Detach Wires from built-in points first';return}
  // Any Wire the switch would orphan or leave between ports sharing no channel refuses it (data core).
  const trial=SovSchematicData.clone(n);if(next==='none')trial.config.attachmentDefaults='none';else delete trial.config.attachmentDefaults;
  try{SovSchematicData.assertDefinitionPortsKept(n,{config:{attachmentDefaults:next}},trial);SovSchematicData.assertWiresSurviveEdit(diagram,n,trial)}catch(error){formAttachments.value=Attachment.attachmentDefaults(n);statusEl.textContent=error.message;return}
  setHistoryHint('Change attachment defaults');
  // Choosing the template's ports where the Component's ports differ from them resets them.
  const differs=next==='standard'&&JSON.stringify(componentPortList(n).slice(0,SovSchematicData.templatePorts(n.symbolId).length))!==JSON.stringify(SovSchematicData.normalizeDeclaredPorts(SovSchematicData.templatePorts(n.symbolId)));
  if(next==='none')n.config.attachmentDefaults='none';else delete n.config.attachmentDefaults;
  SovSchematicData.reconcileComponentWirePorts(diagram,n.id);componentConfig(n);
  routeCache.clear();arrowPoseCache.clear();render();selectNode(n.id,{focus:false});scheduleHistoryCapture();
  if(differs)statusEl.textContent='Reset to template ports';
});
// --- Ports ------------------------------------------------------------------
// Every Ports edit sends the Component's complete port list through the data core's component
// update, which stores it in the smallest form and applies every refusal. One edit is one history
// transition; a refusal changes nothing, puts its message in the status line, and the rebuilt rows
// show the record as it still is. A port is moved only here (side, t): dragging a port starts a Wire.
function componentPortList(n){
  return Attachment.pointSpecs(n).map(spec=>{
    const port={id:spec.id};if(spec.compatId&&spec.compatId!==spec.id)port.compatId=spec.compatId;
    Object.assign(port,{side:spec.side,t:spec.t,flow:spec.flow,channels:SovSchematicData.clone(spec.channels||[{id:'main'}])});
    if(spec.label)port.label=spec.label;
    return port;
  });
}
// One component update from the port controls (panel or bar). An edit is never pending: the data
// change and its history transition happen now, inside the event that commits it. Only the refresh
// (render, the panel or bar rebuild, focus) waits for the event to finish, and it changes neither
// data nor history. `after` runs in that refresh; the default refreshes the Component's selection
// if it is still the one selected, and rebuilds its settings only if the panel is still open. The
// refresh never opens the panel: the click that committed the edit may be the one that closed it.
function applyComponentPortPatch(n,config,label,after=null){
  const showing=()=>selected===n.id; // this Component is still the one selected
  const panelOpen=()=>showing()&&!selectionSettingsPanel.hidden;
  const refreshPanel=()=>setTimeout(()=>{if(panelOpen())syncPortsPanel(nodes.find(x=>x.id===n.id)||n)},0);
  if(mutationBlocked(n,label)){refreshPanel();return false}
  commitHistoryCapture();
  const receipt=SovSchematicData.applyOperation(diagram,{schema:SovSchematicData.OPERATION_SCHEMA,id:`ports-${Date.now()}`,op:'update',resource:'component',resourceId:n.id,patch:{config}});
  if(!receipt.ok){statusEl.textContent=receipt.error?.message||'Port edit refused';refreshPanel();if(after)setTimeout(()=>after(false),0);return false}
  // The runtime projections as every CRUD edit makes them; the render waits for the refresh below.
  normalizeRuntimeAfterCrud({render:false});commitHistoryCapture(label);
  statusEl.textContent=label;
  setTimeout(()=>{render();if(after)after(true);else if(showing()){const open=panelOpen();selectNode(n.id,{focus:false});if(open)openSelectionSettings('component')}},0);
  return true;
}
function applyComponentPorts(n,ports,label,extraConfig=null,after=null){
  return applyComponentPortPatch(n,{...(extraConfig||{}),attachmentDefaults:'none',attachmentPoints:ports},label,after);
}
function reselectPort(info){return ()=>{const again=selectedPortInfo();if(again)selectPortRef(again,{focus:false})}}
function selectedPortsComponent(){const n=nodes.find(x=>x.id===selected);return componentPortsEditable(n)?n:null}
function editComponentPort(n,portId,mutate,label,extraConfig=null,after=null){
  if(!componentPortsEditable(n))return false;
  const ports=componentPortList(n),port=ports.find(p=>p.id===portId);if(!port){setTimeout(()=>{if(selected===n.id)syncPortsPanel(n)},0);return false}
  mutate(port,ports);
  return applyComponentPorts(n,ports.filter(p=>!p.removed),label,extraConfig,after);
}
// The port contract (`config.ports[compatId]`) holds what the canvas draws: the label, and the flow
// of its active connection, which reads `in | out | duplex | control` (a `trigger` port is drawn
// as `control`, the receiving flow it is closest to).
function portContractMirror(n,spec,{label,flow}={}){
  const contract=n.config?.ports?.[spec.compatId]||{},mirror={};
  if(label!==undefined)mirror.label=label;
  if(flow!==undefined&&Array.isArray(contract.connections)&&contract.connections.length){
    const connections=SovSchematicData.clone(contract.connections),i=Math.max(0,Math.min(connections.length-1,Number(contract.activeConnection)||0));
    connections[i].flow=flow==='trigger'?'control':flow;mirror.connections=connections;
  }
  return {ports:{[spec.compatId]:mirror}};
}
// A Point's `self` declaration with one field changed (the data core stores it in its clean form).
function pointSelfList(n,change){
  const declared=Attachment.selfDeclaration(n)||{id:'self',channels:[{id:'main'}]};
  return [{id:'self',...(declared.flow?{flow:declared.flow}:{}),channels:SovSchematicData.clone(declared.channels),...change}];
}
// One flow: the declared `flow`, with the contract's drawn flow mirrored in the same update.
function setComponentPortFlow(n,pointId,flow,after=null){
  const spec=Attachment.resolveSpec(n,pointId);if(!spec)return false;
  const mirror=portContractMirror(n,spec,{flow});
  if(Attachment.effectiveDimension(n)===2)return editComponentPort(n,spec.id,port=>{port.flow=flow},'Change port flow',mirror,after);
  if(Attachment.intrinsicDimension(n)===0)return applyComponentPortPatch(n,{...mirror,attachmentPoints:pointSelfList(n,{flow})},'Change port flow',after);
  // A Path end's direction is its role (start receives, end emits); it is not a setting.
  statusEl.textContent=PATH_END_FLOW_TITLE;return false;
}
// One label: the declared `label` and the drawn label, written together. A Point's `self` and a 1D
// endpoint declare no label, so only the drawn label is theirs.
function setComponentPortLabel(n,pointId,value,after=null){
  const spec=Attachment.resolveSpec(n,pointId);if(!spec)return false;
  const label=String(value||'').slice(0,24),mirror=portContractMirror(n,spec,{label});
  if(Attachment.effectiveDimension(n)===2)return editComponentPort(n,spec.id,port=>{if(label)port.label=label;else delete port.label},'Relabel port',mirror,after);
  return applyComponentPortPatch(n,mirror,'Relabel port',after);
}
function portChannelsFromText(text,before){
  const kept=new Map((before||[]).map(c=>[c.id,c]));
  return String(text||'').split(',').map(x=>x.trim()).filter(Boolean).map(id=>kept.has(id)?SovSchematicData.clone(kept.get(id)):{id});
}
portsList.addEventListener('change',e=>{
  const row=e.target.closest('.ports-row');if(!row)return;
  // The edit's target is bound now, when the change fires: the row's own Component and port.
  const componentId=row.dataset.componentId,portId=row.dataset.portId,el=e.target,value=el.value;
  // A change fires as focus leaves the field (Tab, Shift+Tab, a click; a click elsewhere blurs it
  // first, see below). The edit applies now, to the bound target; the rebuilt rows come after focus
  // has landed, so they put it back on the control that was about to receive it.
  const n=nodes.find(x=>x.id===componentId);
  if(!n){statusEl.textContent=`Port edit dropped: ${componentId} no longer exists`;return}
  if(el.classList.contains('port-label'))setComponentPortLabel(n,portId,value);
  else if(el.classList.contains('port-side'))editComponentPort(n,portId,port=>{port.side=value},'Move port');
  else if(el.classList.contains('port-t'))editComponentPort(n,portId,port=>{port.t=value.trim()===''?null:Number(value)},'Move port');
  else if(el.classList.contains('port-flow'))setComponentPortFlow(n,portId,value);
  else if(el.classList.contains('port-channels'))editComponentPort(n,portId,port=>{port.channels=portChannelsFromText(value,port.channels)},'Change port channels');
});
portsList.addEventListener('click',e=>{
  const button=e.target.closest('.port-remove');if(!button||button.disabled)return;
  const target=button.closest('.ports-row'),n=nodes.find(x=>x.id===target.dataset.componentId);if(!n)return;
  editComponentPort(n,target.dataset.portId,port=>{port.removed=true},'Remove port');
});
// A new port: id p1, p2, ... (the first free), on the right, at the first free position of
// .5, .25, .75, .125, .375, .625, .875 on that side; once those are used, at the midpoint of the
// largest free gap on that side (between its ports and the ends 0 and 1; ties to the lowest t).
// Duplex, on the main channel.
const NEW_PORT_POSITIONS=[.5,.25,.75,.125,.375,.625,.875];
function largestGapMidpoint(ts){
  const edges=[0,...[...new Set(ts)].sort((a,b)=>a-b),1];let best=null;
  for(let i=1;i<edges.length;i++){const gap=edges[i]-edges[i-1];if(!best||gap>best.gap+1e-12)best={gap,t:(edges[i]+edges[i-1])/2}}
  return best.t;
}
function newPortFor(ports){
  const taken=new Set(ports.flatMap(p=>[p.id,p.compatId||p.id]));
  let i=1;while(taken.has(`p${i}`))i++;
  const ts=ports.filter(p=>p.side==='right').map(p=>p.t),used=new Set(ts);
  return {id:`p${i}`,side:'right',t:NEW_PORT_POSITIONS.find(t=>!used.has(t))??largestGapMidpoint(ts),flow:'duplex',channels:[{id:'main'}]};
}
portsAddBtn.addEventListener('click',()=>{
  const n=selectedPortsComponent();if(!n||portsAddBtn.disabled)return;
  const ports=componentPortList(n),port=newPortFor(ports);
  applyComponentPorts(n,[...ports,port],'Add port');
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
