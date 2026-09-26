"""`schematic.logic.run` over MCP (static: Node server, no browser).

The MCP server answers with the same `run` as the editor's `SovSchematicAPI.logic.run`
(src/07-logic-core.js). Checked against scripts/logic_sov.py:

  - the tool is listed with its schema;
  - a full adder served from a folder that also holds half-adder.sov: every vector's outputs,
    settle time and transitions, and every top-level wire's value, equal logic_sov.py's;
  - a clocked sequence of steps on the 4-bit accumulator equals logic_sov.py pulse by pulse;
  - composites passed by name stand in for files that are not there;
  - a missing composite is a typed refusal (isError), and the run changes nothing on disk.
"""
from __future__ import annotations

import itertools
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib import request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from logic_sov import Circuit  # noqa: E402

LG = ROOT / 'examples' / 'logic'


def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def rpc(base: str, method: str, params: dict | None = None) -> dict:
    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}}).encode()
    req = request.Request(base + '/mcp', data=body, method='POST', headers={'content-type': 'application/json'})
    with request.urlopen(req, timeout=10) as res:
        return json.loads(res.read())['result']


def serve(file: Path):
    port = free_port()
    proc = subprocess.Popen(['node', str(ROOT / 'mcp' / 'server.mjs'), '--port', str(port), '--file', str(file)], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    base = f'http://127.0.0.1:{port}'
    for _ in range(100):
        try:
            request.urlopen(base + '/', timeout=1).read()
            return proc, base
        except OSError:
            time.sleep(0.05)
    proc.kill()
    raise SystemExit(proc.stdout.read())


def run(base: str, args: dict) -> tuple[dict, bool]:
    r = rpc(base, 'tools/call', {'name': 'schematic.logic.run', 'arguments': args})
    return r['structuredContent'], r.get('isError', False)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for name in ('full-adder.sov', 'half-adder.sov', 'accumulator4.sov', 'adder4.sov', 'register4.sov'):
            shutil.copy(LG / name, td / name)
        proc, base = serve(td / 'full-adder.sov')
        try:
            tools = {t['name']: t for t in rpc(base, 'tools/list')['tools']}
            assert 'schematic.logic.run' in tools and 'steps' in tools['schematic.logic.run']['inputSchema']['properties']
            doc = json.loads((LG / 'full-adder.sov').read_text(encoding='utf-8'))
            for a, b, cin in itertools.product((0, 1), repeat=3):
                vector = {'A': a, 'B': b, 'Cin': cin}
                got, err = run(base, {'vector': vector})
                py = Circuit(LG / 'full-adder.sov')
                want = py.apply(vector)
                assert not err and got['ok'], got
                step = got['steps'][0]
                assert {k: step[k] for k in ('outputs', 'settle', 'transitions', 'time')} == want, (vector, step, want)
                for w in doc['wires']:
                    net = py.net_of[(w['a'], w['aSide'])]
                    assert got['wires'][w['id']]['value'] == py.value[net], (vector, w['id'])
            before = (td / 'full-adder.sov').read_bytes()
            assert before == (LG / 'full-adder.sov').read_bytes(), 'a run writes nothing'
        finally:
            proc.kill()

        proc, base = serve(td / 'accumulator4.sov')
        try:
            steps = [{'set': {'X0': x & 1, 'X1': x >> 1 & 1, 'X2': x >> 2 & 1, 'X3': x >> 3 & 1}, 'pulse': 'CLK'} for x in (3, 5, 9, 15, 1)]
            got, err = run(base, {'steps': steps})
            assert not err and got['ok'], got
            py = Circuit(LG / 'accumulator4.sov')
            for step, g in zip(steps, got['steps']):
                want = py.pulse('CLK', step['set'])
                assert {k: g[k] for k in want} == want, (step, g, want)
        finally:
            proc.kill()

        lone = td / 'lone'
        lone.mkdir()
        shutil.copy(LG / 'full-adder.sov', lone / 'full-adder.sov')
        proc, base = serve(lone / 'full-adder.sov')
        try:
            got, err = run(base, {'vector': {'A': 1, 'B': 1, 'Cin': 0}})
            assert err and got['refused'] == 'NO_COMPOSITE', got
            half = json.loads((LG / 'half-adder.sov').read_text(encoding='utf-8'))
            got, err = run(base, {'vector': {'A': 1, 'B': 1, 'Cin': 0}, 'composites': {'half-adder.sov': half}})
            assert not err and got['steps'][0]['outputs'] == {'S': 0, 'Cout': 1}, got
        finally:
            proc.kill()
    print('logic_mcp QA PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
