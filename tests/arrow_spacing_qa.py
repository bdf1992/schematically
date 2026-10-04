"""Arrow spacing QA: direction marks are spaced by length, one per run, not two per segment.

- A directed wire under 20 draws none; one up to 480 (ARROW_SPACING) draws one mark at the middle
  of its longest straight segment; each further 480 adds one, at most 4, on different segments.
- A mark keeps 8 or more from a bend and stays clear of hops and junctions.
- A duplex wire puts a forward and a reverse mark side by side at each place.
- The work-engine sample has no arrowless wire and no segment carrying two marks unless it is
  longer than 480.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

SPACING = 480
HOP = 6.5

# Every wire's world-space corners and marks; a mark is its tip in world space and whether it is the reverse one.
READ = r"""()=>{
  const out=[];
  for(const g of workspace.querySelectorAll('.wire-group')){
    const p=g.querySelector('path.wire'),m=layoutWorldMatrix(p),w=wires.find(x=>x.id===g.dataset.wireId);
    const to=(x,y)=>{const q=new DOMPoint(x,y);return m?q.matrixTransform(m):q};
    const marks=[...g.querySelectorAll('.flow-chevron')].map(c=>{
      const t=/translate\(([-\d.e]+) ([-\d.e]+)\) rotate\(([-\d.e]+)\)/.exec(c.getAttribute('transform')),q=to(+t[1],+t[2]);
      return {x:q.x,y:q.y,angle:+t[3]};
    });
    out.push({id:g.dataset.wireId,length:p.getTotalLength(),corners:layoutRouteCorners(p).map(q=>({x:q.x,y:q.y})),
      hops:(p.getAttribute('d').match(/ A /g)||[]).length,marks});
  }
  return out;
}"""

# Free-ended wires: the route is exactly the points given (ends, then pinned bends).
PLANT = r"""([specs])=>{
  SovSchematicAPI.document.replace({schema:SovSchematicData.DOCUMENT_SCHEMA,id:'arrows',components:[],wires:[]});
  for(const s of specs){
    const r=SovSchematicAPI.create('wire',{id:s.id,aAttachment:{kind:'free',x:s.pts[0][0],y:s.pts[0][1]},
      bAttachment:{kind:'free',x:s.pts.at(-1)[0],y:s.pts.at(-1)[1]},config:s.config||{}});
    if(!r.ok&&!r.result)throw new Error(JSON.stringify(r));
    const mid=s.pts.slice(1,-1).map(p=>({x:p[0],y:p[1]}));
    if(mid.length){const q=SovSchematicAPI.layout.route(s.id,{mode:'pinned',points:mid});if(!q.ok)throw new Error(JSON.stringify(q))}
  }
  fitDiagram();
}"""


def legs(corners):
    return [(corners[i], corners[i + 1]) for i in range(len(corners) - 1)]


def seg_len(a, b):
    return ((a['x'] - b['x']) ** 2 + (a['y'] - b['y']) ** 2) ** .5


def on_seg(q, a, b, tol=.6):
    lo_x, hi_x = min(a['x'], b['x']) - tol, max(a['x'], b['x']) + tol
    lo_y, hi_y = min(a['y'], b['y']) - tol, max(a['y'], b['y']) + tol
    return lo_x <= q['x'] <= hi_x and lo_y <= q['y'] <= hi_y


def leg_of(q, corners):
    for i, (a, b) in enumerate(legs(corners)):
        if on_seg(q, a, b):
            return i
    raise AssertionError(('a mark is on no segment', q, corners))


def check_marks(wire):
    """Every mark is on a segment and 8 or more from every bend."""
    cs = wire['corners']
    for q in wire['marks']:
        leg_of(q, cs)
        for bend in cs[1:-1]:
            assert seg_len(q, bend) >= 8 - .01, ('a mark within 8 of a bend', wire['id'], q, bend)


def run() -> None:
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(250)

        def plant(specs):
            page.evaluate(PLANT, [specs])
            page.wait_for_timeout(120)
            return {w['id']: w for w in page.evaluate(READ)}

        # A straight wire 300 long: one mark at its middle. A 15 wire: none.
        ws = plant([
            {'id': 'straight', 'pts': [(100, 100), (400, 100)]},
            {'id': 'tiny', 'pts': [(100, 300), (115, 300)]},
        ])
        w = ws['straight']
        assert abs(w['length'] - 300) < 1, w['length']
        assert len(w['marks']) == 1, ('a 300 wire has one mark', w['marks'])
        assert abs(w['marks'][0]['x'] - 250) < 1.5 and abs(w['marks'][0]['y'] - 100) < 1.5, ('at its middle', w['marks'])
        assert len(ws['tiny']['marks']) == 0, ('a wire under 20 has none', ws['tiny']['marks'])

        # An L with legs 400 and 120: one mark, on the 400 leg.
        ws = plant([{'id': 'ell', 'pts': [(100, 100), (500, 100), (500, 220)]}])
        w = ws['ell']
        assert len(w['corners']) == 3 and abs(w['length'] - 520) < 1, (w['corners'], w['length'])
        assert len(w['marks']) == 1, ('an L of 400 and 120 has one mark', w['marks'])
        assert leg_of(w['marks'][0], w['corners']) == 0, ('on the 400 leg', w['marks'], w['corners'])
        assert abs(w['marks'][0]['x'] - 300) < 1.5, ('at the middle of the 400 leg', w['marks'])
        check_marks(w)

        # An L short of one spacing: legs 330 and 120 (450): exactly one mark, on the long leg.
        ws = plant([{'id': 'ell2', 'pts': [(100, 100), (430, 100), (430, 220)]}])
        w = ws['ell2']
        assert len(w['marks']) == 1, ('one mark up to 480', w['marks'])
        assert leg_of(w['marks'][0], w['corners']) == 0, ('on the long leg', w['marks'], w['corners'])
        assert abs(w['marks'][0]['x'] - 265) < 1.5, ('at the middle of the long leg', w['marks'])
        check_marks(w)

        # A Z 1200 long (three legs of 400): three marks on three different segments.
        ws = plant([{'id': 'zed', 'pts': [(100, 100), (500, 100), (500, 500), (900, 500)]}])
        w = ws['zed']
        assert abs(w['length'] - 1200) < 1, w['length']
        assert len(w['marks']) == 3, ('a 1200 wire has three marks', w['marks'])
        assert len({leg_of(q, w['corners']) for q in w['marks']}) == 3, ('on three different segments', w['marks'])
        check_marks(w)

        # A very long staircase takes at most 4 marks.
        pts = [(100, 100)]
        for i in range(8):
            pts.append((pts[-1][0] + 300, pts[-1][1]) if i % 2 == 0 else (pts[-1][0], pts[-1][1] + 300))
        ws = plant([{'id': 'long', 'pts': pts}])
        w = ws['long']
        assert len(w['marks']) == 4, ('at most 4 marks', len(w['marks']), w['length'])
        assert len({leg_of(q, w['corners']) for q in w['marks']}) == 4, w['marks']
        check_marks(w)

        # A duplex wire 300 long: one forward and one reverse mark.
        ws = plant([{'id': 'duo', 'pts': [(100, 100), (400, 100)], 'config': {'direction': 'duplex'}}])
        w = ws['duo']
        assert len(w['marks']) == 2, ('a duplex wire has a pair', w['marks'])
        a, b = sorted(w['marks'], key=lambda q: q['x'])
        angles = sorted(round(q['angle']) % 360 for q in w['marks'])
        assert angles == [0, 180], ('one forward, one reverse', angles)
        assert abs((a['x'] + b['x']) / 2 - 250) < 1.5, ('side by side at the middle', a, b)
        check_marks(w)

        # Crossings: two 300 wires meet at the middle of each; their marks slide off the hop.
        # Bound wires: a wire with free ends shares no end to cross over, so use cards.
        page.evaluate(r"""()=>{
          SovSchematicAPI.document.replace({schema:SovSchematicData.DOCUMENT_SCHEMA,id:'x',components:[
            {id:'l',symbolId:'act',x:100,y:300},{id:'r',symbolId:'act',x:700,y:300},
            {id:'t',symbolId:'act',x:318,y:80},{id:'b',symbolId:'act',x:318,y:560,config:{ports:{in:{boundary:{side:'top',t:.5}}}}}],
            wires:[{id:'h',a:'l',aSide:'out',b:'r',bSide:'in'},{id:'v',a:'t',aSide:'out',b:'b',bSide:'in'}]});
          fitDiagram();}""")
        page.wait_for_timeout(150)
        ws = {x['id']: x for x in page.evaluate(READ)}
        assert sum(x['hops'] for x in ws.values()) == 1, ('one crossing is drawn as one hop', {k: v['hops'] for k, v in ws.items()})
        hc, vc = ws['h']['corners'], ws['v']['corners']
        cross = {'x': vc[1]['x'], 'y': hc[0]['y']}  # v's long vertical leg runs at its second corner's x
        for x in ws.values():
            assert len(x['marks']) >= 1, ('each wire keeps a mark', x['id'], x['marks'])
            for q in x['marks']:
                assert seg_len(q, cross) > HOP, ('a mark clear of the hop', x['id'], q, cross)
            check_marks(x)
        # The middle of each wire is on the crossing, so the marks had to slide to clear it.
        mid_h = (hc[0]['x'] + hc[-1]['x']) / 2
        assert abs(mid_h - cross['x']) < 24, ('the plant puts the middle of h on the crossing', mid_h, cross)

        # The work-engine sample: no arrowless wire, and a segment carries two marks only past 480.
        text = (ROOT / 'tests' / 'fixtures' / 'work-engine-sample.sov').read_text(encoding='utf-8')
        page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [text, 'work-engine-sample.sov'])
        page.wait_for_timeout(300)
        counts = page.evaluate('()=>SovSchematicAPI.layout.metrics({static:true}).counts')
        assert counts.get('arrowless', 0) == 0, ('the sample has no arrowless wire', counts)
        sample = page.evaluate(READ)
        marked = 0
        for x in sample:
            check_marks(x)
            marked += len(x['marks'])
            per_leg: dict[int, int] = {}
            for q in x['marks']:
                i = leg_of(q, x['corners'])
                per_leg[i] = per_leg.get(i, 0) + 1
            for i, n in per_leg.items():
                a, b = legs(x['corners'])[i]
                assert n == 1 or seg_len(a, b) > SPACING, ('two marks on one short segment', x['id'], i, n, seg_len(a, b))
            assert len(x['marks']) <= 4, (x['id'], len(x['marks']))
        browser.close()
    assert not errors, errors
    print('PASS arrow spacing QA', {'sample marks': marked})


run()
