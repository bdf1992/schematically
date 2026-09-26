"""Messages on the state-space runtime (contract one-runtime-04-messages).

A message is a recorded value on the message channel: every Path carries that channel in each
direction it carries, which Paths carry is the graph core's passability, and an inject leaves by
the component's outgoing Paths the way the graph core's forward does (fanout, config.accepts,
refusal instead of a drop, a Point relaying on every carried Path but the one it came by). Every
hop is a record of form message with principal and hop, and a message flow traces and replays
byte for byte like a level run. Runs src/07-state-space.js with src/07-graph-core.js in Node.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r"""
const fs=require('fs');
require('./src/03-canonical.js');require('./src/03-notation-core.js');require('./src/06-attachment-core.js');
const D=require('./src/05-data-core.js'),S=require('./src/07-state-space.js'),G=require('./src/07-graph-core.js'),C=globalThis.SovSchematicCanonical;
const canon=C.canonicalize;
const pack=S.loadPack(JSON.parse(fs.readFileSync('data/core.logic.pack.json','utf8'))).pack,packs=[pack];
const out={};
const started=args=>{const s=S.startRun({packs,...args});if(!s.ok)throw new Error(JSON.stringify(s));return s.run};
const settle=run=>{for(let i=0;i<500;i++){const r=S.step(run);if(!r.ok)throw new Error(JSON.stringify(r));if(r.tick===null)return run}throw new Error('no quiet')};
const msgs=run=>run.records.filter(r=>r.form==='message');
const hops=(run,event)=>msgs(run).filter(r=>r.hop.event===event);
const inj=(entity,point,channel,extra={},at=0)=>({entity,point,channel:'message',value:{channel,payload:null,...extra},at});

// The carried (wire, direction) pairs equal the graph core's arcs, and the blocked legs its blocked list.
out.arcs={};
for(const f of ['08-gated-service.sov','09-print-ai-proof-run.sov','10-clocked-signals.sov','12-membrane.sov','13-half-adder.sov']){
  const doc=D.documentFromFilePayload(JSON.parse(fs.readFileSync('examples/'+f,'utf8')));
  const g=G.build(doc),run=started({doc});
  const byId=new Map(doc.wires.map(w=>[w.id,w]));
  const dev=g.arcs.map(a=>[a.wireId,a.from===byId.get(a.wireId).a&&a.fromPort===byId.get(a.wireId).aSide?'forward':'reverse',a.from,a.to]).map(x=>x.join(' ')).sort();
  const mine=[];for(const w of run.wires){if(w.forward)mine.push([w.id,'forward',w.a.entity,w.b.entity].join(' '));if(w.reverse)mine.push([w.id,'reverse',w.b.entity,w.a.entity].join(' '))}
  out.arcs[f]={dev,mine:mine.sort(),devBlocked:g.blocked.map(b=>[b.wireId,b.reason]),blocked:run.blocked.map(b=>[b.wire,b.reason]),
    messageOnEvery:run.wires.every(w=>w.channels.includes('message')),ports:canon(run.doc.components.map(c=>c.config.attachmentPoints??null))===canon(D.normalizeDocument(JSON.parse(JSON.stringify(doc))).components.map(c=>c.config.attachmentPoints??null))};
}

