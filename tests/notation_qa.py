"""Notation QA (NOTATION-MODEL.md): a notation is data, glyph terminals are what wires meet,
tokens decide corners and depth, and a domain notation brings its own shapes and behaviour.

1. src/03-notation-core.js in Node: resolution through `extends`, refusal of an unknown
   notation, a document carrying its own notation, terminal points, concentric radii.
2. The half adder (examples/13-half-adder.sov) in Node: the graph engine runs each gate's
   declared combine through its two real inputs.
3. In the editor: symbols are generated from the notation with pins at the terminals, a gate's
   inputs are two points on their own terminal lines with straight leads, and a nested card is
   lifted above its container.
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

NODE = r"""
const N=require('./src/03-notation-core.js');require('./src/06-attachment-core.js');
const D=require('./src/05-data-core.js'),G=require('./src/07-graph-core.js'),A=require('./src/06-attachment-core.js');
const out={};
out.schematic=N.resolve('schematic').ok;
const logic=N.resolve('logic');out.logic={ok:logic.ok,inherits:!!logic.notation.glyphs.act,gate:!!logic.notation.glyphs.and2,radius:logic.notation.tokens.radius};
out.unknown=N.resolve('nope');
out.unknownValidate=D.validateDocument(D.makeDocument({notation:'nope'})).errors;
// A document can carry its own notation: a new glyph and a token change, extending the default.
const carried={notation:'plant',references:[{id:'n',kind:'notation',data:{id:'plant',extends:'schematic',tokens:{radius:{card:3}},glyphs:{valve:{title:'Valve',draw:[{d:'M30 20L66 44M30 44L66 20'}],terminals:[{id:'in',role:'in',at:[30,32],toward:'left'},{id:'out',role:'out',at:[66,32],toward:'right'}]}}}}]};
const r=N.resolve(carried);out.carried={ok:r.ok,valve:!!r.notation.glyphs.valve,card:r.notation.tokens.radius.card,core:r.notation.tokens.radius.core,act:!!r.notation.glyphs.act};
out.carriedValidate=D.validateDocument(D.makeDocument(carried)).errors;
out.points=A.builtinPointIds({symbolId:'and2',form:{dimension:2},config:{}});
out.standard=A.builtinPointIds({symbolId:'act',form:{dimension:2},config:{}});
const T=N.tokens('schematic'),tot=30;
out.radii=[0,8,22,30].map(i=>N.cornerRadius(T,{total:tot,inset:i,w:300-2*i,h:220-2*i,sectioned:true}));
out.capped=N.cornerRadius(T,{total:30,inset:0,w:60,h:60,sectioned:true});
out.card=N.cornerRadius(T,{w:112,h:84});
out.markup=N.glyphMarkup(logic.notation.glyphs.and2);
const doc=JSON.parse(require('fs').readFileSync('examples/13-half-adder.sov','utf8'));
out.valid=D.validateDocument(D.makeDocument(doc)).errors;
const s=G.createSimulation(doc,{}).sim;out.truth=[];
for(const [a,b] of [[0,0],[0,1],[1,0],[1,1]]){s.set('a',a);s.set('b',b);s.advance(1000);const L=s.levels();out.truth.push([a,b,L.sum.value,L.carry.value])}
out.combine=G.query(doc,'signals').signals.filter(x=>x.id.endsWith('-gate')).map(x=>[x.id,x.mode,x.combine]);
console.log(JSON.stringify(out));
"""
r = json.loads(subprocess.run(['node', '-e', NODE], cwd=ROOT, capture_output=True, text=True, check=True).stdout)
assert r['schematic'] and r['logic']['ok'] and r['logic']['inherits'] and r['logic']['gate'], r['logic']
assert r['unknown']['ok'] is False and r['unknown']['code'] == 'UNKNOWN_NOTATION', r['unknown']
assert any('UNKNOWN_NOTATION' in e for e in r['unknownValidate']), r['unknownValidate']
assert r['carried'] == {'ok': True, 'valve': True, 'card': 3, 'core': 6, 'act': True}, r['carried']
assert r['carriedValidate'] == [], r['carriedValidate']
assert r['points'] == ['a', 'b', 'y'] and r['standard'] == ['left', 'right', 'top'], (r['points'], r['standard'])
# Offset from inside: the core keeps 6 and each line outward adds the bands inside it.
assert r['radii'] == [36, 28, 14, 6], r['radii']
assert r['capped'] == 15 and r['card'] == 10, (r['capped'], r['card'])
assert 'class="glyph-pin" data-terminal="a" d="M30 22L8 22"' in r['markup'] and 'data-terminal="y" d="M70 32L88 32"' in r['markup'], r['markup']
assert r['valid'] == [], r['valid']
assert r['truth'] == [[0, 0, 0, 0], [0, 1, 1, 0], [1, 0, 1, 0], [1, 1, 0, 1]], r['truth']
assert r['combine'] == [['sum-gate', 'derived', 'xor'], ['carry-gate', 'derived', 'and']], r['combine']

PAGE = r"""()=>{
  const A=window.SovSchematicAPI,out={};
  out.symbols=[...document.querySelectorAll('.hidden-symbols symbol')].map(s=>s.id);
  out.actPins=[...document.querySelectorAll('#sym-act .glyph-pin')].map(p=>p.getAttribute('d'));
  out.iconPins=document.querySelectorAll('#sym-authority .glyph-pin').length;
  return out;
}"""
HALF = r"""()=>{
  const n=id=>nodes.find(x=>x.id===id),g=n('carry-gate'),ax=componentGlyphAxis(g);
  const pa=componentPortLocalPosition(g,'a'),pb=componentPortLocalPosition(g,'b'),py=componentPortLocalPosition(g,'y');
  const leads=[...document.querySelectorAll('.node[data-id="carry-gate"] .component-lead')].map(l=>l.getAttribute('d'));
  const pin=t=>ax.y0+SovSchematicNotation.terminal(componentGlyph(g),t).at[1]*ax.scale;
  return {symbols:[...document.querySelectorAll('.hidden-symbols symbol')].map(s=>s.id).filter(x=>/^sym-(and2|xor2)$/.test(x)),
    pa,pb,py,pinA:pin('a'),pinB:pin('b'),leads,points:componentAttachmentPoints(g).map(p=>p.id),
    marks:document.querySelectorAll('.node[data-id="carry-gate"] .terminal-mark').length};
}"""
NEST = r"""()=>{
  const A=window.SovSchematicAPI;
  A.document.replace({schema:SovSchematicData.DOCUMENT_SCHEMA,id:'nest',components:[
    {id:'box',symbolId:'plane',x:400,y:300,form:{dimension:2,regions:{interior:{state:'open'}}},config:{attachmentDefaults:'none',presentation:{size:{w:400,h:260}}}},
    {id:'kid',symbolId:'act',x:400,y:330,canvasId:'canvas:component:box',parentId:'box'}],wires:[]});
  const f=id=>document.querySelector(`.node[data-id="${id}"] > .body`);
  return {box:f('box').dataset.elevation,kid:f('kid').dataset.elevation,boxShadow:f('box').style.filter,kidShadow:f('kid').style.filter,depthRects:document.querySelectorAll('.component-body-depth').length};
}"""
with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)
    base = page.evaluate(PAGE)
    half_text = (ROOT / 'examples' / '13-half-adder.sov').read_text(encoding='utf-8')
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [half_text, '13-half-adder.sov'])
    page.wait_for_timeout(200)
    half = page.evaluate(HALF)
    nest = page.evaluate(NEST)
    browser.close()
assert not errors, errors
assert {'sym-act', 'sym-gate', 'sym-clock', 'sym-clock-sine'} <= set(base['symbols']), base['symbols']
assert 'and2' not in ' '.join(base['symbols']), 'a domain glyph appears only when the document uses that notation'
assert sorted(base['actPins']) == ['M28 32L8 32', 'M68 32L88 32'], base['actPins']
assert base['iconPins'] == 0, 'an icon has no terminals'
assert set(half['symbols']) == {'sym-and2', 'sym-xor2'}, half['symbols']
assert half['points'] == ['a', 'b', 'y'], half['points']
assert abs(half['pa']['y'] - half['pinA']) < .01 and abs(half['pb']['y'] - half['pinB']) < .01 and half['pa']['y'] < half['pb']['y'] - 10, half
assert len(half['leads']) == 3 and all('V' not in d for d in half['leads']), ('every lead straight', half['leads'])
assert half['marks'] == 3, half['marks']
assert nest['box'] == '1' and nest['kid'] == '2' and nest['depthRects'] == 0, nest
assert nest['boxShadow'] != nest['kidShadow'], nest
print('PASS notation QA', {'symbols': len(base['symbols']), 'truth': 'half adder'})
