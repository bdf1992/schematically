'use strict';
// 0.1 concern: the wave view. Draws the run's spectra along wires: a faint travelling wave under
// each wire whose source varies. It reads the run (simClock.run.spectrum and its time), the routes
// renderWires drew last (drawnRoutePoints) and the camera, and writes only the children of
// #waveLayer; it writes neither the document nor the run, and changes nothing in the wires layer.
//
// The setting, waveStyle, is the view's: off (the default), string, dots or lanes. A workspace
// carries it (src/75-persistence.js); a document never does.
//
// What a wire shows comes from sim.spectrum alone. A wire's source is its a end. Per source the
// surface is read once to learn the node's period P (a one-step window; the period is the run's
// and does not change), and then once per completed period: fromMs (k - 1) * P, toMs k * P,
// k = floor(T / P), stepMs 50, harmonics 6. No transform and no level history is computed here.
// The signal is the source's own, delayed by distance over speed (a lossless line, one speed for
// the canvas): a mark at arc length s shows u(T - 1000 * s / 120).
//
// Geometry is the wave studies' (control/sketchbooks, wave-curves, wave-loops, wave-energy): the
// guide is the drawn route with every corner rounded by an arc of radius 16, capped at half of each
// adjacent leg; displacement is along the guide's normal and eases to 0 at both ends with zero
// slope. A parallel curve has no cusp while its offset stays below the local radius, so the swing
// is held under half the smallest corner radius on the wire, and the lanes' ribbon under 0.9 of it.
// Drawing is a pure function of run time, routes, zoom and the kept spectra.

const WAVE_STYLES=['off','string','dots','lanes'];
const WAVE_LOOK={
  radius:16,swingPx:4,speed:120,stationStep:2,easeFloor:14,easeSwings:6,
  dotRadiusPx:.75,dotGapPx:3.2,
  lane:{gapPx:3,ribbonPx:9,minBandPx:1.6,spreadPx:40,swingFrac:.8,minShare:.02,most:3,sideProbe:14,widthBase:.5,widthShare:.8,alphaBase:.22,alphaShare:.63,radiusShare:.9},
  spectrum:{stepMs:50,harmonics:6,peakSamples:64,flat:1e-6}
};
const waveView={style:'off',run:null,kept:new Map(),watching:false};

function waveStyle(){return waveView.style}
function setWaveStyle(name){
  if(!WAVE_STYLES.includes(name))return {ok:false,code:'WAVE_STYLE_UNKNOWN',message:`Unknown wave style ${String(name)}; one of ${WAVE_STYLES.join(', ')}`,allowed:[...WAVE_STYLES]};
  waveView.style=name;paintSim();
  return {ok:true,waveStyle:waveView.style};
}
// A workspace's view: the key missing, or holding anything but the four values, gives off.
function waveStyleFromView(view){waveView.style=WAVE_STYLES.includes(view?.waveStyle)?view.waveStyle:'off';return waveView.style}

const waveClamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const waveSmooth=u=>{u=waveClamp(u,0,1);return u*u*(3-2*u)};
function waveEl(tag,cls,wireId,attrs){
  const e=document.createElementNS('http://www.w3.org/2000/svg',tag);e.setAttribute('class',cls);e.setAttribute('data-wire-id',wireId);
  for(const k in attrs)e.setAttribute(k,String(attrs[k]));
  return e;
}
// Screen px per world unit, as the editor's own label scale measures it (syncLabelScale).
function waveZoom(){const m=workspace.getScreenCTM(),k=m?Math.hypot(m.a,m.b):1;return k>0?k:1}

