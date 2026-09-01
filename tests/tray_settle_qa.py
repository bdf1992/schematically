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
        errors=[]
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.set_content(HTML.read_text(), wait_until='load')
        await page.wait_for_timeout(250)
        state=await page.evaluate("""()=>{
          nodes.splice(0);wires.splice(0);
          const a=SovSchematicData.makeComponent(diagram,{symbolId:'act',x:220,y:360});
          const b=SovSchematicData.makeComponent(diagram,{symbolId:'buffer',x:880,y:360});
          nodes.push(a,b);
          const w=SovSchematicData.makeWire(diagram,{a:a.id,aSide:'out',b:b.id,bSide:'in'});wires.push(w);render();
          const path=renderedWirePath(w),L=path.getTotalLength(),q=path.getPointAtLength(L*.5);
          const g=SovSchematicData.makeComponent(diagram,{symbolId:'gate',x:q.x,y:q.y});nodes.push(g);activeNodeDrag=g.id;render();
          const c=componentHostCandidateAtPoint(g,g.x,g.y);activeNodeDrag=null;
          const s={node:g,originCanvasId:'canvas:global',hostCandidate:null,hostCandidateKey:'',hostReady:false,hostDwellTimer:null};
          window.__trayState=s;activeNodeDragState=s;armHostCandidate(s,c);
          return {ready:s.hostReady,ghost:!!document.querySelector('.settle-host-ghost'),candidate:c?.kind};
        }""")
        assert state['candidate']=='wire',state
        assert not state['ready'] and not state['ghost'],state
        await page.wait_for_timeout(340)
        state2=await page.evaluate("""()=>({ready:window.__trayState.hostReady,ghost:!!document.querySelector('.settle-host-ghost')})""")
        assert state2['ready'] and state2['ghost'],state2
        await page.evaluate("""()=>{clearHostCandidateArm(window.__trayState);activeNodeDragState=null;delete window.__trayState}""")
        assert not errors,errors
        await browser.close()
        print('PASS tray settle QA')

asyncio.run(main())
