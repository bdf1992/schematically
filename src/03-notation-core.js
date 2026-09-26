'use strict';
// 0.1 concern: notations (NOTATION-MODEL.md). A notation is the declared vocabulary a diagram
// is drawn in: tokens (radius, stroke, type, spacing, elevation), colour roles, glyphs with
// terminals, signal shapes. No DOM; shared by the editor, the audits and the server. The
// editor's own look is the built-in `schematic` notation; a domain extends it.
(function(root,factory){
  const api=factory();
  root.SovSchematicNotation=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  const SCHEMATIC={
    id:'schematic',name:'Schematic',version:1,
    tokens:{
      // Offset from inside: the core keeps radius.core, each line outward adds its band.
      radius:{core:6,card:10},
      // World units. Selected and highlighted states multiply these, never replace them.
      stroke:{structure:1.5,section:1.25,flow:2.25,symbol:2.6},
      space:{labelClear:10,bevel:3.5,pin:14},
      // Text roles (NOTATION-MODEL.md §4). `size` is the base at zoom 1; on screen every role is
      // clamped to `screen` (a subtitle keeps its own lower floor, so it stays under its title).
      type:{screen:{min:12,max:16},title:{size:10,weight:600},subtitle:{size:8.5,weight:400,min:8},body:{size:9,weight:400},caption:{size:9,weight:600},narration:{size:15,weight:500}},
      // One soft shadow per level: a root card is lifted 1, a card inside it 2, and so on.
      elevation:{
        light:[null,{dy:2,blur:3,opacity:.16},{dy:3,blur:5,opacity:.2},{dy:4.5,blur:7,opacity:.22}],
        dark:[null,{dy:2,blur:3.5,opacity:.6},{dy:3.2,blur:5.5,opacity:.66},{dy:4.6,blur:7.5,opacity:.7}]
      }
    }
  };

  // Glyphs in a 96 x 64 box. `draw` is the body only: the renderer draws a pin from each
  // terminal to the box margin (8) in its `toward` direction, so no drawing carries its own
  // stubs and every glyph is symmetric about what it connects. A glyph without terminals is
  // an icon: drawn whole, never connected through.
  const P=(d,o={})=>({d,...o});
  const C=(cx,cy,r)=>`M${cx-r} ${cy}a${r} ${r} 0 1 0 ${2*r} 0a${r} ${r} 0 1 0 ${-2*r} 0`;
  const GLYPHS={
    blank:{title:'Blank',family:'unset',draw:[P('M48 18v28M34 32h28',{width:3.5})]},
    ground:{title:'Ground',family:'passive',draw:[P('M48 8v18M24 28h48M31 38h34M39 48h18')]},
    point:{title:'Point',family:'primitive',draw:[P(C(48,32,9)),P(C(48,32,2.5),{fill:true})]},
    port:{title:'Port',family:'primitive',draw:[P('M8 32h28M60 32h28'+C(48,32,12))]},
    path:{title:'Path',family:'primitive',draw:[P('M12 32h72'),P(C(12,32,4)+C(84,32,4),{fill:true})]},
    plane:{title:'Plane',family:'primitive',draw:[P('M19 10h58a5 5 0 0 1 5 5v34a5 5 0 0 1-5 5H19a5 5 0 0 1-5-5V15a5 5 0 0 1 5-5z'),P('M26 22h44M26 32h44M26 42h28',{width:2.5,opacity:.5})]},
    join:{title:'Join',family:'connection',draw:[P('M8 32h80M48 8v48'),P(C(48,32,6),{fill:true})]},
    cross:{title:'Cross',family:'connection',draw:[P('M8 32h30M58 32h30M48 8v16M48 40v16M38 32c0-8 20-8 20 0')]},
    hold:{title:'Hold',family:'state',draw:[P('M38 16v32M58 16v32')],terminals:[{id:'in',role:'in',at:[32,32],toward:'left'},{id:'out',role:'out',at:[64,32],toward:'right'}]},
    buffer:{title:'Buffer',family:'state',draw:[P('M34 18h28v28H34z'),P('M40 38c6-12 10-12 16 0')],terminals:[{id:'in',role:'in',at:[34,32],toward:'left'},{id:'out',role:'out',at:[62,32],toward:'right'}]},
    act:{title:'Act',family:'transform',draw:[P('M28 14l40 18-40 18z')],terminals:[{id:'in',role:'in',at:[28,32],toward:'left'},{id:'out',role:'out',at:[68,32],toward:'right'}]},
    gate:{title:'Gate',family:'control',draw:[P('M48 18l18 14-18 14-18-14z')],terminals:[{id:'in',role:'in',at:[30,32],toward:'left'},{id:'out',role:'out',at:[66,32],toward:'right'},{id:'control',role:'control',at:[48,18],toward:'top'}]},
    clock:{title:'Clock',family:'timing',draw:[P('M20 42V22h14v20h14V22h14v20h14')],terminals:[{id:'in',role:'in',at:[20,32],toward:'left'},{id:'out',role:'out',at:[76,32],toward:'right'}],
      variants:{wave:{square:[P('M20 42V22h14v20h14V22h14v20h14')],sine:[P('M20 32c7-18 11-18 14 0s7 18 14 0 7-18 14 0 7 18 14 0')],saw:[P('M20 42l18-20v20l19-20v20l19-20v10')],triangle:[P('M20 32l9-10 18 20 18-20 11 10')]}}},
    lever:{title:'Lever',family:'control',draw:[P('M28 40h40M48 40L62 14'),P(C(62,14,5),{fill:true})],terminals:[{id:'in',role:'in',at:[28,40],toward:'left'},{id:'out',role:'out',at:[68,40],toward:'right'}]},
    switch:{title:'Switch',family:'control',draw:[P(C(34,38,4)+C(62,38,4),{fill:true}),P('M36 36l22-18')],terminals:[{id:'in',role:'in',at:[30,38],toward:'left'},{id:'out',role:'out',at:[66,38],toward:'right'},{id:'control',role:'control',at:[48,18],toward:'top'}]},
    limit:{title:'Limit',family:'constraint',draw:[P('M26 32l8-12 10 24 10-24 10 24 8-12')],terminals:[{id:'in',role:'in',at:[26,32],toward:'left'},{id:'out',role:'out',at:[72,32],toward:'right'}]},
    'one-way':{title:'One-way',family:'connection',draw:[P('M8 32h80M48 22l12 10-12 10')]},
    return:{title:'Return',family:'connection',draw:[P('M14 24h60M66 16l10 8-10 8M82 40H22M30 32l-10 8 10 8')]},
    observe:{title:'Observe',family:'evidence',draw:[P('M32 42h32M48 42V24'),P(C(48,16,8))],terminals:[{id:'in',role:'in',at:[32,42],toward:'left'},{id:'out',role:'out',at:[64,42],toward:'right'}]},
    receipt:{title:'Receipt',family:'evidence',draw:[P('M32 24h32M48 24v12'),P('M40 36h16a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H40a2 2 0 0 1-2-2V38a2 2 0 0 1 2-2zM43 45h10')],terminals:[{id:'in',role:'in',at:[32,24],toward:'left'},{id:'out',role:'out',at:[64,24],toward:'right'}]},
    authority:{title:'Authority',family:'reference',draw:[P('M48 8v16M48 40v16M40 32h16'),P(C(48,32,8))]},
    refuse:{title:'Refuse',family:'termination',draw:[P('M30 32h22M54 12v40')],terminals:[{id:'in',role:'in',at:[30,32],toward:'left'}]}
  };
  SCHEMATIC.glyphs=GLYPHS;
  // Logic gates in IEEE Std 91-1984 distinctive shape. Each terminal is a point on the card
  // (`points: 'terminals'`) and each gate declares the combine the simulation runs.
  const IN2=[{id:'a',role:'in',at:[30,22],toward:'left'},{id:'b',role:'in',at:[30,42],toward:'left'}];
  const OR_BODY='M26 12Q46 12 72 32Q46 52 26 52Q36 32 26 12Z';
  const gate=(title,meaning,draw,terminals,combine)=>({title,family:'logic',meaning,draw,terminals,points:'terminals',signal:{combine}});
  const LOGIC={
    id:'logic',name:'Logic gates',version:1,extends:'schematic',source:'IEEE Std 91-1984, distinctive shapes',
    glyphs:{
      and2:gate('And','High when both inputs are high.',[P('M30 12H50A20 20 0 0 1 50 52H30Z')],[...IN2,{id:'y',role:'out',at:[70,32],toward:'right'}],'and'),
      or2:gate('Or','High when either input is high.',[P(OR_BODY)],[...IN2,{id:'y',role:'out',at:[72,32],toward:'right'}],'or'),
      xor2:gate('Exclusive or','High when exactly one input is high.',[P('M30 12Q50 12 74 32Q50 52 30 52Q40 32 30 12Z'),P('M23 12Q33 32 23 52')],[{id:'a',role:'in',at:[27,22],toward:'left'},{id:'b',role:'in',at:[27,42],toward:'left'},{id:'y',role:'out',at:[74,32],toward:'right'}],'xor'),
      nand2:gate('Not and','Low only when both inputs are high.',[P('M30 12H50A20 20 0 0 1 50 52H30Z'),P(C(74,32,4))],[...IN2,{id:'y',role:'out',at:[78,32],toward:'right'}],'nand'),
      nor2:gate('Not or','High only when both inputs are low.',[P(OR_BODY),P(C(76,32,4))],[...IN2,{id:'y',role:'out',at:[80,32],toward:'right'}],'nor'),
      not:gate('Not','High when its input is low.',[P('M30 14L62 32L30 50Z'),P(C(66,32,4))],[{id:'a',role:'in',at:[30,32],toward:'left'},{id:'y',role:'out',at:[70,32],toward:'right'}],'not'),
      buf:gate('Buffer','Repeats its input.',[P('M30 14L62 32L30 50Z')],[{id:'a',role:'in',at:[30,32],toward:'left'},{id:'y',role:'out',at:[62,32],toward:'right'}],'buffer')
    }
  };
  const BUILTIN={schematic:SCHEMATIC,logic:LOGIC};
  const isObject=v=>!!v&&typeof v==='object'&&!Array.isArray(v);
  function merge(base,over){
    if(!isObject(over))return over===undefined?base:over;
    const out={...(isObject(base)?base:{})};
    for(const [k,v] of Object.entries(over))out[k]=isObject(v)?merge(out[k],v):v;
    return out;
  }
  // The notation a document is drawn in, flattened through `extends`. An unknown name is
  // refused, never replaced by the default.
  function resolve(docOrId,extra={}){
    const id=typeof docOrId==='string'?docOrId:(docOrId?.notation||'schematic');
    const carried=typeof docOrId==='object'?(docOrId?.references||[]).filter(r=>r?.kind==='notation'&&isObject(r.data)).map(r=>r.data):[];
    const table={...BUILTIN,...extra};for(const n of carried)if(n.id)table[n.id]=n;
    const chain=[];let cur=table[id];const seen=new Set();
    if(!cur)return {ok:false,code:'UNKNOWN_NOTATION',message:`No notation "${id}"`,next_operation:`use one of: ${Object.keys(table).join(', ')}`};
    while(cur&&!seen.has(cur.id)){chain.unshift(cur);seen.add(cur.id);cur=cur.extends?table[cur.extends]:null}
    let flat={};for(const n of chain)flat=merge(flat,n);
    flat.id=id;registerPoints(flat);return {ok:true,notation:flat};
  }
  // Glyphs whose terminals are the card's attachment points (`points: 'terminals'`), by symbol
  // id, filled whenever a notation is resolved. The attachment core reads it, so a gate's two
  // inputs are two points wherever the card is created, retyped, loaded or served.
  const TERMINAL_POINTS=new Map();
  function terminalAttachmentPoints(g){
    const bySide={};for(const t of g.terminals||[]){const side=t.toward==='top'?'top':t.toward==='bottom'?'bottom':t.toward;(bySide[side]=bySide[side]||[]).push(t)}
    const out=[];
    for(const [side,list] of Object.entries(bySide)){
      const along=side==='left'||side==='right'?1:0;list.sort((a,b)=>a.at[along]-b.at[along]);
      list.forEach((t,i)=>out.push({id:t.id,compatId:t.id,side,t:+((i+1)/(list.length+1)).toFixed(4),defaultFlow:['in','out','control','duplex','trigger'].includes(t.role)?t.role:'duplex'}));
    }
    return out;
  }
  function registerPoints(notation){for(const [id,g] of Object.entries(notation?.glyphs||{}))if(g.points==='terminals')TERMINAL_POINTS.set(id,terminalAttachmentPoints(g))}
  function pointsFor(symbolId){const p=TERMINAL_POINTS.get(symbolId);return p?p.map(x=>({...x})):null}
  function tokens(docOrId){const r=resolve(docOrId);return (r.ok?r.notation:SCHEMATIC).tokens}
  // Corner radius of the rectangle at `inset` inside a card whose bands sum to `total`.
  // Concentric by construction; capped at a quarter of the rectangle's shorter side.
  function cornerRadius(t,{total=0,inset=0,w=Infinity,h=Infinity,sectioned=false}={}){
    const r=sectioned?t.radius.core+Math.max(0,total-inset):t.radius.card;
    return Math.max(0,Math.min(r,Math.min(w,h)/4));
  }
  function elevation(t,level,appearance='light'){
    const L=(t.elevation?.[appearance]||t.elevation?.light||[]);
    return L[Math.max(0,Math.min(L.length-1,level|0))]||null;
  }
  const MARGIN=8;
  function glyphOf(notation,id){return notation?.glyphs?.[id]||null}
  // The body for a variant (`{wave: 'sine'}`), falling back to the plain drawing.
  function glyphDraw(g,variant={}){
    for(const [key,value] of Object.entries(variant||{}))if(value!=null&&g?.variants?.[key]?.[value])return g.variants[key][value];
    return g?.draw||[];
  }
  function pinEnd(t){const [x,y]=t.at;return t.toward==='left'?[MARGIN,y]:t.toward==='right'?[96-MARGIN,y]:t.toward==='top'?[x,MARGIN]:[x,64-MARGIN]}
  // The glyph as SVG markup in its 96 x 64 box: body and pins, stroked in currentColor.
  function glyphMarkup(g,{variant={},stroke=4}={}){
    const parts=[];
    for(const p of glyphDraw(g,variant))parts.push(`<path d="${p.d}"${p.fill?' fill="currentColor" stroke="none"':''}${p.width?` stroke-width="${p.width*stroke/4}"`:''}${p.opacity!=null?` opacity="${p.opacity}"`:''}/>`);
    for(const t of g?.terminals||[]){const [x2,y2]=pinEnd(t);parts.push(`<path class="glyph-pin" data-terminal="${t.id}" d="M${t.at[0]} ${t.at[1]}L${x2} ${y2}"/>`)}
    return `<g fill="none" stroke="currentColor" stroke-width="${stroke}" stroke-linecap="round" stroke-linejoin="round">${parts.join('')}</g>`;
  }
  // The glyph box inside a card of `size`, and where a terminal sits relative to the card's
  // centre. One formula for the renderer and the layout engine, so a laid-out wire is straight.
  // The size a role is drawn at zoom 1: its base, held inside the screen range.
  function drawnSize(type,role){const t=type?.[role]||{},lo=t.min??type?.screen?.min??0,hi=type?.screen?.max??Infinity;return Math.max(lo,Math.min(hi,t.size||10))}
  // The glyph leaves the card's foot to its title, and a line more for a subtitle.
  // The glyph leaves the card's foot to its title (one or two lines, from its length at the title
  // size) and a line more for a subtitle. Centred on the axis, so the room is kept on both sides.
  function glyphBox(g,size,{subtitle=false,title='',type=SCHEMATIC.tokens.type}={}){
    const ts=drawnSize(type,'title'),ss=drawnSize(type,'subtitle'),avail=Math.max(1,size.w-12);
    const lines=Math.max(1,Math.min(2,Math.ceil(String(title||'').length*ts*.6/avail)));
    const foot=8+lines*ts*1.15+(subtitle?ss*1.3:0);
    const many=g?.points==='terminals',w=Math.min(size.w*.72,108),h=Math.max(24,Math.min(size.h*(many?.7:.55),70,size.h-2*foot));
    return {w,h,scale:Math.min(w/96,h/64)};
  }
  function glyphAxis(g){
    if(!g)return null;
    if(g.points==='terminals'){const ys=(g.terminals||[]).filter(t=>t.toward==='left'||t.toward==='right').map(t=>t.at[1]);return ys.length?(Math.min(...ys)+Math.max(...ys))/2:null}
    const t=terminal(g,'in')||terminal(g,'out');return t&&(t.toward==='left'||t.toward==='right')?t.at[1]:null;
  }
  function terminalOffset(g,id,size,opts={}){
    const t=(g?.terminals||[]).find(x=>x.id===id),axis=glyphAxis(g);if(!t||axis==null)return null;
    const {scale}=glyphBox(g,size,opts);return {dx:(t.at[0]-48)*scale,dy:(t.at[1]-axis)*scale};
  }
  function terminal(g,idOrRole){return (g?.terminals||[]).find(t=>t.id===idOrRole)||(g?.terminals||[]).find(t=>t.role===idOrRole)||null}
  return {BUILTIN,MARGIN,drawnSize,glyphBox,glyphAxis,terminalOffset,pointsFor,terminalAttachmentPoints,resolve,tokens,cornerRadius,elevation,merge,glyphOf,glyphDraw,glyphMarkup,terminal,pinEnd};
});
