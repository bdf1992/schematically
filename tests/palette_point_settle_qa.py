"""A palette Point shows where it will settle, and settles there (issue #24).

The exact case from the review: a Plane with a Point on its right edge, a
carrier with one end bound to that Point and one free end, and a Point dragged
from the palette over the carrier. The palette ghost was host-blind (a dot at
the pointer), and only an existing node's drag ran the host candidate, behind
a 280 ms dwell whenever the candidate's surface differed from the node's. Now
the palette drag runs the same host candidate as a node drag, and for a 0D
drag a wire, path or edge candidate needs no dwell: attaching is the Point's
only purpose, so the settle ghost appears at once and release settles there.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text()

SCENE = """()=>{const A=window.SovSchematicAPI;
  const pl=A.create('component',{symbolId:'plane',x:500,y:420}).result;
  const edge=A.create('component',{symbolId:'point',x:0,y:0,canvasId:`canvas:component:${pl.id}`,parentId:pl.id,
    placement:{kind:'edge',hostId:pl.id,side:'right',t:.5}}).result;
  const w=A.create('wire',{a:edge.id,aSide:'out',bAttachment:{kind:'free',x:1000,y:420}}).result;
  const loose=A.create('component',{symbolId:'point',x:900,y:700,config:{label:'loose'}}).result;
  render();
  const n=nodes.find(x=>x.id===edge.id),wire=wires.find(x=>x.id===w.id);
  return {plane:pl.id,edge:edge.id,edgeXY:{x:n.x,y:n.y},wire:w.id,wireCanvas:wire.canvasId,loose:loose.id,
    freeEnd:wire.bAttachment}}"""

# Client coordinates of a world point.
CLIENT = "([x,y])=>{const p=workspace.createSVGPoint();p.x=x;p.y=y;const c=p.matrixTransform(workspace.getScreenCTM());return {x:c.x,y:c.y}}"
GHOST = "()=>[...document.querySelectorAll('.settle-host-ghost')].map(g=>g.getAttribute('class'))"


def palette_card_center(page, symbol):
    box = page.locator(f'.symbol-card[data-symbol-id="{symbol}"]').bounding_box()
    assert box, f'no palette card for {symbol}'
    return box['x'] + box['width'] / 2, box['y'] + box['height'] / 2


with sync_playwright() as p:
    b = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = b.new_page(viewport={'width': 1400, 'height': 900})
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(300)
    scene = page.evaluate(SCENE)
    page.wait_for_timeout(120)

    # The carrier runs from the Plane's right-edge Point to a free end; hover its midpoint.
    mid_world = ((scene['edgeXY']['x'] + scene['freeEnd']['x']) / 2, (scene['edgeXY']['y'] + scene['freeEnd']['y']) / 2)
    mid = page.evaluate(CLIENT, list(mid_world))

    # 1. Palette drag: the settle ghost appears over the carrier without a dwell.
    cx, cy = palette_card_center(page, 'point')
    page.mouse.move(cx, cy)
    page.mouse.down()
    page.mouse.move(cx + 30, cy + 30, steps=3)     # past the drag threshold; the drag is live
    page.mouse.move(mid['x'], mid['y'], steps=6)
    page.wait_for_timeout(40)                      # far less than the 280 ms dwell
    ghosts = page.evaluate(GHOST)
    assert any('wire-host' in g for g in ghosts), f'no settle ghost for a palette Point over the carrier: {ghosts}'
    assert page.evaluate("()=>statusEl.textContent") == 'Release → settle', page.evaluate("()=>statusEl.textContent")

    # 2. Release settles the new Point on the carrier.
    before = set(page.evaluate("()=>nodes.map(n=>n.id)"))
    page.mouse.up()
    page.wait_for_timeout(120)
    after = [n for n in page.evaluate("()=>nodes.map(n=>({id:n.id,symbolId:n.symbolId,placement:n.placement,canvasId:n.canvasId}))")
             if n['id'] not in before]
    assert len(after) == 1 and after[0]['symbolId'] == 'point', after
    placed = after[0]
    assert placed['placement']['kind'] == 'wire' and placed['placement']['wireId'] == scene['wire'], placed
    assert 0.2 < placed['placement']['t'] < 0.8, placed
    assert page.evaluate(GHOST) == [], 'settle ghost left behind after release'

    # 3. An existing Point from another surface: the ghost also appears without a dwell.
    loose = page.evaluate("(id)=>{const n=nodes.find(x=>x.id===id);return {x:n.x,y:n.y}}", scene['loose'])
    start = page.evaluate(CLIENT, [loose['x'], loose['y']])
    target = page.evaluate(CLIENT, [mid_world[0] + 40, mid_world[1]])
    page.mouse.move(start['x'], start['y'])
    page.mouse.down()
    page.mouse.move(start['x'] + 12, start['y'] + 12, steps=2)
    page.mouse.move(target['x'], target['y'], steps=6)
    page.wait_for_timeout(40)
    ghosts = page.evaluate(GHOST)
    assert any('wire-host' in g for g in ghosts), f'no immediate settle ghost for a dragged Point: {ghosts}'
    page.mouse.up()
    page.wait_for_timeout(120)
    moved = page.evaluate("(id)=>{const n=nodes.find(x=>x.id===id);return n.placement}", scene['loose'])
    assert moved['kind'] == 'wire' and moved['wireId'] == scene['wire'], moved

    # 4. A 2D drop into an open interior still respects the dwell: no ghost at 40 ms, one after.
    plane_center = page.evaluate("(id)=>{const n=nodes.find(x=>x.id===id);return {x:n.x,y:n.y}}", scene['plane'])
    inside = page.evaluate(CLIENT, [plane_center['x'] - 60, plane_center['y'] + 40])
    cx, cy = palette_card_center(page, 'act')
    page.mouse.move(cx, cy)
    page.mouse.down()
    page.mouse.move(cx + 30, cy + 30, steps=3)
    page.mouse.move(inside['x'], inside['y'], steps=6)
    page.wait_for_timeout(40)
    assert not any('component-host' in g for g in page.evaluate(GHOST)), 'interior ghost skipped the dwell'
    page.wait_for_timeout(400)
    assert any('component-host' in g for g in page.evaluate(GHOST)), f'interior ghost never appeared: {page.evaluate(GHOST)}'
    page.mouse.up()
    page.wait_for_timeout(120)
    assert page.evaluate(GHOST) == []

    assert not errors, f'page errors: {errors}'
    b.close()

print('PASS palette point settle QA')
