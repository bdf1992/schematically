"""Routing buses QA: a harness of buses carries the wires between two groups.

Two groups of six cards (2 columns, 3 rows each), 300 apart, joined by 10 wires in a
non-monotone pattern that sends inner-column cards to far rows. layout.harness between the
groups makes one trunk per wire label in the gap and streets in the row gaps; every wire rides
them on its own lane (LAYOUT-MODEL.md "As built: buses").

- every collected wire has mode bus, and its path runs on its own lane inside its trunk's band;
- the harness crosses fewer times than the router alone, with no wrapped route and no route
  through a card;
- the wires themselves (ends, ports, surface, config) are untouched and the document validates;
- saving and opening again keeps the buses and every path;
- a pinned route stays pinned;
- a bus label is drawn once and its wires draw no label of their own;
- BAD_POINTS, UNKNOWN_BUS, BUS_GAP and GAP_TOO_NARROW are refused and change nothing;
- the page logs no errors.

Diagnostics: --shot DIR saves a picture before and after the harness and prints the lane orders
and route findings; --second LABEL gives the last four wires a second label, so the harness makes
two parallel trunks (each label's exits then cross the other trunk's lanes, and the crossing
count rises above the router's: the cost of one trunk per label).
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

PITCH_X, PITCH_Y = 160, 180


def build(gap: int = 300) -> dict:
    comps, members = [], {'left': [], 'right': []}
    # Left: column 0 is outer (far from the trunk), column 1 inner. Right: column 0 inner, 1 outer.
    left_x = [100, 100 + PITCH_X]
    right_x0 = left_x[1] + 56 + 24 + gap + 24 + 56
    right_x = [right_x0, right_x0 + PITCH_X]
    for r in range(3):
        for c in range(2):
            for side, xs in (('left', left_x), ('right', right_x)):
                cid = f"{side[0]}{r}{c}"
                comps.append({'id': cid, 'symbolId': 'act', 'x': xs[c], 'y': 120 + r * PITCH_Y,
                              'config': {'label': f"{side.title()} {r}{c}"}})
                members[side].append(cid)
    groups = [{'id': g, 'symbolId': 'group', 'x': 0, 'y': 0,
               'config': {'label': g.title(), 'members': members[g], 'presentation': {'graphic': {'kind': 'none'}}}}
              for g in ('left', 'right')]
    # Inner-column cards go to far rows (l01 to row 2, l21 to row 0). An outer card sends only from
    # rows 0 and 1 and receives only in rows 1 and 2: its street lies between two rows.
    label = sys.argv[sys.argv.index('--second') + 1] if '--second' in sys.argv else 'feeds'
    pattern = [('l01', 'r21', 'feeds'), ('l00', 'r20', 'feeds'), ('l11', 'r00', 'feeds'), ('l10', 'r11', 'feeds'),
               ('l21', 'r10', 'feeds'), ('l21', 'r00', 'feeds'), ('l01', 'r10', label), ('l11', 'r20', label),
               ('l10', 'r21', label), ('l00', 'r11', label)]
    wires = [{'id': f"w{i + 1}", 'a': a, 'aSide': 'out', 'b': b, 'bSide': 'in', 'config': {'label': label}}
             for i, (a, b, label) in enumerate(pattern)]
    return {'schema': 'soveraeign.schematic/document@0.1', 'id': 'buses-qa', 'meta': {'title': 'Buses QA'},
            'components': groups + comps, 'wires': wires}


READ = r"""()=>{
  const out={wires:{},busLabels:[],wireLabels:[],bands:{}};
  for(const g of workspace.querySelectorAll('.wire-group')){
    const p=g.querySelector('path.wire'),d=p.getAttribute('d');
    out.wires[g.dataset.wireId]={d,fallback:g.dataset.busFallback||null,
      corners:layoutPathCorners(d.replace(/A[^A-Z]*?(?=[HV])/g,''))};
    const l=g.querySelector('.connection-label');if(l)out.wireLabels.push({w:g.dataset.wireId,text:l.textContent});
  }
  for(const t of workspace.querySelectorAll('.bus-label'))out.busLabels.push({bus:t.dataset.busId,text:t.textContent});
  for(const b of workspace.querySelectorAll('.bus-band'))out.bands[b.dataset.busId]=Number(b.dataset.lanes);
  return out;
}"""
SNAP = "()=>JSON.stringify(SovSchematicAPI.document.get())"


def corners(points: list[dict]) -> list[tuple[float, float]]:
    pts = []
    for q in points:
        p = (round(q['x'], 2), round(q['y'], 2))
        if not pts or pts[-1] != p:
            pts.append(p)
    out = [pts[0]] if pts else []
    for i in range(1, len(pts) - 1):
        a, b, c = out[-1], pts[i], pts[i + 1]
        if (a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1]):
            continue
        out.append(b)
    if len(pts) > 1:
        out.append(pts[-1])
    return out


def wire_semantics(doc: dict) -> dict:
    return {w['id']: {k: w.get(k) for k in ('a', 'b', 'aSide', 'bSide', 'canvasId', 'config')} for w in doc['wires']}


errors: list[str] = []
with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [json.dumps(build()), 'buses-qa.sov'])
    page.evaluate('()=>fitDiagram()')
    page.wait_for_timeout(200)

    # --shot <dir> keeps a picture of each stage, for a reader judging the routes.
    shots = sys.argv[sys.argv.index('--shot') + 1] if '--shot' in sys.argv else None
    if shots:
        page.screenshot(path=str(Path(shots) / 'buses-before.png'))
    # Without buses: the router alone. w10 is pinned to the route it has now.
    before_metrics = page.evaluate('()=>SovSchematicAPI.layout.metrics({static:true})')
    pinned_corners = page.evaluate(r"""()=>{const d=workspace.querySelector('.wire-group[data-wire-id="w10"] path.wire').getAttribute('d');return layoutPathCorners(d.replace(/A[^A-Z]*?(?=[HV])/g,''))}""")
    pin = page.evaluate("()=>SovSchematicAPI.layout.route('w10',{mode:'pinned',points:"
                        "layoutPathCorners(workspace.querySelector('.wire-group[data-wire-id=\"w10\"] path.wire').getAttribute('d').replace(/A[^A-Z]*?(?=[HV])/g,'')).slice(1,-1)})")
    assert pin['ok'], pin
    before_doc = json.loads(page.evaluate(SNAP))

    receipt = page.evaluate("()=>SovSchematicAPI.layout.harness({between:['left','right']})")
    assert receipt['ok'], receipt
    page.wait_for_timeout(150)
    after = page.evaluate(READ)
    after_metrics = page.evaluate('()=>SovSchematicAPI.layout.metrics({static:true})')
    if shots:
        page.screenshot(path=str(Path(shots) / 'buses-after.png'))
        state = page.evaluate('()=>({order:Object.fromEntries(busRouteState.order),fallback:[...busRouteState.fallback]})')
        print('   lanes:', json.dumps(state))
        shown = page.evaluate(READ)
        for f in after_metrics['findings']:
            if f['kind'] in ('crossing', 'route-wraps', 'route-overlap', 'route-through-node'):
                print('  ', f['kind'], f['ids'], f['detail'])
                if f['kind'] == 'route-overlap':
                    for wid in f['ids']:
                        print('      ', wid, corners(shown['wires'][wid]['corners']))
    doc =json.loads(page.evaluate(SNAP))
    view = doc['layout']['views'][doc['layout'].get('default', 'main')]
    buses, routes = view['buses'], view['routes']
    valid = page.evaluate('()=>SovSchematicData.validateDocument(SovSchematicAPI.document.get())')
    markers = page.evaluate('()=>SovSchematicAPI.markers()')

    # Saved and opened again: the buses and every path survive.
    saved = page.evaluate('()=>JSON.stringify(SovSchematicAPI.file.document())')
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [saved, 'buses-qa-again.sov'])
    page.evaluate('()=>fitDiagram()')
    page.wait_for_timeout(200)
    reopened = page.evaluate(READ)
    reopened_doc = json.loads(page.evaluate(SNAP))

    # Refusals: each comes back with its code and leaves the document as it was.
    trunk_feeds = 'harness-left-right-feeds'
    codes = {}
    snap = page.evaluate(SNAP)
    codes['BAD_POINTS'] = page.evaluate("()=>SovSchematicAPI.layout.bus({id:'diag',points:[{x:0,y:0},{x:40,y:40}]})")
    codes['UNKNOWN_BUS'] = page.evaluate("()=>SovSchematicAPI.layout.route('w1',{mode:'bus',buses:['no-such-bus']})")
    unchanged_simple = page.evaluate(SNAP) == snap
    made = page.evaluate("()=>SovSchematicAPI.layout.bus({id:'far',points:[{x:-900,y:-900},{x:-700,y:-900}]})")
    assert made['ok'], made
    snap_far = page.evaluate(SNAP)
    codes['BUS_GAP'] = page.evaluate(f"()=>SovSchematicAPI.layout.route('w1',{{mode:'bus',buses:['{trunk_feeds}','far']}})")
    unchanged_gap = page.evaluate(SNAP) == snap_far
    removed = page.evaluate("()=>SovSchematicAPI.layout.bus({id:'far',remove:true})")
    listed = page.evaluate('()=>SovSchematicAPI.layout.buses()')
    # A document whose groups sit 60 apart: no room for a trunk.
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [json.dumps(build(gap=60)), 'narrow.sov'])
    page.wait_for_timeout(150)
    snap_narrow = page.evaluate(SNAP)
    codes['GAP_TOO_NARROW'] = page.evaluate("()=>SovSchematicAPI.layout.harness({between:['left','right']})")
    unchanged_narrow = page.evaluate(SNAP) == snap_narrow
    browser.close()

assert not errors, errors

# Every collected wire has mode bus; w10 (pinned before) is not collected and stays pinned.
collected = {w['id'] for w in receipt['wires']}
assert collected == {f"w{i}" for i in range(1, 10)}, receipt['wires']
for wid in collected:
    assert routes[wid]['mode'] == 'bus', (wid, routes[wid])
assert routes['w10']['mode'] == 'pinned', routes['w10']
assert corners([{'x': x, 'y': y} for x, y in corners(after['wires']['w10']['corners'])]) == corners(pinned_corners), \
    ('a pinned route keeps its route', after['wires']['w10']['corners'], pinned_corners)
assert not any(after['wires'][w]['fallback'] for w in collected), 'no bus route fell back to the router'

# Each wire runs on its own lane inside its trunk's band.
lanes: dict[str, list[float]] = {}
for wid in collected:
    trunk = next(b for b in routes[wid]['buses'] if b.startswith('harness-'))
    bus = buses[trunk]
    x0 = bus['points'][0]['x']
    n = after['bands'][trunk]
    half = (n * bus['pitch'] + 8) / 2
    pts = corners(after['wires'][wid]['corners'])
    runs = [(a, b) for a, b in zip(pts, pts[1:]) if a[0] == b[0] and abs(a[0] - x0) < half and abs(b[1] - a[1]) > 1]
    assert runs, (wid, 'has no vertical run inside', trunk, pts)
    lanes.setdefault(trunk, []).append(max(runs, key=lambda s: abs(s[1][1] - s[0][1]))[0][0])
for trunk, xs in lanes.items():
    assert len(set(xs)) == len(xs), ('each wire on its own lane', trunk, sorted(xs))
assert set(lanes) == {f"harness-left-right-{b['label']}" for b in buses.values() if b.get('label')}, lanes

# Fewer crossings, nothing wrapped, nothing through a card.
c_before = before_metrics['counts'].get('crossing', 0)
c_after = after_metrics['counts'].get('crossing', 0)
print(f"crossings without buses {c_before}, with the harness {c_after}")
print('counts without:', json.dumps(before_metrics['counts'], sort_keys=True))
print('counts with:   ', json.dumps(after_metrics['counts'], sort_keys=True))
assert c_after < c_before, (c_before, c_after)
assert after_metrics['counts'].get('route-wraps', 0) == 0, after_metrics['counts']
assert after_metrics['counts'].get('route-through-node', 0) == 0, [f for f in after_metrics['findings'] if f['kind'] == 'route-through-node']

# The wires themselves are untouched; the document validates.
assert wire_semantics(before_doc) == wire_semantics(doc), 'wire ends, ports, surface and config are unchanged'
assert not valid.get('errors'), valid
assert not [m for m in markers if m.get('severity') == 'error'], markers

# Saved and opened again: buses kept, every path the same.
re_view = reopened_doc['layout']['views'][reopened_doc['layout'].get('default', 'main')]
assert re_view['buses'] == buses, 'the buses survive a save and an open'
for wid, w in after['wires'].items():
    assert reopened['wires'][wid]['d'] == w['d'], (wid, w['d'], reopened['wires'][wid]['d'])

# One label per bus; its wires draw none.
labelled = [b for b in buses.values() if b.get('label')]
assert sorted(t['text'] for t in after['busLabels']) == sorted(b['label'] for b in labelled), after['busLabels']
assert not [t for t in after['wireLabels'] if t['text'] in ('feeds', 'reads') and t['w'] in collected], after['wireLabels']

# Refusals carry their codes and change nothing.
for code, result in codes.items():
    assert not result['ok'] and result['code'] == code, (code, result)
assert unchanged_simple and unchanged_gap and unchanged_narrow, (unchanged_simple, unchanged_gap, unchanged_narrow)
assert codes['GAP_TOO_NARROW'].get('need', 0) > codes['GAP_TOO_NARROW'].get('have', 0), codes['GAP_TOO_NARROW']
assert removed['ok'] and removed['wires'] == [], removed
assert 'far' not in {b['id'] for b in listed['buses']}, listed
print('PASS routing buses QA', {'crossings': [c_before, c_after], 'buses': sorted(buses), 'wires': len(collected)})
