"""Performance regression QA.

A time is the machine's, so each is printed as the median of five runs and none
is asserted. The cost this test exists to catch, the palette being realised
again on a render (the Beta.16 regression), is held by a count taken from the
test's side in the same run, the way tests/run_repaint_qa.py holds its paint by
a count of writes and prints its frame time.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, statistics
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
RUNS=5
results={}

def scenario(page,n):
    return page.evaluate('''([N,RUNS])=>{
      nodes.splice(0);wires.splice(0);routeCache.clear();arrowPoseCache.clear();
      for(let i=0;i<N;i++){
        const x=180+(i%8)*110,y=150+Math.floor(i/8)*110;
        nodes.push(SovSchematicData.makeComponent(diagram,{id:`c${i+1}`,symbolId:i%3===0?'act':'buffer',x,y}));
      }
      for(let i=0;i<N-1;i++){
        wires.push(SovSchematicData.makeWire(diagram,{id:`k${i+1}`,a:`c${i+1}`,aSide:'out',b:`c${i+2}`,bSide:'in',config:{direction:'forward'}}));
      }
      const once=fn=>{const s=performance.now();fn();return performance.now()-s};
      const cold=once(()=>render());
      const samples=fn=>{const out=[];for(let i=0;i<RUNS;i++)out.push(once(fn));return out};
      let paletteCalls=0,paletteBuilds=0,inPalette=false;
      const realPalette=window.activePalette,realMono=window.activeMonoPalette;
      let warm,wiresOnly;
      try{
        window.activePalette=function(...a){paletteCalls++;const was=inPalette;inPalette=true;try{return realPalette.apply(this,a)}finally{inPalette=was}};
        window.activeMonoPalette=function(...a){if(inPalette)paletteBuilds++;return realMono.apply(this,a)};
        // One counted render first: a build seen here fails the test at once, so a
        // page whose palette cache is gone is not sampled ten more times.
        const first=once(()=>render());
        if(paletteBuilds>0)return {nodes:N,wires:wires.length,svgElements:workspace.querySelectorAll('*').length,cold,warm:[first],wiresOnly:[],signal:[],paletteCalls,paletteBuilds};
        warm=[first,...Array.from({length:RUNS-1},()=>once(()=>render()))];
        wiresOnly=samples(()=>renderWires());
      }finally{
        window.activePalette=realPalette;
        window.activeMonoPalette=realMono;
      }
      const signal=samples(()=>computeSignalState());
      return {nodes:N,wires:wires.length,svgElements:workspace.querySelectorAll('*').length,cold,warm,wiresOnly,signal,paletteCalls,paletteBuilds};
    }''',[n,RUNS])

with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page(viewport={'width':1280,'height':800})
    page.set_content(HTML,wait_until='load'); page.wait_for_timeout(150)
    results['small']=scenario(page,5)
    if results['small']['paletteBuilds']==0:
        results['medium']=scenario(page,10)
    browser.close()

for name,r in results.items():
    med=lambda k:f"{statistics.median(r[k]):.1f}" if r[k] else 'not sampled'
    print(f"{name}: {r['nodes']} cards, warm {med('warm')} ms, wiresOnly {med('wiresOnly')} ms, signal {med('signal')} ms (medians of {RUNS}), cold {r['cold']:.1f} ms, paletteCalls {r['paletteCalls']}, paletteBuilds {r['paletteBuilds']}")

for name,r in results.items():
    assert r['paletteCalls']>0, f"the wire and card passes ask for the palette: {name} {r}"
    assert r['paletteBuilds']==0, f"paletteBuilds: a warm render realises the palette again: {name} {r}"
print('PASS performance regression QA',json.dumps(results))
