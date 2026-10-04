"""Bus lane sharing QA: on a bus whose record carries lanes 'port', the wires that leave the same
port (the same card and the same aSide) share one lane, so a band's width counts ports, not wires
(src/41-buses.js busLaneKey; src/08-layout-core.js channelRoutes; LAYOUT-MODEL.md "As built: buses"
and "What layered does", Channels). The layered layout writes the key on every channel bus and sizes
its gaps by lanes. A bus without the key keeps one lane per wire: tests/routing_buses_qa.py holds
that case on a harness trunk.

Node part, tests/fixtures/booth-record-graphify.sov laid out with scripts/layout_sov.mjs --out in a
temporary directory, each number printed beside its value on the base (dev 87427fc, one lane per
wire):
  - the gap on the channels line is at most BASE_GAP / 2;
  - the area of the group regions' extent is at most two thirds of BASE_EXTENT's;
  - every bus whose id starts with channel- has lanes 'port';
  - on the channel-row or channel-gap bus the most routes name, the lanes are fewer than the wires.
Browser part (index.html, file.open of the laid-out document):
  - for every bus with lanes 'port', data-lanes on its .bus-band is the number of distinct a ends
    among the wires riding it;
  - on the bus the most routes name, each wire's longest run parallel to the bus inside its band
    gives its across-bus coordinate: wires with the same a end run at one coordinate within 0.5,
    wires with different a ends at least the pitch less 0.5 apart, and the distinct coordinates
    number data-lanes;
  - no wire group has data-bus-fallback and the page logs no errors.

    python tests/bus_lane_sharing_qa.py
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))

SPECIMEN = ROOT / 'tests/fixtures/booth-record-graphify.sov'
BASE_GAP = 570                    # the channels line at dev 87427fc
BASE_EXTENT = (10544, 9572)       # the group regions' extent at dev 87427fc
PAD, BAND = 24, 28


def is_group(c: dict) -> bool:
    return c.get('symbolId') == 'group'


def card_rect(c: dict) -> tuple[float, float, float, float]:
    size = ((c.get('config') or {}).get('presentation') or {}).get('size') or {}
    w, h = size.get('w', 112), size.get('h', 84)
    return c['x'] - w / 2, c['x'] + w / 2, c['y'] - h / 2, c['y'] + h / 2


def region(doc: dict, gid: str) -> tuple[float, float, float, float]:
    by_id = {c['id']: c for c in doc['components']}
    rects = [card_rect(by_id[m]) for m in by_id[gid]['config']['members'] if m in by_id and not is_group(by_id[m])]
    return (min(r[0] for r in rects) - PAD, max(r[1] for r in rects) + PAD,
            min(r[2] for r in rects) - PAD - BAND, max(r[3] for r in rects) + PAD)


def view_of(doc: dict) -> dict:
    layout = doc.get('layout') or {}
    return (layout.get('views') or {}).get(layout.get('default') or 'main') or {}


def end_of(w: dict) -> tuple[str, str | None]:
    """The lane key of a wire on a bus with lanes 'port': its a end; a wire with no a end is alone."""
    return (w['a'], w.get('aSide')) if w.get('a') else ('wire', w['id'])


def riders_of(doc: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for wid, rt in sorted((view_of(doc).get('routes') or {}).items()):
        if rt.get('mode') == 'bus':
            for bid in set(rt['buses']):
                out.setdefault(bid, []).append(wid)
    return out


def busiest(riders: dict[str, list[str]]) -> str:
    """The channel-row or channel-gap bus the most routes name; a tie goes to the lower id."""
    ids = sorted(b for b in riders if b.startswith(('channel-row-', 'channel-gap-')))
    assert ids, 'no channel-row or channel-gap bus carries a route'
    return max(ids, key=lambda b: len(riders[b]))


def node_part(tmp: Path) -> dict:
    dest = tmp / 'booth-record-graphify.sov'
    proc = subprocess.run(['node', str(ROOT / 'scripts/layout_sov.mjs'), str(SPECIMEN), '--out', str(dest)],
                          cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    line = next((ln.strip() for ln in proc.stdout.splitlines() if ln.strip().startswith('channels:')), None)
    assert line, 'no channels line in:\n' + proc.stdout
    print(line)
    gap = int(re.search(r'gap (\d+)', line).group(1))
    print(f'widest channel gap: {gap} (base {BASE_GAP}, bound {BASE_GAP / 2:g})')
    assert gap <= BASE_GAP / 2, f'gap {gap} is over half of the base {BASE_GAP}'

    doc = json.loads(dest.read_text(encoding='utf-8'))
    regions = [region(doc, c['id']) for c in doc['components'] if is_group(c)]
    w = max(r[1] for r in regions) - min(r[0] for r in regions)
    h = max(r[3] for r in regions) - min(r[2] for r in regions)
    base_area = BASE_EXTENT[0] * BASE_EXTENT[1]
    print(f'group regions: {w:.0f} x {h:.0f}, area {w * h:.0f}, aspect {w / h:.2f} '
          f'(base {BASE_EXTENT[0]} x {BASE_EXTENT[1]}, area {base_area}, aspect {BASE_EXTENT[0] / BASE_EXTENT[1]:.2f}); '
          f'{w * h / base_area:.3f} of the base, bound {2 / 3:.3f}')
    assert w * h <= base_area * 2 / 3, f'area {w * h:.0f} is over two thirds of the base {base_area}'

    buses = view_of(doc).get('buses') or {}
    channel = sorted(b for b in buses if b.startswith('channel-'))
    assert channel, 'the layout made no channel bus'
    plain = [b for b in channel if buses[b].get('lanes') != 'port']
    print(f"channel buses: {len(channel)} ({sum(1 for b in channel if b.startswith('channel-street-'))} streets), "
          f"{len(channel) - len(plain)} with lanes 'port'")
    assert not plain, plain[:8]

    wires = {x['id']: x for x in doc['wires']}
    riders = riders_of(doc)
    for bid in sorted(riders, key=lambda b: (-len(riders[b]), b))[:3]:
        print(f'  {bid}: {len(riders[bid])} wires on {len({end_of(wires[i]) for i in riders[bid]})} lanes')
    top = busiest(riders)
    n_wires, n_lanes = len(riders[top]), len({end_of(wires[i]) for i in riders[top]})
    print(f'busiest channel bus {top}: {n_wires} wires on {n_lanes} lanes')
    assert n_lanes < n_wires, (top, n_lanes, n_wires)
    return doc


READ = r"""()=>{
  const out={corners:{},fallback:[],bands:{}};
  for(const g of workspace.querySelectorAll('.wire-group')){
    if(g.dataset.busFallback)out.fallback.push(g.dataset.wireId);
    const p=g.querySelector('path.wire');if(!p)continue;
    out.corners[g.dataset.wireId]=layoutPathCorners(p.getAttribute('d').replace(/A[^A-Z]*?(?=[HV])/g,''));
  }
  for(const b of workspace.querySelectorAll('.bus-band'))out.bands[b.dataset.busId]=Number(b.dataset.lanes);
  return out;
}"""


def corners(points: list[dict]) -> list[tuple[float, float]]:
    """The path's corners: repeated points and points in the middle of a straight run dropped."""
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


