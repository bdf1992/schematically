"""The editor's Ports panel (contract 0b-2, steps 1-5, and the panel half of step 9).

A 2D Component's settings panel lists its effective ports, one row each, and every edit sends the
complete port list through the data core's component update: one edit is one history transition,
and a refusal changes nothing, reverts its row and puts its message in the status line. The
section is hidden for 0D and 1D Components. On a Component bound to a definition the id, flow,
channels and Remove controls are disabled with a title saying why, and "Add port" is disabled;
settling such a Component on a Wire is refused (DEFINITION_PORTS) and it returns to where it was.
Everything is driven through the real UI: clicks, typing, selects and pointer drags.
"""
from __future__ import annotations
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')
PACK = json.loads((ROOT / 'data/core.logic.pack.json').read_text(encoding='utf-8'))

# Client coordinates of a world point.
CLIENT = "([x,y])=>{const p=workspace.createSVGPoint();p.x=x;p.y=y;const c=p.matrixTransform(workspace.getScreenCTM());return {x:c.x,y:c.y}}"
STATE = """(id)=>{const n=nodes.find(x=>x.id===id);if(!n)return null;
  return {mode:n.config.attachmentDefaults??null,stored:n.config.attachmentPoints??null,
    specs:Attachment.pointSpecs(n).map(s=>({id:s.id,side:s.side,t:s.t,flow:s.flow,channels:Attachment.channelIds(s),label:s.label??null})),
    x:n.x,y:n.y,canvasId:n.canvasId,placement:n.placement?.kind??'surface'}}"""
HASH = '()=>SovSchematicData.documentHash(diagram)'
UNDO_COUNT = '()=>historyState.undo.length'
ROWS = "()=>[...document.querySelectorAll('#portsList .ports-row')].map(r=>r.dataset.portId)"
ROW_VALUES = """(pid)=>{const r=document.querySelector(`#portsList .ports-row[data-port-id="${pid}"]`);if(!r)return null;
  const v=c=>r.querySelector('.'+c);
  return {id:v('port-id').value,label:v('port-label').value,side:v('port-side').value,t:Number(v('port-t').value),flow:v('port-flow').value,channels:v('port-channels').value}}"""
# The rendered attachment point, in the Component's local coordinates.
DRAWN = """([id,pid])=>{const c=document.querySelector(`.node[data-id="${id}"] circle.attachment-point[data-point="${pid}"]`);
  const n=nodes.find(x=>x.id===id),s=componentSize(n);return c?{cx:+c.getAttribute('cx'),cy:+c.getAttribute('cy'),w:s.w,h:s.h}:null}"""


def row(page, pid, cls):
    return page.locator(f'#portsList .ports-row[data-port-id="{pid}"] .{cls}')


def status(page):
    return page.locator('#status').inner_text()


def client(page, x, y):
    return page.evaluate(CLIENT, [x, y])


def open_panel(page, cid):
    """Select the Component by clicking it, then open its settings with the bar's button."""
    # An open panel may lie over the Component (and over the bar's own settings button), so close it first.
    page.evaluate('()=>closeSelectionSettings()')
    # A Point or a Path is clicked at its centre; a 2D form off-centre, clear of Wires routed across it.
    n = page.evaluate('(id)=>{const n=nodes.find(x=>x.id===id),s=componentSize(n),d=componentForm(n).dimension===2?.3:0;return {x:n.x-s.w*d,y:n.y-s.h*d}}', cid)
    c = client(page, n['x'], n['y'])
    page.mouse.click(c['x'], c['y'])
    page.wait_for_timeout(60)
    assert page.evaluate('()=>selected') == cid, (page.evaluate('()=>selected'), cid)
    if page.evaluate('()=>selectionSettingsPanel.hidden'):
        page.locator('#barSelectionSettings').click()
    page.wait_for_timeout(450)  # a click is a settle, which may snap the Component: let that transition land first
    assert page.evaluate('()=>!selectionSettingsPanel.hidden')


