"""Palette system QA (src/09-colour-core.js PALETTE_SYSTEMS, paletteSystem; src/00-state.js 'system-default').

The palette 'system-default' is generated from a base hue (115), a ratio (75 degrees between the
three roles), one role lightness and chroma, a step (0.08 of OKLCH lightness between tones) and three
status tones (safe, alert, danger) set apart by lightness. Each of the six colours is a five-tone ramp.

Node part: paletteSystem(PALETTE_SYSTEMS['system-default']) gives the palette study's 30 ramp hexes
exactly (written below as literals).
Python part: a port of the study's scorer (score.py measure, search2.py's four separations): sRGB to
linear, Vienot, Brettel and Mollon 1999 deutan and protan matrices with each output clamped at 0,
OKLab distance times 100, the minimum over normal, deutan and protan vision. The four separations
hold their floors and equal the values the study recorded, so the port is faithful.
Browser part: the editor lists 'system-default'; realised in light and dark under every theme it
holds every contrast floor, and in dark every colour slot holds 3:1 on a card. The repo's own audit
(Machado 2009, which adds tritan) is printed, not asserted.
"""
from __future__ import annotations
import json, math, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))

# The palette study's recorded system, sketchbook ep-root-20261002, palette-tasting/best2.json
# (control/sketchbooks/ep-root-20261002/palette-tasting/best2.json in the workstation root).
NAMES = ['primary', 'secondary', 'tertiary', 'safe', 'alert', 'danger']
BEST2_RAMPS = [
    ['#5F6630', '#767E34', '#8D9738', '#A6AF65', '#BFC78E'],
    ['#1A6E6A', '#008984', '#00A69F', '#50BCB5', '#84D1CC'],
    ['#4B5F8C', '#5B76B2', '#6B8DD8', '#89A7E6', '#A9C1F4'],
    ['#2C7257', '#2A8E6A', '#24AB7E', '#62C09A', '#90D6B7'],
    ['#AD8D48', '#CEA444', '#F0BB3B', '#FFD87A', '#FFF4AD'],
    ['#772C1F', '#9D3726', '#C4422C', '#D36854', '#E08A79'],
]
BEST2_SLOTS = ['#8D9738', '#00A69F', '#6B8DD8', '#24AB7E', '#F0BB3B', '#C4422C']
# best2.json: status_sep, role_tone_sep, role_status_sep, ramp_sep.
BEST2_RECORDED = {'status': 12.38, 'role_tone': 6.04, 'role_status': 5.37, 'tones': 6.34}
FLOORS = {'status': 12, 'role_tone': 6, 'role_status': 5, 'tones': 6}

NODE = r"""
const C=require('./src/09-colour-core.js');
const spec=C.PALETTE_SYSTEMS['system-default'];
const p=C.paletteSystem(spec);
process.stdout.write(JSON.stringify({spec,system:p,
  hexOklch:C.hexOklch('#8D9738'),roundTrip:C.oklchHex(...C.hexOklch('#00A69F')),
  ramp:C.toneRamp(.65,.12,115,.08)}));
"""


def node_part() -> dict:
    proc = subprocess.run(['node', '-e', NODE], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    system = out['system']
    assert system['names'] == NAMES, system['names']
    assert system['hues'] == [115, 190, 265, 165, 85, 32], system['hues']
    assert system['ramps'] == BEST2_RAMPS, ('generated ramps differ from best2.json', system['ramps'])
    assert system['slots'] == BEST2_SLOTS, system['slots']
    assert out['ramp'] == BEST2_RAMPS[0], out['ramp']
    assert out['roundTrip'] == '#00A69F', out['roundTrip']
    L, C, h = out['hexOklch']
    assert abs(L - .65) < .005 and abs(C - .12) < .005 and abs(h - 115) < .5, out['hexOklch']
    assert 'best2.json' in out['spec']['source'], out['spec']
    print('node part: paletteSystem gives best2.json\'s 30 ramp hexes;', ' '.join(system['slots']))
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
    sep = separations(system['ramps'])
    print('separations (OKLab x100, worst of normal, deutan, protan):', {k: round(v, 2) for k, v in sep.items()})
    for k, v in sep.items():
        assert v >= FLOORS[k], (k, v, FLOORS[k])
        assert abs(v - BEST2_RECORDED[k]) <= .01, ('the ported scorer differs from the study', k, v, BEST2_RECORDED[k])
    return sep


BROWSER = r"""()=>{
  const A=window.SovSchematicAPI,out={palettes:A.view.colour().palettes,audits:[],onCard:[],rows:{},tones:{}};
  for(const appearance of ['light','dark']){A.view.setAppearance(appearance);
    for(const theme of ['pastel','subtle','reading']){
      A.view.setColour({theme,palette:'system-default'});
      out.audits.push(A.view.paletteAudit());
      if(appearance==='dark')out.onCard.push({theme,min:Math.min(...activePalette().slice(6).map(c=>SovSchematicColour.contrast(c,DARK_CARD_SURFACE)))});
    }}
  out.rows={light:BASE_PALETTES['system-default'],dark:DARK_SURFACE_PALETTES['system-default']};
  for(const palette of ['okabe-ito','system-default','spectrum','mono','custom']){A.view.setColour({theme:'pastel',palette});out.tones[palette]=['safe','alert','danger'].map(statusTone)}
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
    assert r['rows'] == {'light': BEST2_SLOTS, 'dark': BEST2_SLOTS}, r['rows']
    for palette, tones in r['tones'].items():
        assert tones == ['#24AB7E', '#F0BB3B', '#C4422C'], (palette, tones)
    for a in r['audits']:
        assert a['palette'] == 'system-default', a['palette']
        bad = [f for f in a['failures'] if f['kind'] == 'contrast']
        assert not bad, (a['appearance'], a['theme'], bad)
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
    print('browser part: listed, both rows the six generated slots, status tones fixed in five palettes, no contrast failure in 6 realisations, dark on-card minimum',
          round(min(c['min'] for c in r['onCard']), 2))
    return realised


if __name__ == '__main__':
    system = node_part()
    score_part(system)
    browser_part()
    print('PASS palette system QA')
