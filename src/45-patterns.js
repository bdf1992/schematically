'use strict';
// 0.1 concern: Patterns — forms put together, and one thing while they are.
//
// A Pattern is the second ladder's first rung (VOCABULARY.md). It is a record of its
// own: an id, a kind, a name and a color, with Components and Wires belonging to it by
// naming it in `patternId`. That is what makes a Pattern behave the way a Component
// does — one click selects it, one drag moves it, one Delete takes it, its name and
// color live in one place — rather than being a way of drawing several forms at once.
//
// It is still made of ordinary forms. OPEN steps inside and the parts select and move
// one at a time; RELEASE drops the record and leaves the forms loose. Nothing about the
// parts is special: a Pattern is who they belong to, not what they are.

const PATTERN_KINDS=[
  {
    id:'pair',
    name:'PAIR',
    sense:'two Points, joined',
    meaning:'Two Points and the Wire between them. The smallest thing that is a relation rather than a location.',
    build(x,y){
      const a=addNode('point',x-90,y,null,{render:false,select:false});
      const b=addNode('point',x+90,y,null,{render:false,select:false});
      addConnection(a.id,'self',b.id,'self');
      return [a,b];
    }
  },
  {
    id:'chain',
    name:'CHAIN',
    sense:'Points in series',
    meaning:'Points joined end to end, so what leaves one arrives at the next.',
    build(x,y){
      const made=[-140,0,140].map(dx=>addNode('point',x+dx,y,null,{render:false,select:false}));
      for(let i=0;i<made.length-1;i++)addConnection(made[i].id,'self',made[i+1].id,'self');
      return made;
    }
  },
  {
    id:'hub',
    name:'HUB',
    sense:'one Point, many out',
    meaning:'One Point every other Point reaches. A shape, not a permission.',
    build(x,y){
      const centre=addNode('point',x,y,null,{render:false,select:false});
      const spokes=[[150,-110],[170,0],[150,110]].map(([dx,dy])=>
        addNode('point',x+dx,y+dy,null,{render:false,select:false}));
      for(const spoke of spokes)addConnection(centre.id,'self',spoke.id,'self');
      return [centre,...spokes];
    }
  },
  {
    id:'rail',
    name:'RAIL',
    sense:'Points along a Path',
    meaning:'A Path carrying Points at positions along it, each riding the Path when it moves.',
    build(x,y){
      const rail=addNode('path',x,y,null,{render:false,select:false});
      // Settle each Point through the ordinary host path, so what lands is exactly
      // what dragging a Point onto the Path by hand would have produced.
      const riders=[];
      for(const t of [.2,.5,.8]){
        const half=Math.max(PATH_MIN_LENGTH,componentSize(rail).w)/2;
        const point=addNode('point',rail.x-half+half*2*t,rail.y,null,{render:false,select:false});
        applyComponentHost(point,componentHostCandidateAtPoint(point,point.x,point.y));
        riders.push(point);
      }
      return [rail,...riders];
    }
  },
  {
    id:'carrier',
    name:'CARRIER',
    sense:'a Wire, ends free',
    meaning:'A Wire bound to nothing yet. This is what the palette PATH used to drop, before PATH became the 1D form.',
    build(x,y){
      const wire=addCarrier(x,y,null,{render:false,select:false});
      return wire?{components:[],wires:[wire]}:{components:[],wires:[]};
    }
  },
  {
    id:'block',
    name:'BLOCK',
    sense:'a Plane with Points',
    meaning:'A Plane that came with somewhere to attach. This is what a typed Component always was.',
    build(x,y){
      const plane=addNode('plane',x,y,null,{render:false,select:false});
      plane.config.attachmentDefaults='standard';
      componentConfig(plane);
      return [plane];
    }
  },
  {
    id:'nest',
    name:'NEST',
    sense:'a Plane within a Plane',
    meaning:'A Plane held inside another Plane, so the inner one is scoped by the outer.',
    build(x,y){
      const outer=addNode('plane',x,y,null,{render:false,select:false});
      const size=componentSize(outer);
      const inner=addNode('plane',x,y,null,{render:false,select:false});
      const innerPresentation=componentConfig(inner).presentation;
      innerPresentation.size.w=Math.max(80,Math.round(size.w*.5));
      innerPresentation.size.h=Math.max(64,Math.round(size.h*.45));
      updateContainmentFor(inner);
      return [outer,inner];
    }
  }
];
// The palette section still calls the list PATTERNS; the entries are kinds, and a
// dropped Pattern is a record whose `kind` names one of them.
const PATTERNS=PATTERN_KINDS;

