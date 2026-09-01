'use strict';
// 0.1 Beta concern: Contextual bars, palette controls, and UI projection helpers.

function closeSelectionSettings(){selectionSettingsPanel.hidden=true;barSelectionSettings?.setAttribute('aria-expanded','false')}
function hideSelectionBar(){selectionBar.hidden=true;closeSelectionSettings()}
let selectionBarSuppressed=false;
function setSelectionBarSuppressed(active){
  selectionBarSuppressed=!!active;
  const wrap=document.querySelector('.workspace-wrap');
  wrap?.classList.toggle('selection-bar-suppressed',selectionBarSuppressed);
  if(selectionBarSuppressed){
    closeSelectionSettings();
    closeColorSlotPanel();
  }
}
function restoreSelectionBarAfterGesture(){
  setSelectionBarSuppressed(false);
  if(selected)requestAnimationFrame(positionSelectionBar);
}
function slotLabel(slot){
  const s=normalizeSlot(slot);
  return s<6?`M${s+1}`:`C${s-5}`;
}
function setSlotChip(button,slot){
  const s=normalizeSlot(slot),color=slotColor(s);
  button.dataset.slot=slotLabel(s);
  button.style.setProperty('--slot-color',color);
  button.style.setProperty('--slot-label-color',relativeLuminance(color)>.52?'#171715':'#FFFFFF');
}
let slotEditTarget=null;
function closeColorSlotPanel(){colorSlotPanel.hidden=true;slotEditTarget=null}
function openColorSlotPanel(kind){
  slotEditTarget=kind;
  let current=6;
  if(kind==='component'){
    const n=nodes.find(n=>n.id===selected);if(!n)return;
    current=componentConfig(n).colorSlot;
  }else if(kind==='component-interior'){
    const n=nodes.find(n=>n.id===selected);if(!n)return;
    current=componentConfig(n).presentation.interiorColorSlot;
  }else if(kind==='port'){
    const info=selectedPortInfo();if(!info)return;
    current=portConnection(info.port).colorSlot;
  }

  colorSlotPanel.replaceChildren();

  const rows=[
    {label:'MONO',colors:activeMonoPalette(),offset:0},
    {label:'COLOR',colors:activeColorPalette(),offset:6}
  ];
  rows.forEach(row=>{
    const label=document.createElement('div');
    label.className='color-slot-row-label';
    label.textContent=row.label;
    colorSlotPanel.appendChild(label);

    row.colors.forEach((color,i)=>{
      const slot=row.offset+i;
      const b=document.createElement('button');
      b.type='button';
      b.className='color-slot-choice'+(slot===current?' selected':'');
      b.style.background=color;
      b.title=`${row.label} slot ${i+1}`;
      b.innerHTML=`<span>${i+1}</span>`;
      b.addEventListener('click',()=>applySelectedColorSlot(slot));
      colorSlotPanel.appendChild(b);
    });
  });

  colorSlotPanel.hidden=false;
}
function applySelectedColorSlot(slot){
  slot=normalizeSlot(slot);const entity=selectedUtilityEntity?.();if(entity&&mutationBlocked(entity,'color edit')){closeColorSlotPanel();return}setHistoryHint?.('Change color');
  if(slotEditTarget==='component'){
    const n=nodes.find(n=>n.id===selected);if(n)componentConfig(n).colorSlot=slot;
  }else if(slotEditTarget==='component-interior'){
    const n=nodes.find(n=>n.id===selected);if(n)componentConfig(n).presentation.interiorColorSlot=slot;
  }else if(slotEditTarget==='port'){
    const info=selectedPortInfo();
    if(info){
      const p=info.port;
      normalizePortConnections(p);
      p.connections[p.activeConnection].colorSlot=slot;
      p.connections[p.activeConnection].color=slotColor(slot);
      if(info.ownerKind==='component')componentConfig(info.owner);
      else wirePartPortConfig(info.owner,info.part);
    }
  }
  closeColorSlotPanel();
  refreshPaletteDerivedColors();
  render();
  restoreSelectedSurface();scheduleHistoryCapture?.();
}
function refreshPaletteDerivedColors(){
  nodes.forEach(n=>componentConfig(n));
  wires.forEach(w=>connectionConfig(w));
}
function renderPalettePreview(){
  monoPalettePreview.replaceChildren();
  palettePreview.replaceChildren();

  activeMonoPalette().forEach((c,i)=>{
    const s=document.createElement('span');
    s.style.background=c;
    s.title=`Mono ${i+1} · ${c}`;
    monoPalettePreview.appendChild(s);
  });

  activeColorPalette().forEach((c,i)=>{
    const s=document.createElement('span');
    s.style.background=c;
    s.title=`Color ${i+1} · ${c}`;
    palettePreview.appendChild(s);
  });

  customPaletteEditor.hidden=colorEngine.palette!=='custom';

}
function renderCustomPaletteEditor(){
  customPaletteSwatches.replaceChildren();
  colorEngine.custom.forEach((c,i)=>{
    const input=document.createElement('input');
    input.type='color';input.value=c;input.title=`Custom slot ${i+1}`;
    input.addEventListener('input',()=>{
      colorEngine.custom[i]=input.value;
      refreshPaletteDerivedColors();renderPalettePreview();render();restoreSelectedSurface();
    });
    customPaletteSwatches.appendChild(input);
  });
}
function applyColorEngine(){
  colorThemeInput.value=colorEngine.theme;
  colorPaletteInput.value=colorEngine.palette;
  diffuseSignalsInput.checked=colorEngine.diffuse;
  document.documentElement.style.setProperty('--canvas-tone',canvasTone());
  refreshPaletteDerivedColors();
  renderPalettePreview();renderCustomPaletteEditor();render();restoreSelectedSurface();
}
function setPalettePanel(open){
  paletteSettings.hidden=!open;
  paletteBtn.setAttribute('aria-expanded',String(open));
  paletteBtn.classList.toggle('active',open);
  if(open)setGridPanel(false);
}
function selectedCanvasContextId(){
  if(typeof selected==='string'&&selected.startsWith('wire:')){
    const w=wires[Number(selected.split(':')[1])];return w?.canvasId||GLOBAL_CANVAS_ID;
  }
  if(typeof selected==='string'&&selected.startsWith('port:')){
    const info=selectedPortInfo();
    if(info?.ownerKind==='component'){
      const node=info.owner,face=info.port.face||'external';
      return face==='internal'?componentCanvas(node).id:(node.canvasId||GLOBAL_CANVAS_ID);
    }
    if(info?.ownerKind==='wire')return info.owner.canvasId||GLOBAL_CANVAS_ID;
  }
  const n=nodes.find(n=>n.id===selected);return n?.canvasId||GLOBAL_CANVAS_ID;
}
function canvasContextLabel(canvasId){
  const d=canvasDescriptorById(canvasId)||canvasDescriptorById(GLOBAL_CANVAS_ID);
  if(d.scope==='global')return 'Global · 2D';
  return `${d.label} · ${d.dimension}D`;
}
function refreshCanvasScopeControl(){
  // Canvas is model state, not a persistent toolbar mode/readout.
}

