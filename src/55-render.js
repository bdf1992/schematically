'use strict';
// 0.1 Beta concern: Sanitized Component SVG projection and Wire/packet SVG rendering.

function renderMoveTether(group,from,to){
  if(!from||!to) return;
  if(Math.hypot(to.x-from.x,to.y-from.y)<1) return;
  const line=document.createElementNS('http://www.w3.org/2000/svg','path');
  line.setAttribute('class','move-tether');
  line.setAttribute('d',`M ${from.x} ${from.y} L ${to.x} ${to.y}`);
  group.appendChild(line);

  const anchor=document.createElementNS('http://www.w3.org/2000/svg','circle');
  anchor.setAttribute('class','move-anchor');
  anchor.setAttribute('cx',from.x);
  anchor.setAttribute('cy',from.y);
  anchor.setAttribute('r','4');
  group.appendChild(anchor);
}


const SAFE_SVG_TAGS=new Set(['svg','g','path','rect','circle','ellipse','line','polyline','polygon','text']);
const SAFE_SVG_ATTRS=new Set(['viewBox','d','x','y','x1','y1','x2','y2','cx','cy','r','rx','ry','width','height','points','transform','fill','stroke','stroke-width','stroke-linecap','stroke-linejoin','opacity','font-size','font-weight','text-anchor']);
function sanitizeSvgElement(source){
  if(!SAFE_SVG_TAGS.has(source.localName))return null;
  const target=document.createElementNS('http://www.w3.org/2000/svg',source.localName);
  for(const attr of [...source.attributes||[]]){
    if(SAFE_SVG_ATTRS.has(attr.name) && !/^javascript:/i.test(attr.value))target.setAttribute(attr.name,attr.value);
  }
  if(source.localName==='text')target.textContent=source.textContent||'';
  else for(const child of [...source.children||[]]){const safe=sanitizeSvgElement(child);if(safe)target.appendChild(safe)}
  return target;
}
function appendCustomSvgFragment(group,markup,box){
  const raw=String(markup||'').trim();if(!raw)return false;
  const wrapped=/^<svg[\s>]/i.test(raw)?raw:`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 64">${raw}</svg>`;
  const doc=new DOMParser().parseFromString(wrapped,'image/svg+xml');
  if(doc.querySelector('parsererror'))return false;
  const root=doc.documentElement;
  if(root.localName!=='svg')return false;
  const vb=(root.getAttribute('viewBox')||'0 0 96 64').trim().split(/[ ,]+/).map(Number);
  const [vx,vy,vw,vh]=(vb.length===4&&vb.every(Number.isFinite))?vb:[0,0,96,64];
  const scale=Math.min(box.w/Math.max(1,vw),box.h/Math.max(1,vh));
  const tx=box.x+(box.w-vw*scale)/2-vx*scale;
  const ty=box.y+(box.h-vh*scale)/2-vy*scale;
  const safeGroup=document.createElementNS('http://www.w3.org/2000/svg','g');
  safeGroup.setAttribute('class','custom-graphic');safeGroup.setAttribute('transform',`translate(${tx} ${ty}) scale(${scale})`);safeGroup.setAttribute('fill','none');safeGroup.setAttribute('stroke','currentColor');safeGroup.setAttribute('stroke-width','2');
  for(const child of [...root.children]){const safe=sanitizeSvgElement(child);if(safe)safeGroup.appendChild(safe)}
  if(!safeGroup.children.length)return false;
  group.appendChild(safeGroup);return true;
}
function appendComponentGraphic(g,n,cfg){
  const p=cfg.presentation;
  if(p.graphic.kind==='none')return;
  const box=componentInlineGraphicBox(n);
  if(p.graphic.kind==='custom'&&appendCustomSvgFragment(g,p.graphic.svg,box))return;
  const use=document.createElementNS('http://www.w3.org/2000/svg','use');
  use.setAttribute('class','glyph');use.setAttribute('href',`#${(p.graphic.ref||`sym-${n.symbolId}`).replace(/^#/,'')}`);
  use.setAttribute('x',box.x);use.setAttribute('y',box.y);use.setAttribute('width',box.w);use.setAttribute('height',box.h);
  g.appendChild(use);
}
function appendComponentText(g,n,cfg,s){
  const p=cfg.presentation,size=p.size,customLabel=String(cfg.label||'').trim(),label=customLabel||componentTypeCaption(n,s);
  if(p.labelMode!=='none'&&label){
    const t=document.createElementNS('http://www.w3.org/2000/svg','text');
    t.setAttribute('text-anchor','middle');t.setAttribute('class',p.labelMode==='outside'?'outside-label':'component-label');
    if(componentHostedOnWire(n)&&componentBackdropMode(n)==='none'){
      const box=componentInlineGraphicBox(n);t.setAttribute('x','0');t.setAttribute('y',String(box.y+box.h+11));
    }else if(p.labelMode==='inside'){t.setAttribute('x','0');t.setAttribute('y',String(Math.min(size.h/2-10,24)))}
    else if(p.labelMode==='outside'){t.setAttribute('x','0');t.setAttribute('y',String(size.h/2+18))}
    else {t.setAttribute('x','0');t.setAttribute('y',String(size.h/2-8))}
    t.textContent=label;g.appendChild(t);
  }
  const annotation=String(p.text||'').trim();
  if(annotation&&annotation!==label&&annotation!==s.name){
    const t=document.createElementNS('http://www.w3.org/2000/svg','text');
    t.setAttribute('class','internal-text');t.setAttribute('text-anchor','middle');t.setAttribute('x','0');
    t.setAttribute('y',componentAcceptsChildren(n)?String(-p.size.h/2+72):'5');t.textContent=annotation;g.appendChild(t);
  }
}
function appendComponentTransformHandles(g,n,cfg){
  const {w,h}=componentSize(n);
  const baseX=w/2+8,baseY=h/2+8,offset=14;
  const handles=[
    {kind:'xy',x:baseX,y:baseY,shape:'rect'},
    {kind:'x',x:baseX+offset,y:baseY,shape:'circle'},
    {kind:'y',x:baseX,y:baseY+offset,shape:'circle'}
  ];
  const group=document.createElementNS('http://www.w3.org/2000/svg','g');
  group.setAttribute('class','transform-handle-group');
  const hLine=document.createElementNS('http://www.w3.org/2000/svg','line');
  hLine.setAttribute('x1',String(baseX));hLine.setAttribute('y1',String(baseY));
  hLine.setAttribute('x2',String(baseX+offset));hLine.setAttribute('y2',String(baseY));
  group.appendChild(hLine);
  const vLine=document.createElementNS('http://www.w3.org/2000/svg','line');
  vLine.setAttribute('x1',String(baseX));vLine.setAttribute('y1',String(baseY));
  vLine.setAttribute('x2',String(baseX));vLine.setAttribute('y2',String(baseY+offset));
  group.appendChild(vLine);
  for(const handle of handles){
    const halo=document.createElementNS('http://www.w3.org/2000/svg','circle');
    halo.setAttribute('class','transform-handle-halo');halo.dataset.transform=handle.kind;
    halo.setAttribute('cx',handle.x);halo.setAttribute('cy',handle.y);halo.setAttribute('r','11');group.appendChild(halo);
    const dot=document.createElementNS('http://www.w3.org/2000/svg',handle.shape==='rect'?'rect':'circle');
    dot.setAttribute('class','transform-handle');dot.dataset.transform=handle.kind;
    if(handle.shape==='rect'){
      dot.setAttribute('x',handle.x-4);dot.setAttribute('y',handle.y-4);dot.setAttribute('width','8');dot.setAttribute('height','8');dot.setAttribute('rx','1.5');
    }else{
      dot.setAttribute('cx',handle.x);dot.setAttribute('cy',handle.y);dot.setAttribute('r','4');
    }
    group.appendChild(dot);
  }
  g.appendChild(group);
}
function materialFillColor(base,material){
  const dark=surfaceAppearance()==='dark';
  if(material==='paper')return dark?mixHex([base,'#282A2D'],[.78,.22]):lighten(base,.94);
  if(material==='canvas')return mixHex([base,dark?'#463E35':'#e8dfcf'],[.82,.18]);
  if(material==='wood')return mixHex([base,dark?'#6B4A35':'#b78b62'],[.7,.3]);
  if(material==='metal')return mixHex([base,dark?'#485158':'#aeb5b9'],[.72,.28]);
  if(material==='glass')return dark?mixHex([base,'#28343A'],[.78,.22]):lighten(base,.9);
  if(material==='panel')return mixHex([base,dark?'#3B3E3D':'#d3d4cf'],[.85,.15]);
  return base;
}
function renderComponentVisual(g,n,cfg,s,signalColor){
  const p=cfg.presentation,size=p.size,form=componentForm(n);
  const boundaryColor=slotColor(cfg.colorSlot),interiorColor=slotColor(p.interiorColorSlot);
  const mixedInterior=colorEngine.diffuse?mixHex([interiorColor,signalColor],[.66,.34]):interiorColor;
  const materialFill=materialFillColor(componentSurfaceFill(mixedInterior,.86),form.body.material);
  g.dataset.material=form.body.material;g.dataset.dimension=String(form.dimension);
  g.style.setProperty('--component-color',boundaryColor);
  g.style.setProperty('--component-boundary-color',boundaryColor);
  g.style.setProperty('--component-interior-ink',ensureContrast(interiorColor,materialFill,3));
  g.style.setProperty('--component-interior-fill',materialFill);
  const backdrop=componentBackdropMode(n);g.dataset.backdrop=backdrop;
  if(form.dimension===0){
    const pointCfg=componentAttachmentPoint(n,'self')?.config,point=document.createElementNS('http://www.w3.org/2000/svg','circle');
    point.setAttribute('class','dimensional-point-body port attachment-point');point.dataset.point='self';point.dataset.port='out';point.dataset.face=pointCfg?.face||'external';point.setAttribute('r',String(Math.max(5,Math.min(12,5+form.body.thickness*.18))));point.style.setProperty('--port-color',activePortChannel(pointCfg||{}).color);g.appendChild(point);
    const display=String(cfg.label||'').trim()||componentTypeCaption(n,s);
    if(display){
      // A hosted Point inherits its host's angle; its label stays upright and below the point in world space.
      const angle=componentHostAngle(n),label=document.createElementNS('http://www.w3.org/2000/svg','text');
      label.setAttribute('class','component-label dimensional-point-label');label.setAttribute('text-anchor','middle');label.setAttribute('y','0');
      label.setAttribute('transform',`rotate(${-angle}) translate(0 22)`);label.textContent=display;g.appendChild(label);
    }
    return
  }
  if(form.dimension===1){const line=document.createElementNS('http://www.w3.org/2000/svg','line');line.setAttribute('class','dimensional-path-body');line.setAttribute('x1',String(-size.w/2));line.setAttribute('x2',String(size.w/2));line.setAttribute('y1','0');line.setAttribute('y2','0');line.setAttribute('stroke-width',String(Math.max(2,Math.min(14,2+form.body.thickness*.18))));g.appendChild(line);appendComponentGraphic(g,n,cfg);appendComponentText(g,n,cfg,s);return}
  if(backdrop!=='none'){
    const depth=Math.min(12,Math.max(0,form.body.thickness*.18));
    if(depth>0){const back=document.createElementNS('http://www.w3.org/2000/svg','rect');back.setAttribute('class','component-body-depth');back.setAttribute('x',String(-size.w/2+depth));back.setAttribute('y',String(-size.h/2+depth));back.setAttribute('width',String(size.w));back.setAttribute('height',String(size.h));back.setAttribute('rx',String(Math.min(12,Math.max(4,size.h*.095))));g.appendChild(back)}
    const body=document.createElementNS('http://www.w3.org/2000/svg','rect');body.setAttribute('class','body');body.setAttribute('x',String(-size.w/2));body.setAttribute('y',String(-size.h/2));body.setAttribute('width',String(size.w));body.setAttribute('height',String(size.h));body.setAttribute('rx',String(Math.min(12,Math.max(4,size.h*.095))));g.appendChild(body);
    if(form.frame.mode!=='none'||backdrop==='frame'){
      const inset=Math.max(4,Math.min(Math.min(size.w,size.h)/3,form.frame.thickness||12));const frameDepth=Math.min(14,Math.max(0,form.frame.depth*.16));
      if(frameDepth>0){const fd=document.createElementNS('http://www.w3.org/2000/svg','rect');fd.setAttribute('class','component-frame-depth');fd.setAttribute('x',String(-size.w/2+inset+frameDepth));fd.setAttribute('y',String(-size.h/2+inset+frameDepth));fd.setAttribute('width',String(Math.max(1,size.w-inset*2)));fd.setAttribute('height',String(Math.max(1,size.h-inset*2)));fd.setAttribute('rx','6');g.appendChild(fd)}
      const inner=document.createElementNS('http://www.w3.org/2000/svg','rect');inner.setAttribute('class','component-frame-inner');inner.setAttribute('x',String(-size.w/2+inset));inner.setAttribute('y',String(-size.h/2+inset));inner.setAttribute('width',String(Math.max(1,size.w-inset*2)));inner.setAttribute('height',String(Math.max(1,size.h-inset*2)));inner.setAttribute('rx',String(Math.max(2,Math.min(9,(size.h-inset*2)*.08))));g.appendChild(inner);
    }
    if(componentAcceptsChildren(n)){const guide=document.createElementNS('http://www.w3.org/2000/svg','rect');guide.setAttribute('class','container-guide');guide.setAttribute('x',String(-size.w/2+p.padding));guide.setAttribute('y',String(-size.h/2+p.padding));guide.setAttribute('width',String(Math.max(1,size.w-p.padding*2)));guide.setAttribute('height',String(Math.max(1,size.h-p.padding*2)));guide.setAttribute('rx','6');g.appendChild(guide)}
  }else if(componentHostedOnWire(n)){
    const half=componentInlineTerminalHalfSpan(n);
    if(half>0){const cut=document.createElementNS('http://www.w3.org/2000/svg','rect');cut.setAttribute('class','inline-wire-cut');cut.setAttribute('x',String(-half));cut.setAttribute('y','-8');cut.setAttribute('width',String(half*2));cut.setAttribute('height','16');cut.setAttribute('rx','2');g.appendChild(cut)}
  }
  appendComponentGraphic(g,n,cfg);appendComponentText(g,n,cfg,s);
}
function render(){
  syncAllNodeBoundaryContext();
  const signalState=computeSignalState();
  const componentSignals=signalState.colors;
  nodesG.innerHTML='';
  [...nodes].sort((a,b)=>nodeDepth(a)-nodeDepth(b)).forEach(n=>{
    if(isEffectivelyHidden(n))return;
    const s=byId(n.symbolId),cfg=componentConfig(n),g=document.createElementNS('http://www.w3.org/2000/svg','g'),editor=entityEditorState(n);
    {const form=componentForm(n),backdrop=componentBackdropMode(n);g.setAttribute('class','node'+(n.symbolId==='blank'?' blank':'')+(selectedComponentIds.has(n.id)?' selected':'')+(componentAcceptsChildren(n)?' is-container':'')+(form.frame.mode==='shell'?' form-shell':'')+(form.frame.mode==='frame'?' form-frame':'')+(n.parentId?' nested-child':'')+(componentHostedOnWire(n)?' wire-hosted':'')+(backdrop==='none'?' backdrop-none':'')+(editor.pinned?' is-pinned':'')+(editor.locked?' is-locked':''));}
    g.style.opacity=String(editor.opacity);
    g.dataset.id=n.id;if(n.parentId)g.dataset.parentId=n.parentId;
    const signalColor=componentSignals.get(n.id)||cfg.color;
    {const angle=componentHostAngle(n),attached=componentHostedOnWire(n)||componentHostedOnComponentPath(n)||componentHostedOnComponentEdge(n);g.setAttribute('transform',`translate(${n.x} ${n.y})${attached?` rotate(${angle})`:''}`)}
    renderComponentVisual(g,n,cfg,s,signalColor);
    if(!editor.pinned&&!editor.locked&&componentForm(n).dimension===2)appendComponentTransformHandles(g,n,cfg);
    const renderedPoints=componentAttachmentPoints(n);for(const point of renderedPoints){
      const pointId=point.id,pcfg=point.config,local=componentPortLocalPosition(n,pointId);
      const localX=local.x,localY=local.y;
      const hit=document.createElementNS('http://www.w3.org/2000/svg','circle');
      hit.setAttribute('class','port-hit attachment-point-hit');hit.dataset.point=pointId;hit.dataset.side=point.compatId;hit.dataset.canvasIds=portExposedCanvasIds(n,pointId).join(' ');hit.setAttribute('cx',localX);hit.setAttribute('cy',localY);hit.setAttribute('r','16');
      let vis=null;const selfPoint=componentForm(n).dimension===0&&pointId==='self';
      if(selfPoint){vis=g.querySelector('.dimensional-point-body');if(vis){vis.dataset.point=pointId;vis.dataset.port=point.compatId;vis.dataset.face=pcfg.face||'external';vis.style.setProperty('--port-color',activePortChannel(pcfg).color)}}
      else{vis=document.createElementNS('http://www.w3.org/2000/svg','circle');vis.setAttribute('class','port attachment-point');vis.dataset.point=pointId;vis.dataset.port=point.compatId;vis.dataset.face=pcfg.face||'external';vis.setAttribute('cx',localX);vis.setAttribute('cy',localY);vis.setAttribute('r','5');vis.style.setProperty('--port-color',activePortChannel(pcfg).color)}
      g.appendChild(hit);if(!selfPoint)g.appendChild(vis);
      if(selfPoint){
        // A 0D form is both a movable object and an attachment. The inner grip moves it
        // (drag) or selects it (click); the outer ring is the wiring/attachment target.
        const grip=document.createElementNS('http://www.w3.org/2000/svg','circle');
        grip.setAttribute('class','point-grip');grip.setAttribute('cx',localX);grip.setAttribute('cy',localY);grip.setAttribute('r','8');g.appendChild(grip);
      }
      if(pcfg.label){
        const portLabel=document.createElementNS('http://www.w3.org/2000/svg','text');
        portLabel.setAttribute('class','port-label-text');
        const offsets={left:{dx:-10,dy:4,anchor:'end'},right:{dx:10,dy:4,anchor:'start'},top:{dx:0,dy:-10,anchor:'middle'},bottom:{dx:0,dy:16,anchor:'middle'},point:{dx:10,dy:4,anchor:'start'}}[point.side]||{dx:10,dy:4,anchor:'start'};
        portLabel.setAttribute('x',localX+offsets.dx);portLabel.setAttribute('y',localY+offsets.dy);portLabel.setAttribute('text-anchor',offsets.anchor);portLabel.textContent=pcfg.label;g.appendChild(portLabel);
      }
    }
    bindNode(g,n); nodesG.appendChild(g);
  });
  renderWires(signalState);
  renderObjectsPanel?.();if(quickSearchActive)updateQuickSearch(document.getElementById('quickSearchInput')?.value||'');
  if(typeof scheduleLocalAutosave==='function')scheduleLocalAutosave();
}
function clearEndpointFocus(){
  document.querySelectorAll('.port.endpoint-focus,.port-hit.endpoint-focus').forEach(x=>x.classList.remove('endpoint-focus'));
  document.querySelectorAll('.endpoint-halo').forEach(x=>x.remove());
}
function focusWireEndpoints(w){
  clearEndpointFocus();
  for(const end of ['a','b']){
    const ep=carrierEndpoint(w,end);if(!ep)continue;
    if(ep.kind==='bound'){
      const nodeEl=document.querySelector(`.node[data-id="${ep.node.id}"]`),side=ep.compatId;
      nodeEl?.querySelector(`.port-hit[data-side="${side}"]`)?.classList.add('endpoint-focus');
      nodeEl?.querySelector(`.port-hit[data-side="${side}"]`)?.nextElementSibling?.classList.add('endpoint-focus');
    }
    const halo=document.createElementNS('http://www.w3.org/2000/svg','circle');
    halo.setAttribute('class','endpoint-halo'+(ep.kind==='free'?' free-end':''));
    halo.setAttribute('cx',ep.pos.x);halo.setAttribute('cy',ep.pos.y);halo.setAttribute('r','10');
    ghostLayer.appendChild(halo);
  }
}
function angleDelta(a,b){
  let d=Math.abs(a-b)%360;
  return d>180?360-d:d;
}
function pointAngleAtDistance(path,d,window=3){
  const L=path.getTotalLength();
  d=Math.max(1,Math.min(L-1,d));
  const p=path.getPointAtLength(d);
  const p0=path.getPointAtLength(Math.max(0,d-window));
  const p1=path.getPointAtLength(Math.min(L,d+window));
  return {x:p.x,y:p.y,angle:Math.atan2(p1.y-p0.y,p1.x-p0.x)*180/Math.PI,d};
}
function straightnessAt(path,d){
  const L=path.getTotalLength();
  const q=pointAngleAtDistance(path,d,3);
  const before=pointAngleAtDistance(path,Math.max(2,d-10),3);
  const after=pointAngleAtDistance(path,Math.min(L-2,d+10),3);
  return Math.max(angleDelta(q.angle,before.angle),angleDelta(q.angle,after.angle));
}
function stableArrowPoint(path,targetD,minD,maxD){
  const offsets=[0,10,-10,20,-20,30,-30,42,-42];
  let fallback=null;
  for(const off of offsets){
    const d=Math.max(minD,Math.min(maxD,targetD+off));
    const q=pointAngleAtDistance(path,d,3);
    const bend=straightnessAt(path,d);
    if(!fallback || bend<fallback.bend) fallback={q,bend};
    if(bend<=8) return q;
  }
  return fallback?.q||pointAngleAtDistance(path,targetD,3);
}
function appendChevronAt(group,q,reverse=false,className='flow-chevron'){
  const c=document.createElementNS('http://www.w3.org/2000/svg','path');
  c.setAttribute('class',className);
  c.setAttribute('d','M -7 -5 L 0 0 L -7 5');
  c.setAttribute('transform',`translate(${q.x} ${q.y}) rotate(${q.angle+(reverse?180:0)})`);
  group.appendChild(c);
}
function adaptiveArrowDistances(path,duplex=false){
  const L=path.getTotalLength();
  if(L<72) return [];

  // Keep arrows away from terminals and scale density with actual wire length.
  const margin=Math.min(46,Math.max(26,L*.16));
  const usable=L-margin*2;
  if(usable<=8) return [];

  let count;
  if(L<150) count=1;
  else if(L<310) count=2;
  else count=Math.min(7,Math.max(2,Math.round(L/165)));

  // Duplex gets the same total visual density, split between directions,
  // rather than doubling the number of marks.
  const distances=[];
  for(let i=0;i<count;i++){
    distances.push(margin + usable*((i+1)/(count+1)));
  }
  return distances;
}
function arrowPosesForPath(path,duplex=false){
  const L=path.getTotalLength();
  const distances=adaptiveArrowDistances(path,duplex);
  if(!distances.length)return [];
  const margin=Math.min(46,Math.max(26,L*.16));
  const poses=[];
  distances.forEach((d,i)=>{
    const q=stableArrowPoint(path,d,margin,L-margin);
    const reverse=duplex ? (i%2===1) : false;
    poses.push({q,reverse});
  });

  // A one-arrow duplex wire still needs to communicate both directions.
  if(duplex && poses.length===1){
    poses.push({
      q:stableArrowPoint(path,Math.min(L-margin,distances[0]+34),margin,L-margin),
      reverse:true
    });
  }
  return poses;
}
function packetTravelSeconds(pathLength){
  // Geometry changes travel time, never packet count.
  return Math.max(.72,Math.min(4.5,pathLength/175));
}
function appendWirePacket(group,motionPath,pathLength,bodyColor,boundaryColor,direction='forward',tag='',rate=1,operation='none'){
  const packet=document.createElementNS('http://www.w3.org/2000/svg','g');
  packet.setAttribute('class','wire-packet');
  packet.dataset.direction=direction;

  const dot=document.createElementNS('http://www.w3.org/2000/svg','circle');
  dot.setAttribute('r','5.2');
  dot.setAttribute('fill',bodyColor);
  dot.setAttribute('stroke',boundaryColor);
  dot.setAttribute('stroke-width','2.6');
  packet.appendChild(dot);

  if(operation==='read'||operation==='write'){
    const op=document.createElementNS('http://www.w3.org/2000/svg','text');
    op.setAttribute('class','wire-packet-operation');op.setAttribute('text-anchor','middle');op.setAttribute('x','0');op.setAttribute('y','.5');
    op.textContent=operation==='read'?'R':'W';
    const lum=hexRgb(bodyColor);const yiq=lum?(lum.r*299+lum.g*587+lum.b*114)/1000:255;
    op.style.setProperty('--packet-op-ink',yiq<145?'#fff':'#111');
    packet.appendChild(op);
  }

  if(tag){
    const label=document.createElementNS('http://www.w3.org/2000/svg','text');
    label.setAttribute('class','wire-packet-tag');
    label.setAttribute('text-anchor','middle');
    label.setAttribute('x','0');
    label.setAttribute('y','-8');
    label.textContent=tag;
    packet.appendChild(label);
  }

  const duration=packetTravelSeconds(pathLength)/Math.max(.1,Number(rate)||1);

  // Packet skin is identity, not field diffusion.
  // It stays constant across the trip while the carrier/wire field may blend.
  const motion=document.createElementNS('http://www.w3.org/2000/svg','animateMotion');
  motion.setAttribute('path',motionPath);
  motion.setAttribute('dur',`${duration}s`);
  motion.setAttribute('repeatCount','indefinite');
  motion.setAttribute('calcMode','linear');
  packet.appendChild(motion);
  group.appendChild(packet);
  return packet;
}
function renderPacketsForWire(group,cfg,points,signal,pathLength,w){
  // Count invariant:
  // one bound channel × one live direction = one packet instance.
  if(cfg.direction==='none')return 0;

  const forwardPath=pathD(points);
  const reversePath=pathD([...points].reverse());
  let count=0;

  if(cfg.direction==='forward'){
    if(signal.forwardLive){
      appendWirePacket(group,forwardPath,pathLength,signal.forwardBody,signal.forwardBoundary,'forward',wireEndpointMarker(w,'a'),packetRateForWire(w,'forward'),wireOperation(w,'forward'))
      count++;
    }
  }else if(cfg.direction==='reverse'){
    if(signal.reverseLive){
      appendWirePacket(group,reversePath,pathLength,signal.reverseBody,signal.reverseBoundary,'reverse',wireEndpointMarker(w,'b'),packetRateForWire(w,'reverse'),wireOperation(w,'reverse'))
      count++;
    }
  }else if(cfg.direction==='duplex'){
    if(signal.forwardLive){
      appendWirePacket(group,forwardPath,pathLength,signal.forwardBody,signal.forwardBoundary,'forward',wireEndpointMarker(w,'a'),packetRateForWire(w,'forward'),wireOperation(w,'forward'))
      count++;
    }
    if(signal.reverseLive){
      appendWirePacket(group,reversePath,pathLength,signal.reverseBody,signal.reverseBoundary,'reverse',wireEndpointMarker(w,'b'),packetRateForWire(w,'reverse'),wireOperation(w,'reverse'))
      count++;
    }
  }
  return count;
}

