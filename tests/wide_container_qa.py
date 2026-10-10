"""A Plane wider than 4096 canvas units is drawn at its stored width, in the editor and in a picture.

One Plane stored 6000 x 800 hosts two cards placed 2600 units either side of its centre. The test
reads the drawn body of the Plane in the editor and in the picture renderStandaloneSvg makes (loaded
as its own page), and checks both cards lie inside the body. A Plane stored 70000 wide is drawn
65536 wide, the largest side a card or Plane may have.
"""
import json
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
CX, CY = 3200, 450
MAX_SIDE = 65536


def fixture(w, h, offset):
    return {
        'schema': 'soveraeign.schematic/document@0.1', 'id': 'wide-container',
        'components': [
            {'id': 'host', 'symbolId': 'plane', 'x': CX, 'y': CY,
             'config': {'label': 'Wide plane', 'presentation': {'size': {'w': w, 'h': h}}}},
            {'id': 'left', 'symbolId': 'hold', 'x': CX - offset, 'y': CY,
             'parentId': 'host', 'canvasId': 'canvas:component:host', 'config': {'label': 'Left'}},
            {'id': 'right', 'symbolId': 'hold', 'x': CX + offset, 'y': CY,
             'parentId': 'host', 'canvasId': 'canvas:component:host', 'config': {'label': 'Right'}},
        ],
        'wires': [], 'references': [],
    }


MEASURE = '''() => {
  const host=nodes.find(n=>n.id==='host'), size=componentSize(host);
  const body=document.querySelector('.node[data-id="host"] .body').getBBox();
  const cards=['left','right'].map(id=>{const n=nodes.find(m=>m.id===id), s=componentSize(n);
    return {id, l:n.x-s.w/2, r:n.x+s.w/2, t:n.y-s.h/2, b:n.y+s.h/2}});
  return {size, painted:{w:body.width,h:body.height}, x:host.x, y:host.y, cards};
}'''

PICTURE = '''() => {
  const b=document.querySelector('.node[data-id="host"] .body').getBBox();
  return {w:b.width,h:b.height};
}'''


def main():
    with tempfile.TemporaryDirectory() as td, sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs())
        page = browser.new_page(accept_downloads=True)
        page.add_init_script('window.showSaveFilePicker=undefined;window.showOpenFilePicker=undefined;')
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('dialog', lambda d: d.accept())
        for w, h, offset, expect_w in [(6000, 800, 2600, 6000), (70000, 800, 2600, MAX_SIDE)]:
            source = Path(td) / f'wide-{w}.sov'
            source.write_text(json.dumps(fixture(w, h, offset)), encoding='utf-8')
            page.goto((ROOT / 'index.html').as_uri())
            page.locator('#fileOpenInput').set_input_files(str(source))
            page.wait_for_function("nodes.some(n=>n.id==='host')")
            state = page.evaluate(MEASURE)
            assert state['size'] == {'w': expect_w, 'h': h}, ('the stored size is kept', w, state)
            assert abs(state['painted']['w'] - expect_w) <= 0.5 and abs(state['painted']['h'] - h) <= 0.5, \
                ('the drawn body is the stored size', w, state)
            if w == 6000:
                left, right = state['x'] - expect_w / 2, state['x'] + expect_w / 2
                top, bottom = state['y'] - h / 2, state['y'] + h / 2
                for c in state['cards']:
                    assert c['l'] >= left and c['r'] <= right and c['t'] >= top and c['b'] <= bottom, \
                        ('a hosted card lies inside the drawn body', c, state)
                svg = page.evaluate('()=>renderStandaloneSvg({pad:48})')
                pic = browser.new_page()
                pic.set_content(svg, wait_until='load')
                picture = pic.evaluate(PICTURE)
                pic.close()
                assert abs(picture['w'] - expect_w) <= 0.5 and abs(picture['h'] - h) <= 0.5, \
                    ('the picture draws the same width', picture)
        assert not errors, errors
        browser.close()
    print('PASS wide container QA')


if __name__ == '__main__':
    main()
