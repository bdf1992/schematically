'use strict';
// 0.1 Beta concern: the Form spine — dimension, boundary composition, and Mode.
//
// Field · Form · Model · Mode
//   Field  the space an entity sits in            (canvasId, canvas.dimension)
//   Form   its dimensional structure, 0D..3D      (this module, form.dimension)
//   Model  what it is and does                    (boundary.inside.type, symbolId, signalMode)
//   Mode   how this instance is configured here   (this module: self/endpoint/boundary/...)
//
// One relation carries the whole Form layer: the boundary of a dimension-N element is an
// ordered set of dimension-(N-1) elements, recursively, bottoming out at 0D. A path's
// endpoints, a plane's edges, a plane's boundary points and a volume's faces are all that
// same relation at different depths — not four enumerated subsystems. Adding a dimension
// adds one row to BOUNDARY; it does not add a new kind of thing.
//
// This module is intentionally pure: no DOM, routing, rendering, or editor state.
(function(root,factory){
  const api=factory();
  root.SovSchematicForm=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  const DIMENSIONS=[0,1,2,3];
  // Body kind is the name a Form of each dimension goes by. Index is the dimension.
  const BODY_KINDS=['point','path','surface','volume'];
  // The only enumerated data in the Form layer: how a dimension-N element is cut into the
  // dimension-(N-1) elements that bound it. `at` is where a 0D point sits on that element
  // when the boundary is projected down to attachment points — for 1D the bounding elements
  // are already 0D and `at` is their position along the parent (the two ends); for 2D the
  // bounding elements are 1D edges and `at` is the midpoint of each edge.
  const BOUNDARY={
    0:[],
    1:[
      {id:'start',side:'left',at:0},
      {id:'end',side:'right',at:1}
    ],
    2:[
      {id:'left',side:'left',at:.5},
      {id:'right',side:'right',at:.5},
      {id:'top',side:'top',at:.5},
      {id:'bottom',side:'bottom',at:.5}
    ],
    3:[
      {id:'front',side:'front',at:.5},
      {id:'back',side:'back',at:.5},
      {id:'left',side:'left',at:.5},
      {id:'right',side:'right',at:.5},
      {id:'top',side:'top',at:.5},
      {id:'bottom',side:'bottom',at:.5}
    ]
  };
  // Mode is the configuration axis: one Form, many roles. A 0D Point is the same Form
  // whether it stands alone (`self`), terminates a Path (`endpoint`), sits on a Plane's
  // boundary (`boundary`) or carries a signal across a host surface (`port`). Mode never
  // changes what a thing is, only how it is being used where it is.
  const MODES=['self','endpoint','boundary','carrier','port','face','edge'];
  // The Mode a bounding element takes, read from the dimension it bounds. The endpoint of a
  // Path and the edge of a Plane are the same relation; only the host dimension differs.
  const BOUNDARY_MODE={1:'endpoint',2:'edge',3:'face'};

  function isDimension(d){return DIMENSIONS.includes(Number(d))}
  function dimension(value,fallback=2){const d=Number(value);return isDimension(d)?d:fallback}
  function bodyKind(d){return BODY_KINDS[dimension(d)]||'surface'}
  function dimensionOfBodyKind(kind){const i=BODY_KINDS.indexOf(String(kind));return i<0?null:i}
  function isMode(mode){return MODES.includes(String(mode))}
  // A dimension-N element is bounded by dimension-(N-1) elements; 0D has no boundary.
  function boundaryDimension(d){const n=dimension(d);return n<=0?null:n-1}

  // The ordered elements that bound a Form of this dimension. Each is itself a Form, one
  // dimension down, carrying the Mode its host dimension gives it.
  function boundary(d){
    const n=dimension(d),below=boundaryDimension(n);
    if(below===null)return [];
    return (BOUNDARY[n]||[]).map(el=>({
      ...el,
      dimension:below,
      bodyKind:bodyKind(below),
      mode:BOUNDARY_MODE[n]||'boundary',
      hostDimension:n
    }));
  }

  // The full descent from a dimension down to 0D: 3 → faces → edges → points. Used to
  // answer "what is this made of" without any dimension knowing about any other.
  function boundaryChain(d){
    const out=[];let n=dimension(d);
    while(n>0){out.push({dimension:n,bodyKind:bodyKind(n),elements:boundary(n)});n-=1}
    return out;
  }

  // Resolve a path of boundary ids against a dimension: elementAt(2,['left']) is the 1D left
  // edge of a surface; elementAt(2,['left','start']) is the 0D corner where that edge starts.
  function elementAt(d,path=[]){
    let current={dimension:dimension(d),bodyKind:bodyKind(d),mode:'self',id:null,at:.5,side:null,hostDimension:null};
    for(const step of Array.isArray(path)?path:[path]){
      const next=boundary(current.dimension).find(el=>el.id===String(step));
      if(!next)return null;
      current=next;
    }
    return current;
  }

  // The 0D projection of a Form: every default attachment point, derived from the boundary
  // relation rather than listed per dimension. A 0D Form has no boundary, so it samples
  // itself — a Point in `self` Mode is its own attachment point. Every other dimension
  // samples each bounding element at `at`.
  //
  // `sides` optionally restricts which bounding elements are exposed by default; a Form may
  // expose fewer points than it has bounding elements without that being a claim about its
  // geometry (2D exposes left/right/top as a template default while bottom stays available).
  function terminalPoints(d,{sides=null}={}){
    const n=dimension(d);
    if(n===0)return [{id:'self',side:'point',mode:'self',role:'self',t:.5,dimension:0,hostDimension:0}];
    const elements=boundary(n).filter(el=>!sides||sides.includes(el.id));
    return elements.map(el=>({
      id:el.id,
      side:el.side,
      // A point projected off a bounding element is 0D whatever it bounds.
      dimension:0,
      // Mode of the *point*: it terminates a Path, or sits on a Plane's boundary.
      mode:n===1?'endpoint':'boundary',
      role:n===1?'endpoint':'boundary',
      t:el.at,
      // Mode and dimension of the element it was projected from — the Path's edge itself.
      via:{id:el.id,dimension:el.dimension,bodyKind:el.bodyKind,mode:el.mode},
      hostDimension:n
    }));
  }

  // ---- 1D geometry -------------------------------------------------------------------
  // A 1D Form's geometry IS its two 0D boundary points. Length and direction are read off
  // them, never stored beside them, so moving a point cannot disagree with the Form and
  // nothing can "reset" a direction that was never held anywhere else.
  //
  // Points are local offsets from the entity's centre and are kept antipodal, so the centre
  // the rest of the editor translates by stays the midpoint of the path.
  const DEFAULT_PATH_LENGTH=112;
  function finite(value,fallback=0){const n=Number(value);return Number.isFinite(n)?n:fallback}
  function pathPoints(length=DEFAULT_PATH_LENGTH,angle=0){
    const half=Math.max(1,finite(length,DEFAULT_PATH_LENGTH))/2,r=finite(angle)*Math.PI/180;
    const dx=Math.cos(r)*half,dy=Math.sin(r)*half;
    return [{x:-dx,y:-dy},{x:dx,y:dy}];
  }
  // Read a 1D Form's length and direction back off its points. `angle` is the true heading in
  // [-180,180]; `axis` folds it to [-90,90] for anything that wants the line's tilt without
  // its sense, such as keeping a label upright.
  function pathGeometry(points){
    const list=Array.isArray(points)?points:[];
    const a=list[0]||{x:-DEFAULT_PATH_LENGTH/2,y:0},b=list[1]||{x:DEFAULT_PATH_LENGTH/2,y:0};
    const ax=finite(a.x),ay=finite(a.y),bx=finite(b.x),by=finite(b.y);
    const dx=bx-ax,dy=by-ay,length=Math.hypot(dx,dy);
    let angle=length>1e-6?Math.atan2(dy,dx)*180/Math.PI:0,axis=angle;
    while(axis>90)axis-=180;while(axis<-90)axis+=180;
    return {
      start:{x:ax,y:ay},end:{x:bx,y:by},
      length:Math.max(1,length),angle,axis,
      midpoint:{x:(ax+bx)/2,y:(ay+by)/2}
    };
  }
  // Force the pair antipodal about the origin without changing what it draws: the residual
  // midpoint comes back as a world-space nudge the caller folds into the entity's centre.
  function centrePathPoints(points){
    const g=pathGeometry(points),mid=g.midpoint;
    return {points:[{x:g.start.x-mid.x,y:g.start.y-mid.y},{x:g.end.x-mid.x,y:g.end.y-mid.y}],offset:mid};
  }

  return {
    DIMENSIONS,BODY_KINDS,MODES,DEFAULT_PATH_LENGTH,
    isDimension,dimension,bodyKind,dimensionOfBodyKind,isMode,
    boundaryDimension,boundary,boundaryChain,elementAt,terminalPoints,
    pathPoints,pathGeometry,centrePathPoints
  };
});
