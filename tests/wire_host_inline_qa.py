import asyncio, math
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'index.html'
async def main():
  async with async_playwright() as p:
    browser=await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page=await browser.new_page(viewport={'width':1200,'height':800});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    await page.set_content(HTML.read_text(),wait_until='load');await page.wait_for_timeout(250)
    result=await page.evaluate("""()=>{
      nodes.splice(0);wires.splice(0);wireHostPoseCache.clear();
      const a=SovSchematicData.makeComponent(diagram,{symbolId:'act',x:240,y:180});
      const b=SovSchematicData.makeComponent(diagram,{symbolId:'buffer',x:240,y:620});nodes.push(a,b);
      const w=SovSchematicData.makeWire(diagram,{a:a.id,aSide:'out',b:b.id,bSide:'in'});wires.push(w);render();
      const path=renderedWirePath(w),L=path.getTotalLength();let len=L*.5,angle=pathTangentAngleAtLength(path,len);
      for(let i=1;i<40;i++){const probe=L*i/40,a0=pathTangentAngleAtLength(path,probe);if(Math.abs(Math.abs(a0)-90)<2){len=probe;angle=a0;break}}
      const q=path.getPointAtLength(len);
      const g=SovSchematicData.makeComponent(diagram,{symbolId:'gate',x:q.x,y:q.y});nodes.push(g);
      const candidate={kind:'wire',entity:w,canvasId:wireCanvas(w).id,placement:{x:q.x,y:q.y,t:.5,angle,distance:0}};
      applyComponentHost(g,candidate);render();
      const pose=wireHostPoseCache.get(g.id),el=document.querySelector(`.node[data-id="${g.id}"]`),cut=el.querySelector('.inline-wire-cut');
      const box=componentInlineGraphicBox(g),half=componentInlineTerminalHalfSpan(g),use=el.querySelector('.glyph');
      return {id:g.id,angle:pose.angle,transform:el.getAttribute('transform'),cutX:+cut.getAttribute('x'),cutW:+cut.getAttribute('width'),half,box,useY:+use.getAttribute('y'),terminalY:componentInlineTerminalY(g),canvasId:g.canvasId};
    }""")
    assert result['canvasId'].startswith('canvas:wire:'),result
    assert abs(result['angle']) < 2 or abs(abs(result['angle'])-90)<2,result
    assert 'rotate(' in result['transform'],result
    assert abs(result['cutX']+result['half'])<.1 and abs(result['cutW']-result['half']*2)<.1,result
    axis_y=result['useY']+(result['terminalY']/64)*result['box']['h']
    assert abs(axis_y)<.15,(axis_y,result)
    assert not errors,errors
    await page.screenshot(path=str(ROOT/'tests/beta18-inline-wire.png'),full_page=True)
    await browser.close();print('PASS wire host inline QA')
asyncio.run(main())
