"""Group rows QA: a grouped document packs its group blocks into rows and bundles the wires between
neighbouring groups on harness buses (src/08-layout-core.js `layered`, LAYOUT-MODEL.md "What layered
does" and "As built: buses").

Node part, tests/fixtures/booth-record-graphify.sov laid out with scripts/layout_sov.mjs --out on a
temp copy:
  - the union of the group regions (groupRect: members padded 24, 28 more on top) has an aspect
    ratio (width / height) between MIN_ASPECT and MAX_ASPECT; at a902dca it is 17554 x 2342, 7.50;
  - no two group regions overlap and no two cards overlap;
  - the layout's buses come from the harness only (every bus names `between`), at least MIN_PAIRS
    group pairs are bundled, at least MIN_ON_BUS cross-group wires ride buses, and every bus a route
    names exists.
Browser part (index.html, file.open of that laid-out document; layout.metrics is not used, it does
not finish on 262 wires):
  - long horizontal runs: each horizontal stretch of at least LONG px drawn by a cross-group wire
    not on a bus counts once, and each horizontal bus of at least LONG px that a cross-group wire
    rides counts once, however many wires it carries. At most half of DEV_LONG_RUNS, the count at
    a902dca;
  - no wire falls back from its bus (data-bus-fallback) and no bus-routed wire runs through a card,
    its own end cards included past the first and last 4 samples (the route-through-node rule of
    src/57-layout-metrics.js, applied to bus-routed wires only).

    python tests/group_rows_qa.py
"""
from __future__ import annotations
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECIMEN = ROOT / 'tests/fixtures/booth-record-graphify.sov'
PAD, BAND = 24, 28
MIN_ASPECT, MAX_ASPECT = 0.6, 2.5
DEV_LONG_RUNS = 154          # measured at dev a902dca, 2026-10-03
LONG = 1000
MIN_PAIRS = 3
MIN_ON_BUS = 25


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


def overlap(a, b) -> bool:
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


