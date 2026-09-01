from __future__ import annotations
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from urllib import request, error

from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')

def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));return s.getsockname()[1]

def http_json(url,method='GET',payload=None):
    body=None if payload is None else json.dumps(payload).encode()
    req=request.Request(url,data=body,method=method,headers={'content-type':'application/json'})
    try:
        with request.urlopen(req,timeout=4) as res:
            return res.status,json.loads(res.read())
    except error.HTTPError as exc:
        return exc.code,json.loads(exc.read())

def rpc(base,name,args=None,call_id=1):
    status,data=http_json(base+'/mcp','POST',{'jsonrpc':'2.0','id':call_id,'method':'tools/call','params':{'name':name,'arguments':args or {}}})
    assert status==200,(status,data)
    result=data['result'];return result['structuredContent'],result.get('isError',False)

# Browser adapter must use the same core refusal.
with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page();page.set_content(HTML,wait_until='load');page.wait_for_timeout(100)
    state=page.evaluate('''()=>{
      nodes.splice(0);wires.splice(0);diagram.revision=0;
      const c1=SovSchematicAPI.create('component',{id:'a',symbolId:'buffer',x:200,y:200});
      const lock=SovSchematicAPI.update('component','a',{editor:{locked:true}});
      const before=diagram.revision;
      const deniedUpdate=SovSchematicAPI.update('component','a',{config:{label:'forbidden'}});
      const deniedDelete=SovSchematicAPI.delete('component','a');
      const c2=SovSchematicAPI.create('component',{id:'b',symbolId:'act',x:600,y:200});
      const deniedWire=SovSchematicAPI.create('wire',{id:'k1',a:'a',aSide:'out',b:'b',bSide:'in'});
      return {c1,lock,before,after:diagram.revision,deniedUpdate,deniedDelete,c2,deniedWire,count:nodes.length,wires:wires.length};
    }''')
    assert state['c1']['ok'] and state['lock']['ok'] and state['c2']['ok'],state
    for key in ('deniedUpdate','deniedDelete','deniedWire'):
        assert not state[key]['ok'] and 'Locked' in state[key]['error']['message'],(key,state)
    # Only successful c2 creation after `before` advances revision.
    assert state['after']==state['before']+1,state
    assert state['count']==2 and state['wires']==0,state
    browser.close()

# HTTP and MCP share the same document, legality and undo stack.
with tempfile.TemporaryDirectory() as td:
    port=free_port();file=Path(td)/'agent-golden.sov';base=f'http://127.0.0.1:{port}'
    proc=subprocess.Popen(['node',str(ROOT/'mcp/server.mjs'),'--port',str(port),'--file',str(file)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    try:
        for _ in range(50):
            try:
                status,_=http_json(base+'/api/v1/formats')
                if status==200:break
            except Exception:time.sleep(.05)
        else: raise AssertionError('server did not start')
        status,a=http_json(base+'/api/v1/components','POST',{'id':'a','symbolId':'buffer','x':200,'y':200});assert status==201 and a['ok'],a
        status,locked=http_json(base+'/api/v1/components/a','PATCH',{'editor':{'locked':True}});assert status==200 and locked['ok'],locked
        locked_revision=locked['revisionAfter']
        status,denied=http_json(base+'/api/v1/components/a','PATCH',{'config':{'label':'forbidden'}});assert status==400 and not denied['ok'] and denied['revisionAfter']==locked_revision,denied
        status,deleted=http_json(base+'/api/v1/components/a','DELETE');assert status==400 and not deleted['ok'] and deleted['revisionAfter']==locked_revision,deleted
        status,b=http_json(base+'/api/v1/components','POST',{'id':'b','symbolId':'act','x':600,'y':200});assert status==201 and b['ok'],b
        status,wire=http_json(base+'/api/v1/wires','POST',{'id':'k1','a':'a','aSide':'out','b':'b','bSide':'in'});assert status==400 and not wire['ok'] and 'Locked' in wire['error']['message'],wire
        # Refusals do not enter history; last successful mutation is HTTP creation of b.
        undo,is_error=rpc(base,'schematic.history.undo');assert not is_error,(undo,is_error)
        assert all(c['id']!='b' for c in undo['components']),undo
        # MCP recreate b, then gets the same lock refusals as HTTP/Browser.
        created,is_error=rpc(base,'schematic.create',{'resource':'component','value':{'id':'b','symbolId':'act','x':600,'y':200}},2);assert not is_error and created['ok'],created
        mcp_denied,is_error=rpc(base,'schematic.update',{'resource':'component','id':'a','patch':{'config':{'label':'nope'}}},3);assert is_error and not mcp_denied['ok'] and 'Locked' in mcp_denied['error']['message'],mcp_denied
        rev=mcp_denied['revisionAfter']
        mcp_wire,is_error=rpc(base,'schematic.create',{'resource':'wire','value':{'id':'k2','a':'a','aSide':'out','b':'b','bSide':'in'}},4);assert is_error and not mcp_wire['ok'] and mcp_wire['revisionAfter']==rev,mcp_wire
    finally:
        proc.terminate()
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:proc.kill()
print('PASS Browser/API/MCP agent golden parity QA')
