'use strict';
// 0.1 concern: measured contrast of the rendered canvas (WCAG 2.2 SC 1.4.3 and 1.4.11).
// Every visible label and every mark a reader needs (wires, arrows, outlines, terminals,
// junctions, section lines, glyphs) is measured against what is actually painted beneath it:
// the fills that precede it in paint order, composited over the canvas tone. Reads only.

const CONTRAST_MARKS='path.wire, .flow-chevron, .component-lead, .terminal-mark, .junction-dot, .node .body, .dimensional-point-body, .dimensional-path-body, .section-line, use.glyph, .glyph path, .glyph line, .glyph circle, .glyph rect, .glyph polyline, .glyph polygon';
const CONTRAST_SKIP='.wire-packet, .wire-voltage, .wire-hit, .port-hit, .transform-handle-group, .move-tether, .move-anchor, .carrier-end-handle, .endpoint-halo, defs, title';

function contrastCanvasColour(){
  for(let e=workspace;e;e=e.parentElement){const c=SovSchematicColour.parse(getComputedStyle(e).backgroundColor);if(c&&c.a>0)return c}
  return SovSchematicColour.parse(canvasTone());
}
function contrastPaint(value){const c=SovSchematicColour.parse(value);return c&&c.a>0?c:null}
// Every colour a paint can show: a flat colour, or each stop of a referenced gradient.
function contrastPaints(value){
  const m=String(value||'').match(/url\(["']?#([^"')]+)["']?\)/);
  if(!m){const c=contrastPaint(value);return c?[c]:[]}
  const g=document.getElementById(m[1]);if(!g)return [];
  return [...g.querySelectorAll('stop')].map(s=>{const cs=getComputedStyle(s),c=contrastPaint(cs.stopColor);return c?{...c,a:c.a*Number(cs.stopOpacity||1)}:null}).filter(Boolean);
}
function contrastPainters(){
  const out=[];
  for(const el of workspace.querySelectorAll('rect, circle, ellipse, path, polygon, polyline')){
    if(el.closest(CONTRAST_SKIP))continue;
    const cs=getComputedStyle(el),fill=contrastPaint(cs.fill);if(!fill)continue;
    const alpha=layoutEffectiveOpacity(el)*Number(cs.fillOpacity||1);if(alpha<=.01)continue;
    const box=layoutWorldBox(el),m=layoutWorldMatrix(el);if(!box||!m)continue;
    out.push({el,fill,alpha,box,inv:m.inverse()});
  }
  return out;
}
// What a reader sees behind `target` at world point p: every fill painted before it, in order.
function contrastBackdrop(p,target,painters,canvas,under=null){
  let c=canvas;
  for(const P of painters){
    if(P.el===target||P.el.contains(target)||target.contains?.(P.el))continue;
    if(target.compareDocumentPosition(P.el)&Node.DOCUMENT_POSITION_FOLLOWING)break;
    if(p.x<P.box.l||p.x>P.box.r||p.y<P.box.t||p.y>P.box.b)continue;
    const q=new DOMPoint(p.x,p.y).matrixTransform(P.inv);
    let inside=false;try{inside=P.el.isPointInFill(q)}catch(_){inside=false}
    if(inside){c=SovSchematicColour.over(P.fill,c,P.alpha);under?.push([...P.el.classList][0]||P.el.tagName)}
  }
  return c;
}
function contrastOwner(el){return el.closest('.node')?.dataset.id||el.closest('.wire-group')?.dataset.wireId||null}

