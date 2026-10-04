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

(a) tests/fixtures/task-lifecycle.sov, picture: the label of w5 is wrapped into 'push, through' and
    'the broker', carries data-caption 'push, through the broker', is not crowded, both tspans share
    the label's x, and its box meets no card body, no container border, no other text and no other
    wire.
(b) No other label of task-lifecycle.sov, tests/fixtures/work-engine-sample.sov or
    docs/workengine/map.sov is wrapped in the picture, and each has the x, y and textContent it has
    with the wrap step switched off. The switch is window.SOV_QA_NO_WIRE_LABEL_WRAP, a flag only a
    test sets; both readings are taken in one picture render, by placeWireLabels() with and without
    it, so the values are compared exactly.
(c) A document built here, two act cards 60 apart joined by a wire whose one-word label is wider
    than the gap: the label keeps one line and is marked crowded.
(d) placeWireLabels() run three times leaves the wrapped label's x, y and lines unchanged.
(e) After a camera zoom to 2 and back, the picture's labels are as before (within 0.01: two picture
    renders place a caption about 1e-4 apart).
(f) renderStandaloneSvg() carries the two tspans with the same x and dy, and loaded as its own page
    the label's box is the canvas picture's within 0.5. The page draws the picture at the canvas's
    own screen scale: Chromium measures a text box about 3.5 units wider on the left at scale 1
    than at the fitted 0.28, for every label, one line or two.
(g) SovSchematicAPI.layout.metrics({static: true}) reports no text-collision naming w5, and
    SovSchematicAPI.layout.contrast({static: true}) no text-contrast naming w5, in light and dark.
(h) The page logs no errors.

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
from wire_label_placement_qa import generated  # noqa: E402

