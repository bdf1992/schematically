"""State space ledger and step (slice 1b of STATE-SPACE.md, issue #43): the first runs.

The hash-chained ledger, the replay key, two-phase ticks with merges, recorded stochastic
order draws, the trace (`.sovtrace`) and replay, driven under node against the engine in
src/07-state-space.js and the golden examples in examples/state/.
"""
from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'examples/state'

CORE = r"""
const S=require(process.argv[1]),D=globalThis.SovSchematicData,C=globalThis.SovSchematicCanonical,fs=require('fs');
const dir=process.argv[3];
const clone=x=>JSON.parse(JSON.stringify(x));
const canon=C.canonicalize;
const packJson=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const pack=S.loadPack(clone(packJson)).pack,packs=[pack];
const read=f=>JSON.parse(fs.readFileSync(dir+'/'+f,'utf8'));
const load=f=>D.normalizeDocument(read(f));
const out={};
const K=(e,p,c='main')=>JSON.stringify([e,p,c]);
function settle(run,limit=1000){const steps=[];for(let i=0;i<limit;i++){const r=S.step(run);steps.push(r);if(!r.ok||r.tick===null)return steps}throw new Error('no quiet')}
function started(args){const s=S.startRun(args);if(!s.ok)throw new Error(JSON.stringify(s));return s.run}
// Each device's definition, delay and input ports, read from the document and the packs.
const devicesOf=(doc,packs)=>Object.fromEntries(doc.components.filter(c=>c.config&&c.config.definition).map(c=>{const def=S.resolveDefinition(c.config.definition,packs);return [c.id,{definition:c.config.definition,delay:def.delay||0,inputs:def.parameters.inputs}]}));
const rehash=trace=>{let prev='0'.repeat(64);trace.ledger.forEach((e,i)=>{e.prev=prev;e.hash=C.sha256Hex(canon({seq:e.seq,kind:e.kind,body:e.body,prev}));prev=e.hash});trace.head=prev;return trace};

out.api={keys:Object.keys(S),version:S.RUNTIME_VERSION,fns:['startRun','step','traceOf','replay','validateTrace'].map(k=>typeof S[k])};

// Golden examples: a re-run is byte-identical to the stored trace, forward and in the reversed walk.
const vec=v=>[{entity:'A',point:'self',value:v[0]==='1',at:0},{entity:'B',point:'self',value:v[1]==='1',at:0}];
const mergeInputs=[{entity:'S1',point:'self',value:true,at:0},{entity:'S2',point:'self',value:false,at:0}];
const jobs=[['not.sov','not.0.sovtrace',[{entity:'A',point:'self',value:false,at:0}]],['not.sov','not.1.sovtrace',[{entity:'A',point:'self',value:true,at:0}]],['not-loop.sov','not-loop.sovtrace',[],40],
  ['and.sov','and.00.sovtrace',vec('00')],['and.sov','and.01.sovtrace',vec('01')],['and.sov','and.10.sovtrace',vec('10')],['and.sov','and.11.sovtrace',vec('11')],
  ['merge.sov','merge.declared.sovtrace',mergeInputs],['merge.or.sov','merge.or.sovtrace',mergeInputs],['merge.stochastic.sov','merge.stochastic.sovtrace',mergeInputs]];
out.golden={};
for(const [sov,file,inputs,budget] of jobs){
  const stored=fs.readFileSync(dir+'/'+file,'utf8'),trace=JSON.parse(stored);
  const docBefore=canon(read(sov)),doc=load(sov),docNorm=canon(doc),packBefore=canon(packs);
  const run=started({doc,packs,inputs,budget});
  const startLedger=run.ledger.map(e=>({seq:e.seq,kind:e.kind,body:e.body}));
  const steps=settle(run);
  const bytes=canon(S.traceOf(run));
  const rev=started({doc:load(sov),packs,inputs,budget,walk:'reverse'});settle(rev);
  const replayed=S.replay({trace,doc,packs});
  const signal=(e,p='self')=>run.signal[K(e,p)]===true;
  out.golden[file]={
    same:bytes===stored,reversed:canon(S.traceOf(rev))===stored,storedCanonical:canon(trace)===stored,
    valid:S.validateTrace(trace),replay:{ok:replayed.ok,code:replayed.code||null,same:replayed.ok&&canon(replayed.records)===canon(trace.records)},
    docUnchanged:canon(doc)===docNorm&&canon(read(sov))===docBefore,packsUnchanged:canon(packs)===packBefore,
    lastStep:steps[steps.length-1],ticks:steps.filter(s=>s.ok&&s.tick!==null).map(s=>s.tick),
    startLedger,final:{Q:signal('Q'),J:signal('J'),OUT:signal('OUT'),q:signal('G','q')},through:trace.through,head:trace.head,lastHash:trace.ledger[trace.ledger.length-1].hash,
    records:trace.records,ledgerKinds:trace.ledger.map(e=>e.kind),draws:trace.ledger.filter(e=>e.kind==='draw').map(e=>e.body),
    recordChecks:trace.records.map(r=>S.validateRecord(r).ok),runId:run.id,devices:devicesOf(doc,packs),replayKey:trace.replayKey,top:Object.keys(trace).sort(),budget:trace.budget,revision:trace.documentRevision
  };
}

// Tampering one byte of one ledger entry fails validateTrace at that entry and every entry after it.
{
  const stored=fs.readFileSync(dir+'/merge.stochastic.sovtrace','utf8');
  const flipHex=h=>(h[0]==='0'?'1':'0')+h.slice(1);
  const cases={
    startSeed:[0,e=>{e.body.replayKey.seed='1'}],
    startBudget:[0,e=>{e.body.budget=1}],
    inputValue:[1,e=>{e.body.value=!e.body.value}],
    inputAt:[2,e=>{e.body.at=1}],
    drawOrder:[3,e=>{e.body.order=e.body.order.slice().reverse()}],
    prev:[2,e=>{e.prev=flipHex(e.prev)}],
    hash:[1,e=>{e.hash=flipHex(e.hash)}],
    seq:[2,e=>{e.seq=7}],
    kind:[3,e=>{e.kind='input'}]
  };
  out.tamper={};
  for(const [name,[i,f]] of Object.entries(cases)){
    const t=JSON.parse(stored);f(t.ledger[i]);
    // The start entry's replayKey copy is left as stored, so only the ledger byte differs.
    const v=S.validateTrace(t),r=S.replay({trace:t,doc:load('merge.stochastic.sov'),packs});
    out.tamper[name]={at:i,len:t.ledger.length,ok:v.ok,entry:v.entry,ledgerErrors:v.errors.filter(e=>e.startsWith('ledger ')).map(e=>Number(e.split(' ')[1].replace(':',''))),replay:{code:r.code,entry:r.entry}};
  }
  const t=JSON.parse(stored);t.records[0].value='x';
  out.tamperRecord=S.validateTrace(t);
  const noRecords=JSON.parse(stored);delete noRecords.records;
  const truncated=JSON.parse(stored);truncated.ledger.pop();
  const raised=JSON.parse(stored);raised.budget=20000;
  const raisedChain=JSON.parse(stored);raisedChain.budget=20000;raisedChain.ledger[0].body.budget=20000;
  const raisedStale=JSON.parse(JSON.stringify(raisedChain));rehash(raisedChain);
  out.optional={valid:S.validateTrace(noRecords),replay:S.replay({trace:noRecords,doc:load('merge.stochastic.sov'),packs}),records:JSON.parse(stored).records,
    truncated:S.validateTrace(truncated),truncatedLen:truncated.ledger.length,truncatedReplay:S.replay({trace:truncated,doc:load('merge.stochastic.sov'),packs}).code,
    raised:S.validateTrace(raised),raisedStale:S.validateTrace(raisedStale),raisedChain:{valid:S.validateTrace(raisedChain).ok,headChanged:raisedChain.head!==JSON.parse(stored).head,replay:S.replay({trace:raisedChain,doc:load('merge.stochastic.sov'),packs}).ok},
    badHead:S.validateTrace({...JSON.parse(stored),head:'x'}).ok,badThrough:S.validateTrace({...JSON.parse(stored),through:-1}).ok};
  // A trace taken after any number of steps replays.
  out.midRun={};
  for(const [sov,inputs,budget] of [['merge.stochastic.sov',mergeInputs],['and.sov',vec('11')],['not-loop.sov',[],40]]){
    const run=started({doc:load(sov),packs,inputs,budget});const got=[];
    for(let i=0;i<25;i++){const t=S.traceOf(run);const r=S.replay({trace:t,doc:load(sov),packs});got.push([t.through,r.ok,r.ok&&canon(r.records)===canon(t.records)]);const s=S.step(run);if(!s.ok||s.tick===null)break}
    out.midRun[sov]=got;
  }
  out.shape={notObject:S.validateTrace(null).ok,extraKey:S.validateTrace({...JSON.parse(stored),extra:1}).ok,format:S.validateTrace({...JSON.parse(stored),format:'soveraeign.schematic/trace@0.2'}).ok,emptyLedger:S.validateTrace({...JSON.parse(stored),ledger:[]}).ok,keyDiffers:S.validateTrace({...JSON.parse(stored),replayKey:{...JSON.parse(stored).replayKey,seed:'9'}})};
}

// REPLAY_KEY_MISMATCH: a changed runtimeVersion (the chain rehashed so the trace itself is valid), a changed document.
{
  const stored=fs.readFileSync(dir+'/and.11.sovtrace','utf8');
  const t=JSON.parse(stored);t.replayKey.runtimeVersion='state-space@2';t.ledger[0].body.replayKey.runtimeVersion='state-space@2';rehash(t);
  const unhashed=JSON.parse(stored);unhashed.replayKey.runtimeVersion='state-space@2';unhashed.ledger[0].body.replayKey.runtimeVersion='state-space@2';
  const changed=load('and.sov');changed.components.find(c=>c.id==='Q').x+=10;
  const before=canon(changed);
  out.keyMismatch={runtime:S.replay({trace:t,doc:load('and.sov'),packs}),runtimeValid:S.validateTrace(t).ok,unhashed:S.replay({trace:unhashed,doc:load('and.sov'),packs}),
    doc:S.replay({trace:JSON.parse(stored),doc:changed,packs}),docUnchanged:canon(changed)===before,
    seed:(()=>{const x=JSON.parse(stored);x.replayKey.seed='7';x.ledger[0].body.replayKey.seed='7';rehash(x);return S.replay({trace:x,doc:load('and.sov'),packs})})()};
}

// REPLAY_DIVERGED: a recorded draw that does not re-derive from the seed; recorded records that differ.
{
  const t=JSON.parse(fs.readFileSync(dir+'/merge.stochastic.sovtrace','utf8'));
  const i=t.ledger.findIndex(e=>e.kind==='draw');t.ledger[i].body.order=t.ledger[i].body.order.slice().reverse();rehash(t);
  const r=JSON.parse(fs.readFileSync(dir+'/merge.or.sovtrace','utf8'));r.records[r.records.length-1].value=!r.records[r.records.length-1].value;
  const extra=JSON.parse(fs.readFileSync(dir+'/merge.declared.sovtrace','utf8'));extra.records.pop();
  out.diverged={draw:S.replay({trace:t,doc:load('merge.stochastic.sov'),packs}),drawIndex:i,valid:S.validateTrace(t).ok,record:S.replay({trace:r,doc:load('merge.or.sov'),packs}),missing:S.replay({trace:extra,doc:load('merge.sov'),packs})};
}

// A port fed by a queue merge delivers one value per tick, in merge order.
const withMerge=(mergeSpec,base='merge.stochastic.sov')=>{const d=read(base);d.components.find(c=>c.id==='J').config.attachmentPoints=[{id:'self',channels:[{id:'main',merge:mergeSpec}]}];return D.normalizeDocument(d)};
const timeline=run=>run.records.map(r=>[r.time.logical,r.subject.entity,r.subject.point,r.value,r.kind,r.observer,r.provenance.rule]);
{
  const q=(order,inputs,walk)=>{const run=started({doc:withMerge({combine:'queue',order:{kind:'declared',paths:order}}),packs,inputs,walk});const steps=settle(run);return {timeline:timeline(run),ticks:steps.map(s=>s.tick),bytes:canon(S.traceOf(run)),queues:run.queues}};
  const three=read('merge.stochastic.sov');three.components.push({id:'S3',symbolId:'point',x:80,y:360,config:{label:'S3'}});
  three.wires.push({id:'w4',a:'S3',aSide:'self',aAttachment:{kind:'attachment-ref',componentId:'S3',pointId:'self'},b:'J',bSide:'self',bAttachment:{kind:'attachment-ref',componentId:'J',pointId:'self'},config:{direction:'forward'}});
  three.components.find(c=>c.id==='J').config.attachmentPoints=[{id:'self',channels:[{id:'main',merge:{combine:'queue',order:{kind:'declared',paths:['w4']}}}]}];
  const threeInputs=[...mergeInputs,{entity:'S3',point:'self',value:true,at:0}];
  const r3=started({doc:D.normalizeDocument(clone(three)),packs,inputs:threeInputs});settle(r3);
  const r3r=started({doc:D.normalizeDocument(clone(three)),packs,inputs:threeInputs,walk:'reverse'});settle(r3r);
  out.queue={w12:q(['w1','w2'],mergeInputs),w21:q(['w2','w1'],mergeInputs),w12rev:q(['w1','w2'],mergeInputs,'reverse'),
    three:{timeline:timeline(r3),draws:r3.ledger.filter(e=>e.kind==='draw').map(e=>e.body),same:canon(S.traceOf(r3))===canon(S.traceOf(r3r)),replay:S.replay({trace:S.traceOf(r3),doc:D.normalizeDocument(clone(three)),packs}).ok}};
}

// An input overrides the arrivals at its port and tick; they are recorded as overridden.
{
  const inputs=[...mergeInputs,{entity:'J',point:'self',value:false,at:1}];
  const run=started({doc:load('merge.or.sov'),packs,inputs});settle(run);
  const rev=started({doc:load('merge.or.sov'),packs,inputs,walk:'reverse'});settle(rev);
  const plain=started({doc:load('merge.or.sov'),packs,inputs:mergeInputs});settle(plain);
  out.override={timeline:timeline(run),final:{J:run.signal[K('J','self')],OUT:run.signal[K('OUT','self')]},plainJ:plain.signal[K('J','self')],same:canon(S.traceOf(run))===canon(S.traceOf(rev)),
    replay:S.replay({trace:S.traceOf(run),doc:load('merge.or.sov'),packs}).ok,records:run.records.filter(r=>r.time.logical===1)};
}

// Device delay 0 and 2, with definitions declared inline in a test pack.
{
  const testPack=S.loadPack({format:'soveraeign.schematic/pack@0.1',id:'test.delay',version:1,definitions:[
    {id:'test.buf',version:1,pattern:'truth_table@1',delay:0,parameters:{inputs:['a'],outputs:['q'],table:[[0,0],[1,1]]}},
    {id:'test.buf',version:2,pattern:'truth_table@1',delay:2,parameters:{inputs:['a'],outputs:['q'],table:[[0,0],[1,1]]}}]});
  const docFor=ref=>D.normalizeDocument({schema:'soveraeign.schematic/document@0.1',id:'delay',revision:0,meta:{},components:[
    {id:'S',symbolId:'point',x:0,y:0,config:{}},
    {id:'G',symbolId:'act',x:200,y:0,config:{definition:ref,attachmentDefaults:'none',attachmentPoints:[{id:'a',side:'left',t:.5,flow:'in',channels:[{id:'main'}]},{id:'q',side:'right',t:.5,flow:'out',channels:[{id:'main'}]}]}},
    {id:'Q',symbolId:'point',x:400,y:0,config:{}}],
    wires:[{id:'wS',a:'S',aSide:'self',b:'G',bSide:'a'},{id:'wQ',a:'G',aSide:'q',b:'Q',bSide:'self',config:{delay:2}}],references:[],layout:{}});
  const go=(ref,inputs,walk)=>{const run=started({doc:docFor(ref),packs:[testPack.pack],inputs,walk});const steps=settle(run);return {timeline:timeline(run),ticks:steps.map(s=>s.tick),bytes:canon(S.traceOf(run)),defs:run.ledger[0].body.replayKey.definitions,replay:S.replay({trace:S.traceOf(run),doc:docFor(ref),packs:[testPack.pack]}).ok}};
  const pulse=[{entity:'S',point:'self',value:true,at:0},{entity:'S',point:'self',value:false,at:1}];
  out.delay={pack:testPack.ok,d0:go('test.buf@1',[{entity:'S',point:'self',value:true,at:0}]),d2:go('test.buf@2',[{entity:'S',point:'self',value:true,at:0}]),
    pulse:go('test.buf@2',pulse),pulseRev:go('test.buf@2',pulse,'reverse')};
}

// BUDGET_SPENT: nothing of the refused tick is applied, and the run stays inspectable.
{
  const run=started({doc:load('and.sov'),packs,inputs:vec('11'),budget:3});
  const first=S.step(run),before=canon(run),second=S.step(run),after=canon(run),third=S.step(run);
  const exact=started({doc:load('and.sov'),packs,inputs:vec('11'),budget:6});const exactSteps=settle(exact);
  const five=started({doc:load('and.sov'),packs,inputs:vec('11'),budget:5});const fiveSteps=settle(five);
  out.budget={first,second,third,unchanged:before===after,trace:S.validateTrace(S.traceOf(run)).ok,tick:run.tick,spent:run.spent,
    exact:{last:exactSteps[exactSteps.length-1],spent:exact.spent},five:{last:fiveSteps[fiveSteps.length-1],spent:five.spent,tick:five.tick},
    defaults:(()=>{const r=started({doc:load('and.sov'),packs});return {budget:r.budget,seed:r.seed,inputs:r.ledger[0].body.replayKey.inputs,quiet:S.step(r)}})()};
}

// Refusals at start.
{
  const doc=load('and.sov'),A=(o)=>({entity:'A',point:'self',value:true,at:0,...o});
  const cases={
    unknownEntity:[A({entity:'Z'})],unknownPort:[A({point:'left'})],unknownChannel:[A({channel:'aux'})],unknownKey:[A({wire:'wA'})],
    valueNumber:[A({value:1})],valueString:[A({value:'true'})],valueMissing:[{entity:'A',point:'self',at:0}],
    atNegative:[A({at:-1})],atFraction:[A({at:1.5})],atString:[A({at:'0'})],atMissing:[{entity:'A',point:'self',value:true}],
    duplicate:[A({}),A({value:false})],duplicateChannel:[A({}),A({channel:'main',value:false})],duplicateCompat:[A({}),A({point:'out'})],
    notObject:[7],deviceOutput:[{entity:'G',point:'q',value:true,at:0}],deviceOutputCompat:[{entity:'G',point:'q',channel:'main',value:false,at:3}]
  };
  out.inputInvalid={};
  for(const [k,inputs] of Object.entries(cases)){const r=S.startRun({doc,packs,inputs});out.inputInvalid[k]={ok:r.ok,code:r.code,message:r.message}}
  out.inputOk={deviceInput:S.startRun({doc,packs,inputs:[{entity:'G',point:'a',value:true,at:0}]}).ok,distinctTicks:S.startRun({doc,packs,inputs:[A({}),A({at:1,value:false})]}).ok,compat:S.startRun({doc,packs,inputs:[A({point:'out'})]}).run?.ledger[1].body};
  out.mergeForm=S.startRun({doc:withMerge({combine:'sum'}),packs,inputs:mergeInputs});
  out.mergeFormOk=['or','and','min','max','first','last','queue'].map(c=>S.startRun({doc:withMerge({combine:c}),packs,inputs:mergeInputs}).ok);
  const unresolved=S.startRun({doc,packs:[],inputs:vec('11')});
  const badDelay=read('and.sov');badDelay.wires[0].config.delay=0;
  const delay=S.startRun({doc:D.normalizeDocument(badDelay),packs,inputs:vec('11')});
  out.runRefused={unresolved:{ok:unresolved.ok,code:unresolved.code,codes:(unresolved.refusals||[]).map(r=>r.code)},delay:{ok:delay.ok,code:delay.code,codes:(delay.refusals||[]).map(r=>r.code)}};
}

// A Point's self declaration: the placeholder form 1f7c745 wrote loads clean and runs the same.
{
  const placeholder=read('merge.or.sov');
  placeholder.components.find(c=>c.id==='J').config.attachmentPoints=[{id:'self',side:'left',t:.5,channels:[{id:'main',merge:{combine:'or'}}]}];
  const n=D.normalizeDocument(clone(placeholder)),j=n.components.find(c=>c.id==='J');
  const a=started({doc:n,packs,inputs:mergeInputs});settle(a);
  const b=started({doc:load('merge.or.sov'),packs,inputs:mergeInputs});settle(b);
  out.selfForm={stored:j.config.attachmentPoints,compact:D.compactDocument(n).components.find(c=>c.id==='J').config.attachmentPoints,
    ports:D.canonicalAttachmentPointDescriptors(j).map(s=>[s.id,s.channels]),check:S.checkDocument(n,packs).ok,
    sameHash:D.documentHash(n)===D.documentHash(load('merge.or.sov')),sameTrace:canon(S.traceOf(a))===canon(S.traceOf(b))};
}

// Provenance of power-on records, both ways: a device with a tick-0 input on its own input port
// (its power-on output names that input), and a delay-2 NOT whose power-on output is recorded at
// tick 2 with no input records.
{
  const own=started({doc:load('and.sov'),packs,inputs:[{entity:'G',point:'a',value:true,at:0},{entity:'G',point:'b',value:true,at:0}]});settle(own);
  const notPack=S.loadPack({format:'soveraeign.schematic/pack@0.1',id:'test.not2',version:1,definitions:[
    {id:'test.not',version:2,pattern:'truth_table@1',delay:2,parameters:{inputs:['a'],outputs:['q'],table:[[0,1],[1,0]]}}]});
  const notDoc=()=>{const d=read('not.sov');d.components.find(c=>c.id==='G').config.definition='test.not@2';return D.normalizeDocument(d)};
  const quiet=started({doc:notDoc(),packs:[notPack.pack]});settle(quiet);
  const fed=started({doc:notDoc(),packs:[notPack.pack],inputs:[{entity:'G',point:'a',value:false,at:0}]});settle(fed);
  out.powerOn={own:{records:S.traceOf(own).records,devices:devicesOf(load('and.sov'),packs)},
    not2:{pack:notPack.ok,records:S.traceOf(quiet).records,devices:devicesOf(notDoc(),[notPack.pack])},
    not2fed:{records:S.traceOf(fed).records,devices:devicesOf(notDoc(),[notPack.pack])}};
}

// Only the engine appends; the ledger is hash-chained.
{
  const run=started({doc:load('merge.stochastic.sov'),packs,inputs:mergeInputs});settle(run);
  out.chain=run.ledger.map((e,i)=>({seq:e.seq,prevOk:e.prev===(i?run.ledger[i-1].hash:'0'.repeat(64)),hashOk:e.hash===C.sha256Hex(canon({seq:e.seq,kind:e.kind,body:e.body,prev:e.prev})),keys:Object.keys(e).sort()}));
  out.jsonSafe=canon(JSON.parse(JSON.stringify(run)))===canon(run);
}

// Slice 1c: settle, query, the run receipt and the registry.
{
  const notPack=S.loadPack({format:'soveraeign.schematic/pack@0.1',id:'test.not2',version:1,definitions:[
    {id:'test.not',version:2,pattern:'truth_table@1',delay:2,parameters:{inputs:['a'],outputs:['q'],table:[[0,1],[1,0]]}}]}).pack;
  const loop2=()=>{const d=read('not-loop.sov');d.components.find(c=>c.id==='G').config.definition='test.not@2';return D.normalizeDocument(d)};
  const and11=()=>started({doc:load('and.sov'),packs,inputs:vec('11')});
  const s={};
  {const run=and11();s.quiet={result:S.settle(run),tick:run.tick,again:S.settle(run),same:canon(S.traceOf(run))===fs.readFileSync(dir+'/and.11.sovtrace','utf8')}}
  {const run=started({doc:load('not-loop.sov'),packs,budget:40});s.loop={result:S.settle(run),tick:run.tick,again:S.settle(run),tickAgain:run.tick}}
  {const run=started({doc:load('not-loop.sov'),packs,budget:40});for(let i=0;i<5;i++)S.step(run);s.loopLate={result:S.settle(run),tick:run.tick}}
  {const run=started({doc:loop2(),packs:[notPack]});s.loop2={result:S.settle(run),tick:run.tick,qs:run.records.filter(r=>r.subject.point==='q').map(r=>[r.time.logical,r.value])}}
  {const run=started({doc:load('and.sov'),packs,inputs:vec('11'),budget:3});const r=S.settle(run);s.budget={result:r,tick:run.tick,spent:run.spent}}
  {const run=started({doc:load('not-loop.sov'),packs,budget:1});s.budgetLoop={result:S.settle(run),tick:run.tick}}
  s.invalid=S.settle({runtimeVersion:'x'});
  s.bench=(()=>{const run=started({doc:load('bench.sov'),packs,inputs:read('bench.inputs.json'),budget:20000});const r=S.settle(run);return {kind:r.kind,period:r.period,subjects:(r.subjects||[]).length}})();
  out.settle=s;
  // query: passive, in record order, an omitted point or channel matches any.
  {
    const run=and11();S.settle(run);
    const bytes=canon(run);const results=[];
    for(let i=0;i<50;i++)results.push(canon(S.query(run,{entity:'G',observable:'logic.level'})));
    out.query={passive:canon(run)===bytes,stable:new Set(results).size===1,
      G:S.query(run,{entity:'G',observable:'logic.level'}).map(r=>r.id),all:run.records.filter(r=>r.subject.entity==='G').map(r=>r.id),
      Gq:S.query(run,{entity:'G',point:'q',channel:'main',observable:'logic.level'}).map(r=>[r.subject.point,r.value]),
      other:S.query(run,{entity:'G',observable:'logic.other'}),none:S.query(run,{entity:'Z',observable:'logic.level'}),
      copies:(()=>{const q=S.query(run,{entity:'Q',observable:'logic.level'});q[0].value='x';return canon(run)===bytes})(),
      refused:[S.query(run,null),S.query(run,{entity:'G'}),S.query(run,{entity:'',observable:'logic.level'}),S.query(run,{entity:'G',observable:'logic.level',at:1}),S.query(run,{entity:'G',point:3,observable:'logic.level'})].map(r=>r.code),
      invalid:S.query({},{entity:'G',observable:'logic.level'}).code};
  }
  // runReceipt: the shape, and head equal to the trace's head after every operation.
  {
    const run=and11(),receipts=[];const head=()=>S.traceOf(run).head;
    receipts.push([S.runReceipt('schematic.run.start',run,{ok:true,run}),head()]);
    let before=run.tick;receipts.push([S.runReceipt('schematic.run.step',run,S.step(run),before),head()]);
    before=run.tick;receipts.push([S.runReceipt('schematic.run.settle',run,S.settle(run),before),head()]);
    receipts.push([S.runReceipt('schematic.state.query',run,S.query(run,{entity:'Q',observable:'logic.level'})),head()]);
    receipts.push([S.runReceipt('schematic.run.trace',run,S.traceOf(run)),head()]);
    const replayed=S.replay({trace:S.traceOf(run),doc:load('and.sov'),packs});
    receipts.push([S.runReceipt('schematic.run.replay',replayed.run,replayed,null),head()]);
    const refusedStep=S.step(null);
    const spent=started({doc:load('not-loop.sov'),packs,budget:1});S.step(spent);before=spent.tick;
    receipts.push([S.runReceipt('schematic.run.step',spent,S.step(spent),before),S.traceOf(spent).head]);
    receipts.push([S.runReceipt('schematic.state.query',run,S.query(run,{entity:'Q'})),head()]);
    receipts.push([S.runReceipt('schematic.run.start',null,S.startRun({doc:load('and.sov'),packs,budget:-1})),null]);
    let unknown=null;try{S.runReceipt('schematic.run.go',run,{})}catch(e){unknown=String(e.message)}
    out.receipt={receipts,unknown,format:S.RUN_RECEIPT_FORMAT,operations:S.RUN_OPERATIONS,runId:run.id,refusedStep:refusedStep.code};
  }
  // The registry: runs beside the document, addressed by handle, started from the current document.
  {
    const doc=load('and.sov'),docBytes=canon(doc);
    const reg=S.createRunRegistry({packs:[packJson],document:()=>doc});
    const a=reg.start({inputs:vec('11')}),b=reg.settle(a.handle),t=reg.trace(a.handle),q=reg.query(a.handle,{entity:'Q',observable:'logic.level'});
    const rp=reg.replay(t.result);
    // A second start with the same replay key is a second run: the first is untouched.
    const again=reg.start({inputs:vec('11')}),firstAfter=reg.trace(a.handle),secondStep=reg.step(again.handle),firstAgain=reg.trace(a.handle);
    out.registry={start:a,settle:b,trace:{head:t.head,traceHead:t.result.head,through:t.result.through,handle:t.handle},query:q.result.map(r=>r.value),
      replay:{ok:rp.ok,runId:rp.runId,handle:rp.handle,head:rp.head,tickAfter:rp.tickAfter},byRunId:reg.step(a.runId).error.code,
      again:{runId:again.runId,handle:again.handle,firstThrough:firstAfter.result.through,secondTick:secondStep.tickAfter,firstStill:firstAgain.result.through,firstBytes:canon(firstAgain.result)===canon(t.result)},
      docUnchanged:canon(doc)===docBytes,
      unknown:[reg.step('nope'),reg.settle(undefined),reg.trace(7),reg.query('nope',{entity:'Q',observable:'logic.level'})].map(r=>[r.operation,r.ok,r.error.code,r.runId,r.handle,r.head]),
      extraKey:reg.start({walk:'reverse'}).error.code,notObject:reg.start(5).error.code,
      cap:[reg.start({budget:S.BUDGET_LIMIT+1}).error,reg.start({budget:1e20}).error.code,reg.start({budget:S.BUDGET_LIMIT}).ok,S.BUDGET_LIMIT,S.startRun({doc,packs,budget:S.BUDGET_LIMIT*10}).ok],
      badPack:S.createRunRegistry({packs:[{format:'x'}],document:()=>doc}).start({}).error.code,
      noPacks:S.createRunRegistry({document:()=>doc}).replay(t.result).error.code,
      emptyPacks:[S.createRunRegistry({packs:[],document:()=>doc}).start({}).error,S.createRunRegistry({packs:[],document:()=>doc}).replay(t.result).error,
        S.createRunRegistry({packs:[],document:()=>load('merge.sov')}).start({inputs:mergeInputs}).ok]};
    // error.details on each refusal kind.
    const spent=reg.start({inputs:vec('11'),budget:1}),tampered=JSON.parse(JSON.stringify(t.result));tampered.ledger[1].hash='0'+tampered.ledger[1].hash.slice(1);
    const other=S.createRunRegistry({packs:[packJson],document:()=>load('not-loop.sov')});
    const badDoc=load('and.sov');badDoc.wires[0].config={...(badDoc.wires[0].config||{}),delay:0};
    out.details={budget:reg.step(spent.handle).error,trace:reg.replay(tampered).error,key:reg.replay(other.trace(other.start({budget:40}).handle).result).error,
      refused:S.createRunRegistry({packs:[packJson],document:()=>badDoc}).start({}).error,notFound:reg.step('x').error,input:reg.start({seed:1}).error};
  }
  // Settle is linear: a NOT loop fanning out on two Paths into a queue-merge Point grows the queue
  // by one every few ticks; settle at budget 30000 is timed against stepping the same run.
  {
    const grow=()=>{const d=read('not-loop.sov');
      d.components.push({id:'J',symbolId:'point',x:400,y:180,config:{label:'J',attachmentPoints:[{id:'self',channels:[{id:'main',merge:{combine:'queue'}}]}]}},{id:'O',symbolId:'point',x:520,y:180,config:{label:'O'}});
      const w=(id,a,ap,b,bp)=>({id,a,aSide:ap,aAttachment:{kind:'attachment-ref',componentId:a,pointId:ap},b,bSide:bp,bAttachment:{kind:'attachment-ref',componentId:b,pointId:bp},config:{direction:'forward',delay:1}});
      d.wires.push(w('p1','G','q','J','self'),w('p2','G','q','J','self'),w('p3','J','self','O','self'));return D.normalizeDocument(d)};
    const a=started({doc:grow(),packs,budget:30000});let t0=process.hrtime.bigint();const r=S.settle(a);const ms=Number(process.hrtime.bigint()-t0)/1e6;
    const b=started({doc:grow(),packs,budget:30000});t0=process.hrtime.bigint();let s;while((s=S.step(b)).ok&&s.tick!==null);const stepMs=Number(process.hrtime.bigint()-t0)/1e6;
    out.grow={result:r,ms,stepMs,tick:a.tick,stepTick:b.tick,queue:Object.values(a.queues).map(q=>S.queueItems(q).length),same:canon(a)===canon(b)};
  }
  // Settle against brute force: the smallest p with the committed signal state at t equal to that at
  // t + p for every t from the first occurrence on, over a long horizon, on three cycles.
  {
    const packFor=delay=>S.loadPack({format:'soveraeign.schematic/pack@0.1',id:`test.not${delay}`,version:1,definitions:[{id:'test.not',version:delay+1,pattern:'truth_table@1',delay,parameters:{inputs:['a'],outputs:['q'],table:[[0,1],[1,0]]}}]}).pack;
    const loopDoc=(delay,pathDelay)=>{const d=read('not-loop.sov');d.components[0].config.definition=`test.not@${delay+1}`;d.wires[0].config.delay=pathDelay;return D.normalizeDocument(d)};
    const twoLoops=()=>{const d=read('not-loop.sov'),h=JSON.parse(JSON.stringify(d.components[0])),w=JSON.parse(JSON.stringify(d.wires[0]));
      h.id='H';w.id='wH';w.a='H';w.b='H';w.aAttachment.componentId='H';w.bAttachment.componentId='H';d.wires[0].config.delay=2;w.config.delay=3;d.components.push(h);d.wires.push(w);return D.normalizeDocument(d)};
    const cases=[['not-loop',load('not-loop.sov'),packs],['not-delay2',loopDoc(2,1),[packFor(2)]],['two-loops-2-3',twoLoops(),packs]];
    out.brute=cases.map(([name,doc,ps])=>{
      const run=started({doc,packs:ps,budget:100000}),res=S.settle(run),end=run.tick,first=end-res.period;
      const b=started({doc,packs:ps,budget:100000}),at=new Map();const horizon=end+10*res.period+10;
      for(;;){const s=S.step(b);if(!s.ok||s.tick===null||s.tick>horizon)break;at.set(s.tick,JSON.stringify(Object.keys(b.signal).filter(k=>b.signal[k]).sort()))}
      const ticks=[...at.keys()].sort((x,y)=>x-y),state=t=>{let v='[]';for(const k of ticks){if(k>t)break;v=at.get(k)}return v};
      let period=null;
      for(let p=1;p<=4*res.period&&period===null;p++){let ok=true;for(let t=first;t+p<=horizon;t++)if(state(t)!==state(t+p)){ok=false;break}if(ok)period=p}
      return {name,result:res,brute:period};
    });
  }
}
process.stdout.write(JSON.stringify(out));
"""


