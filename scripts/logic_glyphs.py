"""Gate glyphs for the logic pack, written into packs/logic/gates.json.

The rule (VISUAL-LANGUAGE.md, agreed in the bake-off):
  - the eight classic gates (AND, OR, XOR, NOT, NAND, NOR, XNOR, BUFFER) get their distinctive
    ANSI/IEEE 91 shape;
  - everything else, anything with state, a threshold or more than two inputs, gets an IEC 60617
    rectangle with a qualifier;
  - every gate also carries its rectangle as `glyph_small`, for when it is drawn below about
    40 px, where distinctive shapes stop being distinguishable.

Each glyph is SVG markup on the editor's 96 x 64 symbol grid, stroked in the current color, and
uses only the tags and attributes the editor's custom-graphic sanitizer admits
(src/55-render.js), so a Component can carry it as `presentation.graphic.svg` with no renderer
change.

    python scripts/logic_glyphs.py            # write the glyphs into the pack
    python scripts/logic_glyphs.py --check    # exit 1 if the pack's glyphs are stale
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'packs' / 'logic' / 'gates.json'
CLASSIC = ('and', 'or', 'xor', 'not', 'buffer', 'nand', 'nor', 'xnor')


def stub(y: float, x0: float = 6, x1: float = 28) -> str:
    return f'M{x0} {y}H{x1}'


def paths(*ds: str) -> str:
    return ''.join(f'<path d="{d}"/>' for d in ds)


def label(x: float, y: float, s: str, size: int = 14) -> str:
    # Escaped: the markup is parsed as XML by the editor, and a bare '&' (IEC AND) would make
    # the whole glyph unparseable and fall back to the generic symbol.
    s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return (f'<text x="{x}" y="{y}" text-anchor="middle" font-size="{size}" font-weight="600" '
            f'fill="currentColor" stroke="none">{s}</text>')


def bubble(x: float, y: float = 32) -> str:
    return f'<circle cx="{x}" cy="{y}" r="4"/>'


AND = 'M28 12H48A20 20 0 0 1 48 52H28Z'
OR = 'M26 12Q40 32 26 52Q56 52 70 32Q56 12 26 12Z'
XOR = 'M30 12Q44 32 30 52Q60 52 72 32Q60 12 30 12Z'
XOR_BACK = 'M22 12Q36 32 22 52'
NAND = 'M28 12H46A20 20 0 0 1 46 52H28Z'
NOR = 'M26 12Q40 32 26 52Q54 52 66 32Q54 12 26 12Z'
XNOR = 'M30 12Q44 32 30 52Q58 52 68 32Q58 12 30 12Z'

DISTINCTIVE = {
    'and': paths(stub(22), stub(42), AND, 'M68 32H90'),
    'or': paths(stub(22, 6, 33), stub(42, 6, 33), OR, 'M70 32H90'),
    'xor': paths(stub(22, 6, 31), stub(42, 6, 31), XOR, XOR_BACK, 'M72 32H90'),
    'not': paths(stub(32), 'M28 14L62 32L28 50Z', 'M70 32H90') + bubble(66),
    'buffer': paths(stub(32), 'M28 14L66 32L28 50Z', 'M66 32H90'),
    'nand': paths(stub(22), stub(42), NAND, 'M74 32H90') + bubble(70),
    'nor': paths(stub(22, 6, 33), stub(42, 6, 33), NOR, 'M74 32H90') + bubble(70),
    'xnor': paths(stub(22, 6, 31), stub(42, 6, 31), XNOR, XOR_BACK, 'M76 32H90') + bubble(72),
}


def rect(ins: list[float], outs: list[float], q: str = '', size: int = 14, clock: float | None = None,
         pins: list[tuple[str, float, float]] = (), loop: bool = False, out_bubble: bool = False) -> str:
    """An IEC rectangle: input stubs, a frame, output stubs, a qualifier, pin letters."""
    body = paths(*(stub(y, 6, 30) for y in ins), 'M30 8H66V56H30Z',
                 *(f'M{70 if out_bubble else 66} {y}H90' for y in outs))
    if clock is not None:
        body += paths(f'M30 {clock - 4}L38 {clock}L30 {clock + 4}')
    if out_bubble:
        body += bubble(70, outs[0])
    if q:
        body += label(48, 37, q, size)
    for s, x, y in pins:
        body += label(x, y, s, 9)
    if loop:
        body += paths('M38 38H50V26H58', 'M42 38V26H54')
    return body


def iec(name: str, gate: dict) -> str:
    n_in, n_out = len(gate['inputs']), len(gate['outputs'])
    ins = {0: [], 1: [32], 2: [22, 42], 3: [18, 32, 46]}[n_in]
    outs = {1: [32], 2: [22, 42]}[n_out]
    table = {
        'and': ('&', {}), 'or': ('≥1', {}), 'xor': ('=1', {}), 'buffer': ('1', {}), 'not': ('1', {'out_bubble': True}),
        'nand': ('&', {'out_bubble': True}), 'nor': ('≥1', {'out_bubble': True}), 'xnor': ('=1', {'out_bubble': True}),
        'false': ('0', {}), 'true': ('1', {}),
        'imply': ('⇒', {}), 'nimply': ('⇏', {}), 'cimply': ('⇐', {}), 'ncimply': ('⇍', {}),
        'majority': ('≥2', {}), 'mux': ('MUX', {'size': 11}), 'half-adder': ('Σ', {}),
        'threshold': ('Σ≥θ', {'size': 11}), 'compare': ('≥θ', {}), 'c-element': ('C', {}),
        'schmitt': ('', {'loop': True}),
        'dff': ('', {'clock': 42, 'pins': [('D', 36, 25), ('Q', 58, 25), ('Q̄', 58, 45)]}),
        'tff': ('', {'clock': 42, 'pins': [('T', 36, 25), ('Q', 58, 25), ('Q̄', 58, 45)]}),
        'jkff': ('', {'clock': 46, 'pins': [('J', 36, 21), ('K', 36, 35), ('Q', 58, 25), ('Q̄', 58, 45)]}),
        'sr-latch': ('', {'pins': [('S', 36, 25), ('R', 36, 45), ('Q', 58, 25), ('Q̄', 58, 45)]}),
        'd-latch': ('', {'pins': [('D', 36, 25), ('EN', 38, 45), ('Q', 58, 25), ('Q̄', 58, 45)]}),
    }
    if name not in table:
        raise SystemExit(f'no rectangle qualifier for gate {name!r}; add one to logic_glyphs.py')
    q, opts = table[name]
    return rect(ins, outs, q, **opts)


def glyphs(pack: dict) -> dict[str, dict[str, str]]:
    out = {}
    for name, gate in sorted(pack['gates'].items()):
        small = iec(name, gate)
        out[name] = {'glyph': DISTINCTIVE.get(name, small), 'glyph_small': small,
                     'glyph_family': 'distinctive' if name in DISTINCTIVE else 'rectangle'}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    pack = json.loads(PACK.read_text(encoding='utf-8'))
    made = glyphs(pack)
    stale = [n for n, g in made.items() if any(pack['gates'][n].get(k) != v for k, v in g.items())]
    if args.check:
        for n in stale:
            print(f'stale glyph {n}')
        return 1 if stale else 0
    for n, g in made.items():
        pack['gates'][n].update(g)
    PACK.write_text(json.dumps(pack, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print(f'wrote glyphs for {len(made)} gates ({sum(g["glyph_family"] == "distinctive" for g in made.values())} distinctive)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
