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
// The run's ACL: only the mailer service may carry work out. A notify acting as anyone else is refused at the exit.
{const mut=structuredClone(print);mut.components.find(c=>c.id==='notify').config.principal='ai:rogue';
 const r=G.runScenario(mut,print.references.find(r=>r.id==='s-approve'));assert.equal(r.ok,false);assert.ok(r.refusals.some(x=>/ai:rogue may not exit Run/.test(x.reason)),r.refusals)}
// Every scenario of the clocked-signals example passes.
{const ten=load('examples/10-clocked-signals.sov');for(const sc of ten.references){const r=G.runScenario(ten,sc);assert.equal(r.ok,true,sc.id+' '+JSON.stringify(r.checks))}}
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

// Classic 08 as authored: a Point's own point is two-way (its spec says duplex), so its
// boundary Points carry work in and out and nothing is blocked.
assert.deepEqual(G.query(gated,'blocked').blocked,[]);
// The gate passes only after the grant opens its control point.
{const {sim}=G.createSimulation(gated,{});sim.inject('req',{payload:'r1'});sim.run();assert.match(sim.refusals()[0].reason,/gate is closed/);
 sim.inject('grant',{payload:{open:true}});sim.run();sim.inject('req',{payload:'r2'});sim.run();
 assert.equal(sim.taps('log').arrivals.length,1);assert.equal(sim.receipts().filter(r=>r.kind==='receipt').length,1)}

// A bare Point (no ports authored) is two-way by default: work passes through it.
{const d=doc([A('s'),{id:'mid',symbolId:'point',x:0,y:0,form:{dimension:0}},A('z',{signalMode:'passive'})],[{id:'w1',a:'s',aSide:'out',b:'mid',bSide:'out'},{id:'w2',a:'mid',aSide:'out',b:'z',bSide:'in'}]);
 assert.deepEqual(G.query(d,'blocked').blocked,[]);const {sim}=G.createSimulation(d);sim.inject('s',{payload:1});sim.run();assert.equal(sim.taps('z').arrivals.length,1)}
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

// ---- Signals: levels, edges, clocks, asserted versus derived.
const L=(id,value=0,extra={})=>({id,symbolId:'lever',x:0,y:0,config:{signal:{value},...extra}});
const DV=(id,signal={},extra={})=>({id,symbolId:'act',x:0,y:0,config:{signal:{mode:'derived',...signal},...extra}});
const CK=(id,clock,signal={})=>({id,symbolId:'clock',x:0,y:0,config:{signal:{clock,...signal}}});
const Wz=(id,a,b,bSide='in',lat=0)=>({id,a,aSide:'out',b,bSide,config:{latencyMs:lat}});
// A square clock ANDed with a lever: the output follows the clock only while the lever is up.
{const d=doc([CK('clk',{periodMs:100,duty:.5}),L('lev',1),DV('and',{combine:'and'})],[Wz('w1','clk','and'),Wz('w2','lev','and')]);
 const {sim}=G.createSimulation(d);sim.advance(299);
 const e=sim.edges({node:'clk'}).edges;assert.deepEqual(e.map(x=>x.polarity+x.at),['+0','-50','+100','-150','+200','-250']);
 assert.deepEqual(sim.edges({node:'and'}).edges.map(x=>x.polarity+x.at),['+0','-50','+100','-150','+200','-250']);
 sim.set('lev',0);sim.advance(100);assert.equal(sim.levels().and.value,0);assert.ok(sim.edges({node:'and'}).edges.every(x=>x.at<300||x.polarity==='-'));
 assert.equal(sim.set('and',1).code,'DERIVED_SIGNAL','a derived signal is computed, never set')}
