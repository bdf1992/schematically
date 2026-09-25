"""Graph core QA: queries, junction policies, the message simulation, and saved scenarios.

Runs src/07-graph-core.js in Node, with no browser. Each behaviour is checked in both
directions: the declared case passes, and a mutation that removes the mechanism fails.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r"""
const assert=require('node:assert/strict');const fs=require('node:fs');
require('./src/06-attachment-core.js');const D=require('./src/05-data-core.js');const G=require('./src/07-graph-core.js');
const load=f=>JSON.parse(fs.readFileSync(f,'utf8'));
const print=load('examples/09-print-ai-proof-run.sov'),gated=load('examples/08-gated-service.sov');
const DUPLEX={out:{connections:[{id:'connection-1',flow:'duplex',access:'read-write'}]}};
const P=(id,x=0)=>({id,symbolId:'point',x,y:0,form:{dimension:0},config:{signalMode:'relay',ports:DUPLEX}});
const A=(id,extra={})=>({id,symbolId:'act',x:0,y:0,config:{signalMode:'relay',...extra}});
const W=(id,a,b,config)=>({id,a,aSide:'out',b,bSide:a===b?'in':(b.startsWith('j')?'out':'in'),...(config?{config}:{})});
const doc=(components,wires,extra={})=>({components,wires,...extra});

// Every saved scenario in the Print AI example passes.
assert.equal(D.validateDocument(D.documentFromFilePayload(print)).ok,true);
for(const sc of print.references.filter(r=>r.kind==='scenario')){const r=G.runScenario(print,sc);assert.equal(r.ok,true,sc.id+' '+JSON.stringify(r.checks))}

// Mutation: without effect identity a retry messages the customer twice, and the scenario says so.
{const mut=structuredClone(print);delete mut.components.find(c=>c.id==='notify').config.behavior.effect;
 const r=G.runScenario(mut,print.references.find(r=>r.id==='s-retry'));assert.equal(r.ok,false);assert.equal(r.checks.find(c=>c.name==='taps customer').actual,2)}
// Mutation: a restart that drops the ledger (fresh engine, no restore) re-sends.
{const sc=print.references.find(r=>r.id==='s-approve').data;const run=()=>{const {sim}=G.createSimulation(print,{handlers:sc.handlers});sim.inject('case',sc.steps[0].inject);sim.run();sim.resume(sim.parked()[0].id);sim.run();return sim.taps('customer').arrivals.length};
 assert.equal(run()+run(),2,'two engines without a shared ledger each send once')}
// Handing the ledger to a new engine keeps replay identity across processes.
{const sc=print.references.find(r=>r.id==='s-approve').data;const a=G.createSimulation(print,{handlers:sc.handlers}).sim;a.inject('case',sc.steps[0].inject);a.run();a.resume(a.parked()[0].id);a.run();
 const b=G.createSimulation(print,{handlers:sc.handlers,effects:a.effects()}).sim;b.inject('case',sc.steps[0].inject);b.run();b.resume(b.parked()[0].id);b.run();
 assert.equal(b.taps('customer').arrivals.length,0);assert.equal(b.log().filter(e=>e.event==='effect-replayed').length,1)}
// A handler nobody registered refuses; it never passes through silently.
{const {sim}=G.createSimulation(print,{handlers:{}});sim.inject('case',{payload:{caseId:'1',proof:'good'}});sim.run();
 assert.match(sim.refusals()[0].reason,/no handler registered: ingest/);assert.equal(sim.taps('customer').arrivals.length,0)}
// A failing effect handler leaves the effect ambiguous; retry is refused until reconciled.
{const sc=print.references[0].data;const {sim}=G.createSimulation(print,{handlers:{...sc.handlers,'send-email':()=>{throw new Error('socket closed')}}});
 const go=()=>{sim.inject('case',{payload:{caseId:'7',proof:'good'}});sim.run();sim.resume(sim.parked()[0].id);sim.run()};
 go();assert.equal(sim.effects()['notify:7'].status,'ambiguous');go();assert.match(sim.refusals().at(-1).reason,/ambiguous/);
 assert.equal(sim.reconcile('notify:7',{confirmed:true}).ok,true);go();assert.equal(sim.log().filter(e=>e.event==='effect-replayed').length,1);assert.equal(sim.taps('customer').arrivals.length,0)}

