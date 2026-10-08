"""The workspace grid is drawn in world units and follows the camera.

The minor cell is canvasGridSize world units, the unit of the snap step, so it grows
with zoom and moves with pan; every fourth line is a major line; the minor level is
dropped when it would be under 8 screen px; a hidden grid draws nothing.
"""
import asyncio
import re
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'index.html'

def close(a,b,tol,what):
  print(f'  {what}: {a:.4f} vs {b:.4f} (tol {tol})')
  assert abs(a-b)<=tol,(what,a,b)

def px_list(text):
  return [float(v) for v in re.findall(r'(-?[\d.]+)px',text)]

async def main():
  async with async_playwright() as p:
    browser=await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page=await browser.new_page(viewport={'width':1400,'height':900})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
    await page.set_content(HTML.read_text(encoding='utf-8'),wait_until='load');await page.wait_for_timeout(250)

    K="()=>{const m=workspace.getScreenCTM();return Math.hypot(m.a,m.b)}"
    async def k(): return await page.evaluate(K)
    async def sizes():
      t=await page.evaluate("()=>getComputedStyle(workspace).backgroundSize")
      v=px_list(t);return v[0],v[-1]
    async def set_k(target):
      # k is linear in the zoom; read it at the base camera, then scale the camera.
      await page.evaluate("()=>{camera={...BASE_VIEW};applyCamera()}")
      k1=await k()
      await page.evaluate("(z)=>{camera={x:0,y:0,w:BASE_VIEW.w/z,h:BASE_VIEW.h/z};applyCamera()}",target/k1)
      await page.wait_for_timeout(60)
    async def bg():
      return await page.evaluate("()=>getComputedStyle(workspace).backgroundImage")
    async def set_visible(on):
      await page.evaluate("(on)=>{gridVisibleInput.checked=on;gridVisibleInput.dispatchEvent(new Event('change',{bubbles:true}))}",on)

    size=await page.evaluate("canvasGridSize")

    print('(a) start')
    k0=await k();major,minor=await sizes()
    close(minor,size*k0,.01,'minor');close(major,4*size*k0,.01,'major')

    print('(b) zoomAt(2)')
    await page.evaluate("zoomAt(2)");await page.wait_for_timeout(60)
    k2=await k();major2,minor2=await sizes()
    close(k2,2*k0,.001,'k doubled')
    close(minor2,2*minor,.01,'minor doubled');close(major2,2*major,.01,'major doubled')

    print('(c) pan by 10 world units')
    await page.evaluate("()=>{camera={...BASE_VIEW};applyCamera()}")
    kk=await k()
    x0=await page.evaluate("()=>parseFloat(workspace.style.getPropertyValue('--canvas-grid-x'))")
    await page.evaluate("()=>{camera={...camera,x:camera.x+10};applyCamera()}")
    x1=await page.evaluate("()=>parseFloat(workspace.style.getPropertyValue('--canvas-grid-x'))")
    close(x1-x0,-10*kk,.01,'grid x change')

    print('(d) a card at world 48,72 sits on a grid line')
    await page.evaluate("()=>{camera={...BASE_VIEW};applyCamera()}")
    n=await page.evaluate("()=>{const n=addNode('act',48,72,null,{select:false});return {x:n.x,y:n.y}}")
    assert (n['x'],n['y'])==(48,72),n
    for z in (1,1.31,0.5):
      await page.evaluate("(z)=>{camera={x:0,y:0,w:BASE_VIEW.w/z,h:BASE_VIEW.h/z};applyCamera()}",z)
      await page.wait_for_timeout(60)
      r=await page.evaluate("""()=>{
        const m=workspace.getScreenCTM(),b=workspace.getBoundingClientRect();
        const kk=Math.hypot(m.a,m.b),minor=parseFloat(workspace.style.getPropertyValue('--canvas-grid-size'));
        const gx=parseFloat(workspace.style.getPropertyValue('--canvas-grid-x'))+.5;
        const gy=parseFloat(workspace.style.getPropertyValue('--canvas-grid-y'))+.5;
        const cx=m.a*48+m.c*72+m.e-b.left,cy=m.b*48+m.d*72+m.f-b.top;
        return {k:kk,minor,dx:(cx-gx)/minor,dy:(cy-gy)/minor}}""")
      print(f"  zoom {z}: k={r['k']:.4f} minor={r['minor']:.4f} cell offsets {r['dx']:.4f},{r['dy']:.4f}")
      for axis in ('dx','dy'):
        off=r[axis]*r['minor']
        whole=round(r[axis])*r['minor']
        assert abs(off-whole)<=.6,(z,axis,r)

    print('(e) minor level hides under 8 px')
    await set_k(.25)
    cls=await page.evaluate("()=>workspace.classList.contains('grid-minor-hidden')")
    img=await bg();print(f'  k=0.25 class={cls} gradients={img.count("linear-gradient")}')
    assert cls and img.count('linear-gradient')==2,(cls,img)
    await set_k(1)
    cls=await page.evaluate("()=>workspace.classList.contains('grid-minor-hidden')")
    img=await bg();print(f'  k=1 class={cls} gradients={img.count("linear-gradient")}')
    assert (not cls) and img.count('linear-gradient')==4,(cls,img)

    print('(f) Show grid off draws nothing')
    await set_visible(False)
    for target in (.25,1):
      await set_k(target)
      img=await bg();print(f'  k={target} background-image={img}')
      assert img=='none',img
    await set_visible(True)

    print('(g) grid size 48 doubles the minor cell')
    await set_k(1)
    _,before=await sizes()
    await page.evaluate("()=>{gridSizeInput.value='48';gridSizeInput.dispatchEvent(new Event('change',{bubbles:true}))}")
    _,after=await sizes()
    close(after,2*before,.01,'minor doubled')

    print('(h) no errors')
    assert not errors,errors
    await browser.close()
  print('PASS grid world units QA')

asyncio.run(main())
