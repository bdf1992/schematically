"""Layered groups QA: the layered layout places each group's members as one block.

src/08-layout-core.js layoutCanvas() lays a group's members out on their own, like a container's
interior, and places the block, padded as groupRect pads a region (24, 28 more on top), as one
node of the canvas (LAYOUT-MODEL.md "What layered does"; SECTION-MODEL.md "Never an obstacle").

Node part, each document laid out with scripts/layout_sov.mjs --out on a temp copy:
  - the seeded fixture (build_fixture), tests/fixtures/booth-record-graphify.sov and
    docs/workengine/map.sov: every card has a numeric x and y, no two cards overlap, no two group
    regions overlap; each document's region-pair count and card extent are printed;
  - two groups listing one card (g0 [a, b, c], g1 [c, d, e]): layout_sov exits 0, c lies inside
    g0's region and g0's region holds no card it does not list.
Browser part (index.html, the way scripts/layout_audit.py reads a document), on the fixture only:
  - group-overlap 0 and route-through-node 0, and crossings at most 1.10 times the crossings of
    the same fixture laid out with its groups removed; routes through a third group are printed;
  - a planted document whose two regions overlap counts group-overlap 1 naming both groups, and
    metrics().rubric has no group-overlap key;
  - the two-groups case counts exactly one group-overlap, g0 and g1, naming c.
Byte check, with --base REF: layout_sov.mjs and src/ from git merge-base HEAD REF, against the
working tree, on every group-free example and on the two fixtures with their groups removed;
the outputs are equal once meta.updatedAt is dropped. The base layout of the grouped fixture
must have a region aspect (union of group regions, width / height) above 2.5, so the check
bites on the code before groups packed into rows (5.19 at a902dca).

    python tests/layered_groups_qa.py [--base origin/dev]
"""
from __future__ import annotations
import argparse
import io
import json
import random
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECIMEN = ROOT / 'tests/fixtures/booth-record-graphify.sov'
MAP = ROOT / 'docs/workengine/map.sov'
PAD, BAND = 24, 28
CROSSING_RATIO = 1.10


