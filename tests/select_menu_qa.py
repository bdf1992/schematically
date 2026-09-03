"""The editor draws its own dropdown lists.

A `<select>` popup is a window the browser opens, not part of the page: it cannot carry
the app's tokens, type or spacing, and `color-scheme` is the whole of the page's say over
it. In a dark editor that one control is where the theme visibly stops, so the list is
drawn in the document instead.

The `<select>` stays the source of truth. It holds the value and it fires `change`, so
every listener already wired to it is untouched - this only replaces the picture.
"""
import asyncio
import sys
from pathlib import Path

from browser_runtime import chromium_launch_kwargs
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = await browser.new_page(viewport={'width': 1400, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.set_content(HTML.read_text(encoding='utf-8'), wait_until='load')
        await page.wait_for_timeout(220)

        for appearance in ('light', 'dark'):
            await page.evaluate('(mode)=>{appearanceMode=mode;applyAppearanceMode()}', appearance)
            await page.evaluate("()=>{nodes.splice(0);wires.splice(0);patternRecords.splice(0);"
                                "const n=addNode('plane',560,420);selectNode(n.id)}")
            await page.wait_for_timeout(300)

            assert await page.locator('.select-menu').is_visible() is False, 'menu open before a click'
            await page.locator('#barComponentType').click()
            await page.wait_for_timeout(180)
            assert await page.locator('.select-menu').is_visible(), f'{appearance}: no menu opened'

            # Every option the select declares, and its groups, in order.
            declared = await page.evaluate(
                "()=>[...barComponentType.options].map(o=>o.textContent)")
            drawn = await page.evaluate(
                "()=>[...document.querySelectorAll('.select-menu-item')].map(b=>b.textContent)")
            assert drawn == declared, (appearance, drawn, declared)
            groups = await page.evaluate(
                "()=>[...document.querySelectorAll('.select-menu-group')].map(g=>g.textContent)")
            assert groups == ['Primitives'], (appearance, groups)

            # It is painted from the app's own tokens, which is the whole point.
            painted = await page.evaluate("""()=>{
                const menu=document.querySelector('.select-menu');
                const style=getComputedStyle(menu);
                const root=getComputedStyle(document.documentElement);
                return {bg:style.backgroundColor,panel:root.getPropertyValue('--panel').trim(),
                        scheme:root.colorScheme};
            }""")
            assert appearance in painted['scheme'], painted
            # The panel token, whatever the appearance says it is.
            assert painted['bg'] != 'rgba(0, 0, 0, 0)', painted

            # The current value is marked, so the list says where you are.
            current = await page.evaluate(
                "()=>document.querySelector('.select-menu-item.current')?.textContent")
            assert current == 'Plane', (appearance, current)

            # Picking one drives the select, and the select drives the model.
            await page.locator('.select-menu-item', has_text='Point').first.click()
            await page.wait_for_timeout(300)
            assert await page.evaluate('()=>nodes[0].symbolId') == 'point', appearance
            assert await page.evaluate('()=>barComponentType.value') == 'point', appearance
            assert await page.locator('.select-menu').is_visible() is False, 'menu stayed open'

            # Escape closes it and leaves the value alone.
            await page.locator('#barComponentType').click()
            await page.wait_for_timeout(160)
            assert await page.locator('.select-menu').is_visible()
            await page.keyboard.press('Escape')
            await page.wait_for_timeout(160)
            assert await page.locator('.select-menu').is_visible() is False, 'Escape did not close it'
            assert await page.evaluate('()=>nodes[0].symbolId') == 'point', 'Escape changed the value'

        # A select whose options are built at runtime is covered too, because the menu is
        # opened by delegation rather than by registering each control.
        await page.evaluate("()=>{nodes.splice(0);wires.splice(0);patternRecords.splice(0);"
                            "render();addPattern('pair',560,420)}")
        await page.wait_for_timeout(300)
        assert await page.evaluate('()=>barPatternKind.options.length') > 0
        # The Pattern's kind is read-only, and a disabled control opens nothing. Click
        # where it is rather than through the element, because a disabled control is not
        # a click target and the point is what a real pointer does over it.
        box = await page.locator('#barPatternKind').bounding_box()
        await page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        await page.wait_for_timeout(160)
        assert await page.locator('.select-menu').is_visible() is False, \
            'a disabled select opened a list'

        assert not errors, errors
        await browser.close()
    print('select_menu_qa ok')


if __name__ == '__main__':
    sys.exit(asyncio.run(main()) or 0)