function syncSelectionFormState(kind,entity){
  if(kind==='port'||!entity){barFormState.hidden=true;return}
  barFormState.hidden=false;barFormState.disabled=false;barFormState.classList.remove('wire-form');
  if(kind==='component'){
    const f=componentForm(entity);barFormState.textContent=`${f.dimension}D`;barFormState.title=`${formDimensionLabel(f)} · configure Form`;
    barFormState.classList.toggle('active',f.frame.mode!=='none'||f.regions.interior.state==='open');
  }else{
    barFormState.textContent='1D';barFormState.title='Wire Form · 1D path';barFormState.disabled=true;barFormState.classList.add('wire-form');
  }
}
function syncComponentVisualPanel(n){
  const p=componentConfig(n).presentation;
  visualGraphicMode.value=p.graphic.kind;visualLabelMode.value=p.labelMode;
  visualWidth.value=String(p.size.w);visualHeight.value=String(p.size.h);
  visualText.value=p.text;visualSvgMarkup.value=p.graphic.svg;visualSvgRow.hidden=p.graphic.kind!=='custom';
  setSlotChip(visualInteriorColor,p.interiorColorSlot);
  const f=componentForm(n);
  formDimension.value=String(f.dimension);formBodyKind.value=f.body.kind;formMaterial.value=f.body.material;formBodyThickness.value=String(f.body.thickness);
  formInteriorState.value=f.regions.interior.state;formFrameMode.value=f.frame.mode;formFrameThickness.value=String(f.frame.thickness);formFrameDepth.value=String(f.frame.depth);
}
function syncSelectionSettings(kind){
  if(typeof syncEntityUtilityPanel==='function')syncEntityUtilityPanel(kind);
  componentSettingsFields.hidden=kind!=='component';
  wireSettingsFields.hidden=kind!=='wire';
  portSettingsFields.hidden=kind!=='port';
  if(kind==='component'){
    const n=nodes.find(n=>n.id===selected);if(n){barComponentSignalMode.value=normalizeSignalMode(componentConfig(n));syncComponentVisualPanel(n)}
  }
}
function openSelectionSettings(kind){
  syncSelectionSettings(kind);
  selectionSettingsPanel.hidden=false;
  barSelectionSettings.setAttribute('aria-expanded','true');
}
function selectedSurfaceKind(){
  if(typeof selected==='string'&&selected.startsWith('wire:'))return 'wire';
  if(typeof selected==='string'&&selected.startsWith('port:'))return 'port';
  return selected?'component':null;
}
function showComponentBar(n){
  const cfg=componentConfig(n);
  selectionBar.hidden=false;
  componentBarFields.hidden=false;connectionBarFields.hidden=true;portBarFields.hidden=true;
  barComponentType.value=n.symbolId;
  barComponentLabel.value=cfg.label;
  setSlotChip(barComponentColorSlot,cfg.colorSlot);
  syncSelectionFormState('component',n);
  barComponentSignalMode.value=normalizeSignalMode(cfg);
  if(!selectionSettingsPanel.hidden)syncSelectionSettings('component');
  closeColorSlotPanel();
  positionSelectionBar();
}
function showConnectionBar(w,i){
  const cfg=connectionConfig(w);
  selectionBar.hidden=false;
  componentBarFields.hidden=true;connectionBarFields.hidden=false;portBarFields.hidden=true;
  barConnectionDirection.value=cfg.direction;
  barConnectionReciprocity.value=cfg.reciprocity;

  const io=wireIOEnds(w);
  const outConnection=endpointConnection(w,io.out);
  const inConnection=endpointConnection(w,io.in);

  if(cfg.direction==='duplex' || cfg.direction==='none'){
    barWireOutLabel.textContent='A';
    barWireInLabel.textContent='B';
  }else{
    barWireOutLabel.textContent='OUT';
    barWireInLabel.textContent='IN';
  }

  if(cfg.direction==='duplex'){
    barWirePrimaryOperationLabel.textContent='A→B operation';
    barWireReturnOperationLabel.textContent='B→A operation';
    barWirePrimaryOperation.value=cfg.forwardOperation;barWireReturnOperation.value=cfg.reverseOperation;
    barWirePrimaryOperation.disabled=false;barWireReturnOperation.disabled=false;
  }else if(cfg.direction==='reverse'){
    barWirePrimaryOperationLabel.textContent='OUT operation';barWireReturnOperationLabel.textContent='RETURN operation';
    barWirePrimaryOperation.value=cfg.reverseOperation;barWireReturnOperation.value=cfg.forwardOperation;
    barWirePrimaryOperation.disabled=false;barWireReturnOperation.disabled=true;
  }else{
    barWirePrimaryOperationLabel.textContent='OUT operation';barWireReturnOperationLabel.textContent='RETURN operation';
    barWirePrimaryOperation.value=cfg.forwardOperation;barWireReturnOperation.value=cfg.reverseOperation;
    barWirePrimaryOperation.disabled=cfg.direction==='none';barWireReturnOperation.disabled=true;
  }

  barWireOutMarker.value=wireEndpointMarker(w,io.out);
  barWireInMarker.value=wireEndpointMarker(w,io.in);
  setSlotChip(barWireOutColor,outConnection.colorSlot);
  setSlotChip(barWireInColor,inConnection.colorSlot);
  barConnectionLabel.value=cfg.label;
  syncSelectionFormState('wire',w);
  if(!selectionSettingsPanel.hidden)syncSelectionSettings('wire');
  closeColorSlotPanel();
  positionSelectionBar();
}

