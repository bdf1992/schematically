'use strict';
// Live logic state on the canvas (VISUAL-LANGUAGE.md: signal state, pin chips).
// While live, the open document runs as a circuit through the shared logic core
// (src/07-logic-core.js, equal to scripts/logic_sov.py) and every render draws its state:
// a high wire in the signal colour, a low one in ink, and a chip at each pin with its value.
// Chips show on the hovered or selected component, and everywhere at zoom >= 100%; an
// input's chip always shows and is its switch (click to flip a bit input).
// The circuit keeps its state (flip-flops, latches) between changes of inputs; it is rebuilt,
// and the current inputs applied again, only when the document's logic changes.
const LOGIC_CHIP_ZOOM=1;
const logicPack=SovSchematicLogic.loadPack(globalThis.SovSchematicLogicPack);
const logicComposites=new Map();   // name -> document, for {"composite": name}
const logicLive={on:false,vector:{},circuit:null,key:null,refusal:null,rebuilt:0,last:null};
let logicHoverNode=null;

function logicResolve(name){const document=logicComposites.get(String(name).split(/[\\/]/).pop());return document?{key:name,document}:null}
function logicOptions(){return {pack:logicPack,resolve:logicResolve,key:currentFileName||'document.sov'}}
// What the circuit depends on, and nothing it does not (positions, labels, styles).
function logicKey(doc){
  return JSON.stringify([(doc.components||[]).map(c=>[c.id,c.symbolId,c.config?.logic||null,(c.config?.attachmentPoints||[]).map(p=>p?.id)]),
    (doc.wires||[]).map(w=>[w.id,w.a,w.aSide,w.b,w.bSide]),[...logicComposites.keys()]]);
}
function logicReceipt(extra={}){
  const c=logicLive.circuit;
  const state={ok:!logicLive.refusal,live:logicLive.on,vector:{...logicLive.vector},rebuilt:logicLive.rebuilt};
  if(logicLive.refusal)return {...state,...logicLive.refusal,...extra};
  if(c){state.inputs=[...c.inputs.keys()].sort();state.outputs=Object.fromEntries([...c.outputs.keys()].sort().map(n=>[n,c.value[c.netOf.get(c.outputs.get(n))]]));
    state.wires=c.wireState(snapshotDocument());state.time=c.time}
  return {...state,...(logicLive.last?{last:logicLive.last}:{}),...extra};
}
// Build (or keep) the circuit for the document as it is now; false when refused.
function logicEnsureCircuit(){
  const doc=snapshotDocument(),key=logicKey(doc);
  if(logicLive.circuit&&logicLive.key===key)return true;
  logicLive.key=key;logicLive.circuit=null;logicLive.refusal=null;
  try{
    if(!SovSchematicLogic.isLogicDocument(doc))throw new SovSchematicLogic.LogicRefusal('NOT_LOGIC','the document declares no config.logic on any component','open a logic document, e.g. examples/logic/half-adder.sov');
    const c=new SovSchematicLogic.Circuit(doc,logicOptions());
    // Inputs the vector does not name start at 0 and are named in it from here on, so the
    // state shown always says what every input is.
    for(const name of c.inputs.keys())if(!(name in logicLive.vector))logicLive.vector[name]=0;
    for(const name of Object.keys(logicLive.vector))if(!c.inputs.has(name))delete logicLive.vector[name];
    logicLive.last=c.apply({...logicLive.vector});
    logicLive.circuit=c;logicLive.rebuilt+=1;
    return true;
  }catch(e){
    if(!(e instanceof SovSchematicLogic.LogicRefusal))throw e;
    logicLive.refusal=e.asDict();return false;
  }
}
function logicLiveStep(vector,clock=null){
  if(!logicLive.on)return {ok:false,refused:'NOT_LIVE',reason:'live logic state is off',next_operation:'logic.live.start()'};
  if(!logicEnsureCircuit())return logicReceipt();
  try{
    logicLive.last=clock?logicLive.circuit.pulse(clock,vector):logicLive.circuit.apply(vector);
    Object.assign(logicLive.vector,vector);
  }catch(e){
    if(!(e instanceof SovSchematicLogic.LogicRefusal))throw e;
    applyLogicLive();return {...logicReceipt(),ok:false,...e.asDict()};
  }
  applyLogicLive();
  return logicReceipt();
}
function startLogicLive(vector={}){
  logicLive.on=true;logicLive.circuit=null;logicLive.key=null;logicLive.vector={...vector};logicLive.last=null;
  logicEnsureCircuit();applyLogicLive();
  statusEl.textContent=logicLive.refusal?`Logic · refused ${logicLive.refusal.refused}`:'Logic · live';
  return logicReceipt();
}
function stopLogicLive(){logicLive.on=false;logicLive.circuit=null;logicLive.key=null;logicLive.refusal=null;render();statusEl.textContent='Logic · off';return logicReceipt()}

