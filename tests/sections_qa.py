"""Sections QA (SECTION-MODEL.md): a form's lines and the regions between them.

Presets from the settings panel author form.section, and the legacy frame / interior fields
become its projection; a legacy frame is drawn as the two-line section it always meant; each
card preset draws its inner lines; wires draw strips, lanes and pipes; the file round-trips;
a section whose band count is not one fewer than its lines is refused, never repaired.
"""
import json, subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')

# Data core: validation refuses a broken section on components and wires alike.
out = subprocess.run(['node', '-e', r"""
require('./src/06-attachment-core.js');const D=require('./src/05-data-core.js');
const bad=D.makeDocument({components:[{id:'a',symbolId:'act',x:0,y:0,form:{dimension:2,section:{lines:[{},{},{}],bands:[{}]}}},{id:'b',symbolId:'act',x:300,y:0}],
  wires:[{id:'w',a:'a',aSide:'out',b:'b',bSide:'in',form:{section:{lines:[{},{}],bands:[]}}}]});
const v=D.validateDocument(bad);
console.log(JSON.stringify({ok:v.ok,errors:v.errors.length,derived:D.componentSection({form:{dimension:2,frame:{mode:'shell',thickness:9}}}).lines.length}));
"""], cwd=ROOT, capture_output=True, text=True, check=True)
r = json.loads(out.stdout)
assert r == {'ok': False, 'errors': 2, 'derived': 2}, r

with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1500, 'height': 900})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.set_content(HTML, wait_until='load'); page.wait_for_timeout(200)
    page.evaluate('([t])=>{SovSchematicAPI.file.open(t,"x.sov");fitDiagram()}', [(ROOT / 'examples/11-sections.sov').read_text(encoding='utf-8')])
    page.wait_for_timeout(120)
    lines = page.evaluate("()=>Object.fromEntries(['disk','circle','cell','coated','double'].map(id=>[id,document.querySelectorAll(`.node[data-id=\"${id}\"] > .section-line`).length]))")
    assert lines == {'disk': 0, 'circle': 0, 'cell': 1, 'coated': 1, 'double': 3}, lines
    fills = page.evaluate("()=>['disk','circle'].map(id=>document.querySelector(`.node[data-id=\"${id}\"] > .body`).getAttribute('class'))")
    assert 'fill-solid' in fills[0] and 'fill-space' in fills[1], fills
    layers = page.evaluate("()=>Object.fromEntries(['w1','w2','w3','w4'].map(id=>[id,document.querySelectorAll(`.wire-group[data-wire-id=\"${id}\"] .wire-section`).length]))")
    assert layers == {'w1': 0, 'w2': 2, 'w3': 2, 'w4': 4}, layers
    # Labels sit inside the innermost line.
    inside = page.evaluate("""()=>{const t=document.querySelector('.node[data-id="double"] > text.component-label').getBBox(),r=[...document.querySelectorAll('.node[data-id="double"] > .section-line')].at(-1).getBBox();
      return t.x>=r.x&&t.x+t.width<=r.x+r.width&&t.y>=r.y&&t.y+t.height<=r.y+r.height}""")
    assert inside
    # The settings panel authors a section; frame and interior follow as its projection.
    page.evaluate("()=>{selectNode('disk');openSelectionSettings('component');syncComponentVisualPanel(nodes.find(n=>n.id==='disk'))}")
    assert page.input_value('#formSection') == 'disk'
    page.select_option('#formSection', 'double-wall'); page.wait_for_timeout(60)
    f = page.evaluate("()=>SovSchematicAPI.file.document().components.find(c=>c.id==='disk').form")
    assert len(f['section']['lines']) == 4 and f['frame']['mode'] == 'frame' and f['regions']['interior']['state'] == 'open', f
    assert page.evaluate("()=>document.querySelectorAll('.node[data-id=\"disk\"] > .section-line').length") == 3
    page.evaluate('()=>SovSchematicAPI.history.undo()'); page.wait_for_timeout(60)
    assert page.evaluate("()=>SovSchematicAPI.file.document().components.find(c=>c.id==='disk').form.section.lines.length") == 1
    # The wire settings choose a wire's section.
    page.evaluate("()=>{selectWire(wires.findIndex(w=>w.id==='w1'));openSelectionSettings('wire')}")
    assert page.input_value('#barWireSection') == 'line'
    page.select_option('#barWireSection', 'pipe'); page.wait_for_timeout(60)
    assert page.evaluate("()=>document.querySelectorAll('.wire-group[data-wire-id=\"w1\"] .wire-section').length") == 4
    # A legacy frame is the two-line section it always meant, bevel included.
    page.evaluate("""()=>SovSchematicAPI.create('component',{id:'legacy',symbolId:'hold',x:300,y:700,form:{dimension:2,frame:{mode:'frame',thickness:14,depth:30}}})""")
    page.wait_for_timeout(60)
    assert page.evaluate("()=>document.querySelectorAll('.node[data-id=\"legacy\"] > .section-line').length") == 1
    assert page.evaluate("()=>document.querySelectorAll('.node[data-id=\"legacy\"] .component-frame-depth').length") == 1
    assert 'section' not in page.evaluate("()=>SovSchematicAPI.file.document().components.find(c=>c.id==='legacy').form"), 'a derived section is never written'
    # Round trip.
    doc = page.evaluate('()=>SovSchematicAPI.file.document()')
    page.evaluate('(d)=>SovSchematicAPI.file.open(JSON.stringify(d),"y.sov")', doc); page.wait_for_timeout(60)
    assert page.evaluate("()=>document.querySelectorAll('.wire-group[data-wire-id=\"w1\"] .wire-section').length") == 4
    assert not errors, errors
    browser.close()
print('PASS sections QA')
