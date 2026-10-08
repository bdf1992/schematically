"""Group selection QA (SECTION-MODEL.md "Groups (reading only)", Selection).

A click on a group's title or on its ground (any part of its region that no card or wire
covers) selects the group and shows it in the Inspector. A drag from that ground pans the
canvas and leaves the selection as it was. The arrow keys do not move a selected group.

Browser (index.html in Chromium, examples/work-engine/groups.sov, 1400 by 900):
  (a) a click on the centre of the Records title selects records: its g.node.group is
      .selected, #componentDetail is shown and #iName reads GROUP;
  (b) a click on a point that resolves to #workspace clears the selection;
  (c) a click on a ground point of Surfaces selects surfaces;
  (d) a press on that ground point dragged 120 px right pans the camera, selection kept;
  (e) with Shift held, a press on the ground and a 40 px move is a marquee;
  (f) a click on a member card of Surfaces selects the card;
  (g) ArrowRight with surfaces selected leaves the group where it is;
  (h) render.svg({}) carries no group-hit;
  (i) every .group-region still computes pointer-events none; no page error.
"""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/work-engine/groups.sov'

# The first point of a 12 px grid over the group's region where the topmost element is the
# group's own hit rect.
GROUND = '''(id)=>{
  const g=document.querySelector(`.node.group[data-id="${CSS.escape(id)}"]`);if(!g)return null;
  const region=g.querySelector(':scope > .group-region'),hit=g.querySelector(':scope > .group-hit');
  if(!region||!hit)return null;
  const r=region.getBoundingClientRect();
  for(let y=r.top+6;y<r.bottom;y+=12)for(let x=r.left+6;x<r.right;x+=12){
    if(document.elementFromPoint(x,y)===hit)return {x,y};
  }
  return null;
}'''

# The first point of a 12 px grid over the canvas where the topmost element is #workspace.
BLANK = '''()=>{
  const ws=document.getElementById('workspace'),r=ws.getBoundingClientRect();
  for(let y=r.top+6;y<r.bottom;y+=12)for(let x=r.left+6;x<r.right;x+=12){
    if(document.elementFromPoint(x,y)===ws)return {x,y};
  }
  return null;
}'''

STATE = '''()=>({
  selected,
  classed:[...document.querySelectorAll('.node.group.selected')].map(g=>g.dataset.id),
  detailShown:!document.getElementById('componentDetail').hidden,
  name:document.getElementById('iName').textContent,
  cameraX:camera.x
})'''


