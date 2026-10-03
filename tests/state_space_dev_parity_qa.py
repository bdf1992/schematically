"""The state-space engine against the graph core's own example checks (tests/graph_core_qa.py).

src/07-graph-core.js at 7b939e3 is the parity reference for the one runtime. Each case here runs
on src/07-state-space.js in ticks (tickMs 1) and is checked against the graph core on the same
document, as tests/state_space_acl_qa.py does, and every run replays byte for byte:

1. every scenario of examples/09-print-ai-proof-run.sov, its fixture read as authored (the
   evaluate score is stated in thousandths, 930), passes its expect block (graph_core_qa.py:25);
2. every scenario of examples/10-clocked-signals.sov passes its expect block (graph_core_qa.py:41):
   the alarm's edge message goes on from the alarm's own continueAt, as the graph core's setLevel
   hands it (7b939e3:469-473), so the limit card never refuses its own edge message;
3. the one named intended difference: planeDoc(acl,0) of graph_core_qa.py:147-163, the anonymous
   lever at the Vault door, is settled by the recorded seeded draw (STATE-SPACE.md Settled item 15)
   where the graph core applies same-tick level arrivals first in, first out.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r"""
const fs=require('fs');
require('./src/03-canonical.js');require('./src/03-notation-core.js');require('./src/06-attachment-core.js');
const D=require('./src/05-data-core.js'),S=require('./src/07-state-space.js'),canon=globalThis.SovSchematicCanonical.canonicalize;
const loadPack=f=>S.loadPack(JSON.parse(fs.readFileSync(f,'utf8'))).pack;
const packs=[loadPack('data/core.logic.pack.json'),loadPack('data/core.flow.pack.json')];
const TICK_MS=1,LEVEL=1<<20;
const out={};

