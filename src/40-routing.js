'use strict';
// 0.1 Beta concern: Obstacle geometry, route scoring, stable routing, and graph creation primitives.

function rectForNode(n,pad=12){return componentBounds(n,pad)}
function nodeInsideContainer(node,container){return !!node&&!!container&&isDescendantOf(node.id,container.id)}
function ignoreContainerObstacle(candidate,sourceNode,targetNode){
  return componentAcceptsChildren(candidate)&&nodeInsideContainer(sourceNode,candidate)&&nodeInsideContainer(targetNode,candidate);
}
function endpointNeedsOuterObstacle(node,portId,wire=null){
  if(!node)return false;
  // A 0D Point has no body a route could tunnel through; its own wires leave from its centre.
  if(componentForm(node).dimension===0)return false;
  // A carrier on the endpoint's own interior surface starts inside it: the body is the
  // surface the carrier runs on, not an obstacle to route around.
  if(wire&&(wire.canvasId||GLOBAL_CANVAS_ID)===componentCanvas(node).id)return false;
  return (componentConfig(node).ports[portId]?.face||'external')!=='internal';
}
function segHitsRect(A,B,R){
  // Orthogonal segment only. Touching the outside boundary is acceptable;
  // entering the padded rectangle is not.
  if(A.x===B.x){
    const x=A.x, lo=Math.min(A.y,B.y), hi=Math.max(A.y,B.y);
    return x>R.l && x<R.r && hi>R.t && lo<R.b;
  }
  if(A.y===B.y){
    const y=A.y, lo=Math.min(A.x,B.x), hi=Math.max(A.x,B.x);
    return y>R.t && y<R.b && hi>R.l && lo<R.r;
  }
  return true;
}
function normalizePoints(points){
  const out=[];
  for(const p of points){
    const q={x:Math.round(p.x*100)/100,y:Math.round(p.y*100)/100};
    const prev=out[out.length-1];
    if(prev && prev.x===q.x && prev.y===q.y) continue;
    out.push(q);
  }
  // Remove collinear middle points.
  let changed=true;
  while(changed){
    changed=false;
    for(let i=1;i<out.length-1;i++){
      const a=out[i-1],b=out[i],c=out[i+1];
      if((a.x===b.x&&b.x===c.x)||(a.y===b.y&&b.y===c.y)){
        out.splice(i,1); changed=true; break;
      }
    }
  }
  return out;
}
function pathValid(points, obstacles){
  const pts=normalizePoints(points);
  for(let i=0;i<pts.length-1;i++){
    for(const R of obstacles){
      if(segHitsRect(pts[i],pts[i+1],R)) return false;
    }
  }
  return true;
}
function segmentLength(A,B){
  return Math.abs(B.x-A.x)+Math.abs(B.y-A.y);
}
function segmentAxis(A,B){
  if(A.y===B.y) return 'h';
  if(A.x===B.x) return 'v';
  return 'd';
}
function overlap1D(a1,a2,b1,b2){
  const lo=Math.max(Math.min(a1,a2),Math.min(b1,b2));
  const hi=Math.min(Math.max(a1,a2),Math.max(b1,b2));
  return Math.max(0,hi-lo);
}
function segmentsCross(A,B,C,D){
  const ab=segmentAxis(A,B), cd=segmentAxis(C,D);
  if(ab==='d'||cd==='d') return false;
  if(ab===cd) return false;
  const H=ab==='h'?[A,B]:[C,D];
  const V=ab==='v'?[A,B]:[C,D];
  const hx1=Math.min(H[0].x,H[1].x), hx2=Math.max(H[0].x,H[1].x), hy=H[0].y;
  const vy1=Math.min(V[0].y,V[1].y), vy2=Math.max(V[0].y,V[1].y), vx=V[0].x;
  return vx>hx1 && vx<hx2 && hy>vy1 && hy<vy2;
}
function sharedLength(A,B,C,D){
  const ab=segmentAxis(A,B), cd=segmentAxis(C,D);
  if(ab!==cd || ab==='d') return 0;
  if(ab==='h' && Math.abs(A.y-C.y)<1) return overlap1D(A.x,B.x,C.x,D.x);
  if(ab==='v' && Math.abs(A.x-C.x)<1) return overlap1D(A.y,B.y,C.y,D.y);
  return 0;
}
function distanceSegmentToRect(A,B,R){
  if(segmentAxis(A,B)==='h'){
    const y=A.y;
    if(y>=R.t && y<=R.b) return 0;
    return Math.min(Math.abs(y-R.t),Math.abs(y-R.b));
  }
  if(segmentAxis(A,B)==='v'){
    const x=A.x;
    if(x>=R.l && x<=R.r) return 0;
    return Math.min(Math.abs(x-R.l),Math.abs(x-R.r));
  }
  return 999;
}
function directionPenalty(points,A,B){
  // Penalize leaving the destination envelope and coming back.
  // This does not prohibit intentional far-side routing; it merely makes it expensive.
  const pts=normalizePoints(points);
  const minX=Math.min(A.x,B.x), maxX=Math.max(A.x,B.x);
  const minY=Math.min(A.y,B.y), maxY=Math.max(A.y,B.y);
  let p=0;
  for(const q of pts.slice(1,-1)){
    if(q.x<minX) p += (minX-q.x)*1.8;
    if(q.x>maxX) p += (q.x-maxX)*1.8;
    if(q.y<minY) p += (minY-q.y)*1.8;
    if(q.y>maxY) p += (q.y-maxY)*1.8;
  }
  return p;
}
function pathScore(points,A,B,obstacles=[],occupied=[],ends=null){
  const pts=normalizePoints(points);
  let length=0, bends=Math.max(0,pts.length-2), crossings=0, shared=0, hugging=0, tracks=0, crowded=0;
  for(let i=0;i<pts.length-1;i++){
    const P=pts[i], Q=pts[i+1];
    length += segmentLength(P,Q);
    for(const seg of occupied){
      crossings += segmentsCross(P,Q,seg.a,seg.b) ? 1 : 0;
      shared += sharedLength(P,Q,seg.a,seg.b);
      if(ends&&seg.ends&&!seg.ends.some(e=>ends.includes(e))){if(onOneTrack(P,Q,seg.a,seg.b))tracks++;else if(runsBeside(P,Q,seg.a,seg.b))crowded++}
    }
    for(const R of obstacles){
      const d=distanceSegmentToRect(P,Q,R);
      if(d<12) hugging += (12-d);
    }
  }
  // Readability order: bends > backtracking > crossings > sharing > tiny length differences.
  return (
    length +
    bends*46 +
    directionPenalty(pts,A,B)*2.2 +
    crossings*90 +
    shared*5 +
    tracks*260 +
    crowded*70 +
    hugging*1.6
  );
}
function pathD(points){
  const pts=normalizePoints(points);
  if(!pts.length) return '';
  let d=`M ${pts[0].x} ${pts[0].y}`;
  for(let i=1;i<pts.length;i++){
    const a=pts[i-1],b=pts[i];
    if(a.y===b.y) d+=` H ${b.x}`;
    else if(a.x===b.x) d+=` V ${b.y}`;
    else d+=` L ${b.x} ${b.y}`;
  }
  return d;
}
function uniqueNumbers(values,eps=1){
  const out=[];
  values.sort((a,b)=>a-b);
  for(const v of values){
    if(!out.length || Math.abs(v-out[out.length-1])>eps) out.push(v);
  }
  return out;
}
function snapRouteCoord(v){
  return Math.round(v/ROUTE_SNAP_GRID)*ROUTE_SNAP_GRID;
}
function quantizedNumbers(values){
  return uniqueNumbers(values.map(snapRouteCoord), ROUTE_SNAP_GRID/2);
}
function routeSignature(points){
  const pts=normalizePoints(points);
  if(pts.length<2) return '';
  const parts=[];
  for(let i=0;i<pts.length-1;i++){
    const a=pts[i],b=pts[i+1];
    const axis=segmentAxis(a,b);
    if(axis==='h') parts.push(`H:${snapRouteCoord(a.y)}`);
    else if(axis==='v') parts.push(`V:${snapRouteCoord(a.x)}`);
  }
  return parts.join('|');
}
function routeAnchor(points){
  const pts=normalizePoints(points);
  if(pts.length<3) return {x:0,y:0};
  const mids=pts.slice(1,-1);
  return {
    x:mids.reduce((s,p)=>s+p.x,0)/mids.length,
    y:mids.reduce((s,p)=>s+p.y,0)/mids.length
  };
}
function routeAnchorDistance(a,b){
  return Math.abs(a.x-b.x)+Math.abs(a.y-b.y);
}
function clonePoints(points){
  return (points||[]).map(p=>({x:p.x,y:p.y}));
}
function clonePoses(poses){
  return (poses||[]).map(p=>({
    q:{x:p.q.x,y:p.q.y,angle:p.q.angle},
    reverse:!!p.reverse
  }));
}
function routeCacheFromCandidate(candidate){
  return {
    points:clonePoints(candidate.points),
    core:clonePoints(candidate.core),
    score:candidate.score,
    signature:candidate.signature,
    anchor:{x:candidate.anchor.x,y:candidate.anchor.y},
    blocked:!!candidate.blocked
  };
}
const drawnRoutePoints=new Map();
// A loop that routes every wire while the document stands still asks for the bus routes once and
// holds that answer for the loop (src/41-buses.js withBusRoutes), the way renderWires does. Asked
// per wire, each asking reads both ends of every bus wire: wires x wires end readings a loop.
function withBusRoutesOnce(fn){
  return typeof busRoutesForRender==='function'&&typeof withBusRoutes==='function'?withBusRoutes(busRoutesForRender(),fn):fn();
}
function captureDragSnapshots(nodeId){
  dragRouteSnapshots.clear();
  const occupied=[];
  withBusRoutesOnce(()=>wires.forEach((w,i)=>{
    const A=carrierEndpointPos(w,'a'), B=carrierEndpointPos(w,'b');
    if(!A||!B) return;
    const points=stableRouteForWire(i,w,A,B,occupied);
    occupied.push(...routeSegments(points,w));
    if(w.a===nodeId || w.b===nodeId){
      const drawn=drawnRoutePoints.get(i);
      const useDrawn=!!drawn && drawn.length>=2 &&
        Math.abs(drawn[0].x-A.x)<=0.01 && Math.abs(drawn[0].y-A.y)<=0.01 &&
        Math.abs(drawn[drawn.length-1].x-B.x)<=0.01 && Math.abs(drawn[drawn.length-1].y-B.y)<=0.01;
      dragRouteSnapshots.set(i,{
        points:clonePoints(useDrawn?drawn:points),
        aPos:{x:A.x,y:A.y},
        bPos:{x:B.x,y:B.y}
      });
    }
  }));
}
function settleDraggedRoutes(){
  if(!activeNodeDrag) return;
  const occupied=[];
  withBusRoutesOnce(()=>wires.forEach((w,i)=>{
    const A=carrierEndpointPos(w,'a'), B=carrierEndpointPos(w,'b');
    if(!A||!B) return;

    // A wire on buses settles onto its buses, not onto a route of its own.
    if((w.a===activeNodeDrag || w.b===activeNodeDrag) && !(typeof busSpecOf==='function'&&busSpecOf(w))){
      const candidate=routePoints(A,B,w.aSide,w.bSide,w.a,w.b,w.lane??i,occupied,w.id);
      routeCache.set(i,routeCacheFromCandidate(candidate));
      dragRouteSnapshots.delete(i);
      occupied.push(...routeSegments(candidate.points,w));
    }else{
      const points=stableRouteForWire(i,w,A,B,occupied);
      if(w.a===activeNodeDrag || w.b===activeNodeDrag)dragRouteSnapshots.delete(i);
      occupied.push(...routeSegments(points,w));
    }
  }));
  renderWires();
  wires.forEach((w,i)=>{
    if(!(w.a===activeNodeDrag || w.b===activeNodeDrag)) return;
    const A=carrierEndpointPos(w,'a'), B=carrierEndpointPos(w,'b');
    if(!A||!B||!drawnRoutePoints.has(i)) return;
    dragRouteSnapshots.set(i,{points:clonePoints(drawnRoutePoints.get(i)),aPos:{x:A.x,y:A.y},bPos:{x:B.x,y:B.y}});
  });
  statusEl.textContent='Settled';
}
function scheduleDragSettle(mods=null){
  if(settleTimer) clearTimeout(settleTimer);
  settleTimer=setTimeout(()=>{
    settleTimer=null;

    // Pointer is still held: the component's position is authoritative and
    // continuous. Never quantize it here. Only let connected wires settle
    // around the exact free-position component.
    if(activeNodeDragState){
      settleDraggedRoutes();

      // Re-capture the now-settled wire geometry as the next frozen state,
      // without altering the component position.
      captureDragSnapshots(activeNodeDragState.node.id);
      statusEl.textContent=`Held freely · ${snapModeLabel(dragSnapStep(activeNodeDragState.modifiers))} on release`;
      return;
    }

    settleDraggedRoutes();
  },ROUTE_SETTLE_DELAY);
}


