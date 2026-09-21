"""Readings use native canvas/file lifecycle and one Browser/HTTP/MCP core."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from urllib import request, error
from playwright.sync_api import sync_playwright, Error as BrowserError
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
INPUT=json.loads((ROOT/'tests/fixtures/work-graph/mission.json').read_text())
PACK=json.loads((ROOT/'examples/workstation-review.sovpak').read_text())
checks=[]

def passed(name):
    checks.append(name)
    print('PASS '+name,flush=True)


def http(base,path,body=None):
    req=request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'content-type':'application/json'})
    try:
        with request.urlopen(req,timeout=10) as response:
            return response.status,json.loads(response.read())
    except error.HTTPError as exc:
        return exc.code,json.loads(exc.read())


with sync_playwright() as playwright:
    browser=playwright.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]
    page.on('pageerror',lambda error: errors.append(str(error)))
    page.set_content(HTML,wait_until='load')
    projected=page.evaluate('input=>SovSchematicAPI.graph.projectWorkstation(input)',INPUT)
    assert projected==PACK
    page.evaluate("input=>SovSchematicAPI.graph.openWorkstation(input)",INPUT)
    assert page.locator('.graph-node-heading').count()==len(PACK['document']['components'])
    assert 'Fixture · not live work' in page.locator('#graphInspector').inner_text()
    passed('native browser projection equals the offline package')

    page.locator('#graphInspector .graph-card').first.click()
    page.locator('#graphInspector button[data-address="ws:task:build-candidate"]').click()
    assert 'ACTIVE' in page.locator('#graphInspector').inner_text()
    page.locator('#graphInspector button[data-address="ws:task:build-candidate/contract"]').click()
    assert page.locator('#graphInspector h3').inner_text()=='Work contract'
    assert page.locator('#graphInspector .graph-crumb').count()==2
    assert 'declared' in page.locator('#graphInspector').inner_text()
    # Clicking the inspector disables canvas deletion keys.
    before=page.evaluate('SovSchematicAPI.document.get().components.length')
    page.keyboard.press('Delete')
    assert page.evaluate('SovSchematicAPI.document.get().components.length')==before
    passed('native selection, nested charges, and breadcrumbs are keyboard-safe')

    details=page.locator('#graphInspector .graph-value-tree').first
    details.evaluate('(e)=>e.open=false')
    page.evaluate('render()')
    assert details.evaluate('(e)=>e.open') is False
    passed('rerender preserves expanded-value inspection state')

    page.evaluate("SovSchematicAPI.graph.focus('ws:task:build-candidate/candidate')")
    assert 'Not supplied' in page.locator('#graphInspector').inner_text()
    page.evaluate("SovSchematicAPI.graph.focus('ws:task:build-candidate')")
    assert 'Null (recorded)' in page.locator('#graphInspector').inner_text()
    assert 'Empty list' in page.locator('#graphInspector').inner_text()
    passed('absence, recorded null, and empty collections are different on screen')

    saved=page.evaluate('SovSchematicAPI.file.package()')
    assert saved['meta']['graph']==PACK['meta']['graph']
    doc=page.evaluate('SovSchematicAPI.file.document()')
    assert 'readings' not in doc['meta']['graph'] and 'source' not in doc['meta']['graph']
    page.evaluate('p=>SovSchematicAPI.file.open(p,"round-trip.sovpak")',saved)
    assert page.evaluate('SovSchematicAPI.graph.inspect().subjects')==11
    page.evaluate('SovSchematicAPI.graph.setView(true)')
    passed('package round trip preserves readings; document export does not impersonate a snapshot')

    before=page.evaluate('JSON.stringify(SovSchematicAPI.document.get())')
    bad=copy.deepcopy(saved);bad['meta']['graph']['definition']='wrong'
    code=page.evaluate('p=>{try{SovSchematicAPI.file.open(p);return null}catch(e){return e.code}}',bad)
    assert code=='GRAPH_DEFINITION_CHANGED'
    assert page.evaluate('JSON.stringify(SovSchematicAPI.document.get())')==before
    passed('a transplanted or detached package refuses atomically before replacing the open file')

    page.evaluate("SovSchematicAPI.update('component','task-build-candidate',{x:370})")
    assert page.evaluate('SovSchematicAPI.graph.inspect().subjects')==11
    page.evaluate("SovSchematicAPI.update('component','task-build-candidate',{config:{label:'Other responsibility'}})")
    assert 'graph readings detached' in page.locator('#graphInspector').inner_text().lower()
    assert page.locator('.graph-node-heading').count()==0
    code=page.evaluate('()=>{try{SovSchematicAPI.file.package();return null}catch(e){return e.code}}')
    assert code=='GRAPH_DEFINITION_CHANGED'
    page.evaluate('SovSchematicAPI.history.undo()')
    assert 'graph readings detached' not in page.locator('#graphInspector').inner_text().lower()
    assert page.evaluate('SovSchematicAPI.graph.inspect().subjects')==11
    passed('geometry stays usable; semantic edits detach readings and undo restores their binding')

    attack=copy.deepcopy(INPUT);attack['mission']['title']='<img src=x onerror="globalThis.graphPwned=1">'
    attack['tasks'][0]['contract']['steps']=['<script>globalThis.graphPwned=1</script>']
    attack['source']['baseUrl']='javascript:alert(1)'
    page.evaluate('input=>SovSchematicAPI.graph.openWorkstation(input)',attack)
    page.evaluate("SovSchematicAPI.graph.focus('ws:task:build-candidate/contract')")
    assert page.evaluate('globalThis.graphPwned===undefined')
    assert page.locator('#graphInspector img,#graphInspector script,#graphInspector a').count()==0
    assert '<script>' in page.locator('#graphInspector').inner_text()
    passed('untrusted labels and structured content remain text, not markup or script links')

    page.evaluate('input=>SovSchematicAPI.graph.openWorkstation(input)',INPUT)
    page.evaluate("SovSchematicAPI.graph.focus('ws:task:check-evidence')")
    second=browser.new_page(viewport={'width':1280,'height':800})
    second.set_content(HTML,wait_until='load')
    second.evaluate('input=>SovSchematicAPI.graph.openWorkstation(input)',INPUT)
    second.evaluate("SovSchematicAPI.graph.focus('ws:task:review-outcome')")
    assert page.locator('#graphInspector h3').inner_text()!=second.locator('#graphInspector h3').inner_text()
    second.close()
    passed('independent embedded instances share no selection')

    page.set_viewport_size({'width':780,'height':820})
    panel=page.locator('.inspector').bounding_box()
    assert panel and panel['x']>=0 and panel['x']+panel['width']<=781,panel
    assert page.locator('#graphInspector').is_visible()
    passed('graph inspector remains reachable at constrained workstation widths')
    page.set_viewport_size({'width':1440,'height':1000})
    page.evaluate('fitDiagram()')
    if os.environ.get('GRAPH_QA_OUTPUT'):
        out=Path(os.environ['GRAPH_QA_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(out/'work-graph-native.png'))
    assert not errors,errors

    # File recovery is exercised with storage on a real origin, as set_content
    # without a URL intentionally has no storage authority.
    with tempfile.TemporaryDirectory() as temp:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        file=Path(temp)/'server.sov'
        proc=subprocess.Popen(['node',str(ROOT/'mcp/server.mjs'),'--port',str(port),'--file',str(file)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        base=f'http://127.0.0.1:{port}'
        try:
            for _ in range(80):
                try:
                    if http(base,'/api/v1/formats')[0]==200:break
                except Exception:time.sleep(.05)
            else:raise AssertionError('server failed to start')
            _,before_doc=http(base,'/mcp',{'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'schematic.document.get'}})
            cases=[('project-workstation',{'input':INPUT}),('inspect',{'package':PACK,'address':'ws:task:check-evidence'}),('compare',{'before':PACK,'after':PACK}),('inspect',{'package':bad})]
            for suffix,args in cases:
                name='schematic.graph.'+suffix
                expected=page.evaluate('p=>SovSchematicAPI.graph.execute(p.name,p.args)',{'name':name,'args':args})
                status,actual=http(base,'/api/v1/graph/'+suffix,args)
                assert actual==expected,(suffix,actual)
                assert status==(200 if expected['ok'] else 400)
                _,rpc=http(base,'/mcp',{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':name,'arguments':args}})
                assert rpc['result']['structuredContent']==expected['value'],rpc
                assert rpc['result']['isError']==(not expected['ok'])
            _,after_doc=http(base,'/mcp',{'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'schematic.document.get'}})
            assert before_doc==after_doc
            assert not file.exists()
            passed('Browser, HTTP and MCP return identical projections, inspection, comparison and refusals without server writes')
            # Serve a genuine origin using Playwright routing, no extra process.
            page.route(base+'/',lambda route:route.fulfill(status=200,content_type='text/html',body=HTML))
            origin_available=True
            try:page.goto(base+'/')
            except BrowserError as exc:
                if os.environ.get('GRAPH_QA_ALLOW_ORIGIN_BLOCK')=='1' and 'ERR_BLOCKED_BY_ADMINISTRATOR' in str(exc):
                    origin_available=False
                    print('UNAVAILABLE real-origin recovery: browser administrator policy; required on CI',flush=True)
                else:raise
            if origin_available:
                page.evaluate('input=>SovSchematicAPI.graph.openWorkstation(input)',INPUT)
                page.evaluate('SovSchematicAPI.document.saveRecovery()')
                page.reload()
                # Recovery deliberately asks before replacing the unsaved startup file.
                # Playwright dismisses unhandled dialogs: exercise both real choices.
                page.once('dialog',lambda dialog:dialog.dismiss())
                assert page.evaluate('SovSchematicAPI.document.restoreRecovery()') is False
                assert page.evaluate('SovSchematicAPI.file.package().meta.graph || null') is None
                passed('cancelling recovery leaves the current file and its metadata unchanged')
                page.once('dialog',lambda dialog:dialog.accept())
                assert page.evaluate('SovSchematicAPI.document.restoreRecovery()') is True
                assert page.evaluate('SovSchematicAPI.graph.inspect().subjects')==11
                assert page.evaluate('SovSchematicAPI.file.info().format')=='package'
                passed('recovery restores a package snapshot rather than silently discarding its source readings')
        finally:
            proc.terminate()
            try:proc.wait(timeout=3)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
    browser.close()
print(f'WORK GRAPH BROWSER PASS: {len(checks)} cases')