def node_part(tmp: Path) -> dict:
    dest = tmp / 'booth-record-graphify.sov'
    proc = subprocess.run(['node', str(ROOT / 'scripts/layout_sov.mjs'), str(SPECIMEN), '--out', str(dest)],
                          cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    doc = json.loads(dest.read_text(encoding='utf-8'))
    groups = [c['id'] for c in doc['components'] if is_group(c)]
    regions = {g: region(doc, g) for g in groups}
    w = max(r[1] for r in regions.values()) - min(r[0] for r in regions.values())
    h = max(r[3] for r in regions.values()) - min(r[2] for r in regions.values())
    aspect = w / h
    hits = [(a, b) for i, a in enumerate(groups) for b in groups[i + 1:] if overlap(regions[a], regions[b])]
    cards = [c for c in doc['components'] if not is_group(c)]
    for i, a in enumerate(cards):
        for b in cards[i + 1:]:
            assert not overlap(card_rect(a), card_rect(b)), f"{a['id']} overlaps {b['id']}"
    layout = doc.get('layout') or {}
    view = (layout.get('views') or {}).get(layout.get('default') or 'main') or {}
    buses, routes = view.get('buses') or {}, view.get('routes') or {}
    of = {}
    for c in doc['components']:
        if is_group(c):
            for m in c['config']['members']:
                of.setdefault(m, c['id'])
    cross = {w['id'] for w in doc['wires'] if of.get(w['a']) and of.get(w['b']) and of[w['a']] != of[w['b']]}
    on_bus = sorted(wid for wid, rt in routes.items() if rt.get('mode') == 'bus' and wid in cross)
    by_id = {w['id']: w for w in doc['wires']}
    pairs = sorted({tuple(sorted((of[by_id[wid]['a']], of[by_id[wid]['b']]))) for wid in on_bus})
    print(f'booth-record-graphify: region extent {w:.0f} x {h:.0f}, aspect {aspect:.2f} (bounds {MIN_ASPECT}-{MAX_ASPECT}); '
          f'{len(hits)} region pairs overlap; {len(pairs)} group pairs bundled, {len(on_bus)} of {len(cross)} cross-group wires on buses')
    assert MIN_ASPECT <= aspect <= MAX_ASPECT, f'aspect {aspect:.2f} outside {MIN_ASPECT}-{MAX_ASPECT}'
    assert not hits, f'{len(hits)} group regions overlap: {hits[:4]}'
    assert all(b.get('between') or k.startswith('channel-') for k, b in buses.items()), [k for k, b in buses.items() if not (b.get('between') or k.startswith('channel-'))]
    for wid, rt in routes.items():
        if rt.get('mode') == 'bus':
            assert all(bid in buses for bid in rt['buses']), (wid, rt)
    assert len(pairs) >= MIN_PAIRS, f'{len(pairs)} group pairs bundled, need {MIN_PAIRS}'
    assert len(on_bus) >= MIN_ON_BUS, f'{len(on_bus)} cross-group wires on buses, need {MIN_ON_BUS}'
    return doc


RUNS = '''(L)=>{
 const view=diagram.layout?.views?.[diagram.layout?.default||'main']||{},routes=view.routes||{},buses=view.buses||{};
 const of=new Map();for(const g of nodes.filter(isGroupComponent))for(const m of (g.config.members||[]))if(!of.has(m))of.set(m,g.id);
 const busKeys=new Set();let runs=0;const fallback=[],through=[];
 const cards=nodes.filter(n=>!isGroupComponent(n)).map(n=>{const s=componentSize(n);return {id:n.id,R:{l:n.x-s.w/2,r:n.x+s.w/2,t:n.y-s.h/2,b:n.y+s.h/2}}});
 for(const el of workspace.querySelectorAll('.wire-group')){
  const w=wires.find(x=>x.id===el.dataset.wireId);if(!w)continue;
  if(el.dataset.busFallback==='true')fallback.push(w.id);
  const path=el.querySelector('path.wire');if(!path)continue;
  const rt=routes[w.id],onBus=rt?.mode==='bus'&&el.dataset.busFallback!=='true';
  if(onBus){
   const pts=layoutSamplePath(path),inner=pts.slice(Math.min(pts.length,4),Math.max(0,pts.length-4));
   for(const c of cards){const own=c.id===w.a||c.id===w.b;if((own?inner:pts).some(p=>layoutInside(p,c.R,own?3:2))){through.push(w.id+'>'+c.id);break}}
  }
  const ga=of.get(w.a),gb=of.get(w.b);if(!(ga&&gb&&ga!==gb))continue;
  if(onBus){for(const bid of rt.buses){const P=buses[bid]?.points||[];for(let i=1;i<P.length;i++)if(P[i].y===P[i-1].y&&Math.abs(P[i].x-P[i-1].x)>=L){busKeys.add(bid);break}}continue}
  const P=layoutPathCorners(path.getAttribute('d'));
  for(let i=1;i<P.length;i++)if(Math.abs(P[i].y-P[i-1].y)<0.5&&Math.abs(P[i].x-P[i-1].x)>=L)runs++;
 }
 return {runs:runs+busKeys.size,wireRuns:runs,busRuns:busKeys.size,fallback,through};
}'''


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
        m = page.evaluate(RUNS, LONG)
        bound = DEV_LONG_RUNS // 2
        print(f"long horizontal runs (>= {LONG} px, cross-group): {m['runs']} ({m['wireRuns']} wire runs + {m['busRuns']} buses), "
              f"bound {bound} = half of {DEV_LONG_RUNS} at a902dca; bus fallbacks {len(m['fallback'])}; bus routes through a card {len(m['through'])}")
        assert m['runs'] <= bound, (m['runs'], bound)
        assert not m['fallback'], m['fallback'][:8]
        assert not m['through'], m['through'][:8]
        assert not errors, errors
        browser.close()


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        doc = node_part(Path(td))
        browser_part(doc)
    print('PASS group rows QA')


if __name__ == '__main__':
    main()
