"""A 1D Form's direction lives in its two boundary points, and nowhere else.

Direction used to be read from a runtime pose cache, so it was not saved, not undoable, and
was dropped whenever the entity moved. The Form spine says a 1D Form's geometry IS its two 0D
boundary points; these checks hold to that, because a direction that is derived cannot reset.
"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = await browser.new_page(viewport={'width': 1000, 'height': 700})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.set_content(HTML.read_text(), wait_until='load')
        await page.wait_for_timeout(200)
        await page.evaluate('newSchematic()')

        path = await page.evaluate(
            "window.SovSchematicAPI.create('component',{symbolId:'path',x:400,y:350}).result")
        await page.wait_for_timeout(120)
        pid = path['id']

        # A free-standing Path exposes a grip on each end: the geometry is those two points.
        grips = f'.node[data-id="{pid}"] .path-end-grip'
        assert await page.locator(grips).count() == 2, 'a free Path should grip both ends'

        # Reshaping by one end changes length and heading together.
        before = await page.evaluate(
            '(id)=>{const g=componentPathGeometry(nodes.find(n=>n.id===id));'
            'return {angle:g.angle,length:g.length}}', pid)
        assert round(before['angle']) == 0, before

        box = await page.locator(f'{grips}[data-point="end"]').bounding_box()
        await page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        await page.mouse.down()
        await page.mouse.move(box['x'] + 120, box['y'] - 90, steps=8)
        await page.mouse.up()
        await page.wait_for_timeout(150)

        tilted = await page.evaluate(
            '(id)=>{const n=nodes.find(x=>x.id===id),g=componentPathGeometry(n);'
            'return {angle:g.angle,length:g.length,points:n.form.geometry.points}}', pid)
        assert abs(tilted['angle']) > 5, f'dragging an end must tilt the Path: {tilted}'
        assert tilted['length'] > before['length'], tilted

        # The two points stay antipodal about the centre, so n.x/n.y remains the midpoint.
        a, b = tilted['points']
        assert abs(a['x'] + b['x']) < 1e-6 and abs(a['y'] + b['y']) < 1e-6, tilted['points']

        # Moving the whole Component must not touch its direction. This is the reported bug.
        moved = await page.evaluate(
            '(id)=>{const n=nodes.find(x=>x.id===id);n.x+=150;n.y+=40;'
            'updateContainmentFor(n);render();const g=componentPathGeometry(n);'
            'return {angle:g.angle,length:g.length}}', pid)
        assert abs(moved['angle'] - tilted['angle']) < 1e-6, f'move reset direction: {moved}'
        assert abs(moved['length'] - tilted['length']) < 1e-6, moved

        # A re-render derives the same direction: nothing is cached that could go stale.
        rerendered = await page.evaluate(
            '(id)=>{render();render();const g=componentPathGeometry(nodes.find(n=>n.id===id));'
            'return {angle:g.angle,length:g.length}}', pid)
        assert abs(rerendered['angle'] - moved['angle']) < 1e-6, rerendered

        # The drawn body runs between the two points, not along a hardcoded axis.
        line = await page.evaluate(
            '(id)=>{const el=document.querySelector(`.node[data-id="${id}"] .dimensional-path-body`);'
            'return el&&{x1:+el.getAttribute("x1"),y1:+el.getAttribute("y1"),'
            'x2:+el.getAttribute("x2"),y2:+el.getAttribute("y2")}}', pid)
        assert line and abs(line['y1']) > 1e-6, f'the body should be drawn tilted: {line}'

        # Geometry is entity state, so it survives serialization.
        saved = await page.evaluate(
            '(id)=>{const doc=SovSchematicData.compactDocument(diagram);'
            'const c=JSON.parse(JSON.stringify(doc)).components.find(x=>x.id===id);'
            'return c&&c.form&&c.form.geometry||null}', pid)
        assert saved and len(saved['points']) == 2, f'geometry must be saved: {saved}'
        assert json.dumps(saved['points']) == json.dumps(tilted['points']), saved

        # Reloading the saved document restores the same heading.
        reloaded = await page.evaluate(
            '(id)=>{const doc=SovSchematicData.compactDocument(diagram);'
            'replaceRuntimeDocument(JSON.parse(JSON.stringify(doc)));render();'
            'const g=componentPathGeometry(nodes.find(n=>n.id===id));'
            'return {angle:g.angle,length:g.length}}', pid)
        assert abs(reloaded['angle'] - moved['angle']) < 1e-6, f'reload lost direction: {reloaded}'

        # A Point settled on a tilted Path lands on the tilted line, and takes its axis. This is
        # the whole chain: stored points -> derived heading -> where a hosted 0D Form sits.
        hosted = await page.evaluate('''(id)=>{
          const host=nodes.find(n=>n.id===id),g=componentPathGeometry(host);
          const mid={x:host.x+(g.start.x+g.end.x)/2,y:host.y+(g.start.y+g.end.y)/2};
          const quarter={x:host.x+g.start.x*0.5,y:host.y+g.start.y*0.5};
          const q=nearestPointOnComponentPath(host,quarter.x,quarter.y);
          const pt=window.SovSchematicAPI.create('component',{symbolId:'point',x:quarter.x,y:quarter.y}).result;
          const node=nodes.find(n=>n.id===pt.id);
          applyComponentHost(node,componentHostCandidateAtPoint(node));render();
          return {hostAngle:g.angle,snapAngle:q&&q.angle,snapDistance:q&&q.distance,
                  placement:node.placement.kind,pointAngle:componentHostAngle(node),
                  offMidpoint:Math.hypot(node.x-mid.x,node.y-mid.y)};
        }''', pid)
        assert abs(hosted['snapAngle'] - hosted['hostAngle']) < 1e-6, hosted
        assert hosted['snapDistance'] < 1, f'a point on the line should snap to it: {hosted}'
        assert hosted['placement'] == 'path', hosted
        assert abs(hosted['pointAngle'] - hosted['hostAngle']) < 1e-6, \
            f'a hosted Point should take the Path axis it sits on: {hosted}'
        assert hosted['offMidpoint'] > 1, 'the point should land where it was put, not at centre'

        # A 0D Point and a 2D Plane carry no path geometry; only a 1D Form has one.
        other = await page.evaluate('''()=>{
          const pt=window.SovSchematicAPI.create('component',{symbolId:'point',x:200,y:200}).result;
          const pl=window.SovSchematicAPI.create('component',{symbolId:'plane',x:700,y:200}).result;
          return [pt,pl].map(r=>{const n=nodes.find(x=>x.id===r.id);
            return {dim:componentForm(n).dimension,geometry:n.form.geometry||null,
                    path:componentPathGeometry(n)}})}''')
        for entry in other:
            assert entry['geometry'] is None and entry['path'] is None, entry

        assert not errors, errors
        await browser.close()
    print('PATH DIRECTION PASS')


asyncio.run(main())