// ---- the signal: one source's harmonics, kept until its next period completes ----------------
function waveRaw(harmonics,P,t){let y=0;const w=2*Math.PI/P;for(const h of harmonics)y+=h.amplitude*Math.cos(h.n*w*t+h.phase);return y}
function waveSignal(run,id,T){
  if(waveView.run!==run){waveView.run=run;waveView.kept=new Map()}
  const S=WAVE_LOOK.spectrum;let row=waveView.kept.get(id);
  if(!row){
    if(T<S.stepMs)return null;
    const probe=run.spectrum({fromMs:0,toMs:S.stepMs,stepMs:S.stepMs,harmonics:0,nodes:[id]});
    row={periodMs:probe.ok?(probe.nodes[0]?.periodMs??null):null,k:0,signal:null};
    waveView.kept.set(id,row);
  }
  const P=row.periodMs;if(!(P>0))return null;
  const k=Math.floor(T/P);if(k<1)return null;
  if(row.k!==k){
    row.k=k;row.signal=null;
    const read=run.spectrum({fromMs:(k-1)*P,toMs:k*P,stepMs:S.stepMs,harmonics:S.harmonics,nodes:[id]});
    const node=read.ok?read.nodes[0]:null;
    if(node&&Array.isArray(node.harmonics)){
      const harmonics=node.harmonics.map(h=>({n:h.n,amplitude:h.amplitude,phase:h.phase}));
      let peak=0;for(let j=0;j<S.peakSamples;j++)peak=Math.max(peak,Math.abs(waveRaw(harmonics,P,j*P/S.peakSamples)));
      if(peak>=S.flat)row.signal={P,harmonics,peak,energy:node.energy};
    }
  }
  return row.signal;
}
// u(t): the rebuilt signal over its largest value at 64 evenly spaced times in one period. Between
// those times a sum of harmonics can pass that value, so u is held to -1..1 and the swing to its cap.
function waveU(signal,t){return waveClamp(waveRaw(signal.harmonics,signal.P,t)/signal.peak,-1,1)}

// ---- the guide: the drawn route with rounded corners, by arc length from the a end -----------
function waveGuide(points){
  const pts=[];
  for(const p of points||[]){const z=pts[pts.length-1];if(!z||Math.hypot(p.x-z.x,p.y-z.y)>.01)pts.push({x:p.x,y:p.y})}
  for(let i=pts.length-2;i>=1;i--){
    const a=pts[i-1],b=pts[i],c=pts[i+1],la=Math.hypot(b.x-a.x,b.y-a.y),lc=Math.hypot(c.x-b.x,c.y-b.y);
    const cross=((b.x-a.x)*(c.y-b.y)-(b.y-a.y)*(c.x-b.x))/(la*lc),dot=(b.x-a.x)*(c.x-b.x)+(b.y-a.y)*(c.y-b.y);
    if(Math.abs(cross)<1e-6&&dot>0)pts.splice(i,1);
  }
  const n=pts.length;if(n<2)return null;
  const legs=[];
  for(let i=0;i<n-1;i++){const dx=pts[i+1].x-pts[i].x,dy=pts[i+1].y-pts[i].y,len=Math.hypot(dx,dy);legs.push({len,ux:dx/len,uy:dy/len,head:0,tail:0})}
  const arcs=new Array(n);let rmin=Infinity;
  for(let i=1;i<n-1;i++){
    const g=legs[i-1],h=legs[i],th=Math.acos(waveClamp(g.ux*h.ux+g.uy*h.uy,-1,1));
    if(th<1e-3||th>Math.PI-1e-3)continue;
    const tn=Math.tan(th/2),tl=Math.min(WAVE_LOOK.radius*tn,.5*g.len,.5*h.len),r=tl/tn;
    if(!(r>1e-6))continue;
    rmin=Math.min(rmin,r);g.tail=tl;h.head=tl;
    const side=Math.sign(g.ux*h.uy-g.uy*h.ux),ax=pts[i].x-g.ux*tl,ay=pts[i].y-g.uy*tl,cx=ax-g.uy*side*r,cy=ay+g.ux*side*r;
    arcs[i]={arc:true,cx,cy,r,a0:Math.atan2(ay-cy,ax-cx),dth:side*th,len:r*th};
  }
  const segs=[];let L=0;
  for(let i=0;i<n-1;i++){
    const g=legs[i],len=g.len-g.head-g.tail;
    if(len>1e-9){segs.push({arc:false,x:pts[i].x+g.ux*g.head,y:pts[i].y+g.uy*g.head,ux:g.ux,uy:g.uy,len,s0:L});L+=len}
    if(arcs[i+1]){arcs[i+1].s0=L;segs.push(arcs[i+1]);L+=arcs[i+1].len}
  }
  if(!segs.length||!(L>0))return null;
  let cursor=0;
  // The point at arc length s and the unit normal there (the tangent turned a quarter turn).
  const at=s=>{
    s=waveClamp(s,0,L);if(s<segs[cursor].s0)cursor=0;
    while(cursor<segs.length-1&&s>segs[cursor].s0+segs[cursor].len)cursor++;
    const g=segs[cursor],d=s-g.s0;
    if(!g.arc)return {x:g.x+g.ux*d,y:g.y+g.uy*d,nx:-g.uy,ny:g.ux};
    const an=g.a0+g.dth*(d/g.len),sg=Math.sign(g.dth),co=Math.cos(an),si=Math.sin(an);
    return {x:g.cx+g.r*co,y:g.cy+g.r*si,nx:-co*sg,ny:-si*sg};
  };
  return {L,rmin,at,first:pts[0],last:pts[n-1]};
}
function waveStations(L,step){const out=[];for(let s=0;s<L;s+=step)out.push(s);out.push(L);return out}

