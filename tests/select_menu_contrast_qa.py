from pathlib import Path
import json
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
DOC=json.loads((ROOT/'examples/02-duplex-buffer.sov').read_text(encoding='utf-8'))


def parse(color):
    inner=color[color.index('(')+1:color.index(')')].replace('/',',').replace(' ',',')
    parts=[p for p in inner.split(',') if p]
    return [float(p) for p in parts[:3]]


def luminance(color):
    chans=[]
    for v in parse(color):
        v/=255
        chans.append(v/12.92 if v<=0.03928 else ((v+0.055)/1.055)**2.4)
    return 0.2126*chans[0]+0.7152*chans[1]+0.0722*chans[2]


def contrast(a,b):
    la,lb=luminance(a),luminance(b)
    hi,lo=max(la,lb),min(la,lb)
    return (hi+0.05)/(lo+0.05)


COLLECT='''()=>{
  const out=[];
  for(const s of document.querySelectorAll('select')){
    const r=s.getBoundingClientRect();
    const cs=getComputedStyle(s);
    if(!r.width||!r.height||cs.visibility==='hidden'||cs.display==='none')continue;
    const o=s.querySelector('option');
    if(!o)continue;
    const oc=getComputedStyle(o);
    out.push({id:s.id||s.className,bg:oc.backgroundColor,color:oc.color,
      appearance:document.documentElement.getAttribute('data-appearance')});
  }
  return out;
}'''

results={}; errors=[]

with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page(viewport={'width':1280,'height':820})
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.set_content(HTML,wait_until='load')
    page.wait_for_timeout(350)
    page.evaluate('(doc)=>window.SovSchematicAPI.document.replace(doc)',DOC)
    page.evaluate('fitDiagram()')
    for mode in ('dark','light'):
        page.evaluate('(m)=>window.SovSchematicAPI.view.setAppearance(m)',mode)
        page.evaluate('selectNode("c1",{focus:false})')
        page.wait_for_timeout(350)
        results[mode]=page.evaluate(COLLECT)
    browser.close()

assert not errors, errors
for mode,rows in results.items():
    assert rows, f'no visible select in {mode}'
    for row in rows:
        ratio=contrast(row['color'],row['bg'])
        assert ratio>=4.5, (mode,row,ratio)
        if mode!='light':
            assert row['bg']!='rgb(255, 255, 255)', (mode,row)
print('select_menu_contrast_qa ok')
