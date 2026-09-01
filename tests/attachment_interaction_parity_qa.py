import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'index.html'

async def main():
  async with async_playwright() as p:
    browser=await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page=await browser.new_page(viewport={'width':1400,'height':900})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    await page.set_content(HTML.read_text(),wait_until='load');await page.wait_for_timeout(180)
    await page.evaluate('newSchematic()')
    state=await page.evaluate('''()=>{
      const a=SovSchematicData.makeComponent(diagram,{symbolId:'buffer',x:180,y:300});
      const b=SovSchematicData.makeComponent(diagram,{symbolId:'act',x:760,y:300});
      nodes.push(a,b);
      const base=SovSchematicData.makeWire(diagram,{a:a.id,aSide:'out',b:b.id,bSide:'in'});wires.push(base);
      base.attachments.push({id:'legacy-tap',kind:'attachment-point',type:'point',t:.5,placement:{kind:'wire',t:.5},config:{face:'external',label:'tap',connections:[{id:'connection-1',name:'Connection 1',colorSlot:0,flow:'duplex',access:'read-write'}],activeConnection:0}});
      SovSchematicData.normalizeDocument(diagram);syncAllNodeBoundaryContext();render();
      const tap=nodes.find(n=>n.placement?.sourceAttachmentId==='legacy-tap');
      const c=SovSchematicData.makeComponent(diagram,{symbolId:'hold',x:1100,y:300});nodes.push(c);syncNodeBoundaryContext(c);render();
      return {a:a.id,b:b.id,base:base.id,tap:tap?.id,c:c.id,remaining:base.attachments.length,tapCanvas:tap?.canvasId,tapPoints:Object.keys(tap?.parts?.points||{}),reach:SovSchematicData.connectionReachability(diagram,tap.id,'self',c.id,'left')};
    }''')
    assert state['tap'],state
    assert state['remaining']==0,state
    assert state['tapPoints']==['self'],state
    assert state['reach']['ok'] and state['reach']['canvasId']=='canvas:global',state
    # No legacy Wire-owned visible port survives migration.
    assert await page.locator('.port[data-owner-kind="wire"]').count()==0
    # The migrated tap uses the ordinary Component attachment hit/selection path.
    assert await page.locator(f'.node[data-id="{state["tap"]}"] .port-hit[data-point="self"]').count()==1
    await page.evaluate('(id)=>selectPort(id,"self")',state['tap'])
    assert (await page.evaluate('selected')).startswith('point:component:')
    # Same addConnection path works from 1D-hosted 0D point -> 2D boundary.
    ok=await page.evaluate('(ids)=>addConnection(ids[0],"self",ids[1],"left")',[state['tap'],state['c']])
    assert ok
    branch=await page.evaluate('(id)=>wires.find(w=>(w.a===id||w.b===id)&&w.id!==arguments?.[1])',state['tap']) if False else None
    await page.wait_for_timeout(60)
    branch_info=await page.evaluate('(id)=>{const w=wires.find(w=>w.a===id||w.b===id);const hosted=wires.filter(w=>w.a===id||w.b===id);return hosted.map(w=>({id:w.id,a:w.a,b:w.b,aSide:w.aSide,bSide:w.bSide,canvasId:w.canvasId}))}',state['tap'])
    assert any(x['canvasId']=='canvas:global' for x in branch_info),branch_info
    # Reverse direction: ordinary 2D point can target a Wire-hosted 0D point through the same legality path.
    d=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'buffer',x:1050,y:520}).result")
    ok2=await page.evaluate('(ids)=>addConnection(ids[0],"right",ids[1],"self")',[d['id'],state['tap']])
    assert ok2
    # +Port now creates an ordinary 0D hosted Component, not wire.attachments[] state.
    before=await page.evaluate('(wid)=>{const i=wires.findIndex(w=>w.id===wid);selectWire(i);return {nodes:nodes.length,parts:wires[i].attachments.length}}',state['base'])
    await page.evaluate('barAddWirePortBtn.click()');await page.wait_for_timeout(50)
    after=await page.evaluate('(wid)=>{const w=wires.find(x=>x.id===wid);return {nodes:nodes.length,parts:w.attachments.length,hosted:nodes.filter(n=>n.canvasId===`canvas:wire:${wid}`&&componentForm(n).dimension===0).length,selected}}',state['base'])
    assert after['nodes']==before['nodes']+1,(before,after)
    assert after['parts']==before['parts'],(before,after)
    assert after['hosted']>=2,after
    assert str(after['selected']).startswith('point:component:'),after
    # A 2D component hosted on the same 1D carrier exposes start/end only, using standard component hit targets.
    inline=await page.evaluate('(wid)=>{const n=SovSchematicData.makeComponent(diagram,{symbolId:"gate",x:500,y:300,canvasId:`canvas:wire:${wid}`,placement:{kind:"wire",wireId:wid,t:.35}});nodes.push(n);syncNodeBoundaryContext(n);render();return n.id}',state['base'])
    pts=await page.evaluate('(id)=>componentAttachmentPointIds(nodes.find(n=>n.id===id))',inline)
    assert pts==['start','end'],pts
    assert await page.locator(f'.node[data-id="{inline}"] .port-hit').count()==2
    assert not errors,errors
    await browser.close()
    print('PASS Beta.24 1D/2D attachment interaction parity QA')

asyncio.run(main())
