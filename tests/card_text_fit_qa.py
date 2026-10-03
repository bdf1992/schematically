"""A card's title and subtitle are one block inside the card (NOTATION-MODEL.md section 4).

- On the generated maps (frame 4 task lifecycle, frame 5 work-engine sample, the work-engine map),
  fitted as the editor fits them, no card's title overlaps its own subtitle and no title runs
  past its card (text-overflow 0).
- One card, 200 x 120, with a long title and a subtitle, across zooms 0.25 to 2: the title box and
  the visible subtitle box are apart by space.textGap or more and both sit inside the card body;
  where both cannot fit, the subtitle is hidden and says so (data-lod="hidden").
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

DOCS = [ROOT / 'tests' / 'fixtures' / 'task-lifecycle.sov',
        ROOT / 'tests' / 'fixtures' / 'work-engine-sample.sov',
        ROOT / 'docs' / 'workengine' / 'map.sov']
ZOOMS = [0.25, 0.5, 1, 2]

# A text-collision finding that pairs a card's own title with its own subtitle.
OWN = r"""()=>{const m=window.SovSchematicAPI.layout.metrics({static:true}),own=[];
  for(const f of m.findings){
    if(f.kind!=='text-collision'||f.ids.length!==2||f.ids[0]!==f.ids[1]||!f.ids[0])continue;
    const g=nodesG.querySelector(`.node[data-id="${CSS.escape(f.ids[0])}"]`);
    const t=g?.querySelector(':scope > text.component-label,:scope > text.outside-label'),u=g?.querySelector(':scope > text.component-subtitle');
    if(t&&u&&f.detail.includes(`"${t.textContent.trim()}"`)&&f.detail.includes(`"${u.textContent.trim()}"`))own.push(f.detail);
  }
  return {own,overflow:m.counts['text-overflow']||0,overflowDetail:m.findings.filter(f=>f.kind==='text-overflow').map(f=>f.detail).slice(0,5)}}"""

CARD = r"""()=>{const A=window.SovSchematicAPI;
  A.document.replace({schema:SovSchematicData.DOCUMENT_SCHEMA,id:'fit',components:[
    {id:'card',symbolId:'act',x:400,y:300,config:{label:'Worktree and branch for the bound task',subtitle:'claimed by the contractor seat',presentation:{size:{w:200,h:120}}}}],wires:[]});
  return SovSchematicNotation.tokens(diagram).space.textGap}"""

SET_ZOOM = "(z)=>{camera={x:400-BASE_VIEW.w/z/2,y:300-BASE_VIEW.h/z/2,w:BASE_VIEW.w/z,h:BASE_VIEW.h/z};applyCamera();return currentZoom()}"

MEASURE = r"""()=>{const g=nodesG.querySelector('.node[data-id="card"]'),w=200,h=120;
  const t=g.querySelector(':scope > text.component-label'),u=g.querySelector(':scope > text.component-subtitle');
  const box=el=>{const b=el.getBBox();return {l:b.x,r:b.x+b.width,t:b.y,b:b.y+b.height}};
  return {title:box(t),sub:box(u),subVisible:getComputedStyle(u).visibility!=='hidden',lod:u.dataset.lod||null,
    lines:[...t.querySelectorAll(':scope > tspan')].map(s=>s.textContent),glyph:componentInlineGraphicBox(nodes.find(x=>x.id==='card')),em:parseFloat(getComputedStyle(t).fontSize),body:{l:-w/2,r:w/2,t:-h/2,b:h/2}}}"""

inside = lambda a, R, tol=0.5: a['l'] >= R['l'] - tol and a['r'] <= R['r'] + tol and a['t'] >= R['t'] - tol and a['b'] <= R['b'] + tol

missing = [doc.relative_to(ROOT).as_posix() for doc in DOCS if not doc.exists()]

with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)

    docs = {}
    for doc in DOCS:
        if not doc.exists():
            continue
        page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [doc.read_text(encoding='utf-8'), doc.name])
        page.evaluate('()=>fitDiagram()')
        page.wait_for_timeout(300)
        docs[str(doc.relative_to(ROOT).as_posix())] = page.evaluate(OWN)

    gap = page.evaluate(CARD)
    page.wait_for_timeout(150)
    zooms = {}
    for z in ZOOMS:
        page.evaluate(SET_ZOOM, z)
        page.wait_for_timeout(150)  # the block is laid out again on the next frame after a zoom
        zooms[z] = page.evaluate(MEASURE)
    browser.close()

for name, r in docs.items():
    print(f"{name}: own title-subtitle collisions {len(r['own'])}, text-overflow {r['overflow']}")
for z, m in zooms.items():
    sep = round(m['sub']['t'] - m['title']['b'], 2)
    print(f"zoom {z}: title em {m['em']:.1f}, subtitle {'shown' if m['subVisible'] else 'hidden'} (lod {m['lod']}), gap {sep}, title lines {m['lines']}")
    print(f"  title box {m['title']}, subtitle box {m['sub']}, glyph {m['glyph']}")

assert not errors, errors
assert not missing, f'missing fixtures: {missing}'
assert gap == 3, f'space.textGap is {gap}, expected 3'
for name, r in docs.items():
    assert not r['own'], (name, 'a card title overlaps its own subtitle', r['own'][:5])
    assert r['overflow'] == 0, (name, 'text-overflow', r['overflowDetail'])
for z, m in zooms.items():
    assert inside(m['title'], m['body']), (z, 'title leaves the card body', m['title'], m['body'])
    if m['subVisible']:
        assert m['sub']['t'] - m['title']['b'] >= gap - 0.01, (z, 'subtitle closer to the title than textGap', m['title'], m['sub'])
        assert inside(m['sub'], m['body']), (z, 'subtitle leaves the card body', m['sub'], m['body'])
        assert m['lod'] is None, (z, 'a shown subtitle is not marked hidden', m['lod'])
    else:
        assert m['lod'] == 'hidden', (z, 'a hidden subtitle carries data-lod="hidden"', m['lod'])
# Where there is room (zoom 2: the title fits on one line) the subtitle is shown, not hidden by default.
assert zooms[2]['subVisible'], {z: m['subVisible'] for z, m in zooms.items()}
print('PASS card text fit QA')
