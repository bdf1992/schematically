"""Label contrast floor QA: every label holds 4.5:1 against what is drawn behind it.

Each document is opened in headless Chromium, fitted, and measured with layout.metrics({static: true})
in light and in dark. Card text, status chips, waits-on lines, group titles, wire captions and channel
tags take their role ink, darkened (lightened in dark) only as far as the floor against the colour
actually behind them, and text is drawn opaque: a status's opacity fades the card's body, glyph,
leads, ports and marks, not its title.

Asserted:
  - text-contrast is 0 for tests/fixtures/task-lifecycle.sov, tests/fixtures/work-engine-sample.sov,
    docs/workengine/map.sov and examples/work-engine/status.sov, in light and in dark (counts printed,
    with mark-contrast, which is reported and not required to fall);
  - a card whose status is missing has its body at opacity 0.55 while its title is opaque;
  - the page logs no errors.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

DOCS = [
    'tests/fixtures/task-lifecycle.sov',
    'tests/fixtures/work-engine-sample.sov',
    'docs/workengine/map.sov',
    'examples/work-engine/status.sov',
]

MEASURE = r"""()=>{
  const A=window.SovSchematicAPI;
  fitDiagram();
  const m=A.layout.metrics({static:true}),c=A.layout.contrast({static:true});
  return {counts:m.counts,text:c.findings.filter(f=>f.kind==='text-contrast').slice(0,6).map(f=>f.detail)};
}"""

MISSING = r"""()=>{
  const A=window.SovSchematicAPI;
  const card=document.querySelector('.node[data-id="anchor"]');
  if(!card)return null;
  const op=el=>{let o=1;for(let e=el;e&&e!==document.body;e=e.parentElement){const v=getComputedStyle(e).opacity;o*=Number(v)}return o};
  const body=card.querySelector(':scope > .body'),title=card.querySelector(':scope > text.component-label');
  const texts=[...card.querySelectorAll('text')].filter(t=>(t.textContent||'').trim());
  return {body:op(body),title:title?op(title):null,texts:texts.map(t=>[t.getAttribute('class')||t.dataset.role,op(t)])};
}"""

results = {}
with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)
    missing = None
    for appearance in ['light', 'dark']:
        page.evaluate('(m)=>SovSchematicAPI.view.setAppearance(m)', appearance)
        for rel in DOCS:
            src = ROOT / rel
            page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [src.read_text(encoding='utf-8'), src.name])
            page.wait_for_timeout(200)
            results[(rel, appearance)] = page.evaluate(MEASURE)
            if rel.endswith('status.sov') and appearance == 'light':
                missing = page.evaluate(MISSING)
    browser.close()

for (rel, appearance), r in results.items():
    print(f"{rel} {appearance}: text-contrast {r['counts'].get('text-contrast', 0)} mark-contrast {r['counts'].get('mark-contrast', 0)}")
assert not errors, errors
for (rel, appearance), r in results.items():
    assert r['counts'].get('text-contrast', 0) == 0, (rel, appearance, r['counts'], r['text'])

assert missing, 'examples/work-engine/status.sov has no card with id anchor'
assert abs(missing['body'] - 0.55) < 0.01, ('a missing-status card body is drawn at 0.55', missing)
assert missing['title'] is not None and missing['title'] >= 0.99, ('the title of a missing-status card is opaque', missing)
assert all(o >= 0.99 for _, o in missing['texts']), ('every text of a missing-status card is opaque', missing)
print('LABEL CONTRAST FLOOR QA PASS')
