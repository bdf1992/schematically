"""State space surfaces (slice 1c of STATE-SPACE.md, issue #43): settle, state query and runs on
every surface.

One scenario runs on the browser API (Playwright), over HTTP and over MCP (the server started as
tests/agent_api_mcp_golden_qa.py starts it), in three documents:

- examples/state/and.sov: start with A=1, B=1 and settle; query Q; take the trace; replay it (handle
  null); a refused start; a second start with the same inputs (a new handle, stepped on its own while
  the first run is untouched); a budget over the surface limit; BUDGET_SPENT and TRACE_INVALID with
  their details; a trace of a run with no inputs, kept for the next document;
- examples/state/not-loop.sov: start (budget 40) and settle to oscillating; replay the and.sov trace
  (REPLAY_KEY_MISMATCH with its fields); an unknown handle; a run id used as a handle;
- and.sov with a Path delay -1: a start refused with RUN_REFUSED and its refusals.

Every run receipt must be identical across the three surfaces; the only surface-specific field is
the HTTP status. Afterwards the document, its revision and the history are unchanged on every
surface, and no recovery is saved in the browser. Over HTTP alone, a body that is not JSON and a path
that does not decode give 400 run receipts. The unbuilt index.source.html carries no packs and says so.
"""
from __future__ import annotations
import json
from pathlib import Path
import http.client
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
LIMIT = 1000000


def bad_document():
    doc = json.loads((STATE / 'and.sov').read_text(encoding='utf-8'))
    # Delay 0 is a zero-delay Path since 2026-09-26; -1 is the refused example.
    doc['id'] = 'state-and-delay-negative'
    doc['wires'][0]['config'] = {'direction': 'forward', 'delay': -1}
    return json.dumps(doc)


DOCUMENTS = [('and', (STATE / 'and.sov').read_text(encoding='utf-8')), ('loop', (STATE / 'not-loop.sov').read_text(encoding='utf-8')), ('bad', bad_document())]


def tamper(trace):
    t = json.loads(json.dumps(trace))
    t['ledger'][1]['hash'] = ('1' if t['ledger'][1]['hash'][0] == '0' else '0') + t['ledger'][1]['hash'][1:]
    return t


# The scenario: (label, operation, argument). An argument naming an earlier label ('@label') is that
# receipt's handle; ('trace', label) is that receipt's trace; ('runId', label) its run id.
SCENARIO = {
    'and': [
        ('start', 'start', {'inputs': AND_INPUTS}),
        ('settle', 'settle', '@start'),
        ('query', 'query', ('@start', Q)),
        ('trace', 'trace', '@start'),
        ('replay', 'replay', ('trace', 'trace')),
        ('refused', 'start', {'budget': -1}),
        ('start2', 'start', {'inputs': AND_INPUTS}),
        ('step2', 'step', '@start2'),
        ('traceFirst', 'trace', '@start'),
        ('overLimit', 'start', {'budget': LIMIT + 1}),
        ('huge', 'start', {'budget': 1e20}),
        ('small', 'start', {'inputs': AND_INPUTS, 'budget': 1}),
        ('spent', 'step', '@small'),
        ('tampered', 'replay', ('tampered', 'trace')),
        ('plain', 'start', {}),
        ('plainTrace', 'trace', '@plain'),
    ],
    'loop': [
        ('start', 'start', {'budget': 40}),
        ('settle', 'settle', '@start'),
        ('mismatch', 'replay', ('trace', 'and.plainTrace')),
        ('unknown', 'step', 'no-such-run'),
        ('byRunId', 'step', ('runId', 'start')),
    ],
    'bad': [
        ('refused', 'start', {}),
    ],
}


def resolve(arg, receipts):
    if isinstance(arg, str) and arg.startswith('@'):
        return receipts[arg[1:]]['handle']
    if isinstance(arg, tuple) and arg[0] == 'trace':
        return receipts[arg[1]]['result']
    if isinstance(arg, tuple) and arg[0] == 'tampered':
        return tamper(receipts[arg[1]]['result'])
    if isinstance(arg, tuple) and arg[0] == 'runId':
        return receipts[arg[1]]['runId']
    return arg


def run_scenario(name, call, carried):
    """call(operation, arg) -> (receipt, extra); returns [(label, receipt, extra)]."""
    receipts, steps = dict(carried), []
    for label, operation, arg in SCENARIO[name]:
        if operation == 'query':
            value = (resolve(arg[0], receipts), arg[1])
        else:
            value = resolve(arg, receipts)
        receipt, extra = call(operation, value)
        receipts[label] = receipt;receipts[f'{name}.{label}'] = receipt
        steps.append((f'{name}.{label}', receipt, extra))
    return steps, {k: v for k, v in receipts.items() if '.' in k}


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0));return s.getsockname()[1]


