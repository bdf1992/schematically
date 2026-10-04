"""Port side QA: a wire meets a port from the side the port faces, and the port it ends on is drawn.

Every route that ends on a port of a 2D card leaves and arrives along that port's outward normal:
the segment touching the port is collinear with the normal, and the point before the port lies
outside the card on the port's facing side, at least 4 from the edge. That holds for auto routes,
for pinned and guided routes (the router adds the lead when the declared points do not give it) and
for bus taps. Every bound end on a 2D card has a visible port mark at the route's end.

layout.metrics reports both, with no weight in the score: port-wrong-side and port-undrawn.

- tests/fixtures/task-lifecycle.sov (frame 4 of the Miro parity study) and
  tests/fixtures/work-engine-sample.sov (frame 5) have port-wrong-side 0 and port-undrawn 0.
- A target act card left of and below its source is entered at its in port from the left.
- A gate wired into its top control port from a card below it is entered from above, and that port
  is drawn.
- A pinned route whose last point sits right of a left-facing port still arrives from the left: with
  the last point beyond the card on the port's own line, and with it over the card. A guided route
  through a point right of the port does too.
- A wire on a bus that lies behind both of its ports taps on and off round its cards: it leaves the
  out port to the right and enters the in port from the left.
- A gate boxed in by eight cards and fed from below has no clear route; its blocked fallback route
  still drops into the control port from above.
- A card with no default ports and one declared port, and a card with no backdrop, have their wired
  ports drawn.
- The page logs no errors.
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

FIXTURES = [ROOT / 'tests' / 'fixtures' / 'task-lifecycle.sov', ROOT / 'tests' / 'fixtures' / 'work-engine-sample.sov']
SCHEMA = 'soveraeign.schematic/document@0.1'
KINDS = ('port-wrong-side', 'port-undrawn')

# The metrics, each wire's drawn corners in world space (hops stripped, collinear corners merged),
# each card's body, and the port marks drawn within 3 of each bound end: [class, opacity].
READ = r"""()=>{
  const m=SovSchematicAPI.layout.metrics({static:true});
  const out={counts:m.counts,findings:m.findings.filter(f=>f.kind==='port-wrong-side'||f.kind==='port-undrawn'),weighted:Object.keys(m.rubric).filter(k=>k.startsWith('port-')),wires:{},cards:{},marks:{}};
  for(const g of workspace.querySelectorAll('.wire-group')){
    const p=g.querySelector('path.wire'),w=wires.find(x=>x.id===g.dataset.wireId);if(!p||!w)continue;
    const c=layoutRouteCorners(p);out.wires[w.id]=c;
    for(const end of ['a','b']){
      const ep=carrierEndpoint(w,end);if(ep?.kind!=='bound'||componentForm(ep.node).dimension!==2)continue;
      const P=end==='a'?c[0]:c.at(-1),el=nodesG.querySelector(`.node[data-id="${CSS.escape(ep.node.id)}"]`),near=[];
      for(const k of el.querySelectorAll(':scope > .port.attachment-point,:scope > .terminal-mark')){
        const B=layoutWorldBox(k);if(!B)continue;
        if(Math.hypot(Math.max(B.l-P.x,P.x-B.r,0),Math.max(B.t-P.y,P.y-B.b,0))<=3)near.push([k.getAttribute('class'),layoutEffectiveOpacity(k)]);
      }
      out.marks[`${w.id}:${end}`]=near;
    }
  }
  for(const n of nodes)if(componentForm(n).dimension===2&&!isGroupComponent(n)){const R=componentBounds(n);out.cards[n.id]={l:R.l,r:R.r,t:R.t,b:R.b}}
  return out;
}"""


def settle(page):
    page.evaluate('()=>{ if (typeof fitDiagram === "function") fitDiagram(); }')
    page.wait_for_timeout(300)
    return page.evaluate(READ)


def plant(page, components, wires, layout=None):
    doc = {'schema': SCHEMA, 'id': 'planted', 'components': components, 'wires': wires}
    if layout:
        doc['layout'] = layout
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [json.dumps(doc), 'planted.sov'])
    return settle(page)


def open_file(page, path: Path):
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [path.read_text(encoding='utf-8'), path.name])
    return settle(page)


def route(page, wire, spec):
    r = page.evaluate('([w,s])=>SovSchematicAPI.layout.route(w,s)', [wire, spec])
    assert r['ok'], r
    return settle(page)


def counts(r):
    return {k: r['counts'].get(k, 0) for k in KINDS}


def orthogonal(name, r):
    for wid, pts in r['wires'].items():
        for p, q in zip(pts, pts[1:]):
            assert abs(p['x'] - q['x']) < .5 or abs(p['y'] - q['y']) < .5, (name, wid, 'a diagonal step', p, q)


def arrives(name, r, wire, end, card, side):
    """The segment touching the port runs along the side's outward normal, from 4 or more outside."""
    pts, R = r['wires'][wire], r['cards'][card]
    P, Q = (pts[0], pts[1]) if end == 'a' else (pts[-1], pts[-2])
    if side == 'left':
        ok = abs(Q['y'] - P['y']) < .5 and Q['x'] <= R['l'] - 4 + .01
    elif side == 'right':
        ok = abs(Q['y'] - P['y']) < .5 and Q['x'] >= R['r'] + 4 - .01
    elif side == 'top':
        ok = abs(Q['x'] - P['x']) < .5 and Q['y'] <= R['t'] - 4 + .01
    else:
        ok = abs(Q['x'] - P['x']) < .5 and Q['y'] >= R['b'] + 4 - .01
    assert ok, (f'{name}: {wire} meets {card} from the {side}', {'port': P, 'before': Q, 'card': R, 'route': pts})


