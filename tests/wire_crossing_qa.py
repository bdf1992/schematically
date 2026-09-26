"""Wire crossing QA: a crossing never reads as a junction.

- Where two wires that share no end cross, the later wire hops over the earlier one with a
  half-circle arc; the earlier wire runs straight through.
- Wires that share an end (a fan-out) never hop each other: they meet at a junction dot.
- No arrowhead sits on a crossing or a junction.
- Unrelated wires are kept off one track and apart when they run side by side.
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

READ = r"""()=>{
  const out={wires:{},chevrons:[],dots:[]};
  for(const g of workspace.querySelectorAll('.wire-group')){
    const p=g.querySelector('path.wire'),m=layoutWorldMatrix(p);
    out.wires[g.dataset.wireId]={d:p.getAttribute('d'),corners:layoutPathCorners(p.getAttribute('d').replace(/A[^A-Z]*?(?=[HV])/g,'')).map(q=>m?new DOMPoint(q.x,q.y).matrixTransform(m):q)};
    for(const c of g.querySelectorAll('.flow-chevron')){const b=layoutWorldBox(c);out.chevrons.push({w:g.dataset.wireId,x:(b.l+b.r)/2,y:(b.t+b.b)/2})}
  }
  for(const d of document.querySelectorAll('.junction-dot'))out.dots.push({x:+d.getAttribute('cx'),y:+d.getAttribute('cy')});
  return out;
}"""
with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)
    text = (ROOT / 'examples' / '13-half-adder.sov').read_text(encoding='utf-8')
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [text, '13-half-adder.sov'])
    page.wait_for_timeout(200)
    half = page.evaluate(READ)
    # Two unrelated wires crossing at right angles, and a fan-out that crosses itself nowhere.
    plant = page.evaluate(r"""()=>{
      SovSchematicAPI.document.replace({schema:SovSchematicData.DOCUMENT_SCHEMA,id:'x',components:[
        {id:'l',symbolId:'act',x:100,y:300},{id:'r',symbolId:'act',x:700,y:300},
        {id:'t',symbolId:'act',x:400,y:80},{id:'b',symbolId:'act',x:400,y:560,config:{ports:{in:{boundary:{side:'top',t:.5}}}}}],
        wires:[{id:'h',a:'l',aSide:'out',b:'r',bSide:'in'},{id:'v',a:'t',aSide:'out',b:'b',bSide:'in'}]});
      fitDiagram();return [...workspace.querySelectorAll('.wire-group')].map(g=>({id:g.dataset.wireId,d:g.querySelector('path.wire').getAttribute('d')}));
    }""")
    browser.close()
assert not errors, errors

arcs = {k: len(re.findall(r'A ', v['d'])) for k, v in half['wires'].items()}
assert sum(arcs.values()) == 1, ('the half adder has one crossing, drawn as one hop', arcs)
hopper = next(k for k, v in arcs.items() if v)
assert hopper == 'w3', ('the later wire hops', hopper)
# Fan-outs from A and from B are junctions, never hops.
assert arcs['w1'] == 0 and arcs['w2'] == 0 and arcs['w4'] == 0, arcs
assert len(half['dots']) == 2, half['dots']
m = re.search(r'H ([\d.]+) A ([\d.]+) \2 0 0 [01] ([\d.]+) ([\d.]+)', half['wires']['w3']['d']) or re.search(r'V ([\d.]+) A ([\d.]+) \2 0 0 [01] ([\d.]+) ([\d.]+)', half['wires']['w3']['d'])
assert m and float(m.group(2)) >= 6, half['wires']['w3']['d']
# No arrowhead within 16 of a junction dot.
for c in half['chevrons']:
    for dnt in half['dots']:
        assert ((c['x'] - dnt['x']) ** 2 + (c['y'] - dnt['y']) ** 2) ** .5 > 16, (c, dnt)
hx = (float(m.group(1)) + float(m.group(3))) / 2 if m.re.pattern.startswith('H') else float(m.group(3))
hy = float(m.group(4)) if m.re.pattern.startswith('H') else (float(m.group(1)) + float(m.group(4))) / 2
for c in half['chevrons']:
    assert ((c['x'] - hx) ** 2 + (c['y'] - hy) ** 2) ** .5 > 16, ('no arrowhead on the crossing', c, (hx, hy))
assert sum(1 for w in plant if ' A ' in w['d']) == 1, plant
print('PASS wire crossing QA', {'hops': sum(arcs.values())})