def http_json(url, method='GET', payload=None, raw=None):
    body = raw if raw is not None else None if payload is None else json.dumps(payload).encode()
    req = request.Request(url, data=body, method=method, headers={'content-type': 'application/json'})
    try:
        with request.urlopen(req, timeout=30) as res:
            return res.status, json.loads(res.read())
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def http_raw_path(port, method, path, body=b''):
    """A request whose path is sent as is (urllib would not send a path that does not decode)."""
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    conn.request(method, path, body=body, headers={'content-type': 'application/json'})
    res = conn.getresponse();data = res.read();conn.close()
    return res.status, json.loads(data)


def mcp(base, method, params=None, _id=[0]):
    _id[0] += 1
    status, data = http_json(base + '/mcp', 'POST', {'jsonrpc': '2.0', 'id': _id[0], 'method': method, 'params': params or {}})
    assert status == 200 and 'result' in data, (status, data)
    return data['result']


def call_tool(base, name, args=None):
    result = mcp(base, 'tools/call', {'name': name, 'arguments': args or {}})
    return result['structuredContent'], result.get('isError', False)


BROWSER_STATE = '''()=>({document:JSON.stringify(SovSchematicAPI.document.get()),revision:diagram.revision,
  history:SovSchematicAPI.history.list().length,file:SovSchematicAPI.file.info(),recovery:localStorage.getItem(LOCAL_RECOVERY_KEY)})'''
BROWSER_CALL = '''([operation,value])=>{
  const R=SovSchematicAPI.run;
  if(operation==='query')return R.query(value[0],value[1]);
  if(operation==='start')return R.start(value);
  if(operation==='replay')return R.replay(value);
  return R[operation](value);
}'''


def browser_scenario():
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs())
        steps, states, docs, carried = [], {}, {}, {}
        for name, text in DOCUMENTS:
            # A fresh page per document, as a fresh server per document: each surface's registry counts its
            # starts from 1. Loaded from its file URL, not set_content, so the page has localStorage and
            # recovery is observable.
            page = browser.new_page();page.goto((ROOT / 'index.html').resolve().as_uri(), wait_until='load');page.wait_for_timeout(100)
            page.evaluate('([text,name])=>SovSchematicAPI.file.open(text,name)', [text, f'{name}.sov'])
            before = page.evaluate(BROWSER_STATE)
            docs[name] = json.loads(before['document'])
            got, kept = run_scenario(name, lambda op, value: (page.evaluate(BROWSER_CALL, [op, value]), None), carried)
            carried.update(kept);steps += got
            states[name] = (before, page.evaluate(BROWSER_STATE))
        # The unbuilt page carries an empty pack list, and says so.
        source = browser.new_page();source.goto((ROOT / 'index.source.html').resolve().as_uri(), wait_until='load');source.wait_for_timeout(300)
        source.evaluate('([text])=>SovSchematicAPI.file.open(text,"and.sov")', [DOCUMENTS[0][1]])
        no_packs = source.evaluate('''()=>({tag:document.getElementById('sov-packs').textContent,start:SovSchematicAPI.run.start({}),
          replay:SovSchematicAPI.run.replay({})})''')
        built_tag = page.evaluate("()=>JSON.parse(document.getElementById('sov-packs').textContent)")
        browser.close()
    return steps, states, docs, no_packs, built_tag


