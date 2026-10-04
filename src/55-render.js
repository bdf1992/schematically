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
  // A clock draws the wave it makes.
  const wave=n.symbolId==='clock'?cfg.signal?.clock?.wave:null,ref=(p.graphic.ref||`sym-${n.symbolId}`).replace(/^#/,'');
  use.setAttribute('class','glyph');use.setAttribute('href',`#${ref==='sym-clock'&&['saw','triangle','sine'].includes(wave)?`sym-clock-${wave}`:ref}`);
  use.setAttribute('x',box.x);use.setAttribute('y',box.y);use.setAttribute('width',box.w);use.setAttribute('height',box.h);
  g.appendChild(use);
}
// A label belongs inside the body it names. Measured after the node is in the document (label
// size follows zoom): a label wider than the body wraps onto two lines at word breaks, and one
// still too long is cut with an ellipsis; the full text stays available as a tooltip.
// A wired side point on the glyph's axis gets an inner lead from the body edge to the symbol,
// so the wire, the edge and the symbol read as one continuous line.
// A wired terminal is joined to its point on the card's edge by a lead: straight when they
// line up, one orthogonal dogleg when the point sits elsewhere on the same side.
function appendComponentLeads(g,n){
  const axis=componentGlyphAxis(n);if(!axis)return;
  const glyph=componentGlyph(n);
  for(const t of glyph?.terminals||[]){
    const spec=Attachment.resolveSpec(n,t.id);if(!spec||spec.side!==t.toward)continue;
    if(!wires.some(x=>(x.a===n.id&&x.aSide===spec.compatId)||(x.b===n.id&&x.bSide===spec.compatId)))continue;
    const P=componentPortLocalPosition(n,spec.id),[ex,ey]=SovSchematicNotation.pinEnd(t),E={x:axis.x0+ex*axis.scale,y:axis.y0+ey*axis.scale};
    const horizontal=t.toward==='left'||t.toward==='right';
    let d;
    if(horizontal)d=Math.abs(P.y-E.y)<.5?`M${P.x} ${E.y}H${E.x}`:`M${P.x} ${P.y}H${(P.x+E.x)/2}V${E.y}H${E.x}`;
    else d=Math.abs(P.x-E.x)<.5?`M${E.x} ${P.y}V${E.y}`:`M${P.x} ${P.y}V${(P.y+E.y)/2}H${E.x}V${E.y}`;
    const lead=document.createElementNS('http://www.w3.org/2000/svg','path');lead.setAttribute('class','component-lead');lead.setAttribute('d',d);
    lead.setAttribute('stroke-width',String(axis.stroke));g.appendChild(lead);
  }
}
// Where a wire meets a card, a short bar on the edge in the point's own colour: amber where
// work leaves, blue where it arrives, both halves for a two-way point, muted for control.
function appendTerminalMarks(g,n){
  if(componentForm(n).dimension!==2)return;
  for(const point of componentAttachmentPoints(n)){
    const compat=point.compatId;
    if(!wires.some(x=>(x.a===n.id&&x.aSide===compat)||(x.b===n.id&&x.bSide===compat)))continue;
    const flow=activePortChannel(point.config||{}).flow||'duplex',side=physicalPortSide(n,point.id),P=componentPortLocalPosition(n,point.id);
    const vertical=side==='left'||side==='right',len=12,th=3.2;
    const parts=flow==='duplex'?[['in',-len/2,len/2],['out',0,len/2]]:[[flow==='control'?'control':flow==='in'?'in':'out',-len/2,len]];
    for(const [cls,off,span] of parts){
      const r=document.createElementNS('http://www.w3.org/2000/svg','rect');r.setAttribute('class','terminal-mark '+cls);
      if(vertical){r.setAttribute('x',String(P.x-th/2));r.setAttribute('y',String(P.y+off));r.setAttribute('width',String(th));r.setAttribute('height',String(span))}
      else{r.setAttribute('x',String(P.x+off));r.setAttribute('y',String(P.y-th/2));r.setAttribute('width',String(span));r.setAttribute('height',String(th))}
      r.setAttribute('rx','1.2');g.appendChild(r);
    }
  }
}
// A card's title and subtitle are one block, laid out at the size they are drawn at (after the
// screen clamp, so the block is laid out again when the zoom changes): the title wraps at word
// breaks to at most two lines within the card's text width, a line still too long ends in an
// ellipsis, the subtitle is one line cut the same way, and its top sits space.textGap under the
// title's last line. The block's foot stays where the title sat (or, below a glyph or the body, its
// head does). Inside a card the block keeps clear of the glyph and inside the inner edge; when it
// cannot, the least important line goes first: the subtitle is hidden (data-lod="hidden"), then the
// title is cut to one line. A cut line sets data-truncated, and the full text goes in a tooltip on
// the card's group (a <title> child of the .node g), never inside the drawn <text>, so whatever
// reads a text's contents reads only what is drawn. A line that is one word, with no break to wrap
// at, may use the card's full inner width (w - 8, section inset ignored) before it is cut.
// A title drawn outside its card (outside label mode) keeps one line at its own width, uncut, and
// only its subtitle's place follows space.textGap.
const SVG_NS='http://www.w3.org/2000/svg';
function setFittedText(el,lines,x,step){
  el.textContent='';
  lines.forEach((line,i)=>{const span=document.createElementNS(SVG_NS,'tspan');span.setAttribute('x',x);span.setAttribute('dy',i?String(step):'0');span.textContent=line;el.appendChild(span)});
}
function fitComponentLabels(g,n){
  if(componentForm(n).dimension!==2)return;
  const t=g.querySelector(':scope > text.component-label,:scope > text.outside-label');if(!t)return;
  const u=g.querySelector(':scope > text.component-subtitle');
  // A refit starts from what was authored, never from the last fit.
  if(t.dataset.full==null)t.dataset.full=t.textContent;
  if(u&&u.dataset.full==null)u.dataset.full=u.textContent;
  const full=t.dataset.full,subFull=u?u.dataset.full:'';if(!full)return;
  const size=componentSize(n),inset=componentSectionInset(n),max=size.w-12-inset*2,x=t.getAttribute('x')||'0';
  const gap=Number(SovSchematicNotation.tokens(diagram).space?.textGap)||3,down=t.dataset.grow==='down';
  const y0=t.dataset.y0!=null?Number(t.dataset.y0):Number(t.getAttribute('y'))||0;
  // A title drawn outside its card (under it) is not held to the card's width: it stays one line.
  const outside=t.classList.contains('outside-label'),inCard=!outside&&componentBackdropMode(n)!=='none';
  delete t.dataset.truncated;
  if(u){delete u.dataset.truncated;delete u.dataset.lod;u.style.visibility=''}
  const wide=size.w-8,fits=(el,s,limit=max)=>{el.textContent=s;return el.getComputedTextLength()<=limit};
  const cut=(el,s)=>{const limit=/\s/.test(s.trim())?max:Math.max(max,wide);if(outside||fits(el,s,limit))return s;let c=s;while(c.length>1){c=c.slice(0,-1).trimEnd();if(fits(el,c+'…',limit))return c+'…'}return '…'};
  const wrap=limit=>{
    if(outside)return [full];
    const lines=[];let cur='';
    for(const w of full.split(/\s+/).filter(Boolean)){const trial=cur?cur+' '+w:w;if(!cur||fits(t,trial))cur=trial;else{lines.push(cur);cur=w}}
    if(cur)lines.push(cur);
    const kept=lines.length>limit?[...lines.slice(0,limit-1),lines.slice(limit-1).join(' ')]:lines;
    return kept.map(l=>cut(t,l));
  };
  const innerTop=-size.h/2+inset+2,innerBottom=size.h/2-inset-2;
  const graphic=componentConfig(n).presentation?.graphic;
  let topLimit=innerTop;
  if(graphic?.kind&&graphic.kind!=='none'){const box=componentInlineGraphicBox(n);if(!down)topLimit=Math.max(topLimit,box.y+box.h+2)}
  const subLine=u&&subFull?cut(u,subFull):null;
  const ok=r=>!inCard||(r.top>=topLimit-.01&&r.bottom<=innerBottom+.01);
  const isCut=r=>r.lines.some(l=>l.endsWith('…'));
  // The whole layout at the title's current font size: wrap, place, then the least important line
  // goes first (the subtitle, then the title's second line).
  const layout=()=>{
  // Where the title sat on its own: the block's foot (growing up) or head (growing down).
  t.textContent=full;t.setAttribute('y',String(y0));
  const b0=t.getBBox();
  const head=b0.y;let foot=inCard&&!down?Math.min(b0.y+b0.height,innerBottom):b0.y+b0.height;
  const em=parseFloat(getComputedStyle(t).fontSize)||10;
  const place=(lines,showSub)=>{
    setFittedText(t,lines,x,em*1.15);t.setAttribute('y','0');
    const bt=t.getBBox();let top=bt.y,bottom=bt.y+bt.height;
    if(u){
      setFittedText(u,[subLine??''],x,0);u.setAttribute('y','0');
      // A hidden subtitle keeps its place under the title; only a shown one adds to the block.
      const bu=u.getBBox();u.setAttribute('y',String(bottom+gap-bu.y));if(showSub&&subLine!=null)bottom=bottom+gap+bu.height;
    }
    const shift=down?head-top:foot-bottom;
    t.setAttribute('y',String(shift));
    if(u)u.setAttribute('y',String((Number(u.getAttribute('y'))||0)+shift));
    return {top:top+shift,bottom:bottom+shift,lines,showSub};
  };
  // A block that does not fit at the lone title's foot may sit lower, down to the inner edge.
  const fit=(lines,showSub)=>{const base=foot;let r=place(lines,showSub);
    if(!ok(r)&&inCard&&!down&&base<innerBottom){foot=innerBottom;r=place(lines,showSub);foot=base}
    return r};
  let r=fit(wrap(2),!!subLine);
  if(!ok(r)&&r.showSub)r=fit(r.lines,false);
  if(!ok(r)&&r.lines.length>1)r=fit(wrap(1),false);
  return r};
  const screen=parseFloat(typeof workspace!=='undefined'&&workspace?workspace.style.getPropertyValue('--zoom'):'')||1;
  t.style.fontSize='';delete t.dataset.shrunk;
  let r=layout();
  // A title inside its card that would be cut may shrink below the 12 px screen floor, down to
  // 10 px on screen, before an ellipsis is used; it is marked data-shrunk. Only a size that keeps
  // the title whole is taken; otherwise it stays at its clamped size and is cut.
  if(inCard&&isCut(r)&&screen>.25){
    const px0=(parseFloat(getComputedStyle(t).fontSize)||10)*screen;let whole=null;
    for(let px=Math.floor(px0*2)/2-.5;px>=10-1e-9;px-=.5){t.style.fontSize=`${px/screen}px`;const r2=layout();if(!isCut(r2)){whole=r2;break}}
    if(whole){r=whole;t.dataset.shrunk='true'}else{t.style.fontSize='';r=layout()}
  }
  if(u&&(!r.showSub)){u.style.visibility='hidden';u.dataset.lod='hidden'}
  // Zoomed far out (screen scale 0.25 or less), a title that still runs into its glyph is hidden.
  delete t.dataset.lod;t.style.visibility='';
  if(inCard&&graphic?.kind&&graphic.kind!=='none'&&screen<=.25&&r.top<topLimit-.01){t.style.visibility='hidden';t.dataset.lod='hidden'}
  // Wrapping onto two lines is not a cut; only an ellipsis is.
  if(r.lines.some(l=>l.endsWith('…')))t.dataset.truncated='true';
  if(u&&r.showSub&&subLine!==subFull)u.dataset.truncated='true';
  // Whatever is cut or hidden is read in full from the card's tooltip.
  g.querySelector(':scope > title.card-text-full')?.remove();
  if(t.dataset.truncated||t.dataset.lod||(u&&(u.dataset.truncated||u.dataset.lod))){
    const tip=document.createElementNS(SVG_NS,'title');tip.setAttribute('class','card-text-full');
    tip.textContent=subFull?`${full}\n${subFull}`:full;g.insertBefore(tip,g.firstChild);
  }
}
// The zoom changes the size labels are drawn at, so each card's text block is laid out again on
// the next frame after it changes, and a waits-on caption follows the block's new foot.
let componentLabelFitZoom=null,componentLabelFitFrame=0;
function refitComponentLabels(){
  componentLabelFitFrame=0;
  const zoom=workspace.style.getPropertyValue('--zoom');if(zoom===componentLabelFitZoom)return;componentLabelFitZoom=zoom;
  const byId=new Map(nodes.map(n=>[n.id,n]));
  for(const g of nodesG.querySelectorAll('.node:not(.group)')){
    const n=byId.get(g.dataset.id);if(!n||componentForm(n).dimension!==2)continue;
    fitComponentLabels(g,n);
    const waits=g.querySelector(':scope > text.waits-on');if(waits){waits.remove();appendComponentWaitsOn(g,n)}
  }
}
if(typeof MutationObserver==='function'&&typeof workspace!=='undefined'&&workspace)
  new MutationObserver(()=>{if(workspace.style.getPropertyValue('--zoom')!==componentLabelFitZoom&&!componentLabelFitFrame)componentLabelFitFrame=requestAnimationFrame(refitComponentLabels)})
    .observe(workspace,{attributes:true,attributeFilter:['style']});
