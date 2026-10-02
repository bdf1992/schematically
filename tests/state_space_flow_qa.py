"""Flow cards on the state-space runtime (contract 06 of the one-runtime plan).

Gate, switch, buffer, limit, join, hold, the terminals and the junction policies run as flow
patterns (route@1, join@1, buffer@1, limit@1, gate@1, terminal@1, hold@1) reached through the
one binding lookup: a declared config.flow.policy other than fanout names flow.<policy>@1, else
the core.flow pack binds the card's symbol id. A stateful card keeps its memory as device.state
records. Asserted levels are set by set/toggle messages and an edge starts a message. Each case
is a case of tests/graph_core_qa.py, run in ticks (1 tick = 1 ms), checked against the graph core
on the same document, and every run replays byte for byte and gives the same trace walked in reverse.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r"""
const fs=require('fs');
require('./src/03-canonical.js');require('./src/03-notation-core.js');require('./src/06-attachment-core.js');
const D=require('./src/05-data-core.js'),S=require('./src/07-state-space.js'),C=globalThis.SovSchematicCanonical,canon=C.canonicalize;
const loadPack=f=>S.loadPack(JSON.parse(fs.readFileSync(f,'utf8')));
const logic=loadPack('data/core.logic.pack.json'),flow=loadPack('data/core.flow.pack.json');
const packs=[logic.pack,flow.pack];
const out={pack:{ok:flow.ok,errors:flow.errors,definitions:flow.ok?flow.pack.definitions.map(d=>`${d.id}@${d.version} ${d.pattern}`):[],bindings:flow.ok?flow.pack.bindings:null},
  flowPatterns:S.flowPatterns().map(p=>`${p.id}@${p.version}`),levelPatterns:S.patterns().map(p=>`${p.id}@${p.version}`)};

// A run to quiet, with its replay and its reversed walk: every case must replay byte for byte.
const runs={};
function go(name,doc,inputs,extra={}){
  const s=S.startRun({doc,packs,inputs,...extra});if(!s.ok)throw new Error(name+' '+JSON.stringify(s));
  const run=s.run;const settled=S.settle(run);
  const trace=S.traceOf(run),bytes=canon(trace);
  const replayed=S.replay({trace:JSON.parse(bytes),doc,packs});
  const rev=S.startRun({doc,packs,inputs,...extra,walk:'reverse'}).run;S.settle(rev);
  const again=S.startRun({doc,packs,inputs,...extra}).run;S.settle(again);
  runs[name]={settled,replay:replayed.ok&&canon(replayed.records)===canon(trace.records)&&canon(replayed.run.ledger)===canon(trace.ledger),replayCode:replayed.code||null,
    reversed:canon(S.traceOf(rev))===bytes,rerun:canon(S.traceOf(again))===bytes,valid:S.validateTrace(JSON.parse(bytes)).ok,
    invalidRecords:run.records.map(r=>S.validateRecord(r)).filter(v=>!v.ok).map(v=>v.errors),pending:run.pending.length,queues:Object.keys(run.queues).length,
    definitions:trace.replayKey.definitions};
  return run;
}
const msgs=run=>run.records.filter(r=>r.form==='message');
const hops=(run,event)=>msgs(run).filter(r=>r.hop&&r.hop.event===event);
const arrived=(run,entity)=>hops(run,'arrived').filter(r=>r.subject.entity===entity);
const refusals=run=>hops(run,'refused').map(r=>r.hop.reason);
const states=(run,entity)=>run.records.filter(r=>r.observable==='device.state'&&r.subject.entity===entity).map(r=>[r.time.logical,r.value]);
const inj=(entity,payload,channel=null,at=0,extra={})=>({entity,point:'out',channel:'message',value:{channel,payload,...extra},at});
const level=(run,entity)=>{const r=run.records.filter(x=>x.observable==='logic.level'&&x.subject.entity===entity&&x.subject.point==='right'&&x.provenance.rule!=='overridden');return r.length?r[r.length-1].value:null};
const levelChanges=(run,entity)=>{const r=run.records.filter(x=>x.observable==='logic.level'&&x.subject.entity===entity&&x.subject.point==='right'&&x.provenance.rule!=='overridden');const outl=[];let prev=false;for(const x of r){if(x.value!==prev)outl.push((x.value?'+':'-')+x.time.logical);prev=x.value}return outl};

