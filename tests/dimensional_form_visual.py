import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tests/beta19-dimensions.png'
async def main():
  async with async_playwright() as p:
    browser=await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page=await browser.new_page(viewport={'width':1200,'height':760})
    await page.set_content((ROOT/'index.html').read_text(),wait_until='load');await page.wait_for_timeout(200)
    await page.evaluate("""()=>{
      nodes.splice(0,nodes.length);wires.splice(0,wires.length);diagram.references.splice(0,diagram.references.length);
      const path=SovSchematicData.makeComponent(diagram,{symbolId:'limit',x:520,y:320,config:{label:'1D PATH'}});path.form={dimension:1,body:{kind:'path',material:'metal',thickness:8},frame:{mode:'none',thickness:0,depth:0},regions:{interior:{state:'closed'}}};nodes.push(path);
      const surface=SovSchematicData.makeComponent(diagram,{symbolId:'buffer',x:850,y:450,config:{label:'2D SURFACE'}});surface.form={dimension:2,body:{kind:'surface',material:'panel',thickness:0},frame:{mode:'frame',thickness:10,depth:0},regions:{interior:{state:'closed'}}};nodes.push(surface);
      const point=SovSchematicData.makeComponent(diagram,{symbolId:'port',x:520,y:320,config:{label:'0D'}});point.form={dimension:0,body:{kind:'point',material:'generic',thickness:3},frame:{mode:'none',thickness:0,depth:0},regions:{interior:{state:'closed'}}};nodes.push(point);render();
      const c=componentHostCandidateAtPoint(point,610,320);applyComponentHost(point,c);render();fitDiagram();
    }""")
    await page.wait_for_timeout(250)
    errors=[];page.on('pageerror',lambda e: errors.append(str(e)))
    await page.screenshot(path=str(OUT),full_page=True)
    assert await page.locator('.dimensional-path-body').count()==1
    assert await page.locator('.dimensional-point-body').count()==1
    await browser.close()
    print(OUT)
asyncio.run(main())
