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
const rehash=trace=>{let prev='0'.repeat(64);trace.ledger.forEach((e,i)=>{e.prev=prev;e.hash=C.sha256Hex(canon({seq:e.seq,kind:e.kind,body:e.body,prev}));prev=e.hash});return trace};

out.api={keys:Object.keys(S),version:S.RUNTIME_VERSION,fns:['startRun','step','traceOf','replay','validateTrace'].map(k=>typeof S[k])};

// Golden examples: a re-run is byte-identical to the stored trace, forward and in the reversed walk.
const vec=v=>[{entity:'A',point:'self',value:v[0]==='1',at:0},{entity:'B',point:'self',value:v[1]==='1',at:0}];
const mergeInputs=[{entity:'S1',point:'self',value:true,at:0},{entity:'S2',point:'self',value:false,at:0}];
const jobs=[['and.sov','and.00.sovtrace',vec('00')],['and.sov','and.01.sovtrace',vec('01')],['and.sov','and.10.sovtrace',vec('10')],['and.sov','and.11.sovtrace',vec('11')],
  ['merge.sov','merge.declared.sovtrace',mergeInputs],['merge.or.sov','merge.or.sovtrace',mergeInputs],['merge.stochastic.sov','merge.stochastic.sovtrace',mergeInputs]];
out.golden={};
for(const [sov,file,inputs] of jobs){
  const stored=fs.readFileSync(dir+'/'+file,'utf8'),trace=JSON.parse(stored);
  const docBefore=canon(read(sov)),doc=load(sov),docNorm=canon(doc),packBefore=canon(packs);
  const run=started({doc,packs,inputs});
  const startLedger=run.ledger.map(e=>({seq:e.seq,kind:e.kind,body:e.body}));
  const steps=settle(run);
  const bytes=canon(S.traceOf(run));
  const rev=started({doc:load(sov),packs,inputs,walk:'reverse'});settle(rev);
  const replayed=S.replay({trace,doc,packs});
  const signal=(e,p='self')=>run.signal[K(e,p)]===true;
  out.golden[file]={
    same:bytes===stored,reversed:canon(S.traceOf(rev))===stored,storedCanonical:canon(trace)===stored,
    valid:S.validateTrace(trace),replay:{ok:replayed.ok,code:replayed.code||null,same:replayed.ok&&canon(replayed.records)===canon(trace.records)},
    docUnchanged:canon(doc)===docNorm&&canon(read(sov))===docBefore,packsUnchanged:canon(packs)===packBefore,
    lastStep:steps[steps.length-1],ticks:steps.filter(s=>s.tick!==null).map(s=>s.tick),
    startLedger,final:{Q:signal('Q'),J:signal('J'),OUT:signal('OUT')},
    records:trace.records,ledgerKinds:trace.ledger.map(e=>e.kind),draws:trace.ledger.filter(e=>e.kind==='draw').map(e=>e.body),
    recordChecks:trace.records.map(r=>S.validateRecord(r).ok),runId:run.id,replayKey:trace.replayKey,top:Object.keys(trace).sort(),budget:trace.budget,revision:trace.documentRevision
  };
}

