'use strict';
// 0.1 concern: the canvas control plane. One clock drives the graph engine
// (src/07-graph-core.js) over the live document; this module only projects its state onto the
// canvas (levels, edges, waiting steps) and turns gestures into engine operations. It never
// writes the document: a simulation reads a snapshot and restarts when the document changes.

const simLayer=document.getElementById('simLayer');
const simClock={run:null,playing:false,speed:1,frame:null,last:0,edgeMark:0,fingerprint:null,note:'',stubbed:[]};

// Handlers a document names come from its saved scenarios; any other name is stubbed, and
// the transport says so, so a run in the editor never silently claims a real handler ran.
function simHandlersFor(doc){
  const handlers={};
  for(const r of doc.references||[])if(r.kind==='scenario'&&r.data?.handlers)Object.assign(handlers,r.data.handlers);
  const stubbed=[];
  for(const c of doc.components||[])for(const name of [c.config?.behavior?.handler,c.config?.flow?.handler])if(name&&!handlers[name]){handlers[name]={kind:'stub'};stubbed.push(name)}
  return {handlers,stubbed:[...new Set(stubbed)]};
}
function simStart(){
  const doc=snapshotDocument(),{handlers,stubbed}=simHandlersFor(doc);
  const made=SovSchematicGraph.createSimulation(doc,{handlers});
  simClock.fingerprint=semanticFingerprint();simClock.edgeMark=0;simClock.stubbed=stubbed;
  if(!made.ok){simClock.run=null;simClock.note=made.message;simPause();paintSim();updateSimReadout();return made}
  simClock.run=made.sim;simClock.note=stubbed.length?`stubbed: ${stubbed.join(', ')}`:'';
  simClock.run.run({until:0});paintSim();updateSimReadout();
  return {ok:true};
}
function simEnsure(){
  // The document is the authority: an edit restarts the clock from time 0.
  if(!simClock.run||simClock.fingerprint!==semanticFingerprint()){const r=simStart();if(simClock.run&&simClock.fingerprint)simClock.note=simClock.note||'';return r.ok!==false}
  return true;
}
function simFrame(now){
  if(!simClock.playing)return;
  if(simClock.fingerprint!==semanticFingerprint()){simStart();simClock.note='restarted: the document changed'}
  const dt=Math.min(100,Math.max(0,now-(simClock.last||now)));simClock.last=now;
  if(simClock.run)simClock.run.advance(dt*simClock.speed);
  paintSim();updateSimReadout();
  simClock.frame=requestAnimationFrame(simFrame);
}
function simPlay(){if(!simEnsure())return false;simClock.playing=true;simClock.last=0;simClock.frame=requestAnimationFrame(simFrame);updateSimReadout();return true}
function simPause(){simClock.playing=false;if(simClock.frame)cancelAnimationFrame(simClock.frame);simClock.frame=null;updateSimReadout()}
function simStep(){if(!simEnsure())return null;const r=simClock.run.tick();paintSim();updateSimReadout();return r}
function simAdvance(ms){if(!simEnsure())return null;const r=simClock.run.advance(ms);paintSim();updateSimReadout();return r}
function simReset(){simPause();simClock.run=null;simClock.note='';paintSim();updateSimReadout()}
function simToggleLever(id){
  if(!simEnsure())return null;const current=simClock.run.levels()[id]?.value??0;
  const r=simClock.run.set(id,current>0?0:1);simClock.run.run({until:simClock.run.state().time});paintSim();updateSimReadout();return r;
}
function simSend(id){
  if(!simEnsure())return null;
  const doc=snapshotDocument(),saved=(doc.references||[]).filter(r=>r.kind==='scenario').flatMap(r=>r.data?.steps||[]).map(s=>s.inject).find(i=>i&&i.node===id);
  const message=saved?{channel:saved.channel??null,payload:saved.payload??null,principal:saved.principal??null}:{payload:{from:id}};
  const r=simClock.run.inject(id,message);simClock.run.run({until:simClock.run.state().time});paintSim();updateSimReadout();return r;
}
function simResume(parkId,decision){if(!simClock.run)return null;const r=simClock.run.resume(parkId,{decision});simClock.run.run({until:simClock.run.state().time});paintSim();updateSimReadout();return r}

