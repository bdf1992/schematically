"""Card shapes QA (SECTION-MODEL.md "Card shapes", DATA-FORMATS.md "Card shape").

A 2D card with a closed interior may declare config.presentation.shape: rect (the default), cylinder
or parallelogram. Ports, routing and every layout metric keep the bounding rectangle.

In headless Chromium on index.html:
  - an act card with shape cylinder and one with shape parallelogram, each wired in, out and on top,
    draw a body path (not a rect) inside their bounding box, with the corners the shape cuts away
    outside the fill;
  - every wired port lies on the drawn outline or has a .component-lead from the port that ends on it;
  - every route ends on the port, on the bounding side; route-through-node and port-wrong-side are 0;
  - the title, the glyph and a badge lie inside the inner rectangle (parallelogram: w - 2 s wide;
    cylinder: below the cap);
  - text-contrast is 0 in light and in dark;
  - shape 'disk' is refused with SHAPE_INVALID on create and update and the document is unchanged; so is
    a cylinder on a group or on a container; a file carrying it loads and reports SHAPE_INVALID;
  - a sectioned Form keeps the rectangle;
  - saving and opening keeps the shapes; the selection panel shows the shape; the picture carries the path;
  - on examples/work-engine/status.sov a shaped card keeps its status: the dashed outline, the fade on
    the body and never on the text, the status chip and a badge inside the inner rectangle;
  - the page logs no errors.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'examples/work-engine/status.sov'
W, H = 170, 96

DOC = {
    'id': 'card-shapes',
    'components': [
        {'id': 'src', 'symbolId': 'act', 'x': 120, 'y': 320, 'config': {'label': 'Source'}},
        {'id': 'cyl', 'symbolId': 'act', 'x': 430, 'y': 320, 'config': {
            'label': 'Store', 'badges': [{'label': 'Kept'}],
            'presentation': {'shape': 'cylinder', 'size': {'w': W, 'h': H}},
            'attachmentPoints': [{'id': 'tap', 'side': 'top', 't': 0.1, 'flow': 'in'}]}},
        {'id': 'par', 'symbolId': 'act', 'x': 780, 'y': 320, 'config': {
            'label': 'Input', 'badges': [{'label': 'Read'}],
            'presentation': {'shape': 'parallelogram', 'size': {'w': W, 'h': H}},
            'attachmentPoints': [{'id': 'tap', 'side': 'top', 't': 0.05, 'flow': 'in'}]}},
        {'id': 'dst', 'symbolId': 'act', 'x': 1090, 'y': 320, 'config': {'label': 'Sink'}},
        {'id': 'ctl', 'symbolId': 'act', 'x': 560, 'y': 90, 'config': {'label': 'Control'}},
        {'id': 'ctl2', 'symbolId': 'act', 'x': 240, 'y': 90, 'config': {'label': 'Clock'}},
    ],
    'wires': [
        {'id': 'w1', 'a': 'src', 'aSide': 'out', 'b': 'cyl', 'bSide': 'in'},
        {'id': 'w2', 'a': 'cyl', 'aSide': 'out', 'b': 'par', 'bSide': 'in'},
        {'id': 'w3', 'a': 'par', 'aSide': 'out', 'b': 'dst', 'bSide': 'in'},
        {'id': 'w4', 'a': 'ctl2', 'aSide': 'out', 'b': 'cyl', 'bSide': 'tap'},
        {'id': 'w5', 'a': 'ctl', 'aSide': 'out', 'b': 'par', 'bSide': 'tap'},
    ],
    'references': [],
}

# Everything is read in the card's own frame (its group is translated to the card's centre).
CARD = r'''(id)=>{
  const n=nodes.find(x=>x.id===id),g=document.querySelector(`#nodes > .node[data-id="${id}"]`);
  const body=g.querySelector(':scope > .body'),size=componentSize(n);
  const bb=el=>{const b=el.getBBox();return {l:b.x,r:b.x+b.width,t:b.y,b:b.y+b.height}};
  const at=(x,y)=>{const p=body.ownerSVGElement.createSVGPoint();p.x=x;p.y=y;return p};
  const inFill=(x,y)=>body.isPointInFill(at(x,y)),onStroke=(x,y)=>body.isPointInStroke(at(x,y));
  const hw=size.w/2,hh=size.h/2;
  const ports=[];
  for(const point of componentAttachmentPoints(n)){
    const compat=point.compatId;
    const ends=wires.filter(w=>(w.a===n.id&&w.aSide===compat)||(w.b===n.id&&w.bSide===compat));
    if(!ends.length)continue;
    const P=componentPortLocalPosition(n,point.id),side=physicalPortSide(n,point.id);
    const lead=g.querySelector(`:scope > .component-lead.shape-lead[data-point="${point.id}"]`);
    let leadInfo=null;
    if(lead){const L=lead.getTotalLength(),a=lead.getPointAtLength(0),b=lead.getPointAtLength(L);
      leadInfo={length:L,from:{x:a.x,y:a.y},to:{x:b.x,y:b.y},endsOnOutline:onStroke(b.x,b.y),stroke:getComputedStyle(lead).stroke,width:getComputedStyle(lead).strokeWidth}}
    // Where each wire on this port ends, in the card's frame.
    const routeEnds=ends.map(w=>{const p=workspace.querySelector(`.wire-group[data-wire-id="${w.id}"] path.wire`),m=layoutWorldMatrix(p),L=p.getTotalLength();
      const q=p.getPointAtLength(w.a===n.id&&w.aSide===compat?0:L),world=m?new DOMPoint(q.x,q.y).matrixTransform(m):q;return {wire:w.id,x:world.x-n.x,y:world.y-n.y}});
    ports.push({id:point.id,side,x:P.x,y:P.y,onOutline:onStroke(P.x,P.y),lead:leadInfo,routeEnds});
  }
  const title=g.querySelector(':scope > text.component-label'),glyph=g.querySelector(':scope > use.glyph, :scope > .custom-graphic');
  const badge=g.querySelector(':scope > .card-badge rect'),chip=g.querySelector(':scope > .status-chip rect'),rim=g.querySelector(':scope > .body-rim');
  const rect=el=>({l:Number(el.getAttribute('x')),t:Number(el.getAttribute('y')),r:Number(el.getAttribute('x'))+Number(el.getAttribute('width')),b:Number(el.getAttribute('y'))+Number(el.getAttribute('height'))});
  return {tag:body.localName,d:body.getAttribute('d'),shape:g.dataset.shape||null,w:size.w,h:size.h,box:bb(body),
    corners:{tl:inFill(-hw+1,-hh+1),tr:inFill(hw-1,-hh+1),bl:inFill(-hw+1,hh-1),br:inFill(hw-1,hh-1),centre:inFill(0,0)},
    ports,title:title?bb(title):null,titleText:title?title.textContent:null,glyph:glyph?bb(glyph):null,
    badge:badge?rect(badge):null,chip:chip?rect(chip):null,rim:!!rim,
    dash:getComputedStyle(body).strokeDasharray,rimDash:rim?getComputedStyle(rim).strokeDasharray:null,
    bodyOpacity:Number(getComputedStyle(body).opacity),titleOpacity:title?Number(getComputedStyle(title).opacity):null,
    fade:statusFade(n),elevation:body.dataset.elevation||null,filter:body.style.filter||''};
}'''

TEXT_CONTRAST = r'''()=>{
  fitDiagram();
  const c=SovSchematicAPI.layout.contrast({static:true});
  return c.findings.filter(f=>f.kind==='text-contrast').map(f=>f.detail);
}'''


def inner(shape: str, w: float, h: float) -> dict:
    """The inner rectangle, from the contract's own formulas."""
    if shape == 'parallelogram':
        s = min(0.2 * w, 0.25 * h, 24)
        return {'l': -w / 2 + s, 'r': w / 2 - s, 't': -h / 2, 'b': h / 2}
    cap = min(0.18 * h, 18)
    return {'l': -w / 2, 'r': w / 2, 't': -h / 2 + cap, 'b': h / 2 - cap / 2}