// What a route keeps clear of: every visible card that is not a group and not a container holding
// both ends, padded by the clearance 12, and the wire's own end cards padded 8. A card hosted on
// the wire itself sits on the line and is not in the way. routePoints and the cached rebuild in
// stableRouteForWire take this one set, so a rebuild is held to the rule a fresh route is.
const ROUTE_CLEARANCE=12,ROUTE_END_CLEARANCE=8;
function routeObstacleSet(sourceNode,targetNode,aSide,bSide,routedWire,wireId){
  const hostCanvasId=wireId?localCanvasId('wire',wireId):null;
  const others=nodes
    .filter(n=>n!==sourceNode && n!==targetNode && n.id!==activeNodeDrag && !isGroupComponent(n) && !isEffectivelyHidden(n) && (!hostCanvasId||(n.canvasId||GLOBAL_CANVAS_ID)!==hostCanvasId) && !ignoreContainerObstacle(n,sourceNode,targetNode))
    .map(n=>rectForNode(n,ROUTE_CLEARANCE));
  const ownA=endpointNeedsOuterObstacle(sourceNode,aSide,routedWire)?rectForNode(sourceNode,ROUTE_END_CLEARANCE):null;
  const ownB=endpointNeedsOuterObstacle(targetNode,bSide,routedWire)?rectForNode(targetNode,ROUTE_END_CLEARANCE):null;
  return {hostCanvasId,others,ownA,ownB,obstacles:[...others,...[ownA,ownB].filter(Boolean)]};
}
// An end's lead: the stub from the port P to the lead's end S, and on along the same line. That
// stub is the one part of a route allowed inside its own card's padding.
function axisDirection(P,S){
  if(!P||!S)return null;
  const dx=S.x-P.x,dy=S.y-P.y;
  if(Math.abs(dx)>=.5&&Math.abs(dy)<.5)return {dx:Math.sign(dx),dy:0};
  if(Math.abs(dy)>=.5&&Math.abs(dx)<.5)return {dx:0,dy:Math.sign(dy)};
  return null;
}
function routeLeadRay(P,S,R){
  const d=R?axisDirection(P,S):null;
  return d?{S,R,...d}:null;
}
function onLeadRay(P,Q,lead){
  const tol=.05;
  if(lead.dx)return Math.abs(P.y-lead.S.y)<tol&&Math.abs(Q.y-lead.S.y)<tol&&(P.x-lead.S.x)*lead.dx>=-tol&&(Q.x-lead.S.x)*lead.dx>=-tol;
  return Math.abs(P.x-lead.S.x)<tol&&Math.abs(Q.x-lead.S.x)<tol&&(P.y-lead.S.y)*lead.dy>=-tol&&(Q.y-lead.S.y)*lead.dy>=-tol;
}
function segmentClear(P,Q,obstacles,leads=[]){
  for(const R of obstacles){
    if(!segHitsRect(P,Q,R))continue;
    if(leads.some(l=>l&&l.R===R&&onLeadRay(P,Q,l)))continue;
    return false;
  }
  return true;
}
// A route enters no padded obstacle; only each end's lead may sit inside its own card's padding.
function routeClear(points,obstacles,leads=[]){
  const pts=normalizePoints(points);
  for(let i=0;i<pts.length-1;i++)if(!segmentClear(pts[i],pts[i+1],obstacles,leads))return false;
  return true;
}
// What one segment costs against the routes already drawn: the crossing, shared-track and crowding
// terms of pathScore.
function occupiedCost(P,Q,occupied,ends){
  let c=0;
  for(const seg of occupied){
    if(segmentsCross(P,Q,seg.a,seg.b))c+=90;
    c+=sharedLength(P,Q,seg.a,seg.b)*5;
    if(ends&&seg.ends&&!seg.ends.some(e=>ends.includes(e))){if(onOneTrack(P,Q,seg.a,seg.b))c+=260;else if(runsBeside(P,Q,seg.a,seg.b))c+=70}
  }
  return c;
}
// Orthogonal connector routing (Wybrow, Marriott and Stuckey, GD 2009; libavoid): A* over the grid
// of channel lines, from the source lead's end to the target lead's end, along grid edges that enter
// no padded obstacle. Cost: length + 46 per bend + occupiedCost. Returns the grid points or null.
const ROUTE_BEND_COST=46;
function gridRoute(SA,SB,xs,ys,obstacles,leads,fence,occupied,ends,outA,inB){
  const X=uniqueNumbers([...xs,SA.x,SB.x],.01),Y=uniqueNumbers([...ys,SA.y,SB.y],.01);
  const ix=v=>{let k=0;for(let i=1;i<X.length;i++)if(Math.abs(X[i]-v)<Math.abs(X[k]-v))k=i;return k};
  const iy=v=>{let k=0;for(let i=1;i<Y.length;i++)if(Math.abs(Y[i]-v)<Math.abs(Y[k]-v))k=i;return k};
  const sx=ix(SA.x),sy=iy(SA.y),gx=ix(SB.x),gy=iy(SB.y),NY=Y.length;
  const pt=(i,j)=>(i===sx&&j===sy)?SA:(i===gx&&j===gy)?SB:{x:X[i],y:Y[j]};
  const inside=(i,j)=>!fence||(i===sx&&j===sy)||(i===gx&&j===gy)||routeInsideFence([null,{x:X[i],y:Y[j]},null],fence);
  const DIRS=[[1,0],[-1,0],[0,1],[0,-1]];
  const dirOf=v=>v?DIRS.findIndex(d=>d[0]===v.dx&&d[1]===v.dy):-1;
  const start=dirOf(outA),finish=dirOf(inB);
  const key=(i,j,d)=>((i*NY+j)*5)+d+1;
  const heur=(i,j)=>Math.abs(X[i]-SB.x)+Math.abs(Y[j]-SB.y);
  const gScore=new Map(),from=new Map(),edgeMemo=new Map(),heap=[];
  const push=n=>{heap.push(n);let c=heap.length-1;while(c>0){const p=(c-1)>>1;if(heap[p].f<=heap[c].f)break;[heap[p],heap[c]]=[heap[c],heap[p]];c=p}};
  const pop=()=>{const top=heap[0],last=heap.pop();if(heap.length){heap[0]=last;let c=0;for(;;){const l=2*c+1,r=l+1;let m=c;if(l<heap.length&&heap[l].f<heap[m].f)m=l;if(r<heap.length&&heap[r].f<heap[m].f)m=r;if(m===c)break;[heap[m],heap[c]]=[heap[c],heap[m]];c=m}}return top};
  const k0=key(sx,sy,start);gScore.set(k0,0);push({i:sx,j:sy,d:start,g:0,f:heur(sx,sy),k:k0});
  let budget=60000;
  while(heap.length&&budget-->0){
    const cur=pop();
    if(!cur.done&&cur.g>(gScore.get(cur.k)??Infinity))continue;
    if(cur.i===gx&&cur.j===gy){
      // Arrive heading into the target's lead, or pay for the bend there.
      const total=cur.g+(finish>=0&&cur.d>=0&&cur.d!==finish?ROUTE_BEND_COST:0);
      if(!cur.done){push({...cur,g:total,f:total,done:true});continue}
      const out=[];let k=cur.k,node=cur;
      while(node){out.push(pt(node.i,node.j));node=from.get(k);k=node?.k}
      return out.reverse();
    }
    if(cur.done)continue;
    for(let d=0;d<4;d++){
      const ni=cur.i+DIRS[d][0],nj=cur.j+DIRS[d][1];
      if(ni<0||nj<0||ni>=X.length||nj>=NY||!inside(ni,nj))continue;
      const P=pt(cur.i,cur.j),Q=pt(ni,nj);
      if(Math.abs(P.x-Q.x)>.01&&Math.abs(P.y-Q.y)>.01)continue;
      const ek=Math.min(cur.i*NY+cur.j,ni*NY+nj)+':'+Math.max(cur.i*NY+cur.j,ni*NY+nj);
      let edge=edgeMemo.get(ek);
      if(edge===undefined){edge=segmentClear(P,Q,obstacles,leads)?segmentLength(P,Q)+occupiedCost(P,Q,occupied,ends):null;edgeMemo.set(ek,edge)}
      if(edge===null)continue;
      const g=cur.g+edge+(cur.d>=0&&cur.d!==d?ROUTE_BEND_COST:0),k=key(ni,nj,d);
      if(g>=(gScore.get(k)??Infinity))continue;
      gScore.set(k,g);from.set(k,cur);push({i:ni,j:nj,d,g,f:g+heur(ni,nj),k});
    }
  }
  return null;
}

