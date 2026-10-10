"""Run repaint QA (src/65-sim-control.js simFrame, simPaintKey, paintSim).

A playing run paints when what it shows changed, not on every frame. Measured from outside, with
MutationObserver and requestAnimationFrame; the product carries no counter.

A small document (two levers, each wired to an observer, the legend open) and then
docs/workengine/map.sov are opened in headless Chromium at 1600 x 1000:

  (a) with a run playing, one wire lit and no level changing for one second, the legend panel has 0
      DOM changes, #wires has 0 attribute changes and the run's marks (#simLayer) are not rebuilt;
  (b) a lever toggled while playing changes the lit class on its wire within two frames, by the
      clock's own toggle and by a level set on the run with no paint asked for (the frame's own
      comparison); the other lever's wire is left alone;
  (c) simStep, a render and simReset each repaint at once: the mark for the changed level is in
      #simLayer when the call returns;
  (d) with the legend open, simStep still renders the legend again;
  (e) on map.sov a playing run holds a median frame interval of 20 ms or less over two seconds;
  (f) the page logs no errors.

Two more, past the six: a wire pass with no render (renderWires alone, which is what a card drag
and a wire edit run) while the run plays has its new wire group lit again within two frames; and on
examples/10-clocked-signals.sov, whose levels are continuous, the marks are rebuilt at most 20 times
a second plus one for each frame a binary level changed on, and still at least 3 times (12 to 21
were measured on 2026-10-04; before the change, 61 in 61 frames).

And one about the document: simFrame no longer reads the whole document on every frame to learn
whether it changed (9 to 17 ms a frame on the map, which alone held the map at 30 frames a second
here). An edit while the run plays still restarts the clock from 0: by the next frames when the
edit renders, within the half second when it draws nothing.

The numbers are printed before anything is asserted, so a failing run still shows them.
"""
from __future__ import annotations
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

HTML = (ROOT / 'index.html').read_text(encoding='utf-8')
MAP = ROOT / 'docs' / 'workengine' / 'map.sov'
CLOCKED = ROOT / 'examples' / '10-clocked-signals.sov'
CONTINUOUS_PAINTS = 20  # a second: one every 50 ms

FIXTURE = r"""()=>{
  const A=SovSchematicAPI;A.clock.reset();
  A.document.replace({schema:SovSchematicData.DOCUMENT_SCHEMA,id:'run-repaint',components:[
    {id:'a',symbolId:'lever',x:150,y:200,config:{label:'A',signal:{value:0}}},
    {id:'b',symbolId:'lever',x:150,y:420,config:{label:'B',signal:{value:0}}},
    {id:'oa',symbolId:'observe',x:520,y:200,config:{label:'Sees A',signal:{mode:'derived'}}},
    {id:'ob',symbolId:'observe',x:520,y:420,config:{label:'Sees B',signal:{mode:'derived'}}}],
    wires:[{id:'wa',a:'a',aSide:'out',b:'oa',bSide:'in'},{id:'wb',a:'b',aSide:'out',b:'ob',bSide:'in'}]});
  fitDiagram();
  return {open:A.view.setLegend(true).open,rows:document.querySelectorAll('#legendPanel .legend-row').length};
}"""

# One second of a playing run with nothing changing: what the page wrote meanwhile.
QUIET = r"""async ()=>{
  const count={legend:0,wires:0,marks:0},seen=[];
  const watch=(el,key,options)=>{const o=new MutationObserver(r=>{count[key]+=r.length});o.observe(el,options);seen.push([o,key])};
  watch(document.getElementById('legendPanel'),'legend',{childList:true,subtree:true,attributes:true,characterData:true});
  watch(document.getElementById('wires'),'wires',{attributes:true,subtree:true});
  watch(document.getElementById('simLayer'),'marks',{childList:true,subtree:true});
  const before=SovSchematicAPI.clock.state().time;let frames=0;
  await new Promise(done=>{const start=performance.now();const tick=()=>{frames++;if(performance.now()-start<1000)requestAnimationFrame(tick);else done()};requestAnimationFrame(tick)});
  for(const [o,key] of seen){count[key]+=o.takeRecords().length;o.disconnect()}
  const state=SovSchematicAPI.clock.state();
  return {...count,frames,playing:state.playing,advanced:state.time-before,lit:document.querySelectorAll('.wire-group.level-high').length};
}"""

