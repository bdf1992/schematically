"""Wire travel QA: a wire that takes a new route when a move settles travels there, it does not jump.

When a move settles (settleDraggedRoutes, src/40-routing.js) the wire pass draws every wire group at
its new route at once, as it always has: the d of path.wire is final in that pass. For each wire
whose route changed, startWireTravel (src/55-render.js) then adds one path.wire-travel to the group
on the next animation frame and moves it from the old route to the new one with a cubic ease out,
over 180 ms counted from the settle pass. While it moves the group carries data-travel, which hides the stroke of path.wire and the
direction marks (styles/app.css). Under prefers-reduced-motion nothing travels.

Planted through SovSchematicAPI.create (headless Chromium, 1600 x 1000, snap off): act cards a at
300,300 and b at 700,300 and wire w1 from a out to b in.

(a) b is pressed, moved 240 px down in 6 pointer moves and released. From the release every animation
    frame is sampled for 600 ms: a path.wire-travel is seen on at least 3 frames with at least 3
    different d values, and on those frames the stroke of path.wire is hidden.
(b) The d of path.wire is the same on every sampled frame and equals the d a pass from nothing draws.
(c) The middle of the travel path (the mean of its two central points) never moves away from the
    middle of the final path.wire by more than 0.5 from one frame to the next, and ends under 1 from it.
(d) After the 600 ms no .wire-travel exists, no .wire-group carries data-travel, and the computed
    stroke-opacity of path.wire is 1.
(e) Under reduced motion the same drag shows no .wire-travel on any frame.
(f) b is selected and moved by 30 ArrowDown keys; frames sampled for 900 ms show a path.wire-travel
    on at least 3 frames.
(g) The page logs no error.
(h) The 180 ms count from the settle pass. With every animation frame held back 250 ms from the
    test's side, so the first frame after the settle comes too late, the same drag adds no
    .wire-travel at any time (a MutationObserver counts them) and the wire is at its redrawn route.
"""
from __future__ import annotations
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402
from drag_redraw_parity_qa import open_document, press  # noqa: E402

DRAG_PX, MOVES = 240, 6
ARROWS = 30
PLANT = r"""()=>[
  SovSchematicAPI.create('component',{id:'a',symbolId:'act',x:300,y:300}),
  SovSchematicAPI.create('component',{id:'b',symbolId:'act',x:700,y:300}),
  SovSchematicAPI.create('wire',{id:'w1',a:'a',aSide:'out',b:'b',bSide:'in'}),
].map(r=>!!r&&r.ok!==false&&!r.error)"""
# Every animation frame for ms milliseconds: the d of path.wire of w1, the d of the travel path in
# its group when there is one, and the computed stroke-opacity of path.wire.
SAMPLE = r"""(ms)=>new Promise(resolve=>{
  const frames=[],start=performance.now();
  const step=()=>{
    const t=performance.now()-start,group=workspace.querySelector('.wire-group[data-wire-id="w1"]');
    const wire=group?group.querySelector('path.wire'):null,travel=group?group.querySelector('path.wire-travel'):null;
    frames.push({t,d:wire?wire.getAttribute('d'):null,travel:travel?travel.getAttribute('d'):null,opacity:wire?getComputedStyle(wire).strokeOpacity:null});
    if(t<ms)requestAnimationFrame(step);else resolve(frames);
  };
  requestAnimationFrame(step);
})"""
KEYBOARD = r"""([count,ms])=>{
  selectNode('b');
  const n=nodes.find(q=>q.id==='b'),y=n.y;
  for(let k=0;k<count;k++)document.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',code:'ArrowDown',bubbles:true,cancelable:true}));
  const dy=n.y-y;
  return (SAMPLE)(ms).then(frames=>({dy,frames}));
}""".replace('SAMPLE', SAMPLE)
AFTER = r"""()=>{
  const wire=workspace.querySelector('.wire-group[data-wire-id="w1"] path.wire'),L=wire.getTotalLength(),q=wire.getPointAtLength(L/2);
  return {travels:workspace.querySelectorAll('.wire-travel').length,marked:workspace.querySelectorAll('.wire-group[data-travel]').length,
    opacity:getComputedStyle(wire).strokeOpacity,middle:[q.x,q.y],d:wire.getAttribute('d')};
}"""
REDRAWN = r"""()=>{
  routeCache.clear();arrowPoseCache.clear();wireGroupDrawn.clear();renderWires();
  return workspace.querySelector('.wire-group[data-wire-id="w1"] path.wire').getAttribute('d');
}"""
# Test side only: every animation frame is held back ms, and each .wire-travel added is counted.
LATE_FRAMES = r"""(ms)=>{
  const raf=window.requestAnimationFrame.bind(window);window.__raf=window.requestAnimationFrame;
  window.requestAnimationFrame=fn=>setTimeout(()=>raf(fn),ms);
  window.__travelsAdded=0;
  window.__travelWatch=new MutationObserver(records=>{for(const r of records)for(const n of r.addedNodes)
    if(n.nodeType===1&&(n.matches('.wire-travel')||n.querySelector('.wire-travel')))window.__travelsAdded++});
  window.__travelWatch.observe(workspace,{childList:true,subtree:true});
}"""
LATE_RESULT = r"""()=>{
  window.requestAnimationFrame=window.__raf;window.__travelWatch.disconnect();
  return {added:window.__travelsAdded,travels:workspace.querySelectorAll('.wire-travel').length,marked:workspace.querySelectorAll('.wire-group[data-travel]').length,
    d:workspace.querySelector('.wire-group[data-wire-id="w1"] path.wire').getAttribute('d')};
}"""
NUMBER = re.compile(r'-?\d+(?:\.\d+)?(?:e[-+]?\d+)?')


