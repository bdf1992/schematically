"""Panel visibility: the palette, the inspector and the top bar hide and show again.

Each part has a key (Ctrl B, Ctrl Alt B, Ctrl Backslash), a View menu item and a restore
button. A hidden part gives its space to the canvas, the label zoom follows the new canvas
size, the choice survives a reload (localStorage only) and the document is never touched.
"""
import asyncio
import http.server
import json
import socket
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_runtime import chromium_launch_kwargs
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
KEY = 'soveraeign.schematic.panels'

# part -> (key chord, menu button, restore button, dimension that grows, measured size)
PARTS = {
    'palette': ('Control+b', 'viewPaletteBtn', 'showPaletteBtn', 'width', '.palette'),
    'inspector': ('Control+Alt+b', 'viewInspectorBtn', 'showInspectorBtn', 'width', '.inspector'),
    'header': ('Control+Backslash', 'viewHeaderBtn', 'showHeaderBtn', 'height', 'header'),
}


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *args):
        pass


async def canvas(page):
    return await page.evaluate(
        '''()=>{const r=document.querySelector('.workspace-wrap').getBoundingClientRect();
        return {w:r.width,h:r.height}}''')


async def part_size(page, selector, dim):
    return await page.evaluate(
        '([sel,dim])=>document.querySelector(sel).getBoundingClientRect()[dim]', [selector, dim])


async def settled_zoom(page):
    """--zoom on #workspace once it equals the canvas's real scale (the resize observer ran)."""
    await page.wait_for_function(
        '''()=>{const m=document.getElementById("workspace").getScreenCTM();
        const s=Math.hypot(m.a,m.b);
        return Math.abs(parseFloat(document.getElementById("workspace").style.getPropertyValue("--zoom"))-s)<1e-6}''',
        timeout=5000)
    return float(await page.evaluate('document.getElementById("workspace").style.getPropertyValue("--zoom")'))


async def restore_state(page):
    return await page.evaluate(
        '''()=>({bar:!document.getElementById("panelRestore").hidden,
        shown:["showHeaderBtn","showPaletteBtn","showInspectorBtn"].filter(i=>!document.getElementById(i).hidden)})''')


async def fresh(browser, base):
    context = await browser.new_context(viewport={'width': 1400, 'height': 900})
    page = await context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    await page.goto(f'{base}/index.html', wait_until='load')
    await page.wait_for_function('()=>typeof SovSchematicAPI!=="undefined"&&typeof togglePanel==="function"')
    return context, page, errors