function routePoints(A,B,aSide='out',bSide='in',sourceId=null,targetId=null,laneSeed=0,occupied=[],wireId=null){
  const sourceNode=nodes.find(n=>n.id===sourceId);
  const targetNode=nodes.find(n=>n.id===targetId);
  const routedWire=wireId?wires.find(x=>x.id===wireId):null;
  const ends=routedWire?[`${routedWire.a}:${routedWire.aSide}`,`${routedWire.b}:${routedWire.bSide}`]:null;
  // A free end has no boundary to leave; the route starts exactly there.
  // A carrier on a Component's interior runs inside it: that interior is its whole surface.
  const fence=routeFence(routedWire);
  // A lead never leaves the fence: a card near the core's edge gets a shorter lead, not a detour.
  const inFence=P=>fence?{x:Math.max(fence.l+2,Math.min(fence.r-2,P.x)),y:Math.max(fence.t+2,Math.min(fence.b-2,P.y))}:P;
  const SA=sourceNode?inFence(routeLead(A,B,aSide,sourceNode,wireEndpointInward(routedWire,sourceNode))):A, SB=targetNode?inFence(routeLead(B,A,bSide,targetNode,wireEndpointInward(routedWire,targetNode))):B;
  // A group is drawn behind everything and is never an obstacle (SECTION-MODEL.md "Groups").
  // Source and target are included after the outward lead. This prevents a path
  // from exiting one side and visually tunneling through either endpoint card.
  const {hostCanvasId,ownA,ownB,obstacles}=routeObstacleSet(sourceNode,targetNode,aSide,bSide,routedWire,wireId);
  const leads=[routeLeadRay(A,SA,ownA),routeLeadRay(B,SB,ownB)].filter(Boolean);

  const allRects=nodes.filter(n=>n.id!==activeNodeDrag&&!isGroupComponent(n)&&(!hostCanvasId||(n.canvasId||GLOBAL_CANVAS_ID)!==hostCanvasId)&&!ignoreContainerObstacle(n,sourceNode,targetNode)).map(n=>rectForNode(n,16));
  const xs=[SA.x,SB.x,(SA.x+SB.x)/2];
  const ys=[SA.y,SB.y,(SA.y+SB.y)/2];
  if(fence){xs.push(fence.l+14,fence.r-14);ys.push(fence.t+14,fence.b-14)}

  for(const R of allRects){
    xs.push(R.l-18,R.r+18);
    ys.push(R.t-18,R.b+18);
  }

  // A private nearby channel prevents unrelated wires from collapsing onto one track.
  const lane=((laneSeed%9)-4)*10;
  xs.push((SA.x+SB.x)/2+lane);
  ys.push((SA.y+SB.y)/2+lane);

  const channelsX=quantizedNumbers(xs);
  const channelsY=quantizedNumbers(ys);
  const candidates=[];

  // Straight when aligned.
  if(Math.abs(SA.y-SB.y)<1) candidates.push([SA,SB]);
  if(Math.abs(SA.x-SB.x)<1) candidates.push([SA,SB]);

  // L routes.
  candidates.push([SA,{x:SB.x,y:SA.y},SB]);
  candidates.push([SA,{x:SA.x,y:SB.y},SB]);

  // H-V-H and V-H-V through candidate channels.
  for(const x of channelsX){
    candidates.push([SA,{x,y:SA.y},{x,y:SB.y},SB]);
  }
  for(const y of channelsY){
    candidates.push([SA,{x:SA.x,y},{x:SB.x,y},SB]);
  }

  const valid=candidates
    .map(normalizePoints)
    .filter(points=>routeClear(points,obstacles,leads)&&routeInsideFence(points,fence))
    .map(points=>({
      points,
      score:pathScore(points,SA,SB,obstacles,occupied,ends),
      signature:routeSignature(points),
      anchor:routeAnchor(points)
    }))
    .sort((a,b)=>a.score-b.score);

  let chosen=valid[0]||null,blocked=false;

  if(!chosen){
    // No simple shape clears: search the channel grid rather than take a route through a card.
    const found=gridRoute(SA,SB,channelsX,channelsY,obstacles,leads,fence,occupied,ends,axisDirection(A,SA),axisDirection(SB,B));
    if(found){
      const points=normalizePoints(found);
      chosen={points,score:pathScore(points,SA,SB,obstacles,occupied,ends),signature:routeSignature(points),anchor:routeAnchor(points)};
    }
  }

  if(!chosen){
    // The grid has no clear route either: the route is blocked, and drawn round the perimeter.
    blocked=true;
    // Last resort: a clean perimeter route. Choose the cheapest of four sides; inside a
    // fence the perimeter is the fence's own inner edge, never the world outside it.
    const minL=fence?fence.l+8:Math.min(SA.x,SB.x,...allRects.map(r=>r.l))-36-Math.abs(lane);
    const maxR=fence?fence.r-8:Math.max(SA.x,SB.x,...allRects.map(r=>r.r))+36+Math.abs(lane);
    const minT=fence?fence.t+8:Math.min(SA.y,SB.y,...allRects.map(r=>r.t))-36-Math.abs(lane);
    const maxB=fence?fence.b-8:Math.max(SA.y,SB.y,...allRects.map(r=>r.b))+36+Math.abs(lane);
    const fallback=[
      [SA,{x:SA.x,y:minT},{x:SB.x,y:minT},SB],
      [SA,{x:SA.x,y:maxB},{x:SB.x,y:maxB},SB],
      [SA,{x:minL,y:SA.y},{x:minL,y:SB.y},SB],
      [SA,{x:maxR,y:SA.y},{x:maxR,y:SB.y},SB],
    ].map(normalizePoints)
     .map(points=>({
       points,
       score:pathScore(points,SA,SB,obstacles,occupied,ends),
       signature:routeSignature(points),
       anchor:routeAnchor(points)
     }))
     .sort((a,b)=>a.score-b.score);
    // Prefer a perimeter that clears every body; when none does, the cheapest that still leaves and
    // arrives along each port's lead (it never doubles back over a port), and only then the cheapest.
    const alongLeads=f=>{
      const p=normalizePoints([A,SA,...f.points.slice(1,-1),SB,B]),same=(u,v)=>!u||(!!v&&u.dx===v.dx&&u.dy===v.dy);
      return p.length<2||(same(sourceNode&&axisDirection(A,SA),axisDirection(p[0],p[1]))&&same(targetNode&&axisDirection(SB,B),axisDirection(p.at(-2),p.at(-1))));
    };
    chosen=fallback.find(f=>routeClear(f.points,obstacles,leads))||fallback.find(alongLeads)||fallback[0];
  }

  return {
    points: normalizePoints([A,SA,...chosen.points.slice(1,-1),SB,B]),
    core: chosen.points,
    score: chosen.score,
    signature: chosen.signature,
    anchor: chosen.anchor,
    blocked,
    obstacles
  };
}
// The first bend point after leaving an endpoint. A lead never overshoots a facing port:
// across a short gap each lead takes at most half of it. A free 0D Point has no side, so it
// leaves toward the other end along the dominant axis, with a short lead.
const ROUTE_LEAD=26,POINT_LEAD=12;
function routeLead(P,Q,portId,node,inward){
  const placement=componentPlacement(node);
  if(componentForm(node).dimension===0&&placement.kind!=='edge'&&!componentHostedOnWire(node)){
    const dx=Q.x-P.x,dy=Q.y-P.y;
    if(Math.abs(dx)<1&&Math.abs(dy)<1)return P;
    return Math.abs(dx)>=Math.abs(dy)?{x:P.x+Math.sign(dx)*Math.min(POINT_LEAD,Math.abs(dx)/2),y:P.y}:{x:P.x,y:P.y+Math.sign(dy)*Math.min(POINT_LEAD,Math.abs(dy)/2)};
  }
  const unit=stubPos(P,portId,1,node,inward),nx=unit.x-P.x,ny=unit.y-P.y;
  const ahead=(Q.x-P.x)*nx+(Q.y-P.y)*ny;
  let d=ahead>0?Math.max(4,Math.min(ROUTE_LEAD,ahead/2)):ROUTE_LEAD;
  // Nor into a body in front of it: stop short of the first card the lead would enter.
  for(const other of nodes){
    if(other.id===node.id||componentForm(other).dimension!==2||isGroupComponent(other)||isDescendantOf(node.id,other.id)||isEffectivelyHidden(other))continue;
    const R=componentBounds(other,10);
    for(let s=2;s<=d;s+=2){const x=P.x+nx*s,y=P.y+ny*s;if(x>R.l&&x<R.r&&y>R.t&&y<R.b){d=Math.max(4,s/2);break}}
  }
  return {x:P.x+nx*d,y:P.y+ny*d};
}
// How a declared route joins an end's lead (LAYOUT-MODEL.md "As built: port side"). N is the
// route's point next to the end, P the port, S the lead's end. Returned: the corners between N and
// S, in that order, so the route reaches S from outside the stretch between S and the port and the
// segment touching the port runs along the port's normal. Tried in order: the corner asked for, the
// other corner, then round the end's own card on its nearer and its farther side; the first that
// also keeps out of the card's padding is taken. node is the end's card when its body is an
// obstacle to this wire, else null (the corner asked for is returned). Points closer than eps to
// one axis line count as aligned and need no corner. Pinned and guided routes (src/58-layouts.js)
// and bus taps (src/41-buses.js) build their ends with this.
function leadJoin(N,P,S,node,first=null,eps=.5){
  const aligned=Math.abs(N.x-S.x)<=eps||Math.abs(N.y-S.y)<=eps,asked=aligned||!first?[]:[first];
  const d=axisDirection(P,S);
  if(!d||!node||componentForm(node).dimension!==2||componentHostedOnWire(node))return asked;
  const R=componentBounds(node,Math.min(ROUTE_END_CLEARANCE,Math.abs(S.x-P.x)+Math.abs(S.y-P.y))),W=componentBounds(node,ROUTE_CLEARANCE),lead={S,R,...d};
  const nearer=(p,q,at)=>Math.abs(p-at)<=Math.abs(q-at)?[p,q]:[q,p];
  const options=[asked,...(aligned?[]:[[{x:S.x,y:N.y}],[{x:N.x,y:S.y}]]),
    ...(d.dx?nearer(W.t,W.b,N.y).map(y=>[{x:N.x,y},{x:S.x,y}]):nearer(W.l,W.r,N.x).map(x=>[{x,y:N.y},{x,y:S.y}]))];
  const path=mid=>{const out=[{x:N.x,y:N.y}];for(const q of [...mid,S]){const p=out.at(-1);out.push(Math.abs(p.x-q.x)<=eps?{x:p.x,y:q.y}:Math.abs(p.y-q.y)<=eps?{x:q.x,y:p.y}:q)}return normalizePoints(out)};
  // The point before S is off the lead's line, or on it beyond S: never between S and the port or behind the port.
  const reaches=mid=>{const pts=path(mid);if(pts.length<2)return true;const M=pts.at(-2),E=pts.at(-1);return Math.abs((M.x-E.x)*d.dy)+Math.abs((M.y-E.y)*d.dx)>=.5||(M.x-E.x)*d.dx+(M.y-E.y)*d.dy>=0};
  const clear=mid=>{const pts=path(mid);for(let i=0;i<pts.length-1;i++)if(!segmentClear(pts[i],pts[i+1],[R],[lead]))return false;return true};
  return options.find(o=>reaches(o)&&clear(o))||options.find(reaches)||asked;
}
function routeFence(wire){
  const surface=wire?.canvasId||'';
  if(!surface.startsWith('canvas:component:'))return null;
  const owner=nodes.find(n=>componentCanvas(n).id===surface);
  // The interior is the core: inside the innermost line of the owner's section.
  return owner?componentBounds(owner,-4-(typeof componentSectionInset==='function'?componentSectionInset(owner):0)):null;
}
function routeInsideFence(points,fence){
  if(!fence)return true;
  // The ends sit where their points are (a through-point sits in the skin); the route between stays in.
  return points.slice(1,-1).every(p=>p.x>=fence.l-.5&&p.x<=fence.r+.5&&p.y>=fence.t-.5&&p.y<=fence.b+.5);
}
function routePath(A,B,aSide='out',bSide='in',sourceId=null,targetId=null,laneSeed=0,occupied=[]){
  return pathD(routePoints(A,B,aSide,bSide,sourceId,targetId,laneSeed,occupied).points);
}
function stableRouteForWire(index,w,A,B,occupied=[]){
  // A route the layout on screen pins or guides is drawn as declared, not re-derived. A wire on
  // buses rides them (src/41-buses.js); when that route cannot be built the router takes over.
  const spec=typeof activeRouteSpec==='function'?activeRouteSpec(w.id):null;
  if(spec?.mode==='bus'){const onBus=typeof busRouteFor==='function'?busRouteFor(w):null;if(onBus)return onBus}
  else if(spec){const declared=routeThroughSpec(A,B,w,spec);if(declared)return declared}
  // Two free ends have no normal to meet and no boundary to leave: there is nothing for
  // orthogonal routing to do, so the carrier is the segment between its own two points -
  // straight even when the ends are not aligned, the same thing a 1D Form's body is between its
  // own two boundary points. A pinned, guided or bus route above still wins; this only replaces
  // the open router's own elbow. The cache is dropped so a route chosen while an end was still
  // bound cannot survive the unbinding, and binding an end again starts fresh.
  if(carrierEndpoint(w,'a')?.kind==='free'&&carrierEndpoint(w,'b')?.kind==='free'){
    routeCache.delete(index);
    return normalizePoints([A,B]);
  }
  const candidate=routePoints(A,B,w.aSide,w.bSide,w.a,w.b,w.lane??index,occupied,w.id);
  const cached=routeCache.get(index);

  if(!cached){
    routeCache.set(index,{
      points:candidate.points,
      core:candidate.core,
      score:candidate.score,
      signature:candidate.signature,
      anchor:candidate.anchor,
      blocked:candidate.blocked
    });
    return candidate.points;
  }

  // Rebuild the cached topology around the moving endpoints by keeping its
  // interior channel coordinates. This avoids a frozen wire while still
  // preserving the chosen route family.
  const cachedCore=cached.core||[];
  const sourceNode=nodes.find(n=>n.id===w.a);
  const targetNode=nodes.find(n=>n.id===w.b);
  let rebuilt=null;
  if(cachedCore.length>=2){
    const SA=sourceNode?routeLead(A,B,w.aSide,sourceNode,wireEndpointInward(w,sourceNode)):A, SB=targetNode?routeLead(B,A,w.bSide,targetNode,wireEndpointInward(w,targetNode)):B;
    const inner=cachedCore.slice(1,-1).map(q=>({x:q.x,y:q.y}));
    rebuilt=normalizePoints([A,SA,...inner,SB,B]);

    // Cached topology may remain readable while endpoints move. It is thrown away when its
    // route enters any padded obstacle, the wire's own end cards included; only the leads
    // may sit inside their own card's padding.
    const routeOnly=normalizePoints([SA,...inner,SB]);
    const {ownA,ownB,obstacles}=routeObstacleSet(sourceNode,targetNode,w.aSide,w.bSide,w,w.id);
    const leads=[routeLeadRay(A,SA,ownA),routeLeadRay(B,SB,ownB)].filter(Boolean);

    if(!routeClear(routeOnly,obstacles,leads)||!routeInsideFence(routeOnly,routeFence(w))) rebuilt=null;
  }

  if(!rebuilt){
    routeCache.set(index,{
      points:candidate.points,core:candidate.core,score:candidate.score,
      signature:candidate.signature,anchor:candidate.anchor,blocked:candidate.blocked
    });
    return candidate.points;
  }

  const SA=sourceNode?routeLead(A,B,w.aSide,sourceNode,wireEndpointInward(w,sourceNode)):A, SB=targetNode?routeLead(B,A,w.bSide,targetNode,wireEndpointInward(w,targetNode)):B;
  const rebuiltCore=normalizePoints([SA,...rebuilt.slice(2,-2),SB]);
  const rebuiltScore=pathScore(rebuiltCore,SA,SB,routeObstacleSet(sourceNode,targetNode,w.aSide,w.bSide,w,w.id).others,occupied,[`${w.a}:${w.aSide}`,`${w.b}:${w.bSide}`]);
  const anchor=routeAnchor(rebuiltCore);

  const sameFamily = candidate.signature===cached.signature;
  const movementPastRelease = routeAnchorDistance(anchor,cached.anchor||anchor) > ROUTE_RELEASE_DISTANCE;
  const clearlyBetter = candidate.score + ROUTE_SWITCH_MARGIN < rebuiltScore;

  // Hysteresis:
  // - same topology family: allow its geometry to update quietly
  // - different family: hold the old one through the dead zone
  // - switch only when materially better or after the old route drifts too far
  if(sameFamily || (clearlyBetter && movementPastRelease)){
    routeCache.set(index,{
      points:candidate.points,core:candidate.core,score:candidate.score,
      signature:candidate.signature,anchor:candidate.anchor,blocked:candidate.blocked
    });
    return candidate.points;
  }

  routeCache.set(index,{
    ...cached,
    points:rebuilt,
    score:rebuiltScore,
    anchor,
    blocked:false
  });
  return rebuilt;
}

