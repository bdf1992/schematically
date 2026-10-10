"""A card that hosts other cards is drawn closed under INTERIOR_FLOOR (NOTATION-MODEL.md section 4).

One Plane (Outer, 760 x 400) hosts two Planes (A and B, 300 x 220) side by side. Each inner Plane
hosts two cards joined by one wire, and carries one Point on its boundary; the two Points are joined
by one wire on Outer's surface. Outer carries one labelled Point on its own boundary. INTERIOR_FLOOR
is read from the page, and three screen scales are worked out from it and the Planes' shorter
sides (400 and 220): every Plane at or above the floor; Outer above it and A and B under it; all
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
- A Plane 100 x 100 hosting one card is closed in the editor at the first scale and open in a
  picture made there.
- The same Plane at the camera zoom that gives screen scale exactly 1 is closed in the editor: the
  editor follows the floor at that scale like any other. A picture made there shows the card, and
  the editor is closed again after it.
- A default Plane (no stored size, 320 x 220) hosting one card, at camera zoom 1, is open, and a
  click on the hosted card selects that card.
- A Plane hosting one card whose out port feeds two others draws a junction dot there. With the
  Plane open the dot is visible; with it closed the dot is hidden with data-lod="hidden".
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
OUTER, INNER = (760, 400), (300, 220)
AX, BX = CX - 170, CX + 170
CARD, STEP = (80, 60), 80  # the innermost cards, and how far each sits from its Plane's centre
PRESS = [AX - STEP, CY - 20]  # a canvas point on card a1, above its centre
SMALL = (100, 100)
DEFAULT_PLANE = (320, 220)
JUNCTION = (400, 300)
POINT_LABEL = 'feed'
LOWEST = 0.26

INNER_CARDS = ['a1', 'a2', 'b1', 'b2']
INNER_WIRES = ['wa', 'wb']
CARDS = ['outer', 'inA', 'inB', *INNER_CARDS, 'pa', 'pb', 'po']
WIRES = [*INNER_WIRES, 'wab']


def plane(pid: str, label: str, x: int, size: tuple[int, int] | None, host: str | None = None) -> str:
    inside = f"canvasId:'canvas:component:{host}',parentId:'{host}'," if host else ''
    stored = f",presentation:{{size:{{w:{size[0]},h:{size[1]}}}}}" if size else ''
    return f"{{id:'{pid}',symbolId:'plane',x:{x},y:{CY},{inside}config:{{label:'{label}'{stored}}}}}"


def card(cid: str, symbol: str, label: str, x: int, host: str, y: int = CY, size: tuple[int, int] = CARD) -> str:
    return (f"{{id:'{cid}',symbolId:'{symbol}',x:{x},y:{y},canvasId:'canvas:component:{host}',parentId:'{host}',"
            f"config:{{label:'{label}',presentation:{{size:{{w:{size[0]},h:{size[1]}}}}}}}}}")


def point(pid: str, host: str, side: str, x: int, label: str = '') -> str:
    named = f"label:'{label}'," if label else ''
    return (f"{{id:'{pid}',symbolId:'point',x:{x},y:{CY},canvasId:'canvas:component:{host}',parentId:'{host}',"
            f"placement:{{kind:'edge',hostId:'{host}',side:'{side}',t:.5}},config:{{{named}ports:{{out:{{face:'both'}}}}}}}}")


def document(doc_id: str, components: str, wires: str = '') -> str:
    return (f"()=>{{window.SovSchematicAPI.document.replace({{schema:SovSchematicData.DOCUMENT_SCHEMA,id:'{doc_id}',"
            f"components:[{components}],wires:[{wires}]}})}}")


DOC = document('interior-levels', f"""
    {plane('outer', 'Outer', CX, OUTER)},
    {plane('inA', 'A', AX, INNER, 'outer')},
    {plane('inB', 'B', BX, INNER, 'outer')},
    {card('a1', 'act', 'Build', AX - STEP, 'inA')},{card('a2', 'hold', 'Keep', AX + STEP, 'inA')},
    {card('b1', 'act', 'Check', BX - STEP, 'inB')},{card('b2', 'hold', 'Store', BX + STEP, 'inB')},
    {point('pa', 'inA', 'right', AX + INNER[0] // 2)},{point('pb', 'inB', 'left', BX - INNER[0] // 2)},
    {point('po', 'outer', 'left', CX - OUTER[0] // 2, POINT_LABEL)}""",
               """{id:'wa',a:'a1',aSide:'out',b:'a2',bSide:'in'},{id:'wb',a:'b1',aSide:'out',b:'b2',bSide:'in'},
    {id:'wab',a:'pa',aSide:'self',b:'pb',bSide:'self',canvasId:'canvas:component:outer'}""")

# A Plane 100 x 100 hosting one card: under the floor at every scale the test uses, 1 included.
SMALL_DOC = document('interior-small', f"{plane('small', 'Small', CX, SMALL)},{card('k', 'act', 'Build', CX, 'small', size=(60, 40))}")
# A Plane with no stored size (the default, 320 x 220) hosting one card.
DEFAULT_DOC = document('interior-default', f"{plane('dflt', 'Default', CX, None)},{card('d1', 'act', 'Build', CX, 'dflt')}")
# A Plane hosting three cards; two wires leave j1's out port, so a junction dot is drawn there.
JUNCTION_DOC = document('interior-junction', f"""{plane('jp', 'Join', CX, JUNCTION)},
    {card('j1', 'act', 'Split', CX - 120, 'jp')},{card('j2', 'hold', 'Keep', CX + 120, 'jp', CY - 70)},{card('j3', 'hold', 'Store', CX + 120, 'jp', CY + 70)}""",
                        "{id:'wj1',a:'j1',aSide:'out',b:'j2',bSide:'in'},{id:'wj2',a:'j1',aSide:'out',b:'j3',bSide:'in'}")

SET_ZOOM = f"(z)=>{{camera={{x:{CX}-BASE_VIEW.w/z/2,y:{CY}-BASE_VIEW.h/z/2,w:BASE_VIEW.w/z,h:BASE_VIEW.h/z}};applyCamera();return currentZoom()}}"
SCREEN = "()=>parseFloat(workspace.style.getPropertyValue('--zoom'))"
MODEL = "()=>({cards:nodes.map(n=>[n.id,n.canvasId||'canvas:global']),wires:wires.map(w=>[w.id,w.canvasId||'canvas:global'])})"
SIZE = "(id)=>{const s=componentSize(nodes.find(n=>n.id===id));return [s.w,s.h]}"

# Each record: whether it is drawn (its own and every ancestor's visibility and display) and its data-lod.
READ = r"""()=>{const shown=el=>{for(let e=el;e&&e.nodeType===1;e=e.parentElement){const cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden')return false}return true};
  const one=el=>el?{visible:shown(el),lod:el.getAttribute('data-lod'),text:el.textContent}:null;
  const q=s=>document.querySelector(s),all=s=>[...document.querySelectorAll(s)];
  const ws=document.getElementById('workspace'),screen=ws?parseFloat(ws.style.getPropertyValue('--zoom'))||1:1;
  const cards={},wires={},titles={},bodies={},dots={};
  for(const g of all('.node[data-id]')){cards[g.dataset.id]=one(g);titles[g.dataset.id]=one(g.querySelector(':scope > text.component-label,:scope > text.outside-label'));bodies[g.dataset.id]=one(g.querySelector(':scope > .body'))}
  for(const g of all('.wire-group[data-wire-id]'))wires[g.dataset.wireId]=one(g);
  for(const d of all('#junctionLayer > .junction-dot'))dots[d.dataset.port]=one(d);
  return {screen,cards,wires,titles,bodies,dots,pointLabel:one(all('.node[data-id="po"] text').find(t=>t.textContent.trim()))}}"""

# What a press at a canvas point lands on: the card or wire it belongs to, and whether that record is hidden.
HIT = r"""([x,y])=>{const p=new DOMPoint(x,y).matrixTransform(workspace.getScreenCTM()),el=document.elementFromPoint(p.x,p.y);
  const rec=el&&el.closest('.node,.wire-group');
  return {sx:p.x,sy:p.y,id:rec?(rec.dataset.id||rec.dataset.wireId):null,hidden:!!(el&&el.closest('[data-lod="hidden"]'))}}"""
WIRE_MID = "(id)=>{const p=document.querySelector(`.wire-group[data-wire-id=\"${id}\"] path.wire`),q=p.getPointAtLength(p.getTotalLength()/2);return [q.x,q.y]}"
SELECTED = "()=>({cards:[...selectedComponentIds],selected:typeof selected==='string'?selected:null})"
# The pointer-events rule is in the stylesheet (styles/app.css); the script adds no style element for it.
STYLE = "()=>({added:!!document.getElementById('interiorDetailStyle'),sheet:[...document.styleSheets].some(s=>[...s.cssRules].some(r=>r.selectorText&&r.selectorText.includes('#workspace [data-lod=\"hidden\"]')&&r.style.pointerEvents==='none'))})"

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

    def at_scale(scale: float) -> None:
        page.evaluate(SET_ZOOM, scale / unit)
        page.wait_for_timeout(150)  # the rule is applied on the next frame after a zoom

    # Three screen scales from the declared floor and the Planes' shorter sides. None goes under
    # LOWEST: a card title has its own rule at 0.25 or less (hidden over its glyph), and the camera
    # stays finite when the floor is set to 0.
    px, outer_side, inner_side = floor['px'], min(OUTER), min(INNER)
    scales = {'open': max(px / inner_side * 1.15, LOWEST), 'inner closed': max((px / outer_side + px / inner_side) / 2, LOWEST),
              'all closed': max(px / outer_side * 0.9, LOWEST)}
    read, hits = {}, {}
    wire_mid = None
    for name, scale in scales.items():
        at_scale(scale)
        read[name] = page.evaluate(READ)
        if name == 'open':
            wire_mid = page.evaluate(WIRE_MID, 'wa')
        hits[name] = {'card': page.evaluate(HIT, PRESS), 'wire': page.evaluate(HIT, wire_mid)}
    # A picture made at the lowest zoom, then the editor again at that zoom.
    svg = page.evaluate('()=>renderStandaloneSvg({pad:48})')
    page.wait_for_timeout(150)
    read['all closed, after the picture'] = page.evaluate(READ)
    # A click on a hidden card, with A and B closed: it is not selected.
    at_scale(scales['inner closed'])
    at = page.evaluate(HIT, PRESS)
    page.mouse.click(at['sx'], at['sy'])
    page.wait_for_timeout(100)
    clicked = page.evaluate(SELECTED)
    read['inner closed, after a click'] = page.evaluate(READ)
    at_scale(scales['open'])
    read['open, again'] = page.evaluate(READ)
    style = page.evaluate(STYLE)
    pic_page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    pic_page.set_content(svg, wait_until='load')
    picture = pic_page.evaluate(READ)

    def picture_of() -> dict:
        pic_page.set_content(page.evaluate('()=>renderStandaloneSvg({pad:48})'), wait_until='load')
        return pic_page.evaluate(READ)

    # A Plane 100 x 100: closed in the editor at the first scale, open in a picture made there.
    page.evaluate(SMALL_DOC)
    page.wait_for_timeout(150)
    at_scale(scales['open'])
    small = page.evaluate(READ)
    small_picture = picture_of()
    # The same Plane at screen scale exactly 1: closed in the editor, open in a picture made there,
    # closed again afterwards. The camera zoom is corrected until the page reports exactly 1.
    zoom_one = 1 / unit
    for _ in range(8):
        page.evaluate(SET_ZOOM, zoom_one)
        raw_one = page.evaluate("()=>workspace.style.getPropertyValue('--zoom')")
        if float(raw_one) == 1:
            break
        zoom_one /= float(raw_one)
    page.wait_for_timeout(150)
    one = page.evaluate(READ)
    one_picture = picture_of()
    page.wait_for_timeout(150)
    one_after = page.evaluate(READ)
    one_raw_after = page.evaluate("()=>workspace.style.getPropertyValue('--zoom')")
    # A picture whose drawing throws leaves the flag cleared and the editor closed.
    thrown = page.evaluate("()=>{let threw=false;try{withPictureLabels(()=>{throw new Error('drawing failed')})}catch(e){threw=e.message==='drawing failed'}return {threw,flag:pictureDrawing}}")
    page.wait_for_timeout(150)
    one_thrown = page.evaluate(READ)
    # A default Plane hosting one card, at camera zoom 1: open, and a click on the hosted card selects it.
    page.evaluate(DEFAULT_DOC)
    page.wait_for_timeout(150)
    page.evaluate(SET_ZOOM, 1)
    page.wait_for_timeout(150)
    default_size = page.evaluate(SIZE, 'dflt')
    default = page.evaluate(READ)
    default_hit = page.evaluate(HIT, [CX - 15, CY + 5])  # on the card's body, clear of its ports
    page.mouse.click(default_hit['sx'], default_hit['sy'])
    page.wait_for_timeout(100)
    default_clicked = page.evaluate(SELECTED)
    # A junction dot inside a Plane, open and then closed.
    junction_side = min(JUNCTION)
    junction_scales = {'open': max(px / junction_side * 1.5, LOWEST), 'closed': max(px / junction_side * 0.75, LOWEST)}
    page.evaluate(JUNCTION_DOC)
    page.wait_for_timeout(150)
    junction = {}
    for name, scale in junction_scales.items():
        at_scale(scale)
        junction[name] = page.evaluate(READ)
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
print(f"picture: hidden {hidden_of(picture) or 'nothing'} | pointer-events rule: in the stylesheet {style['sheet']}, added by script {style['added']}")
print(f"Plane {SMALL[0]} x {SMALL[1]} at screen scale {small['screen']:.4f}: editor card {state(small['cards'].get('k'))}, picture card {state(small_picture['cards'].get('k'))}")
print(f"Plane {SMALL[0]} x {SMALL[1]} at screen scale {raw_one} (camera zoom {zoom_one:.6f}): editor card {state(one['cards'].get('k'))}, picture card {state(one_picture['cards'].get('k'))}, "
      f"editor after the picture {state(one_after['cards'].get('k'))}, after a picture that throws {state(one_thrown['cards'].get('k'))} (flag {thrown['flag']})")
print(f"default Plane {default_size[0]} x {default_size[1]} at camera zoom 1: shorter side {min(default_size) * default['screen']:.1f} screen px, hosted card {state(default['cards'].get('d1'))}, "
      f"press lands on {default_hit['id']}, click selected {default_clicked}")
for name, r in junction.items():
    print(f"junction, Plane {name}: screen scale {r['screen']:.4f}, shorter side {junction_side * r['screen']:.0f} screen px | dot {state(r['dots'].get('j1|out'))} | hidden {hidden_of(r) or 'nothing'}")

assert not errors, errors
assert list(floor) == ['px'] and frozen, ('INTERIOR_FLOOR is one frozen value in screen pixels', floor, frozen)
assert style == {'added': False, 'sheet': True}, ('the pointer-events rule is in the stylesheet and the script adds none', style)
surfaces = {**dict(model['cards']), **dict(model['wires'])}
assert sorted(surfaces) == sorted([*CARDS, *WIRES]), ('the document holds the records the test names', surfaces)
assert surfaces['wa'] == 'canvas:component:inA' and surfaces['wb'] == 'canvas:component:inB', ('the inner wires are on the inner surfaces', surfaces)
assert surfaces['wab'] == 'canvas:component:outer' and surfaces['pa'] == 'canvas:component:inA' and surfaces['po'] == 'canvas:component:outer', surfaces
for name, scale in scales.items():
    assert abs(read[name]['screen'] - scale) < 0.005, (name, 'the page reports the screen scale the test asked for', read[name]['screen'], scale)
assert inner_side * scales['open'] >= px, ('every Plane is at or above the floor', scales, px)


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


def is_hidden(m: dict | None) -> bool:
    return m is not None and not m['visible'] and m['lod'] == 'hidden'


def is_shown(m: dict | None) -> bool:
    return m is not None and m['visible'] and m['lod'] is None


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
# A picture is drawn with the picture flag set, whatever the camera: it shows every interior.
check('picture', set(), picture)
for rid in INNER_CARDS:
    assert picture['cards'][rid]['visible'], ('the picture made at the lowest zoom shows', rid)
# A Plane 100 x 100 at the first scale: the editor closes it, the picture does not.
assert px <= 0 or min(SMALL) * scales['open'] < px, ('the small Plane is under the floor at the first scale', scales, px)
assert is_hidden(small['cards']['k']), ('the editor draws the small Plane closed', small['cards'])
assert is_shown(small['cards']['small']) and is_shown(small['titles']['small']), ('the closed small Plane shows itself and its title', small)
assert is_shown(small_picture['cards']['k']), ('a picture shows the inside of a Plane under the floor', small_picture['cards'])
# The same Plane at screen scale exactly 1: the editor follows the floor there like at any other scale.
assert float(raw_one) == 1 and float(one_raw_after) == 1, ('the page reports a screen scale of exactly 1, before and after the picture', raw_one, one_raw_after)
assert px <= 0 or min(SMALL) * 1 < px, ('the small Plane is under the floor at screen scale 1', px)
assert is_hidden(one['cards']['k']), ('at screen scale exactly 1 the editor draws the small Plane closed', one['cards'])
assert is_shown(one_picture['cards']['k']), ('a picture made at screen scale exactly 1 shows the inside', one_picture['cards'])
assert is_hidden(one_after['cards']['k']), ('after that picture the editor draws the small Plane closed again', one_after['cards'])
assert thrown == {'threw': True, 'flag': False}, ('a picture whose drawing throws passes the error on and clears the flag', thrown)
assert is_hidden(one_thrown['cards']['k']), ('after a picture that throws the editor draws the small Plane closed', one_thrown['cards'])
# A default Plane at camera zoom 1 is open, and a click on the card it hosts selects that card.
assert default_size == list(DEFAULT_PLANE), ('a Plane with no stored size is 320 x 220', default_size)
assert abs(default['screen'] - unit) < 1e-9 and min(DEFAULT_PLANE) * unit >= px, ('the default Plane is at or above the floor at camera zoom 1', default['screen'], unit, px)
assert is_shown(default['cards']['dflt']) and is_shown(default['cards']['d1']), ('the default Plane is drawn open at camera zoom 1', default['cards'])
assert default_hit['id'] == 'd1' and not default_hit['hidden'], ('a press on the hosted card reaches it', default_hit)
assert default_clicked['cards'] == ['d1'], ('a click on the hosted card selects that card', default_clicked)
# A junction dot inside a Plane: drawn with the Plane open, hidden with it closed.
assert junction_side * junction_scales['open'] >= px, ('the junction Plane is at or above the floor', junction_scales, px)
assert px <= 0 or junction_side * junction_scales['closed'] < px, ('the junction Plane is under the floor', junction_scales, px)
for name in junction:
    assert list(junction[name]['dots']) == ['j1|out'], (name, "one junction dot is drawn, at j1's out port", junction[name]['dots'])
assert is_shown(junction['open']['dots']['j1|out']) and not hidden_of(junction['open']), ('with the Plane open the junction dot is drawn', junction['open']['dots'])
assert is_hidden(junction['closed']['dots']['j1|out']), ('a junction dot inside a closed Plane is hidden with data-lod="hidden"', junction['closed']['dots'])
assert is_hidden(junction['closed']['cards']['j1']) and is_shown(junction['closed']['cards']['jp']), ('the Plane is closed around the dot', junction['closed']['cards'])
print('PASS interior levels QA')
