'use strict';
// 0.1 concern: measured quality of the rendered projection (LAYOUT-MODEL.md §5).
// Reads the rendered SVG in world coordinates and never mutates the document or the DOM.
// A metric is observed, never declared: every finding names the ids it measured.

const LAYOUT_RUBRIC={
  // kind: [penalty per finding, cap for the kind]. Score = 10 - Σ min(cap, n × penalty), floor 0.
  'text-overflow':[.5,3],'text-truncated':[.3,2],'text-collision':[.5,3],'placeholder-text':[.1,2],'ghost-mark':[.1,2],
  'faint-structure':[.5,2],'route-escape':[1,4],'route-jog':[.25,2],'arrowless':[.25,2],'unmarked-junction':[.5,2],'route-through-node':[1,4],'crossing':[.25,2],'node-overlap':[1,4]
};

function layoutWorldMatrix(el){const root=workspace.getScreenCTM(),m=el.getScreenCTM();return root&&m?root.inverse().multiply(m):null}
function layoutWorldBox(el){
  let b;try{b=el.getBBox()}catch(_){return null}
  if(!b||(!b.width&&!b.height))return null;
  const m=layoutWorldMatrix(el);if(!m)return null;
  const pts=[[b.x,b.y],[b.x+b.width,b.y],[b.x,b.y+b.height],[b.x+b.width,b.y+b.height]].map(([x,y])=>new DOMPoint(x,y).matrixTransform(m));
  const xs=pts.map(p=>p.x),ys=pts.map(p=>p.y);
  return {l:Math.min(...xs),r:Math.max(...xs),t:Math.min(...ys),b:Math.max(...ys)};
}
function layoutEffectiveOpacity(el){
  let o=1;
  for(let e=el;e&&e!==workspace;e=e.parentElement){const cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden')return 0;o*=Number(cs.opacity||1)}
  return o;
}
const layoutOverlap=(a,b,pad=0)=>a.l<b.r-pad&&b.l<a.r-pad&&a.t<b.b-pad&&b.t<a.b-pad;
const layoutInside=(p,R,pad=0)=>p.x>R.l+pad&&p.x<R.r-pad&&p.y>R.t+pad&&p.y<R.b-pad;
function layoutSamplePath(path,step=6){
  const L=path.getTotalLength(),out=[];if(!(L>0))return out;
  const m=layoutWorldMatrix(path);
  for(let d=0;d<=L;d+=step){const q=path.getPointAtLength(d);out.push(m?new DOMPoint(q.x,q.y).matrixTransform(m):q)}
  const end=path.getPointAtLength(L);out.push(m?new DOMPoint(end.x,end.y).matrixTransform(m):end);return out;
}
function layoutSegmentsCross(a,b,c,d){
  const o=(p,q,r)=>(q.x-p.x)*(r.y-p.y)-(q.y-p.y)*(r.x-p.x);
  const d1=o(c,d,a),d2=o(c,d,b),d3=o(a,b,c),d4=o(a,b,d);
  return ((d1>0&&d2<0)||(d1<0&&d2>0))&&((d3>0&&d4<0)||(d3<0&&d4>0));
}

// Corner points of an orthogonal path written as M/L/H/V commands.
function layoutPathCorners(d){
  const out=[];let x=0,y=0;
  for(const [,cmd,args] of String(d||'').matchAll(/([MLHV])\s*([^MLHV]*)/gi)){
    const n=args.trim().split(/[\s,]+/).filter(Boolean).map(Number);
    if(/[ML]/i.test(cmd)){x=n[0];y=n[1]}else if(/H/i.test(cmd))x=n[0];else y=n[0];
    out.push({x,y});
  }
  return out;
}
function layoutMetrics(options={}){
  const staticView=options.static!==false; // an export or a screenshot freezes animation
  const findings=[],add=(kind,ids,detail)=>findings.push({kind,ids,detail});
  const visible=nodes.filter(n=>!isEffectivelyHidden(n));
  const body=new Map(visible.map(n=>[n.id,componentBounds(n)]));
  const nodeEl=id=>nodesG.querySelector(`.node[data-id="${CSS.escape(id)}"]`);
  const ancestors=id=>{const out=new Set();let n=nodes.find(x=>x.id===id);while(n?.parentId){out.add(n.parentId);n=nodes.find(x=>x.id===n.parentId)}return out};
  const is2D=n=>componentForm(n).dimension===2;

  // Text: every visible label, in world space.
  const texts=[];
  for(const el of workspace.querySelectorAll('#nodes text,#wires text')){
    if(!el.textContent.trim()||layoutEffectiveOpacity(el)<.1)continue;
    if(el.closest('.wire-packet'))continue; // motion, never structure; static exports drop it
    const box=layoutWorldBox(el);if(!box)continue;
    const owner=el.closest('.node')?.dataset.id||null,wire=el.closest('.wire-group')?.dataset.wireId||null;
    texts.push({el,box,owner,wire,text:el.textContent.trim(),cls:el.getAttribute('class')||''});
  }
  for(const t of texts){
    const n=t.owner&&nodes.find(x=>x.id===t.owner);
    if(n&&is2D(n)&&/component-label|internal-text/.test(t.cls)){
      const R=body.get(n.id);if(R&&(t.box.l<R.l-1||t.box.r>R.r+1||t.box.t<R.t-1||t.box.b>R.b+1))add('text-overflow',[n.id],`"${t.text}" is ${Math.round((t.box.r-t.box.l)-(R.r-R.l))}px wider than its body`);
    }
  }
  // A label across one of its own card's inner lines is as unreadable as one across another card.
  for(const t of texts){
    if(!t.owner)continue;const lines=nodeEl(t.owner)?.querySelectorAll(':scope > .section-line')||[];
    for(const l of lines){const L=layoutWorldBox(l);if(L&&layoutOverlap(t.box,L)&&!(t.box.l>L.l&&t.box.r<L.r&&t.box.t>L.t&&t.box.b<L.b)){add('text-collision',[t.owner],`"${t.text}" crosses its own section line`);break}}
  }
  for(const t of texts)if(t.el.dataset.truncated)add('text-truncated',[t.owner],`"${t.el.querySelector('title')?.textContent||t.text}" is cut to fit`);
  for(let i=0;i<texts.length;i++)for(let j=i+1;j<texts.length;j++)if(layoutOverlap(texts[i].box,texts[j].box,1))add('text-collision',[texts[i].owner||texts[i].wire,texts[j].owner||texts[j].wire],`"${texts[i].text}" overlaps "${texts[j].text}"`);
  for(const t of texts){
    const own=t.owner?new Set([t.owner,...ancestors(t.owner)]):new Set();
    for(const n of visible){
      if(own.has(n.id)||!is2D(n))continue;
      const R=body.get(n.id),container=componentAcceptsChildren(n);
      // A label crossing a container's border is as unreadable as one over a box.
      const hit=container?(layoutOverlap(t.box,R)&&!(t.box.l>R.l&&t.box.r<R.r&&t.box.t>R.t&&t.box.b<R.b)):layoutOverlap(t.box,R,1);
      if(hit){add('text-collision',[t.owner||t.wire,n.id],`"${t.text}" ${container?'straddles the border of':'overlaps'} ${n.config?.label||n.id}`);break}
    }
  }
  // Placeholder text: a default channel tag on a single-connection end says nothing.
  for(const t of texts)if(/endpoint-channel-tag|wire-packet-tag/.test(t.cls)&&t.text==='1')add('placeholder-text',[t.wire],'default channel marker "1"');

  // Ghost marks: marks that look like structure but are not.
  const bound=new Set();for(const w of wires){if(w.a)bound.add(`${w.a}:${w.aSide}`);if(w.b)bound.add(`${w.b}:${w.bSide}`)}
  for(const el of nodesG.querySelectorAll('.port.attachment-point:not(.dimensional-point-body)')){
    const id=el.closest('.node')?.dataset.id;if(layoutEffectiveOpacity(el)>=.1&&!bound.has(`${id}:${el.dataset.port}`))add('ghost-mark',[id],`unused ${el.dataset.port} point drawn`);
  }
  // Faint structure: a junction or boundary Point that carries wires must be seen.
  for(const n of visible){
    if(componentForm(n).dimension!==0)continue;
    const ends=wires.filter(w=>w.a===n.id||w.b===n.id).length,hosted=n.placement?.kind==='edge';
    if(!(ends>=3||(hosted&&ends)))continue;
    const el=nodeEl(n.id)?.querySelector('.dimensional-point-body');if(el&&layoutEffectiveOpacity(el)<.5)add('faint-structure',[n.id],`${ends>=3?'junction':'boundary point'} drawn at ${layoutEffectiveOpacity(el).toFixed(2)} opacity`);
  }

  // Routes.
  const routes=[];
  for(const g of workspace.querySelectorAll('.wire-group')){
    const path=g.querySelector('path.wire'),w=wires.find(x=>x.id===g.dataset.wireId);if(!path||!w)continue;
    routes.push({w,pts:layoutSamplePath(path),corners:layoutPathCorners(path.getAttribute('d'))});
  }
  // A jog is a short step between two bends: two lines that should have been one.
  for(const {w,corners} of routes){
    for(let i=1;i+2<corners.length;i++){const a=corners[i],b=corners[i+1],len=Math.hypot(b.x-a.x,b.y-a.y);if(len>.5&&len<12){add('route-jog',[w.id],`${len.toFixed(1)}px step`);break}}
  }
  for(const {w,pts} of routes){
    const canvasOwner=String(w.canvasId||'').startsWith('canvas:component:')?String(w.canvasId).slice('canvas:component:'.length):null;
    const own=canvasOwner&&body.get(canvasOwner);
    if(own&&pts.some(p=>!layoutInside(p,own,-1)))add('route-escape',[w.id,canvasOwner],`leaves the interior of ${nodes.find(n=>n.id===canvasOwner)?.config?.label||canvasOwner}`);
    const exempt=new Set([w.a,w.b,canvasOwner,...ancestors(w.a),...ancestors(w.b)].filter(Boolean));
    for(const n of visible){
      if(exempt.has(n.id)||!is2D(n))continue;
      const R=body.get(n.id),inner=componentAcceptsChildren(n);
      if(inner){if(pts.some(p=>layoutInside(p,R,2))&&pts.some(p=>!layoutInside(p,R,-2)))add('route-through-node',[w.id,n.id],`crosses the boundary of ${n.config?.label||n.id} without a point`);continue}
      if(pts.some(p=>layoutInside(p,R,2)))add('route-through-node',[w.id,n.id],`passes through ${n.config?.label||n.id}`);
    }
  }
  for(let i=0;i<routes.length;i++)for(let j=i+1;j<routes.length;j++){
    const A=routes[i],B=routes[j],shared=[A.w.a,A.w.b].some(x=>x&&(x===B.w.a||x===B.w.b));
    let crossed=0;
    for(let s=1;s<A.pts.length&&crossed<4;s++)for(let t=1;t<B.pts.length;t++)if(layoutSegmentsCross(A.pts[s-1],A.pts[s],B.pts[t-1],B.pts[t])){crossed++;break}
    if(crossed&&!(shared&&crossed===1))add('crossing',[A.w.id,B.w.id],`${crossed} crossing${crossed>1?'s':''}`);
  }
  // A directed wire long enough to carry a mark must say which way it runs.
  for(const {w} of routes){
    const dir=connectionConfig(w).direction,gEl=workspace.querySelector(`.wire-group[data-wire-id="${CSS.escape(w.id)}"]`),path=gEl?.querySelector('path.wire');
    if(dir!=='none'&&path&&path.getTotalLength()>=20&&!gEl.querySelector('.flow-chevron'))add('arrowless',[w.id],`${dir} wire with no direction mark`);
  }
  // Wires sharing one point of a card must be marked as joined.
  {const shared=new Map();for(const w of wires)for(const [id,side] of [[w.a,w.aSide],[w.b,w.bSide]]){const n=id&&nodes.find(x=>x.id===id);if(!n||componentForm(n).dimension===0)continue;const k=`${id}|${side}`;shared.set(k,(shared.get(k)||0)+1)}
   for(const [k,count] of shared)if(count>=2&&!workspace.querySelector(`.junction-dot[data-port="${CSS.escape(k)}"]`))add('unmarked-junction',[k.split('|')[0]],`${count} wires meet at ${k.split('|')[1]} with no junction mark`)}
  // Points drawn on top of each other read as one.
  {const pts=visible.filter(n=>componentForm(n).dimension===0);
   for(let i=0;i<pts.length;i++)for(let j=i+1;j<pts.length;j++)if(Math.hypot(pts[i].x-pts[j].x,pts[i].y-pts[j].y)<12)add('node-overlap',[pts[i].id,pts[j].id],'points drawn on top of each other')}
  // Sibling bodies must not overlap.
  for(let i=0;i<visible.length;i++)for(let j=i+1;j<visible.length;j++){
    const a=visible[i],b=visible[j];
    if(!is2D(a)||!is2D(b)||(a.canvasId||'')!==(b.canvasId||''))continue;
    if(layoutOverlap(body.get(a.id),body.get(b.id),1))add('node-overlap',[a.id,b.id],'bodies overlap');
  }

  const counts={};for(const f of findings)counts[f.kind]=(counts[f.kind]||0)+1;
  let score=10;for(const [kind,n] of Object.entries(counts)){const [p,cap]=LAYOUT_RUBRIC[kind]||[0,0];score-=Math.min(cap,n*p)}
  return {ok:true,score:Math.max(0,Math.round(score*10)/10),counts,findings,rubric:LAYOUT_RUBRIC,static:staticView};
}