// Continuous: a sine rises (+) and falls (−) in small steps; a binary threshold of it makes one + and one − per period.
{const d=doc([CK('wave',{periodMs:100,wave:'sine',sampleMs:10}),DV('level',{kind:'continuous',combine:'max'}),DV('bit',{kind:'binary',threshold:.5})],[Wz('w1','wave','level'),Wz('w2','wave','bit')]);
 const {sim}=G.createSimulation(d);sim.advance(199);
 const lv=sim.edges({node:'level'}).edges;assert.ok(lv.filter(e=>e.polarity==='+').length>=8&&lv.filter(e=>e.polarity==='-').length>=8,'continuous rises and falls');
 assert.ok(lv.every(e=>e.to>=0&&e.to<=1));assert.equal(sim.levels().level.kind,'continuous');
 assert.deepEqual(sim.edges({node:'bit'}).edges.map(e=>e.polarity),['+','-','+','-']);
 assert.ok(Object.values(sim.levels()).every(l=>l.kind==='continuous'||[0,1].includes(l.value)),'binary levels are 0 or 1')}
// Scheduling: a clock's rising edge starts work, as a message.
{const d=doc([CK('tick',{periodMs:1000,duty:.1,cycles:3},{on:'+',channel:'job'}),A('job',{signalMode:'passive'})],[Wz('w1','tick','job')]);
 const {sim}=G.createSimulation(d);sim.advance(10000);
 assert.equal(sim.taps('job').arrivals.filter(m=>m.channel==='job').length,3,'three periods, three jobs');
 assert.equal(sim.state().pending,0,'a clock with cycles stops')}
// An asserted signal is changed by an operation: set, a scheduled action, or a message.
{const d=doc([L('lev'),DV('out'),A('ctl')],[Wz('w1','lev','out'),{id:'w2',a:'ctl',aSide:'out',b:'lev',bSide:'in'}]);
 const {sim}=G.createSimulation(d);sim.at(50,{set:{node:'lev',value:1}});sim.at(80,{toggle:{node:'lev'}});sim.advance(100);
 assert.deepEqual(sim.edges({node:'out'}).edges.map(e=>e.polarity+e.at),['+50','-80']);
 sim.inject('ctl',{payload:{toggle:true}});sim.run();assert.equal(sim.levels().lev.value,1);assert.equal(sim.levels().out.value,1)}
// A control point gates a derived level.
{const d=doc([L('data',1),L('en'),DV('sw')],[Wz('w1','data','sw'),Wz('w2','en','sw','control')]);
 const {sim}=G.createSimulation(d);sim.run();assert.equal(sim.levels().sw.value,0,'closed without control');
 sim.set('en',1);sim.run();assert.equal(sim.levels().sw.value,1)}
// A clock needs a period; absence is refused, not defaulted.
assert.equal(G.createSimulation(doc([{id:'c',symbolId:'clock',x:0,y:0}],[])).code,'CLOCK_HAS_NO_PERIOD');
// Restarting mid-run keeps levels and the clock's schedule.
{const d=doc([CK('clk',{periodMs:100})],[]);const a=G.createSimulation(d).sim;a.advance(120);
 const b=G.createSimulation(d,{restore:a.snapshot()}).sim;b.advance(100);assert.deepEqual(b.edges({node:'clk'}).edges.map(e=>e.polarity+e.at),['+0','-50','+100','-150','+200'])}

