"""Header menu dismissal QA (issue #12).

File, Edit, and View menus must dismiss on Escape and on pointerdown over any
outside surface — including the canvas and palette, whose gesture handlers
stopPropagation and must not veto dismissal. The owning button still toggles.
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text()

CANVAS = (640, 600)
PALETTE = (120, 400)
INSPECTOR = (1100, 500)

with sync_playwright() as p:
    b = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = b.new_page(viewport={'width': 1280, 'height': 800})
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(300)

    for btn, menu in [('#fileBtn', '#fileMenu'), ('#editBtn', '#editMenu'), ('#viewBtn', '#viewMenu')]:
        def open_menu():
            page.click(btn)
            page.wait_for_timeout(80)
            assert page.locator(menu).is_visible(), f'{menu} did not open from {btn}'

        for label, dismiss in [
            ('escape', lambda: page.keyboard.press('Escape')),
            ('canvas pointerdown', lambda: page.mouse.click(*CANVAS)),
            ('palette pointerdown', lambda: page.mouse.click(*PALETTE)),
            ('inspector pointerdown', lambda: page.mouse.click(*INSPECTOR)),
            ('button re-toggle', lambda: page.click(btn)),
        ]:
            open_menu()
            dismiss()
            page.wait_for_timeout(120)
            assert not page.locator(menu).is_visible(), f'{menu} not dismissed by {label}'

    # Dismissal must not have destroyed menu function: it reopens and its items act.
    page.click('#fileBtn'); page.wait_for_timeout(80)
    assert page.locator('#fileMenu').is_visible()
    page.click('#fileBtn'); page.wait_for_timeout(80)

    assert not errors, f'page errors: {errors}'
    b.close()

print('PASS header menu dismissal QA')
