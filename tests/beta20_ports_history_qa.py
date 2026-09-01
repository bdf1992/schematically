import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'index.html'

async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page=await browser.new_page(viewport={'width':1200,'height':820})
        errors=[]; page.on('pageerror',lambda e: errors.append(str(e)))
        await page.set_content(HTML.read_text(),wait_until='load'); await page.wait_for_timeout(250)
        await page.evaluate('newSchematic()')

        c=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'observe',x:360,y:280,config:{label:'Witness'}}).result")
        cid=c['id']
        await page.wait_for_timeout(80)
        # 2D = 3 canonical ports and custom label replaces type label.
        assert await page.locator(f'.node[data-id="{cid}"] .port').count()==3
        texts=await page.locator(f'.node[data-id="{cid}"] text').all_text_contents()
        assert texts.count('Witness')==1 and 'OBSERVE' not in texts, texts
        parts=await page.evaluate('(id)=>Object.keys(nodes.find(n=>n.id===id).parts.ports)',cid)
        assert len(parts)==3,parts

        # 1D = two endpoints and no transform grip.
        await page.evaluate('(id)=>window.SovSchematicAPI.update("component",id,{form:{dimension:1,body:{kind:"path"}}})',cid)
        await page.wait_for_timeout(80)
        assert await page.locator(f'.node[data-id="{cid}"] .port').count()==2
        assert await page.locator(f'.node[data-id="{cid}"] .transform-handle').count()==0
        parts=await page.evaluate('(id)=>Object.keys(nodes.find(n=>n.id===id).parts.ports)',cid)
        assert parts==['in','out'] or set(parts)=={'in','out'},parts

        # 0D = exactly one point Port.
        await page.evaluate('(id)=>window.SovSchematicAPI.update("component",id,{form:{dimension:0,body:{kind:"point"}}})',cid)
        await page.wait_for_timeout(80)
        assert await page.locator(f'.node[data-id="{cid}"] .port').count()==1
        parts=await page.evaluate('(id)=>Object.keys(nodes.find(n=>n.id===id).parts.ports)',cid)
        assert parts==['out'],parts

        # Return to 2D for ordinary delete interaction.
        await page.evaluate('(id)=>window.SovSchematicAPI.update("component",id,{form:{dimension:2,body:{kind:"surface"}}})',cid)
        await page.wait_for_timeout(80)
        await page.evaluate('(id)=>selectNode(id)',cid)
        await page.locator('#barDeleteSelection').click(); await page.wait_for_timeout(30)
        assert await page.evaluate('(id)=>nodes.some(n=>n.id===id)',cid) is False
        # Immediate keyboard Undo must work even though the contextual toolbar just disappeared.
        await page.keyboard.press('Control+z'); await page.wait_for_timeout(100)
        assert await page.evaluate('(id)=>nodes.some(n=>n.id===id)',cid) is True

        # Persistent quick Redo/Undo and Checkpoint.
        assert await page.locator('#quickUndoBtn').count()==1 and await page.locator('#quickRedoBtn').count()==1 and await page.locator('#quickCheckpointBtn').count()==1
        await page.locator('#quickRedoBtn').click(); await page.wait_for_timeout(80)
        assert await page.evaluate('(id)=>nodes.some(n=>n.id===id)',cid) is False
        await page.locator('#quickUndoBtn').click(); await page.wait_for_timeout(80)
        assert await page.evaluate('(id)=>nodes.some(n=>n.id===id)',cid) is True
        before=await page.evaluate('listCheckpoints().length')
        await page.locator('#quickCheckpointBtn').click(); await page.wait_for_timeout(80)
        after=await page.evaluate('listCheckpoints().length')
        assert after==before+1,(before,after)

        # API refuses a noncanonical 1D control port.
        a=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:150,y:600}).result")
        b=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'hold',x:430,y:600,form:{dimension:1,body:{kind:'path'}}}).result")
        receipt=await page.evaluate('(ids)=>window.SovSchematicAPI.create("wire",{a:ids[0],aSide:"out",b:ids[1],bSide:"control"})',[a['id'],b['id']])
        assert receipt['ok'] is False,receipt

        assert not errors,errors
        await browser.close()
        print('PASS Beta.24 dimensional ports + history QA')

asyncio.run(main())
