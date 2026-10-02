"""Access control on the state-space runtime (contract 05 of the one-runtime plan).

A plane's config.acl, the crossing a value makes at a boundary Point or a plane's own open
interior, and the decision a principal gets there are the graph core's own model
(src/07-graph-core.js aclConfig/aclDecide/crossingAt, GRAPH-MODEL.md); src/07-state-space.js
reads the same document fields and gives the same verdicts, read fresh over its own document
instead of through that module (so a run's behaviour never depends on whether something else
happens to have loaded the graph core, as tests/state_space_message_qa.py's load-order check
requires). This suite mirrors the graph core's own fixtures (tests/graph_core_qa.py:147-174):
the Vault document (enter, anonymous and denied principals, a level crossing) and the Room
document (exit). Runs src/07-state-space.js with src/07-graph-core.js in Node.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r"""
const fs=require('fs');
require('./src/06-attachment-core.js');
const D=require('./src/05-data-core.js'),S=require('./src/07-state-space.js'),G=require('./src/07-graph-core.js'),C=globalThis.SovSchematicCanonical;
const canon=C.canonicalize;
const A=(id,extra={})=>({id,symbolId:'act',x:0,y:0,config:{signalMode:'relay',...extra}});
const started=args=>{const s=S.startRun({packs:[],...args});if(!s.ok)throw new Error(JSON.stringify(s));return s.run};
const settle=run=>{for(let i=0;i<200;i++){const r=S.step(run);if(!r.ok)throw new Error(JSON.stringify(r));if(r.tick===null)return run}throw new Error('no quiet')};
const inj=(entity,point,channel,extra={},at=0)=>({entity,point,channel:'message',value:{channel,payload:null,...extra},at});
const msgs=run=>run.records.filter(r=>r.form==='message');
const out={};

// The graph core's Vault (tests/graph_core_qa.py:147-153): a plane with an interior Point (door)
// on its boundary; outside and inside sit either side of it.
const vaultDoc=acl=>D.normalizeDocument({components:[
  {id:'vault',symbolId:'plane',x:400,y:200,form:{dimension:2,regions:{interior:{state:'open'}}},config:{label:'Vault',attachmentDefaults:'none',...(acl?{acl}:{})}},
  {id:'door',symbolId:'point',x:250,y:200,canvasId:'canvas:component:vault',parentId:'vault',placement:{kind:'edge',hostId:'vault',side:'left',t:.5},form:{dimension:0},config:{signalMode:'relay'}},
  {...A('inside'),canvasId:'canvas:component:vault',parentId:'vault'},
  A('outside')],
  wires:[{id:'k1',a:'outside',aSide:'out',b:'door',bSide:'out',canvasId:'canvas:global'},
         {id:'k2',a:'door',aSide:'out',b:'inside',bSide:'in',canvasId:'canvas:component:vault'}]});
const acl={entries:[{principal:'svc:*',allow:['enter']},{principal:'svc:intruder',deny:['enter']}]};

// svc:ops enters; eve and the anonymous message are refused with the graph core's own reasons.
{
  const d=vaultDoc(acl);
  const run=settle(started({doc:d,inputs:[inj('outside','out',null,{principal:'svc:ops'}),inj('outside','out',null,{principal:'eve'}),inj('outside','out',null,{})]}));
  const m=msgs(run);
  out.vault={
    arrivedInside:m.filter(r=>r.subject.entity==='inside'&&r.hop.event==='arrived').length,
    refused:m.filter(r=>r.hop.event==='refused').map(r=>r.hop.reason).sort(),
    crossed:m.filter(r=>r.hop.event==='crossed').map(r=>[r.subject.entity,r.hop.wire,r.principal]),
    // every record validates (RECORD_KEYS/HOP_EVENTS admit crossed and refused).
    valid:run.records.every(r=>S.validateRecord(r).ok)
  };
  // Replay: the refused leg is never taken, so the run and its trace agree byte for byte.
  const trace=S.traceOf(run),replayed=S.replay({trace,doc:d,packs:[]});
  out.vault.replay={ok:replayed.ok,same:replayed.ok&&canon(replayed.records)===canon(trace.records)};
  // The graph core gives the identical refusal text for the identical document and inputs.
  const gsim=G.createSimulation(d).sim;
  gsim.inject('outside',{principal:'svc:ops'});gsim.inject('outside',{principal:'eve'});gsim.inject('outside',{});gsim.run();
  out.vault.devReasons=gsim.refusals().map(r=>r.reason).sort();
}
// Mutation: without the ACL every principal gets in (graph_core_qa.py:168).
{
  const d=vaultDoc(null);
  const run=settle(started({doc:d,inputs:[inj('outside','out',null,{principal:'eve'})]}));
  out.noAcl={arrivedInside:msgs(run).filter(r=>r.subject.entity==='inside'&&r.hop.event==='arrived').length};
}
// Bite check target: a mutant acl-deny-does-not-win still refuses the denied principal, never a
// silent pass; expressed here as a direct check that the deny entry still wins over the matching
// allow (svc:intruder matches svc:* too).
{
  const d=vaultDoc(acl);
  const run=settle(started({doc:d,inputs:[inj('outside','out',null,{principal:'svc:intruder'})]}));
  out.denyWins={refused:msgs(run).filter(r=>r.hop.event==='refused').map(r=>r.hop.reason)};
}

