"""Drop on wire redraw QA: a card released onto a wire leaves the wires a full redraw draws.

A release that hosts a card on a wire moves the card twice. applyComponentHost (src/30-canvas.js)
puts it on the nearest point of the wire's drawn path, and the first wire pass that runs with the
drag over then gives it its pose at placement.t along that path (renderWires, poseHosted,
src/55-render.js), after every route of that pass was found. The two points differ when t was
clamped (a drop next to a wire's end gives t 0.02 or 0.98) or when the host wire's own path changed,
and the card's own wires were then left ending where it had been. The oracle is from-scratch
consistency, as in tests/drag_redraw_parity_qa.py: straight after the release, the d of every
path.wire must equal the d a renderWires() draws with the route cache and the record of drawn groups
cleared.

Planted document (headless Chromium, 1600 x 1000, snap off): act cards p 404,300, q 1204,300,
c 464,140, e 1204,100, f 104,140; wires x0 p-q, x1 c-e and x2 f-c. c has two wires of its own and
x0 touches neither end of them.

- 'hosted': c is pressed, moved 170 down by real pointer moves to 464,310 (10 off x0, 4 along it
  from its start), held there past the host dwell and released. The release hosts c on x0 with
  t 0.02.
- 'control': the same document again, c moved 60 down and released the same way. Nothing hosts it,
  and the release never empties the record of drawn groups (wireGroupDrawn), so no wire pass of it
  draws from nothing: the incremental redraw stands.

Asserted: (a) hosted, c's placement kind is wire on x0 and its x or y is more than 1 from where the
pointer left it; (b) hosted, every wire's d equals the full redraw's; (c) control, c stays on the
surface with no parent, every wire's d equals the full redraw's, and the record of drawn groups is
emptied 0 times during the release; (d) the page logs no errors.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402
from drag_redraw_parity_qa import differences, open_document, press  # noqa: E402

CARDS = [('p', 404, 300), ('q', 1204, 300), ('c', 464, 140), ('e', 1204, 100), ('f', 104, 140)]
WIRES = [('x0', 'p', 'q'), ('x1', 'c', 'e'), ('x2', 'f', 'c')]
CARD, HOST_WIRE = 'c', 'x0'
HOSTED_DY, CONTROL_DY, MOVES = 170, 60, 6
REST_MS = 700  # past HOST_ADOPT_DWELL (280) and ROUTE_SETTLE_DELAY (140)

WIRE_D = "()=>Object.fromEntries([...workspace.querySelectorAll('.wire-group')].map(g=>[g.dataset.wireId,g.querySelector('path.wire')?.getAttribute('d')??null]))"
# P is what the release left; Q is what a pass from nothing draws at the same state, no cache kept.
PAIR = "()=>{const read=" + WIRE_D + ";const P=read();routeCache.clear();arrowPoseCache.clear();wireGroupDrawn.clear();renderWires();return [P,read()]}"
NODE = "(id)=>{const n=nodes.find(q=>q.id===id);return {x:n.x,y:n.y,kind:n.placement?.kind||'surface',wireId:n.placement?.wireId||null,t:n.placement?.t??null,parent:n.parentId||null}}"
SCALE = '()=>{const a=svgPoint(0,0),b=svgPoint(100,0);return 100/(b.x-a.x)}'
# Counted from the test's side: how often the record of drawn groups is emptied, which is what makes
# a wire pass draw every group from nothing. The product code carries no counter.
WATCH = "()=>{const clear=wireGroupDrawn.clear.bind(wireGroupDrawn);window.dropOnWireClears=0;wireGroupDrawn.clear=()=>{window.dropOnWireClears++;return clear()}}"
CLEARS = '()=>{const count=window.dropOnWireClears;delete wireGroupDrawn.clear;return count}'
STATE = '()=>({drag:activeNodeDrag,keyboard:keyboardMoveNodeId,snapshots:dragRouteSnapshots.size})'


def differing(pair) -> list[str]:
    """The wires whose d the release left differs from the full redraw's, compared as the parity test does."""
    left, full = pair
    assert set(left) == set(full), ('the same wires before and after the full redraw', sorted(left), sorted(full))
    return [wire for wire in sorted(left) if differences(left[wire], full[wire])]