def main() -> None:
    from playwright.sync_api import sync_playwright
    from browser_runtime import chromium_launch_kwargs
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    text = EXAMPLE.read_text(encoding='utf-8')
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.set_content(html, wait_until='load'); page.wait_for_timeout(150)
        page.evaluate('(t)=>{const r=SovSchematicAPI.file.open(t,"groups.sov");fitDiagram();return r}', text)
        page.wait_for_timeout(250)
        assert not errors, errors

        state = lambda: page.evaluate(STATE)
        ground = lambda gid: page.evaluate(GROUND, gid)

        def click(pt: dict) -> None:
            page.mouse.click(pt['x'], pt['y']); page.wait_for_timeout(80)

        # (a) the title of Records.
        title = page.evaluate('''()=>{const t=document.querySelector('.node.group[data-id="records"] > .group-title');
          if(!t)return null;const r=t.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2,text:t.textContent}}''')
        assert title and title['text'] == 'Records', title
        click(title)
        s = state()
        assert s['selected'] == 'records', ('(a) a click on the Records title must select the group', s)
        assert s['classed'] == ['records'], ('(a) the selected group carries class selected', s)
        assert s['detailShown'] and s['name'] == 'GROUP', ('(a) the Inspector shows the group', s)

        # (b) blank canvas clears.
        blank = page.evaluate(BLANK)
        assert blank, '(b) no point of the canvas resolves to #workspace'
        click(blank)
        s = state()
        assert s['selected'] is None and s['classed'] == [], ('(b) a click on blank canvas clears the selection', s)

        # (c) the ground of Surfaces.
        pt = ground('surfaces')
        assert pt, '(c) no ground point: no point of the Surfaces region resolves to its .group-hit'
        click(pt)
        s = state()
        assert s['selected'] == 'surfaces' and s['classed'] == ['surfaces'], ('(c) a click on the Surfaces ground must select the group', s)
        assert s['detailShown'] and s['name'] == 'GROUP', ('(c) the Inspector shows the group', s)

        # (d) a drag from the ground pans and keeps the selection.
        before = s['cameraX']
        page.mouse.move(pt['x'], pt['y']); page.mouse.down()
        for i in range(1, 7):
            page.mouse.move(pt['x'] + 20 * i, pt['y'])
        page.mouse.up(); page.wait_for_timeout(80)
        s = state()
        assert abs(s['cameraX'] - before) > 1, ('(d) a drag from the ground must pan the canvas', before, s)
        assert s['selected'] == 'surfaces' and s['classed'] == ['surfaces'], ('(d) a pan from the ground keeps the selection', s)
        moved = page.evaluate('()=>{const n=nodes.find(x=>x.id==="surfaces");return {x:n.x,y:n.y}}')

        # (e) Shift and a press on the ground is a marquee.
        pt = ground('surfaces')
        assert pt, '(e) no ground point after the pan'
        page.keyboard.down('Shift')
        page.mouse.move(pt['x'], pt['y']); page.mouse.down()
        page.mouse.move(pt['x'] + 20, pt['y'] + 4); page.mouse.move(pt['x'] + 40, pt['y'] + 8)
        marquee = page.evaluate('()=>marqueeGesture!==null')
        page.mouse.up(); page.keyboard.up('Shift'); page.wait_for_timeout(80)
        assert marquee, '(e) Shift and a press on the ground must begin a marquee'
        assert page.evaluate('()=>marqueeGesture===null&&panDrag===null'), '(e) the marquee did not end on release'
        blank = page.evaluate(BLANK)
        assert blank, '(e) no blank canvas point'
        click(blank)

        # (f) a member card still selects itself.
        card = page.evaluate('''()=>{const n=nodes.find(x=>x.id==="surfaces"),id=n.config.members[0];
          const b=document.querySelector(`#nodes > .node[data-id="${CSS.escape(id)}"] > .body`).getBoundingClientRect();
          return {id,x:b.left+b.width/2,y:b.top+b.height/2}}''')
        click(card)
        s = state()
        assert s['selected'] == card['id'] and s['classed'] == [], ('(f) a click on a member card selects the card', card, s)

        # (g) the arrow keys do not move a selected group.
        pt = ground('surfaces')
        assert pt, '(g) no ground point'
        click(pt)
        assert state()['selected'] == 'surfaces', ('(g) the group is selected before the key', state())
        rec = '''()=>{const n=nodes.find(x=>x.id==="surfaces"),g=document.querySelector('.node.group[data-id="surfaces"]');
          const r=g.querySelector(':scope > .group-region');
          return {x:n.x,y:n.y,transform:g.getAttribute('transform'),region:[r.getAttribute('x'),r.getAttribute('y')],
            members:n.config.members.map(id=>{const m=nodes.find(x=>x.id===id);return [m.x,m.y]}),selected,status:statusEl.textContent}}'''
        was = page.evaluate(rec)
        page.evaluate('''()=>{document.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',code:'ArrowRight',bubbles:true,cancelable:true}))}''')
        page.wait_for_timeout(400)
        now = page.evaluate(rec)
        assert now['transform'] is None, ('(g) ArrowRight must not translate the group', now)
        assert (now['x'], now['y']) == (was['x'], was['y']) == (moved['x'], moved['y']), ('(g) ArrowRight must not move the group record', was, now)
        assert now['region'] == was['region'] and now['members'] == was['members'], ('(g) the region and its members stay', was, now)
        assert now['selected'] == 'surfaces' and now['status'] == 'A group follows its cards', ('(g) the refusal is said in the status line', now)

        # (h) the picture carries no hit area.
        svg = page.evaluate('()=>SovSchematicAPI.render.svg({})')
        assert 'group-region' in svg, 'render.svg lost the groups'
        assert 'group-hit' not in svg, '(h) render.svg carries a group-hit'

        # (i) the region itself takes no pointer events.
        pointer = page.evaluate('()=>[...document.querySelectorAll(".group-region")].map(r=>getComputedStyle(r).pointerEvents)')
        assert len(pointer) == 2 and all(v == 'none' for v in pointer), ('(i) .group-region must compute pointer-events none', pointer)
        hits = page.evaluate('()=>[...document.querySelectorAll(".node.group")].map(g=>g.querySelectorAll(":scope > .group-hit").length)')
        assert hits == [1, 1], ('each group holds one .group-hit', hits)
        assert not errors, errors
        browser.close()
    print('PASS group select QA')


if __name__ == '__main__':
    main()
