"""The dimension control changes the dimension, and a dwelled Wire grows a Point.

The bar's dimension button steps up the ladder and wraps; shift steps back. Retyping
across dimensions changes which attachment points exist, so a change that would leave
a Wire ending on a point that no longer exists is refused rather than silently
dropping the connection. The Form select is the same act and answers to the same rule.

Dragging a Wire into open space and dwelling grows another of whatever it grew out
of, joined on whichever of that form's points faces back. The gesture continues what
is already there rather than deciding on the person's behalf that the next thing is
something else, and nothing is asked for afterwards because no type is left to pick.
A free Point has no side, so a Wire leaves it in whatever direction the route wants.
"""
import asyncio
import sys
from pathlib import Path

from browser_runtime import chromium_launch_kwargs
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'


async def dimension_of(page, node_id):
    return await page.evaluate('(id)=>componentForm(nodes.find(n=>n.id===id)).dimension', node_id)


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = await browser.new_page(viewport={'width': 1400, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.set_content(HTML.read_text(encoding='utf-8'), wait_until='load')
        await page.wait_for_timeout(180)

        # --- the button walks the ladder -----------------------------------
        plane = await page.evaluate(
            "window.SovSchematicAPI.create('component',{symbolId:'plane',x:500,y:400}).result")
        await page.evaluate('(id)=>selectNode(id)', plane['id'])
        await page.wait_for_timeout(120)
        assert await page.evaluate('barFormState.textContent') == '2D'

        await page.locator('#barFormState').click()
        await page.wait_for_timeout(140)
        assert await dimension_of(page, plane['id']) == 3, 'click did not step up'
        assert await page.evaluate('barFormState.textContent') == '3D'

        await page.locator('#barFormState').click()
        await page.wait_for_timeout(140)
        assert await dimension_of(page, plane['id']) == 0, 'the ladder did not wrap'

        # Shift steps back, and wraps the other way.
        await page.locator('#barFormState').click(modifiers=['Shift'])
        await page.wait_for_timeout(140)
        assert await dimension_of(page, plane['id']) == 3, 'shift did not step back'

        # A 3D Pod keeps the Plane's boundary behaviour and gains its thickness.
        form = await page.evaluate('(id)=>componentForm(nodes.find(n=>n.id===id))', plane['id'])
        assert form['body']['kind'] == 'volume', form
        assert await page.evaluate('(id)=>componentIsSurface(nodes.find(n=>n.id===id))', plane['id'])

        # The Form select is the same act.
        await page.evaluate('()=>{openSelectionSettings("component");formDimension.value="1";'
                            'formDimension.dispatchEvent(new Event("change"))}')
        await page.wait_for_timeout(140)
        assert await dimension_of(page, plane['id']) == 1

        # --- a change that would orphan a Wire is refused -------------------
        act = await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:200,y:700}).result")
        hold = await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'hold',x:800,y:700}).result")
        wire = await page.evaluate(
            "([a,b])=>window.SovSchematicAPI.create('wire',{a,aSide:'out',b,bSide:'in'}).result",
            [act['id'], hold['id']])
        assert wire, 'the fixture wire was not created'

        await page.evaluate('(id)=>selectNode(id)', act['id'])
        await page.wait_for_timeout(120)
        # ACT is wired on `right`, which a 0D form does not have.
        await page.evaluate('()=>setSelectedComponentDimension(0)')
        await page.wait_for_timeout(140)
        assert await dimension_of(page, act['id']) == 2, 'the refusal did not hold the form'
        status = await page.evaluate('statusEl.textContent')
        assert 'detach' in status.lower(), status
        assert await page.evaluate('wires.length') == 1, 'the Wire was dropped'

        # The select snaps back rather than showing a value that was refused.
        await page.evaluate('()=>{openSelectionSettings("component");formDimension.value="0";'
                            'formDimension.dispatchEvent(new Event("change"))}')
        await page.wait_for_timeout(140)
        assert await page.evaluate('formDimension.value') == '2', \
            await page.evaluate('formDimension.value')

        # Detached, the same change is allowed.
        await page.evaluate('(id)=>window.SovSchematicAPI.delete("wire",id)', wire['id'])
        await page.evaluate('(id)=>selectNode(id)', act['id'])
        await page.wait_for_timeout(120)
        await page.evaluate('()=>setSelectedComponentDimension(0)')
        await page.wait_for_timeout(140)
        assert await dimension_of(page, act['id']) == 0

        # A Wire is a carrier Path and is not retypable, so its button does not offer to be.
        wire2 = await page.evaluate(
            "([a,b])=>window.SovSchematicAPI.create('wire',{a,aSide:'self',b,bSide:'in'}).result",
            [act['id'], hold['id']])
        await page.evaluate('(id)=>selectWire(wires.findIndex(w=>w.id===id))', wire2['id'])
        await page.wait_for_timeout(140)
        assert await page.evaluate('barFormState.disabled') is True
        assert await page.evaluate('barFormState.textContent') == '1D'

        # --- dwelling out of a point grows a Point --------------------------
        await page.evaluate('()=>{selectNode(null)}')
        before_nodes = await page.evaluate('nodes.length')
        before_wires = await page.evaluate('wires.length')
        port = page.locator(f'.node[data-id="{hold["id"]}"] .port-hit[data-point="right"]')
        box = await port.bounding_box()
        assert box, 'no attachment point to drag from'
        cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
        # Aim at open canvas inside the workspace, not past its right edge.
        surface = await page.locator('#workspace').bounding_box()
        tx = surface['x'] + surface['width'] * 0.72
        ty = surface['y'] + surface['height'] * 0.18
        await page.mouse.move(cx, cy)
        await page.mouse.down()
        for i in range(1, 13):
            await page.mouse.move(cx + (tx - cx) * i / 12, cy + (ty - cy) * i / 12)
            await page.wait_for_timeout(22)
        await page.wait_for_timeout(700)   # the dwell
        # The ghost names and shapes what will actually appear. HOLD is 2D, so a body.
        ghost_label = await page.evaluate(
            "document.querySelector('.wire-blank-ghost text')?.textContent||''")
        assert ghost_label == 'NEW HOLD', ghost_label
        assert await page.locator('.wire-blank-ghost rect.body').count() == 1
        assert await page.locator('.wire-blank-ghost circle.body').count() == 0
        await page.mouse.up()
        await page.wait_for_timeout(260)

        assert await page.evaluate('nodes.length') == before_nodes + 1, (
            'nothing was grown; status=' + await page.evaluate('statusEl.textContent'))
        assert await page.evaluate('wires.length') == before_wires + 1, 'it was not connected'
        grown = await page.evaluate('nodes.at(-1)')
        assert grown['symbolId'] == 'hold', grown
        # Nothing is asked for afterwards: there is no type left to choose.
        assert (await page.evaluate('statusEl.textContent')) == 'HOLD created', \
            await page.evaluate('statusEl.textContent')
        # Grown downstream of an output, so it is joined on its own input.
        joined = await page.evaluate(
            '(id)=>wires.filter(w=>w.a===id||w.b===id).map(w=>w.a===id?w.aSide:w.bSide)', grown['id'])
        assert joined == ['in'], joined

        # Growing out of a Point gives a Point, joined through its one point `self`.
        seed = await page.evaluate(
            "window.SovSchematicAPI.create('component',{symbolId:'point',x:260,y:180}).result")
        await page.wait_for_timeout(140)
        rbox = await page.locator(
            f'.node[data-id="{seed["id"]}"] .port-hit[data-point="self"]').bounding_box()
        # The inner grip moves a Point and the outer ring wires from it, so the drag
        # has to start on the ring rather than at the centre.
        rx = rbox['x'] + rbox['width'] * 0.86
        ry = rbox['y'] + rbox['height'] / 2
        px = surface['x'] + surface['width'] * 0.32
        py = surface['y'] + surface['height'] * 0.45
        await page.mouse.move(rx, ry)
        await page.mouse.down()
        for i in range(1, 13):
            await page.mouse.move(rx + (px - rx) * i / 12, ry + (py - ry) * i / 12)
            await page.wait_for_timeout(22)
        await page.wait_for_timeout(700)
        ghost = await page.evaluate(
            "document.querySelector('.wire-blank-ghost text')?.textContent||''")
        assert ghost == 'NEW POINT', (ghost, await page.evaluate('statusEl.textContent'))
        assert await page.locator('.wire-blank-ghost circle.body').count() == 1
        await page.mouse.up()
        await page.wait_for_timeout(280)
        twin = await page.evaluate('nodes.at(-1)')
        assert twin['symbolId'] == 'point', twin
        assert await dimension_of(page, twin['id']) == 0, twin

        # A free Point has no side, so it is given no stub direction and a Wire leaves
        # it wherever the route wants rather than along a normal it does not have.
        assert await page.evaluate(
            '(id)=>{const n=nodes.find(n=>n.id===id),p={x:n.x,y:n.y};'
            'const s=stubPos(p,"self",26,n,null);return s.x===p.x&&s.y===p.y}', twin['id']), \
            'a free Point was pushed out along a normal'

        # A Point is drawn at a size a person can see and aim at, and the drawn radius
        # is the one the rest of the editor reasons about.
        radius = await page.evaluate('(id)=>pointBodyRadius(nodes.find(n=>n.id===id))', twin['id'])
        assert radius >= 9, radius
        drawn = await page.evaluate(
            '(id)=>Number(document.querySelector(`.node[data-id="${id}"] .dimensional-point-body`)'
            '.getAttribute("r"))', twin['id'])
        assert abs(drawn - radius) < 1e-6, (drawn, radius)

        assert not errors, errors
        await browser.close()
    print('dimension_control_qa ok')


if __name__ == '__main__':
    sys.exit(asyncio.run(main()) or 0)