def drawn(name, r, wire, end):
    marks = r['marks'].get(f'{wire}:{end}', [])
    assert any(o >= .5 for _, o in marks), (f'{name}: the port {wire} ends on ({end}) is drawn', marks)


def clean(name, r):
    c = counts(r)
    assert c['port-wrong-side'] == 0, (f'{name}: port-wrong-side 0', c, r['findings'])
    assert c['port-undrawn'] == 0, (f'{name}: port-undrawn 0', c, r['findings'])


def dump(name, r):
    if not os.environ.get('PORT_QA_DEBUG'):
        return
    print('---', name)
    for f in r['findings']:
        print('  ', f['kind'], f['ids'], f['detail'])
    for wid, pts in r['wires'].items():
        print('   wire', wid, [(p['x'], p['y']) for p in pts])
    for cid, R in r['cards'].items():
        print('   card', cid, R)
    print('   marks', r['marks'])


PAIR = [{'id': 'a', 'symbolId': 'act', 'x': 100, 'y': 300}, {'id': 'b', 'symbolId': 'act', 'x': 500, 'y': 300}]
AB = [{'id': 'ab', 'a': 'a', 'aSide': 'out', 'b': 'b', 'bSide': 'in'}]

results = {}
with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)

    fixtures = {f.name: open_file(page, f) for f in FIXTURES}

    # A target left of and below its source: out on the right, in on the left of a card behind it.
    results['back'] = plant(page,
                            [{'id': 's', 'symbolId': 'act', 'x': 600, 'y': 100}, {'id': 't', 'symbolId': 'act', 'x': 200, 'y': 400}],
                            [{'id': 'st', 'a': 's', 'aSide': 'out', 'b': 't', 'bSide': 'in'}])
    # A gate's control port is on its top; the card that feeds it sits straight below the gate.
    results['gate'] = plant(page,
                            [{'id': 'g', 'symbolId': 'gate', 'x': 400, 'y': 100}, {'id': 'c', 'symbolId': 'act', 'x': 400, 'y': 420}],
                            [{'id': 'cg', 'a': 'c', 'aSide': 'out', 'b': 'g', 'bSide': 'control'}])
    # Pinned: the last declared point is right of b's left-facing in port, on the port's own line
    # beyond the card (the route would run back through the card to reach the port).
    plant(page, PAIR, AB)
    results['pinned-beyond'] = route(page, 'ab', {'mode': 'pinned', 'points': [{'x': 300, 'y': 300}, {'x': 300, 'y': 150}, {'x': 760, 'y': 150}, {'x': 760, 'y': 300}]})
    # Pinned: the last declared point is over the card, right of the port.
    plant(page, PAIR, AB)
    results['pinned-over'] = route(page, 'ab', {'mode': 'pinned', 'points': [{'x': 300, 'y': 150}, {'x': 540, 'y': 150}]})
    # Pinned: the last declared point is inside the card, on the port's own line.
    plant(page, PAIR, AB)
    results['pinned-inside'] = route(page, 'ab', {'mode': 'pinned', 'points': [{'x': 300, 'y': 150}, {'x': 520, 'y': 150}, {'x': 520, 'y': 300}]})
    # Guided: one via point right of the port, on its line; and the first point left of a's out port.
    plant(page, PAIR, AB)
    results['guided'] = route(page, 'ab', {'mode': 'guided', 'via': [{'x': 20, 'y': 300}, {'x': 20, 'y': 150}, {'x': 760, 'y': 150}, {'x': 760, 'y': 300}]})
    # A bus behind both ports: left of the source's out port, right of the target's in port.
    results['bus'] = plant(page,
                           [{'id': 'a', 'symbolId': 'act', 'x': 1000, 'y': 100}, {'id': 'b', 'symbolId': 'act', 'x': 500, 'y': 400}],
                           AB,
                           {'default': 'main', 'views': {'main': {'name': 'Main', 'buses': {'spine': {'points': [{'x': 760, 'y': 0}, {'x': 760, 'y': 500}]}},
                                                                    'routes': {'ab': {'mode': 'bus', 'buses': ['spine']}}}}})
    results['bus-on'] = page.evaluate("()=>({bus:!!busSpecOf(wires.find(w=>w.id==='ab')),fallback:workspace.querySelector('.wire-group[data-wire-id=\"ab\"]').dataset.busFallback||null})")
    # A gate boxed in by eight cards 12 apart, fed from a card far below: no clear route exists, so
    # the route is the perimeter fallback. It still drops into the control port from above.
    ring = [(-124, -96), (0, -96), (124, -96), (-124, 0), (124, 0), (-124, 96), (0, 96), (124, 96)]
    results['boxed'] = plant(page,
                             [{'id': 'g', 'symbolId': 'gate', 'x': 400, 'y': 300}, {'id': 'c', 'symbolId': 'act', 'x': 400, 'y': 700},
                              *[{'id': f'r{i}', 'symbolId': 'act', 'x': 400 + dx, 'y': 300 + dy} for i, (dx, dy) in enumerate(ring)]],
                             [{'id': 'cg', 'a': 'c', 'aSide': 'out', 'b': 'g', 'bSide': 'control'}])
    results['boxed-blocked'] = page.evaluate("()=>workspace.querySelector('.wire-group[data-wire-id=\"cg\"]').dataset.routeBlocked||null")
    # Ports drawn whatever the card's attachment defaults or backdrop: a card with no default ports
    # and one declared port, a card with no backdrop, a declared port named by its id.
    results['drawn'] = plant(page,
                             [{'id': 'src', 'symbolId': 'act', 'x': 100, 'y': 300},
                              {'id': 'non', 'symbolId': 'hold', 'x': 500, 'y': 150, 'config': {'attachmentDefaults': 'none', 'attachmentPoints': [{'id': 'only', 'side': 'left', 't': .5, 'flow': 'in'}]}},
                              {'id': 'bare', 'symbolId': 'gate', 'x': 500, 'y': 300, 'config': {'presentation': {'backdrop': 'none'}}},
                              {'id': 'imp', 'symbolId': 'gate', 'x': 500, 'y': 480, 'config': {'attachmentPoints': [{'id': 'aux2', 'compatId': 'aux-2', 'side': 'bottom', 't': .75, 'flow': 'in'}]}}],
                             [{'id': 'w-non', 'a': 'src', 'aSide': 'out', 'b': 'non', 'bSide': 'only'},
                              {'id': 'w-bare', 'a': 'src', 'aSide': 'out', 'b': 'bare', 'bSide': 'in'},
                              {'id': 'w-imp', 'a': 'src', 'aSide': 'out', 'b': 'imp', 'bSide': 'aux2'}])
    browser.close()

