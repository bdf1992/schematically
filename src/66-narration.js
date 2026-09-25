'use strict';
// 0.1 concern: narration (NOTATION-MODEL.md §4). Interface narration is shown the way a film
// shows subtitles: one line at a time in a caption bar at the foot of the canvas, following the
// clock, with the components it names in focus and the rest dimmed. Narration is presentation,
// like a layout: it never changes what the document means.

const narrationBar=document.getElementById('narrationBar');
const narrationState={index:null,manual:false};

// Every line, in order: the document's own track, then the lines its saved scenarios carry.
function narrationLines(doc=diagram){
  const own=(Array.isArray(doc.narration)?doc.narration:[]).filter(l=>l&&typeof l.say==='string'&&l.say.trim()).map(l=>({at:Number.isFinite(Number(l.at))?Number(l.at):null,say:l.say.trim(),focus:Array.isArray(l.focus)?l.focus.map(String):[]}));
  const scenario=[];
  for(const r of doc.references||[])if(r.kind==='scenario')for(const step of r.data?.steps||[])if(typeof step?.say==='string'&&step.say.trim())scenario.push({at:Number.isFinite(Number(step.at))?Number(step.at):null,say:step.say.trim(),focus:step.inject?.node?[String(step.inject.node)]:[],scenario:r.id});
  return [...own,...scenario];
}
// The line in force at a clock time: the last one whose time has come.
function narrationIndexAt(time,lines=narrationLines()){
  let best=null;lines.forEach((l,i)=>{if(l.at!=null&&l.at<=time&&(best==null||l.at>=lines[best].at))best=i});return best;
}
function showNarration(index,{manual=true}={}){
  const lines=narrationLines(),line=index==null?null:lines[index];
  narrationState.index=line?index:null;narrationState.manual=!!line&&manual;
  if(narrationBar){narrationBar.hidden=!line;narrationBar.textContent=line?line.say:''}
  const focus=new Set(line?.focus||[]);
  workspace.classList.toggle('narrating',!!line&&focus.size>0);
  for(const g of workspace.querySelectorAll('.node'))g.classList.toggle('narration-dim',focus.size>0&&!focus.has(g.dataset.id));
  for(const g of workspace.querySelectorAll('.wire-group')){const w=wires.find(x=>x.id===g.dataset.wireId);g.classList.toggle('narration-dim',focus.size>0&&!(w&&(focus.has(w.a)||focus.has(w.b))))}
  return {ok:true,index:narrationState.index,line};
}
// Called by the clock readout: while the clock runs, the line for the current time is shown.
function narrationTick(){
  if(narrationState.manual)return;
  const st=simClock.run?.state();if(!st){if(narrationState.index!=null)showNarration(null,{manual:false});return}
  const i=narrationIndexAt(st.time);if(i!==narrationState.index)showNarration(i,{manual:false});
}
