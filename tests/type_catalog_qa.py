"""One control for dimension and type (issue #20).

Dimension is a property of the type, not a separate control. One list, the symbol catalog, is read
by the palette and by the selection bar's type control: Point, Path, Plane, then the Component types,
the Signals, then the glyphs the active notation adds, every entry carrying its dimension. The Form
section's Dimension selector is gone; the bar badge and the Form section read the dimension out.
Retyping through the bar is the one way a Component's dimension changes, and it goes through the
same preset a creation does. Driven through the real select.
"""
from __future__ import annotations
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')

CATALOG = "()=>symbolCatalog().map(g=>({group:g.group,ids:g.entries.map(e=>e.id),dims:g.entries.map(e=>e.dimension),names:g.entries.map(e=>e.name)}))"
BAR = "()=>[...barComponentType.options].map(o=>[o.parentElement.label,o.value,o.textContent])"
PALETTE = "()=>[...palette.querySelectorAll('.section')].map(s=>[s.querySelector('h2').textContent,[...s.querySelectorAll('.symbol-card')].map(b=>b.dataset.symbolId)])"
SHAPE = "(id)=>{const n=nodes.find(x=>x.id===id);return {symbolId:n.symbolId,dimension:n.form.dimension,body:n.form.body.kind,points:Attachment.pointSpecs(n).map(s=>s.id),badge:barFormState.textContent,readout:formDimensionReadout.textContent,bar:barComponentType.value,name:iName.textContent}}"


def flatten(catalog):
    return [(g['group'], i, f"{n} · {d}D") for g in catalog for i, n, d in zip(g['ids'], g['names'], g['dims'])]


def select_type(page, symbol):
    page.locator('#barComponentType').select_option(symbol)
    page.wait_for_timeout(120)


with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(300)
    page.evaluate('newSchematic()')
    page.evaluate("()=>{SovSchematicAPI.create('component',{id:'a',symbolId:'act',x:400,y:300});render();selectNode('a');openSelectionSettings('component')}")
    page.wait_for_timeout(150)

    # 1. The Dimension selector is gone; the Form section reads the dimension out.
    assert page.evaluate("()=>document.getElementById('formDimension')") is None
    s = page.evaluate(SHAPE, 'a')
    assert s['badge'] == '2D' and s['readout'] == '2D · Surface · Act', s

    # 2. One list. Point, Path, Plane first with their dimensions, then the Component types and the
    #    Signals, all 2D; the bar's options and the palette's cards are that list, in that order.
    catalog = page.evaluate(CATALOG)
    assert catalog[0] == {'group': 'Primitives', 'ids': ['point', 'path', 'plane'], 'dims': [0, 1, 2], 'names': ['Point', 'Path', 'Plane']}, catalog[0]
    assert [g['group'] for g in catalog] == ['Primitives', 'Components', 'Signals'], [g['group'] for g in catalog]
    assert catalog[1]['ids'] == ['blank', 'act', 'hold', 'buffer', 'gate', 'switch', 'limit', 'receipt', 'observe'], catalog[1]
    assert all(d == 2 for g in catalog[1:] for d in g['dims']), catalog
    assert page.evaluate(BAR) == [list(x) for x in flatten(catalog)], page.evaluate(BAR)
    assert page.evaluate(PALETTE) == [[g['group'], g['ids']] for g in catalog], page.evaluate(PALETTE)

    # 3. Dimension follows the type, through the one control: 2D Act to 0D Point to 2D Plane to a
    #    Signal, each the preset a creation gives, with the badge and the read-out following.
    select_type(page, 'point')
    s = page.evaluate(SHAPE, 'a')
    assert (s['symbolId'], s['dimension'], s['body'], s['points'], s['badge'], s['bar']) == ('point', 0, 'point', ['self'], '0D', 'point'), s
    assert s['readout'].startswith('0D · Point'), s
    select_type(page, 'plane')
    s = page.evaluate(SHAPE, 'a')
    assert (s['symbolId'], s['dimension'], s['points'], s['badge']) == ('plane', 2, [], '2D'), s
    select_type(page, 'clock')
    s = page.evaluate(SHAPE, 'a')
    assert (s['symbolId'], s['dimension'], s['badge'], s['bar']) == ('clock', 2, '2D', 'clock'), s
    assert s['points'] == ['left', 'right', 'top'], s

    # 4. A Path is a carrier drawn from the palette, never a retype target; the control springs back.
    select_type(page, 'path')
    s = page.evaluate(SHAPE, 'a')
    assert s['symbolId'] == 'clock' and s['bar'] == 'clock', s
    assert page.locator('#status').inner_text() == 'Draw a Path from the palette'

    # 5. A notation adds its glyphs to the same list, in the bar and in the palette alike, and a
    #    Component retypes into one of them: the gate's terminals become its points (#54) and the
    #    inspector names it from the notation (#55). Back on the plain notation the group is gone.
    adder = (ROOT / 'examples/13-half-adder.sov').read_text(encoding='utf-8')
    page.evaluate("(text)=>{SovSchematicAPI.file.open(text,'13-half-adder.sov');render()}", adder)
    page.wait_for_timeout(200)
    page.evaluate("()=>{SovSchematicAPI.create('component',{id:'g',symbolId:'act',x:900,y:600});render();selectNode('g')}")
    page.wait_for_timeout(120)
    catalog = page.evaluate(CATALOG)
    gates = next((g for g in catalog if 'and2' in g['ids']), None)
    assert gates and gates['group'] == 'Logic gates' and gates['ids'][:3] == ['and2', 'or2', 'xor2'] and set(gates['dims']) == {2}, catalog
    assert ('Logic gates', 'xor2', 'Exclusive or · 2D') in flatten(catalog)
    assert page.evaluate(BAR) == [list(x) for x in flatten(catalog)], page.evaluate(BAR)
    assert page.evaluate(PALETTE) == [[g['group'], g['ids']] for g in catalog], page.evaluate(PALETTE)
    select_type(page, 'xor2')
    s = page.evaluate(SHAPE, 'g')
    assert (s['symbolId'], s['dimension'], s['points'], s['badge'], s['name']) == ('xor2', 2, ['a', 'b', 'y'], '2D', 'Exclusive or'), s
    # The document was edited, so New asks first; it is answered yes.
    page.once('dialog', lambda d: d.accept())
    page.evaluate("()=>{newSchematic();SovSchematicAPI.create('component',{id:'b',symbolId:'hold',x:400,y:300});render();selectNode('b')}")
    page.wait_for_timeout(120)
    assert page.evaluate("()=>[diagram.notation??'schematic',nodes.length]") == ['schematic', 1]
    assert 'xor2' not in [row[1] for row in page.evaluate(BAR)], page.evaluate(BAR)
    assert [g['group'] for g in page.evaluate(CATALOG)] == ['Primitives', 'Components', 'Signals']

    assert not errors, errors
    browser.close()
    print('PASS type catalog QA')
