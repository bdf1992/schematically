"""Run records and views QA (static: Python and Node, no browser).

The views in scripts/plot_run.mjs claim to draw what a record holds and nothing else. Each
claim is checked here against the record, not against the renderer's own arithmetic:

  - glyphs: the pack's glyphs are what scripts/logic_glyphs.py writes, parse as XML, use only
    the tags and attributes the editor's custom-graphic sanitizer admits (read from
    src/55-render.js), follow the agreed family rule, and are what the example gates carry;
  - determinism: the same records render byte-identical SVG, and every SVG parses;
  - timing: every value-lane segment shows the bus value decoded from the record's bit changes,
    the ripple counter's 7 -> 8 shows the transient 6, 4, 0, and the synchronous counter shows
    no transient at all;
  - level: each output lane's switch count is the record's count, and the Schmitt trigger
    switches less than the comparator;
  - landscape: every plan marker sits at its record position with its certificate, every
    whole-unit local optimum is ringed and nothing else is, and every limit is drawn;
  - search: one outline row per logged node, dead exactly when pruned or infeasible, the
    gradient in [0, 1] with the incumbent at 0;
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
from record_run import noisy_wave, record_logic, record_optimize, record_simulate  # noqa: E402

PACK = json.loads((ROOT / 'packs' / 'logic' / 'gates.json').read_text(encoding='utf-8'))
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
    for name, g in PACK['gates'].items():
        assert g['glyph_family'] == ('distinctive' if name in CLASSIC else 'rectangle'), name
        for key in ('glyph', 'glyph_small'):
            root = ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 64">{g[key]}</svg>')
            for node in root.iter():
                t = node.tag.replace(SVG, '')
                assert t in tags, (name, key, t)
                if node is not root:
                    bad = set(node.attrib) - attrs
                    assert not bad, (name, key, t, bad)
        assert g['glyph_small'].count('M30 8H66V56H30Z') == 1, f'{name}: small glyph must be the rectangle'
    for doc_path in sorted((ROOT / 'examples' / 'logic').glob('*.sov')):
        doc = json.loads(doc_path.read_text(encoding='utf-8'))
        for c in doc['components']:
            logic = c.get('config', {}).get('logic', {})
            if 'gate' in logic:
                svg = c['config']['presentation']['graphic']['svg']
                assert svg == PACK['gates'][logic['gate']]['glyph'], (doc_path.name, c['id'])


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
        'ripple': record_logic(lg / 'ripple-counter4.sov', [{} for _ in range(17)], 'CLK', 24, ['Q']),
        'sync': record_logic(lg / 'sync-counter4.sov', [{} for _ in range(17)], 'CLK', 24, ['Q']),
        'schmitt': record_logic(lg / 'schmitt.sov', [{'X': x} for x in noisy_wave(240)], None, 1, [], 'X'),
        'learning': record_optimize(op / 'workshop.sov', op / 'workshop.learning.opt.json', segments=20, starts=12, steps=41),
        'week': record_simulate(op / 'workshop.sov', op / 'workshop.learning.opt.json', {'chairs': 14, 'tables': 2}),
    }
    for rec in records.values():
        assert rec['schema'] == 'soveraeign.schematic/run@0.0-draft' and rec['document']['fingerprint'].startswith('sem1:')
    with tempfile.TemporaryDirectory() as tmp:
        views = render(records, Path(tmp))

    # timing: segments against bits decoded here from the record
    for name in ('ripple', 'sync'):
        rec = records[name]
        segs = nodes(views[f'{name}.timing'], 'data-bus')
        assert segs
        for s in segs:
            t0 = float(s.attrib['data-t0'])
            decoded = sum(value_at(rec['signals'][bit], t0) << i for i, bit in enumerate(rec['buses']['Q']))
            assert int(s.attrib['data-value']) == decoded, (name, s.attrib, decoded)
        transients = [int(s.attrib['data-value']) for s in segs if s.attrib['data-transient'] == '1']
        if name == 'sync':
            assert not transients and 'sync.timing-zoom' not in views, 'a synchronous counter has no transient values'
        else:
            zoom = [int(s.attrib['data-value']) for s in nodes(views['ripple.timing-zoom'], 'data-bus') if s.attrib['data-transient'] == '1']
            assert zoom in ([6, 4, 0], [14, 12, 8]), zoom

    # level: switch counts
    rec = records['schmitt']
    counts = {}
    for n in nodes(views['schmitt.level'], 'data-switches'):
        counts[len(counts)] = int(n.attrib['data-switches'])
    expected = [len([c for c in rec['signals'][o] if c[0] > 0]) for r in rec['readers'] for o in r['outputs']]
    assert list(counts.values()) == expected, (counts, expected)
    cmp_, hys = expected
    assert hys < cmp_, expected

    # landscape
    rec = records['learning']
    land = views['learning.landscape']
    marks = {n.attrib['data-plan']: n.attrib for n in nodes(land, 'data-plan')}
    for p in rec['plans']:
        m = marks[p['name']]
        x, y = map(float, m['data-at'].split(','))
        assert abs(x - p['at'][0]) < 0.01 and abs(y - p['at'][1]) < 0.01, (p, m)
        assert m['data-certificate'] == p['certificate'] and m['data-feasible'] == ('1' if p['feasible'] else '0')
    ringed = sorted(n.attrib['data-whole'] for n in nodes(land, 'data-whole') if n.attrib['data-local'] == '1')
    assert ringed == sorted(f'{w["at"][0]},{w["at"][1]}' for w in rec['landscape']['whole'] if w['local']), ringed
    assert len(ringed) == 6, ringed
    drawn = {n.attrib['data-limit'] for n in nodes(land, 'data-limit')}
    assert drawn == set(rec['landscape']['slack']), (drawn, rec['landscape']['slack'].keys())
    assert len(nodes(land, 'data-climb')) == len(rec['climbs'])

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
    assert page.count('<figure>') == sum(1 for k in views if k != 'page')
    assert 'data-link="ev:Q0:169"' in page and 'CSS.escape' in page


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
