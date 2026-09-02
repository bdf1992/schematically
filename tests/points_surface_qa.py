"""Attachments are state, and the panel reads them.

The settings panel lists the points on the selected object and what is on each one,
for a Component and for a Wire alike, including Points hosted on it rather than
exposed by it. The list is not where the set is configured: a point arrives by being
dropped and leaves by being deleted, and the only control beside the list acts on
the template's built-in boundary points, which is an action on the list rather than
a setting inside Form.
"""
import asyncio
import sys
from pathlib import Path

from browser_runtime import chromium_launch_kwargs
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'

ROWS = ("[...document.querySelectorAll('#pointsList .points-row')]"
        ".map(r=>[r.querySelector('b').textContent,r.querySelector('span').textContent])")


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = await browser.new_page(viewport={'width': 1400, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.set_content(HTML.read_text(encoding='utf-8'), wait_until='load')
        await page.wait_for_timeout(180)

        # Attachments are no longer a Form setting.
        assert await page.evaluate('!document.getElementById("formAttachments")'), \
            'the Attachments select is still in Form'

        act = await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:300,y:300}).result")
        hold = await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'hold',x:820,y:300}).result")
        wire = await page.evaluate(
            "([a,b])=>window.SovSchematicAPI.create('wire',{a,aSide:'out',b,bSide:'in'}).result",
            [act['id'], hold['id']])

        # A Component lists its points and says what is on each.
        await page.evaluate('(id)=>{selectNode(id);openSelectionSettings("component")}', act['id'])
        await page.wait_for_timeout(140)
        assert await page.evaluate('pointsSurface.hidden') is False
        rows = await page.evaluate(ROWS)
        assert [r[0] for r in rows] == ['left', 'right', 'top'], rows
        assert 'nothing attached' in dict(rows)['left'], rows
        assert 'HOLD' in dict(rows)['right'], rows
        assert await page.evaluate('pointsSummary.textContent') == '3 points'

        # A row leads to the point it names.
        await page.evaluate("document.querySelectorAll('#pointsList .points-row')[1].click()")
        await page.wait_for_timeout(140)
        assert await page.evaluate('selected') == f'point:component:{act["id"]}:right', \
            await page.evaluate('selected')

        # A Wire has points too: its two ends, named by what they are bound to.
        await page.evaluate('(id)=>{selectWire(wires.findIndex(w=>w.id===id));openSelectionSettings("wire")}',
                            wire['id'])
        await page.wait_for_timeout(140)
        rows = await page.evaluate(ROWS)
        assert [r[0] for r in rows] == ['A', 'B'], rows
        assert 'bound' in rows[0][1] and 'ACT' in rows[0][1], rows
        assert 'bound' in rows[1][1] and 'HOLD' in rows[1][1], rows
        # The built-in control belongs to a 2D template, not to a Wire.
        assert await page.evaluate('pointsBuiltinToggle.hidden') is True

        # A Plane starts with nothing attached, and says so rather than showing an empty box.
        plane = await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'plane',x:520,y:640}).result")
        await page.evaluate('(id)=>{selectNode(id);openSelectionSettings("component")}', plane['id'])
        await page.wait_for_timeout(140)
        rows = await page.evaluate(ROWS)
        assert rows == [['None', 'nothing is attached to this object yet']], rows

        # Built-in points are added and removed as an action on the list.
        assert await page.evaluate('pointsBuiltinToggle.textContent') == 'Add built-in points'
        await page.evaluate('pointsBuiltinToggle.click()')
        await page.wait_for_timeout(180)
        rows = await page.evaluate(ROWS)
        assert [r[0] for r in rows] == ['left', 'right', 'top'], rows
        assert await page.evaluate('pointsBuiltinToggle.textContent') == 'Remove built-in points'
        await page.evaluate('pointsBuiltinToggle.click()')
        await page.wait_for_timeout(180)
        assert await page.evaluate(ROWS) == [['None', 'nothing is attached to this object yet']]

        # Removing built-ins is refused while a Wire still ends on one.
        await page.evaluate('(id)=>{selectNode(id);openSelectionSettings("component")}', act['id'])
        await page.wait_for_timeout(140)
        await page.evaluate('pointsBuiltinToggle.click()')
        await page.wait_for_timeout(180)
        assert 'Detach Wires' in await page.evaluate('statusEl.textContent'), \
            await page.evaluate('statusEl.textContent')
        assert [r[0] for r in await page.evaluate(ROWS)] == ['left', 'right', 'top']

        # A Point hosted on a Wire is attached to it, and the Wire's list says so.
        hosted = await page.evaluate("""(id)=>{
            const w=wires.find(w=>w.id===id);
            const r=window.SovSchematicAPI.create('component',{symbolId:'point',x:560,y:300}).result;
            const n=nodes.find(n=>n.id===r.id);
            n.canvasId=wireCanvas(w).id;n.placement={kind:'wire',wireId:w.id,t:0.5};
            render();return n.id}""", wire['id'])
        await page.evaluate('(id)=>{selectWire(wires.findIndex(w=>w.id===id));openSelectionSettings("wire")}',
                            wire['id'])
        await page.wait_for_timeout(140)
        rows = await page.evaluate(ROWS)
        assert len(rows) == 3, rows
        assert 'hosted' in rows[2][1], rows

        # That row leads to the hosted Point itself.
        await page.evaluate("document.querySelectorAll('#pointsList .points-row')[2].click()")
        await page.wait_for_timeout(140)
        assert await page.evaluate('selected') == hosted, await page.evaluate('selected')

        # The panel says Point where the model says Point.
        text = await page.evaluate("document.getElementById('portSettingsFields').textContent")
        assert 'Point settings' in text, text

        assert not errors, errors
        await browser.close()
    print('points_surface_qa ok')


if __name__ == '__main__':
    sys.exit(asyncio.run(main()) or 0)
