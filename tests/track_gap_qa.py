"""Track gap QA: two wires that run side by side stand a track apart, so each can be followed by eye.

TRACK_GAP (10, src/40-routing.js) is the rule: two auto-routed wires whose parallel middle segments
overlap for 24 or more are at least TRACK_GAP apart; wires sharing an end may instead share one line
exactly (a trunk). After routing, jogs (a step under 10 between two parallel legs) are taken out and
segments that share a channel are ordered and spread (nudgeRoutes). window.ROUTE_NUDGE=false turns
both off, for this test only.

- tests/fixtures/mixed-waves.sov (the H3 case of the wave-corners study): among w1 to w5 no pair of
  middle segments 0.5 to under 10 apart overlaps 24 or more, w5 has no route-jog, w3 and w5 run on
  one trunk from saw:out to where they part, and crossing is at most 1.
- Two columns of 4 act cards with 6 wires whose shortest routes share one vertical channel: drawn at
  x values at least 10 apart there, with no more crossings than with nudging off (where the scene
  does put two of them closer than 10).
- tests/fixtures/task-lifecycle.sov and tests/fixtures/work-engine-sample.sov: route-close-parallel 0
  and route-overlap 0.
- docs/workengine/map.sov: every route-close-parallel left is a pair that rides one bus.
- No route enters a padded card (route-through-node 0, route-hugs-node 0), and the page logs no errors.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

GAP, STRETCH = 10, 24
MIXED = ROOT / 'tests' / 'fixtures' / 'mixed-waves.sov'
FIXTURES = [ROOT / 'tests' / 'fixtures' / 'task-lifecycle.sov', ROOT / 'tests' / 'fixtures' / 'work-engine-sample.sov']
MAP = ROOT / 'docs' / 'workengine' / 'map.sov'
KINDS = ('route-overlap', 'route-close-parallel', 'route-jog', 'crossing', 'route-through-node', 'route-hugs-node')

READ = r"""()=>{
  const out={metrics:SovSchematicAPI.layout.metrics({static:true}),wires:{},cramped:[],ends:{},bus:{}};
  for(const g of workspace.querySelectorAll('.wire-group')){
    const p=g.querySelector('path.wire');if(!p)continue;const m=layoutWorldMatrix(p);
    const d=String(p.getAttribute('d')||'').replace(/A[^A-Z]*?(?=[MLHV])/g,'');
    out.wires[g.dataset.wireId]=layoutPathCorners(d).map(q=>m?new DOMPoint(q.x,q.y).matrixTransform(m):q).map(q=>({x:Math.round(q.x*100)/100,y:Math.round(q.y*100)/100}));
    if(g.dataset.trackCramped==='true')out.cramped.push(g.dataset.wireId);
  }
  for(const w of wires){out.ends[w.id]=[w.a?`${w.a}:${w.aSide}`:null,w.b?`${w.b}:${w.bSide}`:null].filter(Boolean);const s=typeof busSpecOf==='function'?busSpecOf(w):null;out.bus[w.id]=s?s.buses:[]}
  return out;
}"""

# Two columns of four act cards, 400 apart; six wires from the left column to the right one, two or
# three rows down or up, so every shortest route turns down the one channel between the columns.
# The columns sit 4 off the route grid (12), so a lead's end and a grid line land under 10 apart.
COLUMNS = [{'id': f'{side}{r}', 'symbolId': 'act', 'x': 104 if side == 'l' else 504, 'y': 100 + 150 * r}
           for side in 'lr' for r in range(4)]
COLUMN_WIRES = [('l0', 'r2'), ('l1', 'r3'), ('l2', 'r0'), ('l3', 'r1'), ('l0', 'r3'), ('l3', 'r0')]
CHANNEL = (160, 448)  # the left column's right edge to the right column's left edge


def clean(pts):
    """Corners with hop points and collinear corners merged."""
    out = []
    for p in pts:
        if out and abs(out[-1]['x'] - p['x']) < .5 and abs(out[-1]['y'] - p['y']) < .5:
            continue
        if len(out) >= 2:
            a, l = out[-2], out[-1]
            if (abs(a['x'] - l['x']) < .5 and abs(l['x'] - p['x']) < .5) or (abs(a['y'] - l['y']) < .5 and abs(l['y'] - p['y']) < .5):
                out[-1] = p
                continue
        out.append(p)
    return out


def middles(pts):
    """Middle segments (end leads left out) as (axis, at, lo, hi)."""
    c = clean(pts)
    out = []
    for P, Q in zip(c[1:-2], c[2:-1]):
        if abs(P['y'] - Q['y']) < .5:
            out.append(('h', P['y'], min(P['x'], Q['x']), max(P['x'], Q['x'])))
        elif abs(P['x'] - Q['x']) < .5:
            out.append(('v', P['x'], min(P['y'], Q['y']), max(P['y'], Q['y'])))
    return out


def close_pairs(r, ids=None):
    ids = ids or sorted(r['wires'])
    out = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            for s in middles(r['wires'][a]):
                for t in middles(r['wires'][b]):
                    if s[0] != t[0]:
                        continue
                    d, run = abs(s[1] - t[1]), min(s[3], t[3]) - max(s[2], t[2])
                    if .5 <= d < GAP and run >= STRETCH:
                        out.append((a, b, round(d, 2), round(run, 1)))
    return out


def counts(r):
    c = r['metrics']['counts']
    return {k: c.get(k, 0) for k in KINDS}


def findings(r, kind):
    return [f for f in r['metrics']['findings'] if f['kind'] == kind]


def show(page, text, name):
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [text, name])
    page.evaluate('()=>{ if (typeof fitDiagram === "function") fitDiagram(); }')
    page.wait_for_timeout(300)
    return page.evaluate(READ)


def planted(page):
    doc = page.evaluate('()=>({schema:SovSchematicData.DOCUMENT_SCHEMA})')
    doc.update({'id': 'columns', 'components': COLUMNS,
                'wires': [{'id': f'c{i}', 'a': a, 'aSide': 'out', 'b': b, 'bSide': 'in'} for i, (a, b) in enumerate(COLUMN_WIRES)]})
    return show(page, json.dumps(doc), 'columns.sov')


def channel_xs(r):
    """The x of every middle vertical segment between the two columns, with its span."""
    out = []
    for wid, pts in r['wires'].items():
        for axis, at, lo, hi in middles(pts):
            if axis == 'v' and CHANNEL[0] < at < CHANNEL[1]:
                out.append((wid, at, lo, hi))
    return out


with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)

    mixed = show(page, MIXED.read_text(encoding='utf-8'), MIXED.name)
    fixtures = {f.name: show(page, f.read_text(encoding='utf-8'), f.name) for f in FIXTURES}
    the_map = show(page, MAP.read_text(encoding='utf-8'), MAP.name)
    columns = planted(page)
    page.evaluate('()=>{window.ROUTE_NUDGE=false}')
    columns_off = planted(page)
    page.evaluate('()=>{delete window.ROUTE_NUDGE}')
    browser.close()

print('mixed-waves', counts(mixed), 'close pairs w1-w5', close_pairs(mixed, ['w1', 'w2', 'w3', 'w4', 'w5']))
print('  w3', [(q['x'], q['y']) for q in clean(mixed['wires']['w3'])])
print('  w5', [(q['x'], q['y']) for q in clean(mixed['wires']['w5'])])
for name, r in fixtures.items():
    print(name, counts(r), 'cramped', r['cramped'])
print('map.sov', counts(the_map), 'close-parallel', [f['ids'] for f in findings(the_map, 'route-close-parallel')], 'cramped', len(the_map['cramped']))
print('columns', counts(columns), 'channel x', sorted((w, x) for w, x, _, _ in channel_xs(columns)), 'cramped', columns['cramped'])
print('columns, nudging off', counts(columns_off), 'channel x', sorted((w, x) for w, x, _, _ in channel_xs(columns_off)), 'close pairs', close_pairs(columns_off))

assert not errors, ('the page logs no errors', errors)

# The H3 shape: w5's 8 px jog under the saw trunk is gone and w5 rides w3's trunk.
c = counts(mixed)
assert not close_pairs(mixed, ['w1', 'w2', 'w3', 'w4', 'w5']), ('mixed-waves: no two of w1-w5 run 0.5 to under 10 apart for 24 or more', close_pairs(mixed, ['w1', 'w2', 'w3', 'w4', 'w5']))
assert not [f for f in findings(mixed, 'route-jog') if 'w5' in f['ids']], ('mixed-waves: w5 has no route-jog', findings(mixed, 'route-jog'))
w3, w5 = clean(mixed['wires']['w3']), clean(mixed['wires']['w5'])
assert w3[0] == w5[0] and w3[1] == w5[1] and abs(w3[0]['y'] - w3[1]['y']) < .5 and abs(w3[1]['x'] - w3[0]['x']) >= STRETCH, \
    ('mixed-waves: w3 and w5 run on one trunk from saw:out to where they part', w3, w5)
assert c['crossing'] <= 1, ('mixed-waves: crossing at most 1', c)

# The planted channel: the six wires are spread a track apart where they run side by side.
xs = channel_xs(columns)
assert len(columns['wires']) == len(COLUMN_WIRES), ('every planted wire is drawn', sorted(columns['wires']))
assert close_pairs(columns_off), ('the planted scene puts two wires closer than 10 with nudging off', channel_xs(columns_off))
for i, (wa, xa, la, ha) in enumerate(xs):
    for wb, xb, lb, hb in xs[i + 1:]:
        if wa == wb or min(ha, hb) - max(la, lb) < STRETCH:
            continue
        shared = set(columns['ends'][wa]) & set(columns['ends'][wb])
        assert abs(xa - xb) >= GAP or (shared and abs(xa - xb) < .5), ('columns: side by side in the channel at least 10 apart', wa, xa, wb, xb)
assert not close_pairs(columns), ('columns: no close pair anywhere', close_pairs(columns))
assert counts(columns)['crossing'] <= counts(columns_off)['crossing'], ('columns: no more crossings than with nudging off', counts(columns), counts(columns_off))

# The Miro parity fixtures stay clean.
for name, r in fixtures.items():
    c = counts(r)
    assert c['route-close-parallel'] == 0, (name, 'route-close-parallel 0', findings(r, 'route-close-parallel'))
    assert c['route-overlap'] == 0, (name, 'route-overlap 0', findings(r, 'route-overlap'))

# The map: what is left close is a bus's own lanes.
for f in findings(the_map, 'route-close-parallel'):
    a, b = f['ids']
    assert set(the_map['bus'].get(a, [])) & set(the_map['bus'].get(b, [])), ('map.sov: a close pair left rides one bus', f)

# No route enters a padded card.
for name, r in [('mixed-waves', mixed), *fixtures.items(), ('map.sov', the_map), ('columns', columns)]:
    c = counts(r)
    assert c['route-through-node'] == 0, (name, 'no route runs through a card', findings(r, 'route-through-node'))
    assert c['route-hugs-node'] == 0, (name, 'no route runs along a card edge', findings(r, 'route-hugs-node'))
print('PASS track gap QA')
