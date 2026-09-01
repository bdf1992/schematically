from pathlib import Path
import os
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
errors=[]

with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page(viewport={'width':1000,'height':700})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(HTML,wait_until='load')
    page.wait_for_timeout(250)

    def state():
        return page.evaluate("""()=>({
          visible:canvasGridVisible,
          checked:gridVisibleInput.checked,
          hiddenClass:workspace.classList.contains('grid-hidden'),
          bg:getComputedStyle(workspace).backgroundImage,
          appearance:document.documentElement.dataset.appearance
        })""")

    for mode in ('light','dark'):
        page.evaluate('(m)=>window.SovSchematicAPI.view.setAppearance(m)',mode)
        page.wait_for_timeout(80)
        on=state()
        assert on['visible'] and on['checked'] and not on['hiddenClass'],on
        assert on['bg']!='none',on

        page.evaluate("""()=>{gridVisibleInput.checked=false;gridVisibleInput.dispatchEvent(new Event('change',{bubbles:true}))}""")
        page.wait_for_timeout(50)
        off=state()
        assert not off['visible'] and not off['checked'] and off['hiddenClass'],off
        assert off['bg']=='none',off

        other='dark' if mode=='light' else 'light'
        page.evaluate('(m)=>window.SovSchematicAPI.view.setAppearance(m)',other)
        page.wait_for_timeout(50)
        switched=state()
        assert not switched['visible'] and switched['hiddenClass'] and switched['bg']=='none',switched

        page.evaluate("""()=>{gridVisibleInput.checked=true;gridVisibleInput.dispatchEvent(new Event('change',{bubbles:true}))}""")
        page.wait_for_timeout(50)
        restored=state()
        assert restored['visible'] and restored['checked'] and not restored['hiddenClass'],restored
        assert restored['bg']!='none',restored

    page.evaluate("""()=>{gridVisibleInput.checked=false;gridVisibleInput.dispatchEvent(new Event('change',{bubbles:true}))}""")
    snapshot=page.evaluate('captureWorkspace()')
    page.evaluate("""()=>{gridVisibleInput.checked=true;gridVisibleInput.dispatchEvent(new Event('change',{bubbles:true}))}""")
    page.evaluate('(w)=>applyWorkspace(w)',snapshot)
    page.wait_for_timeout(80)
    loaded=state()
    assert not loaded['visible'] and loaded['hiddenClass'] and loaded['bg']=='none',loaded
    assert not errors,errors
    browser.close()

print('PASS grid visibility QA')