const msgs=run=>run.records.filter(r=>r.form==='message');
const hops=(run,event)=>msgs(run).filter(r=>r.hop&&r.hop.event===event);
const taps=(run,entity)=>hops(run,'arrived').filter(r=>r.subject.entity===entity).length;
const refusals=run=>hops(run,'refused').map(r=>r.hop.reason);
const parkedAt=(run,entity)=>Object.values(run.parked).find(p=>!entity||p.entity===entity);
const quiet=run=>{const s=S.settle(run);if(s.kind!=='quiet')throw new Error('not quiet '+JSON.stringify(s));};
const nextAt=run=>run.tick===null?0:run.tick+1;
const started=args=>{const s=S.startRun({packs,tickMs:TICK_MS,...args});if(!s.ok)throw new Error(JSON.stringify(s));return s.run};
// A replay of the run's trace, records included: ok and the same ledger and records, byte for byte.
function replays(run,doc,handlers){
  const bytes=canon(S.traceOf(run)),trace=JSON.parse(bytes);
  const r=S.replay({trace,doc,packs,handlers});
  return {ok:r.ok,code:r.code||null,valid:S.validateTrace(trace).ok,
    same:r.ok&&canon(r.run.ledger)===canon(trace.ledger)&&canon(r.records)===canon(trace.records),
    invalidRecords:run.records.map(x=>S.validateRecord(x)).filter(v=>!v.ok).length};
}
// A node's level is its out port's main channel (the engine's signal, absent = 0); its edges are
// the changes of the level records written there, from 0.
const levelOf=v=>v===true?LEVEL:Number.isSafeInteger(v)?v:0;
const levelAt=(run,entity)=>levelOf(run.signal[JSON.stringify([entity,'right','main'])])/LEVEL;
function edgesAt(run,entity){
  const e={'+':0,'-':0};let prev=0;
  for(const r of run.records){
    if(r.observable!=='logic.level'||r.subject.entity!==entity||r.subject.point!=='right'||r.subject.channel!=='main'||r.provenance.rule==='overridden'||r.level===true)continue;
    const v=levelOf(r.value);if(v>prev)e['+']++;else if(v<prev)e['-']++;prev=v;
  }
  return e;
}
// Every scheduled tick up to and including `until` (the graph core's advance, 1 tick = 1 ms).
function advanceTo(run,until){
  for(;;){
    let t=run.tick===null?0:null;
    for(const p of run.pending)if(t===null||p.at<t)t=p.at;
    for(const q of Object.values(run.queues))if(q.items.length>q.head&&(t===null||q.next<t))t=q.next;
    if(t===null||t>until)return;
    const r=S.step(run);if(!r.ok)throw new Error(JSON.stringify(r));
  }
}
// A saved scenario in ticks. inject, resume, reconcile and restart as tests/state_space_effects_qa.py
// runs them; at {time, set} is a level input at that tick; advance runs every tick up to it.
function runScenario(doc,sc){
  const handlers=sc.data.handlers||{};
  let run=started({doc,handlers}),now=0;
  const notes=[];
  for(const step of sc.data.steps){
    if(step.inject){const r=S.addInput(run,{entity:step.inject.node,point:'out',channel:'message',value:{channel:step.inject.channel??null,payload:step.inject.payload??null},at:nextAt(run)});if(!r.ok)throw new Error(JSON.stringify(r))}
    else if(step.resume){const p=parkedAt(run,step.resume.node);if(!p)throw new Error('nothing parked; refusals '+JSON.stringify(refusals(run)));const r=S.resume(run,p.id,step.resume);if(!r.ok)throw new Error(JSON.stringify(r))}
    else if(step.restart){const r=S.replay({trace:JSON.parse(canon(S.traceOf(run))),doc,packs,handlers});if(!r.ok)throw new Error('restart '+JSON.stringify(r));run=r.run;notes.push('restarted')}
    else if(step.reconcile){const r=S.reconcile(run,step.reconcile.effectKey,step.reconcile);if(!r.ok)throw new Error(JSON.stringify(r))}
    else if(step.at){const {time,set}=step.at;const r=S.addInput(run,{entity:set.node,point:'out',channel:'main',value:!!set.value,at:time});if(!r.ok)throw new Error(JSON.stringify(r))}
    // A step that only schedules (at) runs nothing, as in the graph core.
    if(step.advance!=null){now+=step.advance;advanceTo(run,now)}
    else if(!step.at)quiet(run);
  }
  const exp=sc.data.expect||{},checks=[];
  for(const [node,n] of Object.entries(exp.taps||{}))checks.push({name:`taps ${node}`,expected:n,actual:taps(run,node)});
  if(exp.levelRefusals!=null)checks.push({name:'level refusals',expected:exp.levelRefusals,actual:run.records.filter(r=>r.level===true).length});
  if(exp.refusals!=null)checks.push({name:'refusals',expected:exp.refusals,actual:refusals(run).length});
  if(exp.parked!=null)checks.push({name:'parked',expected:exp.parked,actual:Object.keys(run.parked).length});
  for(const [status,n] of Object.entries(exp.effects||{}))checks.push({name:`effects ${status}`,expected:n,actual:Object.values(run.effects).filter(e=>e.status===status).length});
  const events={'effect-replayed':()=>hops(run,'replayed').length,'effect-confirmed':()=>hops(run,'handled').filter(r=>r.hop.effectKey).length};
  for(const [event,n] of Object.entries(exp.events||{}))checks.push({name:`events ${event}`,expected:n,actual:events[event]?events[event]():null});
  for(const [node,v] of Object.entries(exp.levels||{}))checks.push({name:`level ${node}`,expected:v,actual:levelAt(run,node)});
  for(const [node,want] of Object.entries(exp.edges||{})){const e=edgesAt(run,node);for(const [pol,n] of Object.entries(want))checks.push({name:`edges ${node} ${pol}`,expected:n,actual:e[pol]})}
  for(const c of checks)c.pass=c.actual===c.expected;
  return {ok:checks.every(c=>c.pass),checks,notes,refusals:refusals(run),replay:replays(run,doc,handlers),run};
}

// (1) Example 09, the fixture as authored.
const printRaw=JSON.parse(fs.readFileSync('examples/09-print-ai-proof-run.sov','utf8'));
const print=D.documentFromFilePayload(printRaw);
const printScenarios=printRaw.references.filter(r=>r.kind==='scenario');
out.print={};
for(const sc of printScenarios){
  let r;try{r=runScenario(print,sc)}catch(e){out.print[sc.id]={ok:false,error:String(e.message||e),checks:[],refusals:[],replay:null};continue}
  out.print[sc.id]={ok:r.ok,checks:r.checks,notes:r.notes,refusals:r.refusals,replay:r.replay};
}

// (2) Example 10: levels, edges and the jobs the alarm's rising crossings start.
const tenRaw=JSON.parse(fs.readFileSync('examples/10-clocked-signals.sov','utf8'));
const ten=D.documentFromFilePayload(tenRaw);
out.ten={};
for(const sc of tenRaw.references.filter(r=>r.kind==='scenario')){
  const r=runScenario(ten,sc);
  out.ten[sc.id]={ok:r.ok,checks:r.checks,replay:r.replay,jobs:taps(r.run,'job'),
    alarmRefusals:hops(r.run,'refused').filter(x=>x.subject.entity==='alarm').map(x=>x.hop.reason),
    alarmEdgeMessages:hops(r.run,'edge').filter(x=>x.subject.entity==='alarm').length};
}

