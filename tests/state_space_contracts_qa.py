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
  extraProvenance:r=>{r.provenance.threshold=0.8}
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
  const rc=D.applyOperation(d,clone(op1));
  const g=d.components.find(c=>c.id==='g');
  const A=globalThis.SovSchematicAttachment;
  out.bind={op:op1,ok:rc.ok,msg:rc.error?.message||'',definition:g.config.definition,mode:g.config.attachmentDefaults,stored:g.config.attachmentPoints,specs:A.pointSpecs(g).map(s=>({id:s.id,side:s.side,t:s.t,flow:s.flow,channels:s.channels})),check:S.checkDocument(d,packs),reloaded:reload(d).components.find(c=>c.id==='g').config};
  out.unresolved=S.bindDefinition(d,'g','logic.nand@1',packs);
  // PORT_IN_USE: a Wire ends on `top`, which logic.and@1 does not have.
  const e=D.makeDocument({id:'inuse'});
  mk(e,{id:'g',symbolId:'act',x:300,y:100});mk(e,{id:'s',symbolId:'act',x:0,y:100});
  const w=mkw(e,{id:'w',a:'s',aSide:'out',b:'g',bSide:'control'});
  const rev=e.revision,before=JSON.stringify(e.components.find(c=>c.id==='g'));
  const rc2=D.applyOperation(e,S.bindDefinition(e,'g','logic.and@1',packs));
  out.inUse={wire:w.ok,bound:e.wires[0].bAttachment.pointId,ok:rc2.ok,msg:rc2.error?.message||'',rev:e.revision===rev,same:JSON.stringify(e.components.find(c=>c.id==='g'))===before};
}

// Step 9: one crafted document per checkDocument code, and a valid A AND B -> Q.
{
  const base=()=>{const d=D.makeDocument({id:'q'});mk(d,{id:'pa',symbolId:'point',x:0,y:0});mk(d,{id:'pb',symbolId:'point',x:0,y:200});mk(d,{id:'g',symbolId:'act',x:300,y:100});mk(d,{id:'pq',symbolId:'point',x:600,y:100});return d};
  const valid=base();
  const bound=D.applyOperation(valid,S.bindDefinition(valid,'g','logic.and@1',packs));
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
  // DEFINITION_UNRESOLVED: a definition no pack holds.
  {const d=D.makeDocument({id:'un'});mk(d,{id:'g',symbolId:'act',x:0,y:0});upd(d,'g',{config:{definition:'logic.nand@1'}});crafted.DEFINITION_UNRESOLVED=reload(d)}
  // DEFINITION_PORTS: bound to logic.and@1 but still carrying the template trio.
  {const d=D.makeDocument({id:'dp'});mk(d,{id:'g',symbolId:'act',x:0,y:0});upd(d,'g',{config:{definition:'logic.and@1'}});crafted.DEFINITION_PORTS=reload(d)}
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
   mkw(d,{id:'dupBad',a:'a',aSide:'out',b:'b',bSide:'in',config:{direction:'duplex'}});
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
            undo, is_error = rpc(base, 'schematic.history.undo', {}, 4)
            assert not is_error and not undo['components'], undo
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
const ctx=vm.createContext({window:{},SovSchematicData:D,diagram,Date,Math,String,
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

    examples = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'examples').glob('*.sov'))
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

    # checkDocument on every example returns without throwing; its result is printed.
    for file, res in r['examples'].items():
        assert 'threw' not in res, (file, res)
        print(f'checkDocument {file}: {json.dumps(res["result"])}')

    # Step 4 on every surface: an invalid merge update is refused, with no revision and no history.
    check_http_mcp()
    ad = check_adapter()
    assert ad['made'] and ad['denied']['ok'] is False and 'MERGE_INVALID' in ad['denied']['error']['message'], ad
    assert ad['labelled'] == [] and ad['runtime'] == [] and ad['revSame'] and ad['same'] and ad['channels'] == GOOD_MERGE_PORTS[0]['channels'], ad

    # The page loads 07 right after the data core; the built page carries it.
    page = (ROOT / 'index.source.html').read_text(encoding='utf-8')
    assert '<script src="src/05-data-core.js"></script>\n<script src="src/07-state-space.js"></script>' in page, 'index.source.html must load 07 after 05'
    assert 'data-beta-module="src/07-state-space.js"' in (ROOT / 'index.html').read_text(encoding='utf-8'), 'index.html does not carry 07; run build.py'
    print('PASS state space contracts QA')


if __name__ == '__main__':
    main()
