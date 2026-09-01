from pathlib import Path
from playwright.sync_api import sync_playwright
import os
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page()
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.set_content(HTML,wait_until='load');page.wait_for_timeout(150)
    result=page.evaluate('''()=>{
      nodes.splice(0);wires.splice(0);
      const parent=SovSchematicData.makeComponent(diagram,{id:'parent',symbolId:'buffer',x:500,y:320,form:{dimension:2,regions:{interior:{state:'open'}}}});
      const child=SovSchematicData.makeComponent(diagram,{id:'child',symbolId:'act',x:500,y:320,canvasId:'canvas:component:parent'});
      nodes.push(parent,child);componentConfig(parent);componentConfig(child);
      // Parent OUT port is outside-facing: child inside may not implicitly reach it.
      let outsideRefused=false;
      try{SovSchematicData.makeWire(diagram,{a:'child',aSide:'out',b:'parent',bSide:'out'})}catch(e){outsideRefused=/Boundary blocks/.test(String(e.message||e))}
      // Parent IN port exposed internally creates an explicit crossing surface.
      componentConfig(parent).ports.in.face='internal';
      let insideAllowed=false;
      try{const w=SovSchematicData.makeWire(diagram,{a:'child',aSide:'out',b:'parent',bSide:'in'});insideAllowed=w.canvasId==='canvas:component:parent'}catch(e){}
      return {outsideRefused,insideAllowed};
    }''')
    assert result=={'outsideRefused':True,'insideAllowed':True},result
    assert not errors,errors
    browser.close()
print('PASS boundary legality QA')