function selectedPortInfo(){
  if(typeof selected!=='string'||!selected.startsWith('port:'))return null;
  const parts=selected.split(':');
  if(parts[1]==='component'){
    const node=nodes.find(n=>n.id===parts[2]);if(!node)return null;
    const portId=parts[3],port=componentConfig(node).ports[portId];if(!port)return null;
    return {ownerKind:'component',owner:node,node,portId,port};
  }
  if(parts[1]==='wire'){
    const wire=wires.find(w=>w.id===parts[2]);if(!wire)return null;
    const part=wire.attachments.find(p=>p.id===parts[3]&&(p.type==='port'||p.kind==='port'));if(!part)return null;
    const port=wirePartPortConfig(wire,part);
    return {ownerKind:'wire',owner:wire,wire,part,portId:part.id,port};
  }

  // Legacy component Port selection format: port:<componentId>:<portId>
  const node=nodes.find(n=>n.id===parts[1]);
  if(node){
    const portId=parts[2],port=componentConfig(node).ports[portId];
    return port?{ownerKind:'component',owner:node,node,portId,port}:null;
  }
  return null;
}
function portMarkerSummaryText(info){
  if(info.ownerKind==='component'){
    const markers=wireMarkerSummaryForPort(info.owner.id,info.portId);
    return markers.length?markers.join(' · '):'No wire markers';
  }
  const w=info.owner;
  return `A ${wireEndpointMarker(w,'a')} · B ${wireEndpointMarker(w,'b')}`;
}
function showPortBar(info){
  const port=info.port;
  normalizePortChannels(port);

  selectionBar.hidden=false;
  syncSelectionFormState('port',null);
  componentBarFields.hidden=true;connectionBarFields.hidden=true;portBarFields.hidden=false;

  barPortSide.disabled=info.ownerKind==='wire';
  barPortSide.value=info.ownerKind==='wire'?'along':port.side;

  const ch=portConnection(port);
  barPortLabel.value=port.label||'';
  barPortFace.value=port.face||'external';
  barPortMarkers.textContent=portMarkerSummaryText(info);
  setSlotChip(barPortColorSlot,ch.colorSlot);
  barPortFlow.value=ch.flow;
  barPortAccess.value=ch.access;
  if(!selectionSettingsPanel.hidden)syncSelectionSettings('port');
  closeColorSlotPanel();
  positionSelectionBar();
}
function portDisplayName(info){
  if(info.ownerKind==='component'){
    return componentConfig(info.owner).label||byId(info.owner.symbolId).name;
  }
  return info.owner.config?.label||info.owner.id||'Wire';
}

