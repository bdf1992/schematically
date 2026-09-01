import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'index.html'
async def main():
  async with async_playwright() as p:
    browser=await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page=await browser.new_page(viewport={'width':1200,'height':800});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    await page.set_content(HTML.read_text(),wait_until='load');await page.wait_for_timeout(200);await page.evaluate('newSchematic()')
    # 0D is itself one attachment point; no recursive port-on-port.
    p0=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'observe',x:180,y:180,form:{dimension:0,body:{kind:'point'}}}).result")
    assert await page.locator(f'.node[data-id="{p0["id"]}"] .attachment-point').count()==1
    point_state=await page.evaluate('(id)=>({points:Object.keys(nodes.find(n=>n.id===id).parts.points),ports:Object.keys(nodes.find(n=>n.id===id).parts.ports)})',p0['id'])
    assert point_state['points']==['self'],point_state
    assert point_state['ports']==['out'],point_state
    # 1D owns start/end; 2D owns left/right/top.
    p1=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'limit',x:420,y:180,form:{dimension:1,body:{kind:'path'}}}).result")
    p2=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'buffer',x:760,y:180,form:{dimension:2,body:{kind:'surface'}}}).result")
    assert await page.locator(f'.node[data-id="{p1["id"]}"] .attachment-point').count()==2
    assert await page.locator(f'.node[data-id="{p2["id"]}"] .attachment-point').count()==3
    assert await page.evaluate('(id)=>Object.keys(nodes.find(n=>n.id===id).parts.points)',p1['id'])==['start','end']
    assert await page.evaluate('(id)=>Object.keys(nodes.find(n=>n.id===id).parts.points)',p2['id'])==['left','right','top']
    # A 2D component settled on a 1D wire projects connectivity down to 1D.
    a=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:220,y:500}).result")
    b=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'hold',x:900,y:500}).result")
    w=await page.evaluate('(ids)=>window.SovSchematicAPI.create("wire",{a:ids[0],aSide:"out",b:ids[1],bSide:"in"}).result',[a['id'],b['id']]);await page.wait_for_timeout(80)
    g=await page.evaluate('(wid)=>{const n=SovSchematicData.makeComponent(diagram,{symbolId:"gate",x:560,y:500});n.canvasId=`canvas:wire:${wid}`;n.placement={kind:"wire",wireId:wid,t:.5};nodes.push(n);syncAllNodeBoundaryContext();render();return n}',w['id']);await page.wait_for_timeout(80)
    assert await page.locator(f'.node[data-id="{g["id"]}"] .attachment-point').count()==2
    assert await page.evaluate('(id)=>Object.keys(nodes.find(n=>n.id===id).parts.points)',g['id'])==['start','end']
    # Endpoint refs store canonical point ids while legacy sides remain projected.
    ref=await page.evaluate('(id)=>{const w=wires.find(x=>x.id===id);return {a:w.aAttachment,b:w.bAttachment,aSide:w.aSide,bSide:w.bSide}}',w['id'])
    assert ref['a']['pointId']=='right' and ref['aSide']=='out',ref
    assert ref['b']['pointId']=='left' and ref['bSide']=='in',ref
    # Selection uses point identity, while Port UI remains compatible.
    await page.evaluate('(id)=>selectPort(id,"self")',p0['id']);await page.wait_for_timeout(30)
    sel=await page.evaluate('selected');assert sel.startswith('point:component:'),sel
    assert not errors,errors
    await browser.close();print('PASS Beta.24 0D attachment-point refactor QA')
asyncio.run(main())
