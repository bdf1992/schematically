"""Section exposure QA (SECTION-MODEL.md): where a point sits on a multi-line boundary decides
what it reaches. Outer line: outside; inner line: inside (if the core is space); through a band:
both sides of it. Without a declared position the face places it, so legacy documents keep their
exposure. Wires, the simulation and the ACL all follow; the editor draws and edits the position.
"""
import json, subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')

out = subprocess.run(['node', '-e', r"""
require('./src/06-attachment-core.js');const D=require('./src/05-data-core.js');const G=require('./src/07-graph-core.js');
const doc=D.documentFromFilePayload(JSON.parse(require('fs').readFileSync('examples/12-membrane.sov','utf8')));
const ex=id=>D.portExposedCanvasIds(doc,id,'out').sort();
const r={};
r.channel=ex('channel');r.receptor=ex('receptor');r.pore=ex('pore');
r.refused=D.applyOperation(D.clone(doc),{op:'create',resource:'wire',value:{id:'x',a:'receptor',aSide:'out',b:'nucleus',bSide:'in'}}).ok;
{const {sim}=G.createSimulation(doc);sim.inject('signal',{payload:1});sim.run();r.world=sim.taps('world').arrivals.length}
// The ACL is checked where work crosses the skin through a channel.
{const d=D.clone(doc);d.components.find(c=>c.id==='cell').config.acl={entries:[{principal:'ok:*',allow:['enter','exit']}]};
 const {sim}=G.createSimulation(d);sim.inject('signal',{payload:1,principal:'eve'});sim.inject('signal',{payload:2,principal:'ok:1'});sim.run();
 r.acl=sim.refusals().filter(x=>!x.level).map(x=>x.reason);r.aclWorld=sim.taps('world').arrivals.map(m=>m.payload)}
// Legacy faces on a framed card keep their exposure (the migration).
const legacy=D.makeDocument({components:[{id:'box',symbolId:'plane',x:0,y:0,form:{dimension:2,frame:{mode:'frame',thickness:12},regions:{interior:{state:'open'}}},config:{attachmentDefaults:'none'}},
  ...['external','internal','both'].map(face=>({id:face,symbolId:'point',x:0,y:0,canvasId:'canvas:component:box',parentId:'box',placement:{kind:'edge',hostId:'box',side:'left',t:.5},form:{dimension:0},config:{ports:{out:{face}}}}))]});
r.legacy=['external','internal','both'].map(f=>D.portExposedCanvasIds(legacy,f,'out').sort().join('+'));
// A through-point on a coated card reaches only the outside: its core is solid.
const coated=D.makeDocument({components:[{id:'c',symbolId:'plane',x:0,y:0,form:{dimension:2,section:D.sectionPreset('coated',2)},config:{attachmentDefaults:'none'}},
  {id:'p',symbolId:'point',x:0,y:0,canvasId:'canvas:component:c',parentId:'c',placement:{kind:'edge',hostId:'c',side:'left',t:.5,at:{through:0}},form:{dimension:0}}]});
r.coated=D.portExposedCanvasIds(coated,'p','out');
console.log(JSON.stringify(r));
"""], cwd=ROOT, capture_output=True, text=True, check=True)
r = json.loads(out.stdout)
G_, IN = 'canvas:global', 'canvas:component:cell'
assert r['channel'] == sorted([G_, IN]) and r['pore'] == sorted([G_, IN]) and r['receptor'] == [G_], r
assert r['refused'] is False, 'the outer line does not reach inside'
assert r['world'] == 1, r
assert any('eve may not enter' in x for x in r['acl']) and r['aclWorld'] == [2], r
assert r['legacy'] == ['canvas:global', 'canvas:component:box', 'canvas:component:box+canvas:global'], r['legacy']
assert r['coated'] == ['canvas:global'], r['coated']

with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1500, 'height': 900})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.set_content(HTML, wait_until='load'); page.wait_for_timeout(200)
    page.evaluate('([t])=>{SovSchematicAPI.file.open(t,"x.sov");fitDiagram()}', [(ROOT / 'examples/12-membrane.sov').read_text(encoding='utf-8')])
    page.wait_for_timeout(120)
    # Drawn where they sit: the channel across the skin's middle, the receptor on the outline.
    g = page.evaluate("""()=>{const cell=nodes.find(n=>n.id==='cell'),L=cell.x-componentSize(cell).w/2;
      return {channel:nodes.find(n=>n.id==='channel').x-L,receptor:nodes.find(n=>n.id==='receptor').x-L,marks:document.querySelectorAll('.through-mark').length}}""")
    assert abs(g['channel'] - 6) < .01 and abs(g['receptor']) < .01 and g['marks'] == 2, g
    # The settings offer the position; moving the receptor through the skin lets it reach inside.
    page.evaluate("()=>{selectNode('receptor');openSelectionSettings('component');syncComponentVisualPanel(nodes.find(n=>n.id==='receptor'))}")
    assert page.is_visible('#formPointPosition')
    opts = page.evaluate("()=>[...document.querySelectorAll('#formPointPosition option')].map(o=>o.value)")
    assert opts == ['line:0', 'line:1', 'through:0'], opts
    assert page.input_value('#formPointPosition') == 'line:0'
    assert not page.evaluate("()=>SovSchematicAPI.create('wire',{id:'x',a:'receptor',aSide:'out',b:'nucleus',bSide:'in'}).ok")
    page.select_option('#formPointPosition', 'through:0'); page.wait_for_timeout(60)
    assert page.evaluate("()=>SovSchematicAPI.file.document().components.find(c=>c.id==='receptor').placement.at") == {'through': 0}
    assert page.evaluate("()=>SovSchematicAPI.create('wire',{id:'x',a:'receptor',aSide:'out',b:'nucleus',bSide:'in'}).ok")
    page.evaluate('()=>{SovSchematicAPI.history.undo();SovSchematicAPI.history.undo()}'); page.wait_for_timeout(60)
    assert page.evaluate("()=>SovSchematicAPI.file.document().components.find(c=>c.id==='receptor').placement.at") == {'line': 'L0'}
    # A card's own port on an inner line is drawn on that line.
    page.evaluate("""()=>{SovSchematicAPI.create('component',{id:'box',symbolId:'hold',x:300,y:700,form:{dimension:2,section:SovSchematicData.sectionPreset('section',2)},config:{ports:{in:{at:{line:1}}}}})}""")
    x = page.evaluate("()=>{const b=nodes.find(n=>n.id==='box');return portPos(b,'in').x-(b.x-componentSize(b).w/2)}")
    assert abs(x - 12) < .01, x
    assert not errors, errors
    browser.close()
print('PASS section exposure QA')