def provenance_errors(records: list, devices: dict) -> list:
    """Every derived record names input records, all recorded before it. Exempt, exactly: a record
    produced by a device's power-on evaluation (tick 0, so recorded at tick `device delay`, by the
    device's own rule) when none of that device's input ports has a record at tick 0. A power-on
    record whose device does have tick-0 input records must name each of them."""
    errors, seen = [], set()
    at_zero = {}
    for rec in records:
        if rec['time']['logical'] == 0 and rec['provenance']['rule'] != 'overridden':
            at_zero.setdefault((rec['subject']['entity'], rec['subject']['point']), []).append(rec['id'])
    for rec in records:
        inputs = rec['provenance']['inputs']
        if rec['kind'] == 'derived':
            dev = devices.get(rec['subject']['entity'])
            power_on = (dev is not None and rec['observer'] == f"rule:{dev['definition']}"
                        and rec['time']['logical'] == dev['delay'])
            required = [i for p in dev['inputs'] for i in at_zero.get((rec['subject']['entity'], p), [])] if power_on else []
            if power_on and not all(i in inputs for i in required):
                errors.append((rec['id'], 'a power-on record does not name its tick-0 input records', required))
            if not inputs and not (power_on and not required):
                errors.append((rec['id'], 'a derived record names no input records'))
        if not all(i in seen for i in inputs):
            errors.append((rec['id'], 'names a record not recorded before it'))
        seen.add(rec['id'])
    return errors


