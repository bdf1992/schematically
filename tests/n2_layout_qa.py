"""N-squared layout QA: layout.apply with engine n2 (LAYOUT-MODEL.md "What n2 does").

n2 writes a stored layout in which the cards of a canvas sit on the diagonal in document order,
group by group, and every wire between two of them is a pinned route of one point: the corner at
(receiver column, sender row). The view also holds the side each wired port is drawn on (outcomes
right and intakes top for forward wires; left and bottom for feedback), because one corner can only
be drawn between a port that faces along the row and a port that faces along the column
("As built: port sides per layout"). No record changes.

- Three act cards and three wires, one of them feedback (c to a):
  - n2 on the default layout with no `into` is refused with DEFAULT_LAYOUT and changes nothing;
  - into a new layout: card i at (x0 + i * pitch, y0 + i * pitch), the pitch clearing the largest card;
  - every wire is drawn with exactly one corner, the stored point, on the sender's row (the y of the
    sender's port) and the receiver's column (the x of the receiver's port); it leaves the sender
    horizontally and enters the receiver vertically, each end on its port on the card's edge;
  - the two forward wires turn above the diagonal, the feedback wire below it;
  - layout.metrics counts no port-wrong-side and no port-undrawn;
  - the saved document's components and wires are the ones it had, and the shared core leaves the
    components, the wires and the default layout's record byte-identical;
  - sliding a port the view places moves it in the view, not in the record;
  - with the default layout selected every port is back where the record puts it and every wire is
    drawn as it was before;
  - the saved document, opened again, draws the n2 layout the same;
  - ensure() drops a placement naming a missing card, a missing port or no valid side, and clamps t.
- The same three cards with b's intake fed forward and back and b's outcome sent forward and back:
  each port keeps the forward side, the two forward wires are pinned with one corner, and the two
  feedback wires are left to the router and listed in the receipt as PORT_SHARED.
- examples/work-engine/groups.sov (two groups, five cards, three wires, two of them feedback): the
  same placement and route assertions, each group's cards next to each other on the diagonal, and
  unchanged records.
- The page logs no errors.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

SCHEMA = 'soveraeign.schematic/document@0.1'
GLOBAL = 'canvas:global'
THREE = {'schema': SCHEMA, 'id': 'n2-three',
         'components': [{'id': 'a', 'symbolId': 'act', 'x': 200, 'y': 300}, {'id': 'b', 'symbolId': 'act', 'x': 500, 'y': 300},
                        {'id': 'c', 'symbolId': 'act', 'x': 800, 'y': 300}],
         'wires': [{'id': 'ab', 'a': 'a', 'aSide': 'out', 'b': 'b', 'bSide': 'in'},
                   {'id': 'bc', 'a': 'b', 'aSide': 'out', 'b': 'c', 'bSide': 'in'},
                   {'id': 'ca', 'a': 'c', 'aSide': 'out', 'b': 'a', 'bSide': 'in'}]}
# b's intake is fed forward (from a) and back (from c); b's outcome goes forward (to c) and back (to a).
BOTH = {'schema': SCHEMA, 'id': 'n2-both',
        'components': THREE['components'],
        'wires': [{'id': 'ab', 'a': 'a', 'aSide': 'out', 'b': 'b', 'bSide': 'in'}, {'id': 'cb', 'a': 'c', 'aSide': 'out', 'b': 'b', 'bSide': 'in'},
                  {'id': 'ba', 'a': 'b', 'aSide': 'out', 'b': 'a', 'bSide': 'in'}, {'id': 'bc', 'a': 'b', 'aSide': 'out', 'b': 'c', 'bSide': 'in'}]}
GROUPS = ROOT / 'examples' / 'work-engine' / 'groups.sov'

# Each wire's drawn corners in world space, each card's body and centre, each wired port's drawn
# side and position, and the two port findings of layout.metrics.
READ = r"""()=>{
  const m=SovSchematicAPI.layout.metrics({static:true}),out={wires:{},cards:{},ports:{},counts:{'port-wrong-side':m.counts['port-wrong-side']||0,'port-undrawn':m.counts['port-undrawn']||0}};
  for(const g of workspace.querySelectorAll('.wire-group')){const p=g.querySelector('path.wire');if(p)out.wires[g.dataset.wireId]=layoutRouteCorners(p)}
  for(const n of nodes){if(isGroupComponent(n))continue;const R=componentBounds(n);out.cards[n.id]={l:R.l,r:R.r,t:R.t,b:R.b,x:n.x,y:n.y}}
  for(const w of wires)for(const [id,port] of [[w.a,w.aSide],[w.b,w.bSide]]){const n=nodes.find(x=>x.id===id);if(n)out.ports[id+'|'+port]={side:physicalPortSide(n,port),at:portPos(n,port)}}
  return out}"""
# The shared core alone, on a parsed copy: what an n2 apply leaves of the records and the default layout.
CORE = r"""([t])=>{
  const d=SovSchematicData.documentFromFilePayload(JSON.parse(t)),e=SovSchematicData.clone(d);SovSchematicLayout.ensure(e);
  const records=JSON.stringify([d.components,d.wires]),def=JSON.stringify(e.layout.views[e.layout.default]);
  const r=SovSchematicLayout.execute(d,'apply',{engine:'n2',into:'N2'});
  return {ok:r.ok,records:JSON.stringify([d.components,d.wires])===records,defaultView:JSON.stringify(d.layout.views[d.layout.default])===def,defaultId:d.layout.default===e.layout.default}}"""


def near(a, b, eps=.51):
    return abs(a - b) <= eps


def settle(page):
    page.evaluate('()=>fitDiagram()')
    page.wait_for_timeout(250)
    return page.evaluate(READ)


def open_doc(page, text, name):
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [text, name])
    return settle(page)


def saved(page):
    return page.evaluate('()=>SovSchematicAPI.file.document()')


def records(doc):
    return json.dumps([doc['components'], doc['wires']], sort_keys=True)


def expected_order(doc):
    """Cards of the top-level canvas in document order, group by group (the first group that lists a card)."""
    comps = doc['components']
    cards = [c for c in comps if c.get('symbolId') != 'group' and (c.get('canvasId') or GLOBAL) == GLOBAL
             and (c.get('placement') or {}).get('kind') not in ('edge', 'wire', 'path')]
    block = {}
    for g in comps:
        if g.get('symbolId') == 'group':
            for m in g.get('config', {}).get('members', []):
                block.setdefault(m, g['id'])
    keys = []
    for c in cards:
        k = block.get(c['id'], 'card:' + c['id'])
        if k not in keys:
            keys.append(k)
    return [c['id'] for k in keys for c in cards if block.get(c['id'], 'card:' + c['id']) == k], block


def check_layout(name, doc, receipt, r, view):
    """The diagonal, and every pinned wire's one corner. Returns the wires by direction."""
    order, cards, pitch = receipt['order'], r['cards'], receipt['pitch']
    want, block = expected_order(doc)
    assert order == want, (name, 'document order, group by group', order, want)
    assert receipt['placed'] == len(order) and not receipt['frozen'], (name, receipt)
    side = max(max(c['r'] - c['l'], c['b'] - c['t']) for c in (cards[i] for i in order))
    assert pitch > side, (name, 'the pitch clears the largest card', pitch, side)
    x0, y0 = cards[order[0]]['x'], cards[order[0]]['y']
    for i, cid in enumerate(order):
        assert near(cards[cid]['x'], x0 + i * pitch) and near(cards[cid]['y'], y0 + i * pitch), (name, f'{cid} is at row {i} and column {i}', cards[cid], pitch)
    # A group's cards stand next to each other on the diagonal.
    for gid in set(block.values()):
        at = [i for i, cid in enumerate(order) if block.get(cid) == gid]
        assert at == list(range(at[0], at[0] + len(at))), (name, f'group {gid} is contiguous', at)
    routes = view['routes']
    wires = {w['id']: w for w in doc['wires']}
    between = [w for w in doc['wires'] if w['a'] in order and w['b'] in order and w['a'] != w['b']]
    auto = {a['wire'] for a in receipt['autoRouted']}
    assert {w['id'] for w in between} == set(routes) | auto, (name, 'every wire between two placed cards is pinned or reported', sorted(routes), sorted(auto))
    assert receipt['wires']['pinned'] == len(routes) and receipt['wires']['auto'] == len(auto), (name, receipt['wires'])
    forward, feedback = [], []
    for wid, route in routes.items():
        w, pts = wires[wid], r['wires'][wid]
        rev = (w.get('config') or {}).get('direction') == 'reverse'
        s, t = (w['b'], w['a']) if rev else (w['a'], w['b'])
        s_port, t_port = (w['bSide'], w['aSide']) if rev else (w['aSide'], w['bSide'])
        if rev:
            pts = pts[::-1]
        S, T = cards[s], cards[t]
        fwd = order.index(s) < order.index(t)
        (forward if fwd else feedback).append(wid)
        assert route['mode'] == 'pinned' and len(route['points']) == 1, (name, wid, route)
        assert len(pts) == 3, (name, f'{wid} is drawn with exactly one corner', pts)
        start, turn, end = pts
        assert near(turn['x'], route['points'][0]['x']) and near(turn['y'], route['points'][0]['y']), (name, f'{wid} turns at its stored point', turn, route)
        # Along the sender's row, then into the receiver's column.
        assert near(start['y'], turn['y']) and near(turn['x'], end['x']), (name, f'{wid} runs along the row, then down or up the column', pts)
        assert S['t'] < turn['y'] < S['b'] and T['l'] < turn['x'] < T['r'], (name, f'{wid} turns in the sender row and the receiver column', turn, S, T)
        # Each end is on its port, on the edge the view draws that port on.
        ps, pt = r['ports'][f'{s}|{s_port}'], r['ports'][f'{t}|{t_port}']
        assert ps['side'] == ('right' if fwd else 'left') and pt['side'] == ('top' if fwd else 'bottom'), (name, wid, ps, pt)
        assert near(start['x'], ps['at']['x']) and near(start['y'], ps['at']['y']) and near(end['x'], pt['at']['x']) and near(end['y'], pt['at']['y']), (name, f'{wid} ends on its ports', pts, ps, pt)
        assert near(start['x'], S['r'] if fwd else S['l']) and near(end['y'], T['t'] if fwd else T['b']), (name, f'{wid} leaves and arrives on the card edges', pts, S, T)
        # The diagonal passes through (x0 + k, y0 + k): above it y is smaller, below it larger.
        diagonal_y = y0 + (turn['x'] - x0)
        assert (turn['y'] < diagonal_y) if fwd else (turn['y'] > diagonal_y), (name, f'{wid} turns {"above" if fwd else "below"} the diagonal', turn, diagonal_y)
    assert receipt['wires']['forward'] == len(forward) and receipt['wires']['feedback'] == len(feedback), (name, receipt['wires'], forward, feedback)
    assert r['counts'] == {'port-wrong-side': 0, 'port-undrawn': 0}, (name, r['counts'])
    return forward, feedback


