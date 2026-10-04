"""Wave view QA (src/68-wave-view.js, styles/app.css --wave-ink, scripts/wave_board.py).

view.waveStyle is the view's own setting with four values: off, string, dots, lanes. While a run is
live it draws the run's spectra along the wires in #waveLayer, under #wires, and nothing else in
the workspace changes. This checks, printing counts:

  (a) example 10, lever raised at 500 ms, run at 8000 ms: off leaves the layer empty; string gives one
      path.wave-string for each of w1, w3, w4, w5, w6 and none for w2 (the lever has no period);
      dots gives at least 10 circle.wave-dot on w1 and no path; lanes gives 1 to 3 path.wave-lane on
      w1 and exactly 1 on w4 (a sine holds one harmonic);
  (b) the wires layer's innerHTML is one string under all four values at that time;
  (c) the wave moves and is a pure function of run time: after advance(100) w1's string differs, and
      after a clock reset and the same steps to 8000 ms it is the first reading again;
  (d) w1's string starts and ends on the wire's drawn end points (within 0.01);
  (e) an unknown style is refused with WAVE_STYLE_UNKNOWN and the value stays;
  (f) a workspace carries the setting; one without the key, or with an unknown value, gives off; the
      document, its revision and its fingerprint never carry it;
  (g) the standalone SVG holds no #waveLayer and no wave- class, and is the same text with the
      setting on string as with it off;
  (h) with no run live every value leaves the layer empty;
  (i) scripts/wave_board.py writes one file that, opened by its file URL, readies four tiles (0 marks
      for off, more for the other three) and plays them on one clock: after play, 600 ms and pause the
      four tiles show the same run time, above 8000;
  (j) no page logs an error.

It also prints, per style, the count of marks on example 10 at 8000 ms and on mixed waves at
12000 ms, and the mean milliseconds of one clock.advance(16) over 120 calls on mixed waves.
"""
import json, re, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')
EX10 = ROOT / 'examples' / '10-clocked-signals.sov'
MIXED = ROOT / 'tests' / 'fixtures' / 'mixed-waves-12s.sov'
STYLES = ['off', 'string', 'dots', 'lanes']

errors = []


def new_page(browser):
    page = browser.new_page(viewport={'width': 1500, 'height': 900})
    page.on('pageerror', lambda e: errors.append(f'pageerror: {e}'))
    page.on('console', lambda m: errors.append(f'console: {m.text}') if m.type == 'error' else None)
    return page


def editor(browser):
    page = new_page(browser)
    page.set_content(HTML, wait_until='load'); page.wait_for_timeout(200)
    return page


def open_doc(page, path):
    page.evaluate('([t,n])=>{SovSchematicAPI.clock.reset();SovSchematicAPI.file.open(t,n);fitDiagram()}', [path.read_text(encoding='utf-8'), path.name])
    page.wait_for_timeout(120)


def warm_example10(page):
    """The lever goes up at 500 ms; the run stands at 8000 ms (8 clock periods, 2 sine periods)."""
    return page.evaluate("()=>{const A=SovSchematicAPI;A.clock.reset();A.clock.advance(500);A.clock.toggle('enable');A.clock.advance(7500);return A.clock.state().time}")


MARKS = """(style)=>{
  const set=SovSchematicAPI.view.setWaveStyle(style),layer=document.getElementById('waveLayer'),per={};
  for(const e of layer.children){const k=`${e.tagName.toLowerCase()}.${e.getAttribute('class')}`,w=e.getAttribute('data-wire-id');(per[w]||(per[w]={}))[k]=(per[w][k]||0)+1}
  return {set,value:SovSchematicAPI.view.waveStyle(),marks:layer.children.length,per,unowned:[...layer.children].filter(e=>!e.getAttribute('data-wire-id')).length,
    elsewhere:document.querySelectorAll('[class^="wave-"]').length-layer.querySelectorAll('[class^="wave-"]').length,
    wires:document.getElementById('wires').innerHTML,pointer:getComputedStyle(layer).pointerEvents};
}"""

