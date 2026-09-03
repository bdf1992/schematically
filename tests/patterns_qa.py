"""Patterns: arrangements of forms, in a second palette section.

The palette has two sections because the vocabulary has two ladders. Form offers
Point, Path, Plane and Pod. Pattern offers arrangements of those, and dropping one
runs the same creation and hosting paths a person's own gestures run: what lands is
ordinary forms and Wires with nothing marking them as having come from a Pattern.
One drop is one undoable step.

PATH is the 1D form and behaves like every other rung - it can be clicked, selected
and dragged by its body. A loose carrier, which is what PATH used to drop, is an
arrangement rather than a form and lives in the Pattern list.
"""
import asyncio
import sys
from pathlib import Path

from browser_runtime import chromium_launch_kwargs
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'

# Clearing the canvas outside history would leave the undo baseline stale, so the
# reset commits itself as a step before a Pattern is dropped on top of it.
RESET = """()=>{nodes.splice(0);wires.splice(0);routeCache.clear();arrowPoseCache.clear();
  clearComponentSelectionSet();selected=null;render();commitHistoryCapture('Clear')}"""


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = await browser.new_page(viewport={'width': 1500, 'height': 950})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.set_content(HTML.read_text(encoding='utf-8'), wait_until='load')
        await page.wait_for_timeout(200)

        # Two sections, because the vocabulary has two ladders.
        sections = await page.evaluate(
            "[...document.querySelectorAll('#palette .section h2')].map(h=>h.textContent)")
        assert sections == ['Form', 'Pattern'], sections

        # Every Pattern has a card, a one-line "made of", and a glyph that resolves.
        cards = await page.evaluate(
            "[...document.querySelectorAll('.pattern-card')].map(b=>({"
            "id:b.dataset.patternId,name:b.querySelector('b').textContent,"
            "sense:b.querySelector('small').textContent,"
            "glyph:b.querySelector('use')?.getAttribute('href')}))")
        declared = await page.evaluate("PATTERNS.map(p=>({id:p.id,name:p.name,sense:p.sense}))")
        assert [c['id'] for c in cards] == [p['id'] for p in declared], (cards, declared)
        for card, pattern in zip(cards, declared):
            assert card['name'] == pattern['name'] and card['sense'] == pattern['sense'], card
            assert card['glyph'] == f'#pat-{pattern["id"]}', card
            assert await page.evaluate('(id)=>!!document.getElementById(id)',
                                       f'pat-{pattern["id"]}'), pattern
            assert card['sense'], f'{pattern["id"]} does not say what it is made of'

        # Each Pattern puts down what it says it does, through the ordinary paths.
        expected = {
            'pair':    {'nodes': 2, 'wires': 1, 'kinds': ['point'] * 2, 'hosted': 0},
            'chain':   {'nodes': 3, 'wires': 2, 'kinds': ['point'] * 3, 'hosted': 0},
            'hub':     {'nodes': 4, 'wires': 3, 'kinds': ['point'] * 4, 'hosted': 0},
            'rail':    {'nodes': 4, 'wires': 0, 'kinds': ['path'] + ['point'] * 3, 'hosted': 3},
            'carrier': {'nodes': 0, 'wires': 1, 'kinds': [], 'hosted': 0},
            'block':   {'nodes': 1, 'wires': 0, 'kinds': ['plane'], 'hosted': 0},
            'nest':    {'nodes': 2, 'wires': 0, 'kinds': ['plane'] * 2, 'hosted': 0},
        }
        for pattern_id, want in expected.items():
            await page.evaluate(RESET)
            got = await page.evaluate("""(id)=>{
                const made=addPattern(id,600,400);
                return {made:made?made.length:null,nodes:nodes.length,wires:wires.length,
                        kinds:nodes.map(n=>n.symbolId),
                        hosted:nodes.filter(n=>n.placement&&n.placement.kind!=='surface').length};
            }""", pattern_id)
            assert got['nodes'] == want['nodes'], (pattern_id, got, want)
            assert got['wires'] == want['wires'], (pattern_id, got, want)
            assert got['kinds'] == want['kinds'], (pattern_id, got, want)
            assert got['hosted'] == want['hosted'], (pattern_id, got, want)

        # A Pattern leaves ordinary records: nothing marks them as having come from one.
        await page.evaluate(RESET)
        await page.evaluate("()=>addPattern('rail',600,400)")
        document = await page.evaluate('window.SovSchematicAPI.document.get()')
        assert not any('pattern' in str(k).lower() for c in document['components'] for k in c), \
            document['components'][0]
        # RAIL's riders are hosted on the Path itself, at their own t.
        rail = next(c for c in document['components'] if c['symbolId'] == 'path')
        riders = [c for c in document['components'] if c['symbolId'] == 'point']
        assert len(riders) == 3, riders
        for rider in riders:
            assert rider['placement']['kind'] == 'path', rider
            assert rider['placement']['hostId'] == rail['id'], rider
        assert sorted(round(r['placement']['t'], 2) for r in riders) == [0.2, 0.5, 0.8], riders

        # One drop is one undoable step, however many forms it puts down.
        await page.evaluate(RESET)
        await page.evaluate("()=>addPattern('hub',600,400)")
        await page.wait_for_timeout(160)
        assert await page.evaluate('nodes.length') == 4
        await page.evaluate('window.SovSchematicAPI.history.undo()')
        await page.wait_for_timeout(200)
        assert await page.evaluate('nodes.length') == 0, 'undo did not take the whole arrangement'
        assert await page.evaluate('wires.length') == 0

        # The whole arrangement is what was added, so the whole arrangement is selected.
        await page.evaluate(RESET)
        made = await page.evaluate("()=>addPattern('chain',600,400).map(n=>n.id)")
        assert sorted(await page.evaluate('[...selectedComponentIds]')) == sorted(made), made

        # BLOCK is a Plane that came with somewhere to attach - what a typed Component
        # always was - and it is still an ordinary Plane underneath.
        await page.evaluate(RESET)
        block = await page.evaluate("()=>addPattern('block',600,400)[0].id")
        assert await page.evaluate(
            '(id)=>componentAttachmentPointIds(nodes.find(n=>n.id===id))', block) == \
            ['left', 'right', 'top']
        assert await page.evaluate('(id)=>nodes.find(n=>n.id===id).symbolId', block) == 'plane'

        # NEST puts the inner Plane inside the outer one's interior.
        await page.evaluate(RESET)
        nest = await page.evaluate("()=>addPattern('nest',600,400).map(n=>n.id)")
        inner = await page.evaluate('(id)=>nodes.find(n=>n.id===id).canvasId', nest[1])
        assert inner == f'canvas:component:{nest[0]}', (inner, nest)

        # --- PATH is a form and behaves like one ---------------------------
        await page.evaluate(RESET)
        path = await page.evaluate("()=>addNode('path',600,400,null,{select:false}).id")
        assert await page.evaluate('(id)=>nodes.some(n=>n.id===id)', path), \
            'the palette PATH did not drop a Component'
        assert await page.evaluate('wires.length') == 0, 'the palette PATH dropped a Wire'

        # A 1D form is drawn thin, so it carries a band that makes it grabbable.
        band = f'.node[data-id="{path}"] .dimensional-path-hit'
        assert await page.locator(band).count() == 1
        box = await page.locator(band).bounding_box()
        assert box['height'] >= 16, box

        # Clicking the body selects it, and dragging the body moves it. The band is
        # re-measured because selecting reflows the bar above the canvas.
        await page.mouse.click(box['x'] + box['width'] * 0.35, box['y'] + box['height'] / 2)
        await page.wait_for_timeout(420)
        assert await page.evaluate('selected') == path, await page.evaluate('selected')
        box = await page.locator(band).bounding_box()
        cx, cy = box['x'] + box['width'] * 0.35, box['y'] + box['height'] / 2
        before = await page.evaluate('(id)=>{const n=nodes.find(n=>n.id===id);return {x:n.x,y:n.y}}', path)
        await page.mouse.move(cx, cy)
        await page.mouse.down()
        for i in range(1, 10):
            await page.mouse.move(cx + 140 * i / 9, cy + 90 * i / 9)
            await page.wait_for_timeout(18)
        await page.mouse.up()
        await page.wait_for_timeout(220)
        after = await page.evaluate('(id)=>{const n=nodes.find(n=>n.id===id);return {x:n.x,y:n.y}}', path)
        assert after != before, f'a Path did not move when dragged by its body: {before}'

        assert not errors, errors
        await browser.close()
    print('patterns_qa ok')


if __name__ == '__main__':
    sys.exit(asyncio.run(main()) or 0)
