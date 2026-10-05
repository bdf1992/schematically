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
      with answers null removes the key; a wire's answer is admitted the same way;
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
