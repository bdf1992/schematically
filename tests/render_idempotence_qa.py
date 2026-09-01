from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(HTML,wait_until='load');page.wait_for_timeout(100)
    state=page.evaluate('''()=>{
      nodes.splice(0);wires.splice(0);diagram.revision=0;
      const a=SovSchematicAPI.create('component',{id:'a',symbolId:'buffer',x:220,y:260});
      const b=SovSchematicAPI.create('component',{id:'b',symbolId:'act',x:650,y:260});
      const w=SovSchematicAPI.create('wire',{id:'k1',a:'a',aSide:'right',b:'b',bSide:'left'});
      const before=semanticFingerprint(),revision=diagram.revision;
      for(let i=0;i<6;i++)render();
      const after=semanticFingerprint();
      return {ok:a.ok&&b.ok&&w.ok,before,after,revision,afterRevision:diagram.revision,receiptRevision:w.revisionAfter};
    }''')
    assert state['ok'],state
    assert state['before']==state['after'],state
    assert state['revision']==state['afterRevision']==state['receiptRevision'],state
    assert not errors,errors
    browser.close()
print('PASS render semantic idempotence QA')
