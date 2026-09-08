"""The settings panel stays clear of the entity it edits (issue #22).

The selection bar sits just above the selected entity, and the settings panel
used to open below the bar, exactly where the entity is. The panel is now
placed above, below, or beside the bar (beside meaning clear of the entity's
own edge), clamped inside the workspace, choosing the placement that covers
the least of the selected entity and, among equals, the one with the most free
space. It is re-placed whenever the bar moves. When a clear placement exists
it is taken; when the view is too small for one, the panel still stays inside
the workspace and covers less than the old below-the-bar placement did.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text()

RECTS = """(id)=>{const r=el=>{const b=el.getBoundingClientRect();return {left:b.left,top:b.top,right:b.right,bottom:b.bottom,w:b.width,h:b.height}};
  return {panel:r(selectionSettingsPanel),entity:r(document.querySelector(`.node[data-id="${id}"]`)),
    wrap:r(document.querySelector('.workspace-wrap')),bar:r(selectionBar),place:selectionSettingsPanel.dataset.place,hidden:selectionSettingsPanel.hidden}}"""


def overlap_area(a, b):
    w = min(a['right'], b['right']) - max(a['left'], b['left'])
    h = min(a['bottom'], b['bottom']) - max(a['top'], b['top'])
    return w * h if w > 0 and h > 0 else 0


def inside(a, wrap, margin=4):
    return (a['left'] >= wrap['left'] - margin and a['right'] <= wrap['right'] + margin
            and a['top'] >= wrap['top'] - margin and a['bottom'] <= wrap['bottom'] + margin)


def below_the_bar(r):
    # Where the panel used to open: centred under the bar.
    left = r['bar']['left'] + r['bar']['w'] / 2 - r['panel']['w'] / 2
    top = r['bar']['bottom'] + 6
    return {'left': left, 'top': top, 'right': left + r['panel']['w'], 'bottom': top + r['panel']['h']}


def check(page, cid, label, clear_expected):
    r = page.evaluate(RECTS, cid)
    assert not r['hidden'], label
    assert r['panel']['w'] > 100 and r['panel']['h'] > 60, (label, r['panel'])
    assert inside(r['panel'], r['wrap']), (label, 'panel left the workspace', r['place'], r['panel'], r['wrap'])
    covered = overlap_area(r['panel'], r['entity'])
    if clear_expected:
        assert covered == 0, (label, 'panel covers the entity', r['place'], r['panel'], r['entity'])
    else:
        old = overlap_area(below_the_bar(r), r['entity'])
        assert covered < old, (label, 'no better than below the bar', r['place'], covered, old)
    return r


def select_and_open(page, cid):
    page.evaluate("(id)=>{render();selectNode(id)}", cid)
    page.wait_for_timeout(120)
    if page.evaluate("()=>selectionSettingsPanel.hidden"):
        page.click('#barSelectionSettings')
        page.wait_for_timeout(120)


with sync_playwright() as p:
    b = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = b.new_page(viewport={'width': 1600, 'height': 1000})
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(300)

    centre = "()=>({x:camera.x+camera.w/2,y:camera.y+camera.h/2})"

    # A typed Component in the middle of the view has room beside it: the panel is clear.
    act = page.evaluate("()=>{const A=window.SovSchematicAPI;const c=" + centre + "();"
                        "return A.create('component',{symbolId:'act',x:c.x,y:c.y}).result.id}")
    select_and_open(page, act)
    mid = check(page, act, 'act mid-view', clear_expected=True)

    # A Point has room too.
    point = page.evaluate("()=>{const A=window.SovSchematicAPI;const c=" + centre + "();"
                          "return A.create('component',{symbolId:'point',x:c.x-300,y:c.y+200,config:{label:'p'}}).result.id}")
    select_and_open(page, point)
    check(page, point, 'point', clear_expected=True)

    # The placement follows the bar: pan the Point to the top edge and it is still clear.
    page.evaluate("()=>{camera={...camera,y:camera.y+camera.h*0.42};applyCamera()}")
    page.wait_for_timeout(150)
    top = check(page, point, 'point at top', clear_expected=True)
    assert top['place'] != 'above', top['place']
    page.evaluate("()=>{camera={...camera,y:camera.y-camera.h*0.42};applyCamera()}")
    page.wait_for_timeout(150)

    # A wide Plane fills the view's middle; beside it there may be no clear room. The panel
    # stays inside the workspace and covers less than the old placement did.
    plane = page.evaluate("()=>{const A=window.SovSchematicAPI;const c=" + centre + "();"
                          "return A.create('component',{symbolId:'plane',x:c.x+250,y:c.y-250,config:{label:'wide'}}).result.id}")
    select_and_open(page, plane)
    check(page, plane, 'plane', clear_expected=False)

    # Closing hides it.
    page.click('#barSelectionSettings')
    page.wait_for_timeout(60)
    assert page.evaluate("()=>selectionSettingsPanel.hidden")

    assert not errors, f'page errors: {errors}'
    b.close()

print('PASS settings panel placement QA')
