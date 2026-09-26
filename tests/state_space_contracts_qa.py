"""State space contracts (slice 1a of STATE-SPACE.md, issue #43).

The contract layer only: the state record envelope, the pattern registry (truth_table@1 and
merge@1), definitions and packs with generated contracts, ports generated from a bound
definition, channel `merge` and Wire `config.delay` stored through the data core, and the
load checks. No ledger, tick or run. Node for the cores, the HTTP/MCP server, and the
browser API adapter for the refusal parity.
"""
from __future__ import annotations
import json
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]

CORE = r"""
const S=require(process.argv[1]),D=globalThis.SovSchematicData,C=globalThis.SovSchematicCanonical,fs=require('fs');
const clone=x=>JSON.parse(JSON.stringify(x));
const out={};
const packJson=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const loaded=S.loadPack(clone(packJson));
out.pack={ok:loaded.ok,errors:loaded.errors,defs:(loaded.pack?.definitions||[]).map(d=>[d.id,d.version,d.pattern,d.delay,d.parameters.inputs,d.parameters.outputs]),id:loaded.pack?.id,version:loaded.pack?.version};
const packs=[loaded.pack];

// Step 2: the state record.
const good={format:'soveraeign.schematic/state-record@0.1',id:'sr-000017',subject:{entity:'c-and1',point:'q',run:'run-1'},vantage:'point',observable:'logic.level',kind:'derived',form:'binary',value:true,time:{logical:4,sequence:17,mode:'observed'},certainty:{kind:'exact'},observer:'rule:logic.and@1',provenance:{rule:'logic.and@1',inputs:['sr-000012','sr-000015']},perturbation:'none'};
const variant=f=>{const r=clone(good);f(r);return r};
out.record={good:S.validateRecord(good),full:S.validateRecord(variant(r=>{r.subject.channel='main';r.subject.attempt=0;r.vantage='relative';r.reference='baseline';r.form='continuous';r.value=0.5;r.kind='measured';r.time.mode='predicted';r.perturbation='created'})),categorical:S.validateRecord(variant(r=>{r.form='categorical';r.value='high'}))};
const bad={
  format:r=>{r.format='soveraeign.schematic/state-record@0.2'},
  id:r=>{r.id=''},
  subjectMissing:r=>{delete r.subject},
  entity:r=>{r.subject.entity=''},
  run:r=>{delete r.subject.run},
  point:r=>{r.subject.point=''},
  channel:r=>{r.subject.channel=3},
  attempt:r=>{r.subject.attempt=-1},
  attemptFraction:r=>{r.subject.attempt=1.5},
  vantage:r=>{r.vantage='lagrangian'},
  referenceMissing:r=>{r.vantage='relative'},
  referenceForbidden:r=>{r.reference='baseline'},
  observable:r=>{r.observable=''},
  kind:r=>{r.kind='estimated'},
  form:r=>{r.form='vector'},
  binaryValue:r=>{r.value=1},
  continuousValue:r=>{r.form='continuous';r.value='1'},
  continuousInfinite:r=>{r.form='continuous';r.value=Infinity},
  categoricalValue:r=>{r.form='categorical';r.value=true},
  timeMissing:r=>{delete r.time},
  logical:r=>{r.time.logical=-1},
  sequence:r=>{r.time.sequence=1.5},
  mode:r=>{r.time.mode='wall'},
  certainty:r=>{r.certainty={kind:'gum'}},
  observer:r=>{r.observer=''},
  provenanceRule:r=>{r.provenance.rule=''},
  provenanceInputs:r=>{r.provenance.inputs=['sr-1','']},
  provenanceInputsType:r=>{r.provenance.inputs='sr-1'},
  perturbation:r=>{r.perturbation='maybe'},
  extraTop:r=>{r.quality='good'},
  extraSubject:r=>{r.subject.region='x'},
  extraTime:r=>{r.time.wall='2026-09-25'},
  extraCertainty:r=>{r.certainty.u=0.1},
  extraProvenance:r=>{r.provenance.seed=7}
};
out.recordBad={};for(const [k,f] of Object.entries(bad))out.recordBad[k]=S.validateRecord(variant(f));

// Step 3: the pattern registry.
out.patterns=S.patterns().map(p=>({id:p.id,version:p.version,class:p.class,stateful:p.stateful,blastRadius:p.blastRadius,validate:typeof p.validate,derive:typeof p.derive}));
out.patternLookup={tt:S.pattern('truth_table@1')?.id||null,merge:S.pattern('merge@1')?.id||null,missing:S.pattern('truth_table@2'),bare:S.pattern('merge')};
const tt=S.pattern('truth_table@1'),mg=S.pattern('merge@1');
// Every core.logic definition validates; evaluate over every row of every table.
out.defs={};
for(const d of loaded.pack.definitions){
  const rows=d.parameters.table.map(row=>{const n=d.parameters.inputs.length,ins={};d.parameters.inputs.forEach((name,i)=>{ins[name]=row[i]===1});const got=tt.evaluate(d.parameters,ins),want={};d.parameters.outputs.forEach((name,i)=>{want[name]=row[n+i]===1});return {ins,got,want}});
  out.defs[`${d.id}@${d.version}`]={check:S.checkDefinition(d),validate:tt.validate(d.parameters),rows};
}
out.contractAnd=C.canonicalize(S.contractOf(S.resolveDefinition('logic.and@1',packs)));
out.derivedAnd=tt.derive(S.resolveDefinition('logic.and@1',packs).parameters);
out.resolve={and:S.resolveDefinition('logic.and@1',packs)?.id||null,v2:S.resolveDefinition('logic.and@2',packs),nand:S.resolveDefinition('logic.nand@1',packs)};
const andP=S.resolveDefinition('logic.and@1',packs).parameters;
const ttBad={
  missingRow:{...andP,table:andP.table.slice(0,3)},
  duplicateRow:{...andP,table:[...andP.table.slice(0,3),[0,0,1]]},
  wrongWidth:{...andP,table:andP.table.map((r,i)=>i===1?r.slice(0,2):r)},
  notBit:{...andP,table:andP.table.map((r,i)=>i===2?[1,0,2]:r)},
  notBitBool:{...andP,table:andP.table.map((r,i)=>i===2?[true,false,false]:r)},
  duplicateName:{...andP,inputs:['a','a']},
  overlap:{...andP,outputs:['a']},
  badName:{...andP,inputs:['A','b']},
  tooMany:{inputs:['a','b','c','d','e','f','g','h','i'],outputs:['q'],table:[]},
  noOutputs:{...andP,outputs:[]},
  extraKey:{...andP,delay:1}
};
out.ttBad={};for(const [k,p] of Object.entries(ttBad))out.ttBad[k]=tt.validate(p);
// A stated derived member that differs is CONTRACT_MISMATCH; the same stated is accepted; unknown keys refused.
const andDef=S.resolveDefinition('logic.and@1',packs);
const derived=tt.derive(andDef.parameters);
const statedSame={...clone(andDef),...clone(derived)};
const statedDiff={...clone(andDef),outputs:[{...derived.outputs[0],id:'y'}]};
const statedFlow={...clone(andDef),inputs:derived.inputs.map(p=>({...p,flow:'duplex'}))};
out.stated={same:S.checkDefinition(statedSame),diff:S.checkDefinition(statedDiff),flow:S.checkDefinition(statedFlow),
  unknownKey:S.checkDefinition({...clone(andDef),behaviour:'x'}),
  unknownPattern:S.checkDefinition({...clone(andDef),pattern:'truth_table@9'}),
  badParams:S.checkDefinition({...clone(andDef),parameters:ttBad.missingRow}),
  badDelay:S.checkDefinition({...clone(andDef),delay:-1}),
  badVersion:S.checkDefinition({...clone(andDef),version:0}),
  badPorts:S.checkDefinition({...clone(andDef),ports:{a:{side:'middle',t:.5}}}),
  strangerPort:S.checkDefinition({...clone(andDef),ports:{z:{side:'left',t:.5}}})};
const packOf=defs=>({format:'soveraeign.schematic/pack@0.1',id:'t',version:1,definitions:defs});
out.packs={diff:S.loadPack(packOf([statedDiff])),same:S.loadPack(packOf([statedSame])),unknownKey:S.loadPack({...packOf([]),extra:1}),format:S.loadPack({...packOf([]),format:'soveraeign.schematic/pack@9'}),missingId:S.loadPack({format:'soveraeign.schematic/pack@0.1',version:1,definitions:[]}),dup:S.loadPack(packOf([clone(andDef),clone(andDef)])),notObject:S.loadPack(null)};
// contractOf placement from `ports`.
const placedDef={...clone(andDef),ports:{q:{side:'bottom',t:.25,label:'Q'}}};
out.placed=S.contractOf(placedDef);

// merge@1 for every combine.
out.merge={};
for(const combine of ['or','and','min','max','sum','first','last','queue']){
  out.merge[combine]={bare:mg.validate({combine}),derive:mg.validate({combine}).length?null:mg.derive({combine}),
    declared:mg.validate({combine,order:{kind:'declared',paths:['w1','w2']}}),stochastic:mg.validate({combine,order:{kind:'stochastic'}}),observed:mg.validate({combine,order:{kind:'observed'}}),
    deriveDeclared:mg.validate({combine,order:{kind:'declared',paths:['w1','w2']}}).length?null:mg.derive({combine,order:{kind:'declared',paths:['w1','w2']}})};
}
out.mergeBad={combine:mg.validate({combine:'avg'}),missing:mg.validate({}),extra:mg.validate({combine:'last',priority:1}),kind:mg.validate({combine:'last',order:{kind:'random'}}),emptyPaths:mg.validate({combine:'last',order:{kind:'declared',paths:[]}}),dupPaths:mg.validate({combine:'last',order:{kind:'declared',paths:['w1','w1']}}),blankPath:mg.validate({combine:'last',order:{kind:'declared',paths:['']}}),pathsOnStochastic:mg.validate({combine:'last',order:{kind:'stochastic',paths:['w1']}}),notObject:mg.validate('last')};

// Steps 4 + 5: a channel merge and a Wire delay round-trip through save and reload.
const op=(doc,o)=>D.applyOperation(doc,o);
const upd=(doc,id,patch,resource='component')=>op(doc,{op:'update',resource,resourceId:id,patch});
const mk=(doc,value)=>op(doc,{op:'create',resource:'component',value});
const mkw=(doc,value)=>op(doc,{op:'create',resource:'wire',value});
const reload=doc=>D.documentFromFilePayload(JSON.parse(JSON.stringify(D.compactDocument(doc))));
{
  const d=D.makeDocument({id:'rt'});
  mk(d,{id:'s1',symbolId:'point',x:0,y:0});mk(d,{id:'s2',symbolId:'point',x:0,y:200});
  const mergeChannel={id:'main',merge:{combine:'last',order:{kind:'declared',paths:['w1','w2']}}};
  const created=mk(d,{id:'g',symbolId:'act',x:300,y:100,config:{attachmentDefaults:'none',attachmentPoints:[{id:'in',side:'left',t:.5,flow:'in',channels:[mergeChannel]},{id:'out',side:'right',t:.5,flow:'out'}]}});
  const w1=mkw(d,{id:'w1',a:'s1',aSide:'self',b:'g',bAttachment:{pointId:'in'},config:{delay:3}});
  const w2=mkw(d,{id:'w2',a:'s2',aSide:'self',b:'g',bAttachment:{pointId:'in'}});
  const saved=D.compactDocument(d),back=reload(d),again=D.compactDocument(D.normalizeDocument(clone(back)));
  const gOf=doc=>doc.components.find(c=>c.id==='g').config.attachmentPoints;
  const wOf=(doc,id)=>doc.wires.find(w=>w.id===id).config;
  const stored=clone(gOf(d));
  // An update that sets the merge on an existing port, and a delay by wire update.
  const upMerge=upd(d,'g',{config:{attachmentPoints:[{id:'in',side:'left',t:.5,flow:'in',channels:[{id:'main',merge:{combine:'sum'}}]},{id:'out',side:'right',t:.5,flow:'out'}]}});
  const upDelay=upd(d,'w2',{config:{delay:2}},'wire');
  const back2=reload(d);
  out.roundtrip={created:created.ok,w1:w1.ok,w2:w2.ok,stored,saved:gOf(saved),reloaded:gOf(back),again:gOf(again),delaySaved:[wOf(saved,'w1').delay??null,wOf(saved,'w2').delay??null],delayReloaded:[wOf(back,'w1').delay??null,'delay' in wOf(back,'w2')],
    upMerge:upMerge.ok,upDelay:upDelay.ok,after:gOf(back2),afterDelay:wOf(back2,'w2').delay??null,
    specChannels:globalThis.SovSchematicAttachment.pointSpecs(back.components.find(c=>c.id==='g')).find(s=>s.id==='in').channels,
    check:S.checkDocument(back,packs)};
  // A channel without merge stores {id} only; a Wire without delay writes none.
  out.plain={channels:saved.components.find(c=>c.id==='g').config.attachmentPoints[1].channels,noDelay:!('delay' in wOf(saved,'w2'))};
  // Invalid merge updates are refused: receipt not ok, revision and record unchanged.
  const rev=d.revision,before=JSON.stringify(d.components.find(c=>c.id==='g'));
  const invalid={orderOnFree:{combine:'sum',order:{kind:'stochastic'}},unknownCombine:{combine:'avg'},emptyPaths:{combine:'last',order:{kind:'declared',paths:[]}},extraKey:{combine:'last',weight:2}};
  out.mergeRefused={};
  for(const [k,m] of Object.entries(invalid)){
    const rc=upd(d,'g',{config:{attachmentPoints:[{id:'in',side:'left',t:.5,flow:'in',channels:[{id:'main',merge:m}]},{id:'out',side:'right',t:.5,flow:'out'}]}});
    out.mergeRefused[k]={ok:rc.ok,msg:rc.error?.message||'',rev:rc.revisionAfter===rev&&d.revision===rev,same:JSON.stringify(d.components.find(c=>c.id==='g'))===before};
  }
  const cr=mk(d,{id:'h',symbolId:'act',x:0,y:0,config:{attachmentPoints:[{id:'x',side:'bottom',t:.5,flow:'in',channels:[{id:'main',merge:{combine:'avg'}}]}]}});
  out.mergeRefused.create={ok:cr.ok,msg:cr.error?.message||''};
}

// Step 8: binding a definition.
{
  const d=D.makeDocument({id:'bind'});
  mk(d,{id:'g',symbolId:'act',x:300,y:100});
  const op1=S.bindDefinition(d,'g','logic.and@1',packs);
  const rc=S.applyBind(d,'g','logic.and@1',packs);
  const g=d.components.find(c=>c.id==='g');
  const A=globalThis.SovSchematicAttachment;
  out.bind={op:op1,ok:rc.ok,msg:rc.error?.message||'',definition:g.config.definition,mode:g.config.attachmentDefaults,stored:g.config.attachmentPoints,specs:A.pointSpecs(g).map(s=>({id:s.id,side:s.side,t:s.t,flow:s.flow,channels:s.channels})),check:S.checkDocument(d,packs),reloaded:reload(d).components.find(c=>c.id==='g').config};
  out.unresolved=S.bindDefinition(d,'g','logic.nand@1',packs);
  // PORT_IN_USE: a Wire ends on `top`, which logic.and@1 does not have.
  const e=D.makeDocument({id:'inuse'});
  mk(e,{id:'g',symbolId:'act',x:300,y:100});mk(e,{id:'s',symbolId:'act',x:0,y:100});
  const w=mkw(e,{id:'w',a:'s',aSide:'out',b:'g',bSide:'control'});
  const rev=e.revision,before=JSON.stringify(e.components.find(c=>c.id==='g'));
  const rc2=S.applyBind(e,'g','logic.and@1',packs);
  out.inUse={wire:w.ok,bound:e.wires[0].bAttachment.pointId,ok:rc2.ok,msg:rc2.error?.message||'',rev:e.revision===rev,same:JSON.stringify(e.components.find(c=>c.id==='g'))===before};
}

// Step 9: one crafted document per checkDocument code, and a valid A AND B -> Q.
{
  const base=()=>{const d=D.makeDocument({id:'q'});mk(d,{id:'pa',symbolId:'point',x:0,y:0});mk(d,{id:'pb',symbolId:'point',x:0,y:200});mk(d,{id:'g',symbolId:'act',x:300,y:100});mk(d,{id:'pq',symbolId:'point',x:600,y:100});return d};
  const valid=base();
  const bound=S.applyBind(valid,'g','logic.and@1',packs);
  const wires=[mkw(valid,{id:'wa',a:'pa',aSide:'self',b:'g',bAttachment:{pointId:'a'}}),mkw(valid,{id:'wb',a:'pb',aSide:'self',b:'g',bAttachment:{pointId:'b'}}),mkw(valid,{id:'wq',a:'g',aAttachment:{pointId:'q'},b:'pq',bSide:'self'})];
  const validDoc=reload(valid);
  const snapshot=JSON.stringify(validDoc);
  out.valid={bound:bound.ok,wires:wires.map(w=>w.ok),check:S.checkDocument(validDoc,packs),unmutated:JSON.stringify(validDoc)===snapshot,noPacks:S.checkDocument(validDoc,[])};
  const crafted={};
  // PATH_DELAY_INVALID: delay 0 on an otherwise valid Wire.
  {const d=reload(valid);d.wires[0].config.delay=0;crafted.PATH_DELAY_INVALID=d}
  // PATH_DIRECTION_FLOW: a forward Wire from an input port to an output port.
  {const d=D.makeDocument({id:'dir'});mk(d,{id:'a',symbolId:'act',x:0,y:0});mk(d,{id:'b',symbolId:'act',x:400,y:0});mkw(d,{id:'k',a:'a',aSide:'in',b:'b',bSide:'out'});crafted.PATH_DIRECTION_FLOW=reload(d)}
  // CHANNEL_MISMATCH: a file whose Wire joins ports sharing no channel (the loader keeps it as written).
  {const file={schema:D.DOCUMENT_SCHEMA,id:'ch',revision:0,references:[],components:[
     {id:'a',symbolId:'act',x:0,y:0,config:{attachmentDefaults:'none',attachmentPoints:[{id:'tx',side:'right',t:.5,flow:'out',channels:[{id:'data'}]}]}},
     {id:'b',symbolId:'act',x:400,y:0,config:{attachmentDefaults:'none',attachmentPoints:[{id:'rx',side:'left',t:.5,flow:'in',channels:[{id:'main'}]}]}}],
   wires:[{id:'k',a:'a',aSide:'tx',aAttachment:{kind:'attachment-ref',componentId:'a',pointId:'tx'},b:'b',bSide:'rx',bAttachment:{kind:'attachment-ref',componentId:'b',pointId:'rx'},config:{direction:'forward'}}]};
   crafted.CHANNEL_MISMATCH=D.makeDocument(file)}
  // A stand-in pack binds through applyBind a ref the core pack does not hold, or holds with other ports.
  const standIn=(id,parameters)=>S.loadPack({format:'soveraeign.schematic/pack@0.1',id:'stand-in',version:1,definitions:[{...clone(andDef),id,...(parameters?{parameters}:{})}]}).pack;
  // DEFINITION_UNRESOLVED: a definition no pack holds.
  {const d=D.makeDocument({id:'un'});mk(d,{id:'g',symbolId:'act',x:0,y:0});S.applyBind(d,'g','logic.nand@1',[standIn('logic.nand')]);crafted.DEFINITION_UNRESOLVED=reload(d)}
  // DEFINITION_PORTS: bound to logic.and@1 but carrying ports another logic.and@1 generated (x, y -> z).
  {const d=D.makeDocument({id:'dp'});mk(d,{id:'g',symbolId:'act',x:0,y:0});S.applyBind(d,'g','logic.and@1',[standIn('logic.and',{inputs:['x','y'],outputs:['z'],table:andDef.parameters.table})]);crafted.DEFINITION_PORTS=reload(d)}
  // MERGE_INVALID (a): a declared order naming a Wire that does not end on the port.
  {const d=reload(valid);const g=d.components.find(c=>c.id==='g');g.config.attachmentPoints[0].channels=[{id:'main',merge:{combine:'first',order:{kind:'declared',paths:['wa','wq']}}}];crafted.MERGE_INVALID=D.normalizeDocument(d)}
  // MERGE_INVALID (b): a file whose merge fails merge@1 (order on an order-free combine); loading keeps it as written.
  {const d=JSON.parse(JSON.stringify(D.compactDocument(valid)));d.components.find(c=>c.id==='g').config.attachmentPoints[1].channels=[{id:'main',merge:{combine:'or',order:{kind:'stochastic'}}}];crafted.MERGE_INVALID_SHAPE=D.documentFromFilePayload(d)}
  out.crafted={};
  for(const [k,doc] of Object.entries(crafted)){const snap=JSON.stringify(doc);const r=S.checkDocument(doc,packs);out.crafted[k]={codes:r.refusals.map(x=>x.code),ok:r.ok,refusals:r.refusals,unmutated:JSON.stringify(doc)===snap}}
  // A declared order naming only Wires that end on the port is accepted.
  {const d=reload(valid);const g=d.components.find(c=>c.id==='g');g.config.attachmentPoints[0].channels=[{id:'main',merge:{combine:'last',order:{kind:'declared',paths:['wa']}}}];out.declaredOk=S.checkDocument(D.normalizeDocument(d),packs)}
  // Every direction rule: forward, reverse, duplex, none; free ends skipped.
  {const d=D.makeDocument({id:'dirs'});mk(d,{id:'a',symbolId:'act',x:0,y:0});mk(d,{id:'b',symbolId:'act',x:400,y:0});mk(d,{id:'p1',symbolId:'point',x:0,y:300});mk(d,{id:'p2',symbolId:'point',x:400,y:300});
   mkw(d,{id:'fwd',a:'a',aSide:'out',b:'b',bSide:'in',config:{direction:'forward'}});
   mkw(d,{id:'rev',a:'a',aSide:'in',b:'b',bSide:'out',config:{direction:'reverse'}});
   mkw(d,{id:'ctl',a:'a',aSide:'out',b:'b',bSide:'control',config:{direction:'forward'}});
   mkw(d,{id:'none',a:'a',aSide:'in',b:'b',bSide:'in',config:{direction:'none'}});
   mkw(d,{id:'dup',a:'p1',aSide:'self',b:'p2',bSide:'self',config:{direction:'duplex'}});
   mkw(d,{id:'dupOutIn',a:'a',aSide:'out',b:'b',bSide:'in',config:{direction:'duplex'}});
   mkw(d,{id:'dupBad',a:'a',aSide:'in',b:'b',bSide:'in',config:{direction:'duplex'}});
   mkw(d,{id:'revBad',a:'a',aSide:'out',b:'b',bSide:'in',config:{direction:'reverse'}});
   mkw(d,{id:'free',aAttachment:{kind:'free',x:0,y:0},b:'b',bSide:'in',config:{direction:'reverse'}});
   out.directions=S.checkDocument(reload(d),packs).refusals.map(x=>[x.code,x.subject])}
  out.garbage={nul:S.checkDocument(null,packs).ok,str:S.checkDocument('x',packs).ok};
}

// Every example: checkDocument returns without throwing; the result is printed, not asserted.
out.examples={};
for(const file of JSON.parse(process.argv[3])){
  const raw=JSON.parse(fs.readFileSync(file,'utf8'));
  try{out.examples[file]={result:S.checkDocument(D.documentFromFilePayload(raw),packs)}}catch(e){out.examples[file]={threw:String(e&&e.message||e)}}
}
console.log(JSON.stringify(out));
"""