async def main():
    port = free_port()
    base = f'http://127.0.0.1:{port}'
    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
            context, page, errors = await fresh(browser, base)

            doc_before = json.dumps(await page.evaluate('SovSchematicAPI.file.document()'), sort_keys=True)
            shown = await canvas(page)
            zoom_shown = await settled_zoom(page)
            assert (await restore_state(page)) == {'bar': False, 'shown': []}, await restore_state(page)
            assert await page.evaluate(f'localStorage.getItem({json.dumps(KEY)})') is None

            # Each key hides its part, and the canvas grows by that part's measured size.
            previous = shown
            zooms = {}
            for part, (chord, menu, restore, dim, selector) in PARTS.items():
                size = await part_size(page, selector, dim)
                assert size > 40, (part, size)
                await page.keyboard.press(chord)
                await page.wait_for_function(
                    f'()=>document.querySelector(".app").classList.contains("hide-{part}")')
                now = await canvas(page)
                key = 'w' if dim == 'width' else 'h'
                other = 'h' if key == 'w' else 'w'
                assert abs(now[key] - previous[key] - size) <= 1, (part, now, previous, size)
                assert abs(now[other] - previous[other]) <= 1, (part, now, previous)
                zooms[part] = await settled_zoom(page)
                previous = now
            assert zooms['palette'] != zoom_shown, (zooms, zoom_shown)
            state = await restore_state(page)
            assert state['bar'] and sorted(state['shown']) == ['showHeaderBtn', 'showInspectorBtn', 'showPaletteBtn'], state
            pressed = await page.evaluate(
                '["viewPaletteBtn","viewInspectorBtn","viewHeaderBtn"].map(i=>document.getElementById(i).getAttribute("aria-pressed"))')
            assert pressed == ['false', 'false', 'false'], pressed

            # The choice survives a reload.
            await page.reload(wait_until='load')
            await page.wait_for_function('()=>typeof togglePanel==="function"')
            classes = await page.evaluate('[...document.querySelector(".app").classList]')
            for part in PARTS:
                assert f'hide-{part}' in classes, (part, classes)
            reloaded = await canvas(page)
            assert abs(reloaded['w'] - previous['w']) <= 1 and abs(reloaded['h'] - previous['h']) <= 1, (reloaded, previous)
            await settled_zoom(page)
            stored = json.loads(await page.evaluate(f'localStorage.getItem({json.dumps(KEY)})'))
            assert stored == {'palette': False, 'inspector': False, 'header': False}, stored

            # Restore buttons bring each part back, one by one; only hidden parts offer a button.
            for part, (chord, menu, restore, dim, selector) in PARTS.items():
                await page.click(f'#{restore}')
                classes = await page.evaluate('[...document.querySelector(".app").classList]')
                assert f'hide-{part}' not in classes, (part, classes)
            state = await restore_state(page)
            assert state == {'bar': False, 'shown': []}, state
            back = await canvas(page)
            assert abs(back['w'] - shown['w']) <= 1 and abs(back['h'] - shown['h']) <= 1, (back, shown)
            assert abs(await settled_zoom(page) - zoom_shown) < 1e-6

            # Each View item hides and shows its part; a second reload shows all three.
            for part, (chord, menu, restore, dim, selector) in PARTS.items():
                await page.evaluate("document.getElementById('viewMenu').hidden=false")
                await page.evaluate(f"document.getElementById('{menu}').click()")
                assert f'hide-{part}' in await page.evaluate('[...document.querySelector(".app").classList]'), part
                state = await restore_state(page)
                assert state['shown'] == [restore], (part, state)
                await page.evaluate(f"document.getElementById('{menu}').click()")
                assert f'hide-{part}' not in await page.evaluate('[...document.querySelector(".app").classList]'), part
            await page.reload(wait_until='load')
            await page.wait_for_function('()=>typeof togglePanel==="function"')
            classes = await page.evaluate('[...document.querySelector(".app").classList]')
            assert not [c for c in classes if c.startswith('hide-')], classes
            assert (await restore_state(page)) == {'bar': False, 'shown': []}

            # A stored value that is not three booleans is ignored.
            for bad in ('{"palette":false}', '{"palette":"no","inspector":false,"header":false}', 'nonsense', '[false,false,false]'):
                await page.evaluate(f'localStorage.setItem({json.dumps(KEY)},{json.dumps(bad)})')
                await page.reload(wait_until='load')
                await page.wait_for_function('()=>typeof togglePanel==="function"')
                classes = await page.evaluate('[...document.querySelector(".app").classList]')
                assert not [c for c in classes if c.startswith('hide-')], (bad, classes)

            # Keys do nothing in a text field, and the document never changes.
            await page.evaluate("localStorage.removeItem(%s)" % json.dumps(KEY))
            await page.reload(wait_until='load')
            await page.wait_for_function('()=>typeof togglePanel==="function"')
            await page.evaluate("document.getElementById('globalRate').focus()")
            await page.evaluate(
                "document.body.insertAdjacentHTML('beforeend','<input id=qaField>');document.getElementById('qaField').focus()")
            await page.keyboard.press('Control+b')
            classes = await page.evaluate('[...document.querySelector(".app").classList]')
            assert 'hide-palette' not in classes, classes

            doc_after = json.dumps(await page.evaluate('SovSchematicAPI.file.document()'), sort_keys=True)
            # meta carries a fresh stamp for each page load; everything else must be identical.
            a, b = json.loads(doc_before), json.loads(doc_after)
            a.pop('meta', None)
            b.pop('meta', None)
            assert a == b, ('document changed', [k for k in set(a) | set(b) if a.get(k) != b.get(k)])
            assert not errors, errors
            await context.close()
            await browser.close()
    finally:
        server.shutdown()
        server.server_close()
    print('PASS panel visibility QA')


if __name__ == '__main__':
    sys.exit(asyncio.run(main()) or 0)