// The graph core's fixtures (tests/graph_core_qa.py), as documents.
const DUPLEX={out:{connections:[{id:'connection-1',flow:'duplex',access:'read-write'}]}};
const P=id=>({id,symbolId:'point',x:0,y:0,form:{dimension:0},config:{signalMode:'relay',ports:DUPLEX}});
const A=(id,extra={})=>({id,symbolId:'act',x:0,y:0,config:{signalMode:'relay',...extra}});
const W=(id,a,b,config)=>({id,a,aSide:'out',b,bSide:a===b?'in':(b.startsWith('j')?'out':'in'),...(config?{config}:{})});
const raw=(components,wires)=>({components,wires});
const doc=r=>D.normalizeDocument(JSON.parse(JSON.stringify(r)));
const hub=(policy,extra={})=>raw([A('src'),{...P('j'),config:{signalMode:'relay',ports:DUPLEX,flow:{policy,...extra}}},A('x',{signalMode:'passive'}),A('y',{signalMode:'passive'})],
  [W('w0','src','j'),{id:'wx',a:'j',aSide:'out',b:'x',bSide:'in',config:{accepts:['red']}},{id:'wy',a:'j',aSide:'out',b:'y',bSide:'in',config:{accepts:['blue','red']}}]);
const dev={};

// Junction policies at a Point (graph_core_qa.py:81-84).
{const r=go('roundRobin',doc(hub('distribute',{by:'round-robin'})),[0,1,2,3].map(()=>inj('src',null,'red')));
 out.roundRobin={x:arrived(r,'x').length,y:arrived(r,'y').length,state:states(r,'j'),forwarded:hops(r,'forwarded').filter(x=>x.subject.entity==='j').map(x=>x.provenance.rule)}}
{const r=go('byChannel',doc(hub('distribute',{by:'channel'})),[inj('src',null,'green')]);out.byChannel={refused:refusals(r),x:arrived(r,'x').length,y:arrived(r,'y').length}}
{const r=go('byKey',doc(hub('distribute',{by:'key',key:'payload.k'})),[0,1,2].map(()=>inj('src',{k:'same'},'red')));out.byKey=[arrived(r,'x').length,arrived(r,'y').length].sort((a,b)=>a-b)}
{const r=go('select',doc(hub('select')),[inj('src',null,'red')]);out.select={refused:refusals(r),x:arrived(r,'x').length,y:arrived(r,'y').length}}
// Join waits for every incoming Path, then emits one combined message (86-88).
const joinDoc=raw([A('a'),A('b'),{...A('j'),config:{signalMode:'relay',flow:{policy:'join'}}},A('z',{signalMode:'passive'})],[{id:'wa',a:'a',aSide:'out',b:'j',bSide:'in'},{id:'wb',a:'b',aSide:'out',b:'j',bSide:'in'},{id:'wz',a:'j',aSide:'out',b:'z',bSide:'in'}]);
{const r=go('join',doc(joinDoc),[inj('a',1,null,0),inj('b',2,null,100)]);const z=arrived(r,'z');
 out.join={beforeB:z.filter(x=>x.time.logical<100).length,arrivals:z.length,payload:z.map(x=>x.value.payload),waiting:hops(r,'waiting').length,joined:hops(r,'joined').map(x=>x.value.id),state:states(r,'j')}}
// Buffer, limit, switch (91-98).
const bufDoc=raw([A('s'),{...A('buf'),symbolId:'buffer',config:{signalMode:'relay',flow:{capacity:2,releaseMs:100}}},A('z',{signalMode:'passive'})],[{id:'w1',a:'s',aSide:'out',b:'buf',bSide:'in'},{id:'w2',a:'buf',aSide:'out',b:'z',bSide:'in'}]);
{const r=go('buffer',doc(bufDoc),[0,1,2].map(i=>inj('s',i)));const z=arrived(r,'z');
 out.buffer={arrivals:z.length,refused:refusals(r),lastMs:Math.max(...z.map(x=>x.time.logical))*r.tickMs,buffered:hops(r,'buffered').length,released:hops(r,'released').map(x=>x.time.logical),state:states(r,'buf')}}
