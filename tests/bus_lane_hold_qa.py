"""Bus lane hold QA: while a card is moved the lanes of a bus keep the order they had at the press.

Ordering the lanes of every bus is a batch step (src/41-buses.js busRoutesForRender: the natural
order, its reverse, the swap passes, the sifting). While a card is moved that order is held from the
press; it is computed again when the pointer rests (settleDraggedRoutes) and when the move ends
(LAYOUT-MODEL.md "As built: buses", Lane order). Plans and routes are still built on every step.

The planted document (headless Chromium, 1600 x 1000): act cards s1 104,100, s2 104,300, s3 104,500,
t1 912,360, t2 704,400, t3 704,560; wires w1 s1-t1, w2 s2-t2, w3 s3-t3, all on one bus 'trunk' from
400,0 to 400,700, pitch 6, a lane per wire. t1 is dragged down 3 steps of 20 px and passes t2, so
w1 leaves the trunk after w2 where it left before it.

    On the base (dev at e02d27f, before the hold), lanes of 'trunk' by pointer:
        pressed    w1 w2 w3
        step 1     w1 w2 w3
        step 2     w2 w1 w3      <- re-ordered during the move
        step 3     w2 w1 w3
        released   w2 w1 w3
    and by three ArrowDown keys of 24 (snap on): before w1 w2 w3, after arrow 1 w1 w2 w3, after
    arrows 2 and 3 w2 w1 w3, settled w2 w1 w3.

Asserted, and printed:

(a) the lane order after each drag step equals the order at the press;
(b) at each step every bus wire's route still ends on its cards' ports: the first and last point of
    its route (busRoutesForRender().routes) equal carrierEndpointPos within 0.01;
(c) after settleDraggedRoutes() while held, the lane order equals the order of a second page that
    opens the same positions from nothing, and differs from the order at the press; the snapshots
    are then captured again, as scheduleDragSettle does, and the order held from there is that one;
(d) after release the picture (tests/drag_redraw_parity_qa.py PICTURE) equals the picture of a
    second page that opens the released positions from nothing: strings exactly, numbers within 0.01;
(e) the same four when t1 is moved by three ArrowDown keys (snap on, 24 a key, dispatched in one
    evaluate so the settle timer cannot fire between them) and left to settle;
(f) on docs/workengine/map.sov, the most wired card dragged 5 steps of 20 px: the lane order of
    every bus at each step equals the order at the press, and at the settle and after release it
    equals the order of a second page holding the map with every card at the same position;
(g) neither page logs an error.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402
from drag_redraw_parity_qa import DRAG_STEP, PICTURE, differences, open_document, press, press_most_wired  # noqa: E402

INDEX = ROOT / 'index.html'
MAP = ROOT / 'docs' / 'workengine' / 'map.sov'
CARDS = [('s1', 104, 100), ('s2', 104, 300), ('s3', 104, 500), ('t1', 912, 360), ('t2', 704, 400), ('t3', 704, 560)]
WIRES = [('w1', 's1', 't1'), ('w2', 's2', 't2'), ('w3', 's3', 't3')]
TRUNK = [{'x': 400, 'y': 0}, {'x': 400, 'y': 700}]
CARD, STEP_PX, STEPS, MAP_STEPS, ARROWS = 't1', 20, 3, 5, 3

LANES = "()=>Object.fromEntries([...busRoutesForRender().lanes].map(([bus,L])=>[bus,[...L]]))"
# How far each bus wire's route ends from its two ports: the larger of the four coordinate gaps.
ENDS = r"""()=>wires.filter(w=>busSpecOf(w)).map(w=>{
  const r=busRoutesForRender().routes.get(w.id),A=carrierEndpointPos(w,'a'),B=carrierEndpointPos(w,'b');
  return [w.id,r&&A&&B?Math.max(Math.abs(r[0].x-A.x),Math.abs(r[0].y-A.y),Math.abs(r.at(-1).x-B.x),Math.abs(r.at(-1).y-B.y)):null];
})"""
POSITIONS = "()=>nodes.map(n=>[n.id,n.x,n.y])"
PLANT = r"""([points,ids])=>{
  const made=SovSchematicAPI.layout.bus({id:'trunk',points,pitch:6});
  const routed=ids.map(id=>SovSchematicAPI.layout.route(id,{mode:'bus',buses:['trunk']}));
  render();
  return {refused:[made,...routed].filter(r=>!r||r.ok===false),fallback:[...busRoutesForRender().fallback]};
}"""
PRESSED = "()=>{flushDragVisualRefresh();return (" + LANES + ")()}"
# One drag step (the app's pointermove handler and one frame pass); the settle timer it set is cleared.
STEP = ("(at)=>{(" + DRAG_STEP + ")(at);if(settleTimer){clearTimeout(settleTimer);settleTimer=null}"
        "return {lanes:(" + LANES + ")(),ends:(" + ENDS + ")()}}")
# The settle while held, by hand as scheduleDragSettle does it: settle, then capture again.
SETTLE = ("(card)=>{if(settleTimer){clearTimeout(settleTimer);settleTimer=null}settleDraggedRoutes();"
          "const lanes=(" + LANES + ")(),positions=(" + POSITIONS + ")();"
          "captureDragSnapshots(card);flushDragVisualRefresh();return {lanes,positions,held:(" + LANES + ")()}}")
RELEASED = "()=>({lanes:(" + LANES + ")(),positions:(" + POSITIONS + ")(),picture:(" + PICTURE + ")()})"
# Three arrow keys in one evaluate, so the keyboard settle timer cannot fire between them.
ARROW_KEYS = r"""([card,count])=>{
  const lanes=LANES,ends=ENDS,n=nodes.find(q=>q.id===card),out={before:lanes(),y:[n.y],moving:[],steps:[]};
  for(let k=0;k<count;k++){
    document.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',code:'ArrowDown',bubbles:true,cancelable:true}));
    out.moving.push(keyboardMoveNodeId);out.y.push(n.y);out.steps.push({lanes:lanes(),ends:ends()});
  }
  return out;
}""".replace('LANES', LANES).replace('ENDS', ENDS)
AT_POSITIONS = ("(positions)=>{for(const [id,x,y] of positions){const n=nodes.find(q=>q.id===id);if(n){n.x=x;n.y=y}}"
                "return (" + LANES + ")()}")
STATE = '()=>({drag:activeNodeDrag,keyboard:keyboardMoveNodeId,snapshots:dragRouteSnapshots.size})'


def plant(page, positions=None, selected=None, snap=False) -> None:
    """Open the planted document from nothing, the cards at positions (id to x, y) when given."""
    at = {i: (x, y) for i, x, y in CARDS}
    at.update(positions or {})
    doc = page.evaluate('()=>({schema:SovSchematicData.DOCUMENT_SCHEMA})')
    doc.update({'id': 'lane-hold', 'components': [{'id': i, 'symbolId': 'act', 'x': at[i][0], 'y': at[i][1]} for i, _, _ in CARDS],
                'wires': [{'id': i, 'a': a, 'aSide': 'out', 'b': b, 'bSide': 'in'} for i, a, b in WIRES]})
    open_document(page, json.dumps(doc), 'lane-hold.sov')
    planted = page.evaluate(PLANT, [TRUNK, [w[0] for w in WIRES]])
    assert not planted['refused'] and not planted['fallback'], ('the bus and its three routes are planted', planted)
    page.evaluate('()=>fitDiagram()')
    page.wait_for_timeout(300)
    if selected:
        page.evaluate('(id)=>selectNode(id)', selected)
    page.evaluate('(on)=>{canvasSnapEnabled=on}', snap)


def short(lanes: dict) -> str:
    return '; '.join(f"{bus}: {' '.join(k.replace('wire:', '') for k in order)}" for bus, order in sorted(lanes.items()))


def worst_end(ends) -> float:
    return max((gap if gap is not None else float('inf')) for _, gap in ends)


def main() -> None:
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))

        def new_page():
            page = browser.new_page(viewport={'width': 1600, 'height': 1000})
            page.on('pageerror', lambda exc: errors.append(str(exc)))
            page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
            page.set_content(INDEX.read_text(encoding='utf-8'), wait_until='load')
            page.wait_for_timeout(250)
            return page

        page, fresh = new_page(), new_page()

        # By pointer.
        plant(page)
        point = press(page, CARD)
        assert point, ('the press starts a drag of', CARD)
        x, y = point
        pressed = page.evaluate(PRESSED)
        steps = [page.evaluate(STEP, [x, y + STEP_PX * k]) for k in range(1, STEPS + 1)]
        settled = page.evaluate(SETTLE, CARD)
        page.mouse.up()
        page.wait_for_timeout(300)
        released = page.evaluate(RELEASED)
        pointer_state = page.evaluate(STATE)
        plant(fresh, {i: (px, py) for i, px, py in settled['positions']})
        settled_fresh = fresh.evaluate(LANES)
        plant(fresh, {i: (px, py) for i, px, py in released['positions']}, selected=CARD)
        released_fresh = fresh.evaluate(RELEASED)

        # By three arrow keys, left to settle.
        plant(page, selected=CARD, snap=True)
        keys = page.evaluate(ARROW_KEYS, [CARD, ARROWS])
        page.wait_for_timeout(500)
        key_settled = page.evaluate(RELEASED)
        key_state = page.evaluate(STATE)
        plant(fresh, {i: (px, py) for i, px, py in key_settled['positions']}, selected=CARD)
        key_fresh = fresh.evaluate(RELEASED)

        # The Work Engine map.
        text = MAP.read_text(encoding='utf-8')
        open_document(page, text, MAP.name)
        map_card, (mx, my) = press_most_wired(page)
        map_pressed = page.evaluate(PRESSED)
        map_steps = [page.evaluate(STEP, [mx, my + STEP_PX * k])['lanes'] for k in range(1, MAP_STEPS + 1)]
        map_settled = page.evaluate(SETTLE, map_card)
        page.mouse.up()
        page.wait_for_timeout(300)
        map_released = page.evaluate("()=>({lanes:(" + LANES + ")(),positions:(" + POSITIONS + ")()})")
        open_document(fresh, text, MAP.name)
        map_settled_fresh = fresh.evaluate(AT_POSITIONS, map_settled['positions'])
        map_released_fresh = fresh.evaluate(AT_POSITIONS, map_released['positions'])
        browser.close()

    print(f'planted, {CARD} by pointer: pressed [{short(pressed)}]')
    for k, step in enumerate(steps, 1):
        print(f'  step {k}: [{short(step["lanes"])}]; farthest route end from its port {worst_end(step["ends"]):.4f}')
    print(f'  settled while held: [{short(settled["lanes"])}]; from nothing [{short(settled_fresh)}]; held from there [{short(settled["held"])}]')
    picture_gap = differences(released['picture'], released_fresh['picture'])
    print(f'  released: [{short(released["lanes"])}]; from nothing [{short(released_fresh["lanes"])}]; '
          f'{len(released["picture"]["groups"])} wire groups, {len(picture_gap)} differences from the picture from nothing')
    print(f'planted, {CARD} by {ARROWS} arrow keys: before [{short(keys["before"])}], y {keys["y"]}')
    for k, step in enumerate(keys['steps'], 1):
        print(f'  arrow {k}: [{short(step["lanes"])}]; farthest route end from its port {worst_end(step["ends"]):.4f}')
    key_gap = differences(key_settled['picture'], key_fresh['picture'])
    print(f'  settled: [{short(key_settled["lanes"])}]; from nothing [{short(key_fresh["lanes"])}]; '
          f'{len(key_settled["picture"]["groups"])} wire groups, {len(key_gap)} differences from the picture from nothing')
    moved_on_map = [k for k, lanes in enumerate(map_steps, 1) if lanes != map_pressed]
    print(f'map.sov, {map_card}: {len(map_pressed)} buses, {sum(len(v) for v in map_pressed.values())} lanes; '
          f'steps whose lane order differs from the press {moved_on_map}; settled equals from nothing '
          f'{map_settled["lanes"] == map_settled_fresh}; released equals from nothing {map_released["lanes"] == map_released_fresh}')

    # (g)
    assert not errors, ('the pages log no errors', errors)
    # (a)
    assert len(pressed['trunk']) >= 3, ('the planted bus has at least three lanes', pressed)
    for k, step in enumerate(steps, 1):
        assert step['lanes'] == pressed, ('(a) the lane order at a drag step is the order at the press', k, step['lanes'], pressed)
    # (b)
    for k, step in enumerate(steps, 1):
        assert worst_end(step['ends']) <= .01, ('(b) every bus route ends on its ports at a drag step', k, step['ends'])
    # (c)
    assert settled['lanes'] == settled_fresh, ('(c) settled while held, the lane order is the order from nothing', settled['lanes'], settled_fresh)
    assert settled['lanes'] != pressed, ('(c) the settled lane order differs from the order at the press', settled['lanes'], pressed)
    assert settled['held'] == settled['lanes'], ('(c) the order held after the settle is the settled one', settled['held'], settled['lanes'])
    # (d)
    assert pointer_state == {'drag': None, 'keyboard': None, 'snapshots': 0}, ('after release no drag and no snapshots', pointer_state)
    assert released['lanes'] == released_fresh['lanes'], ('(d) released, the lane order is the order from nothing', released['lanes'], released_fresh['lanes'])
    assert not picture_gap, ('(d) released, the picture is the picture from nothing', picture_gap[:3])
    # (e)
    assert all(m == CARD for m in keys['moving']) and keys['y'][-1] > keys['y'][0], ('(e) each arrow moves the card inside one keyboard move', keys['moving'], keys['y'])
    for k, step in enumerate(keys['steps'], 1):
        assert step['lanes'] == keys['before'], ('(e, a) the lane order after an arrow key is the order before the move', k, step['lanes'], keys['before'])
        assert worst_end(step['ends']) <= .01, ('(e, b) every bus route ends on its ports after an arrow key', k, step['ends'])
    assert key_state == {'drag': None, 'keyboard': None, 'snapshots': 0}, ('(e) the keyboard move has settled', key_state)
    assert key_settled['lanes'] == key_fresh['lanes'], ('(e, c) settled, the lane order is the order from nothing', key_settled['lanes'], key_fresh['lanes'])
    assert key_settled['lanes'] != keys['before'], ('(e, c) the settled lane order differs from the order before the move', key_settled['lanes'], keys['before'])
    assert not key_gap, ('(e, d) settled, the picture is the picture from nothing', key_gap[:3])
    # (f)
    assert not moved_on_map, ('(f) on the map the lane order of every bus at each step is the order at the press', moved_on_map)
    assert map_settled['lanes'] == map_settled_fresh, ('(f) on the map, settled while held, the lane order is the order from nothing',
                                                       [b for b in map_settled_fresh if map_settled['lanes'].get(b) != map_settled_fresh[b]])
    assert map_released['lanes'] == map_released_fresh, ('(f) on the map, released, the lane order is the order from nothing',
                                                         [b for b in map_released_fresh if map_released['lanes'].get(b) != map_released_fresh[b]])
    print('PASS bus lane hold QA')


if __name__ == '__main__':
    main()
