from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text()
with sync_playwright() as p:
    b=p.chromium.launch(**chromium_launch_kwargs())
    page=b.new_page(viewport={'width':900,'height':600})
    page.set_content(HTML,wait_until='load'); page.wait_for_timeout(200)
    for mode in ('light','dark'):
        page.evaluate('(m)=>window.SovSchematicAPI.view.setAppearance(m)',mode)
        page.evaluate("()=>{gridVisibleInput.checked=false;gridVisibleInput.dispatchEvent(new Event('change',{bubbles:true}))}")
        page.wait_for_timeout(60)
        page.screenshot(path=str(ROOT/'tests'/f'beta21-{mode}-grid-off.png'),full_page=True)
    b.close()