# Amendment 1 (steps 12-19).
AMEND = r"""
const S=require(process.argv[1]),D=globalThis.SovSchematicData,A=globalThis.SovSchematicAttachment,fs=require('fs'),vm=require('vm');
const clone=x=>JSON.parse(JSON.stringify(x));
const packs=[S.loadPack(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))).pack];
const out={};
const op=(doc,o)=>D.applyOperation(doc,o);
const upd=(doc,id,patch,resource='component')=>op(doc,{op:'update',resource,resourceId:id,patch});
const mk=(doc,value)=>op(doc,{op:'create',resource:'component',value});
const mkw=(doc,value)=>op(doc,{op:'create',resource:'wire',value});
const reload=doc=>D.documentFromFilePayload(JSON.parse(JSON.stringify(D.compactDocument(doc))));
const refusedClean=(doc,fn,pick)=>{const rev=doc.revision,before=JSON.stringify(pick(doc));const rc=fn();return {ok:rc.ok,msg:rc.error?.message||'',rev:rc.revisionAfter===rev&&doc.revision===rev,same:JSON.stringify(pick(doc))===before}};

// Step 13: an invalid delay is refused on create and update; load keeps a stored one.
{
  const d=D.makeDocument({id:'delay'});mk(d,{id:'a',symbolId:'act',x:0,y:0});mk(d,{id:'b',symbolId:'act',x:400,y:0});
  const w=mkw(d,{id:'w',a:'a',aSide:'out',b:'b',bSide:'in',config:{delay:2}});
  const wires=doc=>doc.wires;
  const r={ok:w.ok,create:{},update:{}};
  for(const [k,v] of Object.entries({zero:0,negative:-1,fraction:1.5,string:'2',nul:null})){
    r.create[k]=refusedClean(d,()=>mkw(d,{id:'x'+k,a:'a',aSide:'out',b:'b',bSide:'in',config:{delay:v}}),wires);
    // Contract #47 step 7: an update's delay null removes the delay (absent means 1); it is not refused.
    if(v!==null)r.update[k]=refusedClean(d,()=>upd(d,'w',{config:{delay:v}},'wire'),wires);
  }
  r.accepted=upd(d,'w',{config:{delay:5}},'wire').ok&&d.wires[0].config.delay===5;
  r.unrelated=upd(d,'w',{config:{label:'x'}},'wire').ok;
  const file=JSON.parse(JSON.stringify(D.compactDocument(d)));file.wires[0].config.delay=0;
  const loaded=D.documentFromFilePayload(file);
  r.loadKeeps=loaded.wires[0].config.delay;
  r.check=S.checkDocument(loaded,packs).refusals.map(x=>x.code);
  out.delay=r;
}

// Step 14: a definition that resolves but does not validate is DEFINITION_INVALID.
// Step 16: a definition with no ports is refused on bind and on load with DEFINITION_NOT_BINDABLE.
{
  const and=clone(packs[0].definitions.find(x=>x.id==='logic.and'));
  const broken={format:'soveraeign.schematic/pack@0.1',id:'broken',version:1,definitions:[{...and,id:'logic.broken',parameters:{...and.parameters,table:and.parameters.table.slice(0,3)}}]};
  const flow=S.loadPack({format:'soveraeign.schematic/pack@0.1',id:'flow',version:1,definitions:[{id:'flow.last',version:1,pattern:'merge@1',parameters:{combine:'last'}}]});
  const d=D.makeDocument({id:'defs'});mk(d,{id:'g',symbolId:'act',x:0,y:0});
  out.flowPack={ok:flow.ok,errors:flow.errors};
  out.notBindable=S.bindDefinition(d,'g','flow.last@1',[flow.pack]);
  // A stand-in pack binds through applyBind a ref whose definition the checked pack holds differently.
  const standIn=id=>S.loadPack({format:'soveraeign.schematic/pack@0.1',id:'stand-in',version:1,definitions:[{...clone(and),id}]}).pack;
  S.applyBind(d,'g','logic.broken@1',[standIn('logic.broken')]);
  out.invalid=S.checkDocument(reload(d),[broken]).refusals.map(x=>x.code);
  const e=D.makeDocument({id:'nb'});mk(e,{id:'g',symbolId:'act',x:0,y:0});S.applyBind(e,'g','flow.last@1',[standIn('flow.last')]);
  out.notBindableCheck=S.checkDocument(reload(e),[flow.pack]).refusals.map(x=>x.code);
}

// Step 15: rebinding carries merges; a dropped port or channel holding one is MERGE_IN_USE.
{
  const d=D.makeDocument({id:'rebind'});mk(d,{id:'g',symbolId:'act',x:300,y:0});
  S.applyBind(d,'g','logic.and@1',packs);
  const g=()=>d.components.find(c=>c.id==='g');
  const withMerge=clone(g().config.attachmentPoints);withMerge[0].channels=[{id:'main',merge:{combine:'last'}}];withMerge[1].channels=[{id:'main',merge:{combine:'or'}}];
  const set=upd(d,'g',{config:{attachmentPoints:withMerge}});
  const rebind=S.bindDefinition(d,'g','logic.or@1',packs);
  const applied=S.applyBind(d,'g','logic.or@1',packs);
  const not=S.bindDefinition(d,'g','logic.not@1',packs);
  out.rebind={set:set.ok,patchA:rebind.patch?.config.attachmentPoints[0].channels,applied:applied.ok,definition:g().config.definition,stored:g().config.attachmentPoints.map(p=>[p.id,p.channels]),check:S.checkDocument(reload(d),packs),not};
}

// Step 18: owned ports are guarded; move, relabel and merge edits pass; unbinding is allowed.
{
  const d=D.makeDocument({id:'own'});mk(d,{id:'g',symbolId:'act',x:300,y:0});mk(d,{id:'p',symbolId:'point',x:0,y:0});
  S.applyBind(d,'g','logic.and@1',packs);
  mkw(d,{id:'w',a:'p',aSide:'self',b:'g',bAttachment:{pointId:'a'}});
  const g=()=>d.components.find(c=>c.id==='g');
  const ports=()=>clone(g().config.attachmentPoints);
  const edit=f=>{const list=ports();f(list);return {config:{attachmentPoints:list}}};
  const forbidden={
    addPort:edit(l=>l.push({id:'c',side:'left',t:.9,flow:'in'})),
    removePort:edit(l=>l.splice(1,1)),
    renamePort:edit(l=>{l[1].id='bb'}),
    flow:edit(l=>{l[2].flow='duplex'}),
    channelIds:edit(l=>{l[1].channels=[{id:'main'},{id:'aux'}]}),
    channelRename:edit(l=>{l[1].channels=[{id:'data'}]}),
    standard:{config:{attachmentDefaults:'standard'}},
    retype:{symbolId:'gate'},
    retypePlane:{symbolId:'plane'}
  };
  const r={forbidden:{},allowed:{}};
  for(const [k,patch] of Object.entries(forbidden))r.forbidden[k]=refusedClean(d,()=>upd(d,'g',patch),doc=>doc.components.find(c=>c.id==='g'));
  const allowed={
    move:()=>edit(l=>{l[0].side='top';l[0].t=.25}),
    relabel:()=>edit(l=>{l[2].label='Q'}),
    merge:()=>edit(l=>{l[0].channels=[{id:'main',merge:{combine:'first',order:{kind:'declared',paths:['w']}}}]}),
    noneAgain:()=>({config:{attachmentDefaults:'none'}}),
    label:()=>({config:{label:'AND'}}),
    sameType:()=>({symbolId:'act'})
  };
  for(const [k,patch] of Object.entries(allowed)){const rc=upd(d,'g',patch());r.allowed[k]={ok:rc.ok,msg:rc.error?.message||''}}
  r.after=g().config.attachmentPoints.map(p=>[p.id,p.side,p.t,p.label||null,p.channels]);
  r.check=S.checkDocument(reload(d),packs);
  // The binding path is exempt (it sets config.definition).
  r.rebindExempt=S.applyBind(d,'g','logic.xor@1',packs).ok&&g().config.definition==='logic.xor@1';
  // Unbinding leaves the ports as stored; then the ports are free to change.
  const before=JSON.stringify(g().config.attachmentPoints);
  const unbind=upd(d,'g',{config:{definition:null}});
  r.unbind={ok:unbind.ok,definition:g().config.definition,portsKept:JSON.stringify(g().config.attachmentPoints)===before,thenFree:upd(d,'g',{symbolId:'gate'}).ok,check:S.checkDocument(reload(d),packs)};
  out.owned=r;
}

// Step 19: provenance.threshold.
{
  const rec={format:'soveraeign.schematic/state-record@0.1',id:'sr-1',subject:{entity:'g',run:'run-1'},vantage:'point',observable:'level_high',kind:'derived',form:'binary',value:true,time:{logical:12,sequence:3,mode:'observed'},certainty:{kind:'exact'},observer:'rule:gate.threshold@1',provenance:{rule:'gate.threshold@1',inputs:['sr-0'],threshold:0.8},perturbation:'none'};
  const v=t=>{const r=clone(rec);r.provenance.threshold=t;return S.validateRecord(r)};
  out.threshold={number:S.validateRecord(rec),integer:v(1),string:v('0.8'),nul:v(null),bool:v(true)};
}

// Step 17: paste and Duplicate remap declared orders (the real 15-editor-kernel.js, editor runtime stubbed).
{
  const diagram=D.makeDocument({id:'paste'});
  mk(diagram,{id:'s1',symbolId:'point',x:0,y:0});mk(diagram,{id:'s2',symbolId:'point',x:0,y:200});
  mk(diagram,{id:'g',symbolId:'act',x:300,y:100,config:{attachmentDefaults:'none',attachmentPoints:[{id:'in',side:'left',t:.5,flow:'in',channels:[{id:'main',merge:{combine:'last',order:{kind:'declared',paths:['w1','w2']}}}]},{id:'out',side:'right',t:.5,flow:'out'}]}});
  mkw(diagram,{id:'w1',a:'s1',aSide:'self',b:'g',bAttachment:{pointId:'in'}});
  mkw(diagram,{id:'w2',a:'s2',aSide:'self',b:'g',bAttachment:{pointId:'in'}});
  const source=S.checkDocument(reload(diagram),packs).refusals.filter(x=>x.code==='MERGE_INVALID').length;
  const nodes=diagram.components,wires=diagram.wires,noop=()=>{};
  const ctx=vm.createContext({window:{addEventListener:noop},document:{getElementById:()=>null,querySelectorAll:()=>[]},SovSchematicData:D,diagram,nodes,wires,selected:null,
    statusEl:{},GLOBAL_CANVAS_ID:D.GLOBAL_CANVAS_ID,parentComponent:()=>null,descendantsOf:()=>[],isAttachmentSelectionValue:()=>false,nodeDepth:()=>0,
    syncAllNodeBoundaryContext:noop,render:noop,routeCache:{clear:noop},arrowPoseCache:{clear:noop},setTimeout:()=>0,clearTimeout:noop,Date,Math,Number,String,JSON,Map,Set,Array,Object});
  vm.runInContext(fs.readFileSync(process.argv[3],'utf8'),ctx,{filename:'15-editor-kernel.js'});
  const dup=ids=>{vm.runInContext(`setComponentSelection(${JSON.stringify(ids)})`,ctx);const made=vm.runInContext('duplicateSelection()',ctx);return made.map(c=>c.id)};
  const orderOf=id=>nodes.find(c=>c.id===id).config.attachmentPoints[0].channels[0].merge;
  const r={source};
  // g, s1 and s2 copied: both Wires copied, the order follows them.
  {const before=new Set(wires.map(w=>w.id));const made=dup(['g','s1','s2']);const newWires=wires.filter(w=>!before.has(w.id));const g2=made.find(id=>nodes.find(c=>c.id===id).symbolId==='act');
   r.all={made:made.length,merge:orderOf(g2),wires:newWires.map(w=>[w.id,w.a,w.b]),g2}}
  // g and s1 copied: only w1's copy; w2 leaves the list.
  {const before=new Set(wires.map(w=>w.id));const made=dup(['g','s1']);const newWires=wires.filter(w=>!before.has(w.id));const g2=made.find(id=>nodes.find(c=>c.id===id).symbolId==='act');
   r.some={merge:orderOf(g2),wires:newWires.map(w=>[w.id,w.a,w.b]),g2}}
  // g alone: no Wire copied; the order is removed and the merge keeps its combine.
  {const made=dup(['g']);r.none={merge:orderOf(made[0])}}
  r.original=orderOf('g');
  r.after=S.checkDocument(reload(diagram),packs).refusals.filter(x=>x.code==='MERGE_INVALID').length;
  out.paste=r;
}

// Step 13 over the browser API adapter.
{
  const diagram=D.makeDocument({id:'adapter-delay'});
  mk(diagram,{id:'a',symbolId:'act',x:0,y:0});mk(diagram,{id:'b',symbolId:'act',x:400,y:0});mkw(diagram,{id:'w',a:'a',aSide:'out',b:'b',bSide:'in'});
  D.normalizeDocument(diagram);
  const captures=[],runtime=[];
  const ctx=vm.createContext({window:{},SovSchematicData:D,SovSchematicGraph:require(require('path').join(require('path').dirname(process.argv[1]),'07-graph-core.js')),diagram,Date,Math,String,commitHistoryCapture:label=>captures.push(label===undefined?null:label),normalizeRuntimeAfterCrud:()=>runtime.push('normalize'),saveWorkspaceToStorage:()=>runtime.push('save'),LOCAL_RECOVERY_KEY:'k'});
  vm.runInContext(fs.readFileSync(process.argv[4],'utf8'),ctx,{filename:'85-api.js'});
  const api=ctx.window.SovSchematicAPI,rev=diagram.revision,before=JSON.stringify(diagram.wires);
  const u=api.update('wire','w',{config:{delay:0}}),c=api.create('wire',{id:'w2',a:'a',aSide:'out',b:'b',bSide:'in',config:{delay:1.5}});
  out.adapterDelay={update:u,create:c,labelled:captures.filter(x=>x!==null),runtime,revSame:diagram.revision===rev,same:JSON.stringify(diagram.wires)===before};
}
console.log(JSON.stringify(out));
"""

