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
        errors=[]; page.on('pageerror',lambda e: errors.append(str(e)))
        await page.set_content(HTML.read_text(),wait_until='load'); await page.wait_for_timeout(250)
        await page.evaluate("newSchematic()")
        # Host with an open interior and effectful Form values.
        host=await page.evaluate("""window.SovSchematicAPI.create('component',{
          symbolId:'switch',x:570,y:330,
          form:{dimension:2,body:{kind:'surface',material:'wood',thickness:24},frame:{mode:'frame',thickness:16,depth:36},regions:{interior:{state:'open'}}},
          config:{label:'Tray',presentation:{size:{w:360,h:250}}}
        }).result""")
        child=await page.evaluate("""window.SovSchematicAPI.create('component',{symbolId:'buffer',x:240,y:250,config:{label:'Payload'}}).result""")
        await page.wait_for_timeout(150)
        # Effectful Form values have visible projections.
        assert await page.locator(f'.node[data-id="{host["id"]}"] .component-body-depth').count()==1
        assert await page.locator(f'.node[data-id="{host["id"]}"] .component-frame-depth').count()==1
        assert await page.locator(f'.node[data-id="{host["id"]}"]').get_attribute('data-material')=='wood'

        # Actual pointer settle: ghost appears before release and relationship is established on release.
        cb=await page.locator(f'.node[data-id="{child["id"]}"]').bounding_box()
        hb=await page.locator(f'.node[data-id="{host["id"]}"]').bounding_box()
        sx,sy=cb['x']+cb['width']/2,cb['y']+cb['height']/2
        tx,ty=hb['x']+hb['width']*.72,hb['y']+hb['height']*.68
        await page.mouse.move(sx,sy); await page.mouse.down(); await page.mouse.move(tx,ty,steps=10); await page.wait_for_timeout(340)
        assert await page.locator('.settle-host-ghost').count()==1
        await page.mouse.up(); await page.wait_for_timeout(180)
        rel=await page.evaluate('(id)=>{const n=nodes.find(x=>x.id===id);return {parentId:n.parentId,canvasId:n.canvasId}}',child['id'])
        assert rel['parentId']==host['id'] and rel['canvasId']==f'canvas:component:{host["id"]}'

        # Pin prevents both pointer and keyboard geometry changes.
        await page.evaluate('(id)=>{const n=nodes.find(x=>x.id===id);entityEditorState(n).pinned=true;selectNode(id,{focus:false});render()}',child['id'])
        before=await page.evaluate('(id)=>{const n=nodes.find(x=>x.id===id);return [n.x,n.y]}',child['id'])
        cb=await page.locator(f'.node[data-id="{child["id"]}"]').bounding_box(); sx,sy=cb['x']+cb['width']/2,cb['y']+cb['height']/2
        await page.mouse.move(sx,sy); await page.mouse.down(); await page.mouse.move(sx+100,sy+40,steps=5); await page.mouse.up()
        await page.keyboard.press('ArrowRight'); await page.wait_for_timeout(80)
        after=await page.evaluate('(id)=>{const n=nodes.find(x=>x.id===id);return [n.x,n.y]}',child['id'])
        assert before==after

        # Lock makes browser CRUD mutation refuse instead of bypassing UI semantics.
        await page.evaluate('(id)=>{const n=nodes.find(x=>x.id===id);entityEditorState(n).pinned=false;entityEditorState(n).locked=true;render()}',child['id'])
        receipt=await page.evaluate('(id)=>window.SovSchematicAPI.update("component",id,{x:999})',child['id'])
        assert receipt['ok'] is False and 'Locked' in receipt['error']['message']

        # Hidden remains recoverable from Objects; clicking hidden row makes it visible again.
        await page.evaluate('(id)=>{const n=nodes.find(x=>x.id===id);entityEditorState(n).locked=false;entityEditorState(n).hidden=true;render();selectNode(null)}',child['id'])
        assert await page.locator(f'.node[data-id="{child["id"]}"]').count()==0
        row=page.locator('#objectsList .object-row',has_text='Payload')
        assert await row.count()==1
        await row.click(); await page.wait_for_timeout(80)
        assert await page.locator(f'.node[data-id="{child["id"]}"]').count()==1

        # Rate composition is global × source Component × Wire.
        a=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:150,y:600}).result")
        b=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'hold',x:390,y:600}).result")
        wire=await page.evaluate('(ids)=>window.SovSchematicAPI.create("wire",{a:ids[0],aSide:"out",b:ids[1],bSide:"in",config:{direction:"forward"}}).result',[a['id'],b['id']])
        assert wire and wire.get('id')
        rate=await page.evaluate('(ids)=>{const a=nodes.find(n=>n.id===ids[0]),w=wires.find(w=>w.id===ids[1]);entityEditorState(a).rate=2;entityEditorState(w).rate=.5;setGlobalTimeScale(4);return packetRateForWire(w,"forward")}',[a['id'],wire['id']])
        assert abs(rate-4)<1e-9

        assert not errors,errors
        await browser.close()
        print('PASS editor kernel extended QA')

asyncio.run(main())