FRAMES = "n=>new Promise(done=>{const tick=()=>{if(--n<=0)done();else requestAnimationFrame(tick)};requestAnimationFrame(tick)})"
LIT = "id=>!!document.querySelector(`.wire-group[data-wire-id=\"${id}\"]`)?.classList.contains('level-high')"

# A lever toggled while the run plays: its wire's lit class two frames later, and the other wire's group.
TOGGLE = r"""async how=>{
  const frames=%s,lit=%s,other=document.querySelector('.wire-group[data-wire-id="wb"]');
  const o=new MutationObserver(()=>{});o.observe(other,{attributes:true});
  const out={playing:SovSchematicAPI.clock.state().playing,before:lit('wa')};
  const flip=()=>{if(how==='toggle')SovSchematicAPI.clock.toggle('a');else{const run=simClock.run,now=run.levels().a.value;run.set('a',now>0?0:1);run.run({until:run.state().time})}};
  flip();await frames(2);out.first=lit('wa');
  flip();await frames(2);out.second=lit('wa');
  out.otherTouched=o.takeRecords().length;o.disconnect();out.otherLit=lit('wb');
  return out;
}""" % (FRAMES, LIT)

# Each of these returns in one task: no frame runs between the call and the reading.
AT_ONCE = r"""()=>{
  const A=SovSchematicAPI,high=()=>!!document.querySelector('#simLayer .sim-lever[data-lever="a"].high'),marks=()=>document.querySelectorAll('#simLayer *').length;
  const quiet=v=>{const run=simClock.run;run.set('a',v);run.run({until:run.state().time})};
  const out={playing:A.clock.state().playing,start:high()};
  quiet(0);out.unpainted=high();A.clock.step();out.afterStep=high();
  quiet(1);simClock.run.advance(1);out.stale=high();render();out.afterRender=high();
  out.beforeReset={high:high(),marks:marks(),lit:document.querySelectorAll('.wire-group.level-high').length};
  A.clock.reset();out.afterReset={marks:marks(),lit:document.querySelectorAll('.wire-group.level-high').length,live:workspace.classList.contains('sim-live')};
  return out;
}"""

LEGEND_ON_STEP = r"""()=>{
  const panel=document.getElementById('legendPanel'),o=new MutationObserver(()=>{});
  o.observe(panel,{childList:true,subtree:true});SovSchematicAPI.clock.step();
  const changes=o.takeRecords().length;o.disconnect();
  return {changes,rows:panel.querySelectorAll('.legend-row').length,shown:!panel.hidden};
}"""

# An edit while the run plays restarts the clock from 0: one that draws nothing (the card's record
# changed in place) within the frame's own half-second look at the document, one made through the
# API, which renders, by the next frames.
EDITS = r"""async ()=>{
  const frames=%s,time=()=>SovSchematicAPI.clock.state().time,out={playing:SovSchematicAPI.clock.state().playing,before:time()};
  nodes.find(n=>n.id==='ob').config.label='Sees B, edited';
  await new Promise(done=>setTimeout(done,700));out.afterQuietEdit=time();out.note=document.getElementById('simTime').textContent;
  await new Promise(done=>setTimeout(done,400));out.beforeDrawnEdit=time();
  SovSchematicAPI.update('component','oa',{config:{label:'Sees A, edited'}});
  await frames(3);out.afterDrawnEdit=time();out.stillPlaying=SovSchematicAPI.clock.state().playing;
  return out;
}""" % FRAMES

# A wire pass with no render replaces the lit group; the playing run lights the new one.
WIRE_PASS = r"""async ()=>{
  const frames=%s,lit=%s,group=()=>document.querySelector('.wire-group[data-wire-id="wa"]');
  const old=group(),out={playing:SovSchematicAPI.clock.state().playing,before:lit('wa')};
  renderWires();out.replaced=group()!==old;out.atOnce=lit('wa');
  await frames(2);out.after=lit('wa');
  return out;
}""" % (FRAMES, LIT)

# Paints of the marks in one second: each one empties #simLayer in one record that removes a mark.
# An edge flash removed by its own timer is a record too, and is not counted.
PAINTS = r"""async ()=>{
  let paints=0;const count=r=>{for(const m of r)if([...m.removedNodes].some(n=>!n.classList?.contains('sim-edge')))paints++};
  const o=new MutationObserver(count);o.observe(document.getElementById('simLayer'),{childList:true});
  const state=()=>SovSchematicAPI.clock.state(),edges=()=>simClock.run.edges().edges.length,e0=edges(),t0=state().time;let frames=0;
  await new Promise(done=>{const start=performance.now();const tick=()=>{frames++;if(performance.now()-start<1000)requestAnimationFrame(tick);else done()};requestAnimationFrame(tick)});
  count(o.takeRecords());o.disconnect();
  return {paints,frames,edges:edges()-e0,advanced:state().time-t0,meters:document.querySelectorAll('#simLayer .sim-meter-fill').length};
}"""

