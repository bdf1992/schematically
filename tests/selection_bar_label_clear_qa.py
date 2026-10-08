"""The selection toolbar stays clear of a wire label.

The bar sits above the selected entity. A label that lies there, such as the label
of a wire passing over the selected card, used to be covered. The bar now takes
the side of the selection (above or below) whose bar rectangle covers less label
area, and on a tie, above. Wire labels do not move for editor chrome.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text()

PLANT = """()=>{canvasSnapEnabled=false;const A=window.SovSchematicAPI;
  A.create('component',{id:'a',symbolId:'act',x:300,y:300});
  A.create('component',{id:'b',symbolId:'act',x:700,y:300});
  A.create('component',{id:'c',symbolId:'act',x:500,y:372});
  const w=A.create('wire',{id:'w1',a:'a',aSide:'out',b:'b',bSide:'in',config:{label:'carries the record'}});
  render();return w}"""

RECTS = """()=>{const r=el=>{if(!el)return null;const b=el.getBoundingClientRect();return {left:b.left,top:b.top,right:b.right,bottom:b.bottom,w:b.width,h:b.height}};
  return {bar:r(selectionBar),place:selectionBar.dataset.place,hidden:selectionBar.hidden,
    wrap:r(document.querySelector('.workspace-wrap')),
    labels:[...document.querySelectorAll('#workspace .connection-label')].filter(e=>e.getClientRects().length).map(r),
    c:r(document.querySelector('.node[data-id="c"] rect.body'))}}"""
# c is the card's body rectangle: the node group also holds the resize and rotate handles that
# hang below a selected card, and those are editor chrome, not the card.


def overlap_area(a, b):
    w = min(a['right'], b['right']) - max(a['left'], b['left'])
    h = min(a['bottom'], b['bottom']) - max(a['top'], b['top'])
    return w * h if w > 0 and h > 0 else 0


def inside(a, wrap, margin=1):
    return (a['left'] >= wrap['left'] - margin and a['right'] <= wrap['right'] + margin
            and a['top'] >= wrap['top'] - margin and a['bottom'] <= wrap['bottom'] + margin)


def read(page, tag):
    r = page.evaluate(RECTS)
    print(tag, 'place', r['place'], 'bar', r['bar'], 'labels', r['labels'], 'c', r['c'])
    return r


def covered(r):
    return sum(overlap_area(r['bar'], l) for l in r['labels'])


with sync_playwright() as p:
    b = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = b.new_page(viewport={'width': 1600, 'height': 1000})
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(300)
    page.evaluate(PLANT)
    page.wait_for_timeout(200)

    # (a) c selected: the bar flips below the card and clears the label.
    page.evaluate("()=>{render();selectNode('c')}")
    page.wait_for_timeout(200)
    r = read(page, '(a)')
    assert r['labels'], 'the planted wire shows no label'
    assert covered(r) == 0, ('bar covers a wire label', r['bar'], r['labels'])
    assert r['place'] == 'below', r['place']
    assert inside(r['bar'], r['wrap']), ('bar left the workspace', r['bar'], r['wrap'])
    assert overlap_area(r['bar'], r['c']) == 0, ('bar covers the card', r['bar'], r['c'])

    # (b) no label: the bar is above, just over the card.
    page.evaluate("()=>SovSchematicAPI.update('wire','w1',{config:{label:''}})")
    page.evaluate("()=>{render();selectNode('c')}")
    page.wait_for_timeout(200)
    r = read(page, '(b)')
    assert r['place'] == 'above', r['place']
    gap = r['c']['top'] - r['bar']['bottom']
    assert gap <= 20, ('bar is more than 20 px above the card', gap)

    # (c) label back; drag c 150 px right by the pointer; bar and label stay apart.
    page.evaluate("()=>SovSchematicAPI.update('wire','w1',{config:{label:'carries the record'}})")
    page.evaluate("()=>{render();selectNode('c')}")
    page.wait_for_timeout(200)
    box = page.locator('.node[data-id="c"]').first.bounding_box()
    x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    for i in range(1, 7):
        page.mouse.move(x + 25 * i, y)
        page.wait_for_timeout(20)
    page.mouse.up()
    page.wait_for_timeout(300)
    r = read(page, '(c)')
    assert r['labels'], 'label gone after drag'
    assert covered(r) == 0, ('bar covers a wire label after the drag', r['bar'], r['labels'])

    # (d) the wire itself selected: the bar clears its own label.
    page.evaluate("()=>{selectWire(0)}")
    page.wait_for_timeout(200)
    r = read(page, '(d)')
    assert r['labels'], 'label missing for wire selection'
    assert covered(r) == 0, ('bar covers the selected wire label', r['bar'], r['labels'])

    # (e)
    assert not errors, f'page errors: {errors}'
    b.close()

print('PASS selection bar label clear QA')
