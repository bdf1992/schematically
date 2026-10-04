"""Drag redraw parity QA: the wire pass of a move leaves the picture a plain renderWires() draws.

While a card is moved, renderWiresForDrag() (src/55-render.js) computes every route in full and then
keeps each wire group whose inputs did not change, replacing only the others. The oracle is
from-scratch consistency: at one state, the picture P a drag pass leaves must equal the picture Q
that renderWires() draws from nothing at that same state.

The picture is, for every .wire-group in document order: its wire id, index, parent, class, inline
style (the gradient's id aside), data-route-blocked, data-track-cramped, data-bus-fallback,
data-status, the --voltage-ink value and the gradient stop colours; the d and class of path.wire and
the d of path.wire-hit (hops are its arcs); the transform of every .flow-chevron; the d of
.move-tether and cx, cy of .move-anchor; the text, x, y and data-label-crowded of .connection-label;
x, y of .net-badge and .reciprocity-mark; x, y and text of every .endpoint-channel-tag; cx, cy of
every .carrier-end-handle; the marker badges; the count of .wire-packet and of the group's children;
and the transform of every .node. Strings are equal exactly, numbers within 0.01.

Scenarios (headless Chromium, 1600 x 1000, snap off):

- docs/workengine/map.sov, tests/fixtures/task-lifecycle.sov and tests/fixtures/work-engine-sample.sov,
  each dragged by its most wired card: among cards that are neither groups nor containers, the one
  with the most wire ends, ties by id, the first whose press starts a drag.
- 'corridor', planted: act cards p 104,300, q 704,300, d 404,140, e 704,60; wires x0 p-q and x1 d-e.
  p is selected together with d and d is dragged, so p is carried along: x0, neither of whose ends is
  on the dragged card, changes on every step. The test asserts that it does.
- docs/workengine/map.sov again, the same card moved by three arrow keys and left to settle.

Moments of a pointer scenario, P read after the drag pass and Q after renderWires() at each: before
the press; pressed; each of 3 drag steps of 20 px (one step is a pointermove dispatched on window
and flushDragVisualRefresh(), in one evaluate, so the settle timer cannot fire inside it); settled
while held (settleDraggedRoutes() by hand, as scheduleDragSettle does it: that pass draws with the
dragged wires' snapshots removed, so Q is drawn with the snapshots set aside, then they are put back
and captured again); released. After release there is no drag, no snapshot, and no page error.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

DOCUMENTS = [ROOT / 'docs' / 'workengine' / 'map.sov', ROOT / 'tests' / 'fixtures' / 'task-lifecycle.sov',
             ROOT / 'tests' / 'fixtures' / 'work-engine-sample.sov']
STEP_PX, STEPS = 20, 3
CORRIDOR_CARDS = [('p', 104, 300), ('q', 704, 300), ('d', 404, 140), ('e', 704, 60)]
CORRIDOR_WIRES = [('x0', 'p', 'q'), ('x1', 'd', 'e')]

PICTURE = r"""()=>{
  const groups=[...workspace.querySelectorAll('.wire-group')].map(g=>{
    const q=sel=>[...g.querySelectorAll(sel)],at=(el,...names)=>names.map(n=>el.getAttribute(n));
    return {
      id:g.dataset.wireId,index:g.dataset.wireIndex,parent:g.parentNode.id||g.parentNode.tagName,cls:g.getAttribute('class'),
      css:g.style.cssText.replace(/wire-gradient-\d+-\d+/,'gradient'),
      blocked:g.dataset.routeBlocked??null,cramped:g.dataset.trackCramped??null,fallback:g.dataset.busFallback??null,status:g.dataset.status??null,
      ink:g.style.getPropertyValue('--voltage-ink'),stops:q('linearGradient stop').map(s=>s.getAttribute('stop-color')),
      d:g.querySelector('path.wire')?.getAttribute('d')??null,wireCls:g.querySelector('path.wire')?.getAttribute('class')??null,
      hit:g.querySelector('path.wire-hit')?.getAttribute('d')??null,
      chevrons:q('.flow-chevron').map(c=>c.getAttribute('transform')),
      tether:q('.move-tether').map(c=>c.getAttribute('d')),anchor:q('.move-anchor').map(c=>at(c,'cx','cy')),
      label:q('.connection-label').map(t=>[t.textContent,...at(t,'x','y'),t.dataset.labelCrowded??null]),
      badge:q('.net-badge').map(t=>at(t,'x','y')),recip:q('.reciprocity-mark').map(t=>at(t,'x','y')),
      tags:q('.endpoint-channel-tag').map(t=>[...at(t,'x','y'),t.textContent]),
      handles:q('.carrier-end-handle').map(t=>at(t,'cx','cy')),
      markers:q('.marker-badge').map(t=>at(t,'transform','title')),
      packets:q('.wire-packet').length,children:g.children.length,
    };
  });
  return {groups,nodes:[...workspace.querySelectorAll('.node')].map(n=>[n.dataset.id,n.getAttribute('transform')])};
}"""

# P is what the drag pass left; Q is what a pass from nothing draws at the same state.
PAIR = "()=>{const picture=" + PICTURE + ";const P=picture();renderWires();return [P,picture()]}"
BEFORE = "()=>{renderWiresForDrag();return (" + PAIR + ")()}"
PRESSED = "()=>{flushDragVisualRefresh();return (" + PAIR + ")()}"
# One drag step: the app's own pointermove handler and one frame pass. Returns its milliseconds.
DRAG_STEP = r"""([x,y])=>{
  const state=activeNodeDragState;if(!state)throw new Error('no drag in progress');
  const start=performance.now();
  window.dispatchEvent(new PointerEvent('pointermove',{pointerId:state.pointerId,pointerType:'mouse',buttons:1,bubbles:true,clientX:x,clientY:y}));
  flushDragVisualRefresh();
  return performance.now()-start;
}"""
# The hand-run settle below is the only one: the timer a step set is cleared with the step.
STEP = "(at)=>{(" + DRAG_STEP + ")(at);if(settleTimer){clearTimeout(settleTimer);settleTimer=null}return (" + PAIR + ")()}"
SETTLED = r"""(card)=>{
  const picture=PICTURE;
  if(settleTimer){clearTimeout(settleTimer);settleTimer=null}
  settleDraggedRoutes();
  const P=picture(),kept=[...dragRouteSnapshots];
  dragRouteSnapshots.clear();renderWires();
  const Q=picture();
  for(const [i,s] of kept)dragRouteSnapshots.set(i,s);
  captureDragSnapshots(card);
  return [P,Q];
}""".replace('PICTURE', PICTURE)
ARROW = r"""(card)=>{
  const picture=PICTURE,n=nodes.find(q=>q.id===card),y=n.y;
  document.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',code:'ArrowDown',bubbles:true,cancelable:true}));
  const moving=keyboardMoveNodeId,dy=n.y-y,P=picture();
  renderWires();
  return {moving,dy,pair:[P,picture()]};
}""".replace('PICTURE', PICTURE)
CANDIDATES = r"""()=>{
  const ends=new Map();
  for(const w of wires)for(const id of [w.a,w.b])if(id)ends.set(id,(ends.get(id)||0)+1);
  return nodes.filter(n=>!isGroupComponent(n)&&!componentAcceptsChildren(n))
    .map(n=>({id:n.id,ends:ends.get(n.id)||0})).sort((p,q)=>q.ends-p.ends||(p.id<q.id?-1:p.id>q.id?1:0)).map(c=>c.id);
}"""
STATE = '()=>({drag:activeNodeDrag,keyboard:keyboardMoveNodeId,snapshots:dragRouteSnapshots.size})'
NUMBER = re.compile(r'-?\d+(?:\.\d+)?(?:e[-+]?\d+)?')


def differences(a, b, path='', out=None, limit=5):
    """Where two pictures differ: strings exactly, numbers (also inside strings) within 0.01."""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict) and set(a) == set(b):
        for k in sorted(a):
            differences(a[k], b[k], f'{path}/{k}', out, limit)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((f'{path} length', len(a), len(b)))
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                differences(x, y, f'{path}[{i}]', out, limit)
    elif isinstance(a, str) and isinstance(b, str):
        if a != b:
            na, nb = NUMBER.findall(a), NUMBER.findall(b)
            if NUMBER.sub('#', a) != NUMBER.sub('#', b) or any(abs(float(x) - float(y)) > .01 for x, y in zip(na, nb)):
                out.append((path, a, b))
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        if abs(a - b) > .01:
            out.append((path, a, b))
    elif a != b:
        out.append((path, a, b))
    return out


def open_document(page, text: str, name: str) -> None:
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [text, name])
    page.evaluate('()=>fitDiagram()')
    page.wait_for_timeout(300)
    page.evaluate('()=>{canvasSnapEnabled=false}')


def press(page, card: str):
    """Press the centre of a card's box; the point pressed when that starts a drag of it, else None."""
    box = page.locator(f'.node[data-id="{card}"]').first.bounding_box() if page.locator(f'.node[data-id="{card}"]').count() else None
    if not box:
        return None
    x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    if page.evaluate('()=>activeNodeDrag') == card:
        return x, y
    page.mouse.up()
    page.wait_for_timeout(300)
    return None


