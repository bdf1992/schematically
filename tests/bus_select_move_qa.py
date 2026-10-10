"""Bus select and move QA: a bus is selected by its label or its rim, read in the Inspector, and moved.

A bus is a record of the active layout (LAYOUT-MODEL.md "As built: buses", Selecting and moving a
bus). The wires on a bus lie over its band, so a press on the band reaches the wire under the
pointer. The bus itself is taken by its label, or by a rim 12 screen px wide outside its band
(rect.bus-hit, src/41-buses.js renderBuses). The selection value is bus: followed by the bus id.

The document (headless Chromium, 1400 x 900, snap off) is examples/work-engine/groups.sov, fitted.
The bus under test is harness-records-surfaces-delivers, a straight vertical bus labelled delivers
that carries one wire, broker-to-recording. Its rim point is 5 screen px left of the left edge of
its band rect at mid height.

Asserted, and printed:

(a) a click on the centre of the bus label selects the bus: selected is bus:<id>, its g.bus-band
    carries class selected, #busDetail is shown and the other Inspector blocks are hidden, #bLabel
    reads delivers, #bLanes reads 1, #bWires holds one row naming both cards of the wire, and
    #selectionBar is hidden;
(b) a click on the rim point selects the same bus;
(c) a click on the line of broker-to-recording where it rides the bus selects that wire;
(d) a click on blank canvas clears the selection;
(e) a press on the rim point, 6 pointer moves to 60 px left, release: every point of the bus moved
    on x by 60 / --zoom within 1 and not on y; pitch, label, between and lanes are as before; the
    wire's path changed and it has no data-bus-fallback; the bus is still selected; one undo puts
    the points back;
(f) a press on the rim point and a move of 60 px straight down, release: the points are unchanged;
(g) with the bus selected, a Delete keydown leaves the bus and the wire count as they were;
(h) the exported picture (SovSchematicAPI.render.svg) holds no bus-hit;
(i) on a planted document (act cards a 104,200 and b 904,640; bus p 400,100 to 400,500; bus q
    400,500 to 800,500; wire w a-b on p then q) a drag of p 60 px left, which leaves p and q not
    meeting, is refused: the points of p are unchanged and the status starts Bus move refused;
(j) the page logs no error.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

INDEX = ROOT / 'index.html'
GROUPS = ROOT / 'examples' / 'work-engine' / 'groups.sov'
BUS = 'harness-records-surfaces-delivers'
WIRE = 'broker-to-recording'
DRAG_PX, MOVES = 60, 6
P_POINTS = [{'x': 400, 'y': 100}, {'x': 400, 'y': 500}]
Q_POINTS = [{'x': 400, 'y': 500}, {'x': 800, 'y': 500}]

# The rim point of a bus, and what lies under it: the .bus-hit of that bus when the rim is drawn.
RIM = r"""(id)=>{
  const rect=document.querySelector(`.bus-band[data-bus-id="${id}"] rect`);if(!rect)return null;
  const r=rect.getBoundingClientRect(),x=r.left-5,y=r.top+r.height/2,el=document.elementFromPoint(x,y);
  const hit=el?.closest?.('.bus-hit')||null;
  return {x,y,under:el?`${el.tagName}.${el.getAttribute('class')||''}`:null,hit:!!hit,bus:hit?.closest('.bus-hit-band')?.dataset.busId??null};
}"""
LABEL = r"""(id)=>{
  const t=document.querySelector(`text.bus-label[data-bus-id="${id}"]`);if(!t)return null;
  const r=t.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};
}"""
# Where the wire rides the bus, on screen: the point of its bus route nearest the centreline of the
# bus (on groups.sov the wire crosses the bus in one straight line, so that is where it crosses),
# with how far from the centreline it lies and whether it is inside the band.
ON_BUS = r"""([wireId,busId])=>{
  const pts=busRoutesForRender().routes.get(wireId),line=busLine(activeBuses()[busId]);if(!pts||!line)return null;
  let best=null;
  for(let i=1;i<pts.length;i++)for(let k=0;k<=400;k++){
    const a=pts[i-1],b=pts[i],q={x:a.x+(b.x-a.x)*k/400,y:a.y+(b.y-a.y)*k/400},d=busProject(line,q).d;
    if(!best||d<best.d)best={d,x:q.x,y:q.y};
  }
  if(!best)return null;
  const m=workspace.getScreenCTM(),p=workspace.createSVGPoint();p.x=best.x;p.y=best.y;const s=p.matrixTransform(m);
  const r=document.querySelector(`.bus-band[data-bus-id="${busId}"] rect`).getBoundingClientRect();
  return {x:s.x,y:s.y,off:best.d,inBand:s.x>=r.left&&s.x<=r.right&&s.y>=r.top&&s.y<=r.bottom,index:wires.findIndex(w=>w.id===wireId)};
}"""
# A point of the canvas with nothing over it.
BLANK = r"""()=>{
  const r=workspace.getBoundingClientRect();
  for(let y=r.bottom-12;y>r.top+8;y-=14)for(let x=r.left+12;x<r.right-8;x+=14)if(document.elementFromPoint(x,y)===workspace)return {x,y};
  return null;
}"""
STATE = r"""(id)=>{
  const shown=k=>!document.getElementById(k).hidden,text=k=>document.getElementById(k)?.textContent??null;
  return {
    selected,
    band:[...document.querySelectorAll('.bus-band.selected')].map(g=>g.dataset.busId),
    shown:Object.fromEntries(['busDetail','componentDetail','connectionDetail','portDetail','emptyInspector'].map(k=>[k,document.getElementById(k)?shown(k):null])),
    label:text('bLabel'),between:text('bBetween'),lanes:text('bLanes'),
    rows:[...(document.getElementById('bWires')?.children||[])].map(r=>r.textContent),
    bar:!document.getElementById('selectionBar').hidden,
    status:document.getElementById('status').textContent,
  };
}"""
BUS_RECORD = "(id)=>{const b=(SovSchematicAPI.layout.buses().buses||[]).find(b=>b.id===id);return b||null}"
WIRE_DRAWN = r"""(id)=>{
  const g=workspace.querySelector(`.wire-group[data-wire-id="${id}"]`);
  return {d:g?.querySelector('path.wire')?.getAttribute('d')??null,fallback:g?.dataset.busFallback??null,count:wires.length};
}"""
CARDS_OF = "(id)=>{const w=wires.find(w=>w.id===id),name=c=>componentConfig(nodes.find(n=>n.id===c)).label;return [name(w.a),name(w.b)]}"
PLANT = r"""([p,q])=>{
  const made=[SovSchematicAPI.layout.bus({id:'p',points:p,pitch:6,label:'down'}),SovSchematicAPI.layout.bus({id:'q',points:q,pitch:6})];
  const routed=SovSchematicAPI.layout.route('w',{mode:'bus',buses:['p','q']});
  render();
  return {refused:[...made,routed].filter(r=>!r||r.ok===false),met:!!SovSchematicLayout.busMeet(p,q),fallback:[...busRoutesForRender().fallback]};
}"""
MEET = "()=>{const b=activeBuses();return !!SovSchematicLayout.busMeet(b.p.points,b.q.points)}"
MEET_AT = "([p,q])=>!!SovSchematicLayout.busMeet(p,q)"


def drag(page, x: float, y: float, dx: float, dy: float) -> None:
    page.mouse.move(x, y)
    page.mouse.down()
    for k in range(1, MOVES + 1):
        page.mouse.move(x + dx * k / MOVES, y + dy * k / MOVES)
    page.mouse.up()
    page.wait_for_timeout(200)


def click(page, at: dict) -> None:
    page.mouse.click(at['x'], at['y'])
    page.wait_for_timeout(120)


def main() -> None:
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
        page.set_content(INDEX.read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(250)
        page.evaluate('()=>{canvasSnapEnabled=false}')
        page.evaluate('([t,n])=>{SovSchematicAPI.file.open(t,n);fitDiagram()}', [GROUPS.read_text(encoding='utf-8'), GROUPS.name])
        page.wait_for_timeout(350)
        page.evaluate('()=>{canvasSnapEnabled=false}')

        # Step 4: the rim of the bus is its own target.
        rim = page.evaluate(RIM, BUS)
        print(f'rim point of {BUS}: {rim}')
        assert rim, ('the band of the bus is drawn', BUS)
        assert rim['hit'] and rim['bus'] == BUS, ('the rim point, 5 px left of the band, lies on a .bus-hit of the bus', rim)

        # (a) the label.
        label_at = page.evaluate(LABEL, BUS)
        assert label_at, ('the bus draws its label', BUS)
        click(page, label_at)
        by_label = page.evaluate(STATE, BUS)
        cards = page.evaluate(CARDS_OF, WIRE)
        print(f'(a) label click: selected {by_label["selected"]}; label {by_label["label"]!r}, between {by_label["between"]!r}, '
              f'lanes {by_label["lanes"]!r}, rows {by_label["rows"]}')
        assert by_label['selected'] == f'bus:{BUS}', ('(a) a click on the label selects the bus', by_label)
        assert by_label['band'] == [BUS], ('(a) the band of the selected bus, and no other, carries selected', by_label['band'])
        assert by_label['shown'] == {'busDetail': True, 'componentDetail': False, 'connectionDetail': False, 'portDetail': False,
                                     'emptyInspector': False}, ('(a) the Inspector shows the bus block alone', by_label['shown'])
        assert by_label['label'] == 'delivers', ('(a) the Inspector names the bus', by_label['label'])
        assert by_label['lanes'] == '1', ('(a) the Inspector gives the lane count', by_label['lanes'])
        assert len(by_label['rows']) == 1 and all(c and c in by_label['rows'][0] for c in cards), \
            ('(a) one row names both cards of the wire', by_label['rows'], cards)
        assert by_label['bar'] is False, ('(a) a selected bus shows no selection bar', by_label['bar'])

        # (d) blank canvas clears it; then (b) the rim selects it again.
        blank = page.evaluate(BLANK)
        assert blank, 'the canvas has a point with nothing over it'
        click(page, blank)
        cleared = page.evaluate(STATE, BUS)
        print(f'(d) blank click: selected {cleared["selected"]}, selected bands {cleared["band"]}, bus block shown {cleared["shown"]["busDetail"]}')
        assert cleared['selected'] is None and cleared['band'] == [] and cleared['shown']['busDetail'] is False, \
            ('(d) a click on blank canvas clears the bus selection', cleared)
        click(page, rim)
        by_rim = page.evaluate(STATE, BUS)
        print(f'(b) rim click: selected {by_rim["selected"]}')
        assert by_rim['selected'] == f'bus:{BUS}' and by_rim['band'] == [BUS] and by_rim['shown']['busDetail'] is True, \
            ('(b) a click on the rim selects the bus', by_rim)

        # (c) the wire that rides the bus is taken by a press on its own line.
        on_bus = page.evaluate(ON_BUS, [WIRE, BUS])
        assert on_bus and on_bus['inBand'], ('the wire rides the bus: its route passes inside the band', WIRE, on_bus)
        click(page, on_bus)
        by_wire = page.evaluate(STATE, BUS)
        print(f'(c) click on {WIRE} where it rides the bus: selected {by_wire["selected"]}')
        assert by_wire['selected'] == f'wire:{on_bus["index"]}', ('(c) a click on a wire that rides the bus selects the wire', by_wire['selected'])
        assert by_wire['band'] == [] and by_wire['shown']['busDetail'] is False, ('(c) the bus is no longer shown as selected', by_wire)

        # (e) a drag across the bus moves it.
        click(page, blank)
        zoom = page.evaluate("()=>Number(workspace.style.getPropertyValue('--zoom'))")
        before, drawn_before = page.evaluate(BUS_RECORD, BUS), page.evaluate(WIRE_DRAWN, WIRE)
        history_before = page.evaluate('()=>SovSchematicAPI.history.list().length')
        rim = page.evaluate(RIM, BUS)
        drag(page, rim['x'], rim['y'], -DRAG_PX, 0)
        after, drawn_after, moved_state = page.evaluate(BUS_RECORD, BUS), page.evaluate(WIRE_DRAWN, WIRE), page.evaluate(STATE, BUS)
        history_after = page.evaluate('()=>SovSchematicAPI.history.list()')
        want = DRAG_PX / zoom
        print(f'(e) dragged {DRAG_PX} px left at zoom {zoom:.4f}: x {[p["x"] for p in before["points"]]} -> {[round(p["x"], 2) for p in after["points"]]} '
              f'(wanted a move of {want:.2f}); history +{len(history_after) - history_before} {history_after[-1]["label"] if history_after else None!r}')
        assert len(after['points']) == len(before['points']), ('(e) the bus keeps its points', after['points'])
        for was, now in zip(before['points'], after['points']):
            assert abs((was['x'] - now['x']) - want) <= 1, ('(e) every point moved on x by 60 / zoom', was, now, want)
            assert now['y'] == was['y'], ('(e) no point moved on y', was, now)
        for key in ('pitch', 'label', 'between', 'lanes'):
            assert after.get(key) == before.get(key), ('(e) the move keeps', key, before.get(key), after.get(key))
        assert drawn_after['d'] and drawn_after['d'] != drawn_before['d'], ('(e) the wire on the bus follows it', drawn_before['d'], drawn_after['d'])
        assert drawn_after['fallback'] is None, ('(e) the wire still rides the bus', drawn_after)
        assert moved_state['selected'] == f'bus:{BUS}' and moved_state['band'] == [BUS], ('(e) the moved bus is still selected', moved_state)
        assert len(history_after) == history_before + 1 and history_after[-1]['label'] == 'Move bus', \
            ('(e) one gesture makes one history transition, Move bus', history_before, history_after[-2:])
        assert page.evaluate('()=>window.SovSchematicAPI.history.undo()'), '(e) the move can be undone'
        page.wait_for_timeout(150)
        undone = page.evaluate(BUS_RECORD, BUS)
        print(f'    undo: x {[p["x"] for p in undone["points"]]}')
        assert undone['points'] == before['points'], ('(e) one undo puts the points back', undone['points'], before['points'])

        # (f) a drag along a straight bus moves nothing.
        rim = page.evaluate(RIM, BUS)
        assert rim['hit'] and rim['bus'] == BUS, ('after the undo the rim is drawn again', rim)
        history_before = page.evaluate('()=>SovSchematicAPI.history.list().length')
        drag(page, rim['x'], rim['y'], 0, DRAG_PX)
        along = page.evaluate(BUS_RECORD, BUS)
        history_along = page.evaluate('()=>SovSchematicAPI.history.list().length')
        print(f'(f) dragged {DRAG_PX} px down: points unchanged {along["points"] == before["points"]}; history +{history_along - history_before}')
        assert along['points'] == before['points'], ('(f) a drag along a straight bus leaves its points', along['points'])
        assert history_along == history_before, ('(f) a drag that moves nothing writes nothing', history_before, history_along)

        # (g) Delete does not remove a bus.
        click(page, rim)
        assert page.evaluate('()=>selected') == f'bus:{BUS}', 'the bus is selected before Delete'
        page.evaluate("()=>{document.dispatchEvent(new KeyboardEvent('keydown',{key:'Delete',code:'Delete',bubbles:true,cancelable:true}))}")
        page.wait_for_timeout(120)
        kept, kept_wire, kept_state = page.evaluate(BUS_RECORD, BUS), page.evaluate(WIRE_DRAWN, WIRE), page.evaluate(STATE, BUS)
        print(f'(g) Delete on the selected bus: bus kept {kept is not None}, wires {drawn_before["count"]} -> {kept_wire["count"]}, status {kept_state["status"]!r}')
        assert kept and kept['points'] == before['points'], ('(g) Delete leaves the bus', kept)
        assert kept_wire['count'] == drawn_before['count'], ('(g) Delete leaves every wire', drawn_before['count'], kept_wire['count'])

        # (h) the exported picture carries no hit rim.
        svg = page.evaluate('()=>SovSchematicAPI.render.svg({})')
        svg_text = svg if isinstance(svg, str) else json.dumps(svg)
        print(f'(h) exported picture: {len(svg_text)} characters, bus-band in it {"bus-band" in svg_text}, bus-hit in it {"bus-hit" in svg_text}')
        assert 'bus-band' in svg_text, '(h) the exported picture draws the buses'
        assert 'bus-hit' not in svg_text, '(h) the exported picture holds no bus-hit'

        # (i) a move that would part two buses a wire rides in a row is refused.
        doc = page.evaluate('()=>({schema:SovSchematicData.DOCUMENT_SCHEMA})')
        doc.update({'id': 'bus-move-refusal',
                    'components': [{'id': 'a', 'symbolId': 'act', 'x': 104, 'y': 200}, {'id': 'b', 'symbolId': 'act', 'x': 904, 'y': 640}],
                    'wires': [{'id': 'w', 'a': 'a', 'aSide': 'out', 'b': 'b', 'bSide': 'in'}]})
        page.evaluate('([t,n])=>{SovSchematicAPI.file.open(t,n)}', [json.dumps(doc), 'bus-move-refusal.sov'])
        planted = page.evaluate(PLANT, [P_POINTS, Q_POINTS])
        assert not planted['refused'] and planted['met'], ('the two buses and the route over both are planted', planted)
        page.evaluate('()=>{fitDiagram();canvasSnapEnabled=false}')
        page.wait_for_timeout(350)
        rim_p = page.evaluate(RIM, 'p')
        assert rim_p and rim_p['hit'] and rim_p['bus'] == 'p', ('the rim of the planted bus p is its own target', rim_p)
        zoom_p = page.evaluate("()=>Number(workspace.style.getPropertyValue('--zoom'))")
        parted = [{'x': q['x'] - DRAG_PX / zoom_p, 'y': q['y']} for q in P_POINTS]
        assert not page.evaluate(MEET_AT, [parted, Q_POINTS]), ('moved 60 px left, p would no longer meet q', parted)
        history_before = page.evaluate('()=>SovSchematicAPI.history.list().length')
        drag(page, rim_p['x'], rim_p['y'], -DRAG_PX, 0)
        refused, refused_state = page.evaluate(BUS_RECORD, 'p'), page.evaluate(STATE, 'p')
        history_refused = page.evaluate('()=>SovSchematicAPI.history.list().length')
        still_met = page.evaluate(MEET)
        print(f'(i) planted p dragged {DRAG_PX} px left of q: points {refused["points"]}, status {refused_state["status"]!r}, still meeting {still_met}')
        assert refused['points'] == P_POINTS, ('(i) a refused move leaves the points of the bus', refused['points'])
        assert refused_state['status'].startswith('Bus move refused'), ('(i) the status says the move was refused', refused_state['status'])
        assert still_met and history_refused == history_before, ('(i) a refused move writes nothing', still_met, history_before, history_refused)
        browser.close()

    # (j)
    assert not errors, ('(j) the page logs no errors', errors)
    print('PASS bus select and move QA')


if __name__ == '__main__':
    main()
