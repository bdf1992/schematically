"""The logic examples run on state space and compute what they claim (static: Python and Node).

The examples in examples/logic/ are state space documents (STATE-SPACE.md): gates are
Components bound to `truth_table@1` definitions from data/core.logic.pack.json and
data/logic.gates.pack.json. Each is run here by the engine itself (src/07-state-space.js,
through scripts/run_state.mjs) and its settled outputs are checked against an oracle written
here, not read from the definitions:

  - generated files are current: the pack, the glyphs, the examples and the golden trace;
  - every example passes the engine's load checks with both packs;
  - every definition, on the gallery, for all eight vectors of A, B, C, against its Boolean
    function;
  - half and full adder, XOR from NANDs and the multiplexer, exhaustively;
  - the 4-bit adder (all 512 vectors) sums, the 8-bit adder sums on 64 seeded vectors, and the
    adder/subtractor adds or subtracts mod 16 (all 512 vectors), carry out included;
  - the golden carry trace replays byte for byte, settles at 8, and on its way passes the
    ripple's transient sums 6, 4 and 0 (transport delay: every change is carried);
  - a document that binds a definition no pack holds is refused, not run;
  - the semantic fingerprint (scripts/sov_fingerprint.py) sees a changed definition and a
    changed Wire delay, and not a moved Component.
"""
from __future__ import annotations

import itertools
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LG = ROOT / 'examples' / 'logic'
PACKS = [ROOT / 'data' / 'core.logic.pack.json', ROOT / 'data' / 'logic.gates.pack.json']

ORACLE = {
    'NOT': lambda a, b, c: 1 - a, 'AND': lambda a, b, c: a & b, 'OR': lambda a, b, c: a | b,
    'XOR': lambda a, b, c: a ^ b, 'BUFFER': lambda a, b, c: a, 'NAND': lambda a, b, c: 1 - (a & b),
    'NOR': lambda a, b, c: 1 - (a | b), 'XNOR': lambda a, b, c: 1 - (a ^ b),
    'IMPLY': lambda a, b, c: int(not a or b), 'NIMPLY': lambda a, b, c: int(a and not b),
    'CIMPLY': lambda a, b, c: int(a or not b), 'NCIMPLY': lambda a, b, c: int(not a and b),
    'MAJORITY': lambda a, b, c: int(a + b + c >= 2), 'MUX': lambda a, b, c: b if c else a,   # s is fed from C
    'HALF_ADDER_S': lambda a, b, c: (a + b) % 2, 'HALF_ADDER_C': lambda a, b, c: (a + b) // 2,
    'FULL_ADDER_S': lambda a, b, c: (a + b + c) % 2, 'FULL_ADDER_COUT': lambda a, b, c: (a + b + c) // 2,
}