LIFECYCLE = ROOT / 'tests' / 'fixtures' / 'task-lifecycle.sov'
SAMPLE = ROOT / 'tests' / 'fixtures' / 'work-engine-sample.sov'
MAP = ROOT / 'docs' / 'workengine' / 'map.sov'
WIRE, CAPTION, LINES = 'w5', 'push, through the broker', ['push, through', 'the broker']
ONE_WORD = 'Supercalifragilisticexpialidocious'
SNAPSHOT_NAME = 'tests__fixtures__task-lifecycle.svg'

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
  const label=workspace.querySelector(`.wire-group[data-wire-id="${wire}"] .connection-label`),meets=[];
  let box=null;
  if(label){
    box=world(label);
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
  return {first,thrice,plain,again:labels(),box,meets,scale:Math.hypot(matrix.a,matrix.b)};
})""".replace('LABELS', LABELS)

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


def main() -> int:
    with sync_playwright() as p:
        browser, page, errors = start(p)
        pictures, fitted = {}, {}
        for path in (LIFECYCLE, SAMPLE, MAP):
            open_document(page, path.read_text(encoding='utf-8'), path.name)
            fitted[path.name] = page.evaluate(LABELS)
            pictures[path.name] = page.evaluate(PICTURE, WIRE)

        # The rest reads task-lifecycle.sov again.
        open_document(page, LIFECYCLE.read_text(encoding='utf-8'), LIFECYCLE.name)
        before = page.evaluate('()=>withPictureLabels(' + LABELS + ')')
        zoom = page.evaluate(ZOOM)
        after = page.evaluate('()=>withPictureLabels(' + LABELS + ')')
        canvas = page.evaluate(PICTURE, WIRE)
        svg = page.evaluate('()=>renderStandaloneSvg()')
        standalone_page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        standalone_page.set_content(svg, wait_until='load')
        standalone = standalone_page.evaluate(STANDALONE, [WIRE, canvas['scale']])
        standalone_page.close()
        findings = page.evaluate(FINDINGS, WIRE)

        open_document(page, json.dumps(generated()), 'wire-label-placement-qa.sov')
        receipt = page.evaluate("()=>SovSchematicAPI.layout.apply({engine:'layered'})")
        page.evaluate('()=>fitDiagram()')
        page.wait_for_timeout(300)
        fitted['generated'] = page.evaluate(LABELS)

        open_document(page, json.dumps(one_word_document()), 'wire-label-wrap-qa.sov')
        gap = page.evaluate("()=>{const a=componentBounds(nodes.find(n=>n.id==='a')),b=componentBounds(nodes.find(n=>n.id==='b'));return b.l-a.r}")
        one_word_fitted = page.evaluate(LABELS)
        one_word = page.evaluate("()=>withPictureLabels(()=>{const t=workspace.querySelector('.connection-label'),m=workspace.getScreenCTM();"
                                 "return {labels:(" + LABELS + ")(),width:t.getBoundingClientRect().width/Math.hypot(m.a,m.b)}})")
        browser.close()

    lifecycle = pictures[LIFECYCLE.name]
    label = next(l for l in lifecycle['first'] if l['wire'] == WIRE)
    print(f"{LIFECYCLE.name} picture: {WIRE} lines {[l['text'] for l in label['lines']]} caption {label['caption']!r} "
          f"x {label['x']} y {label['y']} tspans x {[l['x'] for l in label['lines']]} dy {[l['dy'] for l in label['lines']]} "
          f"crowded {label['crowded']} box {({k: round(v, 2) for k, v in lifecycle['box'].items()})} meets {lifecycle['meets']}")
    for name, r in pictures.items():
        wrapped = [l['wire'] for l in r['first'] if l['wrapped']]
        moved = [(a['wire'], place(a), place(b)) for a, b in zip(r['first'], r['plain']) if place(a) != place(b)]
        print(f"{name} picture: {len(r['first'])} labels, wrapped {wrapped}, crowded {[l['wire'] for l in r['first'] if l['crowded']]}; "
              f"with the wrap step off: wrapped {[l['wire'] for l in r['plain'] if l['wrapped']]}, "
              f"crowded {[l['wire'] for l in r['plain'] if l['crowded']]}, labels that differ {[m[0] for m in moved]}")
    for name, labels in fitted.items():
        print(f"{name} fitted view: {len(labels)} labels, {len([l for l in labels if l['wrapped']])} wrapped "
              f"{[l['wire'] for l in labels if l['wrapped']]}, {len([l for l in labels if l['crowded']])} crowded")
    print(f"one word: gap {gap}, label {round(one_word['width'], 2)} wide, picture {[(l['text'], l['wrapped'], l['crowded'], len(l['lines'])) for l in one_word['labels']]}, "
          f"fitted view {[(l['wrapped'], l['crowded']) for l in one_word_fitted]}")
    print(f"zoom: camera zoom {round(zoom['at'], 4)} with {zoom['wrapped']} wrapped, then back; labels that differ in the picture {len(close(before, after))}")
    print(f"standalone at scale {round(canvas['scale'], 4)}: lines {standalone['lines']} box {({k: round(v, 2) for k, v in standalone['box'].items()})} "
          f"canvas box {({k: round(v, 2) for k, v in canvas['box'].items()})}")
    print(f'findings naming {WIRE}: {findings}')

    # (a)
    assert label['wrapped'] == 'true' and [l['text'] for l in label['lines']] == LINES, ('(a) w5 is wrapped into two lines', label)
    assert label['caption'] == CAPTION, ('(a) w5 keeps its caption in data-caption', label['caption'])
    assert label['crowded'] is None, ('(a) w5 is not crowded', label)
    assert all(l['x'] == label['x'] for l in label['lines']), ('(a) both tspans share the label x', label)
    assert [l['dy'] for l in label['lines']] == ['0', '1.15em'], ('(a) the lines are dy 0 and dy 1.15em', label['lines'])
    assert not lifecycle['meets'], ('(a) the w5 label box meets no card body, container border, other text or other wire', lifecycle['meets'])
    # (b)
    for name, r in pictures.items():
        assert r['first'], (name, 'draws connection labels')
        assert all(l['caption'] is not None for l in r['first']), ('(b) every connection label carries data-caption', name)
        others = [l for l in r['first'] if not (name == LIFECYCLE.name and l['wire'] == WIRE)]
        wrapped = [l['wire'] for l in others if l['wrapped'] or l['lines']]
        assert not wrapped, ('(b) no other label is wrapped in the picture', name, wrapped)
        assert not [l['wire'] for l in r['plain'] if l['wrapped'] or l['lines']], ('(b) the flag switches the wrap step off', name)
        plain = {l['wire']: place(l) for l in r['plain']}
        moved = [(place(l), plain.get(l['wire'])) for l in others if place(l) != plain.get(l['wire'])]
        assert not moved, ('(b) every other label has the x, y and text it has with the wrap step off', name, moved)
        assert not close(r['again'], r['first']), ('(b) placing again with the flag gone gives the first picture', name, close(r['again'], r['first'])[:3])
    # (c)
    assert gap == 60 and one_word['width'] > gap, ('(c) the cards are 60 apart and the label is wider', gap, one_word['width'])
    only = one_word['labels']
    assert len(only) == 1 and only[0]['text'] == ONE_WORD and not only[0]['lines'] and only[0]['wrapped'] is None, ('(c) a one-word label keeps one line', only)
    assert only[0]['crowded'] == 'true', ('(c) and is marked crowded', only)
    # (d)
    assert lifecycle['thrice'] == lifecycle['first'], ('(d) three more placements leave every label unchanged',
                                                       [(a, b) for a, b in zip(lifecycle['first'], lifecycle['thrice']) if a != b])
    # (e)
    assert abs(zoom['at'] - 2) < 1e-6, ('(e) the camera reached zoom 2', zoom)
    assert not close(before, after), ('(e) after a zoom to 2 and back the picture is as before', close(before, after)[:3])
    # (f)
    assert standalone['wrapped'] == 'true' and standalone['caption'] == CAPTION, ('(f) the picture keeps data-wrapped and data-caption', standalone)
    assert [l['text'] for l in standalone['lines']] == LINES and [l['dy'] for l in standalone['lines']] == ['0', '1.15em'] \
        and all(l['x'] == standalone['x'] for l in standalone['lines']), ('(f) the picture carries the two tspans with the same x and dy', standalone)
    apart = {k: abs(standalone['box'][k] - canvas['box'][k]) for k in 'ltrb'}
    assert max(apart.values()) <= .5, ('(f) the label box in the picture is the canvas box within 0.5', apart)
    # (g)
    for theme, found in findings.items():
        assert not found['collisions'], ('(g) no text-collision names w5', theme, found['collisions'])
        assert not found['contrast'], ('(g) no text-contrast names w5', theme, found['contrast'])
    assert receipt['ok'], receipt
    # (h)
    assert not errors, ('(h) the page logs no errors', errors)
    print('PASS wire label wrap QA')
    return 0


if __name__ == '__main__':
    args = sys.argv[1:]
    if args[:1] == ['--snapshot'] and len(args) == 2:
        raise SystemExit(snapshot_mode(Path(args[1])))
    if args:
        raise SystemExit('usage: python tests/wire_label_wrap_qa.py [--snapshot DIR]')
    raise SystemExit(main())