// The graph core's Room (tests/graph_core_qa.py:170-174): exit is checked on the way out.
const roomDoc=D.normalizeDocument({components:[
  {id:'room',symbolId:'plane',x:400,y:200,form:{dimension:2,regions:{interior:{state:'open'}}},config:{attachmentDefaults:'none',label:'Room',acl:{entries:[{principal:'*',allow:['enter']}]}}},
  {id:'gate',symbolId:'point',x:550,y:200,canvasId:'canvas:component:room',parentId:'room',placement:{kind:'edge',hostId:'room',side:'right',t:.5},form:{dimension:0},config:{signalMode:'relay'}},
  {...A('worker'),canvasId:'canvas:component:room',parentId:'room'},
  A('world',{signalMode:'passive'})],
  wires:[{id:'e1',a:'worker',aSide:'out',b:'gate',bSide:'out',canvasId:'canvas:component:room'},
         {id:'e2',a:'gate',aSide:'out',b:'world',bSide:'in',canvasId:'canvas:global'}]});
{
  const run=settle(started({doc:roomDoc,inputs:[inj('worker','out',null,{principal:'svc:a'})]}));
  const m=msgs(run);
  out.room={refused:m.filter(r=>r.hop.event==='refused').map(r=>r.hop.reason),worldArrivals:m.filter(r=>r.subject.entity==='world'&&r.hop.event==='arrived').length};
}

// Levels: a lever's own principal, else the principal of the arrival that set it, crosses the
// same plane boundary under the crossing op; a refusal is a record with rule refused, level true.
const leverDoc=principal=>D.normalizeDocument({components:[
  {id:'vault',symbolId:'plane',x:400,y:200,form:{dimension:2,regions:{interior:{state:'open'}}},config:{label:'Vault',attachmentDefaults:'none',acl:{entries:[{principal:'svc:*',allow:['enter']}]}}},
  {id:'door',symbolId:'point',x:250,y:200,canvasId:'canvas:component:vault',parentId:'vault',placement:{kind:'edge',hostId:'vault',side:'left',t:.5},form:{dimension:0},config:{signalMode:'relay'}},
  {id:'inside',symbolId:'act',x:0,y:0,canvasId:'canvas:component:vault',parentId:'vault',config:{signalMode:'relay'}},
  {id:'lever',symbolId:'lever',x:0,y:0,config:{signal:{value:1},...(principal?{principal}:{})}}],
  wires:[{id:'k3',a:'lever',aSide:'out',b:'door',bSide:'out',canvasId:'canvas:global'},
         {id:'k2',a:'door',aSide:'out',b:'inside',bSide:'in',canvasId:'canvas:component:vault'}]});
{
  // The principalled lever drives the inside level: every record it reaches carries its principal,
  // and the run makes no level refusal.
  const d=leverDoc('svc:ops'),run=settle(started({doc:d}));
  const insideRecord=run.records.find(r=>r.subject.entity==='inside'&&r.value===true);
  // inside is itself an implied combine device (an 'act' card, not a Point): its own Wire-named
  // input (k2) carries the crossing's principal, and its re-derived output picks it up the same
  // way a Point's arrival does (the first Wire-named input, in wire order, whose value is its own).
  out.level={principals:run.records.filter(r=>['lever','door','inside'].includes(r.subject.entity)&&r.value===true).map(r=>[r.subject.entity,r.principal]),
    insideSet:!!insideRecord,levelRefusals:run.records.filter(r=>r.level===true).length};
  // With the lever anonymous, the door's own level is refused crossing into the Vault and the
  // inside level is never set.
  const d2=leverDoc(null),run2=settle(started({doc:d2}));
  const refusal=run2.records.find(r=>r.level===true);
  out.levelAnon={refusal:refusal?[refusal.subject.entity,refusal.provenance.rule,/anonymously/.test(refusal.value)]:null,
    insideSet:run2.records.some(r=>r.subject.entity==='inside'&&r.value===true)};
}

