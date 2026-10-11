"""Opening native virtual detail is projection only; closed instances keep running."""
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT=Path(__file__).resolve().parents[1]
components=[{'id':'$node','symbolId':'plane','x':0,'y':0,'config':{'presentation':{'size':{'w':1200,'h':800}}}}]
for row in range(3):
    for col in range(3):
        ident=f'$node-t{row}{col}'
        components.append({'id':ident,'symbolId':'plane','x':(col-1)*350,'y':(row-1)*240,'parentId':'$node','canvasId':'canvas:component:$node','config':{'presentation':{'size':{'w':320,'h':220}}}})
        components.append({'id':ident+'-value','symbolId':'lever','x':(col-1)*350,'y':(row-1)*240,'parentId':ident,'canvasId':'canvas:component:'+ident,'config':{'signal':{'value':0}}})
doc={'id':'virtual-editor-test','virtual':{'definitions':{'kernel':{'components':components,'wires':[]}},'instances':[{'id':'a','definitionId':'kernel','x':0,'y':0},{'id':'b','definitionId':'kernel','x':1800,'y':0}]}}
with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page=browser.new_page(viewport={'width':1440,'height':900})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content((ROOT/'index.html').read_text(encoding='utf-8'),wait_until='load')
    page.evaluate('(d)=>SovSchematicAPI.document.replace(d)',doc)
    assert page.locator('.node').count()==2
    page.evaluate('()=>{SovSchematicAPI.clock.advance(100);simClock.run.set("a-t11-value",1);SovSchematicAPI.clock.advance(100);window.keptRun=simClock.run;window.keptFingerprint=semanticFingerprint()}')
    page.get_by_role('button',name='Open a 3×3',exact=True).click()
    assert page.evaluate('SovSchematicAPI.virtual.list().open')=='a'
    assert page.locator('.node[data-parent-id="a"]').count()==9
    assert page.locator('.node[data-parent-id="b"]').count()==0
    assert page.evaluate('simClock.run===window.keptRun && semanticFingerprint()===window.keptFingerprint')
    assert page.evaluate('SovSchematicAPI.clock.instance("a").time')==200
    page.get_by_role('button',name='Overview',exact=True).click()
    assert page.locator('.node').count()==2
    page.evaluate('SovSchematicAPI.clock.advance(100)')
    assert page.evaluate('SovSchematicAPI.clock.state().levels["a-t11-value"].value')==1
    assert page.evaluate('SovSchematicAPI.clock.state().levels["b-t11-value"].value')==0
    saved=page.evaluate('()=>{SovSchematicAPI.virtual.open("b");return SovSchematicAPI.file.package()}')
    assert len(saved['document']['components'])==0
    page.evaluate('(p)=>SovSchematicAPI.file.open(p)',saved)
    assert page.evaluate('SovSchematicAPI.virtual.list().open')=='b'
    assert page.locator('.node[data-parent-id="b"]').count()==9
    assert not errors,errors
    browser.close()
print('PASS virtual editor: native open/Overview, full 3×3, same run, isolated state, compact package, saved open view')