with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = editor(browser)

    # The default is off.
    assert page.evaluate("()=>SovSchematicAPI.view.waveStyle()") == 'off'
    open_doc(page, EX10)

    # (h) No run live: every value leaves the layer empty.
    idle = {s: page.evaluate(MARKS, s)['marks'] for s in STYLES}
    assert idle == {s: 0 for s in STYLES}, ('(h) no run, no wave', idle)
    page.evaluate("()=>SovSchematicAPI.view.setWaveStyle('off')")

    # (a) Example 10 at 8000 ms.
    revision = page.evaluate("()=>[SovSchematicAPI.file.info().revision,semanticFingerprint(),JSON.stringify(SovSchematicAPI.file.document())]")
    assert warm_example10(page) == 8000
    seen = {s: page.evaluate(MARKS, s) for s in STYLES}
    for s in STYLES:
        assert seen[s]['set'] == {'ok': True, 'waveStyle': s} and seen[s]['value'] == s, seen[s]['set']
        assert seen[s]['unowned'] == 0 and seen[s]['elsewhere'] == 0, ('every mark is a child of waveLayer and names its wire', s)
        assert seen[s]['pointer'] == 'none', 'marks take no pointer events'
    assert seen['off']['marks'] == 0, ('(a) off leaves the layer empty', seen['off']['per'])
    assert seen['string']['per'] == {w: {'path.wave-string': 1} for w in ('w1', 'w3', 'w4', 'w5', 'w6')}, ('(a) string: one path on each varying wire, none on w2', seen['string']['per'])
    assert set(seen['dots']['per']['w1']) == {'circle.wave-dot'} and seen['dots']['per']['w1']['circle.wave-dot'] >= 10, ('(a) dots on w1', seen['dots']['per'].get('w1'))
    assert all(set(kinds) == {'circle.wave-dot'} for kinds in seen['dots']['per'].values()) and 'w2' not in seen['dots']['per'], ('(a) dots draws circles only', seen['dots']['per'])
    assert set(seen['lanes']['per']['w1']) == {'path.wave-lane'} and 1 <= seen['lanes']['per']['w1']['path.wave-lane'] <= 3, ('(a) lanes on w1', seen['lanes']['per'].get('w1'))
    assert seen['lanes']['per']['w4'] == {'path.wave-lane': 1}, ('(a) one lane on the sine wire w4', seen['lanes']['per'].get('w4'))
    assert 'w2' not in seen['lanes']['per'], seen['lanes']['per']
    example10_marks = {s: seen[s]['marks'] for s in STYLES}

    # (b) The wires layer is the same DOM under every value.
    assert len({seen[s]['wires'] for s in STYLES}) == 1 and seen['off']['wires'], '(b) the wires layer differs between wave styles'
    # The layer sits directly before the wires layer (the render's group layer goes before both).
    assert page.evaluate("()=>{const g=document.getElementById('waveLayer');return g.getAttribute('aria-hidden')==='true'&&g.nextElementSibling?.id==='wires'&&g.parentElement.id==='workspace'}"), 'waveLayer sits directly before #wires'

    # The setting is the view's: the document, its revision and its fingerprint do not move.
    after = page.evaluate("()=>[SovSchematicAPI.file.info().revision,semanticFingerprint(),JSON.stringify(SovSchematicAPI.file.document())]")
    assert after == revision and 'waveStyle' not in after[2], 'setWaveStyle wrote to the document'

    # (c) The wave moves with the run and is a pure function of run time.
    READ = "()=>document.querySelector('#waveLayer path.wave-string[data-wire-id=\"w1\"]').getAttribute('d')"
    page.evaluate("()=>SovSchematicAPI.view.setWaveStyle('string')")
    first = page.evaluate(READ)
    # (d) The string starts and ends on the wire's drawn end points.
    ends = page.evaluate("""()=>{
      const i=wires.findIndex(w=>w.id==='w1'),route=drawnRoutePoints.get(i),n=document.querySelector('#waveLayer path.wave-string[data-wire-id="w1"]').getAttribute('d').match(/-?\\d+(\\.\\d+)?/g).map(Number);
      const a=route[0],b=route[route.length-1];
      return {points:n.length/2,start:Math.hypot(n[0]-a.x,n[1]-a.y),end:Math.hypot(n[n.length-2]-b.x,n[n.length-1]-b.y)};
    }""")
    assert ends['points'] > 10 and ends['start'] <= 0.01 and ends['end'] <= 0.01, ('(d) the string is pinned to the wire ends', ends)
    page.evaluate("()=>SovSchematicAPI.clock.advance(100)")
    moved = page.evaluate(READ)
    assert moved != first, '(c) the string did not move in 100 ms'
    assert warm_example10(page) == 8000
    again = page.evaluate(READ)
    assert again == first, '(c) the same run time drew a different string'

    # (e) An unknown style is refused and nothing changes.
    refused = page.evaluate("()=>[SovSchematicAPI.view.setWaveStyle('ribbon'),SovSchematicAPI.view.waveStyle(),document.querySelectorAll('#waveLayer path.wave-string').length]")
    assert refused[0]['ok'] is False and refused[0]['code'] == 'WAVE_STYLE_UNKNOWN' and refused[0]['allowed'] == STYLES and refused[0]['message'], refused[0]
    assert refused[1] == 'string' and refused[2] == 5, ('(e) the value stays', refused[1:])

    # (g) The standalone SVG carries no trace of the wave, taken during the run with string set.
    picture, snapshot = page.evaluate("()=>[SovSchematicAPI.render.svg({}),SovSchematicAPI.file.svg({})]")
    for name, svg in (('render.svg', picture), ('file.svg', snapshot)):
        assert isinstance(svg, str) and svg.startswith('<svg'), name
        assert 'waveLayer' not in svg and 'class="wave-' not in svg and 'wave-string' not in svg, f'(g) {name} carries the wave layer'
    plain = page.evaluate("()=>{SovSchematicAPI.view.setWaveStyle('off');const out=[SovSchematicAPI.render.svg({}),SovSchematicAPI.file.svg({})];SovSchematicAPI.view.setWaveStyle('string');return out}")
    # Every render numbers its wire gradients afresh (wire-gradient-<wire>-<epoch>); the epoch is not the picture.
    steady = lambda svg: re.sub(r'wire-gradient-(\d+)-\d+', r'wire-gradient-\1', svg)
    assert [steady(s) for s in plain] == [steady(picture), steady(snapshot)], '(g) the exported SVG differs between string and off'

    # (f) A workspace carries the setting; a missing or unknown value gives off.
    workspace = page.evaluate("()=>captureWorkspace()")
    assert workspace['view']['waveStyle'] == 'string' and 'waveStyle' not in json.dumps(workspace['document']), '(f) the workspace view holds waveStyle, the document does not'
    fresh = editor(browser)
    assert fresh.evaluate("()=>SovSchematicAPI.view.waveStyle()") == 'off'
    fresh.evaluate("(w)=>{SovSchematicAPI.file.open(w,'wave.sov')}", workspace)
    assert fresh.evaluate("()=>SovSchematicAPI.view.waveStyle()") == 'string', '(f) an applied workspace gives its waveStyle'
    bare = json.loads(json.dumps(workspace)); del bare['view']['waveStyle']
    fresh.evaluate("(w)=>{SovSchematicAPI.file.open(w,'wave.sov')}", bare)
    assert fresh.evaluate("()=>SovSchematicAPI.view.waveStyle()") == 'off', '(f) a workspace without the key gives off'
    fresh.evaluate("(w)=>{SovSchematicAPI.file.open(w,'wave.sov')}", workspace)
    odd = json.loads(json.dumps(workspace)); odd['view']['waveStyle'] = 'ribbon'
    fresh.evaluate("(w)=>{SovSchematicAPI.file.open(w,'wave.sov')}", odd)
    assert fresh.evaluate("()=>SovSchematicAPI.view.waveStyle()") == 'off', '(f) a workspace with an unknown value gives off'
    fresh.close()

    # (h) again, after a run: a reset empties the layer whatever the value.
    page.evaluate("()=>SovSchematicAPI.clock.reset()")
    idle = {s: page.evaluate(MARKS, s)['marks'] for s in STYLES}
    assert idle == {s: 0 for s in STYLES}, ('(h) no run, no wave', idle)

    # Counts and cost on mixed waves at 12000 ms (reported, not judged).
    mixed_marks, advance_ms = {}, {}
    for s in STYLES:
        open_doc(page, MIXED)
        assert page.evaluate("()=>{SovSchematicAPI.clock.advance(12000);return SovSchematicAPI.clock.state().time}") == 12000
        mixed_marks[s] = page.evaluate(MARKS, s)['marks']
        advance_ms[s] = page.evaluate("()=>{const t=performance.now();for(let i=0;i<120;i++)SovSchematicAPI.clock.advance(16);return +((performance.now()-t)/120).toFixed(3)}")
    assert mixed_marks['off'] == 0 and all(mixed_marks[s] > 0 for s in STYLES[1:]), mixed_marks
    page.close()

    # (i) The board: one file, four tiles, one clock.
    with tempfile.TemporaryDirectory(prefix='wave-board-') as tmp:
        out = Path(tmp) / 'wave-board.html'
        made = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'wave_board.py'), '--out', str(out)], cwd=ROOT, capture_output=True, text=True, timeout=120)
        assert made.returncode == 0 and out.exists(), made.stdout + made.stderr
        assert [f.name for f in Path(tmp).iterdir()] == ['wave-board.html'], 'the board is one file'
        board = new_page(browser)
        board.goto(out.as_uri(), wait_until='load')
        board.wait_for_function("()=>document.body.dataset.ready==='4'", timeout=90000)
        TILES = "()=>[...document.querySelectorAll('.tile')].map(t=>({style:t.dataset.style,time:Number(t.dataset.time),marks:Number(t.dataset.marks),caption:t.querySelector('figcaption').textContent,frames:t.querySelectorAll('iframe').length}))"
        tiles = board.evaluate(TILES)
        assert [t['style'] for t in tiles] == STYLES and [t['caption'] for t in tiles] == STYLES and all(t['frames'] == 1 for t in tiles), tiles
        assert tiles[0]['marks'] == 0 and all(t['marks'] > 0 for t in tiles[1:]), ('(i) marks per tile', tiles)
        assert all(t['time'] == 8000 for t in tiles), ('(i) every tile is warmed to 8000 ms', tiles)
        board.click('#play'); board.wait_for_timeout(600); board.click('#play')
        # Replies to the last advance are still on their way: wait until the readings stand still.
        last = None
        for _ in range(40):
            board.wait_for_timeout(100)
            now = board.evaluate(TILES)
            if now == last:
                break
            last = now
        played = board.evaluate(TILES)
        assert len({t['time'] for t in played}) == 1 and played[0]['time'] > 8000, ('(i) four tiles, one clock', played)
        assert played[0]['marks'] == 0 and all(t['marks'] > 0 for t in played[1:]), played
        board_report = {'bytes': out.stat().st_size, 'time': played[0]['time'], 'marks': {t['style']: t['marks'] for t in played}}
        board.close()

    # (j) No page logged an error.
    assert not errors, errors
    browser.close()

print('PASS wave view QA', json.dumps({'example10@8000': example10_marks, 'mixed@12000': mixed_marks, 'advance16_ms_mixed': advance_ms, 'w1_string': ends, 'board': board_report}))
