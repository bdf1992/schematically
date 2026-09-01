from pathlib import Path
from playwright.sync_api import sync_playwright
import json, os
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
results={}

def scenario(page,n):
    return page.evaluate('''(N)=>{
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
      const signal=once(()=>computeSignalState());
      const wiresOnly=once(()=>renderWires());
      const warm=once(()=>render());
      return {nodes:N,wires:wires.length,cold,signal,wiresOnly,warm,svgElements:workspace.querySelectorAll('*').length};
    }''',n)

with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page(viewport={'width':1280,'height':800})
    page.set_content(HTML,wait_until='load'); page.wait_for_timeout(150)
    results['small']=scenario(page,5)
    results['medium']=scenario(page,10)
    browser.close()

# Headless thresholds are intentionally loose enough for CI variance but tight enough
# to catch the Beta.16 palette-realization regression (hundreds of ms at 5 nodes).
assert results['small']['warm'] < 80, results
assert results['small']['wiresOnly'] < 80, results
assert results['small']['signal'] < 40, results
assert results['medium']['warm'] < 100, results
assert results['medium']['wiresOnly'] < 100, results
(ROOT/'tests'/'performance-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print('PASS performance regression QA',json.dumps(results))
