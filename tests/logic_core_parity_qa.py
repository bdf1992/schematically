"""The editor's logic runtime equals the scripts' (static: Python and Node, no browser).

src/07-logic-core.js is a port of scripts/logic_sov.py so the editor can run a circuit live.
Two runtimes are only safe if they cannot drift, so each request here runs through both and
every observable is compared:

  - every example in examples/logic: truth tables where the inputs are few, seeded random
    vectors where they are many, clock pulses for the sequential ones, noisy level waves for
    the level ones; per step the outputs, settle time, transition count and clock, and at the
    end every recorded event (time, sequence, net name, value, cause), every net value and
    every top-level wire's value and end pins;
  - gates the examples do not use (threshold with instance weights over levels, JK and T
    flip-flops, the C-element, constants);
  - refusals: the same code and the same reason for multiple drivers, an undriven input, a
    level into a truth table, a composite cycle, a missing composite, an unknown gate, a
    missing pin, an unknown input, a non-bit into a bit input, an empty hysteresis band, and
    an oscillator that never settles;
  - src/04-logic-pack.js is what scripts/build_logic_pack_js.py writes from the pack.
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from logic_sov import Circuit  # noqa: E402
from optimize_sov import Refusal  # noqa: E402
from record_run import noisy_wave  # noqa: E402

LG = ROOT / 'examples' / 'logic'


def python_run(req: dict) -> dict:
    try:
        path = Path(req['path'])
        c = Circuit(path)
        results = []
        for op in req['ops']:
            if op.get('table'):
                results.append(c.truth_table())
            elif op.get('pulse'):
                results.append(c.pulse(op['pulse'], op.get('set') or {}))
            else:
                results.append(c.apply(op.get('apply') or {}, record=bool(op.get('record'))))
        doc = json.loads(path.read_text(encoding='utf-8'))
        points = {x['id'] for x in doc.get('components', []) if x.get('symbolId') == 'point'}
        wires = {}
        for w in doc.get('wires', []):
            a = (w['a'], 'out' if w['a'] in points else w['aSide'])
            b = (w['b'], 'out' if w['b'] in points else w['bSide'])
            if a in c.net_of:
                wires[w['id']] = {'value': c.value[c.net_of[a]], 'a': f'{a[0]}.{a[1]}', 'b': f'{b[0]}.{b[1]}'}
        return {'results': results, 'events': c.events, 'values': c.value, 'nets': c.n_nets, 'wires': wires}
    except Refusal as r:
        return r.as_dict()


def node_run(reqs: list[dict]) -> list[dict]:
    out = subprocess.run(['node', str(ROOT / 'scripts' / 'logic_run.mjs')], input=json.dumps(reqs),
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def rec(ops: list[dict]) -> list[dict]:
    for op in ops:
        if 'apply' in op:
            op['record'] = True
    return ops


def example_requests() -> list[dict]:
    rng = random.Random(20260926)
    reqs = []
    for path in sorted(LG.glob('*.sov')):
        c = Circuit(path)
        names = sorted(c.inputs)
        levels = [n for n in names if c.levels.get(n)]
        if levels:
            wave = noisy_wave(160)
            ops = rec([{'apply': {levels[0]: round(x * (40 if path.stem == 'reorder' else 1), 4)}} for x in wave])
        elif 'CLK' in names:
            data = [n for n in names if n != 'CLK']
            ops = [{'pulse': 'CLK', 'set': {n: rng.randint(0, 1) for n in data}} for _ in range(18)]
            ops.insert(0, {'apply': {n: 0 for n in names}, 'record': True})
            ops.append({'apply': {'CLK': 1}, 'record': True})
        elif path.stem == 'sr-latch':
            ops = rec([{'apply': v} for v in ({'S': 0, 'R': 1}, {'R': 0}, {'S': 1}, {'S': 0}, {'R': 1}, {'R': 0})])
            reqs.append({'path': str(path), 'ops': rec([{'apply': {'S': 1, 'R': 1}}, {'apply': {'S': 0, 'R': 0}}])})
        elif len(names) <= 9:
            ops = [{'table': True}] + rec([{'apply': {n: rng.randint(0, 1) for n in names}} for _ in range(30)])
        else:
            ops = rec([{'apply': {n: rng.randint(0, 1) for n in names}} for _ in range(60)])
        reqs.append({'path': str(path), 'ops': ops})
    return reqs


# ---------------------------------------------------------------- synthetic documents

def part(cid: str, logic: dict, pins: list[str]) -> dict:
    return {'id': cid, 'symbolId': 'gate', 'config': {'logic': logic, 'attachmentPoints': [{'id': p} for p in pins]}}


def inp(name: str, level: bool = False) -> dict:
    return part(f'in-{name}', {'kind': 'input', 'name': name, **({'type': 'level'} if level else {})}, ['out'])


def out(name: str) -> dict:
    return part(f'out-{name}', {'kind': 'output', 'name': name}, ['in'])


def wire(i: int, a: str, a_side: str, b: str, b_side: str) -> dict:
    return {'id': f'w{i}', 'a': a, 'aSide': a_side, 'b': b, 'bSide': b_side}


def doc(components: list, wires: list) -> dict:
    return {'components': components, 'wires': wires}


def synthetic(tmp: Path) -> list[dict]:
    def write(name: str, d: dict) -> str:
        p = tmp / name
        p.write_text(json.dumps(d), encoding='utf-8')
        return str(p)

    reqs = []
    # Gates the examples do not use.
    th = doc([inp('X', True), inp('Y', True), inp('Z', True), part('t', {'gate': 'threshold', 'weights': [0.5, 1, 2], 'theta': 1.5}, ['a', 'b', 'c', 'q']), out('Q')],
             [wire(1, 'in-X', 'out', 't', 'a'), wire(2, 'in-Y', 'out', 't', 'b'), wire(3, 'in-Z', 'out', 't', 'c'), wire(4, 't', 'q', 'out-Q', 'in')])
    rng = random.Random(7)
    # Bit corners put the weighted sum exactly on theta (0.5 + 1 = 1.5), where >= and > differ.
    corners = [{'X': x, 'Y': y, 'Z': z} for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    reqs.append({'path': write('threshold.sov', th), 'ops': rec([{'apply': v} for v in corners] +
                                                                [{'apply': {k: round(rng.random(), 3) for k in 'XYZ'}} for _ in range(40)])})
    ff = doc([inp('J'), inp('K'), inp('T'), inp('A'), inp('B'), inp('CLK'), part('jk', {'gate': 'jkff'}, ['j', 'k', 'clk', 'q', 'qn']),
              part('tf', {'gate': 'tff', 'delay': 3}, ['t', 'clk', 'q', 'qn']), part('ce', {'gate': 'c-element'}, ['a', 'b', 'q']),
              part('one', {'gate': 'true'}, ['q']), part('an', {'gate': 'and'}, ['a', 'b', 'q']),
              out('JQ'), out('TQ'), out('TN'), out('C'), out('K1')],
             [wire(1, 'in-J', 'out', 'jk', 'j'), wire(2, 'in-K', 'out', 'jk', 'k'), wire(3, 'in-CLK', 'out', 'jk', 'clk'),
              wire(4, 'in-T', 'out', 'tf', 't'), wire(5, 'in-CLK', 'out', 'tf', 'clk'), wire(6, 'in-A', 'out', 'ce', 'a'),
              wire(7, 'in-B', 'out', 'ce', 'b'), wire(8, 'jk', 'q', 'out-JQ', 'in'), wire(9, 'tf', 'q', 'out-TQ', 'in'),
              wire(10, 'tf', 'qn', 'out-TN', 'in'), wire(11, 'ce', 'q', 'out-C', 'in'), wire(12, 'one', 'q', 'an', 'a'),
              wire(13, 'in-J', 'out', 'an', 'b'), wire(14, 'an', 'q', 'out-K1', 'in')])
    rng = random.Random(11)
    reqs.append({'path': write('flipflops.sov', ff),
                 'ops': [{'apply': {k: 0 for k in ('J', 'K', 'T', 'A', 'B', 'CLK')}, 'record': True}] +
                        [{'pulse': 'CLK', 'set': {k: rng.randint(0, 1) for k in 'JKTAB'}} for _ in range(20)]})

    # Refusals: each document is wrong in one way.
    wrong = {
        'drivers': doc([inp('A'), inp('B'), out('Q')], [wire(1, 'in-A', 'out', 'out-Q', 'in'), wire(2, 'in-B', 'out', 'out-Q', 'in')]),
        'undriven': doc([inp('A'), part('g', {'gate': 'and'}, ['a', 'b', 'q']), out('Q')],
                        [wire(1, 'in-A', 'out', 'g', 'a'), wire(2, 'g', 'q', 'out-Q', 'in')]),
        'level': doc([inp('X', True), part('g', {'gate': 'not'}, ['a', 'q']), out('Q')],
                     [wire(1, 'in-X', 'out', 'g', 'a'), wire(2, 'g', 'q', 'out-Q', 'in')]),
        'cycle': doc([part('me', {'composite': 'cycle.sov'}, [])], []),
        'missing': doc([part('p', {'composite': 'nowhere.sov'}, [])], []),
        'unknown': doc([part('g', {'gate': 'frobnicate'}, ['q'])], []),
        'pin': doc([part('g', {'gate': 'and'}, ['a', 'q'])], []),
        'band': doc([inp('X', True), part('s', {'gate': 'schmitt', 'low': 0.7, 'high': 0.3}, ['x', 'q', 'qn']), out('Q')],
                    [wire(1, 'in-X', 'out', 's', 'x'), wire(2, 's', 'q', 'out-Q', 'in')]),
        'oscillator': doc([inp('A'), part('n', {'gate': 'nand'}, ['a', 'b', 'q']), out('Q')],
                          [wire(1, 'in-A', 'out', 'n', 'a'), wire(2, 'n', 'q', 'n', 'b'), wire(3, 'n', 'q', 'out-Q', 'in')]),
    }
    for name, d in wrong.items():
        reqs.append({'path': write(f'{name}.sov', d), 'ops': [{'apply': {'A': 1}} if name == 'oscillator' else {}]})
    ok = write('ok.sov', doc([inp('A'), inp('X', True), out('Q')], [wire(1, 'in-A', 'out', 'out-Q', 'in')]))
    reqs.append({'path': ok, 'ops': [{'apply': {'Nope': 1}}]})
    reqs.append({'path': ok, 'ops': [{'apply': {'A': 2}}]})
    return reqs


def compare(reqs: list[dict]) -> tuple[int, int]:
    got = node_run(reqs)
    refused = 0
    for req, js in zip(reqs, got):
        py = python_run(req)
        name = Path(req['path']).name
        if 'refused' in py:
            refused += 1
            assert js.get('refused') == py['refused'], (name, py, js)
            assert js['reason'] == py['reason'], (name, py['reason'], js['reason'])
            continue
        assert 'refused' not in js, (name, js)
        for key in ('nets', 'values', 'wires', 'events', 'results'):
            assert js[key] == py[key], (name, key, first_difference(py[key], js[key]))
    return len(reqs), refused


def first_difference(a, b, where='') -> str:
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                return first_difference(a.get(k), b.get(k), f'{where}.{k}')
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f'{where}: {len(a)} vs {len(b)} items'
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                return first_difference(x, y, f'{where}[{i}]')
    return f'{where}: python {a!r} vs js {b!r}'


def main() -> int:
    subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build_logic_pack_js.py'), '--check'], check=True)
    n, refused = compare(example_requests())
    assert n == len(list(LG.glob('*.sov'))) + 1 and refused == 1, (n, refused)   # the latch released from 11 races
    with tempfile.TemporaryDirectory() as tmp:
        n, refused = compare(synthetic(Path(tmp)))
        assert refused == 11, refused
    print('logic_core_parity QA PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
