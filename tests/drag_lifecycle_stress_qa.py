import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'index.html'

async def drag_center(page, selector, dx, dy):
    box=await page.locator(selector).bounding_box()
    assert box, selector
    x=box['x']+box['width']/2; y=box['y']+box['height']/2
    await page.mouse.move(x,y); await page.mouse.down()
    await page.mouse.move(x+dx*.5,y+dy*.5,steps=2)
    await page.mouse.move(x+dx,y+dy,steps=2)
    await page.mouse.up(); await page.wait_for_timeout(12)

async def main():
  async with async_playwright() as p:
    browser=await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page=await browser.new_page(viewport={'width':1400,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    await page.set_content(HTML.read_text(),wait_until='load');await page.wait_for_timeout(180);await page.evaluate('newSchematic()')
    root=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:360,y:240}).result")
    selector=f'.node[data-id="{root["id"]}"]'
    for i in range(24):
      await drag_center(page,selector,6 if i%2==0 else -4,3 if i%3 else -2)
      st=await page.evaluate('()=>({active:!!activeNodeDragState,drag:activeNodeDrag,wire:!!wireDrag,transform:!!componentTransformGesture})')
      assert not any(st.values()),(i,st)
    # Nested child uses same component gesture path and remains nested on small moves.
    ids=await page.evaluate('''()=>{
      const host=SovSchematicData.makeComponent(diagram,{symbolId:'blank',x:780,y:300,form:{dimension:2,body:{kind:'surface'},regions:{interior:{state:'open'}}},config:{presentation:{size:{w:360,h:260}}}});nodes.push(host);componentForm(host).regions.interior.state='open';componentCanvas(host).state='open';componentConfig(host).presentation.size={w:360,h:260};
      const child=SovSchematicData.makeComponent(diagram,{symbolId:'buffer',x:780,y:300,canvasId:componentCanvas(host).id,parentId:host.id,placement:{kind:'surface',x:780,y:300}});nodes.push(child);syncAllNodeBoundaryContext();render();return {host:host.id,child:child.id};
    }''')
    child_sel=f'.node[data-id="{ids["child"]}"]'
    for i in range(12):
      await drag_center(page,child_sel,4 if i%2==0 else -3,2)
      st=await page.evaluate('(id)=>{const n=nodes.find(n=>n.id===id);return {active:!!activeNodeDragState,parent:n.parentId,canvas:n.canvasId}}',ids['child'])
      assert not st['active'] and st['parent']==ids['host'],(i,st)
    # Wire-hosted component repeatedly moves without leaving stale gesture state.
    wire=await page.evaluate('''()=>{
      const a=SovSchematicData.makeComponent(diagram,{symbolId:'hold',x:240,y:650});const b=SovSchematicData.makeComponent(diagram,{symbolId:'act',x:1050,y:650});nodes.push(a,b);const w=SovSchematicData.makeWire(diagram,{a:a.id,aSide:'out',b:b.id,bSide:'in'});wires.push(w);render();const path=renderedWirePath(w),q=path.getPointAtLength(path.getTotalLength()*.5);const g=SovSchematicData.makeComponent(diagram,{symbolId:'gate',x:q.x,y:q.y,canvasId:wireCanvas(w).id,placement:{kind:'wire',wireId:w.id,t:.5}});nodes.push(g);syncNodeBoundaryContext(g);render();return {wire:w.id,node:g.id};
    }''')
    wire_sel=f'.node[data-id="{wire["node"]}"]'
    for i in range(10):
      await drag_center(page,wire_sel,5 if i%2==0 else -4,0)
      st=await page.evaluate('(id)=>{const n=nodes.find(n=>n.id===id);return {active:!!activeNodeDragState,kind:n.placement.kind,wireId:n.placement.wireId}}',wire['node'])
      assert not st['active'] and st['kind']=='wire' and st['wireId']==wire['wire'],(i,st)
    assert not errors,errors
    await browser.close();print('PASS Beta.24 drag lifecycle stress QA: 46 repeated drags, no stranded gesture state')

asyncio.run(main())