def inside(box: dict, room: dict, slack: float = 0.5) -> bool:
    return box['l'] >= room['l'] - slack and box['r'] <= room['r'] + slack and box['t'] >= room['t'] - slack and box['b'] <= room['b'] + slack


def check_card(m: dict, shape: str, leads: set[str], label: str) -> None:
    w, h = m['w'], m['h']
    assert m['tag'] == 'path' and m['d'], (label, 'the body is a path, not a rect', m['tag'])
    assert m['shape'] == shape, (label, m['shape'])
    B = m['box']
    assert B['l'] >= -w / 2 - 0.01 and B['r'] <= w / 2 + 0.01 and B['t'] >= -h / 2 - 0.01 and B['b'] <= h / 2 + 0.01, (label, 'the body leaves its bounding box', B)
    assert abs(B['l'] + w / 2) < 0.5 and abs(B['r'] - w / 2) < 0.5 and abs(B['t'] + h / 2) < 0.5 and abs(B['b'] - h / 2) < 0.5, (label, 'the body does not span its bounding box', B)
    c = m['corners']
    assert c['centre'], (label, 'the centre is not filled')
    if shape == 'parallelogram':
        assert not c['tl'] and not c['br'] and c['tr'] and c['bl'], (label, 'a parallelogram cuts the top-left and bottom-right corners', c)
    else:
        assert not any(c[k] for k in ('tl', 'tr', 'bl', 'br')), (label, 'a cylinder cuts all four corners', c)
        assert m['rim'], (label, 'a cylinder draws its rim')
    # Ports: on the bounding sides; on the outline, or joined to it by a lead.
    assert {p['side'] for p in m['ports']} >= {'left', 'right', 'top'}, (label, 'wired in, out and on top', [(p['id'], p['side']) for p in m['ports']])
    for p in m['ports']:
        on_side = {'left': abs(p['x'] + w / 2), 'right': abs(p['x'] - w / 2), 'top': abs(p['y'] + h / 2), 'bottom': abs(p['y'] - h / 2)}[p['side']]
        assert on_side < 0.01, (label, 'a port left its bounding side', p)
        lead = p['lead']
        if lead:
            assert abs(lead['from']['x'] - p['x']) < 0.05 and abs(lead['from']['y'] - p['y']) < 0.05, (label, 'a lead does not start at its port', p)
            assert lead['endsOnOutline'], (label, 'a lead does not reach the drawn outline', p)
            assert lead['length'] > 0.5 and lead['stroke'] not in ('none', ''), (label, 'a lead is not drawn', p)
        assert p['onOutline'] or (lead and lead['endsOnOutline']), (label, 'a wired port neither lies on the outline nor has a lead reaching it', p)
        for e in p['routeEnds']:
            assert abs(e['x'] - p['x']) < 1.0 and abs(e['y'] - p['y']) < 1.0, (label, 'a route does not end on its port, on the bounding side', e, p)
    assert {p['side'] for p in m['ports'] if p['lead']} == leads, (label, 'leads', {p['side'] for p in m['ports'] if p['lead']}, leads)
    # Text, glyph and chips keep to the inner rectangle.
    room = inner(shape, w, h)
    assert m['title'] and inside(m['title'], room), (label, 'the title leaves the inner rectangle', m['title'], room)
    assert m['glyph'] and inside(m['glyph'], room), (label, 'the glyph leaves the inner rectangle', m['glyph'], room)
    if m['badge']:
        assert inside(m['badge'], room), (label, 'a badge leaves the inner rectangle', m['badge'], room)
    if m['chip']:
        assert inside(m['chip'], room), (label, 'the status chip leaves the inner rectangle', m['chip'], room)