const limDoc=rate=>raw([A('s'),{...A('lim'),symbolId:'limit',...(rate?{config:{signalMode:'relay',flow:{rate}}}:{})},A('z',{signalMode:'passive'})],[{id:'w1',a:'s',aSide:'out',b:'lim',bSide:'in'},{id:'w2',a:'lim',aSide:'out',b:'z',bSide:'in'}]);
{const r=go('limitNoRate',doc(limDoc(null)),[inj('s',null)]);out.limitNoRate={refused:refusals(r),z:arrived(r,'z').length}}
{const r=go('limit',doc(limDoc({count:1,windowMs:1000})),[inj('s',1),inj('s',2)]);out.limit={z:arrived(r,'z').length,refused:refusals(r),state:states(r,'lim')}}
const swDoc=raw([A('s'),A('c'),{...A('sw'),symbolId:'switch'},A('z',{signalMode:'passive'})],[{id:'w1',a:'s',aSide:'out',b:'sw',bSide:'in'},{id:'w2',a:'sw',aSide:'out',b:'z',bSide:'in'},{id:'w3',a:'c',aSide:'out',b:'sw',bSide:'control'}]);
{const r=go('switch',doc(swDoc),[inj('s',null,null,0),inj('c',{open:true},null,100),inj('s',null,null,200)]);
 out.switch={refused:refusals(r),controlled:hops(r,'controlled').map(x=>[x.subject.entity,x.time.logical]),z:arrived(r,'z').map(x=>x.time.logical),state:states(r,'sw')}}
// Classic 08: the gate passes only after the grant opens its control point (66-70).
const gatedRaw=JSON.parse(fs.readFileSync('examples/08-gated-service.sov','utf8'));
{const r=go('gated',D.documentFromFilePayload(gatedRaw),[inj('req','r1',null,0),inj('grant',{open:true},null,100),inj('req','r2',null,200)]);
 out.gated={refused:refusals(r),log:arrived(r,'log').length,receipts:r.records.filter(x=>x.provenance.rule==='receipt').map(x=>[x.subject.entity,x.observable,x.value.payload]),
   holdState:states(r,'store'),gateState:states(r,'check')}}
// Signals: a clock's rising edge starts work as a message (127-130); a lever set by input, toggled, then by a message (131-135).
const L=(id,value=0,extra={})=>({id,symbolId:'lever',x:0,y:0,config:{signal:{value},...extra}});
const DV=(id,signal={},extra={})=>({id,symbolId:'act',x:0,y:0,config:{signal:{mode:'derived',...signal},...extra}});
const CK=(id,clock,signal={})=>({id,symbolId:'clock',x:0,y:0,config:{signal:{clock,...signal}}});
const Wz=(id,a,b,bSide='in',lat=0)=>({id,a,aSide:'out',b,bSide,config:{latencyMs:lat}});
const clockDoc=raw([CK('tick',{periodMs:1000,duty:.1,cycles:3},{on:'+',channel:'job'}),A('job',{signalMode:'passive'})],[Wz('w1','tick','job')]);
{const r=go('clock',doc(clockDoc),[]);
 out.clock={jobs:arrived(r,'job').filter(m=>m.value.channel==='job').length,edges:hops(r,'edge').map(x=>[x.time.logical,x.value.payload]),pending:r.pending.length,queues:Object.keys(r.queues).length}}
const leverDoc=raw([L('lev'),DV('out'),A('ctl')],[Wz('w1','lev','out'),{id:'w2',a:'ctl',aSide:'out',b:'lev',bSide:'in'}]);
{const r=go('lever',doc(leverDoc),[{entity:'lev',point:'out',channel:'main',value:true,at:50},{entity:'lev',point:'out',channel:'main',value:false,at:80},inj('ctl',{toggle:true},null,100)]);
 out.lever={outEdges:levelChanges(r,'out'),lev:level(r,'lev'),out:level(r,'out'),asserted:hops(r,'asserted').map(x=>[x.subject.entity,x.time.logical])}}

