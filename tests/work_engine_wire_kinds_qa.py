"""Work Engine wire kinds QA (NOTATION-MODEL.md "Domain notation: work-engine" and "Kinds").

The Work Engine notation declares five wire kinds, named by what a line means, and the gap map's
wires name four of them.

Node part, over the real src files:
  - data/work-engine.notation.json declares flow, stream, control, reference and proposed in that
    order, each with the dash, weight, arrowhead and open value below;
  - kindFindings of the resolved notation is empty;
  - every wire of docs/workengine/map.sov has a config.kind, and by label: backs is flow, feeds
    tracks is stream, registered by is reference, moves records out of is proposed;
  - node scripts/validate_sov.mjs passes on map.sov and on the three other carriers.

Browser part (index.html in Chromium), with map.sov open:
  - every wire group carries a data-kind equal to the kind of its wire;
  - the proposed wire has a computed dash of 6 4;
  - no reference wire holds a .flow-chevron;
  - every mark on a stream wire has a path ending in Z and a fill other than none;
  - the legend's wire kinds are kind:flow, kind:stream, kind:reference, kind:proposed in that order;
  - the legend sample of a status whose outline is dashed is dashed 6 4, as a kind is.
On a planted document that carries the notation, with two straight wires 300 long, one of kind
control and one of kind stream:
  - the control mark's bounding box is twice the stream mark's in width and in height.
The page logs no errors.
"""
from __future__ import annotations
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

NOTATION = 'data/work-engine.notation.json'
MAP = 'docs/workengine/map.sov'
CARRIERS = [MAP, 'examples/work-engine/notation.sov', 'examples/work-engine/status.sov', 'docs/workengine/board-sample.sov']
KINDS = [
    {'id': 'flow', 'applies': 'wire', 'title': 'Flow', 'meaning': 'Facts are read along it on request.', 'dash': 'solid', 'weight': 'regular', 'arrowhead': 'chevron'},
    {'id': 'stream', 'applies': 'wire', 'title': 'Stream', 'meaning': 'A continuous feed carried as channels.', 'dash': 'solid', 'weight': 'regular', 'arrowhead': 'filled'},
    {'id': 'control', 'applies': 'wire', 'title': 'Control', 'meaning': 'One side governs the other.', 'dash': 'solid', 'weight': 'heavy', 'arrowhead': 'filled'},
    {'id': 'reference', 'applies': 'wire', 'title': 'Reference', 'meaning': 'One side is listed by the other and nothing moves.', 'dash': 'solid', 'weight': 'regular', 'arrowhead': 'none'},
    {'id': 'proposed', 'applies': 'wire', 'title': 'Proposed', 'meaning': 'Planned and not built.', 'dash': 'dashed', 'weight': 'regular', 'arrowhead': 'chevron', 'open': True},
]
# The kind each relation of the map takes, by the label of its wires.
BY_LABEL = {'backs': 'flow', 'feeds tracks': 'stream', 'registered by': 'reference', 'moves records out of': 'proposed'}

NODE = r"""
const fs=require('fs');
const N=require('./src/03-notation-core.js');require('./src/06-attachment-core.js');
const D=require('./src/05-data-core.js');
const out={};
const pack=JSON.parse(fs.readFileSync('%NOTATION%','utf8'));
out.kinds=Array.isArray(pack.kinds)?pack.kinds:null;
out.keys=Object.keys(pack);
const doc=JSON.parse(fs.readFileSync('%MAP%','utf8'));
const r=N.resolve(doc);out.ok=r.ok;out.code=r.code||null;
out.findings=r.ok?N.kindFindings(r.notation):null;
out.admitted=r.ok?N.kindsOf(r.notation,'wire').map(k=>k.id):null;
out.wires=(doc.wires||[]).map(w=>[w.id,w.config?.label??null,w.config?.kind??null]);
out.valid=D.validateDocument(D.makeDocument(doc)).errors;
console.log(JSON.stringify(out));
""".replace('%NOTATION%', NOTATION).replace('%MAP%', MAP)

