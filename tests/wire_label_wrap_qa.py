"""Wire label wrap QA: a label with no clear one-line place wraps onto two lines that have one.

placeWireLabels (src/55-render.js) places a label on one line by its three tiers. Only when that
place truly overlaps something and the caption has a word break, the label is set on two lines at
the break whose wider line is narrowest (the earlier break on a tie) and placed again by the same
tiers. It stays on two lines only where the two-line box meets nothing; otherwise it goes back to
one line at the one-line place and is marked crowded (LAYOUT-MODEL.md "As built: wire labels").

A wrapped label is one text element, class connection-label, with data-wrapped="true" and two tspan
children: both with the label's x, the first with dy 0, the second with dy 1.15em. Every connection
label keeps its whole caption in data-caption.

Headless Chromium on index.html at 1600 by 1000, each document after fitDiagram(). "The picture" is
the drawing static metrics and exports measure: labels at base size (withPictureLabels).

Two fonts. The page asks for system-ui, so a caption is as wide as the reader's own font makes it:
Segoe UI on this host, a wider sans on GitHub's runner, where one line can fit a gap that needs two
here and the other way round. The product draws in the reader's font, so nothing here pins one.
Everything read from a fixture, and (i) to (l), is asserted twice: under the page's own font and
under a wide one (WIDE_FONT of tests/wire_label_placement_qa.py, set on a second page before a
document opens). What is asserted is what holds under any font: the label is clear, and it wraps
when and only when one line has no clear place. Every line printed names its font.

(a) tests/fixtures/task-lifecycle.sov, picture: the label of w5 carries data-caption 'push, through
    the broker', is not crowded, and its box meets no card body, no container border, no other text
    and no other wire. When it is wrapped it has two tspans that share the label's x and whose
    texts joined by one space are the caption.
(b) In task-lifecycle.sov, tests/fixtures/work-engine-sample.sov and docs/workengine/map.sov, in
    the picture, a label is wrapped only if with the wrap step switched off it is marked crowded,
    and every label that is not wrapped has the x, y and textContent it has with the wrap step
    switched off. The switch is window.SOV_QA_NO_WIRE_LABEL_WRAP, a flag only a test sets; both
    readings are taken in one picture render, by placeWireLabels() with and without it, so the
    values are compared exactly.
(c) A document built here, two act cards 60 apart joined by a wire whose one-word label is wider
    than the gap: the label keeps one line and is marked crowded. (The page's own font only.)
(d) placeWireLabels() run three times leaves every label's x, y and lines unchanged.
(e) After a camera zoom to 2 and back, the picture's labels are as before (within 0.01: two picture
    renders place a caption about 1e-4 apart).
(f) renderStandaloneSvg() carries the w5 label as the canvas has it, wrapped or not: the same
    data-wrapped and data-caption and the same lines with the same x and dy; loaded as its own
    page the label's box is the canvas picture's within 0.5. The page draws the picture at the
    canvas's own screen scale: Chromium measures a text box about 3.5 units wider on the left at
    scale 1 than at the fitted 0.28, for every label, one line or two.
(g) SovSchematicAPI.layout.metrics({static: true}) reports no text-collision naming w5, and
    SovSchematicAPI.layout.contrast({static: true}) no text-contrast naming w5, in light and dark.
(h) The page logs no errors.
(i) The w5 label's box, taken 0.1 world unit inside its edges, is crossed by no segment of w5 (the
    points wireLabelPaths holds for its path).
(j) The narrow document, the fixture with the GitHub plane back where it stood (the eleven x values
    lowered by D): its w5 label is marked crowded or its box is crossed by no segment of w5. A
    label never sits across a leg of its own wire and says nothing.
(k) A document built here, two act cards on one row 300 apart joined by a straight wire labelled
    'ok': the label is on one line, not crowded, its centre x within 0.5 of the wire's midpoint x
    and its box 6 screen pixels above the wire (within 0.5 px). A wire with no other leg is placed
    as it was before a label counted its own wire.
(l) The wrap itself, free of any font: two act cards on one row joined by a straight wire labelled
    'alpha beta gamma delta', the gap between the card bodies set to the mean (to the whole unit)
    of the label's one-line width and its two-line width as the page measures them in the picture.
    The label is wrapped at a word break into two tspans sharing its x, is not crowded, and three
    runs of placeWireLabels() leave it unchanged.

It prints, without asserting, the count of wrapped labels in each fitted view on screen, the
generated document of tests/wire_label_placement_qa.py included.

--snapshot DIR writes the picture of tests/fixtures/task-lifecycle.sov into DIR.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402
from wire_label_placement_qa import FONTS, generated, open_page  # noqa: E402

LIFECYCLE = ROOT / 'tests' / 'fixtures' / 'task-lifecycle.sov'
SAMPLE = ROOT / 'tests' / 'fixtures' / 'work-engine-sample.sov'
MAP = ROOT / 'docs' / 'workengine' / 'map.sov'
WIRE, CAPTION = 'w5', 'push, through the broker'
ONE_WORD = 'Supercalifragilisticexpialidocious'
SHORT, WORDS = 'ok', 'alpha beta gamma delta'
SNAPSHOT_NAME = 'tests__fixtures__task-lifecycle.svg'
# The room for w5: the GitHub plane and everything right of it stand D further right than they did,
# so the label has a clear place under both fonts. MOVED are the eleven cards that moved. Measured
# 2026-10-05 in the picture at 1600 by 1000, the eleven x values at their old value plus D. 'Clear'
# is: not crowded, no leg of w5 across the box, no text-collision or cramped-label finding naming
# w5, no other label crowded or in a label collision.
#
#   D    the page's own font (Segoe UI)             the wide font (Verdana)
#   0    one line, crowded, overlaps Commits         one line, crowded, overlaps Commits
#   20   one line, crowded, overlaps Commits         one line, crowded, overlaps Commits
#   40   two lines, clear                            one line, crowded, overlaps Commits
#   60   two lines, clear                            one line, clear
#   80   two lines, clear                            one line, clear
#   100  one line, clear                             one line, clear
#   120  one line, clear                             one line, clear
#
# 60 is the smallest offset clear under both. Without the own-wire rule the label at D 0 sat across
# two legs of w5 under the page's own font and was counted clear, which (j) holds against.
D = 60
MOVED = ('github', 'gh-push', 'gh-fail', 'gh-merge', 'gh-drop', 'pr', 'checks', 'merged', 'landing', 'tomb', 'abandoned')

# Every connection label as it is drawn now.
LABELS = r"""()=>[...workspace.querySelectorAll('.wire-group[data-wire-id] .connection-label')].map(t=>({
  wire:t.closest('.wire-group').dataset.wireId,x:t.getAttribute('x'),y:t.getAttribute('y'),text:t.textContent,
  caption:t.dataset.caption??null,wrapped:t.dataset.wrapped??null,crowded:t.dataset.labelCrowded??null,
  lines:[...t.querySelectorAll('tspan')].map(s=>({text:s.textContent,x:s.getAttribute('x'),dy:s.getAttribute('dy')}))}))"""

# One picture render: the labels, the labels after three more placements, the labels with the wrap
# step switched off, and what the box of one wire's label meets, in world units.
PICTURE = r"""(wire)=>withPictureLabels(()=>{
  const labels=LABELS;
  const first=labels();
  for(let i=0;i<3;i++)placeWireLabels();
  const thrice=labels();
  const inverse=workspace.getScreenCTM().inverse();
  const world=el=>{const r=el.getBoundingClientRect(),a=new DOMPoint(r.left,r.top).matrixTransform(inverse),b=new DOMPoint(r.right,r.bottom).matrixTransform(inverse);return {l:a.x,t:a.y,r:b.x,b:b.y}};
  const overlap=(a,b)=>a.l<b.r-.1&&a.r>b.l+.1&&a.t<b.b-.1&&a.b>b.t+.1;
  const label=workspace.querySelector(`.wire-group[data-wire-id="${wire}"] .connection-label`),meets=[],own=[];
  let box=null,points=[];
  if(label){
    box=world(label);
    // The label's own wire: each drawn segment that enters the box taken .1 inside its edges.
    const drawn=[...label.parentElement.querySelectorAll('path')].find(p=>wireLabelPaths.has(p));
    points=drawn?wireLabelPaths.get(drawn).map(p=>({x:p.x,y:p.y})):[];
    const inner={l:box.l+.1,r:box.r-.1,t:box.t+.1,b:box.b-.1};
    for(let i=1;i<points.length;i++){
      const a=points[i-1],b=points[i];let lo=0,hi=1,hit=true;
      for(const [start,delta,min,max] of [[a.x,b.x-a.x,inner.l,inner.r],[a.y,b.y-a.y,inner.t,inner.b]]){
        if(Math.abs(delta)<1e-9){if(start<min||start>max){hit=false;break}continue}
        const u=(min-start)/delta,v=(max-start)/delta;
        lo=Math.max(lo,Math.min(u,v));hi=Math.min(hi,Math.max(u,v));if(lo>hi){hit=false;break}
      }
      if(hit)own.push([[a.x,a.y],[b.x,b.y]]);
    }
    for(const el of workspace.querySelectorAll('.node:not(.is-container)>.body'))if(overlap(box,world(el)))meets.push(['card',el.parentElement.dataset.id]);
    for(const el of workspace.querySelectorAll('.node.is-container>.body')){
      const o=world(el);if(overlap(box,o)&&!(box.l>o.l&&box.r<o.r&&box.t>o.t&&box.b<o.b))meets.push(['border',el.parentElement.dataset.id]);
    }
    for(const el of workspace.querySelectorAll('#groupLayer text,#nodes text,#wires text')){
      if(el===label||el.closest('.wire-packet')||!el.textContent.trim()||!el.getClientRects().length)continue;
      if(overlap(box,world(el)))meets.push(['text',el.textContent]);
    }
    for(const path of workspace.querySelectorAll('.wire-group path.wire')){
      if(path.parentElement===label.parentElement)continue;
      const length=path.getTotalLength();
      for(let at=0;at<=length;at+=1){
        const q=path.getPointAtLength(at);
        if(q.x>box.l&&q.x<box.r&&q.y>box.t&&q.y<box.b){meets.push(['wire',path.parentElement.dataset.wireId]);break}
      }
    }
  }
  window.SOV_QA_NO_WIRE_LABEL_WRAP=true;
  let plain;
  try{placeWireLabels();plain=labels()}finally{delete window.SOV_QA_NO_WIRE_LABEL_WRAP;placeWireLabels()}
  const matrix=workspace.getScreenCTM();
  return {first,thrice,plain,again:labels(),box,meets,own,points:points.map(p=>[p.x,p.y]),scale:Math.hypot(matrix.a,matrix.b)};
})""".replace('LABELS', LABELS)

# A document of two cards and one wire, in the picture: its label, the label after three more
# placements, its box and the wire's drawn points in world units, the gap between the two card
# bodies, and the screen scale.
ROW = r"""()=>withPictureLabels(()=>{
  const labels=LABELS;
  const first=labels();
  for(let i=0;i<3;i++)placeWireLabels();
  const thrice=labels();
  const matrix=workspace.getScreenCTM(),inverse=matrix.inverse();
  const world=el=>{const r=el.getBoundingClientRect(),a=new DOMPoint(r.left,r.top).matrixTransform(inverse),b=new DOMPoint(r.right,r.bottom).matrixTransform(inverse);return {l:a.x,t:a.y,r:b.x,b:b.y}};
  const label=workspace.querySelector('.connection-label');
  const drawn=[...label.parentElement.querySelectorAll('path')].find(p=>wireLabelPaths.has(p));
  const bodies=[...workspace.querySelectorAll('.node:not(.is-container)>.body')].map(world).sort((a,b)=>a.l-b.l);
  return {first,thrice,box:world(label),points:wireLabelPaths.get(drawn).map(p=>[p.x,p.y]),gap:bodies[1].l-bodies[0].r,scale:Math.hypot(matrix.a,matrix.b)};
})""".replace('LABELS', LABELS)

# The widths of a caption as the page measures them in the picture, in world units: on one line,
# and the wider of the two lines wireLabelLines breaks it into.
WIDTHS = r"""(caption)=>withPictureLabels(()=>{
  const label=workspace.querySelector('.connection-label'),matrix=workspace.getScreenCTM(),scale=Math.hypot(matrix.a,matrix.b);
  delete label.dataset.wrapped;
  const lines=wireLabelLines(label,caption);
  const wide=text=>{label.textContent=text;return label.getBoundingClientRect().width/scale};
  const one=wide(caption),two=Math.max(...lines.map(wide));
  label.textContent=caption;placeWireLabels();
  return {one,two,lines};
})"""

# The label of one wire in a standalone picture, in the picture's own units.
STANDALONE = r"""([wire,scale])=>{
  const label=document.querySelector(`.wire-group[data-wire-id="${wire}"] .connection-label`);
  const svg=label.ownerSVGElement,view=svg.viewBox.baseVal;
  svg.setAttribute('width',view.width*scale);svg.setAttribute('height',view.height*scale);
  svg.style.width=view.width*scale+'px';svg.style.height=view.height*scale+'px';
  const inverse=svg.getScreenCTM().inverse(),r=label.getBoundingClientRect();
  const a=new DOMPoint(r.left,r.top).matrixTransform(inverse),b=new DOMPoint(r.right,r.bottom).matrixTransform(inverse);
  return {box:{l:a.x,t:a.y,r:b.x,b:b.y},x:label.getAttribute('x'),caption:label.dataset.caption??null,wrapped:label.dataset.wrapped??null,
    lines:[...label.querySelectorAll('tspan')].map(s=>({text:s.textContent,x:s.getAttribute('x'),dy:s.getAttribute('dy')}))};
}"""

FINDINGS = r"""(wire)=>{
  const out={};
  for(const theme of ['light','dark']){
    SovSchematicAPI.view.setAppearance(theme);
    const metrics=SovSchematicAPI.layout.metrics({static:true}),contrast=SovSchematicAPI.layout.contrast({static:true});
    out[theme]={collisions:metrics.findings.filter(f=>f.kind==='text-collision'&&(f.ids||[]).includes(wire)).map(f=>f.detail),
      contrast:contrast.findings.filter(f=>f.kind==='text-contrast'&&(f.ids||[]).includes(wire)).map(f=>f.detail)};
  }
  SovSchematicAPI.view.setAppearance('light');
  return out;
}"""

ZOOM = r"""()=>{
  const saved={...camera};
  zoomAt(2/currentZoom());
  const at=currentZoom(),wrapped=workspace.querySelectorAll('.connection-label[data-wrapped="true"]').length;
  camera=saved;applyCamera();
  return {at,wrapped};
}"""


def one_word_document() -> dict:
    """Two act cards 120 wide whose facing edges are 60 apart, and a one-word label wider than that."""
    size = {'presentation': {'size': {'w': 120, 'h': 80}}}
    return {
        'schema': 'soveraeign.schematic/document@0.1', 'id': 'wire-label-wrap-qa', 'meta': {'title': 'Wire label wrap QA'},
        'components': [{'id': 'a', 'symbolId': 'act', 'x': 0, 'y': 0, 'config': {'label': 'A', **size}},
                       {'id': 'b', 'symbolId': 'act', 'x': 180, 'y': 0, 'config': {'label': 'B', **size}}],
        'wires': [{'id': 'x0', 'a': 'a', 'aSide': 'out', 'b': 'b', 'bSide': 'in', 'config': {'label': ONE_WORD}}],
    }


def row_document(label: str, gap: float) -> dict:
    """Two act cards 120 wide on one row, their facing edges gap apart, joined by one labelled wire."""
    size = {'presentation': {'size': {'w': 120, 'h': 80}}}
    return {
        'schema': 'soveraeign.schematic/document@0.1', 'id': 'wire-label-row-qa', 'meta': {'title': 'Wire label row QA'},
        'components': [{'id': 'a', 'symbolId': 'act', 'x': 0, 'y': 0, 'config': {'label': 'A', **size}},
                       {'id': 'b', 'symbolId': 'act', 'x': 120 + gap, 'y': 0, 'config': {'label': 'B', **size}}],
        'wires': [{'id': 'x0', 'a': 'a', 'aSide': 'out', 'b': 'b', 'bSide': 'in', 'config': {'label': label}}],
    }


def narrow_document() -> str:
    """The fixture with the GitHub plane back where it stood: the eleven x values lowered by D."""
    doc = json.loads(LIFECYCLE.read_text(encoding='utf-8'))
    moved = [c for c in doc['components'] if c['id'] in MOVED]
    assert len(moved) == len(MOVED) == 11, ('the fixture holds the eleven moved cards', [c['id'] for c in moved])
    for c in moved:
        c['x'] -= D
    return json.dumps(doc)


def open_document(page, text: str, name: str) -> None:
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [text, name])
    page.evaluate('()=>fitDiagram()')
    page.wait_for_timeout(300)


def start(p):
    errors: list[str] = []
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)
    return browser, page, errors


def place(label: dict) -> tuple:
    return label['wire'], label['x'], label['y'], label['text']


def close(a: list, b: list) -> list:
    """The labels of a that are not, within 0.01, the labels of b."""
    out = []
    if len(a) != len(b):
        return [('count', len(a), len(b))]
    for p, q in zip(a, b):
        same = (p['wire'], p['text'], p['wrapped'], p['crowded'], [l['text'] for l in p['lines']]) == \
               (q['wire'], q['text'], q['wrapped'], q['crowded'], [l['text'] for l in q['lines']])
        if not same or abs(float(p['x']) - float(q['x'])) > .01 or abs(float(p['y']) - float(q['y'])) > .01:
            out.append((p, q))
    return out


def snapshot_mode(target: Path) -> int:
    target.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser, page, errors = start(p)
        open_document(page, LIFECYCLE.read_text(encoding='utf-8'), LIFECYCLE.name)
        svg = page.evaluate('()=>renderStandaloneSvg({pad:48})')
        browser.close()
    out = target / SNAPSHOT_NAME
    out.write_text(svg, encoding='utf-8', newline='\n')
    print(f'wrote {out} ({len(svg.encode("utf-8"))} bytes)')
    assert not errors, ('the page logs no errors', errors)
    return 0


def measure(browser, style: str | None) -> dict:
    """Everything the assertions read, on one page; with a style, every text on it is in that font."""
    errors: list[str] = []
    page = open_page(browser, errors, style)
    pictures, fitted = {}, {}
    for path in (LIFECYCLE, SAMPLE, MAP):
        open_document(page, path.read_text(encoding='utf-8'), path.name)
        fitted[path.name] = page.evaluate(LABELS)
        pictures[path.name] = page.evaluate(PICTURE, WIRE)

    # The rest of the fixture readings take task-lifecycle.sov again.
    open_document(page, LIFECYCLE.read_text(encoding='utf-8'), LIFECYCLE.name)
    before = page.evaluate('()=>withPictureLabels(' + LABELS + ')')
    zoom = page.evaluate(ZOOM)
    after = page.evaluate('()=>withPictureLabels(' + LABELS + ')')
    canvas = page.evaluate(PICTURE, WIRE)
    svg = page.evaluate('()=>renderStandaloneSvg()')
    standalone_page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    standalone_page.set_content(svg, wait_until='load')
    if style:
        standalone_page.add_style_tag(content=style)
    standalone = standalone_page.evaluate(STANDALONE, [WIRE, canvas['scale']])
    standalone_page.close()
    findings = page.evaluate(FINDINGS, WIRE)

    open_document(page, narrow_document(), LIFECYCLE.name)
    narrow = page.evaluate(PICTURE, WIRE)

    open_document(page, json.dumps(row_document(SHORT, 300)), 'wire-label-row-qa.sov')
    short = page.evaluate(ROW)

    # (l): a first document wide enough for one line gives the two widths; the second has the gap.
    open_document(page, json.dumps(row_document(WORDS, 600)), 'wire-label-row-qa.sov')
    widths = page.evaluate(WIDTHS, WORDS)
    gap = round((widths['one'] + widths['two']) / 2)
    open_document(page, json.dumps(row_document(WORDS, gap)), 'wire-label-row-qa.sov')
    words = page.evaluate(ROW)

    out = {'pictures': pictures, 'fitted': fitted, 'before': before, 'zoom': zoom, 'after': after, 'canvas': canvas,
           'standalone': standalone, 'findings': findings, 'narrow': narrow, 'short': short, 'widths': widths, 'gap': gap,
           'words': words, 'errors': errors}
    if style is None:
        open_document(page, json.dumps(generated()), 'wire-label-placement-qa.sov')
        out['receipt'] = page.evaluate("()=>SovSchematicAPI.layout.apply({engine:'layered'})")
        page.evaluate('()=>fitDiagram()')
        page.wait_for_timeout(300)
        fitted['generated'] = page.evaluate(LABELS)

        open_document(page, json.dumps(one_word_document()), 'wire-label-wrap-qa.sov')
        out['one_word_gap'] = page.evaluate("()=>{const a=componentBounds(nodes.find(n=>n.id==='a')),b=componentBounds(nodes.find(n=>n.id==='b'));return b.l-a.r}")
        out['one_word_fitted'] = page.evaluate(LABELS)
        out['one_word'] = page.evaluate("()=>withPictureLabels(()=>{const t=workspace.querySelector('.connection-label'),m=workspace.getScreenCTM();"
                                        "return {labels:(" + LABELS + ")(),width:t.getBoundingClientRect().width/Math.hypot(m.a,m.b)}})")
    page.close()
    return out


def rounded(box: dict) -> dict:
    return {k: round(v, 2) for k, v in box.items()}


def report(font: str, m: dict) -> None:
    pictures, canvas, standalone = m['pictures'], m['canvas'], m['standalone']
    lifecycle = pictures[LIFECYCLE.name]
    label = next(l for l in lifecycle['first'] if l['wire'] == WIRE)
    print(f"{font}: {LIFECYCLE.name} picture: {WIRE} lines {[l['text'] for l in label['lines']] or 'one line'} caption {label['caption']!r} "
          f"x {label['x']} y {label['y']} tspans x {[l['x'] for l in label['lines']]} dy {[l['dy'] for l in label['lines']]} "
          f"crowded {label['crowded']} box {rounded(lifecycle['box'])} meets {lifecycle['meets']} "
          f"{WIRE} points {lifecycle['points']} own segments across the box {lifecycle['own']}")
    for name, r in pictures.items():
        wrapped = [l['wire'] for l in r['first'] if l['wrapped']]
        moved = [(a['wire'], place(a), place(b)) for a, b in zip(r['first'], r['plain']) if place(a) != place(b)]
        print(f"{font}: {name} picture: {len(r['first'])} labels, wrapped {wrapped}, crowded {[l['wire'] for l in r['first'] if l['crowded']]}; "
              f"with the wrap step off: wrapped {[l['wire'] for l in r['plain'] if l['wrapped']]}, "
              f"crowded {[l['wire'] for l in r['plain'] if l['crowded']]}, labels that differ {[x[0] for x in moved]}")
    for name, labels in m['fitted'].items():
        print(f"{font}: {name} fitted view: {len(labels)} labels, {len([l for l in labels if l['wrapped']])} wrapped "
              f"{[l['wire'] for l in labels if l['wrapped']]}, {len([l for l in labels if l['crowded']])} crowded")
    if 'one_word' in m:
        one_word = m['one_word']
        print(f"{font}: one word: gap {m['one_word_gap']}, label {round(one_word['width'], 2)} wide, picture "
              f"{[(l['text'], l['wrapped'], l['crowded'], len(l['lines'])) for l in one_word['labels']]}, "
              f"fitted view {[(l['wrapped'], l['crowded']) for l in m['one_word_fitted']]}")
    print(f"{font}: zoom: camera zoom {round(m['zoom']['at'], 4)} with {m['zoom']['wrapped']} wrapped, then back; "
          f"labels that differ in the picture {len(close(m['before'], m['after']))}")
    print(f"{font}: standalone at scale {round(canvas['scale'], 4)}: wrapped {standalone['wrapped']} lines {standalone['lines']} "
          f"box {rounded(standalone['box'])} canvas box {rounded(canvas['box'])}")
    print(f"{font}: findings naming {WIRE}: {m['findings']}")
    narrow = m['narrow']
    there = next(l for l in narrow['first'] if l['wire'] == WIRE)
    print(f"{font}: narrow document (the eleven x values lowered by {D}): {WIRE} lines {[l['text'] for l in there['lines']] or 'one line'} "
          f"crowded {there['crowded']} box {rounded(narrow['box'])} {WIRE} points {narrow['points']} own segments across the box {narrow['own']}")
    short = m['short']
    print(f"{font}: '{SHORT}' on a straight wire, cards {round(short['gap'], 2)} apart: {[(l['text'], l['x'], l['y'], l['wrapped'], l['crowded']) for l in short['first']]} "
          f"box {rounded(short['box'])} wire {short['points']} screen scale {round(short['scale'], 4)}")
    words = m['words']
    print(f"{font}: '{WORDS}': one line {round(m['widths']['one'], 2)} wide, two lines {round(m['widths']['two'], 2)} {m['widths']['lines']}, "
          f"cards {round(words['gap'], 2)} apart: {[([s['text'] for s in l['lines']], l['x'], l['y'], l['wrapped'], l['crowded']) for l in words['first']]} "
          f"box {rounded(words['box'])}")


def crossed(label: dict, own: list) -> str:
    return f"crowded {label['crowded']}, own segments across the box {own}"


def check(font: str, m: dict) -> None:
    pictures, canvas, standalone = m['pictures'], m['canvas'], m['standalone']
    lifecycle = pictures[LIFECYCLE.name]
    label = next(l for l in lifecycle['first'] if l['wire'] == WIRE)
    lines = [l['text'] for l in label['lines']]
    # (a)
    assert label['caption'] == CAPTION, (font, '(a) w5 keeps its caption in data-caption', label['caption'])
    assert label['crowded'] is None, (font, '(a) w5 is not crowded', label)
    assert not lifecycle['meets'], (font, '(a) the w5 label box meets no card body, container border, other text or other wire', lifecycle['meets'])
    if label['wrapped']:
        assert len(lines) == 2 and ' '.join(lines) == CAPTION, (font, '(a) wrapped, w5 has two lines that joined by one space are the caption', label)
        assert all(l['x'] == label['x'] for l in label['lines']), (font, '(a) both tspans share the label x', label)
        assert [l['dy'] for l in label['lines']] == ['0', '1.15em'], (font, '(a) the lines are dy 0 and dy 1.15em', label['lines'])
    else:
        assert not lines and label['text'] == CAPTION, (font, '(a) on one line, w5 has no tspan and reads its caption', label)
    # (b)
    for name, r in pictures.items():
        assert r['first'], (font, name, 'draws connection labels')
        assert all(l['caption'] is not None for l in r['first']), (font, '(b) every connection label carries data-caption', name)
        assert not [l['wire'] for l in r['plain'] if l['wrapped'] or l['lines']], (font, '(b) the flag switches the wrap step off', name)
        off = {l['wire']: l for l in r['plain']}
        wrapped = [l for l in r['first'] if l['wrapped'] or l['lines']]
        needless = [l['wire'] for l in wrapped if off[l['wire']]['crowded'] != 'true']
        assert not needless, (font, '(b) a label is wrapped only if it is crowded with the wrap step off', name, needless)
        moved = [(place(l), place(off[l['wire']])) for l in r['first'] if l not in wrapped and place(l) != place(off[l['wire']])]
        assert not moved, (font, '(b) every label that is not wrapped has the x, y and text it has with the wrap step off', name, moved)
        assert not close(r['again'], r['first']), (font, '(b) placing again with the flag gone gives the first picture', name, close(r['again'], r['first'])[:3])
    # (d)
    assert lifecycle['thrice'] == lifecycle['first'], (font, '(d) three more placements leave every label unchanged',
                                                       [(a, b) for a, b in zip(lifecycle['first'], lifecycle['thrice']) if a != b])
    # (e)
    assert abs(m['zoom']['at'] - 2) < 1e-6, (font, '(e) the camera reached zoom 2', m['zoom'])
    assert not close(m['before'], m['after']), (font, '(e) after a zoom to 2 and back the picture is as before', close(m['before'], m['after'])[:3])
    # (f)
    assert standalone['wrapped'] == label['wrapped'] and standalone['caption'] == CAPTION, (font, '(f) the picture keeps data-wrapped and data-caption', standalone)
    assert [l['text'] for l in standalone['lines']] == lines and [l['dy'] for l in standalone['lines']] == [l['dy'] for l in label['lines']] \
        and all(l['x'] == standalone['x'] for l in standalone['lines']), (font, '(f) the picture carries the same lines with the same x and dy', standalone)
    apart = {k: abs(standalone['box'][k] - canvas['box'][k]) for k in 'ltrb'}
    assert max(apart.values()) <= .5, (font, '(f) the label box in the picture is the canvas box within 0.5', apart)
    # (g)
    for theme, found in m['findings'].items():
        assert not found['collisions'], (font, '(g) no text-collision names w5', theme, found['collisions'])
        assert not found['contrast'], (font, '(g) no text-contrast names w5', theme, found['contrast'])
    # (i)
    assert len(lifecycle['points']) >= 2, (font, '(i) w5 has drawn points', lifecycle['points'])
    assert not lifecycle['own'], (font, '(i) the w5 label box is crossed by no segment of w5', crossed(label, lifecycle['own']), rounded(lifecycle['box']))
    # (j)
    narrow = m['narrow']
    there = next(l for l in narrow['first'] if l['wire'] == WIRE)
    assert there['crowded'] == 'true' or not narrow['own'], (
        font, '(j) narrow document: the w5 label is marked crowded or its box is crossed by no segment of w5',
        crossed(there, narrow['own']), rounded(narrow['box']))
    # (k)
    short, only = m['short'], m['short']['first']
    assert abs(short['gap'] - 300) < .01, (font, '(k) the cards are 300 apart', short['gap'])
    assert len(only) == 1 and only[0]['text'] == SHORT and not only[0]['lines'] and only[0]['wrapped'] is None, (font, '(k) a short label keeps one line', only)
    assert only[0]['crowded'] is None, (font, '(k) and is not crowded', only)
    (ax, ay), (bx, by) = short['points'][0], short['points'][-1]
    assert abs(ay - by) < .01, (font, '(k) the wire is straight', short['points'])
    centre = (short['box']['l'] + short['box']['r']) / 2
    assert abs(centre - (ax + bx) / 2) <= .5, (font, "(k) the label's centre x is the wire's midpoint x within 0.5", centre, (ax + bx) / 2)
    above = (ay - short['box']['b']) * short['scale']
    assert abs(above - 6) <= .5, (font, '(k) the label box is 6 screen pixels above the wire', above)
    assert short['thrice'] == only, (font, '(k) three more placements leave it unchanged', short['thrice'])
    # (l)
    widths, words, both = m['widths'], m['words'], m['words']['first']
    assert widths['two'] + 12 < m['gap'] < widths['one'] - 12, (font, '(l) the gap lies between the two-line and the one-line width', widths, m['gap'])
    assert abs(words['gap'] - m['gap']) < .01, (font, '(l) the cards are that far apart', words['gap'], m['gap'])
    assert len(both) == 1 and both[0]['wrapped'] == 'true' and both[0]['caption'] == WORDS, (font, '(l) the label is wrapped', both)
    broken = [l['text'] for l in both[0]['lines']]
    assert len(broken) == 2 and all(broken) and ' '.join(broken) == WORDS and broken == widths['lines'], (font, '(l) into two lines at a word break', broken)
    assert all(l['x'] == both[0]['x'] for l in both[0]['lines']), (font, '(l) both tspans share the label x', both)
    assert both[0]['crowded'] is None, (font, '(l) and is not crowded', both)
    assert words['thrice'] == both, (font, '(l) three more placements leave it unchanged', words['thrice'])
    # (h)
    assert not m['errors'], (font, '(h) the page logs no errors', m['errors'])


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        measured = {font: measure(browser, style) for font, style in FONTS.items()}
        browser.close()
    for font, m in measured.items():
        report(font, m)
    for font, m in measured.items():
        check(font, m)

    # (c), on the page's own font.
    m = next(iter(measured.values()))
    gap, one_word = m['one_word_gap'], m['one_word']
    assert gap == 60 and one_word['width'] > gap, ('(c) the cards are 60 apart and the label is wider', gap, one_word['width'])
    only = one_word['labels']
    assert len(only) == 1 and only[0]['text'] == ONE_WORD and not only[0]['lines'] and only[0]['wrapped'] is None, ('(c) a one-word label keeps one line', only)
    assert only[0]['crowded'] == 'true', ('(c) and is marked crowded', only)
    assert m['receipt']['ok'], m['receipt']
    print('PASS wire label wrap QA')
    return 0


if __name__ == '__main__':
    args = sys.argv[1:]
    if args[:1] == ['--snapshot'] and len(args) == 2:
        raise SystemExit(snapshot_mode(Path(args[1])))
    if args:
        raise SystemExit('usage: python tests/wire_label_wrap_qa.py [--snapshot DIR]')
    raise SystemExit(main())