// No flow pack: the same cards relay by fanout, as before this contract.
{const s=S.startRun({doc:doc(swDoc),packs:[logic.pack],inputs:[inj('s',null)]});S.settle(s.run);out.noFlowPack={z:arrived(s.run,'z').length,refused:refusals(s.run),defs:s.run.ledger[0].body.replayKey.definitions}}
// A flow definition generates no ports, so no Component binds one through config.definition.
{const d=doc(swDoc);out.bindFlow=S.applyBind(d,'sw','flow.switch@1',packs).error?.code||'bound'}
// A pack binding naming a definition it does not hold, or a level pattern, is refused.
out.badBindings=[S.loadPack({...JSON.parse(fs.readFileSync('data/core.flow.pack.json','utf8')),bindings:{gate:'flow.nope@1'}}).errors.map(e=>e.code),
  S.loadPack({format:'soveraeign.schematic/pack@0.1',id:'x',version:1,definitions:[{id:'x.and',version:1,pattern:'truth_table@1',parameters:{inputs:['a'],outputs:['q'],table:[[0,1],[1,0]]}}],bindings:{gate:'x.and@1'}}).errors.map(e=>e.code)];
// The lookup: a declared policy first, then the pack's binding by symbol id.
out.lookup=[{symbolId:'gate'},{symbolId:'gate',config:{flow:{policy:'join'}}},{symbolId:'point',config:{flow:{policy:'distribute'}}},{symbolId:'act'},{symbolId:'act',config:{flow:{policy:'fanout'}}},{symbolId:'act',config:{flow:{policy:'merge'}}}].map(c=>S.flowBindingOf(c,packs));

