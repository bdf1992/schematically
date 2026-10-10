"""Wire label placement QA: a wire label sits clear of cards, other text and other wires, or says so.

placeWireLabels (src/55-render.js) first tries the wire's midpoint and each segment's midpoint, on
both sides of the line, then slides the label along the wire: on every straight run at least as
long as the label plus twice the clearance, a place every 12 screen pixels on both sides, nearest
the wire's midpoint first. It takes the first place clear with the 6 px clearance; else a place
clear with no padding; else the place of least overlap. A label whose place truly overlaps a card,
a container border, other text or another wire carries data-label-crowded="true"
(LAYOUT-MODEL.md "Wire labels").

A label collision is a text-collision finding of SovSchematicAPI.layout.metrics({static: true})
that names the label's wire and quotes the label's text. Static metrics measure the picture: the
document drawn again with labels at their base size (withPictureLabels, src/75-persistence.js). The
crowded marks are read in that same drawing, so a mark and a finding describe one placement. The
marks in the fitted view on screen, where labels hold a 12 px floor, are printed and not asserted.

The page asks for system-ui, so text is as wide as the reader's own font makes it. The two fixtures
are measured twice: under the page's own font and under a wide one (WIDE_FONT, set on a second page
before a document opens). Every line printed names its font.

- tests/fixtures/task-lifecycle.sov: 0 label collisions under both fonts. w5 'push, through the
  broker' has a clear place under both fonts, on one line or two: the GitHub plane stands far enough
  from Commits for either (tests/wire_label_wrap_qa.py holds the place itself).
- tests/fixtures/work-engine-sample.sov: 0 label collisions under both fonts.
- On both, under both fonts, every label named in a label collision is marked crowded and no other
  label is.
- A document built here, 12 act cards and 14 wires with labels of 8 to 30 characters, arranged by
  SovSchematicAPI.layout.apply({engine: 'layered'}): 0 label collisions and 0 crowded labels. In its
  picture (renderStandaloneSvg) no label box overlaps a card body. It is asserted under the page's
  own font; its numbers under the wide font are printed, not asserted.
- docs/workengine/map.sov: its numbers are printed under both fonts, not asserted.
- The page logs no errors.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

FIXTURES = [ROOT / 'tests' / 'fixtures' / 'task-lifecycle.sov', ROOT / 'tests' / 'fixtures' / 'work-engine-sample.sov']
MAP = ROOT / 'docs' / 'workengine' / 'map.sov'
# A font wider than this host's system-ui, as GitHub's runner draws text. Given to a page through
# add_style_tag before a document opens; the product never sets a font for it.
WIDE_FONT = '*{font-family:Verdana,"DejaVu Sans",sans-serif !important}'
FONTS = {"the page's own font": None, 'the wide font': WIDE_FONT}

# Every connection label as the picture draws it, each text-collision finding that names its wire
# and quotes its text, and the wires marked crowded in the fitted view on screen.
READ = r"""()=>{
  const read=()=>[...workspace.querySelectorAll('.wire-group[data-wire-id] .connection-label')].map(t=>({
    wire:t.closest('.wire-group').dataset.wireId,text:t.textContent.trim(),crowded:t.dataset.labelCrowded==='true'}));
  const fitted=read().filter(l=>l.crowded).map(l=>l.wire);
  const metrics=SovSchematicAPI.layout.metrics({static:true});
  const labels=withPictureLabels(read);
  const hits=[];
  for(const f of metrics.findings){
    if(f.kind!=='text-collision')continue;
    for(const l of labels)if((f.ids||[]).includes(l.wire)&&String(f.detail||'').includes(`"${l.text}"`))hits.push({wire:l.wire,text:l.text,detail:f.detail});
  }
  return {labels,hits,fitted,zoom:Number(workspace.style.getPropertyValue('--zoom')),textCollisions:metrics.counts['text-collision']||0};
}"""

# In a standalone picture: each label box against every card body that is not a container.
PICTURE = r"""()=>{
  const overlap=(a,b,tol)=>a.left<b.right-tol&&a.right>b.left+tol&&a.top<b.bottom-tol&&a.bottom>b.top+tol;
  const captions=[...document.querySelectorAll('.wire-group[data-wire-id] .connection-label')].map(t=>({id:t.closest('.wire-group').dataset.wireId,r:t.getBoundingClientRect()}));
  const cards=[...document.querySelectorAll('.node:not(.is-container)[data-id] > .body')].map(el=>({id:el.parentElement.dataset.id,r:el.getBoundingClientRect()}));
  const bad=[];
  for(const c of captions)for(const card of cards)if(overlap(c.r,card.r,.5))bad.push([c.id,card.id]);
  return {captions:captions.length,cards:cards.length,bad};
}"""

# 12 act cards and 14 labelled wires. The labels run from 8 to 30 characters.
CARDS = ['Intake', 'Triage', 'Estimate', 'Contract', 'Launch', 'Build', 'Audit', 'Land', 'Observe', 'Retro', 'Archive', 'Report']
WIRES = [
    (0, 1, 'new work'),
    (0, 2, 'sized by its points'),
    (1, 3, 'ranked, then written up'),
    (2, 3, 'points and a time estimate'),
    (3, 4, 'checked contract'),
    (3, 5, 'paths the engineer may write'),
    (4, 6, 'a seat and a model, named once'),
    (5, 6, 'commit on the branch'),
    (6, 7, 'accepted'),
    (2, 8, 'what was measured'),
    (8, 9, 'signals over a window'),
    (9, 10, 'lessons kept'),
    (10, 11, 'tombstone and receipt'),
    (7, 11, 'landed on the base'),
]


def generated() -> dict:
    assert len(CARDS) == 12 and len(WIRES) == 14
    assert min(len(w[2]) for w in WIRES) == 8 and max(len(w[2]) for w in WIRES) == 30, sorted(len(w[2]) for w in WIRES)
    return {
        'schema': 'soveraeign.schematic/document@0.1', 'id': 'wire-label-placement-qa',
        'meta': {'title': 'Wire label placement QA'},
        # A starting grid, so the page has something to draw before layout.apply arranges it.
        'components': [{'id': f'c{i}', 'symbolId': 'act', 'x': 260 * (i % 4), 'y': 180 * (i // 4), 'config': {'label': name}}
                       for i, name in enumerate(CARDS)],
        'wires': [{'id': f'w{i}', 'a': f'c{a}', 'aSide': 'out', 'b': f'c{b}', 'bSide': 'in', 'config': {'label': label}}
                  for i, (a, b, label) in enumerate(WIRES)],
    }


def show(page, text: str, name: str, arrange: bool = False) -> dict:
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [text, name])
    if arrange:
        receipt = page.evaluate("()=>SovSchematicAPI.layout.apply({engine:'layered'})")
        assert receipt['ok'], receipt
    page.evaluate('()=>fitDiagram()')
    page.wait_for_timeout(300)
    return page.evaluate(READ)


def summary(r: dict) -> dict:
    return {'labels': len(r['labels']), 'label collisions': len(r['hits']),
            'labels in a collision': len({h['wire'] for h in r['hits']}),
            'crowded': len([l for l in r['labels'] if l['crowded']]), 'text-collision': r['textCollisions'],
            'fitted zoom': round(r['zoom'], 2), 'crowded in the fitted view': len(r['fitted'])}


def open_page(browser, errors: list, style: str | None = None):
    """A page holding index.html; with a style, every text on it is drawn in that font."""
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    if style:
        page.add_style_tag(content=style)
    page.wait_for_timeout(250)
    return page


def main() -> None:
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = open_page(browser, errors)
        wide_page = open_page(browser, errors, WIDE_FONT)

        by_font = {font: {f.name: show(pg, f.read_text(encoding='utf-8'), f.name) for f in FIXTURES}
                   for font, pg in zip(FONTS, (page, wide_page))}
        wide_map = show(wide_page, MAP.read_text(encoding='utf-8'), MAP.name)
        wide_made = show(wide_page, json.dumps(generated()), 'wire-label-placement-qa.sov', arrange=True)
        the_map = show(page, MAP.read_text(encoding='utf-8'), MAP.name)
        made = show(page, json.dumps(generated()), 'wire-label-placement-qa.sov', arrange=True)
        svg = page.evaluate('()=>renderStandaloneSvg()')
        after_picture = page.evaluate(READ)
        picture_page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        picture_page.set_content(svg, wait_until='load')
        picture = picture_page.evaluate(PICTURE)
        browser.close()

    own, wide = FONTS
    for font, fixtures in by_font.items():
        for name, r in fixtures.items():
            print(f'{font}:', name, summary(r), [h['detail'] for h in r['hits']])
    print(f'{own}:', 'map.sov', summary(the_map), [h['detail'] for h in the_map['hits']])
    print(f'{wide}:', 'map.sov', summary(wide_map), [h['detail'] for h in wide_map['hits']], '(printed, not asserted)')
    print(f'{own}:', 'generated', summary(made), [h['detail'] for h in made['hits']])
    print(f'{wide}:', 'generated', summary(wide_made), [h['detail'] for h in wide_made['hits']], '(printed, not asserted)')
    print(f'{own}:', 'generated picture', {'captions': picture['captions'], 'cards': picture['cards'], 'label over card': picture['bad']})

    assert not errors, ('the page logs no errors', errors)

    # Each font is held to the same assertions; a failure under one does not hide the other's.
    failed = []
    for font, fixtures in by_font.items():
        try:
            lifecycle, sample = fixtures['task-lifecycle.sov'], fixtures['work-engine-sample.sov']
            assert lifecycle['labels'] and sample['labels'], (font, 'the fixtures have connection labels')
            assert not lifecycle['hits'], (font, 'task-lifecycle.sov: 0 label collisions', lifecycle['hits'])
            assert not sample['hits'], (font, 'work-engine-sample.sov: 0 label collisions', sample['hits'])
            for name, r in fixtures.items():
                colliding = {h['wire'] for h in r['hits']}
                marked = {l['wire'] for l in r['labels'] if l['crowded']}
                assert colliding <= marked, (font, name, 'every label in a text-collision carries data-label-crowded', sorted(colliding - marked))
                assert marked <= colliding, (font, name, 'no other label carries data-label-crowded', sorted(marked - colliding))
        except AssertionError as failure:
            failed.append(failure.args[0])
    assert not failed, failed

    assert len(made['labels']) == 14, ('generated: every wire draws its label', len(made['labels']))
    assert not made['hits'], ('generated: 0 label collisions', made['hits'])
    crowded = [l for l in made['labels'] if l['crowded']]
    assert not crowded, ('generated: 0 crowded labels', crowded)
    assert picture['captions'] == 14 and picture['cards'] == 12, ('generated picture: every label and card is drawn', picture)
    assert not picture['bad'], ('generated picture: no connection-label box overlaps a card body', picture['bad'])
    assert after_picture == made, ('generated: making the picture leaves the labels where they were', after_picture, made)
    print('PASS wire label placement QA')


if __name__ == '__main__':
    main()