def server_scenario(kind, docs):
    """kind is 'http' or 'mcp'. One server per document, its file the document the browser holds
    after opening the example: the editor fills defaults in on open (and advances the revision), so
    that, not the example file, is the document every surface runs."""
    steps, states, tools, malformed, carried = [], {}, None, {}, {}
    with tempfile.TemporaryDirectory() as td:
        for name, _ in DOCUMENTS:
            file = Path(td) / f'{name}.sov';file.write_text(json.dumps(docs[name]), encoding='utf-8', newline='\n')
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
                    undo, is_error = call_tool(base, 'schematic.history.undo')
                    return {'document': json.dumps(doc, sort_keys=True), 'revision': doc['revision'],
                            'history': 0 if is_error and undo == {'error': 'Nothing to undo'} else undo, 'file': file.read_bytes()}
                before = state()
                if kind == 'http':
                    def call(operation, value):
                        if operation == 'start':return tuple(reversed(http_json(base + '/api/v1/runs', 'POST', value)))
                        if operation == 'replay':return tuple(reversed(http_json(base + '/api/v1/replay', 'POST', value)))
                        if operation == 'query':
                            return tuple(reversed(http_json(base + f'/api/v1/runs/{request.quote(value[0], safe="")}/query', 'POST', value[1])))
                        method = 'GET' if operation == 'trace' else 'POST'
                        return tuple(reversed(http_json(base + f'/api/v1/runs/{request.quote(value, safe="")}/{operation}', method)))
                else:
                    tool = {'start': 'schematic.run.start', 'step': 'schematic.run.step', 'settle': 'schematic.run.settle',
                            'trace': 'schematic.run.trace', 'query': 'schematic.state.query', 'replay': 'schematic.run.replay'}
                    def call(operation, value):
                        if operation == 'start':args = value
                        elif operation == 'replay':args = {'trace': value}
                        elif operation == 'query':args = {'handle': value[0], **value[1]}
                        else:args = {'handle': value}
                        return call_tool(base, tool[operation], args)
                got, kept = run_scenario(name, call, carried)
                carried.update(kept);steps += got
                if kind == 'http' and name == 'and':
                    handle = kept['and.start']['handle']
                    malformed['start'] = http_json(base + '/api/v1/runs', 'POST', raw=b'{"budget": 4')
                    malformed['replay'] = http_json(base + '/api/v1/replay', 'POST', raw=b'not json')
                    malformed['query'] = http_json(base + f'/api/v1/runs/{handle}/query', 'POST', raw=b'{entity')
                    malformed['uri'] = http_raw_path(port, 'POST', '/api/v1/runs/%E0%A4%A/step')
                    malformed['uriTrace'] = http_raw_path(port, 'GET', '/api/v1/runs/%ZZ/trace')
                    malformed['route'] = http_json(base + '/api/v1/runs/x/fly', 'POST', {})
                states[name] = (before, state())
            finally:
                proc.terminate()
                try:proc.wait(timeout=3)
                except subprocess.TimeoutExpired:proc.kill()
    return steps, states, tools, malformed


