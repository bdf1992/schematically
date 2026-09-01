import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'index.html'

async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page=await browser.new_page(viewport={'width':1200,'height':800})
        errors=[]
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.set_content(HTML.read_text(), wait_until='load')
        await page.wait_for_timeout(300)
        ids=await page.evaluate("""()=>{
          const a=SovSchematicData.makeComponent(diagram,{symbolId:'act',x:260,y:300});
          const b=SovSchematicData.makeComponent(diagram,{symbolId:'buffer',x:760,y:300});
          nodes.push(a,b);
          const w=SovSchematicData.makeWire(diagram,{a:a.id,aSide:'out',b:b.id,bSide:'in'});
          wires.push(w);render();
          return {a:a.id,b:b.id,w:w.id};
        }""")
        await page.wait_for_timeout(150)
        gate=await page.evaluate("""(ids)=>{
          const w=wires.find(x=>x.id===ids.w),path=renderedWirePath(w),L=path.getTotalLength(),q=path.getPointAtLength(L*.5);
          const g=SovSchematicData.makeComponent(diagram,{symbolId:'gate',x:q.x,y:q.y});
          nodes.push(g);activeNodeDrag=g.id;render();
          const c=componentHostCandidateAtPoint(g,g.x,g.y);activeNodeDrag=null;
          applyComponentHost(g,c);render();
          return {id:g.id,canvasId:g.canvasId,placement:g.placement,backdrop:componentBackdropMode(g),host:c?.kind};
        }""",ids)
        assert gate['host']=='wire',gate
        assert gate['canvasId']==f"canvas:wire:{ids['w']}"
        assert gate['placement']['kind']=='wire' and .02 <= gate['placement']['t'] <= .98
        assert gate['backdrop']=='none'
        cls=await page.locator(f'.node[data-id="{gate["id"]}"]').get_attribute('class')
        assert 'wire-hosted' in cls and 'backdrop-none' in cls,cls
        # Host deletion should preserve the Component and rehome it.
        state=await page.evaluate("""(ids)=>{
          SovSchematicData.remove(diagram,'wire',ids.w);syncAllNodeBoundaryContext();render();
          const g=nodes.find(x=>x.symbolId==='gate');
          return {exists:!!g,canvasId:g?.canvasId,placement:g?.placement};
        }""",ids)
        assert state['exists'] and state['canvasId']=='canvas:global',state
        assert state['placement']['kind']=='surface',state
        assert not errors,errors
        await browser.close()
        print('PASS host surface QA')

asyncio.run(main())
