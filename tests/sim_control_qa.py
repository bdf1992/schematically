"""Canvas control plane QA: one clock drives the graph engine over the live document.

Levels paint and light their wires; a lever toggles by click; editing the document restarts
the clock; an entry node sends its scenario's message; a waiting human step is approved in
place; a retried case does not reach the customer twice; exports carry no overlay.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')

def open_doc(page, name):
    page.evaluate('([t,n])=>{SovSchematicAPI.clock.reset();SovSchematicAPI.file.open(t,n);fitDiagram()}', [(ROOT / 'examples' / name).read_text(encoding='utf-8'), name])
    page.wait_for_timeout(120)

def click_center(page, selector):
    box = page.locator(selector).first.bounding_box()
    assert box, selector
    page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    page.wait_for_timeout(40)

with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1500, 'height': 900})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.set_content(HTML, wait_until='load'); page.wait_for_timeout(200)
    assert page.evaluate("()=>SovSchematicAPI.clock.state().running") is False

    # Example 10: the clock ANDed with the lever.
    open_doc(page, '10-clocked-signals.sov')
    s = page.evaluate("()=>{SovSchematicAPI.clock.advance(1250);return SovSchematicAPI.clock.state()}")
    assert s['time'] == 1250 and s['levels']['enable']['value'] == 0 and s['levels']['lamp']['value'] == 0, s
    assert page.evaluate("()=>document.querySelectorAll('#simLayer .sim-meter-fill').length") >= 2, 'continuous meters drawn'
    assert page.evaluate("()=>document.querySelectorAll('#workspace.sim-live').length") == 1
    # Lever up by click; in the clock's high half the lamp lights and its wire is lit.
    click_center(page, '#simLayer .sim-lever')
    s = page.evaluate("()=>{SovSchematicAPI.clock.advance(1000);return SovSchematicAPI.clock.state()}")
    assert s['levels']['enable']['value'] == 1 and s['levels']['both']['value'] == 1 and s['levels']['lamp']['value'] == 1, s
    assert page.evaluate("()=>document.querySelector('.wire-group[data-wire-id=\"w3\"]').classList.contains('level-high')")
    assert page.evaluate("()=>document.querySelectorAll('#simLayer .sim-level.binary.high').length") >= 2
    edges = page.evaluate("()=>SovSchematicAPI.clock.inspect('edges','lamp').edges.map(e=>e.polarity)")
    assert edges == ['+', '-', '+'], edges  # up at 1250 in the clock's high half, down at 1500, up at 2000
    # A derived signal cannot be set by the canvas either.
    assert page.evaluate("()=>SovSchematicAPI.clock.toggle('both')")['code'] == 'DERIVED_SIGNAL'
    # Editing the document restarts the clock from time 0: the document is the authority.
    page.evaluate("()=>SovSchematicAPI.update('component','lamp',{config:{label:'Lamp 2'}})")
    s = page.evaluate("()=>{SovSchematicAPI.clock.advance(10);return SovSchematicAPI.clock.state()}")
    assert s['time'] == 10, s
    # Play and pause through the transport.
    click_center(page, '#simPlayBtn'); page.wait_for_timeout(250); click_center(page, '#simPlayBtn')
    s = page.evaluate("()=>SovSchematicAPI.clock.state()")
    assert s['time'] > 10 and not s['playing'], s

    # Example 09: send, wait on the reviewer, approve in place, retry without a second send.
    open_doc(page, '09-print-ai-proof-run.sov')
    assert page.evaluate("()=>document.querySelectorAll('#simLayer .sim-send').length") == 0, 'controls appear only while the clock is on'
    click_center(page, '#simStepBtn')
    click_center(page, '#simLayer .sim-send')
    page.evaluate("()=>SovSchematicAPI.clock.advance(200)")
    assert page.evaluate("()=>SovSchematicAPI.clock.state().parked.length") == 1
    click_center(page, '#simLayer .sim-decide.approve')
    page.evaluate("()=>SovSchematicAPI.clock.advance(200)")
    assert page.evaluate("()=>SovSchematicAPI.clock.inspect('taps','customer').arrivals.filter(m=>m.channel==='proof').length") == 1
    click_center(page, '#simLayer .sim-send'); page.evaluate("()=>SovSchematicAPI.clock.advance(200)")
    click_center(page, '#simLayer .sim-decide.approve'); page.evaluate("()=>SovSchematicAPI.clock.advance(200)")
    assert page.evaluate("()=>SovSchematicAPI.clock.inspect('taps','customer').arrivals.filter(m=>m.channel==='proof').length") == 1, 'replayed, not resent'
    assert page.evaluate("()=>SovSchematicAPI.clock.inspect('log').log.filter(e=>e.event==='effect-replayed').length") == 1
    assert page.evaluate("()=>SovSchematicAPI.clock.inspect('refusals').refusals.length") == 0, 'the run ACL admits intake and the mailer'
    # The overlay is a moment, not the document.
    doc = page.evaluate("()=>JSON.stringify(SovSchematicAPI.file.document())")
    assert 'levels' not in doc and 'simLayer' not in doc
    page.evaluate("()=>SovSchematicAPI.clock.reset()")
    assert page.evaluate("()=>document.querySelectorAll('#simLayer *').length") == 0
    assert not errors, errors
    browser.close()
print('PASS canvas control plane QA')