PAGE_MAP = r"""()=>{
  const A=window.SovSchematicAPI,out={};
  const wires=A.file.document().wires,kindOf=Object.fromEntries(wires.map(w=>[w.id,w.config?.kind??null]));
  const groups=[...document.querySelectorAll('.wire-group')];
  out.wires=wires.length;out.groups=groups.length;
  out.wrong=groups.filter(g=>!(g.dataset.wireId in kindOf)||(g.dataset.kind??null)!==kindOf[g.dataset.wireId]||!g.dataset.kind).map(g=>[g.dataset.wireId??null,g.dataset.kind??null]);
  out.drawn={};for(const g of groups)out.drawn[g.dataset.kind]=(out.drawn[g.dataset.kind]||0)+1;
  const of=kind=>groups.filter(g=>g.dataset.kind===kind);
  out.proposed=of('proposed').map(g=>{const p=g.querySelector('path.wire');return [getComputedStyle(p).strokeDasharray,p.getAttribute('stroke-dasharray')]});
  out.referenceMarks=of('reference').reduce((n,g)=>n+g.querySelectorAll('.flow-chevron').length,0);
  out.streamMarks=of('stream').flatMap(g=>[...g.querySelectorAll('.flow-chevron')].map(m=>[m.getAttribute('d'),getComputedStyle(m).fill]));
  out.flowMarks=of('flow').flatMap(g=>[...g.querySelectorAll('.flow-chevron')].map(m=>[m.getAttribute('d'),getComputedStyle(m).fill]));
  const entries=A.view.legend().entries;
  out.legend=entries.filter(e=>e.kind==='wire-kind').map(e=>e.id);
  out.statusSamples=entries.filter(e=>e.kind==='status'&&e.sample?.outline==='dashed').map(e=>[e.id,legendSampleMarkup(e)]);
  out.solidSamples=entries.filter(e=>e.kind==='status'&&e.sample?.outline!=='dashed').map(e=>[e.id,legendSampleMarkup(e)]);
  return out;
}"""

PAGE_PLANTED = r"""(pack)=>{
  const A=window.SovSchematicAPI,D=SovSchematicData,out={};
  const names=['control','stream'];
  const doc=dx=>({schema:D.DOCUMENT_SCHEMA,id:'work-engine-wire-kinds',notation:'work-engine',
    components:names.flatMap((k,i)=>[
      {id:'a'+i,symbolId:'act',x:200,y:120+i*150,config:{label:'From '+k}},
      {id:'b'+i,symbolId:'act',x:200+dx,y:120+i*150,config:{label:'To '+k}}]),
    wires:names.map((k,i)=>({id:'w-'+k,a:'a'+i,aSide:'out',b:'b'+i,bSide:'in',config:{kind:k}})),
    references:[{id:'notation-work-engine',kind:'notation',label:'Work Engine',data:pack}]});
  // Place the cards so both wires are 300 long.
  const lengthOf=()=>document.querySelector('.wire-group[data-wire-id="w-stream"] path.wire').getTotalLength();
  let dx=500;A.document.replace(doc(dx));dx+=300-lengthOf();A.document.replace(doc(dx));fitDiagram();
  out.markers=A.markers();
  for(const k of names){
    const g=document.querySelector(`.wire-group[data-wire-id="w-${k}"]`),p=g.querySelector('path.wire'),marks=[...g.querySelectorAll('.flow-chevron')];
    const box=marks[0]?.getBBox();
    out[k]={length:p.getTotalLength(),segments:(p.getAttribute('d').match(/[LHV]/g)||[]).length,kind:g.dataset.kind??null,width:parseFloat(getComputedStyle(p).strokeWidth),
      marks:marks.length,d:marks[0]?.getAttribute('d')||null,fill:marks[0]?getComputedStyle(marks[0]).fill:null,box:box?[box.width,box.height]:null};
  }
  return out;
}"""


def dash_of(value) -> str:
    """A computed or inlined stroke-dasharray as plain numbers: '6px, 4px' reads '6 4'."""
    return ' '.join((value or 'none').replace('px', '').replace(',', ' ').split())


