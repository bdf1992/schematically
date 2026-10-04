"""Status chip QA (NOTATION-MODEL.md "Statuses": tone and glyph; src/55-render.js appendComponentStatus).

A status that declares a tone (safe, alert, danger) draws its chip as a solid pill filled with that
status tone, the same in every palette and set by the appearance's row (src/00-state.js statusTone), holding '<glyph> <title>' in
#141414 or #FFFFFF, whichever has the higher WCAG contrast on the fill (SC 1.4.3, 4.5:1 at least).
The glyph means colour is never the only cue (SC 1.4.1).

examples/work-engine/status.sov, in light and dark, under okabe-ito and under system-default:
  - each chip's rect is filled with its status's declared tone at fill-opacity 1, with no stroke;
  - its text starts with the glyph and a space, then the title;
  - its ink is the higher-contrast of #141414 and #FFFFFF and reaches 4.5:1 on the fill;
  - the chip lies inside the card body;
  - render.svg({}) carries each tone and each glyph.
A copy whose carried notation drops tone from 'exists' draws that chip as before (fill-opacity
0.16, the title alone). The page logs no errors.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
EXAMPLE = ROOT / 'examples/work-engine/status.sov'
TONES = {'light': {'safe': '#01B597', 'alert': '#C28923', 'danger': '#7F1F26'},
         'dark': {'safe': '#28D4B2', 'alert': '#E3A849', 'danger': '#EC5258'}}
DECLARED = {'exists': ('safe', '✓', 'Exists'), 'partial': ('alert', '◷', 'Partial'),
            'missing': ('danger', '✕', 'Missing'), 'proposed': ('alert', '◷', 'Proposed')}
CARDS = {'web-booth': 'partial', 'recording': 'partial', 'case': 'exists', 'anchor': 'missing', 'continuity-to-sqlite': 'proposed'}


def lum(h: str) -> float:
    def ch(v: int) -> float:
        x = v / 255
        return x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return .2126 * ch(r) + .7152 * ch(g) + .0722 * ch(b)


def contrast(a: str, b: str) -> float:
    A, B = lum(a), lum(b)
    return (max(A, B) + .05) / (min(A, B) + .05)


CHIPS = r"""()=>{
  const hex=c=>{const m=String(c).match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);return m?'#'+[m[1],m[2],m[3]].map(v=>(+v).toString(16).padStart(2,'0')).join('').toUpperCase():String(c).toUpperCase()};
  const box=el=>{const r=el.getBoundingClientRect();return {l:r.left,r:r.right,t:r.top,b:r.bottom}};
  const out={};
  for(const g of document.querySelectorAll('#nodes > .node')){
    const chip=g.querySelector(':scope > .status-chip');if(!chip)continue;
    const rect=chip.querySelector('rect'),text=chip.querySelector('text'),body=g.querySelector(':scope > .body');
    out[g.dataset.id]={status:chip.dataset.status,fill:hex(rect.style.fill),fillOpacity:Number(rect.style.fillOpacity),stroke:rect.style.stroke,
      text:text.textContent,nodes:text.childNodes.length,ink:hex(text.style.fill),chip:box(rect),body:box(body)};
  }
  return out;
}"""


def check_chips(chips: dict, where: str) -> list:
    inks = []
    assert set(chips) == set(CARDS), (where, sorted(chips))
    for cid, sid in CARDS.items():
        c = chips[cid]
        tone, glyph, title = DECLARED[sid]
        assert c['status'] == sid, (where, cid, c)
        want = TONES[where.split('/')[0]][tone]
        assert c['fill'] == want, (where, cid, 'chip fill is the declared tone', c['fill'], want)
        assert c['fillOpacity'] == 1, (where, cid, c['fillOpacity'])
        assert c['stroke'] in ('none', ''), (where, cid, c['stroke'])
        assert c['text'].startswith(glyph + ' ') and c['text'] == f'{glyph} {title}' and c['nodes'] == 1, (where, cid, c['text'])
        best = '#141414' if contrast(c['fill'], '#141414') >= contrast(c['fill'], '#FFFFFF') else '#FFFFFF'
        assert c['ink'] == best, (where, cid, 'ink is the higher-contrast of #141414 and #FFFFFF', c['ink'], best)
        ratio = contrast(c['ink'], c['fill'])
        assert ratio >= 4.5, (where, cid, ratio)
        C, B = c['chip'], c['body']
        assert C['l'] > B['l'] and C['r'] < B['r'] and C['t'] > B['t'] and C['b'] < B['b'], (where, cid, 'chip inside the card body', C, B)
        inks.append((tone, c['ink'], round(ratio, 2)))
    return inks


def main() -> None:
    from playwright.sync_api import sync_playwright
    from browser_runtime import chromium_launch_kwargs
    text = EXAMPLE.read_text(encoding='utf-8')
    plain = json.loads(text)
    for s in plain['references'][0]['data']['statuses']:
        if s['id'] == 'exists':
            s.pop('tone')
    plain_text = json.dumps(plain, ensure_ascii=False)
    inks = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(150)
        page.evaluate('(t)=>{SovSchematicAPI.file.open(t,"status.sov");fitDiagram()}', text)
        for appearance in ('light', 'dark'):
            for palette in ('okabe-ito', 'system-default'):
                page.evaluate('([a,p])=>{SovSchematicAPI.view.setAppearance(a);SovSchematicAPI.view.setColour({theme:"pastel",palette:p});render()}', [appearance, palette])
                page.wait_for_timeout(80)
                where = f'{appearance}/{palette}'
                inks.update(check_chips(page.evaluate(CHIPS), where))
                svg = page.evaluate('()=>SovSchematicAPI.render.svg({})')
                for tone, hexv in TONES[appearance].items():
                    r, g, b = (int(hexv[i:i + 2], 16) for i in (1, 3, 5))
                    assert hexv.lower() in svg.lower() or f'rgb({r}, {g}, {b})' in svg, (where, 'render.svg lost the tone', tone, hexv)
                for sid, (_, glyph, title) in DECLARED.items():
                    assert f'{glyph} {title}<' in svg, (where, 'render.svg lost the glyph', sid)
        # A status with no tone draws today's chip: a faint fill of the card's colour, the title alone.
        page.evaluate('()=>{SovSchematicAPI.view.setAppearance("light");SovSchematicAPI.view.setColour({theme:"pastel",palette:"okabe-ito"})}')
        page.evaluate('(t)=>{SovSchematicAPI.file.open(t,"status-plain.sov");fitDiagram()}', plain_text)
        page.wait_for_timeout(120)
        chips = page.evaluate(CHIPS)
        browser.close()
    case = chips['case']
    assert abs(case['fillOpacity'] - .16) < 1e-6 and case['text'] == 'Exists', ('a status with no tone draws as before', case)
    assert case['fill'] not in TONES.values(), case
    assert chips['recording']['text'] == '◷ Partial' and chips['recording']['fillOpacity'] == 1, chips['recording']
    assert not errors, errors
    print('chip inks (tone, ink, contrast):', sorted(inks))
    print("no tone: 'case' draws", case['text'], 'at fill-opacity', case['fillOpacity'])
    print('PASS status chip QA')


if __name__ == '__main__':
    main()
