"""Channel buses QA: on a packed grouped canvas, every wire between two items of the canvas rides
channel buses: a horizontal bus in each row gap of the packed grid, a vertical bus in each gap
between two items of a row (and beside the first and last), and, for a card with another member
between it and its gap, a street in its block's row gap (src/08-layout-core.js `layered`,
LAYOUT-MODEL.md "What layered does" and "As built: buses"). Laying a grouped document out twice
gives the same document.

Node part, tests/fixtures/booth-record-graphify.sov laid out with scripts/layout_sov.mjs --out on a
temp copy:
  - no two group regions overlap and no two cards overlap;
  - every cross-group wire rides buses, and every bus a route names exists;
  - no bus centreline meets the region of a group it does not serve: a harness bus serves the two
    groups it names in `between`, a street `channel-street-<group>-...` serves its group, every
    other channel bus serves none;
  - no bus band (lanes x pitch + 8 wide; lanes = the distinct (a, aSide) ends among the wires whose
    route names it on a bus with lanes 'port', else the routes naming it) meets a card.
Twice: the seeded fixture of tests/layered_groups_qa.py, the booth-record fixture,
examples/work-engine/groups.sov and docs/workengine/map.sov, each laid out, then the result laid out
again: the two results are equal once meta.updatedAt is dropped. At 3f3aa75 none of the four is.
Browser part (index.html, file.open of the laid-out fixture):
  - long horizontal runs: each horizontal stretch of at least LONG px drawn by a cross-group wire
    and lying along no horizontal bus it rides counts once (a wire off buses, or a tap leg), and
    each horizontal bus of at least LONG px that a cross-group wire rides counts once. At most
    MAX_LONG_RUNS; at 3f3aa75 the count is 73;
  - no wire falls back from its bus and no bus-routed wire runs through a card (the
    route-through-node rule of src/57-layout-metrics.js, own end cards past 4 samples).

    python tests/channel_buses_qa.py
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from layered_groups_qa import build_fixture  # noqa: E402

SPECIMEN = ROOT / 'tests/fixtures/booth-record-graphify.sov'
TWICE = {'seeded fixture': None, 'booth-record-graphify': SPECIMEN,
         'examples/work-engine/groups.sov': ROOT / 'examples/work-engine/groups.sov',
         'docs/workengine/map.sov': ROOT / 'docs/workengine/map.sov'}
PAD, BAND = 24, 28
LONG = 1000
MAX_LONG_RUNS = 39           # the task's bound, under 40; 73 at 3f3aa75, 29 on the coordinator's prototype
BASE_LONG_RUNS = 73


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


def lay_out(src: Path, dest: Path) -> dict:
    proc = subprocess.run(['node', str(ROOT / 'scripts/layout_sov.mjs'), str(src), '--out', str(dest)],
                          cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(dest.read_text(encoding='utf-8'))


def normalised(doc: dict) -> str:
    doc = json.loads(json.dumps(doc))
    (doc.get('meta') or {}).pop('updatedAt', None)
    return json.dumps(doc, sort_keys=True)


def node_part(tmp: Path) -> dict:
    doc = lay_out(SPECIMEN, tmp / 'booth-record-graphify.sov')
    groups = [c['id'] for c in doc['components'] if is_group(c)]
    regions = {g: region(doc, g) for g in groups}
    hits = [(a, b) for i, a in enumerate(groups) for b in groups[i + 1:] if overlap(regions[a], regions[b])]
    assert not hits, f'{len(hits)} group regions overlap: {hits[:4]}'
    cards = [c for c in doc['components'] if not is_group(c)]
    for i, a in enumerate(cards):
        for b in cards[i + 1:]:
            assert not overlap(card_rect(a), card_rect(b)), f"{a['id']} overlaps {b['id']}"
    layout = doc.get('layout') or {}
    view = (layout.get('views') or {}).get(layout.get('default') or 'main') or {}
    buses, routes = view.get('buses') or {}, view.get('routes') or {}
    of: dict[str, str] = {}
    for c in doc['components']:
        if is_group(c):
            for m in c['config']['members']:
                of.setdefault(m, c['id'])
    cross = sorted(w['id'] for w in doc['wires'] if of.get(w['a']) and of.get(w['b']) and of[w['a']] != of[w['b']])
    on_bus = [wid for wid in cross if (routes.get(wid) or {}).get('mode') == 'bus']
    off = sorted(set(cross) - set(on_bus))
    riders: dict[str, list[str]] = {}
    for wid, rt in routes.items():
        if rt.get('mode') == 'bus':
            missing = [bid for bid in rt['buses'] if bid not in buses]
            assert not missing, (wid, missing)
            for bid in set(rt['buses']):
                riders.setdefault(bid, []).append(wid)
    # A bus with lanes 'port' has one lane per distinct (a, aSide) among its wires; any other, one per route.
    ends = {w['id']: (w['a'], w.get('aSide')) if w.get('a') else ('wire', w['id']) for w in doc['wires']}
    lanes = {bid: len({ends[wid] for wid in ws}) if buses[bid].get('lanes') == 'port' else len(ws) for bid, ws in riders.items()}
    print(f'booth-record-graphify: {len(buses)} buses ({sum(1 for b in buses if b.startswith("channel-"))} channel), '
          f'{len(on_bus)} of {len(cross)} cross-group wires on buses; 0 of {len(groups) * (len(groups) - 1) // 2} region pairs overlap')
    assert not off, f'{len(off)} cross-group wires ride no bus: {off[:8]}'
    third, over = [], []
    for bid, bus in sorted(buses.items()):
        if bus.get('between'):
            serves = set(bus['between'])
        elif bid.startswith('channel-street-'):
            serves = {max((g for g in groups if bid.startswith(f'channel-street-{g}-')), key=len, default='')}
        else:
            serves = set()
        pts, hw = bus['points'], (lanes.get(bid, 0) * bus.get('pitch', 6) + 8) / 2
        for p, q in zip(pts, pts[1:]):
            seg = (min(p['x'], q['x']), max(p['x'], q['x']), min(p['y'], q['y']), max(p['y'], q['y']))
            seg = (seg[0] - 1e-6, seg[1] + 1e-6, seg[2] - 1e-6, seg[3] + 1e-6)
            third += [f'{bid}>{g}' for g in groups if g not in serves and overlap(seg, regions[g])]
            band = (seg[0] - hw, seg[1] + hw, seg[2] - hw, seg[3] + hw)
            over += [f"{bid}>{c['id']}" for c in cards if overlap(band, card_rect(c))]
    print(f'buses meeting a region they do not serve: {len(third)}; bus bands over a card: {len(over)}')
    assert not third, sorted(set(third))[:8]
    assert not over, sorted(set(over))[:8]
    return doc


def twice_part(tmp: Path) -> None:
    for k, (name, path) in enumerate(TWICE.items()):
        src = tmp / f'twice{k}.in.sov'
        src.write_text(json.dumps(build_fixture()) if path is None else path.read_text(encoding='utf-8'), encoding='utf-8')
        once = lay_out(src, tmp / f'twice{k}.1.sov')
        again = lay_out(tmp / f'twice{k}.1.sov', tmp / f'twice{k}.2.sov')
        assert normalised(once) == normalised(again), f'{name}: laying the layout out again changes it'
    print(f'twice: {len(TWICE)} grouped documents laid out twice are unchanged by the second layout')


RUNS = '''(L)=>{
 const view=diagram.layout?.views?.[diagram.layout?.default||'main']||{},routes=view.routes||{},buses=view.buses||{};
 const of=new Map();for(const g of nodes.filter(isGroupComponent))for(const m of (g.config.members||[]))if(!of.has(m))of.set(m,g.id);
 const st=busRoutesForRender(),hw=bid=>((st.lanes.get(bid)?.length||0)*busPitchOf(buses[bid])+8)/2;
 const busKeys=new Set();let wireRuns=0,tapRuns=0;const fallback=[],through=[];
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
  const P=layoutPathCorners(path.getAttribute('d'));
  const flat=[];for(let i=1;i<P.length;i++)if(Math.abs(P[i].y-P[i-1].y)<0.5&&Math.abs(P[i].x-P[i-1].x)>=L)flat.push([P[i-1],P[i]]);
  if(!onBus){wireRuns+=flat.length;continue}
  for(const bid of rt.buses){const Q=buses[bid]?.points||[];for(let i=1;i<Q.length;i++)if(Q[i].y===Q[i-1].y&&Math.abs(Q[i].x-Q[i-1].x)>=L){busKeys.add(bid);break}}
  // A long stretch along a horizontal bus the wire rides is that bus's run; any other is the wire's own.
  const ends=Math.max(0,...rt.buses.map(hw));
  for(const [a,b] of flat){const y=a.y,lo=Math.min(a.x,b.x),hi=Math.max(a.x,b.x);
   const along=rt.buses.some(bid=>{const Q=buses[bid]?.points||[];for(let k=1;k<Q.length;k++)if(Q[k].y===Q[k-1].y&&Math.abs(Q[k].y-y)<=hw(bid)&&Math.min(Q[k].x,Q[k-1].x)<=lo+ends+1&&Math.max(Q[k].x,Q[k-1].x)>=hi-ends-1)return true;return false});
   if(!along)tapRuns++}
 }
 return {runs:wireRuns+tapRuns+busKeys.size,wireRuns,tapRuns,busRuns:busKeys.size,fallback,through};
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
        print(f"long horizontal runs (>= {LONG} px, cross-group): {m['runs']} ({m['wireRuns']} off buses + {m['tapRuns']} taps + "
              f"{m['busRuns']} buses), bound {MAX_LONG_RUNS} ({BASE_LONG_RUNS} at 3f3aa75); bus fallbacks {len(m['fallback'])}; "
              f"bus routes through a card {len(m['through'])}")
        assert m['runs'] <= MAX_LONG_RUNS, (m['runs'], MAX_LONG_RUNS)
        assert not m['fallback'], m['fallback'][:8]
        assert not m['through'], m['through'][:8]
        assert not errors, errors
        browser.close()


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        doc = node_part(tmp)
        twice_part(tmp)
        browser_part(doc)
    print('PASS channel buses QA')


if __name__ == '__main__':
    main()
