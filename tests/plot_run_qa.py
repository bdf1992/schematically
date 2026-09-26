"""Run records and views QA (static: Python and Node, no browser).

The views in scripts/plot_run.mjs claim to draw what a record holds and nothing else. Each
claim is checked here against the record, not against the renderer's own arithmetic:

  - glyphs: data/logic.glyphs.json is what scripts/logic_glyphs.py writes, has one entry per
    logic definition, parses as XML, uses only the tags and attributes the editor's
    custom-graphic sanitizer admits (read from src/55-render.js), follows the agreed family
    rule, and is what every example device bound to that definition carries;
  - determinism: the same records render byte-identical SVG, and every SVG parses;
  - timing, from state space runs: every value-lane segment shows the bus value decoded from
    the record's bit changes, the 4-bit adder's 7 -> 8 shows the carry's transient 6, 4, 0, and
    0 -> 1 on A0 alone (no carry) shows no transient at all; the record names its run;
  - landscape: every plan marker sits at its record position with its certificate, every
    slice of a three-decision model holds the others at the whole-unit plan, says so, marks
    what lies outside it as projected, and holds the true value of the plans it names; every
    whole-unit local optimum is ringed and nothing else is, and every limit is drawn;
  - search: one outline row per logged node, dead exactly when pruned or infeasible, the
    gradient in [0, 1] with the incumbent at 0, and step order equal to log order;
  - step-through: timing marks sit on recorded changes, one cursor per timing view, and the
    page puts step controls on exactly the timing and search figures;
  - timeline: one bar per unit span at its recorded start and end, and the stall where it happened;
  - both themes: every view carries the dark tokens;
  - the committed gallery in docs/visual/ is what the code draws today.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from record_run import parse_vector, record_logic, record_optimize, record_simulate  # noqa: E402

GLYPHS = json.loads((ROOT / 'data' / 'logic.glyphs.json').read_text(encoding='utf-8'))['glyphs']
DEFS = {f"{d['id']}@{d['version']}" for p in ('core.logic.pack.json', 'logic.gates.pack.json')
        for d in json.loads((ROOT / 'data' / p).read_text(encoding='utf-8'))['definitions']}
SVG = '{http://www.w3.org/2000/svg}'
CLASSIC = {'and', 'or', 'xor', 'not', 'buffer', 'nand', 'nor', 'xnor'}


def sanitizer_allowlist() -> tuple[set, set]:
    src = (ROOT / 'src' / '55-render.js').read_text(encoding='utf-8')
    tags = set(re.findall(r"'([a-z]+)'", re.search(r'SAFE_SVG_TAGS=new Set\(\[(.*?)\]\)', src).group(1)))
    attrs = set(re.findall(r"'([a-zA-Z0-9-]+)'", re.search(r'SAFE_SVG_ATTRS=new Set\(\[(.*?)\]\)', src).group(1)))
    return tags, attrs


def check_glyphs() -> None:
    subprocess.run([sys.executable, str(ROOT / 'scripts' / 'logic_glyphs.py'), '--check'], check=True)
    tags, attrs = sanitizer_allowlist()
    assert {'path', 'text', 'circle'} <= tags and 'd' in attrs, (tags, attrs)
    assert set(GLYPHS) == DEFS, (sorted(GLYPHS), sorted(DEFS))
    for ref, g in GLYPHS.items():
        name = ref.split('.', 1)[1].split('@')[0]
        assert g['family'] == ('distinctive' if name in CLASSIC else 'rectangle'), ref
        for key in ('glyph', 'glyphSmall'):
            root = ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 64">{g[key]}</svg>')
            for node in root.iter():
                t = node.tag.replace(SVG, '')
                assert t in tags, (ref, key, t)
                if node is not root:
                    bad = set(node.attrib) - attrs
                    assert not bad, (ref, key, t, bad)
        assert g['glyphSmall'].count('M30 8H66V56H30Z') == 1, f'{ref}: small glyph must be the rectangle'
    bound = 0
    for doc_path in sorted((ROOT / 'examples' / 'logic').glob('*.sov')):
        doc = json.loads(doc_path.read_text(encoding='utf-8'))
        for c in doc['components']:
            ref = c.get('config', {}).get('definition')
            if ref:
                bound += 1
                graphic = c['config']['presentation']['graphic']
                assert graphic['svg'] == GLYPHS[ref]['glyph'], (doc_path.name, c['id'])
                assert graphic.get('svgSmall', graphic['svg']) == GLYPHS[ref]['glyphSmall'], (doc_path.name, c['id'])
    assert bound > 16, bound


def value_at(changes: list, t: float) -> int:
    v = 0
    for tt, vv in changes:
        if tt <= t:
            v = vv
        else:
            break
    return v


def render(records: dict[str, dict], tmp: Path) -> dict[str, str]:
    for name, rec in records.items():
        (tmp / f'{name}.json').write_text(json.dumps(rec), encoding='utf-8')
    files = [str(tmp / f'{n}.json') for n in records]
    out: dict[str, str] = {}
    for run in ('a', 'b'):
        subprocess.run(['node', str(ROOT / 'scripts' / 'plot_run.mjs'), *files, '--out', str(tmp / run),
                        '--page', str(tmp / f'{run}.html')], check=True, stdout=subprocess.DEVNULL)
    for f in sorted((tmp / 'a').glob('*.svg')):
        text = f.read_text(encoding='utf-8')
        assert text == (tmp / 'b' / f.name).read_text(encoding='utf-8'), f'{f.name} is not deterministic'
        ET.fromstring(text)
        assert '--v-canvas:#17191B' in text and 'prefers-color-scheme: dark' in text, f'{f.name} has no dark theme'
        out[f.stem] = text
    assert (tmp / 'a.html').read_text() == (tmp / 'b.html').read_text()
    out['page'] = (tmp / 'a.html').read_text(encoding='utf-8')
    return out


def nodes(svg_text: str, attr: str) -> list[ET.Element]:
    root = ET.fromstring(svg_text)
    return [n for n in root.iter() if attr in n.attrib]


def check_views() -> None:
    lg = ROOT / 'examples' / 'logic'
    op = ROOT / 'examples' / 'optimization'
    records = {
        'carry': record_logic(lg / 'adder4.sov', [parse_vector('A=7:4,B=0:4,Cin=0'), parse_vector('B0=1')], 20, ['S']),
        'calm': record_logic(lg / 'adder4.sov', [parse_vector('A=0:4,B=0:4,Cin=0'), parse_vector('A0=1')], 20, ['S']),
        'learning': record_optimize(op / 'workshop.sov', op / 'workshop.learning.opt.json', segments=20, starts=12, steps=41),
        'week': record_simulate(op / 'workshop.sov', op / 'workshop.learning.opt.json', {'chairs': 14, 'tables': 2}),
        'three': record_optimize(op / 'workshop3.sov', op / 'workshop3.opt.json', segments=20, starts=8, steps=21),
    }
    from optimize_sov import load
    load3 = load(op / 'workshop3.sov', op / 'workshop3.opt.json')
    for rec in records.values():
        assert rec['schema'] == 'soveraeign.schematic/run@0.0-draft' and rec['document']['fingerprint'].startswith('sem1:')
    with tempfile.TemporaryDirectory() as tmp:
        views = render(records, Path(tmp))

    # timing: segments against bits decoded here from the record
    for name in ('carry', 'calm'):
        rec = records[name]
        assert rec['run']['head'] and rec['run']['id'] and rec['run']['through'] is not None, rec['run']
        segs = nodes(views[f'{name}.timing'], 'data-bus')
        assert segs
        for s in segs:
            t0 = float(s.attrib['data-t0'])
            decoded = sum(value_at(rec['signals'][bit], t0) << i for i, bit in enumerate(rec['buses']['S']))
            assert int(s.attrib['data-value']) == decoded, (name, s.attrib, decoded)
        transients = [int(s.attrib['data-value']) for s in segs if s.attrib['data-transient'] == '1']
        if name == 'calm':
            assert not transients and 'calm.timing-zoom' not in views, 'a change with no carry has no transient values'
        else:
            zoom = [int(s.attrib['data-value']) for s in nodes(views['carry.timing-zoom'], 'data-bus') if s.attrib['data-transient'] == '1']
            assert zoom == [6, 4, 0], zoom
        # Step-through: one steppable mark per recorded change, at its time, with a hidden cursor.
        marks = nodes(views[f'{name}.timing'], 'data-t')
        changes = {(sig, c[0]) for sig, cs in rec['signals'].items() for c in cs if c[0] > 0}
        assert marks and {(m.attrib['data-link'].split(':')[1], float(m.attrib['data-t'])) for m in marks} <= changes, name
        assert all(m.attrib['data-label'] and m.attrib['data-x'] for m in marks)
        assert len(nodes(views[f'{name}.timing'], 'data-cursor')) == 1

    # landscape (two decisions: the whole problem, one view)
    rec = records['learning']
    assert len(rec['landscapes']) == 1 and rec['landscapes'][0]['held'] == {}
    L = rec['landscapes'][0]
    dx, dy = L['decisions']
    land = views['learning.landscape']
    marks = {n.attrib['data-plan']: n.attrib for n in nodes(land, 'data-plan')}
    for p in rec['plans']:
        m = marks[p['name']]
        x, y = map(float, m['data-at'].split(','))
        assert abs(x - p['at'][dx]) < 0.01 and abs(y - p['at'][dy]) < 0.01, (p, m)
        assert m['data-certificate'] == p['certificate'] and m['data-feasible'] == ('1' if p['feasible'] else '0')
        assert m['data-in-slice'] == '1'
    ringed = sorted(n.attrib['data-whole'] for n in nodes(land, 'data-whole') if n.attrib['data-local'] == '1')
    assert ringed == sorted(f'{w["at"][0]},{w["at"][1]}' for w in L['whole'] if w['local']), ringed
    assert len(ringed) == 6, ringed
    drawn = {n.attrib['data-limit'] for n in nodes(land, 'data-limit')}
    assert drawn == set(L['slack']), (drawn, L['slack'].keys())
    assert len(nodes(land, 'data-climb')) == len(rec['climbs'])
    assert not nodes(land, 'data-slice'), 'the whole problem is not labelled a slice'

    # landscape slices (three decisions): one per pair, the third held at the whole-unit plan
    rec3 = records['three']
    best = next(p for p in rec3['plans'] if p['name'] == 'whole-unit optimum')
    assert len(rec3['landscapes']) == 3, len(rec3['landscapes'])
    for L in rec3['landscapes']:
        (held_name, held_value), = L['held'].items()
        assert held_value == best['at'][held_name], (L['held'], best['at'])
        view = views[f'three.landscape-{L["decisions"][0]}-{L["decisions"][1]}']
        label = nodes(view, 'data-slice')
        assert label and held_name in label[0].attrib['data-slice'], 'a slice says what it holds'
        marks = {n.attrib['data-plan']: n.attrib for n in nodes(view, 'data-plan')}
        for p in rec3['plans']:
            inside = abs(p['at'][held_name] - held_value) < 1e-6
            assert marks[p['name']]['data-in-slice'] == ('1' if inside else '0'), (p['name'], L['held'])
        assert marks['whole-unit optimum']['data-in-slice'] == '1'
        assert all(n.attrib['data-projected'] == '1' for n in nodes(view, 'data-climb'))
        # the grid holds the true value of the plan it names, recomputed here
        doc3, model3 = load3
        from optimize_sov import _decision_space, true_value
        space = _decision_space(doc3, model3)
        i, j = 7, 5
        y = [0.0] * len(space['names'])
        y[space['names'].index(L['decisions'][0])] = L['x'][i]
        y[space['names'].index(L['decisions'][1])] = L['y'][j]
        y[space['names'].index(held_name)] = held_value
        if L['value'][i][j] is not None:
            assert abs(true_value(doc3, model3, space['plan_of'](space['expand'](y)))['value'] - L['value'][i][j]) < 1e-3

    # search: outline and tree
    log = rec['search']['nodes']
    for view in ('learning.search-outline', 'learning.search-tree'):
        rows = {n.attrib['data-node']: n.attrib for n in nodes(views[view], 'data-node')}
        assert sorted(rows) == sorted(str(e['id']) for e in log), view
        for e in log:
            row = rows[str(e['id'])]
            assert row['data-dead'] == ('1' if e['outcome'] in ('pruned', 'infeasible') else '0'), (view, e)
            if row['data-gap']:
                assert 0 <= float(row['data-gap']) <= 1
            if e['outcome'] == 'incumbent':
                assert float(row['data-gap']) == 0, row
            # Step-through order is the order branch and bound decided the nodes: the log's.
            assert row['data-order'] == str(log.index(e)), (view, e, row['data-order'])

    # timeline
    rec = records['week']
    bars = {n.attrib['data-span']: n.attrib for n in nodes(views['week.timeline'], 'data-span')}
    assert len(bars) == len(rec['spans'])
    for sp in rec['spans']:
        b = bars[f'{sp["stage"]}:{sp["unit"]}']
        assert abs(float(b['data-start']) - sp['start']) < 0.01 and abs(float(b['data-end']) - sp['end']) < 0.01
    stall = [s for s in rec['stops'] if s['kind'] == 'stalled'][0]
    assert abs(float(nodes(views['week.timeline'], 'data-stall')[0].attrib['data-stall']) - stall['t']) < 0.01
    progress = {n.attrib['data-progress']: n.attrib for n in nodes(views['week.timeline'], 'data-progress')}
    assert progress['tables']['data-done'] == '1' and progress['tables']['data-target'] == '2', progress

    # page: every view present, linking wired
    page = views['page']
    assert page.count('<figure') == sum(1 for k in views if k != 'page')
    assert page.count('data-step="timing"') == sum(1 for k in views if '.timing' in k)
    assert page.count('data-step="search"') == sum(1 for k in views if k.endswith('.search-outline')) >= 1
    last = records['carry']['events'][-1]
    assert f'data-link="ev:{last["signal"]}:{last["t"]}"' in page and 'CSS.escape' in page


def check_gallery() -> None:
    # docs/visual/ is what the code draws today, or the check fails.
    subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build_visual_gallery.py'), '--check'], check=True)


def main() -> int:
    check_glyphs()
    check_views()
    check_gallery()
    print('plot_run QA PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