function renderArrowPoses(group,poses,className='flow-chevron'){
  for(const pose of poses||[]) appendChevronAt(group,pose.q,pose.reverse,className);
}

function focusWireVisual(i){
  document.querySelectorAll('.wire-group').forEach(g=>g.classList.toggle('muted',Number(g.dataset.wireIndex)!==i));
  const w=wires[i]; if(w) focusWireEndpoints(w);
}
function clearWireVisualFocus(){
  document.querySelectorAll('.wire-group').forEach(g=>g.classList.remove('muted'));
  if(!(typeof selected==='string'&&selected.startsWith('wire:'))) clearEndpointFocus();
}
function renderWires(signalState=computeSignalState()){
  wiresG.innerHTML='';
  nodesG.querySelectorAll(':scope > .wire-group').forEach(g=>g.remove());
  clearEndpointFocus();
  const occupied=[];
  const dragging=!!activeNodeDrag;
  const hostAnchors=new Map();

  wires.forEach((w,i)=>{
    const editor=entityEditorState(w);const cfg=connectionConfig(w);if(editor.hidden||!carrierIsRenderable(w))return;
    const epA=carrierEndpoint(w,'a'),epB=carrierEndpoint(w,'b'),a=epA.node,b=epB.node;
    const A=epA.pos, B=epB.pos;
    const touchesDragged = dragging && (w.a===activeNodeDrag || w.b===activeNodeDrag);
    const snapshot = touchesDragged ? dragRouteSnapshots.get(i) : null;

    // While moving, the settled route is immutable. We do not rebuild its
    // interior, endpoint leads, arrows, or direction marks on pointer frames.
    const points = snapshot
      ? clonePoints(snapshot.points)
      : stableRouteForWire(i,w,A,B,occupied);

    const d=pathD(points);
    occupied.push(...routeSegments(points));

    const signal=wireSignalColors(w,signalState);
    const group=document.createElementNS('http://www.w3.org/2000/svg','g');
    group.setAttribute('class','wire-group'+(snapshot?' drag-frozen':'')+((!signal.forwardLive && !signal.reverseLive)?' dormant':'')+(editor.locked?' is-locked':'')+((epA.kind==='free'||epB.kind==='free')?' has-free-end':''));group.dataset.wireId=w.id;group.dataset.wireIndex=String(i);group.style.opacity=String(editor.opacity);

    const gradientId=`wire-gradient-${i}-${renderEpoch++}`;
    const gradient=document.createElementNS('http://www.w3.org/2000/svg','linearGradient');
    gradient.setAttribute('id',gradientId);
    gradient.setAttribute('gradientUnits','userSpaceOnUse');
    gradient.setAttribute('x1',points[0].x);gradient.setAttribute('y1',points[0].y);
    gradient.setAttribute('x2',points[points.length-1].x);gradient.setAttribute('y2',points[points.length-1].y);
    const stopA=document.createElementNS('http://www.w3.org/2000/svg','stop');
    stopA.setAttribute('offset','0%');stopA.setAttribute('stop-color',signal.aColor);
    const stopB=document.createElementNS('http://www.w3.org/2000/svg','stop');
    stopB.setAttribute('offset','100%');stopB.setAttribute('stop-color',signal.bColor);
    gradient.appendChild(stopA);gradient.appendChild(stopB);group.appendChild(gradient);

    group.style.setProperty('--wire-ink',`url(#${gradientId})`);
    group.style.setProperty('--voltage-ink',signal.field);

    const voltage=document.createElementNS('http://www.w3.org/2000/svg','path');
    voltage.setAttribute('d',d);voltage.setAttribute('class','wire-voltage');

    const base=document.createElementNS('http://www.w3.org/2000/svg','path');
    base.setAttribute('d',d);
    base.setAttribute('class','wire'+(selected===`wire:${i}`?' selected':''));

    const hit=document.createElementNS('http://www.w3.org/2000/svg','path');
    hit.setAttribute('d',d); hit.setAttribute('class','wire-hit');

    group.appendChild(voltage);
    group.appendChild(base);
    {const L=base.getTotalLength();for(const hosted of nodes.filter(n=>(n.canvasId||GLOBAL_CANVAS_ID)===wireCanvas(w).id&&n.id!==activeNodeDrag)){
      const placement=componentPlacement(hosted),len=Math.max(1,Math.min(L-1,L*placement.t)),q=base.getPointAtLength(len),angle=pathTangentAngleAtLength(base,len);
      hosted.x=q.x;hosted.y=q.y;wireHostPoseCache.set(hosted.id,{x:q.x,y:q.y,angle,wireId:w.id,t:placement.t});
      const el=nodesG.querySelector(`.node[data-id="${hosted.id}"]`);if(el)el.setAttribute('transform',`translate(${hosted.x} ${hosted.y}) rotate(${angle})`)
    }}

    // Discrete packets are real instances, not repeated dash patterns.
    // Path length may alter motion duration but cannot manufacture particles.
    renderPacketsForWire(group,cfg,points,signal,base.getTotalLength(),w);

    group.appendChild(hit);
    // Wires paint beneath the nodes, so a wire on a Component's interior surface would be
    // hidden by its host's body. It is lifted to just after its host in the node layer:
    // above the host body, beneath the hosted children that follow it.
    const surface=w.canvasId||GLOBAL_CANVAS_ID;
    const hostId=surface.startsWith('canvas:component:')?surface.slice('canvas:component:'.length):null;
    const hostEl=hostId?nodesG.querySelector(`:scope > .node[data-id="${hostId}"]`):null;
    if(hostEl){(hostAnchors.get(hostId)||hostEl).after(group);hostAnchors.set(hostId,group)}
    else wiresG.appendChild(group);

    // Marks have no independent positional truth. Every arrow is regenerated
    // from the exact line geometry being rendered in this frame. If the line is
    // frozen, arrows derive from that frozen line; they can never detach from it.
    const poses=arrowPosesForPath(base,cfg.direction==='duplex');
    if(cfg.direction==='reverse')poses.forEach(p=>p.reverse=!p.reverse);
    if(cfg.direction==='none')poses.length=0;
    renderArrowPoses(group,poses,'flow-chevron');

    if(snapshot){
      // The only geometry outside the frozen line is the exact displacement
      // tether from its old terminal to the held Component.
      if(w.a===activeNodeDrag)renderMoveTether(group,snapshot.aPos,A);
      if(w.b===activeNodeDrag)renderMoveTether(group,snapshot.bPos,B);
    }

    if(cfg.direction==='duplex'){
      const q=pointAngleAtDistance(base,base.getTotalLength()*.5);
      const badge=document.createElementNS('http://www.w3.org/2000/svg','text');
      badge.setAttribute('class','net-badge');
      badge.setAttribute('x',q.x); badge.setAttribute('y',q.y-7);
      badge.setAttribute('text-anchor','middle');
      badge.textContent='↔';
      group.appendChild(badge);
    }

    if(cfg.reciprocity!=='none'){const q=pointAngleAtDistance(base,base.getTotalLength()*.5),mark=document.createElementNS('http://www.w3.org/2000/svg','text');mark.setAttribute('class','reciprocity-mark');mark.setAttribute('x',q.x);mark.setAttribute('y',q.y+14);mark.setAttribute('text-anchor','middle');mark.textContent=cfg.reciprocity==='required'?'RETURN!':'RETURN?';group.appendChild(mark)}
    if(cfg.label){const q=pointAngleAtDistance(base,base.getTotalLength()*.5),label=document.createElementNS('http://www.w3.org/2000/svg','text');label.setAttribute('class','connection-label');label.setAttribute('x',q.x);label.setAttribute('y',q.y-13);label.setAttribute('text-anchor','middle');label.textContent=cfg.label;group.appendChild(label)}
    // Channel markers belong to bound ends; a free end has no port to mark.
    if(a){
      const markerA=document.createElementNS('http://www.w3.org/2000/svg','text');
      markerA.setAttribute('class','endpoint-channel-tag');
      {const side=physicalPortSide(a,w.aSide);markerA.setAttribute('x',A.x+(side==='left'?-14:side==='right'?14:0));markerA.setAttribute('y',A.y+(side==='top'?-12:side==='bottom'?15:4));markerA.setAttribute('text-anchor',side==='left'?'end':side==='right'?'start':'middle')}
      markerA.textContent=endpointMarkerDisplay(w,'a');
      group.appendChild(markerA);
    }
    if(b){
      const markerB=document.createElementNS('http://www.w3.org/2000/svg','text');
      markerB.setAttribute('class','endpoint-channel-tag');
      {const side=physicalPortSide(b,w.bSide);markerB.setAttribute('x',B.x+(side==='left'?-14:side==='right'?14:0));markerB.setAttribute('y',B.y+(side==='top'?-12:side==='bottom'?15:4));markerB.setAttribute('text-anchor',side==='left'?'end':side==='right'?'start':'middle')}
      markerB.textContent=endpointMarkerDisplay(w,'b');
      group.appendChild(markerB);
    }
    // End handles: a free end shows an open ring where the Path stops; a bound end's handle sits a
    // little way along the lead so the Component's own port keeps pointer priority at the terminal.
    {const L=base.getTotalLength();
     for(const [end,ep,at] of [['a',epA,0],['b',epB,L]]){
       const q=ep.kind==='free'?ep.pos:base.getPointAtLength(at===0?Math.min(20,L/2):Math.max(L-20,L/2));
       const handle=document.createElementNS('http://www.w3.org/2000/svg','circle');
       handle.setAttribute('class','carrier-end-handle'+(ep.kind==='free'?' free':' bound'));handle.dataset.end=end;handle.dataset.wireIndex=String(i);
       handle.setAttribute('cx',q.x);handle.setAttribute('cy',q.y);handle.setAttribute('r',ep.kind==='free'?'6':'4.5');
       handle.addEventListener('pointerdown',e=>{e.stopPropagation();beginCarrierEndDrag(e,i,end)});
       group.appendChild(handle);
     }}
    // Legacy Wire-owned attachment points are migrated to hosted 0D Components before projection.

    hit.addEventListener('pointerdown',e=>{e.stopPropagation();selectWire(i);focusWireVisual(i)});
    group.addEventListener('pointerenter',()=>focusWireVisual(i));
    group.addEventListener('pointerleave',()=>{if(selected!==`wire:${i}`)clearWireVisualFocus()});
    if(selected===`wire:${i}`) focusWireVisual(i);
  });
}
