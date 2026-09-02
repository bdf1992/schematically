"""The palette is the dimensional ladder.

One rung per row, read top to bottom, each naming its dimension and its sense.
Typed Components are not offered here - they are compositions of the primitives, not
siblings of them - though documents that carry them still open and the selection
bar still retypes to them. Pod is declared but not built: it shows dimmed and
refuses to be dragged rather than being left out of the ladder.
"""
import asyncio
import sys
from pathlib import Path

from browser_runtime import chromium_launch_kwargs
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'

CARDS = ("[...document.querySelectorAll('#palette .symbol-card')].map(b=>({"
         "id:b.dataset.symbolId,dimension:b.dataset.dimension,disabled:b.disabled,"
         "name:b.querySelector('b').textContent,caption:b.querySelector('small').textContent}))")


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = await browser.new_page(viewport={'width': 1400, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.set_content(HTML.read_text(encoding='utf-8'), wait_until='load')
        await page.wait_for_timeout(180)

        cards = await page.evaluate(CARDS)
        assert [c['id'] for c in cards] == ['point', 'path', 'plane', 'pod'], cards
        assert [c['dimension'] for c in cards] == ['0', '1', '2', '3'], cards
        assert [c['caption'] for c in cards] == [
            '0D · where', '1D · through', '2D · across', '3D · within'], cards
        assert [c['name'] for c in cards] == ['POINT', 'PATH', 'PLANE', 'POD'], cards

        # One rung per row: no two cards share a top edge.
        tops = await page.evaluate(
            "[...document.querySelectorAll('#palette .symbol-card')]"
            ".map(b=>Math.round(b.getBoundingClientRect().top))")
        assert len(set(tops)) == len(tops), tops
        assert tops == sorted(tops), tops

        # Typed Components are gone from the palette but not from the document model.
        assert all(c['id'] in ('point', 'path', 'plane', 'pod') for c in cards), cards
        assert await page.evaluate("GROUPS.Components.includes('act')")
        assert await page.evaluate(
            "[...barComponentType.options].some(o=>o.value==='act')"), \
            'retyping to a Component must still be possible'
        act = await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:300,y:300})")
        assert act['ok'], act

        # Pod is declared, dimmed, and undraggable until it is built.
        pod = next(c for c in cards if c['id'] == 'pod')
        assert pod['disabled'] is True, pod
        assert await page.locator('.symbol-card[data-symbol-id="pod"].pending').count() == 1
        before = await page.evaluate('nodes.length')
        await page.locator('.symbol-card[data-symbol-id="pod"]').click(force=True)
        await page.wait_for_timeout(150)
        assert await page.evaluate('nodes.length') == before, 'a pending rung created something'

        # The help disclosures and the grammar line are gone.
        assert await page.evaluate("document.querySelectorAll('.palette .help-disclosure').length") == 0
        assert await page.evaluate("document.querySelectorAll('.grammar-line').length") == 0

        # The ladder is the boundary recursion, and the data says so.
        ladder = await page.evaluate('DIMENSIONAL_LADDER')
        assert [r['boundedBy'] for r in ladder] == [None, 'Points', 'Paths', 'Planes'], ladder

        # A rung that is available still drags onto the canvas.
        assert await page.evaluate(
            "window.SovSchematicAPI.create('component',{symbolId:'plane',x:700,y:400}).ok")

        assert not errors, errors
        await browser.close()
    print('palette_ladder_qa ok')


if __name__ == '__main__':
    sys.exit(asyncio.run(main()) or 0)
