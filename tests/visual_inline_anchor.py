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
        await page.set_content(HTML.read_text(),wait_until='load');await page.wait_for_timeout(250)
        gid=await page.evaluate("""()=>{
          nodes.splice(0);wires.splice(0);wireHostPoseCache.clear();
          const a=SovSchematicData.makeComponent(diagram,{symbolId:'act',x:300,y:250});
          const b=SovSchematicData.makeComponent(diagram,{symbolId:'buffer',x:300,y:650});nodes.push(a,b);
          const w=SovSchematicData.makeWire(diagram,{a:a.id,aSide:'out',b:b.id,bSide:'in'});wires.push(w);render();
          const path=renderedWirePath(w),L=path.getTotalLength();let len=L*.1;
          for(let i=1;i<60;i++){const probe=L*i/60,a0=pathTangentAngleAtLength(path,probe);if(Math.abs(Math.abs(a0)-90)<2){len=probe;break}}
          const q=path.getPointAtLength(len),angle=pathTangentAngleAtLength(path,len);
          const g=SovSchematicData.makeComponent(diagram,{symbolId:'gate',x:q.x,y:q.y});nodes.push(g);
          applyComponentHost(g,{kind:'wire',entity:w,canvasId:wireCanvas(w).id,placement:{x:q.x,y:q.y,t:len/L,angle,distance:0}});render();
          selectNode(g.id,{focus:false});return g.id;
        }""")
        await page.wait_for_timeout(150)
        box=await page.locator(f'.node[data-id="{gid}"]').bounding_box()
        clip={'x':max(0,box['x']-100),'y':max(0,box['y']-100),'width':min(500,box['width']+200),'height':min(500,box['height']+200)}
        await page.screenshot(path=str(ROOT/'tests/beta18-wire-anchor-closeup.png'),clip=clip)
        await browser.close()
asyncio.run(main())