// Example 09's s-approve handlers (graph_core_qa.py 09 fixture): the case's own principal
// (intake:case-48219) enters the Run plane and notify's own principal (svc:mailer) carries it out
// again, so the message reaches the customer and makes no message refusal. The document declares
// no signal anywhere, but every Wire still carries the level channel too (STATE-SPACE.md): case's
// own undeclared signalMode source implies an asserted level of 1 (src/04-signal-model.js
// signalConfig), which case's own principal carries across the Run boundary entering, through the
// implied combine devices relay cards become (each its own Wire-named input is the via a Point's
// arrival gives), to notify, whose own principal carries it out again: no level refusal either.
{
  const print=D.documentFromFilePayload(JSON.parse(fs.readFileSync('examples/09-print-ai-proof-run.sov','utf8')));
  const pack=S.loadPack(JSON.parse(fs.readFileSync('data/core.logic.pack.json','utf8'))).pack;
  const run=settle(started({doc:print,packs:[pack],inputs:[{entity:'case',point:'out',channel:'message',value:{channel:null,payload:{caseId:'1',proof:'good'},principal:null},at:0}]}));
  const m=msgs(run);
  out.print={customerArrivals:m.filter(r=>r.subject.entity==='customer'&&r.hop.event==='arrived').length,
    refused:m.filter(r=>r.hop.event==='refused').map(r=>r.hop.reason),
    levelRefusals:run.records.filter(r=>r.level===true).map(r=>[r.subject.entity,r.value])};
}

console.log(JSON.stringify(out));
"""


def main() -> None:
    proc = subprocess.run(['node', '-e', SCRIPT], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    r = json.loads(proc.stdout)

    v = r['vault']
    assert v['arrivedInside'] == 1, v
    assert v['refused'] == sorted(['acl: eve may not enter Vault', 'acl: no principal may enter Vault anonymously']), v['refused']
    assert v['crossed'] == [['door', 'k2', 'svc:ops']], v['crossed']
    assert v['valid'], v
    assert v['replay'] == {'ok': True, 'same': True}, v['replay']
    assert v['devReasons'] == v['refused'], ('the graph core gives the identical reason text', v)

    assert r['noAcl']['arrivedInside'] == 1, r['noAcl']

    assert r['denyWins']['refused'] == ['acl: svc:intruder is denied enter on Vault'], r['denyWins']

    room = r['room']
    assert room['refused'] == ['acl: svc:a may not exit Room'], room
    assert room['worldArrivals'] == 0, room

    lv = r['level']
    assert all(p == 'svc:ops' for _, p in lv['principals']), lv['principals']
    assert {e for e, _ in lv['principals']} == {'lever', 'door', 'inside'}, lv['principals']
    assert lv['insideSet'] is True and lv['levelRefusals'] == 0, lv

    la = r['levelAnon']
    assert la['refusal'] is not None, la
    assert la['refusal'][0] == 'door' and la['refusal'][1] == 'refused' and la['refusal'][2] is True, la['refusal']
    assert la['insideSet'] is False, la

    p = r['print']
    assert p['customerArrivals'] == 1, ('intake:case-48219 enters, svc:mailer carries it out', p)
    assert p['refused'] == [], p['refused']
    assert p['levelRefusals'] == [], p['levelRefusals']

    print('STATE SPACE ACL PASS')


if __name__ == '__main__':
    main()
