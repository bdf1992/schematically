"""Live logic state on the editor's own export (browser).

`export_svg.py --logic-state` draws a circuit's settled state onto the real editor render.
Checked here against the circuit's definition, not the overlay's own reading:

  - for every input vector of the half adder, each wire carries the value its net must have
    (the S wire A xor B, the C wire A and B, input wires their input), and each chip shows it;
  - one chip per pin, never two on a shared output;
  - no packet is left moving in a state snapshot;
  - monochrome uses no signal colour and dashes low wires;
  - every gate keeps its pack glyph through the editor's sanitizer (a custom graphic, not the
    generic symbol), in both appearances.
"""
from __future__ import annotations

import itertools
import json
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
from export_svg import export_documents  # noqa: E402

HALF = ROOT / 'examples' / 'logic' / 'half-adder.sov'
SVG = '{http://www.w3.org/2000/svg}'
HI = ('#2a78d6', '#3987e5')


def groups(svg_text: str) -> dict[str, ET.Element]:
    root = ET.fromstring(svg_text)
    return {g.attrib['data-wire-id']: g for g in root.iter(f'{SVG}g') if 'data-wire-id' in g.attrib}


def check_half_adder() -> None:
    doc = json.loads(HALF.read_text(encoding='utf-8'))
    wires = {w['id']: w for w in doc['wires']}
    with tempfile.TemporaryDirectory() as tmp:
        for a, b in itertools.product((0, 1), repeat=2):
            out = Path(tmp) / f'{a}{b}'
            r = export_documents([HALF], out, 'light', logic={'A': a, 'B': b})[0]
            assert not r['errors'], r['errors']
            text = r['target'].read_text(encoding='utf-8')
            gs = groups(text)
            assert set(gs) == set(wires), (set(gs), set(wires))
            for wid, w in wires.items():
                source = {'in-A': a, 'in-B': b, 'x': a ^ b, 'n': a & b}[w['a']]
                g = gs[wid]
                assert g.attrib['data-logic-value'] == str(source), (a, b, wid, g.attrib)
                assert not any(x.tag.endswith('animateMotion') for x in g.iter()), 'a snapshot has no packets in flight'
            chips = [c for c in ET.fromstring(text).iter(f'{SVG}g') if c.attrib.get('class') == 'logic-chip']
            pins = [c.attrib['data-pin'] for c in chips]
            assert len(pins) == len(set(pins)), 'one chip per pin'
            for c in chips:
                # A chip shows its own pin's net: a gate's input pins read the inputs, its q the result.
                expect = {'in-A.out': a, 'in-B.out': b, 'x.a': a, 'x.b': b, 'n.a': a, 'n.b': b,
                          'x.q': a ^ b, 'n.q': a & b, 'out-S.in': a ^ b, 'out-C.in': a & b}[c.attrib['data-pin']]
                assert c.attrib['data-value'] == str(expect), (a, b, c.attrib)
        mono = export_documents([HALF], Path(tmp) / 'mono', 'light', logic={'A': 1, 'B': 0}, monochrome=True)[0]
        text = mono['target'].read_text(encoding='utf-8')
        for g in groups(text).values():
            style = g.attrib.get('style', '')
            assert not any(h in style for h in HI), f'monochrome wire uses the signal colour: {style}'
        low = groups(text)[next(w for w, x in wires.items() if x['a'] == 'n')]
        wire = next(p for p in low.iter(f'{SVG}path') if 'wire' in p.attrib.get('class', '').split())
        assert '5' in (wire.attrib.get('style', '') + wire.attrib.get('stroke-dasharray', '')), 'a low wire is dashed in monochrome'


def check_glyphs_survive() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        for appearance in ('light', 'dark'):
            r = export_documents([ROOT / 'examples' / 'logic' / 'gates.sov'], Path(tmp) / appearance, appearance)[0]
            assert not r['errors'], r['errors']
            root = ET.fromstring(r['target'].read_text(encoding='utf-8'))
            gates = [c for c in json.loads((ROOT / 'examples' / 'logic' / 'gates.sov').read_text())['components']
                     if 'gate' in c.get('config', {}).get('logic', {})]
            custom = [g for g in root.iter(f'{SVG}g') if 'custom-graphic' in g.attrib.get('class', '').split()]
            # One glyph per gate, and it is the full one: an export draws at the document's own
            # scale, so the small variant is hidden and dropped from the file.
            assert len(custom) == len(gates), (appearance, len(custom), len(gates))
            assert not any('glyph-small' in g.attrib.get('class', '') for g in custom), appearance


def main() -> int:
    check_half_adder()
    check_glyphs_survive()
    print('logic_state_export QA PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