// The graph core on the same documents (loaded last: the runs above never saw it).
const G=require('./src/07-graph-core.js');
const sim=d=>G.createSimulation(JSON.parse(JSON.stringify(d))).sim;
{const s=sim(hub('distribute',{by:'round-robin'}));for(let i=0;i<4;i++)s.inject('src',{channel:'red'});s.run();dev.roundRobin={x:s.taps('x').arrivals.length,y:s.taps('y').arrivals.length}}
{const s=sim(hub('distribute',{by:'channel'}));s.inject('src',{channel:'green'});s.run();dev.byChannel=s.refusals().map(r=>r.reason)}
{const s=sim(hub('distribute',{by:'key',key:'payload.k'}));for(let i=0;i<3;i++)s.inject('src',{channel:'red',payload:{k:'same'}});s.run();dev.byKey=[s.taps('x').arrivals.length,s.taps('y').arrivals.length].sort((a,b)=>a-b)}
{const s=sim(hub('select'));s.inject('src',{channel:'red'});s.run();dev.select=s.refusals().map(r=>r.reason)}
{const s=sim(joinDoc);s.inject('a',{payload:1});s.run();s.inject('b',{payload:2});s.run();dev.join=s.taps('z').arrivals.map(m=>m.payload)}
{const s=sim(bufDoc);for(let i=0;i<3;i++)s.inject('s',{payload:i});s.run();dev.buffer={arrivals:s.taps('z').arrivals.length,refused:s.refusals().map(r=>r.reason),time:s.state().time}}
{const s=sim(limDoc(null));s.inject('s');s.run();dev.limitNoRate=s.refusals().map(r=>r.reason)}
{const s=sim(limDoc({count:1,windowMs:1000}));s.inject('s');s.inject('s');s.run();dev.limit={z:s.taps('z').arrivals.length,refused:s.refusals().map(r=>r.reason)}}
{const s=sim(swDoc);s.inject('s');s.run();s.inject('c',{payload:{open:true}});s.run();s.inject('s');s.run();dev.switch={refused:s.refusals().map(r=>r.reason),z:s.taps('z').arrivals.length}}
{const s=sim(gatedRaw);s.inject('req',{payload:'r1'});s.run();s.inject('grant',{payload:{open:true}});s.run();s.inject('req',{payload:'r2'});s.run();dev.gated={refused:s.refusals().map(r=>r.reason),log:s.taps('log').arrivals.length,receipts:s.receipts().filter(r=>r.kind==='receipt').length}}
{const s=sim(clockDoc);s.advance(10000);dev.clock={jobs:s.taps('job').arrivals.filter(m=>m.channel==='job').length,pending:s.state().pending}}
{const s=sim(leverDoc);s.at(50,{set:{node:'lev',value:1}});s.at(80,{toggle:{node:'lev'}});s.advance(100);dev.lever={outEdges:s.edges({node:'out'}).edges.map(e=>e.polarity+e.at)};s.inject('ctl',{payload:{toggle:true}});s.run();dev.lever.lev=s.levels().lev.value;dev.lever.out=s.levels().out.value}
out.dev=dev;out.runs=runs;
console.log(JSON.stringify(out));
"""


def main() -> None:
    proc = subprocess.run(['node', '-e', SCRIPT], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    r = json.loads(proc.stdout)
    dev = r['dev']

    # The pack: twelve definitions, eight bindings by symbol id, seven flow patterns beside the level ones.
    assert r['pack']['ok'] and r['pack']['errors'] == [], r['pack']
    assert [d.split(' ')[0] for d in r['pack']['definitions']] == [f'flow.{x}@1' for x in ('fanout', 'distribute', 'select', 'join', 'buffer', 'limit', 'switch', 'gate', 'observe', 'receipt', 'refuse', 'hold')], r['pack']
    assert r['pack']['bindings'] == {s: f'flow.{s}@1' for s in ('buffer', 'gate', 'hold', 'limit', 'observe', 'receipt', 'refuse', 'switch')}, r['pack']
    assert r['flowPatterns'] == ['route@1', 'join@1', 'buffer@1', 'limit@1', 'gate@1', 'terminal@1', 'hold@1'], r['flowPatterns']
    assert r['levelPatterns'] == ['truth_table@1', 'merge@1', 'combine@1'], r['levelPatterns']
    assert r['lookup'] == ['flow.gate@1', 'flow.join@1', 'flow.distribute@1', None, None, None], r['lookup']
    assert r['bindFlow'] == 'DEFINITION_NOT_BINDABLE', r['bindFlow']
    assert r['badBindings'] == [['PACK_INVALID'], ['PACK_INVALID']], r['badBindings']

    # Every run: quiet, nothing left pending, valid records, a byte-identical replay, the same trace walked in reverse and run again.
    for name, run in r['runs'].items():
        assert run['settled'] == {'kind': 'quiet'}, (name, run['settled'])
        assert run['replay'] and run['replayCode'] is None, (name, 'replay', run)
        assert run['reversed'] and run['rerun'] and run['valid'], (name, run)
        assert run['invalidRecords'] == [], (name, run['invalidRecords'])
        assert run['pending'] == 0 and run['queues'] == 0, (name, run)

    # Round-robin: 4 messages, 2 and 2; the counter is device.state; the forward names its rule.
    rr = r['roundRobin']
    assert [rr['x'], rr['y']] == [2, 2] == [dev['roundRobin']['x'], dev['roundRobin']['y']], (rr, dev['roundRobin'])
    assert rr['state'] == [[10, {'rr': 4}]], rr['state']
    assert rr['forwarded'] == ['flow.distribute@1'] * 4, rr['forwarded']
    assert 'flow.distribute@1' in r['runs']['roundRobin']['definitions'], r['runs']['roundRobin']['definitions']
    # By channel: green is refused, never dropped.
    assert r['byChannel']['refused'] == ['no end accepts channel green'] == dev['byChannel'] and r['byChannel']['x'] + r['byChannel']['y'] == 0, (r['byChannel'], dev['byChannel'])
    # By key: one key, one end.
    assert r['byKey'] == [0, 3] == dev['byKey'], (r['byKey'], dev['byKey'])
    # Select needs a handler.
    assert r['select']['refused'] == ['select needs a handler (config.behavior.handler)'] == dev['select'], (r['select'], dev['select'])

    # Join waits, then one message with every part.
    j = r['join']
    assert j['beforeB'] == 0 and j['arrivals'] == 1 and j['payload'] == [{'parts': {'wa': 1, 'wb': 2}}] and dev['join'] == [{'parts': {'wa': 1, 'wb': 2}}], (j, dev['join'])
    assert j['waiting'] == 2 and j['joined'] == ['m-2.0.j'], j
    assert [s[0] for s in j['state']] == [10, 110] and j['state'][-1][1] == {'fifos': {}}, j['state']

    # Buffer: capacity 2, release every 100 ms: two arrive, the third is refused, the last at 220 ms.
    b = r['buffer']
    assert b['arrivals'] == 2 == dev['buffer']['arrivals'] and b['refused'] == ['buffer full (2)'] == dev['buffer']['refused'], (b, dev['buffer'])
    assert b['lastMs'] == 220 == dev['buffer']['time'], (b, dev['buffer'])
    assert b['buffered'] == 2 and b['released'] == [110, 210], b
    assert [s[0] for s in b['state']] == [10, 110, 210] and b['state'][-1][1] == {'queue': [], 'releasing': False}, b['state']

    # Limit: no rate is refused; 1 per 1000 ms passes one and refuses the next.
    assert r['limitNoRate']['refused'] == ['limit has no rate (config.flow.rate {count, windowMs})'] == dev['limitNoRate'] and r['limitNoRate']['z'] == 0, (r['limitNoRate'], dev['limitNoRate'])
    lm = r['limit']
    assert lm['z'] == 1 == dev['limit']['z'] and lm['refused'] == ['limit 1 per 1000ms exceeded'] == dev['limit']['refused'], (lm, dev['limit'])
    assert lm['state'] == [[10, {'arrivals': [10]}]], lm['state']

    # Switch: closed, opened by its control Path, then passes.
    sw = r['switch']
    assert sw['refused'] == ['switch is closed'] == dev['switch']['refused'] and sw['z'] == [220] and dev['switch']['z'] == 1, (sw, dev['switch'])
    assert sw['controlled'] == [['sw', 110]] and sw['state'] == [[110, {'open': True}]], sw

    # Classic 08: the gate is closed, the grant opens it, one log arrival and one receipt.
    g = r['gated']
    assert g['refused'] == ['gate is closed: no control has opened it'] and dev['gated']['refused'] == g['refused'], (g, dev['gated'])
    assert g['log'] == 1 == dev['gated']['log'] and len(g['receipts']) == 1 == dev['gated']['receipts'], (g, dev['gated'])
    assert g['receipts'] == [['log', 'receipt', 'r2']], g['receipts']
    assert g['holdState'] and g['holdState'][-1][1] == {'value': 'r2'} and g['gateState'][-1][1] == {'open': True}, g

    # A clock with on + and channel job: three periods, three job messages, nothing pending.
    ck = r['clock']
    assert ck['jobs'] == 3 == dev['clock']['jobs'] and ck['pending'] == 0 == dev['clock']['pending'] and ck['queues'] == 0, (ck, dev['clock'])
    assert [e[0] for e in ck['edges']] == [0, 1000, 2000] and ck['edges'][1][1] == {'node': 'tick', 'polarity': '+', 'from': 0, 'to': 1, 'at': 1000}, ck['edges']

    # A lever set at 50, toggled at 80, then toggled by a message.
    lv = r['lever']
    # The graph core reads its edges at 100 ms, before the message; the message's toggle reaches lev at 110.
    assert lv['outEdges'][:2] == ['+50', '-80'] == dev['lever']['outEdges'] and lv['outEdges'] == ['+50', '-80', '+110'], (lv, dev['lever'])
    assert lv['lev'] is True and lv['out'] is True and dev['lever']['lev'] == 1 and dev['lever']['out'] == 1, (lv, dev['lever'])
    assert lv['asserted'] == [['lev', 110]], lv['asserted']

    # Without core.flow the switch relays by fanout and names no flow definition.
    assert r['noFlowPack']['z'] == 1 and r['noFlowPack']['refused'] == [] and not any(d.startswith('flow.') for d in r['noFlowPack']['defs']), r['noFlowPack']

    print(f"STATE SPACE FLOW PASS: {len(r['runs'])} runs at parity with the graph core, each replayed byte for byte")


if __name__ == '__main__':
    main()