def plant(page) -> None:
    doc = page.evaluate('()=>({schema:SovSchematicData.DOCUMENT_SCHEMA})')
    doc.update({'id': 'travel', 'components': [], 'wires': []})
    open_document(page, json.dumps(doc), 'travel.sov')
    made = page.evaluate(PLANT)
    assert all(made), ('the two cards and the wire are created', made)
    page.wait_for_timeout(300)
    page.evaluate('()=>{canvasSnapEnabled=false}')


def drag_and_sample(page) -> list:
    """Press b, move it down in MOVES pointer moves, release, and sample 600 ms of frames."""
    point = press(page, 'b')
    assert point, 'the press starts a drag of b'
    x, y = point
    for k in range(1, MOVES + 1):
        page.mouse.move(x, y + DRAG_PX * k / MOVES)
    page.mouse.up()
    return page.evaluate(SAMPLE, 600)


def middle(d: str) -> tuple[float, float]:
    """The middle of a travel path: the mean of its two central points (one, when the count is odd)."""
    v = [float(x) for x in NUMBER.findall(d)]
    pts = list(zip(v[0::2], v[1::2]))
    p, q = pts[(len(pts) - 1) // 2], pts[len(pts) // 2]
    return (p[0] + q[0]) / 2, (p[1] + q[1]) / 2


def main() -> None:
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(250)

        plant(page)
        before_d = page.evaluate(AFTER)['d']
        frames = drag_and_sample(page)
        after = page.evaluate(AFTER)
        redrawn = page.evaluate(REDRAWN)

        page.emulate_media(reduced_motion='reduce')
        plant(page)
        reduced = drag_and_sample(page)
        reduced_d = page.evaluate(AFTER)['d']
        page.emulate_media(reduced_motion='no-preference')

        plant(page)
        keyboard = page.evaluate(KEYBOARD, [ARROWS, 900])
        keyboard_after = page.evaluate(AFTER)

        plant(page)
        point = press(page, 'b')
        assert point, 'the press starts a drag of b'
        for k in range(1, MOVES + 1):
            page.mouse.move(point[0], point[1] + DRAG_PX * k / MOVES)
        page.evaluate(LATE_FRAMES, 250)
        page.mouse.up()
        page.wait_for_timeout(900)
        late = page.evaluate(LATE_RESULT)
        browser.close()

    travel = [f for f in frames if f['travel']]
    shapes = {f['travel'] for f in travel}
    duration = travel[-1]['t'] - travel[0]['t'] if travel else 0
    distances = [math.dist(middle(f['travel']), after['middle']) for f in travel]
    keyboard_travel = [f for f in keyboard['frames'] if f['travel']]
    print(f'pointer: {len(frames)} frames sampled, {len(travel)} with a travel path, {len(shapes)} different travel d values, '
          f'travel seen for {duration:.0f} ms')
    print(f'pointer: middle of the travel path to the middle of the final wire, first {distances[0] if distances else None}, '
          f'last {distances[-1] if distances else None}')
    print(f'reduced motion: {len(reduced)} frames sampled, {sum(1 for f in reduced if f["travel"])} with a travel path')
    print(f'keyboard: dy {keyboard["dy"]}, {len(keyboard["frames"])} frames sampled, {len(keyboard_travel)} with a travel path')
    print(f'frames held back 250 ms: {late["added"]} travel paths added, {late["travels"]} left')

    assert len(travel) >= 3 and len(shapes) >= 3, ('(a) a travel path is seen on at least 3 frames with at least 3 different d values',
                                                  len(travel), len(shapes))
    assert all(float(f['opacity']) == 0 for f in travel), ('(a) the stroke of path.wire is hidden while its travel path moves',
                                                           [f['opacity'] for f in travel])
    wire_ds = {f['d'] for f in frames}
    assert wire_ds == {redrawn} and before_d != redrawn, ('(b) path.wire is at its final route on every frame, the one a pass from nothing draws',
                                                         wire_ds, redrawn, before_d)
    grew = [(k, a, b) for k, (a, b) in enumerate(zip(distances, distances[1:])) if b - a > .5]
    assert not grew and distances[-1] < 1, ('(c) the travel path only approaches the final route and ends on it', grew[:3], distances[-1])
    assert after['travels'] == 0 and after['marked'] == 0 and float(after['opacity']) == 1, ('(d) after the travel nothing of it is left', after)
    assert not any(f['travel'] for f in reduced) and reduced_d == redrawn, ('(e) under reduced motion nothing travels and the wire is at its route',
                                                                          sum(1 for f in reduced if f['travel']), reduced_d)
    assert keyboard['dy'] == ARROWS and len(keyboard_travel) >= 3, ('(f) a keyboard move ends in a travel seen on at least 3 frames',
                                                                   keyboard['dy'], len(keyboard_travel))
    assert keyboard_after['travels'] == 0 and keyboard_after['marked'] == 0 and float(keyboard_after['opacity']) == 1, (
        '(f) after the keyboard travel nothing of it is left', keyboard_after)
    assert not errors, ('(g) the page logs no errors', errors)
    assert late == {'added': 0, 'travels': 0, 'marked': 0, 'd': redrawn}, (
        '(h) a first frame later than 180 ms after the settle adds no travel path, and the wire is at its route', late, redrawn)
    print('PASS wire travel QA')


if __name__ == '__main__':
    main()
