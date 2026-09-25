"""Write the logic examples in examples/logic/ from a short description of each circuit.

Every file is an ordinary `.sov` in the compact authored form (see skills/author-offline).
Gates are `gate` Components with one attachment point per pin; composites are Components
whose logic names another document here. Running this again writes the same bytes.

    python scripts/build_logic_examples.py            # write examples/logic/*.sov
    python scripts/build_logic_examples.py --check    # exit 1 if any file differs from what it would write
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'examples' / 'logic'
PACK = json.loads((ROOT / 'packs' / 'logic' / 'gates.json').read_text(encoding='utf-8'))['gates']


class Doc:
    """A circuit being described: inputs on the left, parts in columns, outputs on the right."""

    def __init__(self, ident: str, title: str):
        self.ident, self.title = ident, title
        self.components: list[dict] = []
        self.wires: list[dict] = []
        self.pins: dict[str, tuple[list[str], list[str]]] = {}
        self.column: dict[str, int] = {}
        self.rows: dict[int, int] = {}

    def _place(self, col: int) -> tuple[int, int]:
        row = self.rows.get(col, 0)
        self.rows[col] = row + 1
        return 120 + col * 220, 100 + row * 130

    def input(self, name: str) -> str:
        x, y = self._place(0)
        cid = f'in-{name}'
        self.components.append({'id': cid, 'symbolId': 'act', 'x': x, 'y': y,
                                'config': {'label': name, 'signalMode': 'source', 'logic': {'kind': 'input', 'name': name}}})
        self.pins[cid] = ([], ['out'])
        return cid

    def output(self, name: str, col: int) -> str:
        x, y = self._place(col)
        cid = f'out-{name}'
        self.components.append({'id': cid, 'symbolId': 'observe', 'x': x, 'y': y,
                                'config': {'label': name, 'logic': {'kind': 'output', 'name': name}}})
        self.pins[cid] = (['in'], [])
        return cid

    def _part(self, cid: str, col: int, label: str, logic: dict, ins: list[str], outs: list[str],
              symbol: str = 'gate') -> str:
        x, y = self._place(col)
        points = [{'id': p, 'side': 'left', 't': round((i + 1) / (len(ins) + 1), 4), 'defaultFlow': 'in'}
                  for i, p in enumerate(ins)]
        points += [{'id': p, 'side': 'right', 't': round((i + 1) / (len(outs) + 1), 4), 'defaultFlow': 'out'}
                   for i, p in enumerate(outs)]
        self.components.append({'id': cid, 'symbolId': symbol, 'x': x, 'y': y,
                                'config': {'label': label, 'logic': logic, 'attachmentPoints': points}})
        self.pins[cid] = (ins, outs)
        return cid

    def gate(self, cid: str, kind: str, col: int) -> str:
        g = PACK[kind]
        return self._part(cid, col, kind.upper(), {'gate': kind}, g['inputs'], g['outputs'])

    def part(self, cid: str, composite: str, col: int, label: str) -> str:
        ins, outs = composite_pins(composite)
        return self._part(cid, col, label, {'composite': composite}, ins, outs, symbol='act')

    def wire(self, src: str, dst: str) -> None:
        """'cid' or 'cid.pin' for each end; an input's pin is out, an output's is in."""
        a, _, a_pin = src.partition('.')
        b, _, b_pin = dst.partition('.')
        a_pin = a_pin or self.pins[a][1][0]
        b_pin = b_pin or self.pins[b][0][0]
        self.wires.append({'id': f'w{len(self.wires) + 1}', 'a': a, 'aSide': a_pin, 'b': b, 'bSide': b_pin})

    def write(self, name: str) -> tuple[Path, str]:
        doc = {'schema': 'soveraeign.schematic/document@0.1', 'id': self.ident, 'revision': 0,
               'meta': {'title': self.title}, 'components': self.components, 'wires': self.wires, 'references': []}
        return OUT / name, json.dumps(doc, indent=2) + '\n'


_BUILT: dict[str, str] = {}


def composite_pins(name: str) -> tuple[list[str], list[str]]:
    doc = json.loads(_BUILT[name])
    ins = [c['config']['logic']['name'] for c in doc['components'] if c['config'].get('logic', {}).get('kind') == 'input']
    outs = [c['config']['logic']['name'] for c in doc['components'] if c['config'].get('logic', {}).get('kind') == 'output']
    return ins, outs


def gallery() -> Doc:
    d = Doc('logic-gates', 'Every gate in the pack, side by side, on shared inputs A, B, C')
    for n in 'ABC':
        d.input(n)
    pins = {'a': 'in-A', 'b': 'in-B', 'c': 'in-C', 's': 'in-C'}
    for i, kind in enumerate(sorted(PACK)):
        g = PACK[kind]
        cid = d.gate(kind, kind, 1 + i // 6)
        for p in g['inputs']:
            d.wire(pins[p], f'{cid}.{p}')
        for p in g['outputs']:
            out = d.output(kind if len(g['outputs']) == 1 else f'{kind}-{p}', 4 + i // 9)
            d.wire(f'{cid}.{p}', out)
    return d


def half_adder() -> Doc:
    d = Doc('logic-half-adder', 'Half adder: S = A xor B, C = A and B')
    a, b = d.input('A'), d.input('B')
    x, n = d.gate('x', 'xor', 1), d.gate('n', 'and', 1)
    for g in (x, n):
        d.wire(a, f'{g}.a')
        d.wire(b, f'{g}.b')
    d.wire(f'{x}.q', d.output('S', 2))
    d.wire(f'{n}.q', d.output('C', 2))
    return d


def full_adder() -> Doc:
    d = Doc('logic-full-adder', 'Full adder: two half adders and an OR')
    a, b, cin = d.input('A'), d.input('B'), d.input('Cin')
    h1, h2 = d.part('ha1', 'half-adder.sov', 1, 'HALF ADDER'), d.part('ha2', 'half-adder.sov', 2, 'HALF ADDER')
    o = d.gate('carry', 'or', 3)
    d.wire(a, f'{h1}.A')
    d.wire(b, f'{h1}.B')
    d.wire(f'{h1}.S', f'{h2}.A')
    d.wire(cin, f'{h2}.B')
    d.wire(f'{h1}.C', f'{o}.a')
    d.wire(f'{h2}.C', f'{o}.b')
    d.wire(f'{h2}.S', d.output('S', 4))
    d.wire(f'{o}.q', d.output('Cout', 4))
    return d


def ripple(width: int, part: str, part_width: int, ident: str, title: str) -> Doc:
    d = Doc(ident, title)
    a = [d.input(f'A{i}') for i in range(width)]
    b = [d.input(f'B{i}') for i in range(width)]
    carry = d.input('Cin')
    for k in range(width // part_width):
        cid = d.part(f'{"fa" if part_width == 1 else "add"}{k}', part, 1 + k, part.split('.')[0].upper())
        for j in range(part_width):
            i = k * part_width + j
            suffix = '' if part_width == 1 else str(j)
            d.wire(a[i], f'{cid}.A{suffix}')
            d.wire(b[i], f'{cid}.B{suffix}')
            d.wire(f'{cid}.S{suffix}', d.output(f'S{i}', 2 + width // part_width))
        d.wire(carry if k == 0 else f'{prev}.Cout', f'{cid}.Cin')
        prev = cid
    d.wire(f'{prev}.Cout', d.output('Cout', 2 + width // part_width))
    return d


def add_sub4() -> Doc:
    d = Doc('logic-add-sub4', '4-bit adder/subtractor: SUB=1 inverts B and carries in 1, so S = A - B (mod 16)')
    a = [d.input(f'A{i}') for i in range(4)]
    b = [d.input(f'B{i}') for i in range(4)]
    sub = d.input('SUB')
    add = d.part('add', 'adder4.sov', 2, 'ADDER4')
    for i in range(4):
        x = d.gate(f'inv{i}', 'xor', 1)
        d.wire(b[i], f'{x}.a')
        d.wire(sub, f'{x}.b')
        d.wire(a[i], f'{add}.A{i}')
        d.wire(f'{x}.q', f'{add}.B{i}')
        d.wire(f'{add}.S{i}', d.output(f'S{i}', 3))
    d.wire(sub, f'{add}.Cin')
    d.wire(f'{add}.Cout', d.output('Cout', 3))
    return d


def xor_from_nand() -> Doc:
    d = Doc('logic-xor-nand', 'XOR from four NAND gates: NAND is universal')
    a, b = d.input('A'), d.input('B')
    m = d.gate('m', 'nand', 1)
    d.wire(a, f'{m}.a')
    d.wire(b, f'{m}.b')
    p, q = d.gate('p', 'nand', 2), d.gate('q', 'nand', 2)
    d.wire(a, f'{p}.a')
    d.wire(f'{m}.q', f'{p}.b')
    d.wire(f'{m}.q', f'{q}.a')
    d.wire(b, f'{q}.b')
    r = d.gate('r', 'nand', 3)
    d.wire(f'{p}.q', f'{r}.a')
    d.wire(f'{q}.q', f'{r}.b')
    d.wire(f'{r}.q', d.output('Q', 4))
    return d


def mux_from_gates() -> Doc:
    d = Doc('logic-mux2', 'Two-way multiplexer from NOT, AND and OR: Q = A when S is 0, B when S is 1')
    s, a, b = d.input('S'), d.input('A'), d.input('B')
    n = d.gate('ns', 'not', 1)
    d.wire(s, f'{n}.a')
    x, y = d.gate('pa', 'and', 2), d.gate('pb', 'and', 2)
    d.wire(a, f'{x}.a')
    d.wire(f'{n}.q', f'{x}.b')
    d.wire(b, f'{y}.a')
    d.wire(s, f'{y}.b')
    o = d.gate('o', 'or', 3)
    d.wire(f'{x}.q', f'{o}.a')
    d.wire(f'{y}.q', f'{o}.b')
    d.wire(f'{o}.q', d.output('Q', 4))
    return d


def sr_latch() -> Doc:
    d = Doc('logic-sr-latch', 'SR latch from two cross-coupled NOR gates: memory from feedback')
    s, r = d.input('S'), d.input('R')
    top, bottom = d.gate('q', 'nor', 1), d.gate('qn', 'nor', 1)
    d.wire(r, f'{top}.a')
    d.wire(f'{bottom}.q', f'{top}.b')
    d.wire(s, f'{bottom}.a')
    d.wire(f'{top}.q', f'{bottom}.b')
    d.wire(f'{top}.q', d.output('Q', 2))
    d.wire(f'{bottom}.q', d.output('QN', 2))
    return d


def build() -> dict[Path, str]:
    """Composites before the documents that use them."""
    plan = [
        ('gates.sov', gallery),
        ('half-adder.sov', half_adder),
        ('full-adder.sov', full_adder),
        ('adder4.sov', lambda: ripple(4, 'full-adder.sov', 1, 'logic-adder4', '4-bit ripple-carry adder: four full adders')),
        ('adder8.sov', lambda: ripple(8, 'adder4.sov', 4, 'logic-adder8', '8-bit adder: two 4-bit adders, carry rippling between them')),
        ('add-sub4.sov', add_sub4),
        ('xor-nand.sov', xor_from_nand),
        ('mux2.sov', mux_from_gates),
        ('sr-latch.sov', sr_latch),
    ]
    files = {}
    for name, make in plan:
        path, text = make().write(name)
        _BUILT[name] = text
        files[path] = text
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    files = build()
    stale = [p for p, text in files.items() if not p.exists() or p.read_text(encoding='utf-8') != text]
    if args.check:
        for p in stale:
            print(f'stale {p.relative_to(ROOT)}')
        return 1 if stale else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for p, text in files.items():
        p.write_text(text, encoding='utf-8', newline='\n')
    print(f'wrote {len(files)} files to {OUT.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
