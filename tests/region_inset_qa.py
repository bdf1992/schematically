"""Region inset QA: a region keeps a declared inset between its edge, its title and its children.

The schematic notation declares space.regionInset 24 and space.regionTitle 28; groupRect pads a
group's members by them, and layout.metrics reports `region-inset` (no weight in the score) for a
child that comes closer than regionInset to its container's core edge, or closer than regionTitle
to the top edge when the container draws a label or a glyph at its head.

- tests/fixtures/work-engine-sample.sov: region-inset fires on its hugging planes (the evidence the
  finding fires); after SovSchematicAPI.layout.apply({engine: 'layered'}) it is 0.
- a plane with one child 6 from its left core edge: exactly one region-inset, naming both.
- groupRect of a planted group is the union of its members padded 24 and 28.
- docs/workengine/map.sov: the count is printed.
- the page logs no errors.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

SAMPLE = ROOT / 'tests' / 'fixtures' / 'work-engine-sample.sov'
MAP = ROOT / 'docs' / 'workengine' / 'map.sov'
KIND = 'region-inset'

METRICS = "()=>SovSchematicAPI.layout.metrics({static:true})"
GROUP_RECT = r"""()=>{
  const size=c=>({w:100,h:60}),r=SovSchematicData.groupRect(diagram,'g1',size);
  return {r,tokens:SovSchematicNotation.tokens(diagram).space};
}"""


def show(page, text, name):
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [text, name])
    page.evaluate('()=>{ if (typeof fitDiagram === "function") fitDiagram(); }')
    page.wait_for_timeout(300)


def region(page):
    m = page.evaluate(METRICS)
    return [f for f in m['findings'] if f['kind'] == KIND], m


def plant(page):
    doc = page.evaluate('()=>({schema:SovSchematicData.DOCUMENT_SCHEMA})')
    # The plane spans x 200..600, y 150..450; the child (100 wide) sits 6 from its left edge.
    doc.update({'id': 'inset-plane', 'components': [
        {'id': 'p', 'symbolId': 'plane', 'x': 400, 'y': 300, 'form': {'dimension': 2, 'regions': {'interior': {'state': 'open'}}},
         'config': {'label': 'Plane', 'presentation': {'size': {'w': 400, 'h': 300}}}},
        {'id': 'c', 'symbolId': 'act', 'x': 256, 'y': 320, 'canvasId': 'canvas:component:p', 'parentId': 'p',
         'config': {'label': 'Child', 'presentation': {'size': {'w': 100, 'h': 60}}}},
    ], 'wires': []})
    show(page, json.dumps(doc), 'inset-plane.sov')
    return region(page)


def group(page):
    doc = page.evaluate('()=>({schema:SovSchematicData.DOCUMENT_SCHEMA})')
    doc.update({'id': 'inset-group', 'components': [
        {'id': 'g1', 'symbolId': 'group', 'x': 0, 'y': 0, 'config': {'label': 'G', 'members': ['a', 'b']}},
        {'id': 'a', 'symbolId': 'act', 'x': 100, 'y': 100, 'config': {'label': 'A'}},
        {'id': 'b', 'symbolId': 'act', 'x': 300, 'y': 220, 'config': {'label': 'B'}},
    ], 'wires': []})
    show(page, json.dumps(doc), 'inset-group.sov')
    return page.evaluate(GROUP_RECT), region(page)[0]


with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)

    show(page, SAMPLE.read_text(encoding='utf-8'), SAMPLE.name)
    as_authored, _ = region(page)
    # On this base the authored sample keeps 40 or more around every child (the 2026-10-02 reading of
    # hugging planes no longer holds), so the evidence the finding fires is the sample with its Web
    # booth card slid to 8 from the Surfaces plane's right edge: the same document, one card moved.
    hugging = json.loads(SAMPLE.read_text(encoding='utf-8'))
    for c in hugging['components']:
        if c['id'] == 'web-booth':
            c['x'] += 32
    show(page, json.dumps(hugging), SAMPLE.name)
    before, _ = region(page)
    receipt = page.evaluate("()=>SovSchematicAPI.layout.apply({engine:'layered'})")
    page.evaluate('()=>{ if (typeof fitDiagram === "function") fitDiagram(); }')
    page.wait_for_timeout(300)
    after, after_m = region(page)

    show(page, MAP.read_text(encoding='utf-8'), MAP.name)
    the_map, map_m = region(page)

    planted, planted_m = plant(page)
    grp, group_findings = group(page)
    browser.close()

print('work-engine-sample region-inset as authored', len(as_authored), 'with web-booth 8 from the Surfaces edge', len(before), [(f['ids'], f['detail']) for f in before])
print('work-engine-sample region-inset after layered', len(after), 'score', after_m['score'], 'receipt ok', receipt.get('ok') if isinstance(receipt, dict) else receipt)
print('map.sov region-inset', len(the_map), 'score', map_m['score'])
print('planted plane region-inset', len(planted), planted)
print('groupRect', grp['r'], 'tokens', {k: grp['tokens'].get(k) for k in ('regionInset', 'regionTitle')}, 'group findings', len(group_findings))

assert not errors, ('the page logs no errors', errors)
assert grp['tokens'].get('regionInset') == 24 and grp['tokens'].get('regionTitle') == 28, ('the schematic notation declares the two tokens', grp['tokens'])
assert len(as_authored) == 0, ('the authored sample keeps its inset on this base', as_authored)
assert len(before) == 1 and set(before[0]['ids']) == {'web-booth', 'surfaces'}, ('region-inset fires on the sample with a card pushed against its plane', before)
assert len(after) == 0, ('region-inset is 0 after the layered layout', after)
assert 'region-inset' not in after_m['rubric'], 'region-inset carries no rubric weight'
assert len(planted) == 1 and set(planted[0]['ids']) == {'c', 'p'}, ('one region-inset naming the child and the plane', planted)
assert '6.0px of the left' in planted[0]['detail'], ('the detail names the shortfall', planted[0])
r = grp['r']
# members: a at (100,100) and b at (300,220), each 100 x 60 -> union l 50, r 350, t 70, b 250
assert (r['l'], r['r'], r['t'], r['b']) == (50 - 24, 350 + 24, 70 - 24 - 28, 250 + 24), ('groupRect is the members padded 24 and 28', r)
assert not group_findings, ('a group drawn by groupRect keeps its inset', group_findings)
print('PASS region inset QA')
