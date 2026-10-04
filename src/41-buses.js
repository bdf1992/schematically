'use strict';
// 0.1 concern: the route of a wire on buses (LAYOUT-MODEL.md "As built: buses"). A bus is a layout
// record (src/08-layout-core.js): a centreline declared once in a layout, which wires name in their
// route ({mode: 'bus', buses: [id, ...]}) instead of each finding a path. A wire taps on to the first
// bus from the end of its source lead, rides each bus on a lane, turns once where one bus meets the
// next, and taps off the last bus to the end of its target lead. A lane holds one wire; on a bus
// whose record carries lanes: 'port' it holds every wire leaving one port. Lanes are ordered once
// per render, before any auto route, so auto routes keep clear of the buses. Presentation only:
// nothing here writes the document.

function activeBuses(){const v=diagram.layout?.views?.[activeLayoutId()];return v&&v.buses&&typeof v.buses==='object'&&!Array.isArray(v.buses)?v.buses:{}}
function busSpecOf(w){const s=typeof activeRouteSpec==='function'?activeRouteSpec(w.id):null;return s?.mode==='bus'&&Array.isArray(s.buses)&&s.buses.length?s:null}
function busPitchOf(bus){const p=Number(bus?.pitch);return Number.isFinite(p)?Math.max(4,Math.min(16,p)):6}
// The lane a wire takes on a bus. On a bus with lanes: 'port' the wires that share their a end
// (card and side) share a lane: a hyperedge slot in ELK's orthogonal routing (after Sander, GD
// 2003), one track per net in VLSI channel routing. On any other bus each wire has its own.
function busLaneKey(w,bus){return bus?.lanes==='port'&&w.a?w.a+':'+w.aSide:'wire:'+w.id}

// ---- Bus geometry: a centreline measured along its length --------------------------------------
function busLine(bus){
  const raw=SovSchematicLayout.busPoints(bus?.points);if(!raw)return null;
  const pts=normalizePoints(raw);if(pts.length<2)return null;
  const segs=[];let s=0;
  for(let i=1;i<pts.length;i++){
    const a=pts[i-1],b=pts[i],len=Math.abs(b.x-a.x)+Math.abs(b.y-a.y),dir={x:Math.sign(b.x-a.x),y:Math.sign(b.y-a.y)};
    // The lane normal: the direction of travel turned a quarter, the same on every segment.
    segs.push({a,b,s0:s,s1:s+len,dir,n:{x:-dir.y,y:dir.x}});s+=len;
  }
  return {pts,segs,length:s};
}
// The nearest point of the centreline to p, and how far along the bus it lies.
function busProject(line,p){
  let best=null;
  line.segs.forEach((g,k)=>{
    const x=Math.max(Math.min(g.a.x,g.b.x),Math.min(Math.max(g.a.x,g.b.x),p.x)),y=Math.max(Math.min(g.a.y,g.b.y),Math.min(Math.max(g.a.y,g.b.y),p.y));
    const d=Math.hypot(p.x-x,p.y-y);
    if(!best||d<best.d-1e-9)best={d,x,y,k,s:g.s0+Math.abs(x-g.a.x)+Math.abs(y-g.a.y)};
  });
  return best;
}
// The point s along the bus, o across it (on the lane normal). At a corner, where the two lanes meet.
function busAt(line,s,o){
  const t=Math.max(0,Math.min(line.length,s));
  for(let k=0;k<line.segs.length;k++){
    const g=line.segs[k];if(t>g.s1+1e-9&&k<line.segs.length-1)continue;
    const next=line.segs[k+1];
    if(next&&Math.abs(t-g.s1)<1e-9)return {x:g.b.x+o*(g.n.x+next.n.x),y:g.b.y+o*(g.n.y+next.n.y)};
    const along=t-g.s0;return {x:g.a.x+g.dir.x*along+o*g.n.x,y:g.a.y+g.dir.y*along+o*g.n.y};
  }
  return {x:line.pts[0].x,y:line.pts[0].y};
}
// Riding a lane from s1 to s2, in either direction: the two ends and every corner between.
function busRide(line,s1,s2,o){
  const out=[busAt(line,s1,o)],lo=Math.min(s1,s2),hi=Math.max(s1,s2);
  const corners=line.segs.slice(0,-1).map(g=>g.s1).filter(s=>s>lo+1e-9&&s<hi-1e-9);
  if(s2<s1)corners.reverse();
  for(const s of corners)out.push(busAt(line,s,o));
  out.push(busAt(line,s2,o));
  return out;
}

