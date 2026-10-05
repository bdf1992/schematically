"""Picture bounds include bus labels QA.

A bus band and its label are drawn for the drawing (src/41-buses.js renderBuses), so they count in
the drawing's bounds (diagramBounds in src/30-canvas.js), and so in the fitted view and in the
picture SovSchematicAPI.render.svg makes (scripts/export_svg.py). The label sits beyond the bus's
start, rotated for a vertical bus; before this it lay past the top edge of the picture.

Checks, each printed with what it measured:
(a) examples/work-engine/groups.sov laid out by scripts/layout_sov.mjs --out into a temporary
    folder has 2 bus labels, and in render.svg({pad:48}) loaded as its own page each label's box
    lies inside the viewBox with at least 47 units to every edge;
(b) the same for every bus label and every bus-band rect of docs/workengine/map.sov;
(c) after fitDiagram() every bus label's screen box lies inside the workspace's screen box;
(d) tests/fixtures/task-lifecycle.sov, which has no bus, has the same diagramBounds() within 0.01
    with window.__boundsLeaveBusOut set (a test-only flag the product reads and never sets);
(e) a document built here with one vertical and one horizontal bus whose labels lie beyond the
    cards, on the top and on the left: both lie inside the picture with at least 47 units to every edge;
(f) the page logs no errors.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from browser_runtime import chromium_launch_kwargs  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PAD = 48
MIN_EDGE = 47

# Boxes of every bus element in a loaded picture, in the picture's own units, and its viewBox.
PICTURE_JS = """
() => {
  const svg = document.body.firstElementChild;
  const vb = svg.viewBox.baseVal, inv = svg.getScreenCTM().inverse();
  const boxes = [];
  for (const el of svg.querySelectorAll('text.bus-label,.bus-band rect')) {
    const r = el.getBBox(), m = inv.multiply(el.getScreenCTM());
    const pts = [[r.x, r.y], [r.x + r.width, r.y], [r.x, r.y + r.height], [r.x + r.width, r.y + r.height]]
      .map(([x, y]) => new DOMPoint(x, y).matrixTransform(m));
    const l = Math.min(...pts.map(p => p.x)), rr = Math.max(...pts.map(p => p.x));
    const t = Math.min(...pts.map(p => p.y)), b = Math.max(...pts.map(p => p.y));
    boxes.push({kind: el.tagName === 'text' ? 'label' : 'band', text: el.textContent, l, r: rr, t, b,
      edge: Math.min(l - vb.x, vb.x + vb.width - rr, t - vb.y, vb.y + vb.height - b)});
  }
  return {viewBox: [vb.x, vb.y, vb.width, vb.height], boxes};
}
"""

SCREEN_JS = """
() => {
  const w = workspace.getBoundingClientRect();
  return [...workspace.querySelectorAll('text.bus-label')].map(el => {
    const r = el.getBoundingClientRect();
    return {text: el.textContent, left: r.left - w.left, right: w.right - r.right, top: r.top - w.top, bottom: w.bottom - r.bottom};
  });
}
"""


def new_app(browser, errors):
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)
    return page


def open_doc(page, text, name):
    page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [text, name])
    page.evaluate('()=>fitDiagram()')
    page.wait_for_timeout(300)


def picture_measure(browser, page, errors):
    svg = page.evaluate('(pad)=>SovSchematicAPI.render.svg({pad})', PAD)
    view = browser.new_page()
    view.on('pageerror', lambda exc: errors.append(str(exc)))
    view.set_content(svg, wait_until='load')
    got = view.evaluate(PICTURE_JS)
    view.close()
    return got


def report(name, got, want_labels=None):
    labels = [b for b in got['boxes'] if b['kind'] == 'label']
    bands = [b for b in got['boxes'] if b['kind'] == 'band']
    print(f"{name}: viewBox {[round(v, 1) for v in got['viewBox']]}, {len(labels)} bus labels, {len(bands)} band rects")
    for b in labels:
        print(f"  label {b['text']!r}: box l={b['l']:.1f} r={b['r']:.1f} t={b['t']:.1f} b={b['b']:.1f}, nearest edge {b['edge']:.1f}")
    if bands:
        print(f"  band rects: nearest edge {min(b['edge'] for b in bands):.1f}")
    if want_labels is not None:
        assert len(labels) == want_labels, f'{name}: {len(labels)} bus labels, expected {want_labels}'
    for b in labels + bands:
        assert b['edge'] >= MIN_EDGE, f"{name}: {b['kind']} {b['text']!r} lies {b['edge']:.1f} from the nearest edge, need {MIN_EDGE}"


def built_document() -> dict:
    return {
        'schema': 'soveraeign.schematic/document@0.1', 'id': 'bus-labels-built', 'revision': 0,
        'meta': {'updatedAt': '2026-10-04T00:00:00.000Z', 'title': 'Bus labels built'},
        'canvas': {'id': 'canvas:global', 'scope': 'global', 'dimension': 2, 'state': 'open'},
        'components': [
            {'id': 'a', 'type': 'act', 'symbolId': 'act', 'x': 300, 'y': 350, 'config': {'label': 'Card A', 'colorSlot': 6}},
            {'id': 'b', 'type': 'hold', 'symbolId': 'hold', 'x': 700, 'y': 350, 'config': {'label': 'Card B', 'colorSlot': 7}},
        ],
        'wires': [{'id': 'w-ab', 'a': 'a', 'aSide': 'out', 'b': 'b', 'bSide': 'in', 'canvasId': 'canvas:global', 'config': {}}],
        'references': [], 'layout': {},
    }


def main() -> None:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as td, sync_playwright() as p:
        groups = Path(td) / 'groups.sov'
        done = subprocess.run(['node', 'scripts/layout_sov.mjs', 'examples/work-engine/groups.sov', '--out', str(groups)],
                              cwd=ROOT, capture_output=True, text=True)
        assert done.returncode == 0, f'layout_sov failed: {done.stdout} {done.stderr}'
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))

        page = new_app(browser, errors)
        open_doc(page, groups.read_text(encoding='utf-8'), 'groups.sov')
        report('(a) groups.sov re-laid', picture_measure(browser, page, errors), want_labels=2)
        shown = page.evaluate(SCREEN_JS)
        for s in shown:
            print(f"  (c) screen {s['text']!r}: to workspace edges l={s['left']:.1f} r={s['right']:.1f} t={s['top']:.1f} b={s['bottom']:.1f}")
            assert min(s['left'], s['right'], s['top'], s['bottom']) >= 0, f"(c) groups.sov: bus label {s['text']!r} outside the workspace: {s}"
        page.close()

        page = new_app(browser, errors)
        open_doc(page, (ROOT / 'docs/workengine/map.sov').read_text(encoding='utf-8'), 'map.sov')
        report('(b) docs/workengine/map.sov', picture_measure(browser, page, errors))
        shown = page.evaluate(SCREEN_JS)
        assert shown, 'the map has bus labels'
        worst = min(min(s['left'], s['right'], s['top'], s['bottom']) for s in shown)
        print(f"  (c) map: {len(shown)} bus labels on screen, nearest workspace edge {worst:.1f}")
        assert worst >= 0, f'(c) map: a bus label lies outside the workspace by {-worst:.1f}'
        page.close()

        page = new_app(browser, errors)
        open_doc(page, (ROOT / 'tests/fixtures/task-lifecycle.sov').read_text(encoding='utf-8'), 'task-lifecycle.sov')
        assert page.evaluate("()=>document.querySelectorAll('text.bus-label,.bus-band rect').length") == 0, 'task-lifecycle has no bus'
        with_bus = page.evaluate('()=>diagramBounds()')
        page.evaluate('()=>{window.__boundsLeaveBusOut=true}')
        without = page.evaluate('()=>diagramBounds()')
        print(f'(d) task-lifecycle diagramBounds {with_bus} ; bus elements left out {without}')
        for k in ('l', 'r', 't', 'b'):
            assert abs(with_bus[k] - without[k]) <= 0.01, f'(d) {k}: {with_bus[k]} vs {without[k]}'
        page.close()

        page = new_app(browser, errors)
        page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [json.dumps(built_document()), 'bus-labels-built.sov'])
        v = page.evaluate("()=>SovSchematicAPI.layout.bus({id:'vertical',label:'Vertical bus label',points:[{x:500,y:-300},{x:500,y:100}]})")
        h = page.evaluate("()=>SovSchematicAPI.layout.bus({id:'horizontal',label:'Horizontal bus label',points:[{x:-300,y:350},{x:100,y:350}]})")
        assert v.get('ok') and h.get('ok'), f'bus ops refused: {v} {h}'
        page.evaluate('()=>fitDiagram()')
        page.wait_for_timeout(300)
        report('(e) built document', picture_measure(browser, page, errors), want_labels=2)
        page.close()
        browser.close()

    assert not errors, f'(f) page errors: {errors}'
    print('(f) no page errors')
    print('PASS picture bounds bus labels QA')


if __name__ == '__main__':
    main()
