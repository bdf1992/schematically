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
      // One soft shadow per level: a root card is lifted 1, a card inside it 2, and so on.
      elevation:{
        light:[null,{dy:2,blur:3,opacity:.16},{dy:3,blur:5,opacity:.2},{dy:4.5,blur:7,opacity:.22}],
        dark:[null,{dy:2,blur:3.5,opacity:.6},{dy:3.2,blur:5.5,opacity:.66},{dy:4.6,blur:7.5,opacity:.7}]
      }
    }
  };
  const BUILTIN={schematic:SCHEMATIC};
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
    flat.id=id;return {ok:true,notation:flat};
  }
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
  return {BUILTIN,resolve,tokens,cornerRadius,elevation,merge};
});