// ---- A wire's plan on its buses: where it joins and leaves each one -----------------------------
function busPlan(w,A,B,spec){
  const all=activeBuses(),legs=spec.buses.map(id=>({id,bus:all[id],line:busLine(all[id])}));
  if(!A||!B||legs.some(l=>!l.line))return null;
  const meets=[];
  for(let i=1;i<legs.length;i++){
    const m=SovSchematicLayout.busMeet(legs[i-1].bus.points,legs[i].bus.points);if(!m)return null;
    const p=busProject(legs[i-1].line,m),q=busProject(legs[i].line,m);
    meets.push({x:m.x,y:m.y,sFrom:p.s,sTo:q.s,nFrom:legs[i-1].line.segs[p.k].n,nTo:legs[i].line.segs[q.k].n});
  }
  const a=w.a?nodes.find(n=>n.id===w.a):null,b=w.b?nodes.find(n=>n.id===w.b):null;
  const first=legs[0].line,last=legs.at(-1).line,pa=busProject(first,A),pb=busProject(last,B);
  // The leads are the router's own (routeLead), aimed at where the wire meets its bus.
  const SA=a?routeLead(A,{x:pa.x,y:pa.y},w.aSide,a,wireEndpointInward(w,a)):A,SB=b?routeLead(B,{x:pb.x,y:pb.y},w.bSide,b,wireEndpointInward(w,b)):B;
  const on=busProject(first,SA),off=busProject(last,SB);
  legs.forEach((l,i)=>{l.sIn=i===0?on.s:meets[i-1].sTo;l.sOut=i===legs.length-1?off.s:meets[i].sFrom});
  return {w,A,B,SA,SB,legs,meets,
    horizA:Math.abs(SA.x-A.x)>=Math.abs(SA.y-A.y),horizB:Math.abs(SB.x-B.x)>=Math.abs(SB.y-B.y)};
}
// The drawn route for a plan, given the wire's lane offset on each of its buses.
function busPlanPoints(plan,offsets){
  const o=i=>offsets.get(plan.legs[i].id)||0,L=plan.legs,n=L.length;
  // Tap on: one L from the end of the lead to the lane, its first leg continuing the lead.
  const T=busAt(L[0].line,L[0].sIn,o(0));
  const out=[plan.A,plan.SA,plan.horizA?{x:T.x,y:plan.SA.y}:{x:plan.SA.x,y:T.y}];
  for(let i=0;i<n;i++){
    out.push(...busRide(L[i].line,L[i].sIn,L[i].sOut,o(i)));
    if(i<n-1){
      // One turn, where the two lanes meet.
      const m=plan.meets[i],perpendicular=Math.abs(m.nFrom.x*m.nTo.x+m.nFrom.y*m.nTo.y)<.5;
      if(perpendicular)out.push({x:m.x+o(i)*m.nFrom.x+o(i+1)*m.nTo.x,y:m.y+o(i)*m.nFrom.y+o(i+1)*m.nTo.y});
    }
  }
  // Tap off: the mirror of tap on.
  const U=busAt(L[n-1].line,L[n-1].sOut,o(n-1));
  out.push(plan.horizB?{x:U.x,y:plan.SB.y}:{x:plan.SB.x,y:U.y},plan.SB,plan.B);
  // Two consecutive points off one axis (a parallel hand-over) get a corner between them.
  const ortho=[out[0]];
  for(let i=1;i<out.length;i++){const p=ortho.at(-1),q=out[i];if(Math.abs(p.x-q.x)>.01&&Math.abs(p.y-q.y)>.01)ortho.push({x:q.x,y:p.y});ortho.push(q)}
  return normalizePoints(ortho);
}
// Two routes cross, or (sharing no end) run on one track, which a reader cannot tell from a crossing.
function busRoutesCross(p,q,related=false){
  for(let i=1;i<p.length;i++)for(let j=1;j<q.length;j++){
    if(segmentsCross(p[i-1],p[i],q[j-1],q[j]))return true;
    if(!related&&onOneTrack(p[i-1],p[i],q[j-1],q[j],8))return true;
  }
  return false;
}
// The same two faults apart: 4 for two wires sharing no end on one track, else 1 for a crossing, the
// ratio of route-overlap to crossing in the layout rubric (src/57-layout-metrics.js).
const BUS_TRACK_COST=4;
// A route as its segments, each the line it lies on (c) and its span along it: what onOneTrack and
// segmentsCross (src/40-routing.js) read, taken once per route instead of once per pair.
function busRouteSegs(pts){
  const out=[];
  for(let i=1;i<pts.length;i++){
    const A=pts[i-1],B=pts[i];
    if(A.y===B.y)out.push({h:true,c:A.y,lo:Math.min(A.x,B.x),hi:Math.max(A.x,B.x)});
    else if(A.x===B.x)out.push({h:false,c:A.x,lo:Math.min(A.y,B.y),hi:Math.max(A.y,B.y)});
  }
  return out;
}
function busSegsCost(P,Q,related=false){
  let cross=0;
  for(const s of P)for(const t of Q){
    if(s.h===t.h){if(!related&&Math.abs(s.c-t.c)<3&&Math.max(s.lo,t.lo)-Math.min(s.hi,t.hi)<8)return BUS_TRACK_COST}
    else if(!cross&&t.c>s.lo&&t.c<s.hi&&s.c>t.lo&&s.c<t.hi)cross=1;
  }
  return cross;
}
// On a bus with lanes: 'port', after the swaps, when two of its wires that share no end lie on one
// track. A wire that taps on along the line another wire taps off along (a card each side of the
// bus in one row) lies on that wire's track from the other's lane to its own whenever its own lane
// is the farther one, and a shared lane puts every wire of its port there at once. This is the
// vertical constraint of channel routing (Hashimoto and Stevens, DAC 1971), and the swaps above
// cannot meet it: passing the lanes in between changes nothing, so no single swap is kept. So the
// lanes are sifted (Matuszewski, Schonfeld and Molitor, GD 1999): each in turn is walked by
// adjacent swaps to one end of the bus and then to the other, and left where the cost over the
// bus's wires was least (where it stood, unless another place is strictly cheaper; of equal places
// the first met). Rounds repeat while the cost fell and a track is still shared, at most 4.
function busSiftLanes(L,W,H,routeOf,wireOf,rebuild){
  if(L.length<3)return;
  const n=W.length,ix=new Map(W.map((id,i)=>[id,i])),segs=W.map(id=>busRouteSegs(routeOf(id)));
  const related=new Uint8Array(n*n),cost=new Uint8Array(n*n),inMove=new Uint8Array(n);let total=0;
  for(let i=0;i<n;i++)for(let j=i+1;j<n;j++){
    related[i*n+j]=related[j*n+i]=busWiresRelated(wireOf(W[i]),wireOf(W[j]))?1:0;
    const c=busSegsCost(segs[i],segs[j],!!related[i*n+j]);cost[i*n+j]=cost[j*n+i]=c;total+=c;
  }
  // Lanes k and k+1 change places: every wire in either is routed again and priced again.
  const swap=k=>{
    const u=L[k],v=L[k+1],ids=[...H.get(u),...H.get(v)],moved=ids.map(id=>ix.get(id));
    L[k]=v;L[k+1]=u;rebuild(ids);
    for(const i of moved){segs[i]=busRouteSegs(routeOf(W[i]));inMove[i]=1}
    for(const i of moved)for(let j=0;j<n;j++){
      if(j===i||(inMove[j]&&j<i))continue;
      const c=busSegsCost(segs[i],segs[j],!!related[i*n+j]);total+=c-cost[i*n+j];cost[i*n+j]=cost[j*n+i]=c;
    }
    for(const i of moved)inMove[i]=0;
  };
  for(let round=0;round<4&&cost.includes(BUS_TRACK_COST);round++){
    const before=total;
    for(const lane of [...L]){
      let i=L.indexOf(lane),best=total,at=i;
      while(i>0){swap(--i);if(total<best){best=total;at=i}}
      while(i<L.length-1){swap(i++);if(total<best){best=total;at=i}}
      while(i>at)swap(--i);
    }
    if(!(total<before))break;
  }
}
const busWiresRelated=(a,b)=>[`${a.a}:${a.aSide}`,`${a.b}:${a.bSide}`].some(e=>e===`${b.a}:${b.aSide}`||e===`${b.b}:${b.bSide}`);