def node(js: str, *args: str):
    proc = subprocess.run(['node', '-e', js, *args], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def main() -> None:
    r = node(CORE, str(ROOT / 'src/07-state-space.js'), str(ROOT / 'data/core.logic.pack.json'), str(STATE))

    # Step 1: the API.
    api = r['api']
    assert api['version'] == 'state-space@1', api
    assert api['fns'] == ['function'] * 5, api
    for key in ('RUNTIME_VERSION', 'startRun', 'step', 'traceOf', 'replay', 'validateTrace', 'checkDocument', 'bindDefinition'):
        assert key in api['keys'], (key, api['keys'])
    for key in ('settle', 'query', 'runReceipt', 'createRunRegistry', 'RUN_RECEIPT_FORMAT'):
        assert key in api['keys'], (key, 'slice 1c exports it')

    # Step 8 + 9: every golden re-runs byte-identical (forward and reversed walk) and replays.
    names = sorted(p.name for p in STATE.iterdir())
    assert names == ['and.00.sovtrace', 'and.01.sovtrace', 'and.10.sovtrace', 'and.11.sovtrace', 'and.sov',
                     'bench.inputs.json', 'bench.sov', 'bench.sovtrace',
                     'grow.sov', 'grow.sovtrace',
                     'merge.declared.sovtrace', 'merge.or.sov', 'merge.or.sovtrace', 'merge.sov',
                     'merge.stochastic.sov', 'merge.stochastic.sovtrace',
                     'not-loop.sov', 'not-loop.sovtrace', 'not.0.sovtrace', 'not.1.sovtrace', 'not.sov'], names
    run_id = re.compile(r'^[0-9a-f]{12}$')
    for file, g in r['golden'].items():
        assert g['same'], f'{file}: a re-run is not byte-identical to the stored trace'
        assert g['reversed'], f'{file}: the reversed walk changes the trace'
        assert g['storedCanonical'], f'{file}: the stored trace is not in canonical encoding'
        assert g['valid'] == {'ok': True, 'entry': None, 'errors': []}, (file, g['valid'])
        assert g['replay'] == {'ok': True, 'code': None, 'same': True}, (file, g['replay'])
        assert g['docUnchanged'] and g['packsUnchanged'], (file, 'startRun/step/replay mutated doc or packs')
        if file == 'not-loop.sovtrace':
            assert g['lastStep']['ok'] is False and g['lastStep']['code'] == 'BUDGET_SPENT', (file, g['lastStep'])
            assert g['budget'] == 40, g['budget']
        else:
            assert g['lastStep'] == {'ok': True, 'tick': None, 'records': []}, (file, g['lastStep'])
            assert g['budget'] == 10000, g['budget']
        assert g['top'] == ['budget', 'documentRevision', 'format', 'head', 'ledger', 'records', 'replayKey', 'through'], g['top']
        assert g['revision'] == 0 and g['through'] == g['ticks'][-1] and g['ticks'][0] == 0 and g['head'] == g['lastHash'], g
        key = g['replayKey']
        assert sorted(key) == ['definitions', 'documentHash', 'documentId', 'inputs', 'runtimeVersion', 'seed', 'traceFormat'], key
        assert key['runtimeVersion'] == 'state-space@1' and key['traceFormat'] == 'soveraeign.schematic/trace@0.1' and key['seed'] == '0', key
        assert re.fullmatch(r'[0-9a-f]{64}', key['documentHash']), key
        assert g['startLedger'][0] == {'seq': 0, 'kind': 'start', 'body': {'replayKey': key, 'budget': g['budget']}}, g['startLedger'][0]
        assert [e['kind'] for e in g['startLedger']] == ['start'] + ['input'] * len(key['inputs']), g['startLedger']
        assert [e['body'] for e in g['startLedger'][1:]] == key['inputs'], g['startLedger']
        # Inputs in (at, entity, point, channel) order, channel defaulted to main.
        assert [(i['at'], i['entity'], i['point'], i['channel']) for i in key['inputs']] == sorted((i['at'], i['entity'], i['point'], i['channel']) for i in key['inputs']), key['inputs']
        assert all(i['channel'] == 'main' for i in key['inputs']), key['inputs']
        # Step 5: every record's fixed coordinates, ids and sequence.
        assert all(g['recordChecks']), (file, g['recordChecks'])
        assert run_id.match(g['runId']), g['runId']
        for n, rec in enumerate(g['records']):
            assert rec['id'] == f"sr-{g['runId']}-{n:06d}" and rec['time']['sequence'] == n, (file, rec)
            assert rec['subject']['run'] == g['runId'] and rec['subject']['channel'] == 'main', rec
            assert (rec['vantage'], rec['observable'], rec['form'], rec['time']['mode'], rec['certainty'], rec['perturbation']) == ('space', 'logic.level', 'binary', 'observed', {'kind': 'exact'}, 'none'), rec
            if rec['observer'] == 'input':
                assert rec['kind'] == 'registered' and rec['provenance'] == {'rule': 'input', 'inputs': []}, rec
            else:
                assert rec['kind'] == 'derived' and re.match(r'^(path:.+|rule:.+@\d+|engine:merge@1)$', rec['observer']), rec
        # Only a power-on evaluation from the unrecorded starting state has no input records.
        assert provenance_errors(g['records'], g['devices']) == [], (file, provenance_errors(g['records'], g['devices']))
        # Sequence order within a tick is (entity, point, channel, observable, kind).
        for a, b in zip(g['records'], g['records'][1:]):
            if a['time']['logical'] == b['time']['logical']:
                ka = (a['subject']['entity'], a['subject']['point'], a['subject']['channel'], a['observable'], a['kind'])
                kb = (b['subject']['entity'], b['subject']['point'], b['subject']['channel'], b['observable'], b['kind'])
                assert ka <= kb, (file, ka, kb)
            else:
                assert a['time']['logical'] < b['time']['logical'], (file, a, b)

    # The provenance exemption is exact, both ways.
    po = r['powerOn']
    own = po['own']['records']
    q0 = [x for x in own if x['subject'] == {'entity': 'G', 'point': 'q', 'channel': 'main', 'run': x['subject']['run']} and x['time']['logical'] == 0]
    ga = [x['id'] for x in own if x['subject']['entity'] == 'G' and x['subject']['point'] in ('a', 'b') and x['time']['logical'] == 0]
    assert len(q0) == 1 and q0[0]['value'] is True and len(ga) == 2 and q0[0]['provenance']['inputs'] == ga, (q0, ga)
    assert provenance_errors(own, po['own']['devices']) == [], provenance_errors(own, po['own']['devices'])
    doctored = json.loads(json.dumps(own))
    [x for x in doctored if x['id'] == q0[0]['id']][0]['provenance']['inputs'] = []
    assert [e[0] for e in provenance_errors(doctored, po['own']['devices'])] == [q0[0]['id'], q0[0]['id']], provenance_errors(doctored, po['own']['devices'])
    partly = json.loads(json.dumps(own))
    [x for x in partly if x['id'] == q0[0]['id']][0]['provenance']['inputs'] = ga[:1]
    assert [e[:2] for e in provenance_errors(partly, po['own']['devices'])] == [(q0[0]['id'], 'a power-on record does not name its tick-0 input records')], provenance_errors(partly, po['own']['devices'])
    assert po['not2']['pack'] and po['not2']['devices'] == {'G': {'definition': 'test.not@2', 'delay': 2, 'inputs': ['a']}}, po['not2']
    q2 = [x for x in po['not2']['records'] if x['subject']['entity'] == 'G' and x['subject']['point'] == 'q']
    assert [(x['time']['logical'], x['value'], x['observer'], x['provenance']['inputs']) for x in q2] == [(2, True, 'rule:test.not@2', [])], q2
    assert provenance_errors(po['not2']['records'], po['not2']['devices']) == [], provenance_errors(po['not2']['records'], po['not2']['devices'])
    # Exactly: the same empty provenance at any other tick, or on a Path's record, is not exempt.
    moved = json.loads(json.dumps(po['not2']['records']))
    [x for x in moved if x['id'] == q2[0]['id']][0]['time']['logical'] = 3
    assert [e[:2] for e in provenance_errors(moved, po['not2']['devices'])] == [(q2[0]['id'], 'a derived record names no input records')], provenance_errors(moved, po['not2']['devices'])
    path = json.loads(json.dumps(po['not2']['records']))
    qrec = [x for x in path if x['subject']['entity'] == 'Q']
    assert qrec and qrec[0]['provenance']['inputs'], qrec
    qrec[0]['provenance']['inputs'] = []
    assert [e[:2] for e in provenance_errors(path, po['not2']['devices'])] == [(qrec[0]['id'], 'a derived record names no input records')], provenance_errors(path, po['not2']['devices'])
    # A delay-2 NOT fed at tick 0 on its own input: its power-on output at tick 2 names that input.
    fed = po['not2fed']['records']
    fq = [x for x in fed if x['subject']['entity'] == 'G' and x['subject']['point'] == 'q' and x['time']['logical'] == 2]
    fa = [x['id'] for x in fed if x['subject']['entity'] == 'G' and x['subject']['point'] == 'a' and x['time']['logical'] == 0]
    assert len(fq) == 1 and len(fa) == 1 and fq[0]['provenance']['inputs'] == fa, (fq, fa)
    assert provenance_errors(fed, po['not2fed']['devices']) == [], provenance_errors(fed, po['not2fed']['devices'])
    dropped = json.loads(json.dumps(fed))
    [x for x in dropped if x['id'] == fq[0]['id']][0]['provenance']['inputs'] = []
    assert [e[:2] for e in provenance_errors(dropped, po['not2fed']['devices'])] == [(fq[0]['id'], 'a power-on record does not name its tick-0 input records'), (fq[0]['id'], 'a derived record names no input records')], provenance_errors(dropped, po['not2fed']['devices'])

    # Power-on: NOT gives Q = NOT A for both values of A; the NOT loop starts and alternates.
    for v in ('0', '1'):
        g = r['golden'][f'not.{v}.sovtrace']
        assert g['final']['Q'] == (v == '0') and g['replayKey']['definitions'] == ['logic.not@1'], (v, g['final'])
        q0 = [x for x in g['records'] if x['subject']['entity'] == 'G' and x['subject']['point'] == 'q' and x['time']['logical'] == 0]
        assert len(q0) == 1 and q0[0]['value'] is True and q0[0]['observer'] == 'rule:logic.not@1', q0
    loop = r['golden']['not-loop.sovtrace']
    qs = [(x['time']['logical'], x['value']) for x in loop['records'] if x['subject']['point'] == 'q']
    assert qs == [(t, t % 2 == 0) for t in range(20)], qs
    assert loop['through'] == 19 and loop['lastStep']['tick'] == 20 and loop['lastStep']['left'] == 1, loop
    assert len(loop['records']) == 39, len(loop['records'])

    # The AND truth table, all four vectors, inputs at tick 0 and every Path delay 1.
    for v in ('00', '01', '10', '11'):
        g = r['golden'][f'and.{v}.sovtrace']
        assert g['final']['Q'] == (v == '11'), (v, g['final'])
        assert g['replayKey']['definitions'] == ['logic.and@1'] and g['draws'] == [], g
    tl = [(x['time']['logical'], x['subject']['entity'], x['subject']['point'], x['value'], x['observer']) for x in r['golden']['and.11.sovtrace']['records']]
    assert tl == [(0, 'A', 'self', True, 'input'), (0, 'B', 'self', True, 'input'), (1, 'G', 'a', True, 'path:wA'), (1, 'G', 'b', True, 'path:wB'),
                  (1, 'G', 'q', True, 'rule:logic.and@1'), (2, 'Q', 'self', True, 'path:wQ')], tl
    q = r['golden']['and.11.sovtrace']['records'][4]
    assert q['provenance'] == {'rule': 'logic.and@1', 'inputs': [r['golden']['and.11.sovtrace']['records'][2]['id'], r['golden']['and.11.sovtrace']['records'][3]['id']]}, q
    assert r['golden']['and.11.sovtrace']['ticks'] == [0, 1, 2], r['golden']['and.11.sovtrace']['ticks']

    # Merge goldens: S1 = true and S2 = false both arrive at J at tick 1.
    dec, orr, sto = (r['golden'][f'merge.{k}.sovtrace'] for k in ('declared', 'or', 'stochastic'))
    for g in (dec, orr, sto):
        at_j = [x for x in g['records'] if x['subject']['entity'] == 'J']
        assert len(at_j) == 1 and at_j[0]['time']['logical'] == 1 and at_j[0]['observer'] == 'engine:merge@1' and len(at_j[0]['provenance']['inputs']) == 2, at_j
        assert at_j[0]['provenance']['rule'] == 'merge@1', at_j
    assert dec['draws'] == [] and dec['final'] == {'Q': False, 'J': False, 'OUT': False, 'q': False}, dec['final']
    assert orr['draws'] == [] and orr['final'] == {'Q': False, 'J': True, 'OUT': True, 'q': False}, orr['final']
    assert sto['ledgerKinds'].count('draw') == 1 and sto['ledgerKinds'] == ['start', 'input', 'input', 'draw'], sto['ledgerKinds']
    draw = sto['draws'][0]
    assert draw['tick'] == 1 and (draw['entity'], draw['point'], draw['channel']) == ('J', 'self', 'main') and draw['paths'] == ['w1', 'w2'] and sorted(draw['order']) == ['w1', 'w2'], draw
    last = {'w1': True, 'w2': False}[draw['order'][-1]]
    assert sto['final']['J'] == last and sto['final']['OUT'] == last, (draw, sto['final'])
    # The declared order lists the provenance in merge order.
    j = [x for x in dec['records'] if x['subject']['entity'] == 'J'][0]
    s1 = [x for x in dec['records'] if x['subject']['entity'] == 'S1'][0]['id']
    s2 = [x for x in dec['records'] if x['subject']['entity'] == 'S2'][0]['id']
    assert j['provenance']['inputs'] == [s1, s2] and j['value'] is False, j

    # Step 3: one changed byte fails validateTrace at that entry and every later one; replay refuses it.
    for name, t in r['tamper'].items():
        assert t['ok'] is False and t['entry'] == t['at'], (name, t)
        assert t['ledgerErrors'] == list(range(t['at'], t['len'])), (name, t)
        assert t['replay'] == {'code': 'TRACE_INVALID', 'entry': t['at']}, (name, t)
    assert r['tamperRecord']['ok'] is False and r['tamperRecord']['entry'] is None, r['tamperRecord']
    assert r['shape'] == {'notObject': False, 'extraKey': False, 'format': False, 'emptyLedger': False,
                          'keyDiffers': {'ok': False, 'entry': 0, 'errors': ['ledger 0: the start entry does not carry the replayKey and budget']}}, r['shape']
    # Records are optional; the budget is in the chain; head catches a truncated ledger.
    op = r['optional']
    assert op['valid']['ok'] and op['replay']['ok'] and op['replay']['records'] == op['records'], op['replay']
    assert op['truncated']['ok'] is False and op['truncated']['entry'] == op['truncatedLen'] and 'head' in op['truncated']['errors'][0], op['truncated']
    assert op['truncatedReplay'] == 'TRACE_INVALID', op
    assert op['raised']['ok'] is False and op['raised']['entry'] == 0, op['raised']
    assert op['raisedStale']['ok'] is False and op['raisedStale']['entry'] == 0, op['raisedStale']
    assert op['raisedChain'] == {'valid': True, 'headChanged': True, 'replay': True}, op['raisedChain']
    assert op['badHead'] is False and op['badThrough'] is False, op
    # A trace taken after any number of steps replays ok, records identical.
    for sov, got in r['midRun'].items():
        assert got[0][0] is None and all(ok and same for _, ok, same in got), (sov, got)
    assert [t for t, _, _ in r['midRun']['merge.stochastic.sov']] == [None, 0, 1, 2], r['midRun']
    assert len(r['midRun']['not-loop.sov']) == 21, r['midRun']['not-loop.sov']

    # Step 7: REPLAY_KEY_MISMATCH names the differing fields.
    km = r['keyMismatch']
    assert km['runtimeValid'] and km['runtime']['code'] == 'REPLAY_KEY_MISMATCH' and km['runtime']['fields'] == ['runtimeVersion'], km['runtime']
    assert km['unhashed']['code'] == 'TRACE_INVALID' and km['unhashed']['entry'] == 0, km['unhashed']
    assert km['doc']['code'] == 'REPLAY_KEY_MISMATCH' and km['doc']['fields'] == ['documentHash'] and km['docUnchanged'], km['doc']
    # The seed and inputs are read from the trace, so a changed seed cannot mismatch the key: the fold differs instead.
    assert km['seed']['code'] == 'REPLAY_DIVERGED', km['seed']

    # REPLAY_DIVERGED: an altered recorded draw; a recorded record that the fold does not reproduce.
    dv = r['diverged']
    assert dv['valid'] and dv['draw']['ok'] is False and dv['draw']['code'] == 'REPLAY_DIVERGED' and dv['draw']['entry'] == dv['drawIndex'], dv['draw']
    assert dv['record']['code'] == 'REPLAY_DIVERGED' and dv['missing']['code'] == 'REPLAY_DIVERGED', dv

    # A queue merge delivers one value per tick, in merge order; the walk order changes nothing.
    qu = r['queue']
    def at(timeline, entity):
        return [(x[0], x[3], x[5]) for x in timeline if x[1] == entity]
    assert at(qu['w12']['timeline'], 'J') == [(1, True, 'engine:merge@1'), (2, False, 'engine:merge@1')], qu['w12']
    assert at(qu['w12']['timeline'], 'OUT') == [(2, True, 'path:w3'), (3, False, 'path:w3')], qu['w12']
    assert at(qu['w21']['timeline'], 'J') == [(1, False, 'engine:merge@1'), (2, True, 'engine:merge@1')], qu['w21']
    assert at(qu['w21']['timeline'], 'OUT') == [(3, True, 'path:w3')], qu['w21']
    assert qu['w12']['ticks'] == [0, 1, 2, 3, None] and qu['w12']['queues'] == {}, qu['w12']
    assert qu['w12']['bytes'] == qu['w12rev']['bytes'], 'the reversed walk changes a queue run'
    # Three arrivals, one declared: w4 first, then a recorded draw over w1 and w2.
    three = qu['three']
    assert three['same'] and three['replay'] and len(three['draws']) == 1 and three['draws'][0]['paths'] == ['w1', 'w2'], three
    js = [x for x in three['timeline'] if x[1] == 'J']
    want = [True] + [{'w1': True, 'w2': False}[w] for w in three['draws'][0]['order']]
    assert [x[0] for x in js] == [1, 2, 3] and [x[3] for x in js] == want, (js, want)

    # An input overrides the arrivals at its port and tick.
    ov = r['override']
    assert ov['plainJ'] is True and ov['final'] == {'J': False, 'OUT': False}, ov
    at_j1 = sorted((x['kind'], x['observer'], x['provenance']['rule'], x['value']) for x in ov['records'] if x['subject']['entity'] == 'J')
    assert at_j1 == [('derived', 'path:w1', 'overridden', True), ('derived', 'path:w2', 'overridden', False), ('registered', 'input', 'input', False)], at_j1
    assert at(ov['timeline'], 'OUT') == [(2, False, 'path:w3')], ov['timeline']
    assert ov['same'] and ov['replay'], ov

    # Device delay 0 and 2 (definitions in an inline test pack; wQ has Path delay 2).
    dl = r['delay']
    assert dl['pack'], dl
    assert at(dl['d0']['timeline'], 'G') == [(1, True, 'path:wS'), (1, True, 'rule:test.buf@1')], dl['d0']
    assert at(dl['d0']['timeline'], 'Q') == [(3, True, 'path:wQ')] and dl['d0']['defs'] == ['test.buf@1'], dl['d0']
    assert at(dl['d2']['timeline'], 'G') == [(1, True, 'path:wS'), (3, True, 'rule:test.buf@2')], dl['d2']
    assert at(dl['d2']['timeline'], 'Q') == [(5, True, 'path:wQ')] and dl['d2']['ticks'] == [0, 1, 3, 5, None], dl['d2']
    # Transport delay: a one-tick pulse is carried through the device delay.
    assert at(dl['pulse']['timeline'], 'G') == [(1, True, 'path:wS'), (2, False, 'path:wS'), (3, True, 'rule:test.buf@2'), (4, False, 'rule:test.buf@2')], dl['pulse']
    assert at(dl['pulse']['timeline'], 'Q') == [(5, True, 'path:wQ'), (6, False, 'path:wQ')], dl['pulse']
    assert dl['pulse']['bytes'] == dl['pulseRev']['bytes'] and all(dl[k]['replay'] for k in ('d0', 'd2', 'pulse')), dl

    # BUDGET_SPENT: refused with the count left in the queue; nothing of the tick applied.
    bu = r['budget']
    assert bu['first']['ok'] and bu['first']['tick'] == 0 and len(bu['first']['records']) == 2, bu['first']
    assert bu['second']['ok'] is False and bu['second']['code'] == 'BUDGET_SPENT' and bu['second']['tick'] == 1 and bu['second']['left'] == 2, bu['second']
    assert bu['third'] == bu['second'] and bu['unchanged'] and bu['trace'] and bu['tick'] == 0 and bu['spent'] == 2, bu
    assert bu['exact']['last'] == {'ok': True, 'tick': None, 'records': []} and bu['exact']['spent'] == 6, bu['exact']
    assert bu['five']['last']['code'] == 'BUDGET_SPENT' and bu['five']['last']['tick'] == 2 and bu['five']['last']['left'] == 1 and bu['five']['tick'] == 1, bu['five']
    # Power-on: tick 0 is processed even with nothing scheduled at it.
    assert bu['defaults'] == {'budget': 10000, 'seed': '0', 'inputs': [], 'quiet': {'ok': True, 'tick': 0, 'records': []}}, bu['defaults']

    # Step 2: refusals at start.
    for k, res in r['inputInvalid'].items():
        assert res['ok'] is False and res['code'] == 'INPUT_INVALID' and res['message'], (k, res)
    assert 'output of logic.and@1' in r['inputInvalid']['deviceOutput']['message'] and r['inputOk']['deviceInput'], r
    assert r['inputOk']['distinctTicks'] and r['inputOk']['compat'] == {'entity': 'A', 'point': 'self', 'channel': 'main', 'value': True, 'at': 0}, r['inputOk']
    assert r['mergeForm']['ok'] is False and r['mergeForm']['code'] == 'MERGE_FORM' and r['mergeForm']['subject'] == 'component:J:self:main', r['mergeForm']
    assert r['mergeFormOk'] == [True] * 7, r['mergeFormOk']
    assert r['runRefused']['unresolved'] == {'ok': False, 'code': 'RUN_REFUSED', 'codes': ['DEFINITION_UNRESOLVED']}, r['runRefused']
    assert r['runRefused']['delay'] == {'ok': False, 'code': 'RUN_REFUSED', 'codes': ['PATH_DELAY_INVALID']}, r['runRefused']

    # Step 15: the placeholder self form loads clean, checks and runs exactly as the clean form.
    sf = r['selfForm']
    clean = [{'id': 'self', 'channels': [{'id': 'main', 'merge': {'combine': 'or'}}]}]
    assert sf['stored'] == clean and sf['compact'] == clean and sf['ports'] == [['self', [{'id': 'main', 'merge': {'combine': 'or'}}]]], sf
    assert sf['check'] and sf['sameHash'] and sf['sameTrace'], sf
    # The ledger's chain, and a run is plain JSON.
    for e in r['chain']:
        assert e['prevOk'] and e['hashOk'] and e['keys'] == ['body', 'hash', 'kind', 'prev', 'seq'], e
    assert r['jsonSafe'], 'a run must be JSON-safe'

    # Slice 1c, settle: quiet, oscillating (with its period and subjects) and budget.
    st = r['settle']
    assert st['quiet'] == {'result': {'kind': 'quiet'}, 'tick': 2, 'again': {'kind': 'quiet'}, 'same': True}, st['quiet']
    assert st['loop']['result'] == {'kind': 'oscillating', 'period': 2, 'subjects': ['G.a.main', 'G.q.main']} and st['loop']['tick'] == 2, st['loop']
    assert st['loop']['again'] == st['loop']['result'] and st['loop']['tickAgain'] == 4, st['loop']
    assert st['loopLate']['result'] == st['loop']['result'] and st['loopLate']['tick'] == 6, st['loopLate']
    # A delay-2 NOT feeding itself through a delay-1 Path: q changes every 3 ticks, so the state repeats every 6.
    assert st['loop2']['qs'] == [[2, True], [5, False]], st['loop2']
    assert st['loop2']['result'] == {'kind': 'oscillating', 'period': 6, 'subjects': ['G.a.main', 'G.q.main']} and st['loop2']['tick'] == 6, st['loop2']
    assert st['budget'] == {'result': {'kind': 'budget', 'left': 2}, 'tick': 0, 'spent': 2}, st['budget']
    assert st['budgetLoop'] == {'result': {'kind': 'budget', 'left': 1}, 'tick': 0}, st['budgetLoop']
    assert st['invalid']['ok'] is False and st['invalid']['code'] == 'RUN_INVALID', st['invalid']
    assert st['bench']['kind'] in ('quiet', 'oscillating', 'budget'), st['bench']

    # Slice 1c, query: passive (the run's canonical bytes unchanged after 50 queries), in record order.
    qy = r['query']
    assert qy['passive'] and qy['stable'] and qy['copies'], qy
    assert qy['G'] == qy['all'] and len(qy['G']) == 3, qy
    assert qy['Gq'] == [['q', True]] and qy['other'] == [] and qy['none'] == [], qy
    assert qy['refused'] == ['QUERY_INVALID'] * 5 and qy['invalid'] == 'RUN_INVALID', qy

    # Slice 1c, the run receipt: its shape, and head equal to the trace's head.
    rc = r['receipt']
    assert rc['format'] == 'soveraeign.schematic/run-receipt@0.1', rc['format']
    assert rc['operations'] == ['schematic.run.start', 'schematic.run.step', 'schematic.run.settle', 'schematic.run.trace', 'schematic.state.query', 'schematic.run.replay', 'schematic.run.drop'], rc['operations']
    assert rc['unknown'] and 'RUN_OPERATION_UNKNOWN' in rc['unknown'], rc['unknown']
    keys = ['error', 'handle', 'head', 'ok', 'operation', 'result', 'runId', 'schema', 'tickAfter', 'tickBefore']
    for receipt, head in rc['receipts']:
        assert sorted(receipt) == keys and receipt['schema'] == rc['format'], receipt
        assert receipt['head'] == head, (receipt['operation'], receipt['head'], head)
        if receipt['ok']:
            assert receipt['error'] is None, receipt
        else:
            assert receipt['result'] is None and sorted(receipt['error']) in (['code', 'message'], ['code', 'details', 'message']) and receipt['error']['message'], receipt
        assert receipt['handle'] is None, 'a receipt built outside a registry has no handle'
    ops = [(x['operation'], x['ok'], x['tickBefore'], x['tickAfter']) for x, _ in rc['receipts']]
    assert ops == [('schematic.run.start', True, None, None), ('schematic.run.step', True, None, 0), ('schematic.run.settle', True, 0, 2),
                   ('schematic.state.query', True, 2, 2), ('schematic.run.trace', True, 2, 2), ('schematic.run.replay', True, None, 2),
                   ('schematic.run.step', False, 0, 0), ('schematic.state.query', False, 2, 2), ('schematic.run.start', False, None, None)], ops
    start, step, settle, query, trace, replayed, spent, badQuery, badStart = [x for x, _ in rc['receipts']]
    assert start['result']['budget'] == 10000 and start['result']['replayKey']['inputs'] == [dict(i, channel='main') for i in (
        {'entity': 'A', 'point': 'self', 'value': True, 'at': 0}, {'entity': 'B', 'point': 'self', 'value': True, 'at': 0})], start
    assert step['result']['tick'] == 0 and len(step['result']['records']) == 2 and settle['result'] == {'kind': 'quiet'}, (step, settle)
    assert [x['subject']['entity'] for x in query['result']] == ['Q'] and trace['result']['head'] == trace['head'], (query, trace)
    assert replayed['runId'] == rc['runId'] and list(replayed['result']) == ['records'] and replayed['result']['records'] == trace['result']['records'], replayed
    assert spent['error']['code'] == 'BUDGET_SPENT' and badQuery['error']['code'] == 'QUERY_INVALID', (spent, badQuery)
    assert badStart['error']['code'] == 'INPUT_INVALID' and (badStart['runId'], badStart['head'], badStart['tickAfter']) == (None, None, None), badStart
    assert rc['refusedStep'] == 'RUN_INVALID', rc['refusedStep']

    # Slice 1c, the registry every surface keeps: addressed by handle, never touching the document.
    rg = r['registry']
    handle = re.compile(r'^[0-9a-f]{12}\.[1-9][0-9]*$')
    assert rg['start']['ok'] and rg['start']['handle'] == rg['start']['runId'] + '.1' and handle.match(rg['start']['handle']), rg['start']
    assert rg['settle']['result'] == {'kind': 'quiet'} and rg['settle']['runId'] == rg['start']['runId'] and rg['settle']['handle'] == rg['start']['handle'], rg
    assert rg['trace'] == {'head': rg['settle']['head'], 'traceHead': rg['settle']['head'], 'through': 2, 'handle': rg['start']['handle']} and rg['query'] == [True], rg
    assert rg['replay'] == {'ok': True, 'runId': rg['start']['runId'], 'handle': None, 'head': rg['settle']['head'], 'tickAfter': 2}, rg['replay']
    assert rg['byRunId'] == 'RUN_NOT_FOUND', 'a run is addressed by its handle, not its run id'
    assert rg['again'] == {'runId': rg['start']['runId'], 'handle': rg['start']['runId'] + '.2', 'firstThrough': 2, 'secondTick': 0, 'firstStill': 2, 'firstBytes': True}, rg['again']
    assert rg['docUnchanged'], rg
    for operation, ok, code, run_id, run_handle, head in rg['unknown']:
        assert (ok, code, run_id, run_handle, head) == (False, 'RUN_NOT_FOUND', None, None, None), (operation, ok, code)
    assert rg['extraKey'] == 'INPUT_INVALID' and rg['notObject'] == 'INPUT_INVALID', rg
    cap, cap_huge, cap_ok, limit, engine_uncapped = rg['cap']
    assert cap['code'] == 'INPUT_INVALID' and '1000000' in cap['message'] and cap_huge == 'INPUT_INVALID' and cap_ok and limit == 1000000 and engine_uncapped, rg['cap']
    assert rg['badPack'] == 'PACK_INVALID' and rg['noPacks'] == 'PACK_INVALID', rg
    empty_start, empty_replay, empty_plain = rg['emptyPacks']
    for e in (empty_start, empty_replay):
        assert e == {'code': 'PACK_INVALID', 'message': 'this page carries no packs', 'details': {'definitions': ['logic.and@1']}}, e
    assert empty_plain, 'a document with no definitions runs without packs'
    dt = r['details']
    assert dt['budget'] == {'code': 'BUDGET_SPENT', 'message': dt['budget']['message'], 'details': {'tick': 0, 'left': 2}}, dt['budget']
    assert dt['trace']['code'] == 'TRACE_INVALID' and dt['trace']['details']['entry'] == 1 and dt['trace']['details']['errors'], dt['trace']
    assert dt['key']['code'] == 'REPLAY_KEY_MISMATCH' and dt['key']['details'] == {'fields': ['documentId', 'documentHash', 'definitions']}, dt['key']
    assert dt['refused']['code'] == 'RUN_REFUSED' and [x['code'] for x in dt['refused']['details']['refusals']] == ['PATH_DELAY_INVALID'], dt['refused']
    assert 'details' not in dt['notFound'] and 'details' not in dt['input'], (dt['notFound'], dt['input'])

    # Slice 1c, settle is linear: the growing-queue case settles to budget in under 3 s.
    gr = r['grow']
    assert gr['result']['kind'] == 'budget' and gr['tick'] == gr['stepTick'] and gr['same'] and gr['queue'][0] > 1000, gr
    print(f"growing-queue settle at budget 30000: {gr['ms'] / 1000:.3f} s (stepping alone {gr['stepMs'] / 1000:.3f} s); queue {gr['queue'][0]}")
    assert gr['ms'] < 3000, f"settle took {gr['ms']:.0f} ms at budget 30000"
    # Settle's period equals the brute-force period on three cycles.
    brute = {b['name']: b for b in r['brute']}
    assert [b['result']['period'] for b in r['brute']] == [2, 6, 12], r['brute']
    for b in r['brute']:
        assert b['result']['kind'] == 'oscillating' and b['result']['period'] == b['brute'], b

    receipt_schema = json.loads((ROOT / 'formats/schematic.run-receipt.schema.json').read_text(encoding='utf-8'))
    assert receipt_schema['$id'] == 'soveraeign.schematic/run-receipt@0.1' and sorted(receipt_schema['required']) == keys, receipt_schema

    # Step 6: the trace schema and the file format doc.
    schema = json.loads((ROOT / 'formats/schematic.trace.schema.json').read_text(encoding='utf-8'))
    assert schema['$id'] == 'soveraeign.schematic/trace@0.1' and sorted(schema['required']) == ['budget', 'documentRevision', 'format', 'head', 'ledger', 'replayKey', 'through'], schema
    formats = (ROOT / 'DATA-FORMATS.md').read_text(encoding='utf-8')
    assert '.sovtrace' in formats and 'soveraeign.schematic/trace@0.1' in formats, 'DATA-FORMATS.md must document .sovtrace'
    assert 'soveraeign.schematic/run-receipt@0.1' in formats, 'DATA-FORMATS.md must name the run receipt'
    src = (ROOT / 'src/07-state-space.js').read_text(encoding='utf-8')
    assert 'Math.random' not in src and 'Date' not in src, 'the engine draws only from the seed and reads no clock'
    assert 'data-beta-module="src/07-state-space.js"' in (ROOT / 'index.html').read_text(encoding='utf-8'), 'index.html does not carry 07; run build.py'
    assert src.strip() in (ROOT / 'index.html').read_text(encoding='utf-8'), 'index.html carries a stale 07; run build.py'
    print('PASS state space run QA')


if __name__ == '__main__':
    main()
