import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'index.html'
OUT=ROOT/'tests/beta16-wire-host.png'
async def main():
  async with async_playwright() as p:
    browser=await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page=await browser.new_page(viewport={'width':1300,'height':760})
    await page.set_content(HTML.read_text(),wait_until='load');await page.wait_for_timeout(250)
    await page.evaluate("""()=>{
      nodes.splice(0,nodes.length);wires.splice(0,wires.length);diagram.references.splice(0,diagram.references.length);
      const a=SovSchematicData.makeComponent(diagram,{symbolId:'act',x:390,y:350,config:{label:'Source'}});
      const b=SovSchematicData.makeComponent(diagram,{symbolId:'buffer',x:950,y:350,config:{label:'Buffer'}});
      nodes.push(a,b);const w=SovSchematicData.makeWire(diagram,{a:a.id,aSide:'out',b:b.id,bSide:'in',config:{direction:'forward',label:'Signal'}});wires.push(w);render();
      const path=renderedWirePath(w),L=path.getTotalLength(),q=path.getPointAtLength(L*.5);
      const g=SovSchematicData.makeComponent(diagram,{symbolId:'gate',x:q.x,y:q.y,config:{label:'Gate'}});nodes.push(g);activeNodeDrag=g.id;render();const c=componentHostCandidateAtPoint(g,g.x,g.y);activeNodeDrag=null;applyComponentHost(g,c);render();selectNode(g.id,{focus:false});fitDiagram();
    }""")
    await page.wait_for_timeout(250)
    await page.screenshot(path=str(OUT),full_page=True)
    await browser.close()
asyncio.run(main())
