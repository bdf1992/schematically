from pathlib import Path
import json, os
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
DOC=json.loads((ROOT/'examples/06-read-write-evidence.sov').read_text(encoding='utf-8'))
errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page(viewport={'width':1280,'height':820})
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.set_content(HTML,wait_until='load'); page.wait_for_timeout(250)
    page.evaluate('(doc)=>window.SovSchematicAPI.document.replace(doc)',DOC); page.evaluate('fitDiagram()'); page.wait_for_timeout(300)
    state=page.evaluate('''()=>({
      ops:[...document.querySelectorAll('.wire-packet-operation')].map(x=>x.textContent).sort(),
      recordAccess:componentConfig(nodes.find(n=>n.id==='c2')).ports.in.connections[0].access,
      observerAccess:componentConfig(nodes.find(n=>n.id==='c3')).ports.out.connections[0].access,
      writeOp:connectionConfig(wires.find(w=>w.id==='k1')).forwardOperation,
      readOp:connectionConfig(wires.find(w=>w.id==='k2')).forwardOperation
    })''')
    assert state['ops']==['R','W'],state
    assert state['recordAccess']=='write' and state['observerAccess']=='read',state
    assert state['writeOp']=='write' and state['readOp']=='read',state
    page.evaluate("componentConfig(nodes.find(n=>n.id==='c2')).ports.in.connections[0].access='read';render()")
    page.wait_for_timeout(120)
    blocked=page.evaluate("()=>[...document.querySelectorAll('.wire-packet-operation')].map(x=>x.textContent)")
    assert 'W' not in blocked and 'R' in blocked,blocked
    page.evaluate('''()=>{
      const a=nodes.find(n=>n.id==='c1'),b=nodes.find(n=>n.id==='c2');
      componentConfig(a).ports.out.connections[0].flow='duplex';componentConfig(a).ports.out.connections[0].access='read-write';
      componentConfig(b).ports.in.connections[0].flow='duplex';componentConfig(b).ports.in.connections[0].access='read-write';
      const w=wires.find(w=>w.id==='k1');w.config.direction='duplex';w.config.forwardOperation='write';w.config.reverseOperation='read';
      componentConfig(b).signalMode='source';render();
    }''')
    page.wait_for_timeout(180)
    duplex=page.evaluate("()=>[...document.querySelectorAll('.wire-packet-operation')].map(x=>x.textContent).sort()")
    assert duplex.count('R')>=1 and duplex.count('W')>=1,duplex
    page.screenshot(path=str(ROOT/'tests'/'beta17-read-write.png'),full_page=True)
    assert not errors,errors
    browser.close()
print('PASS read/write access QA')
