"""Live logic state in the editor (browser).

`SovSchematicAPI.logic.live` runs the open document as a circuit through the shared logic core
and draws its state on every render; `logic.run` is the stateless call MCP also answers.
Checked here in the running editor, against the circuit's definition and against
scripts/logic_sov.py, not against the overlay's own reading:

  - half adder: for every input vector each wire carries the value its net must have (S wire
    A xor B, C wire A and B, input wires their input) and each chip shows it, one chip per pin;
  - chips: under 100% zoom only inputs' chips show, plus the hovered and the selected
    component's; at 100% and above every chip shows;
  - an input's chip is its switch: clicking it flips the input and the outputs follow, and
    the click neither moves nor selects anything;
  - state: a register keeps what it latched while a part is moved (the circuit is not rebuilt);
    a change to the logic rebuilds it and says so;
  - composites: a full adder is refused until half-adder.sov is added, then every vector gives
    what scripts/logic_sov.py gives, on the canvas and through `logic.run`;
  - `logic.run` equals scripts/logic_sov.py for a clocked sequence (outputs, settle, transitions);
  - stopping restores the plain render: no chips, no logic values;
  - no page errors.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from logic_sov import Circuit  # noqa: E402

HTML = (ROOT / 'index.html').read_text()
LG = ROOT / 'examples' / 'logic'

WIRES = "()=>Object.fromEntries([...document.querySelectorAll('.wire-group[data-wire-id]')].map(g=>[g.dataset.wireId,g.dataset.logicValue??null]))"
INK = "()=>Object.fromEntries([...document.querySelectorAll('.wire-group[data-wire-id]')].map(g=>[g.dataset.wireId,g.style.getPropertyValue('--wire-ink').trim()]))"
CHIPS = "()=>[...document.querySelectorAll('.logic-chip')].map(c=>({pin:c.dataset.pin,node:c.dataset.node,value:c.dataset.value,shown:getComputedStyle(c).display!=='none',input:c.classList.contains('logic-input')}))"


def open_doc(page, name: str) -> dict:
    page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [(LG / name).read_text(encoding='utf-8'), name])
    page.wait_for_timeout(150)
    return json.loads((LG / name).read_text(encoding='utf-8'))


def api(page, expr: str, *args):
    return page.evaluate(f'(a)=>window.SovSchematicAPI.{expr}', list(args) if len(args) != 1 else args[0])


def check_half_adder(page) -> None:
    doc = open_doc(page, 'half-adder.sov')
    wires = {w['id']: w for w in doc['wires']}
    for a, b in itertools.product((0, 1), repeat=2):
        r = api(page, 'logic.live.start(a)', {'A': a, 'B': b})
        assert r['ok'] and r['outputs'] == {'S': a ^ b, 'C': a & b}, r
        seen = page.evaluate(WIRES)
        ink = page.evaluate(INK)
        for wid, w in wires.items():
            want = {'in-A': a, 'in-B': b, 'x': a ^ b, 'n': a & b}[w['a']]
            assert seen[wid] == str(want), (a, b, wid, seen[wid])
            # High in the signal colour, low in ink.
            assert (ink[wid] in ('#2a78d6', '#3987e5')) == (want == 1), (a, b, wid, ink[wid])
        chips = page.evaluate(CHIPS)
        pins = [c['pin'] for c in chips]
        assert len(pins) == len(set(pins)) == 10, pins
        for c in chips:
            want = {'in-A.out': a, 'in-B.out': b, 'x.a': a, 'x.b': b, 'n.a': a, 'n.b': b, 'x.q': a ^ b, 'n.q': a & b,
                    'out-S.in': a ^ b, 'out-C.in': a & b}[c['pin']]
            assert c['value'] == str(want), (a, b, c)


def check_chip_rule(page) -> None:
    api(page, 'logic.live.start(a)', {'A': 1, 'B': 0})
    api(page, 'view.setZoom(a)', 0.6)
    page.mouse.move(2, 2)
    chips = page.evaluate(CHIPS)
    assert chips and all(c['shown'] == c['input'] for c in chips), ('under 100%: inputs only', chips)
    page.hover('.node[data-id="x"]')
    chips = page.evaluate(CHIPS)
    for c in chips:
        assert c['shown'] == (c['input'] or c['node'] == 'x'), ('hovered part shows its chips', c)
    page.mouse.move(2, 2)
    page.evaluate("()=>{const g=document.querySelector('.node[data-id=\"n\"]');const r=g.getBoundingClientRect();"
                  "const o={bubbles:true,clientX:r.x+r.width/2,clientY:r.y+r.height/2,pointerId:1,button:0};"
                  "g.dispatchEvent(new PointerEvent('pointerdown',o));window.dispatchEvent(new PointerEvent('pointerup',o));g.dispatchEvent(new MouseEvent('click',o));}")
    page.wait_for_timeout(100)
    selected = api(page, 'selection.components()')
    assert selected == ['n'], selected
    page.mouse.move(2, 2)
    page.wait_for_timeout(50)
    chips = page.evaluate(CHIPS)
    for c in chips:
        assert c['shown'] == (c['input'] or c['node'] == 'n'), ('selected part shows its chips', c)
    api(page, 'view.setZoom(a)', 1.2)
    assert all(c['shown'] for c in page.evaluate(CHIPS)), 'at 100% and above every chip shows'


def check_toggle(page) -> None:
    open_doc(page, 'half-adder.sov')
    api(page, 'logic.live.start(a)', {'A': 0, 'B': 1})
    api(page, 'view.setZoom(a)', 1.0)
    # With a part selected, flipping an input keeps the selection (the click is the switch's alone).
    page.evaluate("()=>{const g=document.querySelector('.node[data-id=\"n\"]');const r=g.getBoundingClientRect();"
                  "const o={bubbles:true,clientX:r.x+r.width/2,clientY:r.y+r.height/2,pointerId:1,button:0};"
                  "g.dispatchEvent(new PointerEvent('pointerdown',o));window.dispatchEvent(new PointerEvent('pointerup',o));g.dispatchEvent(new MouseEvent('click',o));}")
    assert api(page, 'selection.components()') == ['n']
    before = api(page, 'document.get()')
    positions = {c['id']: (c.get('x'), c.get('y')) for c in before.get('result', before)['components']}
    page.locator('.logic-toggle[data-input="A"]').click()
    state = api(page, 'logic.live.state()')
    assert state['vector'] == {'A': 1, 'B': 1} and state['outputs'] == {'S': 0, 'C': 1}, state
    assert page.evaluate("()=>document.querySelector('.logic-chip[data-pin=\"x.q\"]').dataset.value") == '0'
    after = api(page, 'document.get()')
    assert {c['id']: (c.get('x'), c.get('y')) for c in after.get('result', after)['components']} == positions, 'a flip moves nothing'
    assert api(page, 'selection.components()') == ['n'], 'a flip neither selects nor clears'
    page.locator('.logic-toggle[data-input="A"]').click()
    assert api(page, 'logic.live.state()')['outputs'] == {'S': 1, 'C': 0}


def check_state_kept(page) -> None:
    open_doc(page, 'register4.sov')
    api(page, 'logic.live.start(a)', {})
    r = api(page, 'logic.live.pulse(a[0],a[1])', 'CLK', {'D0': 1, 'D1': 0, 'D2': 1, 'D3': 1})
    assert r['outputs'] == {'Q0': 1, 'Q1': 0, 'Q2': 1, 'Q3': 1}, r
    api(page, 'logic.live.set(a)', {'D0': 0, 'D1': 1, 'D2': 0, 'D3': 0})
    rebuilt = api(page, 'logic.live.state()')['rebuilt']
    moved = api(page, 'update(a[0],a[1],a[2])', 'component', 'ff0', {'x': 900, 'y': 600})
    assert moved['ok'], moved
    state = api(page, 'logic.live.state()')
    assert state['rebuilt'] == rebuilt and state['outputs'] == {'Q0': 1, 'Q1': 0, 'Q2': 1, 'Q3': 1}, ('moving keeps state', state)
    doc = api(page, 'document.get()')
    ff0 = next(c for c in doc.get('result', doc)['components'] if c['id'] == 'ff0')
    cfg = ff0['config']
    cfg['logic'] = {**cfg['logic'], 'delay': 2}
    changed = api(page, 'update(a[0],a[1],a[2])', 'component', 'ff0', {'config': cfg})
    assert changed['ok'], changed
    state = api(page, 'logic.live.state()')
    assert state['rebuilt'] == rebuilt + 1, ('a logic change rebuilds', state)
    # Rebuilt from power-on with the current inputs: nothing latched until the next edge.
    assert state['outputs'] == {'Q0': 0, 'Q1': 0, 'Q2': 0, 'Q3': 0}, state


def check_composites(page) -> None:
    open_doc(page, 'full-adder.sov')
    api(page, 'logic.composites.remove(a)', 'half-adder.sov')
    r = api(page, 'logic.live.start(a)', {'A': 1})
    assert not r['ok'] and r['refused'] == 'NO_COMPOSITE' and 'logic.composites.add' in r['next_operation'], r
    assert page.evaluate("()=>document.getElementById('workspace').dataset.logicLive") == 'refused'
    assert not page.evaluate(CHIPS)
    assert api(page, 'logic.composites.add(a[0],a[1])', 'half-adder.sov', (LG / 'half-adder.sov').read_text()) == ['half-adder.sov']
    py = Circuit(LG / 'full-adder.sov')
    for a, b, cin in itertools.product((0, 1), repeat=3):
        vector = {'A': a, 'B': b, 'Cin': cin}
        want = py.apply(vector)['outputs']
        r = api(page, 'logic.live.set(a)', vector) if (a, b, cin) != (0, 0, 0) else api(page, 'logic.live.start(a)', vector)
        assert r['ok'] and r['outputs'] == want, (vector, r, want)
        once = api(page, 'logic.run(a)', {'vector': vector})
        assert once['ok'] and once['steps'][0]['outputs'] == want, (vector, once)


def check_run_sequence(page) -> None:
    open_doc(page, 'accumulator4.sov')
    steps = [{'set': {'X0': 1, 'X1': 1, 'X2': 0, 'X3': 0}, 'pulse': 'CLK'}, {'set': {'X0': 1, 'X1': 0, 'X2': 1, 'X3': 0}, 'pulse': 'CLK'},
             {'set': {'X0': 1, 'X1': 0, 'X2': 0, 'X3': 1}, 'pulse': 'CLK'}]
    for name in ('adder4.sov', 'full-adder.sov', 'half-adder.sov', 'register4.sov'):
        api(page, 'logic.composites.add(a[0],a[1])', name, (LG / name).read_text())
    r = api(page, 'logic.run(a)', {'steps': steps})
    assert r['ok'], r
    py = Circuit(LG / 'accumulator4.sov')
    for step, got in zip(steps, r['steps']):
        want = py.pulse('CLK', step['set'])
        assert {k: got[k] for k in want} == want, (step, got, want)


def check_stop(page) -> None:
    open_doc(page, 'half-adder.sov')
    api(page, 'logic.live.start(a)', {'A': 1, 'B': 1})
    assert page.evaluate(CHIPS)
    r = api(page, 'logic.live.stop()')
    assert r['live'] is False
    assert not page.evaluate(CHIPS) and not any(v is not None for v in page.evaluate(WIRES).values())
    r = api(page, 'logic.live.set(a)', {'A': 0})
    assert not r['ok'] and r['refused'] == 'NOT_LIVE', r


def run() -> None:
    with sync_playwright() as p:
        b = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content(HTML, wait_until='load')
        page.wait_for_timeout(250)
        check_half_adder(page)
        check_chip_rule(page)
        check_toggle(page)
        check_state_kept(page)
        check_composites(page)
        check_run_sequence(page)
        check_stop(page)
        assert not errors, errors
        b.close()


if __name__ == '__main__':
    run()
    print('logic_live QA PASS')
