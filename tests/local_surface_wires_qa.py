"""Wires on a local surface paint above their host.

Every wire is projected beneath the nodes, so a wire on a Component's interior surface
would be hidden by its host's body. Such a wire is lifted to just after its host in the
node layer on every render: above the host body, beneath the hosted children, on the
first load and on every later one, and after a wire-only frame.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
errors=[]
ORDER=r'''()=>{
  const layer=[...nodesG.children];
  const out={count:document.querySelectorAll('.wire-group').length,globalInWires:0,local:[]};
  for(const w of wires){
    const g=document.querySelector(`.wire-group[data-wire-id="${w.id}"]`);
    const surface=w.canvasId||'canvas:global';
    if(!surface.startsWith('canvas:component:')){if(g?.parentElement===wiresG)out.globalInWires++;continue}
    const hostId=surface.slice('canvas:component:'.length);
    const hostEl=nodesG.querySelector(`:scope > .node[data-id="${hostId}"]`);
    const children=nodes.filter(n=>n.canvasId===surface).map(n=>layer.indexOf(nodesG.querySelector(`:scope > .node[data-id="${n.id}"]`)));
    const path=g?.querySelector('.wire');const L=path?path.getTotalLength():0;const mid=path?path.getPointAtLength(L/2):null;
    let top=null;if(mid){const m=workspace.getScreenCTM();const el=document.elementFromPoint(mid.x*m.a+m.e,mid.y*m.d+m.f);top=el?.closest('.wire-group')?.dataset.wireId||el?.closest('.node')?.dataset.id||null}
    out.local.push({id:w.id,host:hostId,inNodes:g?.parentElement===nodesG,wireIndex:layer.indexOf(g),hostIndex:layer.indexOf(hostEl),minChild:Math.min(...children),top,path:!!renderedWirePath(w)});
  }
  return out}'''
def check(state,total,local,label):
    assert state['count']==total and len(state['local'])==local and state['globalInWires']==total-local,(label,state)
    for w in state['local']:
        assert w['inNodes'] and w['path'],(label,w)
        assert w['hostIndex']<w['wireIndex']<w['minChild'],(label,w)
        assert w['top']==w['id'],(label,w)
with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page(viewport={'width':1600,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(HTML,wait_until='load');page.wait_for_timeout(120)
    example=(ROOT/'examples/08-gated-service.sov').read_text(encoding='utf-8')
    # 1. First load: interior wires sit above the host body and below its children.
    page.evaluate('(t)=>{SovSchematicAPI.file.open(t,"08.sov");fitDiagram()}',example);page.wait_for_timeout(200)
    check(page.evaluate(ORDER),7,4,'first load')
    # 2. A wire-only frame (drag, inspector edit) and a full render keep one group per wire.
    page.evaluate('renderWires()');check(page.evaluate(ORDER),7,4,'renderWires alone')
    page.evaluate('render()');check(page.evaluate(ORDER),7,4,'render')
    # 3. The second open of the same file paints exactly like the first.
    page.evaluate('(t)=>{SovSchematicAPI.file.open(t,"08.sov");fitDiagram()}',example);page.wait_for_timeout(200)
    check(page.evaluate(ORDER),7,4,'second load')
    # 4. Wire focus mutes by wire identity, not by document order.
    muted=page.evaluate('''()=>{const i=wires.findIndex(w=>w.id==='k5');focusWireVisual(i);
      const on=[...document.querySelectorAll('.wire-group')].filter(g=>!g.classList.contains('muted')).map(g=>g.dataset.wireId);
      clearWireVisualFocus();const after=document.querySelectorAll('.wire-group.muted').length;return {on,after}}''')
    assert muted=={'on':['k5'],'after':0},muted
    browser.close()
assert not errors,errors
print('PASS local-surface wires QA')