// (3) The named intended difference (STATE-SPACE.md Settled item 15): planeDoc(acl,0) of
// graph_core_qa.py:147-163. The svc:ops lever (level 0, k3) and the anonymous lever (level 1, k4)
// reach the Vault's door in the same tick, and the door declares no merge. The graph core applies
// them first in, first out, so the anonymous lever's 1 is last and is refused at the door; here the
// order is the recorded seeded draw and the door takes the value of the Path last in that draw, so
// the door's level and whether a level refusal is made follow the draw, and replay gives it back.
const A=(id,extra={})=>({id,symbolId:'act',x:0,y:0,config:{signalMode:'relay',...extra}});
const L=(id,value=0,extra={})=>({id,symbolId:'lever',x:0,y:0,config:{signal:{value},...extra}});
const planeDoc=(acl,leverValue=1)=>({components:[
  {id:'vault',symbolId:'plane',x:400,y:200,form:{dimension:2,regions:{interior:{state:'open'}}},config:{label:'Vault',attachmentDefaults:'none',...(acl?{acl}:{})}},
  {id:'door',symbolId:'point',x:250,y:200,canvasId:'canvas:component:vault',parentId:'vault',placement:{kind:'edge',hostId:'vault',side:'left',t:.5},form:{dimension:0},config:{signalMode:'relay',ports:{out:{face:'both',connections:[{id:'connection-1',flow:'duplex',access:'read-write'}]}}}},
  {...A('inside'),canvasId:'canvas:component:vault',parentId:'vault',config:{signalMode:'relay'}},
  A('outside'),{...L('lever',leverValue),config:{signal:{value:leverValue},principal:'svc:ops'}},L('anon',1)],
  wires:[{id:'k1',a:'outside',aSide:'out',b:'door',bSide:'out',canvasId:'canvas:global'},{id:'k2',a:'door',aSide:'out',b:'inside',bSide:'in',canvasId:'canvas:component:vault'},
   {id:'k3',a:'lever',aSide:'out',b:'door',bSide:'out',canvasId:'canvas:global'},{id:'k4',a:'anon',aSide:'out',b:'door',bSide:'out',canvasId:'canvas:global'}]});
const acl={entries:[{principal:'svc:*',allow:['enter']},{principal:'svc:intruder',deny:['enter']}]};
const vaultRaw=planeDoc(acl,0),vault=D.normalizeDocument(JSON.parse(JSON.stringify(vaultRaw)));
const sourceOf=Object.fromEntries(vaultRaw.wires.map(w=>[w.id,w.a]));
function doorCase(seed){
  const run=started({doc:vault,...(seed===null?{}:{seed})});quiet(run);
  const draws=run.ledger.filter(e=>e.kind==='draw').map(e=>e.body);
  const atDoor=draws.filter(d=>d.entity==='door');
  const last=atDoor.length?atDoor[0].order.at(-1):null;
  // The value a Path carries is its source's own level.
  const carried=w=>levelAt(run,sourceOf[w]);
  const doorLevel=run.records.filter(r=>r.subject.entity==='door'&&r.subject.channel==='main'&&r.observable==='logic.level'&&r.level!==true&&r.provenance.rule!=='overridden').map(r=>levelOf(r.value)/LEVEL).at(-1);
  const refusal=run.records.some(r=>r.level===true&&r.subject.entity==='door'&&/anonymously/.test(r.value));
  return {draws:draws.length,atDoor:atDoor.map(d=>({point:d.point,channel:d.channel,paths:d.paths,order:d.order})),last,lastCarries:last===null?null:carried(last),
    anonLevel:levelAt(run,'anon'),leverLevel:levelAt(run,'lever'),doorLevel,refusal,inside:levelAt(run,'inside'),replay:replays(run,vault,undefined)};
}
out.door={authored:doorCase(null),seeds:['1','2','3','4','5','6','7'].map(doorCase)};