with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)
    A = 'SovSchematicAPI.layout'

    # ---- Three cards, one feedback wire ----------------------------------------------------------
    before = open_doc(page, json.dumps(THREE), 'three.sov')
    doc0 = saved(page)
    refused = page.evaluate(f"()=>{A}.apply({{engine:'n2'}})")
    assert refused.get('ok') is False and refused.get('code') == 'DEFAULT_LAYOUT', refused
    assert records(saved(page)) == records(doc0) and settle(page) == before, 'a refused n2 changes nothing'

    receipt = page.evaluate(f"()=>{A}.apply({{engine:'n2',into:'N2'}})")
    assert receipt['ok'] and receipt['engine'] == 'n2' and receipt['view'] == 'n2', receipt
    assert page.evaluate(f'()=>{A}.active()') == 'n2'
    drawn = settle(page)
    doc1 = saved(page)
    view = doc1['layout']['views']['n2']
    forward, feedback = check_layout('three', doc0, receipt, drawn, view)
    assert sorted(forward) == ['ab', 'bc'] and feedback == ['ca'] and not receipt['autoRouted'], (forward, feedback, receipt)
    assert view['ports'] == {'a': {'in': {'side': 'bottom', 't': .5}, 'out': {'side': 'right', 't': .5}},
                             'b': {'in': {'side': 'top', 't': .5}, 'out': {'side': 'right', 't': .5}},
                             'c': {'in': {'side': 'top', 't': .5}, 'out': {'side': 'left', 't': .5}}}, view['ports']
    print('three: order', receipt['order'], 'pitch', receipt['pitch'], 'wires', receipt['wires'])
    for wid in ('ab', 'bc', 'ca'):
        print('  ', wid, [(q['x'], q['y']) for q in drawn['wires'][wid]])

    # No record changed: in the saved document, and in the shared core on its own.
    assert records(doc1) == records(doc0), 'components and wires are the ones the document had'
    assert doc1['layout']['default'] == 'main' and 'nodes' not in doc1['layout']['views']['main'] and 'ports' not in doc1['layout']['views']['main']
    core = page.evaluate(CORE, [json.dumps(THREE)])
    assert core == {'ok': True, 'records': True, 'defaultView': True, 'defaultId': True}, core

    # A port the view places slides in the view; the record keeps its side.
    slid = page.evaluate("()=>{const n=nodes.find(x=>x.id==='b');return slidePortTo(n,'in',n.x-200,n.y)}")
    assert slid and slid['side'] == 'left', slid
    doc_slid = saved(page)
    assert doc_slid['layout']['views']['n2']['ports']['b']['in']['side'] == 'left' and records(doc_slid) == records(doc0), 'the slide moved the view placement only'
    page.evaluate("()=>{const n=nodes.find(x=>x.id==='b');slidePortTo(n,'in',n.x,n.y-200)}")
    assert saved(page)['layout']['views']['n2']['ports'] == view['ports'] and settle(page)['wires'] == drawn['wires'], 'slid back'

    # The default layout draws every port where the record puts it, and every wire as before.
    assert page.evaluate(f"()=>{A}.switch('main')")['ok']
    back = settle(page)
    assert back == before, ('the default layout is drawn as it was', back, before)
    assert {k: v['side'] for k, v in back['ports'].items()} == {'a|out': 'right', 'b|in': 'left', 'b|out': 'right', 'c|in': 'left', 'c|out': 'right', 'a|in': 'left'}, back['ports']

    # The saved document, opened again, draws the n2 layout the same.
    open_doc(page, json.dumps(doc1), 'three-saved.sov')
    assert sorted(v['id'] for v in page.evaluate(f'()=>{A}.list()')['views']) == ['main', 'n2']
    assert page.evaluate(f"()=>{A}.switch('n2')")['ok']
    again = settle(page)
    assert again['wires'] == drawn['wires'] and again['ports'] == drawn['ports'] and again['cards'] == drawn['cards'], 'a saved n2 layout loads as it was drawn'
    assert records(saved(page)) == records(doc0)

    # Validation: ensure() keeps only placements of a boundary port of a card that exists.
    cleaned = page.evaluate(r"""([t])=>{
      const d=SovSchematicData.documentFromFilePayload(JSON.parse(t));
      d.layout.views.n2.ports={ghost:{in:{side:'top',t:.5}},a:{in:{side:'diagonal',t:.5},nope:{side:'top',t:.5},out:{side:'left',t:7}},b:'x',c:{in:{side:'bottom'}}};
      d.layout.views.empty={name:'Empty',ports:{ghost:{in:{side:'top',t:.5}}}};
      SovSchematicLayout.ensure(d);return {n2:d.layout.views.n2.ports,empty:'ports' in d.layout.views.empty}}""", [json.dumps(doc1)])
    assert cleaned == {'n2': {'a': {'out': {'side': 'left', 't': 1}}, 'c': {'in': {'side': 'bottom', 't': .5}}}, 'empty': False}, cleaned

    # ---- A port used both ways has one side: forward wires keep it, feedback wires are routed ----
    open_doc(page, json.dumps(BOTH), 'both.sov')
    b0 = saved(page)
    b_receipt = page.evaluate(f"()=>{A}.apply({{engine:'n2',into:'N2'}})")
    b_drawn = settle(page)
    b1 = saved(page)
    b_forward, b_feedback = check_layout('both ways', b0, b_receipt, b_drawn, b1['layout']['views']['n2'])
    assert sorted(b_forward) == ['ab', 'bc'] and not b_feedback, (b_forward, b_feedback)
    assert b_receipt['autoRouted'] == [{'wire': 'ba', 'reason': 'PORT_SHARED', 'card': 'b', 'port': 'out', 'side': 'right'},
                                       {'wire': 'cb', 'reason': 'PORT_SHARED', 'card': 'b', 'port': 'in', 'side': 'top'}], b_receipt['autoRouted']
    assert b1['layout']['views']['n2']['ports']['b'] == {'in': {'side': 'top', 't': .5}, 'out': {'side': 'right', 't': .5}}
    assert records(b1) == records(b0)
    print('both ways: wires', b_receipt['wires'], 'auto', [a['wire'] for a in b_receipt['autoRouted']])

    # ---- Groups: examples/work-engine/groups.sov -------------------------------------------------
    text = GROUPS.read_text(encoding='utf-8')
    g_before = open_doc(page, text, GROUPS.name)
    g0 = saved(page)
    g_receipt = page.evaluate(f"()=>{A}.apply({{engine:'n2',into:'N2'}})")
    assert g_receipt['ok'] and g_receipt['view'] == 'n2', g_receipt
    g_drawn = settle(page)
    g1 = saved(page)
    g_forward, g_feedback = check_layout('groups', g0, g_receipt, g_drawn, g1['layout']['views']['n2'])
    assert g_receipt['order'] == ['case', 'recording', 'anchor', 'web-booth', 'delivery-broker'], g_receipt['order']
    assert g_forward == ['case-to-anchor'] and sorted(g_feedback) == ['booth-to-case', 'broker-to-recording'] and not g_receipt['autoRouted'], (g_forward, g_feedback, g_receipt)
    assert records(g1) == records(g0), 'groups: components and wires are the ones the document had'
    g_core = page.evaluate(CORE, [text])
    assert g_core == {'ok': True, 'records': True, 'defaultView': True, 'defaultId': True}, g_core
    print('groups: order', g_receipt['order'], 'pitch', g_receipt['pitch'], 'wires', g_receipt['wires'])
    for wid in g_forward + g_feedback:
        print('  ', wid, [(q['x'], q['y']) for q in g_drawn['wires'][wid]])
    assert page.evaluate(f"()=>{A}.switch('main')")['ok']
    assert settle(page) == g_before, 'groups: the default layout is drawn as it was'
    browser.close()

assert not errors, ('the page logs no errors', errors)
print('PASS n2 layout QA')