// Whether the wire at this index is drawn on the perimeter fallback because neither a simple shape
// nor the grid search found a clear route (the wire group's data-route-blocked).
function routeBlockedAt(index){return !!routeCache.get(index)?.blocked}

// Segments a later route must keep clear of, tagged with the wire's two ends: wires that
// share an end (a fan-out, a fan-in) may run together; any others may not run on one track.
function routeSegments(points,w=null){
  const pts=normalizePoints(points), out=[];
  const ends=w?[`${w.a}:${w.aSide}`,`${w.b}:${w.bSide}`]:null;
  for(let i=0;i<pts.length-1;i++) out.push({a:pts[i],b:pts[i+1],ends});
  return out;
}
// Two unrelated segments side by side, closer than a reader can tell apart, for a real stretch.
function runsBeside(A,B,C,D,near=16,stretch=16){
  const ab=segmentAxis(A,B),cd=segmentAxis(C,D);if(ab!==cd||ab==='d')return false;
  const off=ab==='h'?Math.abs(A.y-C.y):Math.abs(A.x-C.x);if(off<3||off>=near)return false;
  const [p,q,r,s]=ab==='h'?[A.x,B.x,C.x,D.x]:[A.y,B.y,C.y,D.y];
  return Math.min(Math.max(p,q),Math.max(r,s))-Math.max(Math.min(p,q),Math.min(r,s))>=stretch;
}
// Two segments on one track: collinear and overlapping, or end to end within a gap a reader
// would read as one line.
function onOneTrack(A,B,C,D,gap=14){
  const ab=segmentAxis(A,B),cd=segmentAxis(C,D);if(ab!==cd||ab==='d')return false;
  const [p,q,r,s,off]=ab==='h'?[A.x,B.x,C.x,D.x,Math.abs(A.y-C.y)]:[A.y,B.y,C.y,D.y,Math.abs(A.x-C.x)];
  if(off>=3)return false;
  const lo1=Math.min(p,q),hi1=Math.max(p,q),lo2=Math.min(r,s),hi2=Math.max(r,s);
  return Math.max(lo1,lo2)-Math.min(hi1,hi2)<gap;
}

