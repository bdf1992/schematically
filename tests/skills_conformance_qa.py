"""Skills conformance + agent-surface coverage QA.

Executes the surface the agent-facing skills document (skills/operator,
skills/author, skills/reviewer) against the real build, and covers the
agent-surface areas the golden parity suite does not: the MCP tool manifest,
boundary-reachability refusal via HTTP and MCP, reference CRUD on all three
surfaces, the MCP checkpoint lifecycle, history.redo, and document
round-trip through the server.
"""
from __future__ import annotations
import json, socket, subprocess, tempfile, time
from pathlib import Path
from urllib import request, error

from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')

# --- Browser: every operation the operator skill documents must exist and act.
DOCUMENTED = [
    'list', 'get', 'create', 'update', 'delete', 'execute', 'formats',
    'document.get', 'document.replace', 'document.saveRecovery', 'document.restoreRecovery',
    'file.info', 'file.document', 'file.package', 'file.parse', 'file.open',
    'history.list', 'history.undo', 'history.redo',
    'checkpoints.list', 'checkpoints.create', 'checkpoints.restore',
    'selection.components', 'selection.copy', 'selection.paste', 'selection.duplicate',
    'view.appearance', 'view.setAppearance', 'view.globalRate', 'view.setGlobalRate',
]

with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(200)
    result = page.evaluate('''(names)=>{
      const A=window.SovSchematicAPI;
      const missing=names.filter(path=>{let o=A;for(const k of path.split('.')){o=o?.[k];if(o===undefined)return true}return false});
      A.create('component',{id:'c1',symbolId:'buffer',x:200,y:200});
      const ref=A.create('reference',{id:'ref1',label:'datasheet'});
      const refRoundtrip=ref.ok&&A.get('reference','ref1').ok&&A.update('reference','ref1',{label:'v2'}).ok&&A.delete('reference','ref1').ok;
      A.checkpoints.create('conformance');
      const cpPersisted=JSON.stringify(A.file.document()).includes('conformance');
      return {missing,refRoundtrip,cpPersisted};
    }''', DOCUMENTED)
    assert not result['missing'], f"operator skill documents missing API: {result['missing']}"
    assert result['refRoundtrip'], 'reference CRUD round-trip failed in browser'
    assert result['cpPersisted'], 'checkpoint not persisted into .sov document'
    assert not errors, errors
    browser.close()

# --- Server: manifest parity plus the surface untouched by the golden suite.
def http_json(url, method='GET', payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = request.Request(url, data=body, method=method, headers={'content-type': 'application/json'})
    try:
        with request.urlopen(req, timeout=4) as res:
            return res.status, json.loads(res.read())
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read())

def rpc(base, name, args=None, _id=[0]):
    _id[0] += 1
    status, data = http_json(base + '/mcp', 'POST', {
        'jsonrpc': '2.0', 'id': _id[0], 'method': 'tools/call',
        'params': {'name': name, 'arguments': args or {}}})
    assert status == 200, (status, data)
    r = data['result']
    return r['structuredContent'], r.get('isError', False)

with socket.socket() as s:
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]

with tempfile.TemporaryDirectory() as td:
    base = f'http://127.0.0.1:{port}'
    proc = subprocess.Popen(
        ['node', str(ROOT / 'mcp/server.mjs'), '--port', str(port), '--file', f'{td}/conformance.sov'],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(60):
            try:
                status, _ = http_json(base + '/api/v1/formats')
                if status == 200:
                    break
            except Exception:
                time.sleep(.05)
        else:
            raise AssertionError('server did not start')

        # tools/list must serve exactly the manifest in mcp/tools.json.
        status, data = http_json(base + '/mcp', 'POST', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
        served = sorted(t['name'] for t in data['result']['tools'])
        manifest = sorted(json.loads((ROOT / 'mcp/tools.json').read_text())['tools'])
        assert served == manifest, (served, manifest)

        # Boundary reach-through refused identically over HTTP and MCP.
        status, _ = http_json(base + '/api/v1/components', 'POST',
            {'id': 'parent', 'symbolId': 'buffer', 'x': 500, 'y': 320,
             'form': {'dimension': 2, 'regions': {'interior': {'state': 'open'}}}})
        assert status == 201
        status, _ = http_json(base + '/api/v1/components', 'POST',
            {'id': 'child', 'symbolId': 'act', 'x': 500, 'y': 320, 'canvasId': 'canvas:component:parent'})
        assert status == 201
        status, denied = http_json(base + '/api/v1/wires', 'POST',
            {'id': 'w1', 'a': 'child', 'aSide': 'out', 'b': 'parent', 'bSide': 'out'})
        assert status == 400 and not denied['ok'] and 'Boundary blocks' in denied['error']['message'], denied
        mcp_denied, is_error = rpc(base, 'schematic.create',
            {'resource': 'wire', 'value': {'id': 'w2', 'a': 'child', 'aSide': 'out', 'b': 'parent', 'bSide': 'out'}})
        assert is_error and 'Boundary blocks' in mcp_denied['error']['message'], mcp_denied

        # Reference CRUD over HTTP and MCP.
        status, ref = http_json(base + '/api/v1/references', 'POST', {'id': 'ref1', 'label': 'ds'})
        assert status == 201 and ref['ok'], ref
        created, is_error = rpc(base, 'schematic.create', {'resource': 'reference', 'value': {'id': 'ref2', 'label': 'ds2'}})
        assert not is_error and created['ok'], created
        listed, is_error = rpc(base, 'schematic.list', {'resource': 'reference'})
        assert not is_error and len(listed['result']) == 2, listed

        # Checkpoint lifecycle over MCP: create, mutate, list, restore.
        cp, is_error = rpc(base, 'schematic.checkpoint.create', {'name': 'm1'})
        assert not is_error, cp
        rpc(base, 'schematic.create', {'resource': 'component', 'value': {'id': 'extra', 'symbolId': 'hold', 'x': 100, 'y': 100}})
        cl, is_error = rpc(base, 'schematic.checkpoint.list')
        assert not is_error, cl
        checkpoints = cl if isinstance(cl, list) else cl.get('checkpoints', [])
        assert checkpoints and checkpoints[0]['name'] == 'm1', cl
        restored, is_error = rpc(base, 'schematic.checkpoint.restore', {'id': checkpoints[0]['id']})
        assert not is_error, restored
        comps, _ = rpc(base, 'schematic.list', {'resource': 'component'})
        ids = [c['id'] for c in comps['result']]
        assert 'extra' not in ids, ids

        # history.redo over MCP restores an undone mutation.
        rpc(base, 'schematic.create', {'resource': 'component', 'value': {'id': 'redoTest', 'symbolId': 'act', 'x': 50, 'y': 50}})
        rpc(base, 'schematic.history.undo')
        redone, is_error = rpc(base, 'schematic.history.redo')
        assert not is_error, redone
        comps, _ = rpc(base, 'schematic.list', {'resource': 'component'})
        assert 'redoTest' in [c['id'] for c in comps['result']], comps

        # Document round-trip through the server keeps the schema identity.
        doc_result, is_error = rpc(base, 'schematic.document.get')
        doc = doc_result.get('document') or doc_result.get('result') or doc_result
        assert not is_error and doc['schema'] == 'soveraeign.schematic/document@0.1', doc_result
        replaced, is_error = rpc(base, 'schematic.document.replace', {'document': doc})
        assert not is_error and replaced['schema'] == 'soveraeign.schematic/document@0.1', replaced
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

print('PASS skills conformance + agent-surface coverage QA')
