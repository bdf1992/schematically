"""A card that hosts other cards is drawn closed under INTERIOR_FLOOR (NOTATION-MODEL.md section 4).

One Plane (Outer, 1200 x 800) hosts two Planes (A and B, 400 x 300) side by side. Each inner Plane
hosts two cards joined by one wire, and carries one Point on its boundary; the two Points are joined
by one wire on Outer's surface. Outer carries one labelled Point on its own boundary. INTERIOR_FLOOR
is read from the page, and three screen scales are worked out from it and the Planes' shorter
sides (800 and 300): every Plane at or above the floor; Outer above it and A and B under it; all
three under it. The camera zoom for each is the scale divided by the screen scale the page reports
at camera zoom 1.
- At the first scale every card, Point and wire is visible, with no data-lod.
- At the second the four innermost cards and the two wires inside A and B are hidden with
  data-lod="hidden"; A and B, their titles, their boundary Points and the wire between them are
  visible. A press on a hidden card or a hidden wire does not reach it, and a click there does not
  select it.
- At the third everything inside Outer is hidden; Outer, its title and its boundary Point with its
  label are visible.
- A picture made at the lowest zoom (renderStandaloneSvg, loaded as its own page) shows every record.
- Back at the first scale everything is visible with no data-lod.
- A Plane whose shorter side is under the floor in canvas units is closed in the editor at the
  first scale and open in a picture made there.
- The page logs no errors.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from browser_runtime import chromium_launch_kwargs  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

CX, CY = 600, 400
OUTER, INNER = (1200, 800), (400, 300)
AX, BX = CX - 250, CX + 250
POINT_LABEL = 'feed'
LOWEST = 0.26

INNER_CARDS = ['a1', 'a2', 'b1', 'b2']
INNER_WIRES = ['wa', 'wb']
CARDS = ['outer', 'inA', 'inB', *INNER_CARDS, 'pa', 'pb', 'po']
WIRES = [*INNER_WIRES, 'wab']


def plane(pid: str, label: str, x: int, size: tuple[int, int], host: str | None = None) -> str:
    inside = f"canvasId:'canvas:component:{host}',parentId:'{host}'," if host else ''
    return f"{{id:'{pid}',symbolId:'plane',x:{x},y:{CY},{inside}config:{{label:'{label}',presentation:{{size:{{w:{size[0]},h:{size[1]}}}}}}}}}"


def card(cid: str, symbol: str, label: str, x: int, host: str) -> str:
    return (f"{{id:'{cid}',symbolId:'{symbol}',x:{x},y:{CY},canvasId:'canvas:component:{host}',parentId:'{host}',"
            f"config:{{label:'{label}',presentation:{{size:{{w:120,h:80}}}}}}}}")


def point(pid: str, host: str, side: str, x: int, label: str = '') -> str:
    named = f"label:'{label}'," if label else ''
    return (f"{{id:'{pid}',symbolId:'point',x:{x},y:{CY},canvasId:'canvas:component:{host}',parentId:'{host}',"
            f"placement:{{kind:'edge',hostId:'{host}',side:'{side}',t:.5}},config:{{{named}ports:{{out:{{face:'both'}}}}}}}}")


DOC = f"""()=>{{window.SovSchematicAPI.document.replace({{schema:SovSchematicData.DOCUMENT_SCHEMA,id:'interior-levels',components:[
    {plane('outer', 'Outer', CX, OUTER)},
    {plane('inA', 'A', AX, INNER, 'outer')},
    {plane('inB', 'B', BX, INNER, 'outer')},
    {card('a1', 'act', 'Build', AX - 90, 'inA')},{card('a2', 'hold', 'Keep', AX + 90, 'inA')},
    {card('b1', 'act', 'Check', BX - 90, 'inB')},{card('b2', 'hold', 'Store', BX + 90, 'inB')},
    {point('pa', 'inA', 'right', AX + INNER[0] // 2)},{point('pb', 'inB', 'left', BX - INNER[0] // 2)},
    {point('po', 'outer', 'left', CX - OUTER[0] // 2, POINT_LABEL)}],
  wires:[{{id:'wa',a:'a1',aSide:'out',b:'a2',bSide:'in'}},{{id:'wb',a:'b1',aSide:'out',b:'b2',bSide:'in'}},
    {{id:'wab',a:'pa',aSide:'self',b:'pb',bSide:'self',canvasId:'canvas:component:outer'}}]}})}}"""

# A Plane under the floor in canvas units (shorter side 200) hosting one card.
SMALL_DOC = f"""()=>{{window.SovSchematicAPI.document.replace({{schema:SovSchematicData.DOCUMENT_SCHEMA,id:'interior-small',components:[
    {plane('small', 'Small', CX, (300, 200))},{card('k', 'act', 'Build', CX, 'small')}],wires:[]}})}}"""

SET_ZOOM = f"(z)=>{{camera={{x:{CX}-BASE_VIEW.w/z/2,y:{CY}-BASE_VIEW.h/z/2,w:BASE_VIEW.w/z,h:BASE_VIEW.h/z}};applyCamera();return currentZoom()}}"
SCREEN = "()=>parseFloat(workspace.style.getPropertyValue('--zoom'))"
MODEL = "()=>({cards:nodes.map(n=>[n.id,n.canvasId||'canvas:global']),wires:wires.map(w=>[w.id,w.canvasId||'canvas:global'])})"

# Each record: whether it is drawn (its own and every ancestor's visibility and display) and its data-lod.
READ = r"""()=>{const shown=el=>{for(let e=el;e&&e.nodeType===1;e=e.parentElement){const cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden')return false}return true};
  const one=el=>el?{visible:shown(el),lod:el.getAttribute('data-lod'),text:el.textContent}:null;
  const q=s=>document.querySelector(s),all=s=>[...document.querySelectorAll(s)];
  const ws=document.getElementById('workspace'),screen=ws?parseFloat(ws.style.getPropertyValue('--zoom'))||1:1;
  const cards={},wires={},titles={},bodies={};
  for(const g of all('.node[data-id]')){cards[g.dataset.id]=one(g);titles[g.dataset.id]=one(g.querySelector(':scope > text.component-label,:scope > text.outside-label'));bodies[g.dataset.id]=one(g.querySelector(':scope > .body'))}
  for(const g of all('.wire-group[data-wire-id]'))wires[g.dataset.wireId]=one(g);
  return {screen,cards,wires,titles,bodies,pointLabel:one(all('.node[data-id="po"] text').find(t=>t.textContent.trim()))}}"""

# What a press at a canvas point lands on: the card or wire it belongs to, and whether that record is hidden.
HIT = r"""([x,y])=>{const p=new DOMPoint(x,y).matrixTransform(workspace.getScreenCTM()),el=document.elementFromPoint(p.x,p.y);
  const rec=el&&el.closest('.node,.wire-group');
  return {sx:p.x,sy:p.y,id:rec?(rec.dataset.id||rec.dataset.wireId):null,hidden:!!(el&&el.closest('[data-lod="hidden"]'))}}"""
WIRE_MID = "(id)=>{const p=document.querySelector(`.wire-group[data-wire-id=\"${id}\"] path.wire`),q=p.getPointAtLength(p.getTotalLength()/2);return [q.x,q.y]}"
SELECTED = "()=>({cards:[...selectedComponentIds],selected:typeof selected==='string'?selected:null})"

with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)
    floor = page.evaluate('()=>({...INTERIOR_FLOOR})')
    frozen = page.evaluate('()=>Object.isFrozen(INTERIOR_FLOOR)')
    page.evaluate(DOC)
    page.wait_for_timeout(150)
    page.evaluate(SET_ZOOM, 1)
    unit = page.evaluate(SCREEN)  # the screen scale at camera zoom 1 on this viewport
    model = page.evaluate(MODEL)

    # Three screen scales from the declared floor and the Planes' shorter sides. None goes under
    # LOWEST: a card title has its own rule at 0.25 or less (hidden over its glyph), and the camera
    # stays finite when the floor is set to 0.
    px, outer_side, inner_side = floor['px'], min(OUTER), min(INNER)
    scales = {'open': max(px / inner_side * 1.15, LOWEST), 'inner closed': max((px / outer_side + px / inner_side) / 2, LOWEST),
              'all closed': max(px / outer_side * 0.9, LOWEST)}
    read, hits = {}, {}
    wire_mid = None
    for name, scale in scales.items():
        page.evaluate(SET_ZOOM, scale / unit)
        page.wait_for_timeout(150)  # the rule is applied on the next frame after a zoom
        read[name] = page.evaluate(READ)
        if name == 'open':
            wire_mid = page.evaluate(WIRE_MID, 'wa')
        hits[name] = {'card': page.evaluate(HIT, [AX - 90, CY - 30]), 'wire': page.evaluate(HIT, wire_mid)}
    # A picture made at the lowest zoom, then the editor again at that zoom.
    svg = page.evaluate('()=>renderStandaloneSvg({pad:48})')
    page.wait_for_timeout(150)
    read['all closed, after the picture'] = page.evaluate(READ)
    # A click on a hidden card, with A and B closed: it is not selected.
    page.evaluate(SET_ZOOM, scales['inner closed'] / unit)
    page.wait_for_timeout(150)
    at = page.evaluate(HIT, [AX - 90, CY - 30])
    page.mouse.click(at['sx'], at['sy'])
    page.wait_for_timeout(100)
    clicked = page.evaluate(SELECTED)
    read['inner closed, after a click'] = page.evaluate(READ)
    page.evaluate(SET_ZOOM, scales['open'] / unit)
    page.wait_for_timeout(150)
    read['open, again'] = page.evaluate(READ)
    pic_page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    pic_page.set_content(svg, wait_until='load')
    picture = pic_page.evaluate(READ)
    # A Plane under the floor in canvas units: closed in the editor, open in a picture.
    page.evaluate(SMALL_DOC)
    page.wait_for_timeout(150)
    page.evaluate(SET_ZOOM, scales['open'] / unit)
    page.wait_for_timeout(150)
    small = page.evaluate(READ)
    small_svg = page.evaluate('()=>renderStandaloneSvg({pad:48})')
    pic_page.set_content(small_svg, wait_until='load')
    small_picture = pic_page.evaluate(READ)
    browser.close()

state = lambda m: 'missing' if m is None else ('shown' if m['visible'] else 'hidden') + (f" lod={m['lod']}" if m['lod'] else '')
hidden_of = lambda r: sorted(k for kind in ('cards', 'wires') for k, m in r[kind].items() if not m['visible'])
print('INTERIOR_FLOOR', floor, 'frozen', frozen, f'| screen scale at camera zoom 1: {unit:.4f}')
for name, r in read.items():
    want = scales[name.split(',')[0]]
    print(f"{name}: camera zoom {want / unit:.4f}, screen scale {r['screen']:.4f}, shorter sides {outer_side * r['screen']:.0f} and {inner_side * r['screen']:.0f} screen px | hidden {hidden_of(r) or 'nothing'}")
for name, h in hits.items():
    print(f"press at {name}: on the card's place {h['card']['id']} (hidden {h['card']['hidden']}), on the wire's place {h['wire']['id']} (hidden {h['wire']['hidden']})")
print(f"click on a hidden card: selected {clicked}")
print(f"picture: hidden {hidden_of(picture) or 'nothing'} | small Plane: editor card {state(small['cards'].get('k'))}, picture card {state(small_picture['cards'].get('k'))}")

assert not errors, errors
assert list(floor) == ['px'] and frozen, ('INTERIOR_FLOOR is one frozen value in screen pixels', floor, frozen)
surfaces = {**dict(model['cards']), **dict(model['wires'])}
assert sorted(surfaces) == sorted([*CARDS, *WIRES]), ('the document holds the records the test names', surfaces)
assert surfaces['wa'] == 'canvas:component:inA' and surfaces['wb'] == 'canvas:component:inB', ('the inner wires are on the inner surfaces', surfaces)
assert surfaces['wab'] == 'canvas:component:outer' and surfaces['pa'] == 'canvas:component:inA' and surfaces['po'] == 'canvas:component:outer', surfaces
for name, scale in scales.items():
    assert abs(read[name]['screen'] - scale) < 0.005, (name, 'the page reports the screen scale the test asked for', read[name]['screen'], scale)
assert inner_side * scales['open'] >= px, ('every Plane is at or above the floor', scales, px)
assert abs(scales['open'] - 1) > 0.01, ('the first scale is not the scale a picture is drawn at', scales)


def check(name: str, hidden: set[str], r: dict | None = None) -> None:
    r = r or read[name]
    for kind, ids in (('cards', CARDS), ('wires', WIRES)):
        assert sorted(r[kind]) == sorted(ids), (name, f'every one of the {kind} is drawn once', sorted(r[kind]))
        for rid in ids:
            m = r[kind][rid]
            if rid in hidden:
                assert not m['visible'] and m['lod'] == 'hidden', (name, f'{rid} is hidden with data-lod="hidden"', m)
            else:
                assert m['visible'] and m['lod'] is None, (name, f'{rid} is visible with no data-lod', m)
    # A Plane that is drawn shows its body and its title, closed or open.
    for rid in ('outer', 'inA', 'inB'):
        if rid not in hidden:
            for part in ('bodies', 'titles'):
                m = r[part][rid]
                assert m is not None and m['visible'] and m['lod'] is None, (name, f'{rid} shows its {part}', m)
    m = r['pointLabel']
    assert m is not None and m['text'].strip() == POINT_LABEL and m['visible'], (name, "Outer's boundary Point keeps its label", m)


INSIDE_OUTER = set(CARDS) - {'outer', 'po'} | set(WIRES)
check('open', set())
assert px <= 0 or inner_side * scales['inner closed'] < px <= outer_side * scales['inner closed'], ('Outer is above the floor, A and B under it', scales, px)
check('inner closed', {*INNER_CARDS, *INNER_WIRES})
assert px <= 0 or outer_side * scales['all closed'] < px, ('all three Planes are under the floor', scales, px)
check('all closed', INSIDE_OUTER)
check('all closed, after the picture', INSIDE_OUTER)
check('inner closed, after a click', {*INNER_CARDS, *INNER_WIRES})
check('open, again', set())
# A hidden record takes no pointer events and is not selected by a click.
assert hits['open']['card'] == {**hits['open']['card'], 'id': 'a1', 'hidden': False}, ('open, a press on the card reaches it', hits['open'])
assert hits['open']['wire'] == {**hits['open']['wire'], 'id': 'wa', 'hidden': False}, ('open, a press on the wire reaches it', hits['open'])
for name in ('inner closed', 'all closed'):
    for kind, own in (('card', 'a1'), ('wire', 'wa')):
        h = hits[name][kind]
        assert not h['hidden'] and h['id'] not in (own, None), (name, f'a press where the hidden {kind} is lands on what is drawn there', h)
assert hits['inner closed']['card']['id'] == 'inA' and hits['all closed']['card']['id'] == 'outer', ('the press lands on the closed card', hits)
assert 'a1' not in clicked['cards'] and clicked['selected'] != 'a1', ('a click on a hidden card does not select it', clicked)
# The picture is drawn at screen scale 1, whatever the camera: it shows every interior.
check('picture', set(), picture)
for rid in INNER_CARDS:
    assert picture['cards'][rid]['visible'], ('the picture made at the lowest zoom shows', rid)
# Under the floor in canvas units: the editor closes the Plane at the first scale, the picture does not.
assert min(300, 200) * scales['open'] >= px or (not small['cards']['k']['visible'] and small['cards']['k']['lod'] == 'hidden'), ('the editor draws the small Plane closed', small['cards'])
assert small_picture['cards']['k']['visible'] and small_picture['cards']['k']['lod'] is None, ('a picture shows the inside of a Plane under the floor', small_picture['cards'])
print('PASS interior levels QA')