function logicColors(){
  const dark=document.documentElement.dataset.appearance==='dark',css=getComputedStyle(document.documentElement);
  return {hi:dark?'#3987e5':'#2a78d6',ink:css.getPropertyValue('--canvas-ink').trim()||(dark?'#E7E8E3':'#42423E'),
    panel:css.getPropertyValue('--canvas-tone').trim()||(dark?'#17191B':'#FEFEFC')};
}
const chipText=v=>Number.isInteger(v)?String(v):v.toFixed(2);
// Runs after every render: wire colours and chips from the circuit's current values.
function applyLogicLive(){
  nodesG.querySelectorAll(':scope > .logic-chips').forEach(x=>x.remove());
  if(!logicLive.on)return;
  if(!logicEnsureCircuit()){workspace.dataset.logicLive='refused';return}
  workspace.dataset.logicLive='on';
  const c=logicLive.circuit,{hi,ink,panel}=logicColors(),doc=snapshotDocument(),state=c.wireState(doc);
  const inputs=new Map((doc.components||[]).filter(x=>x.config?.logic?.kind==='input').map(x=>[x.id,x.config.logic]));
  const layer=document.createElementNS('http://www.w3.org/2000/svg','g');layer.setAttribute('class','logic-chips');
  const chipped=new Set();
  for(const group of workspace.querySelectorAll('.wire-group[data-wire-id]')){
    const st=state[group.dataset.wireId];if(!st)continue;
    const high=st.value===1||(!Number.isInteger(st.value)&&st.value>0);
    group.querySelectorAll('.wire-packet,animateMotion,animate').forEach(x=>x.remove());
    group.style.setProperty('--wire-ink',high?hi:ink);group.style.setProperty('--voltage-ink',hi);
    group.dataset.logicValue=String(st.value);
    const wire=group.querySelector('path.wire');if(!wire)continue;
    wire.style.strokeWidth=high?'2.9px':'2.3px';
    const glow=group.querySelector('path.wire-voltage');if(glow)glow.style.opacity=high?'0.18':'0';
    const total=wire.getTotalLength();
    for(const [pin,at] of [[st.a,12],[st.b,total-12]]){
      if(chipped.has(pin))continue;chipped.add(pin);
      const node=pin.slice(0,pin.lastIndexOf('.')),p=wire.getPointAtLength(Math.max(0,Math.min(total,at))),text=chipText(st.value);
      const w=Math.max(14,6+text.length*6.2),input=inputs.get(node),toggle=!!input&&input.type!=='level';
      const g=document.createElementNS('http://www.w3.org/2000/svg','g');
      g.setAttribute('class','logic-chip'+(input?' logic-input':'')+(toggle?' logic-toggle':''));
      g.dataset.pin=pin;g.dataset.node=node;g.dataset.value=String(st.value);
      if(toggle){g.dataset.input=input.name;g.setAttribute('role','button');g.setAttribute('aria-label',`Input ${input.name} is ${text}; flip it`)}
      const r=document.createElementNS('http://www.w3.org/2000/svg','rect');
      r.setAttribute('x',p.x-w/2);r.setAttribute('y',p.y-7);r.setAttribute('width',w);r.setAttribute('height',14);r.setAttribute('rx',3);
      r.setAttribute('fill',high?hi:panel);r.setAttribute('stroke',high?hi:ink);r.setAttribute('stroke-width','1.2');
      const t=document.createElementNS('http://www.w3.org/2000/svg','text');
      t.setAttribute('x',p.x);t.setAttribute('y',p.y+3.5);t.setAttribute('text-anchor','middle');t.setAttribute('fill',high?panel:ink);t.textContent=text;
      g.append(r,t);layer.appendChild(g);
    }
  }
  nodesG.appendChild(layer);
  applyLogicChipVisibility();
}
// A chip shows when its component is hovered or selected, at zoom >= 100%, or when it is an input.
function applyLogicChipVisibility(zoom=currentZoom()){
  const all=zoom>=LOGIC_CHIP_ZOOM;
  for(const chip of nodesG.querySelectorAll('.logic-chips .logic-chip')){
    const node=chip.dataset.node;
    chip.classList.toggle('shown',all||chip.classList.contains('logic-input')||selectedComponentIds.has(node)||logicHoverNode===node);
  }
}
nodesG.addEventListener('pointerover',e=>{
  if(!logicLive.on)return;
  const id=e.target.closest?.('.node')?.dataset.id||e.target.closest?.('.logic-chip')?.dataset.node||null;
  if(id!==logicHoverNode){logicHoverNode=id;applyLogicChipVisibility()}
});
nodesG.addEventListener('pointerleave',()=>{if(logicHoverNode!==null){logicHoverNode=null;applyLogicChipVisibility()}});
// An input's chip is its switch. (The canvas ignores a press on a chip, so a flip neither
// moves nor selects; tests/logic_live_qa.py holds that.)
nodesG.addEventListener('click',e=>{
  const chip=e.target.closest?.('.logic-toggle');if(!chip||!logicLive.on)return;
  e.stopPropagation();const name=chip.dataset.input;
  const r=logicLiveStep({[name]:logicLive.vector[name]===1?0:1});
  statusEl.textContent=r.ok?`Logic · ${name} = ${logicLive.vector[name]}`:`Logic · refused ${r.refused}`;
},true);
