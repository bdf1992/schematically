"""Wave board: one HTML file where the real editor plays the same run in four tiles, one per waveStyle.

  python scripts/wave_board.py [--out PATH]     (default _site/wave-board.html, which git ignores)

The file is self-contained: the built index.html once, examples/10-clocked-signals.sov and
tests/fixtures/mixed-waves-12s.sov. The page makes four iframes in a two by two grid, each an
srcdoc copy of index.html with a boot script added before its closing body tag, captioned with its
waveStyle value (off, string, dots, lanes), and one row of controls: play or pause, reset, speed,
document, appearance.

The page is the only clock. While playing, each animation frame posts one advance (elapsed ms
times speed) to all four frames; each frame calls SovSchematicAPI.clock.advance and posts back its
style, run time and count of #waveLayer marks, which the page writes to data-style, data-time and
data-marks on the tile. data-ready on the body is the number of frames that have opened the
document. The message listener lives in the boot script, in the board file only: the editor source
has no URL parameter, message listener or document loader for this.

From its boot script on, a tile writes nothing to browser storage (the script turns its frame's
Storage writes off), so opening a document or setting the appearance in a tile never replaces the
editor's recovery snapshot or its saved appearance.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLES = ['off', 'string', 'dots', 'lanes']
# Each document with its warm-up: example 10 raises the Enable lever at 500 ms and runs to 8 s
# (8 x the 1 s clock, 2 x the 4 s sine); mixed waves runs to 12 s, which every source's period divides.
DOCS = [
    ('example-10', 'example 10', ROOT / 'examples' / '10-clocked-signals.sov',
     [{'advance': 500}, {'toggle': 'enable'}, {'until': 8000}]),
    ('mixed-waves', 'mixed waves', ROOT / 'tests' / 'fixtures' / 'mixed-waves-12s.sov',
     [{'until': 12000}]),
]

# The CSS control/sketchbooks/ep-root-20261002/wave-loops/capture.py uses: the editor's toolbar,
# palette, panels and status are hidden and the canvas fills the frame. The Send buttons (a gesture,
# not state) and the +/- edge flashes (their removal runs on wall time) are hidden as there.
CHROMELESS = """
body > .app{display:block!important}
.app > *:not(main.workspace-wrap){display:none!important}
main.workspace-wrap{position:fixed!important;inset:0!important;margin:0!important;padding:0!important;border:0!important;width:100vw!important;height:100vh!important}
main.workspace-wrap > *:not(#workspace){display:none!important}
#workspace{position:absolute!important;inset:0!important;width:100vw!important;height:100vh!important;border:0!important;border-radius:0!important;box-shadow:none!important}
.sim-send{display:none!important}
.sim-edge{display:none!important}
"""

# Runs inside each tile, after the editor's own scripts. __STYLE__ is replaced per tile by the page.
BOOT = r"""
(function(){
  const STYLE=__STYLE__,DOCS=__DOCS__,CSS=__CSS__,A=window.SovSchematicAPI;
  // A tile is a viewer: it writes nothing to browser storage.
  try{Storage.prototype.setItem=function(){};Storage.prototype.removeItem=function(){}}catch(_){ }
  const sheet=document.createElement('style');sheet.textContent=CSS;document.head.appendChild(sheet);
  let current=null,opened=false,turn=0;
  const time=()=>{const s=A.clock.state();return typeof s.time==='number'?s.time:0};
  const report=()=>parent.postMessage({board:'wave',style:STYLE,time:time(),marks:document.querySelectorAll('#waveLayer > *').length,opened,turn},'*');
  function warm(){
    A.clock.reset();
    for(const step of DOCS[current].warm){
      if(step.advance!=null)A.clock.advance(step.advance);
      else if(step.toggle)A.clock.toggle(step.toggle);
      else if(step.until!=null)A.clock.advance(step.until-time());
    }
  }
  function open(name,appearance){
    current=name;opened=false;
    if(appearance)A.view.setAppearance(appearance);
    A.clock.reset();A.file.open(DOCS[name].text,DOCS[name].file);
    fitDiagram();render();
    A.view.setWaveStyle(STYLE);
    warm();opened=true;
  }
  addEventListener('message',e=>{
    const m=e.data;if(e.source!==parent||!m||m.board!=='wave')return;
    if(m.cmd==='open'){turn=m.turn;open(m.name,m.appearance)}
    else if(!opened)return;
    else if(m.cmd==='advance')A.clock.advance(m.ms);
    else if(m.cmd==='reset')warm();
    else if(m.cmd==='appearance'){A.view.setAppearance(m.mode);render()}
    report();
  });
  addEventListener('resize',()=>{if(opened)fitDiagram()});
  const hello=()=>requestAnimationFrame(()=>parent.postMessage({board:'wave',style:STYLE,hello:true},'*'));
  if(document.readyState==='complete')hello();else addEventListener('load',hello);
})();
"""

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wave styles</title>
<style>
:root{color-scheme:dark;--bg:#0E1012;--panel:#17191B;--line:#2B2E31;--ink:#E7E8E3;--muted:#A8AAA4}
:root[data-appearance="light"]{color-scheme:light;--bg:#ECEBE6;--panel:#F6F5F0;--line:#D8D8D1;--ink:#171715;--muted:#6C6C65}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.3 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;display:grid;grid-template-rows:auto 1fr;gap:8px;padding:8px}
.controls{display:flex;align-items:center;gap:8px}
.controls button,.controls select{font:inherit;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:5px 10px;min-width:38px}
.controls button:hover,.controls select:hover{border-color:var(--muted)}
.tiles{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:8px;min-height:0}
.tile{position:relative;margin:0;min-height:0;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--panel)}
.tile iframe{display:block;width:100%;height:100%;border:0}
.tile figcaption{position:absolute;left:10px;bottom:8px;font:12px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--muted);pointer-events:none}
</style>
</head>
<body data-ready="0">
<div class="controls">
  <button id="play" type="button" aria-label="Play or pause" aria-pressed="false">&#9654;</button>
  <button id="reset" type="button" aria-label="Reset">&#8634;</button>
  <select id="speed" aria-label="Speed"><option value="0.25">0.25&times;</option><option value="1" selected>1&times;</option><option value="4">4&times;</option></select>
  <select id="doc" aria-label="Document">__DOC_OPTIONS__</select>
  <select id="appearance" aria-label="Appearance"><option value="dark" selected>dark</option><option value="light">light</option></select>
</div>
<div class="tiles" id="tiles"></div>
<script type="application/json" id="editor-html">__EDITOR__</script>
<script type="application/json" id="boot-script">__BOOT__</script>
<script>
(function(){
  const STYLES=__STYLES__;
  const editor=JSON.parse(document.getElementById('editor-html').textContent),boot=JSON.parse(document.getElementById('boot-script').textContent);
  const cut=editor.lastIndexOf('</body>');
  // turn counts document opens: a tile's report counts toward data-ready only for the open in force.
  const state={playing:false,speed:1,doc:document.getElementById('doc').value,appearance:'dark',last:0,ready:new Set(),turn:1};
  const open=to=>to.postMessage({board:'wave',cmd:'open',name:state.doc,appearance:state.appearance,turn:state.turn},'*');
  const tiles=STYLES.map(style=>{
    const el=document.createElement('figure');el.className='tile';el.dataset.style=style;el.dataset.time='0';el.dataset.marks='0';
    const frame=document.createElement('iframe');frame.title=style;
    frame.srcdoc=editor.slice(0,cut)+'<script>'+boot.replace('__STYLE__',JSON.stringify(style))+'</'+'script>'+editor.slice(cut);
    const caption=document.createElement('figcaption');caption.textContent=style;
    el.append(frame,caption);document.getElementById('tiles').appendChild(el);
    return {style,el,frame};
  });
  const post=message=>{for(const t of tiles)t.frame.contentWindow?.postMessage({board:'wave',...message},'*')};
  const ready=()=>{document.body.dataset.ready=String(state.ready.size)};
  addEventListener('message',e=>{
    const t=tiles.find(x=>x.frame.contentWindow===e.source),m=e.data;if(!t||!m||m.board!=='wave')return;
    if(m.hello){open(t.frame.contentWindow);return}
    if(m.turn!==state.turn)return;
    t.el.dataset.style=m.style;t.el.dataset.time=String(m.time);t.el.dataset.marks=String(m.marks);
    if(m.opened)state.ready.add(t.style);ready();
  });
  // The page is the only clock: one advance per animation frame, the same for all four tiles.
  function tick(now){
    if(!state.playing)return;
    const dt=Math.min(100,Math.max(0,now-(state.last||now)));state.last=now;
    if(dt>0)post({cmd:'advance',ms:dt*state.speed});
    requestAnimationFrame(tick);
  }
  const play=document.getElementById('play');
  play.addEventListener('click',()=>{
    state.playing=!state.playing;state.last=0;play.innerHTML=state.playing?'&#10074;&#10074;':'&#9654;';play.setAttribute('aria-pressed',String(state.playing));
    if(state.playing)requestAnimationFrame(tick);
  });
  document.getElementById('reset').addEventListener('click',()=>post({cmd:'reset'}));
  document.getElementById('speed').addEventListener('change',e=>{state.speed=Number(e.target.value)||1});
  document.getElementById('doc').addEventListener('change',e=>{state.doc=e.target.value;state.turn++;state.ready.clear();ready();for(const t of tiles)if(t.frame.contentWindow)open(t.frame.contentWindow)});
  document.getElementById('appearance').addEventListener('change',e=>{state.appearance=e.target.value;document.documentElement.dataset.appearance=state.appearance;post({cmd:'appearance',mode:state.appearance})});
})();
</script>
</body>
</html>
"""


def embed(value) -> str:
    """JSON for a script element: no '<' survives, so nothing inside can close or open a tag."""
    return json.dumps(value, ensure_ascii=False).replace('<', '\\u003c')


def build() -> str:
    editor = (ROOT / 'index.html').read_text(encoding='utf-8')
    assert editor.count('</body>') >= 1, 'index.html has no closing body tag'
    docs = {key: {'file': path.name, 'text': path.read_text(encoding='utf-8'), 'warm': warm} for key, _, path, warm in DOCS}
    boot = BOOT.replace('__DOCS__', embed(docs)).replace('__CSS__', embed(CHROMELESS))
    options = ''.join(f'<option value="{key}"{" selected" if i == 0 else ""}>{label}</option>' for i, (key, label, _, _) in enumerate(DOCS))
    return (PAGE.replace('__DOC_OPTIONS__', options).replace('__STYLES__', json.dumps(STYLES))
            .replace('__BOOT__', embed(boot)).replace('__EDITOR__', embed(editor)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', default=str(ROOT / '_site' / 'wave-board.html'))
    out = Path(parser.parse_args().out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(), encoding='utf-8', newline='\n')
    print(out)


if __name__ == '__main__':
    main()
