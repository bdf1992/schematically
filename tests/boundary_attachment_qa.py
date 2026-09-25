"""Boundary attachment + seamless terminal QA.

A card's own points can be placed anywhere on its perimeter (config.ports.<id>.boundary):
by Alt-dragging the point (round corners, snapped to eighths, one history step, refused when
pinned) or by a CRUD patch (the agent path). An unplaced side point sits on the symbol's axis,
which is the card's centre line; the wire meets the body edge exactly, and an inner lead
joins the edge to the symbol.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')
DOC = {'schema': 'soveraeign.schematic/document@0.1', 'id': 'slide', 'components': [
    {'id': 'a', 'symbolId': 'act', 'x': 300, 'y': 300, 'config': {'label': 'A'}},
    {'id': 'b', 'symbolId': 'buffer', 'x': 700, 'y': 300, 'config': {'label': 'B'}}],
    'wires': [{'id': 'w', 'a': 'a', 'aSide': 'out', 'b': 'b', 'bSide': 'in'}]}

with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.set_content(HTML, wait_until='load'); page.wait_for_timeout(150)
    page.evaluate('(d)=>{SovSchematicAPI.document.replace(d);fitDiagram()}', DOC); page.wait_for_timeout(150)

    # Seamless: the side points sit on the centre line, the wire starts on the body edge,
    # and a lead joins each wired edge to its symbol.
    g = page.evaluate('''()=>{const a=nodes.find(n=>n.id==='a'),b=nodes.find(n=>n.id==='b'),w=wires[0];
      const A=portPos(a,'out'),B=portPos(b,'in'),d=document.querySelector('.wire-group[data-wire-id="w"] path.wire').getAttribute('d');
      const leads=[...document.querySelectorAll('.node .component-lead')].map(l=>({id:l.closest('.node').dataset.id,x1:+l.getAttribute('x1'),x2:+l.getAttribute('x2'),y:+l.getAttribute('y1')}));
      return {A,B,ax:a.x,ay:a.y,aw:componentSize(a).w,bx:b.x,bw:componentSize(b).w,d,leads}}''')
    assert abs(g['A']['y'] - g['ay']) < .01 and abs(g['B']['y'] - g['ay']) < .01, g
    assert abs(g['A']['x'] - (g['ax'] + g['aw'] / 2)) < .01 and abs(g['B']['x'] - (g['bx'] - g['bw'] / 2)) < .01, g
    assert g['d'].startswith(f"M {g['A']['x']:g} ") or g['d'].startswith(f"M {g['A']['x']}"), g['d']
    assert sorted(l['id'] for l in g['leads']) == ['a', 'b'] and all(l['y'] == 0 for l in g['leads']), g['leads']

    def port_center(node, point):
        return page.evaluate('''([n,p])=>{const r=document.querySelector(`.node[data-id="${n}"] .port-hit[data-point="${p}"]`).getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]}''', [node, point])
    def world_to_screen(x, y):
        return page.evaluate('''([x,y])=>{const m=workspace.getScreenCTM();const q=new DOMPoint(x,y).matrixTransform(m);return [q.x,q.y]}''', [x, y])

    # Alt-drag A's right point down past the bottom-right corner: it rounds the corner.
    sx, sy = port_center('a', 'right')
    tx, ty = world_to_screen(300 + 20, 300 + 80)
    page.keyboard.down('Alt'); page.mouse.move(sx, sy); page.mouse.down()
    page.mouse.move((sx + tx) / 2, (sy + ty) / 2, steps=4); page.mouse.move(tx, ty, steps=6); page.mouse.up(); page.keyboard.up('Alt')
    page.wait_for_timeout(100)
    moved = page.evaluate('''()=>({b:componentConfig(nodes.find(n=>n.id==='a')).ports.out.boundary,side:physicalPortSide(nodes.find(n=>n.id==='a'),'out'),wires:wires.length,A:portPos(nodes.find(n=>n.id==='a'),'out')})''')
    assert moved['b']['side'] == 'bottom' and moved['side'] == 'bottom', moved
    assert abs(moved['b']['t'] * 8 - round(moved['b']['t'] * 8)) < 1e-9, 'snapped to eighths'
    assert moved['wires'] == 1, 'sliding a point never starts a wire'
    # It persists as data and leaves the card's leads: a placed point is off the axis.
    doc = page.evaluate('()=>SovSchematicAPI.file.document()')
    assert next(c for c in doc['components'] if c['id'] == 'a')['config']['ports']['out']['boundary']['side'] == 'bottom'
    assert page.evaluate('''()=>[...document.querySelectorAll('.node[data-id="a"] .component-lead')].length''') == 0
    # One gesture, one history step.
    page.evaluate('()=>SovSchematicAPI.history.undo()'); page.wait_for_timeout(50)
    assert page.evaluate('''()=>componentConfig(nodes.find(n=>n.id==='a')).ports.out.boundary||null''') is None

    # Pinned: geometry is frozen, the gesture is refused and nothing moves.
    page.evaluate('''()=>{entityEditorState(nodes.find(n=>n.id==='a')).pinned=true;render()}''')
    sx, sy = port_center('a', 'right')
    page.keyboard.down('Alt'); page.mouse.move(sx, sy); page.mouse.down(); page.mouse.move(tx, ty, steps=6); page.mouse.up(); page.keyboard.up('Alt')
    assert page.evaluate('''()=>componentConfig(nodes.find(n=>n.id==='a')).ports.out.boundary||null''') is None
    page.evaluate('''()=>{entityEditorState(nodes.find(n=>n.id==='a')).pinned=false;render()}''')

    # The agent path: a CRUD patch places the point; the route follows it.
    r = page.evaluate('''()=>SovSchematicAPI.update('component','b',{config:{ports:{in:{boundary:{side:'top',t:.25}}}}})''')
    assert r['ok'], r
    placed = page.evaluate('''()=>{const b=nodes.find(n=>n.id==='b');return {side:physicalPortSide(b,'in'),P:portPos(b,'in'),top:b.y-componentSize(b).h/2,left:b.x-componentSize(b).w/2,w:componentSize(b).w}}''')
    assert placed['side'] == 'top' and abs(placed['P']['y'] - placed['top']) < .01 and abs(placed['P']['x'] - (placed['left'] + placed['w'] * .25)) < .01, placed
    assert not errors, errors
    browser.close()
print('PASS boundary attachment + seamless terminal QA')
