"""Route clear of cards QA: a wire never runs through a card or along its edge.

The router treats every visible 2D card (not a group, not a container holding both ends) as an
obstacle padded by 12, and the wire's own end cards padded by 8; only each end's lead, the stub
from the port to its first bend, may sit inside its own card's padding. When no simple shape
clears, it searches the channel grid (A*) instead of taking a perimeter route through a card.

- tests/fixtures/task-lifecycle.sov (frame 4 of the Miro parity study) and
  tests/fixtures/work-engine-sample.sov (frame 5) have route-through-node 0 and route-hugs-node 0.
- A planted 4 x 4 grid of act cards 220 apart, with 12 wires between non-adjacent cards, has
  route-through-node 0, route-hugs-node 0 and no wire marked data-route-blocked.
- In a row of three cards a, m, b, the wire a to b routes round m.
- Every route is horizontal and vertical steps, and the page logs no errors.
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

FIXTURES = [ROOT / 'tests' / 'fixtures' / 'task-lifecycle.sov', ROOT / 'tests' / 'fixtures' / 'work-engine-sample.sov']

# The planted grid: 4 rows x 4 columns of act cards, 220 apart. Card ids are g<row><col>.
GRID = [(r, c) for r in range(4) for c in range(4)]
# Twelve wires between cards that are not neighbours in a row or a column: across a row past a
# card, down a column past a card, diagonals, and backwards (out on the right into a card left of it).
GRID_WIRES = [
    ('g00', 'g02'), ('g10', 'g13'), ('g21', 'g23'), ('g30', 'g32'),
    ('g00', 'g22'), ('g01', 'g33'), ('g02', 'g20'), ('g03', 'g11'),
    ('g12', 'g30'), ('g13', 'g31'), ('g20', 'g03'), ('g33', 'g11'),
]

READ = r"""()=>{
  const out={metrics:SovSchematicAPI.layout.metrics({static:true}),wires:{},blocked:[],cards:{}};
  for(const g of workspace.querySelectorAll('.wire-group')){
    const p=g.querySelector('path.wire');if(!p)continue;const m=layoutWorldMatrix(p);
    const d=String(p.getAttribute('d')||'').replace(/A[^A-Z]*?(?=[MLHV])/g,'');
    out.wires[g.dataset.wireId]=layoutPathCorners(d).map(q=>m?new DOMPoint(q.x,q.y).matrixTransform(m):q).map(q=>({x:Math.round(q.x*100)/100,y:Math.round(q.y*100)/100}));
    if(g.dataset.routeBlocked==='true')out.blocked.push(g.dataset.wireId);
  }
  // The router's own record too, so a blocked route is seen whether or not the renderer marks it.
  for(const [i,e] of routeCache)if(e&&e.blocked&&wires[i]&&!out.blocked.includes(wires[i].id))out.blocked.push(wires[i].id);
  for(const n of nodes)if(componentForm(n).dimension===2&&!isGroupComponent(n)){const R=componentBounds(n);out.cards[n.id]={l:R.l,r:R.r,t:R.t,b:R.b}}
  return out;
}"""


def plant(page, components, wires):
    doc = page.evaluate('()=>({schema:SovSchematicData.DOCUMENT_SCHEMA})')
    doc.update({'id': 'planted', 'components': components, 'wires': wires})
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [json.dumps(doc), 'planted.sov'])
    page.evaluate('()=>{ if (typeof fitDiagram === "function") fitDiagram(); }')
    page.wait_for_timeout(300)
    return page.evaluate(READ)


def open_file(page, path: Path):
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [path.read_text(encoding='utf-8'), path.name])
    page.evaluate('()=>{ if (typeof fitDiagram === "function") fitDiagram(); }')
    page.wait_for_timeout(300)
    return page.evaluate(READ)


def orthogonal(name, wires):
    for wid, pts in wires.items():
        for p, q in zip(pts, pts[1:]):
            assert abs(p['x'] - q['x']) < .5 or abs(p['y'] - q['y']) < .5, (name, wid, 'a diagonal step', p, q)


def counts(r):
    c = r['metrics']['counts']
    return {k: c.get(k, 0) for k in ('route-through-node', 'route-hugs-node', 'route-wraps', 'crossing')}


def dump(name, r):
    if not os.environ.get('ROUTE_QA_DEBUG'):
        return
    print('---', name)
    for f in r['metrics']['findings']:
        if f['kind'] in ('route-through-node', 'route-hugs-node', 'route-wraps'):
            print('  ', f['kind'], f['ids'], f['detail'])
    if os.environ.get('ROUTE_QA_DEBUG') == '2':
        for wid, pts in r['wires'].items():
            print('   wire', wid, [(p['x'], p['y']) for p in pts])
        for cid, R in r['cards'].items():
            print('   card', cid, R)


with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)

    fixtures = {}
    for f in FIXTURES:
        fixtures[f.name] = open_file(page, f)
        dump(f.name, fixtures[f.name])

    grid = plant(page,
                 [{'id': f'g{r}{c}', 'symbolId': 'act', 'x': 100 + 220 * c, 'y': 100 + 220 * r} for r, c in GRID],
                 [{'id': f'w{i}', 'a': a, 'aSide': 'out', 'b': b, 'bSide': 'in'} for i, (a, b) in enumerate(GRID_WIRES)])
    dump('grid', grid)

    row = plant(page,
                [{'id': 'a', 'symbolId': 'act', 'x': 100, 'y': 300}, {'id': 'm', 'symbolId': 'act', 'x': 400, 'y': 300},
                 {'id': 'b', 'symbolId': 'act', 'x': 700, 'y': 300}],
                [{'id': 'ab', 'a': 'a', 'aSide': 'out', 'b': 'b', 'bSide': 'in'}])
    dump('row', row)

    # A pocket no straight, L, HVH or VHV shape clears: a wire from a back to b, on its left, with
    # cards 16 above and below both, over both leads, so no channel runs beside either card. Only a
    # search finds the way out and round.
    pocket = plant(page,
                   [{'id': 'b', 'symbolId': 'act', 'x': 100, 'y': 300}, {'id': 'a', 'symbolId': 'act', 'x': 500, 'y': 300},
                    {'id': 'u1', 'symbolId': 'act', 'x': 600, 'y': 200}, {'id': 'd1', 'symbolId': 'act', 'x': 600, 'y': 400},
                    {'id': 'u2', 'symbolId': 'act', 'x': 0, 'y': 200}, {'id': 'd2', 'symbolId': 'act', 'x': 0, 'y': 400}],
                   [{'id': 'back', 'a': 'a', 'aSide': 'out', 'b': 'b', 'bSide': 'in'}])
    dump('pocket', pocket)
    browser.close()

for name, r in fixtures.items():
    print(name, counts(r))
print('grid', counts(grid), 'blocked', grid['blocked'])
print('row', counts(row))
print('pocket', counts(pocket), 'blocked', pocket['blocked'])

assert not errors, ('the page logs no errors', errors)
for name, r in [*fixtures.items(), ('grid', grid), ('row', row), ('pocket', pocket)]:
    orthogonal(name, r['wires'])
for name, r in fixtures.items():
    c = counts(r)
    assert c['route-through-node'] == 0, (name, 'no route runs through a card', c)
    assert c['route-hugs-node'] == 0, (name, 'no route runs along a card edge', c)
c = counts(grid)
assert len(grid['wires']) == len(GRID_WIRES), ('every planted wire is drawn', sorted(grid['wires']))
assert c['route-through-node'] == 0, ('grid: no route runs through a card', c)
assert c['route-hugs-node'] == 0, ('grid: no route runs along a card edge', c)
assert not grid['blocked'], ('grid: every wire finds a clear route', grid['blocked'])
m, pts = row['cards']['m'], row['wires']['ab']
assert any(q['y'] <= m['t'] - 12 or q['y'] >= m['b'] + 12 for q in pts), ('a to b routes round m', pts, m)
for P, Q in zip(pts, pts[1:]):
    if abs(P['y'] - Q['y']) < .5:
        assert not (m['t'] - 12 < P['y'] < m['b'] + 12 and min(P['x'], Q['x']) < m['r'] and max(P['x'], Q['x']) > m['l']), ('a to b never crosses m', P, Q, m)
assert counts(row)['route-through-node'] == 0, ('row: a to b clears m', counts(row))
c = counts(pocket)
assert c['route-through-node'] == 0, ('pocket: the search finds a route through no card', c, pocket['wires'])
assert c['route-hugs-node'] == 0, ('pocket: the search finds a route along no card edge', c, pocket['wires'])
assert not pocket['blocked'], ('pocket: the wire is not blocked', pocket['blocked'])
print('PASS route clear of cards QA')
