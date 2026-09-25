"""Logic gates, composites and binary computation QA.

`scripts/logic_sov.py` claims, and this checks against definitions it does not share:

  - the pack's gates, with inputs chosen, cover all sixteen Boolean functions of two inputs,
    and every gate in the gallery document computes what Python's own operators say, in any
    order of input vectors (combinational outputs do not depend on history);
  - a pack table that is incomplete, malformed or repeats a row is refused;
  - composites are what they claim: the half adder built from gates equals the pack's
    half-adder primitive; XOR from four NANDs equals XOR; the gate-built multiplexer equals
    the mux primitive;
  - composites compute: the full adder, and the 4-bit adder over all 512 inputs, satisfy
    S + 2^n * Cout = A + B + Cin; the 8-bit adder (two 4-bit adders) on edge and random cases;
    the adder/subtractor gives A - B mod 16 with Cout meaning "no borrow";
  - carry ripples in time linear in width: flipping Cin under A = all ones settles after
    2 gate delays per bit;
  - feedback makes memory: the NOR latch sets, resets and holds; released from S = R = 1 at
    once it races, and a ring of three NOTs never settles; both are refused as UNSETTLED;
  - wiring faults are refused, not guessed: two drivers on a net, an undriven input, an
    unknown gate, a missing pin, a composite that uses itself;
  - the examples are what the builder writes, validate in the data core, and their
    semantic fingerprint moves when a gate changes kind.
"""
from __future__ import annotations

import itertools
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from logic_sov import PACK, Circuit, Refusal, bits, load_pack, number  # noqa: E402

DIR = ROOT / 'examples' / 'logic'

# Independent definitions: Python's operators, not the pack's tables.
DEFINED = {
    'false': lambda a, b, c: 0, 'true': lambda a, b, c: 1,
    'buffer': lambda a, b, c: a, 'not': lambda a, b, c: 1 - a,
    'and': lambda a, b, c: a & b, 'or': lambda a, b, c: a | b, 'xor': lambda a, b, c: a ^ b,
    'nand': lambda a, b, c: 1 - (a & b), 'nor': lambda a, b, c: 1 - (a | b), 'xnor': lambda a, b, c: 1 - (a ^ b),
    'imply': lambda a, b, c: (1 - a) | b, 'nimply': lambda a, b, c: a & (1 - b),
    'cimply': lambda a, b, c: a | (1 - b), 'ncimply': lambda a, b, c: (1 - a) & b,
    'majority': lambda a, b, c: int(a + b + c >= 2),
    'mux': lambda a, b, c: b if c else a,             # gallery wires s to C
    'half-adder-s': lambda a, b, c: a ^ b, 'half-adder-c': lambda a, b, c: a & b,
}


# Reference models for the stateful gates: (state, inputs, clock edge seen) -> next state.
# Written from the textbook definitions, not from the pack's tables.
REFERENCE = {
    'dff': (['d', 'clk'], lambda q, i, edge: i['d'] if edge else q),
    'tff': (['t', 'clk'], lambda q, i, edge: q ^ i['t'] if edge else q),
    'jkff': (['j', 'k', 'clk'], lambda q, i, edge: ((i['j'] and not q) or (not i['k'] and q)) if edge else q),
    'd-latch': (['d', 'en'], lambda q, i, edge: i['d'] if i['en'] else q),
    'sr-latch': (['s', 'r'], lambda q, i, edge: 0 if i['r'] else (1 if i['s'] else q)),
    'c-element': (['a', 'b'], lambda q, i, edge: i['a'] if i['a'] == i['b'] else q),
}


def refused(fn, code: str) -> None:
    try:
        fn()
    except Refusal as r:
        assert r.code == code, (r.code, code, r.reason)
        return
    raise AssertionError(f'expected refusal {code}')