def main() -> None:
    browser, browser_states, docs, no_packs, built_tag = browser_scenario()
    http_steps, http_states, tools, malformed = server_scenario('http', docs)
    mcp_steps, mcp_states, _, _ = server_scenario('mcp', docs)

    # The six tools are listed in mcp/tools.json and in tools/list, each with an inputSchema.
    manifest = json.loads((ROOT / 'mcp/tools.json').read_text(encoding='utf-8'))['tools']
    served = {t['name']: t for t in tools}
    for name in RUN_TOOLS:
        assert name in manifest and name in served, name
        assert served[name]['inputSchema']['type'] == 'object', served[name]
    for name in ('schematic.run.step', 'schematic.run.settle', 'schematic.run.trace', 'schematic.state.query'):
        assert served[name]['inputSchema']['required'][0] == 'handle', served[name]

    labels = [label for label, _, _ in browser]
    assert labels == [f'{name}.{label}' for name, _ in DOCUMENTS for label, _, _ in SCENARIO[name]], labels
    assert [x[0] for x in http_steps] == labels and [x[0] for x in mcp_steps] == labels, ([x[0] for x in http_steps], [x[0] for x in mcp_steps])

    # Receipts identical across the three surfaces, byte for byte in canonical form.
    canon = lambda x: json.dumps(x, sort_keys=True, separators=(',', ':'))
    for (label, b, _), (_, h, status), (_, m, is_error) in zip(browser, http_steps, mcp_steps):
        assert canon(b) == canon(h), (label, 'browser and HTTP receipts differ', b, h)
        assert canon(b) == canon(m), (label, 'browser and MCP receipts differ', b, m)
        assert sorted(b) == ['error', 'handle', 'head', 'ok', 'operation', 'result', 'runId', 'schema', 'tickAfter', 'tickBefore'], b
        assert b['schema'] == RECEIPT, b
        # HTTP status (the one surface-specific field) and MCP isError follow the receipt.
        want = (201 if b['operation'] == 'schematic.run.start' else 200) if b['ok'] else 404 if b['error']['code'] == 'RUN_NOT_FOUND' else 409
        assert status == want, (label, status, want)
        assert is_error is (not b['ok']), (label, is_error)

    r = {label: receipt for label, receipt, _ in browser}
    start = r['and.start']
    assert start['ok'] and start['operation'] == 'schematic.run.start' and start['tickBefore'] is None and start['tickAfter'] is None, start
    assert start['handle'] == start['runId'] + '.1', start
    assert start['result']['replayKey']['inputs'] == [dict(i, channel='main') for i in AND_INPUTS] and start['result']['budget'] == 10000, start
    settled = r['and.settle']
    assert settled['ok'] and settled['result'] == {'kind': 'quiet'} and settled['tickBefore'] is None and settled['tickAfter'] == 2, settled
    assert settled['handle'] == start['handle'] and settled['runId'] == start['runId'], settled
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
    assert replayed['ok'] and replayed['runId'] == start['runId'] and replayed['handle'] is None and replayed['head'] == trace['head'] and replayed['tickAfter'] == 2, replayed
    assert replayed['result'] == {'records': trace['result']['records']}, replayed
    refused = r['and.refused']
    assert refused['ok'] is False and refused['error']['code'] == 'INPUT_INVALID' and refused['runId'] is None and refused['handle'] is None and refused['result'] is None, refused
    # A second start with the same inputs: the same run id, a new handle, stepped on its own.
    second, step2, first = r['and.start2'], r['and.step2'], r['and.traceFirst']
    assert second['ok'] and second['runId'] == start['runId'] and second['handle'] == start['runId'] + '.2' and second['head'] == start['head'], second
    assert step2['ok'] and step2['handle'] == second['handle'] and (step2['tickBefore'], step2['tickAfter']) == (None, 0), step2
    assert first['ok'] and canon(first['result']) == canon(trace['result']) and first['handle'] == start['handle'], 'the second start touched the first run'
    # The surface budget limit.
    for key in ('and.overLimit', 'and.huge'):
        assert r[key]['ok'] is False and r[key]['error']['code'] == 'INPUT_INVALID' and 'over the surface limit 1000000' in r[key]['error']['message'], r[key]
    # Refusal details, the same on every surface.
    assert r['and.small']['ok'] and r['and.spent']['error'] == {'code': 'BUDGET_SPENT', 'message': r['and.spent']['error']['message'], 'details': {'tick': 0, 'left': 2}}, r['and.spent']
    tampered = r['and.tampered']['error']
    assert tampered['code'] == 'TRACE_INVALID' and tampered['details']['entry'] == 1 and tampered['details']['errors'], tampered
    mismatch = r['loop.mismatch']['error']
    assert mismatch['code'] == 'REPLAY_KEY_MISMATCH' and mismatch['details'] == {'fields': ['documentId', 'documentHash', 'definitions']}, mismatch
    bad = r['bad.refused']['error']
    assert bad['code'] == 'RUN_REFUSED' and [x['code'] for x in bad['details']['refusals']] == ['PATH_DELAY_INVALID'], bad
    loop = r['loop.settle']
    assert loop['ok'] and loop['result'] == OSCILLATING and loop['tickAfter'] == 2, loop
    for key in ('loop.unknown', 'loop.byRunId'):
        unknown = r[key]
        assert unknown['ok'] is False and unknown['error']['code'] == 'RUN_NOT_FOUND' and 'details' not in unknown['error'], unknown
        assert unknown['runId'] is None and unknown['handle'] is None and unknown['head'] is None, unknown

    # Over HTTP, malformed input gets a 400 run receipt, not a 500.
    for key, operation in (('start', 'schematic.run.start'), ('replay', 'schematic.run.replay'), ('query', 'schematic.state.query'),
                           ('uri', 'schematic.run.step'), ('uriTrace', 'schematic.run.trace')):
        status, receipt = malformed[key]
        assert status == 400 and receipt['schema'] == RECEIPT and receipt['operation'] == operation, (key, status, receipt)
        assert receipt['ok'] is False and receipt['error']['code'] == 'INPUT_INVALID' and receipt['runId'] is None and receipt['handle'] is None, (key, receipt)
    assert malformed['route'][0] == 404, malformed['route']

    # The unbuilt page has no packs and says so; the built page carries every data/*.pack.json.
    assert no_packs['tag'] == '[]', no_packs['tag']
    for key in ('start', 'replay'):
        assert no_packs[key]['error'] == {'code': 'PACK_INVALID', 'message': 'this page carries no packs', 'details': {'definitions': ['logic.and@1']}}, no_packs[key]
    assert built_tag == [json.loads(p.read_text(encoding='utf-8')) for p in sorted((ROOT / 'data').glob('*.pack.json'), key=lambda p: p.name)], 'the sov-packs tag differs from data/'

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
