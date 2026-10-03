"""Lit wire role QA (src/65-sim-control.js paintSim, src/00-state.js litTone, styles/app.css).

A wire is lit while its source end is high. When the source sits in a role or status slot (6-11)
the lit wire takes that slot's own tone, one step lighter on dark (+1) and one step darker on light
(-1) on the slot's ramp; any other source keeps the output accent (--accent-out).

examples/10-clocked-signals.sov, sim_control_qa's route: the clock is reset and the file opened, the
source slot is set before the clock runs (an edit restarts it), the lever goes up, and the clock is
advanced into its high half, where w3 (from 'both' to the lamp) is lit.
  - system-default, 'both' on slot 6: w3's stroke is #A6AF65 on dark and #767E34 on light (the
    primary ramp's +1 and -1 tones in the palette study's best2.json);
  - 'both' on slot 2: w3's stroke is the computed --accent-out;
  - okabe-ito, slot 6: w3's stroke is the page's litTone(6, appearance) and not the accent;
  - after clock.reset no wire group keeps level-high or --wire-lit;
  - render.svg({}) taken while w3 is lit carries neither level-high nor --wire-lit.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
EXAMPLE = ROOT / 'examples' / '10-clocked-signals.sov'
EXPECTED = {'dark': '#A6AF65', 'light': '#767E34'}

LIGHT_UP = r"""([appearance,palette,slot])=>{
  const A=window.SovSchematicAPI;
  A.view.setAppearance(appearance);A.view.setColour({theme:'pastel',palette});
  A.update('component','both',{config:{colorSlot:slot}});
  A.clock.advance(1250);
  const toggled=A.clock.toggle('enable');
  const s=A.clock.advance(1000)||A.clock.state();
  const hex=c=>{const m=String(c).match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);return m?'#'+[m[1],m[2],m[3]].map(v=>(+v).toString(16).padStart(2,'0')).join('').toUpperCase():String(c).trim().toUpperCase()};
  const g=document.querySelector('.wire-group[data-wire-id="w3"]'),wire=g.querySelector('path.wire');
  const probe=document.createElement('div');probe.style.color=getComputedStyle(g).getPropertyValue('--accent-out').trim();document.body.appendChild(probe);
  const accent=hex(getComputedStyle(probe).color);probe.remove();
  const state=A.clock.state();
  return {lit:g.classList.contains('level-high'),both:state.levels.both.value,toggled,stroke:hex(getComputedStyle(wire).stroke),
    wireLit:g.style.getPropertyValue('--wire-lit').trim().toUpperCase(),accent,litTone:litTone(slot,appearance),appearance:surfaceAppearance()};
}"""

CLEARED = r"""()=>{
  const A=window.SovSchematicAPI;A.clock.reset();
  return {high:document.querySelectorAll('.wire-group.level-high').length,
    lit:[...document.querySelectorAll('.wire-group')].filter(g=>g.style.getPropertyValue('--wire-lit')).length};
}"""


def main() -> None:
    from playwright.sync_api import sync_playwright
    from browser_runtime import chromium_launch_kwargs
    text = EXAMPLE.read_text(encoding='utf-8')
    seen = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1500, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(200)

        def run(appearance: str, palette: str, slot: int) -> dict:
            page.evaluate('([t,n])=>{SovSchematicAPI.clock.reset();SovSchematicAPI.file.open(t,n);fitDiagram()}', [text, EXAMPLE.name])
            page.wait_for_timeout(100)
            r = page.evaluate(LIGHT_UP, [appearance, palette, slot])
            assert r['appearance'] == appearance, r
            assert r['lit'] and r['both'] == 1, ('w3 is lit in the clock high half with the lever up', appearance, palette, slot, r)
            seen.append((appearance, palette, slot, r['stroke']))
            return r

        for appearance in ('dark', 'light'):
            r = run(appearance, 'system-default', 6)
            assert r['stroke'] == EXPECTED[appearance], (appearance, 'system-default slot 6 lit tone', r['stroke'], EXPECTED[appearance])
            assert r['wireLit'] == EXPECTED[appearance], r
            svg = page.evaluate('()=>SovSchematicAPI.render.svg({})')
            assert 'level-high' not in svg and '--wire-lit' not in svg, (appearance, 'render.svg carries the run overlay')
            r = run(appearance, 'system-default', 2)
            assert r['stroke'] == r['accent'] and not r['wireLit'], (appearance, 'a slot under 6 keeps the accent', r)
            r = run(appearance, 'okabe-ito', 6)
            assert r['stroke'] == r['litTone'].upper() and r['stroke'] != r['accent'], (appearance, 'okabe-ito slot 6 lit tone', r)
            c = page.evaluate(CLEARED)
            assert c == {'high': 0, 'lit': 0}, (appearance, 'clock.reset clears the lit wires', c)
        assert not errors, errors
        browser.close()
    for row in seen:
        print('lit w3:', *row)
    print('PASS lit wire role QA')


if __name__ == '__main__':
    main()
