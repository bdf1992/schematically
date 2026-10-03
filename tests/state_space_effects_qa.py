"""Handlers, effects, park and resume on the state-space runtime (contract 07 of the one-runtime plan).

handler@1, effect@1 and park@1 are flow patterns a card reaches through the one binding lookup
from its config.behavior. A function handler's answer is a ledger result entry; an input given
mid-run (addInput), a resume and a reconcile are ledger entries applied by replay where they were
given; an effects ledger handed to a new run is an effects entry. Each case is a case of
tests/graph_core_qa.py (lines 25-49), run in ticks and checked against the graph core on the same
document, and every run replays byte for byte.

Example 09's evaluate fixture states its score as 930 thousandths. A run records no floating
point, so the example states it in integer units, as PAYLOAD_FRACTION's next operation says; a
fixture with the score set back to 0.93 is refused at the handler, and that is checked too.
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
const loadPack=f=>S.loadPack(JSON.parse(fs.readFileSync(f,'utf8')));
const logic=loadPack('data/core.logic.pack.json'),flow=loadPack('data/core.flow.pack.json');
const packs=[logic.pack,flow.pack];
const printRaw=JSON.parse(fs.readFileSync('examples/09-print-ai-proof-run.sov','utf8'));
const print=D.documentFromFilePayload(printRaw);
const scenarios=printRaw.references.filter(r=>r.kind==='scenario');
const scenario=id=>scenarios.find(r=>r.id===id);
const out={flowPatterns:S.flowPatterns().map(p=>`${p.id}@${p.version}`),levelPatterns:S.patterns().map(p=>`${p.id}@${p.version}`),
  resolved:['handler@1','effect@1','park@1'].map(ref=>!!S.pattern(ref)&&S.pattern(ref).messages===true),
  pack:{ok:flow.ok,errors:flow.errors,definitions:flow.ok?flow.pack.definitions.map(d=>`${d.id}@${d.version} ${d.pattern}`):[]},
  bindings:Object.fromEntries(print.components.map(c=>[c.id,S.behaviorBindingsOf(c,packs)]).filter(([,b])=>Object.keys(b).length)),
  noFlowPack:S.behaviorBindingsOf(print.components.find(c=>c.id==='notify'),[logic.pack])};

// Every number a run records is a safe integer: fractions in a scenario's fixtures are stated in thousandths.
const changed=[];
function thousandths(value,path){
  if(typeof value==='number'&&!Number.isSafeInteger(value)){changed.push([path,value]);return Math.round(value*1000)}
  if(Array.isArray(value))return value.map((x,i)=>thousandths(x,`${path}[${i}]`));
  if(value&&typeof value==='object'){const o={};for(const k of Object.keys(value))o[k]=thousandths(value[k],`${path}.${k}`);return o}
  return value;
}
const handlersOf=sc=>thousandths(JSON.parse(JSON.stringify(sc.data.handlers)),`${sc.id}.handlers`);

const msgs=run=>run.records.filter(r=>r.form==='message');
const hops=(run,event)=>msgs(run).filter(r=>r.hop&&r.hop.event===event);
const taps=(run,entity)=>hops(run,'arrived').filter(r=>r.subject.entity===entity).length;
const refusals=run=>hops(run,'refused').map(r=>r.hop.reason);
const quiet=run=>{const s=S.settle(run);if(s.kind!=='quiet')throw new Error('not quiet '+JSON.stringify(s));};
const nextAt=run=>run.tick===null?0:run.tick+1;
const inject=(run,entity,payload,channel=null)=>{const r=S.addInput(run,{entity,point:'out',channel:'message',value:{channel,payload},at:nextAt(run)});if(!r.ok)throw new Error(JSON.stringify(r));return r};
const parkedAt=(run,entity)=>Object.values(run.parked).find(p=>!entity||p.entity===entity);
// A replay of the run's trace, records included: ok and the same ledger and records, byte for byte.
function replays(run,doc,handlers){
  const bytes=canon(S.traceOf(run)),trace=JSON.parse(bytes);
  const r=S.replay({trace,doc,packs,handlers});
  return {ok:r.ok,code:r.code||null,message:r.message||null,valid:S.validateTrace(trace).ok,
    same:r.ok&&canon(r.run.ledger)===canon(trace.ledger)&&canon(r.records)===canon(trace.records),
    invalidRecords:run.records.map(x=>S.validateRecord(x)).filter(v=>!v.ok).length};
}

// A saved scenario in ticks: each inject an input given mid-run, each resume and reconcile a ledger
// entry, a restart a replay of the trace (a process restart rebuilt from the ledger); each step then
// settles, as the graph core runs each step to quiet.
function runScenario(doc,sc,extra={}){
  const handlers={...handlersOf(sc),...(extra.handlers||{})};
  let run=S.startRun({doc,packs,handlers,...(extra.effects?{effects:extra.effects}:{})}).run;
  const notes=[];
  for(const step of sc.data.steps){
    if(step.inject)inject(run,step.inject.node,step.inject.payload??null,step.inject.channel??null);
    else if(step.resume){const p=parkedAt(run,step.resume.node);if(!p)throw new Error('nothing parked');const r=S.resume(run,p.id,step.resume);if(!r.ok)throw new Error(JSON.stringify(r))}
    else if(step.restart){const r=S.replay({trace:JSON.parse(canon(S.traceOf(run))),doc,packs,handlers});if(!r.ok)throw new Error('restart '+JSON.stringify(r));run=r.run;notes.push('restarted')}
    else if(step.reconcile){const r=S.reconcile(run,step.reconcile.effectKey,step.reconcile);if(!r.ok)throw new Error(JSON.stringify(r))}
    quiet(run);
  }
  const exp=sc.data.expect||{},checks=[];
  for(const [node,n] of Object.entries(exp.taps||{}))checks.push({name:`taps ${node}`,expected:n,actual:taps(run,node)});
  if(exp.levelRefusals!=null)checks.push({name:'level refusals',expected:exp.levelRefusals,actual:run.records.filter(r=>r.level===true).length});
  if(exp.refusals!=null)checks.push({name:'refusals',expected:exp.refusals,actual:refusals(run).length});
  if(exp.parked!=null)checks.push({name:'parked',expected:exp.parked,actual:Object.keys(run.parked).length});
  for(const [status,n] of Object.entries(exp.effects||{}))checks.push({name:`effects ${status}`,expected:n,actual:Object.values(run.effects).filter(e=>e.status===status).length});
  const events={'effect-replayed':()=>hops(run,'replayed').length,'effect-confirmed':()=>hops(run,'handled').filter(r=>r.hop.effectKey).length};
  for(const [event,n] of Object.entries(exp.events||{}))checks.push({name:`events ${event}`,expected:n,actual:events[event]?events[event]():null});
  for(const c of checks)c.pass=c.actual===c.expected;
  return {ok:checks.every(c=>c.pass),checks,notes,run,handlers,refusals:refusals(run)};
}

// Every scenario of example 09 passes its expect block, and replays byte for byte.
out.scenarios={};
for(const sc of scenarios){const r=runScenario(print,sc);out.scenarios[sc.id]={ok:r.ok,checks:r.checks,notes:r.notes,refusals:r.refusals,replay:replays(r.run,print,r.handlers),
  mid:r.run.ledger.filter(e=>['input','resume','reconcile'].includes(e.kind)&&'after' in e.body).map(e=>e.kind)}}
out.changed=changed;
// A fixture whose score is set back to 0.93 is refused at the handler: a run records no floating point.
{const sc=scenario('s-approve');const fractional=JSON.parse(JSON.stringify(sc.data.handlers));fractional.evaluate.responses.good.payload.score=0.93;const run=S.startRun({doc:print,packs,handlers:fractional}).run;inject(run,'case',{caseId:'48219',proof:'good'},'proof');quiet(run);
 out.fraction={refused:refusals(run),customer:taps(run,'customer')}}

// Without effect identity a retry messages the customer twice (graph_core_qa.py:28-29).
{const mut=JSON.parse(JSON.stringify(printRaw));delete mut.components.find(c=>c.id==='notify').config.behavior.effect;
 const r=runScenario(D.documentFromFilePayload(mut),scenario('s-retry'));out.noEffect={ok:r.ok,customer:r.checks.find(c=>c.name==='taps customer').actual}}
// Two runs without a shared effects ledger each send once; a run handed the first run's effects sends none (31-36).
{const sc=scenario('s-approve');const a=runScenario(print,sc),b=runScenario(print,sc);
 const c=runScenario(print,sc,{effects:a.run.effects});
 out.ledger={twoRuns:taps(a.run,'customer')+taps(b.run,'customer'),handed:taps(c.run,'customer'),replayed:hops(c.run,'replayed').length,
   effectsEntry:c.run.ledger[1].kind,replay:replays(c.run,print,c.handlers)}}
// Only the mailer may carry work out of the Run: a notify acting as ai:rogue is refused at the exit (38-39).
{const mut=JSON.parse(JSON.stringify(printRaw));mut.components.find(c=>c.id==='notify').config.principal='ai:rogue';
 const r=runScenario(D.documentFromFilePayload(mut),scenario('s-approve'));out.rogue={ok:r.ok,refusals:r.refusals}}
// A handler nobody registered refuses; it never passes through silently (43-44).
{const run=S.startRun({doc:print,packs,handlers:{}}).run;inject(run,'case',{caseId:'1',proof:'good'});quiet(run);
 out.unregistered={refusals:refusals(run),customer:taps(run,'customer'),replay:replays(run,print,{})}}
// A throwing send-email leaves notify:7 ambiguous; the retry is refused until reconciled (46-49).
{const sc=scenario('s-approve');let calls=0;
 const handlers={...handlersOf(sc),'send-email':()=>{calls++;throw new Error('socket closed')}};
 const run=S.startRun({doc:print,packs,handlers}).run;
 const go=()=>{inject(run,'case',{caseId:'7',proof:'good'});quiet(run);const r=S.resume(run,parkedAt(run).id);if(!r.ok)throw new Error(JSON.stringify(r));quiet(run)};
 go();const first={status:run.effects['notify:7']?.status,error:run.effects['notify:7']?.error,ambiguous:hops(run,'ambiguous').map(r=>r.hop.effectKey)};
 go();const retried=refusals(run).at(-1);
 const notAmbiguous=S.reconcile(run,'notify:8',{confirmed:true});
 const rec=S.reconcile(run,'notify:7',{confirmed:true});
 go();
 const callsBefore=calls,rep=replays(run,print,handlers);
 out.ambiguous={first,retried,reconcile:rec,notAmbiguous:{code:notAmbiguous.code,message:notAmbiguous.message},replayed:hops(run,'replayed').length,customer:taps(run,'customer'),
   calls:callsBefore,replayCalls:calls-callsBefore,replay:rep,results:run.ledger.filter(e=>e.kind==='result').map(e=>e.body),
   unknownPark:(({code,message})=>({code,message}))(S.resume(run,'p-nothing'))}}
// A function handler's answer is a result entry: replay reads it and calls the function zero times.
{const sc=scenario('s-approve');let calls=0;
 const handlers={...handlersOf(sc),'send-email':(m,ctx)=>{calls++;return {payload:{...m.payload,sent:ctx.tick}}}};
 const run=S.startRun({doc:print,packs,handlers}).run;inject(run,'case',{caseId:'48219',proof:'good'},'proof');quiet(run);S.resume(run,parkedAt(run).id);quiet(run);
 const callsRun=calls,rep=replays(run,print,handlers),callsReplay=calls-callsRun;
 const withoutIt=replays(run,print,handlersOf(sc));
 const {['send-email']:_,...rest}=handlersOf(sc);const absent=replays(run,print,rest); out.functionResult={calls:callsRun,replayCalls:callsReplay,replay:rep,stubInstead:withoutIt.same,absent:absent.same,customer:taps(run,'customer'),
   results:run.ledger.filter(e=>e.kind==='result').map(e=>[e.body.entity,e.body.messageId,Object.keys(e.body).sort()])}}
// addInput mid-run gives the same records as the same input given at start with the same at.
{const handlers=handlersOf(scenario('s-eval-fails'));
 const x={entity:'case',point:'out',channel:'message',value:{channel:'proof',payload:{caseId:'1',proof:'bad'}},at:0};
 const y={entity:'case',point:'out',channel:'message',value:{channel:'proof',payload:{caseId:'2',proof:'bad'}},at:5};
 const a=S.startRun({doc:print,packs,handlers,inputs:[x]}).run;S.step(a);const added=S.addInput(a,y);quiet(a);
 const b=S.startRun({doc:print,packs,handlers,inputs:[x,y]}).run;quiet(b);
 const norm=run=>canon(run.records).split(run.id).join('RUN');
 out.addInput={added,sameRecords:norm(a)===norm(b),records:a.records.length,refusals:refusals(a),entry:a.ledger.filter(e=>e.kind==='input').map(e=>e.body.after===undefined?'start':`after ${e.body.after}`),replay:replays(a,print,handlers),
   late:(()=>{const c=S.startRun({doc:print,packs,handlers,inputs:[x]}).run;quiet(c);const at=c.tick;const r=S.addInput(c,{...y,at:0});quiet(c);return {scheduled:r.at===at+1,tick:at}})()}}

// The graph core on the same document (loaded last: the runs above never saw it).
const G=require('./src/07-graph-core.js');
out.dev={};
for(const sc of scenarios){const r=G.runScenario(printRaw,sc);out.dev[sc.id]={ok:r.ok,refusals:r.refusals.map(x=>x.reason)}}
console.log(JSON.stringify(out));
"""