BARE = r"""
const S=require(process.argv[1]);
console.log(JSON.stringify({keys:Object.keys(S).sort(),global:typeof globalThis.SovSchematicStateSpace,data:typeof globalThis.SovSchematicData,patterns:S.patterns().map(p=>p.id+'@'+p.version)}));
"""


def node(js: str, *args: str):
    proc = subprocess.run(['node', '-e', js, *args], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


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


BAD_MERGE_PORTS = [
    {'id': 'in', 'side': 'left', 't': .5, 'flow': 'in', 'channels': [{'id': 'main', 'merge': {'combine': 'sum', 'order': {'kind': 'stochastic'}}}]},
    {'id': 'out', 'side': 'right', 't': .5, 'flow': 'out'},
]
GOOD_MERGE_PORTS = [
    {'id': 'in', 'side': 'left', 't': .5, 'flow': 'in', 'channels': [{'id': 'main', 'merge': {'combine': 'last', 'order': {'kind': 'declared', 'paths': ['w1', 'w2']}}}]},
    {'id': 'out', 'side': 'right', 't': .5, 'flow': 'out'},
]


def check_http_mcp() -> None:
    with tempfile.TemporaryDirectory() as td:
        port = free_port()
        base = f'http://127.0.0.1:{port}'
        proc = subprocess.Popen(['node', str(ROOT / 'mcp/server.mjs'), '--port', str(port), '--file', str(Path(td) / 'merge.sov')], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            for _ in range(80):
                try:
                    if http_json(base + '/api/v1/formats')[0] == 200:
                        break
                except Exception:
                    time.sleep(.05)
            else:
                raise AssertionError('server did not start')
            status, made = http_json(base + '/api/v1/components', 'POST', {'id': 'g', 'symbolId': 'act', 'x': 0, 'y': 0, 'config': {'attachmentDefaults': 'none', 'attachmentPoints': GOOD_MERGE_PORTS}})
            assert status == 201 and made['ok'], made
            rev = made['revisionAfter']
            patch = {'config': {'attachmentPoints': BAD_MERGE_PORTS}}
            status, denied = http_json(base + '/api/v1/components/g', 'PATCH', patch)
            assert status == 400 and not denied['ok'] and 'MERGE_INVALID' in denied['error']['message'] and denied['revisionAfter'] == rev, denied
            mcp, is_error = rpc(base, 'schematic.update', {'resource': 'component', 'id': 'g', 'patch': patch}, 2)
            assert is_error and not mcp['ok'] and 'MERGE_INVALID' in mcp['error']['message'] and mcp['revisionAfter'] == rev, mcp
            # The stored merge is untouched, and the refusals entered no history: one undo removes the creation.
            doc, is_error = rpc(base, 'schematic.document.get', {}, 3)
            assert not is_error and doc['components'][0]['config']['attachmentPoints'][0]['channels'] == GOOD_MERGE_PORTS[0]['channels'], doc
            # Amendment 1, step 13: an invalid Wire delay is refused on create and update, over HTTP and MCP.
            assert http_json(base + '/api/v1/components', 'POST', {'id': 'h', 'symbolId': 'act', 'x': 400, 'y': 0})[0] == 201
            status, wire = http_json(base + '/api/v1/wires', 'POST', {'id': 'w', 'a': 'g', 'aSide': 'out', 'b': 'h', 'bSide': 'in', 'config': {'delay': 2}})
            assert status == 201 and wire['ok'] and wire['result']['config']['delay'] == 2, wire
            rev = wire['revisionAfter']
            status, denied = http_json(base + '/api/v1/wires/w', 'PATCH', {'config': {'delay': 0}})
            assert status == 400 and 'PATH_DELAY_INVALID' in denied['error']['message'] and denied['revisionAfter'] == rev, denied
            status, denied = http_json(base + '/api/v1/wires', 'POST', {'id': 'w9', 'a': 'g', 'aSide': 'out', 'b': 'h', 'bSide': 'in', 'config': {'delay': 1.5}})
            assert status == 400 and 'PATH_DELAY_INVALID' in denied['error']['message'] and denied['revisionAfter'] == rev, denied
            mcp, is_error = rpc(base, 'schematic.update', {'resource': 'wire', 'id': 'w', 'patch': {'config': {'delay': -1}}}, 5)
            assert is_error and 'PATH_DELAY_INVALID' in mcp['error']['message'] and mcp['revisionAfter'] == rev, mcp
            mcp, is_error = rpc(base, 'schematic.create', {'resource': 'wire', 'value': {'id': 'w8', 'a': 'g', 'aSide': 'out', 'b': 'h', 'bSide': 'in', 'config': {'delay': '3'}}}, 6)
            assert is_error and 'PATH_DELAY_INVALID' in mcp['error']['message'] and mcp['revisionAfter'] == rev, mcp
            # Contract #47, step 2: a non-null definition by update or create is refused over HTTP and MCP.
            status, denied = http_json(base + '/api/v1/components/h', 'PATCH', {'config': {'definition': 'logic.and@1'}})
            assert status == 400 and denied['error']['message'].startswith('DEFINITION_BIND_REQUIRED:') and denied['revisionAfter'] == rev, denied
            status, denied = http_json(base + '/api/v1/components', 'POST', {'id': 'n', 'symbolId': 'act', 'config': {'definition': 'logic.and@1'}})
            assert status == 400 and denied['error']['message'].startswith('DEFINITION_BIND_REQUIRED:') and denied['revisionAfter'] == rev, denied
            mcp, is_error = rpc(base, 'schematic.update', {'resource': 'component', 'id': 'h', 'patch': {'config': {'definition': 'logic.and@1'}}}, 7)
            assert is_error and mcp['error']['message'].startswith('DEFINITION_BIND_REQUIRED:') and mcp['revisionAfter'] == rev, mcp
            mcp, is_error = rpc(base, 'schematic.create', {'resource': 'component', 'value': {'id': 'n', 'symbolId': 'act', 'config': {'definition': {'evil': 1}}}}, 8)
            assert is_error and mcp['error']['message'].startswith('DEFINITION_INVALID:') and mcp['revisionAfter'] == rev, mcp
            # No refusal entered history: three undos remove the Wire, h and the creation of g.
            for n in range(3):
                undo, is_error = rpc(base, 'schematic.history.undo', {}, 10 + n)
                assert not is_error, undo
            assert not undo['components'] and not undo['wires'], undo
        finally:
            proc.terminate()
            proc.wait(timeout=5)


# The browser API adapter (src/85-api.js) run under node: the real adapter source in a context holding the
# real cores and the editor document, with the editor runtime it calls recorded. A refused operation must never
# reach normalizeRuntimeAfterCrud or a labelled history capture.
ADAPTER = r"""
const vm=require('vm'),fs=require('fs');
const D=require(process.argv[1]);const S=require(process.argv[2]);
const [good,bad]=JSON.parse(process.argv[4]);
const diagram=D.makeDocument({id:'adapter'});
const made=D.applyOperation(diagram,{op:'create',resource:'component',value:{id:'g',symbolId:'act',x:200,y:200,config:{attachmentDefaults:'none',attachmentPoints:good}}});
const captures=[],runtime=[];
const ctx=vm.createContext({window:{},SovSchematicData:D,SovSchematicGraph:require(require('path').join(require('path').dirname(process.argv[1]),'07-graph-core.js')),diagram,Date,Math,String,
  commitHistoryCapture:label=>captures.push(label===undefined?null:label),
  normalizeRuntimeAfterCrud:()=>runtime.push('normalize'),saveWorkspaceToStorage:()=>runtime.push('save'),LOCAL_RECOVERY_KEY:'k'});
vm.runInContext(fs.readFileSync(process.argv[3],'utf8'),ctx,{filename:'85-api.js'});
D.normalizeDocument(diagram);
const api=ctx.window.SovSchematicAPI,rev=diagram.revision,before=JSON.stringify(diagram.components[0]);
const denied=api.update('component','g',{config:{attachmentPoints:bad}});
console.log(JSON.stringify({made:made.ok,denied,labelled:captures.filter(x=>x!==null),runtime,revSame:diagram.revision===rev,same:JSON.stringify(diagram.components[0])===before,channels:diagram.components[0].config.attachmentPoints[0].channels}));
"""


def check_adapter() -> dict:
    return node(ADAPTER, str(ROOT / 'src/05-data-core.js'), str(ROOT / 'src/07-state-space.js'), str(ROOT / 'src/85-api.js'), json.dumps([GOOD_MERGE_PORTS, BAD_MERGE_PORTS]))


def check_amendment() -> None:
    a = node(AMEND, str(ROOT / 'src/07-state-space.js'), str(ROOT / 'data/core.logic.pack.json'), str(ROOT / 'src/15-editor-kernel.js'), str(ROOT / 'src/85-api.js'))

    # Step 13: delay refused on edit, kept on load, reported by checkDocument.
    dl = a['delay']
    assert dl['ok'] and dl['accepted'] and dl['unrelated'], dl
    for kind in ('create', 'update'):
        for key, got in dl[kind].items():
            assert got['ok'] is False and 'PATH_DELAY_INVALID' in got['msg'] and got['rev'] and got['same'], (kind, key, got)
    assert dl['loadKeeps'] == 0 and dl['check'] == ['PATH_DELAY_INVALID'], dl
    ad = a['adapterDelay']
    for key in ('update', 'create'):
        assert ad[key]['ok'] is False and 'PATH_DELAY_INVALID' in ad[key]['error']['message'], ad
    assert ad['labelled'] == [] and ad['runtime'] == [] and ad['revSame'] and ad['same'], ad

    # Steps 14 + 16.
    assert a['invalid'] == ['DEFINITION_INVALID'], a['invalid']
    assert a['flowPack'] == {'ok': True, 'errors': []}, a['flowPack']
    assert a['notBindable']['ok'] is False and a['notBindable']['code'] == 'DEFINITION_NOT_BINDABLE', a['notBindable']
    assert a['notBindableCheck'] == ['DEFINITION_NOT_BINDABLE'], a['notBindableCheck']

    # Step 15: rebinding and.a.main.merge onto logic.or keeps it; logic.not drops b, which holds one.
    rb = a['rebind']
    assert rb['set'] and rb['applied'] and rb['definition'] == 'logic.or@1', rb
    assert rb['patchA'] == [{'id': 'main', 'merge': {'combine': 'last'}}], rb['patchA']
    assert rb['stored'] == [['a', [{'id': 'main', 'merge': {'combine': 'last'}}]], ['b', [{'id': 'main', 'merge': {'combine': 'or'}}]], ['q', [{'id': 'main'}]]], rb['stored']
    assert rb['check'] == {'ok': True, 'refusals': []}, rb['check']
    assert rb['not']['ok'] is False and rb['not']['code'] == 'MERGE_IN_USE', rb['not']

    # Step 18: each forbidden owned-port edit refused; move, relabel and merge edits accepted.
    ow = a['owned']
    for key, got in ow['forbidden'].items():
        assert got['ok'] is False and 'DEFINITION_PORTS' in got['msg'] and got['rev'] and got['same'], (key, got)
    for key, got in ow['allowed'].items():
        assert got['ok'], (key, got)
    assert ow['after'][0] == ['a', 'top', .25, None, [{'id': 'main', 'merge': {'combine': 'first', 'order': {'kind': 'declared', 'paths': ['w']}}}]], ow['after']
    assert ow['after'][2][3] == 'Q', ow['after']
    assert ow['check'] == {'ok': True, 'refusals': []}, ow['check']
    assert ow['rebindExempt'], ow
    assert ow['unbind'] == {'ok': True, 'definition': None, 'portsKept': True, 'thenFree': True, 'check': {'ok': True, 'refusals': []}}, ow['unbind']

    # Step 19.
    th = a['threshold']
    assert th['number']['ok'] and th['integer']['ok'], th
    for key in ('string', 'nul', 'bool'):
        assert th[key]['ok'] is False and any('threshold' in e for e in th[key]['errors']), (key, th[key])

    # Step 17: paste and Duplicate remap declared orders through the Wire id map.
    ps = a['paste']
    assert ps['source'] == 0, ps
    new_ids = [w[0] for w in ps['all']['wires']]
    assert len(new_ids) == 2 and all(w[2] == ps['all']['g2'] for w in ps['all']['wires']), ps['all']
    assert ps['all']['merge'] == {'combine': 'last', 'order': {'kind': 'declared', 'paths': new_ids}}, ps['all']
    assert len(ps['some']['wires']) == 1 and ps['some']['merge'] == {'combine': 'last', 'order': {'kind': 'declared', 'paths': [ps['some']['wires'][0][0]]}}, ps['some']
    assert ps['none']['merge'] == {'combine': 'last'}, ps['none']
    assert ps['original'] == {'combine': 'last', 'order': {'kind': 'declared', 'paths': ['w1', 'w2']}}, ps['original']
    assert ps['after'] == 0, ps


# Contract #47: a definition binding is only ever done by binding.
BINDING = r"""
const S=require(process.argv[1]),D=globalThis.SovSchematicData,A=globalThis.SovSchematicAttachment,fs=require('fs'),vm=require('vm');
const clone=x=>JSON.parse(JSON.stringify(x));
const packs=[S.loadPack(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))).pack];
const out={};
const op=(doc,o)=>D.applyOperation(doc,o);
const upd=(doc,id,patch,resource='component')=>op(doc,{op:'update',resource,resourceId:id,patch});
const mk=(doc,value)=>op(doc,{op:'create',resource:'component',value});
const mkw=(doc,value)=>op(doc,{op:'create',resource:'wire',value});
const reload=doc=>D.documentFromFilePayload(JSON.parse(JSON.stringify(D.compactDocument(doc))));
const refusedClean=(doc,fn,pick=d=>d.components)=>{const rev=doc.revision,before=JSON.stringify(pick(doc));const rc=fn();return {ok:rc.ok,msg:rc.error?.message||'',code:rc.error?.code??null,rev:rc.revisionAfter===rev&&doc.revision===rev,same:JSON.stringify(pick(doc))===before}};
const bound=()=>{const d=D.makeDocument({id:'b47'});mk(d,{id:'g',symbolId:'act',x:300,y:0});mk(d,{id:'p',symbolId:'point',x:0,y:0});mk(d,{id:'h',symbolId:'plane',x:900,y:0});
  const rc=S.applyBind(d,'g','logic.and@1',packs);mkw(d,{id:'w',a:'p',aSide:'self',b:'g',bAttachment:{pointId:'a'}});return {d,rc}};

// Step 1: applyBind binds and returns a receipt; bindDefinition only builds the patch.
{
  const d=D.makeDocument({id:'s1'});mk(d,{id:'g',symbolId:'act',x:0,y:0});
  const snap=JSON.stringify(d),patch=S.bindDefinition(d,'g','logic.and@1',packs),untouched=JSON.stringify(d)===snap;
  const rev=d.revision,rc=S.applyBind(d,'g','logic.and@1',packs),g=d.components.find(c=>c.id==='g');
  out.step1={patch:patch.patch,untouched,ok:rc.ok,schema:rc.schema,revs:[rev,rc.revisionBefore,rc.revisionAfter,d.revision],error:rc.error,definition:g.config.definition,stored:g.config.attachmentPoints,
    check:S.checkDocument(reload(d),packs),exported:typeof D.applyBinding};
  // Refused applyBind receipts carry a code and change nothing.
  const e=D.makeDocument({id:'s1r'});mk(e,{id:'g',symbolId:'act',x:0,y:0});mk(e,{id:'s',symbolId:'act',x:-400,y:0});mkw(e,{id:'k',a:'s',aSide:'out',b:'g',bSide:'control'});
  out.step1.refused={unresolved:refusedClean(e,()=>S.applyBind(e,'g','logic.nand@1',packs)),missing:refusedClean(e,()=>S.applyBind(e,'zz','logic.and@1',packs)),inUse:refusedClean(e,()=>S.applyBind(e,'g','logic.and@1',packs))};
  // The binding path itself accepts only a binding patch, on a 2D Component.
  out.step1.binding={extra:refusedClean(e,()=>D.applyBinding(e,'s',{symbolId:'gate',config:{definition:'logic.and@1',attachmentDefaults:'none',attachmentPoints:[]}})),
    nul:refusedClean(e,()=>D.applyBinding(e,'s',{config:{definition:null,attachmentDefaults:'none',attachmentPoints:[]}}))};
}

// Step 2: update and create never set a definition, on the core path (HTTP, MCP and the adapter below).
{
  const {d,rc}=bound(),g=()=>d.components.find(c=>c.id==='g');
  const renamed=clone(g().config.attachmentPoints);renamed[1].id='bb';
  const r={bound:rc.ok,restate:{},plain:{},invalid:{},create:{}};
  // The three patches that restate config.definition: with a port change, a retype, and the attachment mode.
  const restate={ports:{config:{definition:'logic.and@1',attachmentPoints:renamed}},retype:{symbolId:'gate',config:{definition:'logic.and@1'}},standard:{config:{definition:'logic.and@1',attachmentDefaults:'standard'}}};
  for(const [k,patch] of Object.entries(restate))r.restate[k]=refusedClean(d,()=>upd(d,'g',patch));
  r.plain.rebind=refusedClean(d,()=>upd(d,'g',{config:{definition:'logic.or@1'}}));
  r.plain.operation=refusedClean(d,()=>op(d,S.bindDefinition(d,'g','logic.or@1',packs)));
  mk(d,{id:'u',symbolId:'act',x:0,y:400});D.normalizeDocument(d); // the first operation after a create normalizes its port records
  r.plain.unbound=refusedClean(d,()=>upd(d,'u',{config:{definition:'logic.and@1'}}));
  for(const [k,v] of Object.entries({evil:{evil:1},noVersion:'logic.and',zeroVersion:'logic.and@0',number:5,empty:'',list:['logic.and@1']}))r.invalid[k]=refusedClean(d,()=>upd(d,'u',{config:{definition:v}}));
  r.create.bound=refusedClean(d,()=>mk(d,{id:'n1',symbolId:'act',config:{definition:'logic.and@1',attachmentDefaults:'none',attachmentPoints:clone(g().config.attachmentPoints)}}));
  r.create.evil=refusedClean(d,()=>mk(d,{id:'n2',symbolId:'act',config:{definition:{evil:1}}}));
  const nul=mk(d,{id:'n3',symbolId:'act',config:{definition:null}});
  r.create.nul={ok:nul.ok,saved:'definition' in D.compactDocument(d).components.find(c=>c.id==='n3').config};
  r.unbind=upd(d,'g',{config:{definition:null}}).ok&&g().config.definition===null;
  out.step2=r;
}

// Step 2: paste and Duplicate copy a bound Component as-is (the real 15-editor-kernel.js, editor runtime stubbed).
{
  const {d:diagram}=bound();
  const nodes=diagram.components,wires=diagram.wires,noop=()=>{},statusEl={};
  const ctx=vm.createContext({window:{addEventListener:noop},document:{getElementById:()=>null,querySelectorAll:()=>[]},SovSchematicData:D,diagram,nodes,wires,selected:null,
    statusEl,GLOBAL_CANVAS_ID:D.GLOBAL_CANVAS_ID,parentComponent:()=>null,descendantsOf:()=>[],isAttachmentSelectionValue:()=>false,nodeDepth:()=>0,
    syncAllNodeBoundaryContext:noop,render:noop,routeCache:{clear:noop},arrowPoseCache:{clear:noop},setTimeout:()=>0,clearTimeout:noop,Date,Math,Number,String,JSON,Map,Set,Array,Object});
  vm.runInContext(fs.readFileSync(process.argv[3],'utf8'),ctx,{filename:'15-editor-kernel.js'});
  const view=id=>{const c=nodes.find(x=>x.id===id);return [c.config.definition,c.config.attachmentDefaults,c.config.attachmentPoints.map(p=>p.id)]};
  vm.runInContext(`setComponentSelection(['g','p'])`,ctx);
  const dup=vm.runInContext('duplicateSelection()',ctx).map(c=>c.id);
  vm.runInContext(`setComponentSelection(['g'])`,ctx);vm.runInContext('copySelection()',ctx);
  const pasted=vm.runInContext('pasteClipboard()',ctx).map(c=>c.id);
  const g2=dup.find(id=>nodes.find(c=>c.id===id).symbolId==='act');
  const r={dup:dup.length,dupView:view(g2),pasteView:view(pasted[0]),wire:wires.filter(w=>w.b===g2).map(w=>w.bAttachment.pointId),check:S.checkDocument(reload(diagram),packs)};
  // A clipboard carrying an invalid definition pastes nothing.
  const count=nodes.length;
  vm.runInContext(`semanticClipboard.components[0].config.definition={evil:1}`,ctx);
  const refused=vm.runInContext('pasteClipboard()',ctx);
  r.evil={made:refused.length,count:nodes.length===count,status:statusEl.textContent};
  out.paste=r;
}

// Step 3: host and dimension changes are refused; moving, relabelling and merges stay allowed.
{
  const {d}=bound(),g=()=>d.components.find(c=>c.id==='g');
  const r={forbidden:{},allowed:{}};
  const forbidden={
    dimension1:{form:{dimension:1}},
    dimension0:{form:{dimension:0}},
    wireHost:{placement:{kind:'wire',wireId:'w',t:.5}},
    edgeHost:{placement:{kind:'edge',hostId:'h',side:'top',t:.5}},
    pathHost:{placement:{kind:'path',hostId:'h',t:.5}}
  };
  for(const [k,patch] of Object.entries(forbidden))r.forbidden[k]=refusedClean(d,()=>upd(d,'g',patch));
  const ports=()=>clone(g().config.attachmentPoints);
  const edit=f=>{const l=ports();f(l);return {config:{attachmentPoints:l}}};
  const allowed={move:()=>edit(l=>{l[1].side='bottom';l[1].t=.75}),relabel:()=>edit(l=>{l[0].label='A'}),merge:()=>edit(l=>{l[0].channels=[{id:'main',merge:{combine:'or'}}]}),
    surface:()=>({placement:{kind:'surface',x:320,y:40},x:320,y:40}),reorder:()=>edit(l=>l.reverse()),label:()=>({config:{label:'AND'}})};
  for(const [k,f] of Object.entries(allowed)){const rc=upd(d,'g',f());r.allowed[k]={ok:rc.ok,msg:rc.error?.message||''}}
  r.check=S.checkDocument(reload(d),packs);
  // Unbound, the same host and dimension patches are ordinary edits.
  const e=D.makeDocument({id:'free'});mk(e,{id:'g',symbolId:'act',x:0,y:0});S.applyBind(e,'g','logic.and@1',packs);upd(e,'g',{config:{definition:null}});
  r.unbound=upd(e,'g',{form:{dimension:1}}).ok;
  out.step3=r;
}

// Step 4: applySymbol on a bound Component is refused (the bar retype calls it).
{
  const {d}=bound(),g=d.components.find(c=>c.id==='g'),before=JSON.stringify(g);
  const attempt=f=>{try{f();return ''}catch(e){return String(e.message)}};
  out.step4={withDoc:attempt(()=>D.applySymbol(g,'gate',d)),bare:attempt(()=>D.applySymbol(g,'point')),sameType:attempt(()=>D.applySymbol(g,'act',d)),same:JSON.stringify(g)===before};
  // The real bar handler from 60-interactions.js, with the editor runtime it reads stubbed.
  const src=fs.readFileSync(process.argv[4],'utf8'),start=src.indexOf("barComponentType.addEventListener('change',"),end=src.indexOf('\n});\n',start)+4;
  let handler=null;const statusEl={textContent:''},hints=[],captures=[];
  const barComponentType={value:'act',addEventListener:(ev,fn)=>{handler=fn}};
  const ctx=vm.createContext({SovSchematicData:D,Attachment:A,diagram:d,nodes:d.components,selected:'g',barComponentType,statusEl,GROUPS:{Primitives:['point','path','plane'],Components:['blank','act','hold','buffer','gate','switch','limit','receipt','observe']},
    mutationBlocked:()=>false,setHistoryHint:h=>hints.push(h),componentForm:n=>D.clone(n.form),wiresOnBuiltinPoints:()=>[],formHostsChildren:()=>false,
    componentFallbackPlan:()=>[],componentHostPlanRefusal:()=>null,applyComponentHostPlan:()=>{}, // the hosting concern (30-canvas.js); nothing hosted here
    GLOBAL_CANVAS_ID:D.GLOBAL_CANVAS_ID,ensureComponentStructure:()=>{},routeCache:{clear(){}},arrowPoseCache:{clear(){}},render:()=>{},selectNode:()=>{},scheduleHistoryCapture:()=>captures.push(1)});
  vm.runInContext(src.slice(start,end),ctx,{filename:'60-interactions.js'});
  const bar={};
  for(const next of ['gate','point','plane']){barComponentType.value=next;statusEl.textContent='';handler();bar[next]={status:statusEl.textContent,value:barComponentType.value,symbol:g.symbolId,same:JSON.stringify(g)===before}}
  out.step4.bar={found:typeof handler==='function',results:bar,captures:captures.length};
}

// Step 5: only 2D Components bind.
{
  const d=D.makeDocument({id:'s5'});mk(d,{id:'pt',symbolId:'point',x:0,y:0});mk(d,{id:'rail',symbolId:'path',x:0,y:200});
  mk(d,{id:'a',symbolId:'act',x:-300,y:0});mk(d,{id:'b',symbolId:'act',x:300,y:0});mkw(d,{id:'k',a:'a',aSide:'out',b:'b',bSide:'in'});
  mk(d,{id:'onPath',symbolId:'act',canvasId:'canvas:wire:k',placement:{kind:'wire',wireId:'k',t:.5}});
  const r={};
  for(const id of ['pt','rail','onPath']){const dim=D.effectiveDimension(d.components.find(c=>c.id===id));r[id]={dim,patch:S.bindDefinition(d,id,'logic.and@1',packs),apply:refusedClean(d,()=>S.applyBind(d,id,'logic.and@1',packs))}}
  out.step5=r;
}

// Step 6: load cleaning keeps owned ports. The review's file: a bound Component stored with two `a` entries
// and a Wire with bSide 'a'. The Wire stays on the original `a`; no DEFINITION_PORTS.
{
  const file={schema:D.DOCUMENT_SCHEMA,id:'dupA',revision:0,references:[],components:[
    {id:'p',symbolId:'point',x:0,y:0},
    {id:'g',symbolId:'act',x:300,y:0,config:{definition:'logic.and@1',attachmentDefaults:'none',attachmentPoints:[
      {id:'a',side:'left',t:1/3,flow:'in',channels:[{id:'main'}]},{id:'b',side:'left',t:2/3,flow:'in',channels:[{id:'main'}]},{id:'q',side:'right',t:.5,flow:'out',channels:[{id:'main'}]},
      {id:'a',side:'bottom',t:.5,flow:'in',channels:[{id:'main'}]}]}}],
    wires:[{id:'w',a:'p',aSide:'self',b:'g',bSide:'a'}]};
  const once=D.documentFromFilePayload(clone(file)),twice=reload(once);
  const view=doc=>{const g=doc.components.find(c=>c.id==='g');return {ids:A.pointIds(g),stored:g.config.attachmentPoints.map(p=>[p.id,p.side]),wire:[doc.wires[0].bAttachment.pointId,doc.wires[0].bSide]}};
  out.step6={once:view(once),twice:view(twice),check:S.checkDocument(once,packs),checkTwice:S.checkDocument(twice,packs)};
}

// Step 7: a clean save. A null definition is not written; a Wire update with delay null removes the delay.
{
  const {d}=bound();
  const unbind=upd(d,'g',{config:{definition:null}});
  const saved=D.compactDocument(d).components.find(c=>c.id==='g').config;
  mk(d,{id:'z',symbolId:'act',x:600,y:0});
  const wire=mkw(d,{id:'k',a:'g',aAttachment:{pointId:'q'},b:'z',bSide:'in',config:{delay:3}});
  const rev=d.revision,clear=upd(d,'k',{config:{delay:null}},'wire'),k=()=>d.wires.find(w=>w.id==='k');
  const cleared={ok:clear.ok,msg:clear.error?.message||'',rev:[rev,d.revision],inRecord:'delay' in k().config,saved:'delay' in D.compactDocument(d).wires.find(w=>w.id==='k').config,reloaded:'delay' in reload(d).wires.find(w=>w.id==='k').config};
  const again=upd(d,'k',{config:{delay:null}},'wire').ok&&!('delay' in k().config);
  out.step7={unbind:unbind.ok,savedHasDefinition:'definition' in saved,wire:wire.ok,cleared,again,check:S.checkDocument(reload(d),packs)};
}

// Step 2 over the browser API adapter: a refusal reaches no runtime normalization and no history.
{
  const diagram=D.makeDocument({id:'adapter-bind'});mk(diagram,{id:'g',symbolId:'act',x:0,y:0});D.normalizeDocument(diagram);
  const captures=[],runtime=[];
  const ctx=vm.createContext({window:{},SovSchematicData:D,SovSchematicGraph:require(require('path').join(require('path').dirname(process.argv[1]),'07-graph-core.js')),diagram,Date,Math,String,commitHistoryCapture:label=>captures.push(label===undefined?null:label),normalizeRuntimeAfterCrud:()=>runtime.push('normalize'),saveWorkspaceToStorage:()=>runtime.push('save'),LOCAL_RECOVERY_KEY:'k'});
  vm.runInContext(fs.readFileSync(process.argv[5],'utf8'),ctx,{filename:'85-api.js'});
  const api=ctx.window.SovSchematicAPI,rev=diagram.revision,before=JSON.stringify(diagram.components);
  const u=api.update('component','g',{config:{definition:'logic.and@1'}}),c=api.create('component',{id:'h',symbolId:'act',config:{definition:'logic.and@1'}}),x=api.create('component',{id:'i',symbolId:'act',config:{definition:{evil:1}}});
  out.adapter={update:u.error?.message||'',create:c.error?.message||'',evil:x.error?.message||'',oks:[u.ok,c.ok,x.ok],labelled:captures.filter(x=>x!==null),runtime,revSame:diagram.revision===rev,same:JSON.stringify(diagram.components)===before};
}
console.log(JSON.stringify(out));
"""


def check_binding() -> None:
    b = node(BINDING, str(ROOT / 'src/07-state-space.js'), str(ROOT / 'data/core.logic.pack.json'), str(ROOT / 'src/15-editor-kernel.js'), str(ROOT / 'src/60-interactions.js'), str(ROOT / 'src/85-api.js'))
    main_ch = [{'id': 'main'}]
    want_ports = [
        {'id': 'a', 'side': 'left', 't': 1 / 3, 'flow': 'in', 'channels': main_ch},
        {'id': 'b', 'side': 'left', 't': 2 / 3, 'flow': 'in', 'channels': main_ch},
        {'id': 'q', 'side': 'right', 't': .5, 'flow': 'out', 'channels': main_ch},
    ]
    clean = {'ok': True, 'refusals': []}

    def refused(got, code, where=''):
        assert got['ok'] is False and got['msg'].startswith(code + ':') and got['rev'] and got['same'], (where, code, got)

    # Step 1: applyBind binds with a receipt; bindDefinition returns the patch and changes nothing.
    s1 = b['step1']
    assert s1['patch'] == {'config': {'definition': 'logic.and@1', 'attachmentDefaults': 'none', 'attachmentPoints': want_ports}} and s1['untouched'], s1
    assert s1['ok'] and s1['schema'] == 'soveraeign.schematic/receipt@0.1' and s1['error'] is None, s1
    assert s1['revs'][1] == s1['revs'][0] and s1['revs'][2] == s1['revs'][3] == s1['revs'][0] + 1, s1['revs']
    assert s1['definition'] == 'logic.and@1' and s1['stored'] == want_ports and s1['check'] == clean and s1['exported'] == 'function', s1
    for key, code in (('unresolved', 'DEFINITION_UNRESOLVED'), ('missing', 'COMPONENT_NOT_FOUND'), ('inUse', 'PORT_IN_USE')):
        got = s1['refused'][key]
        refused(got, code)
        assert got['code'] == code, (key, got)
    for key, got in s1['binding'].items():
        refused(got, 'DEFINITION_INVALID')
        assert got['code'] == 'DEFINITION_INVALID', (key, got)

    # Step 2: a non-null definition by update or create is DEFINITION_BIND_REQUIRED; a malformed one DEFINITION_INVALID.
    s2 = b['step2']
    assert s2['bound'], s2
    for key, got in list(s2['restate'].items()) + list(s2['plain'].items()) + [('create.bound', s2['create']['bound'])]:
        refused(got, 'DEFINITION_BIND_REQUIRED', key)
    assert set(s2['restate']) == {'ports', 'retype', 'standard'}, s2['restate']
    for key, got in list(s2['invalid'].items()) + [('create.evil', s2['create']['evil'])]:
        refused(got, 'DEFINITION_INVALID')
    assert s2['create']['nul'] == {'ok': True, 'saved': False} and s2['unbind'], s2
    ad = b['adapter']
    assert ad['oks'] == [False, False, False] and ad['update'].startswith('DEFINITION_BIND_REQUIRED:') and ad['create'].startswith('DEFINITION_BIND_REQUIRED:') and ad['evil'].startswith('DEFINITION_INVALID:'), ad
    assert ad['labelled'] == [] and ad['runtime'] == [] and ad['revSame'] and ad['same'], ad

    # Step 2: paste and Duplicate keep a bound Component bound; an invalid definition pastes nothing.
    ps = b['paste']
    bound_view = ['logic.and@1', 'none', ['a', 'b', 'q']]
    assert ps['dup'] == 2 and ps['dupView'] == bound_view and ps['pasteView'] == bound_view and ps['wire'] == ['a'], ps
    assert ps['check'] == clean, ps['check']
    assert ps['evil']['made'] == 0 and ps['evil']['count'] and ps['evil']['status'].startswith('Paste refused · DEFINITION_INVALID:'), ps['evil']

    # Step 3: the three host and dimension changes (and two more) are DEFINITION_PORTS.
    s3 = b['step3']
    for key, got in s3['forbidden'].items():
        refused(got, 'DEFINITION_PORTS')
    for key, got in s3['allowed'].items():
        assert got['ok'], (key, got)
    assert s3['check'] == clean and s3['unbound'], s3

    # Step 4: applySymbol and the bar retype refuse a bound Component and change nothing.
    s4 = b['step4']
    for key in ('withDoc', 'bare', 'sameType'):
        assert s4[key].startswith('DEFINITION_PORTS:'), (key, s4)
    assert s4['same'], s4
    assert s4['bar']['found'] and s4['bar']['captures'] == 0, s4['bar']
    for key, got in s4['bar']['results'].items():
        assert got['status'].startswith('DEFINITION_PORTS:') and got['value'] == 'act' and got['symbol'] == 'act' and got['same'], (key, got)

    # Step 5: a Point, a Path and a Component hosted on a Path do not bind.
    s5 = b['step5']
    assert {k: v['dim'] for k, v in s5.items()} == {'pt': 0, 'rail': 1, 'onPath': 1}, s5
    for key, got in s5.items():
        assert got['patch']['ok'] is False and got['patch']['code'] == 'DEFINITION_NOT_BINDABLE', (key, got)
        refused(got['apply'], 'DEFINITION_NOT_BINDABLE')

    # Step 6: the duplicate-`a` file loads with the Wire on the original `a` and no DEFINITION_PORTS.
    s6 = b['step6']
    want6 = {'ids': ['a', 'b', 'q'], 'stored': [['a', 'left'], ['b', 'left'], ['q', 'right']], 'wire': ['a', 'a']}
    assert s6['once'] == want6 and s6['twice'] == want6, s6
    assert s6['check'] == clean and s6['checkTwice'] == clean, s6

    # Step 7: a null definition is not saved; delay null removes the delay, and absent means 1.
    s7 = b['step7']
    assert s7['unbind'] and s7['savedHasDefinition'] is False and s7['wire'], s7
    c = s7['cleared']
    assert c['ok'] and c['msg'] == '' and c['rev'][1] == c['rev'][0] + 1 and not c['inRecord'] and not c['saved'] and not c['reloaded'], c
    assert s7['again'] and s7['check'] == clean, s7


# Contract 1b amendment 1, step 15: a Point declares its `self` port (channels, merge) without side or t.
POINT_SELF = r"""
const S=require(process.argv[1]),D=globalThis.SovSchematicData,fs=require('fs');
const clone=x=>JSON.parse(JSON.stringify(x));
const packs=[S.loadPack(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))).pack];
const base=()=>({schema:'soveraeign.schematic/document@0.1',id:'self',revision:0,meta:{},components:[
  {id:'S1',symbolId:'point',x:0,y:0,config:{}},{id:'S2',symbolId:'point',x:0,y:100,config:{}},{id:'J',symbolId:'point',x:100,y:50,config:{}}],
  wires:[{id:'w1',a:'S1',aSide:'self',b:'J',bSide:'self'},{id:'w2',a:'S2',aSide:'self',b:'J',bSide:'self'}],references:[],layout:{}});
const withSelf=entry=>{const d=base();d.components[2].config.attachmentPoints=[entry];return d};
const look=d=>{const n=D.normalizeDocument(clone(d)),j=n.components.find(c=>c.id==='J');
  return {stored:j.config.attachmentPoints??null,compact:D.compactDocument(n).components.find(c=>c.id==='J').config.attachmentPoints??null,
    ports:D.canonicalAttachmentPointDescriptors(j).map(s=>[s.id,s.flow??null,s.channels??null]),valid:D.validateDocument(n).ok,
    check:S.checkDocument(n,packs).refusals.map(r=>r.code),reload:JSON.stringify(D.documentFromFilePayload(clone(D.compactDocument(n))).components.find(c=>c.id==='J').config.attachmentPoints??null)}};
const merge={combine:'last',order:{kind:'declared',paths:['w1','w2']}};
const out={
  none:look(base()),
  clean:look(withSelf({id:'self',channels:[{id:'main',merge}]})),
  placeholder:look(withSelf({id:'self',side:'left',t:.5,flow:'duplex',channels:[{id:'main',merge}]})),
  bare:look(withSelf({id:'self'})),
  stranger:look(withSelf({id:'self',channels:[{id:'main',merge:{combine:'first',order:{kind:'declared',paths:['w9']}}}]})),
  shape:look(withSelf({id:'self',channels:[{id:'main',merge:{combine:'or',order:{kind:'stochastic'}}}]})),
  channel:look(withSelf({id:'self',channels:[{id:'aux'}]})),
  plusPort:look((()=>{const d=withSelf({id:'self',channels:[{id:'main',merge:{combine:'or'}}]});d.components[2].config.attachmentPoints.push({id:'x',side:'left',t:.5,flow:'in'});return d})()),
  stated:look(withSelf({id:'self',side:'left',t:.5,flow:'in',channels:[{id:'main',merge}]}))
};
// Contract 0b-2, step 7: the four forms of one declaration - placeholder or clean, each with or
// without an explicit flow 'duplex' - load to one stored form and give one documentHash.
{
  const forms={clean:{id:'self',channels:[{id:'main',merge}]},cleanDuplex:{id:'self',flow:'duplex',channels:[{id:'main',merge}]},
    placeholder:{id:'self',side:'left',t:.5,channels:[{id:'main',merge}]},placeholderDuplex:{id:'self',side:'left',t:.5,flow:'duplex',channels:[{id:'main',merge}]}};
  out.canonical={};
  for(const [key,entry] of Object.entries(forms)){
    const raw=withSelf(entry),n=D.normalizeDocument(clone(raw));
    out.canonical[key]={hash:D.documentHash(n),reloaded:D.documentHash(D.documentFromFilePayload(clone(D.compactDocument(n)))),stored:n.components[2].config.attachmentPoints};
  }
}
// Contract 0b-2, step 6: a component update on a Point sets its `self` through the data core.
{
  const d=D.normalizeDocument(base()),upd=(id,patch)=>{const before=clone(d),rc=D.applyOperation(d,{op:'update',resource:'component',resourceId:id,patch});
    return {ok:rc.ok,msg:rc.error?.message||'',stored:d.components.find(c=>c.id===id).config.attachmentPoints??null,same:JSON.stringify(before.components)===JSON.stringify(d.components),rev:rc.revisionAfter===rc.revisionBefore}};
  const set=list=>({config:{attachmentPoints:list}});
  const r={};
  r.merge=upd('J',set([{id:'self',channels:[{id:'main',merge:{combine:'or'}}]}]));
  r.duplex=upd('J',set([{id:'self',flow:'duplex',channels:[{id:'main',merge:{combine:'and'}}]}]));
  r.flow=upd('J',set([{id:'self',flow:'in',channels:[{id:'main'},{id:'aux'}]}]));
  r.bare=upd('S1',set([{id:'self'}]));
  r.ports=D.canonicalAttachmentPointDescriptors(d.components.find(c=>c.id==='J')).map(s=>[s.id,s.flow??null,s.channels]);
  r.refused={
    mismatch:upd('J',set([{id:'self',channels:[{id:'aux'}]}])),
    emptyChannels:upd('J',set([{id:'self',channels:[]}])),
    blankChannel:upd('J',set([{id:'self',channels:[{id:''}]}])),
    repeatChannel:upd('J',set([{id:'self',channels:[{id:'main'},{id:'main'}]}])),
    badFlow:upd('J',set([{id:'self',flow:'sideways',channels:[{id:'main'}]}])),
    badMerge:upd('J',set([{id:'self',channels:[{id:'main',merge:{combine:'xor'}}]}])),
    withSide:upd('J',set([{id:'self',side:'left',t:.5,channels:[{id:'main'}]}])),
    otherId:upd('J',set([{id:'out',channels:[{id:'main'}]}])),
    two:upd('J',set([{id:'self'},{id:'self'}]))
  };
  // Step 9: the declaration set by update round-trips through save and reload unchanged.
  const saved=D.compactDocument(d),back=D.documentFromFilePayload(clone(saved));
  r.roundTrip={saved:saved.components.find(c=>c.id==='J').config.attachmentPoints,back:back.components.find(c=>c.id==='J').config.attachmentPoints,
    again:D.compactDocument(back).components.find(c=>c.id==='J').config.attachmentPoints,hash:D.documentHash(d)===D.documentHash(back),valid:D.validateDocument(back).ok,check:S.checkDocument(back,packs).refusals.map(x=>x.code)};
  // An empty list removes the declaration; self stays.
  r.cleared=upd('J',set([]));r.clearedPorts=D.canonicalAttachmentPointIdsForComponent(d.components.find(c=>c.id==='J'));
  // A Point created with a declaration is checked and stored the same way.
  const rc=D.applyOperation(d,{op:'create',resource:'component',value:{id:'P9',symbolId:'point',x:0,y:0,config:{attachmentPoints:[{id:'self',flow:'duplex',channels:[{id:'main',merge:{combine:'or'}}]}]}}});
  r.create={ok:rc.ok,stored:d.components.find(c=>c.id==='P9')?.config.attachmentPoints??null};
  out.update=r;
}
process.stdout.write(JSON.stringify(out));
"""


def check_point_self() -> None:
    r = node(POINT_SELF, str(ROOT / 'src/07-state-space.js'), str(ROOT / 'data/core.logic.pack.json'))
    merge = {'combine': 'last', 'order': {'kind': 'declared', 'paths': ['w1', 'w2']}}
    clean = [{'id': 'self', 'channels': [{'id': 'main', 'merge': merge}]}]
    assert r['none']['stored'] is None and r['none']['ports'] == [['self', None, None]] and r['none']['check'] == [], r['none']
    # The clean form loads as written, exposes exactly `self` with its channels, and compacts to itself.
    assert r['clean']['stored'] == clean and r['clean']['compact'] == clean and json.loads(r['clean']['reload']) == clean, r['clean']
    assert r['clean']['ports'] == [['self', None, clean[0]['channels']]] and r['clean']['valid'] and r['clean']['check'] == [], r['clean']
    # The placeholder form (side/t) loads clean. A stated flow is kept unless it is the default
    # `duplex`, which the clean form leaves out (contract 0b-2, step 7).
    assert r['placeholder']['stored'] == clean and r['placeholder']['compact'] == clean and json.loads(r['placeholder']['reload']) == clean, r['placeholder']
    assert r['placeholder']['ports'] == [['self', None, clean[0]['channels']]] and r['placeholder']['check'] == [], r['placeholder']
    stated = [{'id': 'self', 'flow': 'in', 'channels': [{'id': 'main', 'merge': merge}]}]
    assert r['stated']['stored'] == stated and r['stated']['compact'] == stated and json.loads(r['stated']['reload']) == stated, r['stated']
    assert r['stated']['ports'] == [['self', 'in', stated[0]['channels']]], r['stated']
    assert r['bare']['stored'] == [{'id': 'self', 'channels': [{'id': 'main'}]}] and r['bare']['ports'][0][0] == 'self', r['bare']
    # checkDocument reads the self declaration: a declared order naming a stranger, a bad merge shape, no shared channel.
    assert r['stranger']['check'] == ['MERGE_INVALID'], r['stranger']
    assert r['shape']['check'] == ['MERGE_INVALID'], r['shape']
    assert r['channel']['check'] == ['CHANNEL_MISMATCH', 'CHANNEL_MISMATCH'], r['channel']
    # Its exposed port stays exactly self, whatever else the list holds.
    assert [p[0] for p in r['plusPort']['ports']] == ['self'] and r['plusPort']['stored'][0] == {'id': 'self', 'channels': [{'id': 'main', 'merge': {'combine': 'or'}}]}, r['plusPort']

    # Contract 0b-2, step 7: placeholder and clean forms, each with or without flow 'duplex', are one
    # document once loaded: one stored form, one documentHash, also after a save and reload.
    cf = r['canonical']
    hashes = {v['hash'] for v in cf.values()} | {v['reloaded'] for v in cf.values()}
    assert len(hashes) == 1, cf
    assert all(v['stored'] == clean for v in cf.values()), cf

    # Contract 0b-2, step 6: a component update on a Point sets its self declaration.
    up = r['update']
    assert up['merge']['ok'] and up['merge']['stored'] == [{'id': 'self', 'channels': [{'id': 'main', 'merge': {'combine': 'or'}}]}], up['merge']
    assert up['duplex']['ok'] and up['duplex']['stored'] == [{'id': 'self', 'channels': [{'id': 'main', 'merge': {'combine': 'and'}}]}], up['duplex']
    assert up['flow']['ok'] and up['flow']['stored'] == [{'id': 'self', 'flow': 'in', 'channels': [{'id': 'main'}, {'id': 'aux'}]}], up['flow']
    assert up['bare']['ok'] and up['bare']['stored'] == [{'id': 'self', 'channels': [{'id': 'main'}]}], up['bare']
    assert up['ports'] == [['self', 'in', [{'id': 'main'}, {'id': 'aux'}]]], up['ports']
    want = {'mismatch': 'CHANNEL_MISMATCH', 'emptyChannels': 'non-empty array', 'blankChannel': 'channel without an id', 'repeatChannel': 'repeats channel main',
            'badFlow': 'invalid flow sideways', 'badMerge': 'MERGE_INVALID', 'withSide': 'has no side, t', 'otherId': 'only its port self', 'two': 'exactly one port'}
    for key, text in want.items():
        got = up['refused'][key]
        assert got['ok'] is False and text in got['msg'] and got['same'] and got['rev'], (key, got)
        assert 'PORT_IN_USE' not in got['msg'], (key, got)
    rt = up['roundTrip']
    want_rt = [{'id': 'self', 'flow': 'in', 'channels': [{'id': 'main'}, {'id': 'aux'}]}]
    assert rt['saved'] == want_rt and rt['back'] == want_rt and rt['again'] == want_rt and rt['hash'] and rt['valid'] and rt['check'] == [], rt
    assert up['cleared']['ok'] and up['cleared']['stored'] is None and up['clearedPorts'] == ['self'], (up['cleared'], up['clearedPorts'])
    assert up['create'] == {'ok': True, 'stored': [{'id': 'self', 'channels': [{'id': 'main', 'merge': {'combine': 'or'}}]}]}, up['create']


# Contract 0b-2, amendment 2, step 14 (data core half): deleting a host whose interior Components would
# fall back onto a Wire's canvas is refused when one of them is bound (DEFINITION_PORTS), on every surface.
HOST_DELETE = r"""
const S=require(process.argv[1]),D=globalThis.SovSchematicData,fs=require('fs');
const packs=[S.loadPack(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))).pack];
const d=D.makeDocument({id:'hd'}),op=o=>D.applyOperation(d,o);
op({op:'create',resource:'component',value:{id:'l1',symbolId:'point',x:0,y:0}});op({op:'create',resource:'component',value:{id:'l2',symbolId:'point',x:600,y:0}});
op({op:'create',resource:'wire',value:{id:'lane',a:'l1',aSide:'self',b:'l2',bSide:'self'}});
op({op:'create',resource:'component',value:{id:'pl',symbolId:'act',x:300,y:0,canvasId:'canvas:wire:lane',placement:{kind:'wire',wireId:'lane',t:.5},form:{dimension:2,regions:{interior:{state:'open'}}}}});
op({op:'create',resource:'component',value:{id:'and',symbolId:'act',x:300,y:0,canvasId:'canvas:component:pl',parentId:'pl'}});
const bound=S.applyBind(d,'and','logic.and@1',packs).ok;
D.normalizeDocument(d);const before=JSON.stringify(d.components),rc=op({op:'delete',resource:'component',resourceId:'pl'});
const refused={ok:rc.ok,msg:rc.error?.message||'',same:JSON.stringify(d.components)===before,rev:rc.revisionAfter===rc.revisionBefore};
op({op:'update',resource:'component',resourceId:'and',patch:{config:{definition:null}}});
const unbound=op({op:'delete',resource:'component',resourceId:'pl'});
process.stdout.write(JSON.stringify({bound,refused,unbound:{ok:unbound.ok,canvasId:d.components.find(c=>c.id==='and').canvasId}}));
"""


def check_host_delete() -> None:
    r = node(HOST_DELETE, str(ROOT / 'src/07-state-space.js'), str(ROOT / 'data/core.logic.pack.json'))
    assert r['bound'], r
    rf = r['refused']
    assert rf['ok'] is False and 'DEFINITION_PORTS' in rf['msg'] and rf['same'] and rf['rev'], rf
    assert r['unbound'] == {'ok': True, 'canvasId': 'canvas:wire:lane'}, r['unbound']


def main() -> None:
    # 07 loads alone under node through a bare require, and brings its two cores with it.
    bare = node(BARE, str(ROOT / 'src/07-state-space.js'))
    assert bare['global'] == 'object' and bare['data'] == 'object', bare
    assert bare['patterns'] == ['truth_table@1', 'merge@1'], bare
    for key in ('validateRecord', 'patterns', 'pattern', 'loadPack', 'resolveDefinition', 'contractOf', 'bindDefinition', 'checkDocument'):
        assert key in bare['keys'], (key, bare['keys'])
    src = (ROOT / 'src/07-state-space.js').read_text(encoding='utf-8')
    assert 'document.' not in src and 'window' not in src and 'logic.and' not in src, 'the engine holds no DOM and no pack data'
    assert "require('./03-canonical.js')" in src and "require('./05-data-core.js')" in src and src.count('require(') == 2, 'requires only 03 and 05'

    examples = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / 'examples').glob('*.sov'))
    assert examples, 'no examples'
    r = node(CORE, str(ROOT / 'src/07-state-space.js'), str(ROOT / 'data/core.logic.pack.json'), json.dumps(examples))

    # Step 7: core.logic is a valid pack with four truth_table@1 definitions.
    pk = r['pack']
    assert pk['ok'] and pk['errors'] == [] and pk['id'] == 'core.logic' and pk['version'] == 1, pk
    assert pk['defs'] == [
        ['logic.not', 1, 'truth_table@1', 0, ['a'], ['q']],
        ['logic.and', 1, 'truth_table@1', 0, ['a', 'b'], ['q']],
        ['logic.or', 1, 'truth_table@1', 0, ['a', 'b'], ['q']],
        ['logic.xor', 1, 'truth_table@1', 0, ['a', 'b'], ['q']],
    ], pk['defs']
    standard = {
        'logic.not@1': lambda a: not a,
        'logic.and@1': lambda a, b: a and b,
        'logic.or@1': lambda a, b: a or b,
        'logic.xor@1': lambda a, b: a != b,
    }
    for ref, fn in standard.items():
        d = r['defs'][ref]
        assert d['check'] == [] and d['validate'] == [], (ref, d)
        assert len(d['rows']) == 2 ** (1 if ref == 'logic.not@1' else 2), (ref, d['rows'])
        for row in d['rows']:
            assert row['got'] == row['want'] == {'q': fn(*row['ins'].values())}, (ref, row)
    golden = (ROOT / 'tests/golden/logic.and@1.contract.json').read_text(encoding='utf-8').strip()
    assert r['contractAnd'] == golden, (r['contractAnd'], golden)
    assert r['resolve'] == {'and': 'logic.and', 'v2': None, 'nand': None}, r['resolve']

    # Step 2: one valid record; each invalid coordinate and each extra key refused.
    rec = r['record']
    assert rec['good'] == {'ok': True, 'errors': []}, rec['good']
    assert rec['full']['ok'] and rec['categorical']['ok'], rec
    for key, res in r['recordBad'].items():
        assert res['ok'] is False and res['errors'], (key, res)
    assert any('unknown key quality' in e for e in r['recordBad']['extraTop']['errors']), r['recordBad']['extraTop']

    # Step 3: the registry.
    assert r['patterns'] == [
        {'id': 'truth_table', 'version': 1, 'class': 'exact', 'stateful': False, 'blastRadius': 'local', 'validate': 'function', 'derive': 'function'},
        {'id': 'merge', 'version': 1, 'class': 'exact', 'stateful': False, 'blastRadius': 'local', 'validate': 'function', 'derive': 'function'},
    ], r['patterns']
    assert r['patternLookup'] == {'tt': 'truth_table', 'merge': 'merge', 'missing': None, 'bare': None}, r['patternLookup']
    main_ch = [{'id': 'main'}]
    assert r['derivedAnd'] == {
        'inputs': [{'id': 'a', 'flow': 'in', 'channels': main_ch, 'observable': 'logic.level', 'form': 'binary'}, {'id': 'b', 'flow': 'in', 'channels': main_ch, 'observable': 'logic.level', 'form': 'binary'}],
        'outputs': [{'id': 'q', 'flow': 'out', 'channels': main_ch, 'observable': 'logic.level', 'form': 'binary'}],
        'state': None,
        'observables': [{'id': 'logic.level', 'form': 'binary', 'unit': None, 'blastRadius': 'local', 'staleness': 0}],
    }, r['derivedAnd']
    want_tt = {'missingRow': 'covers 3 of the 4', 'duplicateRow': 'repeats the input combination', 'wrongWidth': 'must be an array of 3 cells',
               'notBit': 'only 0 and 1', 'notBitBool': 'only 0 and 1', 'duplicateName': 'inputs repeats a name', 'overlap': 'outputs overlap inputs',
               'badName': 'is not a name', 'tooMany': '1 to 8 names', 'noOutputs': '1 to 8 names', 'extraKey': 'unknown key delay'}
    for key, text in want_tt.items():
        assert any(text in e for e in r['ttBad'][key]), (key, r['ttBad'][key])

    # Step 6: stated derived members must equal what is derived; unknown keys refused.
    st = r['stated']
    assert st['same'] == [], st['same']
    for key in ('diff', 'flow'):
        assert [x['code'] for x in st[key]] == ['CONTRACT_MISMATCH'], (key, st[key])
    for key, code in (('unknownKey', 'DEFINITION_INVALID'), ('unknownPattern', 'PATTERN_UNKNOWN'), ('badParams', 'PARAMETERS_INVALID'), ('badDelay', 'DEFINITION_INVALID'),
                      ('badVersion', 'DEFINITION_INVALID'), ('badPorts', 'DEFINITION_INVALID'), ('strangerPort', 'DEFINITION_INVALID')):
        assert st[key] and all(x['code'] == code for x in st[key]), (key, st[key])
    pks = r['packs']
    assert not pks['diff']['ok'] and pks['diff']['pack'] is None and [e['code'] for e in pks['diff']['errors']] == ['CONTRACT_MISMATCH'], pks['diff']
    assert pks['same']['ok'], pks['same']
    for key in ('unknownKey', 'format', 'missingId', 'dup', 'notObject'):
        assert not pks[key]['ok'] and pks[key]['errors'], (key, pks[key])
    placed = r['placed']
    assert [(p['id'], p['side'], p['t']) for p in placed['inputs']] == [('a', 'left', 1 / 3), ('b', 'left', 2 / 3)], placed
    assert [(p['id'], p['side'], p['t'], p.get('label')) for p in placed['outputs']] == [('q', 'bottom', .25, 'Q')], placed

    # merge@1: every combine; order refused on the order-free ones, defaulted on the order-dependent ones.
    for combine, m in r['merge'].items():
        assert m['bare'] == [], (combine, m)
        if combine in ('or', 'and', 'min', 'max', 'sum'):
            assert m['derive'] == {'orderDependent': False, 'order': None}, (combine, m)
            for key in ('declared', 'stochastic', 'observed'):
                assert any('order is refused' in e for e in m[key]), (combine, key, m[key])
        else:
            assert m['derive'] == {'orderDependent': True, 'order': {'kind': 'stochastic'}}, (combine, m)
            assert m['declared'] == m['stochastic'] == m['observed'] == [], (combine, m)
            assert m['deriveDeclared'] == {'orderDependent': True, 'order': {'kind': 'declared', 'paths': ['w1', 'w2']}}, (combine, m)
    for key, res in r['mergeBad'].items():
        assert res, (key, res)

    # Steps 4 + 5: a channel merge and a Wire delay survive save and reload unchanged.
    rt = r['roundtrip']
    merge_ch = [{'id': 'main', 'merge': {'combine': 'last', 'order': {'kind': 'declared', 'paths': ['w1', 'w2']}}}]
    assert rt['created'] and rt['w1'] and rt['w2'], rt
    for key in ('stored', 'saved', 'reloaded', 'again'):
        assert rt[key][0]['channels'] == merge_ch, (key, rt[key])
    assert rt['specChannels'] == merge_ch, rt['specChannels']
    assert rt['delaySaved'] == [3, None] and rt['delayReloaded'] == [3, False], rt
    assert rt['upMerge'] and rt['upDelay'] and rt['after'][0]['channels'] == [{'id': 'main', 'merge': {'combine': 'sum'}}] and rt['afterDelay'] == 2, rt
    assert rt['check'] == {'ok': True, 'refusals': []}, rt['check']
    assert r['plain'] == {'channels': [{'id': 'main'}], 'noDelay': True}, r['plain']
    for key, got in r['mergeRefused'].items():
        assert got['ok'] is False and 'MERGE_INVALID' in got['msg'], (key, got)
        if key != 'create':
            assert got['rev'] and got['same'], (key, got)

    # Step 8: binding logic.and@1 on an act Component.
    b = r['bind']
    assert b['op']['op'] == 'update' and b['op']['resource'] == 'component' and b['op']['resourceId'] == 'g', b['op']
    assert b['ok'] and b['definition'] == 'logic.and@1' and b['mode'] == 'none', b
    want_ports = [
        {'id': 'a', 'side': 'left', 't': 1 / 3, 'flow': 'in', 'channels': main_ch},
        {'id': 'b', 'side': 'left', 't': 2 / 3, 'flow': 'in', 'channels': main_ch},
        {'id': 'q', 'side': 'right', 't': .5, 'flow': 'out', 'channels': main_ch},
    ]
    assert b['stored'] == want_ports and b['specs'] == want_ports, (b['stored'], b['specs'])
    assert b['check'] == {'ok': True, 'refusals': []}, b['check']
    assert b['reloaded']['definition'] == 'logic.and@1' and b['reloaded']['attachmentPoints'] == want_ports, b['reloaded']
    assert r['unresolved']['ok'] is False and r['unresolved']['code'] == 'DEFINITION_UNRESOLVED', r['unresolved']
    iu = r['inUse']
    assert iu['wire'] and iu['bound'] == 'top' and iu['ok'] is False and 'PORT_IN_USE' in iu['msg'] and iu['rev'] and iu['same'], iu

    # Step 9: each crafted document refused with exactly its code; the valid A AND B -> Q is ok.
    v = r['valid']
    assert v['bound'] and v['wires'] == [True, True, True], v
    assert v['check'] == {'ok': True, 'refusals': []} and v['unmutated'], v
    assert [x['code'] for x in v['noPacks']['refusals']] == ['DEFINITION_UNRESOLVED'], v['noPacks']
    for key, got in r['crafted'].items():
        code = 'MERGE_INVALID' if key.startswith('MERGE_INVALID') else key
        assert got['codes'] == [code] and got['ok'] is False and got['unmutated'], (key, got)
        assert all(x['subject'] and x['message'] for x in got['refusals']), (key, got)
    assert r['declaredOk'] == {'ok': True, 'refusals': []}, r['declaredOk']
    assert r['directions'] == [['PATH_DIRECTION_FLOW', 'wire:dupBad'], ['PATH_DIRECTION_FLOW', 'wire:revBad']], r['directions']
    assert r['garbage'] == {'nul': False, 'str': False}, r['garbage']

    # checkDocument on every example returns without throwing (its result is printed), and since amendment 1
    # (step 12, the relaxed direction rule) every example checks ok.
    for file, res in r['examples'].items():
        assert 'threw' not in res, (file, res)
        print(f'checkDocument {file}: {json.dumps(res["result"])}')
        assert res['result'] == {'ok': True, 'refusals': []}, (file, res)

    # Step 4 on every surface: an invalid merge update is refused, with no revision and no history.
    check_http_mcp()
    ad = check_adapter()
    assert ad['made'] and ad['denied']['ok'] is False and 'MERGE_INVALID' in ad['denied']['error']['message'], ad
    assert ad['labelled'] == [] and ad['runtime'] == [] and ad['revSame'] and ad['same'] and ad['channels'] == GOOD_MERGE_PORTS[0]['channels'], ad

    # The page loads 07 right after the data core; the built page carries it.
    page = (ROOT / 'index.source.html').read_text(encoding='utf-8')
    assert '<script src="src/05-data-core.js"></script>\n<script src="src/07-state-space.js"></script>' in page, 'index.source.html must load 07 after 05'
    assert 'data-beta-module="src/07-state-space.js"' in (ROOT / 'index.html').read_text(encoding='utf-8'), 'index.html does not carry 07; run build.py'
    check_amendment()
    check_binding()
    check_point_self()
    check_host_delete()
    print('PASS state space contracts QA')


if __name__ == '__main__':
    main()