def build_fixture(seed=7, sizes=(6, 9, 12, 7), cross=14):
    rnd = random.Random(seed)
    comps, groups, wires, members = [], [], [], []
    n = 0
    for k, size in enumerate(sizes):
        ids = [f"g{k}c{i}" for i in range(size)]
        members.append(ids)
        groups.append({"id": f"g{k}", "symbolId": "group", "config": {"label": f"Group {k}", "members": ids}})
        comps += [{"id": cid, "symbolId": "act", "config": {"label": f"Act {k}.{i}"}} for i, cid in enumerate(ids)]
        # Intra-group: each card after the first takes one wire from an earlier card, plus a few extra.
        for i in range(1, size):
            wires.append((ids[rnd.randrange(i)], ids[i]))
        for _ in range(size // 3):
            i, j = sorted(rnd.sample(range(size), 2))
            wires.append((ids[i], ids[j]))
    for _ in range(cross):
        a, b = sorted(rnd.sample(range(len(sizes)), 2))
        if rnd.random() < .2:
            a, b = b, a
        wires.append((rnd.choice(members[a]), rnd.choice(members[b])))
    seen, out = set(), []
    for a, b in wires:
        if (a, b) in seen:
            continue
        seen.add((a, b))
        out.append({"id": f"w{len(out)}", "a": a, "aSide": "out", "b": b, "bSide": "in"})
    return {"schema": "soveraeign.schematic/document@0.1", "id": "layered-groups-fixture",
            "meta": {"title": "Layered groups fixture"}, "components": groups + comps, "wires": out, "references": []}


def two_groups() -> dict:
    """g0 lists a, b, c; g1 lists c, d, e (GROUP_MEMBER_TWICE): c belongs to g0's block."""
    cards = [{'id': k, 'symbolId': 'act', 'config': {'label': k.upper()}} for k in 'abcde']
    groups = [{'id': 'g0', 'symbolId': 'group', 'config': {'label': 'G0', 'members': ['a', 'b', 'c']}},
              {'id': 'g1', 'symbolId': 'group', 'config': {'label': 'G1', 'members': ['c', 'd', 'e']}}]
    wires = [{'id': f'w{i}', 'a': a, 'aSide': 'out', 'b': b, 'bSide': 'in'} for i, (a, b) in enumerate(['ab', 'bc', 'cd', 'de'])]
    return {'schema': 'soveraeign.schematic/document@0.1', 'id': 'two-groups', 'meta': {'title': 'Two groups'},
            'components': groups + cards, 'wires': wires, 'references': []}


def planted() -> dict:
    """Two groups whose members are placed by hand so the regions overlap; no layout is run."""
    cards = [{'id': 'p1', 'symbolId': 'act', 'x': 200, 'y': 200, 'config': {'label': 'P1'}},
             {'id': 'p2', 'symbolId': 'act', 'x': 400, 'y': 200, 'config': {'label': 'P2'}},
             {'id': 'q1', 'symbolId': 'act', 'x': 300, 'y': 260, 'config': {'label': 'Q1'}},
             {'id': 'q2', 'symbolId': 'act', 'x': 500, 'y': 320, 'config': {'label': 'Q2'}}]
    groups = [{'id': 'pg', 'symbolId': 'group', 'x': 300, 'y': 200, 'config': {'label': 'PG', 'members': ['p1', 'p2']}},
              {'id': 'qg', 'symbolId': 'group', 'x': 400, 'y': 290, 'config': {'label': 'QG', 'members': ['q1', 'q2']}}]
    return {'schema': 'soveraeign.schematic/document@0.1', 'id': 'planted-group-overlap', 'meta': {'title': 'Planted'},
            'components': groups + cards, 'wires': [], 'references': []}


def is_group(c: dict) -> bool:
    return c.get('symbolId') == 'group'


def without_groups(doc: dict) -> dict:
    return {**doc, 'components': [c for c in doc['components'] if not is_group(c)]}


def card_rect(c: dict) -> tuple[float, float, float, float]:
    """l, r, t, b from x, y and config.presentation.size, 112x84 when absent."""
    size = ((c.get('config') or {}).get('presentation') or {}).get('size') or {}
    w, h = size.get('w', 112), size.get('h', 84)
    return c['x'] - w / 2, c['x'] + w / 2, c['y'] - h / 2, c['y'] + h / 2


def region(doc: dict, gid: str, only: list[str] | None = None) -> tuple[float, float, float, float]:
    """groupRect: the members' rectangles, padded 24, 28 more on top."""
    by_id = {c['id']: c for c in doc['components']}
    g = by_id[gid]
    rects = [card_rect(by_id[m]) for m in (only or g['config']['members']) if m in by_id and not is_group(by_id[m])
             and isinstance(by_id[m].get('x'), (int, float)) and isinstance(by_id[m].get('y'), (int, float))]
    return (min(r[0] for r in rects) - PAD, max(r[1] for r in rects) + PAD,
            min(r[2] for r in rects) - PAD - BAND, max(r[3] for r in rects) + PAD)


def overlap(a, b) -> bool:
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


def run_layout(root: Path, src: Path, dest: Path) -> subprocess.CompletedProcess:
    return subprocess.run(['node', str(root / 'scripts/layout_sov.mjs'), str(src), '--out', str(dest)],
                          cwd=root, capture_output=True, text=True)


def laid_out(doc: dict, tmp: Path, name: str, root: Path = ROOT) -> dict:
    src, dest = tmp / f'{name}.in.sov', tmp / f'{name}.sov'
    src.write_text(json.dumps(doc), encoding='utf-8')
    proc = run_layout(root, src, dest)
    assert proc.returncode == 0, (name, proc.stdout + proc.stderr)
    return json.loads(dest.read_text(encoding='utf-8'))


def region_pairs(doc: dict) -> tuple[int, int]:
    """Overlapping region pairs, and all pairs, over the groups on each canvas."""
    groups = [c for c in doc['components'] if is_group(c)]
    hit = total = 0
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            if (groups[i].get('canvasId') or 'canvas:global') != (groups[j].get('canvasId') or 'canvas:global'):
                continue
            total += 1
            hit += overlap(region(doc, groups[i]['id']), region(doc, groups[j]['id']))
    return hit, total


def check_document(doc: dict, name: str) -> None:
    cards = [c for c in doc['components'] if not is_group(c)]
    for c in cards:
        assert isinstance(c.get('x'), (int, float)) and isinstance(c.get('y'), (int, float)), f'{name}: {c["id"]} has no numeric position'
    rects = [(c['id'], c.get('canvasId') or 'canvas:global', card_rect(c)) for c in cards]
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            (ia, ca, ra), (ib, cb, rb) = rects[i], rects[j]
            assert ca != cb or not overlap(ra, rb), f'{name}: {ia} overlaps {ib}: {ra} vs {rb}'
    hit, total = region_pairs(doc)
    l = min(r[0] for _, _, r in rects); r_ = max(r[1] for _, _, r in rects)
    t = min(r[2] for _, _, r in rects); b = max(r[3] for _, _, r in rects)
    print(f'{name}: {len(cards)} cards, {hit} of {total} region pairs overlap, card extent {r_ - l:.0f} x {b - t:.0f}')
    assert hit == 0, f'{name}: {hit} of {total} group regions overlap'


def node_part(tmp: Path) -> dict:
    out = {}
    for name, doc in [('fixture', build_fixture()),
                      ('booth-record-graphify', json.loads(SPECIMEN.read_text(encoding='utf-8'))),
                      ('map', json.loads(MAP.read_text(encoding='utf-8')))]:
        placed = laid_out(doc, tmp, name)
        check_document(placed, name)
        out[name] = placed
    out['fixture-blind'] = laid_out(without_groups(build_fixture()), tmp, 'fixture-blind')

    two = laid_out(two_groups(), tmp, 'two-groups')
    by_id = {c['id']: c for c in two['components']}
    g0 = region(two, 'g0')
    c = card_rect(by_id['c'])
    assert g0[0] <= c[0] and c[1] <= g0[1] and g0[2] <= c[2] and c[3] <= g0[3], ('c lies outside g0', c, g0)
    for k in 'de':
        assert not overlap(card_rect(by_id[k]), g0), (f'{k} sits in g0 block', card_rect(by_id[k]), g0)
    print(f'two groups: c inside g0 {tuple(round(v) for v in g0)}; g0 holds only a, b, c')
    out['two-groups'] = two
    return out


# ---- Browser part -------------------------------------------------------------------------

THIRD = '''()=>{
  const groups=nodes.filter(isGroupComponent),R=new Map(groups.map(g=>[g.id,SovSchematicData.groupRect(diagram,g.id,componentSize)]));
  const of=new Map();for(const g of groups)for(const m of (g.config.members||[]))if(!of.has(m))of.set(m,g.id);
  let through=0,cross=0;
  for(const el of workspace.querySelectorAll('.wire-group')){
    const w=wires.find(x=>x.id===el.dataset.wireId),path=el.querySelector('path.wire');if(!w||!path)continue;
    const ga=of.get(w.a),gb=of.get(w.b);if(!ga||!gb||ga===gb)continue;cross++;
    const pts=layoutSamplePath(path);
    if(groups.some(g=>g.id!==ga&&g.id!==gb&&pts.some(p=>layoutInside(p,R.get(g.id),0))))through++;
  }
  return {through,cross};
}'''


def browser_part(docs: dict) -> None:
    from playwright.sync_api import sync_playwright
    from browser_runtime import chromium_launch_kwargs
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        errors: list[str] = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.set_content(html, wait_until='load'); page.wait_for_timeout(250)

        def metrics(doc: dict, name: str) -> dict:
            page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [json.dumps(doc), name])
            page.evaluate('()=>{ if (typeof fitDiagram === "function") fitDiagram(); }')
            page.wait_for_timeout(300)
            return page.evaluate('()=>window.SovSchematicAPI.layout.metrics({static:true})')

        grouped = metrics(docs['fixture'], 'fixture.sov')
        third = page.evaluate(THIRD)
        blind = metrics(docs['fixture-blind'], 'fixture-blind.sov')
        gc, bc = grouped['counts'], blind['counts']
        print(f"fixture: crossings {gc.get('crossing', 0)} grouped, {bc.get('crossing', 0)} group-blind "
              f"(bound {CROSSING_RATIO:.2f}x = {bc.get('crossing', 0) * CROSSING_RATIO:.1f}); "
              f"group-overlap {gc.get('group-overlap', 0)}, route-through-node {gc.get('route-through-node', 0)}; "
              f"{third['through']} of {third['cross']} cross-group routes pass through a third group's region")
        assert gc.get('group-overlap', 0) == 0, [f for f in grouped['findings'] if f['kind'] == 'group-overlap']
        assert gc.get('route-through-node', 0) == 0, [f for f in grouped['findings'] if f['kind'] == 'route-through-node']
        assert gc.get('crossing', 0) <= CROSSING_RATIO * bc.get('crossing', 0), (gc.get('crossing', 0), bc.get('crossing', 0))

        m = metrics(planted(), 'planted.sov')
        found = [f for f in m['findings'] if f['kind'] == 'group-overlap']
        assert len(found) == 1 and sorted(found[0]['ids']) == ['pg', 'qg'], found
        assert 'group-overlap' not in m['rubric'], 'group-overlap must carry no weight in the score'
        print(f"planted: {found[0]['detail']}; no rubric weight")

        # file.open refuses a card listed by two groups (validateDocument, GROUP_MEMBER_TWICE), so
        # the laid-out document is opened with g1 listing d and e, and c is put back into g1's
        # members in the page's own document before measuring.
        two = json.loads(json.dumps(docs['two-groups']))
        next(c for c in two['components'] if c['id'] == 'g1')['config']['members'] = ['d', 'e']
        page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [json.dumps(two), 'two-groups.sov'])
        page.evaluate('()=>{nodes.find(n=>n.id==="g1").config.members=["c","d","e"];render();if(typeof fitDiagram==="function")fitDiagram()}')
        page.wait_for_timeout(300)
        m = page.evaluate('()=>window.SovSchematicAPI.layout.metrics({static:true})')
        found = [f for f in m['findings'] if f['kind'] == 'group-overlap']
        assert len(found) == 1 and sorted(found[0]['ids']) == ['g0', 'g1'] and 'both list c' in found[0]['detail'], found
        print(f"two groups: {found[0]['detail']}")
        assert not errors, errors
        browser.close()


