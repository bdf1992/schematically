"""Glyph size rule in the editor (VISUAL-LANGUAGE.md, agreed in the bake-off).

A gate's glyph may carry a small variant (`presentation.graphic.svgSmall`, its IEC rectangle).
Below GLYPH_MIN_PX of drawn height the distinctive shape stops being distinguishable, so the
renderer shows the small variant instead. Checked here in the running editor:

  - at every zoom, each gate shows exactly one variant;
  - a gate shows its small variant exactly when its glyph box height x zoom is under 40 px,
    computed here from the box height the page reports and the zoom set here;
  - zooming back restores the full glyph (the rule follows the camera, not only renders);
  - the view API reports and sets zoom;
  - the small variant survives the file round trip (document.get after open);
  - only distinctive-shape gates carry a small variant; a gate without one always shows its
    single glyph, and nothing without one is compacted.
"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text()
DOC = (ROOT / 'examples' / 'logic' / 'gates.sov').read_text()

STATE = """()=>{const out=[];
  for(const g of document.querySelectorAll('#nodes .node, .node')){
    const full=g.querySelector(':scope > .custom-graphic.glyph-full, .custom-graphic.glyph-full');
    const small=g.querySelector(':scope > .custom-graphic.glyph-small, .custom-graphic.glyph-small');
    if(!full&&!small)continue;
    const vis=el=>!!el&&getComputedStyle(el).display!=='none';
    out.push({id:g.dataset.id,h:Number(g.dataset.glyphH),full:vis(full),small:vis(small)});
  }
  return {zoom:window.SovSchematicAPI.view.zoom(),nodes:out};}"""


def run() -> None:
    with sync_playwright() as p:
        b = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content(HTML, wait_until='load')
        page.wait_for_timeout(250)
        page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [DOC, 'gates.sov'])
        page.wait_for_timeout(250)

        doc = page.evaluate('()=>window.SovSchematicAPI.document.get()')
        doc = doc.get('result', doc)
        gates = [c for c in doc['components'] if (c.get('config') or {}).get('definition')]
        # Distinctive-shape gates carry their rectangle as svgSmall; rectangle gates already are it.
        table = json.loads((ROOT / 'data' / 'logic.glyphs.json').read_text(encoding='utf-8'))['glyphs']
        shaped = [c for c in gates if table[c['config']['definition']]['family'] == 'distinctive']
        assert len(shaped) == 8, len(shaped)
        for c in gates:
            has = bool(c['config']['presentation']['graphic'].get('svgSmall'))
            assert has == (c in shaped), ('svgSmall kept through open exactly for distinctive gates', c['id'])
        rectangles = len(gates) - len(shaped)
        gates = shaped

        for zoom in (1.5, 1.0, 0.8, 0.5, 0.3, 1.2):
            got = page.evaluate('(z)=>window.SovSchematicAPI.view.setZoom(z)', zoom)
            assert abs(got - zoom) < 1e-6, (zoom, got)
            state = page.evaluate(STATE)
            assert len(state['nodes']) == len(gates), (zoom, len(state['nodes']), len(gates))
            for n in state['nodes']:
                assert n['full'] != n['small'], ('exactly one variant', zoom, n)
                compact = n['h'] * zoom < 40
                assert n['small'] == compact, (zoom, n)
        # Some zoom in the sweep must show each variant, or the check proves nothing.
        page.evaluate('(z)=>window.SovSchematicAPI.view.setZoom(z)', 0.3)
        assert all(n['small'] for n in page.evaluate(STATE)['nodes'])
        page.evaluate('(z)=>window.SovSchematicAPI.view.setZoom(z)', 1.5)
        assert all(n['full'] for n in page.evaluate(STATE)['nodes'])

        # Rectangle gates have one glyph, always shown; nothing without a small variant is compacted.
        singles = page.evaluate("()=>[...document.querySelectorAll('.node')].filter(g=>!g.dataset.glyphH&&g.querySelector('.custom-graphic')).map(g=>getComputedStyle(g.querySelector('.custom-graphic')).display)")
        assert len(singles) == rectangles and 'none' not in singles, (rectangles, singles)
        # Inputs and outputs carry no custom glyph and are untouched by the rule.
        untouched = page.evaluate("()=>[...document.querySelectorAll('.node')].filter(g=>!g.dataset.glyphH&&g.classList.contains('glyph-compact')).length")
        assert untouched == 0, untouched
        assert not errors, errors
        b.close()


if __name__ == '__main__':
    run()
    print('glyph_size_rule QA PASS')
