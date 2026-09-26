"""State space surfaces (slice 1c of STATE-SPACE.md, issue #43): settle, state query and runs on
every surface.

One scenario runs on the browser API (Playwright), over HTTP and over MCP (the server started as
tests/agent_api_mcp_golden_qa.py starts it): start examples/state/and.sov with A=1, B=1 and settle;
query Q; take the trace; replay it; a refused start; start not-loop.sov (budget 40) and settle to
oscillating; an unknown run id. Every run receipt must be identical across the three surfaces; the
only surface-specific field is the HTTP status. Afterwards the document, its revision and the
history are unchanged on every surface, and no recovery is saved in the browser.
"""
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

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'examples/state'
RECEIPT = 'soveraeign.schematic/run-receipt@0.1'
RUN_TOOLS = ['schematic.run.start', 'schematic.run.step', 'schematic.run.settle', 'schematic.run.trace',
             'schematic.state.query', 'schematic.run.replay']
AND_INPUTS = [{'entity': 'A', 'point': 'self', 'value': True, 'at': 0}, {'entity': 'B', 'point': 'self', 'value': True, 'at': 0}]
Q = {'entity': 'Q', 'observable': 'logic.level'}
OSCILLATING = {'kind': 'oscillating', 'period': 2, 'subjects': ['G.a.main', 'G.q.main']}


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0));return s.getsockname()[1]


def http_json(url, method='GET', payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = request.Request(url, data=body, method=method, headers={'content-type': 'application/json'})
    try:
        with request.urlopen(req, timeout=10) as res:
            return res.status, json.loads(res.read())
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def mcp(base, method, params=None, _id=[0]):
    _id[0] += 1
    status, data = http_json(base + '/mcp', 'POST', {'jsonrpc': '2.0', 'id': _id[0], 'method': method, 'params': params or {}})
    assert status == 200 and 'result' in data, (status, data)
    return data['result']


def call(base, name, args=None):
    result = mcp(base, 'tools/call', {'name': name, 'arguments': args or {}})
    return result['structuredContent'], result.get('isError', False)


# --- The scenario, once per surface. Each step yields (label, receipt, http status or None).

BROWSER_AND = '''(inputs)=>{
  const R=SovSchematicAPI.run,out=[];
  const start=R.start({inputs});out.push(['start',start]);
  out.push(['settle',R.settle(start.runId)]);
  out.push(['query',R.query(start.runId,{entity:'Q',observable:'logic.level'})]);
  const trace=R.trace(start.runId);out.push(['trace',trace]);
  out.push(['replay',R.replay(trace.result)]);
  out.push(['refused',R.start({budget:-1})]);
  return out;
}'''
BROWSER_LOOP = '''()=>{
  const R=SovSchematicAPI.run,out=[];
  const start=R.start({budget:40});out.push(['start',start]);
  out.push(['settle',R.settle(start.runId)]);
  out.push(['unknown',R.step('no-such-run')]);
  return out;
}'''
BROWSER_STATE = '''()=>({document:JSON.stringify(SovSchematicAPI.document.get()),revision:diagram.revision,
  history:SovSchematicAPI.history.list().length,file:SovSchematicAPI.file.info(),recovery:localStorage.getItem(LOCAL_RECOVERY_KEY)})'''


def browser_scenario():
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs())
        # Loaded from its file URL, not set_content, so the page has localStorage and recovery is observable.
        page = browser.new_page();page.goto((ROOT / 'index.html').resolve().as_uri(), wait_until='load');page.wait_for_timeout(100)
        steps, states, docs = [], {}, {}
        for name, script, arg in (('and', BROWSER_AND, AND_INPUTS), ('loop', BROWSER_LOOP, None)):
            page.evaluate('([text,name])=>SovSchematicAPI.file.open(text,name)', [(STATE / f'{"and" if name == "and" else "not-loop"}.sov').read_text(encoding='utf-8'), f'{name}.sov'])
            before = page.evaluate(BROWSER_STATE)
            docs[name] = json.loads(before['document'])
            got = page.evaluate(script, arg) if arg is not None else page.evaluate(script)
            after = page.evaluate(BROWSER_STATE)
            states[name] = (before, after)
            steps += [(f'{name}.{label}', receipt, None) for label, receipt in got]
        browser.close()
    return steps, states, docs


