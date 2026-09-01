"""Visual journey map for release QA.

Drives the built standalone editor through the primary user journeys and
captures a screenshot per stage. Screenshots go to JOURNEY_OUT (default
tests/journey/); the directory is a reviewable release artifact, not a
committed baseline. Fails on any page error encountered along the way.
"""
import json, os
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('JOURNEY_OUT', ROOT / 'tests' / 'journey'))
OUT.mkdir(parents=True, exist_ok=True)
HTML = (ROOT / 'index.html').read_text()

STAGES = []

def shot(page, name, caption):
    page.wait_for_timeout(150)
    path = OUT / f'{len(STAGES):02d}-{name}.png'
    page.screenshot(path=str(path), full_page=True)
    STAGES.append({'name': name, 'caption': caption, 'file': path.name})
    print(f'JOURNEY {path.name}: {caption}')

with sync_playwright() as p:
    b = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = b.new_page(viewport={'width': 1280, 'height': 800})
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(300)

    shot(page, 'boot-blank', 'Fresh boot: blank canvas, light appearance, header quick actions')

    page.click('#fileBtn')
    shot(page, 'file-menu', 'File menu open: New/Open/Save/Save As/Export SVG/Export Package/Restore Recovery')
    page.keyboard.press('Escape')

    doc = json.loads((ROOT / 'examples' / '03-contained-stage.sov').read_text())
    page.evaluate('(d)=>window.SovSchematicAPI.file.open(JSON.stringify(d),"03-contained-stage.sov")', doc)
    page.wait_for_timeout(400)
    shot(page, 'open-example', 'Golden example 03 opened via File surface: containment + boundary exposure')

    page.evaluate("""()=>{
      const A=window.SovSchematicAPI;
      const src=A.create('component',{symbolId:'act',x:260,y:560}).result;
      const dst=A.create('component',{symbolId:'hold',x:760,y:560}).result;
      A.create('wire',{a:src.id,aSide:'out',b:dst.id,bSide:'in'});
    }""")
    page.wait_for_timeout(600)
    shot(page, 'agent-authoring', 'Agent-authored Components and Wire via Browser API, live packets on the carrier')

    page.evaluate("()=>window.SovSchematicAPI.view.setAppearance('dark')")
    shot(page, 'dark-appearance', 'Same document in dark appearance: dark canvas/grid, surface-relative ink')

    page.evaluate("()=>{gridVisibleInput.checked=false;gridVisibleInput.dispatchEvent(new Event('change',{bubbles:true}))}")
    shot(page, 'dark-grid-off', 'Dark appearance with Show grid off: single grid state authority')

    page.evaluate("()=>window.SovSchematicAPI.view.setAppearance('light')")
    page.evaluate("()=>{gridVisibleInput.checked=true;gridVisibleInput.dispatchEvent(new Event('change',{bubbles:true}))}")
    page.evaluate('()=>window.SovSchematicAPI.history.undo()')
    page.evaluate('()=>window.SovSchematicAPI.history.undo()')
    page.wait_for_timeout(300)
    counts = page.evaluate("()=>({c:window.SovSchematicAPI.list('component').result.length,w:window.SovSchematicAPI.list('wire').result.length})")
    assert counts['w'] == 0, f'undo did not remove agent wire: {counts}'
    shot(page, 'undo-history', 'Semantic undo applied twice: agent wire and component removed cleanly')

    b.close()

(OUT / 'journey.json').write_text(json.dumps(STAGES, indent=2))
assert not errors, f'page errors during journey: {errors}'
print(f'JOURNEY PASS: {len(STAGES)} stages, 0 page errors -> {OUT}')
