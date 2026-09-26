'use strict';
// State view: a state space run's records projected onto the canvas (STATE-SPACE.md; the view
// grammar is VISUAL-LANGUAGE.md). Passive by construction: it replays a trace through the
// engine (src/07-state-space.js) against the open document and reads the records; it has no
// path to a ledger and runs nothing of its own.
//
// At a chosen logical tick, a port's level is the last `logic.level` record for it at or before
// that tick. A wire takes the level at the port it leaves from (high: the signal colour; low:
// ink); a chip at each end shows that port's own level, so a change still in flight shows as
// two ends that differ. Chips show on the hovered or selected component, everywhere at zoom
// >= 100%, and always on sources (a run's registered inputs). A trace whose document hash is
// not the open document's is refused, as the engine refuses its replay; so is a shown run once
// the document changes under it (DOCUMENT_CHANGED), until a run of the new document is shown.
const STATE_CHIP_ZOOM=1;
const stateView={on:false,records:null,through:null,tick:null,ticks:[],refusal:null,options:{},hash:null};
let stateHoverNode=null;

function stateViewReceipt(){
  const s=stateView;
  return {ok:!s.refusal,on:s.on,tick:s.tick,through:s.through,ticks:s.ticks.slice(),...(s.refusal?{refused:s.refusal.code,reason:s.refusal.message}:{})};
}
// {trace, packs, tick?, chips?: 'rule' | 'all', monochrome?}
function showStateView(options={}){
  const doc=snapshotDocument(),o=options||{};
  const out=SovSchematicStateSpace.replay({doc,packs:o.packs,trace:o.trace});
  Object.assign(stateView,{on:true,options:{chips:o.chips==='all'?'all':'rule',monochrome:!!o.monochrome},records:null,refusal:null});
  if(!out.ok){
    Object.assign(stateView,{refusal:{code:out.code,message:out.message},through:null,tick:null,ticks:[]});
    applyStateView();statusEl.textContent=`State · refused ${out.code}`;return stateViewReceipt();
  }
  const ticks=[...new Set(out.records.map(r=>r.time.logical))].sort((a,b)=>a-b);
  const through=o.trace.through;
  Object.assign(stateView,{records:out.records,through,ticks,hash:o.trace.replayKey.documentHash,tick:o.tick==null?through:Math.max(0,Math.min(through??0,Number(o.tick)))});
  applyStateView();statusEl.textContent=`State · tick ${stateView.tick}`;
  return stateViewReceipt();
}
function setStateViewTick(t){
  if(!stateView.on||!stateView.records)return {...stateViewReceipt(),ok:false,refused:'NOT_SHOWING',reason:'no run is shown',next_operation:'view.stateSpace.show({trace, packs})'};
  stateView.tick=Math.max(0,Math.min(stateView.through??0,Number(t)||0));applyStateView();return stateViewReceipt();
}
// The hash the engine keys a run of the open document by (07-state-space.js startRun).
function openDocumentHash(){return SovSchematicData.documentHash(SovSchematicData.normalizeDocument(SovSchematicData.clone(snapshotDocument())))}
function hideStateView(){Object.assign(stateView,{on:false,records:null,refusal:null,ticks:[],tick:null,through:null,hash:null});render();statusEl.textContent='State · off';return stateViewReceipt()}