def main() -> None:
    # ---- Node part ---------------------------------------------------------------------------
    proc = subprocess.run(['node', '-e', NODE], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert proc.returncode == 0, proc.stderr
    n = json.loads(proc.stdout)
    assert n['kinds'] is not None and [k.get('id') for k in n['kinds']] == [k['id'] for k in KINDS], ('the notation does not declare flow, stream, control, reference, proposed in that order', n['kinds'])
    assert n['kinds'] == KINDS, ('a kind differs in applies, title, meaning, dash, weight, arrowhead or open', n['kinds'])
    assert all(k['meaning'].endswith('.') for k in n['kinds']), ('a meaning does not end with a full stop', n['kinds'])
    assert n['keys'].index('kinds') == n['keys'].index('statuses') + 1 == n['keys'].index('concerns') - 1, ('kinds does not sit after statuses and before concerns', n['keys'])
    assert n['ok'], ('the notation the map carries must resolve', n['code'])
    assert n['findings'] == [], ('the resolved notation has kind findings', n['findings'])
    assert n['admitted'] == ['reference'] + [k['id'] for k in KINDS if k['id'] != 'reference'],('a declared wire kind is not admitted', n['admitted'])
    assert n['valid'] == [], n['valid']
    assert n['wires'], 'the map has no wires'
    unnamed = [w for w in n['wires'] if not w[2]]
    assert not unnamed, ('a wire of the map names no kind', unnamed)
    wrong = [w for w in n['wires'] if BY_LABEL.get(w[1]) != w[2]]
    assert not wrong, ('a wire of the map names another kind than its relation takes', wrong)
    counts = Counter(w[2] for w in n['wires'])
    assert set(counts) == set(BY_LABEL.values()), ('the map does not use flow, stream, reference and proposed', dict(counts))
    assert 'control' not in counts, ('a wire of the map is heavy', dict(counts))
    for path in CARRIERS:
        v = subprocess.run(['node', 'scripts/validate_sov.mjs', path], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        assert v.returncode == 0, (path, v.stdout, v.stderr)
    per_kind = {k['id']: counts.get(k['id'], 0) for k in KINDS}
    print('node part: wires per kind on the map', per_kind, 'of', len(n['wires']))

    # ---- Browser part ------------------------------------------------------------------------
    pack = json.loads((ROOT / NOTATION).read_text(encoding='utf-8'))
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(250)
        page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [(ROOT / MAP).read_text(encoding='utf-8'), 'map.sov'])
        page.wait_for_timeout(600)
        m = page.evaluate(PAGE_MAP)
        d = page.evaluate(PAGE_PLANTED, pack)
        browser.close()
    assert not errors, errors

    # The map.
    assert m['groups'] == m['wires'] == len(n['wires']), ('a wire of the map has no group', m['groups'], m['wires'], len(n['wires']))
    assert not m['wrong'], ('a wire group does not carry the kind of its wire', m['wrong'])
    assert m['drawn'] == {k: c for k, c in per_kind.items() if c}, ('the kinds drawn differ from the kinds named', m['drawn'], per_kind)
    assert len(m['proposed']) == 1 and all(dash_of(c) == '6 4' and a == '6 4' for c, a in m['proposed']), ('the proposed wire is not dashed 6 4', m['proposed'])
    assert m['referenceMarks'] == 0, ('a reference wire holds a direction mark', m['referenceMarks'])
    assert m['streamMarks'], 'no stream wire carries a mark'
    assert all(path.endswith('Z') and fill not in (None, '', 'none') for path, fill in m['streamMarks']), ('a mark on a stream wire is not filled', m['streamMarks'])
    assert m['flowMarks'] and all(not path.endswith('Z') and fill == 'none' for path, fill in m['flowMarks']), ('a mark on a flow wire is filled', m['flowMarks'][:4])
    assert m['legend'] == ['kind:reference', 'kind:flow', 'kind:stream', 'kind:proposed'], ('the legend lists other wire kinds', m['legend'])
    assert m['statusSamples'], 'the legend lists no status with a dashed outline'
    assert all('stroke-dasharray:6 4' in markup for _, markup in m['statusSamples']), ('a dashed status sample is not dashed 6 4', m['statusSamples'])
    assert all('stroke-dasharray' not in markup for _, markup in m['solidSamples']), ('a solid status sample is dashed', m['solidSamples'])

    # The planted document: a filled mark is twice the size on a heavy wire.
    assert not d['markers'], ('the planted document has markers', d['markers'])
    for kind in ('control', 'stream'):
        one = d[kind]
        assert abs(one['length'] - 300) < .5 and one['segments'] == 1 and one['kind'] == kind, ('a planted wire is not straight, 300 long and of its kind', kind, one)
        assert one['marks'] == 1 and one['d'].endswith('Z') and one['fill'] not in (None, '', 'none'), ('a planted wire does not carry one filled mark', kind, one)
    assert abs(d['control']['width'] - 2 * d['stream']['width']) < 1e-6, ('control is not twice as wide as stream', d['control']['width'], d['stream']['width'])
    (cw, ch), (sw, sh) = d['control']['box'], d['stream']['box']
    assert sw > 0 and sh > 0, ('the stream mark has no size', d['stream'])
    assert abs(cw / sw - 2) < .01 and abs(ch / sh - 2) < .01, ('the control mark is not twice the stream mark', (cw, ch), (sw, sh))

    print('WORK ENGINE WIRE KINDS QA PASS', {'wires per kind': per_kind, 'legend': m['legend'], 'stream marks': len(m['streamMarks']),
                                             'stream mark': [sw, sh], 'control mark': [cw, ch]})


if __name__ == '__main__':
    main()