// ---- Lanes, once per render ---------------------------------------------------------------------
// A bus's own order when it has one. Otherwise wires start in the order they leave the bus (ties by
// where they join, then wire id), and its lanes are the distinct lane keys in that order. Then up
// to 8 passes of adjacent lane swaps keep a swap only when the number of crossing pairs among that
// bus's wires strictly drops: the greedy form of the slot ordering in ELK's
// OrthogonalRoutingGenerator. A bus with lanes: 'port' on which two wires sharing no end still lie
// on one track then has its lanes sifted (busSiftLanes). A lane's offset is
// (its index - (lane count - 1) / 2) x pitch.
let busRouteState={key:null,routes:new Map(),fallback:new Set(),on:new Map(),order:new Map(),lanes:new Map()};
function busRoutesForRender(){
  const all=activeBuses(),entries=[];
  wires.forEach(w=>{
    const spec=busSpecOf(w);if(!spec||entityEditorState(w).hidden||!carrierIsRenderable(w))return;
    entries.push({w,spec,A:carrierEndpoint(w,'a').pos,B:carrierEndpoint(w,'b').pos});
  });
  if(!entries.length&&!Object.keys(all).length){busRouteState={key:null,routes:new Map(),fallback:new Set(),on:new Map(),order:new Map(),lanes:new Map()};return busRouteState}
  const key=JSON.stringify([activeLayoutId(),all,entries.map(e=>[e.w.id,e.spec.buses,e.w.aSide,e.w.bSide,e.A?.x,e.A?.y,e.B?.x,e.B?.y]),nodes.map(n=>[n.id,n.x,n.y,n.config?.presentation?.size])]);
  if(key===busRouteState.key)return busRouteState;
  const plans=new Map(),fallback=new Set();
  for(const e of entries){const p=busPlan(e.w,e.A,e.B,e.spec);if(p)plans.set(e.w.id,p);else fallback.add(e.w.id)}
  const on=new Map();
  for(const [id,p] of plans)for(const l of p.legs){if(!on.has(l.id))on.set(l.id,[]);if(!on.get(l.id).includes(id))on.get(l.id).push(id)}
  // lanes: bus id to its lane keys in order; held: bus id to the wires of each lane; order: the
  // wires lane by lane.
  const order=new Map(),lanes=new Map(),held=new Map(),laneOf=(bid,id)=>busLaneKey(plans.get(id).w,all[bid]);
  for(const [bid,list] of on){
    const leg=id=>plans.get(id).legs.find(l=>l.id===bid);
    const natural=[...list].sort((x,y)=>leg(x).sOut-leg(y).sOut||leg(x).sIn-leg(y).sIn||(x<y?-1:x>y?1:0));
    const own=Array.isArray(all[bid]?.order)?all[bid].order.filter(id=>list.includes(id)):[];
    const first=own.length?[...own,...natural.filter(id=>!own.includes(id))]:natural,H=new Map();
    for(const id of first){const k=laneOf(bid,id);if(!H.has(k))H.set(k,[]);H.get(k).push(id)}
    lanes.set(bid,[...H.keys()]);held.set(bid,H);order.set(bid,[...H.values()].flat());
  }
  const offsetsOf=id=>new Map(plans.get(id).legs.map(l=>{const L=lanes.get(l.id);return [l.id,(L.indexOf(laneOf(l.id,id))-(L.length-1)/2)*busPitchOf(all[l.id])]}));
  const routes=new Map();for(const id of plans.keys())routes.set(id,busPlanPoints(plans.get(id),offsetsOf(id)));
  const pair=(x,y)=>x<y?`${x}|${y}`:`${y}|${x}`;
  const crosses=(x,y)=>busRoutesCross(routes.get(x),routes.get(y),busWiresRelated(plans.get(x).w,plans.get(y).w))?1:0;
  const crossingsOn=L=>{const cross=new Map();let total=0;for(let i=0;i<L.length;i++)for(let j=i+1;j<L.length;j++){const c=crosses(L[i],L[j]);cross.set(pair(L[i],L[j]),c);total+=c}return {cross,total}};
  for(const bid of [...on.keys()].sort()){
    if(Array.isArray(all[bid]?.order)&&all[bid].order.length)continue;
    const L=lanes.get(bid);if(L.length<2)continue;
    const W=order.get(bid),H=held.get(bid),rebuild=ids=>{for(const id of ids)routes.set(id,busPlanPoints(plans.get(id),offsetsOf(id)))};
    // Which side the first leaver takes depends on where the wires go next: the order as sorted
    // and reversed are both measured, and the swaps start from the one that crosses less.
    let {cross,total}=crossingsOn(W);
    {const keep=[...L];L.reverse();rebuild(W);
     const rev=crossingsOn(W);
     if(rev.total<total){cross=rev.cross;total=rev.total}else{L.splice(0,L.length,...keep);rebuild(W)}}
    for(let pass=0;pass<8&&total>0;pass++){
      let improved=false;
      for(let k=0;k+1<L.length;k++){
        // Two neighbouring lanes change places: every wire in either is routed again.
        const u=L[k],v=L[k+1],moved=[...H.get(u),...H.get(v)],keep=new Map(moved.map(id=>[id,routes.get(id)])),was=new Map();
        L[k]=v;L[k+1]=u;rebuild(moved);
        let next=total;
        for(const x of moved)for(const z of W){
          if(z===x)continue;const key=pair(x,z);if(was.has(key))continue;
          const c=crosses(x,z);was.set(key,cross.get(key));next+=c-cross.get(key);cross.set(key,c);
        }
        if(next<total){total=next;improved=true;continue}
        L[k]=u;L[k+1]=v;for(const [id,pts] of keep)routes.set(id,pts);for(const [key,c] of was)cross.set(key,c);
      }
      if(!improved)break;
    }
    if(all[bid]?.lanes==='port')busSiftLanes(L,W,H,id=>routes.get(id),id=>plans.get(id).w,rebuild);
    order.set(bid,L.flatMap(k=>H.get(k)));
  }
  busRouteState={key,routes,fallback,on,order,lanes};
  return busRouteState;
}
// The drawn route of a bus-routed wire, or null when it cannot be built (the router takes over).
function busRouteFor(w){const st=busRoutesForRender(),pts=st.routes.get(w.id);return pts?clonePoints(pts):null}

