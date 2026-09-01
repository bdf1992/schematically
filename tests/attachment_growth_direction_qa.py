import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs

ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'index.html'

async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page=await browser.new_page(viewport={'width':1300,'height':900})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        await page.set_content(HTML.read_text(),wait_until='load');await page.wait_for_timeout(150)

        # Canonical 1D endpoint names must retain their endpoint semantics when
        # release-to-grow creates a new Component in empty space.
        await page.evaluate('''()=>{
          nodes.splice(0);wires.splice(0);routeCache.clear();arrowPoseCache.clear();
          const path=SovSchematicData.makeComponent(diagram,{id:'path',symbolId:'act',x:300,y:300});
          path.form.dimension=1;nodes.push(path);ensureComponentStructure(path);render();
          growBlankFromConnection(path.id,'end',{x:650,y:300},{});
        }''')
        state=await page.evaluate('''()=>({
          nodes:nodes.map(n=>({id:n.id,dim:componentForm(n).dimension})),
          wires:wires.map(w=>({a:w.a,aSide:w.aSide,b:w.b,bSide:w.bSide,aPoint:w.aAttachment?.pointId,bPoint:w.bAttachment?.pointId}))
        })''')
        assert len(state['wires'])==1,state
        w=state['wires'][0]
        assert w['a']=='path' and w['aPoint']=='end' and w['aSide']=='out',w
        assert w['bPoint']=='left' and w['bSide']=='in',w

        await page.evaluate('''()=>{
          nodes.splice(0);wires.splice(0);routeCache.clear();arrowPoseCache.clear();
          const path=SovSchematicData.makeComponent(diagram,{id:'path',symbolId:'act',x:650,y:300});
          path.form.dimension=1;nodes.push(path);ensureComponentStructure(path);render();
          growBlankFromConnection(path.id,'start',{x:300,y:300},{});
        }''')
        w=await page.evaluate('''()=>{const w=wires[0];return {a:w.a,aSide:w.aSide,b:w.b,bSide:w.bSide,aPoint:w.aAttachment?.pointId,bPoint:w.bAttachment?.pointId}}''')
        assert w['b']=='path' and w['bPoint']=='start' and w['bSide']=='in',w
        assert w['aPoint']=='right' and w['aSide']=='out',w

        # 0D self is compatibility-projected to output, so it grows downstream,
        # never through the old fallback control branch.
        await page.evaluate('''()=>{
          nodes.splice(0);wires.splice(0);routeCache.clear();arrowPoseCache.clear();
          const point=SovSchematicData.makeComponent(diagram,{id:'point',symbolId:'observe',x:300,y:500});
          point.form.dimension=0;nodes.push(point);ensureComponentStructure(point);render();
          growBlankFromConnection(point.id,'self',{x:650,y:500},{});
        }''')
        w=await page.evaluate('''()=>{const w=wires[0];return {a:w.a,aSide:w.aSide,b:w.b,bSide:w.bSide,aPoint:w.aAttachment?.pointId,bPoint:w.bAttachment?.pointId}}''')
        assert w['a']=='point' and w['aPoint']=='self' and w['aSide']=='out',w
        assert w['bSide']=='in',w

        # 2D top remains control semantics through the same descriptor resolver.
        await page.evaluate('''()=>{
          nodes.splice(0);wires.splice(0);routeCache.clear();arrowPoseCache.clear();
          const surface=SovSchematicData.makeComponent(diagram,{id:'surface',symbolId:'act',x:650,y:650});
          nodes.push(surface);ensureComponentStructure(surface);render();
          growBlankFromConnection(surface.id,'top',{x:650,y:350},{});
        }''')
        w=await page.evaluate('''()=>{const w=wires[0];return {a:w.a,aSide:w.aSide,b:w.b,bSide:w.bSide,aPoint:w.aAttachment?.pointId,bPoint:w.bAttachment?.pointId}}''')
        assert w['b']=='surface' and w['bPoint']=='top' and w['bSide']=='control',w
        assert not errors,errors
        await browser.close()
    print('PASS canonical attachment growth direction QA')

asyncio.run(main())