function restoreSelectedSurface(){
  if(typeof selected!=='string')return;
  if(selected.startsWith('wire:')){
    const i=Number(selected.split(':')[1]);if(wires[i])selectWire(i);
  }else if(selected.startsWith('port:')){
    const info=selectedPortInfo();if(info)selectPortRef(info);
  }else{
    const n=nodes.find(n=>n.id===selected);if(n)selectNode(n.id);
  }
}
function positionSelectionBar(){
  if(selectionBar.hidden)return;
  let p=null;
  if(typeof selected==='string'&&selected.startsWith('wire:')){
    const i=Number(selected.split(':')[1]),w=wires[i];if(w)p=connectionMidpoint(w,i);
  }else if(typeof selected==='string'&&selected.startsWith('port:')){
    const info=selectedPortInfo();
    if(info){
      if(info.ownerKind==='component')p=portPos(info.node,info.portId);
      else p=wirePartPoint(info.wire,info.part);
    }
  }else{
    const n=nodes.find(n=>n.id===selected);if(n){const size=componentSize(n);p={x:n.x,y:n.y-size.h/2-10}}
  }
  if(!p){hideSelectionBar();return}
  const q=svgToWorkspacePixel(p.x,p.y);
  const wrap=document.querySelector('.workspace-wrap').getBoundingClientRect();
  const x=Math.max(90,Math.min(wrap.width-90,q.x));
  const y=Math.max(44,Math.min(wrap.height-10,q.y-6));
  selectionBar.style.left=`${x}px`;selectionBar.style.top=`${y}px`;
}
