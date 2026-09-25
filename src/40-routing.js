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
  let length=0, bends=Math.max(0,pts.length-2), crossings=0, shared=0, hugging=0, tracks=0;
  for(let i=0;i<pts.length-1;i++){
    const P=pts[i], Q=pts[i+1];
    length += segmentLength(P,Q);
    for(const seg of occupied){
      crossings += segmentsCross(P,Q,seg.a,seg.b) ? 1 : 0;
      shared += sharedLength(P,Q,seg.a,seg.b);
      if(ends&&seg.ends&&!seg.ends.some(e=>ends.includes(e))&&onOneTrack(P,Q,seg.a,seg.b))tracks++;
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
    anchor:{x:candidate.anchor.x,y:candidate.anchor.y}
  };
}
function captureDragSnapshots(nodeId){
  dragRouteSnapshots.clear();
  const occupied=[];
  wires.forEach((w,i)=>{
    const A=carrierEndpointPos(w,'a'), B=carrierEndpointPos(w,'b');
    if(!A||!B) return;
    const points=stableRouteForWire(i,w,A,B,occupied);
    occupied.push(...routeSegments(points,w));
    if(w.a===nodeId || w.b===nodeId){
      dragRouteSnapshots.set(i,{
        points:clonePoints(points),
        aPos:{x:A.x,y:A.y},
        bPos:{x:B.x,y:B.y}
      });
    }
  });
}
function settleDraggedRoutes(){
  if(!activeNodeDrag) return;
  const occupied=[];
  wires.forEach((w,i)=>{
    const A=carrierEndpointPos(w,'a'), B=carrierEndpointPos(w,'b');
    if(!A||!B) return;

    if(w.a===activeNodeDrag || w.b===activeNodeDrag){
      const candidate=routePoints(A,B,w.aSide,w.bSide,w.a,w.b,w.lane??i,occupied,w.id);
      routeCache.set(i,routeCacheFromCandidate(candidate));
      dragRouteSnapshots.set(i,{
        points:clonePoints(candidate.points),
        aPos:{x:A.x,y:A.y},
        bPos:{x:B.x,y:B.y}
      });
      occupied.push(...routeSegments(candidate.points,w));
    }else{
      const points=stableRouteForWire(i,w,A,B,occupied);
      occupied.push(...routeSegments(points,w));
    }
  });
  renderWires();
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
  const hostCanvasId=wireId?localCanvasId('wire',wireId):null;
  const otherRects=nodes
    .filter(n=>n.id!==sourceId && n.id!==targetId && n.id!==activeNodeDrag && (!hostCanvasId||(n.canvasId||GLOBAL_CANVAS_ID)!==hostCanvasId) && !ignoreContainerObstacle(n,sourceNode,targetNode))
    .map(n=>rectForNode(n,12));

  // Source and target are included after the outward lead. This prevents a path
  // from exiting one side and visually tunneling through either endpoint card.
  const endpointRects=[];
  if(endpointNeedsOuterObstacle(sourceNode,aSide,routedWire))endpointRects.push(rectForNode(sourceNode,8));
  if(endpointNeedsOuterObstacle(targetNode,bSide,routedWire))endpointRects.push(rectForNode(targetNode,8));
  const obstacles=[...otherRects,...endpointRects];

  const allRects=nodes.filter(n=>n.id!==activeNodeDrag&&(!hostCanvasId||(n.canvasId||GLOBAL_CANVAS_ID)!==hostCanvasId)&&!ignoreContainerObstacle(n,sourceNode,targetNode)).map(n=>rectForNode(n,16));
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
    .filter(points=>pathValid(points,obstacles)&&routeInsideFence(points,fence))
    .map(points=>({
      points,
      score:pathScore(points,SA,SB,obstacles,occupied,ends),
      signature:routeSignature(points),
      anchor:routeAnchor(points)
    }))
    .sort((a,b)=>a.score-b.score);

  let chosen=valid[0]||null;

  if(!chosen){
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
    // Prefer a perimeter that clears every body; only when none does is the cheapest taken.
    chosen=fallback.find(f=>pathValid(f.points,obstacles))||fallback[0];
  }

  return {
    points: normalizePoints([A,SA,...chosen.points.slice(1,-1),SB,B]),
    core: chosen.points,
    score: chosen.score,
    signature: chosen.signature,
    anchor: chosen.anchor,
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
    if(other.id===node.id||componentForm(other).dimension!==2||isDescendantOf(node.id,other.id)||isEffectivelyHidden(other))continue;
    const R=componentBounds(other,10);
    for(let s=2;s<=d;s+=2){const x=P.x+nx*s,y=P.y+ny*s;if(x>R.l&&x<R.r&&y>R.t&&y<R.b){d=Math.max(4,s/2);break}}
  }
  return {x:P.x+nx*d,y:P.y+ny*d};
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
  // A route the layout on screen pins or guides is drawn as declared, not re-derived.
  const spec=typeof activeRouteSpec==='function'?activeRouteSpec(w.id):null;
  if(spec){const declared=routeThroughSpec(A,B,w,spec);if(declared)return declared}
  const candidate=routePoints(A,B,w.aSide,w.bSide,w.a,w.b,w.lane??index,occupied,w.id);
  const cached=routeCache.get(index);

  if(!cached){
    routeCache.set(index,{
      points:candidate.points,
      core:candidate.core,
      score:candidate.score,
      signature:candidate.signature,
      anchor:candidate.anchor
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

    // Cached topology may remain readable while endpoints move. We only throw
    // it away if its interior route now collides with a component.
    const routeOnly=normalizePoints([SA,...inner,SB]);
    const endpointRects=[];
    const otherRects=nodes.filter(n=>n.id!==w.a && n.id!==w.b && n.id!==activeNodeDrag && (n.canvasId||GLOBAL_CANVAS_ID)!==wireCanvas(w).id && !ignoreContainerObstacle(n,sourceNode,targetNode)).map(n=>rectForNode(n,12));
    if(endpointNeedsOuterObstacle(sourceNode,w.aSide,w))endpointRects.push(rectForNode(sourceNode,8));
    if(endpointNeedsOuterObstacle(targetNode,w.bSide,w))endpointRects.push(rectForNode(targetNode,8));
    const obstacles=[...otherRects,...endpointRects];

    if(!pathValid(routeOnly,obstacles)||!routeInsideFence(routeOnly,routeFence(w))) rebuilt=null;
  }

  if(!rebuilt){
    routeCache.set(index,{
      points:candidate.points,core:candidate.core,score:candidate.score,
      signature:candidate.signature,anchor:candidate.anchor
    });
    return candidate.points;
  }

  const SA=sourceNode?routeLead(A,B,w.aSide,sourceNode,wireEndpointInward(w,sourceNode)):A, SB=targetNode?routeLead(B,A,w.bSide,targetNode,wireEndpointInward(w,targetNode)):B;
  const rebuiltCore=normalizePoints([SA,...rebuilt.slice(2,-2),SB]);
  const otherRects=nodes.filter(n=>n.id!==w.a && n.id!==w.b && n.id!==activeNodeDrag && (n.canvasId||GLOBAL_CANVAS_ID)!==wireCanvas(w).id && !ignoreContainerObstacle(n,sourceNode,targetNode)).map(n=>rectForNode(n,12));
  const rebuiltScore=pathScore(rebuiltCore,SA,SB,otherRects,occupied,[`${w.a}:${w.aSide}`,`${w.b}:${w.bSide}`]);
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
      signature:candidate.signature,anchor:candidate.anchor
    });
    return candidate.points;
  }

  routeCache.set(index,{
    ...cached,
    points:rebuilt,
    score:rebuiltScore,
    anchor
  });
  return rebuilt;
}

// Segments a later route must keep clear of, tagged with the wire's two ends: wires that
// share an end (a fan-out, a fan-in) may run together; any others may not run on one track.
function routeSegments(points,w=null){
  const pts=normalizePoints(points), out=[];
  const ends=w?[`${w.a}:${w.aSide}`,`${w.b}:${w.bSide}`]:null;
  for(let i=0;i<pts.length-1;i++) out.push({a:pts[i],b:pts[i+1],ends});
  return out;
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