function updateSimReadout(){
  const out=document.getElementById('simTime'),play=document.getElementById('simPlayBtn');if(!out||!play)return;
  const st=simClock.run?.state();
  const t=st?st.time:0,seconds=t>=1000?`${(t/1000).toFixed(t>=10000?1:2)} s`:`${Math.round(t)} ms`;
  out.textContent=simClock.run?`t ${seconds} · ${st.high} high · ${st.edges} edges${st.parked?` · ${st.parked} waiting`:''}${simClock.note?` · ${simClock.note}`:''}`:(simClock.note||'clock stopped');
  if(typeof narrationTick==='function')narrationTick();
  play.textContent=simClock.playing?'❚❚':'▶';play.title=simClock.playing?'Pause the clock':'Run the clock';play.classList.toggle('active',simClock.playing);
}

const SVGNS='http://www.w3.org/2000/svg';
function simEl(tag,attrs,cls){const e=document.createElementNS(SVGNS,tag);if(cls)e.setAttribute('class',cls);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));return e}
// Paint the engine's state over the rendered canvas. Called after every render and every frame.
function paintSim(){
  if(!simLayer)return;
  // A render replaces the node groups: narration focus is put back on the new ones.
  if(typeof narrationState!=='undefined'&&narrationState.index!=null)showNarration(narrationState.index,{manual:narrationState.manual});
  if(typeof legendState!=='undefined'&&legendState.open)renderLegendPanel();
  simLayer.replaceChildren();
  workspace.classList.toggle('sim-live',!!simClock.run);
  for(const gEl of workspace.querySelectorAll('.wire-group.level-high'))gEl.classList.remove('level-high');
  const run=simClock.run;if(!run)return;
  const levels=run.levels();
  const wired=new Set(wires.flatMap(w=>[w.a,w.b]));
  for(const n of nodes){
    // A level is shown where it can matter: on a wired node, or one that declares a signal.
    if(isEffectivelyHidden(n)||!(wired.has(n.id)||componentConfig(n).signal))continue;const L=levels[n.id];if(!L)continue;
    const dim=componentForm(n).dimension,size=componentSize(n);
    if(dim===2){
      const x=n.x+size.w/2-10,y=n.y-size.h/2+10;
      if(L.kind==='binary')simLayer.appendChild(simEl('circle',{cx:x,cy:y,r:4.2},'sim-level binary'+(L.value>0?' high':'')));
      else{const w=26;simLayer.appendChild(simEl('rect',{x:x-w+4,y:y-2.5,width:w,height:5,rx:2.5},'sim-meter'));simLayer.appendChild(simEl('rect',{x:x-w+4,y:y-2.5,width:Math.max(.01,w*L.value),height:5,rx:2.5},'sim-meter-fill'))}
      if(L.mode==='asserted'&&n.symbolId==='lever'){
        const knob=simEl('g',{transform:`translate(${n.x-size.w/2+12} ${n.y-size.h/2+12})`},'sim-lever'+(L.value>0?' high':''));
        knob.appendChild(simEl('rect',{x:-8,y:-5,width:16,height:10,rx:5},'sim-lever-track'));knob.appendChild(simEl('circle',{cx:L.value>0?4:-4,cy:0,r:3.6},'sim-lever-knob'));
        knob.dataset.lever=n.id;const title=simEl('title',{});title.textContent=`${componentConfig(n).label||n.id}: ${L.value>0?'up':'down'} — click to toggle`;knob.appendChild(title);
        knob.addEventListener('pointerdown',e=>{e.stopPropagation();e.preventDefault();simToggleLever(n.id)});simLayer.appendChild(knob);
      }
    }else if(dim===0&&L.value>0)simLayer.appendChild(simEl('circle',{cx:n.x,cy:n.y,r:7},'sim-point-high'));
  }
  // An entry node (wires out, none in) can send work: the payload its saved scenario injects, if any.
  for(const n of nodes){
    if(isEffectivelyHidden(n)||componentForm(n).dimension!==2||!wires.some(w=>w.a===n.id)||wires.some(w=>w.b===n.id))continue;
    const size=componentSize(n),send=simEl('g',{transform:`translate(${n.x-size.w/2-4} ${n.y+size.h/2+4})`},'sim-send');
    send.appendChild(simEl('circle',{r:8}));const tt=simEl('text',{y:4,'text-anchor':'middle'});tt.textContent='➤';send.appendChild(tt);
    const title=simEl('title',{});title.textContent=`Send a message from ${componentConfig(n).label||n.id}`;send.appendChild(title);
    send.addEventListener('pointerdown',e=>{e.stopPropagation();e.preventDefault();simSend(n.id)});simLayer.appendChild(send);
  }
  // A wire is lit while its source end is high.
  for(const w of wires){const v=levels[w.a]?.value??0;if(v<=0)continue;const gEl=workspace.querySelector(`.wire-group[data-wire-id="${CSS.escape(w.id)}"]`);if(gEl){gEl.classList.add('level-high');gEl.style.setProperty('--level',String(v))}}
  // New edges flash + or − beside their node.
  const edges=run.edges().edges;
  for(const e of edges.slice(simClock.edgeMark)){
    const n=nodes.find(x=>x.id===e.node);if(!n)continue;const size=componentSize(n);
    const t=simEl('text',{x:n.x-size.w/2+4,y:n.y-size.h/2-6,'text-anchor':'start'},'sim-edge '+(e.polarity==='+'?'rise':'fall'));t.textContent=e.polarity==='+'?'+':'−';
    simLayer.appendChild(t);setTimeout(()=>t.remove(),700);
  }
  simClock.edgeMark=edges.length;
  // A step waiting on a person shows its decision in place.
  for(const p of run.parked()){
    const n=nodes.find(x=>x.id===p.node);if(!n)continue;const size=componentSize(n),x=n.x,y=n.y+size.h/2+14;
    const chip=simEl('g',{transform:`translate(${x} ${y})`},'sim-waiting');
    chip.appendChild(simEl('rect',{x:-58,y:-10,width:116,height:20,rx:10},'sim-waiting-bg'));
    const label=simEl('text',{x:-48,y:4},'sim-waiting-text');label.textContent='waiting';chip.appendChild(label);
    for(const [dx,decision,glyphText] of [[14,'approve','✓'],[38,'reject','✗']]){
      const b=simEl('g',{transform:`translate(${dx} 0)`},'sim-decide '+decision);b.appendChild(simEl('circle',{r:8}));const tt=simEl('text',{y:4,'text-anchor':'middle'});tt.textContent=glyphText;b.appendChild(tt);
      b.addEventListener('pointerdown',e=>{e.stopPropagation();e.preventDefault();simResume(p.id,decision)});chip.appendChild(b);
    }
    const title=simEl('title',{});title.textContent=p.prompt||'Waiting on a person';chip.appendChild(title);
    simLayer.appendChild(chip);
  }
}

document.getElementById('simPlayBtn')?.addEventListener('click',()=>simClock.playing?simPause():simPlay());
document.getElementById('simStepBtn')?.addEventListener('click',()=>{simPause();simStep()});
document.getElementById('simResetBtn')?.addEventListener('click',()=>simReset());
document.getElementById('simSpeed')?.addEventListener('change',e=>{simClock.speed=Number(e.target.value)||1});
updateSimReadout();
