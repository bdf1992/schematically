"""Layout quality QA: every example presents cleanly, and the audit can see each defect it claims to.

Uses scripts/layout_audit.py (SovSchematicAPI.layout.metrics). Planted defects prove each
measure fires; the examples must stay at or above the floor.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
from layout_audit import audit  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

FLOOR = 9.5
results = audit(sorted((ROOT / 'examples').glob('*.sov')))
low = [(r['source'], r['score'], r['counts']) for r in results if r['score'] < FLOOR]
assert not low, f'examples below {FLOOR}/10: {low}'
# Some defects are never acceptable in an example, whatever the score: a directed wire with no
# direction mark, wires joined at a point with no junction mark, a route leaving its container.
NEVER = {'arrowless', 'unmarked-junction', 'route-escape', 'route-through-node', 'node-overlap'}
bad = [(r['source'], k) for r in results for k in r['counts'] if k in NEVER]
assert not bad, bad

PLANTED = r"""()=>{
  const A=window.SovSchematicAPI,out={};
  const load=(components,wires=[])=>{A.document.replace({schema:SovSchematicData.DOCUMENT_SCHEMA,id:'planted',components,wires});fitDiagram();return A.layout.metrics({static:true}).counts};
  out.overflow=load([{id:'a',symbolId:'act',x:200,y:200,config:{label:'An exceptionally long label that cannot possibly fit inside'}}]);
  out.overlap=load([{id:'a',symbolId:'act',x:200,y:200},{id:'b',symbolId:'act',x:230,y:210}]);
  out.through=load([{id:'a',symbolId:'act',x:100,y:200},{id:'m',symbolId:'hold',x:300,y:200},{id:'b',symbolId:'act',x:500,y:200}],[{id:'w',a:'a',aSide:'out',b:'b',bSide:'in'}]);
  // A container whose interior is nearly blocked between two children: the fence keeps the
  // route inside even when going round the outside would be cheaper.
  const inside={canvasId:'canvas:component:box',parentId:'box'};
  out.fenced=load([{id:'box',symbolId:'plane',x:400,y:300,form:{dimension:2,regions:{interior:{state:'open'}}},config:{attachmentDefaults:'none',presentation:{size:{w:500,h:200}}}},
    {id:'a',symbolId:'act',x:230,y:300,...inside},{id:'c',symbolId:'hold',x:400,y:300,...inside,config:{presentation:{size:{w:100,h:170}}}},{id:'b',symbolId:'act',x:570,y:300,...inside}],
    [{id:'w',a:'a',aSide:'out',b:'b',bSide:'in',canvasId:'canvas:component:box'}]);
  out.clean=load([{id:'a',symbolId:'act',x:100,y:200},{id:'b',symbolId:'act',x:400,y:200}],[{id:'w',a:'a',aSide:'out',b:'b',bSide:'in'}]);
  return out;
}"""
with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(200)
    got = page.evaluate(PLANTED)
    browser.close()
assert got['overflow'].get('text-truncated'), got
assert got['overlap'].get('node-overlap'), got
# The router avoids the middle card, so a straight pass-through should not appear; the
# planted case proves the measure runs without inventing findings on a clean route.
assert not got['through'].get('route-through-node'), got
assert not got['fenced'].get('route-escape'), got
assert got['clean'] == {}, got
assert not errors, errors
print(f'PASS layout quality QA (floor {FLOOR}, {len(results)} examples)')
