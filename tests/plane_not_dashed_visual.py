"""Visual check: a Plane is a Plane, not a dashed Plane.

The container guide marks where a child would settle. It is a drop affordance and belongs on
screen only while something is being dragged, so an idle or selected Plane shows no dashes.
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'
SHOT = ROOT / 'tests' / 'plane-not-dashed.png'


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = await browser.new_page(viewport={'width': 900, 'height': 520})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.set_content(HTML.read_text(), wait_until='load')
        await page.wait_for_timeout(200)
        await page.evaluate('newSchematic()')

        plane = await page.evaluate(
            "window.SovSchematicAPI.create('component',{symbolId:'plane',x:430,y:250}).result")
        await page.wait_for_timeout(120)

        assert await page.evaluate(
            '(id)=>componentAcceptsChildren(nodes.find(n=>n.id===id))', plane['id']), \
            'a Plane primitive should host children; otherwise this test proves nothing'
        guide = f'.node[data-id="{plane["id"]}"] .container-guide'
        assert await page.locator(guide).count() == 1, 'guide element should still exist'

        # Idle: the guide is present in the DOM but not painted.
        idle = await page.evaluate(
            '(sel)=>getComputedStyle(document.querySelector(sel)).opacity', guide)
        assert float(idle) == 0.0, f'idle Plane must show no container dashes, got opacity {idle}'

        # Selected: still no dashes — selection is not a drag.
        await page.evaluate('(id)=>selectNode(id,{focus:false})', plane['id'])
        await page.wait_for_timeout(80)
        selected = await page.evaluate(
            '(sel)=>getComputedStyle(document.querySelector(sel)).opacity', guide)
        assert float(selected) == 0.0, f'selected Plane must show no dashes, got {selected}'

        await page.screenshot(path=str(SHOT))

        # While a node is being dragged the guide is what answers "where will this land".
        await page.evaluate("()=>workspace.classList.add('dragging-node')")
        await page.wait_for_timeout(80)
        dragging = await page.evaluate(
            '(sel)=>getComputedStyle(document.querySelector(sel)).opacity', guide)
        assert float(dragging) > 0, 'the guide must appear while a drag is in progress'

        assert not errors, errors
        await browser.close()
    print(f'PLANE NOT DASHED PASS (screenshot: {SHOT.name})')


asyncio.run(main())