// Each (entity, port) on channel main: its level at `tick`.
function stateLevels(records,tick){
  const at=new Map();
  for(const r of records){
    if(r.observable!=='logic.level'||r.time.logical>tick||(r.subject.channel||'main')!=='main')continue;
    at.set(`${r.subject.entity}\u0000${r.subject.point}`,r.value);
  }
  return at;
}
function stateColors(){
  const dark=document.documentElement.dataset.appearance==='dark',css=getComputedStyle(document.documentElement);
  return {hi:dark?'#3987e5':'#2a78d6',ink:css.getPropertyValue('--canvas-ink').trim()||(dark?'#E7E8E3':'#42423E'),
    muted:css.getPropertyValue('--canvas-muted').trim()||(dark?'#AEB0AA':'#73736D'),panel:css.getPropertyValue('--canvas-tone').trim()||(dark?'#17191B':'#FEFEFC')};
}
// Runs after every render: wire colours and chips from the records at the chosen tick.
function applyStateView(){
  nodesG.querySelectorAll(':scope > .state-chips').forEach(x=>x.remove());
  if(!stateView.on){delete workspace.dataset.stateView;return}
  if(stateView.records&&openDocumentHash()!==stateView.hash)
    Object.assign(stateView,{records:null,refusal:{code:'DOCUMENT_CHANGED',message:'the document changed after this run was shown; show a run of the document as it is now'}});
  if(!stateView.records){workspace.dataset.stateView='refused';return}
  workspace.dataset.stateView='on';
  const doc=snapshotDocument(),levels=stateLevels(stateView.records,stateView.tick),mono=stateView.options.monochrome;
  const {hi,ink,muted,panel}=stateColors();
  const byId=new Map((doc.components||[]).map(c=>[c.id,c]));
  const portOf=(w,end)=>w[end+'Attachment']?.pointId||w[end+'Side'];
  const levelOf=(entity,port)=>{const v=levels.get(`${entity}\u0000${port}`);return v===undefined?false:v};
  const layer=document.createElementNS('http://www.w3.org/2000/svg','g');layer.setAttribute('class','state-chips');
  const chipped=new Set(),wires=new Map((doc.wires||[]).map(w=>[w.id,w]));
  for(const group of workspace.querySelectorAll('.wire-group[data-wire-id]')){
    const w=wires.get(group.dataset.wireId);if(!w)continue;
    const high=levelOf(w.a,portOf(w,'a'))===true;
    group.querySelectorAll('.wire-packet,animateMotion,animate').forEach(x=>x.remove());
    group.style.setProperty('--wire-ink',mono?(high?ink:muted):(high?hi:ink));group.style.setProperty('--voltage-ink',mono?ink:hi);
    group.dataset.stateLevel=high?'1':'0';
    const path=group.querySelector('path.wire');if(!path)continue;
    path.style.strokeWidth=mono?(high?'3.6px':'1.4px'):(high?'2.9px':'2.3px');
    if(mono&&!high)path.style.strokeDasharray='5 5';
    const glow=group.querySelector('path.wire-voltage');if(glow)glow.style.opacity=(!mono&&high)?'0.18':'0';
    const total=path.getTotalLength();
    for(const [end,at] of [['a',12],['b',total-12]]){
      const entity=w[end],port=portOf(w,end),key=`${entity}.${port}`;
      if(chipped.has(key))continue;chipped.add(key);
      const on=levelOf(entity,port)===true,p=path.getPointAtLength(Math.max(0,Math.min(total,at)));
      const source=byId.get(entity)?.config?.signalMode==='source'&&byId.get(entity)?.symbolId==='point';
      const g=document.createElementNS('http://www.w3.org/2000/svg','g');
      g.setAttribute('class','logic-chip state-chip'+(source?' state-source':''));
      g.dataset.pin=key;g.dataset.node=entity;g.dataset.value=on?'1':'0';
      const r=document.createElementNS('http://www.w3.org/2000/svg','rect');
      const fill=on?(mono?ink:hi):panel;
      r.setAttribute('x',p.x-7);r.setAttribute('y',p.y-7);r.setAttribute('width',14);r.setAttribute('height',14);r.setAttribute('rx',3);
      r.setAttribute('fill',fill);r.setAttribute('stroke',on?fill:ink);r.setAttribute('stroke-width','1.2');
      const t=document.createElementNS('http://www.w3.org/2000/svg','text');
      t.setAttribute('x',p.x);t.setAttribute('y',p.y+3.5);t.setAttribute('text-anchor','middle');t.setAttribute('fill',on?panel:ink);
      t.setAttribute('font-size','9.5');t.setAttribute('font-weight','700');t.setAttribute('font-family','ui-monospace, Menlo, monospace');
      t.textContent=on?'1':'0';
      g.append(r,t);layer.appendChild(g);
    }
  }
  nodesG.appendChild(layer);
  applyStateChipVisibility();
}
function applyStateChipVisibility(zoom=currentZoom()){
  const all=stateView.options.chips==='all'||zoom>=STATE_CHIP_ZOOM;
  for(const chip of nodesG.querySelectorAll('.state-chips .state-chip')){
    const node=chip.dataset.node;
    chip.classList.toggle('shown',all||chip.classList.contains('state-source')||selectedComponentIds.has(node)||stateHoverNode===node);
  }
}
nodesG.addEventListener('pointerover',e=>{
  if(!stateView.on)return;
  const id=e.target.closest?.('.node')?.dataset.id||e.target.closest?.('.state-chip')?.dataset.node||null;
  if(id!==stateHoverNode){stateHoverNode=id;applyStateChipVisibility()}
});
nodesG.addEventListener('pointerleave',()=>{if(stateHoverNode!==null){stateHoverNode=null;applyStateChipVisibility()}});
