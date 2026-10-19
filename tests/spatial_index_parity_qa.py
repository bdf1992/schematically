"""The routing and label-placement grids change no drawing.

src/40-routing.js occupiedNear and the label grid in src/55-render.js placeWireLabels hand back only
the placed segments and boxes near a candidate, on the argument that everything farther adds exactly
0 to its score or count. This suite draws each document twice, once as built and once with
window.SOV_QA_NO_SPATIAL_INDEX set (the plain scans), and requires the two pictures to be the same
bytes. The documents are the ones large enough for the routing grid to switch on (64 placed segments).
examples/state/bench.sov (164 cards, 234 wires) drew the same on 2026-10-19, unlabelled and with every
wire labelled (86 labels crowded), but the plain scans take two minutes on it, so it is left out of
the gate; add it to DOCUMENTS (and LABELLED) for a deep run. A picture
alone would hide a label-grid fault, because the second drawing pass settles the labels again, so
the as-built drawing also runs with window.SOV_QA_CHECK_SPATIAL_INDEX, which takes every label
overlap count both ways and records any disagreement; there must be none.
A drawing rarely puts two segments in neighbouring cells within the reach, so the suite also scores
random routes against random placed segments set at the distances where each term switches (an
offset of 0, 2, 3, 14, 16 or 17 units, ends a gap of up to 20 apart) and requires the same numbers.
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from browser_runtime import chromium_launch_kwargs  # noqa: E402

DOCUMENTS = [
    'tests/fixtures/task-lifecycle.sov',
    'tests/fixtures/work-engine-sample.sov',
    'examples/09-print-ai-proof-run.sov',
]
LABELLED: set[str] = set()  # add a document here to draw it with every wire labelled
SCORE_JS = """() => {
  let seed = 20261019;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  const pick = list => list[Math.floor(rnd() * list.length)];
  const ids = ['a:out', 'b:in', 'c:out', 'd:in', 'e:control'];
  const seg = (x, y, h, len) => h ? {a: {x, y}, b: {x: x + len, y}} : {a: {x, y}, b: {x, y: y + len}};
  // Placed segments in bundles: a base line, then neighbours at the offsets and end gaps that matter.
  const occupied = [];
  while (occupied.length < 400) {
    const h = rnd() < .5, x = Math.round(rnd() * 900), y = Math.round(rnd() * 900), len = pick([6, 20, 60, 140, 300]);
    const ends = rnd() < .2 ? null : [pick(ids), pick(ids)];
    occupied.push({...seg(x, y, h, len), ends});
    const off = pick([0, 2, 3, 14, 16, 17]), gap = pick([0, 10, 13, 14, 15, 20]);
    occupied.push({...seg(h ? x + len + gap : x + off, h ? y + off : y + len + gap, h, len), ends});
  }
  const routes = [];
  for (let k = 0; k < 300; k++) {
    const o = pick(occupied), h = Math.abs(o.a.y - o.b.y) < 1, off = pick([0, 1, 2, 3, 15, 16, 17, 40]);
    const A = h ? {x: o.a.x - pick([0, 13, 30]), y: o.a.y + off} : {x: o.a.x + off, y: o.a.y - pick([0, 13, 30])};
    const M = h ? {x: A.x + pick([30, 200]), y: A.y} : {x: A.x, y: A.y + pick([30, 200])};
    const B = h ? {x: M.x, y: M.y + pick([-80, 80])} : {x: M.x + pick([-80, 80]), y: M.y};
    routes.push({points: [A, M, B], ends: [pick(ids), pick(ids)]});
  }
  const score = () => routes.map(r => [pathScore(r.points, r.points[0], r.points[2], [], occupied, r.ends),
    occupiedCost(r.points[0], r.points[1], occupied, r.ends)]);
  window.SOV_QA_NO_SPATIAL_INDEX = false; const grid = score();
  window.SOV_QA_NO_SPATIAL_INDEX = true; const plain = score();
  window.SOV_QA_NO_SPATIAL_INDEX = false;
  const differ = grid.map((g, i) => [i, g, plain[i]]).filter(([, g, p]) => g[0] !== p[0] || g[1] !== p[1]);
  return {routes: routes.length, differ: differ.slice(0, 3), count: differ.length};
}"""
DRAW_JS = "([t,n])=>{window.SovSchematicAPI.file.open(t,n);return window.SovSchematicAPI.render.svg({pad:48,packets:false,legend:false})}"


def document_text(rel: str) -> str:
    text = (ROOT / rel).read_text(encoding='utf-8')
    if rel not in LABELLED:
        return text
    doc = json.loads(text)
    for w in doc['wires']:
        w.setdefault('config', {})['label'] = f"wire {w['id']}"
    return json.dumps(doc)


def draw(browser, html: str, path: Path, plain: bool) -> tuple[str, list]:
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    page.set_default_timeout(150000)
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content(html, wait_until='load')
    page.wait_for_timeout(250)
    # Set on the page itself: an init script does not run for set_content.
    flag = 'SOV_QA_NO_SPATIAL_INDEX' if plain else 'SOV_QA_CHECK_SPATIAL_INDEX'
    assert page.evaluate(f'() => (window.{flag} = true)') is True
    svg = page.evaluate(DRAW_JS, [document_text(str(path.relative_to(ROOT).as_posix())), path.name])
    mismatches = page.evaluate('() => window.SOV_QA_SPATIAL_MISMATCHES || []')
    page.close()
    assert not errors, f'{path.name}: page errors {errors}'
    return svg, mismatches


def main() -> int:
    from playwright.sync_api import sync_playwright
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page()
        page.set_content(html, wait_until='load')
        scored = page.evaluate(SCORE_JS)
        page.close()
        assert not scored['count'], f"the routing grid changes {scored['count']} of {scored['routes']} scores: {scored['differ']}"
        print(f"same scores for {scored['routes']} random routes against 400 placed segments")
        for rel in DOCUMENTS:
            path = ROOT / rel
            started = time.time()
            (grid, mismatches), (plain, _) = draw(browser, html, path, False), draw(browser, html, path, True)
            assert not mismatches, f'{rel}: the label grid miscounts {len(mismatches)} places, first {mismatches[0]}'
            if grid != plain:
                i = next((k for k in range(min(len(grid), len(plain))) if grid[k] != plain[k]), min(len(grid), len(plain)))
                raise AssertionError(f'{rel}: the grids change the drawing at byte {i}: {grid[max(0, i - 60):i + 40]!r} vs {plain[max(0, i - 60):i + 40]!r}')
            print(f'same {rel} ({len(grid)} bytes, {time.time() - started:.1f}s)')
        browser.close()
    print(f'spatial index parity QA passed: {len(DOCUMENTS)} documents drawn the same with and without the grids')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
