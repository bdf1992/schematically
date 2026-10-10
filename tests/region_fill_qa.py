"""Region fill QA (00-state.js componentSurfaceFill, 55-render.js renderComponentVisual/renderGroups).

A region's fill is the ground it sits on moved toward the region's own colour, not the colour
moved toward the ground: `componentSurfaceFill(hex, amount, ground)` is `mixHex([ground, hex],
[amount, 1 - amount])`, symmetric in both appearances. A nested region's ground is the fill its
host actually drew, so each level reads as the one above it moved toward its own colour; a card
that is a member of a coloured group takes that group's region fill; a coloured group region is
filled opaque, not a translucent wash.

Fixture: a plane (colorSlot 8) holds a plane (colorSlot 9) holding an act card, and a separate
group (colorSlot 7) whose one member is an act card. Checked in both appearances:

  - the outer plane's drawn interior fill equals mixHex([canvasTone(), slotColor(8)], [a, 1-a])
    for the amount the renderer actually used (read back from the page, not assumed here);
  - the inner plane's drawn interior fill equals the same construction with the outer plane's
    own fill as ground, not the bare canvas;
  - the group region is opaque (fill-opacity 1) and equals componentSurfaceFill(slotColor(7), .9);
  - the outer plane's fill holds a low contrast ratio (< 1.6) against the canvas - a tint of its
    colour, not a block of it;
  - the page raises no error.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

DOC = {
    'schema': None,  # filled in by the page from SovSchematicData.DOCUMENT_SCHEMA
    'id': 'region-fill-fixture',
    'components': [
        {'id': 'outer', 'symbolId': 'plane', 'x': 300, 'y': 300,
         'form': {'dimension': 2, 'regions': {'interior': {'state': 'open'}}},
         'config': {'label': 'Outer', 'colorSlot': 8}},
        {'id': 'inner', 'symbolId': 'plane', 'x': 300, 'y': 300,
         'canvasId': 'canvas:component:outer', 'parentId': 'outer',
         'form': {'dimension': 2, 'regions': {'interior': {'state': 'open'}}},
         'config': {'label': 'Inner', 'colorSlot': 9}},
        {'id': 'card', 'symbolId': 'act', 'x': 300, 'y': 300,
         'canvasId': 'canvas:component:inner', 'parentId': 'inner', 'config': {'label': 'Card'}},
        {'id': 'groupCard', 'symbolId': 'act', 'x': 700, 'y': 300, 'config': {'label': 'GroupCard'}},
        {'id': 'group1', 'symbolId': 'group', 'x': 700, 'y': 200,
         'config': {'label': 'Group', 'colorSlot': 7, 'members': ['groupCard']}},
    ],
    'wires': [],
    'references': [],
}

PAGE = r"""(doc)=>{
  const A=window.SovSchematicAPI,out={};
  const load=(appearance)=>{
    A.view.setAppearance(appearance);
    A.document.replace({...doc,schema:SovSchematicData.DOCUMENT_SCHEMA});
    fitDiagram();
    const outerG=document.querySelector('#nodes > .node[data-id="outer"]');
    const innerG=document.querySelector('#nodes > .node[data-id="inner"]');
    const groupRect=document.querySelector('.node.group[data-id="group1"] > .group-region');
    const outerFill=outerG?outerG.style.getPropertyValue('--component-interior-fill').trim():null;
    const innerFill=innerG?innerG.style.getPropertyValue('--component-interior-fill').trim():null;
    return {
      canvasTone:canvasTone(),
      outerFill,
      innerFill,
      outerExpected:componentSurfaceFill(slotColor(8),.975),
      innerExpectedFromOuter:outerFill?componentSurfaceFill(slotColor(9),.975,outerFill):null,
      groupRegionFillStyle:groupRect?groupRect.style.fill:null,
      groupRegionFillComputed:groupRect?getComputedStyle(groupRect).fill:null,
      groupRegionFillOpacity:groupRect?getComputedStyle(groupRect).fillOpacity:null,
      groupRegionExpected:componentSurfaceFill(slotColor(7),.9),
      outerContrast:outerFill?contrastRatio(outerFill,canvasTone()):null,
    };
  };
  out.light=load('light');
  out.dark=load('dark');
  return out;
}"""


def hex_to_rgb_tuple(hex_str):
    h = hex_str.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_string_to_tuple(rgb_str):
    inside = rgb_str[rgb_str.index('(') + 1:rgb_str.index(')')]
    parts = [p.strip() for p in inside.split(',')]
    return tuple(int(float(p)) for p in parts[:3])


def check(appearance: str, r: dict) -> None:
    assert r['outerFill'] is not None, (appearance, 'outer plane drew no --component-interior-fill')
    assert r['outerFill'] == r['outerExpected'], (appearance, 'outer plane fill', r['outerFill'], r['outerExpected'])
    assert r['innerFill'] is not None, (appearance, 'inner plane drew no --component-interior-fill')
    assert r['innerFill'] == r['innerExpectedFromOuter'], (
        appearance, 'inner plane fill must be computed with the outer plane fill as ground',
        r['innerFill'], r['innerExpectedFromOuter'])
    assert r['groupRegionFillComputed'] is not None, (appearance, 'group region drew no fill')
    assert rgb_string_to_tuple(r['groupRegionFillComputed']) == hex_to_rgb_tuple(r['groupRegionExpected']), (
        appearance, 'group region fill', r['groupRegionFillComputed'], r['groupRegionExpected'])
    assert r['groupRegionFillOpacity'] in ('1', 1), (appearance, 'coloured group region must be opaque', r['groupRegionFillOpacity'])
    assert r['outerContrast'] is not None and r['outerContrast'] < 1.6, (appearance, 'outer plane fill vs canvas', r['outerContrast'])


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(200)
        r = page.evaluate(PAGE, DOC)
        browser.close()
    assert not errors, errors
    check('light', r['light'])
    check('dark', r['dark'])
    print('REGION FILL QA PASS', {
        'light': {'outer': r['light']['outerFill'], 'contrast': round(r['light']['outerContrast'], 3)},
        'dark': {'outer': r['dark']['outerFill'], 'contrast': round(r['dark']['outerContrast'], 3)},
    })


if __name__ == '__main__':
    main()