// The graph core's fixtures (tests/graph_core_qa.py), as documents.
const DUPLEX={out:{connections:[{id:'connection-1',flow:'duplex',access:'read-write'}]}};
const P=id=>({id,symbolId:'point',x:0,y:0,form:{dimension:0},config:{signalMode:'relay',ports:DUPLEX}});
const A=(id,extra={})=>({id,symbolId:'act',x:0,y:0,config:{signalMode:'relay',...extra}});
const doc=(components,wires)=>D.normalizeDocument({components,wires});
// A bare Point (no ports authored) passes work through to a passive card, once.
{
  const d=doc([A('s'),{id:'mid',symbolId:'point',x:0,y:0,form:{dimension:0}},A('z',{signalMode:'passive'})],[{id:'w1',a:'s',aSide:'out',b:'mid',bSide:'out'},{id:'w2',a:'mid',aSide:'out',b:'z',bSide:'in'}]);
  const run=settle(started({doc:d,inputs:[inj('s','out',null,{payload:1})]}));
  // The same with a two-way Path into the Point: it never relays back on the Path it came by.
  const d2=doc([A('s',{ports:DUPLEX}),{id:'mid',symbolId:'point',x:0,y:0,form:{dimension:0}},A('z',{signalMode:'passive'})],[{id:'w1',a:'s',aSide:'out',b:'mid',bSide:'out',config:{direction:'duplex'}},{id:'w2',a:'mid',aSide:'out',b:'z',bSide:'in'}]);
  const run2=settle(started({doc:d2,inputs:[inj('s','out',null,{payload:1})]}));
  out.bare={arrivedZ:hops(run,'arrived').filter(r=>r.subject.entity==='z').length,endZ:hops(run,'absorbed').filter(r=>r.subject.entity==='z').map(r=>r.value.id),
    relayed:hops(run,'sent').filter(r=>r.subject.entity==='mid').map(r=>r.hop.wire),blocked:run.blocked,
    duplexLegs:run2.wires.filter(w=>w.id==='w1').map(w=>[w.forward,w.reverse]),duplexRelayed:hops(run2,'sent').filter(r=>r.subject.entity==='mid').map(r=>r.hop.wire),
    duplexArrivedS:hops(run2,'arrived').filter(r=>r.subject.entity==='s').length};
}
// Fanout at a Point with accepts on its outgoing Paths.
const hub=()=>doc([A('src'),{...P('j'),config:{signalMode:'relay',ports:DUPLEX,flow:{policy:'fanout'}}},A('x',{signalMode:'passive'}),A('y',{signalMode:'passive'})],
  [{id:'w0',a:'src',aSide:'out',b:'j',bSide:'out'},{id:'wx',a:'j',aSide:'out',b:'x',bSide:'in',config:{accepts:['red']}},{id:'wy',a:'j',aSide:'out',b:'y',bSide:'in',config:{accepts:['blue','red']}}]);
