"""Palette system QA (src/09-colour-core.js PALETTE_SYSTEMS, paletteSystem; src/00-state.js 'system-default').

The palette 'system-default' is generated from a base hue (239), a ratio (117 degrees between the
three roles), a step (0.09 of OKLCH lightness between tones) and three status hues, with a light row
and a dark row: each row has its own role lightness and chroma and its own status lightness and
chroma (spec.dark), as okabe-ito has a dark row. Each of the six colours is a five-tone ramp.

Node part: paletteSystem(spec) and paletteSystem(spec, 'dark') give the palette study's 60 ramp hexes
exactly (best5.json, written below as literals).
Python part: a port of the study's scorer (score.py measure, search2.py's four separations): sRGB to
linear, Vienot, Brettel and Mollon 1999 deutan and protan matrices with each output clamped at 0,
OKLab distance times 100, the minimum over normal, deutan and protan vision. On each row the four
separations hold their floors and equal the values the study recorded, so the port is faithful.
Browser part: the editor lists 'system-default'; light uses the light row and dark the dark row;
realised under every theme each passes the repo's own audit (Machado 2009 normal, protan, deutan,
tritan; every contrast floor) with no failure, and in dark every colour slot holds 3:1 on a card.
Status tones are the middle tones of the row of the current appearance, the same in every palette.
"""
from __future__ import annotations
import json, math, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))

# Sketchbook ep-root-20261002, palette-tasting/best5.json (control/sketchbooks/... in the workstation root).
NAMES = ['primary', 'secondary', 'tertiary', 'safe', 'alert', 'danger']
# The palette study's recorded system: a light row and a dark row (best5.json).
RAMPS_LIGHT = [
    ['#003450', '#004D73', '#016797', '#4281AA', '#6C9CBC'],
    ['#4B1F31', '#6C3049', '#904362', '#A5637C', '#B98397'],
    ['#313400', '#484C00', '#616600', '#7B803D', '#959A67'],
    ['#237563', '#1C957D', '#01B597', '#63CEB3', '#98E7D1'],
    ['#7B5923', '#9E7124', '#C28923', '#D8A85F', '#EDC790'],
    ['#380207', '#5B1016', '#7F1F26', '#934544', '#A66664'],
]
RAMPS_DARK = [
    ['#185B81', '#1576AA', '#0A93D4', '#58AEE5', '#8AC9F5'],
    ['#7C3E57', '#A24F71', '#C9618C', '#DD85A7', '#F0A9C3'],
    ['#565A15', '#707510', '#8A9102', '#A5AC52', '#C1C883'],
    ['#3A927D', '#36B297', '#28D4B2', '#79EDD0', '#B0FFEE'],
    ['#9A7641', '#BE8F46', '#E3A849', '#F9C87F', '#FFE8B0'],
    ['#93393B', '#BF4649', '#EC5258', '#FE7E7D', '#FFA7A4'],
]
SLOTS = {'light': ['#016797', '#904362', '#616600', '#01B597', '#C28923', '#7F1F26'], 'dark': ['#0A93D4', '#C9618C', '#8A9102', '#28D4B2', '#E3A849', '#EC5258']}
RECORDED = {'light': {'status': 13.84, 'role_tone': 6.2, 'role_status': 9.44, 'tones': 7.58}, 'dark': {'status': 12.41, 'role_tone': 7.73, 'role_status': 5.21, 'tones': 6.46}}
TONES = {w: SLOTS[w][3:] for w in SLOTS}
FLOORS = {'status': 12, 'role_tone': 6, 'role_status': 5, 'tones': 6}

NODE = r"""
const C=require('./src/09-colour-core.js');
const spec=C.PALETTE_SYSTEMS['system-default'];
process.stdout.write(JSON.stringify({spec,system:{light:C.paletteSystem(spec),dark:C.paletteSystem(spec,'dark')},
  hexOklch:C.hexOklch('#016797'),roundTrip:C.oklchHex(...C.hexOklch('#904362')),
  ramp:C.toneRamp(.49,.11,239,.09)}));
"""


