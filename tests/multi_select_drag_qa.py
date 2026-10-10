"""A pointer drag of a multi-selection moves the whole group (issue #49).

Pressing a Component that is already part of a multi-selection keeps the selection: the drag moves
every selected root together, as one history transition, and the pressed Component becomes the
primary. Pressing an unselected Component still selects it alone. A click that does not drag
collapses the selection to the clicked Component, as it always has. Everything is driven through
the real pointer.
"""
from __future__ import annotations
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')

CLIENT = "([x,y])=>{const p=workspace.createSVGPoint();p.x=x;p.y=y;const c=p.matrixTransform(workspace.getScreenCTM());return {x:c.x,y:c.y}}"
POS = "()=>Object.fromEntries(nodes.map(n=>[n.id,[n.x,n.y]]))"
SELECTION = "()=>({set:[...selectedComponentIds].sort(),primary:selected})"
HASH = '()=>SovSchematicData.documentHash(diagram)'
UNDO_COUNT = '()=>historyState.undo.length'
HIST = '()=>historyState.undo.map(x=>x.label)'
HISTORY_LIMIT_MS = 5000
# True when no history capture is pending and, when a count is given, the undo list holds at least that many entries.
HISTORY_SETTLED = '(n)=>historyState.timer===null&&(n===null||historyState.undo.length>=n)'
# The pointer is kept down and still for this long: past the autosave timer (420 ms) and the history timer (320 ms) together.
HELD_MS = 1500


def history_settles(page, entries=None):
    """Wait, up to HISTORY_LIMIT_MS, until the history has captured; a timeout raises and fails the run."""
    page.wait_for_function(HISTORY_SETTLED, arg=entries, timeout=HISTORY_LIMIT_MS)


def client(page, cid):
    n = page.evaluate("(id)=>{const n=nodes.find(x=>x.id===id);return [n.x,n.y]}", cid)
    return page.evaluate(CLIENT, n)


def press_and_drag(page, cid, dx, dy, entries=None):
    """Press the Component at its centre and drag it by a screen offset."""
    c = client(page, cid)
    page.mouse.move(c['x'], c['y'])
    page.mouse.down()
    page.mouse.move(c['x'] + 8, c['y'] + 8, steps=2)
    page.mouse.move(c['x'] + dx, c['y'] + dy, steps=10)
    page.wait_for_timeout(120)
    page.mouse.up()
    history_settles(page, entries)


def press_hold_and_drag(page, cid, dx, dy, entries):
    """Press, move half of the way, keep the pointer down and still for HELD_MS, move the rest, release."""
    c = client(page, cid)
    page.mouse.move(c['x'], c['y'])
    page.mouse.down()
    page.mouse.move(c['x'] + dx / 2, c['y'] + dy / 2, steps=5)
    page.wait_for_timeout(HELD_MS)
    page.mouse.move(c['x'] + dx, c['y'] + dy, steps=5)
    page.wait_for_timeout(120)
    page.mouse.up()
    history_settles(page, entries)


def click(page, cid):
    c = client(page, cid)
    page.mouse.click(c['x'], c['y'])
    history_settles(page)


def delta(before, after, cid):
    return [round(after[cid][0] - before[cid][0]), round(after[cid][1] - before[cid][1])]


