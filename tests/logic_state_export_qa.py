"""State on the editor's own export (browser): `export_svg.py --run` and `--trace`.

The export draws a state space run through the editor's state view (src/57-state-view.js).
Checked here against the circuit's definition, not the view's own reading:

  - for every input vector of the half adder, each wire carries the level of the port it
    leaves from (the S wire A xor B, the C wire A and B, source wires their input), and the
    chip at each port shows that port's level;
  - exactly one chip per wired port: none dropped from the file, never two on a shared port;
  - no packet is left moving in a state picture;
  - monochrome uses no signal colour and dashes low wires;
  - a trace of another document is refused (the view replays it against the open document),
    the export reports it as an error and draws no state; the same trace on its own document
    draws;
  - every gate keeps its glyph through the editor's sanitizer (a custom graphic, not the
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
from export_svg import RUN_JS, export_documents  # noqa: E402

LG = ROOT / 'examples' / 'logic'
HALF = LG / 'half-adder.sov'
SVG = '{http://www.w3.org/2000/svg}'
HI = ('#2a78d6', '#3987e5')


def groups(svg_text: str) -> dict[str, ET.Element]:
    root = ET.fromstring(svg_text)
    return {g.attrib['data-wire-id']: g for g in root.iter(f'{SVG}g') if 'data-wire-id' in g.attrib}


def chips(svg_text: str) -> list[ET.Element]:
    return [c for c in ET.fromstring(svg_text).iter(f'{SVG}g') if 'state-chip' in c.attrib.get('class', '').split()]


def run_inputs(vector: dict) -> list[dict]:
    return [{'entity': k, 'point': 'self', 'value': bool(v), 'at': 0} for k, v in sorted(vector.items())]


def trace_in_page(path: Path, vector: dict) -> dict:
    from playwright.sync_api import sync_playwright
    from browser_runtime import chromium_launch_kwargs
    packs = [json.loads((ROOT / 'data' / p).read_text(encoding='utf-8')) for p in ('core.logic.pack.json', 'logic.gates.pack.json')]
    with sync_playwright() as p:
        b = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = b.new_page()
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [path.read_text(encoding='utf-8'), path.name])
        made = page.evaluate(RUN_JS, [packs, run_inputs(vector)])
        b.close()
    assert made['ok'], made
    return made['trace']


def check_half_adder() -> None:
    doc = json.loads(HALF.read_text(encoding='utf-8'))
    port = lambda w, end: (w.get(f'{end}Attachment') or {}).get('pointId') or w[f'{end}Side']  # noqa: E731
    wired = {f"{w[e]}.{port(w, e)}" for w in doc['wires'] for e in ('a', 'b')}
    assert len(wired) == 10, wired
    with tempfile.TemporaryDirectory() as tmp:
        for a, b in itertools.product((0, 1), repeat=2):
            r = export_documents([HALF], Path(tmp) / f'{a}{b}', 'light', run=run_inputs({'A': a, 'B': b}))[0]
            assert not r['errors'], r['errors']
            text = r['target'].read_text(encoding='utf-8')
            level = {'A': a, 'B': b, 'x': a ^ b, 'n': a & b}
            gs = groups(text)
            assert set(gs) == {w['id'] for w in doc['wires']}, set(gs)
            for w in doc['wires']:
                g = gs[w['id']]
                assert g.attrib['data-state-level'] == str(level[w['a']]), (a, b, w['id'], g.attrib)
                assert not any(x.tag.endswith('animateMotion') for x in g.iter()), 'a state picture has no packets in flight'
            pins = [c.attrib['data-pin'] for c in chips(text)]
            assert sorted(pins) == sorted(wired), pins
            got = {c.attrib['data-pin']: c.attrib['data-value'] for c in chips(text)}
            want = {'A.self': a, 'B.self': b, 'x.a': a, 'x.b': b, 'n.a': a, 'n.b': b, 'x.q': a ^ b, 'n.q': a & b,
                    'S.self': a ^ b, 'C.self': a & b}
            assert got == {k: str(v) for k, v in want.items()}, (a, b, got)
        mono = export_documents([HALF], Path(tmp) / 'mono', 'light', monochrome=True, run=run_inputs({'A': 1, 'B': 0}))[0]
        assert not mono['errors'], mono['errors']
        text = mono['target'].read_text(encoding='utf-8')
        for g in groups(text).values():
            assert not any(h in g.attrib.get('style', '') for h in HI), f"monochrome wire uses the signal colour: {g.attrib.get('style')}"
        low = groups(text)[next(w['id'] for w in doc['wires'] if w['a'] == 'n')]
        wire = next(p for p in low.iter(f'{SVG}path') if 'wire' in p.attrib.get('class', '').split())
        assert '5' in (wire.attrib.get('style', '') + wire.attrib.get('stroke-dasharray', '')), 'a low wire is dashed in monochrome'
        # A trace of the half adder does not describe the full adder: shown there, it is refused.
        trace = trace_in_page(HALF, {'A': 1, 'B': 1})
        wrong = export_documents([LG / 'full-adder.sov'], Path(tmp) / 'wrong', 'light', trace=trace)[0]
        assert any('REPLAY_KEY_MISMATCH' in e for e in wrong['errors']), wrong['errors']
        assert not chips(wrong['target'].read_text(encoding='utf-8')), 'a refused trace draws no state'
        right = export_documents([HALF], Path(tmp) / 'right', 'light', trace=trace)[0]
        assert not right['errors'] and len(chips(right['target'].read_text(encoding='utf-8'))) == 10, right['errors']


def check_glyphs_survive() -> None:
    gates = [c for c in json.loads((LG / 'gates.sov').read_text(encoding='utf-8'))['components'] if c.get('config', {}).get('definition')]
    with tempfile.TemporaryDirectory() as tmp:
        for appearance in ('light', 'dark'):
            r = export_documents([LG / 'gates.sov'], Path(tmp) / appearance, appearance)[0]
            assert not r['errors'], r['errors']
            root = ET.fromstring(r['target'].read_text(encoding='utf-8'))
            custom = [g for g in root.iter(f'{SVG}g') if 'custom-graphic' in g.attrib.get('class', '').split()]
            # One glyph per gate, and it is the full one: an export draws at the document's own
            # scale, so the small variant is hidden and dropped from the file.
            assert len(custom) == len(gates) == 16, (appearance, len(custom), len(gates))
            assert not any('glyph-small' in g.attrib.get('class', '') for g in custom), appearance


def main() -> int:
    check_half_adder()
    check_glyphs_survive()
    print('logic_state_export QA PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
