"""Batch apply, scoped read, the served guide and the standard MCP handshake, on every surface.

The data core's applyBatch is all-or-none with $refs; the browser API, HTTP and MCP reach the same
function, so the same batch gives the same receipt shape everywhere and a refusal changes nothing.
"""
from __future__ import annotations

import json
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib import error, request

from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')

BATCH = {'operations': [
    {'op': 'create', 'resource': 'component', 'ref': '$src', 'value': {'symbolId': 'act', 'x': 120, 'y': 200, 'config': {'label': 'Source'}}},
    {'op': 'create', 'resource': 'component', 'ref': '$hold', 'value': {'symbolId': 'hold', 'x': 600, 'y': 200, 'config': {'label': 'Store'}}},
    {'op': 'create', 'resource': 'wire', 'ref': '$w', 'value': {'a': '$src', 'aSide': 'out', 'b': '$hold', 'bSide': 'in'}},
    {'op': 'update', 'resource': 'component', 'id': '$hold', 'patch': {'config': {'label': 'Kept'}}},
]}
# The third operation names an id that does not exist: nothing in the batch may land.
BROKEN = {'operations': [
    {'op': 'create', 'resource': 'component', 'ref': '$x', 'value': {'symbolId': 'act', 'x': 900, 'y': 200}},
    {'op': 'create', 'resource': 'component', 'value': {'symbolId': 'hold', 'x': 1100, 'y': 200}},
    {'op': 'update', 'resource': 'component', 'id': 'no-such', 'patch': {'x': 1}},
]}


def check_receipt(receipt, revision_before):
    assert receipt['ok'], receipt
    ids = receipt['result']['ids']
    assert set(ids) == {'$src', '$hold', '$w'}, ids
    assert receipt['revisionAfter'] == revision_before + 1, receipt
    assert [a['op'] for a in receipt['result']['applied']] == ['create', 'create', 'create', 'update'], receipt
    return ids


def check_refusal(receipt, revision):
    assert not receipt['ok'] and receipt['error']['index'] == 2, receipt
    assert receipt['revisionAfter'] == revision, receipt


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def http_json(url, method='GET', payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = request.Request(url, data=body, method=method, headers={'content-type': 'application/json'})
    try:
        with request.urlopen(req, timeout=10) as res:
            raw = res.read()
            return res.status, (json.loads(raw) if raw else None)
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def rpc(base, method, params=None, call_id=1):
    return http_json(base + '/mcp', 'POST', {'jsonrpc': '2.0', 'id': call_id, 'method': method, 'params': params or {}})


def tool(base, name, args=None, call_id=1):
    status, data = rpc(base, 'tools/call', {'name': name, 'arguments': args or {}}, call_id)
    assert status == 200, (status, data)
    return data['result']['structuredContent'], data['result'].get('isError', False)


# Browser API: one history entry, nothing lands on a refusal.
with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs())
    page = browser.new_page()
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(100)
    state = page.evaluate('''([batch, broken]) => {
      nodes.splice(0); wires.splice(0); diagram.revision = 0;
      const before = diagram.revision;
      const ok = SovSchematicAPI.apply(batch);
      const afterOk = {revision: diagram.revision, nodes: nodes.length, wires: wires.length};
      const refused = SovSchematicAPI.apply(broken);
      const afterRefused = {revision: diagram.revision, nodes: nodes.length, wires: wires.length};
      const slice = SovSchematicAPI.read({ids: [ok.result.ids['$hold']]});
      return {before, ok, afterOk, refused, afterRefused, slice};
    }''', [BATCH, BROKEN])
    ids = check_receipt(state['ok'], state['before'])
    assert state['afterOk']['nodes'] == 2 and state['afterOk']['wires'] == 1, state['afterOk']
    check_refusal(state['refused'], state['afterOk']['revision'])
    assert state['afterRefused'] == state['afterOk'], state
    assert [c['config']['label'] for c in state['slice']['components']] == ['Kept'], state['slice']
    browser.close()

with tempfile.TemporaryDirectory() as td:
    port = free_port()
    file = Path(td) / 'apply.sov'
    base = f'http://127.0.0.1:{port}'
    proc = subprocess.Popen(['node', str(ROOT / 'mcp/server.mjs'), '--port', str(port), '--file', str(file)],
                            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(100):
            try:
                if http_json(base + '/api/v1/formats')[0] == 200:
                    break
            except Exception:
                time.sleep(.05)
        else:
            raise AssertionError('server did not start')

        # A standard MCP client: initialize in its own version, the notification, ping.
        status, init = rpc(base, 'initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'qa', 'version': '0'}})
        assert status == 200 and init['result']['protocolVersion'] == '2025-06-18', init
        assert 'schematic.guide' in init['result']['instructions'], init
        status, _ = http_json(base + '/mcp', 'POST', {'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        assert status == 202, status
        assert rpc(base, 'ping')[1]['result'] == {}
        names = [t['name'] for t in rpc(base, 'tools/list')[1]['result']['tools']]
        assert {'schematic.apply', 'schematic.read', 'schematic.guide'} <= set(names), names

        # The guide: an index naming its steps, each step short, an unknown step refused.
        index, is_error = tool(base, 'schematic.guide')
        assert not is_error and index['next'] == 'model' and 'apply' in index['guide'], index
        step, is_error = tool(base, 'schematic.guide', {'step': 'apply'})
        assert not is_error and '$name' in step['guide'] and 'hold' in step['guide'] and step['next'] == 'layout', step
        model, _ = tool(base, 'schematic.guide', {'step': 'model'})
        assert 'The authored form' in model['guide'] and 'Palette' not in model['guide'], model['guide'][:200]
        unknown, is_error = tool(base, 'schematic.guide', {'step': 'nope'})
        assert is_error and unknown['error']['code'] == 'GUIDE_STEP_UNKNOWN', unknown

        # MCP apply, then a refused batch leaves the file and the revision alone.
        receipt, is_error = tool(base, 'schematic.apply', BATCH, 2)
        assert not is_error
        ids = check_receipt(receipt, 0)
        saved = json.loads(file.read_text(encoding='utf-8'))
        assert len(saved['components']) == 2 and len(saved['wires']) == 1, saved
        refused, is_error = tool(base, 'schematic.apply', BROKEN, 3)
        assert is_error
        check_refusal(refused, receipt['revisionAfter'])
        assert json.loads(file.read_text(encoding='utf-8'))['revision'] == receipt['revisionAfter']

        # A stale revision is refused over HTTP with 409; a fresh one lands.
        status, stale = http_json(base + '/api/v1/apply', 'POST', {**BATCH, 'ifRevision': 0})
        assert status == 409 and not stale['ok'], stale
        status, fresh = http_json(base + '/api/v1/apply', 'POST', {**BATCH, 'ifRevision': receipt['revisionAfter']})
        assert status == 200 and fresh['ok'], fresh

        # Read: by id, and by area (the second source sits at x 120 too, the first hold at 600).
        by_id, _ = tool(base, 'schematic.read', {'ids': [ids['$src']]})
        assert [c['id'] for c in by_id['components']] == [ids['$src']] and by_id['crossing'], by_id
        status, by_area = http_json(base + '/api/v1/read', 'POST', {'area': {'x': 500, 'y': 100, 'width': 200, 'height': 200}})
        assert status == 200 and {c['config']['label'] for c in by_area['components']} == {'Kept'}, by_area

        # One undo takes the whole batch back.
        undone, _ = tool(base, 'schematic.history.undo')
        assert len(undone['components']) == 2, len(undone['components'])
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
print('PASS apply, read, guide and handshake on browser, HTTP and MCP')
