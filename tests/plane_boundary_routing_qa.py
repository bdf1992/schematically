"""A carrier on a Plane's boundary point runs inside the Plane.

A wire bound to a data-declared boundary point (`config.attachmentPoints`) of a Plane and
carried on the Plane's interior surface routes inside the Plane exactly as one bound to a
hosted Point does: it leaves the boundary inward, and the Plane's body is the surface it
runs on rather than an obstacle to route around the outside of.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page(viewport={'width':1600,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(HTML,wait_until='load');page.wait_for_timeout(120)
    routes=page.evaluate('''()=>{
      newSchematic();
      const must=r=>{if(!r.ok)throw new Error(r.error.message);return r.result};
      must(SovSchematicAPI.create('component',{id:'pl',symbolId:'plane',x:700,y:400,config:{attachmentPoints:[{id:'feed',side:'left',t:.25}],ports:{feed:{face:'both'}}}}));
      must(SovSchematicAPI.create('component',{id:'h1',symbolId:'hold',x:760,y:350,canvasId:'canvas:component:pl'}));
      must(SovSchematicAPI.create('component',{id:'h2',symbolId:'hold',x:760,y:455,canvasId:'canvas:component:pl'}));
      must(SovSchematicAPI.create('component',{id:'pt',symbolId:'point',x:0,y:0}));
      {const n=nodes.find(n=>n.id==='pt'),h=nodes.find(n=>n.id==='pl'),s=componentSize(h);applyComponentHost(n,componentHostCandidateAtPoint(n,h.x-s.w/2+1,h.y+55));render()}
      must(SovSchematicAPI.update('component','pt',{config:{ports:{out:{face:'both'}}}}));
      must(SovSchematicAPI.create('wire',{id:'w1',a:'pl',aSide:'feed',b:'h1',bSide:'in'}));
      must(SovSchematicAPI.create('wire',{id:'w2',a:'pt',aSide:'self',b:'h2',bSide:'in'}));
      const R=componentBounds(nodes.find(n=>n.id==='pl'));
      const sample=id=>{const w=wires.find(w=>w.id===id),path=renderedWirePath(w),L=path.getTotalLength();
        let inside=true;for(let k=0;k<=20;k++){const q=path.getPointAtLength(L*k/20);if(q.x<R.l-1||q.x>R.r+1||q.y<R.t-1||q.y>R.b+1)inside=false}
        const q=path.getPointAtLength(Math.min(L,20));return {canvasId:w.canvasId,inside,inward:q.x>R.l+8,d:path.getAttribute('d')}};
      // A wire on the world from an outside Component into the same boundary point still leaves outward.
      must(SovSchematicAPI.create('component',{id:'src',symbolId:'act',x:300,y:345}));
      must(SovSchematicAPI.create('wire',{id:'w0',a:'src',aSide:'out',b:'pl',bSide:'feed'}));
      const w0=wires.find(w=>w.id==='w0'),p0=renderedWirePath(w0),L0=p0.getTotalLength(),q0=p0.getPointAtLength(Math.max(0,L0-20));
      return {pt:nodes.find(n=>n.id==='pt').placement.kind,w1:sample('w1'),w2:sample('w2'),w0:{canvasId:w0.canvasId,outside:q0.x<R.l-8,d:p0.getAttribute('d')}}}''')
    assert routes['pt']=='edge',routes
    for key in ('w1','w2'):
        r=routes[key]
        assert r['canvasId']=='canvas:component:pl',(key,r)
        assert r['inside'] and r['inward'],(key,r)
    assert routes['w0']['canvasId']=='canvas:global' and routes['w0']['outside'],routes['w0']
    browser.close()
assert not errors,errors
print('PASS Plane boundary routing QA')
