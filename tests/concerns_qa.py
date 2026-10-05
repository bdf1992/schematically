"""Concerns QA (NOTATION-MODEL.md "Concerns"; DATA-FORMATS.md "Answers").

A notation declares concerns: the questions a schematic drawn in it should answer, for the document,
for Components and for Wires. A document carries the answers in meta.answers and config.answers, the
data core validates them against the resolved notation, and SovSchematicData.concernReport lists each
declared concern as answered or open. An open concern is information, never an error.

Browser part (index.html in Chromium), then node scripts/validate_sov.mjs:
  (a) on a schematic-notation document the report gives four rows, all open, target null, with the
      ids what, why, alternatives, smaller in order and the built-in questions;
  (b) with meta.answers {what, why} the report gives answered 2 and open 2 and the two answers;
  (c) a carried notation that extends schematic, rewords the document concern why and adds the
      component concerns made-by and repeatable and the wire concern carries: why is still second
      with the new question, and two cards and one wire give 4 + 2 * 2 + 1 = 9 rows, the document's
      first, then each card's, then the wire's;
  (d) a card created with config.answers {made-by} is admitted and its row is answered; an update
      with answers null removes the key; a wire's answer is admitted the same way; on a card with
      two answers an update with one key null leaves the other, and a second update removing the
      last leaves no answers key;
  (e) config.answers {nope} on a card is refused with ANSWER_UNKNOWN on create and on update, the
      document unchanged; so is a wire's;
  (f) on a schematic-notation document a card's config.answers {made-by} is refused with
      ANSWER_UNDECLARED on create and on update;
  (g) meta.answers {what: ''}, {what: 3} and [] each make validateDocument report ANSWER_INVALID;
      meta.answers {nope} reports ANSWER_UNKNOWN; a card's and a wire's bad answers are reported
      under their ids; an open concern reports nothing;
  (h) a carried notation with a concern lacking a question, one with applies 'card' and one with
      the same applies and id twice each report CONCERN_INVALID, and the entry is not in concernsOf;
  (i) saving and opening keeps meta.answers and every config.answers, and a document with no
      answers has no answers key anywhere in its compact form, before and after an edit;
  (j) node scripts/validate_sov.mjs --concerns on the document of (c) with one answer exits 0 and
      prints 8 lines beginning 'open' and 'concerns: 1 answered, 8 open'; without the flag neither;
  (k) the page logs no errors.
  (m) a retype is read on the record it makes: an act card holding an answer to a concern asked of
      [act], retyped to hold, is refused with ANSWER_UNKNOWN (alone and in a batch) unless the same
      patch removes the answer; a card with no answers retypes as before.
  (l) a component concern with symbols [act] gives a row for an act card and none for a hold card;
      an answer to it on the hold card is refused with ANSWER_UNKNOWN on create, on update and by
      answerConcerns, and reported on load; a later notation's entry with the same id and no
      symbols replaces it whole; symbols [], symbols on a document or a wire concern, a repeat, a
      value that is not a non-empty string and symbols that is not a list each report
      CONCERN_INVALID, and the entry is not in concernsOf.
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

# The four document concerns the built-in schematic notation declares, in order.
BUILTIN = [
    ('what', 'What it is', 'What is this a schematic of, in one or two sentences?'),
    ('why', 'Why build it', 'Why would someone build this or study it?'),
    ('alternatives', 'Alternatives', 'What are the alternatives, and why this one over the others?'),
    ('smaller', 'Smaller first', 'Can a smaller version be built first, and what is it?'),
]
PLANT_WHY = 'Why would the plant run this line?'
# A domain notation's concerns: one built-in question reworded, two for every card, one for every wire.
PLANT = [
    {'id': 'why', 'applies': 'document', 'question': PLANT_WHY},
    {'id': 'made-by', 'applies': 'component', 'title': 'Made by', 'question': 'What makes this, and from what?'},
    {'id': 'repeatable', 'applies': 'component', 'question': 'Is this made once or over and over?'},
    {'id': 'carries', 'applies': 'wire', 'title': 'Carries', 'question': 'What moves along this, and how much?'},
]

PAGE = r"""([plant])=>{
  const A=window.SovSchematicAPI,D=SovSchematicData,N=SovSchematicNotation,out={};
  const notation=(list,id='plant')=>({id:'notation-'+id,kind:'notation',label:'Plant',data:{id,name:'Plant',version:1,extends:'schematic',concerns:list}});
  // Two cards and one wire, in the carried notation or in the plain schematic notation.
  const doc=({carried=true,list=plant,meta,cardAnswers,wireAnswers}={})=>({schema:D.DOCUMENT_SCHEMA,id:'concerns',...(carried?{notation:'plant'}:{}),
    ...(meta?{meta}:{}),
    components:[
      {id:'ore',symbolId:'act',x:200,y:200,config:{label:'Ore',...(cardAnswers?{answers:cardAnswers}:{})}},
      {id:'bar',symbolId:'act',x:560,y:200,config:{label:'Bar'}}],
    wires:[{id:'belt',a:'ore',aSide:'out',b:'bar',bSide:'in',config:{label:'belt',...(wireAnswers?{answers:wireAnswers}:{})}}],
    references:carried?[notation(list)]:[]});
  const made=input=>{const d=D.makeDocument(input);D.normalizeDocument(d);return d};
  const row=r=>[r.applies,r.target,r.concern];

  // (a) the built-in four, all open.
  {const d=made(doc({carried:false})),before=JSON.stringify(d);out.plain=D.concernReport(d);out.plainUnchanged=JSON.stringify(d)===before}
  // (b) two answered.
  out.two=D.concernReport(made(doc({carried:false,meta:{answers:{what:'A half adder.',why:'To teach carry.'}}})));
  // (c) a domain notation rewords one and adds its own.
  {const d=made(doc());out.plant=D.concernReport(d);out.plantErrors=D.validateDocument(d).errors;
   const r=N.resolve(d).notation;out.plantOf={document:N.concernsOf(r,'document').map(c=>c.id),component:N.concernsOf(r,'component').map(c=>c.id),wire:N.concernsOf(r,'wire').map(c=>c.id),findings:N.concernFindings(r)};
   out.source=JSON.stringify(doc({meta:{answers:{what:'An ore line.'}}}))}
  // (d) an answer on a card and on a wire; null removes.
  {const d=made(doc());
   const c=D.applyOperation(d,{op:'create',resource:'component',value:{id:'slag',symbolId:'act',x:200,y:420,config:{label:'Slag',answers:{'made-by':'Smelt two ore.'}}}});
   const w=D.applyOperation(d,{op:'update',resource:'wire',resourceId:'belt',patch:{config:{answers:{carries:'Bars, four a minute.'}}}});
   const w2=D.applyOperation(d,{op:'create',resource:'wire',value:{id:'back',a:'bar',aSide:'out',b:'ore',bSide:'in',config:{label:'back',answers:{carries:'Scrap.'}}}});
   const report=D.concernReport(d);
   out.admitted={card:c.ok,wire:w.ok,wireCreate:w2.ok,errors:D.validateDocument(d).errors,stored:D.read(d,'component','slag').config.answers,storedWire:D.read(d,'wire','belt').config.answers,storedBack:D.read(d,'wire','back').config.answers,
     rows:report.rows.filter(r=>r.answered).map(r=>[...row(r),r.answer]),total:report.rows.length,answered:report.answered,open:report.open};
   const more=D.applyOperation(d,{op:'update',resource:'component',resourceId:'slag',patch:{config:{answers:{repeatable:'Over and over.'}}}});
   out.merged={ok:more.ok,stored:D.read(d,'component','slag').config.answers};
   const c1=D.applyOperation(d,{op:'update',resource:'component',resourceId:'slag',patch:{config:{answers:null}}});
   const w1=D.applyOperation(d,{op:'update',resource:'wire',resourceId:'belt',patch:{config:{answers:null}}});
   const cfg=D.read(d,'component','slag').config,wcfg=D.read(d,'wire','belt').config,after=D.concernReport(d);
   out.cleared={ok:c1.ok&&w1.ok,cardKey:'answers' in cfg,wireKey:'answers' in wcfg,label:cfg.label,wireLabel:wcfg.label,
     compactKey:'answers' in D.compactComponent(D.read(d,'component','slag')).config,answered:after.answered,slag:after.rows.filter(r=>r.target==='slag').map(r=>r.answered)}}
  // (d2) per-key removal on update: one key null leaves the other; removing the last leaves no key.
  {const d=made(doc({cardAnswers:{'made-by':'Dug from the pit.',repeatable:'Over and over.'}}));
   const one=D.applyOperation(d,{op:'update',resource:'component',resourceId:'ore',patch:{config:{answers:{repeatable:null}}}});
   const left=D.read(d,'component','ore').config.answers;
   const last=D.applyOperation(d,{op:'update',resource:'component',resourceId:'ore',patch:{config:{answers:{'made-by':null}}}});
   const cfg=D.read(d,'component','ore').config;
   const unknown=D.applyOperation(d,{op:'update',resource:'component',resourceId:'ore',patch:{config:{answers:{nope:null}}}});
   const onCreate=D.applyOperation(d,{op:'create',resource:'component',value:{id:'slag',symbolId:'act',x:200,y:420,config:{label:'Slag',answers:{'made-by':null}}}});
   out.perKey={one:one.ok,left,last:last.ok,key:'answers' in cfg,compactKey:'answers' in D.compactComponent(D.read(d,'component','ore')).config,label:cfg.label,
     errors:D.validateDocument(d).errors,unknown:unknown.error?.message||'',onCreate:onCreate.error?.message||''}}
  // (e) (f) refusals leave the document unchanged.
  const refuse=(base,op)=>{const d=made(base),before=JSON.stringify(d);const r=D.applyOperation(d,op);return {ok:r.ok,message:r.error?.message||'',unchanged:JSON.stringify(d)===before}};
  const card=answers=>({id:'slag',symbolId:'act',x:200,y:420,config:{label:'Slag',answers}});
  const back=answers=>({id:'back',a:'bar',aSide:'out',b:'ore',bSide:'in',config:{label:'back',answers}});
  out.refusals={
    unknownCreate:refuse(doc(),{op:'create',resource:'component',value:card({nope:'x'})}),
    unknownUpdate:refuse(doc(),{op:'update',resource:'component',resourceId:'ore',patch:{config:{answers:{nope:'x'}}}}),
    unknownWireCreate:refuse(doc(),{op:'create',resource:'wire',value:back({nope:'x'})}),
    unknownWireUpdate:refuse(doc(),{op:'update',resource:'wire',resourceId:'belt',patch:{config:{answers:{nope:'x'}}}}),
    undeclaredCreate:refuse(doc({carried:false}),{op:'create',resource:'component',value:card({'made-by':'x'})}),
    undeclaredUpdate:refuse(doc({carried:false}),{op:'update',resource:'component',resourceId:'ore',patch:{config:{answers:{'made-by':'x'}}}}),
    undeclaredWireUpdate:refuse(doc({carried:false}),{op:'update',resource:'wire',resourceId:'belt',patch:{config:{answers:{carries:'x'}}}}),
    emptyCreate:refuse(doc(),{op:'create',resource:'component',value:card({'made-by':'  '})}),
    emptyUpdate:refuse(doc(),{op:'update',resource:'component',resourceId:'ore',patch:{config:{answers:{'made-by':''}}}}),
    listUpdate:refuse(doc(),{op:'update',resource:'component',resourceId:'ore',patch:{config:{answers:['x']}}}),
    knownUpdate:refuse(doc(),{op:'update',resource:'component',resourceId:'ore',patch:{config:{answers:{'made-by':'Dug.'}}}}),
  };
  // (g) what loading reports.
  const load=input=>D.validateDocument(D.makeDocument(input)).errors;
  out.load={
    empty:load(doc({carried:false,meta:{answers:{what:''}}})),
    number:load(doc({carried:false,meta:{answers:{what:3}}})),
    list:load(doc({carried:false,meta:{answers:[]}})),
    unknown:load(doc({carried:false,meta:{answers:{nope:'x'}}})),
    open:load(doc({carried:false})),
    none:load(doc({carried:false,meta:{answers:{}}})),
    card:load(doc({cardAnswers:{nope:'x'}})),
    wire:load(doc({wireAnswers:{carries:''}})),
    cardUndeclared:load(doc({carried:false,cardAnswers:{'made-by':'x'}})),
  };
  out.markers=D.markersFor(D.makeDocument(doc({carried:false,meta:{answers:{nope:'x'}}}))).map(m=>m.rule);
  // (h) a notation whose own entries break a rule: reported, and the entry is not admitted.
  const judge=list=>{const d=D.makeDocument(doc({list})),r=N.resolve(d).notation;return {errors:D.validateDocument(d).errors.filter(e=>/CONCERN_INVALID/.test(e)),findings:N.concernFindings(r),
    document:N.concernsOf(r,'document').map(c=>c.id),component:N.concernsOf(r,'component').map(c=>c.id),wire:N.concernsOf(r,'wire').map(c=>c.id),rows:D.concernReport(d).rows.length}};
  out.invalid={
    noQuestion:judge([plant[1],{id:'cost',applies:'component',title:'Cost'}]),
    blankQuestion:judge([plant[1],{id:'cost',applies:'component',question:'   '}]),
    badApplies:judge([plant[1],{id:'cost',applies:'card',question:'What does it cost?'}]),
    twice:judge([plant[1],{id:'cost',applies:'component',question:'What does it cost?'},{id:'cost',applies:'component',question:'What is the cost?'}]),
    unknownKey:judge([plant[1],{id:'cost',applies:'component',question:'What does it cost?',unit:'ore'}]),
    notObject:judge([plant[1],'cost']),
    badTitle:judge([plant[1],{id:'cost',applies:'component',question:'What does it cost?',title:7}]),
  };
  // (l) a component concern names the symbols it is asked of: ore is an act card, bar a hold card.
  {const feeds={id:'feeds',applies:'component',symbols:['act'],title:'Feeds',question:'What does this act feed?'};
   const base=({list=[...plant,feeds],barAnswers}={})=>{const x=doc({list});x.components[1].symbolId='hold';if(barAnswers)x.components[1].config.answers=barAnswers;return x};
   const d=made(base()),report=D.concernReport(d);
   const tank=answers=>({id:'tank',symbolId:'hold',x:200,y:420,config:{label:'Tank',answers}}),mill=answers=>({id:'mill',symbolId:'act',x:200,y:420,config:{label:'Mill',answers}});
   const verb=target=>{const x=made(base()),before=JSON.stringify(x),r=D.answerConcerns(x,{answers:[{concern:'feeds',target,answer:'The bar.'}]});return {ok:r.ok,message:r.error?.message||'',unchanged:JSON.stringify(x)===before}};
   // The join along extends: a later entry with the same applies and id replaces the earlier whole, symbols included.
   const chained=x=>{x.references=[{id:'notation-plant0',kind:'notation',label:'Plant 0',data:{id:'plant0',name:'Plant 0',version:1,extends:'schematic',concerns:[feeds]}},
     {id:'notation-plant',kind:'notation',label:'Plant',data:{id:'plant',name:'Plant',version:1,extends:'plant0',concerns:[{id:'feeds',applies:'component',question:'What does this feed?'}]}}];return x};
   const joined=made(chained(base()));
   out.symbols={errors:D.validateDocument(d).errors,of:N.concernsOf(N.resolve(d).notation,'component').map(c=>[c.id,c.symbols??null]),
     feeds:report.rows.filter(r=>r.concern==='feeds').map(row),bar:report.rows.filter(r=>r.target==='bar').map(r=>r.concern),ore:report.rows.filter(r=>r.target==='ore').map(r=>r.concern),total:report.rows.length,
     createHold:refuse(base(),{op:'create',resource:'component',value:tank({feeds:'x'})}),
     updateHold:refuse(base(),{op:'update',resource:'component',resourceId:'bar',patch:{config:{answers:{feeds:'x'}}}}),
     createAct:refuse(base(),{op:'create',resource:'component',value:mill({feeds:'The bar.'})}),
     updateAct:refuse(base(),{op:'update',resource:'component',resourceId:'ore',patch:{config:{answers:{feeds:'The bar.'}}}}),
     verbHold:verb('bar'),verbAct:verb('ore'),
     load:load(base({barAnswers:{feeds:'x'}})),
     joinedOf:N.concernsOf(N.resolve(joined).notation,'component').map(c=>[c.id,c.symbols??null,c.question]),joinedFeeds:D.concernReport(joined).rows.filter(r=>r.concern==='feeds').map(row)};
   const cost=extra=>[plant[1],{id:'cost',applies:'component',question:'What does it cost?',...extra}];
   out.symbolsInvalid={
     empty:judge(cost({symbols:[]})),
     onDocument:judge([plant[1],{id:'scope',applies:'document',question:'What is in scope?',symbols:['act']}]),
     onWire:judge([plant[1],{id:'load',applies:'wire',question:'What load does it take?',symbols:['act']}]),
     repeat:judge(cost({symbols:['act','act']})),
     notString:judge(cost({symbols:['act',3]})),
     blank:judge(cost({symbols:['act','  ']})),
     notList:judge(cost({symbols:'act'})),
   }}
  // (m) a retype is checked on the record it makes: ore is an act card holding an answer to feeds; keeps is asked of hold.
  {const feeds={id:'feeds',applies:'component',symbols:['act'],title:'Feeds',question:'What does this act feed?'},keeps={id:'keeps',applies:'component',symbols:['hold'],title:'Keeps',question:'What does this hold keep?'};
   const base=(oreAnswers={feeds:'The bar.'})=>doc({list:[...plant,feeds,keeps],cardAnswers:oreAnswers});
   const retype=(patch,start)=>{const d=made(start||base()),before=JSON.stringify(d),r=D.applyOperation(d,{op:'update',resource:'component',resourceId:'ore',patch});
     const ore=D.read(d,'component','ore');return {ok:r.ok,message:r.error?.message||'',unchanged:JSON.stringify(d)===before,symbol:ore.symbolId,answers:ore.config.answers??null,errors:D.validateDocument(d).errors,
       keeps:D.concernReport(d).rows.filter(x=>x.target==='ore'&&x.concern==='keeps').map(x=>[x.answered,x.answer??null])}};
   // The same two operations, the second a retype: first leaving feeds in place, then removing it.
   const ops=patch=>({operations:[{op:'update',resource:'component',id:'bar',patch:{config:{label:'Bar two'}}},{op:'update',resource:'component',id:'ore',patch}]});
   const d=made(base()),before=JSON.stringify(d),batch=D.applyBatch(d,ops({symbolId:'hold'})),batchUnchanged=JSON.stringify(d)===before;
   const batchOk=D.applyBatch(d,ops({symbolId:'hold',config:{answers:{feeds:null}}}));
   out.retype={bare:retype({symbolId:'hold'}),removed:retype({symbolId:'hold',config:{answers:{feeds:null}}}),swapped:retype({symbolId:'hold',config:{answers:{feeds:null,keeps:'Bars.'}}}),
     allNull:retype({symbolId:'hold',config:{answers:null}}),same:retype({symbolId:'act'}),none:retype({symbolId:'hold'},base(null)),
     batch:{ok:batch.ok,message:batch.error?.message||'',index:batch.error?.index??null,unchanged:batchUnchanged},
     batchOk:{ok:batchOk.ok,label:D.read(d,'component','bar').config.label,symbol:D.read(d,'component','ore').symbolId,answers:D.read(d,'component','ore').config.answers??null}}}
  // (i) saving and opening keeps every answer; a document without answers gains no answers key.
  {const full=doc({meta:{answers:{what:'An ore line.',why:'To make bars.'}},cardAnswers:{'made-by':'Dug from the pit.'},wireAnswers:{carries:'Bars, four a minute.'}});
   A.document.replace(full);fitDiagram();
   const first=A.file.document(),saved=JSON.stringify(first);
   A.file.open(saved,'concerns.sov');
   const again=A.file.document();
   const pick=d=>({meta:d.meta?.answers??null,ore:d.components.find(c=>c.id==='ore')?.config?.answers??null,bar:d.components.find(c=>c.id==='bar')?.config?.answers??null,belt:d.wires.find(w=>w.id==='belt')?.config?.answers??null});
   out.kept={saved:pick(first),reopened:pick(again),compact:pick(D.compactDocument(D.makeDocument(full))),report:A.file.document()&&D.concernReport(D.makeDocument(again)).answered};
   const bare=doc({carried:false});A.document.replace(bare);
   const savedBare=JSON.stringify(A.file.document());A.file.open(savedBare,'bare.sov');
   const d=made(bare);
   const before=JSON.stringify(D.compactDocument(d));
   D.concernReport(d);
   D.applyOperation(d,{op:'create',resource:'component',value:{id:'slag',symbolId:'act',x:200,y:420,config:{label:'Slag',answers:{}}}});
   D.applyOperation(d,{op:'update',resource:'component',resourceId:'ore',patch:{config:{label:'Ore two'}}});
   D.applyOperation(d,{op:'update',resource:'wire',resourceId:'belt',patch:{config:{label:'belt two'}}});
   const has=text=>/"answers"/.test(text);
   out.bare={saved:has(savedBare),reopened:has(JSON.stringify(A.file.document())),compact:has(before),edited:has(JSON.stringify(D.compactDocument(d))),normalised:has(JSON.stringify(d))}}
  return out;
}"""


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(200)
        r = page.evaluate(PAGE, [PLANT])
        page.wait_for_timeout(100)
        browser.close()

    # (a) The built-in four, all open.
    plain = r['plain']
    assert plain['notation'] == 'schematic' and len(plain['rows']) == 4, ('a schematic document does not report four concerns', plain)
    assert [(x['concern'], x['title'], x['question']) for x in plain['rows']] == BUILTIN, ('the built-in concerns differ', plain['rows'])
    assert all(x['applies'] == 'document' and x['target'] is None and x['answered'] is False and 'answer' not in x for x in plain['rows']), plain['rows']
    assert all(x['question'].endswith('?') and not x['question'].endswith('??') for x in plain['rows']), plain['rows']
    assert (plain['answered'], plain['open']) == (0, 4) and r['plainUnchanged'], ('counts, or the report changed the document', plain['answered'], plain['open'], r['plainUnchanged'])
    print('(a) schematic notation: 4 document concerns, all open:', [x['concern'] for x in plain['rows']])

    # (b) Two answered.
    two = r['two']
    assert (two['answered'], two['open']) == (2, 2), ('two answers do not count as two', two['answered'], two['open'])
    assert [(x['concern'], x['answered'], x.get('answer')) for x in two['rows']] == [('what', True, 'A half adder.'), ('why', True, 'To teach carry.'), ('alternatives', False, None), ('smaller', False, None)], two['rows']
    print('(b) meta.answers {what, why}: answered 2, open 2')

    # (c) A domain notation rewords one and adds its own.
    plant = r['plant']
    assert r['plantErrors'] == [] and r['plantOf']['findings'] == [], ('the carried notation has findings', r['plantErrors'], r['plantOf'])
    assert r['plantOf']['document'] == ['what', 'why', 'alternatives', 'smaller'], ('a reworded concern moved', r['plantOf'])
    assert r['plantOf']['component'] == ['made-by', 'repeatable'] and r['plantOf']['wire'] == ['carries'], r['plantOf']
    why = plant['rows'][1]
    assert why['concern'] == 'why' and why['question'] == PLANT_WHY and why['title'] == 'why', ('why is not second with the new question', why)
    assert [x['question'] for x in plant['rows'][:4] if x['concern'] != 'why'] == [q for i, _, q in BUILTIN if i != 'why'], plant['rows'][:4]
    order = [[x['applies'], x['target'], x['concern']] for x in plant['rows']]
    expect = ([['document', None, i] for i, _, _ in BUILTIN]
              + [['component', c, i] for c in ('ore', 'bar') for i in ('made-by', 'repeatable')]
              + [['wire', 'belt', 'carries']])
    assert len(order) == 9 and order == expect, ('the rows are not 4 + 2 * 2 + 1 in order', order)
    assert plant['notation'] == 'plant' and (plant['answered'], plant['open']) == (0, 9), plant
    assert [x['title'] for x in plant['rows'][4:6]] == ['Made by', 'repeatable'], ('title is the entry title or its id', plant['rows'][4:6])
    print('(c) carried notation: why reworded in place; 9 rows:', [f"{a}:{t or '-'}:{c}" for a, t, c in order])

    # (d) Answers on a card and a wire; null removes.
    adm = r['admitted']
    assert adm['card'] and adm['wire'] and adm['wireCreate'] and adm['errors'] == [], ('an answer to a declared concern was refused', adm)
    assert adm['stored'] == {'made-by': 'Smelt two ore.'} and adm['storedWire'] == {'carries': 'Bars, four a minute.'} and adm['storedBack'] == {'carries': 'Scrap.'}, adm
    assert adm['rows'] == [['component', 'slag', 'made-by', 'Smelt two ore.'], ['wire', 'belt', 'carries', 'Bars, four a minute.'], ['wire', 'back', 'carries', 'Scrap.']], ('the answered rows', adm['rows'])
    assert (adm['total'], adm['answered'], adm['open']) == (4 + 3 * 2 + 2, 3, 9), (adm['total'], adm['answered'], adm['open'])
    assert r['merged']['ok'] and r['merged']['stored'] == {'made-by': 'Smelt two ore.', 'repeatable': 'Over and over.'}, ('an update does not merge its keys', r['merged'])
    c = r['cleared']
    assert c['ok'] and not c['cardKey'] and not c['wireKey'] and not c['compactKey'], ('answers null did not remove config.answers', c)
    assert c['label'] == 'Slag' and c['wireLabel'] == 'belt' and c['slag'] == [False, False] and c['answered'] == 1, c
    print('(d) a card and a wire answer their concerns; answers null removes config.answers')
    pk = r['perKey']
    assert pk['one'] and pk['left'] == {'made-by': 'Dug from the pit.'}, ('an update with one key null did not leave the other', pk)
    assert pk['last'] and not pk['key'] and not pk['compactKey'] and pk['label'] == 'Ore' and pk['errors'] == [], ('removing the last answer left an answers key', pk)
    assert pk['unknown'].startswith('ANSWER_UNKNOWN:') and pk['onCreate'].startswith('ANSWER_INVALID:'), ('a null for an undeclared key, or a null on create, was admitted', pk)
    print('(d) an update with one key null removes that answer and leaves the other; removing the last leaves no answers key')

    # (e) (f) Refusals.
    f = r['refusals']
    for name, code in (('unknownCreate', 'ANSWER_UNKNOWN'), ('unknownUpdate', 'ANSWER_UNKNOWN'), ('unknownWireCreate', 'ANSWER_UNKNOWN'), ('unknownWireUpdate', 'ANSWER_UNKNOWN'),
                       ('undeclaredCreate', 'ANSWER_UNDECLARED'), ('undeclaredUpdate', 'ANSWER_UNDECLARED'), ('undeclaredWireUpdate', 'ANSWER_UNDECLARED'),
                       ('emptyCreate', 'ANSWER_INVALID'), ('emptyUpdate', 'ANSWER_INVALID'), ('listUpdate', 'ANSWER_INVALID')):
        assert not f[name]['ok'] and f[name]['message'].startswith(code + ':') and f[name]['unchanged'], (name, 'expected a refusal with', code, 'got', f[name])
    assert 'config.answers.nope' in f['unknownCreate']['message'] and 'made-by, repeatable' in f['unknownCreate']['message'], f['unknownCreate']['message']
    assert 'declares no component concerns' in f['undeclaredCreate']['message'] and '"schematic"' in f['undeclaredCreate']['message'], f['undeclaredCreate']['message']
    assert 'config.answers.made-by' in f['emptyUpdate']['message'], f['emptyUpdate']['message']
    assert f['knownUpdate']['ok'], f['knownUpdate']
    print('(e) an undeclared key is refused with ANSWER_UNKNOWN on create and update, the document unchanged')
    print('(f) a card answer in a schematic document is refused with ANSWER_UNDECLARED')

    # (g) What loading reports.
    ld = r['load']
    for name in ('empty', 'number', 'list'):
        assert len(ld[name]) == 1 and ld[name][0].startswith('ANSWER_INVALID: meta.answers'), (name, ld[name])
    assert 'meta.answers.what' in ld['empty'][0] and 'meta.answers.what' in ld['number'][0], (ld['empty'], ld['number'])
    assert len(ld['unknown']) == 1 and ld['unknown'][0].startswith('ANSWER_UNKNOWN: meta.answers.nope') and 'what, why, alternatives, smaller' in ld['unknown'][0], ld['unknown']
    assert ld['open'] == [] and ld['none'] == [], ('an open concern is reported as an error', ld['open'], ld['none'])
    assert ld['card'] == [e for e in ld['card'] if e.startswith('component ore: ANSWER_UNKNOWN:')] and len(ld['card']) == 1, ld['card']
    assert len(ld['wire']) == 1 and ld['wire'][0].startswith('wire belt: ANSWER_INVALID: config.answers.carries'), ld['wire']
    assert len(ld['cardUndeclared']) == 1 and ld['cardUndeclared'][0].startswith('component ore: ANSWER_UNDECLARED:'), ld['cardUndeclared']
    assert r['markers'] == ['status'], r['markers']
    print('(g) validateDocument reports ANSWER_INVALID, ANSWER_UNKNOWN and ANSWER_UNDECLARED; an open concern reports nothing')

    # (h) The notation's own entries.
    bad = r['invalid']
    for name, rule, kept in (('noQuestion', 'question must be a non-empty string', ['made-by']), ('blankQuestion', 'question must be a non-empty string', ['made-by']),
                             ('badApplies', 'applies must be', ['made-by']), ('twice', 'used by more than one component concern', ['made-by']),
                             ('unknownKey', 'unit is not a field of a concern', ['made-by']), ('notObject', 'an entry is an object', ['made-by']),
                             ('badTitle', 'title must be a string', ['made-by'])):
        j = bad[name]
        assert j['findings'] and all(x.startswith('CONCERN_INVALID: notation "plant"') for x in j['findings']), (name, j)
        assert j['errors'] == ['notation: ' + x for x in j['findings']], (name, 'validateDocument does not report the findings', j)
        assert any(rule in x for x in j['findings']), (name, 'expected the rule', rule, 'got', j['findings'])
        assert j['component'] == kept and j['document'] == [i for i, _, _ in BUILTIN] and j['wire'] == [], (name, 'admitted', j['component'], j['document'], j['wire'])
        assert j['rows'] == 4 + 2 * len(kept), (name, 'a refused entry is a row', j['rows'])
    assert len(bad['twice']['findings']) == 2 and all('"cost"' in x for x in bad['twice']['findings']), bad['twice']['findings']
    assert len(bad['noQuestion']['findings']) == 1 and 'component concern "cost"' in bad['noQuestion']['findings'][0], bad['noQuestion']['findings']
    assert '"card"' in bad['badApplies']['findings'][0], bad['badApplies']['findings']
    print('(h) CONCERN_INVALID for a missing question, applies card and an id used twice; the entry is not admitted')

    # (l) A component concern names the symbols it is asked of.
    s = r['symbols']
    assert s['errors'] == [] and ['feeds', ['act']] in s['of'], ('a concern with symbols is not admitted', s['errors'], s['of'])
    assert s['feeds'] == [['component', 'ore', 'feeds']], ('a concern with symbols [act] must be a row for the act card ore and none for the hold card bar', s['feeds'])
    assert s['ore'] == ['made-by', 'repeatable', 'feeds'] and s['bar'] == ['made-by', 'repeatable'] and s['total'] == 4 + 3 + 2 + 1, (s['ore'], s['bar'], s['total'])
    for name in ('createHold', 'updateHold', 'verbHold'):
        assert not s[name]['ok'] and s[name]['message'].startswith('ANSWER_UNKNOWN:') and s[name]['unchanged'], (name, 'an answer to a concern not asked of a hold card must be refused with ANSWER_UNKNOWN', s[name])
        assert 'config.answers.feeds' in s[name]['message'] and '"hold"' in s[name]['message'] and 'made-by, repeatable' in s[name]['message'], (name, s[name]['message'])
    for name in ('createAct', 'updateAct', 'verbAct'):
        assert s[name]['ok'], (name, 'an answer to a concern asked of an act card was refused', s[name])
    assert len(s['load']) == 1 and s['load'][0].startswith('component bar: ANSWER_UNKNOWN: config.answers.feeds'), s['load']
    assert ['feeds', None, 'What does this feed?'] in s['joinedOf'] and s['joinedFeeds'] == [['component', 'ore', 'feeds'], ['component', 'bar', 'feeds']], ('a later entry must replace the earlier whole, symbols included', s['joinedOf'], s['joinedFeeds'])
    bad = r['symbolsInvalid']
    for name, rule, entry in (('empty', 'symbols must be a non-empty list', 'component concern "cost"'), ('onDocument', 'symbols belongs to a component concern, not a document concern', 'document concern "scope"'),
                              ('onWire', 'symbols belongs to a component concern, not a wire concern', 'wire concern "load"'), ('repeat', 'symbols names "act" more than once', 'component concern "cost"'),
                              ('notString', 'symbols[1] must be a non-empty string', 'component concern "cost"'), ('blank', 'symbols[1] must be a non-empty string', 'component concern "cost"'),
                              ('notList', 'symbols must be a non-empty list', 'component concern "cost"')):
        j = bad[name]
        assert len(j['findings']) == 1 and j['findings'][0].startswith('CONCERN_INVALID: notation "plant"') and entry in j['findings'][0] and rule in j['findings'][0], (name, 'expected CONCERN_INVALID naming', rule, 'got', j['findings'])
        assert j['errors'] == ['notation: ' + x for x in j['findings']], (name, 'validateDocument does not report the finding', j)
        assert j['component'] == ['made-by'] and j['document'] == [i for i, _, _ in BUILTIN] and j['wire'] == [] and j['rows'] == 4 + 2, (name, 'the entry was admitted', j)
    print('(l) symbols [act]: a row for the act card and none for the hold card; an answer on the hold card is refused with ANSWER_UNKNOWN on create, update and answerConcerns; symbols [] and symbols on a document concern are CONCERN_INVALID')

    # (m) A retype is checked on the record it makes.
    t = r['retype']
    b = t['bare']
    assert not b['ok'] and b['message'].startswith('ANSWER_UNKNOWN:') and b['unchanged'], ('a retype that leaves an answer the new symbol is not asked must be refused with ANSWER_UNKNOWN, the document unchanged', b)
    assert 'config.answers.feeds' in b['message'] and '"hold"' in b['message'] and 'keeps' in b['message'], ('the refusal names the answer and what the new symbol is asked', b['message'])
    assert b['symbol'] == 'act' and b['answers'] == {'feeds': 'The bar.'}, ('a refused retype changed the card', b)
    for name in ('removed', 'allNull'):
        assert t[name]['ok'] and t[name]['symbol'] == 'hold' and t[name]['answers'] is None and t[name]['errors'] == [], (name, 'a retype whose patch removes the answer was refused or left it', t[name])
    sw = t['swapped']
    assert sw['ok'] and sw['symbol'] == 'hold' and sw['answers'] == {'keeps': 'Bars.'} and sw['keeps'] == [[True, 'Bars.']] and sw['errors'] == [], ('a retype that swaps the answers', sw)
    assert t['same']['ok'] and t['same']['answers'] == {'feeds': 'The bar.'}, ('an update that keeps its symbol changed', t['same'])
    assert t['none']['ok'] and t['none']['symbol'] == 'hold' and t['none']['answers'] is None, ('a retype of a card with no answers was refused', t['none'])
    bt = t['batch']
    assert not bt['ok'] and bt['message'].startswith('ANSWER_UNKNOWN:') and bt['index'] == 1 and bt['unchanged'], ('a batch with a refused retype must be refused whole', bt)
    assert t['batchOk'] == {'ok': True, 'label': 'Bar two', 'symbol': 'hold', 'answers': None}, ('a batch whose retype removes the answer', t['batchOk'])
    print('(m) a retype leaving an answer the new symbol is not asked is refused with ANSWER_UNKNOWN, alone and in a batch; the same patch may remove it')

    # (i) Save and open.
    kept = {'meta': {'what': 'An ore line.', 'why': 'To make bars.'}, 'ore': {'made-by': 'Dug from the pit.'}, 'bar': None, 'belt': {'carries': 'Bars, four a minute.'}}
    k = r['kept']
    assert k['saved'] == kept and k['reopened'] == kept and k['compact'] == kept, ('save, open or compact lost an answer', k)
    assert k['report'] == 4, ('the reopened document answers four concerns', k['report'])
    assert r['bare'] == {'saved': False, 'reopened': False, 'compact': False, 'edited': False, 'normalised': False}, ('a document with no answers gained an answers key', r['bare'])
    print('(i) save and open keep meta.answers and config.answers; a document with none has no answers key')

    # (j) The offline validator.
    with tempfile.TemporaryDirectory(prefix='sov-concerns-') as tmp:
        path = Path(tmp) / 'concerns.sov'
        path.write_text(r['source'], encoding='utf-8', newline='\n')
        flagged = subprocess.run(['node', 'scripts/validate_sov.mjs', '--concerns', str(path)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        plainrun = subprocess.run(['node', 'scripts/validate_sov.mjs', str(path)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        # A file that fails prints nothing more, and an open concern does not change the exit code.
        broken = json.loads(r['source'])
        broken['meta']['answers']['nope'] = 'x'
        badpath = Path(tmp) / 'broken.sov'
        badpath.write_text(json.dumps(broken), encoding='utf-8', newline='\n')
        failed = subprocess.run(['node', 'scripts/validate_sov.mjs', '--concerns', str(badpath)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert flagged.returncode == 0, flagged.stdout + flagged.stderr
    lines = flagged.stdout.splitlines()
    opened = [x for x in lines if x.startswith('open')]
    assert lines[0].startswith('ok   ') and len(opened) == 8 and lines[-1] == 'concerns: 1 answered, 8 open', ('the --concerns output', lines)
    assert opened[0] == 'open  document - why: ' + PLANT_WHY and opened[3] == 'open  component ore made-by: What makes this, and from what?' and opened[-1] == 'open  wire belt carries: What moves along this, and how much?', opened
    assert plainrun.returncode == 0 and not any(x.startswith('open') or x.startswith('concerns:') for x in plainrun.stdout.splitlines()), ('without the flag', plainrun.stdout)
    assert len(plainrun.stdout.splitlines()) == 1, plainrun.stdout
    assert failed.returncode == 1 and 'ANSWER_UNKNOWN' in failed.stdout and not any(x.startswith('open') or x.startswith('concerns:') for x in failed.stdout.splitlines()), ('a failed file', failed.stdout)
    print("(j) validate_sov.mjs --concerns: exit 0, 8 open lines, 'concerns: 1 answered, 8 open'; nothing without the flag")

    # (k) The page.
    assert not errors, errors
    print('(k) the page logged no errors')
    print('CONCERNS QA PASS', {'builtin': [x['concern'] for x in plain['rows']], 'rows': len(order), 'validator': lines[-1]})


if __name__ == '__main__':
    main()
