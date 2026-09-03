'use strict';
// 0.1 concern: Patterns — arrangements of forms.
//
// A Pattern is the second ladder's first rung (VOCABULARY.md): forms put together.
// It is not a new record kind and it is not a type. Dropping one runs the same
// creation and hosting paths a person's own gestures run, and what lands is ordinary
// Points, Paths, Planes and Wires with nothing marking them as having come from here.
// A Pattern is therefore a starting arrangement, not a thing you can later edit as a
// unit — that would be a Program, which does not exist yet.
//
// Each entry says what it is made of in one line, because the sidebar's job is to
// teach the distinction between a form and an arrangement of forms.

const PATTERNS=[
  {
    id:'pair',
    name:'PAIR',
    sense:'two Points, joined',
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
    build(x,y){
      // Not a form: a Wire whose two ends are bound to nothing yet. This is what the
      // palette's PATH used to drop, which is why PATH would not behave like a form.
      addCarrier(x,y,null,{render:false,select:false});
      return [];
    }
  },
  {
    id:'block',
    name:'BLOCK',
    sense:'a Plane with Points',
    build(x,y){
      const plane=addNode('plane',x,y,null,{render:false,select:false});
      // The template's built-in boundary points are what a typed Component always
      // was: a Plane that came with somewhere to attach.
      plane.config.attachmentDefaults='standard';
      componentConfig(plane);
      return [plane];
    }
  },
  {
    id:'nest',
    name:'NEST',
    sense:'a Plane within a Plane',
    build(x,y){
      const outer=addNode('plane',x,y,null,{render:false,select:false});
      const size=componentSize(outer);
      const inner=addNode('plane',x,y,null,{render:false,select:false});
      const inner_p=componentConfig(inner).presentation;
      inner_p.size.w=Math.max(80,Math.round(size.w*.5));
      inner_p.size.h=Math.max(64,Math.round(size.h*.45));
      updateContainmentFor(inner);
      return [outer,inner];
    }
  }
];

function patternById(id){return PATTERNS.find(p=>p.id===String(id))||null}

// One drop is one undoable step, however many forms it puts down.
function addPattern(id,x=null,y=null){
  const pattern=patternById(id);
  if(!pattern){statusEl.textContent=`Unknown pattern: ${id}`;return null}
  const centerX=camera.x+camera.w/2,centerY=camera.y+camera.h/2;
  const px=x==null?centerX:x,py=y==null?centerY:y;
  setHistoryHint(`Add ${pattern.name}`);
  let made=[];
  try{
    made=pattern.build(px,py)||[];
  }catch(error){
    console.error(error);
    statusEl.textContent=`${pattern.name} could not be placed`;
    return null;
  }
  routeCache.clear();arrowPoseCache.clear();
  syncAllNodeBoundaryContext();
  render();
  // The arrangement is the thing that was added, so all of it is selected. A Pattern
  // made only of Wires selects nothing, which is the honest answer for it.
  clearComponentSelectionSet();
  for(const node of made)selectedComponentIds.add(node.id);
  if(made.length)selectNode(made.at(-1).id,{preserveSet:true,focus:false});
  commitHistoryCapture(`Add ${pattern.name}`);
  statusEl.textContent=made.length?`${pattern.name} · ${made.length} forms`:`${pattern.name} added`;
  return made;
}

// One line drawing per Pattern, showing the arrangement rather than a form.
function patternGlyph(id){return `<svg viewBox="0 0 96 64"><use href="#pat-${id}"/></svg>`}

// Patterns are arrangements of those forms, so they are a second section rather than
// more rungs: dropping one puts down several ordinary forms already related to each
// other. The card says what it is made of, because that distinction is the point.
{
  const section=document.createElement('div');
  section.className='section';section.dataset.group='patterns';
  section.innerHTML='<h2>Pattern</h2><div class="symbol-ladder pattern-ladder"></div>';
  const list=section.querySelector('.symbol-ladder');
  for(const pattern of PATTERNS){
    const b=document.createElement('button');
    b.type='button';b.className='symbol-card ladder-rung pattern-card';
    b.dataset.patternId=pattern.id;
    b.innerHTML=patternGlyph(pattern.id)
      +`<span class="ladder-text"><b>${pattern.name}</b><small>${pattern.sense}</small></span>`;
    b.title=`${pattern.name} · ${pattern.sense}`;
    bindPalettePattern(b,pattern.id);
    list.appendChild(b);
  }
  palette.appendChild(section);
}