function patternKind(id){return PATTERN_KINDS.find(k=>k.id===String(id))||null}
// Kept for the earlier name, which the API and the palette both used.
function patternById(id){return patternKind(id)}

// --- Pattern records -------------------------------------------------------
function patternRecord(id){return patternRecords.find(p=>p.id===String(id))||null}
function patternOf(entity){return entity?.patternId?patternRecord(entity.patternId):null}
function patternMemberNodes(id){return nodes.filter(n=>n.patternId===id)}
function patternMemberWires(id){return wires.filter(w=>w.patternId===id)}
function patternMemberCount(id){return patternMemberNodes(id).length+patternMemberWires(id).length}
function patternDisplayName(record){
  if(!record)return '—';
  return record.label||patternKind(record.kind)?.name||record.kind||record.id;
}
function patternSenseText(record){return patternKind(record?.kind)?.sense||'forms, together'}
function patternColor(record){return slotColor(record?.colorSlot??0)}

// A Pattern is open while its parts are being worked on. Open state is a view of the
// session, not of the document: a saved file records who belongs to what, never which
// Pattern happened to be unfolded when it was written.
const openPatternIds=new Set();
function patternIsOpen(id){return openPatternIds.has(String(id))}
function setPatternOpen(id,open){
  if(open)openPatternIds.add(String(id));else openPatternIds.delete(String(id));
}
// The Pattern a click on this node should land on: none if the node is loose, and none
// while the Pattern is open, because open is exactly the state where the parts answer
// for themselves.
function enclosingClosedPattern(entity){
  const record=patternOf(entity);
  return record&&!patternIsOpen(record.id)?record:null;
}

function drawnWireBox(wireId){
  const el=wiresG?.querySelector(`.wire-group[data-wire-id="${wireId}"]`);
  if(!el||typeof el.getBBox!=='function')return null;
  try{
    const box=el.getBBox();
    if(!Number.isFinite(box.x)||(!box.width&&!box.height))return null;
    return {l:box.x,r:box.x+box.width,t:box.y,b:box.y+box.height};
  }catch(_){return null}
}
function patternBounds(id,pad=18){
  let l=Infinity,r=-Infinity,t=Infinity,b=-Infinity;
  for(const node of patternMemberNodes(id)){
    const box=componentBounds(node);
    l=Math.min(l,box.l);r=Math.max(r,box.r);t=Math.min(t,box.t);b=Math.max(b,box.b);
  }
  for(const wire of patternMemberWires(id)){
    // A Wire's endpoints are not its extent: the router takes the room it takes, and a
    // hull that cut through its own Wire would be lying about what belongs to it. Where
    // the Wire has been drawn, its drawn box is the truth; otherwise fall back to the ends.
    const box=drawnWireBox(wire.id);
    if(box){l=Math.min(l,box.l);r=Math.max(r,box.r);t=Math.min(t,box.t);b=Math.max(b,box.b);continue}
    for(const end of ['a','b']){
      const pos=carrierEndpointPos(wire,end);if(!pos)continue;
      l=Math.min(l,pos.x);r=Math.max(r,pos.x);t=Math.min(t,pos.y);b=Math.max(b,pos.y);
    }
  }
  if(!Number.isFinite(l))return null;
  return {l:l-pad,r:r+pad,t:t-pad,b:b+pad};
}