// ---- Track gap (LAYOUT-MODEL.md "As built: track gap") -------------------------------------------
// Two auto-routed wires whose parallel interior segments overlap for TRACK_STRETCH or more stand at
// least TRACK_GAP apart; wires sharing an end may instead share one line exactly (a trunk, which the
// junction dot marks where it parts). TRACK_GAP is the step of a wire's private lane in routePoints.
// After every route is drawn, jogs (a step under TRACK_JOG between two parallel legs) are taken out,
// then the segments that share a channel are ordered and spread (the nudging phase of orthogonal
// connector routing: Wybrow, Marriott and Stuckey, GD 2009; libavoid's nudging and centring; ELK's
// slot assignment). End leads, pinned and guided routes, bus routes and free/free carriers never
// move: they are fixed segments the others keep the rule against.
const TRACK_GAP=10,TRACK_STRETCH=24,TRACK_JOG=10;
// What one wire's route keeps clear of, the rule routePoints uses, plus the fence of an interior.
function routeObstaclesForWire(w){
  const sourceNode=w.a?nodes.find(n=>n.id===w.a)||null:null,targetNode=w.b?nodes.find(n=>n.id===w.b)||null:null;
  return {...routeObstacleSet(sourceNode,targetNode,w.aSide,w.bSide,w,w.id),fence:routeFence(w)};
}
function trackEnds(w){return w?[w.a?`${w.a}:${w.aSide}`:null,w.b?`${w.b}:${w.bSide}`:null].filter(Boolean):[]}
function trackSeg(P,Q){
  const h=Math.abs(P.y-Q.y)<.01,v=Math.abs(P.x-Q.x)<.01;if(h===v)return null;
  return h?{axis:'h',c:P.y,lo:Math.min(P.x,Q.x),hi:Math.max(P.x,Q.x)}:{axis:'v',c:P.x,lo:Math.min(P.y,Q.y),hi:Math.max(P.y,Q.y)};
}
// An item is one drawn route; its segments are interior (movable), lead (an end's stub) or fixed.
function trackItemSegs(it){
  const p=it.pts,n=p.length,out=[];
  for(let k=0;k<n-1;k++){const s=trackSeg(p[k],p[k+1]);if(!s)continue;s.item=it;s.k=k;s.kind=!it.movable?'fixed':(k===0||k===n-2)?'lead':'interior';s.ends=it.ends;out.push(s)}
  return out;
}
// How badly a pair breaks the rule: 0 when it keeps it, else TRACK_GAP less the distance.
function trackPairCost(s,t){
  if(s.axis!==t.axis||(s.item&&s.item===t.item))return 0;
  if(s.kind!=='interior'&&t.kind!=='interior')return 0;
  if(Math.min(s.hi,t.hi)-Math.max(s.lo,t.lo)<TRACK_STRETCH)return 0;
  const d=Math.abs(s.c-t.c);if(d>=TRACK_GAP)return 0;
  if(d<.5)return s.ends.some(e=>t.ends.includes(e))?0:TRACK_GAP;
  return TRACK_GAP-d;
}
// Takes out jogs, then orders and spreads the segments that share a channel, changing the points of
// the movable routes in place. fixed: further segments ({a, b, ends}) that never move (bus lanes and
// taps). obstacles(wire): what that wire's route keeps clear of. Returns the route keys still closer
// than TRACK_GAP to a neighbour because the channel has no room.
function nudgeRoutes(routes,fixed=[],obstacles=routeObstaclesForWire){
  const cramped=new Set();
  if(typeof window!=='undefined'&&window.ROUTE_NUDGE===false)return cramped;
  const items=[];
  for(const [key,r] of routes){
    const w=wires[key];if(!w||!r?.points||r.points.length<2)continue;
    const spec=typeof activeRouteSpec==='function'?activeRouteSpec(w.id):null;
    const freeFree=carrierEndpoint(w,'a')?.kind==='free'&&carrierEndpoint(w,'b')?.kind==='free';
    const movable=!r.snapshot&&!spec&&!freeFree;
    items.push({key,w,r,idx:items.length,movable,ends:trackEnds(w),pts:normalizePoints(r.points)});
  }
  const movers=items.filter(it=>it.movable&&it.pts.length>=4);
  if(!movers.length)return cramped;
  const fixedSegs=[];
  for(const f of fixed){const s=f&&f.a&&f.b?trackSeg(f.a,f.b):null;if(!s)continue;s.item=null;s.k=-1;s.kind='fixed';s.ends=Array.isArray(f.ends)?f.ends:[];fixedSegs.push(s)}
  const segOf=new Map(items.map(it=>[it,trackItemSegs(it)]));
  let all=null;const allSegs=()=>all||(all=[...fixedSegs,...[...segOf.values()].flat()]);
  const refresh=list=>{for(const it of list)segOf.set(it,trackItemSegs(it));all=null};
  // The rule's cost touching the given items, each pair once.
  const badness=W=>{
    const set=new Set(W),A=allSegs();let sum=0;
    for(const it of W)for(const s of segOf.get(it))for(const t of A){
      if(t.axis!==s.axis||Math.abs(t.c-s.c)>=TRACK_GAP||t.item===it)continue;
      if(t.item&&set.has(t.item)&&t.item.idx<it.idx)continue;
      sum+=trackPairCost(s,t);
    }
    return sum;
  };
  const rulePartners=it=>{const out=new Set();for(const s of segOf.get(it))for(const t of allSegs())if(t.item!==it&&trackPairCost(s,t)>0)out.add(t.item?t.item.idx:-1);return out};
  // Crossings the given items make with every other route: wires sharing an end may cross once.
  const crossings=W=>{
    const set=new Set(W);let sum=0;
    for(const it of W)for(const o of items){
      if(o===it||(set.has(o)&&o.idx<it.idx))continue;
      let c=0;
      for(let i=1;i<it.pts.length;i++)for(let j=1;j<o.pts.length;j++)if(segmentsCross(it.pts[i-1],it.pts[i],o.pts[j-1],o.pts[j]))c++;
      sum+=it.ends.some(e=>o.ends.includes(e))?Math.max(0,c-1):c;
    }
    return sum;
  };
  const obsCache=new Map(),obsOf=it=>{if(!obsCache.has(it))obsCache.set(it,obstacles(it.w));return obsCache.get(it)};
  // Segments of a route that enter a padded obstacle: the core against every obstacle (leads
  // excepted on their own ray), each lead against the cards that are not its own.
  const blockedKeys=(it,pts)=>{
    const o=obsOf(it),n=pts.length,out=new Set(),key=(P,Q)=>`${P.x},${P.y},${Q.x},${Q.y}`;
    const leads=[routeLeadRay(pts[0],pts[1],o.ownA),routeLeadRay(pts[n-1],pts[n-2],o.ownB)].filter(Boolean);
    for(let k=0;k<n-1;k++){
      const P=pts[k],Q=pts[k+1];if(P.x===Q.x&&P.y===Q.y)continue;
      const lead=k===0||k===n-2;
      if(lead?o.others.some(R=>segHitsRect(P,Q,R)):!segmentClear(P,Q,o.obstacles,leads))out.add(key(P,Q));
    }
    return out;
  };
  // A move keeps every segment's direction, every lead at least as long as 4 (or as it was), enters
  // no padded obstacle it was not already in, and stays inside an interior's fence.
  const shapeHolds=(it,before)=>{
    const after=it.pts,n=after.length;
    for(let k=0;k<n-1;k++){
      const d0={x:before[k+1].x-before[k].x,y:before[k+1].y-before[k].y},d1={x:after[k+1].x-after[k].x,y:after[k+1].y-after[k].y};
      if(d0.x*d1.x<0||d0.y*d1.y<0)return false;
      if(k===0||k===n-2){const L0=Math.abs(d0.x)+Math.abs(d0.y),L1=Math.abs(d1.x)+Math.abs(d1.y);if(L1<Math.min(4,L0)-.01)return false}
    }
    const was=blockedKeys(it,normalizePoints(before));
    for(const k of blockedKeys(it,normalizePoints(after)))if(!was.has(k))return false;
    const fence=obsOf(it).fence;
    return !fence||!routeInsideFence(before,fence)||routeInsideFence(after,fence);
  };
  // Try a change to some routes; keep it only when accept(before, after) holds, the routes make no
  // new crossing and every shape holds.
  const attempt=(W,apply,accept)=>{
    const saved=W.map(it=>it.pts.map(p=>({x:p.x,y:p.y})));
    const before={bad:badness(W),cross:crossings(W),partners:W.map(rulePartners)};
    apply();refresh(W);
    const ok=W.every((it,i)=>shapeHolds(it,saved[i]))&&(()=>{const after={bad:badness(W),cross:crossings(W),partners:W.map(rulePartners)};return after.cross<=before.cross&&accept(before,after)})();
    if(!ok){W.forEach((it,i)=>{it.pts=saved[i]});refresh(W)}
    return ok;
  };
  const setLine=(pts,k,axis,c)=>{if(axis==='h'){pts[k].y=c;pts[k+1].y=c}else{pts[k].x=c;pts[k+1].x=c}};

  // Jogs: the leg that is not an end lead moves onto the other leg's line, when that leaves no new
  // pair breaking the rule.
  for(const it of movers){
    for(let guard=0;guard<it.pts.length;guard++){
      const p=it.pts,n=p.length;let done=false;
      for(let k=1;k<=n-3&&!done;k++){
        const len=segmentLength(p[k],p[k+1]);if(!(len>.01&&len<TRACK_JOG))continue;
        const legAxis=segmentAxis(p[k],p[k+1])==='v'?'h':'v',coord=q=>legAxis==='h'?q.y:q.x;
        const options=[];
        if(k+1<=n-3)options.push({move:k+1,to:coord(p[k]),len:segmentLength(p[k+1],p[k+2])});
        if(k-1>=1)options.push({move:k-1,to:coord(p[k+1]),len:segmentLength(p[k-1],p[k])});
        options.sort((x,y)=>x.len-y.len);
        for(const o of options){
          if(attempt([it],()=>setLine(it.pts,o.move,legAxis,o.to),(b,a)=>a.bad<=b.bad&&[...a.partners[0]].every(x=>b.partners[0].has(x)))){it.pts=normalizePoints(it.pts);refresh([it]);done=true;break}
        }
      }
      if(!done)break;
    }
  }

  // Nudging: channel by channel, order the segments and spread them TRACK_GAP apart.
  const failed=new Set();
  for(let pass=0;pass<3;pass++){
    const A=allSegs(),parent=new Map(),find=s=>{while(parent.get(s)!==s){parent.set(s,parent.get(parent.get(s)));s=parent.get(s)}return s};
    for(const axis of ['h','v']){
      const L=A.filter(s=>s.axis===axis).sort((p,q)=>p.c-q.c);
      for(let i=0;i<L.length;i++)for(let j=i+1;j<L.length&&L[j].c-L[i].c<TRACK_GAP;j++){
        if(trackPairCost(L[i],L[j])<=0)continue;
        for(const s of [L[i],L[j]])if(!parent.has(s))parent.set(s,s);
        const a=find(L[i]),b=find(L[j]);if(a!==b)parent.set(a,b);
      }
    }
    const groups=new Map();for(const s of parent.keys()){const r=find(s);if(!groups.has(r))groups.set(r,[]);groups.get(r).push(s)}
    let changed=false;
    for(const members of groups.values()){
      const sig=members.map(s=>`${s.item?s.item.key:'f'}:${s.k}:${s.c}`).sort().join('|');
      if(failed.has(sig))continue;
      const axis=members[0].axis;
      // Slots: wires on one line that share an end are one trunk and move together.
      members.sort((p,q)=>p.c-q.c);
      const slots=[];
      for(const s of members){const last=slots.at(-1);if(last&&Math.abs(s.c-last.c)<.5&&last.members.some(t=>t.ends.some(e=>s.ends.includes(e)))){last.members.push(s);continue}slots.push({c:s.c,members:[s]})}
      for(const sl of slots){sl.fixed=sl.members.some(s=>s.kind!=='interior');if(sl.fixed)sl.c=sl.members.find(s=>s.kind!=='interior').c}
      // Metro-line order: an arm leaving a segment inside the other's span wants its segment on the
      // side the arm goes, so the arm never crosses the other segment.
      const arms=s=>{
        if(!s.item)return [];const p=s.item.pts,out=[];
        for(const [at,next] of [[s.k,s.k-1],[s.k+1,s.k+2]]){if(next<0||next>=p.length)continue;const d=axis==='h'?Math.sign(p[next].x-p[at].x):Math.sign(p[next].y-p[at].y);const e=axis==='h'?p[at].x:p[at].y;if(d)out.push({e,d})}
        return out;
      };
      const vote=(s,t)=>{let v=0;for(const a of arms(s))if(a.e>t.lo+.01&&a.e<t.hi-.01)v+=a.d;for(const a of arms(t))if(a.e>s.lo+.01&&a.e<s.hi-.01)v-=a.d;return v};
      const slotVote=(x,y)=>{let v=0;for(const s of x.members)for(const t of y.members)v+=vote(s,t);return v};
      const free=slots.filter(sl=>!sl.fixed),anchors=slots.filter(sl=>sl.fixed).sort((p,q)=>p.c-q.c);
      if(!free.length)continue;
      for(const sl of free){sl.score=free.reduce((a,o)=>o===sl?a:a+slotVote(sl,o),0);sl.region=anchors.filter(F=>{const v=slotVote(sl,F);return v>0||(v===0&&sl.c>=F.c)}).length}
      free.sort((p,q)=>p.region-q.region||p.score-q.score||p.c-q.c||(p.members[0].item.idx-q.members[0].item.idx));
      const W=[...new Set(free.flatMap(sl=>sl.members.map(s=>s.item)))];
      // Each run of free slots between two anchors is spread g apart, centred where it is, kept a
      // gap from the anchors; with no room it is spread evenly between them.
      const place=(g,shift)=>{
        const out=new Map();
        for(let r=0;r<=anchors.length;r++){
          const R=free.filter(sl=>sl.region===r);if(!R.length)continue;
          const lo=r>0?anchors[r-1].c:-Infinity,hi=r<anchors.length?anchors[r].c:Infinity,m=R.length;
          let step=g,start=R.reduce((a,sl)=>a+sl.c,0)/m-(m-1)/2*g+shift;
          if(isFinite(lo)&&isFinite(hi)&&hi-lo<(m+1)*g){step=(hi-lo)/(m+1);start=lo+step}
          else{if(isFinite(lo))start=Math.max(start,lo+g);if(isFinite(hi))start=Math.min(start,hi-g-(m-1)*g)}
          R.forEach((sl,i)=>out.set(sl,Math.round((start+i*step)*100)/100));
        }
        return out;
      };
      const tries=[[TRACK_GAP,0],[TRACK_GAP,TRACK_GAP/2],[TRACK_GAP,-TRACK_GAP/2],[TRACK_GAP,TRACK_GAP],[TRACK_GAP,-TRACK_GAP],[TRACK_GAP,2*TRACK_GAP],[TRACK_GAP,-2*TRACK_GAP]];
      for(let g=TRACK_GAP-1;g>=2;g--)tries.push([g,0]);
      let moved=false;
      for(const [g,shift] of tries){
        const at=place(g,shift);
        if(attempt(W,()=>{for(const [sl,c] of at)for(const s of sl.members)setLine(s.item.pts,s.k,axis,c)},(b,a)=>a.bad<b.bad-.01)){moved=true;break}
      }
      if(moved)changed=true;else failed.add(sig);
    }
    for(const it of movers)it.pts=normalizePoints(it.pts);
    refresh(movers);
    if(!changed)break;
  }

  for(const it of movers)it.r.points=it.pts;
  for(const axis of ['h','v']){
    const L=allSegs().filter(s=>s.axis===axis).sort((p,q)=>p.c-q.c);
    for(let i=0;i<L.length;i++)for(let j=i+1;j<L.length&&L[j].c-L[i].c<TRACK_GAP;j++){
      if(trackPairCost(L[i],L[j])<=0)continue;
      for(const s of [L[i],L[j]])if(s.kind==='interior')cramped.add(s.item.key);
    }
  }
  return cramped;
}
function terminalPointId(nodeId,id){
  const node=nodes.find(n=>n.id===nodeId);
  return node?(Attachment.pointId(node,id)||String(id??'')):String(id??'');
}
function sameTerminal(n1,s1,n2,s2){
  if(!n1||!n2)return false; // a free end is never the same terminal as anything
  return n1===n2 && terminalPointId(n1,s1)===terminalPointId(n2,s2);
}
function findEquivalentWire(a,aSide,b,bSide){
  return wires.findIndex(w=>
    sameTerminal(w.a,w.aSide,a,aSide) && sameTerminal(w.b,w.bSide,b,bSide)
  );
}
function findReverseWire(a,aSide,b,bSide){
  return wires.findIndex(w=>
    sameTerminal(w.a,w.aSide,b,bSide) && sameTerminal(w.b,w.bSide,a,aSide)
  );
}
function addConnection(a,aSide,b,bSide){
  if(a===b && aSide===bSide)return false;
  const reach=connectionReachability(a,aSide,b,bSide);
  if(!reach.ok){statusEl.textContent=reach.reason;return false}
  if(findEquivalentWire(a,aSide,b,bSide)>=0)return true;

  const reverse=findReverseWire(a,aSide,b,bSide);
  if(reverse>=0){const cfg=connectionConfig(wires[reverse]);cfg.direction='duplex';wires[reverse].duplex=true;ensureDuplexEndpointFlows(wires[reverse]);wires[reverse].canvasId=reach.canvasId;routeCache.delete(reverse);selected=`wire:${reverse}`;statusEl.textContent='Duplex connection';return true}
  const wire=SovSchematicData.makeWire(diagram,{a,b,aSide,bSide});
  wires.push(wire);wireCanvas(wire);
  const id=wires.length-1;routeCache.delete(id);selected=`wire:${id}`;refreshCanvasScopeControl();return true;
}