def run(requests: list[dict]) -> list[dict]:
    out = subprocess.run(['node', str(ROOT / 'scripts' / 'run_state.mjs')], input=json.dumps(requests),
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def node_eval(script: str, payload) -> dict:
    prelude = ("require('./src/03-canonical.js');require('./src/06-attachment-core.js');require('./src/05-data-core.js');"
               "const S=require('./src/07-state-space.js');const fs=require('fs');"
               "const input=JSON.parse(fs.readFileSync(0,'utf8'));")
    out = subprocess.run(['node', '-e', prelude + script], input=json.dumps(payload), cwd=ROOT,
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def inputs(vector: dict) -> list[dict]:
    return [{'entity': k, 'value': bool(v), 'at': 0} for k, v in sorted(vector.items())]


def settled(result: dict) -> dict[str, int]:
    """The last level each Point's self port took: what a sink reads once the run is quiet."""
    assert result['ok'], result
    last = {}
    for r in result['trace']['records']:
        if r['observable'] == 'logic.level' and r['subject']['point'] == 'self':
            last[r['subject']['entity']] = int(r['value'])
    return last


def number(values: dict, prefix: str, width: int) -> int:
    return sum(values.get(f'{prefix}{i}', 0) << i for i in range(width))


def check_generated() -> None:
    for script in ('build_logic_pack.py', 'logic_glyphs.py', 'build_logic_examples.py'):
        subprocess.run([sys.executable, str(ROOT / 'scripts' / script), '--check'], check=True)


def check_load() -> None:
    names = sorted(p.name for p in LG.glob('*.sov'))
    assert names == ['add-sub4.sov', 'adder4.sov', 'adder8.sov', 'full-adder.sov', 'gates.sov', 'half-adder.sov',
                     'mux2.sov', 'xor-nand.sov'], names
    got = node_eval("const packs=input.packs.map(p=>JSON.parse(fs.readFileSync(p)));"
                    "console.log(JSON.stringify(Object.fromEntries(input.docs.map(f=>[f,S.checkDocument(JSON.parse(fs.readFileSync(f)),packs)]))))",
                    {'packs': [str(p) for p in PACKS], 'docs': [str(LG / n) for n in names]})
    for f, r in got.items():
        assert r['ok'], (f, r['refusals'])
    # Unresolvable: the same gallery with only core.logic refuses, naming what is missing.
    r = node_eval("console.log(JSON.stringify(S.checkDocument(JSON.parse(fs.readFileSync(input.doc)),[JSON.parse(fs.readFileSync(input.pack))])))",
                  {'doc': str(LG / 'gates.sov'), 'pack': str(PACKS[0])})
    assert not r['ok'] and {x['code'] for x in r['refusals']} == {'DEFINITION_UNRESOLVED'}, r


def check_behaviour() -> None:
    reqs, expect = [], []

    def add(name: str, vector: dict, want: dict) -> None:
        reqs.append({'path': str(LG / name), 'inputs': inputs(vector)})
        expect.append((name, vector, want))

    for a, b, c in itertools.product((0, 1), repeat=3):
        add('gates.sov', {'A': a, 'B': b, 'C': c}, {k: f(a, b, c) for k, f in ORACLE.items()})
        add('full-adder.sov', {'A': a, 'B': b, 'Cin': c}, {'S': (a + b + c) % 2, 'Cout': (a + b + c) // 2})
        add('mux2.sov', {'S': a, 'A': b, 'B': c}, {'Q': c if a else b})
    for a, b in itertools.product((0, 1), repeat=2):
        add('half-adder.sov', {'A': a, 'B': b}, {'S': a ^ b, 'C': a & b})
        add('xor-nand.sov', {'A': a, 'B': b}, {'Q': a ^ b})

    def bits(prefix: str, value: int, width: int) -> dict:
        return {f'{prefix}{i}': (value >> i) & 1 for i in range(width)}

    for x, y, c in itertools.product(range(16), range(16), (0, 1)):
        total = x + y + c
        add('adder4.sov', {**bits('A', x, 4), **bits('B', y, 4), 'Cin': c}, {**bits('S', total % 16, 4), 'Cout': total // 16})
        sub = c
        result = (x - y) % 16 if sub else (x + y) % 16
        carry = int(x >= y) if sub else (x + y) // 16   # two's complement: carry out means no borrow
        add('add-sub4.sov', {**bits('A', x, 4), **bits('B', y, 4), 'SUB': sub}, {**bits('S', result, 4), 'Cout': carry})
    rng = random.Random(20260926)
    for _ in range(64):
        x, y, c = rng.randrange(256), rng.randrange(256), rng.randint(0, 1)
        total = x + y + c
        add('adder8.sov', {**bits('A', x, 8), **bits('B', y, 8), 'Cin': c}, {**bits('S', total % 256, 8), 'Cout': total // 256})

    results = run(reqs)
    for (name, vector, want), result in zip(expect, results):
        got = settled(result)
        wrong = {k: (got.get(k), v) for k, v in want.items() if got.get(k, 0) != v}
        assert not wrong, (name, vector, wrong)
    assert len(results) == len(reqs) == 8 * 3 + 4 * 2 + 512 * 2 + 64


def check_golden() -> None:
    trace = json.loads((LG / 'adder4.carry.sovtrace').read_text(encoding='utf-8'))
    r = node_eval("const packs=input.packs.map(p=>JSON.parse(fs.readFileSync(p)));"
                  "const out=S.replay({doc:JSON.parse(fs.readFileSync(input.doc)),packs,trace:input.trace});"
                  "console.log(JSON.stringify({ok:out.ok,code:out.code||null,message:out.message||null,records:out.records||null}))",
                  {'packs': [str(p) for p in PACKS], 'doc': str(LG / 'adder4.sov'), 'trace': trace})
    assert r['ok'], r
    assert r['records'] == trace['records'], 'replay reproduces the recorded records'
    # The S bus over time, from the records: 7 before the change, 8 after, and the ripple between.
    level: dict[str, int] = {}
    seen = []
    for rec in trace['records']:
        if rec['subject']['point'] == 'self' and rec['subject']['entity'].startswith('S'):
            level[rec['subject']['entity']] = int(rec['value'])
            if rec['time']['logical'] >= 20:
                s = number(level, 'S', 4)
                if not seen or seen[-1][1] != s or seen[-1][0] != rec['time']['logical']:
                    seen.append((rec['time']['logical'], s))
    by_tick = {}
    for t, s in seen:
        by_tick[t] = s
    values = [by_tick[t] for t in sorted(by_tick)]
    assert values[-1] == 8, values
    assert values[:-1] == [6, 4, 0], ('the carry ripples through 6, 4 and 0 before 8', values)


def check_fingerprint() -> None:
    import copy
    sys.path.insert(0, str(ROOT / 'scripts'))
    from sov_fingerprint import document_fingerprint
    doc = json.loads((LG / 'half-adder.sov').read_text(encoding='utf-8'))
    base = document_fingerprint(doc)
    gate = next(i for i, c in enumerate(doc['components']) if c.get('config', {}).get('definition') == 'logic.xor@1')

    def after(change) -> str:
        d = copy.deepcopy(doc)
        change(d)
        return document_fingerprint(d)
    assert after(lambda d: d['components'][gate]['config'].update(definition='logic.xnor@1')) != base, 'a definition is behaviour'
    assert after(lambda d: d['wires'][0]['config'].update(delay=3)) != base, 'a Wire delay changes a run'
    assert after(lambda d: d['components'][gate].update(x=999)) == base, 'a move is layout'


def main() -> int:
    check_generated()
    check_fingerprint()
    check_load()
    check_behaviour()
    check_golden()
    print('logic_examples QA PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
