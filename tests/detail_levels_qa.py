"""The editor draws less text as it zooms out, at the two levels DETAIL_FLOORS declares (NOTATION-MODEL.md section 4).

One group (label Stage) holds two cards joined by one labelled wire; one card carries a subtitle and
body text, and is 700 x 700 so its subtitle has room at every scale here: only the level hides it. DETAIL_FLOORS and LABEL_FLOORS are read from the page, and three screen scales are worked
out from them: above both floors, between them, below both. The camera zoom for each is the scale
divided by the screen scale the page reports at camera zoom 1.
- Above both floors the body text, the subtitle and the wire label are visible, with no data-lod.
- Between them only the body text is hidden (data-lod="hidden").
- Below both, all three are hidden with data-lod="hidden".
- At the first two zooms the card titles are visible; the third is under 0.25, where a card
  title's own rule may hide it over its glyph, so it is not held there.
- At all three zooms the group title is visible at LABEL_FLOORS.general screen px or more.
- A picture made at the lowest zoom (renderStandaloneSvg, loaded as its own page) shows all three.
- Back at the first zoom all three are visible and the subtitle's text is restored.
- The page logs no errors.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from browser_runtime import chromium_launch_kwargs  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

SUBTITLE = 'draft'
WIRE_LABEL = 'hands over'
CX, CY = 450, 300

DOC = f"""()=>{{window.SovSchematicAPI.document.replace({{schema:SovSchematicData.DOCUMENT_SCHEMA,id:'detail-levels',components:[
    {{id:'stage',symbolId:'group',x:{CX},y:{CY},config:{{label:'Stage',members:['a','b']}}}},
    {{id:'a',symbolId:'act',x:0,y:{CY},config:{{label:'Build',subtitle:'{SUBTITLE}',presentation:{{size:{{w:700,h:700}},text:'First line of notes\\nSecond line of notes'}}}}}},
    {{id:'b',symbolId:'hold',x:800,y:{CY},config:{{label:'Keep',presentation:{{size:{{w:200,h:140}}}}}}}}],
  wires:[{{id:'w',a:'a',aSide:'out',b:'b',bSide:'in',config:{{label:'{WIRE_LABEL}'}}}}]}})}}"""

SET_ZOOM = f"(z)=>{{camera={{x:{CX}-BASE_VIEW.w/z/2,y:{CY}-BASE_VIEW.h/z/2,w:BASE_VIEW.w/z,h:BASE_VIEW.h/z}};applyCamera();return currentZoom()}}"
SCREEN = "()=>parseFloat(workspace.style.getPropertyValue('--zoom'))"

# Each text: whether it is drawn (its own and every ancestor's visibility and display), its data-lod, its text.
READ = r"""()=>{const shown=el=>{for(let e=el;e&&e.nodeType===1;e=e.parentElement){const cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden')return false}return true};
  const one=el=>el?{visible:shown(el),lod:el.getAttribute('data-lod'),text:el.textContent,px:parseFloat(getComputedStyle(el).fontSize)}:null;
  const q=s=>document.querySelector(s);
  const ws=document.getElementById('workspace'),screen=ws?parseFloat(ws.style.getPropertyValue('--zoom'))||1:1;
  return {screen,
    body:one(q('.node[data-id="a"] > text.internal-text')),
    subtitle:one(q('.node[data-id="a"] > text.component-subtitle')),
    wire:one(q('.connection-label')),
    titleA:one(q('.node[data-id="a"] > text.component-label')),
    titleB:one(q('.node[data-id="b"] > text.component-label')),
    group:one(q('text.group-title')),
    wireLabels:document.querySelectorAll('.connection-label').length}}"""

with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)
    detail = page.evaluate('()=>({...DETAIL_FLOORS})')
    frozen = page.evaluate('()=>Object.isFrozen(DETAIL_FLOORS)')
    floors = page.evaluate('()=>LABEL_FLOORS')
    page.evaluate(DOC)
    page.wait_for_timeout(150)
    page.evaluate(SET_ZOOM, 1)
    unit = page.evaluate(SCREEN)  # the screen scale at camera zoom 1 on this viewport

    # Three screen scales from the declared floors: above both, between them, below both. The
    # lowest never goes under 0.1, so the camera stays finite when a floor is set to 0.
    hi, lo = max(detail.values()), min(detail.values())
    scales = {'above': hi + 0.15, 'between': (hi + lo) / 2, 'below': max(lo * 0.6, 0.1)}
    read = {}
    for name, scale in scales.items():
        page.evaluate(SET_ZOOM, scale / unit)
        page.wait_for_timeout(150)  # card text is laid out again on the next frame after a zoom
        read[name] = page.evaluate(READ)
    # A picture made at the lowest zoom, then the editor again at that zoom and back at the first.
    svg = page.evaluate('()=>renderStandaloneSvg({pad:48})')
    page.wait_for_timeout(150)
    read['below, after the picture'] = page.evaluate(READ)
    page.evaluate(SET_ZOOM, scales['above'] / unit)
    page.wait_for_timeout(150)
    read['above, again'] = page.evaluate(READ)
    pic_page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    pic_page.set_content(svg, wait_until='load')
    picture = pic_page.evaluate(READ)
    browser.close()

print('DETAIL_FLOORS', detail, 'frozen', frozen, '| LABEL_FLOORS', floors, f'| screen scale at camera zoom 1: {unit:.4f}')
state = lambda m: 'missing' if m is None else ('shown' if m['visible'] else 'hidden') + (f" lod={m['lod']}" if m['lod'] else '')
for name, r in read.items():
    want = scales.get(name.split(',')[0])
    print(f"{name}: camera zoom {want / unit:.4f}, screen scale {r['screen']:.4f} | body {state(r['body'])} | subtitle {state(r['subtitle'])} {r['subtitle']['text']!r} | "
          f"wire label {state(r['wire'])} | titles {state(r['titleA'])}, {state(r['titleB'])} | group title {state(r['group'])} at {r['group']['px'] * r['screen']:.2f} screen px")
print(f"picture: body {state(picture['body'])} | subtitle {state(picture['subtitle'])} | wire label {state(picture['wire'])}")

assert not errors, errors
assert sorted(detail) == ['body', 'secondary'] and frozen, ('DETAIL_FLOORS is one frozen pair', detail, frozen)
for name, scale in scales.items():
    assert abs(read[name]['screen'] - scale) < 0.005, (name, 'the page reports the screen scale the test asked for', read[name]['screen'], scale)
assert scales['above'] >= detail['body'] and scales['above'] >= detail['secondary'], ('above both floors', scales, detail)


def check(name: str, hidden: set[str], card_titles: bool = True) -> None:
    r = read[name]
    assert r['wireLabels'] == 1, (name, 'one wire label', r['wireLabels'])
    for kind in ('body', 'subtitle', 'wire'):
        m = r[kind]
        assert m is not None, (name, kind, 'is in the document')
        if kind in hidden:
            assert not m['visible'] and m['lod'] == 'hidden', (name, f'{kind} text is hidden with data-lod="hidden"', m)
        else:
            assert m['visible'] and m['lod'] is None, (name, f'{kind} text is visible with no data-lod', m)
    # A card title has its own rule at 0.25 or less (hidden over its glyph), so it is held only above that.
    for kind in ('titleA', 'titleB', 'group') if card_titles else ('group',):
        assert r[kind] is not None and r[kind]['visible'] and r[kind]['lod'] is None, (name, f'{kind} is visible', r[kind])
    px = r['group']['px'] * r['screen']
    assert px >= floors['general'] - 0.05, (name, 'the group title reads at the general floor or more', px, floors['general'])


check('above', set())
assert read['above']['subtitle']['text'] == SUBTITLE and read['above']['wire']['text'] == WIRE_LABEL, read['above']
check('between', {'body'})
assert read['below']['screen'] < detail['secondary'] or detail['secondary'] <= 0.1, ('the page reaches a screen scale under secondary', read['below']['screen'], detail)
check('below', {'body', 'subtitle', 'wire'}, card_titles=False)
check('below, after the picture', {'body', 'subtitle', 'wire'}, card_titles=False)
check('above, again', set())
assert read['above, again']['subtitle']['text'] == SUBTITLE, ('the subtitle text is restored', read['above, again']['subtitle'])
assert read['above, again']['wire']['text'] == WIRE_LABEL, ('the wire label text is restored', read['above, again']['wire'])
# The picture is drawn at screen scale 1, whatever the camera: it shows all three.
for kind in ('body', 'subtitle', 'wire'):
    m = picture[kind]
    assert m is not None and m['visible'] and m['lod'] is None, ('the picture made at the lowest zoom shows', kind, m)
assert picture['subtitle']['text'] == SUBTITLE and picture['wire']['text'] == WIRE_LABEL, picture
# The order the levels are declared in: body text goes first.
assert detail['body'] > detail['secondary'] > 0, ('body text is hidden before subtitles and wire labels', detail)
print('PASS detail levels QA')
