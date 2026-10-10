"""A card's title and subtitle are one block inside the card (NOTATION-MODEL.md section 4).

- On the generated maps (frame 4 task lifecycle, frame 5 work-engine sample, the work-engine map),
  fitted as the editor fits them, no card's title overlaps its own subtitle and no title runs
  past its card (text-overflow 0).
- One card, 200 x 120, with a long title and a subtitle, across zooms 0.25 to 2: the title box and
  the visible subtitle box are apart by space.textGap or more and both sit inside the card body;
  where both cannot fit, the subtitle is hidden and says so (data-lod="hidden").
- A title that needs three lines draws two, the second ending in an ellipsis, with
  data-truncated="true" and the full title in the card's tooltip; config.label is unchanged.
- A title drawn outside its card is one line, uncut, and its subtitle sits textGap under it.
- At screen scale 0.25 or less a title that runs into its glyph is hidden (data-lod="hidden").
- A lone title that needs two lines on a 112 x 84 card is drawn whole on two lines in a picture
  (screen scale 1): the glyph shrinks for it (glyphBox, keeping aspect, never below 60%).
- The full-text tooltip is a <title> on the card's group, never inside the drawn <text>.
- A one-word title ('Witness' on a default observe card) drawn 15% wider than here, or wider
  than the text width but within the full inner width (w - 8), is drawn whole.
- Every example exported (render.svg, the SVG export's own route) with every card title drawn at
  least 15% wider than glyphBox's width table estimates it: no title is cut but the case card of
  examples/09. The target is the same on every host, and stands in for fonts wider than this
  host's (DejaVu on Linux runs about 10% wider), so a glyph that keeps full height because the
  width table misjudges a wider font fails here.
- The editor at camera zoom 1 on a 1600 x 1000 viewport cuts no title in examples 04, 09 and 10:
  a title that would be cut shrinks below the 12 px screen floor, to 10 px at least, and carries
  data-shrunk="true"; every other title keeps the floor.
"""
from __future__ import annotations
import os
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
    titleLod:t.dataset.lod||null,titleVisible:getComputedStyle(t).visibility!=='hidden',screen:parseFloat(workspace.style.getPropertyValue('--zoom')),
    lines:[...t.querySelectorAll(':scope > tspan')].map(s=>s.textContent),glyph:componentInlineGraphicBox(nodes.find(x=>x.id==='card')),em:parseFloat(getComputedStyle(t).fontSize),body:{l:-w/2,r:w/2,t:-h/2,b:h/2}}}"""

# A title that needs three lines inside a card, and the same long title drawn outside its card.
# The card is 200 x 200: below a lone title's (larger) glyph, a 200 x 120 card has room for one line.
LONG_TITLE = 'Worktree and branch for the bound task under the contractor seat with its claim receipt and the queue state'
TWO_CARDS = r"""(title)=>{const A=window.SovSchematicAPI;
  A.document.replace({schema:SovSchematicData.DOCUMENT_SCHEMA,id:'fit-cut',components:[
    {id:'long',symbolId:'act',x:300,y:300,config:{label:title,presentation:{size:{w:200,h:200}}}},
    {id:'out',symbolId:'act',x:700,y:300,config:{label:title,subtitle:'claimed by the contractor seat',presentation:{size:{w:120,h:80},labelMode:'outside'}}},
    {id:'small',symbolId:'act',x:1000,y:300,config:{label:'Clock AND enable',presentation:{size:{w:112,h:84}}}},
    {id:'short',symbolId:'act',x:1200,y:300,config:{label:'Sensor',presentation:{size:{w:112,h:84}}}}],wires:[]});
  camera={x:500-BASE_VIEW.w/2,y:300-BASE_VIEW.h/2,w:BASE_VIEW.w,h:BASE_VIEW.h};applyCamera();return currentZoom()}"""
READ_TWO = r"""()=>{const read=(id,sel)=>{const g=nodesG.querySelector(`.node[data-id="${id}"]`),t=g.querySelector(sel),u=g.querySelector(':scope > text.component-subtitle');
    const b=t.getBBox(),bu=u?u.getBBox():null;
    return {lines:[...t.querySelectorAll(':scope > tspan')].map(s=>s.textContent),own:[...t.childNodes].filter(c=>c.nodeType===3).map(c=>c.textContent).join(''),
      truncated:t.dataset.truncated||null,title:g.querySelector(':scope > title.card-text-full')?.textContent??null,label:nodes.find(x=>x.id===id).config.label,
      textContent:t.textContent,innerTitle:t.querySelectorAll('title').length,
      box:{l:b.x,r:b.x+b.width,t:b.y,b:b.y+b.height},sub:bu?{t:bu.y,b:bu.y+bu.height}:null}};
  return {long:read('long',':scope > text.component-label'),out:read('out',':scope > text.outside-label')}}"""
# A small card (112 x 84) with a lone title that needs two lines, drawn as a picture draws it (screen
# scale 1, title 12 px): both lines whole, the glyph shrunk to make room (never below 60%); a short
# title on the same card keeps today's glyph.
READ_SMALL = r"""()=>{workspace.style.setProperty('--zoom','1');render();
  const read=id=>{const g=nodesG.querySelector(`.node[data-id="${id}"]`),t=g.querySelector(':scope > text.component-label'),b=t.getBBox(),n=nodes.find(x=>x.id===id);
    return {lines:[...t.querySelectorAll(':scope > tspan')].map(s=>s.textContent),truncated:t.dataset.truncated||null,glyph:componentInlineGraphicBox(n),top:b.y,em:parseFloat(getComputedStyle(t).fontSize)}};
  return {small:read('small'),short:read('short')}}"""

# A single word ('Witness', 7 letters) on a default-size observe card, as tests/beta20_ports_history_qa.py
# makes it, drawn with a font wider than this host's: letter-spacing widens the word to a target
# width. 'wider15' is 15% wider than here; 'between' puts it between the text width (w - 12) and the
# full inner width (w - 8), where only the one-word rule keeps it whole, so the check bites on any host.
WORD_CARD = "()=>window.SovSchematicAPI.create('component',{symbolId:'observe',x:360,y:280,config:{label:'Witness'}}).result.id"
WORD_WIDTHS = {'wider15': 1.15, 'between': None}
WORD_AT = r"""([id,factor])=>{const g0=()=>nodesG.querySelector(`.node[data-id="${id}"]`),n=nodes.find(x=>x.id===id),size=componentSize(n);
  let style=document.getElementById('word-width-probe');if(!style){style=document.createElement('style');style.id='word-width-probe';document.head.appendChild(style)}
  style.textContent='';render();
  const t0=g0().querySelector('text.component-label'),probe=t0.cloneNode(false);probe.textContent='Witness';g0().appendChild(probe);
  const natural=probe.getComputedTextLength(),base=parseFloat(getComputedStyle(probe).letterSpacing)||0;probe.remove();
  const target=factor?natural*factor:((size.w-12)+(size.w-8))/2;
  style.textContent=`.node[data-id="${id}"] text.component-label{letter-spacing:${base+(target-natural)/7}px !important}`;render();
  const t=g0().querySelector('text.component-label'),p2=t.cloneNode(false);p2.textContent='Witness';g0().appendChild(p2);const drawnWidth=p2.getComputedTextLength();p2.remove();
  const texts=[...g0().querySelectorAll('text')].map(x=>x.textContent);
  style.textContent='';render();
  return {natural,target,drawnWidth,max:size.w-12,wide:size.w-8,size,texts,truncated:t.dataset.truncated||null}}"""

# Every example, exported as scripts/export_svg.py exports it (render.svg, labels at screen scale 1),
# with each card title widened by letter-spacing to WIDER x the width glyphBox's width table
# estimates for it (titleWidth(title) x title size), the same target on every host. A title the host
# font already draws wider than that gets no spacing; nothing is narrowed. Returns the cards whose
# title the export draws cut, and how many titles were widened. CARD_TEXT_WIDER overrides WIDER
# (1.0 checks that nothing is cut at the table's own width).
EXAMPLES = sorted((ROOT / 'examples').glob('*.sov'))
WIDER = float(os.environ.get('CARD_TEXT_WIDER', '1.15'))
CUT_OK = {('09-print-ai-proof-run.sov', 'case')}
# The width table, copied byte for byte from src/03-notation-core.js; the copy is checked against
# the source below, so the test cannot drift from the product.
TABLE_JS = r"""const ADVANCE=[['iljI.,:;!|\'·',.3],['frt ()[]-',.38],['sJ"',.55],['mwMW',.88],['ABCDGHKNOQRUVXY&',.72],['EFLPSTZ',.64]];
function titleWidth(title){let em=0;for(const c of String(title||'')){const hit=ADVANCE.find(([cs])=>cs.includes(c));em+=hit?hit[1]:c>='A'&&c<='Z'?.68:.59}return em*.94}"""
WIDE_EXPORT = r"""(factor)=>{""" + TABLE_JS + r"""
  const ts=SovSchematicNotation.drawnSize(activeNotation().tokens.type,'title');
  const prev=workspace.style.getPropertyValue('--zoom');workspace.style.setProperty('--zoom','1');render();
  let style=document.getElementById('wide-font-probe');if(!style){style=document.createElement('style');style.id='wide-font-probe';document.head.appendChild(style)}
  style.textContent='';const rules=[];
  for(const g of nodesG.querySelectorAll('.node:not(.group)')){
    const n=nodes.find(x=>x.id===g.dataset.id);if(!n||componentForm(n).dimension!==2)continue;
    const t=g.querySelector(':scope > text.component-label');if(!t)continue;
    const full=t.dataset.full||t.textContent,probe=t.cloneNode(false);probe.textContent=full;g.appendChild(probe);
    const w=probe.getComputedTextLength(),base=parseFloat(getComputedStyle(probe).letterSpacing)||0;probe.remove();
    const chars=[...full].length,target=factor*titleWidth(full)*ts;if(!chars||target<=w)continue;
    rules.push(`.node[data-id="${CSS.escape(n.id)}"] > text.component-label{letter-spacing:${base+(target-w)/chars}px !important}`)}
  style.textContent=rules.join('\n');workspace.style.setProperty('--zoom',prev);render();
  const svg=window.SovSchematicAPI.render.svg({pad:48});
  style.textContent='';render();
  const doc=new DOMParser().parseFromString(svg,'image/svg+xml'),cut=[];
  for(const t of doc.querySelectorAll('text.component-label[data-truncated="true"]'))cut.push([t.closest('[data-id]')?.getAttribute('data-id')||'?',t.textContent]);
  return {widened:rules.length,cut}}"""

# The editor at camera zoom 1 on a 1600 x 1000 viewport (screen scale below 1, so the 12 px floor
# draws titles larger than the picture does): no title in 04, 09 or 10 is cut. A title that needs it
# shrinks, down to 10 px on screen, and carries data-shrunk.
EDITOR_EXAMPLES = ['04-boundary-port.sov', '09-print-ai-proof-run.sov', '10-clocked-signals.sov']
ZOOM_ONE = "()=>{const cx=camera.x+camera.w/2,cy=camera.y+camera.h/2;camera={x:cx-BASE_VIEW.w/2,y:cy-BASE_VIEW.h/2,w:BASE_VIEW.w,h:BASE_VIEW.h};applyCamera();return currentZoom()}"
READ_EDITOR = r"""()=>{const screen=parseFloat(workspace.style.getPropertyValue('--zoom')),out={zoom:currentZoom(),screen,cut:[],shrunk:[],floor:[]};
  for(const t of nodesG.querySelectorAll('.node > text.component-label')){
    const id=t.closest('.node').dataset.id,px=+(parseFloat(getComputedStyle(t).fontSize)*screen).toFixed(2),text=[...t.querySelectorAll('tspan')].map(s=>s.textContent);
    if(t.dataset.truncated==='true')out.cut.push([id,text]);
    if(t.dataset.shrunk==='true')out.shrunk.push([id,t.dataset.full,px]);
    else if(px<LABEL_FLOORS.general-0.05)out.floor.push([id,px])}
  return out}"""

inside = lambda a, R, tol=0.5: a['l'] >= R['l'] - tol and a['r'] <= R['r'] + tol and a['t'] >= R['t'] - tol and a['b'] <= R['b'] + tol

missing = [doc.relative_to(ROOT).as_posix() for doc in DOCS if not doc.exists()]
NOTATION_SRC = (ROOT / 'src' / '03-notation-core.js').read_text(encoding='utf-8')
assert all(line in NOTATION_SRC for line in TABLE_JS.splitlines()), 'the width table copy differs from src/03-notation-core.js'

with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)
    floors = page.evaluate('()=>LABEL_FLOORS')

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
    page.evaluate(TWO_CARDS, LONG_TITLE)
    page.wait_for_timeout(200)
    two = page.evaluate(READ_TWO)
    small = page.evaluate(READ_SMALL)
    word = {}
    page.evaluate('newSchematic()')
    wid = page.evaluate(WORD_CARD)
    page.wait_for_timeout(100)
    for name, factor in WORD_WIDTHS.items():
        word[name] = page.evaluate(WORD_AT, [wid, factor])
    wide_cuts = {}
    for doc in EXAMPLES:
        page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [doc.read_text(encoding='utf-8'), doc.name])
        page.evaluate('()=>fitDiagram()')
        page.wait_for_timeout(150)
        wide_cuts[doc.name] = page.evaluate(WIDE_EXPORT, WIDER)
    editor = {}
    for name in EDITOR_EXAMPLES:
        doc = ROOT / 'examples' / name
        page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [doc.read_text(encoding='utf-8'), doc.name])
        page.evaluate(ZOOM_ONE)
        page.wait_for_timeout(200)  # the block is laid out again on the next frame after a zoom
        editor[name] = page.evaluate(READ_EDITOR)
    browser.close()

for name, r in docs.items():
    print(f"{name}: own title-subtitle collisions {len(r['own'])}, text-overflow {r['overflow']}")
for z, m in zooms.items():
    sep = round(m['sub']['t'] - m['title']['b'], 2)
    print(f"zoom {z} (screen {m['screen']:.3f}): title em {m['em']:.1f}, title lod {m['titleLod']}, subtitle {'shown' if m['subVisible'] else 'hidden'} (lod {m['lod']}), gap {sep}, title lines {m['lines']}")
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
    # Zoomed far out (screen scale 0.25 or less) a title that runs into its glyph is hidden, not drawn over it.
    over_glyph = m['title']['t'] < m['glyph']['y'] + m['glyph']['h'] + 2 - 0.01
    if m['screen'] <= 0.25 and over_glyph:
        assert m['titleLod'] == 'hidden' and not m['titleVisible'], (z, 'a title over its glyph far out is hidden', m['titleLod'])
    if m['screen'] > 0.25:
        assert m['titleLod'] is None and m['titleVisible'], (z, 'a title is shown above screen scale 0.25', m['titleLod'])
assert zooms[0.25]['titleLod'] == 'hidden', ('zoom 0.25 hides the title that runs into its glyph', {z: m['titleLod'] for z, m in zooms.items()})
# Where there is room (zoom 2: the title fits on one line) the subtitle is shown, not hidden by default.
assert zooms[2]['subVisible'], {z: m['subVisible'] for z, m in zooms.items()}

# A title that needs three lines draws two, the second ending in an ellipsis; the full title stays
# in the data and in the hover <title>.
lng, out = two['long'], two['out']
print(f"three-line title: lines {lng['lines']}, data-truncated {lng['truncated']}, <title> {lng['title']!r}")
print(f"outside title: lines {out['lines']}, own text {out['own']!r}, box {out['box']}, subtitle {out['sub']}")
assert len(lng['lines']) == 2, ('a three-line title draws two lines', lng['lines'])
assert lng['lines'][1].endswith('…'), ('the second line ends in an ellipsis', lng['lines'])
assert lng['truncated'] == 'true', ('a cut title sets data-truncated', lng['truncated'])
assert lng['title'] == LONG_TITLE, ('the full title stays in the card\'s <title> tooltip', lng['title'])
# The tooltip sits on the card's group, never in the drawn text: a reader of the text's contents
# sees only what is drawn.
assert lng['innerTitle'] == 0 and lng['textContent'] == ''.join(lng['lines']), ('textContent of a cut title holds only the drawn text', lng['textContent'], lng['lines'])
assert lng['label'] == LONG_TITLE, ('config.label is never changed', lng['label'])
# A title drawn outside its card is one line, at its own width, uncut.
out_lines = out['lines'] or [out['own']]
assert len(out_lines) == 1 and out_lines[0] == LONG_TITLE, ('an outside title is one uncut line', out['lines'], out['own'])
assert out['box']['r'] - out['box']['l'] > 120, ('an outside title is not held to the card width', out['box'])
assert out['sub'] and out['sub']['t'] - out['box']['b'] >= gap - 0.01, ('the outside subtitle sits textGap under its title', out['box'], out['sub'])
# A lone title needing two lines on a 112 x 84 card gets them whole; the glyph shrinks for it, not for a short title.
sm, sh = small['small'], small['short']
print(f"small card: lines {sm['lines']}, truncated {sm['truncated']}, glyph {sm['glyph']}, title top {sm['top']:.1f}; short title glyph {sh['glyph']}")
assert sm['em'] == floors['general'],('the picture draws the title at 12 px', sm['em'])
assert sm['lines'] == ['Clock AND', 'enable'] and sm['truncated'] is None, ('a lone two-line title is drawn whole', sm['lines'], sm['truncated'])
assert sm['top'] >= sm['glyph']['y'] + sm['glyph']['h'] + 2 - 0.01, ('the two lines sit below the glyph', sm['top'], sm['glyph'])
# Today's glyph boxes on dev 2a366e0's glyphBox for a 112 x 84 card at title size 12: a two-line
# title leaves 80.64 x 24 (its floor), a one-line title 80.64 x 40.4.
TODAY_TWO, TODAY_ONE = (80.64, 24.0), (80.64, 40.4)
close = lambda box, wh: abs(box['w'] - wh[0]) < 0.01 and abs(box['h'] - wh[1]) < 0.01
assert close(sh['glyph'], TODAY_ONE), ('a one-line title keeps today\'s glyph', sh['glyph'])
assert 0.6 * TODAY_TWO[1] - 1e-6 <= sm['glyph']['h'] < TODAY_TWO[1], ('the glyph shrinks, never below 60%', sm['glyph'])
assert abs(sm['glyph']['w'] / sm['glyph']['h'] - TODAY_TWO[0] / TODAY_TWO[1]) < 1e-6, ('the glyph keeps its aspect', sm['glyph'])
# A one-word title may use the card's full inner width before it is cut; its text holds only the word.
for name, w in word.items():
    print(f"one word '{name}': natural {w['natural']:.1f}, drawn {w['drawnWidth']:.1f} (target {w['target']:.1f}), text width {w['max']}, inner width {w['wide']}, texts {w['texts']}")
    assert abs(w['drawnWidth'] - w['target']) < 0.5, (name, 'the probe widened the word to its target', w)
    assert w['texts'].count('Witness') == 1 and w['truncated'] is None and not any('…' in s for s in w['texts']), (name, 'a single word within the inner width is drawn whole', w['texts'])
assert word['between']['max'] < word['between']['drawnWidth'] <= word['between']['wide'], ('the bite case sits between text and inner width', word['between'])
# With every title 15% wider than here, the export cuts no example title but the case card's.
widened = sum(r['widened'] for r in wide_cuts.values())
unexpected = [(name, cid, text) for name, r in wide_cuts.items() for cid, text in r['cut'] if (name, cid) not in CUT_OK]
print(f"titles at {WIDER:.2f}x the width table's estimate: {widened} widened across {len(wide_cuts)} examples; cut {[(n, c, t) for n, r in wide_cuts.items() for c, t in r['cut']]}")
assert widened > 0 or WIDER <= 1.0, 'no title was widened'
assert not unexpected, (f'with titles at {WIDER:.2f}x the width table, the export cuts example titles', unexpected)
# The editor at camera zoom 1: nothing cut in 04, 09 and 10; a shrunk title stays at 10 px or more on
# screen, and a title that is not marked shrunk keeps the 12 px floor.
for name, e in editor.items():
    print(f"editor zoom {e['zoom']:.3f} (screen {e['screen']:.3f}) {name}: cut {e['cut']}, shrunk {e['shrunk']}")
    assert abs(e['zoom'] - 1) < 1e-6, (name, 'camera zoom 1', e['zoom'])
    assert not e['cut'], (name, 'the editor at zoom 1 cuts example titles', e['cut'])
    assert all(px >= floors['shrunkTitle'] - 0.05 for _, _, px in e['shrunk']), (name, 'a shrunk title reads at 10 px or more', e['shrunk'])
    assert not e['floor'], (name, 'a title below 12 px is marked data-shrunk', e['floor'])
print('PASS card text fit QA')