def check_pack() -> None:
    pack = load_pack()
    tables = {k for k, g in pack.items() if g['kind'] == 'table'}
    assert set(DEFINED) - {'half-adder-s', 'half-adder-c'} | {'half-adder'} == tables, sorted(tables)
    assert set(pack) - tables == set(REFERENCE) | {'threshold', 'compare', 'schmitt'}, sorted(set(pack) - tables)
    # Every function of two inputs, as its output column over ab = 00, 01, 10, 11, is some
    # pack gate with its inputs taken from a and b (either, both, or neither).
    columns = set()
    for g in pack.values():
        if g['kind'] != 'table' or len(g['inputs']) > 2 or len(g['outputs']) != 1:
            continue
        for choice in itertools.product((0, 1), repeat=len(g['inputs'])):   # 0 = a, 1 = b
            col = ''
            for a, b in ((0, 0), (0, 1), (1, 0), (1, 1)):
                key = ''.join(str((a, b)[k]) for k in choice)
                col += str(g['table'][key][0])
            columns.add(col)
    assert len(columns) == 16, sorted(columns)

    with tempfile.TemporaryDirectory() as tmp:
        base = json.loads(PACK.read_text())
        for change, code in [
            (lambda p: p['gates']['and']['table'].pop(), 'INCOMPLETE_TABLE'),
            (lambda p: p['gates']['and']['table'].__setitem__(0, '0:0'), 'BAD_ROW'),
            (lambda p: p['gates']['and']['table'].__setitem__(1, '00:1'), 'DUPLICATE_ROW'),
        ]:
            broken = json.loads(json.dumps(base))
            change(broken)
            path = Path(tmp) / 'pack.json'
            path.write_text(json.dumps(broken))
            refused(lambda: load_pack(path), code)


def check_gallery() -> None:
    vectors = list(itertools.product((0, 1), repeat=3))
    orders = [vectors, list(reversed(vectors)), [vectors[i] for i in (0, 1, 3, 2, 6, 7, 5, 4)]]  # plain, reversed, Gray
    rng = random.Random(7)
    orders += [rng.sample(vectors * 3, 24) for _ in range(3)]
    for order in orders:
        c = Circuit(DIR / 'gates.sov')
        for a, b, cc in order:
            out = c.apply({'A': a, 'B': b, 'C': cc})['outputs']
            for name, fn in DEFINED.items():
                assert out[name] == fn(a, b, cc), (name, a, b, cc, out[name])


def table(path: Path) -> dict[tuple, dict]:
    c = Circuit(path)
    return {tuple(sorted(r['inputs'].items())): r['outputs'] for r in c.truth_table()}


def check_composites_equal_primitives() -> None:
    pack = load_pack()
    for key, out in table(DIR / 'half-adder.sov').items():
        v = dict(key)
        s, c = pack['half-adder']['table'][f"{v['A']}{v['B']}"]
        assert (out['S'], out['C']) == (s, c), (v, out)
    for key, out in table(DIR / 'xor-nand.sov').items():
        v = dict(key)
        assert out['Q'] == pack['xor']['table'][f"{v['A']}{v['B']}"][0], (v, out)
    for key, out in table(DIR / 'mux2.sov').items():
        v = dict(key)
        assert out['Q'] == pack['mux']['table'][f"{v['S']}{v['A']}{v['B']}"][0], (v, out)
    # Composition flattens: the 4-bit adder is four full adders, each two half adders and an OR.
    c = Circuit(DIR / 'adder4.sov')
    assert len(c.gates) == 4 * (2 * 2 + 1), len(c.gates)
    assert any(g['id'] == 'fa3.ha2.x' for g in c.gates)