// A bevel inside a rounded rectangle w x h: raised (lit from the top left) or recessed.
function appendBevel(g,w,h,rx,mode='raised'){
  const d=SovSchematicNotation.tokens(diagram).space.bevel;w-=d*2;h-=d*2;if(w<12||h<12)return;
  const r=Math.max(0,rx-d),x0=-w/2,y0=-h/2,x1=w/2,y1=h/2;
  const tl=`M${x0} ${y1-r}L${x0} ${y0+r}Q${x0} ${y0} ${x0+r} ${y0}L${x1-r} ${y0}`,br=`M${x1} ${y0+r}L${x1} ${y1-r}Q${x1} ${y1} ${x1-r} ${y1}L${x0+r} ${y1}`;
  for(const [cls,path] of mode==='raised'?[['light',tl],['shade',br]]:[['shade',tl],['light',br]]){
    const e=document.createElementNS('http://www.w3.org/2000/svg','path');e.setAttribute('class',`section-bevel ${mode} ${cls}`);e.setAttribute('d',path);g.appendChild(e);
  }
}
function appendSolidBevel(g,size,section){
  const T=SovSchematicNotation.tokens(diagram),sectioned=section.lines.length>=2,total=sectioned?section.bands.reduce((a,b)=>a+b.thickness,0):0;
  const w=size.w-total*2,h=size.h-total*2;
  appendBevel(g,w,h,SovSchematicNotation.cornerRadius(T,{total,inset:total,w,h,sectioned}),'raised');
}
// A card's elevation: one above what holds it. Root cards sit at 1.
function componentElevation(n){let k=1,p=n;const seen=new Set();while(p?.parentId&&!seen.has(p.parentId)){seen.add(p.parentId);p=nodes.find(x=>x.id===p.parentId);if(p)k++}return k}
function componentSectionInset(n){const s=componentForm(n).dimension===2?SovSchematicData.componentSection(n):null;return s&&s.lines.length>=2?s.bands.reduce((a,b)=>a+b.thickness,0):0}
function appendComponentText(g,n,cfg,s){
  const p=cfg.presentation,size=p.size,customLabel=String(cfg.label||'').trim(),label=customLabel||componentTypeCaption(n,s),labelMode=SovSchematicData.effectiveLabelMode(n);
  if(labelMode!=='none'&&label){
    const t=document.createElementNS('http://www.w3.org/2000/svg','text');
    t.setAttribute('text-anchor','middle');t.setAttribute('class',labelMode==='outside'?'outside-label':'component-label');
    // An outside label stands on the ground, not on the card: the muted ink, as far as that ground needs.
    if(labelMode==='outside')t.style.fill=roleInk(componentBackdropMode(n)==='none'?'--canvas-ink':'--muted','#6C6C65',componentFillGround(n));
    if(componentHostedOnWire(n)&&componentBackdropMode(n)==='none'){
      const box=componentInlineGraphicBox(n);t.setAttribute('x','0');t.setAttribute('y',String(box.y+box.h+11));
    }else if(labelMode==='inside'){t.setAttribute('x','0');t.setAttribute('y',String(Math.min(size.h/2-10,24)))}
    else if(labelMode==='outside'){t.setAttribute('x','0');t.setAttribute('y',String(size.h/2+18))}
    // Inside the innermost line: a label never straddles a section's own boundary.
    // A container's name heads it, under its glyph; a card's sits at its foot.
    else if(componentAcceptsChildren(n)&&((p.graphic?.kind&&p.graphic.kind!=='none')||nodes.some(c=>c.parentId===n.id))){const box=componentInlineGraphicBox(n),glyph=p.graphic?.kind&&p.graphic.kind!=='none';t.setAttribute('x','0');t.setAttribute('y',String(glyph?box.y+box.h+12:box.y+10))}
    else {const inset=componentSectionInset(n),sec=componentForm(n).section?SovSchematicData.componentSection(n):null,bevel=sec&&(sec.core?.fill||'solid')==='solid';t.setAttribute('x','0');t.setAttribute('y',String(size.h/2-(bevel?15:inset?11:8)-inset))}
    t.textContent=label;g.appendChild(t);
    // Where the title sits before any subtitle, and which way its block grows from there: up from
    // the foot of a card, down under a container's glyph, below the body, or under a wire's glyph.
    {const y0=Number(t.getAttribute('y'))||0;t.dataset.y0=String(y0);
     t.dataset.grow=labelMode==='outside'||(componentAcceptsChildren(n)&&y0<0)||(componentHostedOnWire(n)&&componentBackdropMode(n)==='none')?'down':'up'}
    // A subtitle sits under its title; the title steps up a line to make room. On a card the two
    // are laid out again as one block once drawn (fitComponentLabels).
    const subtitle=String(cfg.subtitle||'').trim();
    if(subtitle&&labelMode!=='none'){
      const u=document.createElementNS('http://www.w3.org/2000/svg','text');u.setAttribute('class','component-subtitle');u.setAttribute('text-anchor','middle');
      const y=Number(t.getAttribute('y'))||0,below=labelMode==='outside'||(componentAcceptsChildren(n)&&t.getAttribute('y')&&y<0);
      const step=SovSchematicNotation.drawnSize(SovSchematicNotation.tokens(diagram).type,'subtitle')*1.3;
      u.setAttribute('x','0');u.setAttribute('y',String(below?y+step:y));if(!below)t.setAttribute('y',String(y-step));
      u.textContent=subtitle;g.appendChild(u);
    }
  }
  const annotation=String(p.text||'').trim();
  if(annotation&&annotation!==label&&annotation!==s.name){
    const t=document.createElementNS('http://www.w3.org/2000/svg','text');
    t.setAttribute('class','internal-text');t.setAttribute('text-anchor','middle');t.setAttribute('x','0');
    const lines=appendMarkdownLite(t,annotation,{x:0,lineHeight:11});
    t.setAttribute('y',componentAcceptsChildren(n)?String(-p.size.h/2+72):String(5-(lines-1)*5.5));g.appendChild(t);
  }
}
// Body text is a small, safe Markdown (NOTATION-MODEL.md §4): **bold**, *italic*, `code`, line
// breaks and "- " list items. Everything goes in as text content; nothing is read as markup.
function appendMarkdownLite(textEl,source,{x=0,lineHeight=11}={}){
  const lines=String(source).replace(/\r/g,'').split('\n').slice(0,6);
  lines.forEach((raw,i)=>{
    const line=document.createElementNS('http://www.w3.org/2000/svg','tspan');line.setAttribute('x',String(x));if(i)line.setAttribute('dy',String(lineHeight));
    const text=raw.replace(/^\s*[-*]\s+/,'• ');
    for(const part of text.split(/(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)/).filter(Boolean)){
      const run=document.createElementNS('http://www.w3.org/2000/svg','tspan');
      if(/^\*\*.+\*\*$/.test(part)){run.setAttribute('class','md-strong');run.textContent=part.slice(2,-2)}
      else if(/^\*.+\*$/.test(part)){run.setAttribute('class','md-em');run.textContent=part.slice(1,-1)}
      else if(/^`.+`$/.test(part)){run.setAttribute('class','md-code');run.textContent=part.slice(1,-1)}
      else run.textContent=part;
      line.appendChild(run);
    }
    textEl.appendChild(line);
  });
  return lines.length;
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
// The ground this region's fill moves toward its colour from: a card nested on a Component's
// interior takes that host's own drawn fill (read back from the DOM, since hosts are rendered
// before their children by nodeDepth), a card that is a member of a coloured group on the global
// canvas takes that group's region fill, and any other card takes the bare canvas. Each level is
// then the one above it moved toward its own colour, so nesting reads without a shadow.
function componentFillGround(n){
  const surface=n.canvasId||GLOBAL_CANVAS_ID;
  if(surface.startsWith('canvas:component:')){
    const host=nodesG.querySelector(`:scope > .node[data-id="${CSS.escape(surface.slice('canvas:component:'.length))}"]`);
    const hostFill=host?host.style.getPropertyValue('--component-interior-fill').trim():'';
    if(/^#[0-9a-f]{6}$/i.test(hostFill))return hostFill;
    return canvasTone();
  }
  const group=nodes.find(g=>isGroupComponent(g)&&!isEffectivelyHidden(g)
    &&Array.isArray(g.config?.members)&&g.config.members.includes(n.id)
    &&Number.isInteger(g.config?.colorSlot)&&g.config.colorSlot>0);
  if(group)return componentSurfaceFill(slotColor(group.config.colorSlot),.9);
  return canvasTone();
}
function renderComponentVisual(g,n,cfg,s,signalColor){
  const p=cfg.presentation,size=p.size,form=componentForm(n);
  const boundaryColor=slotColor(cfg.colorSlot),interiorColor=slotColor(p.interiorColorSlot);
  const mixedInterior=colorEngine.diffuse?mixHex([interiorColor,signalColor],[.66,.34]):interiorColor;
  const ground=componentFillGround(n);
  // A card is a light tint of its slot, so ink and accents carry the picture, not a gray mass;
  // a container is lighter still, a wash that holds its children without competing with them.
  const materialFill=materialFillColor(componentSurfaceFill(mixedInterior,componentAcceptsChildren(n)?.975:.955,ground),form.body.material);
  // A section fills its regions by what they are: solid is the card's material, space is a wash.
  g.style.setProperty('--section-solid',materialFillColor(componentSurfaceFill(mixedInterior,.86,ground),form.body.material));
  g.style.setProperty('--section-space',componentSurfaceFill(mixedInterior,.985,ground));
  g.dataset.material=form.body.material;g.dataset.dimension=String(form.dimension);
  g.style.setProperty('--component-color',boundaryColor);
  g.style.setProperty('--component-boundary-color',boundaryColor);
  g.style.setProperty('--component-interior-ink',ensureContrast(interiorColor,materialFill,3));
  g.style.setProperty('--component-interior-fill',materialFill);
  // Text on the card is its colour darkened (or lightened) until it reads: WCAG's 4.5:1 for text,
  // where the outline and glyph only need 3:1.
  // A faded (status opacity) body shows the fill over what is behind the card, so the ink is judged
  // on that blend; the text itself is drawn opaque.
  const fade=statusFade(n),seenFill=fade<1?mixHex([materialFill,ground],[fade,1-fade]):materialFill;
  g.style.setProperty('--component-text-color',ensureContrast(boundaryColor,seenFill,TEXT_FLOOR));
  const backdrop=componentBackdropMode(n);g.dataset.backdrop=backdrop;
  if(form.dimension===0){
    const pointCfg=componentAttachmentPoint(n,'self')?.config,point=document.createElementNS('http://www.w3.org/2000/svg','circle');
    // A Point that carries wires is structure (a terminal, a junction) and is drawn solid; an
    // empty Point stays an open ring, an attachment waiting for a wire.
    const ends=wires.reduce((k,w)=>k+(w.a===n.id?1:0)+(w.b===n.id?1:0),0);
    // A through-point spans its band: a capsule across the skin, the channel it is.
    {const pos=componentPlacement(n).kind==='edge'?SovSchematicData.pointSectionPosition(diagram,n.id,'out'):null;
     if(pos&&pos.through!=null){const host=nodes.find(h=>h.id===pos.owner),s=SovSchematicData.componentSection(host),T=s.bands[pos.through]?.thickness||8;
       const cap=document.createElementNS('http://www.w3.org/2000/svg','rect');cap.setAttribute('class','through-mark');cap.setAttribute('x','-4.5');cap.setAttribute('y',String(-T/2-3));cap.setAttribute('width','9');cap.setAttribute('height',String(T+6));cap.setAttribute('rx','4.5');g.appendChild(cap)}}
    point.setAttribute('class','dimensional-point-body port attachment-point'+(ends?' carries':'')+(ends>=3?' junction':''));point.dataset.point='self';point.dataset.port='out';point.dataset.face=pointCfg?.face||'external';point.setAttribute('r',String(ends?(ends>=3?4.5:4):Math.max(5,Math.min(12,5+form.body.thickness*.18))));point.style.setProperty('--port-color',activePortChannel(pointCfg||{}).color);g.appendChild(point);
    const display=String(cfg.label||'').trim()||componentTypeCaption(n,s);
    if(display){
      // A hosted Point inherits its host's angle; its label stays upright and below the point in world space.
      const angle=componentHostAngle(n),label=document.createElementNS('http://www.w3.org/2000/svg','text');
      label.setAttribute('class','component-label dimensional-point-label');label.setAttribute('y','0');
      // A boundary Point labels the crossing from outside its host, clear of the wire it carries.
      const edge=componentPlacement(n).kind==='edge'?componentPlacement(n).side:null;
      // Below the wire it carries: a wire's own label sits above its line.
      const at={left:[-8,15,'end'],right:[8,15,'start'],top:[8,-10,'start'],bottom:[8,16,'start']}[edge]||[0,22,'middle'];
      label.setAttribute('text-anchor',at[2]);
      label.setAttribute('transform',`rotate(${-angle}) translate(${at[0]} ${at[1]})`);label.textContent=display;g.appendChild(label);
    }
    return
  }
  if(form.dimension===1){const line=document.createElementNS('http://www.w3.org/2000/svg','line');line.setAttribute('class','dimensional-path-body');line.setAttribute('x1',String(-size.w/2));line.setAttribute('x2',String(size.w/2));line.setAttribute('y1','0');line.setAttribute('y2','0');line.setAttribute('stroke-width',String(Math.max(2,Math.min(14,2+form.body.thickness*.18))));g.appendChild(line);appendComponentGraphic(g,n,cfg);appendComponentText(g,n,cfg,s);return}
  if(backdrop!=='none'){
    // Depth is elevation, a soft shadow by nesting level (NOTATION-MODEL.md §3), never a second outline.
    const section=SovSchematicData.componentSection(n),T=SovSchematicNotation.tokens(diagram);
    const sectioned=!!(section&&section.lines.length>=2),total=sectioned?section.bands.reduce((a,b)=>a+b.thickness,0):0;
    const body=document.createElementNS('http://www.w3.org/2000/svg','rect');body.setAttribute('class','body');body.setAttribute('x',String(-size.w/2));body.setAttribute('y',String(-size.h/2));body.setAttribute('width',String(size.w));body.setAttribute('height',String(size.h));body.setAttribute('rx',String(SovSchematicNotation.cornerRadius(T,{total,inset:0,w:size.w,h:size.h,sectioned})));
    // A thicker body stands taller: its shadow falls further.
    {const E=SovSchematicNotation.elevation(T,componentElevation(n),surfaceAppearance()),th=Math.max(0,Number(form.body.thickness)||0);
     if(E){const dy=E.dy+Math.min(4,th*.08),blur=E.blur+Math.min(3,th*.06);body.style.filter=`drop-shadow(0 ${+dy.toFixed(2)}px ${+blur.toFixed(2)}px rgba(${surfaceAppearance()==='dark'?'0,0,0':'40,36,28'},${E.opacity}))`;body.dataset.elevation=String(componentElevation(n))}}
    g.appendChild(body);
    // A section's lines inside the outline: each line an inset boundary, each region filled as
    // what it is (solid material, or space). The outline is line L0. Corners are concentric.
    if(sectioned){
      let inset=0;
      for(let i=1;i<section.lines.length;i++){
        inset+=section.bands[i-1]?.thickness||0;const w=size.w-inset*2,h=size.h-inset*2;if(w<=4||h<=4)break;
        const fill=(section.bands[i]?.fill)||section.core?.fill||'solid',rx=SovSchematicNotation.cornerRadius(T,{total,inset,w,h,sectioned:true});
        const r=document.createElementNS('http://www.w3.org/2000/svg','rect');r.setAttribute('class',`section-line fill-${fill}`);
        r.setAttribute('x',String(-w/2));r.setAttribute('y',String(-h/2));r.setAttribute('width',String(w));r.setAttribute('height',String(h));
        r.setAttribute('rx',String(rx));r.dataset.line=section.lines[i].id;g.appendChild(r);
        // A band's depth sinks what lies inside it: a recess, shaded from the top left.
        if(i===1&&Number(section.bands[0]?.depth||0)>0)appendBevel(g,w,h,rx,'recess');
      }
      body.classList.add(`fill-${section.bands[0]?.fill||'solid'}`);
    }else if(form.section&&section){body.classList.add(`fill-${section.core?.fill||'solid'}`)}
    // A solid core is bevelled, lit from the top left, so a disk reads as a body, not a blank card.
    if(form.section&&section&&(section.core?.fill||'solid')==='solid'&&!componentAcceptsChildren(n))appendSolidBevel(g,size,section);
    if(section&&section.lines.length>=2){}else if(form.frame.mode!=='none'||backdrop==='frame'){
      const inset=Math.max(4,Math.min(Math.min(size.w,size.h)/3,form.frame.thickness||12));const frameDepth=Math.min(14,Math.max(0,form.frame.depth*.16));
      if(frameDepth>0)appendBevel(g,size.w-inset*2,size.h-inset*2,SovSchematicNotation.cornerRadius(SovSchematicNotation.tokens(diagram),{total:inset,inset,w:size.w-inset*2,h:size.h-inset*2,sectioned:true}),'recess');
      const inner=document.createElementNS('http://www.w3.org/2000/svg','rect');inner.setAttribute('class','component-frame-inner');inner.setAttribute('x',String(-size.w/2+inset));inner.setAttribute('y',String(-size.h/2+inset));inner.setAttribute('width',String(Math.max(1,size.w-inset*2)));inner.setAttribute('height',String(Math.max(1,size.h-inset*2)));inner.setAttribute('rx',String(Math.max(2,Math.min(9,(size.h-inset*2)*.08))));g.appendChild(inner);
    }
    if(componentAcceptsChildren(n)){const guidePad=Math.max(p.padding,(section&&section.lines.length>=2?section.bands.reduce((a,b)=>a+b.thickness,0):0)+6);const guide=document.createElementNS('http://www.w3.org/2000/svg','rect');guide.setAttribute('class','container-guide');guide.setAttribute('x',String(-size.w/2+guidePad));guide.setAttribute('y',String(-size.h/2+guidePad));guide.setAttribute('width',String(Math.max(1,size.w-guidePad*2)));guide.setAttribute('height',String(Math.max(1,size.h-guidePad*2)));guide.setAttribute('rx','6');g.appendChild(guide)}
  }else if(componentHostedOnWire(n)){
    const half=componentInlineTerminalHalfSpan(n);
    if(half>0){const cut=document.createElementNS('http://www.w3.org/2000/svg','rect');cut.setAttribute('class','inline-wire-cut');cut.setAttribute('x',String(-half));cut.setAttribute('y','-8');cut.setAttribute('width',String(half*2));cut.setAttribute('height','16');cut.setAttribute('rx','2');g.appendChild(cut)}
  }
  appendComponentGraphic(g,n,cfg);appendComponentText(g,n,cfg,s);
}
// Where two or more wires share one point of a card, a dot marks where their lines part:
// connected, not crossing. The dot is found from the rendered lines, walking back from the point.
function renderJunctionDots(){
  const layer=document.getElementById('junctionLayer');if(!layer)return;layer.replaceChildren();
  const groups=new Map();
  for(const w of wires)for(const [end,id,side] of [['a',w.a,w.aSide],['b',w.b,w.bSide]]){
    if(!id)continue;const n=nodes.find(x=>x.id===id);if(!n||componentForm(n).dimension===0||isEffectivelyHidden(n))continue; // a Point is its own junction
    const k=`${id}|${side}`;if(!groups.has(k))groups.set(k,[]);groups.get(k).push({w,end});
  }
  for(const [key,list] of groups){
    if(list.length<2)continue;
    const paths=list.map(({w,end})=>{const el=workspace.querySelector(`.wire-group[data-wire-id="${CSS.escape(w.id)}"] path.wire`);return el?{el,L:el.getTotalLength(),fromEnd:end==='b'}:null}).filter(Boolean);
    if(paths.length<2)continue;
    const at=(p,d)=>p.el.getPointAtLength(p.fromEnd?Math.max(0,p.L-d):Math.min(p.L,d));
    let join=at(paths[0],0);const reach=Math.min(...paths.map(p=>p.L));
    for(let d=0;d<=reach;d+=2){const pts=paths.map(p=>at(p,d));if(pts.some(q=>Math.hypot(q.x-pts[0].x,q.y-pts[0].y)>1.2))break;join=pts[0]}
    const dot=document.createElementNS('http://www.w3.org/2000/svg','circle');dot.setAttribute('class','junction-dot');dot.dataset.port=key;
    dot.setAttribute('cx',String(join.x));dot.setAttribute('cy',String(join.y));dot.setAttribute('r','3.6');layer.appendChild(dot);
  }
}
// The notation's stroke tokens, as the CSS custom properties the stylesheet draws with.
function applyNotationTokens(){
  const T=SovSchematicNotation.tokens(diagram);
  for(const [k,v] of Object.entries(T.stroke))workspace.style.setProperty(`--stroke-${k}`,`${v}px`);
  // Derived weights are computed here, not with calc(): a computed calc() is not a length a reader can parse.
  workspace.style.setProperty('--stroke-structure-container',`${+(T.stroke.structure*1.2).toFixed(2)}px`);
  workspace.style.setProperty('--stroke-structure-selected',`${+(T.stroke.structure*1.9).toFixed(2)}px`);
  for(const [role,t] of Object.entries(T.type||{})){if(role==='screen')continue;workspace.style.setProperty(`--type-${role}-size`,`${t.size}px`);workspace.style.setProperty(`--type-${role}-weight`,String(t.weight))}
}
function markersById(){
  const byId=new Map();
  for(const marker of SovSchematicData.markersFor(diagram)){
    const list=byId.get(marker.id);if(list)list.push(marker);else byId.set(marker.id,[marker]);
  }
  return byId;
}
function appendMarkerBadge(host,markers,x,y){
  const badge=document.createElementNS('http://www.w3.org/2000/svg','g');
  badge.setAttribute('class','marker-badge');
  badge.setAttribute('transform',`translate(${x} ${y})`);
  badge.setAttribute('title',markers.map(m=>m.message).join('; '));
  const dot=document.createElementNS('http://www.w3.org/2000/svg','circle');
  dot.setAttribute('class','marker-badge-dot');dot.setAttribute('r','7');
  badge.appendChild(dot);
  const mark=document.createElementNS('http://www.w3.org/2000/svg','text');
  mark.setAttribute('class','marker-badge-mark');mark.setAttribute('text-anchor','middle');mark.setAttribute('y','3');mark.textContent='!';
  badge.appendChild(mark);
  host.appendChild(badge);
}
function markerCountEl(){
  let el=document.getElementById('markerCount');
  if(!el&&statusEl?.parentElement){
    el=document.createElement('span');el.id='markerCount';el.className='marker-count';
    statusEl.parentElement.insertBefore(el,statusEl.nextSibling);
  }
  return el;
}
// Groups (SECTION-MODEL.md "Groups (reading only)"): a region drawn behind every other node and
// every wire on its canvas. On the global canvas they sit in their own layer just before the wire
// layer; on a Component's interior, directly after the host, before the wires lifted there and
// the host's children. A group is not a body: it hosts nothing, has no ports and takes no gesture.
function groupLayer(){
  let layer=document.getElementById('groupLayer');
  if(!layer){layer=document.createElementNS('http://www.w3.org/2000/svg','g');layer.setAttribute('id','groupLayer');workspace.insertBefore(layer,wiresG)}
  return layer;
}
function placeGroupRegion(g,n){
  const R=SovSchematicData.groupRect(diagram,n.id,componentSize);if(!R)return;
  const rect=g.querySelector(':scope > .group-region'),title=g.querySelector(':scope > .group-title');
  if(rect){rect.setAttribute('x',String(R.l));rect.setAttribute('y',String(R.t));rect.setAttribute('width',String(Math.max(1,R.w)));rect.setAttribute('height',String(Math.max(1,R.h)))}
  if(title){title.setAttribute('x',String(R.l+12));title.setAttribute('y',String(R.t+19))}
  const badge=g.querySelector(':scope > .marker-badge');if(badge)badge.setAttribute('transform',`translate(${R.r} ${R.t})`);
}
// Keeps every drawn region on its members while they move (renderWires runs on drag frames).
function refreshGroupRegions(){
  for(const g of workspace.querySelectorAll('.node.group')){const n=nodes.find(x=>x.id===g.dataset.id);if(n)placeGroupRegion(g,n)}
}
function renderGroups(markers=markersById()){
  const layer=groupLayer();layer.replaceChildren();
  const T=SovSchematicNotation.tokens(diagram);
  for(const n of nodes){
    if(!isGroupComponent(n)||isEffectivelyHidden(n))continue;
    const cfg=n.config||{},surface=n.canvasId||GLOBAL_CANVAS_ID,editor=entityEditorState(n);
    const g=document.createElementNS('http://www.w3.org/2000/svg','g');
    g.setAttribute('class','node group'+(selectedComponentIds.has(n.id)?' selected':''));g.dataset.id=n.id;g.dataset.canvasId=surface;g.style.opacity=String(editor.opacity);
    const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');rect.setAttribute('class','group-region');
    rect.setAttribute('rx',String(T.radius?.card??10));
    // Slot 0 is the colour every record is given, so only a chosen slot tints the region.
    const slot=Number.isInteger(cfg.colorSlot)&&cfg.colorSlot>0?cfg.colorSlot:null;
    const regionFill=slot!=null?componentSurfaceFill(slotColor(slot),.9):null;
    rect.style.fill=regionFill??'none';rect.style.fillOpacity='1';
    rect.style.stroke='var(--muted)';rect.style.strokeWidth='var(--stroke-structure)';rect.style.pointerEvents='none';
    g.appendChild(rect);
    const label=String(cfg.label||'').trim();
    if(label){const title=document.createElementNS('http://www.w3.org/2000/svg','text');title.setAttribute('class','group-title');title.dataset.role='title';
      // The muted ink, darkened (or lightened) only as far as text needs to read on the region: 4.5:1, as card text.
      const muted=(getComputedStyle(workspace).getPropertyValue('--muted')||'').trim(),ink=/^#[0-9a-f]{6}$/i.test(muted)?muted:'#6C6C65';
      title.style.fill=ensureContrast(ink,regionFill??canvasTone(),4.6);title.textContent=label;g.appendChild(title)}
    {const own=markers.get(n.id);if(own)appendMarkerBadge(g,own,0,0)}
    placeGroupRegion(g,n);
    const host=surface.startsWith('canvas:component:')?nodesG.querySelector(`:scope > .node[data-id="${CSS.escape(surface.slice('canvas:component:'.length))}"]`):null;
    if(host){let at=host;while(at.nextElementSibling?.classList.contains('group'))at=at.nextElementSibling;at.after(g)}
    else layer.appendChild(g);
  }
}
// Status and waits-on (NOTATION-MODEL.md "Statuses"). A record's status is the entry its notation
// declares under that id; there is no built-in list, so an undeclared one draws nothing (validation
// reports it). Every style is an attribute or an inline style, so a picture carries it.
function declaredStatus(record){
  const id=record?.config?.status;if(typeof id!=='string')return null;
  return (activeNotation().statuses||[]).find(s=>s&&s.id===id)||null;
}
function statusTitle(status){return String(status?.title||status?.id||'')}
// 'Bdo, rule R-29, decision D1': each entry's label, or else its kind and id.
function waitsOnList(list){return Array.isArray(list)?list.filter(w=>w&&typeof w==='object').map(w=>String(w.label||'').trim()||`${w.kind} ${w.id}`).join(', '):''}
const CAPTION_STYLE='font-size:calc(clamp(12px,var(--type-caption-size,9px) * var(--zoom,1),16px) / var(--zoom,1));font-weight:var(--type-caption-weight,600)';
// A label's ink is its role colour moved (darker in light, lighter in dark) only as far as TEXT_FLOOR
// against the colour actually behind it: the ground a card stands on, a region's fill, or the canvas.
const TEXT_FLOOR=4.6;
function roleInk(name,fallback,ground){const v=(getComputedStyle(workspace).getPropertyValue(name)||'').trim();return ensureContrast(/^#[0-9a-f]{6}$/i.test(v)?v:fallback,ground,TEXT_FLOOR)}
function statusInk(ground=canvasTone()){return roleInk('--muted','#6C6C65',ground)}
// The opacity a card's status declares (1 when none): drawn on the card's body, glyph, leads, ports
// and marks, never on its text.
function statusFade(n){const st=declaredStatus(n),o=st?.opacity;return typeof o==='number'&&Number.isFinite(o)&&o>=0&&o<1?o:1}
function applyStatusFade(g,n){
  const fade=statusFade(n);if(fade>=1||componentForm(n).dimension!==2)return;
  for(const el of g.children){
    if(el.localName==='text'||el.classList.contains('status-chip'))continue;
    el.style.opacity=String((parseFloat(getComputedStyle(el).opacity)||1)*fade);
  }
}
// A status chip's ink on a solid tone: near-black or white, whichever has the higher WCAG contrast.
function statusChipInk(tone){return contrastRatio(tone,'#141414')>=contrastRatio(tone,'#FFFFFF')?'#141414':'#FFFFFF'}
// A card's status: a chip in its top-right corner, 6 in from both edges, holding the status title in
// the caption role; a dashed outline and an opacity when the status declares them. A status that
// declares a tone (safe, alert, danger) is a solid pill in that status tone, its glyph before the title.
function appendComponentStatus(g,n){
  const st=declaredStatus(n);if(!st||componentForm(n).dimension!==2)return;
  // The caption role at its base size: the chip is part of the card and scales with it.
  const {w,h}=componentSize(n),T=SovSchematicNotation.tokens(diagram),px=Number(T.type?.caption?.size)||9,weight=T.type?.caption?.weight||600;
  const cfg=componentConfig(n),edge=g.style.getPropertyValue('--component-boundary-color').trim()||slotColor(cfg.colorSlot),fill=g.style.getPropertyValue('--component-interior-fill').trim()||'#FFFFFF';
  // The chip's own fill is its edge colour at .16 over the card fill, itself faded over the ground.
  const fade=statusFade(n),seen=fade<1?mixHex([fill,componentFillGround(n)],[fade,1-fade]):fill,chipFill=mixHex([edge,seen],[.16,.84]);
  const tone=['safe','alert','danger'].includes(st.tone)?statusTone(st.tone):null,glyph=tone&&typeof st.glyph==='string'?st.glyph.trim():'';
  const title=statusTitle(st),text=glyph?`${glyph} ${title}`:title,ch=Math.round(px*1.5);
  const cw=tone?Math.ceil(text.length*px*.6+px*1.4):Math.ceil(title.length*px*.6+px),x=w/2-6-cw,y=-h/2+6;
  const chip=document.createElementNS('http://www.w3.org/2000/svg','g');chip.setAttribute('class','status-chip');chip.dataset.status=st.id;
  const r=document.createElementNS('http://www.w3.org/2000/svg','rect');
  r.setAttribute('x',String(x));r.setAttribute('y',String(y));r.setAttribute('width',String(cw));r.setAttribute('height',String(ch));r.setAttribute('rx',String(ch/2));
  r.setAttribute('style',tone?`fill:${tone};fill-opacity:1;stroke:none`:`fill:${edge};fill-opacity:.16;stroke:${edge};stroke-width:1`);chip.appendChild(r);
  const t=document.createElementNS('http://www.w3.org/2000/svg','text');t.dataset.role='caption';
  t.setAttribute('x',String(x+cw/2));t.setAttribute('y',String(y+ch/2));t.setAttribute('text-anchor','middle');t.setAttribute('dominant-baseline','central');
  t.setAttribute('style',`font-size:${px}px;font-weight:${weight};fill:${tone?statusChipInk(tone):ensureContrast(edge,chipFill,TEXT_FLOOR)};stroke:none;pointer-events:none`);t.textContent=text;chip.appendChild(t);
  g.appendChild(chip);
  if(st.outline==='dashed'){const body=g.querySelector(':scope > .body');if(body){body.setAttribute('stroke-dasharray','6 4');body.style.strokeDasharray='6 4'}}
}
// What a card waits on, under it and below any outside label: 'Waits on Bdo, rule R-29'.
function appendComponentWaitsOn(g,n){
  const list=waitsOnList(n?.config?.waitsOn);if(!list)return;
  const {h}=componentSize(n);let y=h/2+18;
  for(const el of g.querySelectorAll(':scope > text.outside-label,:scope > text.component-subtitle')){if(el.dataset.lod==='hidden')continue;try{const b=el.getBBox();if(b.height)y=Math.max(y,b.y+b.height+14)}catch(_){}}
  const t=document.createElementNS('http://www.w3.org/2000/svg','text');t.setAttribute('class','waits-on');t.dataset.role='caption';
  t.setAttribute('x','0');t.setAttribute('y',String(y));t.setAttribute('text-anchor','middle');
  t.setAttribute('style',`${CAPTION_STYLE};fill:${statusInk(componentFillGround(n))};stroke:none;pointer-events:none`);t.textContent='Waits on '+list;g.appendChild(t);
}
function render(){
  applyNotationTokens();
  componentLabelFitZoom=workspace.style.getPropertyValue('--zoom'); // the cards drawn below are fitted at this zoom
  if(typeof buildSymbolPalette==='function')buildSymbolPalette();
  syncAllNodeBoundaryContext();
  const signalState=computeSignalState();
  const componentSignals=signalState.colors;
  const markers=markersById();
  nodesG.innerHTML='';
  const unplacedIds=new Set(typeof layoutUnplacedIds==='function'?layoutUnplacedIds():[]);
  [...nodes].sort((a,b)=>nodeDepth(a)-nodeDepth(b)).forEach(n=>{
    if(isEffectivelyHidden(n)||isGroupComponent(n))return; // groups are drawn by renderGroups, behind
    const s=symbolOf(n.symbolId),cfg=componentConfig(n),g=document.createElementNS('http://www.w3.org/2000/svg','g'),editor=entityEditorState(n);
    {const form=componentForm(n),backdrop=componentBackdropMode(n);g.setAttribute('class','node'+(unplacedIds.has(n.id)?' unplaced':'')+(n.symbolId==='blank'?' blank':'')+(selectedComponentIds.has(n.id)?' selected':'')+(componentAcceptsChildren(n)?' is-container':'')+(form.frame.mode==='shell'?' form-shell':'')+(form.frame.mode==='frame'?' form-frame':'')+(n.parentId?' nested-child':'')+(componentHostedOnWire(n)?' wire-hosted':'')+(backdrop==='none'?' backdrop-none':'')+(editor.pinned?' is-pinned':'')+(editor.locked?' is-locked':''));}
    g.style.opacity=String(editor.opacity);
    g.dataset.id=n.id;if(n.parentId)g.dataset.parentId=n.parentId;
    const signalColor=componentSignals.get(n.id)||cfg.color;
    {const angle=componentHostAngle(n),attached=componentHostedOnWire(n)||componentHostedOnComponentPath(n)||componentHostedOnComponentEdge(n);g.setAttribute('transform',`translate(${n.x} ${n.y})${attached?` rotate(${angle})`:''}`)}
    renderComponentVisual(g,n,cfg,s,signalColor);appendComponentStatus(g,n);
    if(!editor.pinned&&!editor.locked&&componentForm(n).dimension===2)appendComponentTransformHandles(g,n,cfg);
    {const nodeMarkers=markers.get(n.id);if(nodeMarkers){const size=componentSize(n);appendMarkerBadge(g,nodeMarkers,size.w/2,-size.h/2)}}
    const renderedPoints=componentAttachmentPoints(n);for(const point of renderedPoints){
      const pointId=point.id,pcfg=point.config,local=componentPortLocalPosition(n,pointId);
      const localX=local.x,localY=local.y;
      const hit=document.createElementNS('http://www.w3.org/2000/svg','circle');
      hit.setAttribute('class','port-hit attachment-point-hit');hit.dataset.point=pointId;hit.dataset.side=point.compatId;hit.dataset.canvasIds=portExposedCanvasIds(n,pointId).join(' ');hit.setAttribute('cx',localX);hit.setAttribute('cy',localY);hit.setAttribute('r','16');
      let vis=null;const selfPoint=componentForm(n).dimension===0&&pointId==='self';
      if(selfPoint){vis=g.querySelector('.dimensional-point-body');if(vis){vis.dataset.point=pointId;vis.dataset.port=point.compatId;vis.dataset.face=pcfg.face||'external';vis.style.setProperty('--port-color',activePortChannel(pcfg).color)}}
      else{vis=document.createElementNS('http://www.w3.org/2000/svg','circle');vis.setAttribute('class','port attachment-point');vis.dataset.point=pointId;vis.dataset.port=point.compatId;vis.dataset.face=pcfg.face||'external';vis.setAttribute('cx',localX);vis.setAttribute('cy',localY);vis.setAttribute('r','5');vis.style.setProperty('--port-color',activePortChannel(pcfg).color)}
      {const pos=componentForm(n).dimension===2?SovSchematicData.pointSectionPosition(diagram,n.id,point.compatId):null;
       if(pos&&pos.through!=null){const s=SovSchematicData.componentSection(n),T=s.bands[pos.through]?.thickness||8,side=point.side,vertical=side==='left'||side==='right';
         const cap=document.createElementNS('http://www.w3.org/2000/svg','rect');cap.setAttribute('class','through-mark');
         cap.setAttribute('x',String(vertical?localX-T/2-3:localX-4.5));cap.setAttribute('y',String(vertical?localY-4.5:localY-T/2-3));cap.setAttribute('width',String(vertical?T+6:9));cap.setAttribute('height',String(vertical?9:T+6));cap.setAttribute('rx','4.5');g.appendChild(cap)}}
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
    appendComponentLeads(g,n);appendTerminalMarks(g,n);
    bindNode(g,n); nodesG.appendChild(g); fitComponentLabels(g,n); appendComponentWaitsOn(g,n); applyStatusFade(g,n);
  });
  renderGroups(markers);
  // Buses (src/41-buses.js): bands in the group layer, after the group regions, behind every wire.
  if(typeof renderBuses==='function')renderBuses(groupLayer());
  renderWires(signalState,markers);
  {const total=[...markers.values()].reduce((sum,list)=>sum+list.length,0),countEl=markerCountEl();if(countEl)countEl.textContent=total?`${total} marker${total===1?'':'s'}`:''}
  renderJunctionDots();
  if(typeof paintSim==='function')paintSim();
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
// Where wires cross, in world space: no arrowhead is placed within reach of one, on either wire.
let arrowKeepClear=[];
const ARROW_CROSSING_CLEAR=24;
function stableArrowPoint(path,targetD,minD,maxD){
  const offsets=[0,10,-10,20,-20,30,-30,42,-42];
  let fallback=null;
  for(const off of offsets){
    const d=Math.max(minD,Math.min(maxD,targetD+off));
    const q=pointAngleAtDistance(path,d,3);
    if(arrowKeepClear.some(c=>Math.hypot(c.x-q.x,c.y-q.y)<ARROW_CROSSING_CLEAR))continue;
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
  // A short directed wire still says which way it runs: one mark at its middle.
  if(L<72) return L>=20?[L/2]:[];

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
  const margin=Math.min(L/2,Math.min(46,Math.max(26,L*.16)));
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

  // A resolved rate of exactly 0 (the document's own rate, issue #40) draws the packet at its
  // start point and stops there: no animateMotion element, so `Number(rate)||1` - which would
  // otherwise read 0 as falsy and silently pick 1 - never gets the chance to erase a pause. Any
  // other rate, including a small positive one, keeps today's duration math and its .1 floor.
  if(Number(rate)===0){
    const startPoint=document.createElementNS('http://www.w3.org/2000/svg','path');
    startPoint.setAttribute('d',motionPath);
    const start=startPoint.getPointAtLength(0);
    packet.setAttribute('transform',`translate(${start.x} ${start.y})`);
  }else{
    const duration=packetTravelSeconds(pathLength)/Math.max(.1,Number(rate)||1);
    // Packet skin is identity, not field diffusion.
    // It stays constant across the trip while the carrier/wire field may blend.
    const motion=document.createElementNS('http://www.w3.org/2000/svg','animateMotion');
    motion.setAttribute('path',motionPath);
    motion.setAttribute('dur',`${duration}s`);
    motion.setAttribute('repeatCount','indefinite');
    motion.setAttribute('calcMode','linear');
    packet.appendChild(motion);
  }
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
      appendWirePacket(group,forwardPath,pathLength,signal.forwardBody,signal.forwardBoundary,'forward',(endpointShowsChannelTag(w,'a')?wireEndpointMarker(w,'a'):''),packetRateForWire(w,'forward'),wireOperation(w,'forward'))
      count++;
    }
  }else if(cfg.direction==='reverse'){
    if(signal.reverseLive){
      appendWirePacket(group,reversePath,pathLength,signal.reverseBody,signal.reverseBoundary,'reverse',(endpointShowsChannelTag(w,'b')?wireEndpointMarker(w,'b'):''),packetRateForWire(w,'reverse'),wireOperation(w,'reverse'))
      count++;
    }
  }else if(cfg.direction==='duplex'){
    if(signal.forwardLive){
      appendWirePacket(group,forwardPath,pathLength,signal.forwardBody,signal.forwardBoundary,'forward',(endpointShowsChannelTag(w,'a')?wireEndpointMarker(w,'a'):''),packetRateForWire(w,'forward'),wireOperation(w,'forward'))
      count++;
    }
    if(signal.reverseLive){
      appendWirePacket(group,reversePath,pathLength,signal.reverseBody,signal.reverseBoundary,'reverse',(endpointShowsChannelTag(w,'b')?wireEndpointMarker(w,'b'):''),packetRateForWire(w,'reverse'),wireOperation(w,'reverse'))
      count++;
    }
  }
  return count;
}

// A route drawn with a hop at each crossing it makes over an earlier wire: a half circle that
// lifts it over the other line, so a crossing never reads as a junction (NOTATION-MODEL.md).
const WIRE_HOP_RADIUS=6.5;
function pathWithHops(points,hops){
  const pts=normalizePoints(points);if(!hops?.length||pts.length<2)return pathD(pts);
  const r=WIRE_HOP_RADIUS;let d=`M ${pts[0].x} ${pts[0].y}`;
  for(let i=1;i<pts.length;i++){
    const a=pts[i-1],b=pts[i],h=a.y===b.y,dir=h?Math.sign(b.x-a.x):Math.sign(b.y-a.y);
    const along=c=>h?(c.x-a.x)*dir:(c.y-a.y)*dir,len=h?Math.abs(b.x-a.x):Math.abs(b.y-a.y);
    const mine=hops.filter(c=>(h?Math.abs(c.y-a.y)<.5:Math.abs(c.x-a.x)<.5)&&along(c)>r+2&&along(c)<len-r-2).sort((p,q)=>along(p)-along(q));
    let last=-Infinity;
    for(const c of mine){
      if(along(c)-last<2*r+2)continue;last=along(c);
      // Over the top going right or down; the mirror going left or up. Always the same side.
      const sweep=dir>0?1:0;
      if(h)d+=` H ${c.x-r*dir} A ${r} ${r} 0 0 ${sweep} ${c.x+r*dir} ${c.y}`;
      else d+=` V ${c.y-r*dir} A ${r} ${r} 0 0 ${sweep} ${c.x} ${c.y+r*dir}`;
    }
    d+=h?` H ${b.x}`:` V ${b.y}`;
  }
  return d;
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
// Projection-only geometry: keep the exact points used to paint each path. Label
// layout never asks the router for another route or writes into the document.
const wireLabelPaths=new Map();
function placeWireLabels(){
  const matrix=workspace.getScreenCTM();if(!matrix)return;
  // LAYOUT-MODEL.md "Wire labels": the clearance round a label and the step it slides by, in screen pixels.
  const inverse=matrix.inverse(),clearance=6,step=12;
  const screen=p=>new DOMPoint(p.x,p.y).matrixTransform(matrix);
  const shown=new Map();
  const visible=el=>{
    if(!el||el===workspace)return true;
    if(shown.has(el))return shown.get(el);
    const style=getComputedStyle(el);
    const ok=style.display!=='none'&&style.visibility!=='hidden'&&Number(style.opacity)!==0&&visible(el.parentElement);
    shown.set(el,ok);return ok;
  };
  const rect=el=>{const r=el.getBoundingClientRect();return {l:r.left,r:r.right,t:r.top,b:r.bottom}};
  const intersects=(a,b)=>a.l<b.r&&a.r>b.l&&a.t<b.b&&a.b>b.t;
  // What a label must stay clear of: card bodies, status chips, marker badges and every other text
  // (titles, subtitles, port and bus labels, group titles, end tags). Wire labels join as they are placed.
  const obstacles=[...workspace.querySelectorAll('.node:not(.is-container)>.body,.node:not(.is-container)>.dimensional-point-body,.node:not(.is-container)>.dimensional-path-body,.node:not(.is-container)>.custom-graphic,.status-chip,.marker-badge,#groupLayer text,#nodes text,#wires text')]
    .filter(el=>!el.classList.contains('connection-label')&&!el.closest('.wire-packet')&&visible(el)).map(rect).filter(box=>box.r>box.l||box.b>box.t);
  // A card drawn on a wire has no body shape; its bounds are the body the layout metrics measure.
  for(const el of workspace.querySelectorAll('.node.wire-hosted:not(.is-container)')){
    const n=nodes.find(x=>x.id===el.dataset.id);if(!n||componentForm(n).dimension!==2||!visible(el))continue;
    const R=componentBounds(n),a=screen({x:R.l,y:R.t}),b=screen({x:R.r,y:R.b});
    obstacles.push({l:Math.min(a.x,b.x),r:Math.max(a.x,b.x),t:Math.min(a.y,b.y),b:Math.max(a.y,b.y)});
  }
  // A container is no obstacle, but its border is: a label lies wholly inside it or wholly outside.
  const frames=[...workspace.querySelectorAll('.node.is-container>.body')].filter(visible).map(rect);
  const entries=[...wireLabelPaths].filter(([path])=>path.isConnected&&visible(path)).map(([path,points])=>({path,points:points.map(screen)}));
  // A slab intersection also handles diagonal carrier segments without sampling.
  const crosses=(box,a,b)=>{
    let lo=0,hi=1;
    for(const [start,delta,min,max] of [[a.x,b.x-a.x,box.l,box.r],[a.y,b.y-a.y,box.t,box.b]]){
      if(Math.abs(delta)<1e-9){if(start<min||start>max)return false;continue}
      const u=(min-start)/delta,v=(max-start)/delta;
      lo=Math.max(lo,Math.min(u,v));hi=Math.min(hi,Math.max(u,v));if(lo>hi)return false;
    }
    return true;
  };
  for(const entry of entries){
    const {path,points}=entry,label=path.parentElement.querySelector('.connection-label');
    if(!label||!visible(label))continue;
    const bounds=rect(label),width=bounds.r-bounds.l,height=bounds.b-bounds.t;
    const anchor=screen({x:Number(label.getAttribute('x')),y:Number(label.getAttribute('y'))});
    const offset={x:bounds.l-anchor.x,y:bounds.t-anchor.y};
    const midpoint=screen(path.getPointAtLength(path.getTotalLength()/2)),candidates=[];
    const beside=(p,a,b)=>{
      if(Math.abs(a.y-b.y)<.01){
        candidates.push({l:p.x-width/2,t:p.y-clearance-height},{l:p.x-width/2,t:p.y+clearance});
      }else if(Math.abs(a.x-b.x)<.01){
        candidates.push({l:p.x-clearance-width,t:p.y-height/2},{l:p.x+clearance,t:p.y-height/2});
      }
    };
    const total=path.getTotalLength(),before=screen(path.getPointAtLength(Math.max(0,total/2-.1))),after=screen(path.getPointAtLength(Math.min(total,total/2+.1)));
    beside(midpoint,before,after);
    for(let i=1;i<points.length;i++)beside({x:(points[i-1].x+points[i].x)/2,y:(points[i-1].y+points[i].y)/2},points[i-1],points[i]);
    // Slid along the wire: on every straight run with room for the label and its clearance, a place
    // every step on both sides, outward from the run's middle.
    const slid=[],runs=[points[0]];
    for(let i=1;i<points.length;i++){
      const p=points[i],l=runs.at(-1),a=runs.at(-2);
      if(a&&((Math.abs(a.y-l.y)<.01&&Math.abs(l.y-p.y)<.01)||(Math.abs(a.x-l.x)<.01&&Math.abs(l.x-p.x)<.01)))runs[runs.length-1]=p;else runs.push(p);
    }
    for(let i=1;i<runs.length;i++){
      const a=runs[i-1],b=runs[i],h=Math.abs(a.y-b.y)<.01,v=Math.abs(a.x-b.x)<.01;if(h===v)continue;
      const room=(h?Math.abs(b.x-a.x):Math.abs(b.y-a.y))-(h?width:height)-2*clearance;if(room<0)continue;
      const mid=h?(a.x+b.x)/2:(a.y+b.y)/2;
      for(let k=0;k*step<=room/2+1e-6;k++)for(const side of k?[-1,1]:[1]){
        const c=mid+side*k*step;
        if(h)slid.push({l:c-width/2,t:a.y-clearance-height},{l:c-width/2,t:a.y+clearance});
        else slid.push({l:a.x-clearance-width,t:c-height/2},{l:a.x+clearance,t:c-height/2});
      }
    }
    // Only what lies within reach of this wire can meet a label beside it.
    const reach=Math.max(width,height)+3*clearance,xs=points.map(p=>p.x),ys=points.map(p=>p.y);
    const zone={l:Math.min(...xs)-reach,r:Math.max(...xs)+reach,t:Math.min(...ys)-reach,b:Math.max(...ys)+reach};
    const solid=obstacles.filter(box=>intersects(zone,box)),borders=frames.filter(box=>intersects(zone,box)),lines=[];
    for(const other of entries){
      if(other===entry)continue;
      for(let i=1;i<other.points.length;i++){
        const a=other.points[i-1],b=other.points[i];
        if(Math.max(a.x,b.x)>=zone.l&&Math.min(a.x,b.x)<=zone.r&&Math.max(a.y,b.y)>=zone.t&&Math.min(a.y,b.y)<=zone.b)lines.push([a,b]);
      }
    }
    // How many things a label at this place, padded by pad, would meet; counted no further than the limit.
    const overlaps=(place,pad,limit)=>{
      const box={l:place.l-pad,r:place.l+width+pad,t:place.t-pad,b:place.t+height+pad};
      let n=0;
      for(const o of solid)if(intersects(box,o)&&++n>=limit)return n;
      for(const o of borders)if(intersects(box,o)&&!(box.l>o.l&&box.r<o.r&&box.t>o.t&&box.b<o.b)&&++n>=limit)return n;
      for(const [a,b] of lines)if(crosses(box,a,b)&&++n>=limit)return n;
      return n;
    };
    // Today's places first, then the slid ones; in each, nearest the wire's midpoint first. The first
    // place clear with the clearance wins; else the first clear with no padding (of those, the one
    // meeting least with the clearance); else the place of least true overlap, and the label says so.
    const near=list=>list.map((place,i)=>({place,i,d:Math.round(Math.hypot(place.l+width/2-midpoint.x,place.t+height/2-midpoint.y)*1e4)})).sort((p,q)=>p.d-q.d||p.i-q.i).map(x=>x.place);
    let chosen=null,bare=Infinity,padded=Infinity;
    for(const place of [...near(candidates),...near(slid)]){
      const n=overlaps(place,0,bare+1);if(n>bare)continue;
      const m=overlaps(place,clearance,n<bare?Infinity:padded);
      if(n<bare||m<padded){chosen=place;bare=n;padded=m;if(!m)break}
    }
    if(chosen){
      // A label already at its place is left alone, so placing twice never drifts.
      if(Math.abs(chosen.l-bounds.l)>.01||Math.abs(chosen.t-bounds.t)>.01){
        const position=new DOMPoint(chosen.l-offset.x,chosen.t-offset.y).matrixTransform(inverse);
        label.setAttribute('x',String(position.x));label.setAttribute('y',String(position.y));
      }
    }else bare=overlaps({l:bounds.l,t:bounds.t},0,Infinity); // a wire with no straight run keeps its place
    // Crowded: the label truly overlaps a card, a border, other text or a wire at the place it has.
    if(bare>0)label.dataset.labelCrowded='true';else delete label.dataset.labelCrowded;
    // Later labels keep clear of this one; the finite candidate list bounds the work.
    obstacles.push(rect(label));
  }
}
function renderWires(signalState=computeSignalState(),markers=markersById()){
  const previousLabels=new Map([...wireLabelPaths.keys()].map(path=>{
    const label=path.parentElement?.querySelector('.connection-label');
    return [path.parentElement?.dataset.wireId,label?{text:label.textContent,d:path.getAttribute('d'),x:label.getAttribute('x'),y:label.getAttribute('y')}:null];
  }));
  wireLabelPaths.clear();
  wiresG.innerHTML='';
  nodesG.querySelectorAll(':scope > .wire-group').forEach(g=>g.remove());
  refreshGroupRegions();
  clearEndpointFocus();
  const occupied=[];
  const dragging=!!activeNodeDrag;
  const hostAnchors=new Map();

  // Every route first, so each wire knows the crossings it makes: the later wire hops over the
  // earlier one, and neither puts an arrowhead on the crossing. Wires sharing an end never hop.
  const routes=new Map();
  // Wires on buses are laid out first, lanes and all, so every auto route keeps clear of them.
  const busState=typeof busRoutesForRender==='function'?busRoutesForRender():null;
  if(busState)for(const [id,pts] of busState.routes){const w=wires.find(x=>x.id===id);if(w)occupied.push(...routeSegments(pts,w))}
  wires.forEach((w,i)=>{
    if(entityEditorState(w).hidden||!carrierIsRenderable(w))return;
    const A=carrierEndpoint(w,'a').pos,B=carrierEndpoint(w,'b').pos;
    const snapshot=dragging&&(w.a===activeNodeDrag||w.b===activeNodeDrag)?dragRouteSnapshots.get(i):null;
    // While moving, the settled route is immutable. We do not rebuild its
    // interior, endpoint leads, arrows, or direction marks on pointer frames.
    const points=snapshot?clonePoints(snapshot.points):stableRouteForWire(i,w,A,B,occupied);
    routes.set(i,{points,snapshot,segs:routeSegments(points,w)});
    if(!busState?.routes.has(w.id))occupied.push(...routes.get(i).segs);
  });
  // Jogs out and close parallels spread a track apart (src/40-routing.js nudgeRoutes); bus lanes and taps stay fixed.
  const trackCramped=nudgeRoutes(routes,busState?[...busState.routes].flatMap(([id,pts])=>routeSegments(pts,wires.find(x=>x.id===id))):[]);
  for(const [i,r] of routes)r.segs=routeSegments(r.points,wires[i]);
  const hops=new Map(),order=[...routes.keys()];arrowKeepClear=[];
  for(let x=0;x<order.length;x++)for(let y=x+1;y<order.length;y++){
    const P=routes.get(order[x]),Q=routes.get(order[y]);
    for(const p of P.segs)for(const q of Q.segs){
      if(p.ends&&q.ends&&p.ends.some(e=>q.ends.includes(e)))continue;
      if(!segmentsCross(p.a,p.b,q.a,q.b))continue;
      const c=segmentAxis(p.a,p.b)==='h'?{x:q.a.x,y:p.a.y}:{x:p.a.x,y:q.a.y};
      // Two wires on one bus cross inside its band where they take their lanes: no hop there.
      if(busState&&typeof busBandHolds==='function'&&busBandHolds(wires[order[x]],wires[order[y]],c))continue;
      if(!hops.has(order[y]))hops.set(order[y],[]);hops.get(order[y]).push(c);arrowKeepClear.push(c);
    }
  }
  // Junctions too: where wires sharing an end part, the dot needs room around it.
  {const at=(pts,d)=>{for(let k=1;k<pts.length;k++){const L=Math.hypot(pts[k].x-pts[k-1].x,pts[k].y-pts[k-1].y);if(d<=L){const t=L?d/L:0;return {x:pts[k-1].x+(pts[k].x-pts[k-1].x)*t,y:pts[k-1].y+(pts[k].y-pts[k-1].y)*t}}d-=L}return pts.at(-1)};
   const lenOf=pts=>pts.slice(1).reduce((a,q,k)=>a+Math.hypot(q.x-pts[k].x,q.y-pts[k].y),0);
   const groups=new Map();
   for(const [i,r] of routes){const w=wires[i];for(const [end,id,side] of [['a',w.a,w.aSide],['b',w.b,w.bSide]]){if(!id)continue;const k=`${id}|${side}`;if(!groups.has(k))groups.set(k,[]);const pts=normalizePoints(r.points);groups.get(k).push(end==='b'?[...pts].reverse():pts)}}
   for(const list of groups.values()){if(list.length<2)continue;const reach=Math.min(...list.map(lenOf));let join=list[0][0];
     for(let d=0;d<=reach;d+=2){const q=list.map(p=>at(p,d));if(q.some(v=>Math.hypot(v.x-q[0].x,v.y-q[0].y)>1.2))break;join=q[0]}
     arrowKeepClear.push(join)}}

  wires.forEach((w,i)=>{
    const editor=entityEditorState(w);const cfg=connectionConfig(w);if(editor.hidden||!carrierIsRenderable(w))return;
    const epA=carrierEndpoint(w,'a'),epB=carrierEndpoint(w,'b'),a=epA.node,b=epB.node;
    const A=epA.pos, B=epB.pos;
    const {points,snapshot}=routes.get(i);
    // A multi-line wire is a band, not a line: it does not hop.
    const d=SovSchematicData.normalizeSection(w.form?.section,1)?.lines?.length>=2?pathD(points):pathWithHops(points,hops.get(i));
    const wireMarkers=markers.get(w.id);

    const signal=wireSignalColors(w,signalState);
    const group=document.createElementNS('http://www.w3.org/2000/svg','g');
    group.setAttribute('class','wire-group'+(snapshot?' drag-frozen':'')+((!signal.forwardLive && !signal.reverseLive)?' dormant':'')+(editor.locked?' is-locked':'')+((epA.kind==='free'||epB.kind==='free')?' has-free-end':''));group.dataset.wireId=w.id;group.dataset.wireIndex=String(i);group.style.opacity=String(editor.opacity);
    if(busState?.fallback.has(w.id))group.dataset.busFallback='true';
    if(routeBlockedAt(i))group.dataset.routeBlocked='true';
    if(trackCramped.has(i))group.dataset.trackCramped='true';

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
    const wireStatus=declaredStatus(w);
    if(wireStatus?.outline==='dashed'){base.setAttribute('stroke-dasharray','6 4');base.style.strokeDasharray='6 4';group.dataset.status=wireStatus.id}
    else if(wireStatus)group.dataset.status=wireStatus.id;
    wireLabelPaths.set(base,clonePoints(points));

    const hit=document.createElementNS('http://www.w3.org/2000/svg','path');
    hit.setAttribute('d',d); hit.setAttribute('class','wire-hit');

    // A multi-line wire (strip, lanes, pipe): its lines and bands drawn as nested strokes along the
    // route, outside in, so the section follows every bend. Symmetric about the route.
    const wsec=SovSchematicData.normalizeSection(w.form?.section,1);
    if(wsec&&wsec.lines.length>=2){
      group.classList.add('sectioned');group.dataset.lines=String(wsec.lines.length);
      const lw=1.6;let r=wsec.bands.reduce((a,b)=>a+b.thickness,0)/2+lw;
      const layer=(width,cls)=>{const q=document.createElementNS('http://www.w3.org/2000/svg','path');q.setAttribute('d',d);q.setAttribute('class','wire-section '+cls);q.setAttribute('stroke-width',String(width));group.appendChild(q)};
      layer(2*r,'line');r-=lw;
      for(const b of wsec.bands){if(r<=0)break;layer(2*r,'band-'+b.fill);r-=b.thickness;if(r<=0)break;layer(2*r,'line');r-=lw}
    }
    group.appendChild(voltage);
    group.appendChild(base);
    if(wireMarkers){
      const top=Math.min(...points.map(p=>p.y)),right=Math.max(...points.map(p=>p.x));
      appendMarkerBadge(group,wireMarkers,right,top);
    }
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
    // The host's groups sit directly after it, behind its wires: the first wire goes after them.
    const firstAnchor=el=>{let at=el;while(at.nextElementSibling?.classList.contains('group'))at=at.nextElementSibling;return at};
    if(hostEl){(hostAnchors.get(hostId)||firstAnchor(hostEl)).after(group);hostAnchors.set(hostId,group)}
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

    // One mark per place: a labelled duplex wire carries ↔ in its label, not stacked above it.
    // A Wire's caption: its label, then its status title, then what it waits on.
    const waits=waitsOnList(w.config?.waitsOn);
    // A bus that carries the wire's label says it once for every wire on it; the label stays in the data.
    const ownLabel=cfg.label&&typeof busLabelsOfWire==='function'&&busLabelsOfWire(w).includes(String(cfg.label))?'':cfg.label;
    let caption=[ownLabel,wireStatus?statusTitle(wireStatus):''].filter(Boolean).join(' · ');
    if(waits)caption=caption?`${caption} · waits on ${waits}`:`Waits on ${waits}`;
    if(cfg.direction==='duplex'&&!caption){
      const q=pointAngleAtDistance(base,base.getTotalLength()*.5);
      const badge=document.createElementNS('http://www.w3.org/2000/svg','text');
      badge.setAttribute('class','net-badge');
      badge.setAttribute('x',q.x); badge.setAttribute('y',q.y-7);
      badge.setAttribute('text-anchor','middle');
      badge.textContent='↔';
      group.appendChild(badge);
    }

    if(cfg.reciprocity!=='none'){const q=pointAngleAtDistance(base,base.getTotalLength()*.5),mark=document.createElementNS('http://www.w3.org/2000/svg','text');mark.setAttribute('class','reciprocity-mark');mark.setAttribute('x',q.x);mark.setAttribute('y',q.y+14);mark.setAttribute('text-anchor','middle');mark.textContent=cfg.reciprocity==='required'?'return required':'return expected';group.appendChild(mark)}
    if(caption){
      // A label keeps the place clearance gave it while its text and route stand (wire-label clearance).
      const text=(cfg.direction==='duplex'?'↔ ':'')+caption,lift=13+(wsec&&wsec.lines.length>=2?wsec.bands.reduce((a,b)=>a+b.thickness,0)/2+1.6:0);
      const q=pointAngleAtDistance(base,base.getTotalLength()*.5),previous=previousLabels.get(w.id),label=document.createElementNS('http://www.w3.org/2000/svg','text');
      const keep=previous?.text===text&&previous.d===d;
      label.setAttribute('class','connection-label');label.setAttribute('x',keep?previous.x:q.x);label.setAttribute('y',keep?previous.y:q.y-lift);label.setAttribute('text-anchor','middle');label.textContent=text;group.appendChild(label);
    }
    // Channel markers belong to bound ends; a free end has no port to mark.
    if(a&&endpointShowsChannelTag(w,'a')){
      const markerA=document.createElementNS('http://www.w3.org/2000/svg','text');
      markerA.setAttribute('class','endpoint-channel-tag');
      {const side=physicalPortSide(a,w.aSide);markerA.setAttribute('x',A.x+(side==='left'?-14:side==='right'?14:0));markerA.setAttribute('y',A.y+(side==='top'?-12:side==='bottom'?15:4));markerA.setAttribute('text-anchor',side==='left'?'end':side==='right'?'start':'middle')}
      markerA.textContent=endpointMarkerDisplay(w,'a');
      group.appendChild(markerA);
    }
    if(b&&endpointShowsChannelTag(w,'b')){
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
  placeWireLabels();
}
