from pathlib import Path
import json, os
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
DOC=json.loads((ROOT/'examples/02-duplex-buffer.sov').read_text(encoding='utf-8'))
results={}; errors=[]

with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page(viewport={'width':1280,'height':820})
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.set_content(HTML,wait_until='load')
    page.wait_for_timeout(350)
    page.evaluate('(doc)=>window.SovSchematicAPI.document.replace(doc)',DOC)
    page.evaluate('fitDiagram()')
    for mode in ('light','dark'):
        page.evaluate('(m)=>window.SovSchematicAPI.view.setAppearance(m)',mode)
        page.wait_for_timeout(350)
        results[mode]=page.evaluate('''()=>{
          const root=getComputedStyle(document.documentElement);
          const ws=getComputedStyle(document.getElementById('workspace'));
          const btn=getComputedStyle(document.querySelector('.btn'));
          const card=getComputedStyle(document.querySelector('.symbol-card'));
          return {
            grid:root.getPropertyValue('--grid').trim(),
            canvas:root.getPropertyValue('--canvas-tone').trim(),
            canvasInk:root.getPropertyValue('--canvas-ink').trim(),
            workspaceBg:ws.backgroundColor,
            buttonColor:btn.color,
            cardColor:card.color,
            forward:document.querySelectorAll('.wire-packet[data-direction="forward"]').length,
            reverse:document.querySelectorAll('.wire-packet[data-direction="reverse"]').length,
            packetTag:document.querySelector('.wire-packet-tag')?getComputedStyle(document.querySelector('.wire-packet-tag')).fill:null
          };
        }''')
        page.screenshot(path=str(ROOT/'tests'/f'beta15-{mode}.png'),full_page=True)
    page.evaluate('window.SovSchematicAPI.view.setAppearance("dark")')
    page.evaluate('selectNode("c1",{focus:false})')
    page.click('#paletteBtn')
    page.wait_for_timeout(150)
    results['darkPalette']=page.evaluate('''()=>({
      paletteBg:getComputedStyle(document.getElementById('paletteSettings')).backgroundColor,
      slotLabel:getComputedStyle(document.getElementById('barComponentColorSlot'),'::after').color,
      slotBg:getComputedStyle(document.getElementById('barComponentColorSlot')).backgroundColor
    })''')
    page.screenshot(path=str(ROOT/'tests'/'beta15-dark-palette.png'),full_page=True)
    browser.close()

assert results['light']['grid'].lower()=='#f1f1ed', results
assert results['dark']['grid'].lower()=='#2b2e31', results
assert results['dark']['canvas'].lower()=='#17191b', results
assert results['light']['forward']==results['light']['reverse']==1, results
assert results['dark']['forward']==results['dark']['reverse']==1, results
assert results['dark']['buttonColor']!='rgb(0, 0, 0)', results
assert results['dark']['cardColor']!='rgb(0, 0, 0)', results
assert results['darkPalette']['paletteBg']!='rgb(255, 255, 255)', results
assert not errors, errors
(ROOT/'tests'/'beta15-visual-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print('PASS visual theme + duplex QA')