// --- Making one ------------------------------------------------------------
// One drop is one undoable step, and what it leaves behind is a Pattern plus the forms
// that belong to it.
function addPattern(id,x=null,y=null){
  const kind=patternKind(id);
  if(!kind){statusEl.textContent=`Unknown pattern: ${id}`;return null}
  const centerX=camera.x+camera.w/2,centerY=camera.y+camera.h/2;
  const px=x==null?centerX:x,py=y==null?centerY:y;
  setHistoryHint(`Add ${kind.name}`);
  const wiresBefore=new Set(wires.map(w=>w.id));
  let built=[];
  try{
    built=kind.build(px,py)||[];
  }catch(error){
    console.error(error);
    statusEl.textContent=`${kind.name} could not be placed`;
    return null;
  }
  const madeNodes=Array.isArray(built)?built:(built.components||[]);
  // Whatever a build wired up belongs to the Pattern too, however it made them.
  const madeWires=Array.isArray(built)
    ?wires.filter(w=>!wiresBefore.has(w.id))
    :(built.wires||[]);

  const record=SovSchematicData.makePattern(diagram,{kind:kind.id,label:'',colorSlot:0});
  patternRecords.push(record);
  for(const member of [...madeNodes,...madeWires])member.patternId=record.id;

  routeCache.clear();arrowPoseCache.clear();
  syncAllNodeBoundaryContext();
  render();
  selectPattern(record.id,{focus:false});
  commitHistoryCapture(`Add ${kind.name}`);
  statusEl.textContent=`${patternDisplayName(record)} · ${patternMemberCount(record.id)} parts`;
  return madeNodes;
}

// --- Selecting one ---------------------------------------------------------
// A Pattern selects as one thing. Its member Components go into the ordinary component
// selection set, because that set is what dragging, nudging and deleting already read;
// `selected` names the Pattern, so the bar and the inspector answer for the Pattern
// rather than for whichever part happened to be under the pointer.
function selectPattern(id,{focus=true}={}){
  const record=patternRecord(id);
  if(!record){selectNode(null);return null}
  clearEndpointFocus?.();
  selectedComponentIds.clear();
  for(const node of patternMemberNodes(record.id))selectedComponentIds.add(node.id);
  selected=`pattern:${record.id}`;
  if(focus)activateCanvasKeyboard();
  document.querySelectorAll('.node').forEach(el=>el.classList.toggle('selected',selectedComponentIds.has(el.dataset.id)));
  document.querySelectorAll('.wire').forEach(el=>el.classList.remove('selected'));
  document.querySelectorAll('.port').forEach(el=>el.classList.remove('port-selected'));
  document.getElementById('emptyInspector').hidden=true;
  hideInspectorKinds();
  patternDetail.hidden=false;
  qName.textContent=patternKind(record.kind)?.name||record.kind;
  qSense.textContent=patternSenseText(record);
  qLabel.textContent=record.label||'—';
  {const n=patternMemberNodes(record.id).length,w=patternMemberWires(record.id).length;
   qParts.textContent=`${n} form${n===1?'':'s'} · ${w} wire${w===1?'':'s'}`;}
  {const host=patternMemberNodes(record.id)[0];
   qParent.textContent=host?componentDisplayName(parentComponent(host)):'—';
   qScope.textContent=host?componentScopePath(host):'world';}
  qState.textContent=patternIsOpen(record.id)?'Open · parts select one at a time':'Closed · selects as one';
  qMeaning.textContent=patternKind(record.kind)?.meaning||'Forms, together.';
  showPatternBar(record);
  renderPatternHulls();
  return record;
}
function selectedPatternRecord(){
  return typeof selected==='string'&&selected.startsWith('pattern:')?patternRecord(selected.slice(8)):null;
}

// OPEN is a toggle, not a mode with its own exit: opening selects the first part so
// there is something to work on, and closing puts the Pattern back in hand.
function togglePatternOpen(id){
  const record=patternRecord(id);if(!record)return;
  const open=!patternIsOpen(record.id);
  setPatternOpen(record.id,open);
  if(open){
    const first=patternMemberNodes(record.id)[0];
    statusEl.textContent=`${patternDisplayName(record)} open · parts select one at a time`;
    if(first)selectNode(first.id,{focus:false});else selectNode(null);
  }else{
    selectPattern(record.id,{focus:false});
    statusEl.textContent=`${patternDisplayName(record)} closed`;
  }
  renderPatternHulls();
}

