"""The screen label floors are exported once, from src/55-render.js, and every size check reads them.

LABEL_FLOORS holds the floor of every canvas label (general) and of a card title marked data-shrunk
(shrunkTitle), in screen pixels. The CSS clamps and tokens.type.screen.min keep their own literals;
this test holds them equal to the export, and scans tests/ for a floor copied as a literal.
"""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')

# The scene tests/label_zoom_qa.py builds.
SETUP = """()=>{const A=window.SovSchematicAPI;
  A.create('component',{symbolId:'plane',x:500,y:400,config:{label:'REGION'}});
  A.create('component',{symbolId:'point',x:200,y:200,config:{label:'tap'}});
  A.create('component',{symbolId:'path',x:900,y:200,config:{label:'rail'}});
  const a=A.create('component',{symbolId:'act',x:300,y:700}).result;
  const h=A.create('component',{symbolId:'hold',x:800,y:700}).result;
  A.create('wire',{a:a.id,aSide:'out',b:h.id,bSide:'in',config:{label:'flow'}});
  render();}"""
SET_ZOOM = "(z)=>{camera={x:camera.x,y:camera.y,w:BASE_VIEW.w/z,h:BASE_VIEW.h/z};applyCamera();return currentZoom()}"
MEASURE = """()=>{const scale=Math.hypot(workspace.getScreenCTM().a,workspace.getScreenCTM().b),out=[];
  for(const el of document.querySelectorAll('.node text.component-label, .node .outside-label')){
    out.push({cls:el.getAttribute('class'),shrunk:el.dataset.shrunk==='true',screen:parseFloat(getComputedStyle(el).fontSize)*scale})}
  return out}"""

with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(300)
    floors = page.evaluate('()=>LABEL_FLOORS')
    frozen = page.evaluate('()=>Object.isFrozen(LABEL_FLOORS)')
    screen_min = page.evaluate("()=>SovSchematicNotation.tokens('schematic').type.screen.min")
    page.evaluate(SETUP)
    page.wait_for_timeout(120)
    page.evaluate(SET_ZOOM, 0.25)
    page.wait_for_timeout(60)
    labels = page.evaluate(MEASURE)
    browser.close()

print('LABEL_FLOORS', floors, 'frozen', frozen, 'tokens.type.screen.min', screen_min)
assert sorted(floors) == ['general', 'shrunkTitle'], floors
assert all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in floors.values()), floors
assert floors['general'] > floors['shrunkTitle'] > 0, floors
assert frozen, 'LABEL_FLOORS is frozen'

measured = [m for m in labels if not m['shrunk']]
print(f"{len(measured)} labels at camera zoom 0.25 read {sorted({round(m['screen'], 3) for m in measured})} screen px")
assert any('component-label' in m['cls'] for m in measured) and any('outside-label' in m['cls'] for m in measured), labels
for m in measured:
    assert abs(m['screen'] - floors['general']) < 0.05, ('the CSS clamp draws the general floor', m, floors['general'])
assert floors['general'] == screen_min, ('LABEL_FLOORS.general equals tokens.type.screen.min', floors, screen_min)
assert not errors, f'page errors: {errors}'

# The scan: patterns are assembled from parts so this file does not match itself.
tok = lambda *parts: r'(?<![\w.])' + r'\.'.join(parts) + r'(?![\w.])'
literal = [re.compile(tok('11', '9')), re.compile(tok('9', '9'))]
for path in sorted((ROOT / 'tests').glob('*.py')):
    if path.name == Path(__file__).name:
        continue
    text = path.read_text(encoding='utf-8')
    for pat in literal:
        assert not pat.search(text), (path.name, 'holds a literal floor', pat.pattern)

FOUR = ['label_zoom_qa.py', 'card_text_fit_qa.py', 'authoring_review_qa.py', 'swarm_review_qa.py']
banned = ['LOW, HIGH = ' + '12', 'SHRUNK_LOW = ' + '10', '12' + '-0.05', '10' + ' - 0.05', "['em'] == " + '12']
for name in FOUR:
    text = (ROOT / 'tests' / name).read_text(encoding='utf-8')
    assert 'LABEL_FLOORS' in text, (name, 'reads LABEL_FLOORS from the page')
    for b in banned:
        assert b not in text, (name, 'holds a literal floor', b)

render = (ROOT / 'src' / '55-render.js').read_text(encoding='utf-8')
assert render.count('LABEL_FLOORS' + '=') == 1, 'LABEL_FLOORS is declared once'
for b in ['clamp(' + '12px', 'px>=' + '10']:
    assert b not in render, ('src/55-render.js holds a literal floor', b)

print('PASS label floor source QA')
