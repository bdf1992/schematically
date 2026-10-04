"""Wire kind QA (NOTATION-MODEL.md "Kinds"; DATA-FORMATS.md "A Wire's kind").

A notation declares kinds in one list, for wires (dash, weight, arrowhead) and for regions (the border
a region draws). A Wire names a wire kind in config.kind and is drawn in it; dashed is reserved for a
kind that is open.

Browser part (index.html in Chromium), on a document whose carried notation extends schematic and
declares four wire kinds: flow (solid, regular, chevron), control (solid, heavy, filled), reference
(solid, regular, none) and proposed (dashed, regular, chevron, open). Five straight wires 300 long,
one per kind and one with no kind:
  - flow, control, reference and the wire with no kind have no stroke-dasharray; proposed has 6 4;
  - control's base path is twice as wide as flow's; the others are as wide as flow's;
  - reference has no .flow-chevron and each other wire has one; control's mark has a fill, flow's none;
  - each wire group carries its data-kind;
  - config.kind 'missing-kind' is refused with KIND_UNKNOWN (create and update), the document unchanged;
  - on a document whose notation is schematic a config.kind is refused with KIND_UNDECLARED;
  - a carried notation with a dashed kind that lacks open true, and one with two kinds both solid,
    regular and chevron, each report KIND_INVALID and do not admit the entry;
  - the resolved notation's region kinds are group, plane, container, gate and intake with dash none,
    solid, solid, solid and dashed;
  - the legend lists the four kinds in use, and not one no wire names;
  - saving and opening keeps every config.kind;
  - the picture from renderStandaloneSvg carries the 6 4 dash and the doubled width;
  - node scripts/validate_sov.mjs passes on the document;
  - the page logs no errors.
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

KINDS = [
    {'id': 'flow', 'applies': 'wire', 'title': 'Flow', 'meaning': 'Work moves along it.', 'dash': 'solid', 'weight': 'regular', 'arrowhead': 'chevron'},
    {'id': 'control', 'applies': 'wire', 'title': 'Control', 'meaning': 'One side decides for the other.', 'dash': 'solid', 'weight': 'heavy', 'arrowhead': 'filled'},
    {'id': 'reference', 'applies': 'wire', 'title': 'Reference', 'meaning': 'One side names the other.', 'dash': 'solid', 'weight': 'regular', 'arrowhead': 'none'},
    {'id': 'proposed', 'applies': 'wire', 'title': 'Proposed', 'meaning': 'Planned, not built.', 'dash': 'dashed', 'weight': 'regular', 'arrowhead': 'chevron', 'open': True},
]
WIRES = ['flow', 'control', 'reference', 'proposed', None]  # the kind each wire names; the last names none


def wire_id(kind):
    return 'w-' + (kind or 'plain')


PAGE = r"""([kinds,names])=>{
  const A=window.SovSchematicAPI,D=SovSchematicData,N=SovSchematicNotation,out={};
  const wid=k=>'w-'+(k||'plain');
  const notation=(list,id='kinds-test')=>({id:'notation-'+id,kind:'notation',label:'Kinds test',data:{id,name:'Kinds test',version:1,extends:'schematic',kinds:list}});
  const doc=(dx,list=kinds,carried=true)=>({schema:D.DOCUMENT_SCHEMA,id:'wire-kinds',...(carried?{notation:'kinds-test'}:{}),
    components:names.flatMap((k,i)=>[
      {id:'a'+i,symbolId:'act',x:200,y:120+i*150,config:{label:'From '+(k||'plain')}},
      {id:'b'+i,symbolId:'act',x:200+dx,y:120+i*150,config:{label:'To '+(k||'plain')}}]),
    wires:names.map((k,i)=>({id:wid(k),a:'a'+i,aSide:'out',b:'b'+i,bSide:'in',config:k?{kind:k}:{}})),
    references:carried?[notation(list)]:[]});
  // Place the cards so every wire is 300 long.
  const lengthOf=()=>document.querySelector('.wire-group[data-wire-id="w-flow"] path.wire').getTotalLength();
  let dx=500;A.document.replace(doc(dx));dx+=300-lengthOf();A.document.replace(doc(dx));fitDiagram();
  out.dx=dx;out.source=JSON.stringify(doc(dx));
  out.wires={};
  for(const k of names){
    const g=document.querySelector(`.wire-group[data-wire-id="${wid(k)}"]`),p=g.querySelector('path.wire'),cs=getComputedStyle(p),marks=[...g.querySelectorAll('.flow-chevron')];
    out.wires[wid(k)]={length:p.getTotalLength(),segments:(p.getAttribute('d').match(/[LHV]/g)||[]).length,dash:cs.strokeDasharray,dashAttr:p.getAttribute('stroke-dasharray'),
      width:parseFloat(cs.strokeWidth),kind:g.dataset.kind??null,marks:marks.length,markFill:marks[0]?getComputedStyle(marks[0]).fill:null,markD:marks[0]?.getAttribute('d')||null};
  }
  out.flowToken=N.tokens(D.makeDocument(doc(dx))).stroke.flow;
  out.legend=A.view.legend().entries.filter(e=>e.kind==='wire-kind').map(e=>({id:e.id,label:e.label,meaning:e.meaning,sample:e.sample}));
  out.regions=N.kindsOf(N.resolve(D.makeDocument(doc(dx))).notation,'region').map(k=>[k.id,k.dash]);
  out.markers=A.markers();
  // The picture: each wire's inlined style, read back from the SVG text.
  {const svg=A.render.svg({}),parsed=new DOMParser().parseFromString(svg,'image/svg+xml');out.picture={};
   for(const k of names){const p=parsed.querySelector(`.wire-group[data-wire-id="${wid(k)}"] path.wire`),style=p?.getAttribute('style')||'';
     out.picture[wid(k)]={found:!!p,width:parseFloat((/(?:^|;)stroke-width:([\d.]+)/.exec(style)||[])[1]),dash:(/(?:^|;)stroke-dasharray:([^;]+)/.exec(style)||[])[1]||null,dashAttr:p?.getAttribute('stroke-dasharray')||null}}
   out.pictureFilled=!!parsed.querySelector('.wire-group[data-kind="control"] .flow-chevron[d$="Z"]')}
  // Save and open keeps every kind.
  {const saved=JSON.stringify(A.file.document());A.file.open(saved,'wire-kinds.sov');
   out.reopened=Object.fromEntries(A.file.document().wires.map(w=>[w.id,w.config?.kind??null]));
   out.reopenedDrawn=Object.fromEntries([...document.querySelectorAll('.wire-group')].map(g=>[g.dataset.wireId,g.dataset.kind??null]))}
  // The legend drops a kind no wire names any more.
  {const r=A.update('wire','w-proposed',{config:{kind:null}});out.cleared={ok:r.ok,key:'kind' in (A.file.document().wires.find(w=>w.id==='w-proposed').config||{}),
     legend:A.view.legend().entries.filter(e=>e.kind==='wire-kind').map(e=>e.id),dash:getComputedStyle(document.querySelector('.wire-group[data-wire-id="w-proposed"] path.wire')).strokeDasharray}}
  // Refusals leave the document unchanged.
  const refuse=(base,op)=>{const d=D.makeDocument(base);D.normalizeDocument(d);const before=JSON.stringify(d);const r=D.applyOperation(d,op);return {ok:r.ok,message:r.error?.message||'',unchanged:JSON.stringify(d)===before}};
  const back=kind=>({id:'back',a:'b0',aSide:'out',b:'a0',bSide:'in',config:{kind}});
  out.refusals={
    unknownUpdate:refuse(doc(dx),{op:'update',resource:'wire',resourceId:'w-plain',patch:{config:{kind:'missing-kind'}}}),
    unknownCreate:refuse(doc(dx),{op:'create',resource:'wire',value:back('missing-kind')}),
    undeclaredUpdate:refuse(doc(dx,kinds,false),{op:'update',resource:'wire',resourceId:'w-plain',patch:{config:{kind:'flow'}}}),
    undeclaredCreate:refuse(doc(dx,kinds,false),{op:'create',resource:'wire',value:back('flow')}),
    knownUpdate:refuse(doc(dx),{op:'update',resource:'wire',resourceId:'w-plain',patch:{config:{kind:'control'}}}),
  };
  {const raw=doc(dx);raw.wires[4].config.kind='missing-kind';out.loadUnknown=D.validateDocument(D.makeDocument(raw)).errors;
   const plain=doc(dx,kinds,false);out.loadUndeclared=D.validateDocument(D.makeDocument(plain)).errors}
  // A notation whose own entries break a rule: reported, and the entry is not admitted.
  const judge=list=>{const d=D.makeDocument(doc(dx,list)),r=N.resolve(d);return {errors:D.validateDocument(d).errors.filter(e=>/KIND_INVALID/.test(e)),findings:N.kindFindings(r.notation),admitted:N.kindsOf(r.notation,'wire').map(k=>k.id),regions:N.kindsOf(r.notation,'region').length}};
  out.invalid={
    dashedNotOpen:judge([kinds[0],{id:'maybe',applies:'wire',dash:'dashed'}]),
    openNotDashed:judge([kinds[0],{id:'maybe',applies:'wire',dash:'solid',weight:'heavy',open:true}]),
    twins:judge([{id:'one',applies:'wire',dash:'solid',weight:'regular',arrowhead:'chevron'},{id:'two',applies:'wire',dash:'solid'},kinds[1]]),
    regionWeight:judge([kinds[0],{id:'zone',applies:'region',dash:'solid',weight:'heavy'}]),
    wireNone:judge([kinds[0],{id:'ghost',applies:'wire',dash:'none',weight:'heavy'}]),
    unknownKey:judge([kinds[0],{id:'odd',applies:'wire',dash:'solid',weight:'heavy',colour:'red'}]),
    dotted:judge([kinds[0],{id:'dots',applies:'wire',dash:'dotted',weight:'heavy'}]),
    twice:judge([kinds[0],{id:'flow',applies:'wire',dash:'solid',weight:'heavy'}]),
  };
  return out;
}"""


def dash_of(value) -> str:
    """A computed or inlined stroke-dasharray as plain numbers: '6px, 4px' reads '6 4'."""
    return ' '.join((value or 'none').replace('px', '').replace(',', ' ').split())


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(200)
        r = page.evaluate(PAGE, [KINDS, WIRES])
        browser.close()
    assert not errors, errors

    w = r['wires']
    for kind in WIRES:
        one = w[wire_id(kind)]
        assert abs(one['length'] - 300) < .5 and one['segments'] == 1, ('a wire is not straight and 300 long', kind, one)
        assert one['kind'] == kind, ('the wire group does not carry its data-kind', kind, one['kind'])
    assert not r['markers'], ('the document has markers', r['markers'])

    # Dash: only the open kind is dashed, 6 4.
    for kind in ('flow', 'control', 'reference', None):
        one = w[wire_id(kind)]
        assert dash_of(one['dash']) == 'none' and one['dashAttr'] is None, ('a wire that is not open is dashed', kind, one)
    assert dash_of(w['w-proposed']['dash']) == '6 4' and w['w-proposed']['dashAttr'] == '6 4', ('the open kind is not dashed 6 4', w['w-proposed'])

    # Weight: heavy is twice the flow stroke; every other wire is the flow stroke.
    flow = w['w-flow']['width']
    assert abs(flow - r['flowToken']) < 1e-6, ('a regular wire is not tokens.stroke.flow wide', flow, r['flowToken'])
    assert abs(w['w-control']['width'] - 2 * flow) < 1e-6, ('a heavy wire is not twice as wide as a regular one', w['w-control']['width'], flow)
    for kind in ('reference', 'proposed', None):
        assert abs(w[wire_id(kind)]['width'] - flow) < 1e-6, ('a regular wire differs from flow in width', kind, w[wire_id(kind)]['width'], flow)

    # Arrowhead: none draws no mark, filled a filled one, chevron the open one.
    assert w['w-reference']['marks'] == 0, ('arrowhead none still draws a mark', w['w-reference'])
    for kind in ('flow', 'control', 'proposed', None):
        assert w[wire_id(kind)]['marks'] == 1, ('a 300 wire carries one mark', kind, w[wire_id(kind)]['marks'])
    assert w['w-control']['markFill'] not in (None, 'none') and w['w-control']['markD'].endswith('Z'), ('a filled arrowhead has no fill', w['w-control'])
    for kind in ('flow', 'proposed', None):
        one = w[wire_id(kind)]
        assert one['markFill'] == 'none' and not one['markD'].endswith('Z'), ('a chevron is filled', kind, one)

    # Refusals.
    f = r['refusals']
    for name, code in (('unknownUpdate', 'KIND_UNKNOWN'), ('unknownCreate', 'KIND_UNKNOWN'), ('undeclaredUpdate', 'KIND_UNDECLARED'), ('undeclaredCreate', 'KIND_UNDECLARED')):
        assert not f[name]['ok'] and f[name]['message'].startswith(code + ':') and f[name]['unchanged'], (name, f[name])
    assert 'flow, control, reference, proposed' in f['unknownUpdate']['message'], f['unknownUpdate']['message']
    assert f['knownUpdate']['ok'], f['knownUpdate']
    assert len(r['loadUnknown']) == 1 and r['loadUnknown'][0].startswith('wire w-plain: KIND_UNKNOWN:'), r['loadUnknown']
    assert len(r['loadUndeclared']) == 4 and all('KIND_UNDECLARED' in e for e in r['loadUndeclared']), r['loadUndeclared']

    # The notation's own entries.
    bad = r['invalid']
    for name, dropped, kept in (('dashedNotOpen', ['maybe'], ['flow']), ('openNotDashed', ['maybe'], ['flow']), ('twins', ['one', 'two'], ['control']),
                                ('wireNone', ['ghost'], ['flow']), ('unknownKey', ['odd'], ['flow']), ('dotted', ['dots'], ['flow']), ('twice', ['flow'], [])):
        j = bad[name]
        assert j['errors'] and j['findings'] and all(x.startswith('KIND_INVALID: notation "kinds-test"') for x in j['findings']), (name, j)
        assert all(e.startswith('notation: KIND_INVALID:') for e in j['errors']) and len(j['errors']) == len(j['findings']), (name, j)
        assert j['admitted'] == kept, (name, 'admitted', j['admitted'], 'expected', kept)
        assert all(any(f'"{d}"' in x for x in j['findings']) for d in dropped), (name, j['findings'])
        assert j['regions'] == 5, (name, 'a wire finding dropped a region kind', j['regions'])
    assert 'open true' in bad['dashedNotOpen']['findings'][0], bad['dashedNotOpen']['findings']
    assert 'weight or arrowhead' in bad['twins']['findings'][0], bad['twins']['findings']
    z = bad['regionWeight']
    assert z['errors'] and 'region kind "zone"' in z['findings'][0] and z['regions'] == 5 and z['admitted'] == ['flow'], z

    # Region kinds: declared in the schematic notation, joined through extends.
    assert r['regions'] == [['group', 'none'], ['plane', 'solid'], ['container', 'solid'], ['gate', 'solid'], ['intake', 'dashed']], r['regions']

    # Legend: the kinds in use, in declared order; not one no wire names.
    assert [e['id'] for e in r['legend']] == ['kind:flow', 'kind:control', 'kind:reference', 'kind:proposed'], r['legend']
    assert [e['label'] for e in r['legend']] == ['Flow', 'Control', 'Reference', 'Proposed'] and all(e['meaning'] for e in r['legend']), r['legend']
    c = r['cleared']
    assert c['ok'] and not c['key'] and c['legend'] == ['kind:flow', 'kind:control', 'kind:reference'], ('the legend lists a kind no wire names', c)
    assert dash_of(c['dash']) == 'none', ('a wire whose kind was removed is still dashed', c)

    # Save and open.
    expect = {wire_id(k): k for k in WIRES}
    assert r['reopened'] == expect and r['reopenedDrawn'] == expect, ('save and open lost a kind', r['reopened'], r['reopenedDrawn'])

    # The picture.
    pic = r['picture']
    assert all(v['found'] for v in pic.values()), pic
    assert dash_of(pic['w-proposed']['dash']) == '6 4' and pic['w-proposed']['dashAttr'] == '6 4', ('the picture lost the 6 4 dash', pic['w-proposed'])
    assert abs(pic['w-control']['width'] - 2 * pic['w-flow']['width']) < 1e-6, ('the picture lost the doubled width', pic['w-control'], pic['w-flow'])
    assert pic['w-flow']['dash'] in (None, 'none') and r['pictureFilled'], ('the picture', pic['w-flow'], r['pictureFilled'])

    # The same document through the offline validator.
    with tempfile.TemporaryDirectory(prefix='sov-wire-kind-') as tmp:
        path = Path(tmp) / 'wire-kinds.sov'
        path.write_text(r['source'], encoding='utf-8', newline='\n')
        proc = subprocess.run(['node', 'scripts/validate_sov.mjs', str(path)], cwd=ROOT, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout + proc.stderr

    print('WIRE KIND QA PASS', {'flow': flow, 'control': w['w-control']['width'], 'proposed': dash_of(w['w-proposed']['dash']),
                                'marks': {k or 'plain': w[wire_id(k)]['marks'] for k in WIRES}, 'legend': [e['id'] for e in r['legend']]})


if __name__ == '__main__':
    main()