// RELEASE drops the record and leaves the forms exactly where they are. Nothing is
// deleted, so it is the honest opposite of dropping a Pattern.
function releasePattern(id){
  const record=patternRecord(id);if(!record)return null;
  commitHistoryCapture();
  setHistoryHint(`Release ${patternDisplayName(record)}`);
  const freed=patternMemberNodes(record.id);
  for(const member of [...freed,...patternMemberWires(record.id)])delete member.patternId;
  const index=patternRecords.findIndex(p=>p.id===record.id);
  if(index>=0)patternRecords.splice(index,1);
  openPatternIds.delete(record.id);
  render();
  setComponentSelection(freed.map(n=>n.id),freed.at(-1)?.id||null);
  if(freed.length)selectNode(freed.at(-1).id,{preserveSet:true,focus:false});else selectNode(null);
  commitHistoryCapture(`Release ${patternDisplayName(record)}`);
  statusEl.textContent=`Released · ${freed.length} form${freed.length===1?'':'s'} loose`;
  return freed;
}

function renamePattern(id,label){
  const record=patternRecord(id);if(!record)return;
  record.label=String(label||'').slice(0,60);
  qLabel.textContent=record.label||'—';
  renderPatternHulls();
  scheduleHistoryCapture('Rename Pattern');
}

// --- Drawing the hull ------------------------------------------------------
// A Pattern is one object, so it needs one outline. It is drawn under the forms and it
// is never a hit target: clicking a member is what selects the Pattern, and an outline
// that swallowed clicks in the gaps would make the parts harder to reach once open.
function renderPatternHulls(){
  if(!patternHullsG)return;
  patternHullsG.replaceChildren();
  for(const record of patternRecords){
    const box=patternBounds(record.id);if(!box)continue;
    const open=patternIsOpen(record.id);
    const active=selectedPatternRecord()?.id===record.id;
    const g=document.createElementNS('http://www.w3.org/2000/svg','g');
    g.setAttribute('class','pattern-hull'+(active?' selected':'')+(open?' open':''));
    g.dataset.patternId=record.id;
    const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');
    rect.setAttribute('x',box.l);rect.setAttribute('y',box.t);
    rect.setAttribute('width',Math.max(1,box.r-box.l));rect.setAttribute('height',Math.max(1,box.b-box.t));
    rect.setAttribute('rx','14');
    rect.style.setProperty('--pattern-color',patternColor(record));
    g.appendChild(rect);
    const label=document.createElementNS('http://www.w3.org/2000/svg','text');
    label.setAttribute('class','pattern-hull-label');
    label.setAttribute('x',box.l+12);label.setAttribute('y',box.t-6);
    label.style.setProperty('--pattern-color',patternColor(record));
    label.textContent=patternDisplayName(record).toUpperCase()+(open?' · OPEN':'');
    g.appendChild(label);
    patternHullsG.appendChild(g);
  }
}

// --- The palette section ---------------------------------------------------
// Patterns are a second section because the vocabulary has two ladders. The card says
// what the Pattern is made of, because that distinction is the point of the section.
{
  const section=document.createElement('div');
  section.className='section';section.dataset.group='patterns';
  section.innerHTML='<h2>Pattern</h2><div class="symbol-ladder pattern-ladder"></div>';
  const list=section.querySelector('.symbol-ladder');
  for(const kind of PATTERN_KINDS){
    const b=document.createElement('button');
    b.type='button';b.className='symbol-card ladder-rung pattern-card';
    b.dataset.patternId=kind.id;
    b.innerHTML=`<svg viewBox="0 0 96 64"><use href="#pat-${kind.id}"/></svg>`
      +`<span class="ladder-text"><b>${kind.name}</b><small>${kind.sense}</small></span>`;
    b.title=`${kind.name} · ${kind.sense}`;
    bindPalettePattern(b,kind.id);
    list.appendChild(b);
  }
  palette.appendChild(section);
}
function patternGlyph(id){return `<svg viewBox="0 0 96 64"><use href="#pat-${id}"/></svg>`}
