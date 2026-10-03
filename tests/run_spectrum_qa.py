"""Reading a run: travel and spectrum (STATE-SPACE.md, Surfaces).

One document, built here: four clocks at 1000 ms (square duty 0.5, sine, saw, triangle), a saw at
1500 ms, a derived continuous max card mx fed by the sine over w1 (config.delay 3) and by the 1500 ms
saw over w2 (config.latencyMs 25), and a zero-latency wire w3 from the square to a derived card. Under
node it runs sim.advance(7000) on src/07-state-surface.js and reads sim.travel() and
sim.spectrum({fromMs: 3000, toMs: 6000, stepMs: 50, harmonics: 7}):

- the spectra against the sampled waves' closed forms (20 samples a period, s(n) = sin(pi/20) /
  sin(n pi/20): a sampled square or saw falls as 1/sin, not 1/n), Parseval to 1e-12 on every node,
  mx's period the least common multiple 3000 ms;
- travel: w1 3 ticks, w2 25, w3 0, at tickMs 1;
- replay: a second simulation of the same document, and a third restored from a snapshot, give
  byte-identical canonical JSON (src/03-canonical.js); the snapshot before and after the reads is
  byte-identical, so the reads change nothing;
- refusals: WINDOW_NOT_ELAPSED, WINDOW_STEP, WINDOW_TOO_LONG, UNKNOWN_NODE;
- the same document over MCP tools/call and POST /api/v1/sim/<verb> (mcp/server.mjs) gives the
  node result, in canonical JSON.

Starts no browser.
"""
from __future__ import annotations
import json
import math
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]

DOC = {
    'schema': 'soveraeign.schematic/document@0.1', 'id': 'run-spectrum-qa', 'revision': 0, 'meta': {'title': 'Run spectrum QA'},
    'references': [],
    'components': [
        {'id': 'sq', 'symbolId': 'clock', 'x': 100, 'y': 100, 'config': {'label': 'Square', 'signal': {'clock': {'wave': 'square', 'duty': 0.5, 'periodMs': 1000, 'phaseMs': 0}}}},
        {'id': 'si', 'symbolId': 'clock', 'x': 100, 'y': 260, 'config': {'label': 'Sine', 'signal': {'clock': {'wave': 'sine', 'periodMs': 1000, 'phaseMs': 0, 'sampleMs': 50}}}},
        {'id': 'sa', 'symbolId': 'clock', 'x': 100, 'y': 420, 'config': {'label': 'Saw', 'signal': {'clock': {'wave': 'saw', 'periodMs': 1000, 'phaseMs': 0, 'sampleMs': 50}}}},
        {'id': 'tr', 'symbolId': 'clock', 'x': 100, 'y': 580, 'config': {'label': 'Triangle', 'signal': {'clock': {'wave': 'triangle', 'periodMs': 1000, 'phaseMs': 0, 'sampleMs': 50}}}},
        {'id': 'sb', 'symbolId': 'clock', 'x': 100, 'y': 740, 'config': {'label': 'Saw 1.5 s', 'signal': {'clock': {'wave': 'saw', 'periodMs': 1500, 'phaseMs': 0, 'sampleMs': 50}}}},
        {'id': 'mx', 'symbolId': 'hold', 'x': 400, 'y': 500, 'config': {'label': 'Mix (max)', 'signal': {'combine': 'max', 'kind': 'continuous', 'mode': 'derived'}}},
        {'id': 'dq', 'symbolId': 'gate', 'x': 400, 'y': 100, 'config': {'label': 'Square through', 'signal': {'combine': 'and', 'mode': 'derived'}}},
    ],
    'wires': [
        {'id': 'w1', 'a': 'si', 'aSide': 'out', 'b': 'mx', 'bSide': 'in', 'config': {'delay': 3}},
        {'id': 'w2', 'a': 'sb', 'aSide': 'out', 'b': 'mx', 'bSide': 'in', 'config': {'latencyMs': 25}},
        {'id': 'w3', 'a': 'sq', 'aSide': 'out', 'b': 'dq', 'bSide': 'in', 'config': {'latencyMs': 0}},
    ],
}
WINDOW = {'fromMs': 3000, 'toMs': 6000, 'stepMs': 50, 'harmonics': 7}

NODE_RUN = r'''
const fs=require('fs'),path=require('path');
const root=process.argv[1],doc=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),win=JSON.parse(process.argv[3]);
const Surface=require(path.join(root,'src/07-state-surface.js'));
const Canonical=require(path.join(root,'src/03-canonical.js'));
const c=x=>Canonical.canonicalize(x);
const make=o=>{const m=Surface.createSimulation(doc,o);if(!m.ok)throw new Error(JSON.stringify(m));return m.sim};
const a=make();a.advance(7000);
const before=c(a.snapshot());
const travel=a.travel(),spectrum=a.spectrum(win);
const after=c(a.snapshot());
const b=make();b.advance(7000);
const r=make({restore:JSON.parse(before)});
const levels=c(a.levels());
const out={travel,spectrum,canon:{travel:c(travel),spectrum:c(spectrum)},
  replay:{travel:c(b.travel()),spectrum:c(b.spectrum(win))},
  restored:{travel:c(r.travel()),spectrum:c(r.spectrum(win))},
  snapshotUnchanged:before===after,levelsUnchanged:levels===c(a.levels()),
  refusals:{late:a.spectrum({...win,toMs:8000}),step:a.spectrum({...win,stepMs:7}),span:a.spectrum({...win,toMs:5990}),
    long:a.spectrum({fromMs:0,toMs:5000,stepMs:1}),unknown:a.spectrum({...win,nodes:['nope']}),
    notWhole:a.spectrum({...win,toMs:5500,nodes:['sq']})},
  snapshotAfterRefusals:c(a.snapshot())===before};
fs.writeFileSync(process.argv[4],JSON.stringify(out));
'''