def press_most_wired(page):
    """Press the most wired card that is neither a group nor a container (ties by id, the first whose
    press starts a drag). Returns its id and the point pressed."""
    for card in page.evaluate(CANDIDATES):
        at = press(page, card)
        if at:
            return card, at
    raise AssertionError('no card of the document starts a drag when pressed')


def wire_d(picture, wire: str):
    return next(g['d'] for g in picture['groups'] if g['id'] == wire)


def pointer_scenario(page, name: str, card: str | None, check) -> dict:
    """The moments of one pointer drag; check(moment, [P, Q]) is called at each. Returns P by moment."""
    seen = {}

    def at(moment, pair):
        seen[moment] = pair[0]
        check(f'{name}: {moment}', pair)

    at('before the press', page.evaluate(BEFORE))
    if card is None:
        card, (x, y) = press_most_wired(page)
    else:
        point = press(page, card)
        assert point, (name, 'the press starts a drag of', card)
        x, y = point
    at('pressed', page.evaluate(PRESSED))
    for k in range(1, STEPS + 1):
        at(f'step {k}', page.evaluate(STEP, [x, y + STEP_PX * k]))
    at('settled while held', page.evaluate(SETTLED, card))
    page.mouse.up()
    page.wait_for_timeout(300)
    at('released', page.evaluate(PAIR))
    state = page.evaluate(STATE)
    assert state == {'drag': None, 'keyboard': None, 'snapshots': 0}, (name, 'after release no drag and no snapshots', state)
    seen['card'] = card
    return seen


