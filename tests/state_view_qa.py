"""The editor's state view (browser): a state space run's records on the canvas.

`SovSchematicAPI.view.stateSpace` replays a trace through the engine against the open
document and projects its records (src/57-state-view.js). Checked in the running editor
against the engine's own records and the circuit's definition:

  - stepping the 4-bit adder's carry run tick by tick, the S chips read 7, then 6, 4, 0 and
    8 at the ticks the records say, and the ticks offered are the records' own;
  - a wire takes the level of the port it leaves from; while a change is in flight the two
    ends of a wire differ;
  - chips: under 100% zoom only sources' chips show, plus the hovered and the selected
    component's; at 100% and above every chip shows;
  - passive: showing, stepping and hiding change neither the document nor the trace (a replay
    after them reproduces the same records);
  - refusals: a trace of another document (REPLAY_KEY_MISMATCH), stepping with nothing shown
    (NOT_SHOWING), and a document edited under a shown run (DOCUMENT_CHANGED), which draws no
    state until a run of the edited document is shown;
  - hiding restores the plain render; no page errors.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from export_svg import RUN_JS  # noqa: E402
from record_run import parse_vector  # noqa: E402

LG = ROOT / 'examples' / 'logic'
PACKS = [json.loads((ROOT / 'data' / p).read_text(encoding='utf-8')) for p in ('core.logic.pack.json', 'logic.gates.pack.json')]
CHIPS = ("()=>[...document.querySelectorAll('.state-chip')].map(c=>({pin:c.dataset.pin,node:c.dataset.node,value:c.dataset.value,"
         "shown:getComputedStyle(c).display!=='none',source:c.classList.contains('state-source')}))")
WIRES = "()=>Object.fromEntries([...document.querySelectorAll('.wire-group[data-wire-id]')].map(g=>[g.dataset.wireId,g.dataset.stateLevel??null]))"


def api(page, expr: str, arg=None):
    return page.evaluate(f'(a)=>window.SovSchematicAPI.{expr}', arg)


def open_doc(page, name: str) -> dict:
    api(page, 'file.open(a[0],a[1])', [(LG / name).read_text(encoding='utf-8'), name])
    page.wait_for_timeout(120)
    return json.loads((LG / name).read_text(encoding='utf-8'))


def run(page, steps: list[str], period: int = 20) -> dict:
    inputs = [{'entity': k, 'point': 'self', 'value': bool(v), 'at': i * period}
              for i, step in enumerate(steps) for k, v in sorted(parse_vector(step).items())]
    made = page.evaluate(RUN_JS, [PACKS, inputs])
    assert made['ok'], made
    return made['trace']


def chip_values(page) -> dict:
    return {c['pin']: int(c['value']) for c in page.evaluate(CHIPS)}


def check_carry(page) -> None:
    doc = open_doc(page, 'adder4.sov')
    revision = api(page, 'file.info()')['revision']
    trace = run(page, ['A=7:4,B=0:4,Cin=0', 'B0=1'])
    shown = api(page, 'view.stateSpace.show(a)', {'trace': trace, 'packs': PACKS})
    assert shown['ok'] and shown['tick'] == trace['through'], shown
    assert shown['ticks'] == sorted({r['time']['logical'] for r in trace['records']}), shown['ticks']
    # S from the engine's records, tick by tick: what the chips must read.
    level, want = {}, {}
    for r in trace['records']:
        if r['subject']['point'] == 'self' and r['subject']['entity'].startswith('S'):
            level[r['subject']['entity']] = int(r['value'])
            want[r['time']['logical']] = sum(level.get(f'S{i}', 0) << i for i in range(4))
    seen = {}
    for t in shown['ticks']:
        api(page, 'view.stateSpace.tick(a)', t)
        v = chip_values(page)
        seen[t] = sum(v[f'S{i}.self'] << i for i in range(4))
    assert [seen[t] for t in sorted(want)] == [want[t] for t in sorted(want)], (seen, want)
    assert [seen[t] for t in (20, 22, 23, 24, 25)] == [7, 6, 4, 0, 8], seen
    # In flight at tick 23: fa2 has already put 0 on s, and S2 still holds 1.
    api(page, 'view.stateSpace.tick(a)', 23)
    v = chip_values(page)
    assert v['fa2.s'] == 0 and v['S2.self'] == 1, v
    port = lambda w, end: (w.get(f'{end}Attachment') or {}).get('pointId') or w[f'{end}Side']  # noqa: E731
    wires = page.evaluate(WIRES)
    for w in doc['wires']:
        assert wires[w['id']] == str(v[f"{w['a']}.{port(w, 'a')}"]), ('a wire shows its sending port', w['id'])
    # Passive: nothing written, and the trace still replays to the same records.
    api(page, 'view.stateSpace.hide()')
    assert api(page, 'file.info()')['revision'] == revision
    again = page.evaluate('([doc,packs,trace])=>SovSchematicStateSpace.replay({doc,packs,trace})', [api(page, 'document.get()'), PACKS, trace])
    assert again['ok'] and again['records'] == trace['records'], again.get('code')
    assert not page.evaluate(CHIPS) and not any(x is not None for x in page.evaluate(WIRES).values()), 'hidden: plain render'


def check_chip_rule(page) -> None:
    open_doc(page, 'half-adder.sov')
    trace = run(page, ['A=1,B=0'])
    api(page, 'view.stateSpace.show(a)', {'trace': trace, 'packs': PACKS})
    api(page, 'view.setZoom(a)', 0.6)
    page.mouse.move(2, 2)
    chips = page.evaluate(CHIPS)
    assert chips and any(c['source'] for c in chips) and all(c['shown'] == c['source'] for c in chips), chips
    page.hover('.node[data-id="x"]')
    for c in page.evaluate(CHIPS):
        assert c['shown'] == (c['source'] or c['node'] == 'x'), ('hovered part shows its chips', c)
    page.mouse.move(2, 2)
    page.evaluate("()=>{const g=document.querySelector('.node[data-id=\"n\"]');const r=g.getBoundingClientRect();"
                  "const o={bubbles:true,clientX:r.x+r.width/2,clientY:r.y+r.height/2,pointerId:1,button:0};"
                  "g.dispatchEvent(new PointerEvent('pointerdown',o));window.dispatchEvent(new PointerEvent('pointerup',o));g.dispatchEvent(new MouseEvent('click',o));}")
    page.wait_for_timeout(80)
    assert api(page, 'selection.components()') == ['n']
    page.mouse.move(2, 2)
    for c in page.evaluate(CHIPS):
        assert c['shown'] == (c['source'] or c['node'] == 'n'), ('selected part shows its chips', c)
    api(page, 'view.setZoom(a)', 1.2)
    assert all(c['shown'] for c in page.evaluate(CHIPS)), 'at 100% and above every chip shows'
    api(page, 'view.stateSpace.hide()')


def check_refusals(page) -> None:
    open_doc(page, 'half-adder.sov')
    trace = run(page, ['A=1,B=1'])
    r = api(page, 'view.stateSpace.tick(a)', 3)
    assert not r['ok'] and r['refused'] == 'NOT_SHOWING', r
    open_doc(page, 'full-adder.sov')
    r = api(page, 'view.stateSpace.show(a)', {'trace': trace, 'packs': PACKS})
    assert not r['ok'] and r['refused'] == 'REPLAY_KEY_MISMATCH', r
    assert page.evaluate("()=>document.getElementById('workspace').dataset.stateView") == 'refused' and not page.evaluate(CHIPS)
    api(page, 'view.stateSpace.hide()')
    # Edited under a shown run: the run no longer describes the document.
    open_doc(page, 'half-adder.sov')
    trace = run(page, ['A=1,B=1'])
    assert api(page, 'view.stateSpace.show(a)', {'trace': trace, 'packs': PACKS})['ok']
    assert page.evaluate(CHIPS)
    moved = api(page, 'update(a[0],a[1],a[2])', ['component', 'x', {'x': 700, 'y': 400}])
    assert moved['ok'], moved
    info = api(page, 'view.stateSpace.info()')
    assert not info['ok'] and info['refused'] == 'DOCUMENT_CHANGED', info
    assert not page.evaluate(CHIPS)
    fresh = run(page, ['A=1,B=1'])
    assert api(page, 'view.stateSpace.show(a)', {'trace': fresh, 'packs': PACKS})['ok'] and page.evaluate(CHIPS)
    api(page, 'view.stateSpace.hide()')


def main() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(250)
        check_carry(page)
        check_chip_rule(page)
        check_refusals(page)
        assert not errors, errors
        b.close()
    print('state_view QA PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
