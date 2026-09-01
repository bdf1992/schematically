"""Appearance/history separation QA (issue #13).

Appearance changes re-realize palette colors into persisted compatibility
fields. That projection must not enter semantic undo history: after an
appearance round-trip, history must hold only the real edits, and undo must
undo the last semantic operation — not an invisible palette rewrite.
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text()

with sync_playwright() as p:
    b = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = b.new_page(viewport={'width': 1280, 'height': 800})
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(300)

    page.evaluate("""()=>{
      const A=window.SovSchematicAPI;
      const s=A.create('component',{symbolId:'act',x:260,y:560}).result;
      const d=A.create('component',{symbolId:'hold',x:760,y:560}).result;
      A.create('wire',{a:s.id,aSide:'out',b:d.id,bSide:'in'});
    }""")
    page.wait_for_timeout(500)

    labels = page.evaluate('()=>window.SovSchematicAPI.history.list().map(h=>h.label)')
    assert labels == ['Create Component', 'Create Component', 'Create Wire'], labels

    # Appearance round-trip, letting the deferred history capture timer fire.
    page.evaluate("()=>window.SovSchematicAPI.view.setAppearance('dark')")
    page.wait_for_timeout(450)
    page.evaluate("()=>window.SovSchematicAPI.view.setAppearance('light')")
    page.wait_for_timeout(450)

    labels = page.evaluate('()=>window.SovSchematicAPI.history.list().map(h=>h.label)')
    assert labels == ['Create Component', 'Create Component', 'Create Wire'], \
        f'appearance change polluted history: {labels}'

    # Undo must remove the wire — the last semantic edit — not a palette rewrite.
    assert page.evaluate('()=>window.SovSchematicAPI.history.undo()')
    page.wait_for_timeout(100)
    counts = page.evaluate("()=>({c:window.SovSchematicAPI.list('component').result.length,"
                           "w:window.SovSchematicAPI.list('wire').result.length})")
    assert counts == {'c': 2, 'w': 0}, f'undo after appearance change went to the wrong entry: {counts}'

    # Redo restores it; a dark-mode redo must not corrupt colorSlot authority.
    page.evaluate("()=>window.SovSchematicAPI.view.setAppearance('dark')")
    assert page.evaluate('()=>window.SovSchematicAPI.history.redo()')
    page.wait_for_timeout(100)
    counts = page.evaluate("()=>({c:window.SovSchematicAPI.list('component').result.length,"
                           "w:window.SovSchematicAPI.list('wire').result.length})")
    assert counts == {'c': 2, 'w': 1}, f'redo failed after appearance change: {counts}'

    assert not errors, f'page errors: {errors}'
    b.close()

print('PASS appearance/history separation QA')