def one_transition(page, before_hash, before_count, label, cid):
    """The edit made exactly one history transition, and undo restores the document exactly.
    Undo and redo replace the document, which closes the panel; it is reopened on `cid`."""
    page.wait_for_timeout(450)  # past any scheduled capture: a second transition would show here
    after_hash = page.evaluate(HASH)
    count = page.evaluate(UNDO_COUNT)
    assert count == before_count + 1 and after_hash != before_hash, (label, count, before_count, page.evaluate('()=>historyState.undo.map(x=>x.label)'))
    page.evaluate('()=>SovSchematicAPI.history.undo()')
    assert page.evaluate(HASH) == before_hash, (label, 'undo does not restore')
    page.evaluate('()=>SovSchematicAPI.history.redo()')
    assert page.evaluate(HASH) == after_hash, (label, 'redo does not restore')
    open_panel(page, cid)


def refused(page, before_hash, before_count, want, label):
    """A refusal leaves the document and history unchanged and shows its message."""
    page.wait_for_timeout(450)
    assert page.evaluate(HASH) == before_hash, (label, 'refusal changed the document')
    assert page.evaluate(UNDO_COUNT) == before_count, (label, 'refusal entered history')
    text = status(page)
    assert want in text, (label, text)


with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(300)
    page.evaluate('newSchematic()')
    scene = page.evaluate("""()=>{const A=window.SovSchematicAPI;
      const g=A.create('component',{id:'g',symbolId:'act',x:520,y:360}).result;
      const src=A.create('component',{id:'src',symbolId:'point',x:220,y:360}).result;
      const q=A.create('component',{id:'q',symbolId:'point',x:860,y:520}).result;
      const rail=A.create('component',{id:'rail',symbolId:'act',x:520,y:720,form:{dimension:1}}).result;
      const w=A.create('wire',{id:'w',a:'src',aSide:'self',b:'g',bAttachment:{pointId:'left'}});
      render();return {w:w.ok}}""")
    assert scene['w'], scene
    page.wait_for_timeout(120)

    # --- Step 1: the Ports list -------------------------------------------------------------
    open_panel(page, 'g')
    assert page.locator('#portsSettings').is_visible()
    assert page.evaluate(ROWS) == ['left', 'right', 'top']
    assert page.evaluate(ROW_VALUES, 'left') == {'id': 'left', 'label': '', 'side': 'left', 't': .5, 'flow': 'in', 'channels': 'main'}
    assert page.evaluate(ROW_VALUES, 'top') == {'id': 'top', 'label': '', 'side': 'top', 't': .5, 'flow': 'control', 'channels': 'main'}
    assert row(page, 'left', 'port-id').get_attribute('readonly') is not None
    assert page.evaluate("()=>[...document.querySelector('#portsList .port-side').options].map(o=>o.value)") == ['left', 'right', 'top', 'bottom']
    assert page.evaluate("()=>[...document.querySelector('#portsList .port-flow').options].map(o=>o.value)") == ['in', 'out', 'duplex', 'control', 'trigger']
    t_attrs = page.evaluate("()=>{const t=document.querySelector('#portsList .port-t');return [t.type,t.min,t.max,t.step]}")
    assert t_attrs == ['number', '0', '1', '0.05'], t_attrs
    # The section sits below the Attachments control.
    below = page.evaluate("()=>formAttachments.closest('label').getBoundingClientRect().bottom<=portsSettings.getBoundingClientRect().top")
    assert below
    # Hidden for 0D and 1D Components.
    open_panel(page, 'q')
    assert page.evaluate('()=>portsSettings.hidden') and not page.locator('#portsSettings').is_visible()
    open_panel(page, 'rail')
    assert page.evaluate('(id)=>Attachment.effectiveDimension(nodes.find(n=>n.id===id))', 'rail') == 1
    assert page.evaluate('()=>portsSettings.hidden')

    # --- Steps 2 and 3: edits apply, one transition each ------------------------------------
    open_panel(page, 'g')
    # Label: stored on the port, and drawn on the canvas.
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'right', 'port-label').fill('OUT')
    row(page, 'right', 'port-label').press('Enter')
    s = page.evaluate(STATE, 'g')
    assert [x['label'] for x in s['specs']] == [None, 'OUT', None], s
    assert s['mode'] == 'none', s  # a changed template port is stored as the full list
    assert page.locator('.node[data-id="g"] .port-label-text', has_text='OUT').count() == 1
    assert page.evaluate(ROW_VALUES, 'right')['label'] == 'OUT'
    one_transition(page, h, c, 'label', 'g')
    # Side: the canvas draws the port on its new side.
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'top', 'port-side').select_option('bottom')
    s = page.evaluate(STATE, 'g')
    assert next(x for x in s['specs'] if x['id'] == 'top')['side'] == 'bottom', s
    d = page.evaluate(DRAWN, ['g', 'top'])
    assert d['cy'] > d['h'] / 2 - 8 and abs(d['cx']) < 1, d
    one_transition(page, h, c, 'side', 'g')
    # Position t: the canvas draws it at its new position along the side.
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'top', 'port-t').fill('0.25')
    row(page, 'top', 'port-t').press('Enter')
    s = page.evaluate(STATE, 'g')
    assert next(x for x in s['specs'] if x['id'] == 'top')['t'] == .25, s
    d = page.evaluate(DRAWN, ['g', 'top'])
    assert abs(d['cx'] - (-d['w'] / 2 + d['w'] * .25)) < 1.5 and d['cy'] > 0, d
    one_transition(page, h, c, 't', 'g')
    # Flow.
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'top', 'port-flow').select_option('trigger')
    assert next(x for x in page.evaluate(STATE, 'g')['specs'] if x['id'] == 'top')['flow'] == 'trigger'
    one_transition(page, h, c, 'flow', 'g')
    # Channels: comma-separated ids.
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'top', 'port-channels').fill('main, aux')
    row(page, 'top', 'port-channels').press('Enter')
    assert next(x for x in page.evaluate(STATE, 'g')['specs'] if x['id'] == 'top')['channels'] == ['main', 'aux']
    assert page.evaluate(ROW_VALUES, 'top')['channels'] == 'main, aux'
    one_transition(page, h, c, 'channels', 'g')

    # Refusals: each leaves nothing changed, reverts its row, and shows the refusal.
    for label, cls, value, want in (
        ('t above 1', 'port-t', '1.5', 'invalid t 1.5'),
        ('t below 0', 'port-t', '-0.2', 'invalid t -0.2'),
        ('empty channels', 'port-channels', ' ', 'channels must be a non-empty array'),
        ('repeated channel', 'port-channels', 'main, main', 'repeats channel main'),
    ):
        before_row = page.evaluate(ROW_VALUES, 'top')
        h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
        row(page, 'top', cls).fill(value)
        row(page, 'top', cls).press('Enter')
        refused(page, h, c, want, label)
        assert page.evaluate(ROW_VALUES, 'top') == before_row, (label, page.evaluate(ROW_VALUES, 'top'), before_row)
    # A channel edit that would leave the bound Wire between ports sharing no channel.
    before_row = page.evaluate(ROW_VALUES, 'left')
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'left', 'port-channels').fill('aux')
    row(page, 'left', 'port-channels').press('Enter')
    refused(page, h, c, 'CHANNEL_MISMATCH', 'channel mismatch')
    assert page.evaluate(ROW_VALUES, 'left') == before_row

    # Remove: refused while a Wire ends on the port, allowed otherwise.
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'left', 'port-remove').click()
    refused(page, h, c, 'PORT_IN_USE', 'remove in use')
    assert page.evaluate(ROWS) == ['left', 'right', 'top']
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'top', 'port-remove').click()
    assert page.evaluate(ROWS) == ['left', 'right']
    assert page.locator('.node[data-id="g"] circle.attachment-point[data-point="top"]').count() == 0
    one_transition(page, h, c, 'remove', 'g')

    # Add port: p1 on the right, at the first free position; then p2 at .25 (right's .5 is taken
    # by `right`), duplex on main. It is drawn and immediately wireable.
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    page.locator('#portsAddBtn').click()
    s = page.evaluate(STATE, 'g')
    assert s['specs'][-1] == {'id': 'p1', 'side': 'right', 't': .25, 'flow': 'duplex', 'channels': ['main'], 'label': None}, s['specs']
    assert page.evaluate(ROWS) == ['left', 'right', 'p1']
    one_transition(page, h, c, 'add p1', 'g')
    page.locator('#portsAddBtn').click()
    page.wait_for_timeout(450)
    s = page.evaluate(STATE, 'g')
    assert [(x['id'], x['side'], x['t']) for x in s['specs'][2:]] == [('p1', 'right', .25), ('p2', 'right', .75)], s['specs']
    assert page.locator('.node[data-id="g"] circle.attachment-point[data-point="p2"]').count() == 1
    d = page.evaluate(DRAWN, ['g', 'p2'])
    assert abs(d['cx'] - d['w'] / 2) < 8 and abs(d['cy'] - (-d['h'] / 2 + d['h'] * .75)) < 1.5, d
    # Wire it by a real drag from its ring to the Point q.
    hit = page.locator('.node[data-id="g"] .port-hit[data-point="p2"]').bounding_box()
    target = page.locator('.node[data-id="q"] .port-hit[data-point="self"]').bounding_box()
    wires_before = page.evaluate('()=>wires.length')
    page.mouse.move(hit['x'] + hit['width'] / 2, hit['y'] + hit['height'] / 2)
    page.mouse.down()
    page.mouse.move(hit['x'] + 40, hit['y'] + 30, steps=4)
    page.mouse.move(target['x'] + target['width'] / 2, target['y'] + target['height'] / 2, steps=8)
    page.mouse.up()
    page.wait_for_timeout(200)
    wired = page.evaluate("()=>wires.filter(w=>(w.a==='g'&&w.aAttachment?.pointId==='p2'&&w.b==='q')||(w.b==='g'&&w.bAttachment?.pointId==='p2'&&w.a==='q')).length")
    assert page.evaluate('()=>wires.length') == wires_before + 1 and wired == 1, page.evaluate('()=>wires.map(w=>[w.a,w.aAttachment,w.b,w.bAttachment])')
    # Now p2 carries a Wire: removing it is refused.
    open_panel(page, 'g')
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'p2', 'port-remove').click()
    refused(page, h, c, 'PORT_IN_USE', 'remove p2 in use')

    # A Plane starts with no ports; Add port gives it p1 at .5.
    page.evaluate("()=>{SovSchematicAPI.create('component',{id:'pl',symbolId:'plane',x:1000,y:220});render()}")
    open_panel(page, 'pl')
    assert page.evaluate(ROWS) == []
    page.locator('#portsAddBtn').click()
    s = page.evaluate(STATE, 'pl')
    assert s['specs'] == [{'id': 'p1', 'side': 'right', 't': .5, 'flow': 'duplex', 'channels': ['main'], 'label': None}], s

    # --- Step 4: definition-owned ports -----------------------------------------------------
    bound = page.evaluate("""(pack)=>{const S=SovSchematicStateSpace,packs=[S.loadPack(pack).pack];
      SovSchematicAPI.create('component',{id:'and',symbolId:'act',x:520,y:120});
      const rc=S.applyBind(diagram,'and','logic.and@1',packs);normalizeRuntimeAfterCrud();commitHistoryCapture('Bind');
      return {ok:rc.ok,err:rc.error}}""", PACK)
    assert bound['ok'], bound
    open_panel(page, 'and')
    assert page.evaluate(ROWS) == ['a', 'b', 'q']
    for pid in ('a', 'b', 'q'):
        for cls in ('port-id', 'port-flow', 'port-channels', 'port-remove'):
            el = row(page, pid, cls)
            assert el.is_disabled(), (pid, cls)
            assert 'logic.and@1' in (el.get_attribute('title') or ''), (pid, cls, el.get_attribute('title'))
        for cls in ('port-label', 'port-side', 'port-t'):
            assert row(page, pid, cls).is_enabled(), (pid, cls)
    assert page.locator('#portsAddBtn').is_disabled() and 'logic.and@1' in page.locator('#portsAddBtn').get_attribute('title')
    # Label, side and t stay editable, one transition each.
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'q', 'port-side').select_option('bottom')
    assert next(x for x in page.evaluate(STATE, 'and')['specs'] if x['id'] == 'q')['side'] == 'bottom'
    one_transition(page, h, c, 'bound side', 'and')
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'a', 'port-t').fill('0.3')
    row(page, 'a', 'port-t').press('Enter')
    assert next(x for x in page.evaluate(STATE, 'and')['specs'] if x['id'] == 'a')['t'] == .3
    one_transition(page, h, c, 'bound t', 'and')
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'b', 'port-label').fill('B in')
    row(page, 'b', 'port-label').press('Enter')
    assert next(x for x in page.evaluate(STATE, 'and')['specs'] if x['id'] == 'b')['label'] == 'B in'
    one_transition(page, h, c, 'bound label', 'and')
    assert page.evaluate("()=>nodes.find(n=>n.id==='and').config.definition") == 'logic.and@1'
    # The other Form controls cannot change its ports either.
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    page.locator('#formAttachments').select_option('standard')
    refused(page, h, c, 'DEFINITION_PORTS', 'bound attachments')
    assert page.evaluate('()=>formAttachments.value') == 'none'
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    page.locator('#formDimension').select_option('0')
    refused(page, h, c, 'DEFINITION_PORTS', 'bound dimension')
    assert page.evaluate('()=>formDimension.value') == '2'
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    page.locator('#barComponentType').select_option('gate')
    refused(page, h, c, 'DEFINITION_PORTS', 'bound retype')

    # --- Step 5: settling a bound Component on a Wire is refused ----------------------------
    page.evaluate('()=>{closeSelectionSettings()}')
    lane = page.evaluate("""()=>{const A=SovSchematicAPI;
      A.create('component',{id:'l1',symbolId:'point',x:200,y:620});A.create('component',{id:'l2',symbolId:'point',x:1200,y:620});
      A.create('wire',{id:'lane',a:'l1',aSide:'self',b:'l2',bSide:'self'});render();
      const path=renderedWirePath(wires.find(w=>w.id==='lane')),q=path.getPointAtLength(path.getTotalLength()*.5);return {x:q.x,y:q.y}}""")
    page.wait_for_timeout(450)
    start = page.evaluate(STATE, 'and')
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    grab = client(page, start['x'], start['y'])
    drop = client(page, lane['x'], lane['y'])
    page.mouse.move(grab['x'], grab['y'])
    page.mouse.down()
    page.mouse.move(grab['x'] + 20, grab['y'] + 20, steps=3)
    page.mouse.move(drop['x'], drop['y'], steps=10)
    page.wait_for_timeout(450)  # past the host dwell: the Wire is the armed candidate
    assert page.evaluate("()=>activeNodeDragState?.hostReady&&activeNodeDragState.hostCandidate?.kind") == 'wire'
    page.mouse.up()
    page.wait_for_timeout(200)
    after = page.evaluate(STATE, 'and')
    assert (after['x'], after['y'], after['canvasId'], after['placement']) == (start['x'], start['y'], start['canvasId'], start['placement']), (start, after)
    assert after['specs'] == start['specs'], after
    refused(page, h, c, 'DEFINITION_PORTS', 'settle on wire')
    # The same drag of an unbound Component settles it on the Wire (the guard is only the definition's).
    page.evaluate("()=>{SovSchematicAPI.create('component',{id:'free',symbolId:'act',x:520,y:900});render()}")
    free = page.evaluate(STATE, 'free')
    grab = client(page, free['x'], free['y'])
    page.mouse.move(grab['x'], grab['y'])
    page.mouse.down()
    page.mouse.move(grab['x'] + 20, grab['y'] - 20, steps=3)
    page.mouse.move(drop['x'], drop['y'], steps=10)
    page.wait_for_timeout(450)
    page.mouse.up()
    page.wait_for_timeout(200)
    assert page.evaluate(STATE, 'free')['placement'] == 'wire'
    # Moving the bound Component on its own surface is still an ordinary move.
    start = page.evaluate(STATE, 'and')
    grab = client(page, start['x'], start['y'])
    page.mouse.move(grab['x'], grab['y'])
    page.mouse.down()
    page.mouse.move(grab['x'] + 60, grab['y'] + 10, steps=6)
    page.mouse.up()
    page.wait_for_timeout(200)
    moved = page.evaluate(STATE, 'and')
    assert moved['x'] != start['x'] and moved['placement'] == 'surface' and moved['specs'] == start['specs'], moved

    # --- Amendment 1, steps 12-13: an arrow-key move is refused by the same hosting guard -------
    # A lane between two Points; the bound Component sits three grid steps above the lane's middle
    # run, clear of it, and Ctrl+ArrowDown moves it three grid steps (72px at the default grid, as
    # measured in this build), onto the lane, so the move would settle it on the Wire. Setup places
    # it; the click that selects it settles first.
    LANE_MID = "()=>{const p=renderedWirePath(wires.find(w=>w.id==='lane2')),q=p.getPointAtLength(p.getTotalLength()/2);return {x:q.x,y:q.y}}"
    page.evaluate("""()=>{const A=SovSchematicAPI,g=canvasGridSize;
      A.create('component',{id:'l3',symbolId:'point',x:26*g,y:36*g});A.create('component',{id:'l4',symbolId:'point',x:54*g,y:36*g});
      A.create('wire',{id:'lane2',a:'l3',aSide:'self',b:'l4',bSide:'self'});render()}""")
    mid = page.evaluate(LANE_MID)
    page.evaluate("([x,y])=>{const g=canvasGridSize,n=nodes.find(n=>n.id==='and');n.x=Math.round(x/g)*g;n.y=y-3*g;render()}", [mid['x'], mid['y']])
    page.wait_for_timeout(450)
    open_panel(page, 'and')
    page.evaluate('()=>closeSelectionSettings()')
    page.wait_for_timeout(450)
    start = page.evaluate(STATE, 'and')
    assert page.evaluate(LANE_MID) == mid and start['y'] + 3 * 24 == mid['y'], (page.evaluate(LANE_MID), mid, start['y'])
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    page.keyboard.press('Control+ArrowDown')
    page.wait_for_timeout(300)
    after = page.evaluate(STATE, 'and')
    assert (after['x'], after['y'], after['canvasId'], after['placement']) == (start['x'], start['y'], start['canvasId'], start['placement']), (start, after, status(page))
    assert after['specs'] == start['specs'], after
    refused(page, h, c, 'DEFINITION_PORTS', 'arrow-key settle on wire')
    # An unbound Component making the same move settles on the Wire: the guard is only the definition's.
    page.evaluate("([x,y])=>{const g=canvasGridSize;SovSchematicAPI.create('component',{id:'free2',symbolId:'act',x:Math.round(x/g)*g-10*g,y:y-3*g});render()}", [mid['x'], mid['y']])
    page.wait_for_timeout(450)
    open_panel(page, 'free2')
    page.evaluate('()=>closeSelectionSettings()')
    page.keyboard.press('Control+ArrowDown')
    page.wait_for_timeout(300)
    assert page.evaluate(STATE, 'free2')['placement'] == 'wire', page.evaluate(STATE, 'free2')
    # Settling into an open interior by arrow keys stays allowed: up into the Plane `pl` (open by preset).
    page.evaluate("()=>{const n=nodes.find(x=>x.id==='and');n.x=1008;n.y=432;render()}")
    page.wait_for_timeout(450)
    open_panel(page, 'and')
    page.evaluate('()=>closeSelectionSettings()')
    page.wait_for_timeout(450)
    start = page.evaluate(STATE, 'and')
    for _ in range(6):
        page.keyboard.press('Control+ArrowUp')
        page.wait_for_timeout(200)
        if page.evaluate(STATE, 'and')['canvasId'] != start['canvasId']:
            break
    inside = page.evaluate(STATE, 'and')
    assert inside['canvasId'] == 'canvas:component:pl' and inside['placement'] == 'surface' and inside['specs'] == start['specs'], inside
    assert 'DEFINITION_PORTS' not in status(page), status(page)

    # --- Step 9, the panel half: a Point's declared self survives an edit in its panel, save and reload.
    page.evaluate("""()=>{SovSchematicAPI.create('component',{id:'J',symbolId:'point',x:1100,y:420,
      config:{attachmentPoints:[{id:'self',flow:'in',channels:[{id:'main',merge:{combine:'or'}}]}]}});render()}""")
    declared = page.evaluate("()=>nodes.find(n=>n.id==='J').config.attachmentPoints")
    assert declared == [{'id': 'self', 'flow': 'in', 'channels': [{'id': 'main', 'merge': {'combine': 'or'}}]}], declared
    page.evaluate("()=>{selectPort('J','self');openSelectionSettings('port')}")
    page.locator('#barPortFace').select_option('both')
    page.wait_for_timeout(450)
    saved = page.evaluate("()=>SovSchematicAPI.file.document()")
    reopened = page.evaluate("(doc)=>{SovSchematicAPI.file.open(doc,'self.sov');const n=nodes.find(x=>x.id==='J');return {ap:n.config.attachmentPoints,face:n.config.ports.out.face}}", saved)
    assert reopened == {'ap': declared, 'face': 'both'}, reopened
    again = page.evaluate("()=>SovSchematicAPI.file.document()")
    assert next(x for x in again['components'] if x['id'] == 'J')['config']['attachmentPoints'] == declared

    assert not errors, errors
    browser.close()
    print('PASS ports panel QA')
