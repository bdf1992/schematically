"""Point / Path / Plane primitives.

The three dimensional primitives are first-class palette entries with minimal
default records. A Point dropped on a Path, a Plane boundary, a Wire, or an open
interior sticks there through the ordinary Component settle path, and the Plane
exposes no built-in points of its own: attachment is emergent from hosted Points.
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

    # Palette offers the three primitives ahead of typed Components.
    cards=await page.evaluate("[...document.querySelectorAll('.symbol-card')].map(b=>b.dataset.symbolId)")
    assert cards[:3]==['point','path','plane'],cards

    # A symbol id alone yields the dimensional preset, and the record stays minimal.
    pt=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'point',x:200,y:200}).result")
    pa=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'path',x:600,y:200}).result")
    pl=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'plane',x:600,y:560}).result")
    assert pt['form']['dimension']==0 and list(pt['config']['ports'])==['out'],pt
    assert pa['form']['dimension']==1 and list(pa['config']['ports'])==['in','out'],pa
    assert pl['form']['dimension']==2 and pl['form']['regions']['interior']['state']=='open',pl
    assert pl['config']['attachmentDefaults']=='none' and pl['config']['ports']=={},pl
    # A Plane has no built-in points; a typed Component keeps its template defaults.
    assert await page.evaluate('(id)=>componentAttachmentPointIds(nodes.find(n=>n.id===id))',pl['id'])==[]
    assert await page.locator(f'.node[data-id="{pl["id"]}"] .attachment-point').count()==0
    act=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:1100,y:200}).result")
    assert list(act['config']['ports'])==['in','out','control'],act
    # The legacy `port` symbol id normalizes to `point`.
    legacy=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'port',x:200,y:400}).result")
    assert legacy['symbolId']=='point' and legacy['form']['dimension']==0,legacy
    # Primitives draw no type caption of their own; a Path body is a single line.
    assert await page.locator(f'.node[data-id="{pa["id"]}"] text').count()==0
    assert await page.locator(f'.node[data-id="{pa["id"]}"] .dimensional-path-body').count()==1
    assert await page.locator(f'.node[data-id="{pa["id"]}"] .glyph').count()==0

    # A Wire cannot end on a Plane that exposes no point.
    refused=await page.evaluate('(ids)=>window.SovSchematicAPI.create("wire",{a:ids[0],aSide:"out",b:ids[1],bSide:"in"})',[act['id'],pl['id']])
    assert refused['ok'] is False,refused

    # Drop the Point on the Plane's left edge: it sticks as a boundary attachment (side + t).
    edge=await page.evaluate("""(ids)=>{
      const pt=nodes.find(n=>n.id===ids.pt),pl=nodes.find(n=>n.id===ids.pl),size=componentSize(pl);
      const x=pl.x-size.w/2+2,y=pl.y+size.h*.25;
      const c=componentHostCandidateAtPoint(pt,x,y);applyComponentHost(pt,c);render();
      return {kind:c?.kind,side:pt.placement.side,t:pt.placement.t,parentId:pt.parentId,canvasId:pt.canvasId,x:pt.x,left:pl.x-size.w/2};
    }""",{'pt':pt['id'],'pl':pl['id']})
    assert edge['kind']=='edge' and edge['side']=='left',edge
    assert edge['parentId']==pl['id'] and edge['canvasId']==f"canvas:component:{pl['id']}",edge
    assert abs(edge['t']-.75)<.05 and abs(edge['x']-edge['left'])<1,edge
    # Its `self` point is exposed to the Plane's outside surface, so an outside Component can wire to it.
    wire=await page.evaluate('(ids)=>window.SovSchematicAPI.create("wire",{a:ids[0],aSide:"out",b:ids[1],bSide:"self"})',[act['id'],pt['id']])
    assert wire['ok'] and wire['result']['canvasId']=='canvas:global',wire
    # Resize the Plane: the Point rides its edge (same t, new world x) and never inflates the host minimum.
    moved=await page.evaluate("""(ids)=>{
      const pt=nodes.find(n=>n.id===ids.pt),pl=nodes.find(n=>n.id===ids.pl);
      componentConfig(pl).presentation.size.w+=80;componentConfig(pl).presentation.size.h+=40;render();
      const size=componentSize(pl);return {t:pt.placement.t,x:pt.x,left:pl.x-size.w/2,minW:transformMinimumSize(pl).w,w:size.w};
    }""",{'pt':pt['id'],'pl':pl['id']})
    assert abs(moved['t']-edge['t'])<1e-6 and abs(moved['x']-moved['left'])<1,moved
    assert moved['minW']<=moved['w'],moved

    # Face `both` makes the same Point a boundary crossing: a child inside the Plane can reach it.
    inner=await page.evaluate('(id)=>window.SovSchematicAPI.create("component",{symbolId:"hold",x:0,y:0,canvasId:`canvas:component:${id}`}).result',pl['id'])
    denied=await page.evaluate('(ids)=>window.SovSchematicAPI.create("wire",{a:ids[0],aSide:"out",b:ids[1],bSide:"self"})',[inner['id'],pt['id']])
    assert denied['ok'] is False and 'Boundary' in denied['error']['message'],denied
    await page.evaluate('(id)=>window.SovSchematicAPI.update("component",id,{config:{ports:{out:{face:"both"}}}})',pt['id'])
    crossed=await page.evaluate('(ids)=>window.SovSchematicAPI.create("wire",{a:ids[0],aSide:"out",b:ids[1],bSide:"self"})',[inner['id'],pt['id']])
    assert crossed['ok'] and crossed['result']['canvasId']==f"canvas:component:{pl['id']}",crossed

    # A Point dropped on a Path sticks along it; dropped in an open interior it is hosted there.
    p2=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'point',x:40,y:40}).result")
    on_path=await page.evaluate("""(ids)=>{const pt=nodes.find(n=>n.id===ids.pt),pa=nodes.find(n=>n.id===ids.pa);const c=componentHostCandidateAtPoint(pt,pa.x+30,pa.y+3);applyComponentHost(pt,c);render();return {kind:c?.kind,t:pt.placement.t,hostId:pt.placement.hostId,dim:Attachment.hostDimension(pt),points:componentAttachmentPointIds(pt)}}""",{'pt':p2['id'],'pa':pa['id']})
    assert on_path['kind']=='path' and on_path['hostId']==pa['id'] and .5<on_path['t']<1,on_path
    assert on_path['dim']==1 and on_path['points']==['self'],on_path
    in_plane=await page.evaluate("""(ids)=>{const pt=nodes.find(n=>n.id===ids.pt),pl=nodes.find(n=>n.id===ids.pl);const c=componentHostCandidateAtPoint(pt,pl.x+10,pl.y+10);applyComponentHost(pt,c);render();return {kind:c?.kind,canvasId:pt.canvasId,placement:pt.placement.kind}}""",{'pt':p2['id'],'pl':pl['id']})
    assert in_plane['kind']=='component' and in_plane['canvasId']==f"canvas:component:{pl['id']}" and in_plane['placement']=='surface',in_plane

    # The 0D grip is the move target; the ring is the wiring target.
    assert await page.locator(f'.node[data-id="{p2["id"]}"] .point-grip').count()==1
    assert await page.locator(f'.node[data-id="{p2["id"]}"] .port-hit[data-point="self"]').count()==1
    box=await page.locator(f'.node[data-id="{p2["id"]}"] .point-grip').bounding_box()
    cx,cy=box['x']+box['width']/2,box['y']+box['height']/2
    await page.mouse.move(cx,cy);await page.mouse.down()
    await page.mouse.move(cx+160,cy+120,steps=8);await page.wait_for_timeout(80)
    assert await page.evaluate('!!activeNodeDragState&&!wireDrag'),'grip drag must move the Point, not start a Wire'
    await page.mouse.up();await page.wait_for_timeout(150)
    assert await page.evaluate('activeNodeDragState===null')

    # Form settings show only what the dimension has; Attachments is a 2D setting.
    await page.evaluate('(id)=>{selectNode(id);openSelectionSettings("component")}',pl['id'])
    assert await page.evaluate('formAttachments.value')=='none'
    assert await page.evaluate('formAttachments.closest("label").hidden') is False
    await page.evaluate('(id)=>{selectNode(id);openSelectionSettings("component")}',p2['id'])
    assert await page.evaluate('formAttachments.closest("label").hidden') is True
    assert await page.evaluate('visualHeight.closest("label").hidden') is True
    assert await page.evaluate('document.getElementById("formBodyKind")===null')

    # Turning built-in points off is refused while a Wire still ends on one.
    await page.evaluate('(id)=>{selectNode(id);openSelectionSettings("component");formAttachments.value="none";formAttachments.dispatchEvent(new Event("change"))}',act['id'])
    await page.wait_for_timeout(50)
    assert await page.evaluate('(id)=>Attachment.attachmentDefaults(nodes.find(n=>n.id===id))',act['id'])=='standard'
    assert 'Detach' in await page.locator('#status').inner_text()
    # Without Wires it is allowed, and the built-in points disappear.
    free=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'gate',x:1100,y:620}).result")
    await page.evaluate('(id)=>{selectNode(id);openSelectionSettings("component");formAttachments.value="none";formAttachments.dispatchEvent(new Event("change"))}',free['id'])
    await page.wait_for_timeout(50)
    assert await page.evaluate('(id)=>componentAttachmentPointIds(nodes.find(n=>n.id===id))',free['id'])==[]
    assert await page.locator(f'.node[data-id="{free["id"]}"] .attachment-point').count()==0

    assert not errors,errors
    await browser.close();print('PASS Point / Path / Plane primitive forms QA')

asyncio.run(main())