def check_arithmetic() -> None:
    for key, out in table(DIR / 'full-adder.sov').items():
        v = dict(key)
        assert out['S'] + 2 * out['Cout'] == v['A'] + v['B'] + v['Cin'], (v, out)

    c = Circuit(DIR / 'adder4.sov')
    cases = [(a, b, ci) for a in range(16) for b in range(16) for ci in (0, 1)]
    for order in (cases, random.Random(1).sample(cases, len(cases))):
        for a, b, ci in order:
            out = c.apply({**bits('A', a, 4), **bits('B', b, 4), 'Cin': ci})['outputs']
            assert number(out, 'S', 4) + 16 * out['Cout'] == a + b + ci, (a, b, ci, out)

    c = Circuit(DIR / 'adder8.sov')
    rng = random.Random(8)
    edges = [(0, 0, 0), (255, 255, 1), (255, 0, 1), (128, 128, 0), (170, 85, 0), (170, 85, 1), (1, 254, 1)]
    for a, b, ci in edges + [(rng.randrange(256), rng.randrange(256), rng.randrange(2)) for _ in range(1500)]:
        out = c.apply({**bits('A', a, 8), **bits('B', b, 8), 'Cin': ci})['outputs']
        assert number(out, 'S', 8) + 256 * out['Cout'] == a + b + ci, (a, b, ci, out)

    c = Circuit(DIR / 'add-sub4.sov')
    for a in range(16):
        for b in range(16):
            out = c.apply({**bits('A', a, 4), **bits('B', b, 4), 'SUB': 0})['outputs']
            assert number(out, 'S', 4) + 16 * out['Cout'] == a + b, ('add', a, b, out)
            out = c.apply({**bits('A', a, 4), **bits('B', b, 4), 'SUB': 1})['outputs']
            assert number(out, 'S', 4) == (a - b) % 16, ('sub', a, b, out)
            assert out['Cout'] == int(a >= b), ('borrow', a, b, out)


def check_carry_ripple_is_linear() -> None:
    settle = {}
    for name, width in (('adder4', 4), ('adder8', 8)):
        c = Circuit(DIR / f'{name}.sov')
        c.apply({**bits('A', 2 ** width - 1, width), **bits('B', 0, width), 'Cin': 0})
        r = c.apply({'Cin': 1})
        assert number(r['outputs'], 'S', width) == 0 and r['outputs']['Cout'] == 1
        settle[width] = r['settle']
    # Each full adder adds two gate delays to the carry (its second half adder's AND, then
    # the OR), so the worst case grows linearly with width.
    assert settle[4] == 2 * 4 and settle[8] == 2 * 8, settle


def check_feedback() -> None:
    c = Circuit(DIR / 'sr-latch.sov', event_budget=2000)
    steps = [({'S': 0, 'R': 1}, (0, 1)), ({'S': 0, 'R': 0}, (0, 1)), ({'S': 1, 'R': 0}, (1, 0)),
             ({'S': 0, 'R': 0}, (1, 0)), ({'S': 0, 'R': 1}, (0, 1)), ({'S': 0, 'R': 0}, (0, 1)),
             ({'S': 1, 'R': 1}, (0, 0))]
    for vector, (q, qn) in steps:
        out = c.apply(vector)['outputs']
        assert (out['Q'], out['QN']) == (q, qn), (vector, out)
    refused(lambda: c.apply({'S': 0, 'R': 0}), 'UNSETTLED')                  # released at once: a race
    fresh = Circuit(DIR / 'sr-latch.sov', event_budget=2000)
    refused(lambda: fresh.apply({'S': 0, 'R': 0}), 'UNSETTLED')              # never initialized

    with tempfile.TemporaryDirectory() as tmp:
        ring = circuit_doc([('n1', 'not'), ('n2', 'not'), ('n3', 'not')],
                           [('n1.q', 'n2.a'), ('n2.q', 'n3.a'), ('n3.q', 'n1.a'), ('n3.q', 'out-Q')],
                           inputs=[], outputs=['Q'])
        path = Path(tmp) / 'ring.sov'
        path.write_text(json.dumps(ring))
        refused(lambda: Circuit(path, event_budget=500).apply({}), 'UNSETTLED')


def one_gate(tmp: Path, kind: str, pins: list[str], outs: list[str], level: set = frozenset(), **params) -> Circuit:
    """A document holding one gate, an input per pin and an output per output pin."""
    doc = circuit_doc([('g', kind)], [(f'in-{p}', f'g.{p}') for p in pins] + [(f'g.{o}', f'out-{o}') for o in outs],
                      pins, outs)
    for c in doc['components']:
        if c['id'] == 'g':
            c['config']['logic'].update(params)
        if c['id'].startswith('in-') and c['id'][3:] in level:
            c['config']['logic']['type'] = 'level'
    path = tmp / f'{kind}.sov'
    path.write_text(json.dumps(doc))
    return Circuit(path, event_budget=5000)