// ---- Access control on a plane: messages and levels crossing its boundary.
const planeDoc=(acl,leverValue=1)=>doc([
  {id:'vault',symbolId:'plane',x:400,y:200,form:{dimension:2,regions:{interior:{state:'open'}}},config:{label:'Vault',attachmentDefaults:'none',...(acl?{acl}:{})}},
  {id:'door',symbolId:'point',x:250,y:200,canvasId:'canvas:component:vault',parentId:'vault',placement:{kind:'edge',hostId:'vault',side:'left',t:.5},form:{dimension:0},config:{signalMode:'relay',ports:{out:{face:'both',connections:[{id:'connection-1',flow:'duplex',access:'read-write'}]}}}},
  {...A('inside'),canvasId:'canvas:component:vault',parentId:'vault',config:{signalMode:'relay'}},
  A('outside'),{...L('lever',leverValue),config:{signal:{value:leverValue},principal:'svc:ops'}},L('anon',1)],
  [{id:'k1',a:'outside',aSide:'out',b:'door',bSide:'out',canvasId:'canvas:global'},{id:'k2',a:'door',aSide:'out',b:'inside',bSide:'in',canvasId:'canvas:component:vault'},
   {id:'k3',a:'lever',aSide:'out',b:'door',bSide:'out',canvasId:'canvas:global'},{id:'k4',a:'anon',aSide:'out',b:'door',bSide:'out',canvasId:'canvas:global'}]);
{const acl={entries:[{principal:'svc:*',allow:['enter']},{principal:'svc:intruder',deny:['enter']}]};
 const d=planeDoc(acl);const {sim}=G.createSimulation(d);
 sim.inject('outside',{principal:'svc:ops',payload:1});sim.inject('outside',{principal:'eve',payload:2});sim.inject('outside',{payload:3});sim.run();
 const got=sim.taps('inside').arrivals.filter(m=>m.channel!=='edge').map(m=>m.payload);assert.deepEqual(got,[1]);
 const reasons=sim.refusals().map(r=>r.reason);
 assert.ok(reasons.some(r=>/eve may not enter Vault/.test(r)),reasons);assert.ok(reasons.some(r=>/no principal may enter Vault anonymously/.test(r)),reasons);
 // Levels cross under the driving node's principal: the principalled lever drives the inside level...
 assert.equal(sim.levels().inside.value,1,'svc:ops lever drives the inside level');
 // ...and when only the anonymous lever drives the door, its level stops there.
 {const {sim:s2}=G.createSimulation(planeDoc(acl,0));s2.run();assert.ok(s2.refusals().some(r=>r.level&&r.node==='door'&&/anonymously/.test(r.reason)),'anonymous level refused at the door');assert.equal(s2.levels().inside.value,0)}
 assert.deepEqual(G.query(d,'acl',{componentId:'vault',principal:'svc:intruder',op:'enter'}).ok,false);
 assert.equal(G.query(d,'acl',{componentId:'vault',principal:'svc:ops',op:'enter'}).ok,true);
 assert.equal(G.query(d,'acl').planes[0].id,'vault')}
// Mutation: without the ACL every principal gets in.
{const {sim}=G.createSimulation(planeDoc(null));sim.inject('outside',{principal:'eve',payload:2});sim.run();assert.equal(sim.taps('inside').arrivals.filter(m=>m.payload===2).length,1)}
// Exit is checked on the way out.
{const d=doc([{id:'room',symbolId:'plane',x:400,y:200,form:{dimension:2,regions:{interior:{state:'open'}}},config:{attachmentDefaults:'none',label:'Room',acl:{entries:[{principal:'*',allow:['enter']}]}}},
   {id:'gate',symbolId:'point',x:550,y:200,canvasId:'canvas:component:room',parentId:'room',placement:{kind:'edge',hostId:'room',side:'right',t:.5},form:{dimension:0},config:{ports:{out:{face:'both',connections:[{id:'connection-1',flow:'duplex',access:'read-write'}]}}}},
   {...A('worker'),canvasId:'canvas:component:room',parentId:'room'},A('world',{signalMode:'passive'})],
   [{id:'e1',a:'worker',aSide:'out',b:'gate',bSide:'out',canvasId:'canvas:component:room'},{id:'e2',a:'gate',aSide:'out',b:'world',bSide:'in',canvasId:'canvas:global'}]);
 const {sim}=G.createSimulation(d);sim.inject('worker',{principal:'svc:a'});sim.run();assert.match(sim.refusals().find(r=>!r.level).reason,/svc:a may not exit Room/);assert.equal(sim.taps('world').arrivals.length,0)}

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
