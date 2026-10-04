"""Track gap while a card is dragged: a wire keeps its nudged route from the press to the settle.

A drag snapshot is the route as drawn (after jogs and nudging), so pressing a card, holding it still
and releasing it leave every wire on that card where it was. The page is set up as
tests/track_gap_qa.py sets it up.

- tests/fixtures/mixed-waves.sov: pressing the card at either end of w5, with no movement, leaves
  every wire on that card on the route it had; while pressed w5 has no interior segment under 10 and
  w1 to w5 have no close pair.
- The columns scene (snap off): the wires on l0 keep their route at the press, are as drawn when
  settled with the button held as after the release, and no close pair appears at any moment.
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

READ = r"""()=>{
  const out={wires:{},ends:{}};
  for(const g of workspace.querySelectorAll('.wire-group')){
    const p=g.querySelector('path.wire');if(!p)continue;const m=layoutWorldMatrix(p);
    const d=String(p.getAttribute('d')||'').replace(/A[^A-Z]*?(?=[MLHV])/g,'');
    out.wires[g.dataset.wireId]=layoutPathCorners(d).map(q=>m?new DOMPoint(q.x,q.y).matrixTransform(m):q).map(q=>({x:Math.round(q.x*100)/100,y:Math.round(q.y*100)/100}));
  }
  for(const w of wires){out.ends[w.id]=[w.a||null,w.b||null]}
  return out;
}"""

COLUMNS = [{'id': f'{side}{r}', 'symbolId': 'act', 'x': 104 if side == 'l' else 504, 'y': 100 + 150 * r}
           for side in 'lr' for r in range(4)]
COLUMN_WIRES = [('l0', 'r2'), ('l1', 'r3'), ('l2', 'r0'), ('l3', 'r1'), ('l0', 'r3'), ('l3', 'r0')]


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


def corners(r, wid):
    return [(q['x'], q['y']) for q in clean(r['wires'][wid])]


def same(r1, r2, wid):
    a, b = clean(r1['wires'][wid]), clean(r2['wires'][wid])
    return len(a) == len(b) and all(abs(p['x'] - q['x']) <= .01 and abs(p['y'] - q['y']) <= .01 for p, q in zip(a, b))


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


def press(page, card):
    box = page.locator(f'.node[data-id="{card}"]').bounding_box()
    assert box, card
    x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    assert page.evaluate('()=>activeNodeDrag') == card, ('the press starts a drag of', card)
    return x, y


def node_xy(page, card):
    return page.evaluate('(id)=>{const n=nodes.find(q=>q.id===id);return [n.x,n.y]}', card)


def held_and_released(page, card, nudge):
    """Read before the press, while pressed, held after a 60 px move down and settled, after release."""
    if not nudge:
        page.evaluate('()=>{window.ROUTE_NUDGE=false}')
    before = planted(page)
    x, y = press(page, card)
    page.wait_for_timeout(80)
    pressed = page.evaluate(READ)
    for k in (1, 2, 3):
        page.mouse.move(x, y + 20 * k)
    page.wait_for_timeout(400)
    held = page.evaluate(READ)
    held_xy = node_xy(page, card)
    page.mouse.up()
    page.wait_for_timeout(300)
    released = page.evaluate(READ)
    released_xy = node_xy(page, card)
    state = page.evaluate('()=>({drag:activeNodeDrag,snaps:dragRouteSnapshots.size})')
    if not nudge:
        page.evaluate('()=>{delete window.ROUTE_NUDGE}')
    return before, pressed, held, released, held_xy, released_xy, state


with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)

    # Part 1: press and release without moving.
    # Snap is off throughout: a release that snaps the card to the grid moves it, and then its
    # routes change for a reason this test does not cover.
    page.evaluate('()=>{canvasSnapEnabled=false}')
    base = show(page, MIXED.read_text(encoding='utf-8'), MIXED.name)
    w5_ends = base['ends']['w5']
    part1 = {}
    for card in w5_ends:
        show(page, MIXED.read_text(encoding='utf-8'), MIXED.name)
        before = page.evaluate(READ)
        press(page, card)
        page.wait_for_timeout(80)
        pressed = page.evaluate(READ)
        page.mouse.up()
        page.wait_for_timeout(300)
        after = page.evaluate(READ)
        part1[card] = (before, pressed, after)

    # Part 2: the columns scene, snap off.
    page.evaluate('()=>{canvasSnapEnabled=false}')
    nudged = held_and_released(page, 'l0', True)
    # Control: nudging off.
    control = held_and_released(page, 'l0', False)
    browser.close()

for card, (before, pressed, after) in part1.items():
    print(f'part 1, card {card}: w5 before', corners(before, 'w5'))
    print(f'part 1, card {card}: w5 pressed', corners(pressed, 'w5'))
    print(f'part 1, card {card}: w5 after  ', corners(after, 'w5'))
before, pressed, held, released, held_xy, released_xy, state = nudged
for wid in ('c0', 'c4'):
    print('part 2', wid, 'pressed', corners(pressed, wid), 'held', corners(held, wid), 'released', corners(released, wid))
c_before, c_pressed, c_held, c_released, _, _, _ = control
print('control (nudging off): c0 equal', same(c_held, c_released, 'c0'), 'c4 equal', same(c_held, c_released, 'c4'))
for wid in ('c0', 'c4'):
    print('  control', wid, 'held', corners(c_held, wid), 'released', corners(c_released, wid))

assert not errors, ('the page logs no errors', errors)

for card, (before, pressed, after) in part1.items():
    for wid, ends in before['ends'].items():
        if card not in ends:
            continue
        assert same(before, pressed, wid), ('part 1: a wire on the pressed card keeps its route at the press', card, wid, corners(before, wid), corners(pressed, wid))
        assert same(before, after, wid), ('part 1: a wire on the pressed card keeps its route after release', card, wid, corners(before, wid), corners(after, wid))
    c = clean(pressed['wires']['w5'])
    for P, Q in zip(c[1:-2], c[2:-1]):
        assert max(abs(P['x'] - Q['x']), abs(P['y'] - Q['y'])) >= 10, ('part 1: w5 has no interior segment under 10 while pressed', card, corners(pressed, 'w5'))
    assert not close_pairs(pressed, ['w1', 'w2', 'w3', 'w4', 'w5']), ('part 1: no close pair among w1-w5 while pressed', card, close_pairs(pressed, ['w1', 'w2', 'w3', 'w4', 'w5']))

if not (same(c_held, c_released, 'c0') and same(c_held, c_released, 'c4')):
    print('CONTROL DIFFERS with nudging off: not this change')
    sys.exit(3)

before, pressed, held, released, held_xy, released_xy, state = nudged
for wid in ('c0', 'c4'):
    assert same(before, pressed, wid), ('part 2: the wire keeps its route at the press', wid, corners(before, wid), corners(pressed, wid))
    assert same(held, released, wid), ('part 2: held-and-settled equals released', wid, corners(held, wid), corners(released, wid))
assert held_xy == released_xy, ('part 2: l0 does not move at the release', held_xy, released_xy)
for name, r in (('pressed', pressed), ('held', held), ('released', released)):
    assert not close_pairs(r), ('part 2: no close pair', name, close_pairs(r))
assert state['drag'] is None and state['snaps'] == 0, ('part 2: after release no drag and no snapshots', state)
print('PASS track gap drag QA')
