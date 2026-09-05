"""A primitive's label is rendered once it exists (issue #16).

The Point / Path / Plane presets used to carry `labelMode: 'none'`, and the
label input only ever wrote `config.label`, so a label typed on a Path or a
Plane was stored and never drawn. The presets no longer carry a mode. The data
core reads one instead: an authored mode as written; otherwise 'none' while
there is no label, and the form's default ('outside' under 0D and 1D,
'boundary' under 2D) once a label exists, through the bar, `create`, and
`update`. A record saved by an earlier build carries an authored 'none' on
every primitive; the first label typed onto such a record adopts the form's
default, while a label edited under 'none' with a label already present stays
hidden. Nothing is written onto a loaded record.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text()

EXPECTED_MODE = {'point': 'outside', 'path': 'outside', 'plane': 'boundary'}

TEXTS = """(id)=>[...document.querySelectorAll(`.node[data-id="${id}"] text`)].map(t=>t.textContent.trim())"""
RECORD = "(id)=>window.SovSchematicAPI.get('component',id).result"
MODE = "(id)=>window.SovSchematicData.effectiveLabelMode(window.SovSchematicAPI.get('component',id).result)"


with sync_playwright() as p:
    b = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = b.new_page(viewport={'width': 1400, 'height': 900})
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(300)

    y = 160
    for symbol, expected in EXPECTED_MODE.items():
        # Born without a label: the record carries no mode, it reads 'none', nothing is drawn.
        rec = page.evaluate("([s,y])=>window.SovSchematicAPI.create('component',{symbolId:s,x:300,y}).result", [symbol, y])
        cid = rec['id']
        assert 'labelMode' not in rec['config']['presentation'], (symbol, rec['config']['presentation'])
        assert page.evaluate(MODE, cid) == 'none', (symbol, page.evaluate(MODE, cid))
        assert page.evaluate(TEXTS, cid) == [], (symbol, page.evaluate(TEXTS, cid))

        # Typed in the bar: the mode follows the form and the label is drawn.
        page.evaluate("(id)=>{selectNode(id);barComponentLabel.value='test';"
                      "barComponentLabel.dispatchEvent(new Event('input',{bubbles:true}))}", cid)
        page.wait_for_timeout(80)
        assert page.evaluate(MODE, cid) == expected, (symbol, 'bar', page.evaluate(MODE, cid))
        assert 'test' in page.evaluate(TEXTS, cid), (symbol, 'bar', page.evaluate(TEXTS, cid))
        page.evaluate("(id)=>syncComponentVisualPanel(nodes.find(n=>n.id===id))", cid)
        assert page.evaluate("()=>visualLabelMode.value") == expected, (symbol, 'panel', page.evaluate("()=>visualLabelMode.value"))

        # Created with a label through the API: same result, still nothing written.
        created = page.evaluate("([s,y])=>window.SovSchematicAPI.create('component',{symbolId:s,x:800,y,config:{label:'born'}}).result", [symbol, y])
        assert 'labelMode' not in created['config']['presentation'], (symbol, 'create', created['config']['presentation'])
        assert page.evaluate(MODE, created['id']) == expected, (symbol, 'create')
        assert 'born' in page.evaluate(TEXTS, created['id']), (symbol, 'create', page.evaluate(TEXTS, created['id']))

        # Labelled later through the API: the same reading applies.
        later = page.evaluate("([s,y])=>window.SovSchematicAPI.create('component',{symbolId:s,x:1200,y}).result.id", [symbol, y])
        page.evaluate("(id)=>window.SovSchematicAPI.update('component',id,{config:{label:'later'}})", later)
        page.wait_for_timeout(80)
        assert page.evaluate(MODE, later) == expected, (symbol, 'update', page.evaluate(MODE, later))
        assert 'later' in page.evaluate(TEXTS, later), (symbol, 'update', page.evaluate(TEXTS, later))
        y += 300

    # A typed Component keeps its type caption: the derivation is for primitives only.
    for symbol in ('act', 'hold', 'gate'):
        typed = page.evaluate("([s])=>window.SovSchematicAPI.create('component',{symbolId:s,x:1000,y:1100}).result.id", [symbol])
        assert page.evaluate(MODE, typed) == 'boundary', (symbol, page.evaluate(MODE, typed))
        assert symbol.upper() in page.evaluate(TEXTS, typed), (symbol, 'caption', page.evaluate(TEXTS, typed))

    # A record from an earlier build: authored 'none', no label. The first label adopts the form's default.
    old = page.evaluate("()=>window.SovSchematicAPI.create('component',{symbolId:'path',x:300,y:1100,"
                        "config:{presentation:{labelMode:'none'}}}).result.id")
    page.evaluate("(id)=>window.SovSchematicAPI.update('component',id,{config:{label:'adopted'}})", old)
    page.wait_for_timeout(80)
    assert page.evaluate(RECORD, old)['config']['presentation']['labelMode'] == 'outside', page.evaluate(RECORD, old)['config']['presentation']
    assert 'adopted' in page.evaluate(TEXTS, old), page.evaluate(TEXTS, old)

    # An authored 'none' with a label already present is a choice: editing the label keeps it hidden.
    hidden = page.evaluate("()=>window.SovSchematicAPI.create('component',{symbolId:'plane',x:800,y:1100,"
                           "config:{label:'a',presentation:{labelMode:'none'}}}).result.id")
    assert page.evaluate(MODE, hidden) == 'none'
    page.evaluate("(id)=>window.SovSchematicAPI.update('component',id,{config:{label:'b'}})", hidden)
    page.wait_for_timeout(80)
    assert page.evaluate(MODE, hidden) == 'none', page.evaluate(MODE, hidden)
    assert page.evaluate(TEXTS, hidden) == [], page.evaluate(TEXTS, hidden)

    # Save and reload: the labels come back because the reading, not the record, carries the mode.
    saved = page.evaluate("()=>JSON.stringify(window.SovSchematicData.compactDocument(window.SovSchematicAPI.document.get()))")
    import json
    written = {c['id']: c['config']['presentation'].get('labelMode') for c in json.loads(saved)['components']
               if 'labelMode' in (c.get('config', {}).get('presentation') or {})}
    assert written == {old: 'outside', hidden: 'none'}, f'a derived mode was written into the save: {written}'
    page.evaluate("(text)=>window.SovSchematicAPI.document.replace(JSON.parse(text))", saved)
    page.wait_for_timeout(150)
    for symbol in EXPECTED_MODE:
        labelled = [c for c in page.evaluate("()=>window.SovSchematicAPI.list('component').result")
                    if c['symbolId'] == symbol and c['config']['label'] == 'born']
        assert labelled, symbol
        assert 'born' in page.evaluate(TEXTS, labelled[0]['id']), (symbol, 'reload')

    assert not errors, f'page errors: {errors}'
    b.close()

print('PASS primitive label QA')
