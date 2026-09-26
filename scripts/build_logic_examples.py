"""Write the logic examples in examples/logic/ as state space documents.

State space (STATE-SPACE.md) runs them: a source is a Point marked `signalMode: source` (a run
registers its inputs there), each gate is a Component bound to a definition by
`config.definition` (`logic.and@1`, from data/core.logic.pack.json and
data/logic.gates.pack.json) with the ports its contract generates, each Wire carries forward
with a declared delay of 1, and each output is a Point. Gates draw with their glyph from
data/logic.glyphs.json.

Files are written in the saved form the data core produces (scripts/normalize_sov.mjs), so
opening and saving one in the editor changes nothing. Beside the 4-bit adder sits a golden
trace, adder4.carry.sovtrace: 7 + 0, then B0 rises (7 + 1), and the carry ripples.

Only combinational circuits are here. Registers, counters, latches, the completion gate and
the level examples wait for the `threshold` and `transition` patterns (slices 2 and 5).

    python scripts/build_logic_examples.py            # write examples/logic/
    python scripts/build_logic_examples.py --check    # exit 1 if any file differs, or a stray one exists
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'examples' / 'logic'
DEFS = {f"{d['id']}@{d['version']}": d for p in ('core.logic.pack.json', 'logic.gates.pack.json')
        for d in json.loads((ROOT / 'data' / p).read_text(encoding='utf-8'))['definitions']}
GLYPHS = json.loads((ROOT / 'data' / 'logic.glyphs.json').read_text(encoding='utf-8'))['glyphs']


class Doc:
    """A circuit being described: sources on the left, devices in columns, outputs on the right."""

    def __init__(self, ident: str, title: str):
        self.ident, self.title = ident, title
        self.components: list[dict] = []
        self.wires: list[dict] = []
        self.rows: dict[int, int] = {}

    def _place(self, col: int) -> tuple[int, int]:
        row = self.rows.get(col, 0)
        self.rows[col] = row + 1
        return 120 + col * 220, 100 + row * 130

    def source(self, name: str) -> str:
        x, y = self._place(0)
        self.components.append({'id': name, 'symbolId': 'point', 'x': x, 'y': y,
                                'config': {'label': name, 'signalMode': 'source'}})
        return name

    def output(self, name: str, col: int) -> str:
        x, y = self._place(col)
        self.components.append({'id': name, 'symbolId': 'point', 'x': x, 'y': y, 'config': {'label': name}})
        return name

    def device(self, cid: str, ref: str, col: int) -> str:
        d = DEFS[ref]
        ins, outs = d['parameters']['inputs'], d['parameters']['outputs']
        # The contract's ports (STATE-SPACE.md "Ports"): inputs spread on the left, outputs on the right.
        port = lambda side, flow, n: lambda i, p: {'id': p, 'side': side, 't': (i + 1) / (n + 1), 'flow': flow,  # noqa: E731
                                                  'channels': [{'id': 'main'}]}
        points = [port('left', 'in', len(ins))(i, p) for i, p in enumerate(ins)]
        points += [port('right', 'out', len(outs))(i, p) for i, p in enumerate(outs)]
        g = GLYPHS[ref]
        graphic = {'kind': 'custom', 'svg': g['glyph'], **({'svgSmall': g['glyphSmall']} if g['glyphSmall'] != g['glyph'] else {})}
        x, y = self._place(col)
        self.components.append({'id': cid, 'symbolId': 'gate', 'x': x, 'y': y, 'config': {
            'label': d['projection']['label'], 'definition': ref, 'attachmentDefaults': 'none',
            'attachmentPoints': points, 'presentation': {'graphic': graphic}}})
        return cid

    def wire(self, src: str, dst: str) -> None:
        """'id' for a Point (its port is self), 'id.port' for a device."""
        a, _, a_port = src.partition('.')
        b, _, b_port = dst.partition('.')
        self.wires.append({'id': f'w{len(self.wires) + 1}', 'a': a, 'aSide': a_port or 'self', 'b': b,
                           'bSide': b_port or 'self', 'config': {'direction': 'forward', 'delay': 1}})

    def doc(self) -> dict:
        return {'schema': 'soveraeign.schematic/document@0.1', 'id': self.ident, 'revision': 0,
                'meta': {'title': self.title}, 'components': self.components, 'wires': self.wires, 'references': []}


def gallery() -> Doc:
    d = Doc('logic-gates', 'Every logic definition, side by side, on shared sources A, B, C')
    for n in 'ABC':
        d.source(n)
    feed = {'a': 'A', 'b': 'B', 'c': 'C', 's': 'C', 'cin': 'C'}
    for i, ref in enumerate(sorted(DEFS)):
        p = DEFS[ref]['parameters']
        name = ref.split('.', 1)[1].split('@')[0]
        cid = d.device(f'g-{name}', ref, 1 + i // 6)
        for port in p['inputs']:
            d.wire(feed[port], f'{cid}.{port}')
        for port in p['outputs']:
            d.wire(f'{cid}.{port}', d.output(name.upper() if len(p['outputs']) == 1 else f'{name.upper()}_{port.upper()}', 4 + i // 8))
    return d


def half_adder() -> Doc:
    d = Doc('logic-half-adder', 'Half adder: S = A xor B, C = A and B')
    a, b = d.source('A'), d.source('B')
    x, n = d.device('x', 'logic.xor@1', 1), d.device('n', 'logic.and@1', 1)
    for g in (x, n):
        d.wire(a, f'{g}.a')
        d.wire(b, f'{g}.b')
    d.wire(f'{x}.q', d.output('S', 2))
    d.wire(f'{n}.q', d.output('C', 2))
    return d


def full_adder() -> Doc:
    d = Doc('logic-full-adder', 'Full adder: two half adders and an OR')
    a, b, cin = d.source('A'), d.source('B'), d.source('Cin')
    h1, h2 = d.device('ha1', 'logic.half_adder@1', 1), d.device('ha2', 'logic.half_adder@1', 2)
    o = d.device('carry', 'logic.or@1', 3)
    d.wire(a, f'{h1}.a')
    d.wire(b, f'{h1}.b')
    d.wire(f'{h1}.s', f'{h2}.a')
    d.wire(cin, f'{h2}.b')
    d.wire(f'{h1}.c', f'{o}.a')
    d.wire(f'{h2}.c', f'{o}.b')
    d.wire(f'{h2}.s', d.output('S', 4))
    d.wire(f'{o}.q', d.output('Cout', 4))
    return d


def ripple(width: int, ident: str, title: str) -> Doc:
    d = Doc(ident, title)
    a = [d.source(f'A{i}') for i in range(width)]
    b = [d.source(f'B{i}') for i in range(width)]
    carry = d.source('Cin')
    for i in range(width):
        fa = d.device(f'fa{i}', 'logic.full_adder@1', 1 + i)
        d.wire(a[i], f'{fa}.a')
        d.wire(b[i], f'{fa}.b')
        d.wire(carry, f'{fa}.cin')
        d.wire(f'{fa}.s', d.output(f'S{i}', 2 + width))
        carry = f'{fa}.cout'
    d.wire(carry, d.output('Cout', 2 + width))
    return d


def add_sub4() -> Doc:
    d = Doc('logic-add-sub4', '4-bit adder/subtractor: SUB=1 inverts B and carries in 1, so S = A - B (mod 16)')
    a = [d.source(f'A{i}') for i in range(4)]
    b = [d.source(f'B{i}') for i in range(4)]
    sub = d.source('SUB')
    carry = sub
    for i in range(4):
        x = d.device(f'inv{i}', 'logic.xor@1', 1)
        d.wire(b[i], f'{x}.a')
        d.wire(sub, f'{x}.b')
        fa = d.device(f'fa{i}', 'logic.full_adder@1', 2 + i)
        d.wire(a[i], f'{fa}.a')
        d.wire(f'{x}.q', f'{fa}.b')
        d.wire(carry, f'{fa}.cin')
        d.wire(f'{fa}.s', d.output(f'S{i}', 6))
        carry = f'{fa}.cout'
    d.wire(carry, d.output('Cout', 6))
    return d


def xor_from_nand() -> Doc:
    d = Doc('logic-xor-nand', 'XOR from four NAND gates: NAND is universal')
    a, b = d.source('A'), d.source('B')
    m = d.device('m', 'logic.nand@1', 1)
    d.wire(a, f'{m}.a')
    d.wire(b, f'{m}.b')
    p, q = d.device('p', 'logic.nand@1', 2), d.device('q', 'logic.nand@1', 2)
    d.wire(a, f'{p}.a')
    d.wire(f'{m}.q', f'{p}.b')
    d.wire(f'{m}.q', f'{q}.a')
    d.wire(b, f'{q}.b')
    r = d.device('r', 'logic.nand@1', 3)
    d.wire(f'{p}.q', f'{r}.a')
    d.wire(f'{q}.q', f'{r}.b')
    d.wire(f'{r}.q', d.output('Q', 4))
    return d


def mux_from_gates() -> Doc:
    d = Doc('logic-mux2', 'Two-way multiplexer from NOT, AND and OR: Q = A when S is 0, B when S is 1')
    s, a, b = d.source('S'), d.source('A'), d.source('B')
    n = d.device('ns', 'logic.not@1', 1)
    d.wire(s, f'{n}.a')
    x, y = d.device('pa', 'logic.and@1', 2), d.device('pb', 'logic.and@1', 2)
    d.wire(a, f'{x}.a')
    d.wire(f'{n}.q', f'{x}.b')
    d.wire(b, f'{y}.a')
    d.wire(s, f'{y}.b')
    o = d.device('o', 'logic.or@1', 3)
    d.wire(f'{x}.q', f'{o}.a')
    d.wire(f'{y}.q', f'{o}.b')
    d.wire(f'{o}.q', d.output('Q', 4))
    return d


PLAN = [
    ('gates.sov', gallery),
    ('half-adder.sov', half_adder),
    ('full-adder.sov', full_adder),
    ('adder4.sov', lambda: ripple(4, 'logic-adder4', '4-bit ripple-carry adder: four full adders')),
    ('adder8.sov', lambda: ripple(8, 'logic-adder8', '8-bit ripple-carry adder: eight full adders')),
    ('add-sub4.sov', add_sub4),
    ('xor-nand.sov', xor_from_nand),
    ('mux2.sov', mux_from_gates),
]
# 7 + 0, then B0 rises: 7 + 1 = 8, and the carry ripples through every stage.
CARRY_INPUTS = ([{'entity': f'A{i}', 'value': i < 3, 'at': 0} for i in range(4)] +
                [{'entity': f'B{i}', 'value': False, 'at': 0} for i in range(4)] +
                [{'entity': 'Cin', 'value': False, 'at': 0}, {'entity': 'B0', 'value': True, 'at': 20}])


def build() -> dict[Path, str]:
    docs = [make().doc() for _, make in PLAN]
    saved = json.loads(subprocess.run(['node', str(ROOT / 'scripts' / 'normalize_sov.mjs')], input=json.dumps(docs),
                                      capture_output=True, text=True, check=True).stdout)
    for doc in saved:
        doc.get('meta', {}).pop('updatedAt', None)   # a save stamps the time; an example has none
    files = {OUT / name: json.dumps(doc, indent=2) + '\n' for (name, _), doc in zip(PLAN, saved)}
    # The golden trace runs the file as written, so it is built from the saved text.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / 'adder4.sov'
        src.write_text(files[OUT / 'adder4.sov'], encoding='utf-8')
        out = json.loads(subprocess.run(['node', str(ROOT / 'scripts' / 'run_state.mjs')],
                                        input=json.dumps([{'path': str(src), 'inputs': CARRY_INPUTS}]),
                                        capture_output=True, text=True, check=True).stdout)[0]
    if not out['ok']:
        raise SystemExit(f"adder4 refused: {out['code']}: {out['message']}")
    files[OUT / 'adder4.carry.sovtrace'] = json.dumps(out['trace'], sort_keys=True, separators=(',', ':')) + '\n'
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    files = build()
    stale = [p for p, text in files.items() if not p.exists() or p.read_text(encoding='utf-8') != text]
    stray = [p for p in OUT.glob('*') if p.is_file() and p not in files]
    if args.check:
        for p in stale:
            print(f'stale {p.relative_to(ROOT)}')
        for p in stray:
            print(f'stray {p.relative_to(ROOT)}')
        return 1 if stale or stray else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for p in stray:
        p.unlink()
    for p, text in files.items():
        p.write_text(text, encoding='utf-8', newline='\n')
    print(f'wrote {len(files)} files to {OUT.relative_to(ROOT)}' + (f', removed {len(stray)}' if stray else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