def check_sequential_gates() -> None:
    pack = load_pack()
    rng = random.Random(6)
    with tempfile.TemporaryDirectory() as tmp:
        for kind, (pins, step) in REFERENCE.items():
            g = pack[kind]
            c = one_gate(Path(tmp), kind, pins, g['outputs'])
            q, inputs = 0, {p: 0 for p in pins}
            assert c.apply(dict(inputs))['outputs']['q'] == 0, kind            # power-on: the declared initial state
            for _ in range(400):
                pin = rng.choice(pins)                                          # one input changes at a time
                before = inputs[pin]
                inputs[pin] = 1 - before
                edge = pin == 'clk' and (before, inputs[pin]) == (0, 1)
                q = int(step(q, inputs, edge))
                out = c.apply({pin: inputs[pin]})['outputs']
                assert out['q'] == q, (kind, inputs, out, q)
                if 'qn' in out:
                    assert out['qn'] == 1 - q, (kind, out)


def check_threshold_and_levels() -> None:
    rng = random.Random(9)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for theta, reference in ((2, lambda a, b, c: int(a + b + c >= 2)), (1, lambda a, b, c: a | b | c),
                                 (3, lambda a, b, c: a & b & c)):
            c = one_gate(tmp, 'threshold', ['a', 'b', 'c'], ['q'], theta=theta)
            for a, b, cc in itertools.product((0, 1), repeat=3):
                assert c.apply({'a': a, 'b': b, 'c': cc})['outputs']['q'] == reference(a, b, cc), (theta, a, b, cc)
        for _ in range(20):
            w = [round(rng.uniform(-2, 3), 2) for _ in range(3)]
            theta = round(rng.uniform(-1, 3), 2)
            c = one_gate(tmp, 'threshold', ['a', 'b', 'c'], ['q'], level={'a', 'b', 'c'}, weights=w, theta=theta)
            for _ in range(30):
                x = [round(rng.uniform(0, 1), 3) for _ in range(3)]
                q = c.apply(dict(zip('abc', x)))['outputs']['q']
                assert q == int(sum(wi * xi for wi, xi in zip(w, x)) >= theta), (w, theta, x, q)

        # A noisy level around 0.5: the comparator chatters, the Schmitt trigger switches only
        # when the level really crosses its band, and matches its reference at every step.
        cmp_ = one_gate(tmp, 'compare', ['x'], ['q'], level={'x'}, theta=0.5)
        hys = one_gate(tmp, 'schmitt', ['x'], ['q', 'qn'], level={'x'}, low=0.4, high=0.6)
        state, flips = {'cmp': 0, 'hys': 0}, {'cmp': 0, 'hys': 0}
        for k in range(600):
            trend = 0.5 + 0.3 * math.sin(k / 60)                     # slow swing across the band
            x = round(trend + rng.uniform(-0.08, 0.08), 4)            # noise smaller than the band
            q1 = cmp_.apply({'x': x})['outputs']['q']
            q2 = hys.apply({'x': x})['outputs']['q']
            expect = 1 if x >= 0.6 else 0 if x <= 0.4 else state['hys']
            assert q1 == int(x >= 0.5) and q2 == expect, (k, x, q1, q2, expect)
            flips['cmp'] += q1 != state['cmp']
            flips['hys'] += q2 != state['hys']
            state = {'cmp': q1, 'hys': q2}
        swings = 600 / (math.pi * 60)                                 # half-periods of the trend
        assert flips['hys'] <= math.ceil(swings) + 1, flips            # once per real crossing
        assert flips['cmp'] > 4 * flips['hys'], flips                  # chatter

        for doc_change, code in [
            (lambda: one_gate(tmp, 'schmitt', ['x'], ['q', 'qn'], level={'x'}, low=0.7, high=0.3), 'BAD_PARAMS'),
            (lambda: one_gate(tmp, 'threshold', ['a', 'b', 'c'], ['q'], weights=[1, 1]), 'BAD_PARAMS'),
            (lambda: one_gate(tmp, 'and', ['a', 'b'], ['q'], level={'a'}), 'LEVEL_INTO_BINARY'),
            (lambda: one_gate(tmp, 'dff', ['d', 'clk'], ['q', 'qn'], level={'d'}), 'LEVEL_INTO_BINARY'),
            (lambda: one_gate(tmp, 'and', ['a', 'b'], ['q']).apply({'a': 0.5}), 'NOT_A_BIT'),
        ]:
            refused(doc_change, code)


