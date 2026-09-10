"""Original review regressions: measured labels preserve model and rendered routes."""
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/swarm-originals'
STATE = """()=>({model:snapshotDocument(),routes:[...workspace.querySelectorAll('.wire')].map(p=>[p.parentElement.dataset.wireId,p.getAttribute('d')])})"""
LABELS = """()=>[...workspace.querySelectorAll('.connection-label')].map(t=>[t.parentElement.dataset.wireId,+t.getAttribute('x'),+t.getAttribute('y')])"""
COLLISIONS = """ids=>{
 const overlap=(a,b)=>a.left<b.right-.1&&a.right>b.left+.1&&a.top<b.bottom-.1&&a.bottom>b.top+.1;
 const bad=[];
 for(const id of ids){
  const label=workspace.querySelector(`.wire-group[data-wire-id="${id}"] .connection-label`);
  if(!label){bad.push([id,'missing']);continue}
  const r=label.getBoundingClientRect();
  for(const el of workspace.querySelectorAll('.node:not(.is-container)>.body,.component-label,.outside-label,.internal-text,.connection-label')){
   if(el!==label&&overlap(r,el.getBoundingClientRect()))bad.push([id,el.textContent||el.parentElement.dataset.id]);
  }
  for(const path of workspace.querySelectorAll('.wire')){
   if(path.parentElement===label.parentElement)continue;
   const m=path.getScreenCTM(),length=path.getTotalLength(),step=1/Math.hypot(m.a,m.b);
   for(let at=0;at<=length;at+=step){
    const q=path.getPointAtLength(at).matrixTransform(m);
    if(q.x>r.left&&q.x<r.right&&q.y>r.top&&q.y<r.bottom){bad.push([id,'wire',path.parentElement.dataset.wireId]);break}
   }
  }
 }
 return bad;
}"""


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs())
        for name, ids in [('02-service-circuit.sov', ['w10', 'w13']), ('03-collaboration.sov', ['w11'])]:
            for theme in ('light', 'dark'):
                page = browser.new_page(viewport={'width': 1440, 'height': 900})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('dialog', lambda dialog: dialog.accept())
                page.goto((ROOT / 'index.html').as_uri())
                page.locator('#fileOpenInput').set_input_files(str(FIXTURES / name))
                page.wait_for_function('wires.length>8')
                page.evaluate('(theme)=>{SovSchematicAPI.view.setAppearance(theme);fitDiagram()}', theme)
                page.wait_for_timeout(100)
                before = page.evaluate(STATE)
                assert not page.evaluate(COLLISIONS, ids), (name, theme, page.evaluate(COLLISIONS, ids))
                labels = page.evaluate(LABELS)
                for _ in range(3):
                    page.evaluate('render()')
                    assert page.evaluate(STATE) == before, (name, 'render altered model/routes')
                    actual = page.evaluate(LABELS)
                    assert all(a[0] == b[0] and abs(a[1]-b[1]) < .001 and abs(a[2]-b[2]) < .001 for a, b in zip(labels, actual)), (name, 'nondeterministic')
                # Calling the placement seam directly cannot change route DOM or model.
                page.evaluate('placeWireLabels()')
                assert page.evaluate(STATE) == before
                assert page.evaluate('''()=>{
                  const exported=new DOMParser().parseFromString(snapshotSvg(),'image/svg+xml');
                  const bounds=diagramBounds(),matrix=workspace.getScreenCTM().inverse();
                  return [...workspace.querySelectorAll('.connection-label')].every(label=>{
                    const id=label.parentElement.dataset.wireId,copy=exported.querySelector(`.wire-group[data-wire-id="${id}"] .connection-label`);
                    const r=label.getBoundingClientRect(),a=new DOMPoint(r.left,r.top).matrixTransform(matrix),b=new DOMPoint(r.right,r.bottom).matrixTransform(matrix);
                    return copy&&copy.getAttribute('x')===label.getAttribute('x')&&copy.getAttribute('y')===label.getAttribute('y')&&a.x>=bounds.l-.1&&a.y>=bounds.t-.1&&b.x<=bounds.r+.1&&b.y<=bounds.b+.1;
                  });
                }'''), (name, 'SVG parity/bounds')
                # Resize, zoom and pan all remeasure without rerouting. Dense views
                # may exhaust the finite candidates; that fallback must stay finite.
                page.set_viewport_size({'width': 768, 'height': 900})
                page.wait_for_timeout(100)
                page.evaluate('camera.w*=1.4;camera.h*=1.4;camera.x+=37;camera.y-=21;applyCamera()')
                assert page.evaluate(STATE)['routes'] == before['routes']
                assert page.evaluate(STATE)['model']['components'] == before['model']['components']
                assert page.evaluate(STATE)['model']['wires'] == before['model']['wires']
                assert page.evaluate('''()=>[...workspace.querySelectorAll('.connection-label')].every(t=>{
                  const x=+t.getAttribute('x'),y=+t.getAttribute('y');return Number.isFinite(x)&&Number.isFinite(y)&&Math.abs(x)<10000&&Math.abs(y)<10000;
                })''')
                # A deliberately occupied candidate field exercises bounded fallback:
                # use a projection-only obstacle; no document entity is created.
                fallback = page.evaluate('''()=>{
                  const label=workspace.querySelector('.connection-label'),position=[label.getAttribute('x'),label.getAttribute('y')];
                  const obstacle=document.createElementNS('http://www.w3.org/2000/svg','text');
                  obstacle.setAttribute('class','outside-label');obstacle.getBoundingClientRect=()=>({left:-1e6,right:1e6,top:-1e6,bottom:1e6});nodesG.appendChild(obstacle);
                  placeWireLabels();obstacle.remove();return position.every((v,i)=>v===label.getAttribute(i?'y':'x'));
                }''')
                assert fallback, (name, 'fallback moved existing label')
                assert not errors, errors
                page.close()
        browser.close()
    print('wire label clearance QA PASS: original labels, deterministic projection, routes, resize/zoom/pan, fallback')


if __name__ == '__main__':
    main()