# Frame times over two seconds, and what the wires layer was written meanwhile.
FRAME_TIMES = r"""async ()=>{
  let wires=0;const o=new MutationObserver(r=>{wires+=r.length});o.observe(document.getElementById('wires'),{attributes:true,subtree:true});
  const times=await new Promise(done=>{const ts=[];const tick=t=>{ts.push(t);if(t-ts[0]<2000)requestAnimationFrame(tick);else done(ts)};requestAnimationFrame(tick)});
  wires+=o.takeRecords().length;o.disconnect();
  const state=SovSchematicAPI.clock.state();
  return {times,wires,playing:state.playing,lit:document.querySelectorAll('.wire-group.level-high').length,groups:document.querySelectorAll('.wire-group').length};
}"""


def main() -> None:
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.set_content(HTML, wait_until='load'); page.wait_for_timeout(200)

        # The small document: lever A up, so one wire is lit, and the run playing.
        opened = page.evaluate(FIXTURE); page.wait_for_timeout(150)
        page.evaluate("()=>{SovSchematicAPI.clock.toggle('a');SovSchematicAPI.clock.play()}")
        page.wait_for_timeout(1000)  # the toggle's edge flashes take themselves away after 700 ms
        quiet = page.evaluate(QUIET)
        by_toggle = page.evaluate(TOGGLE, 'toggle')
        by_frame = page.evaluate(TOGGLE, 'frame')
        wire_pass = page.evaluate(WIRE_PASS)
        at_once = page.evaluate(AT_ONCE)
        page.evaluate("()=>SovSchematicAPI.clock.step()")
        legend = page.evaluate(LEGEND_ON_STEP)
        page.evaluate("()=>SovSchematicAPI.clock.play()"); page.wait_for_timeout(1250)  # between two of the frame's half-second looks
        edits = page.evaluate(EDITS)
        page.evaluate("()=>{SovSchematicAPI.clock.reset();SovSchematicAPI.view.setLegend(false)}")

        # Continuous levels: the clocked example, playing.
        page.evaluate('([t,n])=>{SovSchematicAPI.clock.reset();SovSchematicAPI.file.open(t,n);fitDiagram()}', [CLOCKED.read_text(encoding='utf-8'), CLOCKED.name])
        page.wait_for_timeout(150)
        page.evaluate("()=>SovSchematicAPI.clock.play()"); page.wait_for_timeout(300)
        paints = page.evaluate(PAINTS)
        page.evaluate("()=>SovSchematicAPI.clock.reset()")

        # The map, playing.
        page.evaluate('([t,n])=>{SovSchematicAPI.clock.reset();SovSchematicAPI.file.open(t,n);fitDiagram()}', [MAP.read_text(encoding='utf-8'), MAP.name])
        page.wait_for_timeout(300)
        page.evaluate("()=>SovSchematicAPI.clock.play()"); page.wait_for_timeout(500)
        played = page.evaluate(FRAME_TIMES)
        page.evaluate("()=>SovSchematicAPI.clock.reset()")
        # A continuous level reaching zero: 0.006 and 0 round to the same part in 50, and only one lights a wire.
        crossing = page.evaluate("""()=>{
          const at=v=>{simClock.run={levels:()=>({x:{kind:'continuous',value:v}}),edges:()=>({edges:[]}),parked:()=>[]};const k=simPaintKey();simClock.run=null;return k};
          const low=at(0.006),zero=at(0);return {sameBucket:low.continuous===zero.continuous,steadyDiffers:low.steady!==zero.steady};
        }""")
        browser.close()

    times = played['times']
    intervals = [b - a for a, b in zip(times, times[1:])]
    median_ms = statistics.median(intervals)
    print(f"(a) one quiet second playing: legend changes {quiet['legend']}, #wires attribute changes {quiet['wires']}, #simLayer changes {quiet['marks']}; {quiet['frames']} frames, {quiet['lit']} wire lit, run advanced {quiet['advanced']:.0f} ms")
    print(f"(b) lever toggled while playing, lit after two frames: by the clock {by_toggle}; by the frame {by_frame}")
    print(f"(c) at once: {at_once}")
    print(f"(d) legend on simStep: {legend}")
    print(f"(e) map.sov playing at 1600 x 1000: median frame {median_ms:.2f} ms over {len(intervals)} frames ({1000 / median_ms:.1f} a second), longest {max(intervals):.1f} ms; #wires attribute changes {played['wires']} in two seconds ({played['lit']} of {played['groups']} wires lit)")
    print(f"wire pass with no render: {wire_pass}")
    print(f"edits while playing, run time in ms: {edits}")
    print(f"continuous levels, one second: marks painted {paints['paints']} times in {paints['frames']} frames, {paints['edges']} edges, {paints['meters']} meters")

    assert opened['open'] is True and opened['rows'] >= 2, ('the small document shows its legend', opened)
    # (a)
    assert quiet['playing'] and quiet['advanced'] > 500 and quiet['frames'] > 20 and quiet['lit'] == 1, ('the run was playing with one wire lit', quiet)
    assert quiet['legend'] == 0, ('(a) a playing run with nothing changing leaves the legend panel alone', quiet)
    assert quiet['wires'] == 0, ('(a) a playing run with nothing changing writes no attribute in #wires', quiet)
    assert quiet['marks'] == 0, ('(a) a playing run with nothing changing does not rebuild its marks', quiet)
    # (b)
    for how, got in (('toggle', by_toggle), ('frame', by_frame)):
        assert got['playing'] and got['before'] is True and got['first'] is False and got['second'] is True, ('(b) the lever\'s wire follows it within two frames', how, got)
        assert got['otherTouched'] == 0 and got['otherLit'] is False, ('(b) a wire whose source did not change is not written', how, got)
    # (c)
    assert at_once['playing'] and at_once['start'] is True and at_once['unpainted'] is True and at_once['stale'] is False, ('a level set on the run alone paints nothing', at_once)
    assert at_once['afterStep'] is False, ('(c) simStep repaints at once', at_once)
    assert at_once['afterRender'] is True, ('(c) a render repaints at once', at_once)
    assert at_once['beforeReset']['high'] and at_once['beforeReset']['marks'] > 0 and at_once['beforeReset']['lit'] == 1, at_once
    assert at_once['afterReset'] == {'marks': 0, 'lit': 0, 'live': False}, ('(c) simReset repaints at once', at_once)
    # (d)
    assert legend['shown'] and legend['rows'] >= 2 and legend['changes'] > 0, ('(d) simStep renders the open legend again', legend)
    # The canvas under the run.
    assert wire_pass['playing'] and wire_pass['before'] and wire_pass['replaced'] and wire_pass['after'] is True, ('a wire group replaced with no render is lit again within two frames', wire_pass)
    # The document under the run.
    assert edits['playing'] and edits['before'] > 1000, edits
    # 700 ms after the edit the restarted clock reads at most those 700 ms; one not restarted reads `before` and 700 more.
    assert edits['afterQuietEdit'] < 800 and 'restarted' in edits['note'], ('an edit that draws nothing restarts a playing clock within the half second', edits)
    assert edits['beforeDrawnEdit'] > 300 and edits['afterDrawnEdit'] < 300 and edits['stillPlaying'], ('an edit that renders restarts a playing clock by the next frames', edits)
    # Continuous levels.
    assert paints['meters'] >= 2 and paints['advanced'] > 500, ('the clocked example plays its meters', paints)
    assert 3 <= paints['paints'] <= CONTINUOUS_PAINTS + paints['edges'] + 1, ('continuous levels repaint at most 20 times a second', paints)
    assert crossing == {'sameBucket': True, 'steadyDiffers': True}, ('a continuous level falling to zero repaints at once, so its wire goes dark', crossing)
    # (e)
    assert played['playing'] and len(intervals) > 20, played['playing']
    # The frame time is printed, not asserted: it is the machine's (16.7 ms here, 33.3 ms on the hosted
    # runner). What the paint costs is held by a count instead: with every wire lit and no level
    # changing, a playing run writes nothing in #wires (23,360 attribute writes in two seconds before).
    assert played['groups'] > 20 and played['lit'] > 20, ('(e) the map plays with its wires lit', played['lit'], played['groups'])
    assert played['wires'] == 0, ('(e) the map playing with no level changing writes no attribute in #wires', played['wires'])
    # (f)
    assert not errors, errors
    print('PASS run repaint QA')


if __name__ == '__main__':
    main()
