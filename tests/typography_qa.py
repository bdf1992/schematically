"""Typography QA (NOTATION-MODEL.md §4): text as authored, in its role.

- A card without a label shows its glyph's title in sentence case ("Act", never "ACT"); the
  palette names its symbols the same way; nothing on the canvas is forced into capitals.
- A subtitle sits under its title.
- Body text is a small, safe Markdown: bold, italic, code, line breaks, list items; anything
  else is shown as typed, never read as markup.
- Narration is a subtitle track: shown one line at a time, following the clock, with its focus
  lit and the rest dimmed; a picture can carry a line; the document keeps the track.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

CHECK = r"""()=>{
  const A=window.SovSchematicAPI,out={};
  out.palette=[...document.querySelectorAll('.symbol-card b')].map(b=>b.textContent).slice(0,12);
  A.document.replace({schema:SovSchematicData.DOCUMENT_SCHEMA,id:'t',components:[
    {id:'plain',symbolId:'act',x:120,y:120},
    {id:'sub',symbolId:'hold',x:360,y:120,config:{label:'Ledger',subtitle:'append only',presentation:{size:{w:140,h:110}}}},
    {id:'md',symbolId:'blank',x:620,y:140,config:{label:'Notes',presentation:{size:{w:220,h:140},text:'**Bold** and *soft* `code`\n- first\n<b>not markup</b>'}}}],
    wires:[],narration:[{at:0,say:'Start here.',focus:['plain']},{at:500,say:'Then the ledger.',focus:['sub']}]});
  const q=(id,sel)=>document.querySelector(`.node[data-id="${id}"] ${sel}`);
  out.caption=q('plain','.component-label')?.textContent;
  out.upper=[...workspace.querySelectorAll('text')].filter(t=>getComputedStyle(t).textTransform==='uppercase').length;
  const title=q('sub','.component-label'),sub=q('sub','.component-subtitle');
  out.sub={text:sub?.textContent,below:sub&&title?+sub.getAttribute('y')>+title.getAttribute('y'):null};
  const body=q('md','.internal-text');
  out.md={strong:body?.querySelector('.md-strong')?.textContent,em:body?.querySelector('.md-em')?.textContent,code:body?.querySelector('.md-code')?.textContent,
    lines:body?.querySelectorAll(':scope > tspan').length,bullet:[...(body?.querySelectorAll(':scope > tspan')||[])].map(t=>t.textContent)[1],
    literal:[...(body?.querySelectorAll(':scope > tspan')||[])].map(t=>t.textContent)[2],elements:body?body.querySelectorAll('b').length:null};
  out.lines=A.view.narration().lines.map(l=>l.say);
  const shown=A.view.narrate(1);
  out.bar={text:document.getElementById('narrationBar').textContent,hidden:document.getElementById('narrationBar').hidden,
    dimmed:[...workspace.querySelectorAll('.node.narration-dim')].map(g=>g.dataset.id).sort(),lit:shown.line.focus};
  out.picture=A.render.svg({narration:0});
  A.view.narrate(null);
  out.cleared=document.getElementById('narrationBar').hidden;
  const doc=A.file.document();out.kept={narration:(doc.narration||[]).length,subtitle:doc.components.find(c=>c.id==='sub').config.subtitle};
  return out;
}"""
with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    errors: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
    page.wait_for_timeout(250)
    r = page.evaluate(CHECK)
    # The clock drives the track: after 600 ms the second line is in force.
    page.evaluate("()=>{simStart();simAdvance(600)}")
    clocked = page.evaluate("()=>({text:document.getElementById('narrationBar').textContent,index:SovSchematicAPI.view.narration().index})")
    page.evaluate("()=>simReset()")
    browser.close()
assert not errors, errors
assert all(n and not n.isupper() for n in r['palette']), r['palette']
assert 'Act' in r['palette'] and 'Hold' in r['palette'], r['palette']
assert r['caption'] == 'Act', r['caption']
assert r['upper'] == 0, 'nothing on the canvas is forced into capitals'
assert r['sub'] == {'text': 'append only', 'below': True}, r['sub']
md = r['md']
assert (md['strong'], md['em'], md['code']) == ('Bold', 'soft', 'code'), md
assert md['lines'] == 3 and md['bullet'] == '• first' and md['literal'] == '<b>not markup</b>' and md['elements'] == 0, md
assert r['lines'] == ['Start here.', 'Then the ledger.'], r['lines']
assert r['bar']['text'] == 'Then the ledger.' and r['bar']['hidden'] is False, r['bar']
assert r['bar']['dimmed'] == ['md', 'plain'] and r['bar']['lit'] == ['sub'], r['bar']
assert 'Start here.' in r['picture'] and 'picture-narration' in r['picture'], 'a picture carries its narration line'
assert r['cleared'] is True
assert r['kept'] == {'narration': 2, 'subtitle': 'append only'}, r['kept']
assert clocked == {'text': 'Then the ledger.', 'index': 1}, clocked
print('PASS typography QA')
