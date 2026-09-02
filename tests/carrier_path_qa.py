"""Wire is a carrier Path.

Every Wire is a 1D form with the carrier role whose two ends are each bound to an
attachment point or free. The palette Path creates a carrier with two free ends;
an end handle binds when dropped on a Point and frees when dropped elsewhere; the
same binding rules hold over the API, and files round-trip free ends.
"""
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
    await page.set_content(HTML.read_text(encoding='utf-8'),wait_until='load');await page.wait_for_timeout(180)

    # An ordinary Wire is a carrier Path: 1D form, carrier role, both ends bound.
    src=await page.evaluate("window.SovSchematicAPI.create('component',{id:'src',symbolId:'act',x:200,y:200}).result")
    dst=await page.evaluate("window.SovSchematicAPI.create('component',{id:'dst',symbolId:'hold',x:700,y:200,config:{signalMode:'relay'}}).result")
    w0=await page.evaluate("window.SovSchematicAPI.create('wire',{id:'k0',a:'src',aSide:'out',b:'dst',bSide:'in'}).result")
    assert w0['form']['dimension']==1 and w0['form']['body']['kind']=='path' and w0['role']=='carrier',w0
    assert w0['aAttachment']['kind']=='attachment-ref' and w0['a']=='src',w0
    assert await page.locator('.wire-group[data-wire-id="k0"] .carrier-end-handle.bound').count()==2

    # The palette Path drops a carrier with two free ends on the surface under the pointer.
    before=await page.evaluate('({nodes:nodes.length,wires:wires.length})')
    free=await page.evaluate('()=>{const w=addNode("path",500,500,null,{select:true});return {id:w.id,a:w.a,b:w.b,aAtt:w.aAttachment,bAtt:w.bAttachment,canvasId:w.canvasId,role:w.role,dim:w.form.dimension,selected}}')
    after=await page.evaluate('({nodes:nodes.length,wires:wires.length})')
    assert after['nodes']==before['nodes'] and after['wires']==before['wires']+1,(before,after)
    assert free['a'] is None and free['b'] is None and free['aAtt']['kind']=='free' and free['bAtt']['kind']=='free',free
    assert free['aAtt']['x']<500<free['bAtt']['x'] and free['canvasId']=='canvas:global' and free['role']=='carrier' and free['dim']==1,free
    assert str(free['selected']).startswith('wire:'),free
    fid=free['id']
    assert await page.locator(f'.wire-group[data-wire-id="{fid}"]').count()==1
    assert await page.locator(f'.wire-group[data-wire-id="{fid}"] .carrier-end-handle.free').count()==2
    assert await page.locator(f'.wire-group[data-wire-id="{fid}"] .wire-packet').count()==0
    assert await page.locator(f'.wire-group[data-wire-id="{fid}"] .endpoint-channel-tag').count()==0

    # Bind one end to a Component point: it adopts that point's surface and routes to it.
    b1=await page.evaluate(f'()=>{{const w=wires.find(x=>x.id==="{fid}");bindCarrierEnd(w,"b","dst","in");render();return {{b:w.b,bSide:w.bSide,pointId:w.bAttachment.pointId,canvasId:w.canvasId,a:w.a}}}}')
    assert b1=={'b':'dst','bSide':'in','pointId':'left','canvasId':'canvas:global','a':None},b1
    assert await page.locator(f'.wire-group[data-wire-id="{fid}"] .carrier-end-handle.free').count()==1
    # Bind the other end to a source: now it is indistinguishable from a drawn Wire and carries packets.
    b2=await page.evaluate(f'()=>{{const w=wires.find(x=>x.id==="{fid}");bindCarrierEnd(w,"a","src","out");render();return {{a:w.a,aSide:w.aSide,canvasId:w.canvasId,valid:SovSchematicData.validateDocument(SovSchematicAPI.document.get()).ok}}}}')
    assert b2['a']=='src' and b2['aSide']=='out' and b2['valid'],b2
    await page.wait_for_timeout(60)
    assert await page.locator(f'.wire-group[data-wire-id="{fid}"] .wire-packet').count()>=1
    # Free an end again: packets stop, the end shows an open handle where it was dropped.
    f1=await page.evaluate(f'()=>{{const w=wires.find(x=>x.id==="{fid}");freeCarrierEnd(w,"a",{{x:420,y:420}});render();return {{a:w.a,aSide:w.aSide,att:w.aAttachment}}}}')
    assert f1['a'] is None and f1['aSide'] is None and f1['att']=={'kind':'free','x':420,'y':420},f1
    assert await page.locator(f'.wire-group[data-wire-id="{fid}"] .wire-packet').count()==0
    assert await page.locator(f'.wire-group[data-wire-id="{fid}"] .carrier-end-handle.free').count()==1

    # Legality: with one end bound inside an open Plane, the other end may only bind to points on that surface.
    plane=await page.evaluate("window.SovSchematicAPI.create('component',{id:'pl',symbolId:'plane',x:900,y:600}).result")
    child=await page.evaluate("window.SovSchematicAPI.create('component',{id:'child',symbolId:'gate',x:900,y:600,canvasId:'canvas:component:pl'}).result")
    inner=await page.evaluate("window.SovSchematicAPI.create('wire',{id:'ki',aAttachment:{kind:'free',x:820,y:560},b:'child',bSide:'in'}).result")
    assert inner['canvasId']=='canvas:component:pl' and inner['a'] is None,inner
    outside_pt=await page.evaluate("()=>{const n=nodes.find(x=>x.id==='src');return portPos(n,'out')}")
    snap=await page.evaluate('(q)=>findCarrierSnapTarget(wires.find(x=>x.id==="ki"),"a",q)',outside_pt)
    assert snap is None,snap
    refused=await page.evaluate('()=>{try{bindCarrierEnd(wires.find(x=>x.id==="ki"),"a","src","out");return "bound"}catch(e){return e.message}}')
    assert 'Boundary' in refused,refused
    still=await page.evaluate('()=>{const w=wires.find(x=>x.id==="ki");return {a:w.a,kind:w.aAttachment.kind,canvasId:w.canvasId}}')
    assert still=={'a':None,'kind':'free','canvasId':'canvas:component:pl'},still
    # API parity: freeing and rebinding through update, with the same refusal.
    upd=await page.evaluate('window.SovSchematicAPI.update("wire","k0",{aAttachment:{kind:"free",x:150,y:260}})')
    assert upd['ok'] and upd['result']['a'] is None and upd['result']['aAttachment']['kind']=='free',upd
    upd2=await page.evaluate('window.SovSchematicAPI.update("wire","k0",{a:"src",aSide:"out"})')
    assert upd2['ok'] and upd2['result']['a']=='src' and upd2['result']['aAttachment']['pointId']=='right',upd2
    bad=await page.evaluate('window.SovSchematicAPI.update("wire","ki",{a:"src",aSide:"out"})')
    assert bad['ok'] is False and 'Boundary' in bad['error']['message'],bad
    nothing=await page.evaluate('window.SovSchematicAPI.create("wire",{})')
    assert nothing['ok'] is False,nothing

    # Files keep free ends and round-trip losslessly.
    rt=await page.evaluate('()=>{const before=semanticFingerprint();const doc=SovSchematicAPI.document.get();const k=doc.wires.find(w=>w.id==="ki");SovSchematicAPI.document.replace(JSON.parse(JSON.stringify(doc)));return {before,after:semanticFingerprint(),a:k.a,aSide:k.aSide,att:k.aAttachment,form:k.form,role:k.role,count:wires.length}}')
    assert rt['before']==rt['after'] and rt['a'] is None and rt['aSide'] is None and rt['att']['kind']=='free',rt
    assert rt['form']['dimension']==1 and rt['role']=='carrier' and rt['count']==3,rt

    # Pointer gesture: drag a free end handle onto a point binds it; drag a bound handle off frees it.
    box=await page.locator(f'.wire-group[data-wire-id="{fid}"] .carrier-end-handle.free').bounding_box()
    target=await page.evaluate("()=>{const n=nodes.find(x=>x.id==='src');const q=portPos(n,'out');return svgToWorkspacePixel(q.x,q.y)}")
    wrap=await page.locator('.workspace-wrap').bounding_box()
    await page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2);await page.mouse.down()
    await page.mouse.move(wrap['x']+target['x'],wrap['y']+target['y'],steps=10);await page.wait_for_timeout(40)
    assert await page.evaluate('!!carrierEndDrag&&!!carrierEndDrag.snap'),'free end should snap to the source point'
    await page.mouse.up();await page.wait_for_timeout(120)
    bound=await page.evaluate(f'()=>{{const w=wires.find(x=>x.id==="{fid}");return {{a:w.a,aSide:w.aSide}}}}')
    assert bound=={'a':'src','aSide':'out'},bound
    await page.evaluate(f'()=>{{const i=wires.findIndex(x=>x.id==="{fid}");selectWire(i);render()}}')
    hb=await page.locator(f'.wire-group[data-wire-id="{fid}"] .carrier-end-handle.bound[data-end="a"]').bounding_box()
    await page.mouse.move(hb['x']+hb['width']/2,hb['y']+hb['height']/2);await page.mouse.down()
    await page.mouse.move(hb['x']+hb['width']/2+40,hb['y']+hb['height']/2+220,steps=10);await page.wait_for_timeout(40)
    await page.mouse.up();await page.wait_for_timeout(120)
    freed=await page.evaluate(f'()=>{{const w=wires.find(x=>x.id==="{fid}");return {{a:w.a,kind:w.aAttachment.kind,b:w.b}}}}')
    assert freed['a'] is None and freed['kind']=='free' and freed['b']=='dst',freed
    # A plain click on a bound handle only selects the Wire.
    await page.evaluate(f'()=>{{const i=wires.findIndex(x=>x.id==="k0");selectWire(i);render()}}')
    hb0=await page.locator('.wire-group[data-wire-id="k0"] .carrier-end-handle.bound[data-end="b"]').bounding_box()
    await page.mouse.click(hb0['x']+hb0['width']/2,hb0['y']+hb0['height']/2);await page.wait_for_timeout(60)
    assert await page.evaluate('()=>{const w=wires.find(x=>x.id==="k0");return w.b==="dst"&&String(selected).startsWith("wire:")}')

    assert not errors,errors
    await browser.close();print('PASS carrier Path (Wire → Path) QA')

asyncio.run(main())
