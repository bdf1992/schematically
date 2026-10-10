"""Wire mark minimum size QA: a wire's direction mark is never under 7 screen pixels long.

On a planted document that carries the work-engine notation, with two straight wires 300 long, one
of kind flow (an open chevron) and one of kind stream (a filled head), in Chromium:
  - at camera zoom 0.25 the flow mark's d does not end in Z and its fill is none, the stream mark's
    d ends in Z and its fill is not none, and each mark's screen box is 7 px long (the wires run
    along x, so the length of a mark is the width of its box);
  - at camera zoom 1 and 4 each mark's screen box is 7 times the screen scale long, or 7 px where
    that is less: above the floor the mark follows the camera as before;
  - at every zoom each mark's d and transform attribute are the ones drawn at zoom 1.
The page logs no errors.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

NOTATION = 'data/work-engine.notation.json'
KINDS = ['flow', 'stream']
MARK_FLOOR_PX = 7
TOLERANCE_PX = 0.05

PLANT = r"""(pack)=>{
  const A=window.SovSchematicAPI,D=SovSchematicData,names=['flow','stream'];
  const doc=dx=>({schema:D.DOCUMENT_SCHEMA,id:'wire-mark-minimum-size',notation:'work-engine',
    components:names.flatMap((k,i)=>[
      {id:'a'+i,symbolId:'act',x:200,y:120+i*150,config:{label:'From '+k}},
      {id:'b'+i,symbolId:'act',x:200+dx,y:120+i*150,config:{label:'To '+k}}]),
    wires:names.map((k,i)=>({id:'w-'+k,a:'a'+i,aSide:'out',b:'b'+i,bSide:'in',config:{kind:k}})),
    references:[{id:'notation-work-engine',kind:'notation',label:'Work Engine',data:pack}]});
  const lengthOf=()=>document.querySelector('.wire-group[data-wire-id="w-stream"] path.wire').getTotalLength();
  let dx=500;A.document.replace(doc(dx));dx+=300-lengthOf();A.document.replace(doc(dx));fitDiagram();
  return A.markers();
}"""
SET_ZOOM = "(z)=>{camera={x:camera.x,y:camera.y,w:BASE_VIEW.w/z,h:BASE_VIEW.h/z};applyCamera();return currentZoom()}"
READ = r"""()=>{
  const m=workspace.getScreenCTM(),out={zoom:currentZoom(),screen:Math.hypot(m.a,m.b),marks:{}};
  for(const k of ['flow','stream']){
    const marks=[...document.querySelectorAll(`.wire-group[data-wire-id="w-${k}"] .flow-chevron`)];
    const r=marks[0]?.getBoundingClientRect();
    out.marks[k]={count:marks.length,d:marks[0]?.getAttribute('d')??null,transform:marks[0]?.getAttribute('transform')??null,
      fill:marks[0]?getComputedStyle(marks[0]).fill:null,long:r?r.width:0,across:r?r.height:0};
  }
  return out;
}"""


def main() -> None:
    pack = json.loads((ROOT / NOTATION).read_text(encoding='utf-8'))
    errors: list[str] = []
    seen = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(250)
        markers = page.evaluate(PLANT, pack)
        for zoom in (1, 0.25, 4):
            assert abs(page.evaluate(SET_ZOOM, zoom) - zoom) < 1e-6, ('the camera did not take the zoom', zoom)
            page.wait_for_timeout(60)
            seen[zoom] = page.evaluate(READ)
        browser.close()
    assert not errors, errors
    assert not markers, ('the planted document has markers', markers)

    for zoom, r in seen.items():
        expected = max(MARK_FLOOR_PX, MARK_FLOOR_PX * r['screen'])
        for kind in KINDS:
            mark = r['marks'][kind]
            assert mark['count'] == 1, ('a planted wire does not carry one mark', zoom, kind, mark)
            assert mark['long'] >= MARK_FLOOR_PX - TOLERANCE_PX, ('a mark is under 7 screen px long', zoom, kind, mark['long'])
            assert abs(mark['long'] - expected) < TOLERANCE_PX, ('a mark is not 7 px or 7 times the screen scale long', zoom, kind, mark['long'], expected)
            assert (mark['d'], mark['transform']) == (seen[1]['marks'][kind]['d'], seen[1]['marks'][kind]['transform']), ('a mark is drawn from other attributes than at zoom 1', zoom, kind, mark)
    low = seen[0.25]
    assert low['screen'] < 1, ('zoom 0.25 does not put the marks under the floor', low['screen'])
    flow, stream = low['marks']['flow'], low['marks']['stream']
    assert not flow['d'].endswith('Z') and flow['fill'] == 'none', ('the flow mark is not an open path at zoom 0.25', flow)
    assert stream['d'].endswith('Z') and stream['fill'] not in (None, '', 'none'), ('the stream mark is not a filled closed path at zoom 0.25', stream)

    print('PASS wire mark minimum size QA', {z: {'screen scale': round(r['screen'], 4), **{k: round(r['marks'][k]['long'], 2) for k in KINDS}} for z, r in seen.items()})


if __name__ == '__main__':
    main()
