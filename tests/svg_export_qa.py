"""Headless SVG export QA.

Exports every examples/*.sov through scripts/export_svg.py into a temporary directory and
checks that each file is a standalone SVG: well-formed XML, self-sizing, styled without the
app stylesheet, carrying the document's labels, and free of editor-only interaction state.
"""
from __future__ import annotations
import json
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from export_svg import export_documents  # noqa: E402

SVG_NS = '{http://www.w3.org/2000/svg}'
EDITOR_ONLY = ('selected', 'snap-target', 'wiring-source', 'port-hit', 'wire-hit')


def check(svg_path: Path, doc: dict) -> None:
    text = svg_path.read_text(encoding='utf-8')
    root = ET.fromstring(text)
    assert root.tag == f'{SVG_NS}svg', f'{svg_path.name}: root is {root.tag}'
    assert root.get('viewBox'), f'{svg_path.name}: no viewBox'
    assert 'background-color:' in (root.get('style') or ''), f'{svg_path.name}: no background colour'
    for cls in EDITOR_ONLY:
        assert f'"{cls}"' not in text and f' {cls} ' not in text and f' {cls}"' not in text, f'{svg_path.name}: carries editor class {cls}'
    assert 'display:none' not in text, f'{svg_path.name}: hidden subtree carried into export'
    assert root.find(f'{SVG_NS}defs') is not None, f'{svg_path.name}: symbol defs missing'
    # A Plane draws no label of its own; every other labelled record renders its label as text.
    labels = [c.get('config', {}).get('label') for c in doc['components'] if c.get('symbolId') != 'plane']
    labels = [l for l in labels if l]
    texts = ''.join((t.text or '') for t in root.iter(f'{SVG_NS}text')) + ''.join((t.text or '') for t in root.iter(f'{SVG_NS}tspan'))
    for label in labels:
        assert label in texts, f'{svg_path.name}: label {label!r} not rendered'
    if labels:
        assert root.get('width') and root.get('height'), f'{svg_path.name}: not self-sizing'
        # Ports are styled entirely by app.css; the export must carry that styling inline.
        ports = [el for el in root.iter() if 'port' in (el.get('class') or '').split()]
        assert ports, f'{svg_path.name}: no port elements'
        for port in ports:
            style = port.get('style') or ''
            assert 'stroke:' in style and 'fill:' in style, f'{svg_path.name}: port lacks inline stroke/fill'
    # Wires on a local surface are lifted above their host body so a static picture shows them.
    order = [el for el in root.iter() if el.get('data-wire-id') or el.get('data-id')]
    for w in doc['wires']:
        cid = w.get('canvasId') or ''
        if not cid.startswith('canvas:component:'):
            continue
        host = cid[len('canvas:component:'):]
        host_i = next((i for i, el in enumerate(order) if el.get('data-id') == host), None)
        wire_i = next((i for i, el in enumerate(order) if el.get('data-wire-id') == w['id']), None)
        assert host_i is not None and wire_i is not None, f"{svg_path.name}: host {host} or wire {w['id']} missing"
        assert wire_i > host_i, f"{svg_path.name}: interior wire {w['id']} is painted under its host {host}"
    assert len(text.encode('utf-8')) < 400_000, f'{svg_path.name}: export unexpectedly large'


def main() -> None:
    examples = sorted((ROOT / 'examples').glob('*.sov'))
    assert examples
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        results = export_documents(examples, out)
        assert len(results) == len(examples)
        for r in results:
            assert not r['errors'], f"{r['source'].name}: page errors {r['errors']}"
            doc = json.loads(r['source'].read_text(encoding='utf-8'))
            check(r['target'], doc)
    print(f'PASS SVG export QA ({len(examples)} documents)')


if __name__ == '__main__':
    main()
