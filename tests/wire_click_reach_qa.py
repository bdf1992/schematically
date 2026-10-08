"""A wire is easy to find and click.

A wire takes a click within a few screen pixels of its line at every zoom, shows on hover that it
can be clicked, and where click zones overlap the wire whose line is nearest the pointer is taken.

  A: at the zoom the map opens at (--zoom 0.2625) a click 0, 2 and 5 px off the line selects the
     wire and a click 9 px off does not.
  B: the pointer 5 px off the line marks the wire's group wire-hover and draws it at least 2.9
     screen px wide; 80 px further away no group is marked.
  C: on examples/work-engine/groups.sov, zoomed out below 0.35, the middle of the longest segment
     of each wire that rides a bus selects that wire.

    python tests/wire_click_reach_qa.py
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text()

# Screen point 30 percent along the line of wire w1, moved straight down by dy px.
POINT = """(dy)=>{const p=document.querySelector('.wire-group[data-wire-id="w1"] path.wire');
  const q=p.getPointAtLength(p.getTotalLength()*0.3);const m=p.getScreenCTM();
  return {x:m.a*q.x+m.c*q.y+m.e,y:m.b*q.x+m.d*q.y+m.f+dy}}"""
STATE = "()=>({selected:selected,zoom:Number(workspace.style.getPropertyValue('--zoom'))})"
HOVERED = "()=>[...document.querySelectorAll('.wire-group.wire-hover')].map(g=>g.dataset.wireId)"
CLEAR = "()=>{selectNode(null);selected=null}"


def run():
    with sync_playwright() as p:
        b = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = b.new_page(viewport={'width': 1600, 'height': 1000})
        errors = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content(HTML, wait_until='load')
        page.wait_for_timeout(300)

        page.evaluate("""()=>{const A=window.SovSchematicAPI;
          A.create('component',{id:'a',symbolId:'act',x:300,y:300});
          A.create('component',{id:'b',symbolId:'act',x:700,y:300});
          A.create('wire',{id:'w1',a:'a',aSide:'out',b:'b',bSide:'in'});
          camera={...camera,x:500-BASE_VIEW.w/0.3/2,y:300-BASE_VIEW.h/0.3/2,w:BASE_VIEW.w/0.3,h:BASE_VIEW.h/0.3};
          applyCamera()}""")
        page.wait_for_timeout(200)
        zoom = page.evaluate(STATE)['zoom']
        print('scenario A --zoom', zoom)
        assert abs(zoom - 0.2625) < 0.01, zoom

        # A: reach.
        picked = {}
        for dy in (0, 2, 5, 9):
            page.evaluate(CLEAR)
            pt = page.evaluate(POINT, dy)
            page.mouse.move(pt['x'], pt['y'] - 60)
            page.mouse.click(pt['x'], pt['y'])
            page.wait_for_timeout(60)
            picked[dy] = page.evaluate(STATE)['selected']
        print('scenario A selected by px off the line:', picked)
        for dy in (0, 2, 5):
            assert picked[dy] == 'wire:0', (dy, picked)
        assert picked[9] is None, picked

        # B: hover cue reaches as far as the click and draws at least 3 screen px wide.
        page.evaluate(CLEAR)
        pt = page.evaluate(POINT, 5)
        page.mouse.move(pt['x'], pt['y'] - 40)
        page.mouse.move(pt['x'], pt['y'], steps=4)
        page.wait_for_timeout(250)
        hovered = page.evaluate(HOVERED)
        width = page.evaluate("""()=>{const p=document.querySelector('.wire-group[data-wire-id="w1"] path.wire');
          return parseFloat(getComputedStyle(p).strokeWidth)*Number(workspace.style.getPropertyValue('--zoom'))}""")
        print('scenario B hovered', hovered, 'screen width', round(width, 2))
        assert hovered == ['w1'], hovered
        assert width >= 2.9, width
        page.mouse.move(pt['x'], pt['y'] + 80, steps=4)
        page.wait_for_timeout(250)
        far = page.evaluate(HOVERED)
        print('scenario B hovered 80 px further down', far)
        assert far == [], far

        # C: wires on a bus, zoomed out.
        text = (ROOT / 'examples/work-engine/groups.sov').read_text(encoding='utf-8')
        page.evaluate('(t)=>{SovSchematicAPI.file.open(t,"groups.sov");fitDiagram()}', text)
        page.wait_for_timeout(300)
        page.evaluate("""()=>{let n=0;while(Number(workspace.style.getPropertyValue('--zoom'))>=0.35&&n++<60){
          const cx=camera.x+camera.w/2,cy=camera.y+camera.h/2,w=camera.w*1.05,h=camera.h*1.05;
          camera={...camera,x:cx-w/2,y:cy-h/2,w,h};applyCamera()}}""")
        page.wait_for_timeout(200)
        print('scenario C --zoom', page.evaluate(STATE)['zoom'])
        assert page.evaluate(STATE)['zoom'] < 0.35
        for wid in ('booth-to-case', 'broker-to-recording'):
            page.evaluate(CLEAR)
            pt = page.evaluate("""(wid)=>{const i=wires.findIndex(w=>w.id===wid);const pts=drawnRoutePoints.get(i);
              let best=null,len=-1;for(let k=0;k+1<pts.length;k++){const l=Math.hypot(pts[k+1].x-pts[k].x,pts[k+1].y-pts[k].y);
                if(l>len){len=l;best=k}}
              const q={x:(pts[best].x+pts[best+1].x)/2,y:(pts[best].y+pts[best+1].y)/2};
              const m=workspace.getScreenCTM();return {i:i,x:m.a*q.x+m.c*q.y+m.e,y:m.b*q.x+m.d*q.y+m.f}}""", wid)
            page.mouse.move(pt['x'], pt['y'] - 50)
            page.mouse.click(pt['x'], pt['y'])
            page.wait_for_timeout(60)
            got = page.evaluate(STATE)['selected']
            print(f'scenario C {wid} (wire:{pt["i"]}) click selected', got)
            assert got == f'wire:{pt["i"]}', (wid, got)

        assert not errors, f'page errors: {errors}'
        b.close()


run()
print('PASS wire click reach QA')
