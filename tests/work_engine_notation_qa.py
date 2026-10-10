"""Work Engine notation QA (NOTATION-MODEL.md, "Domain notation: work-engine").

A domain notation is data a document carries in references[] (kind notation). This checks the
one the Work Engine gap map is drawn in:

1. In Node, over the real src files: data/work-engine.notation.json parses; the example carries
   it unchanged; it resolves through `schematic`; it declares exactly the six we- glyphs, each
   titled, explained, in a family, drawn, with an in and an out terminal, and drawn unlike any
   built-in glyph; its statuses are exists, partial, missing, proposed in that order; its four
   document concerns are the built-in ids in the built-in order with the Work Engine questions;
   its component concerns are meaning, authority, evidence, owner and backing, each asked of its
   symbols; every document that carries the notation (CARRIERS) carries the file's content.
2. scripts/validate_sov.mjs accepts the example.
3. In the editor: the example opens with no page error, each glyph becomes a symbol, the legend
   titles each glyph and names the three colour categories, and a picture carries every label.
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

EXAMPLE = 'examples/work-engine/notation.sov'
GLYPHS = {'we-record': 'Record', 'we-surface': 'Surface', 'we-migration': 'Migration',
          'we-port': 'Port', 'we-refactor': 'Refactor', 'we-specification': 'Specification'}
LABELS = ['Case', 'Web booth', 'Continuity records move to SQLite', 'Web booth feeds Recording',
          'Split the session guard', 'Status field for cards']
# Every document on the tree that carries the notation in references.
CARRIERS = [EXAMPLE, 'examples/work-engine/status.sov', 'docs/workengine/board-sample.sov', 'docs/workengine/map.sov']
# The built-in document concerns, asked in Work Engine words: id, title, question.
DOCUMENT_CONCERNS = [
    ['what', 'What it shows', 'Which part of the work engine does this map show?'],
    ['why', 'What it is for', 'What would someone build or settle from this map?'],
    ['alternatives', 'Other readings', 'What else describes the same ground, and why read this map?'],
    ['smaller', 'Smallest slice', 'What is the smallest slice of this map that stands on its own?'],
]
# The card concerns: id, the symbols each is asked of, title, question.
COMPONENT_CONCERNS = [
    ['meaning', ['we-record'], 'Holds', 'What does this record hold?'],
    ['authority', ['we-surface'], 'Authority', 'What does this surface have authority over?'],
    ['evidence', ['we-record', 'we-surface'], 'Evidence', 'What in the kernel shows this status?'],
    ['owner', ['we-record'], 'Owner', 'Which task owns building it?'],
    ['backing', ['we-specification'], 'Backing', 'Which records answer this query?'],
]

NODE = r"""
const fs=require('fs'),assert=require('assert');
const N=require('./src/03-notation-core.js');require('./src/06-attachment-core.js');
const D=require('./src/05-data-core.js');
const out={};
const pack=JSON.parse(fs.readFileSync('data/work-engine.notation.json','utf8'));
const doc=JSON.parse(fs.readFileSync('%EXAMPLE%','utf8'));
const ref=(doc.references||[])[0]||{};
out.ref={id:ref.id,kind:ref.kind,label:ref.label};
try{assert.deepStrictEqual(ref.data,pack);out.identical=true}catch(e){out.identical=false}
const r=N.resolve(doc);out.ok=r.ok;out.code=r.code||null;
const glyphs=r.ok?r.notation.glyphs:{};
out.weIds=Object.keys(glyphs).filter(id=>id.startsWith('we-')).sort();
out.glyphs={};
for(const id of out.weIds){const g=glyphs[id];out.glyphs[id]={title:g.title,meaning:g.meaning,family:g.family,draw:Array.isArray(g.draw)&&g.draw.length>0&&g.draw.every(p=>typeof p.d==='string'&&p.d.length>0),terminals:(g.terminals||[]).map(t=>[t.id,t.role,t.toward])}}
const shape=g=>(g.draw||[]).map(p=>p.d).join('|');
const builtin=new Set(Object.values(N.BUILTIN.schematic.glyphs).map(shape));
out.sameAsBuiltin=out.weIds.filter(id=>builtin.has(shape(glyphs[id])));
out.distinct=new Set(out.weIds.map(id=>shape(glyphs[id]))).size;
out.statuses=(r.ok?r.notation.statuses||[]:[]).map(s=>({id:s.id,title:s.title,meaning:s.meaning,outline:s.outline}));
out.categories=(r.ok?r.notation.categories||[]:[]).map(c=>[c.slot,c.name]);
out.valid=D.validateDocument(D.makeDocument(doc)).errors;
const concerns=applies=>r.ok?N.concernsOf(r.notation,applies):[];
out.concerns={document:concerns('document').map(c=>[c.id,c.title,c.question]),component:concerns('component').map(c=>[c.id,c.symbols,c.title,c.question]),
  wire:concerns('wire').map(c=>c.id),findings:r.ok?N.concernFindings(r.notation):null,builtin:N.concernsOf(N.BUILTIN.schematic,'document').map(c=>c.id)};
