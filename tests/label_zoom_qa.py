"""Labels stay legible at actual SVG screen scale, including panel/viewport fitting.

The old test multiplied by nominal camera zoom and missed sub-8px text.
Measure the SVG screen transform independently of the CSS input (#15, #38).
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text()

# Every class that draws a label on the canvas, with its base size at zoom 1.
BASE = {'.node text.component-label': 10, '.node .outside-label': 9, '.node .dimensional-point-label': 10,
        '.connection-label': 9}
LOW, HIGH = 12, 16
ZOOMS = [0.25, 0.5, 1, 2, 4, 8]

SETUP = """()=>{const A=window.SovSchematicAPI;
  const pl=A.create('component',{symbolId:'plane',x:500,y:400,config:{label:'REGION'}}).result;
  const pt=A.create('component',{symbolId:'point',x:200,y:200,config:{label:'tap'}}).result;
  const pa=A.create('component',{symbolId:'path',x:900,y:200,config:{label:'rail'}}).result;
  const a=A.create('component',{symbolId:'act',x:300,y:700}).result;
  const h=A.create('component',{symbolId:'hold',x:800,y:700}).result;
  A.create('wire',{a:a.id,aSide:'out',b:h.id,bSide:'in',config:{label:'flow'}});
  render();}"""

MEASURE = """(selectors)=>{const z=currentZoom(),scale=Math.hypot(workspace.getScreenCTM().a,workspace.getScreenCTM().b),out={zoom:z,scale,labels:{}};
  for(const sel of selectors){
    const els=[...document.querySelectorAll(sel)];
    out.labels[sel]=els.map(el=>({world:parseFloat(getComputedStyle(el).fontSize),screen:parseFloat(getComputedStyle(el).fontSize)*scale,
      box:el.getBoundingClientRect().height}));
  }
  const stroke=document.querySelector('.dimensional-point-body, .dimensional-path-body');
  out.strokeVectorEffect=stroke?getComputedStyle(stroke).vectorEffect:null;
  return out;}"""

SET_ZOOM = "(z)=>{camera={x:camera.x,y:camera.y,w:BASE_VIEW.w/z,h:BASE_VIEW.h/z};applyCamera();return currentZoom()}"


with sync_playwright() as p:
    b = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = b.new_page(viewport={'width': 1400, 'height': 900})
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(300)
    page.evaluate(SETUP)
    page.wait_for_timeout(120)

    selectors = list(BASE)
    # Screen scale includes the workspace size as well as the nominal camera zoom.
    page.evaluate(SET_ZOOM, 1)
    at_one = page.evaluate(MEASURE, selectors)
    assert abs(at_one['zoom'] - 1) < 1e-6, at_one['zoom']
    for sel, base in BASE.items():
        found = at_one['labels'][sel]
        assert found, f'no label rendered for {sel}'
        for m in found:
            assert abs(m['screen'] - min(HIGH,max(LOW,base*at_one['scale']))) < 0.05, (sel, 'zoom 1', m, base)

    # Across the sweep every label reads between LOW and HIGH screen pixels while strokes
    # keep their non-scaling rule.
    for z in ZOOMS:
        actual = page.evaluate(SET_ZOOM, z)
        page.wait_for_timeout(30)
        r = page.evaluate(MEASURE, selectors)
        assert abs(r['zoom'] - actual) < 1e-6
        assert r['strokeVectorEffect'] == 'non-scaling-stroke', r['strokeVectorEffect']
        for sel, base in BASE.items():
            for m in r['labels'][sel]:
                expected = min(HIGH, max(LOW, base * r['scale']))
                assert abs(m['screen'] - expected) < 0.05, (sel, 'zoom', actual, m, expected)
                assert LOW - 0.05 <= m['screen'] <= HIGH + 0.05, (sel, actual, m)

    # CSS follows actual screen scale, not the nominal camera readout.
    css_zoom = page.evaluate("()=>parseFloat(workspace.style.getPropertyValue('--zoom'))")
    assert abs(css_zoom - page.evaluate('()=>Math.hypot(workspace.getScreenCTM().a,workspace.getScreenCTM().b)')) < 1e-6, css_zoom

    assert not errors, f'page errors: {errors}'
    b.close()

print('PASS label zoom QA')