// ---- What the renderer asks ---------------------------------------------------------------------
// Two wires that cross inside the band of a bus they both ride draw no hop there.
function busBandHolds(wa,wb,c){
  const st=busRouteState,sa=busSpecOf(wa),sb=busSpecOf(wb);if(!sa||!sb||!st.routes.has(wa.id)||!st.routes.has(wb.id))return false;
  const all=activeBuses();
  for(const id of sa.buses){
    if(!sb.buses.includes(id))continue;const line=busLine(all[id]);if(!line)continue;
    const hw=((st.lanes.get(id)?.length||0)*busPitchOf(all[id])+8)/2;
    for(const g of line.segs)if(c.x>=Math.min(g.a.x,g.b.x)-hw&&c.x<=Math.max(g.a.x,g.b.x)+hw&&c.y>=Math.min(g.a.y,g.b.y)-hw&&c.y<=Math.max(g.a.y,g.b.y)+hw)return true;
  }
  return false;
}
// The labels of the buses a wire rides: its own label is not drawn again when one of them carries it.
function busLabelsOfWire(w){
  const spec=busSpecOf(w);if(!spec||!busRouteState.routes.has(w.id))return [];
  const all=activeBuses();return spec.buses.map(id=>all[id]?.label).filter(l=>typeof l==='string'&&l);
}
// Each bus as a band behind the wires: its lane count times its pitch, plus 8, with rounded ends;
// its label once, beyond its start, reading along it.
function renderBuses(layer){
  const all=activeBuses(),st=busRoutesForRender(),SVG='http://www.w3.org/2000/svg';
  for(const id of Object.keys(all).sort()){
    const bus=all[id],line=busLine(bus);if(!line)continue;
    const n=st.lanes.get(id)?.length||0,hw=(n*busPitchOf(bus)+8)/2;
    const g=document.createElementNS(SVG,'g');g.setAttribute('class','bus-band');g.dataset.busId=id;g.dataset.lanes=String(n);
    for(const s of line.segs){
      const r=document.createElementNS(SVG,'rect');
      r.setAttribute('x',String(Math.min(s.a.x,s.b.x)-hw));r.setAttribute('y',String(Math.min(s.a.y,s.b.y)-hw));
      r.setAttribute('width',String(Math.abs(s.b.x-s.a.x)+2*hw));r.setAttribute('height',String(Math.abs(s.b.y-s.a.y)+2*hw));
      r.setAttribute('rx',String(hw));r.setAttribute('ry',String(hw));g.appendChild(r);
    }
    layer.appendChild(g);
    const label=typeof bus.label==='string'?bus.label.trim():'';if(!label)continue;
    const d=line.segs[0].dir,at={x:line.pts[0].x-d.x*(hw+6),y:line.pts[0].y-d.y*(hw+6)};
    const t=document.createElementNS(SVG,'text');t.setAttribute('class','bus-label');t.dataset.busId=id;t.dataset.role='caption';
    t.setAttribute('x',String(at.x));t.setAttribute('y',String(at.y));t.setAttribute('dominant-baseline','central');
    if(d.y!==0){t.setAttribute('text-anchor','start');t.setAttribute('transform',`rotate(${d.y>0?-90:90} ${at.x} ${at.y})`)}
    else t.setAttribute('text-anchor',d.x>0?'end':'start');
    t.setAttribute('style',`${CAPTION_STYLE};fill:${statusInk()};stroke:none;pointer-events:none`);
    t.textContent=label;layer.appendChild(t);
  }
}
