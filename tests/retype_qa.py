"""Retyping applies the whole preset, through the bar and through the API (issues #17, #19).

Creation and retype used to be two code paths: `makeComponent` applied a full
preset, the bar handler applied part of one on the way in and nothing on the
way out, and `update` applied none. One `applySymbol` in the data core now
serves creation, the bar, and `update` over API/HTTP/MCP, so a retyped record
is the record a creation would have made: for every primitive and every
Component type, in both directions, dimension, size, glyph, signal mode and
attachment set match a fresh creation of the target, while identity, position,
label and colour stay. Retyping into Path is refused on both surfaces, and the
0D to 2D to 0D chain leaves a clean record after every step.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text()

PRIMITIVES = ['point', 'plane']
COMPONENTS = ['blank', 'act', 'hold', 'buffer', 'gate', 'switch', 'limit', 'receipt', 'observe']

# The shape a creation gives a symbol, read off the record the same way every time.
SHAPE = """(id)=>{const n=window.SovSchematicAPI.get('component',id).result,p=n.config.presentation;
  return {symbolId:n.symbolId,type:n.type,incomplete:!!n.incomplete,dimension:n.form.dimension,body:n.form.body.kind,
    interior:n.form.regions.interior.state,size:p.size||null,graphic:p.graphic.kind,ref:p.graphic.kind==='symbol'?p.graphic.ref:null,
    signalMode:n.config.signalMode,attachmentDefaults:n.config.attachmentDefaults||null,
    points:window.SovSchematicAttachment.pointSpecs(n).map(s=>s.compatId),
    glyph:[...document.querySelectorAll(`.node[data-id="${id}"] use.glyph`)].map(u=>u.getAttribute('href')),
    canvasDimension:n.canvas.dimension,canvasState:n.canvas.state}}"""
IDENTITY = "(id)=>{const n=window.SovSchematicAPI.get('component',id).result;return {id:n.id,x:n.x,y:n.y,label:n.config.label,colorSlot:n.config.colorSlot}}"


def create(page, symbol, x, y, label=''):
    return page.evaluate("([s,x,y,l])=>window.SovSchematicAPI.create('component',{symbolId:s,x,y,config:{label:l}}).result.id",
                         [symbol, x, y, label])


def retype_api(page, cid, symbol):
    return page.evaluate("([id,s])=>window.SovSchematicAPI.update('component',id,{symbolId:s})", [cid, symbol])


def retype_bar(page, cid, symbol):
    page.evaluate("([id,s])=>{selectNode(id);barComponentType.value=s;barComponentType.dispatchEvent(new Event('change',{bubbles:true}))}",
                  [cid, symbol])
    page.wait_for_timeout(40)


with sync_playwright() as p:
    b = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = b.new_page(viewport={'width': 1400, 'height': 900})
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(300)

    # Reference shapes: what a fresh creation of each symbol looks like.
    reference = {}
    for symbol in PRIMITIVES + COMPONENTS:
        rid = create(page, symbol, 100, 100)
        reference[symbol] = page.evaluate(SHAPE, rid)
        page.evaluate("(id)=>window.SovSchematicAPI.delete('component',id)", rid)
    assert reference['point']['points'] == ['out'] and reference['plane']['points'] == [], reference
    assert reference['act']['points'] == ['in', 'out', 'control'] and reference['act']['dimension'] == 2, reference['act']

    # The bar offers a static option list; it can only retype to what it offers (#18, #20
    # make that list data). The API takes every Component type.
    bar_offers = page.evaluate("()=>[...barComponentType.options].map(o=>o.value)")
    assert set(PRIMITIVES) <= set(bar_offers) and 'act' in bar_offers, bar_offers

    for surface, retype in (('api', retype_api), ('bar', retype_bar)):
        for primitive in PRIMITIVES:
            for component in [c for c in COMPONENTS if surface == 'api' or c in bar_offers]:
                cid = create(page, primitive, 400, 400, label='keep')
                before = page.evaluate(IDENTITY, cid)
                page.evaluate("(id)=>window.SovSchematicAPI.update('component',id,{config:{colorSlot:3}})", cid)

                retype(page, cid, component)
                got = page.evaluate(SHAPE, cid)
                assert got == reference[component], (surface, primitive, '->', component, got, reference[component])

                retype(page, cid, primitive)
                back = page.evaluate(SHAPE, cid)
                assert back == reference[primitive], (surface, component, '->', primitive, back, reference[primitive])

                after = page.evaluate(IDENTITY, cid)
                assert after == {**before, 'colorSlot': 3}, (surface, primitive, component, before, after)
                page.evaluate("(id)=>window.SovSchematicAPI.delete('component',id)", cid)

    # Path is a carrier: refused on both surfaces, record untouched.
    cid = create(page, 'point', 500, 500)
    receipt = retype_api(page, cid, 'path')
    assert receipt['ok'] is False and 'CARRIER_SYMBOL' in receipt['error']['message'], receipt
    assert page.evaluate(SHAPE, cid) == reference['point']
    retype_bar(page, cid, 'path')
    assert page.evaluate(SHAPE, cid) == reference['point']
    assert page.evaluate("()=>barComponentType.value") == 'point'
    assert page.evaluate("()=>statusEl.textContent") == 'Draw a Path from the palette'

    # The chain: Point to Plane to Point, through the bar, clean after every step.
    retype_bar(page, cid, 'plane')
    assert page.evaluate(SHAPE, cid) == reference['plane']
    retype_bar(page, cid, 'point')
    assert page.evaluate(SHAPE, cid) == reference['point']

    # A patch that carries its own fields alongside the retype keeps them over the preset.
    cid2 = create(page, 'point', 700, 700)
    page.evaluate("(id)=>window.SovSchematicAPI.update('component',id,{symbolId:'plane',config:{presentation:{size:{w:200,h:120}}}})", cid2)
    got = page.evaluate(SHAPE, cid2)
    assert got['dimension'] == 2 and got['size'] == {'w': 200, 'h': 120}, got

    assert not errors, f'page errors: {errors}'
    b.close()

print('PASS retype QA')