for name, r in fixtures.items():
    print(name, counts(r))
for name, r in results.items():
    if 'counts' in r:
        print(name, counts(r))
        dump(name, r)
print('bus', results['bus-on'])

assert not errors, ('the page logs no errors', errors)
for name, r in fixtures.items():
    clean(name, r)
    assert not r['weighted'], ('the port findings carry no rubric weight', r['weighted'])
for name, r in results.items():
    if 'counts' in r:
        orthogonal(name, r)

arrives('back', results['back'], 'st', 'b', 't', 'left')
arrives('back', results['back'], 'st', 'a', 's', 'right')
clean('back', results['back'])

arrives('gate', results['gate'], 'cg', 'b', 'g', 'top')
drawn('gate', results['gate'], 'cg', 'b')
clean('gate', results['gate'])

for name in ('pinned-beyond', 'pinned-over', 'pinned-inside', 'guided'):
    arrives(name, results[name], 'ab', 'b', 'b', 'left')
    arrives(name, results[name], 'ab', 'a', 'a', 'right')
    clean(name, results[name])
# The declared points are still on the route: the lead is added, the pinned interior is kept.
for name, kept in (('pinned-beyond', (760, 150)), ('pinned-over', (300, 150)), ('guided', (760, 150))):
    assert any(abs(q['x'] - kept[0]) < .5 and abs(q['y'] - kept[1]) < .5 for q in results[name]['wires']['ab']), (f'{name}: the declared point {kept} stays on the route', results[name]['wires']['ab'])

assert results['bus-on'] == {'bus': True, 'fallback': None}, ('the wire rides its bus', results['bus-on'])
assert any(abs(p['x'] - q['x']) < .5 and abs(p['x'] - 760) <= 8 and abs(p['y'] - q['y']) >= 100 for p, q in zip(results['bus']['wires']['ab'], results['bus']['wires']['ab'][1:])), ('the wire runs along the bus', results['bus']['wires']['ab'])
arrives('bus', results['bus'], 'ab', 'a', 'a', 'right')
arrives('bus', results['bus'], 'ab', 'b', 'b', 'left')
clean('bus', results['bus'])

assert results['boxed-blocked'] == 'true', ('boxed: the route is the blocked fallback', results['boxed-blocked'])
arrives('boxed', results['boxed'], 'cg', 'b', 'g', 'top')
arrives('boxed', results['boxed'], 'cg', 'a', 'c', 'right')
drawn('boxed', results['boxed'], 'cg', 'b')
clean('boxed', results['boxed'])

for wire in ('w-non', 'w-bare', 'w-imp'):
    drawn('drawn', results['drawn'], wire, 'a')
    drawn('drawn', results['drawn'], wire, 'b')
clean('drawn', results['drawn'])
print('PASS port side QA')
