import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'index.html'
OUT=ROOT/'tests/beta23-attachment-parity.png'
async def main():
  async with async_playwright() as p:
    browser=await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page=await browser.new_page(viewport={'width':1200,'height':760})
    await page.set_content(HTML.read_text(),wait_until='load');await page.wait_for_timeout(180)
    await page.evaluate('''()=>{
      newSchematic();
      const a=SovSchematicData.makeComponent(diagram,{symbolId:'buffer',x:220,y:300});
      const b=SovSchematicData.makeComponent(diagram,{symbolId:'act',x:850,y:300});
      const c=SovSchematicData.makeComponent(diagram,{symbolId:'receipt',x:560,y:570});
      nodes.push(a,b,c);
      const base=SovSchematicData.makeWire(diagram,{a:a.id,aSide:'out',b:b.id,bSide:'in'});wires.push(base);render();
      const path=renderedWirePath(base),t=.52,q=path.getPointAtLength(path.getTotalLength()*t);
      const ports={out:{side:'point',face:'external',label:'tap',connectionCount:1,activeConnection:0,connections:[{id:'connection-1',name:'Connection 1',colorSlot:0,flow:'duplex',access:'read-write'}]}};
      const tap=SovSchematicData.makeComponent(diagram,{symbolId:'port',x:q.x,y:q.y,canvasId:wireCanvas(base).id,placement:{kind:'wire',wireId:base.id,t},form:{dimension:0,body:{kind:'point'}},config:{label:'tap',signalMode:'relay',presentation:{graphic:{kind:'none'},labelMode:'outside',backdrop:'none'},ports}});nodes.push(tap);syncNodeBoundaryContext(tap);render();
      addConnection(tap.id,'self',c.id,'top');render();selectPort(tap.id,'self');
      fitDiagram();
    }''')
    await page.wait_for_timeout(150)
    await page.screenshot(path=str(OUT),full_page=True)
    await browser.close()
    print(OUT)
asyncio.run(main())
