"""Native form controls follow the appearance (issue #14).

Dark appearance is applied as custom properties on the root, but a native
<select> popup is painted by the browser from the document's `color-scheme`,
not from those properties. Without `color-scheme` on the appearance root the
popup stays light while the option text inherits the dark ink: light-on-white.

This suite asserts the mechanism the popup follows: the computed
`color-scheme` of the root and of every native select in the bar, the settings
panel and the header menus matches the resolved appearance, in explicit light,
explicit dark, and system mode under both OS preferences.
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text()

# One native select from each surface the issue names: header menu, selection
# bar, Form section, settings panel.
SELECTS = ['#appearanceMode', '#globalRate', '#colorThemeInput', '#gridSizeInput',
           '#barComponentType', '#barConnectionDirection', '#barPortSide',
           '#formDimension', '#formInteriorState', '#formAttachments', '#entityRate']

READ = """(ids)=>{
  const cs=(el)=>getComputedStyle(el).colorScheme;
  const out={root:cs(document.documentElement),appearance:document.documentElement.dataset.appearance,selects:{}};
  for(const id of ids){const el=document.querySelector(id);out.selects[id]=el?cs(el):'MISSING'}
  return out;
}"""


def check(page, expected, label):
    page.wait_for_timeout(120)
    state = page.evaluate(READ, SELECTS)
    assert state['appearance'] == expected, f'{label}: root appearance is {state["appearance"]}'
    assert state['root'] == expected, f'{label}: root color-scheme is {state["root"]!r}, expected {expected!r}'
    wrong = {k: v for k, v in state['selects'].items() if v != expected}
    assert not wrong, f'{label}: selects not following {expected}: {wrong}'


with sync_playwright() as p:
    b = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    for os_scheme in ('light', 'dark'):
        context = b.new_context(viewport={'width': 1280, 'height': 800}, color_scheme=os_scheme)
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content(HTML, wait_until='load')
        page.wait_for_timeout(300)

        page.evaluate("()=>window.SovSchematicAPI.view.setAppearance('system')")
        check(page, os_scheme, f'system under OS {os_scheme}')

        page.evaluate("()=>window.SovSchematicAPI.view.setAppearance('dark')")
        check(page, 'dark', f'explicit dark under OS {os_scheme}')

        # A selected Point puts the bar's type select on screen; its popup is
        # the case the issue reports. Focusing it must not change the scheme.
        page.evaluate("()=>{const A=window.SovSchematicAPI;"
                      "const n=A.create('component',{symbolId:'point',x:300,y:300}).result;selectNode(n.id)}")
        page.wait_for_timeout(150)
        page.focus('#barComponentType')
        check(page, 'dark', f'bar type select focused under OS {os_scheme}')

        page.evaluate("()=>window.SovSchematicAPI.view.setAppearance('light')")
        check(page, 'light', f'explicit light under OS {os_scheme}')

        assert not errors, f'page errors: {errors}'
        context.close()
    b.close()

print('PASS appearance color-scheme QA')