with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(300)
    page.evaluate('newSchematic()')
    page.evaluate("""()=>{const A=window.SovSchematicAPI;
      A.create('component',{id:'a',symbolId:'act',x:240,y:240});
      A.create('component',{id:'b',symbolId:'hold',x:520,y:240});
      A.create('component',{id:'c',symbolId:'gate',x:380,y:560});
      render()}""")
    page.wait_for_timeout(200)
    page.evaluate("()=>{selectNode('a');selectNode('b',{focus:false,additive:true})}")
    assert page.evaluate(SELECTION) == {'set': ['a', 'b'], 'primary': 'b'}

    # 1. Pressing a member of the selection keeps it; the drag moves both roots by the same offset,
    #    leaves the third where it was, makes the pressed Component the primary, and is one transition.
    before, h0, c0 = page.evaluate(POS), page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    press_and_drag(page, 'a', 120, 160, c0 + 1)
    after = page.evaluate(POS)
    da, db = delta(before, after, 'a'), delta(before, after, 'b')
    assert da == db and da[0] >= 80 and da[1] >= 120, ('the group did not move together', da, db)
    assert delta(before, after, 'c') == [0, 0], ('an unselected Component moved', after['c'])
    assert page.evaluate(SELECTION) == {'set': ['a', 'b'], 'primary': 'a'}, page.evaluate(SELECTION)
    # One transition even though the creation's own deferred capture was still pending when the
    # press began: the gesture commits it first, so nothing fires at an intermediate position.
    assert page.evaluate(UNDO_COUNT) == c0 + 1 and page.evaluate(HIST)[-1] == 'Move selection', page.evaluate(HIST)
    page.evaluate('()=>SovSchematicAPI.history.undo()')
    assert page.evaluate(HASH) == h0 and page.evaluate(POS) == before, 'undo does not restore the group move'
    page.evaluate('()=>SovSchematicAPI.history.redo()')
    assert page.evaluate(POS) == after, 'redo does not restore the group move'

    # 2. Pressing an unselected Component selects it alone, and the drag moves only it.
    page.evaluate("()=>{selectNode('a');selectNode('b',{focus:false,additive:true})}")
    before, c1 = page.evaluate(POS), page.evaluate(UNDO_COUNT)
    press_and_drag(page, 'c', 100, -60, c1 + 1)
    after = page.evaluate(POS)
    assert delta(before, after, 'c') != [0, 0] and delta(before, after, 'a') == [0, 0] and delta(before, after, 'b') == [0, 0], (before, after)
    assert page.evaluate(SELECTION) == {'set': ['c'], 'primary': 'c'}, page.evaluate(SELECTION)
    assert page.evaluate(UNDO_COUNT) == c1 + 1 and page.evaluate(HIST)[-1] == 'Move Component', page.evaluate(HIST)

    # 3. A click on a member that does not drag collapses the selection to that Component. A press
    #    is a settle, as it always was: the pressed Component snaps to the grid and, while the group
    #    is still held, the group follows by the same offset; nothing else moves.
    page.evaluate("()=>{selectNode('a');selectNode('b',{focus:false,additive:true})}")
    before = page.evaluate(POS)
    click(page, 'b')
    assert page.evaluate(SELECTION) == {'set': ['b'], 'primary': 'b'}, page.evaluate(SELECTION)
    after = page.evaluate(POS)
    da, db = delta(before, after, 'a'), delta(before, after, 'b')
    assert da == db and max(abs(da[0]), abs(da[1])) < 24 and delta(before, after, 'c') == [0, 0], ('a press is a settle of the held group only', before, after)

    # 4. A shift-click adds to the selection and a plain drag of the group still moves it whole.
    page.keyboard.down('Shift')
    click(page, 'a')
    page.keyboard.up('Shift')
    assert page.evaluate(SELECTION) == {'set': ['a', 'b'], 'primary': 'a'}, page.evaluate(SELECTION)
    before = page.evaluate(POS)
    press_and_drag(page, 'b', -80, 120)
    after = page.evaluate(POS)
    assert delta(before, after, 'a') == delta(before, after, 'b') != [0, 0], (before, after)
    assert page.evaluate(SELECTION) == {'set': ['a', 'b'], 'primary': 'b'}, page.evaluate(SELECTION)

    # 5. A drag held still for longer than the autosave timer and the history timer together is still
    #    one transition: a capture timer that comes due while the pointer is down waits for the
    #    release. render() arms both timers just before the press.
    page.evaluate('newSchematic()')
    page.evaluate("()=>{window.SovSchematicAPI.create('component',{id:'h',symbolId:'act',x:300,y:300});render()}")
    before, c5 = page.evaluate(POS), page.evaluate(UNDO_COUNT)
    press_hold_and_drag(page, 'h', 160, 120, c5 + 1)
    assert delta(before, page.evaluate(POS), 'h') != [0, 0], ('the held drag did not move the Component', before, page.evaluate(POS))
    assert page.evaluate(UNDO_COUNT) == c5 + 1 and page.evaluate(HIST)[-1] == 'Move Component', ('a held drag is not one history entry', page.evaluate(HIST)[c5:])
    page.evaluate('()=>SovSchematicAPI.history.undo()')
    assert page.evaluate(POS) == before, 'one undo does not restore a held drag'

    assert not errors, errors
    browser.close()
    print('PASS multi-select drag QA')