function contrastAudit(options={}){
  const C=SovSchematicColour,canvas=contrastCanvasColour(),painters=contrastPainters(),findings=[];
  let checked=0;
  // Text and lines are judged at their worst sample. A small solid mark is judged by the ring
  // just outside it, at the median: it must stand apart from most of what surrounds it, and a
  // dot joined to a line of its own ink is not a contrast failure.
  const measure=(el,paints,alpha,points,need,kind,label,ring=false)=>{
    paints=(Array.isArray(paints)?paints:[paints]).filter(Boolean);
    if(!paints.length||alpha<=.01||!points.length)return;
    checked++;const samples=[];
    for(const paint of paints)for(const p of points){
      const under=[];let bg=contrastBackdrop(p,el,painters,canvas,under);
      if(kind==='text'){const cs=getComputedStyle(el),halo=contrastPaint(cs.stroke),w=parseFloat(cs.strokeWidth)||0;if(halo&&w>=1.5)bg=C.over(halo,bg,Number(cs.strokeOpacity||1)*alpha)}
      const fg=C.over(paint,bg,alpha),ratio=C.contrast(fg,bg);
      samples.push({ratio,fg:C.hex(fg),bg:C.hex(bg),under:under.length?under:['canvas']});
    }
    samples.sort((a,b)=>a.ratio-b.ratio);const worst=ring?samples[Math.floor((samples.length-1)/2)]:samples[0];
    if(worst.ratio<need)findings.push({kind:kind==='text'?'text-contrast':'mark-contrast',ids:[contrastOwner(el)].filter(Boolean),ratio:Math.round(worst.ratio*100)/100,need,fg:worst.fg,bg:worst.bg,under:worst.under,detail:`${label} ${worst.ratio.toFixed(2)}:1 < ${need}:1 (${worst.fg} on ${worst.bg}: ${worst.under.join(' > ')})`});
  };
  for(const el of workspace.querySelectorAll('text')){
    if(el.closest(CONTRAST_SKIP))continue;
    const txt=(el.textContent||'').trim();if(!txt)continue;
    const cs=getComputedStyle(el),alpha=layoutEffectiveOpacity(el)*Number(cs.fillOpacity||1),box=layoutWorldBox(el);if(!box)continue;
    const px=parseFloat(cs.fontSize)||12,need=C.textFloor(px,cs.fontWeight);
    const w=box.r-box.l,h=box.b-box.t,pts=[[.5,.5],[.25,.3],[.75,.3],[.25,.7],[.75,.7]].map(([fx,fy])=>({x:box.l+w*fx,y:box.t+h*fy}));
    measure(el,contrastPaint(cs.fill),alpha,pts,need,'text',`"${txt.slice(0,24)}"`);
  }
  for(const el of workspace.querySelectorAll(CONTRAST_MARKS)){
    if(el.closest(CONTRAST_SKIP))continue;
    const cs=getComputedStyle(el),sw=parseFloat(cs.strokeWidth)||0,strokes=contrastPaints(cs.stroke);
    // A glyph drawn through <use> paints in its currentColor.
    const useStroke=strokes.length>0&&sw>0,paint=el.tagName==='use'?contrastPaints(cs.color):useStroke?strokes:contrastPaints(cs.fill);
    const alpha=layoutEffectiveOpacity(el)*Number((useStroke?cs.strokeOpacity:cs.fillOpacity)||1);
    let pts=[];
    if(useStroke&&el.tagName!=='use'&&!contrastPaint(cs.fill)&&typeof el.getTotalLength==='function'){
      let L=0;try{L=el.getTotalLength()}catch(_){L=0}
      const m=layoutWorldMatrix(el);
      if(L>0&&m)pts=[.1,.3,.5,.7,.9].map(f=>{const q=el.getPointAtLength(L*f);return new DOMPoint(q.x,q.y).matrixTransform(m)});
    }
    let ring=false;
    if(!pts.length){const b=layoutWorldBox(el);if(b){ring=true;const cx=(b.l+b.r)/2,cy=(b.t+b.b)/2,rx=(b.r-b.l)/2+1.5,ry=(b.b-b.t)/2+1.5;pts=[...Array(8)].map((_,i)=>({x:cx+rx*Math.cos(i*Math.PI/4),y:cy+ry*Math.sin(i*Math.PI/4)}))}}
    const cls=[...el.classList][0]||el.tagName;
    measure(el,paint,alpha,pts,C.WCAG.nonText,'mark',cls,ring);
  }
  const counts={};for(const f of findings)counts[f.kind]=(counts[f.kind]||0)+1;
  return {ok:!findings.length,checked,counts,findings,canvas:C.hex(canvas),static:options.static!==false};
}

// The palette as realised now (theme x appearance), judged as a categorical palette.
function paletteAudit(){
  const bg=canvasTone(),mono=activePalette().slice(0,6),colour=activePalette().slice(6);
  const distinct=colorEngine.palette!=='mono';
  const audit=SovSchematicColour.auditPalette(colour,{background:bg,floor:themeContrastFloor()});
  if(!distinct)audit.failures=audit.failures.filter(f=>f.kind!=='distinct');
  return {appearance:surfaceAppearance(),theme:colorEngine.theme,palette:colorEngine.palette,background:bg,mono,colour,...audit,ok:!audit.failures.length,categorical:distinct};
}