# ---- Byte check -----------------------------------------------------------------------------

def normalised(path: Path) -> str:
    doc = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(doc.get('meta'), dict):
        doc['meta'].pop('updatedAt', None)
    return json.dumps(doc, sort_keys=True)


def byte_check(ref: str, tmp: Path) -> None:
    mb = subprocess.run(['git', 'merge-base', 'HEAD', ref], cwd=ROOT, capture_output=True, text=True)
    assert mb.returncode == 0, mb.stderr
    base = mb.stdout.strip()
    tar = subprocess.run(['git', 'archive', '--format=tar', base, 'src', 'scripts/layout_sov.mjs'], cwd=ROOT, capture_output=True)
    assert tar.returncode == 0, tar.stderr.decode('utf-8', 'replace')
    old = tmp / 'base'
    old.mkdir()
    with tarfile.open(fileobj=io.BytesIO(tar.stdout)) as t:
        t.extractall(old, filter='data')
    cases: list[tuple[str, dict]] = []
    for path in sorted((ROOT / 'examples').rglob('*.sov')):
        doc = json.loads(path.read_text(encoding='utf-8'))
        if not any(is_group(c) for c in doc.get('components') or []):
            cases.append((str(path.relative_to(ROOT)).replace('\\', '/'), doc))
    cases.append(('fixture without groups', without_groups(build_fixture())))
    cases.append(('booth-record-graphify without groups', without_groups(json.loads(SPECIMEN.read_text(encoding='utf-8')))))
    for i, (name, doc) in enumerate(cases):
        src = tmp / f'byte{i}.in.sov'
        src.write_text(json.dumps(doc), encoding='utf-8')
        a, b = tmp / f'byte{i}.base.sov', tmp / f'byte{i}.head.sov'
        pa, pb = run_layout(old, src, a), run_layout(ROOT, src, b)
        assert pa.returncode == pb.returncode, (name, pa.stdout + pa.stderr, pb.stdout + pb.stderr)
        if pa.returncode == 0:
            assert normalised(a) == normalised(b), f'{name}: layout differs from base {base[:7]}'
    based = laid_out(build_fixture(), tmp, 'fixture-base', root=old)
    regions = [region(based, c['id']) for c in based['components'] if is_group(c)]
    aspect = (max(r[1] for r in regions) - min(r[0] for r in regions)) / (max(r[3] for r in regions) - min(r[2] for r in regions))
    assert aspect > 2.5, f'base {base[:7]} lays the grouped fixture out with region aspect {aspect:.2f}, not above 2.5: the check does not bite'
    print(f'byte check: {len(cases)} group-free documents equal to base {base[:7]}; base lays the fixture out with region aspect {aspect:.2f}')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base')
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        if a.base:
            byte_check(a.base, tmp)
        else:
            print('byte check skipped: pass --base origin/dev')
        docs = node_part(tmp)
        browser_part(docs)
    print('PASS layered groups QA')


if __name__ == '__main__':
    main()