// Tampering one byte of one ledger entry fails validateTrace at that entry and every entry after it.
{
  const stored=fs.readFileSync(dir+'/merge.stochastic.sovtrace','utf8');
  const flipHex=h=>(h[0]==='0'?'1':'0')+h.slice(1);
  const cases={
    startSeed:[0,e=>{e.body.seed='1'}],
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
  out.shape={notObject:S.validateTrace(null).ok,extraKey:S.validateTrace({...JSON.parse(stored),extra:1}).ok,format:S.validateTrace({...JSON.parse(stored),format:'soveraeign.schematic/trace@0.2'}).ok,emptyLedger:S.validateTrace({...JSON.parse(stored),ledger:[]}).ok,keyDiffers:S.validateTrace({...JSON.parse(stored),replayKey:{...JSON.parse(stored).replayKey,seed:'9'}})};
}

// REPLAY_KEY_MISMATCH: a changed runtimeVersion (the chain rehashed so the trace itself is valid), a changed document.
{
  const stored=fs.readFileSync(dir+'/and.11.sovtrace','utf8');
  const t=JSON.parse(stored);t.replayKey.runtimeVersion='state-space@2';t.ledger[0].body.runtimeVersion='state-space@2';rehash(t);
  const unhashed=JSON.parse(stored);unhashed.replayKey.runtimeVersion='state-space@2';unhashed.ledger[0].body.runtimeVersion='state-space@2';
  const changed=load('and.sov');changed.components.find(c=>c.id==='Q').x+=10;
  const before=canon(changed);
  out.keyMismatch={runtime:S.replay({trace:t,doc:load('and.sov'),packs}),runtimeValid:S.validateTrace(t).ok,unhashed:S.replay({trace:unhashed,doc:load('and.sov'),packs}),
    doc:S.replay({trace:JSON.parse(stored),doc:changed,packs}),docUnchanged:canon(changed)===before,
    seed:(()=>{const x=JSON.parse(stored);x.replayKey.seed='7';x.ledger[0].body.seed='7';rehash(x);return S.replay({trace:x,doc:load('and.sov'),packs})})()};
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
const withMerge=(mergeSpec,base='merge.stochastic.sov')=>{const d=read(base);d.components.find(c=>c.id==='J').config.attachmentPoints=[{id:'self',side:'left',t:.5,flow:'duplex',channels:[{id:'main',merge:mergeSpec}]}];return D.normalizeDocument(d)};
const timeline=run=>run.records.map(r=>[r.time.logical,r.subject.entity,r.subject.point,r.value,r.kind,r.observer,r.provenance.rule]);
{
  const q=(order,inputs,walk)=>{const run=started({doc:withMerge({combine:'queue',order:{kind:'declared',paths:order}}),packs,inputs,walk});const steps=settle(run);return {timeline:timeline(run),ticks:steps.map(s=>s.tick),bytes:canon(S.traceOf(run)),queues:run.queues}};
  const three=read('merge.stochastic.sov');three.components.push({id:'S3',symbolId:'point',x:80,y:360,config:{label:'S3'}});
  three.wires.push({id:'w4',a:'S3',aSide:'self',aAttachment:{kind:'attachment-ref',componentId:'S3',pointId:'self'},b:'J',bSide:'self',bAttachment:{kind:'attachment-ref',componentId:'J',pointId:'self'},config:{direction:'forward'}});
  three.components.find(c=>c.id==='J').config.attachmentPoints=[{id:'self',side:'left',t:.5,flow:'duplex',channels:[{id:'main',merge:{combine:'queue',order:{kind:'declared',paths:['w4']}}}]}];
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
  const go=(ref,inputs,walk)=>{const run=started({doc:docFor(ref),packs:[testPack.pack],inputs,walk});const steps=settle(run);return {timeline:timeline(run),ticks:steps.map(s=>s.tick),bytes:canon(S.traceOf(run)),defs:run.ledger[0].body.definitions,replay:S.replay({trace:S.traceOf(run),doc:docFor(ref),packs:[testPack.pack]}).ok}};
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
    defaults:(()=>{const r=started({doc:load('and.sov'),packs});return {budget:r.budget,seed:r.seed,inputs:r.ledger[0].body.inputs,quiet:S.step(r)}})()};
}

// Refusals at start.
{
  const doc=load('and.sov'),A=(o)=>({entity:'A',point:'self',value:true,at:0,...o});
  const cases={
    unknownEntity:[A({entity:'Z'})],unknownPort:[A({point:'left'})],unknownChannel:[A({channel:'aux'})],unknownKey:[A({wire:'wA'})],
    valueNumber:[A({value:1})],valueString:[A({value:'true'})],valueMissing:[{entity:'A',point:'self',at:0}],
    atNegative:[A({at:-1})],atFraction:[A({at:1.5})],atString:[A({at:'0'})],atMissing:[{entity:'A',point:'self',value:true}],
    duplicate:[A({}),A({value:false})],duplicateChannel:[A({}),A({channel:'main',value:false})],duplicateCompat:[A({}),A({point:'out'})],
    notObject:[7]
  };
  out.inputInvalid={};
  for(const [k,inputs] of Object.entries(cases)){const r=S.startRun({doc,packs,inputs});out.inputInvalid[k]={ok:r.ok,code:r.code,message:r.message}}
  out.inputOk={distinctTicks:S.startRun({doc,packs,inputs:[A({}),A({at:1,value:false})]}).ok,compat:S.startRun({doc,packs,inputs:[A({point:'out'})]}).run?.ledger[1].body};
  out.mergeForm=S.startRun({doc:withMerge({combine:'sum'}),packs,inputs:mergeInputs});
  out.mergeFormOk=['or','and','min','max','first','last','queue'].map(c=>S.startRun({doc:withMerge({combine:c}),packs,inputs:mergeInputs}).ok);
  const unresolved=S.startRun({doc,packs:[],inputs:vec('11')});
  const badDelay=read('and.sov');badDelay.wires[0].config.delay=0;
  const delay=S.startRun({doc:D.normalizeDocument(badDelay),packs,inputs:vec('11')});
  out.runRefused={unresolved:{ok:unresolved.ok,code:unresolved.code,codes:(unresolved.refusals||[]).map(r=>r.code)},delay:{ok:delay.ok,code:delay.code,codes:(delay.refusals||[]).map(r=>r.code)}};
}

// Only the engine appends; the ledger is hash-chained.
{
  const run=started({doc:load('merge.stochastic.sov'),packs,inputs:mergeInputs});settle(run);
  out.chain=run.ledger.map((e,i)=>({seq:e.seq,prevOk:e.prev===(i?run.ledger[i-1].hash:'0'.repeat(64)),hashOk:e.hash===C.sha256Hex(canon({seq:e.seq,kind:e.kind,body:e.body,prev:e.prev})),keys:Object.keys(e).sort()}));
  out.jsonSafe=canon(JSON.parse(JSON.stringify(run)))===canon(run);
}
process.stdout.write(JSON.stringify(out));
"""


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
    assert 'settle' not in api['keys'], 'settle is slice 1c'

    # Step 8 + 9: every golden re-runs byte-identical (forward and reversed walk) and replays.
    names = sorted(p.name for p in STATE.iterdir())
    assert names == ['and.00.sovtrace', 'and.01.sovtrace', 'and.10.sovtrace', 'and.11.sovtrace', 'and.sov',
                     'merge.declared.sovtrace', 'merge.or.sov', 'merge.or.sovtrace', 'merge.sov',
                     'merge.stochastic.sov', 'merge.stochastic.sovtrace'], names
    run_id = re.compile(r'^[0-9a-f]{12}$')
    for file, g in r['golden'].items():
        assert g['same'], f'{file}: a re-run is not byte-identical to the stored trace'
        assert g['reversed'], f'{file}: the reversed walk changes the trace'
        assert g['storedCanonical'], f'{file}: the stored trace is not in canonical encoding'
        assert g['valid'] == {'ok': True, 'entry': None, 'errors': []}, (file, g['valid'])
        assert g['replay'] == {'ok': True, 'code': None, 'same': True}, (file, g['replay'])
        assert g['docUnchanged'] and g['packsUnchanged'], (file, 'startRun/step/replay mutated doc or packs')
        assert g['lastStep'] == {'ok': True, 'tick': None, 'records': []}, (file, g['lastStep'])
        assert g['top'] == ['budget', 'documentRevision', 'format', 'ledger', 'records', 'replayKey'], g['top']
        assert g['budget'] == 10000 and g['revision'] == 0, g
        key = g['replayKey']
        assert sorted(key) == ['definitions', 'documentHash', 'documentId', 'inputs', 'runtimeVersion', 'seed', 'traceFormat'], key
        assert key['runtimeVersion'] == 'state-space@1' and key['traceFormat'] == 'soveraeign.schematic/trace@0.1' and key['seed'] == '0', key
        assert re.fullmatch(r'[0-9a-f]{64}', key['documentHash']), key
        assert g['startLedger'][0] == {'seq': 0, 'kind': 'start', 'body': key}, g['startLedger'][0]
        assert [e['kind'] for e in g['startLedger']] == ['start', 'input', 'input'], g['startLedger']
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
                assert rec['provenance']['inputs'] and all(i in [x['id'] for x in g['records'][:n]] for i in rec['provenance']['inputs']), rec
        # Sequence order within a tick is (entity, point, channel, observable, kind).
        for a, b in zip(g['records'], g['records'][1:]):
            if a['time']['logical'] == b['time']['logical']:
                ka = (a['subject']['entity'], a['subject']['point'], a['subject']['channel'], a['observable'], a['kind'])
                kb = (b['subject']['entity'], b['subject']['point'], b['subject']['channel'], b['observable'], b['kind'])
                assert ka <= kb, (file, ka, kb)
            else:
                assert a['time']['logical'] < b['time']['logical'], (file, a, b)

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
    assert dec['draws'] == [] and dec['final'] == {'Q': False, 'J': False, 'OUT': False}, dec['final']
    assert orr['draws'] == [] and orr['final'] == {'Q': False, 'J': True, 'OUT': True}, orr['final']
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
                          'keyDiffers': {'ok': False, 'entry': 0, 'errors': ['ledger 0: the start entry does not carry the replayKey']}}, r['shape']

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
    assert bu['defaults'] == {'budget': 10000, 'seed': '0', 'inputs': [], 'quiet': {'ok': True, 'tick': None, 'records': []}}, bu['defaults']

    # Step 2: refusals at start.
    for k, res in r['inputInvalid'].items():
        assert res['ok'] is False and res['code'] == 'INPUT_INVALID' and res['message'], (k, res)
    assert r['inputOk']['distinctTicks'] and r['inputOk']['compat'] == {'entity': 'A', 'point': 'self', 'channel': 'main', 'value': True, 'at': 0}, r['inputOk']
    assert r['mergeForm']['ok'] is False and r['mergeForm']['code'] == 'MERGE_FORM' and r['mergeForm']['subject'] == 'component:J:self:main', r['mergeForm']
    assert r['mergeFormOk'] == [True] * 7, r['mergeFormOk']
    assert r['runRefused']['unresolved'] == {'ok': False, 'code': 'RUN_REFUSED', 'codes': ['DEFINITION_UNRESOLVED']}, r['runRefused']
    assert r['runRefused']['delay'] == {'ok': False, 'code': 'RUN_REFUSED', 'codes': ['PATH_DELAY_INVALID']}, r['runRefused']

    # The ledger's chain, and a run is plain JSON.
    for e in r['chain']:
        assert e['prevOk'] and e['hashOk'] and e['keys'] == ['body', 'hash', 'kind', 'prev', 'seq'], e
    assert r['jsonSafe'], 'a run must be JSON-safe'

    # Step 6: the trace schema and the file format doc.
    schema = json.loads((ROOT / 'formats/schematic.trace.schema.json').read_text(encoding='utf-8'))
    assert schema['$id'] == 'soveraeign.schematic/trace@0.1' and sorted(schema['required']) == ['budget', 'documentRevision', 'format', 'ledger', 'records', 'replayKey'], schema
    formats = (ROOT / 'DATA-FORMATS.md').read_text(encoding='utf-8')
    assert '.sovtrace' in formats and 'soveraeign.schematic/trace@0.1' in formats, 'DATA-FORMATS.md must document .sovtrace'
    src = (ROOT / 'src/07-state-space.js').read_text(encoding='utf-8')
    assert 'Math.random' not in src and 'Date' not in src, 'the engine draws only from the seed and reads no clock'
    assert 'data-beta-module="src/07-state-space.js"' in (ROOT / 'index.html').read_text(encoding='utf-8'), 'index.html does not carry 07; run build.py'
    assert src.strip() in (ROOT / 'index.html').read_text(encoding='utf-8'), 'index.html carries a stale 07; run build.py'
    print('PASS state space run QA')


if __name__ == '__main__':
    main()