def check_level_examples() -> None:
    c = Circuit(DIR / 'window.sov')
    for x in [i / 100 for i in range(0, 101, 5)] + [0.3, 0.7, 0.2999, 0.6999]:
        assert c.apply({'X': x})['outputs']['IN'] == int(0.3 <= x < 0.7), x
    c = Circuit(DIR / 'reorder.sov')
    order = 0
    for stock in [40, 25, 11, 10, 8, 15, 29, 30, 31, 20, 10.5, 9.99, 12, 30]:
        order = 1 if stock <= 10 else 0 if stock >= 30 else order
        assert c.apply({'STOCK': float(stock)})['outputs']['ORDER'] == order, stock
    # Completion: AND reports "both done now"; the C-element reports "both finished" and holds
    # it until both have reset, which is what a return-to-zero handshake needs.
    c = Circuit(DIR / 'completion.sov')
    for step, (both, done) in [({'MATERIALS': 1}, (0, 0)), ({'WORK': 1}, (1, 1)), ({'MATERIALS': 0}, (0, 1)),
                               ({'MATERIALS': 1}, (1, 1)), ({'WORK': 0}, (0, 1)), ({'MATERIALS': 0}, (0, 0))]:
        out = c.apply(step)['outputs']
        assert (out['BOTH'], out['DONE']) == (both, done), (step, out)


def check_sequential_composites() -> None:
    rng = random.Random(4)
    reg = Circuit(DIR / 'register4.sov')
    held = 0
    for _ in range(60):
        v = rng.randrange(16)
        out = reg.apply(bits('D', v, 4))['outputs']
        assert number(out, 'Q', 4) == held, 'a register must not change without a clock edge'
        out = reg.pulse('CLK')['outputs']
        held = v
        assert number(out, 'Q', 4) == held

    acc = Circuit(DIR / 'accumulator4.sov')
    total = 0
    for _ in range(200):
        x = rng.randrange(16)
        carry = int(total + x >= 16)
        before = acc.apply(bits('X', x, 4))['outputs']
        assert before['Carry'] == carry, 'Carry shows whether this step will wrap'
        total = (total + x) % 16
        assert number(acc.pulse('CLK')['outputs'], 'ACC', 4) == total

    ripple, sync = Circuit(DIR / 'ripple-counter4.sov'), Circuit(DIR / 'sync-counter4.sov')
    assert number(ripple.apply({})['outputs'], 'Q', 4) == 0 and number(sync.apply({})['outputs'], 'Q', 4) == 0
    for k in range(1, 41):
        for c in (ripple, sync):
            c.apply({'CLK': 1}, record=True)
            outs = [e for e in c.events if e['net'].startswith('out-Q')]
            seen = set()
            value = {i: None for i in range(4)}
            for e in outs:
                value[int(e['net'][5])] = e['value']
            c.events.clear()
            assert number(c.apply({'CLK': 0})['outputs'], 'Q', 4) == k % 16, (c.path.name, k)
            if c is sync:
                assert len({e['t'] for e in outs}) <= 1, ('synchronous outputs change together', k, outs)
            elif k % 16 in (0, 8):
                # 7 -> 8 and 15 -> 0 ripple through every bit: the outputs pass through wrong counts.
                assert len({e['t'] for e in outs}) == 4, ('ripple outputs change one after another', k, outs)


