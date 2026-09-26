"""Declared ports: the data model (contract 0b-1, issue #45, with amendments 2 and 3).

A 2D Component's ports are declared data. The attachment core holds no port set of its own;
the typed Component template declares the left/right/top trio; stored forms keep their
meaning ('standard' = template ports + authored additions, 'none' = the authored list);
edits are stored in the smallest form and refused when invalid or when they would orphan a
Wire; binding a Wire needs the two ports to share a channel. Node and the HTTP/MCP server
only; no browser.
"""
from __future__ import annotations
import json
import re
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]
TRIO = [
    {'id': 'left', 'compatId': 'in', 'side': 'left', 't': .5, 'flow': 'in', 'channels': [{'id': 'main'}]},
    {'id': 'right', 'compatId': 'out', 'side': 'right', 't': .5, 'flow': 'out', 'channels': [{'id': 'main'}]},
    {'id': 'top', 'compatId': 'control', 'side': 'top', 't': .5, 'flow': 'control', 'channels': [{'id': 'main'}]},
]


def node(js: str, *args: str):
    proc = subprocess.run(['node', '-e', js, *args], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


# Step 1: the attachment core alone (no data core registered) exposes no 2D port set.
CORE_ALONE = r"""
const A=require(process.argv[1]);
const surface={id:'s',symbolId:'act',form:{dimension:2},config:{}};
const authored={id:'t',symbolId:'act',form:{dimension:2},config:{attachmentPoints:[{id:'feed',side:'bottom',t:.3,flow:'in'}]}};
console.log(JSON.stringify({
  bare:A.pointIds(surface),authored:A.pointIds(authored),
  zero:A.pointSpecs({form:{dimension:0}}),one:A.pointSpecs({form:{dimension:1}})
}));
"""

CORE = r"""
const D=require(process.argv[1]),A=globalThis.SovSchematicAttachment,fs=require('fs');
const clone=x=>JSON.parse(JSON.stringify(x));
const out={};
const ids=c=>A.pointIds(c);
const specs=c=>A.pointSpecs(c).map(s=>({id:s.id,compatId:s.compatId,side:s.side,t:s.t,flow:s.flow,channels:s.channels}));
const doc0=()=>D.makeDocument({id:'t'});
const op=(doc,o)=>D.applyOperation(doc,o);
const upd=(doc,id,patch)=>op(doc,{op:'update',resource:'component',resourceId:id,patch});
const mk=(doc,value)=>op(doc,{op:'create',resource:'component',value});
const mkw=(doc,value)=>op(doc,{op:'create',resource:'wire',value});
const reload=doc=>D.documentFromFilePayload(JSON.parse(JSON.stringify(D.compactDocument(doc))));

// Step 2: template data.
out.symbols=JSON.parse(process.argv[2]);
out.templates={};for(const s of out.symbols)out.templates[s]=D.templatePorts(s);
out.planePreset=D.templatePreset('plane');
{const d=doc0();mk(d,{id:'pl',symbolId:'plane',x:0,y:0});mk(d,{id:'ac',symbolId:'act',x:300,y:0});out.planeIds=ids(d.components[0]);out.actSpecs=specs(d.components[1]);}

// Step 4: legacy stored forms, idempotent normalization, nothing written into the array.
{
  const file={schema:D.DOCUMENT_SCHEMA,id:'legacy',revision:0,references:[],components:[
    {id:'plain',symbolId:'act',x:0,y:0},
    {id:'std',symbolId:'buffer',x:300,y:0,config:{attachmentDefaults:'standard',attachmentPoints:[{id:'aux',side:'bottom',t:.25,defaultFlow:'duplex'}]}},
    {id:'imp',symbolId:'gate',x:600,y:0,config:{attachmentPoints:[{id:'aux2',compatId:'aux-2',side:'bottom',t:.75}]}},
    {id:'non',symbolId:'hold',x:900,y:0,config:{attachmentDefaults:'none',attachmentPoints:[{id:'only',side:'left',t:.5,flow:'in'}]}},
    {id:'pls',symbolId:'plane',x:0,y:400,config:{attachmentDefaults:'standard'}}
  ],wires:[
    {id:'k1',a:'plain',aSide:'out',b:'std',bSide:'in'},
    {id:'k2',a:'std',aAttachment:{pointId:'aux'},aSide:'aux',b:'non',bSide:'only'},
    {id:'k3',a:'imp',aSide:'aux-2',b:'pls',bSide:'control'}
  ]};
  const stored=Object.fromEntries(file.components.map(c=>[c.id,clone(c.config||{})]));
  const once=D.documentFromFilePayload(clone(file));
  const twice=D.normalizeDocument(D.normalizeDocument(clone(once)));
  const view=d=>({points:Object.fromEntries(d.components.map(c=>[c.id,ids(c)])),arrays:Object.fromEntries(d.components.map(c=>[c.id,c.config.attachmentPoints??null])),modes:Object.fromEntries(d.components.map(c=>[c.id,c.config.attachmentDefaults??null])),wires:d.wires.map(w=>[w.id,w.aAttachment?.pointId,w.bAttachment?.pointId])});
  out.legacy={stored:Object.fromEntries(Object.entries(stored).map(([k,v])=>[k,v.attachmentPoints??null])),once:view(once),twice:view(twice),again:view(reload(twice)),valid:D.validateDocument(once)};
}

// Step 3 + 6: an edit that sets the complete list, stored in the smallest form.
{
  const d=doc0();mk(d,{id:'a',symbolId:'act',x:0,y:0});mk(d,{id:'b',symbolId:'act',x:400,y:0});
  const w=mkw(d,{id:'k1',a:'a',aSide:'out',b:'b',bSide:'in'});
  const r={wire:w.ok};
  // Additions under 'standard' keep the template: stored as additions only, channels normalized.
  r.add=upd(d,'a',{config:{attachmentPoints:[{id:'x',side:'bottom',t:.4,flow:'out'}]}});
  r.addStored={mode:d.components[0].config.attachmentDefaults??null,points:d.components[0].config.attachmentPoints,ids:ids(d.components[0])};
  // A complete list under 'none' that keeps every template port unchanged collapses to 'standard' + additions.
  r.full=upd(d,'a',{config:{attachmentDefaults:'none',attachmentPoints:[...JSON.parse(process.argv[3]),{id:'x',side:'bottom',t:.4,flow:'out'},{id:'y',side:'bottom',t:.8,flow:'in',label:'Y'}]}});
  r.fullStored={mode:d.components[0].config.attachmentDefaults??null,points:d.components[0].config.attachmentPoints,ids:ids(d.components[0])};
  // Removing a template port (top) that no Wire ends on: stored as 'none' + the full list, and reloads the same.
  r.remove=upd(d,'a',{config:{attachmentDefaults:'none',attachmentPoints:[{id:'left',compatId:'in',side:'left',t:.5,flow:'in'},{id:'right',compatId:'out',side:'right',t:.5,flow:'out'}]}});
  r.removeStored={mode:d.components[0].config.attachmentDefaults??null,points:d.components[0].config.attachmentPoints,ids:ids(d.components[0])};
  const saved=D.compactDocument(d);r.saved=saved.components.find(c=>c.id==='a').config;
  const back=reload(d);r.reloaded={ids:ids(back.components.find(c=>c.id==='a')),wire:[back.wires[0].aAttachment.pointId,back.wires[0].bAttachment.pointId],norm:ids(D.normalizeDocument(clone(back)).components.find(c=>c.id==='a'))};
  // Refusals: receipt not ok, revision and record unchanged.
  const before=JSON.stringify(d.components[0]),rev=d.revision;
  const refusals={
    dupId:[{id:'p',side:'left',t:.1,flow:'in'},{id:'p',side:'right',t:.1,flow:'out'}],
    badSide:[{id:'p',side:'middle',t:.1,flow:'in'}],
    badT:[{id:'p',side:'left',t:1.5,flow:'in'}],
    badFlow:[{id:'p',side:'left',t:.1,flow:'sideways'}],
    dupChannel:[{id:'p',side:'left',t:.1,flow:'in',channels:[{id:'c'},{id:'c'}]}],
    orphan:[{id:'left',compatId:'in',side:'left',t:.5,flow:'in'}]
  };
  r.refused={};
  for(const [k,list] of Object.entries(refusals)){const rc=upd(d,'a',{config:{attachmentDefaults:'none',attachmentPoints:list}});r.refused[k]={ok:rc.ok,msg:rc.error?.message||'',rev:rc.revisionAfter===rev&&d.revision===rev,same:JSON.stringify(d.components[0])===before}}
  out.edit=r;
}

// Step 3 + 7: five ports on four sides, two channels on one; channel matching on binding.
{
  const d=doc0();
  const five=[{id:'w',side:'left',t:.5,flow:'in'},{id:'e',side:'right',t:.5,flow:'out'},{id:'n',side:'top',t:.5,flow:'control'},{id:'s1',side:'bottom',t:.25,flow:'duplex',channels:[{id:'main'},{id:'aux'}]},{id:'s2',side:'bottom',t:.75,flow:'trigger',channels:[{id:'aux'}]}];
  mk(d,{id:'f',symbolId:'act',x:0,y:0});
  const set=upd(d,'f',{config:{attachmentDefaults:'none',attachmentPoints:five}});
  mk(d,{id:'g',symbolId:'act',x:400,y:0});
  const f=d.components.find(c=>c.id==='f');
  const r={set:set.ok,mode:f.config.attachmentDefaults,specs:specs(f),stored:f.config.attachmentPoints};
  r.mismatch=mkw(d,{id:'k1',a:'f',aAttachment:{pointId:'s2'},b:'g',bSide:'in'});
  r.shared=mkw(d,{id:'k2',a:'f',aAttachment:{pointId:'s1'},b:'g',bSide:'in'});
  r.sharedIds=D.sharedChannelIds(d,'f','s1','g','in');
  r.rebind=op(d,{op:'update',resource:'wire',resourceId:'k2',patch:{aAttachment:{kind:'attachment-ref',componentId:'f',pointId:'s2'}}});
  r.k2After=d.wires.find(w=>w.id==='k2').aAttachment.pointId;
  const free=D.makeWire(d,{id:'k3',aAttachment:{kind:'free',x:0,y:0},b:'g',bSide:'in'});d.wires.push(free);
  let bindErr='';try{D.bindWireEndpoint(d,free,'a','f','s2')}catch(e){bindErr=e.message}
  r.bindErr=bindErr;r.k3After=free.aAttachment;
  const bad=clone(D.compactDocument(d));bad.wires.push({id:'k9',a:'f',aSide:'s2',aAttachment:{kind:'attachment-ref',componentId:'f',pointId:'s2'},b:'g',bSide:'in'});
  r.validate=D.validateDocument(D.makeDocument(bad));
  out.channels=r;
}

// Steps 11-15 (amendment 2).
{
  const r={};
  const pair=()=>{const d=doc0();mk(d,{id:'a',symbolId:'act',x:0,y:0});mk(d,{id:'b',symbolId:'act',x:400,y:0});mkw(d,{id:'w',a:'a',aSide:'out',b:'b',bSide:'in'});return d};
  const trace=d=>({rev:d.revision,a:JSON.stringify(d.components.find(c=>c.id==='a'))});
  // Step 11: the review's reproduction.
  {const d=pair(),t0=trace(d);
   const rc=upd(d,'a',{config:{attachmentDefaults:'none',attachmentPoints:[{id:'right',compatId:'out',side:'right',t:.5,flow:'out',channels:[{id:'data'}]}]}});
   r.review={ok:rc.ok,msg:rc.error?.message||'',unchanged:JSON.stringify(trace(d))===JSON.stringify(t0),valid:D.validateDocument(reload(d)).ok,wire:[d.wires[0].aAttachment.pointId,d.wires[0].bAttachment.pointId]};
   // Both ends moved onto the channel together is accepted, and the save stays valid.
   const b1=upd(d,'b',{config:{attachmentPoints:[{id:'feed',side:'bottom',t:.5,flow:'in',channels:[{id:'data'},{id:'main'}]}]}});
   const w1=op(d,{op:'update',resource:'wire',resourceId:'w',patch:{bAttachment:{kind:'attachment-ref',componentId:'b',pointId:'feed'}}});
   const a1=upd(d,'a',{config:{attachmentDefaults:'none',attachmentPoints:[{id:'right',compatId:'out',side:'right',t:.5,flow:'out',channels:[{id:'data'}]}]}});
   const mis=upd(d,'b',{config:{attachmentPoints:[{id:'feed',side:'bottom',t:.5,flow:'in',channels:[{id:'main'}]}]}});
   r.accepted={b1:b1.ok,w1:w1.ok,a1:a1.ok,mis:mis.ok,misMsg:mis.error?.message||'',valid:D.validateDocument(reload(d)).ok,wire:[d.wires[0].aAttachment.pointId,d.wires[0].bAttachment.pointId]};}
  // Step 12: PORT_IN_USE whatever the edit's form.
  {const d=pair(),t0=trace(d),res={},bBefore=JSON.stringify(d.components.find(c=>c.id==='b'));
   // a ends on right/out, b on left/in. A Point's one port, self, answers to compat 'out' only,
   // so retyping b (on 'in') to a Point removes its port; a dimension change keeps a port by compat id.
   for(const [k,[id,patch]] of Object.entries({noneSwitch:['a',{config:{attachmentDefaults:'none'}}],retypePlane:['a',{symbolId:'plane'}],retypePoint:['b',{symbolId:'point'}]})){const rc=upd(d,id,patch);res[k]={ok:rc.ok,msg:rc.error?.message||''}}
   let thrown='';const a=d.components.find(c=>c.id==='a'),before=JSON.stringify(a);try{D.applySymbol(a,'plane',d)}catch(e){thrown=e.message}
   res.applySymbol={msg:thrown,unchanged:JSON.stringify(a)===before};
   res.unchanged=JSON.stringify(trace(d))===JSON.stringify(t0)&&JSON.stringify(d.components.find(c=>c.id==='b'))===bBefore;
   // A retype that keeps the port (another typed Component) and a dimension change that maps it by compat id are accepted.
   res.retypeGate=upd(d,'a',{symbolId:'gate'}).ok;
   res.valid=D.validateDocument(reload(d)).ok;
   r.inUse=res;}
  // Step 13 + 14 + 15: create validates and stores like update; order is kept; flow wins.
  {const d=doc0(),res={};
   res.dup=mk(d,{id:'x1',symbolId:'act',x:0,y:0,config:{attachmentPoints:[{id:'left',side:'left',t:.5,flow:'in'}]}});
   res.badFlow=mk(d,{id:'x2',symbolId:'act',x:0,y:0,config:{attachmentDefaults:'none',attachmentPoints:[{id:'p',side:'left',t:.5,flow:'nope'}]}});
   res.dupChannel=mk(d,{id:'x3',symbolId:'act',x:0,y:0,config:{attachmentPoints:[{id:'p',side:'left',t:.5,flow:'in',channels:[{id:'c'},{id:'c'}]}]}});
   const add=mk(d,{id:'c1',symbolId:'act',x:0,y:0,config:{attachmentPoints:[{id:'x',side:'bottom',t:.3,flow:'in',defaultFlow:'out'}]}});
   const c1=d.components.find(c=>c.id==='c1');
   res.add={ok:add.ok,mode:c1.config.attachmentDefaults??null,stored:c1.config.attachmentPoints,ids:ids(c1),flow:A.pointSpecs(c1).find(s=>s.id==='x').flow};
   const order=[{id:'top',compatId:'control',side:'top',t:.5,flow:'control'},{id:'left',compatId:'in',side:'left',t:.5,flow:'in'},{id:'right',compatId:'out',side:'right',t:.5,flow:'out'},{id:'x',side:'bottom',t:.5,flow:'duplex'}];
   const oc=mk(d,{id:'c2',symbolId:'act',x:0,y:0,config:{attachmentDefaults:'none',attachmentPoints:order}});
   const c2=d.components.find(c=>c.id==='c2');
   res.order={ok:oc.ok,mode:c2.config.attachmentDefaults,stored:c2.config.attachmentPoints.map(p=>p.id),ids:ids(c2)};
   const ou=upd(d,'c1',{config:{attachmentDefaults:'none',attachmentPoints:order}});
   res.orderUpdate={ok:ou.ok,mode:d.components.find(c=>c.id==='c1').config.attachmentDefaults,ids:ids(d.components.find(c=>c.id==='c1'))};
   const back=reload(d);res.reloaded={c1:ids(back.components.find(c=>c.id==='c1')),c2:ids(back.components.find(c=>c.id==='c2'))};
   // Stored list equals the effective list: under 'none' every stored entry is exposed, in order.
   res.storedIsEffective=[c1,c2].every(c=>c.config.attachmentDefaults!=='none'||JSON.stringify(c.config.attachmentPoints.map(p=>p.id))===JSON.stringify(ids(c)));
   // A legacy file entry with both flow and defaultFlow reads flow.
   const legacy=D.documentFromFilePayload({schema:D.DOCUMENT_SCHEMA,id:'f',revision:0,references:[],wires:[],components:[{id:'l',symbolId:'act',x:0,y:0,config:{attachmentPoints:[{id:'q',side:'bottom',t:.5,flow:'in',defaultFlow:'out'},{id:'r',side:'bottom',t:.7,defaultFlow:'out'}]}}]});
   res.legacyFlow=A.pointSpecs(legacy.components[0]).filter(s=>['q','r'].includes(s.id)).map(s=>s.flow);
   r.create=res;}
  out.amend=r;
}

// Steps 17-18 (amendment 3).
{
  const r={};
  const tmpl=new Set(['left','right','top']);
  const storedIds=c=>(c.config.attachmentPoints||[]).map(p=>p.id);
  const storedIsEffective=c=>c.config.attachmentDefaults==='none'?JSON.stringify(storedIds(c))===JSON.stringify(A.authoredPointSpecs(c).map(s=>s.id)):JSON.stringify(storedIds(c))===JSON.stringify(ids(c).filter(id=>!tmpl.has(id)));
  // Step 17, case 1: 'none' + [left, right, x] retyped to authority.
  {const d=doc0();mk(d,{id:'a',symbolId:'act',x:0,y:0,config:{attachmentDefaults:'none',attachmentPoints:[{id:'left',compatId:'in',side:'left',t:.5,flow:'in'},{id:'right',compatId:'out',side:'right',t:.5,flow:'out'},{id:'x',side:'bottom',t:.5,flow:'duplex'}]}});
   const rc=upd(d,'a',{symbolId:'authority'}),a=d.components[0];
   const again=upd(d,'a',{config:{attachmentPoints:clone(a.config.attachmentPoints||[])}});
   r.case1={ok:rc.ok,mode:a.config.attachmentDefaults??null,stored:storedIds(a),ids:ids(a),same:storedIsEffective(a),again:again.ok,againIds:ids(d.components[0])};
   // applySymbol directly (the bar retype) follows the same rule.
   const b=D.makeComponent(doc0(),{id:'b',symbolId:'act',x:0,y:0,config:{attachmentDefaults:'none',attachmentPoints:[{id:'left',compatId:'in',side:'left',t:.5,flow:'in'},{id:'x',side:'bottom',t:.5,flow:'duplex'}]}});
   D.applySymbol(b,'gate');r.case1apply={mode:b.config.attachmentDefaults??null,stored:storedIds(b),ids:ids(b)};}
  // Step 17, case 2: a Plane with an authored left on channel data, retyped to act, wired on that channel.
  {const d=doc0();mk(d,{id:'pl',symbolId:'plane',x:0,y:0,config:{attachmentPoints:[{id:'left',side:'left',t:.5,flow:'in',channels:[{id:'data'}]}]}});
   mk(d,{id:'src',symbolId:'act',x:-400,y:0,config:{attachmentPoints:[{id:'tx',side:'bottom',t:.5,flow:'out',channels:[{id:'data'}]}]}});
   const w=mkw(d,{id:'w',a:'src',aAttachment:{pointId:'tx'},b:'pl',bAttachment:{pointId:'left'}});
   const rc=upd(d,'pl',{symbolId:'act'}),pl=d.components.find(c=>c.id==='pl');
   r.case2={wire:w.ok,ok:rc.ok,msg:rc.error?.message||'',mode:pl.config.attachmentDefaults??null,stored:storedIds(pl),ids:ids(pl),left:A.pointSpecs(pl).find(s=>s.id==='left')?.channels,same:storedIsEffective(pl),valid:D.validateDocument(reload(d)).ok,bound:d.wires[0].bAttachment.pointId};}
  // Step 17: the Wire checks apply to a retype's port list.
  {const d=doc0();mk(d,{id:'pl',symbolId:'plane',x:0,y:0,config:{attachmentPoints:[{id:'feed',side:'left',t:.5,flow:'in',channels:[{id:'data'}]}]}});
   mk(d,{id:'src',symbolId:'act',x:-400,y:0,config:{attachmentPoints:[{id:'tx',side:'bottom',t:.5,flow:'out',channels:[{id:'data'}]}]}});
   mkw(d,{id:'w',a:'src',aAttachment:{pointId:'tx'},b:'pl',bAttachment:{pointId:'feed'}});
   const rc=upd(d,'src',{symbolId:'plane'});r.case2wire={ok:rc.ok,ids:ids(d.components.find(c=>c.id==='src'))};}
  // Step 18: seven lenient lists load, are cleaned, and paste (makeComponent from the loaded record).
  const lenient={
    stringT:[{id:'p',side:'bottom',t:'0.3',flow:'in'}],
    bigT:[{id:'p',side:'bottom',t:1.5,flow:'in'}],
    bareLeft:[{id:'left'}],
    badDefaultFlow:[{id:'p',side:'bottom',t:.5,defaultFlow:'sideways'}],
    noSide:[{id:'p',t:.5,flow:'in'}],
    dupIds:[{id:'p',side:'bottom',t:.2,flow:'in'},{id:'p',side:'top',t:.8,flow:'out'}],
    emptyChannels:[{id:'p',side:'bottom',t:.5,flow:'in',channels:[]}]
  };
  r.lenient={};
  for(const [k,list] of Object.entries(lenient)){
    const file={schema:D.DOCUMENT_SCHEMA,id:'len',revision:0,references:[],wires:[],components:[{id:'c',symbolId:'act',x:0,y:0,config:{attachmentPoints:list}}]};
    let loaded=null,err='';try{loaded=D.documentFromFilePayload(clone(file))}catch(e){err=e.message}
    const c=loaded?.components[0];
    const res={err,stored:c?.config.attachmentPoints??null,ids:c?ids(c):null,same:c?storedIsEffective(c):false,idempotent:c?JSON.stringify(D.normalizeDocument(clone(loaded)).components[0].config.attachmentPoints)===JSON.stringify(c.config.attachmentPoints):false};
    try{const v=clone(c);delete v.id;const pasted=D.makeComponent(loaded,v);res.paste={ok:true,ids:ids(pasted)}}catch(e){res.paste={ok:false,msg:e.message}}
    r.lenient[k]=res;
  }
  out.amend3=r;
}

// Issue #46: load cleaning never unbinds a Wire on an id/compat collision (step 1-2), and a
// retype never silently moves a bound Wire to a different port id (step 3).
{
  const r={};
  // The review's file: 'a' authors [{id:p,compatId:q,side:bottom},{id:q,compatId:r,side:top}];
  // the second entry's id collides with the first's compatId. It is kept as q~2, and Wire w
  // (bound by side 'r', a's compat id) stays bound to it, by compat id.
  {
    const file={schema:D.DOCUMENT_SCHEMA,id:'collide',revision:0,references:[],components:[
      {id:'a',symbolId:'act',x:0,y:0,config:{attachmentPoints:[{id:'p',compatId:'q',side:'bottom'},{id:'q',compatId:'r',side:'top'}]}},
      {id:'b',symbolId:'act',x:400,y:0}
    ],wires:[{id:'w',a:'a',aSide:'r',b:'b',bSide:'in'}]};
    const once=D.documentFromFilePayload(clone(file));
    const twice=D.normalizeDocument(D.normalizeDocument(clone(once)));
    const back=reload(once);
    const view=d=>{const a=d.components.find(c=>c.id==='a');return {ids:ids(a),stored:a.config.attachmentPoints,wire:[d.wires[0].aAttachment.pointId,d.wires[0].bAttachment.pointId,d.wires[0].aSide]}};
    r.review={once:view(once),twice:view(twice),back:view(back),valid:D.validateDocument(once).ok};
  }
  // A second collision variant: the Wire is bound by pointId to the collision's original id
  // ('q'), not by the surviving compat id. The load rebinds the pointId itself.
  {
    const file={schema:D.DOCUMENT_SCHEMA,id:'collide2',revision:0,references:[],components:[
      {id:'a',symbolId:'act',x:0,y:0,config:{attachmentPoints:[{id:'p',compatId:'q',side:'bottom'},{id:'q',compatId:'r',side:'top'}]}},
      {id:'b',symbolId:'act',x:400,y:0}
    ],wires:[{id:'w',a:'a',aAttachment:{pointId:'q'},b:'b',bSide:'in'}]};
    const once=D.documentFromFilePayload(clone(file));
    const twice=D.normalizeDocument(D.normalizeDocument(clone(once)));
    const view=d=>{const a=d.components.find(c=>c.id==='a');return {ids:ids(a),stored:a.config.attachmentPoints,wire:[d.wires[0].aAttachment.pointId,d.wires[0].bAttachment.pointId,d.wires[0].aSide]}};
    r.byPointId={once:view(once),twice:view(twice),valid:D.validateDocument(once).ok};
  }
  // A collision no Wire needs is still dropped, exactly as before (dupIds, step 18).
  {
    const file={schema:D.DOCUMENT_SCHEMA,id:'collide3',revision:0,references:[],wires:[],components:[
      {id:'a',symbolId:'act',x:0,y:0,config:{attachmentPoints:[{id:'p',compatId:'q',side:'bottom'},{id:'q',compatId:'r',side:'top'}]}}
    ]};
    const once=D.documentFromFilePayload(clone(file));
    r.noWireNeed={ids:ids(once.components[0]),stored:once.components[0].config.attachmentPoints};
  }
  // Step 3: a Plane authors {id:'in',side:'bottom'}; a Wire binds to it. Retyped to 'act', the
  // authored 'in' has no same-id template port and the Wire would move to 'left' by compat id
  // ('in' is left's compat), so the retype is refused.
  {
    const d=doc0();mk(d,{id:'pl',symbolId:'plane',x:0,y:0,config:{attachmentPoints:[{id:'in',side:'bottom',t:.5,flow:'in'}]}});
    mk(d,{id:'src',symbolId:'act',x:-400,y:0});
    mkw(d,{id:'w',a:'src',aSide:'out',b:'pl',bAttachment:{pointId:'in'}});
    const rc=upd(d,'pl',{symbolId:'act'});
    r.retypeRefused={ok:rc.ok,msg:rc.error?.message||'',ids:ids(d.components.find(c=>c.id==='pl')),wire:d.wires[0].bAttachment.pointId};
  }
  // The kept exception: a retype to a Point keeps a Wire on 'out' bound to 'self' - the one
  // case where a change of effective dimension may resolve by compat id.
  {
    const d=doc0();mk(d,{id:'a',symbolId:'act',x:0,y:0});mk(d,{id:'b',symbolId:'act',x:400,y:0});
    mkw(d,{id:'w',a:'a',aSide:'out',b:'b',bSide:'in'});
    const rc=upd(d,'a',{symbolId:'point'});
    r.pointException={ok:rc.ok,msg:rc.error?.message||'',ids:ids(d.components.find(c=>c.id==='a')),wire:d.wires[0].aAttachment.pointId};
  }
  // Contract #47, step 6: a Wire reference needs a renamed colliding copy only when it names no surviving
  // port's id. Two `a` entries and a Wire on bSide 'a': the Wire stays on the original `a`, the copy is dropped.
  {
    const file={schema:D.DOCUMENT_SCHEMA,id:'dupA',revision:0,references:[],components:[
      {id:'p',symbolId:'point',x:0,y:0},
      {id:'g',symbolId:'act',x:300,y:0,config:{attachmentDefaults:'none',attachmentPoints:[{id:'a',side:'left',t:.3,flow:'in'},{id:'q',side:'right',flow:'out'},{id:'a',side:'bottom',t:.5,flow:'in'}]}}
    ],wires:[{id:'w',a:'p',aSide:'self',b:'g',bSide:'a'},{id:'v',a:'p',aSide:'self',b:'g',bAttachment:{pointId:'a'}}]};
    const once=D.documentFromFilePayload(clone(file)),twice=reload(once);
    const view=d=>{const g=d.components.find(c=>c.id==='g');return {ids:ids(g),stored:g.config.attachmentPoints.map(x=>[x.id,x.side,x.t]),wires:d.wires.map(w=>[w.bAttachment.pointId,w.bSide])}};
    r.dupA={once:view(once),twice:view(twice),valid:D.validateDocument(once).ok};
    // The same on a template port: an authored `left` duplicates the template's; a Wire on `left` stays on the template port.
    const std={schema:D.DOCUMENT_SCHEMA,id:'dupLeft',revision:0,references:[],components:[
      {id:'p',symbolId:'point',x:0,y:0},{id:'g',symbolId:'act',x:300,y:0,config:{attachmentPoints:[{id:'left',side:'bottom',t:.5,flow:'in'}]}}
    ],wires:[{id:'w',a:'p',aSide:'self',b:'g',bAttachment:{pointId:'left'}}]};
    const loaded=D.documentFromFilePayload(clone(std)),g=loaded.components.find(c=>c.id==='g');
    r.dupLeft={ids:ids(g),stored:g.config.attachmentPoints??null,wire:[loaded.wires[0].bAttachment.pointId,loaded.wires[0].bSide],side:A.resolveSpec(g,loaded.wires[0].bAttachment.pointId).side};
  }
  out.followUps=r;
}

// Contract 0b-2, step 8 (#47 follow-up): the surviving set holds compat ids too. A Wire stored as
// `in` (the compat id of the template's `left`) beside an authored duplicate `in` stays on `left`;
// no `in~2` is made. A Wire naming `in` by pointId still names the authored entry by id (#46).
{
  const r={};
  const file=wire=>({schema:D.DOCUMENT_SCHEMA,id:'compatEdge',revision:0,references:[],components:[
    {id:'p',symbolId:'point',x:0,y:0},
    {id:'g',symbolId:'act',x:300,y:0,config:{attachmentPoints:[{id:'in',side:'bottom',t:.25,flow:'in'}]}}
  ],wires:[{id:'w',a:'p',aSide:'self',b:'g',...wire}]});
  const view=d=>{const g=d.components.find(c=>c.id==='g');return {ids:ids(g),stored:g.config.attachmentPoints??null,wire:[d.wires[0].bAttachment.pointId,d.wires[0].bSide],side:A.resolveSpec(g,d.wires[0].bAttachment.pointId).side}};
  for(const [key,wire] of Object.entries({side:{bSide:'in'},pointId:{bAttachment:{pointId:'in'}}})){
    const once=D.documentFromFilePayload(clone(file(wire))),twice=D.normalizeDocument(D.normalizeDocument(clone(once))),back=reload(once);
    r[key]={once:view(once),twice:view(twice),back:view(back),valid:D.validateDocument(once).ok};
  }
  out.compatEdge=r;
}

// Contract 0b-2, step 9: compactDocument output for every example is unchanged (hashes taken at f676563).
out.compactHashes={};
for(const file of JSON.parse(process.argv[5])){
  const raw=JSON.parse(fs.readFileSync(file,'utf8')),compact=D.compactDocument(D.documentFromFilePayload(raw));
  if(!(raw.document||raw).meta?.updatedAt&&compact.meta)delete compact.meta.updatedAt; // makeDocument stamps a missing one with now
  out.compactHashes[file]=globalThis.SovSchematicCanonical.sha256Hex(globalThis.SovSchematicCanonical.canonicalize(compact));
}

// Step 5 + 9: every example round-trips with the same port ids, bound ports and stored forms.
out.examples={};
for(const file of JSON.parse(process.argv[4])){
  const raw=JSON.parse(fs.readFileSync(file,'utf8')),rawDoc=raw.document||raw;
  const first=D.documentFromFilePayload(raw),saved=D.compactDocument(first),second=D.documentFromFilePayload(JSON.parse(JSON.stringify({...saved,schema:D.DOCUMENT_SCHEMA})));
  const pv=d=>({points:d.components.map(c=>[c.id,ids(c)]),wires:d.wires.map(w=>[w.id,w.aAttachment?.pointId??null,w.bAttachment?.pointId??null,w.aSide,w.bSide])});
  const stored=cs=>(cs||[]).map(c=>[c.id,c.config?.attachmentDefaults??null,c.config?.attachmentPoints??null]);
  out.examples[file]={first:pv(first),second:pv(second),raw:stored(rawDoc.components),saved:stored(saved.components),valid:D.validateDocument(first).ok};
}
console.log(JSON.stringify(out));
"""


# compactDocument(documentFromFilePayload(file)), canonicalized and hashed, as the code at f676563
# (before contract 0b-2) wrote it; contract 0b-2, step 9 keeps every one unchanged.
COMPACT_HASHES = {
    'examples/01-source-hold.sov': 'f84a33ba9687de18bcc2b4eec58318047102d7452f48d993dca61bc715141f0b',
    'examples/02-duplex-buffer.sov': 'a3514bf517c8bbce3f3db07e67af0f6dbc463b88ae799d2bb677d1186ccd810b',
    'examples/03-contained-stage.sov': '7ce534e8f8667c8607aeda6a2d43218c55960d22b65bd43f1e4e26cc4afac76e',
    'examples/04-boundary-port.sov': 'cb4b5855386a9134d6c760ad5f005d315b26b46ec25238a1af520624263ed771',
    'examples/05-rate-chain.sov': '15de44503e19699b89fffc09fb23643ba3c73e322063074901fad00b16c21e87',
    'examples/06-read-write-evidence.sov': 'a7421e628c6768a88486f8563357a4dbd1999942d03a0e0247123c1c600f8974',
    'examples/07-plane-with-points.sov': '2f1b0581d0023af090348c99f3068ef1f321b4bd81a38cb4387218ff05efd7cf',
    'examples/08-gated-service.sov': 'ed2e6c8878e672fb67c175b6c75d726fe5195879a6ede7a68cc09aaee28fc4a1',
    'examples/09-print-ai-proof-run.sov': '1df300a574a517cc0650283cfe3b9dada19c52ef9ec2898560ffb4a28d1516b8',
    'examples/09-proposed-service-review.sov': '24814d24173f6be4a4260f48986ee259b05b64ec896289511d27152d31f70296',
    'examples/10-clocked-signals.sov': 'a9a88907e855171c205d6fb221f96334eaf5b510e310585205c5b576e8646919',
    'examples/11-sections.sov': 'cf375a292c5d2f419fc581f5b49986ba968db8cb177441a42f8dec80885c92a0',
    'examples/12-membrane.sov': '1c6e3971833dd6dc65281a5e91c0e67f489005a139eb59d18292fb62455a642f',
    'examples/13-half-adder.sov': 'a3e71695182edee932682b330b472c4459b49f195603bc0f561c538c47da0a86',
    'examples/blank.sov': 'd2d0606caeaecb459544b398f92a7c3c80dc124822565db17a9886ed07581e2e',
    'examples/state/and.sov': '390703c8dd0b25a52cc09f2ccda372428af5e28c3b7a740af0273a0cb6b6479a',
    'examples/state/merge.or.sov': '3b684d32315c30c03201e36fd43519dc6dfbcc26e17b2feded411f01a2073cf8',
    'examples/state/merge.sov': '689afb77532fb9e25cc676458643f8348b7a3871a26894494517416bb2b749ed',
    'examples/state/merge.stochastic.sov': '66d44b0cdbe2208ab8e37aaa91a054101c3032115f3096fcbe7074f50e0235eb',
    'examples/state/not-loop.sov': '51b5caa23a859d91371ed13d3142284e9d89dd57a83f1df8e5c07054089b48bd',
    'examples/state/not.sov': '76331308e3a671751161c2cadf075da79dfc5a2ec0e2e0706afd6fc6e3b0aa05',
}


def typed_symbols() -> list[str]:
    text = (ROOT / 'src/00-state.js').read_text(encoding='utf-8')
    symbols = json.loads(re.search(r'const SYMBOLS = (\[.*?\]);\n', text).group(1))
    return [s['id'] for s in symbols if s['family'] != 'PRIMITIVE' and s['id'] != 'port']


def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def http_json(url, method='GET', payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = request.Request(url, data=body, method=method, headers={'content-type': 'application/json'})
    try:
        with request.urlopen(req, timeout=4) as res:
            return res.status, json.loads(res.read())
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def rpc(base, name, args=None, call_id=1):
    status, data = http_json(base + '/mcp', 'POST', {'jsonrpc': '2.0', 'id': call_id, 'method': 'tools/call', 'params': {'name': name, 'arguments': args or {}}})
    assert status == 200, (status, data)
    result = data['result']
    return result['structuredContent'], result.get('isError', False)


def main() -> None:
    # Step 1: no hard-coded 2D port set in the attachment core.
    src = (ROOT / 'src/06-attachment-core.js').read_text(encoding='utf-8')
    for literal in ("id:'left'", "id:'right'", "id:'top'"):
        assert literal not in src, literal
    alone = node(CORE_ALONE, str(ROOT / 'src/06-attachment-core.js'))
    assert alone['bare'] == [] and alone['authored'] == ['feed'], alone
    assert [s['id'] for s in alone['zero']] == ['self'] and [s['id'] for s in alone['one']] == ['start', 'end'], alone
    assert alone['zero'][0] == {'id': 'self', 'compatId': 'out', 'side': 'point', 'role': 'self', 'defaultFlow': 'duplex', 't': .5}, alone['zero']

    examples = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / 'examples').glob('*.sov'))
    assert examples, 'no examples'
    r = node(CORE, str(ROOT / 'src/05-data-core.js'), json.dumps(typed_symbols()), json.dumps(TRIO), json.dumps(examples), json.dumps(sorted(COMPACT_HASHES)))

    # Step 2: every typed template declares the trio; the Plane declares none.
    assert len(r['symbols']) >= 10, r['symbols']
    for sym, ports in r['templates'].items():
        assert ports == TRIO, (sym, ports)
    assert 'ports' not in r['planePreset'] and r['planePreset']['attachmentDefaults'] == 'none', r['planePreset']
    assert r['planeIds'] == [], r['planeIds']
    assert r['actSpecs'] == TRIO, r['actSpecs']

    # Step 4: legacy stored forms keep their meaning; normalization is idempotent and never
    # writes template ports into the stored array; every Wire stays bound to the same port.
    lg = r['legacy']
    assert lg['valid']['ok'], lg['valid']
    exp = {'plain': ['left', 'right', 'top'], 'std': ['left', 'right', 'top', 'aux'], 'imp': ['left', 'right', 'top', 'aux2'], 'non': ['only'], 'pls': ['left', 'right', 'top']}
    for key in ('once', 'twice', 'again'):
        assert lg[key]['points'] == exp, (key, lg[key]['points'])
        assert lg[key]['wires'] == [['k1', 'right', 'left'], ['k2', 'aux', 'only'], ['k3', 'aux2', 'top']], (key, lg[key]['wires'])
    # Loading rewrites each stored list into exactly its exposed authored ports (step 18), never the template's.
    main = [{'id': 'main'}]
    cleaned = {'plain': None, 'std': [{'id': 'aux', 'side': 'bottom', 't': .25, 'flow': 'duplex', 'channels': main}],
               'imp': [{'id': 'aux2', 'compatId': 'aux-2', 'side': 'bottom', 't': .75, 'flow': 'duplex', 'channels': main}],
               'non': [{'id': 'only', 'side': 'left', 't': .5, 'flow': 'in', 'channels': main}], 'pls': None}
    for key in ('once', 'twice'):
        assert lg[key]['arrays'] == cleaned, (key, lg[key]['arrays'])
    assert lg['once']['modes'] == lg['twice']['modes'] == {'plain': None, 'std': 'standard', 'imp': None, 'non': 'none', 'pls': 'standard'}, lg['once']['modes']
    assert lg['again']['modes']['pls'] == 'standard', lg['again']['modes']

    # Steps 3 + 6: edits stored in the smallest form; refusals leave no trace.
    ed = r['edit']
    assert ed['wire'] and ed['add']['ok'], ed
    assert ed['addStored'] == {'mode': None, 'points': [{'id': 'x', 'side': 'bottom', 't': .4, 'flow': 'out', 'channels': [{'id': 'main'}]}], 'ids': ['left', 'right', 'top', 'x']}, ed['addStored']
    assert ed['full']['ok'] and ed['fullStored']['mode'] is None, ed['fullStored']
    assert [p['id'] for p in ed['fullStored']['points']] == ['x', 'y'] and ed['fullStored']['ids'] == ['left', 'right', 'top', 'x', 'y'], ed['fullStored']
    assert ed['fullStored']['points'][1]['label'] == 'Y', ed['fullStored']
    assert ed['remove']['ok'] and ed['removeStored']['mode'] == 'none', ed['removeStored']
    assert [p['id'] for p in ed['removeStored']['points']] == ['left', 'right'] and ed['removeStored']['ids'] == ['left', 'right'], ed['removeStored']
    assert ed['saved']['attachmentDefaults'] == 'none' and [p['id'] for p in ed['saved']['attachmentPoints']] == ['left', 'right'], ed['saved']
    assert ed['reloaded'] == {'ids': ['left', 'right'], 'wire': ['right', 'left'], 'norm': ['left', 'right']}, ed['reloaded']
    for key, want in {'dupId': 'share the id', 'badSide': 'invalid side', 'badT': 'invalid t', 'badFlow': 'invalid flow', 'dupChannel': 'repeats channel', 'orphan': 'PORT_IN_USE'}.items():
        got = ed['refused'][key]
        assert got['ok'] is False and want in got['msg'] and got['rev'] and got['same'], (key, got)

    # Steps 3 + 7: five ports on four sides, two channels on one; channel matching on binding.
    ch = r['channels']
    assert ch['set'] and ch['mode'] == 'none', ch
    assert [(s['id'], s['side']) for s in ch['specs']] == [('w', 'left'), ('e', 'right'), ('n', 'top'), ('s1', 'bottom'), ('s2', 'bottom')], ch['specs']
    assert {s['side'] for s in ch['specs']} == {'left', 'right', 'top', 'bottom'}
    assert ch['specs'][3]['channels'] == [{'id': 'main'}, {'id': 'aux'}] and ch['specs'][0]['channels'] == [{'id': 'main'}], ch['specs']
    assert all('channels' in p for p in ch['stored']), ch['stored']
    assert ch['mismatch']['ok'] is False and 'CHANNEL_MISMATCH' in ch['mismatch']['error']['message'], ch['mismatch']
    assert ch['shared']['ok'] and ch['sharedIds'] == ['main'], (ch['shared'], ch['sharedIds'])
    assert ch['rebind']['ok'] is False and 'CHANNEL_MISMATCH' in ch['rebind']['error']['message'] and ch['k2After'] == 's1', ch
    assert 'CHANNEL_MISMATCH' in ch['bindErr'] and ch['k3After']['kind'] == 'free', ch
    assert not ch['validate']['ok'] and any('k9' in e and 'CHANNEL_MISMATCH' in e for e in ch['validate']['errors']), ch['validate']

    # Amendment 2, step 11: an edit that leaves a Wire between ports sharing no channel is refused.
    am = r['amend']
    rv = am['review']
    assert rv['ok'] is False and 'CHANNEL_MISMATCH' in rv['msg'] and rv['unchanged'] and rv['valid'] and rv['wire'] == ['right', 'left'], rv
    ac = am['accepted']
    assert ac['b1'] and ac['w1'] and ac['a1'] and ac['valid'] and ac['wire'] == ['right', 'feed'], ac
    assert ac['mis'] is False and 'CHANNEL_MISMATCH' in ac['misMsg'], ac
    # Step 12: PORT_IN_USE for the 'none' switch, a retype by update, and applySymbol with the document.
    iu = am['inUse']
    for key in ('noneSwitch', 'retypePlane', 'retypePoint'):
        assert iu[key]['ok'] is False and 'PORT_IN_USE' in iu[key]['msg'], (key, iu[key])
    assert 'PORT_IN_USE' in iu['applySymbol']['msg'] and iu['applySymbol']['unchanged'] and iu['unchanged'], iu
    assert iu['retypeGate'] and iu['valid'], iu
    # Steps 13-15: create validates and stores like update; order is kept; flow wins over defaultFlow.
    cr = am['create']
    for key, want in (('dup', 'share the id'), ('badFlow', 'invalid flow'), ('dupChannel', 'repeats channel')):
        assert cr[key]['ok'] is False and want in cr[key]['error']['message'], (key, cr[key])
    assert cr['add'] == {'ok': True, 'mode': None, 'stored': [{'id': 'x', 'side': 'bottom', 't': .3, 'flow': 'in', 'channels': [{'id': 'main'}]}], 'ids': ['left', 'right', 'top', 'x'], 'flow': 'in'}, cr['add']
    assert cr['order'] == {'ok': True, 'mode': 'none', 'stored': ['top', 'left', 'right', 'x'], 'ids': ['top', 'left', 'right', 'x']}, cr['order']
    assert cr['orderUpdate'] == {'ok': True, 'mode': 'none', 'ids': ['top', 'left', 'right', 'x']}, cr['orderUpdate']
    assert cr['reloaded'] == {'c1': ['top', 'left', 'right', 'x'], 'c2': ['top', 'left', 'right', 'x']}, cr['reloaded']
    assert cr['storedIsEffective'], cr
    assert cr['legacyFlow'] == ['in', 'out'], cr['legacyFlow']

    # Amendment 3, step 17: a retype keeps stored = effective and keeps authored channels.
    a3 = r['amend3']
    c1 = a3['case1']
    assert c1 == {'ok': True, 'mode': None, 'stored': ['x'], 'ids': ['left', 'right', 'top', 'x'], 'same': True, 'again': True, 'againIds': ['left', 'right', 'top', 'x']}, c1
    assert a3['case1apply'] == {'mode': None, 'stored': ['x'], 'ids': ['left', 'right', 'top', 'x']}, a3['case1apply']
    c2 = a3['case2']
    assert c2['wire'] and c2['ok'] and c2['mode'] == 'none' and c2['stored'] == ['left', 'right', 'top'] and c2['ids'] == ['left', 'right', 'top'], c2
    assert c2['left'] == [{'id': 'data'}] and c2['same'] and c2['valid'] and c2['bound'] == 'left', c2
    assert a3['case2wire']['ok'] is True and a3['case2wire']['ids'] == ['tx'], a3['case2wire']  # a Plane keeps the authored port
    # Step 18: each lenient list loads, is cleaned into exactly its exposed ports, and pastes.
    m = [{'id': 'main'}]
    want = {
        'stringT': [{'id': 'p', 'side': 'bottom', 't': .3, 'flow': 'in', 'channels': m}],
        'bigT': [{'id': 'p', 'side': 'bottom', 't': 1, 'flow': 'in', 'channels': m}],
        'bareLeft': [],
        'badDefaultFlow': [{'id': 'p', 'side': 'bottom', 't': .5, 'flow': 'duplex', 'channels': m}],
        'noSide': [],
        'dupIds': [{'id': 'p', 'side': 'bottom', 't': .2, 'flow': 'in', 'channels': m}],
        'emptyChannels': [{'id': 'p', 'side': 'bottom', 't': .5, 'flow': 'in', 'channels': m}],
    }
    for key, stored in want.items():
        got = a3['lenient'][key]
        assert got['err'] == '' and got['stored'] == stored and got['same'] and got['idempotent'], (key, got)
        exp_ids = ['left', 'right', 'top'] + [p['id'] for p in stored]
        assert got['ids'] == exp_ids and got['paste'] == {'ok': True, 'ids': exp_ids}, (key, got)

    # Issue #46, steps 1-2: load cleaning never unbinds a Wire on an id/compat collision.
    fu = r['followUps']
    collided = {
        'ids': ['left', 'right', 'top', 'p', 'q~2'],
        'stored': [
            {'id': 'p', 'compatId': 'q', 'side': 'bottom', 't': .5, 'flow': 'duplex', 'channels': m},
            {'id': 'q~2', 'compatId': 'r', 'side': 'top', 't': .5, 'flow': 'duplex', 'channels': m},
        ],
        'wire': ['q~2', 'left', 'r'],
    }
    rv = fu['review']
    for key in ('once', 'twice', 'back'):
        assert rv[key] == collided, (key, rv[key])
    assert rv['valid'], rv
    bp = fu['byPointId']
    for key in ('once', 'twice'):
        assert bp[key] == collided, (key, bp[key])
    assert bp['valid'], bp
    assert fu['noWireNeed'] == {'ids': ['left', 'right', 'top', 'p'], 'stored': [{'id': 'p', 'compatId': 'q', 'side': 'bottom', 't': .5, 'flow': 'duplex', 'channels': m}]}, fu['noWireNeed']

    # Contract #47, step 6: a Wire on a duplicated id stays on the surviving port; the copy is dropped.
    want_dup = {'ids': ['a', 'q'], 'stored': [['a', 'left', .3], ['q', 'right', .5]], 'wires': [['a', 'a'], ['a', 'a']]}
    assert fu['dupA']['once'] == want_dup and fu['dupA']['twice'] == want_dup and fu['dupA']['valid'], fu['dupA']
    assert fu['dupLeft'] == {'ids': ['left', 'right', 'top'], 'stored': [], 'wire': ['left', 'in'], 'side': 'left'}, fu['dupLeft']

    # Issue #46, step 3: a retype that would move a bound Wire to a different port id is
    # refused; a retype to a Point keeping a Wire on out->self is the one kept exception.
    rr = fu['retypeRefused']
    assert rr['ok'] is False and 'PORT_IN_USE' in rr['msg'] and 'would move' in rr['msg'] and rr['ids'] == ['in'] and rr['wire'] == 'in', rr
    pe = fu['pointException']
    assert pe['ok'] is True and pe['msg'] == '' and pe['ids'] == ['self'] and pe['wire'] == 'self', pe

    # Contract 0b-2, step 8: a Wire stored as `in` stays on the template's `left`; no `in~2`.
    ce = r['compatEdge']
    on_left = {'ids': ['left', 'right', 'top', 'in~2'], 'stored': [{'id': 'in~2', 'side': 'bottom', 't': .25, 'flow': 'in', 'channels': m}], 'wire': ['in~2', 'in~2'], 'side': 'bottom'}
    stays = {'ids': ['left', 'right', 'top'], 'stored': [], 'wire': ['left', 'in'], 'side': 'left'}
    for key in ('once', 'twice', 'back'):
        # Saving drops the emptied list, so the reloaded record has none.
        assert ce['side'][key] == ({**stays, 'stored': None} if key == 'back' else stays), (key, ce['side'][key])
        # By pointId the reference names the authored entry's id, which #46 keeps under a fresh id.
        assert ce['pointId'][key] == on_left, (key, ce['pointId'][key])
    assert ce['side']['valid'] and ce['pointId']['valid'], ce

    # Contract 0b-2, step 9: compactDocument output for every example is unchanged.
    assert set(COMPACT_HASHES) >= set(examples), sorted(set(examples) - set(COMPACT_HASHES))
    assert r['compactHashes'] == COMPACT_HASHES, {k: v for k, v in r['compactHashes'].items() if COMPACT_HASHES.get(k) != v}

    # Steps 5 + 9: every example round-trips unchanged; stored forms are saved as authored.
    for file, ex in r['examples'].items():
        assert ex['valid'], file
        assert ex['first'] == ex['second'], (file, ex['first'], ex['second'])
        assert ex['saved'] == ex['raw'], (file, ex['saved'], ex['raw'])
        assert all(w[1] and w[2] for w in ex['first']['wires']), (file, ex['first']['wires'])

    # Step 6 over HTTP and MCP: the same refusal, no revision, no history entry.
    with tempfile.TemporaryDirectory() as td:
        port = free_port()
        base = f'http://127.0.0.1:{port}'
        proc = subprocess.Popen(['node', str(ROOT / 'mcp/server.mjs'), '--port', str(port), '--file', str(Path(td) / 'ports.sov')], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            for _ in range(80):
                try:
                    if http_json(base + '/api/v1/formats')[0] == 200:
                        break
                except Exception:
                    time.sleep(.05)
            else:
                raise AssertionError('server did not start')
            assert http_json(base + '/api/v1/components', 'POST', {'id': 'a', 'symbolId': 'act', 'x': 0, 'y': 0})[0] == 201
            assert http_json(base + '/api/v1/components', 'POST', {'id': 'b', 'symbolId': 'act', 'x': 400, 'y': 0})[0] == 201
            status, wire = http_json(base + '/api/v1/wires', 'POST', {'id': 'k1', 'a': 'a', 'aSide': 'out', 'b': 'b', 'bSide': 'in'})
            assert status == 201 and wire['ok'], wire
            rev = wire['revisionAfter']
            orphan = {'config': {'attachmentDefaults': 'none', 'attachmentPoints': [{'id': 'left', 'compatId': 'in', 'side': 'left', 't': .5, 'flow': 'in'}]}}
            status, denied = http_json(base + '/api/v1/components/a', 'PATCH', orphan)
            assert status == 400 and not denied['ok'] and 'PORT_IN_USE' in denied['error']['message'] and denied['revisionAfter'] == rev, denied
            mcp, is_error = rpc(base, 'schematic.update', {'resource': 'component', 'id': 'a', 'patch': orphan}, 2)
            assert is_error and not mcp['ok'] and 'PORT_IN_USE' in mcp['error']['message'] and mcp['revisionAfter'] == rev, mcp
            status, mismatch = http_json(base + '/api/v1/components/b', 'PATCH', {'config': {'attachmentPoints': [{'id': 'q', 'side': 'bottom', 't': .5, 'flow': 'in', 'channels': [{'id': 'aux'}]}]}})
            assert status == 200 and mismatch['ok'], mismatch
            status, refused = http_json(base + '/api/v1/wires', 'POST', {'id': 'k2', 'a': 'a', 'aSide': 'out', 'b': 'b', 'bAttachment': {'pointId': 'q'}})
            assert status == 400 and 'CHANNEL_MISMATCH' in refused['error']['message'], refused
            # The refusals entered no history: undo reverts the last successful edit (b's ports), then the Wire.
            undo, is_error = rpc(base, 'schematic.history.undo', {}, 3)
            assert not is_error and not any(p.get('id') == 'q' for c in undo['components'] for p in (c.get('config', {}).get('attachmentPoints') or [])), undo
            assert any(w['id'] == 'k1' for w in undo['wires']), undo
            undo, is_error = rpc(base, 'schematic.history.undo', {}, 4)
            assert not is_error and not undo['wires'], undo
        finally:
            proc.terminate()
            proc.wait(timeout=5)
    print('PASS declared ports QA')


if __name__ == '__main__':
    main()
