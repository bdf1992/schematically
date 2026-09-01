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
  if(info.ownerKind==='component'){
    selected=`port:component:${info.owner.id}:${info.portId}`;
  }else{
    selected=`port:wire:${info.owner.id}:${info.portId}`;
  }

  document.querySelectorAll('.node').forEach(el=>el.classList.remove('selected'));
  document.querySelectorAll('.wire').forEach(el=>el.classList.remove('selected'));
  document.querySelectorAll('.port').forEach(el=>el.classList.remove('port-selected'));

  let vis=null;
  if(info.ownerKind==='component'){
    vis=document.querySelector(`.node[data-id="${info.owner.id}"] .port[data-port="${info.portId}"]`);
  }else{
    vis=document.querySelector(`.port[data-owner-kind="wire"][data-owner-id="${info.owner.id}"][data-port="${info.portId}"]`);
  }
  if(vis)vis.classList.add('port-selected');

  document.getElementById('emptyInspector').hidden=true;
  hideInspectorKinds();portDetail.hidden=false;

  normalizePortChannels(info.port);
  const ch=portConnection(info.port);
  pOwner.textContent=portDisplayName(info);
  pId.textContent=info.portId;
  pSide.textContent=info.ownerKind==='component'?info.port.side:`along wire · ${Math.round((info.part?.t??.5)*100)}%`;
  pFace.textContent=info.port.face||'external';
  pLabel.textContent=info.port.label||'—';
  pChannelCount.textContent=portMarkerSummaryText(info);
  pChannel.textContent=info.ownerKind==='component'?ch.name:`A ${wireEndpointMarker(info.owner,'a')} · B ${wireEndpointMarker(info.owner,'b')}`;
  pFlow.textContent=portFlowLabel(ch.flow);
  pAccess.textContent=portAccessLabel(ch.access);
  pColor.textContent=`${slotLabel(ch.colorSlot)} · ${ch.color}`;
  showPortBar(info);
}
function selectPort(nodeId,portId){
  const node=nodes.find(n=>n.id===nodeId);if(!node)return;
  const port=componentConfig(node).ports[portId];if(!port)return;
  selectPortRef({ownerKind:'component',owner:node,node,portId,port});
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
  const cfg=connectionConfig(w),a=nodes.find(n=>n.id===w.a),b=nodes.find(n=>n.id===w.b);
  cFrom.textContent=`${componentConfig(a).label||byId(a.symbolId).name}.${w.aSide} · ch ${wireEndpointMarker(w,'a')}`;
  cTo.textContent=`${componentConfig(b).label||byId(b.symbolId).name}.${w.bSide} · ch ${wireEndpointMarker(w,'b')}`;
  cDirection.textContent=cfg.direction;
  cReciprocity.textContent=cfg.reciprocity;
  cOperations.textContent=cfg.direction==='duplex'?`A→B ${wireOperationLabel(cfg.forwardOperation)} · B→A ${wireOperationLabel(cfg.reverseOperation)}`:`${wireOperationLabel(wireOperation(w,cfg.direction==='reverse'?'reverse':'forward'))}`;
  const io=wireIOEnds(w);
  const outConnection=endpointConnection(w,io.out);
  const inConnection=endpointConnection(w,io.in);
  cChannel.textContent=`ch ${wireEndpointMarker(w,io.out)} → ch ${wireEndpointMarker(w,io.in)}`;
  cColor.textContent=`${slotLabel(outConnection.colorSlot)} → ${slotLabel(inConnection.colorSlot)}`;
  cWireParts.textContent=String(w.attachments.length);
  cLabel.textContent=cfg.label||'—';
  focusWireEndpoints(w);
  showConnectionBar(w,i);
}