def main() -> None:
    from playwright.sync_api import sync_playwright
    from browser_runtime import chromium_launch_kwargs
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load'); page.wait_for_timeout(150)
        doc = dict(DOC, schema=page.evaluate('()=>SovSchematicData.DOCUMENT_SCHEMA'))
        text = json.dumps(doc)

        def open_doc(t: str, name: str = 'shapes.sov') -> None:
            page.evaluate('([t,n])=>{SovSchematicAPI.file.open(t,n);fitDiagram()}', [t, name]); page.wait_for_timeout(250)

        open_doc(text)
        assert page.evaluate('()=>nodes.length') == len(DOC['components']), 'the document did not open'

        # Drawing, ports, leads, routes, the inner rectangle.
        cyl = page.evaluate(CARD, 'cyl')
        par = page.evaluate(CARD, 'par')
        # A cylinder's side ports at mid-height lie on its outline; its off-centre top port needs a lead.
        check_card(cyl, 'cylinder', {'top'}, 'cylinder')
        check_card(par, 'parallelogram', {'left', 'right', 'top'}, 'parallelogram')
        assert cyl['badge'] and par['badge'], 'the badges are drawn'
        plain = page.evaluate('()=>{const b=document.querySelector(`#nodes > .node[data-id="src"] > .body`);return {tag:b.localName,leads:document.querySelectorAll(`#nodes > .node[data-id="src"] > .shape-lead`).length}}')
        assert plain == {'tag': 'rect', 'leads': 0}, ('a card with no shape is a rect with no shape lead', plain)
        # Fill, outline and elevation follow the rectangle's rules.
        ref = page.evaluate(r'''()=>{const s=id=>{const b=document.querySelector(`#nodes > .node[data-id="${id}"] > .body`),c=getComputedStyle(b);return {fill:c.fill,stroke:c.stroke,width:c.strokeWidth,filter:b.style.filter,elevation:b.dataset.elevation||null}};return {src:s('src'),cyl:s('cyl'),par:s('par')}}''')
        assert ref['cyl'] == ref['src'] and ref['par'] == ref['src'], ('fill, outline and elevation differ from a rect card', ref)

        counts = page.evaluate('()=>SovSchematicAPI.layout.metrics({static:true}).counts')
        assert counts.get('route-through-node', 0) == 0, counts
        assert counts.get('port-wrong-side', 0) == 0, counts

        # Contrast in light and in dark.
        for appearance in ('light', 'dark'):
            page.evaluate('(a)=>SovSchematicAPI.view.setAppearance(a)', appearance)
            open_doc(text)
            found = page.evaluate(TEXT_CONTRAST)
            assert found == [], (appearance, found)
            assert page.evaluate('()=>document.querySelectorAll("#nodes > .node > path.body").length') == 2, appearance
        page.evaluate('()=>SovSchematicAPI.view.setAppearance("light")')
        open_doc(text)

        # Refusals: the document is unchanged.
        before = page.evaluate('()=>JSON.stringify(SovSchematicAPI.file.document())')
        refused = {
            'disk on update': '()=>SovSchematicAPI.update("component","src",{config:{presentation:{shape:"disk"}}})',
            'disk on create': '()=>SovSchematicAPI.create("component",{id:"fresh",symbolId:"act",config:{label:"F",presentation:{shape:"disk"}}})',
            'not a string': '()=>SovSchematicAPI.update("component","src",{config:{presentation:{shape:7}}})',
            'cylinder on a group': '()=>SovSchematicAPI.create("component",{id:"grp",symbolId:"group",config:{label:"G",members:[],presentation:{shape:"cylinder"}}})',
            'parallelogram on a container': '()=>SovSchematicAPI.create("component",{id:"pl",symbolId:"plane",form:{dimension:2,regions:{interior:{state:"open"}}},config:{label:"P",presentation:{shape:"parallelogram"}}})',
            'cylinder on a point': '()=>SovSchematicAPI.create("component",{id:"pt",symbolId:"point",config:{presentation:{shape:"cylinder"}}})',
        }
        for name, js in refused.items():
            receipt = page.evaluate(js)
            assert not receipt.get('ok') and 'SHAPE_INVALID' in json.dumps(receipt), (name, receipt)
            assert page.evaluate('()=>JSON.stringify(SovSchematicAPI.file.document())') == before, f'a refused shape ({name}) changed the document'

        # A file carrying a bad shape loads and reports it.
        bad = json.loads(text)
        bad['components'][1]['config']['presentation']['shape'] = 'disk'
        errs = page.evaluate('(t)=>SovSchematicData.validateDocument(SovSchematicData.makeDocument(JSON.parse(t))).errors', json.dumps(bad))
        assert any(e.startswith('component cyl: SHAPE_INVALID') and 'disk' in e for e in errs), errs
        assert page.evaluate('(t)=>SovSchematicData.validateDocument(SovSchematicData.makeDocument(JSON.parse(t))).errors.filter(e=>/SHAPE_INVALID/.test(e))', text) == []

        # rect is what absent means; null removes the key; an update changes the drawing.
        r = page.evaluate('()=>SovSchematicAPI.update("component","dst",{config:{presentation:{shape:"parallelogram"}}})')
        assert r.get('ok'), r
        assert page.evaluate('()=>document.querySelector(`#nodes > .node[data-id="dst"] > .body`).localName') == 'path'
        r = page.evaluate('()=>SovSchematicAPI.update("component","dst",{config:{presentation:{shape:"rect"}}})')
        assert r.get('ok'), r
        assert page.evaluate('()=>document.querySelector(`#nodes > .node[data-id="dst"] > .body`).localName') == 'rect'
        r = page.evaluate('()=>SovSchematicAPI.update("component","dst",{config:{presentation:{shape:null}}})')
        assert r.get('ok'), r
        assert page.evaluate('()=>"shape" in nodes.find(n=>n.id==="dst").config.presentation') is False

        # A sectioned Form keeps the rectangle.
        r = page.evaluate('()=>SovSchematicAPI.create("component",{id:"sec",symbolId:"act",x:1090,y:560,form:{dimension:2,section:SovSchematicData.sectionPreset("coated",2)},config:{label:"Coated",presentation:{shape:"cylinder"}}})')
        assert r.get('ok'), r
        sec = page.evaluate('()=>{const g=document.querySelector(`#nodes > .node[data-id="sec"]`);return {tag:g.querySelector(":scope > .body").localName,lines:g.querySelectorAll(":scope > .section-line").length,shape:g.dataset.shape||null}}')
        assert sec['tag'] == 'rect' and sec['lines'] >= 1 and sec['shape'] is None, ('a sectioned Form keeps the rectangle', sec)

        # The selection panel shows the shape.
        shown = page.evaluate('()=>{const out={};for(const id of ["cyl","par","src"]){selectNode(id,{focus:false});out[id]=iBoundary.textContent}selectNode(null);return out}')
        assert shown == {'cyl': 'cylinder', 'par': 'parallelogram', 'src': 'rect'}, shown
        assert page.evaluate('()=>nodes.every(n=>!n.boundary||!("shape" in n.boundary))'), 'boundary.shape is still written'

        # The picture carries the path; saving and opening keeps the shapes.
        svg = page.evaluate('()=>SovSchematicAPI.render.svg({})')
        assert f'd="{cyl["d"]}"' in svg and f'd="{par["d"]}"' in svg, 'the picture does not carry the shaped bodies'
        saved = page.evaluate('()=>JSON.stringify(SovSchematicAPI.file.document())')
        open_doc(saved, 'again.sov')
        again = page.evaluate('()=>Object.fromEntries(SovSchematicAPI.file.document().components.map(c=>[c.id,c.config.presentation?.shape??null]))')
        assert again['cyl'] == 'cylinder' and again['par'] == 'parallelogram' and again['src'] is None and again['dst'] is None, again
        check_card(page.evaluate(CARD, 'cyl'), 'cylinder', {'top'}, 'cylinder after save and open')
        check_card(page.evaluate(CARD, 'par'), 'parallelogram', {'left', 'right', 'top'}, 'parallelogram after save and open')

        # A status on a shaped card: the dashed outline, the fade on the body and not the text, the chip inside.
        open_doc(STATUS.read_text(encoding='utf-8'), 'status.sov')
        for cid, shape in (('anchor', 'cylinder'), ('continuity-to-sqlite', 'parallelogram'), ('recording', 'parallelogram')):
            r = page.evaluate('([id,s])=>SovSchematicAPI.update("component",id,{config:{badges:[{label:"Kept"}],presentation:{shape:s,size:{w:260,h:110}}}})', [cid, shape])
            assert r.get('ok'), r
        page.evaluate('()=>fitDiagram()'); page.wait_for_timeout(150)
        flat = page.evaluate('()=>({anchor:declaredStatus(nodes.find(n=>n.id==="anchor")),proposed:declaredStatus(nodes.find(n=>n.id==="continuity-to-sqlite"))})')
        for cid, shape in (('anchor', 'cylinder'), ('continuity-to-sqlite', 'parallelogram'), ('recording', 'parallelogram')):
            m = page.evaluate(CARD, cid)
            assert m['tag'] == 'path' and m['shape'] == shape, (cid, m['tag'], m['shape'])
            room = inner(shape, m['w'], m['h'])
            assert m['chip'] and inside(m['chip'], room), (cid, 'the status chip leaves the inner rectangle', m['chip'], room)
            assert m['badge'] and inside(m['badge'], room), (cid, 'a badge leaves the inner rectangle', m['badge'], room)
            assert m['title'] and inside(m['title'], room), (cid, 'the title leaves the inner rectangle', m['title'], room)
            if m['fade'] < 1:
                assert abs(m['bodyOpacity'] - m['fade']) < 0.01 and m['titleOpacity'] == 1, (cid, 'the fade is on the body and not on the text', m['bodyOpacity'], m['titleOpacity'], m['fade'])
        anchor = page.evaluate(CARD, 'anchor')
        assert flat['anchor'] and flat['anchor'].get('outline') == 'dashed', flat
        assert anchor['dash'] not in ('none', '') and anchor['rimDash'] not in ('none', '', None), ('a dashed status dashes the shaped outline and its rim', anchor['dash'], anchor['rimDash'])
        assert any(page.evaluate(CARD, c)['fade'] < 1 for c in ('anchor', 'continuity-to-sqlite', 'recording')), 'no status on this document fades its card; the fade check ran on nothing'
        for appearance in ('light', 'dark'):
            page.evaluate('(a)=>SovSchematicAPI.view.setAppearance(a)', appearance); page.wait_for_timeout(100)
            found = page.evaluate(TEXT_CONTRAST)
            assert found == [], ('status.sov with shapes', appearance, found)

        assert not errors, errors
        browser.close()
    print('card shapes: path bodies, leads to the outline, routes on the bounding sides, inner rectangle, refusals, load report, contrast in light and dark, save and open, selection panel, status and badges')


if __name__ == '__main__':
    main()
    print('PASS card shapes QA')