def main() -> None:
    errors: list[str] = []
    failures: list = []
    counts: dict[str, int] = {}

    def check(moment, pair):
        found = differences(pair[0], pair[1])
        counts[moment] = len(pair[0]['groups'])
        if found:
            failures.append((moment, found[0]))

    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(250)
        page.evaluate('()=>{canvasSnapEnabled=false}')

        cards = {}
        for path in DOCUMENTS:
            open_document(page, path.read_text(encoding='utf-8'), path.name)
            cards[path.name] = pointer_scenario(page, path.name, None, check)['card']

        doc = page.evaluate('()=>({schema:SovSchematicData.DOCUMENT_SCHEMA})')
        doc.update({'id': 'corridor', 'components': [{'id': i, 'symbolId': 'act', 'x': x, 'y': y} for i, x, y in CORRIDOR_CARDS],
                    'wires': [{'id': i, 'a': a, 'aSide': 'out', 'b': b, 'bSide': 'in'} for i, a, b in CORRIDOR_WIRES]})
        open_document(page, json.dumps(doc), 'corridor.sov')
        page.evaluate("()=>{selectNode('p');selectNode('d',{additive:true})}")
        corridor = pointer_scenario(page, 'corridor', 'd', check)
        hosts = page.evaluate("()=>nodes.map(n=>[n.id,n.parentId||null,n.placement?.kind||'surface'])")

        # The same card of the map, moved by the arrow keys and left to settle.
        path = DOCUMENTS[0]
        open_document(page, path.read_text(encoding='utf-8'), path.name)
        card = cards[path.name]
        page.evaluate('(id)=>selectNode(id)', card)
        check('map.sov by keyboard: before the move', page.evaluate(BEFORE))
        arrows = []
        for k in range(1, STEPS + 1):
            moved = page.evaluate(ARROW, card)
            arrows.append((moved['moving'], moved['dy']))
            check(f'map.sov by keyboard: arrow {k}', moved['pair'])
        page.wait_for_timeout(500)
        keyboard_state = page.evaluate(STATE)
        check('map.sov by keyboard: settled', page.evaluate(PAIR))
        browser.close()

    for name, dragged in cards.items():
        print(f'{name}: dragged {dragged}')
    pressed_d, last_d = wire_d(corridor['pressed'], 'x0'), wire_d(corridor[f'step {STEPS}'], 'x0')
    print(f'corridor: x0 pressed {pressed_d!r}, at step {STEPS} {last_d!r}')
    print(f'map.sov by keyboard: {card}, arrows (moving, dy) {arrows}')
    print(f'{len(counts)} moments compared, {sum(counts.values())} wire groups in all, {len(failures)} moments differ')

    assert not errors, ('the page logs no errors', errors)
    assert not failures, ('the picture a drag pass leaves equals the picture renderWires() draws', failures[:3])
    assert pressed_d != last_d, ('corridor: x0 is not on the dragged card and changes during the move', pressed_d, last_d)
    assert all(parent is None and kind == 'surface' for _, parent, kind in hosts), ('corridor: the release changes no host', hosts)
    assert all(moving == card and dy > 0 for moving, dy in arrows), ('map.sov by keyboard: each arrow moves the card inside a keyboard move', arrows)
    assert keyboard_state == {'drag': None, 'keyboard': None, 'snapshots': 0}, ('map.sov by keyboard: the move has settled', keyboard_state)
    print('PASS drag redraw parity QA')


if __name__ == '__main__':
    main()