NODE_CANON = r'''
const fs=require('fs'),path=require('path');
const Canonical=require(path.join(process.argv[1],'src/03-canonical.js'));
const xs=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
fs.writeFileSync(process.argv[3],JSON.stringify(xs.map(x=>Canonical.canonicalize(x))));
'''


def node(script, *args):
    proc = subprocess.run(['node', '-e', script, str(ROOT), *map(str, args)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert proc.returncode == 0, proc.stdout + proc.stderr


def near(x, want, tol, what):
    assert abs(x - want) <= tol, f'{what}: {x!r} is not {want!r} within {tol}'


def node_side(td):
    doc_file, out_file = td / 'doc.sov', td / 'node.json'
    doc_file.write_text(json.dumps(DOC), encoding='utf-8', newline='\n')
    node(NODE_RUN, doc_file, json.dumps(WINDOW), out_file)
    return json.loads(out_file.read_text(encoding='utf-8'))


def check_node(out):
    sp = out['spectrum']
    assert sp['ok'], sp
    by = {n['node']: n for n in sp['nodes']}
    assert sorted(by) == ['dq', 'mx', 'sa', 'sb', 'si', 'sq', 'tr'], sorted(by)
    for n in sp['nodes']:
        assert n['samples'] == 60, n
        assert n['parsevalError'] <= 1e-12, (n['node'], 'parsevalError', n['parsevalError'])
    s = lambda n: math.sin(math.pi / 20) / math.sin(n * math.pi / 20)
    amp = lambda node: [h['amplitude'] for h in by[node]['harmonics']]

    sq = by['sq']
    assert sq['periodMs'] == 1000 and sq['reason'] is None and [h['n'] for h in sq['harmonics']] == list(range(1, 8)), sq
    near(sq['energy'], 0.25, 1e-12, 'sq energy')
    a = amp('sq')
    near(a[0], 1 / (10 * math.sin(math.pi / 20)), 1e-6, 'sq a_1')
    near(a[0], 0.639245, 1e-6, 'sq a_1 (0.639245)')
    for n in (3, 5, 7):
        near(a[n - 1] / a[0], s(n), 1e-6, f'sq a_{n}/a_1')
    for n, want in ((3, 0.344577), (5, 0.221232), (7, 0.175571)):
        near(a[n - 1] / a[0], want, 1e-6, f'sq a_{n}/a_1 ({want})')
    for n in (2, 4, 6):
        assert a[n - 1] < 1e-9, ('sq even harmonic', n, a[n - 1])

    a = amp('si')
    near(a[0], 0.5, 1e-5, 'si a_1')
    for n in range(2, 8):
        assert a[n - 1] < 1e-5, ('si harmonic', n, a[n - 1])

    a = amp('sa')
    for n in range(1, 8):
        near(a[n - 1], 1 / (20 * math.sin(n * math.pi / 20)), 1e-5, f'sa a_{n}')
    for n, want in zip(range(1, 8), (1, 0.506233, 0.344577, 0.266142, 0.221232, 0.193364, 0.175571)):
        near(a[n - 1] / a[0], want, 1e-5, f'sa a_{n}/a_1 ({want})')

    a = amp('tr')
    for n, want in ((3, 0.118733), (5, 0.048943), (7, 0.030825)):
        near(a[n - 1] / a[0], s(n) ** 2, 1e-5, f'tr a_{n}/a_1')
        near(a[n - 1] / a[0], want, 1e-5, f'tr a_{n}/a_1 ({want})')
    for n in (2, 4, 6):
        assert a[n - 1] < 1e-5, ('tr even harmonic', n, a[n - 1])

    mx = by['mx']
    assert mx['periodMs'] == 3000 and mx['harmonics'] is not None and mx['reason'] is None, mx
    assert by['sb']['periodMs'] == 1500 and by['dq']['periodMs'] == 1000, (by['sb'], by['dq'])
    for n in sp['nodes']:
        if n['harmonics'] is not None:
            near(n['rest'], n['energy'] - sum(h['amplitude'] ** 2 / 2 for h in n['harmonics']), 1e-12, f"{n['node']} rest")

    tv = out['travel']
    assert tv['ok'] and tv['tickMs'] == 1, tv
    got = {w['id']: (w['delayTicks'], w['travelMs'], w['forward'], w['reverse'], w['a'], w['b']) for w in tv['wires']}
    assert got == {'w1': (3, 3, True, False, 'si', 'mx'), 'w2': (25, 25, True, False, 'sb', 'mx'), 'w3': (0, 0, True, False, 'sq', 'dq')}, got
    assert [w['id'] for w in tv['wires']] == ['w1', 'w2', 'w3'], tv
    for w in tv['wires']:
        assert sorted(w) == ['a', 'b', 'delayTicks', 'forward', 'id', 'reverse', 'travelMs'], w

    assert out['replay'] == out['canon'], 'a second run of the same document reads differently'
    assert out['restored'] == out['canon'], 'a run restored from its snapshot reads differently'
    assert out['snapshotUnchanged'] and out['levelsUnchanged'] and out['snapshotAfterRefusals'], 'a read changed the run'

    r = out['refusals']
    assert r['late']['ok'] is False and r['late']['code'] == 'WINDOW_NOT_ELAPSED', r['late']
    assert r['step']['ok'] is False and r['step']['code'] == 'WINDOW_STEP', r['step']
    assert r['span']['ok'] is False and r['span']['code'] == 'WINDOW_STEP', r['span']
    assert r['long']['ok'] is False and r['long']['code'] == 'WINDOW_TOO_LONG', r['long']
    assert r['unknown']['ok'] is False and r['unknown']['code'] == 'UNKNOWN_NODE', r['unknown']
    nw = r['notWhole']['nodes'][0]
    assert nw['harmonics'] is None and nw['reason'] == 'window-not-whole-periods' and nw['parsevalError'] <= 1e-12 and nw['energy'] > 0, nw


def http_json(url, method='GET', payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = request.Request(url, data=body, method=method, headers={'content-type': 'application/json'})
    try:
        with request.urlopen(req, timeout=30) as res:
            return res.status, json.loads(res.read())
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def call_tool(base, name, args=None, _id=[0]):
    _id[0] += 1
    status, data = http_json(base + '/mcp', 'POST', {'jsonrpc': '2.0', 'id': _id[0], 'method': 'tools/call', 'params': {'name': name, 'arguments': args or {}}})
    assert status == 200 and 'result' in data, (status, data)
    assert not data['result'].get('isError', False), data
    return data['result']['structuredContent']


def server_side(td):
    file = td / 'served.sov'
    file.write_text(json.dumps(DOC), encoding='utf-8', newline='\n')
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0));port = s.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    proc = subprocess.Popen(['node', str(ROOT / 'mcp/server.mjs'), '--port', str(port), '--file', str(file)], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(100):
            try:
                status, _ = http_json(base + '/api/v1/formats')
                if status == 200:break
            except Exception:time.sleep(.05)
        else:raise AssertionError('server did not start')
        names = [t['name'] for t in http_json(base + '/mcp', 'POST', {'jsonrpc': '2.0', 'id': 0, 'method': 'tools/list'})[1]['result']['tools']]
        assert 'schematic.sim.travel' in names and 'schematic.sim.spectrum' in names, names
        assert call_tool(base, 'schematic.sim.start')['ok']
        assert call_tool(base, 'schematic.sim.advance', {'ms': 7000})['ok']
        mcp_travel = call_tool(base, 'schematic.sim.travel')
        mcp_spectrum = call_tool(base, 'schematic.sim.spectrum', WINDOW)
        status, http_spectrum = http_json(base + '/api/v1/sim/spectrum', 'POST', WINDOW)
        assert status == 200, (status, http_spectrum)
        status, http_travel = http_json(base + '/api/v1/sim/travel', 'POST', {})
        assert status == 200, (status, http_travel)
        status, late = http_json(base + '/api/v1/sim/spectrum', 'POST', {**WINDOW, 'toMs': 8000})
        assert status == 400 and late['code'] == 'WINDOW_NOT_ELAPSED', (status, late)
    finally:
        proc.terminate()
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:proc.kill()
    raw, canon = td / 'served.json', td / 'served.canon.json'
    raw.write_text(json.dumps([mcp_travel, mcp_spectrum, http_travel, http_spectrum]), encoding='utf-8', newline='\n')
    node(NODE_CANON, raw, canon)
    return json.loads(canon.read_text(encoding='utf-8'))


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        out = node_side(td)
        check_node(out)
        mcp_travel, mcp_spectrum, http_travel, http_spectrum = server_side(td)
    assert mcp_travel == out['canon']['travel'], ('MCP travel differs from node', mcp_travel, out['canon']['travel'])
    assert mcp_spectrum == out['canon']['spectrum'], 'MCP spectrum differs from node'
    assert http_travel == out['canon']['travel'], 'HTTP travel differs from node'
    assert http_spectrum == out['canon']['spectrum'], 'HTTP spectrum differs from node'
    by = {n['node']: n for n in out['spectrum']['nodes']}
    print(json.dumps({'travel': out['travel']['wires'], 'sq': by['sq'], 'mx': by['mx']}, indent=1))
    print('PASS run spectrum QA')


if __name__ == '__main__':
    main()
