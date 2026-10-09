"""A card's body text is drawn in canvas units at its picture size, so it stays inside its card at every zoom.

One card, 220 x 140, label 'Notes', three lines of body text. At camera zooms 1 and 0.25 the test
reads the screen scale, the body text's computed font-size and its getBBox, and the font-size the
picture (renderStandaloneSvg({pad:48}), loaded as its own page) draws it at.
- At camera zoom 0.25 the screen scale is under 0.5.
- The font-size is the same at both zooms and the picture's, within 0.01.
- The text box is the same at both zooms within 0.5 and sits inside the card body.
- The body text is three line tspans; the page logs no errors.
The live editor once held body text at 12 screen px, which is 12 / scale canvas units, while its
line step and position are canvas units, so at a low scale it overran the card.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from browser_runtime import chromium_launch_kwargs  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ZOOMS = [1, 0.25]
W, H = 220, 140
BODY = {'l': -W / 2, 'r': W / 2, 't': -H / 2, 'b': H / 2}

CARD = f"""()=>{{window.SovSchematicAPI.document.replace({{schema:SovSchematicData.DOCUMENT_SCHEMA,id:'body-zoom',components:[
    {{id:'note',symbolId:'blank',x:400,y:300,config:{{label:'Notes',presentation:{{size:{{w:{W},h:{H}}},text:'First line of notes\\nSecond line of notes\\nThird line of notes'}}}}}}],wires:[]}})}}"""

SET_ZOOM = "(z)=>{camera={x:400-BASE_VIEW.w/z/2,y:300-BASE_VIEW.h/z/2,w:BASE_VIEW.w/z,h:BASE_VIEW.h/z};applyCamera();return currentZoom()}"

MEASURE = r"""()=>{const t=nodesG.querySelector('.node[data-id="note"] > text.internal-text'),b=t.getBBox();
  return {screen:parseFloat(workspace.style.getPropertyValue('--zoom')),size:parseFloat(getComputedStyle(t).fontSize),
    box:{l:b.x,r:b.x+b.width,t:b.y,b:b.y+b.height},lines:t.querySelectorAll(':scope > tspan').length}}"""

PICTURE_SIZE = r"""()=>{const t=document.querySelector('.node[data-id="note"] > text.internal-text');
  return {size:parseFloat(getComputedStyle(t).fontSize),lines:t.querySelectorAll(':scope > tspan').length}}"""

inside = lambda a, R, tol=0.5: a['l'] >= R['l'] - tol and a['r'] <= R['r'] + tol and a['t'] >= R['t'] - tol and a['b'] <= R['b'] + tol

with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)
    page.evaluate(CARD)
    page.wait_for_timeout(150)
    zooms = {}
    for z in ZOOMS:
        page.evaluate(SET_ZOOM, z)
        page.wait_for_timeout(150)  # the block is laid out again on the next frame after a zoom
        zooms[z] = page.evaluate(MEASURE)
    svg = page.evaluate('()=>renderStandaloneSvg({pad:48})')
    pic_page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    pic_page.set_content(svg, wait_until='load')
    picture = pic_page.evaluate(PICTURE_SIZE)
    browser.close()

for z, m in zooms.items():
    print(f"zoom {z} (screen {m['screen']:.3f}): body font-size {m['size']:.3f}, lines {m['lines']}, box {m['box']}")
print(f"picture: body font-size {picture['size']:.3f}, lines {picture['lines']}")

assert not errors, errors
assert zooms[0.25]['screen'] < 0.5, ('camera zoom 0.25 is a screen scale under 0.5', zooms[0.25]['screen'])
for z, m in zooms.items():
    assert abs(m['size'] - picture['size']) <= 0.01, (z, 'the editor draws body text at the picture size', m['size'], picture['size'])
    assert m['lines'] == 3, (z, 'three line tspans', m['lines'])
    assert inside(m['box'], BODY), (z, 'body text leaves the card body', m['box'], BODY)
assert abs(zooms[1]['size'] - zooms[0.25]['size']) <= 0.01, ('body font-size in canvas units is the same at both zooms', zooms)
for k in ('l', 'r', 't', 'b'):
    assert abs(zooms[1]['box'][k] - zooms[0.25]['box'][k]) <= 0.5, ('the text box is the same at both zooms', k, zooms)
assert picture['lines'] == 3, ('the picture draws three lines', picture)
print('PASS body text zoom QA')
