"""The palette is the dimensional ladder.

One rung per row, read top to bottom, each naming its dimension and its sense.
The rungs are in dimensional order and the glyph says which is which, so each card
carries its name and nothing else; the dimension and the sense are on the title.
Typed Components are not offered here - they are compositions of the primitives, not
siblings of them - though documents that carry them still open and the selection
bar still retypes to them.
"""
import asyncio
import sys
from pathlib import Path

from browser_runtime import chromium_launch_kwargs
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'

CARDS = ("[...document.querySelectorAll('#palette [data-group=\"primitives\"] .symbol-card')].map(b=>({"
         "id:b.dataset.symbolId,dimension:b.dataset.dimension,disabled:b.disabled,"
         "name:b.querySelector('b').textContent,title:b.title,"
         "extraText:b.textContent.trim()}))")


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
        assert [c['name'] for c in cards] == ['POINT', 'PATH', 'PLANE', 'POD'], cards
        # The card is the name; dimension and sense live on the title.
        assert [c['extraText'] for c in cards] == ['POINT', 'PATH', 'PLANE', 'POD'], cards
        for card, sense in zip(cards, ['where', 'through', 'across', 'within']):
            assert sense in card['title'] and f"{card['dimension']}D" in card['title'], card
        assert 'bounded by Points' in cards[1]['title'], cards[1]
        assert 'bounded by Planes' in cards[3]['title'], cards[3]

        # One rung per row: no two cards share a top edge.
        tops = await page.evaluate(
            "[...document.querySelectorAll('#palette [data-group=\"primitives\"] .symbol-card')]"
            ".map(b=>Math.round(b.getBoundingClientRect().top))")
        assert len(set(tops)) == len(tops), tops
        assert tops == sorted(tops), tops

        # Patterns are a separate section; the Form ladder is only the four rungs.
        assert await page.evaluate(
            'document.querySelectorAll(`#palette [data-group="patterns"] .symbol-card`).length') > 0

        # Typed Components are gone from the palette but not from the document model.
        assert all(c['id'] in ('point', 'path', 'plane', 'pod') for c in cards), cards
        assert await page.evaluate("GROUPS.Components.includes('act')")
        assert await page.evaluate(
            "[...barComponentType.options].some(o=>o.value==='act')"), \
            'retyping to a Component must still be possible'
        act = await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:300,y:300})")
        assert act['ok'], act

        # Pod is a real rung: 3D, thick by frame, hosting like a Plane until it is spatial.
        pod = next(c for c in cards if c['id'] == 'pod')
        assert pod['disabled'] is False, pod
        assert await page.locator('.symbol-card[data-symbol-id="pod"].pending').count() == 0
        made = await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'pod',x:900,y:500}).result")
        assert made['form']['dimension'] == 3, made
        assert made['form']['frame']['mode'] == 'shell', made
        assert made['form']['frame']['depth'] > 0, made
        assert made['form']['regions']['interior']['state'] == 'open', made
        assert made['config']['attachmentDefaults'] == 'none', made
        # It is a surface: it bounds a region, hosts children, and takes size handles.
        assert await page.evaluate('(id)=>componentIsSurface(nodes.find(n=>n.id===id))', made['id'])
        assert await page.evaluate('(id)=>formHostsChildren(nodes.find(n=>n.id===id))', made['id'])
        assert await page.locator(f'.node[data-id="{made["id"]}"] .transform-handle').count() > 0

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
