"""Same commands produce the same run over browser, HTTP, MCP and restart."""
from pathlib import Path
import json
import socket
import subprocess
import tempfile
import time
from urllib import request, error
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT=Path(__file__).resolve().parents[1]
DOC=json.loads((ROOT/'examples/logic-memory.sov').read_text())
COMMANDS=[{'action':'start'},{'action':'run','budget':100},
          {'action':'input','component':'enable','value':1},
          {'action':'input','component':'request','value':1},
          {'action':'step'},{'action':'run','budget':100},
          {'action':'input','component':'enable','value':0},
          {'action':'run','budget':100},
          {'action':'input','component':'request','value':0},
          {'action':'run','budget':100}]

def http(url,method='GET',payload=None):
    req=request.Request(url,data=None if payload is None else json.dumps(payload).encode(),method=method,headers={'content-type':'application/json'})
    try:
        with request.urlopen(req,timeout=5) as res:return json.load(res)
    except error.HTTPError as e:return json.load(e)

with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page(viewport={'width':1600,'height':1000})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content((ROOT/'index.html').read_text(),wait_until='load')
    page.evaluate('(doc)=>SovSchematicAPI.document.replace(doc)',DOC)
    browser_results=[]
    for cmd in COMMANDS:
        result=page.evaluate('(cmd)=>SovSchematicAPI.runtime.execute(cmd)',cmd)
        assert result['ok'],result
        browser_results.append(result['session'])
    assert browser_results[-1]['values']['result']['inputs']['in']==1
    assert page.locator('#logicStatus').text_content().startswith('QUIESCENT')
    page.locator('#logicPanel').evaluate('(e)=>e.open=true')
    with page.expect_download() as download:
        page.click('#logicSave')
    saved=json.loads(Path(download.value.path()).read_text())
    assert saved['session']==browser_results[-1]
    page.click('#logicStart')
    page.evaluate('(file)=>SovSchematicAPI.file.open(file,"saved.sovrun")',saved)
    assert page.evaluate('SovSchematicAPI.runtime.get().session')==saved['session']
    # Pending-event snapshot resumes through File Open, not just direct core restore.
    pending=page.evaluate('()=>{SovSchematicAPI.runtime.execute({action:"input",component:"request",value:1});return SovSchematicAPI.runtime.file()}')
    page.evaluate('(file)=>SovSchematicAPI.file.open(file,"pending.sovrun")',pending)
    assert page.evaluate('SovSchematicAPI.runtime.get().session.queue.length')>0
    before=page.evaluate('SovSchematicAPI.document.get()')
    bad=json.loads(json.dumps(saved));bad['session']['trace'][0]['event']['value']=1
    rejected=page.evaluate('(file)=>{try{SovSchematicAPI.file.open(file);return false}catch(e){return true}}',bad)
    assert rejected and page.evaluate('SovSchematicAPI.document.get()')==before
    assert not errors,errors
    page.screenshot(path='/tmp/schematic-logic-runner.png')
    browser.close()

with tempfile.TemporaryDirectory() as td:
    file=Path(td)/'memory.sov';file.write_text(json.dumps(DOC))
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    def start():
        proc=subprocess.Popen(['node',str(ROOT/'mcp/server.mjs'),'--file',str(file),'--port',str(port)],stdout=subprocess.DEVNULL)
        for _ in range(60):
            try:http(base+'/api/v1/formats');return proc
            except OSError:time.sleep(.05)
        proc.terminate();raise AssertionError('server did not start')
    proc=start()
    try:
        for i,cmd in enumerate(COMMANDS):
            if i%2:
                envelope=http(base+'/mcp','POST',{'jsonrpc':'2.0','id':i,'method':'tools/call','params':{'name':'schematic.runtime','arguments':cmd}})
                result=envelope['result']['structuredContent']
            else:result=http(base+'/api/v1/runtime','POST',cmd)
            assert result['ok'],result
            assert result['session']==browser_results[i],i
        proc.terminate();proc.wait(timeout=5);proc=start()
        restored=http(base+'/api/v1/runtime')
        assert restored['ok'] and restored['session']==browser_results[-1],restored
        replay=http(base+'/api/v1/runtime','POST',{'action':'replay'});assert replay['ok']
        disk=Path(str(file)+'.run.json').read_bytes()
        invalid=http(base+'/api/v1/runtime','POST',{'action':'input','component':'request','value':2})
        assert not invalid['ok'] and Path(str(file)+'.run.json').read_bytes()==disk
        proc.terminate();proc.wait(timeout=5)
        Path(str(file)+'.run.json').write_text('{broken')
        proc=start();assert not http(base+'/api/v1/runtime')['ok']
    finally:
        proc.terminate();proc.wait(timeout=5)
print('PASS runtime browser/HTTP/MCP parity, saved memory, queued continuation, restart and corrupt-state refusal')