// Queries over the example.
assert.deepEqual(G.query(print,'cut',{from:'case',to:'customer'}).wires,['k1']);
assert.equal(G.query(print,'paths',{from:'case',to:'customer'}).paths.length,1);
assert.equal(G.query(print,'order').ok,true);
assert.deepEqual(G.query(print,'junctions').junctions.map(j=>j.id),['split']);
assert.equal(G.query(print,'reach',{from:'case'}).nodes.includes('customer'),true);
assert.equal(G.query(print,'untyped').points.length>0,true,'no schema declared yet: every wired point is reported');
assert.equal(G.query(print,'boundary',{componentId:'run'}).points.filter(p=>p.hosted).length,2);
assert.match(G.query(print,'export',{format:'dot'}).text,/"case" -> "run-in"/);
assert.match(G.query(print,'export',{format:'graphml'}).text,/<edge id="k1:case:run-in"/);
assert.equal(Object.keys(G.query(print,'export',{format:'jgf'}).graph.graph.nodes).length,print.components.length);
assert.equal(G.query(print,'nope').code,'UNKNOWN_QUERY');

// Classic 08 as authored: its boundary Points are out-only (the default for a Point's `out`),
// so nothing can enter them. The simulation reports that exactly as the signal view shows it.
assert.deepEqual(G.query(gated,'blocked').blocked.map(b=>b.wireId).sort(),['k1','k3','k6']);
// With its Points made duplex, the gate passes only after the grant opens its control point.
{const g8=structuredClone(gated);for(const c of g8.components)if(c.symbolId==='point')c.config.ports.out.connections=[{id:'connection-1',flow:'duplex',access:'read-write'}];
 const {sim}=G.createSimulation(g8,{});sim.inject('req',{payload:'r1'});sim.run();assert.match(sim.refusals()[0].reason,/gate is closed/);
 sim.inject('grant',{payload:{open:true}});sim.run();sim.inject('req',{payload:'r2'});sim.run();
 assert.equal(sim.taps('log').arrivals.length,1);assert.equal(sim.receipts().filter(r=>r.kind==='receipt').length,1)}

// Junction policies.
const hub=(policy,extra={})=>doc([A('src'),{...P('j'),config:{signalMode:'relay',ports:DUPLEX,flow:{policy,...extra}}},A('x',{signalMode:'passive'}),A('y',{signalMode:'passive'})],
  [W('w0','src','j'),{id:'wx',a:'j',aSide:'out',b:'x',bSide:'in',config:{accepts:['red']}},{id:'wy',a:'j',aSide:'out',b:'y',bSide:'in',config:{accepts:['blue','red']}}]);
{const {sim}=G.createSimulation(hub('fanout'));sim.inject('src',{channel:'red'});sim.run();assert.equal(sim.taps('x').arrivals.length+sim.taps('y').arrivals.length,2)}
{const {sim}=G.createSimulation(hub('fanout'));sim.inject('src',{channel:'green'});sim.run();assert.match(sim.refusals()[0].reason,/no end accepts channel green/,'never a silent drop')}
{const {sim}=G.createSimulation(hub('fanout'));sim.inject('src',{channel:'blue'});sim.run();assert.equal(sim.taps('x').arrivals.length,0,'x does not accept blue');assert.equal(sim.taps('y').arrivals.length,1)}
{const {sim}=G.createSimulation(hub('distribute',{by:'round-robin'}));for(let i=0;i<4;i++)sim.inject('src',{channel:'red'});sim.run();assert.equal(sim.taps('x').arrivals.length,2);assert.equal(sim.taps('y').arrivals.length,2)}
{const {sim}=G.createSimulation(hub('distribute',{by:'channel'}));sim.inject('src',{channel:'green'});sim.run();assert.match(sim.refusals()[0].reason,/no end accepts channel green/)}
{const {sim}=G.createSimulation(hub('distribute',{by:'key',key:'payload.k'}));for(let i=0;i<3;i++)sim.inject('src',{channel:'red',payload:{k:'same'}});sim.run();const n=[sim.taps('x').arrivals.length,sim.taps('y').arrivals.length].sort();assert.deepEqual(n,[0,3],'one key, one end')}
{const {sim}=G.createSimulation(hub('select'));sim.inject('src',{channel:'red'});sim.run();assert.match(sim.refusals()[0].reason,/select needs a handler/)}
// Join waits for every incoming wire, then emits one combined message.
{const d=doc([A('a'),A('b'),{...A('j'),config:{signalMode:'relay',flow:{policy:'join'}}},A('z',{signalMode:'passive'})],[{id:'wa',a:'a',aSide:'out',b:'j',bSide:'in'},{id:'wb',a:'b',aSide:'out',b:'j',bSide:'in'},{id:'wz',a:'j',aSide:'out',b:'z',bSide:'in'}]);
 const {sim}=G.createSimulation(d);sim.inject('a',{payload:1});sim.run();assert.equal(sim.taps('z').arrivals.length,0,'join waits');
 sim.inject('b',{payload:2});sim.run();const got=sim.taps('z').arrivals;assert.equal(got.length,1);assert.deepEqual(got[0].payload,{parts:{wa:1,wb:2}})}