def release(page, name: str, dy: float) -> dict:
    """Open the planted document, drag the card dy units down by pointer, rest, release. What was seen."""
    doc = page.evaluate('()=>({schema:SovSchematicData.DOCUMENT_SCHEMA})')
    doc.update({'id': 'drop-on-wire', 'components': [{'id': i, 'symbolId': 'act', 'x': x, 'y': y} for i, x, y in CARDS],
                'wires': [{'id': i, 'a': a, 'aSide': 'out', 'b': b, 'bSide': 'in'} for i, a, b in WIRES]})
    open_document(page, json.dumps(doc), 'drop-on-wire.sov')
    scale = page.evaluate(SCALE)
    point = press(page, CARD)
    assert point, (name, 'the press starts a drag of', CARD)
    x, y = point
    for k in range(1, MOVES + 1):
        page.mouse.move(x, y + dy * scale * k / MOVES)
    page.wait_for_timeout(REST_MS)
    left = page.evaluate(NODE, CARD)
    page.evaluate(WATCH)
    page.mouse.up()
    clears = page.evaluate(CLEARS)  # read, and the watch removed, before the full redraw below
    pair = page.evaluate(PAIR)
    seen = {'left': left, 'after': page.evaluate(NODE, CARD), 'pair': pair, 'differing': differing(pair),
            'clears': clears, 'state': page.evaluate(STATE)}
    after = seen['after']
    print(f"{name}: pointer left {CARD} at {left['x']:.2f},{left['y']:.2f}; after the release {after['x']:.2f},{after['y']:.2f}, "
          f"placement {after['kind']} {after['wireId'] or ''} t {after['t']}; record of drawn groups emptied {clears} times; "
          f"{len(pair[0])} wire paths, {len(seen['differing'])} differ from the full redraw {seen['differing']}")
    for wire in seen['differing']:
        print(f"  {wire}: left {pair[0][wire]!r}, full redraw {pair[1][wire]!r}")
    return seen


def main() -> None:
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(250)
        page.evaluate('()=>{canvasSnapEnabled=false}')
        hosted = release(page, 'hosted', HOSTED_DY)
        control = release(page, 'control', CONTROL_DY)
        browser.close()

    idle = {'drag': None, 'keyboard': None, 'snapshots': 0}
    left, after = hosted['left'], hosted['after']
    assert len(hosted['pair'][0]) == len(WIRES) and len(control['pair'][0]) == len(WIRES), ('every wire is drawn', hosted['pair'][0], control['pair'][0])
    assert hosted['state'] == idle and control['state'] == idle, ('after release no drag and no snapshots', hosted['state'], control['state'])
    assert after['kind'] == 'wire' and after['wireId'] == HOST_WIRE, ('hosted: the release hosts the card on the wire', after)
    assert max(abs(after['x'] - left['x']), abs(after['y'] - left['y'])) > 1, ('hosted: the host moves the card from where the pointer left it', left, after)
    assert not hosted['differing'], ('hosted: every wire path equals the full redraw', [(w, hosted['pair'][0][w], hosted['pair'][1][w]) for w in hosted['differing']])
    assert control['after']['kind'] == 'surface' and control['after']['parent'] is None, ('control: the release hosts nothing', control['after'])
    assert not control['differing'], ('control: every wire path equals the full redraw', [(w, control['pair'][0][w], control['pair'][1][w]) for w in control['differing']])
    assert control['clears'] == 0, ('control: a release that changes no host never empties the record of drawn groups', control['clears'])
    assert not errors, ('the page logs no errors', errors)
    print('PASS drop on wire redraw QA')


if __name__ == '__main__':
    main()
