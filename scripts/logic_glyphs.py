"""Gate glyphs for the logic definitions, written to data/logic.glyphs.json.

Glyphs are presentation, keyed by the definition they draw (`logic.and@1`), for every
definition in data/core.logic.pack.json and data/logic.gates.pack.json. The rule
(VISUAL-LANGUAGE.md, agreed in the bake-off):
  - the eight classic gates (AND, OR, XOR, NOT, NAND, NOR, XNOR, BUFFER) get their distinctive
    ANSI/IEEE 91 shape;
  - everything else gets an IEC 60617 rectangle with a qualifier;
  - every gate also carries its rectangle as `glyphSmall`, for when it is drawn below about
    40 px, where distinctive shapes stop being distinguishable.

Each glyph is SVG markup on the editor's 96 x 64 symbol grid, stroked in the current color, and
uses only the tags and attributes the editor's custom-graphic sanitizer admits
(src/55-render.js), so a Component carries it as `presentation.graphic.svg` with no renderer
change. Glyphs for gates with memory or a threshold return with their patterns.

    python scripts/logic_glyphs.py            # write data/logic.glyphs.json
    python scripts/logic_glyphs.py --check    # exit 1 if it is stale
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKS = [ROOT / 'data' / 'core.logic.pack.json', ROOT / 'data' / 'logic.gates.pack.json']
TARGET = ROOT / 'data' / 'logic.glyphs.json'
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


def rect(ins: list[float], outs: list[float], q: str = '', size: int = 14, out_bubble: bool = False) -> str:
    """An IEC rectangle: input stubs, a frame, output stubs, a qualifier."""
    body = paths(*(stub(y, 6, 30) for y in ins), 'M30 8H66V56H30Z',
                 *(f'M{70 if out_bubble else 66} {y}H90' for y in outs))
    if out_bubble:
        body += bubble(70, outs[0])
    if q:
        body += label(48, 37, q, size)
    return body

QUALIFIER = {
    'and': ('&', {}), 'or': ('≥1', {}), 'xor': ('=1', {}), 'buffer': ('1', {}), 'not': ('1', {'out_bubble': True}),
    'nand': ('&', {'out_bubble': True}), 'nor': ('≥1', {'out_bubble': True}), 'xnor': ('=1', {'out_bubble': True}),
    'imply': ('⇒', {}), 'nimply': ('⇏', {}), 'cimply': ('⇐', {}), 'ncimply': ('⇍', {}),
    'majority': ('≥2', {}), 'mux': ('MUX', {'size': 11}), 'half_adder': ('HA', {}), 'full_adder': ('FA', {}),
}


def iec(name: str, n_in: int, n_out: int) -> str:
    ins = {1: [32], 2: [22, 42], 3: [18, 32, 46]}[n_in]
    outs = {1: [32], 2: [22, 42]}[n_out]
    if name not in QUALIFIER:
        raise SystemExit(f'no rectangle qualifier for {name!r}; add one to logic_glyphs.py')
    q, opts = QUALIFIER[name]
    return rect(ins, outs, q, **opts)


def definitions() -> list[dict]:
    return [d for p in PACKS for d in json.loads(p.read_text(encoding='utf-8'))['definitions']]


def glyphs() -> dict[str, dict[str, str]]:
    out = {}
    for d in sorted(definitions(), key=lambda d: d['id']):
        name = d['id'].split('.', 1)[1]
        small = iec(name, len(d['parameters']['inputs']), len(d['parameters']['outputs']))
        out[f"{d['id']}@{d['version']}"] = {'glyph': DISTINCTIVE.get(name, small), 'glyphSmall': small,
                                             'family': 'distinctive' if name in DISTINCTIVE else 'rectangle'}
    return out


def text() -> str:
    return json.dumps({'id': 'logic.glyphs', 'note': 'Presentation for the logic definitions, keyed by definition. Written by scripts/logic_glyphs.py.',
                       'glyphs': glyphs()}, indent=2, sort_keys=True, ensure_ascii=False) + '\n'


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    want = text()
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding='utf-8') != want:
            print(f'stale {TARGET.relative_to(ROOT)}')
            return 1
        return 0
    TARGET.write_text(want, encoding='utf-8', newline='\n')
    made = json.loads(want)['glyphs']
    print(f'wrote glyphs for {len(made)} definitions ({sum(g["family"] == "distinctive" for g in made.values())} distinctive)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