def circuit_doc(gates: list[tuple[str, str]], wires: list[tuple[str, str]], inputs: list[str],
                outputs: list[str], extra: list[dict] = ()) -> dict:
    pack = load_pack()
    comps = [{'id': f'in-{n}', 'symbolId': 'act', 'x': 0, 'y': 0, 'config': {'logic': {'kind': 'input', 'name': n}}}
             for n in inputs]
    comps += [{'id': f'out-{n}', 'symbolId': 'observe', 'x': 0, 'y': 0, 'config': {'logic': {'kind': 'output', 'name': n}}}
              for n in outputs]
    for gid, kind in gates:
        pins = pack[kind]['inputs'] + pack[kind]['outputs'] if kind in pack else ['a', 'b', 'q']
        comps.append({'id': gid, 'symbolId': 'gate', 'x': 0, 'y': 0,
                      'config': {'logic': {'gate': kind}, 'attachmentPoints': [{'id': p, 'side': 'left'} for p in pins]}})
    comps += list(extra)
    ws = []
    for i, (a, b) in enumerate(wires):
        (ac, _, ap), (bc, _, bp) = a.partition('.'), b.partition('.')
        ws.append({'id': f'w{i}', 'a': ac, 'aSide': ap or 'out', 'b': bc, 'bSide': bp or 'in'})
    return {'schema': 'soveraeign.schematic/document@0.1', 'id': 't', 'revision': 0, 'meta': {},
            'components': comps, 'wires': ws, 'references': []}


def check_wiring_refusals() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 't.sov'

        def attempt(doc: dict, code: str) -> None:
            path.write_text(json.dumps(doc))
            refused(lambda: Circuit(path), code)

        attempt(circuit_doc([('g1', 'not'), ('g2', 'not')],
                            [('in-A', 'g1.a'), ('in-A', 'g2.a'), ('g1.q', 'out-Q'), ('g2.q', 'out-Q')], ['A'], ['Q']),
                'MULTIPLE_DRIVERS')
        attempt(circuit_doc([('g', 'and')], [('in-A', 'g.a'), ('g.q', 'out-Q')], ['A'], ['Q']), 'UNDRIVEN')
        attempt(circuit_doc([('g', 'maybe')], [('in-A', 'g.a'), ('g.q', 'out-Q')], ['A'], ['Q']), 'UNKNOWN_GATE')
        doc = circuit_doc([('g', 'and')], [('in-A', 'g.a'), ('in-A', 'g.b'), ('g.q', 'out-Q')], ['A'], ['Q'])
        doc['components'][-1]['config']['attachmentPoints'].pop()           # no q
        attempt(doc, 'MISSING_PIN')
        loop = circuit_doc([], [], ['A'], ['Q'], extra=[{'id': 'me', 'symbolId': 'act', 'x': 0, 'y': 0, 'config': {
            'logic': {'composite': 't.sov'}, 'attachmentPoints': [{'id': 'A', 'side': 'left'}, {'id': 'Q', 'side': 'right'}]}}])
        attempt(loop, 'COMPOSITE_CYCLE')
        # A Point is a junction: fanout through it is one net, and a fault through it is still found.
        through = circuit_doc([('g', 'and')], [('in-A', 'j.out'), ('j.out', 'g.a'), ('j.out', 'g.b'), ('g.q', 'out-Q')],
                              ['A'], ['Q'], extra=[{'id': 'j', 'symbolId': 'point', 'x': 0, 'y': 0}])
        path.write_text(json.dumps(through))
        c = Circuit(path)
        assert c.apply({'A': 1})['outputs']['Q'] == 1 and c.apply({'A': 0})['outputs']['Q'] == 0


def check_examples() -> None:
    subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build_logic_examples.py'), '--check'], check=True)
    if shutil.which('node'):
        subprocess.run(['node', str(ROOT / 'scripts' / 'validate_sov.mjs'), *map(str, sorted(DIR.glob('*.sov')))],
                       check=True, stdout=subprocess.DEVNULL)
        from sov_fingerprint import document_fingerprint
        doc = json.loads((DIR / 'half-adder.sov').read_text())
        before = document_fingerprint(doc)
        next(c for c in doc['components'] if c['id'] == 'x')['config']['logic']['gate'] = 'or'
        assert document_fingerprint(doc) != before, 'changing a gate must change what the document means'


def main() -> int:
    check_pack()
    check_gallery()
    check_composites_equal_primitives()
    check_arithmetic()
    check_carry_ripple_is_linear()
    check_feedback()
    check_sequential_gates()
    check_threshold_and_levels()
    check_level_examples()
    check_sequential_composites()
    check_wiring_refusals()
    check_examples()
    print('logic_sov QA PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