def node_part() -> dict:
    proc = subprocess.run(['node', '-e', NODE], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    system = out['system']
    for row, ramps in (('light', RAMPS_LIGHT), ('dark', RAMPS_DARK)):
        assert system[row]['names'] == NAMES, system[row]['names']
        assert system[row]['hues'] == [239, 356, 113, 175, 76, 22], (row, system[row]['hues'])
        assert system[row]['ramps'] == ramps, ('generated ramps differ from best5.json', row, system[row]['ramps'])
        assert system[row]['slots'] == SLOTS[row], (row, system[row]['slots'])
    assert out['ramp'] == RAMPS_LIGHT[0], out['ramp']
    assert out['roundTrip'] == '#904362', out['roundTrip']
    L, C, h = out['hexOklch']
    assert abs(L - .49) < .005 and abs(C - .11) < .005 and abs(h - 239) < .5, out['hexOklch']
    assert 'best5.json' in out['spec']['source'], out['spec']
    print('node part: paletteSystem gives best5.json\'s light and dark rows, 60 ramp hexes;', 'light', ' '.join(SLOTS['light']), 'dark', ' '.join(SLOTS['dark']))
    return system


# The palette study's scorer (score.py), ported line for line.
def lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(h: str) -> list[float]:
    return [lin(int(h[i:i + 2], 16)) for i in (1, 3, 5)]


CVD = {
    'normal': None,
    'deutan': [[0.29275, 0.70725, 0.0], [0.29275, 0.70725, 0.0], [-0.02234, 0.02234, 1.0]],
    'protan': [[0.11238, 0.88762, 0.0], [0.11238, 0.88762, 0.0], [0.00401, -0.00401, 1.0]],
}


def sim(c: list[float], m) -> list[float]:
    return c if m is None else [max(0.0, sum(m[i][j] * c[j] for j in range(3))) for i in range(3)]


def oklab(c: list[float]) -> tuple[float, float, float]:
    r, g, b = c
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def de(a: str, b: str, m) -> float:
    return 100 * math.dist(oklab(sim(rgb(a), m)), oklab(sim(rgb(b), m)))


def d(a: str, b: str) -> float:
    return min(de(a, b, m) for m in CVD.values())


def separations(ramps: list[list[str]]) -> dict:
    roles, status = ramps[:3], ramps[3:]
    return {
        'status': min(d(status[i][2], status[j][2]) for i in range(3) for j in range(i + 1, 3)),
        'role_tone': min(d(roles[i][t], roles[j][t]) for t in range(5) for i in range(3) for j in range(i + 1, 3)),
        'role_status': min(d(r[2], s[2]) for r in roles for s in status),
        'tones': min(d(rr[t], rr[t + 1]) for rr in ramps for t in range(4)),
    }


def score_part(system: dict) -> dict:
    out = {}
    for row in ('light', 'dark'):
        sep = out[row] = separations(system[row]['ramps'])
        print(row, 'separations (OKLab x100, worst of normal, deutan, protan):', {k: round(v, 2) for k, v in sep.items()})
        for k, v in sep.items():
            assert v >= FLOORS[k], (row, k, v, FLOORS[k])
            assert abs(v - RECORDED[row][k]) <= .01, ('the ported scorer differs from the study', row, k, v, RECORDED[row][k])
    return out


BROWSER = r"""()=>{
  const A=window.SovSchematicAPI,out={palettes:A.view.colour().palettes,audits:[],onCard:[],rows:{},tones:{}};
  for(const appearance of ['light','dark']){A.view.setAppearance(appearance);
    for(const theme of ['pastel','subtle','reading']){
      A.view.setColour({theme,palette:'system-default'});
      out.audits.push(A.view.paletteAudit());
      if(appearance==='dark')out.onCard.push({theme,min:Math.min(...activePalette().slice(6).map(c=>SovSchematicColour.contrast(c,DARK_CARD_SURFACE)))});
    }}
  out.rows={light:BASE_PALETTES['system-default'],dark:DARK_SURFACE_PALETTES['system-default']};
  for(const appearance of ['light','dark']){A.view.setAppearance(appearance);out.tones[appearance]={};
    for(const palette of ['okabe-ito','system-default','spectrum','mono','custom']){A.view.setColour({theme:'pastel',palette});out.tones[appearance][palette]=['safe','alert','danger'].map(statusTone)}}
  A.view.setAppearance('light');A.view.setColour({theme:'pastel',palette:'okabe-ito'});
  return out;
}"""


def browser_part() -> list:
    from playwright.sync_api import sync_playwright
    from browser_runtime import chromium_launch_kwargs
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(200)
        options = page.evaluate("()=>[...document.querySelectorAll('#colorPaletteInput option')].map(o=>o.value)")
        r = page.evaluate(BROWSER)
        browser.close()
    assert not errors, errors
    assert 'system-default' in r['palettes'] and r['palettes'][0] == 'okabe-ito', r['palettes']
    assert options[:2] == ['okabe-ito', 'system-default'], options
    assert r['rows'] == SLOTS, r['rows']
    for appearance, by_palette in r['tones'].items():
        for palette, tones in by_palette.items():
            assert tones == TONES[appearance], (appearance, palette, tones)
    for a in r['audits']:
        assert a['palette'] == 'system-default', a['palette']
        assert not a['failures'], (a['appearance'], a['theme'], a['failures'])
    assert all(c['min'] >= 3 for c in r['onCard']), ('dark colour slots on a card', r['onCard'])
    realised = []
    for a in r['audits']:
        if a['theme'] != 'pastel':
            continue
        pairs = {v: (a['closest'][v]['distance'], [a['colour'][i] for i in a['closest'][v]['pair']]) for v in ['normal', 'protan', 'deutan', 'tritan']}
        distinct = [f for f in a['failures'] if f['kind'] == 'distinct']
        print(f"realised audit {a['appearance']} pastel (Machado 2009; floor {a['cvdFloor']}): colour {a['colour']}")
        for v, (dist, pair) in pairs.items():
            print(f'  {v:<7} closest {dist:.3f} {pair[0]} {pair[1]}')
        print(f"  distinct failures: {[(f['vision'], f['distance']) for f in distinct] or 'none'}")
        realised.append({'appearance': a['appearance'], 'closest': pairs, 'distinct': distinct})
    print('browser part: listed, both rows the six generated slots, each appearance its own row, status tones fixed in five palettes per appearance, no audit failure in 6 realisations, dark on-card minimum',
          round(min(c['min'] for c in r['onCard']), 2))
    return realised


if __name__ == '__main__':
    system = node_part()
    score_part(system)
    browser_part()
    print('PASS palette system QA')