// A carrier Path from the palette: a Wire with two free ends, laid across the drop point on
// whichever surface is there (an open interior, else the world).
function addCarrier(x,y,mods=null,options={}){
  const step=dragSnapStep(mods||{});
  const cx=step>0?snapCoord(x,step):x,cy=step>0?snapCoord(y,step):y,half=120;
  const host=nodes.filter(c=>componentAcceptsChildren(c)&&!isEntityLocked(c)&&!isEffectivelyHidden(c)&&pointInsideComponent(cx,cy,c,-componentConfig(c).presentation.padding)).sort((p,q)=>{const P=componentSize(p),Q=componentSize(q);return P.w*P.h-Q.w*Q.h})[0];
  const w=SovSchematicData.makeWire(diagram,{aAttachment:{kind:'free',x:cx-half,y:cy},bAttachment:{kind:'free',x:cx+half,y:cy},canvasId:host?componentCanvas(host).id:GLOBAL_CANVAS_ID});
  wires.push(w);wireCanvas(w);connectionConfig(w);
  const i=wires.length-1;routeCache.delete(i);
  if(options.render!==false)render();
  if(options.select!==false)selectWire(i);
  return w;
}
function addNode(symbolId,x=null,y=null,mods=null,options={}){
  const centerX=camera.x+camera.w/2,centerY=camera.y+camera.h/2;
  const px=x==null?centerX+(Math.random()-.5)*90:x,py=y==null?centerY+(Math.random()-.5)*70:y;
  if(SovSchematicData.templatePreset(symbolId)?.carrier)return addCarrier(px,py,x!=null&&y!=null?mods:null,options);
  const n=SovSchematicData.makeComponent(diagram,{symbolId,x:px,y:py,canvasId:GLOBAL_CANVAS_ID});
  ensureEntityCanvas(n,'component');
  if(x!=null&&y!=null){
    const step=dragSnapStep(mods||{});
    if(step>0){n.x=snapCoord(n.x,step);n.y=snapCoord(n.y,step)}
  }
  nodes.push(n);
  if(x!=null&&y!=null)updateContainmentFor(n);
  else syncNodeBoundaryContext(n);
  if(options.render!==false)render();
  if(options.select!==false)selectNode(n.id);
  return n;
}
