"""Contrast QA: the colour core measures what the standards say, and the canvas audit sees what it claims to.

1. src/09-colour-core.js in Node, against reference values: WCAG 2.2 contrast, large-text
   floors, colour-vision simulation and OKLab distance.
2. The palette as realised on screen: the default palette holds every theme's floor and stays
   colour-blind distinct in light and dark; a hue family is reported as not distinct.
3. Planted defects on the rendered canvas: a faint label, a faint terminal mark and a faint
   gradient wire are each found, attributed to their owner, and cost layout score.
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

CORE = r"""
const C=require('./src/09-colour-core.js');
const out={};
out.bw=C.contrast('#000000','#FFFFFF');
out.grey=C.contrast('#777777','#FFFFFF');             // 4.48:1, the classic just-fails grey
out.greyOk=C.contrast('#767676','#FFFFFF');           // 4.54:1, the darkest passing grey
out.same=C.contrast('#3B3B3B','#3B3B3B');
out.large=[C.textFloor(24,400),C.textFloor(19,700),C.textFloor(19,400),C.textFloor(12,700)];
out.over=C.hex(C.over('#000000','#FFFFFF',.5));
out.parse=[C.parse('rgb(10, 20, 30)'),C.parse('rgba(10,20,30,0.5)'),C.parse('#abc'),C.parse('none')];
// Red and green are far apart for normal vision and collapse for a deuteranope.
out.rg={normal:C.distance('#C8553D','#6D9A3C','normal'),deutan:C.distance('#C8553D','#6D9A3C','deutan')};
// Okabe-Ito's blue and vermillion stay apart under every simulation.
out.ov=C.VISIONS.map(v=>C.distance('#0072B2','#D55E00',v));
out.deutanGrey=C.simulateHex('#808080','deutan');
out.audit=C.auditPalette(['#C8553D','#6D9A3C','#507CCB'],{background:'#FFFFFF'});
console.log(JSON.stringify(out));
"""
core = json.loads(subprocess.run(['node', '-e', CORE], cwd=ROOT, capture_output=True, text=True, check=True).stdout)
assert abs(core['bw'] - 21) < 1e-9, core['bw']
assert 4.47 < core['grey'] < 4.5, core['grey']
assert 4.5 <= core['greyOk'] < 4.6, core['greyOk']
assert core['same'] == 1
assert core['large'] == [3, 3, 4.5, 4.5], core['large']
assert core['over'] in ('#7f7f7f', '#808080'), core['over']
assert core['parse'][0] == {'r': 10, 'g': 20, 'b': 30, 'a': 1} and core['parse'][1]['a'] == .5 and core['parse'][2]['r'] == 0xAA and core['parse'][3] is None, core['parse']
assert core['rg']['normal'] > .15 and core['rg']['deutan'] < .05, core['rg']
assert min(core['ov']) > .1, core['ov']
assert core['deutanGrey'] in ('#808080', '#7f7f7f', '#818181'), core['deutanGrey']  # a neutral stays neutral
kinds = {f['kind'] for f in core['audit']['failures']}
assert 'distinct' in kinds and core['audit']['closest']['deutan']['pair'] == [0, 1], core['audit']

PAGE = r"""()=>{
  const A=window.SovSchematicAPI,out={palettes:[]};
  for(const appearance of ['light','dark']){A.view.setAppearance(appearance);
    for(const theme of ['pastel','subtle','reading'])for(const palette of ['okabe-ito','spectrum']){A.view.setColour({theme,palette});out.palettes.push(A.view.paletteAudit())}}
  A.view.setAppearance('light');A.view.setColour({theme:'pastel',palette:'okabe-ito'});
  out.default=A.view.colour();
  const load=()=>{A.document.replace({schema:SovSchematicData.DOCUMENT_SCHEMA,id:'planted',components:[{id:'a',symbolId:'act',x:100,y:200,config:{label:'Source'}},{id:'b',symbolId:'act',x:400,y:200,config:{label:'Sink'}}],wires:[{id:'w',a:'a',aSide:'out',b:'b',bSide:'in'}]});fitDiagram()};
  const plant=css=>{let s=document.getElementById('planted-style');if(!s){s=document.createElement('style');s.id='planted-style';document.head.appendChild(s)}s.textContent=css;load();return {contrast:A.layout.contrast({static:true}),metrics:A.layout.metrics({static:true})}};
  out.clean=plant('');
  out.label=plant('.component-label{fill:#DDDCD6 !important}');
  out.mark=plant('.terminal-mark.out{fill:#F0E6DA !important}');
  out.gradient=plant('stop{stop-color:#E6E4DE !important}');
  out.halo=plant('.component-label{fill:#DDDCD6 !important;stroke:#111111 !important;stroke-width:3px !important}');
  plant('');
  return out;
}"""
with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)
    r = page.evaluate(PAGE)
    browser.close()
assert not errors, errors

assert r['default']['palette'] == 'okabe-ito', r['default']
for a in r['palettes']:
    assert not [f for f in a['failures'] if f['kind'] == 'contrast'], (a['appearance'], a['theme'], a['palette'], a['failures'])
    if a['palette'] == 'okabe-ito':
        assert a['ok'] and a['minDistance'] >= .05, (a['appearance'], a['theme'], a['closest'])
    else:
        assert a['minDistance'] < .05, ('spectrum is a hue family; if it became distinct, update the audit', a['closest'])

clean = r['clean']
assert clean['contrast']['ok'] and clean['contrast']['checked'] >= 8, clean['contrast']
assert 'text-contrast' not in clean['metrics']['counts'] and 'mark-contrast' not in clean['metrics']['counts'], clean['metrics']['counts']

label = r['label']
texts = [f for f in label['contrast']['findings'] if f['kind'] == 'text-contrast']
assert {tuple(f['ids']) for f in texts} >= {('a',), ('b',)}, texts
assert all(f['need'] == 4.5 and f['ratio'] < 1.5 for f in texts), texts
assert label['metrics']['score'] < clean['metrics']['score'], (label['metrics']['score'], clean['metrics']['score'])

mark = r['mark']
marks = [f for f in mark['contrast']['findings'] if f['kind'] == 'mark-contrast']
assert marks and all(f['need'] == 3 for f in marks) and ('a',) in {tuple(f['ids']) for f in marks}, mark['contrast']

grad = r['gradient']
wires = [f for f in grad['contrast']['findings'] if f['kind'] == 'mark-contrast' and f['ids'] == ['w']]
assert wires, ('a faint gradient wire must be measured through its stops', grad['contrast'])

# A dark halo behind light text is what the reader sees the text against.
assert not [f for f in r['halo']['contrast']['findings'] if f['kind'] == 'text-contrast'], r['halo']['contrast']
print('CONTRAST QA PASS', {'checked': clean['contrast']['checked'], 'palettes': len(r['palettes'])})
