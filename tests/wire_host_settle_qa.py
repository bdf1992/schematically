"""Wire host settle QA: one wire pass places the cards hosted on a wire before it routes their wires.

A card on a wire takes its pose from the host wire's drawn path (renderWires, poseHosted,
src/55-render.js), which exists only after every route of that pass was found. The card's own wires
were among those routes, so they end where the card stood before the pass moved it. The wire pass
therefore repeats: renderWires calls renderWiresOnce, and while a pass moved a hosted card it routes
that card's wires again and runs the pass once more, at most 3 more times. The oracle is from-scratch
consistency, as in tests/drag_redraw_parity_qa.py and tests/drop_on_wire_redraw_qa.py: straight after
an act, the d of every path.wire equals the d drawn with the route cache, the arrow pose cache and the
record of drawn groups cleared.

Planted document (headless Chromium, 1600 x 1000, snap off), as in tests/drop_on_wire_redraw_qa.py:
act cards p 404,300, q 1204,300, c 464,140, e 1204,100, f 104,140; wires x0 p-q, x1 c-e and x2 f-c.
Five scenarios, each on the document opened afresh:

- (a) pointer drop: c pressed, moved 170 down in 6 pointer moves, rested 700 ms, released onto x0.
- (b) keyboard: c selected, ArrowDown keydown events dispatched on document until c.y is 289, then
  700 ms, so the keyboard move settles and hosts c on x0.
- (c) host reroute: the document opened with c stored on x0 (canvasId canvas:wire:x0, placement kind
  wire, wireId x0, t 0.5), then SovSchematicAPI.update('component','p',{y:520}).
- (d) host end dragged: the document of (c), p pressed, moved 220 down in 6 pointer moves, rested
  700 ms, released.
- (e) control: c pressed, moved 60 down, rested and released, hosting nothing.

The passes are counted from the test's side: renderWires and renderWiresOnce are wrapped as globals
for the act, each renderWires call recording how many cards each of its renderWiresOnce passes moved,
and the wraps are removed before the oracle runs. The product code carries no counter. On a tree with
no renderWiresOnce the count reads 0.

Asserted for (a) to (d): c's placement is kind wire on x0; 0 wire paths differ from the full redraw;
a second full redraw changes no path; no drag, no keyboard move and no snapshots remain; within one
renderWires call, the renderWiresOnce passes after the first number at most 3 and each follows a pass
that moved a hosted card. For (e): c stays on the surface, 0 paths differ, a second full redraw
changes no path, and every renderWires call of the act ran renderWiresOnce exactly once. The page logs
no errors.
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
CARD, HOST_WIRE, HOST_END = 'c', 'x0', 'p'
DROP_DY, CONTROL_DY, HOST_END_DY, MOVES = 170, 60, 220, 6
KEYBOARD_Y, REROUTE_Y, STORED_T = 289, 520, 0.5
REST_MS = 700  # past HOST_ADOPT_DWELL (280) and ROUTE_SETTLE_DELAY (140)
FOLLOWING_LIMIT = 3

WIRE_D = "()=>Object.fromEntries([...workspace.querySelectorAll('.wire-group')].map(g=>[g.dataset.wireId,g.querySelector('path.wire')?.getAttribute('d')??null]))"
# P is what the act left; Q is what a pass from nothing draws at the same state, no cache kept; R is
# the same pass from nothing run once more.
TRIPLE = ("()=>{const read=" + WIRE_D + ";const full=()=>{routeCache.clear();arrowPoseCache.clear();wireGroupDrawn.clear();renderWires();return read()};"
          "const P=read(),Q=full(),R=full();return [P,Q,R]}")
NODE = "(id)=>{const n=nodes.find(q=>q.id===id);return {x:n.x,y:n.y,kind:n.placement?.kind||'surface',wireId:n.placement?.wireId||null,t:n.placement?.t??null,parent:n.parentId||null}}"
SCALE = '()=>{const a=svgPoint(0,0),b=svgPoint(100,0);return 100/(b.x-a.x)}'
STATE = '()=>({drag:activeNodeDrag,keyboard:keyboardMoveNodeId,snapshots:dragRouteSnapshots.size})'
# Counted from the test's side. calls holds one list per renderWires call: how many hosted cards each
# of its renderWiresOnce passes moved, in order. With no renderWiresOnce every list stays empty.
WATCH = r"""()=>{
  const log=window.wireHostSettle={calls:[],full:window.renderWires,once:typeof renderWiresOnce==='function'?window.renderWiresOnce:null};
  window.renderWires=function(...args){log.calls.push([]);return log.full.apply(this,args)};
  if(log.once)window.renderWiresOnce=function(...args){
    const moved=log.once.apply(this,args);
    if(!log.calls.length)log.calls.push([]);
    log.calls.at(-1).push(moved&&typeof moved.size==='number'?moved.size:0);
    return moved;
  };
}"""
UNWATCH = r"""()=>{
  const log=window.wireHostSettle;
  window.renderWires=log.full;if(log.once)window.renderWiresOnce=log.once;
  delete window.wireHostSettle;
  return log.calls;
}"""
ARROWS = r"""([card,y])=>{
  selectNode(card);
  const n=nodes.find(q=>q.id===card);let presses=0;
  while(n.y<y-1e-6&&presses<1000){
    document.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',code:'ArrowDown',bubbles:true,cancelable:true}));
    presses++;
  }
  return {presses,y:n.y,moving:keyboardMoveNodeId};
}"""
IDLE = {'drag': None, 'keyboard': None, 'snapshots': 0}


def differing(left: dict, full: dict) -> list[str]:
    """The wires whose d differs between two readings, compared as the parity test does."""
    assert set(left) == set(full), ('the same wires in both readings', sorted(left), sorted(full))
    return [wire for wire in sorted(left) if differences(left[wire], full[wire])]


def plant(page, stored_on_wire: bool) -> float:
    """Open the planted document afresh; with stored_on_wire the card is saved on the host wire. The scale."""
    doc = page.evaluate('()=>({schema:SovSchematicData.DOCUMENT_SCHEMA})')
    components = [{'id': i, 'symbolId': 'act', 'x': x, 'y': y} for i, x, y in CARDS]
    if stored_on_wire:
        card = next(c for c in components if c['id'] == CARD)
        card.update({'canvasId': f'canvas:wire:{HOST_WIRE}', 'placement': {'kind': 'wire', 'wireId': HOST_WIRE, 't': STORED_T}})
    doc.update({'id': 'wire-host-settle', 'components': components,
                'wires': [{'id': i, 'a': a, 'aSide': 'out', 'b': b, 'bSide': 'in'} for i, a, b in WIRES]})
    open_document(page, json.dumps(doc), 'wire-host-settle.sov')
    return page.evaluate(SCALE)


def pointer_drag(page, name: str, card: str, dy: float, scale: float) -> None:
    point = press(page, card)
    assert point, (name, 'the press starts a drag of', card)
    x, y = point
    for k in range(1, MOVES + 1):
        page.mouse.move(x, y + dy * scale * k / MOVES)
    page.wait_for_timeout(REST_MS)
    page.mouse.up()


def scenario(page, name: str, stored_on_wire: bool, act) -> dict:
    """One scenario on the document opened afresh: the act under the watch, then the oracle."""
    scale = plant(page, stored_on_wire)
    before = page.evaluate(NODE, CARD)
    page.evaluate(WATCH)
    note = act(scale)
    calls = page.evaluate(UNWATCH)  # read, and the wraps removed, before the full redraws below
    after = page.evaluate(NODE, CARD)
    left, full, again = page.evaluate(TRIPLE)
    seen = {'name': name, 'before': before, 'after': after, 'left': left, 'full': full, 'differing': differing(left, full),
            'unsettled': differing(full, again), 'calls': calls, 'once': sum(len(c) for c in calls),
            'state': page.evaluate(STATE), 'note': note}
    following = [len(c) - 1 for c in calls if len(c) > 1]
    print(f"{name}: {CARD} stood at {before['x']:.2f},{before['y']:.2f} and stands at {after['x']:.2f},{after['y']:.2f}, "
          f"placement {after['kind']} {after['wireId'] or ''} t {after['t']}{note or ''}; "
          f"{len(left)} wire paths, {len(seen['differing'])} differ from the full redraw {seen['differing']}; "
          f"a second full redraw changes {len(seen['unsettled'])} {seen['unsettled']}; "
          f"renderWires called {len(calls)} times, renderWiresOnce {seen['once']} times, "
          f"{sum(following)} of them following a pass that moved a hosted card (most in one call {max(following, default=0)})")
    for wire in seen['differing']:
        print(f"  {wire}: left {left[wire]!r}, full redraw {full[wire]!r}")
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
        has_once = page.evaluate("()=>typeof renderWiresOnce==='function'")

        def keyboard(_scale):
            moved = page.evaluate(ARROWS, [CARD, KEYBOARD_Y])
            page.wait_for_timeout(REST_MS)
            return f", {moved['presses']} ArrowDown presses to y {moved['y']:.2f}"

        def reroute(_scale):
            page.evaluate("([id,y])=>{SovSchematicAPI.update('component',id,{y})}", [HOST_END, REROUTE_Y])
            return f", {HOST_END} at y {page.evaluate(NODE, HOST_END)['y']:.2f}"

        def host_end(scale):
            pointer_drag(page, '(d) host end dragged', HOST_END, HOST_END_DY, scale)
            at = page.evaluate(NODE, HOST_END)
            return f", {HOST_END} at {at['x']:.2f},{at['y']:.2f}"

        seen = [
            scenario(page, '(a) pointer drop', False, lambda scale: pointer_drag(page, '(a) pointer drop', CARD, DROP_DY, scale)),
            scenario(page, '(b) keyboard', False, keyboard),
            scenario(page, '(c) host reroute', True, reroute),
            scenario(page, '(d) host end dragged', True, host_end),
            scenario(page, '(e) control', False, lambda scale: pointer_drag(page, '(e) control', CARD, CONTROL_DY, scale)),
        ]
        browser.close()

    print(f"renderWiresOnce {'exists' if has_once else 'does not exist: its count reads 0'}")
    failures: list = []

    def check(ok, *what):
        if not ok:
            failures.append(what)

    *hosting, control = seen
    for s in seen:
        name = s['name']
        check(len(s['left']) == len(WIRES), name, 'every wire is drawn', s['left'])
        check(s['state'] == IDLE, name, 'no drag, no keyboard move and no snapshots remain', s['state'])
        check(not s['differing'], name, 'every wire path equals the full redraw', [(w, s['left'][w], s['full'][w]) for w in s['differing']])
        check(not s['unsettled'], name, 'a second full redraw changes no path', s['unsettled'])
        check(len(s['calls']) > 0, name, 'the act runs a wire pass', s['calls'])
    for s in hosting:
        name, after = s['name'], s['after']
        check(after['kind'] == 'wire' and after['wireId'] == HOST_WIRE, name, 'the card is hosted on the wire', after)
        check(all(len(c) >= 1 for c in s['calls']), name, 'every renderWires call runs renderWiresOnce', s['calls'])
        check(all(len(c) - 1 <= FOLLOWING_LIMIT for c in s['calls']), name, 'at most 3 passes follow in one renderWires call', s['calls'])
        check(all(c[k - 1] > 0 for c in s['calls'] for k in range(1, len(c))), name, 'a following pass follows a pass that moved a hosted card', s['calls'])
    check(control['after']['kind'] == 'surface' and control['after']['parent'] is None, control['name'], 'the release hosts nothing', control['after'])
    check(all(len(c) == 1 for c in control['calls']), control['name'], 'every renderWires call ran renderWiresOnce exactly once', control['calls'])
    check(not errors, 'the page logs no errors', errors)
    for what in failures:
        print('FAIL', what)
    assert not failures, (f'{len(failures)} assertions failed', failures[0])
    print('PASS wire host settle QA')


if __name__ == '__main__':
    main()