def server_scenario(kind, docs):
    """kind is 'http' or 'mcp'. One server per document, its file the document the browser holds
    after opening the example: the editor fills defaults in on open (and advances the revision), so
    that, not the example file, is the document every surface runs."""
    steps, states, tools = [], {}, None
    with tempfile.TemporaryDirectory() as td:
        for name, sov in (('and', 'and.sov'), ('loop', 'not-loop.sov')):
            file = Path(td) / sov;file.write_text(json.dumps(docs[name]), encoding='utf-8')
            port = free_port();base = f'http://127.0.0.1:{port}'
            proc = subprocess.Popen(['node', str(ROOT / 'mcp/server.mjs'), '--port', str(port), '--file', str(file)], cwd=ROOT,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            try:
                for _ in range(100):
                    try:
                        status, _ = http_json(base + '/api/v1/formats')
                        if status == 200:break
                    except Exception:time.sleep(.05)
                else:raise AssertionError('server did not start')
                if tools is None:tools = mcp(base, 'tools/list')['tools']

                def state():
                    status, doc = http_json(base + '/api/v1/document');assert status == 200, doc
                    undo, is_error = call(base, 'schematic.history.undo')
                    return {'document': json.dumps(doc, sort_keys=True), 'revision': doc['revision'],
                            'history': 0 if is_error and undo == {'error': 'Nothing to undo'} else undo, 'file': file.read_bytes()}
                before = state()
                if kind == 'http':
                    def run(label, method, path, payload=None):
                        status, receipt = http_json(base + path, method, payload);steps.append((f'{name}.{label}', receipt, status));return receipt
                    if name == 'and':
                        start = run('start', 'POST', '/api/v1/runs', {'inputs': AND_INPUTS})
                        run('settle', 'POST', f"/api/v1/runs/{start['runId']}/settle")
                        run('query', 'POST', f"/api/v1/runs/{start['runId']}/query", Q)
                        trace = run('trace', 'GET', f"/api/v1/runs/{start['runId']}/trace")
                        run('replay', 'POST', '/api/v1/replay', trace['result'])
                        run('refused', 'POST', '/api/v1/runs', {'budget': -1})
                    else:
                        start = run('start', 'POST', '/api/v1/runs', {'budget': 40})
                        run('settle', 'POST', f"/api/v1/runs/{start['runId']}/settle")
                        run('unknown', 'POST', '/api/v1/runs/no-such-run/step')
                else:
                    def run(label, tool, args=None):
                        receipt, is_error = call(base, tool, args);steps.append((f'{name}.{label}', receipt, is_error));return receipt
                    if name == 'and':
                        start = run('start', 'schematic.run.start', {'inputs': AND_INPUTS})
                        run('settle', 'schematic.run.settle', {'runId': start['runId']})
                        run('query', 'schematic.state.query', {'runId': start['runId'], **Q})
                        trace = run('trace', 'schematic.run.trace', {'runId': start['runId']})
                        run('replay', 'schematic.run.replay', {'trace': trace['result']})
                        run('refused', 'schematic.run.start', {'budget': -1})
                    else:
                        start = run('start', 'schematic.run.start', {'budget': 40})
                        run('settle', 'schematic.run.settle', {'runId': start['runId']})
                        run('unknown', 'schematic.run.step', {'runId': 'no-such-run'})
                states[name] = (before, state())
            finally:
                proc.terminate()
                try:proc.wait(timeout=3)
                except subprocess.TimeoutExpired:proc.kill()
    return steps, states, tools


def main() -> None:
    browser, browser_states, docs = browser_scenario()
    http, http_states, tools = server_scenario('http', docs)
    mcp_steps, mcp_states, _ = server_scenario('mcp', docs)

    # The six tools are listed in mcp/tools.json and in tools/list, each with an inputSchema.
    manifest = json.loads((ROOT / 'mcp/tools.json').read_text(encoding='utf-8'))['tools']
    served = {t['name']: t for t in tools}
    for name in RUN_TOOLS:
        assert name in manifest and name in served, name
        assert served[name]['inputSchema']['type'] == 'object', served[name]

    labels = [label for label, _, _ in browser]
    assert labels == ['and.start', 'and.settle', 'and.query', 'and.trace', 'and.replay', 'and.refused',
                      'loop.start', 'loop.settle', 'loop.unknown'], labels
    assert [x[0] for x in http] == labels and [x[0] for x in mcp_steps] == labels, ([x[0] for x in http], [x[0] for x in mcp_steps])

    # Receipts identical across the three surfaces, byte for byte in canonical form.
    canon = lambda x: json.dumps(x, sort_keys=True, separators=(',', ':'))
    for (label, b, _), (_, h, status), (_, m, is_error) in zip(browser, http, mcp_steps):
        assert canon(b) == canon(h), (label, 'browser and HTTP receipts differ', b, h)
        assert canon(b) == canon(m), (label, 'browser and MCP receipts differ', b, m)
        assert sorted(b) == ['error', 'head', 'ok', 'operation', 'result', 'runId', 'schema', 'tickAfter', 'tickBefore'], b
        assert b['schema'] == RECEIPT, b
        # HTTP status (the one surface-specific field) and MCP isError follow the receipt.
        want = (201 if label.endswith('.start') else 200) if b['ok'] else 404 if b['error']['code'] == 'RUN_NOT_FOUND' else 409
        assert status == want, (label, status, want)
        assert is_error is (not b['ok']), (label, is_error)

    r = {label: receipt for label, receipt, _ in browser}
    start = r['and.start']
    assert start['ok'] and start['operation'] == 'schematic.run.start' and start['tickBefore'] is None and start['tickAfter'] is None, start
    assert start['result']['replayKey']['inputs'] == [dict(i, channel='main') for i in AND_INPUTS] and start['result']['budget'] == 10000, start
    settled = r['and.settle']
    assert settled['ok'] and settled['result'] == {'kind': 'quiet'} and settled['tickBefore'] is None and settled['tickAfter'] == 2, settled
    query = r['and.query']
    assert query['ok'] and query['result'] and all(x['subject']['entity'] == 'Q' and x['observable'] == 'logic.level' for x in query['result']), query
    assert [(x['time']['logical'], x['value']) for x in query['result']] == [(2, True)], query
    trace = r['and.trace']
    assert trace['ok'] and trace['result']['format'] == 'soveraeign.schematic/trace@0.1' and trace['result']['through'] == 2, trace
    assert trace['head'] == trace['result']['head'] == settled['head'] == start['head'], trace
    # The same fold as the golden and.11.sovtrace (the document differs by the editor's defaults, so ids and hashes do not).
    golden = json.loads((STATE / 'and.11.sovtrace').read_text(encoding='utf-8'))
    fold = lambda t: [(x['time']['logical'], x['subject']['entity'], x['subject']['point'], x['value'], x['observer']) for x in t['records']]
    assert fold(trace['result']) == fold(golden) and trace['result']['replayKey']['inputs'] == golden['replayKey']['inputs'], fold(trace['result'])
    replayed = r['and.replay']
    assert replayed['ok'] and replayed['runId'] == start['runId'] and replayed['head'] == trace['head'] and replayed['tickAfter'] == 2, replayed
    assert replayed['result'] == {'records': trace['result']['records']}, replayed
    refused = r['and.refused']
    assert refused['ok'] is False and refused['error']['code'] == 'INPUT_INVALID' and refused['runId'] is None and refused['result'] is None, refused
    loop = r['loop.settle']
    assert loop['ok'] and loop['result'] == OSCILLATING and loop['tickAfter'] == 2, loop
    unknown = r['loop.unknown']
    assert unknown['ok'] is False and unknown['error']['code'] == 'RUN_NOT_FOUND' and unknown['runId'] is None and unknown['head'] is None, unknown

    # Nothing a run does reaches the document, its revision, history or recovery.
    for surface, states in (('browser', browser_states), ('http', http_states), ('mcp', mcp_states)):
        for name, (before, after) in states.items():
            for key in before:
                assert before[key] == after[key], (surface, name, key, before[key], after[key])
            if surface != 'browser':
                assert before['history'] == 0, (surface, name, 'the server history is not empty', before['history'])
    print('PASS state space surfaces QA')


if __name__ == '__main__':
    main()