def browser_part(doc: dict) -> None:
    from playwright.sync_api import sync_playwright
    from browser_runtime import chromium_launch_kwargs
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        errors: list[str] = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.set_content(html, wait_until='load'); page.wait_for_timeout(250)
        page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [json.dumps(doc), 'booth-record-graphify.sov'])
        page.wait_for_timeout(300)
        seen = page.evaluate(READ)
        browser.close()

    buses = view_of(doc).get('buses') or {}
    wires = {x['id']: x for x in doc['wires']}
    riders = riders_of(doc)

    # Every band of a bus with lanes 'port' is as wide as its distinct a ends.
    shared = sorted(b for b in buses if buses[b].get('lanes') == 'port')
    wrong = {b: (seen['bands'].get(b), len({end_of(wires[i]) for i in riders.get(b, [])})) for b in shared}
    wrong = {b: v for b, v in wrong.items() if v[0] != v[1]}
    print(f"bands of buses with lanes 'port': {len(shared)}, data-lanes off the distinct a ends on {len(wrong)}")
    assert not wrong, dict(list(wrong.items())[:8])

    # On the busiest bus: one coordinate per a end, a pitch apart.
    top = busiest(riders)
    bus, n = buses[top], seen['bands'][top]
    p0, p1 = bus['points'][0], bus['points'][-1]
    axis = 0 if p0['x'] == p1['x'] else 1            # the across-bus coordinate: x on a vertical bus
    at, half, pitch = (p0['x'], p0['y'])[axis], (n * bus.get('pitch', 6) + 8) / 2, bus.get('pitch', 6)
    by_end: dict[tuple, list[float]] = {}
    for wid in riders[top]:
        pts = corners(seen['corners'][wid])
        runs = [(a, b) for a, b in zip(pts, pts[1:])
                if a[axis] == b[axis] and abs(a[axis] - at) < half and abs(b[1 - axis] - a[1 - axis]) > 1]
        assert runs, (wid, 'has no run along', top, 'inside its band', pts)
        longest = max(runs, key=lambda s: abs(s[1][1 - axis] - s[0][1 - axis]))
        by_end.setdefault(end_of(wires[wid]), []).append(longest[0][axis])
    spread = max(max(xs) - min(xs) for xs in by_end.values())
    lanes = sorted(sum(xs) / len(xs) for xs in by_end.values())
    apart = min((b - a for a, b in zip(lanes, lanes[1:])), default=float('inf'))
    distinct: list[float] = []
    for x in sorted(x for xs in by_end.values() for x in xs):
        if not distinct or x - distinct[-1] > 0.5:
            distinct.append(x)
    print(f"{top}: {len(riders[top])} wires from {len(by_end)} a ends run at {len(distinct)} coordinates (data-lanes {n}); "
          f"widest spread inside one a end {spread:.2f} (bound 0.5); nearest two a ends {apart:.2f} apart (pitch {pitch}, bound {pitch - 0.5})")
    assert spread <= 0.5, {str(e): xs for e, xs in by_end.items() if max(xs) - min(xs) > 0.5}
    assert apart >= pitch - 0.5, lanes
    assert len(distinct) == n, (len(distinct), n, distinct)

    print(f"bus fallbacks {len(seen['fallback'])}; page errors {len(errors)}")
    assert not seen['fallback'], seen['fallback'][:8]
    assert not errors, errors


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        doc = node_part(Path(td))
        browser_part(doc)
    print('PASS bus lane sharing QA')


if __name__ == '__main__':
    main()