// The graph core on the same documents (loaded last: the runs above never saw it).
const G=require('./src/07-graph-core.js');
out.dev={print:{},ten:{}};
for(const sc of printScenarios){const r=G.runScenario(printRaw,sc);out.dev.print[sc.id]={ok:r.ok,refusals:r.refusals.map(x=>x.reason)}}
for(const sc of tenRaw.references.filter(r=>r.kind==='scenario')){const r=G.runScenario(tenRaw,sc);out.dev.ten[sc.id]={ok:r.ok,checks:r.checks.map(c=>[c.name,c.actual])}}
{const {sim}=G.createSimulation(vaultRaw);sim.run();out.dev.door={refusal:sim.refusals().some(r=>r.level&&r.node==='door'&&/anonymously/.test(r.reason)),inside:sim.levels().inside.value}}
console.log(JSON.stringify(out));
"""


def main() -> None:
    proc = subprocess.run(['node', '-e', SCRIPT], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    r = json.loads(proc.stdout)
    dev = r['dev']

    # (1) Example 09 as authored: every scenario passes its expect block with the graph core's refusal reasons.
    assert set(r['print']) == {'s-approve', 's-retry', 's-restart', 's-reject', 's-eval-fails'}, list(r['print'])
    for name, sc in r['print'].items():
        assert sc['ok'], (name, sc.get('error'), sc['checks'], sc['refusals'])
        assert dev['print'][name]['ok'], (name, dev['print'][name])
        assert sorted(sc['refusals']) == sorted(dev['print'][name]['refusals']), (name, sc['refusals'], dev['print'][name]['refusals'])
        rep = sc['replay']
        assert rep['ok'] and rep['same'] and rep['valid'] and rep['invalidRecords'] == 0, (name, rep)
    assert not any('floating point' in x for sc in r['print'].values() for x in sc['refusals']), 'the fixture states no fraction'

    # (2) Example 10: every scenario passes, with the graph core's own counts.
    assert set(r['ten']) == {'s-lamp-off', 's-lamp-follows', 's-threshold-schedules'}, list(r['ten'])
    for name, sc in r['ten'].items():
        assert sc['ok'], (name, sc['checks'])
        assert dev['ten'][name]['ok'], (name, dev['ten'][name])
        assert [[c['name'], c['actual']] for c in sc['checks'] if not c['name'].startswith('level ')] == [c for c in dev['ten'][name]['checks'] if not c[0].startswith('level ')], (name, sc['checks'], dev['ten'][name])
        rep = sc['replay']
        assert rep['ok'] and rep['same'] and rep['valid'] and rep['invalidRecords'] == 0, (name, rep)
    ts = r['ten']['s-threshold-schedules']
    dev_jobs = dict(dev['ten']['s-threshold-schedules']['checks'])['taps job']
    assert ts['jobs'] == 3 == dev_jobs, ('each rising crossing starts the job', ts['jobs'], dev_jobs)
    assert ts['alarmEdgeMessages'] == 3, ts
    assert not any('limit has no rate' in x for x in ts['alarmRefusals']), ('the alarm takes its own edge message through continueAt, not its limit intake', ts['alarmRefusals'])

    # (3) The named intended difference (STATE-SPACE.md Settled item 15): one recorded draw at the
    # door decides its level; a level refusal there exists exactly when the anonymous lever's value
    # wins; the graph core's first-in-first-out order always lets the anonymous lever win.
    assert dev['door'] == {'refusal': True, 'inside': 0}, dev['door']
    cases = [r['door']['authored'], *r['door']['seeds']]
    for c in cases:
        assert c['draws'] == 1 and len(c['atDoor']) == 1, c
        assert c['atDoor'][0]['paths'] == ['k3', 'k4'] and c['atDoor'][0]['channel'] == 'main', c
        assert c['anonLevel'] == 1 and c['leverLevel'] == 0, c
        assert c['doorLevel'] == c['lastCarries'], ('the door takes the value of the Path last in the recorded draw', c)
        assert c['refusal'] == (c['lastCarries'] == c['anonLevel']), ('a level refusal at the door exactly when the anonymous value wins', c)
        assert c['inside'] == 0 == dev['door']['inside'], ('nothing anonymous crosses into the Vault either way', c)
        rep = c['replay']
        assert rep['ok'] and rep['same'] and rep['valid'] and rep['invalidRecords'] == 0, ('the drawn result replays byte for byte', c)
    assert {c['last'] for c in cases} == {'k3', 'k4'}, ('the seeds reach both outcomes of the draw', [c['last'] for c in cases])

    runs = len(r['print']) + len(r['ten']) + len(cases)
    print(f"STATE SPACE DEV PARITY PASS: {runs} runs against the graph core, one named difference (Settled item 15), each replayed byte for byte")


if __name__ == '__main__':
    main()