out.carried={};
for(const file of %CARRIERS%){
  const refs=(JSON.parse(fs.readFileSync(file,'utf8')).references||[]).filter(x=>x&&x.kind==='notation'&&x.data&&x.data.id==='work-engine');
  let same=refs.length===1;if(same)try{assert.deepStrictEqual(refs[0].data,pack)}catch(e){same=false}
  out.carried[file]=same;
}
console.log(JSON.stringify(out));
""".replace('%EXAMPLE%', EXAMPLE).replace('%CARRIERS%', json.dumps(CARRIERS))
proc = subprocess.run(['node', '-e', NODE], cwd=ROOT, capture_output=True, text=True)
assert proc.returncode == 0, proc.stderr
r = json.loads(proc.stdout)
assert r['ref'] == {'id': 'notation-work-engine', 'kind': 'notation', 'label': 'Work Engine'}, r['ref']
assert r['identical'], 'the example must carry data/work-engine.notation.json unchanged'
assert r['ok'], ('the carried notation must resolve', r['code'])
assert r['weIds'] == sorted(GLYPHS), ('exactly the six we- glyphs', r['weIds'])
for gid, title in GLYPHS.items():
    g = r['glyphs'][gid]
    assert g['title'] == title and g['meaning'] and g['family'] and g['draw'], (gid, g)
    assert ['in', 'in', 'left'] in g['terminals'] and ['out', 'out', 'right'] in g['terminals'], (gid, g['terminals'])
assert r['sameAsBuiltin'] == [] and r['distinct'] == 6, ('each glyph drawn unlike the others', r['sameAsBuiltin'], r['distinct'])
assert [s['id'] for s in r['statuses']] == ['exists', 'partial', 'missing', 'proposed'], r['statuses']
assert all(s['title'] and s['meaning'] and s['outline'] in ('solid', 'dashed') for s in r['statuses']), r['statuses']
assert r['categories'] == [['C1', 'Record'], ['C2', 'Surface'], ['C3', 'Work item']], r['categories']
assert r['valid'] == [], r['valid']
c = r['concerns']
assert c['findings'] == [], ('the notation\'s concerns have findings', c['findings'])
assert c['document'] == DOCUMENT_CONCERNS, ('the document concerns are not the Work Engine questions', c['document'])
assert [x[0] for x in c['document']] == c['builtin'] == ['what', 'why', 'alternatives', 'smaller'], ('the built-in order moved', c['document'], c['builtin'])
assert all(q.endswith('?') and q.count('?') == 1 for _, _, q in c['document']) and all(x[3].endswith('?') and x[3].count('?') == 1 for x in c['component']), ('a question does not end in one question mark', c)
assert c['component'] == COMPONENT_CONCERNS, ('the card concerns or their symbols differ', c['component'])
assert c['wire'] == [], ('the notation declares no wire concerns', c['wire'])
assert r['carried'] == {path: True for path in CARRIERS}, ('a document does not carry data/work-engine.notation.json unchanged', r['carried'])

v = subprocess.run(['node', 'scripts/validate_sov.mjs', EXAMPLE], cwd=ROOT, capture_output=True, text=True)
assert v.returncode == 0, (v.stdout, v.stderr)

PAGE = r"""(ids)=>{
  const A=SovSchematicAPI;
  return {symbols:ids.filter(id=>document.getElementById('sym-'+id)),
    legend:A.view.legend().entries.map(e=>[e.kind,e.label]),
    svg:A.render.svg({})};
}"""
with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)
    text = (ROOT / EXAMPLE).read_text(encoding='utf-8')
    page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [text, 'notation.sov'])
    page.wait_for_timeout(250)
    b = page.evaluate(PAGE, sorted(GLYPHS))
    browser.close()
assert not errors, errors
assert b['symbols'] == sorted(GLYPHS), ('a symbol per glyph', b['symbols'])
glyph_titles = {label for kind, label in b['legend'] if kind == 'glyph'}
colour_names = {label for kind, label in b['legend'] if kind == 'colour'}
assert set(GLYPHS.values()) <= glyph_titles, ('legend titles each glyph', b['legend'])
assert {'Record', 'Surface', 'Work item'} <= colour_names, ('legend names each category', b['legend'])
missing = [label for label in LABELS if label not in b['svg']]
assert not missing, ('the picture carries every card label', missing)
print('PASS work-engine notation QA', {'glyphs': len(GLYPHS), 'statuses': len(r['statuses'])})