// ---- the three styles ---------------------------------------------------------------------------
// string and dots share one displacement: swing * envelope(s) * u(T - 1000 s / speed).
function waveDisplacement(guide,signal,T,k){
  const A=Math.min(WAVE_LOOK.swingPx/k,guide.rmin/2),W=Math.max(WAVE_LOOK.easeFloor,WAVE_LOOK.easeSwings*A),v=WAVE_LOOK.speed/1000;
  return s=>A*waveSmooth(Math.min(s,guide.L-s)/W)*waveU(signal,T-s/v);
}
function waveString(layer,wire,guide,signal,T,k){
  const y=waveDisplacement(guide,signal,T,k);let d='';
  for(const s of waveStations(guide.L,WAVE_LOOK.stationStep)){const p=guide.at(s),o=y(s);d+=(d?' L':'M')+(p.x+p.nx*o).toFixed(2)+' '+(p.y+p.ny*o).toFixed(2)}
  layer.appendChild(waveEl('path','wave-string',wire.id,{d}));
}
// Dots stay at fixed arc length and move only across the wire, as the medium does in a transverse wave.
function waveDots(layer,wire,guide,signal,T,k){
  const y=waveDisplacement(guide,signal,T,k),gap=WAVE_LOOK.dotGapPx/k,r=(WAVE_LOOK.dotRadiusPx/k).toFixed(3),count=Math.floor(guide.L/gap),off=(guide.L-count*gap)/2;
  for(let i=0;i<=count;i++){const s=off+i*gap,p=guide.at(s),o=y(s);layer.appendChild(waveEl('circle','wave-dot',wire.id,{cx:(p.x+p.nx*o).toFixed(2),cy:(p.y+p.ny*o).toFixed(2),r}))}
}
// Which side of the wire the lanes go: the side with more room from the cards around the middle.
function waveLaneSide(guide,cards){
  let best=null;
  for(const sg of [1,-1]){
    let room=1e9;
    for(const f of [.35,.5,.65]){
      const p=guide.at(guide.L*f),qx=p.x+p.nx*WAVE_LOOK.lane.sideProbe*sg,qy=p.y+p.ny*WAVE_LOOK.lane.sideProbe*sg;
      for(const c of cards)room=Math.min(room,Math.hypot(Math.max(0,Math.abs(qx-c.x)-c.w/2),Math.max(0,Math.abs(qy-c.y)-c.h/2)));
    }
    if(!best||room>best.room+1e-6)best={sg,room};
  }
  return best.sg;
}
// One lane per harmonic holding at least 2% of the source's energy, the three largest at most.
function waveLanes(layer,wire,guide,signal,T,k,cards){
  const Lk=WAVE_LOOK.lane;
  const picked=signal.harmonics.map(h=>({...h,share:signal.energy>0?h.amplitude*h.amplitude/2/signal.energy:0})).filter(h=>h.share>=Lk.minShare).sort((a,b)=>b.share-a.share||a.n-b.n).slice(0,Lk.most);
  if(!picked.length)return;
  const raw=picked.map(h=>Math.max(Lk.minBandPx,h.share*Lk.ribbonPx)),total=raw.reduce((a,b)=>a+b,0),bands=raw.map(b=>b*Math.min(1,Lk.ribbonPx/total)/k);
  const outer=Lk.gapPx/k+bands.reduce((a,b)=>a+b,0),fit=Math.min(1,Lk.radiusShare*guide.rmin/outer),side=waveLaneSide(guide,cards),spread=Lk.spreadPx/k,v=WAVE_LOOK.speed/1000,w=2*Math.PI/signal.P;
  const stations=waveStations(guide.L,WAVE_LOOK.stationStep);let near=Lk.gapPx/k;
  picked.forEach((h,i)=>{
    const centre=near+bands[i]/2,swing=Lk.swingFrac*bands[i]/2;near+=bands[i];let d='';
    for(const s of stations){
      const p=guide.at(s),o=side*fit*waveSmooth(Math.min(s,guide.L-s)/spread)*(centre+swing*Math.cos(h.n*w*(T-s/v)+h.phase));
      d+=(d?' L':'M')+(p.x+p.nx*o).toFixed(2)+' '+(p.y+p.ny*o).toFixed(2);
    }
    const share=Math.min(1,h.share);
    layer.appendChild(waveEl('path','wave-lane',wire.id,{d,'data-harmonic':h.n,style:`stroke-width:${(Lk.widthBase+Lk.widthShare*share).toFixed(3)}px;opacity:${(Lk.alphaBase+Lk.alphaShare*share).toFixed(3)}`}));
  });
}

