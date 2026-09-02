'use strict';
// 0.1 Beta concern: Selection state projected into contextual UI and inspector.

function hideInspectorKinds(){componentDetail.hidden=true;connectionDetail.hidden=true;portDetail.hidden=true}
function selectNode(id,{focus=true,additive=false,toggle=false,preserveSet=false}={}){
  clearEndpointFocus();
  if(!preserveSet){
    if(!id)clearComponentSelectionSet();
    else if(additive){
      if(toggle&&selectedComponentIds.has(id)){selectedComponentIds.delete(id);if(selected===id)selected=[...selectedComponentIds].at(-1)||null}
      else {selectedComponentIds.add(id);selected=id}
    }else{selectedComponentIds.clear();selectedComponentIds.add(id);selected=id}
  }else selected=id;
  if(id&&focus)activateCanvasKeyboard();
  document.querySelectorAll('.node').forEach(el=>el.classList.toggle('selected',selectedComponentIds.has(el.dataset.id)));
  document.querySelectorAll('.wire').forEach(el=>el.classList.remove('selected'));document.querySelectorAll('.port').forEach(el=>el.classList.remove('port-selected'));
  const n=nodes.find(n=>n.id===selected);
  document.getElementById('emptyInspector').hidden=!!n;
  hideInspectorKinds();
  if(!n){hideSelectionBar();renderObjectsPanel?.();return}

  componentDetail.hidden=false;
  ensureComponentStructure(n);
  const s=byId(n.symbolId);
  iName.textContent=n.boundary.inside.type?s.name:'UNTYPED';
  iOutside.textContent=n.boundary.outside.type;
  {const host=componentHostDescriptor(n);iParent.textContent=host?.ownerKind==='wire'?`Wire · ${host.label||host.ownerId}`:componentDisplayName(parentComponent(n));}
  iScope.textContent=componentScopePath(n);
  iBoundary.textContent=n.boundary.shape;
  iFamily.textContent=s.family;iSignalMode.textContent=componentSignalLabel(componentConfig(n).signalMode);iClass.textContent=s.diagram_class;iMeaning.textContent=s.meaning;
  iVerbs.innerHTML=s.verbs.map(v=>`<span class="pill">${v}</span>`).join('');
  iProps.innerHTML=s.properties.map(v=>`<span class="pill">${v}</span>`).join('');
  {const f=componentForm(n);iForm.textContent=formDimensionLabel(f);iBody.textContent=`${f.body.material} · thickness ${f.body.thickness}`;iFrame.textContent=f.frame.mode==='none'?'None':`${f.frame.mode} · thickness ${f.frame.thickness} · depth ${f.frame.depth}`;iContains.textContent=f.regions.interior.state==='open'?'Open · hosts Components':'Closed';}
  showComponentBar(n);
}
function selectPortRef(info,{focus=true}={}){
  if(!info)return;clearComponentSelectionSet();
  if(focus)activateCanvasKeyboard();
  if(info.ownerKind!=='component')return;
  const point=Attachment.resolveSpec(info.owner,info.pointId||info.portId);if(point){info.pointId=point.id;info.portId=point.compatId;info.port=componentConfig(info.owner).ports[point.compatId]}
  selected=`point:component:${info.owner.id}:${info.pointId||info.portId}`;

  document.querySelectorAll('.node').forEach(el=>el.classList.remove('selected'));
  document.querySelectorAll('.wire').forEach(el=>el.classList.remove('selected'));
  document.querySelectorAll('.port').forEach(el=>el.classList.remove('port-selected'));

  const vis=document.querySelector(`.node[data-id="${info.owner.id}"] .port[data-port="${info.portId}"]`);
  if(vis)vis.classList.add('port-selected');

  document.getElementById('emptyInspector').hidden=true;
  hideInspectorKinds();portDetail.hidden=false;

  normalizePortChannels(info.port);
  const ch=portConnection(info.port);
  pOwner.textContent=portDisplayName(info);
  pId.textContent=info.portId;
  pSide.textContent=info.point?.side||Attachment.resolveSpec(info.owner,info.pointId)?.side||'point';
  pFace.textContent=info.port.face||'external';
  pLabel.textContent=info.port.label||'—';
  pChannelCount.textContent=portMarkerSummaryText(info);
  pChannel.textContent=ch.name;
  pFlow.textContent=portFlowLabel(ch.flow);
  pAccess.textContent=portAccessLabel(ch.access);
  pColor.textContent=`${slotLabel(ch.colorSlot)} · ${ch.color}`;
  showPortBar(info);
}
function selectPort(nodeId,pointId){
  const node=nodes.find(n=>n.id===nodeId);if(!node)return;
  const point=Attachment.resolveSpec(node,pointId);if(!point)return;
  const port=componentConfig(node).ports[point.compatId];if(!port)return;
  selectPortRef({ownerKind:'component',owner:node,node,pointId:point.id,portId:point.compatId,port});
}

function selectWire(i,{focus=true}={}){
  clearComponentSelectionSet();selected=`wire:${i}`;
  if(focus)activateCanvasKeyboard();
  document.querySelectorAll('.node').forEach(el=>el.classList.remove('selected'));document.querySelectorAll('.port').forEach(el=>el.classList.remove('port-selected'));
  document.querySelectorAll('.wire').forEach((el,j)=>el.classList.toggle('selected',j===i));
  document.getElementById('emptyInspector').hidden=true;
  hideInspectorKinds();

  const w=wires[i];
  if(!w){hideSelectionBar();return}
  connectionDetail.hidden=false;
  const cfg=connectionConfig(w),epA=carrierEndpoint(w,'a'),epB=carrierEndpoint(w,'b');
  const endText=(ep,end)=>ep?.kind==='bound'?`${componentConfig(ep.node).label||byId(ep.node.symbolId).name}.${ep.pointId} · ch ${wireEndpointMarker(w,end)}`:ep?`free · ${Math.round(ep.pos.x)}, ${Math.round(ep.pos.y)}`:'—';
  cFrom.textContent=endText(epA,'a');
  cTo.textContent=endText(epB,'b');
  cEnds.textContent=`${epA?.kind==='bound'?'bound':'free'} → ${epB?.kind==='bound'?'bound':'free'}`;
  cDirection.textContent=cfg.direction;
  cReciprocity.textContent=cfg.reciprocity;
  cOperations.textContent=cfg.direction==='duplex'?`A→B ${wireOperationLabel(cfg.forwardOperation)} · B→A ${wireOperationLabel(cfg.reverseOperation)}`:`${wireOperationLabel(wireOperation(w,cfg.direction==='reverse'?'reverse':'forward'))}`;
  const io=wireIOEnds(w);
  const outConnection=endpointConnection(w,io.out);
  const inConnection=endpointConnection(w,io.in);
  cChannel.textContent=`ch ${wireEndpointMarker(w,io.out)} → ch ${wireEndpointMarker(w,io.in)}`;
  cColor.textContent=`${slotLabel(outConnection.colorSlot)} → ${slotLabel(inConnection.colorSlot)}`;
  cWireParts.textContent=String((w.attachments?.length||0)+nodes.filter(n=>(n.canvasId||GLOBAL_CANVAS_ID)===wireCanvas(w).id&&componentForm(n).dimension===0).length);
  cLabel.textContent=cfg.label||'—';
  focusWireEndpoints(w);
  showConnectionBar(w,i);
}