// Buffer, limit, switch, human.
{const d=doc([A('s'),{...A('buf'),symbolId:'buffer',config:{signalMode:'relay',flow:{capacity:2,releaseMs:100}}},A('z',{signalMode:'passive'})],[{id:'w1',a:'s',aSide:'out',b:'buf',bSide:'in'},{id:'w2',a:'buf',aSide:'out',b:'z',bSide:'in'}]);
 const {sim}=G.createSimulation(d);for(let i=0;i<3;i++)sim.inject('s',{payload:i});sim.run();assert.equal(sim.taps('z').arrivals.length,2);assert.match(sim.refusals()[0].reason,/buffer full/);assert.equal(sim.state().time,220)}
{const d=doc([A('s'),{...A('lim'),symbolId:'limit'},A('z',{signalMode:'passive'})],[{id:'w1',a:'s',aSide:'out',b:'lim',bSide:'in'},{id:'w2',a:'lim',aSide:'out',b:'z',bSide:'in'}]);
 const {sim}=G.createSimulation(d);sim.inject('s');sim.run();assert.match(sim.refusals()[0].reason,/limit has no rate/)}
{const d=doc([A('s'),{...A('lim'),symbolId:'limit',config:{signalMode:'relay',flow:{rate:{count:1,windowMs:1000}}}},A('z',{signalMode:'passive'})],[{id:'w1',a:'s',aSide:'out',b:'lim',bSide:'in'},{id:'w2',a:'lim',aSide:'out',b:'z',bSide:'in'}]);
 const {sim}=G.createSimulation(d);sim.inject('s');sim.inject('s');sim.run();assert.equal(sim.taps('z').arrivals.length,1);assert.match(sim.refusals()[0].reason,/exceeded/)}
{const d=doc([A('s'),A('c'),{...A('sw'),symbolId:'switch'},A('z',{signalMode:'passive'})],[{id:'w1',a:'s',aSide:'out',b:'sw',bSide:'in'},{id:'w2',a:'sw',aSide:'out',b:'z',bSide:'in'},{id:'w3',a:'c',aSide:'out',b:'sw',bSide:'control'}]);
 const {sim}=G.createSimulation(d);sim.inject('s');sim.run();assert.match(sim.refusals()[0].reason,/switch is closed/);sim.inject('c',{payload:{open:true}});sim.run();sim.inject('s');sim.run();assert.equal(sim.taps('z').arrivals.length,1)}

// Cycles: a zero-latency cycle is refused at start; a timed one runs.
{const ring=lat=>doc([A('a'),A('b')],[{id:'w1',a:'a',aSide:'out',b:'b',bSide:'in',config:{latencyMs:lat}},{id:'w2',a:'b',aSide:'out',b:'a',bSide:'in',config:{latencyMs:lat}}]);
 const r=G.createSimulation(ring(0));assert.equal(r.code,'ZERO_LATENCY_CYCLE');assert.deepEqual(r.cycles[0].nodes,['a','b']);
 const {sim}=G.createSimulation(ring(5));sim.inject('a');const out=sim.run({maxEvents:50});assert.equal(out.code,'MAX_EVENTS');assert.equal(G.query(ring(5),'order').code,'CYCLE')}
// Direction and port flow: an in-only port cannot emit, so the wire is blocked and nothing flows.
{const d=doc([A('a'),A('b',{signalMode:'passive'})],[{id:'w1',a:'a',aSide:'in',b:'b',bSide:'in'}]);assert.match(G.query(d,'blocked').blocked[0].reason,/cannot emit/)}

// One session dispatches every tool the server and browser serve.
{const s=G.createSession();assert.equal(s.execute('schematic.sim.inject',print,{node:'case'}).code,'NO_SIMULATION');
 assert.equal(s.execute('schematic.sim.start',print,{scenarioId:'s-approve'}).ok,true);s.execute('schematic.sim.inject',print,{node:'case',payload:{caseId:'1',proof:'good'}});s.execute('schematic.sim.run',print,{});
 assert.equal(s.execute('schematic.sim.inspect',print,{what:'parked'}).parked.length,1);assert.equal(s.execute('schematic.sim.scenario',print,{id:'s-reject'}).ok,true);
 assert.deepEqual(G.tools().map(t=>t.name).sort(),s.names.sort())}
const manifest=JSON.parse(fs.readFileSync('mcp/tools.json','utf8')).tools;for(const t of G.tools())assert.ok(manifest.includes(t.name),t.name+' missing from mcp/tools.json');
console.log('GRAPH CORE PASS');
"""

out = subprocess.run(['node', '-e', SCRIPT], cwd=ROOT, capture_output=True, text=True)
if out.returncode != 0:
    raise SystemExit(out.stdout + out.stderr)
print(out.stdout.strip())
