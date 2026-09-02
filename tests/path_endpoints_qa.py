"""A Path is placed by its two ends.

A 1D form carries its own length and direction. Dragging either end pins the other
and moves that one; the form's origin, length and angle all follow from the pair.
Everything that reads path geometry follows without knowing about the gesture: a
hosted Point keeps its t and rides the new line, and the geometry is authored state
that survives a save.
"""
import asyncio
import math
import sys
from pathlib import Path

from browser_runtime import chromium_launch_kwargs
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'


async def drag_to(page, selector, tx, ty, modifiers=None):
    box = await page.locator(selector).bounding_box()
    assert box, f'no box for {selector}'
    cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    if modifiers:
        for key in modifiers:
            await page.keyboard.down(key)
    await page.mouse.move(cx, cy)
    await page.mouse.down()
    for i in range(1, 13):
        await page.mouse.move(cx + (tx - cx) * i / 12, cy + (ty - cy) * i / 12)
        await page.wait_for_timeout(16)
    await page.mouse.up()
    await page.wait_for_timeout(180)
    if modifiers:
        for key in modifiers:
            await page.keyboard.up(key)


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = await browser.new_page(viewport={'width': 1400, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.set_content(HTML.read_text(encoding='utf-8'), wait_until='load')
        await page.wait_for_timeout(180)

        geometry = """(id)=>{const n=nodes.find(n=>n.id===id),p=n.config.presentation;
            return {x:n.x,y:n.y,length:p.size.w,angle:p.angle}}"""

        path = await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'path',x:600,y:400}).result")
        pid = path['id']
        assert path['form']['dimension'] == 1, path
        # A new Path is level. Angle is authored state, filled in by normalization
        # rather than by the CRUD record, so it is read from the runtime node.
        start_geometry = await page.evaluate(geometry, pid)
        assert start_geometry['angle'] == 0, start_geometry

        # Both ends carry a handle, and they sit above the endpoint attachment points
        # so the pointer reaches them rather than starting a wire.
        assert await page.locator(f'.node[data-id="{pid}"] .path-endpoint-handle').count() == 2
        for end in ('start', 'end'):
            assert await page.locator(
                f'.node[data-id="{pid}"] .path-endpoint-halo[data-path-end="{end}"]').count() == 1, end
        assert await page.evaluate(
            f"""()=>{{const g=document.querySelector('.node[data-id="{pid}"]');
                const nodes=[...g.querySelectorAll('.port-hit,.path-endpoint-halo')];
                return nodes.at(-1).classList.contains('path-endpoint-halo')}}"""), \
            'endpoint handles must be painted after the attachment-point hit areas'

        await page.evaluate('(id)=>selectNode(id)', pid)
        await page.wait_for_timeout(100)

        # Dragging one end pins the other. The far end must not move.
        ends = await page.evaluate("""(id)=>{const n=nodes.find(n=>n.id===id);
            const half=Math.max(PATH_MIN_LENGTH,componentSize(n).w)/2,a=componentHostAngle(n);
            const s=rotateVectorByDegrees(-half,0,a),e=rotateVectorByDegrees(half,0,a);
            return {start:{x:n.x+s.x,y:n.y+s.y},end:{x:n.x+e.x,y:n.y+e.y}}}""", pid)
        await drag_to(page, f'.node[data-id="{pid}"] .path-endpoint-halo[data-path-end="end"]', 980, 250)
        moved = await page.evaluate(geometry, pid)
        after_ends = await page.evaluate("""(id)=>{const n=nodes.find(n=>n.id===id);
            const half=Math.max(PATH_MIN_LENGTH,componentSize(n).w)/2,a=componentHostAngle(n);
            const s=rotateVectorByDegrees(-half,0,a),e=rotateVectorByDegrees(half,0,a);
            return {start:{x:n.x+s.x,y:n.y+s.y},end:{x:n.x+e.x,y:n.y+e.y}}}""", pid)
        assert moved['angle'] != 0, f'the Path did not take a direction: {moved}'
        assert moved['length'] > start_geometry['length'], moved
        assert math.hypot(after_ends['start']['x'] - ends['start']['x'],
                          after_ends['start']['y'] - ends['start']['y']) < 2, \
            f'the far end moved: {ends["start"]} -> {after_ends["start"]}'

        # A Point settled on the Path keeps its t and rides the reshaped line.
        point = await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'point',x:600,y:180}).result")
        body = await page.locator(f'.node[data-id="{pid}"] .dimensional-path-body').bounding_box()
        box = await page.locator(f'.node[data-id="{point["id"]}"]').bounding_box()
        cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
        tx, ty = body['x'] + body['width'] * 0.5, body['y'] + body['height'] * 0.5
        await page.mouse.move(cx, cy)
        await page.mouse.down()
        for i in range(1, 15):
            await page.mouse.move(cx + (tx - cx) * i / 14, cy + (ty - cy) * i / 14)
            await page.wait_for_timeout(24)
        await page.wait_for_timeout(700)   # settle dwell
        await page.mouse.up()
        await page.wait_for_timeout(240)

        hosted = await page.evaluate(
            '(id)=>{const n=nodes.find(n=>n.id===id);return {x:n.x,y:n.y,placement:n.placement}}', point['id'])
        assert hosted['placement']['kind'] == 'path' and hosted['placement']['hostId'] == pid, hosted
        t_before = hosted['placement']['t']

        await page.evaluate('(id)=>selectNode(id)', pid)
        await page.wait_for_timeout(100)
        await drag_to(page, f'.node[data-id="{pid}"] .path-endpoint-halo[data-path-end="start"]', 240, 720)
        rode = await page.evaluate(
            '(id)=>{const n=nodes.find(n=>n.id===id);return {x:n.x,y:n.y,t:n.placement.t}}', point['id'])
        assert abs(rode['t'] - t_before) < 1e-6, f't changed when only the host moved: {t_before} -> {rode["t"]}'
        assert math.hypot(rode['x'] - hosted['x'], rode['y'] - hosted['y']) > 8, \
            'the hosted Point did not follow the reshaped Path'

        # Length and direction are authored, not derived: they survive the document.
        reshaped = await page.evaluate(geometry, pid)
        document = await page.evaluate('window.SovSchematicAPI.document.get()')
        saved = next(c for c in document['components'] if c['id'] == pid)['config']['presentation']
        assert abs(saved['angle'] - reshaped['angle']) < 1e-6, (saved, reshaped)
        assert abs(saved['size']['w'] - reshaped['length']) < 1e-6, (saved, reshaped)

        # A Path may run far longer than a 2D body's 520 ceiling.
        assert reshaped['length'] > 520, reshaped

        # Reshaping is one undoable step, and undo puts the geometry back.
        await page.evaluate('window.SovSchematicAPI.history.undo()')
        await page.wait_for_timeout(160)
        undone = await page.evaluate(geometry, pid)
        assert undone != reshaped, 'undo did not restore the Path geometry'

        # A hosted 1D form takes its host's pose, so it gets no endpoint handles.
        plane = await page.evaluate(
            "window.SovSchematicAPI.create('component',{symbolId:'plane',x:400,y:300}).result")
        assert await page.locator(f'.node[data-id="{plane["id"]}"] .path-endpoint-handle').count() == 0

        assert not errors, errors
        await browser.close()
    print('path_endpoints_qa ok')


if __name__ == '__main__':
    sys.exit(asyncio.run(main()) or 0)