out.fanout={};
for(const channel of ['red','green','blue']){
  const run=settle(started({doc:hub(),inputs:[inj('src','out',channel)]}));
  const at=e=>hops(run,'arrived').filter(r=>r.subject.entity===e).length;
  const trace=S.traceOf(run),replayed=S.replay({trace,doc:hub(),packs});
  out.fanout[channel]={x:at('x'),y:at('y'),refused:hops(run,'refused').map(r=>[r.subject.entity,r.hop.reason,r.value.id]),
    sent:hops(run,'sent').filter(r=>r.subject.entity==='j').map(r=>[r.value.id,r.value.parent,r.hop.wire,r.hop.to]),
    backToSrc:hops(run,'sent').some(r=>r.subject.entity==='j'&&r.hop.wire==='w0'),
    replay:{ok:replayed.ok,code:replayed.code||null,same:replayed.ok&&canon(replayed.records)===canon(trace.records)}};
}
// Ids are derived: the root is m-<ledger seq of its input>, a child <parent>.<n> in wire-id order.
{
  const inputs=[inj('src','out','red',{payload:{n:2}},3),inj('src','out','red',{payload:{n:1}},3)];
  const run=settle(started({doc:hub(),inputs}));
  const entries=run.ledger.filter(e=>e.kind==='input');
  out.ids={inputs:entries.map(e=>[e.seq,e.body.value.payload.n]),injected:hops(run,'injected').map(r=>[r.value.id,r.value.root,r.value.parent,r.value.payload.n,r.value.origin]),
    children:msgs(run).filter(r=>r.value.root==='m-1').map(r=>[r.value.id,r.value.parent,r.hop.event]),
    lineageRoots:[...new Set(msgs(run).map(r=>r.value.root))].sort(),
    seqOrdered:run.records.every((r,i)=>r.time.sequence===i),
    hopsOfOne:msgs(run).filter(r=>r.value.id==='m-1.0.1').map(r=>r.hop.event)};
}
// Three messages reaching one port in the same tick are delivered one per tick, in the recorded draw
// order; the run traces and replays byte for byte, forward and in the reversed walk.
{
  const threeRaw=()=>({components:[A('a'),A('b'),A('c'),A('z',{signalMode:'passive'})],wires:[{id:'wa',a:'a',aSide:'out',b:'z',bSide:'in'},{id:'wb',a:'b',aSide:'out',b:'z',bSide:'in'},{id:'wc',a:'c',aSide:'out',b:'z',bSide:'in'}]});
  const three=()=>D.normalizeDocument(threeRaw());
  const inputs=[inj('c','out','k',{payload:3}),inj('a','out','k',{payload:1}),inj('b','out','k',{payload:2})];
  // A seed whose draw is not the sorted order, so delivery order can only come from the draw.
  let seed=null,run=null;
  for(let i=0;i<64&&seed===null;i++){const r=settle(started({doc:three(),inputs,seed:String(i)}));const d=r.ledger.find(e=>e.kind==='draw');if(d&&canon(d.body.order)!==canon(d.body.paths)){seed=String(i);run=r}}
  const draw=run.ledger.find(e=>e.kind==='draw').body;
  const arrived=hops(run,'arrived').filter(r=>r.subject.entity==='z').map(r=>[r.time.logical,`${r.hop.wire}#${r.value.id}`]);
  const rev=settle(started({doc:three(),inputs,seed,walk:'reverse'}));
  const trace=S.traceOf(run),bytes=canon(trace),replayed=S.replay({trace:JSON.parse(bytes),doc:three(),packs});
  const tampered=JSON.parse(bytes);const i=tampered.ledger.findIndex(e=>e.kind==='draw');tampered.ledger[i].body.order=tampered.ledger[i].body.order.slice().reverse();
  let prev='0'.repeat(64);tampered.ledger.forEach(e=>{e.prev=prev;e.hash=C.sha256Hex(canon({seq:e.seq,kind:e.kind,body:e.body,prev}));prev=e.hash});tampered.head=prev;
  const midRun=[];{const r=started({doc:three(),inputs,seed});for(let k=0;k<20;k++){const t=S.traceOf(r),x=S.replay({trace:t,doc:three(),packs});midRun.push(x.ok&&canon(x.records)===canon(t.records));const s=S.step(r);if(s.tick===null)break}}
  out.queue={seed,draw,arrived,reversed:canon(S.traceOf(rev))===bytes,rerun:canon(S.traceOf(settle(started({doc:three(),inputs,seed}))))===bytes,
    replay:{ok:replayed.ok,code:replayed.code||null,same:replayed.ok&&canon(replayed.records)===canon(trace.records)},
    tampered:S.replay({trace:tampered,doc:three(),packs}).code,midRun,valid:S.validateTrace(JSON.parse(bytes)).ok,
    inputOrder:run.ledger.filter(e=>e.kind==='input').map(e=>e.body.entity)};
  // A declared order on the message channel puts its Paths first; any combine but queue is refused.
  const pointZ=merge=>{const d=threeRaw();d.components[3]={id:'z',symbolId:'point',x:0,y:0,form:{dimension:0},config:{attachmentPoints:[{id:'self',channels:[{id:'main'},{id:'message',merge}]}]}};for(const w of d.wires)w.bSide='out';return D.normalizeDocument(d)};
  const dz=S.startRun({doc:pointZ({combine:'queue',order:{kind:'declared',paths:['wc','wb','wa']}}),packs,inputs,seed});
  out.declared=dz.ok?hops(settle(dz.run),'arrived').filter(r=>r.subject.entity==='z').map(r=>r.hop.wire):dz;
  out.lastRefused=S.startRun({doc:pointZ({combine:'last'}),packs,inputs}).code||'started';
}
// An in-only port cannot emit: that leg is blocked, recorded once at the first tick with the graph
// core's reason, and nothing crosses it.
{
  const d=doc([A('a'),A('b')],[{id:'w1',a:'a',aSide:'in',b:'b',bSide:'out',config:{direction:'duplex'}}]);
  const run=settle(started({doc:d,inputs:[inj('a','in',null),inj('b','out',null,{},5)]}));
  const blocked=run.records.filter(r=>r.provenance.rule==='blocked');
  out.blocked={dev:G.build(d).blocked.map(b=>b.reason),records:blocked.map(r=>[r.subject.entity,r.value,r.form,r.observable,r.time.logical]),
    fromA:hops(run,'sent').filter(r=>r.subject.entity==='a').length,endA:hops(run,'delivered').filter(r=>r.subject.entity==='a').map(r=>r.value.id),
    toA:hops(run,'arrived').filter(r=>r.subject.entity==='a').map(r=>r.value.id),ticks:[...new Set(run.records.map(r=>r.time.logical))]};
  // Fully blocked one-way wire: refused at load by the existing flow check, as before.
  out.oneWay=S.startRun({doc:doc([A('a'),A('b')],[{id:'w1',a:'a',aSide:'in',b:'b',bSide:'in'}]),packs}).refusals?.map(r=>r.code);
}
// Records validate and carry principal and hop; a participant with a principal acts in its own name.
{
  const d=doc([A('s'),{...A('m'),config:{signalMode:'relay',principal:'svc:mailer'}},A('z',{signalMode:'passive'})],[{id:'w1',a:'s',aSide:'out',b:'m',bSide:'in'},{id:'w2',a:'m',aSide:'out',b:'z',bSide:'in'}]);
  const run=settle(started({doc:d,inputs:[inj('s','out','job',{payload:{caseId:'7',weight:1.5},principal:'svc:ops'})]}));
  const m=msgs(run);
  out.records={all:run.records.map(r=>S.validateRecord(r)),members:m.map(r=>['principal' in r,'hop' in r,r.channel===undefined,r.subject.channel]),
    principals:m.map(r=>[r.subject.entity,r.hop.event,r.principal]),payload:m.map(r=>canon(r.value.payload)),
    value:Object.keys(m[0].value).sort(),inputs:m.map(r=>r.provenance.inputs.length)};
  const good=m.find(r=>r.hop.event==='sent'),bad={};
  const variant=f=>{const r=JSON.parse(JSON.stringify(good));f(r);return S.validateRecord(r)};
  bad.event=variant(r=>{r.hop.event='teleported'});bad.hopKey=variant(r=>{r.hop.colour='red'});bad.wire=variant(r=>{r.hop.wire=''});
  bad.valueKey=variant(r=>{delete r.value.origin});bad.valueExtra=variant(r=>{r.value.extra=1});bad.parent=variant(r=>{r.value.parent=3});
  bad.principal=variant(r=>{r.principal=7});bad.hopOnLevel=variant(r=>{r.form='binary';r.value=true});bad.notObject=variant(r=>{r.value='m-1'});
  out.bad=Object.fromEntries(Object.entries(bad).map(([k,v])=>[k,v.ok]));
  out.goodNull=variant(r=>{r.principal=null;delete r.hop.wire;delete r.hop.to}).ok;
  out.badInput=['x',{channel:3},{extra:1},{principal:''}].map(v=>S.startRun({doc:d,packs,inputs:[{entity:'s',point:'out',channel:'message',value:v,at:0}]}).code);
}
// Level runs are unchanged: a document with no messages makes no message records.
{
  const d=D.normalizeDocument(JSON.parse(fs.readFileSync('examples/state/merge.stochastic.sov','utf8')));
  const run=settle(started({doc:d,inputs:[{entity:'S1',point:'self',value:true,at:0},{entity:'S2',point:'self',value:false,at:0}]}));
  out.levels={messages:msgs(run).length,forms:[...new Set(run.records.map(r=>r.form))]};
}
console.log(JSON.stringify(out));
"""


def main() -> None:
    proc = subprocess.run(['node', '-e', SCRIPT], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    r = json.loads(proc.stdout)

    # Dev passability: the carried (wire, direction) pairs are the graph core's arcs, on every example.
    for f, a in r['arcs'].items():
        assert a['dev'] and a['mine'] == a['dev'], (f, a['mine'], a['dev'])
        assert a['blocked'] == a['devBlocked'], (f, a['blocked'], a['devBlocked'])
        assert a['messageOnEvery'], (f, 'every carried Path carries the message channel')
        assert a['ports'], (f, 'declared ports do not change')

    # A bare Point relays; the passive card receives the message once and absorbs it.
    b = r['bare']
    assert b['arrivedZ'] == 1 and b['endZ'] == ['m-1.0.0'] and b['relayed'] == ['w2'] and b['blocked'] == [], b
    assert b['duplexLegs'] == [[True, True]], b['duplexLegs']
    assert b['duplexRelayed'] == ['w2'] and b['duplexArrivedS'] == 0, ('a Point relays on every carried Path but the one it came by', b)

    # Fanout with accepts (graph_core_qa.py:76-80).
    f = r['fanout']
    assert f['red']['x'] + f['red']['y'] == 2 and f['red']['refused'] == [], f['red']
    assert f['red']['sent'] == [['m-1.0.0', 'm-1.0', 'wx', 'x'], ['m-1.0.1', 'm-1.0', 'wy', 'y']], f['red']['sent']
    assert f['green']['x'] == 0 and f['green']['y'] == 0, f['green']
    assert f['green']['refused'] == [['j', 'no end accepts channel green', 'm-1.0']], ('never a silent drop', f['green'])
    assert f['blue']['x'] == 0 and f['blue']['y'] == 1 and f['blue']['refused'] == [], f['blue']
    for channel, x in f.items():
        assert not x['backToSrc'], (channel, 'a Point never relays back on the Path it came by')
        assert x['replay'] == {'ok': True, 'code': None, 'same': True}, (channel, x['replay'])

    # Derived ids and lineage.
    i = r['ids']
    order = [n for _, n in i['inputs']]
    assert [s for s, _ in i['inputs']] == [1, 2] and order == [1, 2], i['inputs']
    assert i['injected'] == [['m-1', 'm-1', None, 1, 'src'], ['m-2', 'm-2', None, 2, 'src']], i['injected']
    assert ['m-1.0', 'm-1', 'sent'] in i['children'] and ['m-1.0.1', 'm-1.0', 'sent'] in i['children'], i['children']
    assert i['lineageRoots'] == ['m-1', 'm-2'] and i['seqOrdered'], i
    assert i['hopsOfOne'] == ['sent', 'arrived', 'absorbed'], i['hopsOfOne']

    # Queue delivery: one per tick, in the recorded draw order; trace and replay byte for byte.
    q = r['queue']
    assert q['seed'] is not None, 'no seed in 0..63 draws other than the sorted order'
    assert q['draw']['channel'] == 'message' and q['draw']['entity'] == 'z', q['draw']
    assert sorted(q['draw']['paths']) == q['draw']['paths'] and q['draw']['order'] != q['draw']['paths'], q['draw']
    ticks = [t for t, _ in q['arrived']]
    assert [x for _, x in q['arrived']] == q['draw']['order'], (q['arrived'], q['draw'])
    assert ticks == [ticks[0], ticks[0] + 1, ticks[0] + 2], q['arrived']
    assert q['inputOrder'] == ['a', 'b', 'c'], q['inputOrder']
    assert q['reversed'] and q['rerun'] and q['valid'], q
    assert q['replay'] == {'ok': True, 'code': None, 'same': True}, q['replay']
    assert q['tampered'] == 'REPLAY_DIVERGED', q['tampered']
    assert q['midRun'] and all(q['midRun']), q['midRun']
    assert r['declared'] == ['wc', 'wb', 'wa'], r['declared']
    assert r['lastRefused'] == 'MERGE_FORM', r['lastRefused']

    # An in-only port cannot emit: its leg is blocked, recorded once, and nothing crosses it.
    bl = r['blocked']
    assert bl['dev'] == ['a.in cannot emit'], bl['dev']
    assert bl['records'] == [['w1', 'a.in cannot emit', 'categorical', 'path.carries', 0]], bl['records']
    assert bl['fromA'] == 0 and bl['endA'] == ['m-1', 'm-2.0'], ('a has no carried leg out: delivered', bl)
    assert bl['toA'] == ['m-2.0'] and len(bl['ticks']) > 1, bl
    assert r['oneWay'] == ['PATH_DIRECTION_FLOW'], r['oneWay']

    # Records validate and carry principal and hop.
    rec = r['records']
    assert all(v == {'ok': True, 'errors': []} for v in rec['all']), rec['all']
    assert all(x == [True, True, True, 'message'] for x in rec['members']), rec['members']
    assert rec['value'] == ['channel', 'id', 'origin', 'parent', 'payload', 'root'], rec['value']
    assert ['s', 'injected', 'svc:ops'] in rec['principals'] and ['s', 'sent', 'svc:ops'] in rec['principals'], rec['principals']
    assert ['m', 'sent', 'svc:mailer'] in rec['principals'] and ['z', 'arrived', 'svc:mailer'] in rec['principals'], ('a participant acts in its own name', rec['principals'])
    assert set(rec['payload']) == {'{"caseId":"7","weight":1.5}'}, rec['payload']
    assert rec['inputs'][0] == 0 and all(n == 1 for n in rec['inputs'][1:]), rec['inputs']
    assert all(v is False for v in r['bad'].values()), r['bad']
    assert r['goodNull'] is True
    assert r['badInput'] == ['INPUT_INVALID'] * 4, r['badInput']

    # Level runs make no message records.
    assert r['levels'] == {'messages': 0, 'forms': ['binary']}, r['levels']
    print('STATE SPACE MESSAGE PASS')


if __name__ == '__main__':
    main()