def main() -> None:
    proc = subprocess.run(['node', '-e', SCRIPT], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    r = json.loads(proc.stdout)

    # The registry: handler@1, effect@1 and park@1 are flow patterns beside the rest; the level registry is unchanged.
    assert r['flowPatterns'] == ['route@1', 'join@1', 'buffer@1', 'limit@1', 'gate@1', 'terminal@1', 'hold@1', 'handler@1', 'effect@1', 'park@1'], r['flowPatterns']
    assert r['levelPatterns'] == ['truth_table@1', 'merge@1', 'combine@1'], r['levelPatterns']
    assert r['resolved'] == [True, True, True], r['resolved']
    assert r['pack']['ok'] and r['pack']['errors'] == [], r['pack']
    assert r['pack']['definitions'][-3:] == ['flow.handler@1 handler@1', 'flow.effect@1 effect@1', 'flow.park@1 park@1'], r['pack']
    assert r['bindings'] == {'ingest': {'handler': 'flow.handler@1'}, 'evaluate': {'handler': 'flow.handler@1'}, 'review': {'human': 'flow.park@1'},
                             'notify': {'effect': 'flow.effect@1', 'handler': 'flow.handler@1'}}, r['bindings']
    assert r['noFlowPack'] == {}, r['noFlowPack']

    # Every scenario of example 09 passes its expect block, with the graph core's refusal reasons, and replays byte for byte.
    assert set(r['scenarios']) == {'s-approve', 's-retry', 's-restart', 's-reject', 's-eval-fails'}, list(r['scenarios'])
    for name, sc in r['scenarios'].items():
        assert sc['ok'], (name, sc['checks'])
        assert r['dev'][name]['ok'], (name, r['dev'][name])
        assert sorted(sc['refusals']) == sorted(r['dev'][name]['refusals']), (name, sc['refusals'], r['dev'][name]['refusals'])
        rep = sc['replay']
        assert rep['ok'] and rep['same'] and rep['valid'] and rep['invalidRecords'] == 0, (name, rep)
    assert r['scenarios']['s-restart']['notes'] == ['restarted', 'restarted'], r['scenarios']['s-restart']
    assert r['scenarios']['s-retry']['mid'] == ['input', 'resume', 'input', 'resume'], r['scenarios']['s-retry']['mid']
    assert r['scenarios']['s-reject']['refusals'] == ['rejected at Human review'],r['scenarios']['s-reject']
    assert r['scenarios']['s-eval-fails']['refusals'] == ['eval: proof below threshold'], r['scenarios']['s-eval-fails']
    # Example 09 states its score in thousandths (930), so no fixture carries a fraction; a copy set back to 0.93 is refused at evaluate.
    assert r['changed'] == [], ('no fraction left in any scenario fixture', r['changed'])
    assert r['fraction'] == {'refused': ['handler evaluate result.payload.score is 0.93, not a safe integer; a run records no floating point'], 'customer': 0}, r['fraction']

    # Without effect identity, s-retry reaches the customer twice.
    assert r['noEffect'] == {'ok': False, 'customer': 2}, r['noEffect']
    # Two runs without a shared ledger send twice; handed the first run's effects, a run sends none.
    lg = r['ledger']
    assert lg['twoRuns'] == 2 and lg['handed'] == 0 and lg['replayed'] == 1 and lg['effectsEntry'] == 'effects', lg
    assert lg['replay']['ok'] and lg['replay']['same'], lg['replay']
    # ai:rogue is refused at the Run exit.
    assert r['rogue']['ok'] is False and any('ai:rogue may not exit Run' in x for x in r['rogue']['refusals']), r['rogue']
    # An unregistered handler refuses.
    un = r['unregistered']
    assert un['refusals'][:1] == ['no handler registered: ingest'] and un['customer'] == 0 and un['replay']['same'], un

    # A throwing send-email: ambiguous, the retry refused, reconcile confirms, the next attempt is replayed.
    am = r['ambiguous']
    assert am['first'] == {'status': 'ambiguous', 'error': 'socket closed', 'ambiguous': ['notify:7']}, am['first']
    assert am['retried'] == 'effect notify:7 is ambiguous: reconcile before retrying', am['retried']
    assert am['notAmbiguous'] == {'code': 'NOT_AMBIGUOUS', 'message': 'Effect notify:8 is not awaiting reconciliation'}, am['notAmbiguous']
    assert am['reconcile'] == {'ok': True, 'effectKey': 'notify:7', 'status': 'confirmed'}, am['reconcile']
    assert am['replayed'] == 1 and am['customer'] == 0, am
    assert am['calls'] == 1 and am['replayCalls'] == 0, am
    assert [sorted(b) for b in am['results']] == [['entity', 'error', 'messageId', 'tick']] and am['results'][0]['error'] == 'socket closed', am['results']
    assert am['replay']['ok'] and am['replay']['same'], am['replay']
    assert am['unknownPark'] == {'code': 'UNKNOWN_PARK', 'message': 'Nothing parked as p-nothing'}, am['unknownPark']

    # A function's answer is a result entry: the replay is byte-identical and calls it zero times.
    fr = r['functionResult']
    assert fr['calls'] == 1 and fr['replayCalls'] == 0 and fr['customer'] == 1, fr
    assert fr['replay']['ok'] and fr['replay']['same'] and fr['absent'], fr
    assert fr['stubInstead'], ('a stub given in place of the function changes nothing: the recorded answer is read', fr)
    assert fr['results'] == [['notify', fr['results'][0][1], ['entity', 'messageId', 'result', 'tick']]], fr['results']

    # addInput mid-run: the same records as the same input given at start with the same at.
    ai = r['addInput']
    assert ai['added']['ok'] and ai['added']['at'] == 5, ai['added']
    assert ai['sameRecords'] and ai['records'] > 0 and ai['refusals'] == ['eval: proof below threshold'] * 2, ai
    assert ai['entry'] == ['start', 'after 0'], ai['entry']
    assert ai['replay']['ok'] and ai['replay']['same'], ai['replay']
    assert ai['late']['scheduled'], ai['late']

    print(f"STATE SPACE EFFECTS PASS: {len(r['scenarios'])} scenarios of example 09 in ticks, each replayed byte for byte")


if __name__ == '__main__':
    main()