// Repaint the wave layer. paintSim calls this on every paint, with or without a run.
function paintWaves(){
  const layer=document.getElementById('waveLayer');if(!layer)return;
  // The render puts its group layer before the wires at run time; the waves stay directly under the wires.
  const over=document.getElementById('wires');if(over&&layer.nextElementSibling!==over)over.before(layer);
  layer.replaceChildren();
  const run=simClock.run;
  if(!run){waveView.run=null;waveView.kept=new Map();return}
  if(waveView.style==='off')return;
  // A zoom changes the screen sizes the marks are cut to; the layer follows the camera too.
  if(!waveView.watching&&typeof MutationObserver==='function'){waveView.watching=true;new MutationObserver(()=>paintWaves()).observe(workspace,{attributes:true,attributeFilter:['viewBox']})}
  const T=run.state().time,k=waveZoom(),draw=waveView.style==='string'?waveString:waveView.style==='dots'?waveDots:waveLanes;
  // The cards' boxes, measured once a paint: the lanes pick the side of a wire with more room from them.
  const cards=waveView.style==='lanes'?nodes.map(c=>{const z=componentSize(c);return {x:c.x,y:c.y,w:z.w,h:z.h}}):null;
  wires.forEach((wire,i)=>{
    const points=drawnRoutePoints.get(i);if(!points||!wire.a)return;
    const signal=waveSignal(run,wire.a,T);if(!signal)return;
    const guide=waveGuide(points);if(!guide)return;
    draw(layer,wire,guide,signal,T,k,cards);
  });
}
