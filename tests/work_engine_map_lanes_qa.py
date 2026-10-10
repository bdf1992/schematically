"""Work Engine map lanes QA: the map's two harnesses run with lanes 'port', so the wires that leave one
record share a lane on the backs trunk (src/08-layout-core.js harness; scripts/layout_sov.mjs --lanes
port; docs/workengine/build_map.py; LAYOUT-MODEL.md "As built: buses", Harness, Lanes).

Node part, docs/workengine/map.sov and the constants of docs/workengine/build_map.py, each number
printed beside its base (dev bce66e2, one lane per wire):
  - every bus with a between key has lanes 'port';
  - the trunk harness-records-queries-backs has fewer distinct a ends among the wires naming it than
    wires naming it (base: a lane per wire, 59 of 59);
  - build_map.QUERY_GAP is below 460;
  - the map's width (greatest card right edge less least card left edge) is below BASE_WIDTH.
Browser part (index.html, file.open of map.sov, fitDiagram()):
  - data-lanes on that trunk's .bus-band is the number of distinct a ends among its wires;
  - the wires of the record that backs the most queries run at one across-bus coordinate on the
    trunk, within 0.5 (the method of the own-lane block in tests/routing_buses_qa.py);
  - no wire group has data-bus-fallback;
  - layout.metrics({static: true}) counts route-through-node 0;
  - no route-overlap finding names two wires of that trunk: a wire tapping on along the line another
    taps off along has its lane on the near side (src/41-buses.js busSiftLanes); without the sifting
    26 such pairs are found;
  - route-overlap is at most check_map.MAX_OVERLAP and crossing is below BASE_CROSSING, both printed
    beside the base;
  - the page logs no errors.

    python tests/work_engine_map_lanes_qa.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'docs' / 'workengine'))
import build_map  # noqa: E402
import check_map  # noqa: E402

MAP = ROOT / 'docs' / 'workengine' / 'map.sov'
TRUNK = 'harness-records-queries-backs'
BASE_WIDTH = 4520                 # the map's width at dev bce66e2, QUERY_GAP 460
BASE_QUERY_GAP = 460
BASE_CROSSING = 185               # layout.metrics crossing at dev bce66e2
BASE_OVERLAP = 23                 # layout.metrics route-overlap at dev bce66e2, 19 of them on the trunk


def view_of(doc: dict) -> dict:
    layout = doc.get('layout') or {}
    return (layout.get('views') or {}).get(layout.get('default') or 'main') or {}


def end_of(w: dict) -> tuple:
    return (w['a'], w.get('aSide'))


def width_of(doc: dict) -> float:
    lefts, rights = [], []
    for c in doc['components']:
        if c.get('symbolId') == 'group':
            continue
        w = c['config']['presentation']['size']['w']
        lefts.append(c['x'] - w / 2)
        rights.append(c['x'] + w / 2)
    return max(rights) - min(lefts)


def node_part(doc: dict) -> tuple[list[dict], str]:
    view = view_of(doc)
    buses = view.get('buses') or {}
    harness = sorted(b for b, rec in buses.items() if rec.get('between'))
    plain = [b for b in harness if buses[b].get('lanes') != 'port']
    print(f"harness buses: {len(harness)}, {len(harness) - len(plain)} with lanes 'port'")
    assert harness and not plain, f"every harness bus has lanes 'port'; without: {plain[:8]}"

    wires = {w['id']: w for w in doc['wires']}
    on_trunk = [wires[wid] for wid, rt in sorted((view.get('routes') or {}).items())
                if rt.get('mode') == 'bus' and TRUNK in rt['buses']]
    ends = {end_of(w) for w in on_trunk}
    print(f'{TRUNK}: {len(on_trunk)} wires on {len(ends)} distinct a ends (base: {len(on_trunk)} lanes)')
    assert len(ends) < len(on_trunk), (len(ends), len(on_trunk))

    print(f'QUERY_GAP {build_map.QUERY_GAP} (base {BASE_QUERY_GAP})')
    assert build_map.QUERY_GAP < BASE_QUERY_GAP, build_map.QUERY_GAP

    width = width_of(doc)
    print(f'map width {width:.0f} (base {BASE_WIDTH})')
    assert width < BASE_WIDTH, (width, BASE_WIDTH)
    return on_trunk, TRUNK


READ = r"""()=>{
  const out={corners:{},fallback:[],bands:{},through:null};
  for(const g of workspace.querySelectorAll('.wire-group')){
    if(g.dataset.busFallback)out.fallback.push(g.dataset.wireId);
    const p=g.querySelector('path.wire');if(!p)continue;
    out.corners[g.dataset.wireId]=layoutPathCorners(p.getAttribute('d').replace(/A[^A-Z]*?(?=[HV])/g,''));
  }
  for(const b of workspace.querySelectorAll('.bus-band'))out.bands[b.dataset.busId]=Number(b.dataset.lanes);
  const m=window.SovSchematicAPI.layout.metrics({static:true});
  out.through=(m.counts||{})['route-through-node']||0;
  out.crossing=(m.counts||{})['crossing']||0;
  out.overlaps=m.findings.filter(f=>f.kind==='route-overlap').map(f=>f.ids);
  return out;
}"""


def corners(points: list[dict]) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for q in points:
        p = (round(q['x'], 2), round(q['y'], 2))
        if not pts or pts[-1] != p:
            pts.append(p)
    out = pts[:1]
    for i in range(1, len(pts) - 1):
        a, b, c = out[-1], pts[i], pts[i + 1]
        if (a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1]):
            continue
        out.append(b)
    return out + pts[-1:] if len(pts) > 1 else out


def browser_part(doc: dict, on_trunk: list[dict]) -> None:
    from playwright.sync_api import sync_playwright
    from browser_runtime import chromium_launch_kwargs
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        errors: list[str] = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.set_content(html, wait_until='load'); page.wait_for_timeout(250)
        page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [json.dumps(doc), 'map.sov'])
        page.wait_for_timeout(300)
        page.evaluate('()=>fitDiagram()'); page.wait_for_timeout(200)
        seen = page.evaluate(READ)
        browser.close()

    ends = {end_of(w) for w in on_trunk}
    n = seen['bands'].get(TRUNK)
    print(f'{TRUNK} band: data-lanes {n}, distinct a ends {len(ends)}')
    assert n == len(ends), (n, len(ends))

    bus = (view_of(doc).get('buses') or {})[TRUNK]
    p0, p1 = bus['points'][0], bus['points'][-1]
    axis = 0 if p0['x'] == p1['x'] else 1
    at, pitch = (p0['x'], p0['y'])[axis], bus.get('pitch', 6)
    half = (n * pitch + 8) / 2
    by_end: dict[tuple, list[dict]] = {}
    for w in on_trunk:
        by_end.setdefault(end_of(w), []).append(w)
    record = max(sorted(by_end, key=str), key=lambda e: len(by_end[e]))
    mine = by_end[record]
    assert len(mine) > 1, record
    coords = []
    for w in mine:
        pts = corners(seen['corners'][w['id']])
        runs = [(a, b) for a, b in zip(pts, pts[1:])
                if a[axis] == b[axis] and abs(a[axis] - at) < half and abs(b[1 - axis] - a[1 - axis]) > 1]
        assert runs, (w['id'], 'has no run along', TRUNK, pts)
        longest = max(runs, key=lambda s: abs(s[1][1 - axis] - s[0][1 - axis]))
        coords.append(longest[0][axis])
    spread = max(coords) - min(coords)
    print(f'record {record[0]} backs {len(mine)} queries: across-bus coordinates spread {spread:.2f} (bound 0.5)')
    assert spread <= 0.5, coords

    print(f"bus fallbacks {len(seen['fallback'])}; route-through-node {seen['through']}; page errors {len(errors)}")
    assert not seen['fallback'], seen['fallback'][:8]
    assert seen['through'] == 0, seen['through']

    riders = {w['id'] for w in on_trunk}
    both = [ids for ids in seen['overlaps'] if all(i in riders for i in ids)]
    print(f"route-overlap {len(seen['overlaps'])} (base {BASE_OVERLAP}, bound {check_map.MAX_OVERLAP}), "
          f"{len(both)} between two wires of {TRUNK}; crossing {seen['crossing']} (base {BASE_CROSSING})")
    assert not both, f'two wires of {TRUNK} sharing no end run on one track: {both[:8]}'
    assert len(seen['overlaps']) <= check_map.MAX_OVERLAP, len(seen['overlaps'])
    assert seen['crossing'] < BASE_CROSSING, seen['crossing']
    assert not errors, errors


def main() -> None:
    doc = json.loads(MAP.read_text(encoding='utf-8'))
    on_trunk, _ = node_part(doc)
    browser_part(doc, on_trunk)
    print('PASS work engine map lanes QA')


if __name__ == '__main__':
    main()
