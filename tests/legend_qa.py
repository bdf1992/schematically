"""Legend QA (NOTATION-MODEL.md §5): derived from what the document uses, never authored.

- Marks, glyphs, signal shapes and sections appear only when used; a domain glyph is titled and
  explained by its notation.
- A colour category appears only when a card uses it, named by the document when it names it.
- A document may hide an entry; it cannot add one for something it does not use.
- The panel toggles; a picture carries the legend below the drawing.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)
    text = (ROOT / 'examples' / '13-half-adder.sov').read_text(encoding='utf-8')
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [text, '13-half-adder.sov'])
    page.wait_for_timeout(200)
    half = page.evaluate('()=>SovSchematicAPI.view.legend().entries')
    picture = page.evaluate('()=>SovSchematicAPI.render.svg({legend:true})')
    plain = page.evaluate('()=>SovSchematicAPI.render.svg({})')
    r = page.evaluate(r"""()=>{
      const A=SovSchematicAPI;
      A.document.replace({schema:SovSchematicData.DOCUMENT_SCHEMA,id:'l',legend:{names:{C2:'Refunds'},hide:['mark:in'],extra:[{label:'Invented'}]},components:[
        {id:'x',symbolId:'act',x:100,y:200,config:{colorSlot:7}},{id:'y',symbolId:'hold',x:400,y:200}],
        wires:[{id:'w',a:'x',aSide:'out',b:'y',bSide:'in'}]});
      const entries=A.view.legend().entries;
      const open=A.view.setLegend(true).open,panel=document.getElementById('legendPanel'),rows=panel.querySelectorAll('.legend-row').length,shown=!panel.hidden;
      A.view.setLegend(false);
      return {ids:entries.map(e=>e.id),labels:entries.map(e=>e.label),open,rows,shown,closed:panel.hidden};
    }""")
    browser.close()
assert not errors, errors
ids = [e['id'] for e in half]
assert ids[:4] == ['mark:out', 'mark:in', 'mark:junction', 'mark:hop'], ids
glyphs = {e['id']: e for e in half if e['kind'] == 'glyph'}
assert set(glyphs) == {'glyph:lever', 'glyph:xor2', 'glyph:and2', 'glyph:observe'}, glyphs.keys()
assert glyphs['glyph:xor2']['label'] == 'Exclusive or' and 'exactly one' in glyphs['glyph:xor2']['meaning'], glyphs['glyph:xor2']
assert not [e for e in half if e['kind'] in ('colour', 'section')], 'nothing unused is listed'
assert 'picture-legend' in picture and 'Exclusive or' in picture and 'picture-legend' not in plain
assert r['ids'] == ['mark:out', 'colour:C2', 'glyph:act', 'glyph:hold'], r['ids']
assert 'Refunds' in r['labels'] and 'Invented' not in r['labels'], r['labels']
assert r['open'] is True and r['shown'] and r['rows'] == 4 and r['closed'], r
print('PASS legend QA', {'entries': len(half)})
