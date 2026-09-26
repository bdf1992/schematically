from __future__ import annotations
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from urllib import request, error

ROOT=Path(__file__).resolve().parents[1]

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

STALE_MSG=lambda expected,current: f'Stale revision: expected {expected}, document is at {current}'

# In-process core: mirrors mcp/server.mjs's own loading (await import by file:// URL), against a fresh document.
node_script=r"""
import {pathToFileURL} from 'node:url';
await import(pathToFileURL(process.env.ATTACHMENT_CORE).href);
await import(pathToFileURL(process.env.DATA_CORE).href);
const Data=globalThis.SovSchematicData;
let doc=Data.makeDocument({id:'schematic-1'});
const results={};

// 1. matching ifRevision applies, revision advances.
let r=Data.applyOperation(doc,{op:'create',resource:'component',value:{id:'a',symbolId:'buffer',x:100,y:100},ifRevision:doc.revision});
results.matchOk=r.ok;results.matchRevisionAfter=r.revisionAfter;results.matchRevisionBefore=r.revisionBefore;

// 2. stale ifRevision is refused, document unchanged.
const beforeStale=JSON.parse(JSON.stringify(doc));
r=Data.applyOperation(doc,{op:'update',resource:'component',resourceId:'a',patch:{config:{label:'nope'}},ifRevision:0});
results.staleOk=r.ok;results.staleMessage=r.error&&r.error.message;
results.staleUnchanged=JSON.stringify(doc)===JSON.stringify(beforeStale);
results.staleRevisionAfter=r.revisionAfter;

// 3. no ifRevision applies as before.
r=Data.applyOperation(doc,{op:'update',resource:'component',resourceId:'a',patch:{config:{label:'ok'}}});
results.noneOk=r.ok;results.noneRevisionAfter=r.revisionAfter;

console.log(JSON.stringify(results));
"""

def run_node_in_process():
    env=dict(**__import__('os').environ,ATTACHMENT_CORE=str(ROOT/'src/06-attachment-core.js'),DATA_CORE=str(ROOT/'src/05-data-core.js'))
    proc=subprocess.run(['node','--input-type=module','-e',node_script],cwd=ROOT,capture_output=True,text=True,env=env)
    assert proc.returncode==0,proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])

results=run_node_in_process()
assert results['matchOk'] is True,results
assert results['matchRevisionAfter']==results['matchRevisionBefore']+1,results
assert results['staleOk'] is False,results
assert results['staleMessage']==STALE_MSG(0,results['matchRevisionAfter']),results
assert results['staleUnchanged'] is True,results
assert results['staleRevisionAfter']==results['matchRevisionAfter'],results
assert results['noneOk'] is True,results
assert results['noneRevisionAfter']==results['matchRevisionAfter']+1,results
print('PASS in-process revision guard (create/update/delete core)')

# Same three cases driven through mcp/server.mjs over HTTP (JSON-RPC tools/call).
with tempfile.TemporaryDirectory() as td:
    port=free_port();file=Path(td)/'revision-guard.sov';base=f'http://127.0.0.1:{port}'
    proc=subprocess.Popen(['node',str(ROOT/'mcp/server.mjs'),'--port',str(port),'--file',str(file)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    try:
        for _ in range(50):
            try:
                status,_=http_json(base+'/api/v1/formats')
                if status==200:break
            except Exception:time.sleep(.05)
        else: raise AssertionError('server did not start')

        doc,_=rpc(base,'schematic.document.get')
        rev0=doc['revision']

        # matching ifRevision applies.
        created,is_error=rpc(base,'schematic.create',{'resource':'component','value':{'id':'a','symbolId':'buffer','x':100,'y':100},'ifRevision':rev0},1)
        assert not is_error and created['ok'],created
        rev1=created['revisionAfter'];assert rev1==rev0+1,created

        # stale ifRevision is refused; document unchanged.
        before_doc,_=rpc(base,'schematic.document.get',call_id=2)
        stale,is_error=rpc(base,'schematic.update',{'resource':'component','id':'a','patch':{'config':{'label':'nope'}},'ifRevision':rev0},3)
        assert is_error and not stale['ok'],stale
        assert stale['error']['message']==STALE_MSG(rev0,rev1),stale
        assert stale['revisionAfter']==rev1,stale
        after_doc,_=rpc(base,'schematic.document.get',call_id=4)
        assert after_doc==before_doc,(before_doc,after_doc)

        # no ifRevision applies as before.
        updated,is_error=rpc(base,'schematic.update',{'resource':'component','id':'a','patch':{'config':{'label':'ok'}}},5)
        assert not is_error and updated['ok'],updated
        rev2=updated['revisionAfter'];assert rev2==rev1+1,updated

        # matching ifRevision on delete applies.
        deleted,is_error=rpc(base,'schematic.delete',{'resource':'component','id':'a','ifRevision':rev2},6)
        assert not is_error and deleted['ok'],deleted
    finally:
        proc.terminate()
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:proc.kill()
print('PASS HTTP revision guard (mcp/server.mjs tools/call)')
