"""The editor's Ports panel (contract 0b-2, steps 1-5, the panel half of step 9, and amendments 1-2;
contract #50 step 7, the settings toggle clicked with an edit typed).

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
    # The selection bar of a selected port may lie over the Component too: clear that selection first.
    page.evaluate('()=>{closeSelectionSettings();if(isAttachmentSelectionValue(selected))selectNode(null)}')
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
    page.wait_for_timeout(60)  # a Ports edit runs once focus has settled (step 15)
    s = page.evaluate(STATE, 'g')
    assert [x['label'] for x in s['specs']] == [None, 'OUT', None], s
    assert s['mode'] == 'none', s  # a changed template port is stored as the full list
    assert page.locator('.node[data-id="g"] .port-label-text', has_text='OUT').count() == 1
    assert page.evaluate(ROW_VALUES, 'right')['label'] == 'OUT'
    one_transition(page, h, c, 'label', 'g')
    # Side: the canvas draws the port on its new side.
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'top', 'port-side').select_option('bottom')
    page.wait_for_timeout(60)  # a Ports edit runs once focus has settled (step 15)
    s = page.evaluate(STATE, 'g')
    assert next(x for x in s['specs'] if x['id'] == 'top')['side'] == 'bottom', s
    d = page.evaluate(DRAWN, ['g', 'top'])
    assert d['cy'] > d['h'] / 2 - 8 and abs(d['cx']) < 1, d
    one_transition(page, h, c, 'side', 'g')
    # Position t: the canvas draws it at its new position along the side.
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'top', 'port-t').fill('0.25')
    row(page, 'top', 'port-t').press('Enter')
    page.wait_for_timeout(60)  # a Ports edit runs once focus has settled (step 15)
    s = page.evaluate(STATE, 'g')
    assert next(x for x in s['specs'] if x['id'] == 'top')['t'] == .25, s
    d = page.evaluate(DRAWN, ['g', 'top'])
    assert abs(d['cx'] - (-d['w'] / 2 + d['w'] * .25)) < 1.5 and d['cy'] > 0, d
    one_transition(page, h, c, 't', 'g')
    # Flow.
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'top', 'port-flow').select_option('trigger')
    page.wait_for_timeout(60)  # a Ports edit runs once focus has settled (step 15)
    assert next(x for x in page.evaluate(STATE, 'g')['specs'] if x['id'] == 'top')['flow'] == 'trigger'
    one_transition(page, h, c, 'flow', 'g')
    # Channels: comma-separated ids.
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'top', 'port-channels').fill('main, aux')
    row(page, 'top', 'port-channels').press('Enter')
    page.wait_for_timeout(60)  # a Ports edit runs once focus has settled (step 15)
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
        page.wait_for_timeout(60)  # a Ports edit runs once focus has settled (step 15)
        refused(page, h, c, want, label)
        assert page.evaluate(ROW_VALUES, 'top') == before_row, (label, page.evaluate(ROW_VALUES, 'top'), before_row)
    # A channel edit that would leave the bound Wire between ports sharing no channel.
    before_row = page.evaluate(ROW_VALUES, 'left')
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'left', 'port-channels').fill('aux')
    row(page, 'left', 'port-channels').press('Enter')
    page.wait_for_timeout(60)  # a Ports edit runs once focus has settled (step 15)
    refused(page, h, c, 'CHANNEL_MISMATCH', 'channel mismatch')
    assert page.evaluate(ROW_VALUES, 'left') == before_row

    # Remove: refused while a Wire ends on the port, allowed otherwise.
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'left', 'port-remove').click()
    page.wait_for_timeout(60)  # the rows are rebuilt after the edit's event (step 25)
    refused(page, h, c, 'PORT_IN_USE', 'remove in use')
    assert page.evaluate(ROWS) == ['left', 'right', 'top']
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'top', 'port-remove').click()
    page.wait_for_timeout(60)  # the rows are rebuilt after the edit's event (step 25)
    assert page.evaluate(ROWS) == ['left', 'right']
    assert page.locator('.node[data-id="g"] circle.attachment-point[data-point="top"]').count() == 0
    one_transition(page, h, c, 'remove', 'g')

    # Add port: p1 on the right, at the first free position; then p2 at .25 (right's .5 is taken
    # by `right`), duplex on main. It is drawn and immediately wireable.
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    page.locator('#portsAddBtn').click()
    page.wait_for_timeout(60)  # the rows are rebuilt after the edit's event (step 25)
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
    page.wait_for_timeout(60)  # the rows are rebuilt after the edit's event (step 25)
    refused(page, h, c, 'PORT_IN_USE', 'remove p2 in use')

    # A Plane starts with no ports; Add port gives it p1 at .5.
    page.evaluate("()=>{SovSchematicAPI.create('component',{id:'pl',symbolId:'plane',x:1000,y:220});render()}")
    open_panel(page, 'pl')
    assert page.evaluate(ROWS) == []
    page.locator('#portsAddBtn').click()
    page.wait_for_timeout(60)  # the rows are rebuilt after the edit's event (step 25)
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
    page.wait_for_timeout(60)  # a Ports edit runs once focus has settled (step 15)
    assert next(x for x in page.evaluate(STATE, 'and')['specs'] if x['id'] == 'q')['side'] == 'bottom'
    one_transition(page, h, c, 'bound side', 'and')
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'a', 'port-t').fill('0.3')
    row(page, 'a', 'port-t').press('Enter')
    page.wait_for_timeout(60)  # a Ports edit runs once focus has settled (step 15)
    assert next(x for x in page.evaluate(STATE, 'and')['specs'] if x['id'] == 'a')['t'] == .3
    one_transition(page, h, c, 'bound t', 'and')
    h, c = page.evaluate(HASH), page.evaluate(UNDO_COUNT)
    row(page, 'b', 'port-label').fill('B in')
    row(page, 'b', 'port-label').press('Enter')
    page.wait_for_timeout(60)  # a Ports edit runs once focus has settled (step 15)
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

    # --- Amendment 2 --------------------------------------------------------------------------
    BIND = """([pack,id])=>{const S=SovSchematicStateSpace,packs=[S.loadPack(pack).pack];const rc=S.applyBind(diagram,id,'logic.and@1',packs);
      normalizeRuntimeAfterCrud();commitHistoryCapture('Bind');return rc.ok}"""
    PLACE = """(id)=>{const n=nodes.find(x=>x.id===id);return {x:Math.round(n.x),y:Math.round(n.y),canvasId:n.canvasId,parentId:n.parentId,
      placement:n.placement?.kind??'surface',ports:Attachment.pointSpecs(n).map(s=>s.id)}}"""

    def fresh():
        pg = browser.new_page(viewport={'width': 1400, 'height': 900})
        pg.on('pageerror', lambda exc: errors.append(str(exc)))
        pg.set_content(HTML, wait_until='load')
        pg.wait_for_timeout(300)
        pg.evaluate('newSchematic()')
        return pg

    def drag(pg, fx, fy, tx, ty):
        g, d = client(pg, fx, fy), client(pg, tx, ty)
        pg.mouse.move(g['x'], g['y'])
        pg.mouse.down()
        pg.mouse.move(g['x'] + 12, g['y'] + 12, steps=3)
        pg.mouse.move(d['x'], d['y'], steps=14)
        pg.wait_for_timeout(600)  # past the host dwell
        armed = pg.evaluate("()=>activeNodeDragState&&activeNodeDragState.hostCandidate?.kind")
        pg.mouse.up()
        pg.wait_for_timeout(500)
        return armed

    # Step 14: the review's case. An unbound `pl` on a Wire with its interior open hosts a bound `and`;
    # closing pl's interior, retyping pl, changing its dimension or deleting it would make `and` fall
    # back onto the Wire's canvas (ports start/end). Each is refused: nothing changes, no history.
    for mode in ('interior', 'retype', 'dimension', 'delete'):
        pg = fresh()
        pg.evaluate("""()=>{const A=SovSchematicAPI;
          A.create('component',{id:'pl',symbolId:'act',x:720,y:300});A.create('component',{id:'and',symbolId:'act',x:300,y:250});
          A.create('component',{id:'l1',symbolId:'point',x:200,y:620});A.create('component',{id:'l2',symbolId:'point',x:1200,y:620});
          A.create('wire',{id:'lane',a:'l1',aSide:'self',b:'l2',bSide:'self'});render()}""")
        assert pg.evaluate(BIND, [PACK, 'and'])
        pg.wait_for_timeout(450)
        lane = pg.evaluate("()=>{const p=renderedWirePath(wires.find(x=>x.id==='lane')),q=p.getPointAtLength(p.getTotalLength()*.5);return {x:q.x,y:q.y}}")
        pl = pg.evaluate(PLACE, 'pl')
        assert drag(pg, pl['x'], pl['y'] + 25, lane['x'], lane['y'] + 25) == 'wire'
        assert pg.evaluate(PLACE, 'pl')['placement'] == 'wire'
        pg.evaluate("()=>{selectNode('pl');openSelectionSettings('component')}")
        pg.locator('#formInteriorState').select_option('open')
        pg.wait_for_timeout(450)
        pg.evaluate('()=>closeSelectionSettings()')
        pl, a = pg.evaluate(PLACE, 'pl'), pg.evaluate(PLACE, 'and')
        assert drag(pg, a['x'], a['y'] + 25, pl['x'], pl['y'] + 25) == 'component'
        inside = pg.evaluate(PLACE, 'and')
        assert inside['canvasId'] == 'canvas:component:pl' and inside['ports'] == ['a', 'b', 'q'], inside
        pg.wait_for_timeout(450)
        # `pl` sits across the Wire, which takes clicks on its middle: it is selected as the review's
        # probe selects it; the edits below are made through the real controls.
        pg.evaluate("()=>{selectNode('pl');openSelectionSettings('component')}")
        pg.wait_for_timeout(450)
        h, c = pg.evaluate(HASH), pg.evaluate(UNDO_COUNT)
        before = (pg.evaluate(PLACE, 'pl'), pg.evaluate("()=>SovSchematicData.clone(nodes.find(n=>n.id==='pl').form)"), pg.evaluate("()=>nodes.find(n=>n.id==='pl').symbolId"))
        if mode == 'interior':
            pg.locator('#formInteriorState').select_option('closed')
        elif mode == 'retype':
            pg.locator('#barComponentType').select_option('gate')
        elif mode == 'dimension':
            pg.locator('#formDimension').select_option('1')
        else:
            pg.locator('#barDeleteSelection').click()
        pg.wait_for_timeout(450)
        assert pg.evaluate(PLACE, 'and') == inside, (mode, pg.evaluate(PLACE, 'and'))
        after = (pg.evaluate(PLACE, 'pl'), pg.evaluate("()=>SovSchematicData.clone(nodes.find(n=>n.id==='pl')?.form??null)"), pg.evaluate("()=>nodes.find(n=>n.id==='pl')?.symbolId??null"))
        assert after == before, (mode, after, before)
        refused(pg, h, c, 'DEFINITION_PORTS', f'child fallback by {mode}')
        if mode == 'interior':
            assert pg.evaluate('()=>formInteriorState.value') == 'open'
        elif mode == 'retype':
            assert pg.evaluate('()=>barComponentType.value') == 'act'
        elif mode == 'dimension':
            assert pg.evaluate('()=>formDimension.value') == '2'
        # An unbound child falls back as before: with `and` unbound, the same edit goes through.
        if mode == 'interior':
            pg.evaluate("()=>{SovSchematicAPI.update('component','and',{config:{definition:null}})}")
            pg.wait_for_timeout(450)
            pg.evaluate("()=>{selectNode('pl');openSelectionSettings('component')}")
            pg.locator('#formInteriorState').select_option('closed')
            pg.wait_for_timeout(450)
            assert pg.evaluate(PLACE, 'and')['canvasId'] == 'canvas:wire:lane', pg.evaluate(PLACE, 'and')
        pg.close()

    pg = fresh()
    pg.evaluate("""()=>{const A=SovSchematicAPI;A.create('component',{id:'g',symbolId:'act',x:520,y:360});
      A.create('component',{id:'src',symbolId:'point',x:220,y:360});A.create('wire',{id:'w',a:'src',aSide:'self',b:'g',bAttachment:{pointId:'left'}});render()}""")
    pg.wait_for_timeout(300)
    open_panel(pg, 'g')

    # Step 15: Tab through a row, typing into each text field in turn; every edit lands and focus
    # moves on as a user expects, even though each edit rebuilds the rows.
    FOCUS = "()=>{const a=document.activeElement,r=a?.closest?.('.ports-row');return r?[r.dataset.portId,[...a.classList].find(c=>c.startsWith('port-'))]:a?.id||a?.tagName}"
    c = pg.evaluate(UNDO_COUNT)
    row(pg, 'top', 'port-label').click()
    pg.keyboard.type('Gate')
    pg.keyboard.press('Tab')
    pg.wait_for_timeout(120)
    assert pg.evaluate(FOCUS) == ['top', 'port-side'], pg.evaluate(FOCUS)
    pg.keyboard.press('Tab')
    pg.wait_for_timeout(120)
    assert pg.evaluate(FOCUS) == ['top', 'port-t'], pg.evaluate(FOCUS)
    pg.keyboard.press('Control+a')
    pg.keyboard.type('0.3')
    pg.keyboard.press('Tab')
    pg.wait_for_timeout(120)
    assert pg.evaluate(FOCUS) == ['top', 'port-flow'], pg.evaluate(FOCUS)
    pg.keyboard.press('Tab')
    pg.wait_for_timeout(120)
    assert pg.evaluate(FOCUS) == ['top', 'port-channels'], pg.evaluate(FOCUS)
    pg.keyboard.press('Control+a')
    pg.keyboard.type('main, aux')
    pg.keyboard.press('Shift+Tab')
    pg.wait_for_timeout(120)
    assert pg.evaluate(FOCUS) == ['top', 'port-flow'], pg.evaluate(FOCUS)
    pg.wait_for_timeout(450)
    top = next(x for x in pg.evaluate(STATE, 'g')['specs'] if x['id'] == 'top')
    assert (top['label'], top['t'], top['channels']) == ('Gate', .3, ['main', 'aux']), top
    assert pg.evaluate(UNDO_COUNT) == c + 3, pg.evaluate('()=>historyState.undo.map(x=>x.label)')

    # Step 16: one label, written from the panel and from the bar, read the same by both.
    LABELS = "(pid)=>{const n=nodes.find(x=>x.id==='g'),s=Attachment.resolveSpec(n,pid);return [s.label??null,n.config.ports[s.compatId].label]}"
    DRAWN_LABELS = "()=>[...document.querySelectorAll('.node[data-id=\"g\"] .port-label-text')].map(x=>x.textContent)"
    row(pg, 'right', 'port-label').fill('P1')
    row(pg, 'right', 'port-label').press('Enter')
    pg.wait_for_timeout(120)
    assert pg.evaluate(LABELS, 'right') == ['P1', 'P1'] and 'P1' in pg.evaluate(DRAWN_LABELS)
    pg.evaluate("()=>{closeSelectionSettings();selectPort('g','right');openSelectionSettings('port')}")
    assert pg.evaluate('()=>barPortLabel.value') == 'P1'
    h, c = pg.evaluate(HASH), pg.evaluate(UNDO_COUNT)
    pg.locator('#barPortLabel').fill('B1')
    pg.locator('#barPortLabel').press('Enter')
    pg.wait_for_timeout(120)
    assert pg.evaluate(LABELS, 'right') == ['B1', 'B1'] and 'B1' in pg.evaluate(DRAWN_LABELS), pg.evaluate(LABELS, 'right')
    one_transition(pg, h, c, 'bar label', 'g')
    assert row(pg, 'right', 'port-label').input_value() == 'B1'
    row(pg, 'right', 'port-label').fill('P2')
    row(pg, 'right', 'port-label').press('Enter')
    pg.wait_for_timeout(120)
    assert pg.evaluate(LABELS, 'right') == ['P2', 'P2']
    pg.evaluate("()=>{closeSelectionSettings();selectPort('g','right');openSelectionSettings('port')}")
    assert pg.evaluate('()=>barPortLabel.value') == 'P2'
    # Clearing it from the bar clears both.
    pg.locator('#barPortLabel').fill('')
    pg.locator('#barPortLabel').press('Enter')
    pg.wait_for_timeout(120)
    assert pg.evaluate(LABELS, 'right') == [None, ''], pg.evaluate(LABELS, 'right')

    # Step 17: one flow, the declared flow, set from either side, `trigger` included.
    FLOW = "(pid)=>{const n=nodes.find(x=>x.id==='g'),s=Attachment.resolveSpec(n,pid);return s.flow}"
    assert pg.evaluate("()=>[...barPortFlow.options].map(o=>o.value)") == ['in', 'out', 'duplex', 'control', 'trigger']
    open_panel(pg, 'g')
    row(pg, 'top', 'port-flow').select_option('trigger')
    pg.wait_for_timeout(120)
    assert pg.evaluate(FLOW, 'top') == 'trigger'
    pg.evaluate("()=>{closeSelectionSettings();selectPort('g','top');openSelectionSettings('port')}")
    assert pg.evaluate('()=>barPortFlow.value') == 'trigger'
    h, c = pg.evaluate(HASH), pg.evaluate(UNDO_COUNT)
    pg.locator('#barPortFlow').select_option('duplex')
    pg.wait_for_timeout(120)
    assert pg.evaluate(FLOW, 'top') == 'duplex' and pg.evaluate("()=>nodes.find(x=>x.id==='g').config.ports.control.flow") == 'duplex'
    one_transition(pg, h, c, 'bar flow', 'g')
    assert row(pg, 'top', 'port-flow').input_value() == 'duplex'
    pg.evaluate("()=>{closeSelectionSettings();selectPort('g','top');openSelectionSettings('port')}")
    pg.locator('#barPortFlow').select_option('trigger')
    pg.wait_for_timeout(120)
    assert pg.evaluate(FLOW, 'top') == 'trigger' and pg.evaluate('()=>barPortFlow.value') == 'trigger'
    open_panel(pg, 'g')
    assert row(pg, 'top', 'port-flow').input_value() == 'trigger'
    # A Component with no declared list: a bar change stores the list in the smallest form.
    pg.evaluate("()=>{SovSchematicAPI.create('component',{id:'h',symbolId:'act',x:900,y:600});render();closeSelectionSettings();selectPort('h','right');openSelectionSettings('port')}")
    pg.locator('#barPortFlow').select_option('duplex')
    pg.wait_for_timeout(120)
    hs = pg.evaluate(STATE, 'h')
    assert hs['mode'] == 'none' and [x['flow'] for x in hs['specs']] == ['in', 'duplex', 'control'], hs
    pg.evaluate("()=>{selectPort('h','right');openSelectionSettings('port')}")
    pg.locator('#barPortFlow').select_option('out')
    pg.wait_for_timeout(120)
    hs = pg.evaluate(STATE, 'h')
    assert hs['mode'] is None and hs['stored'] is None, hs  # back to the template: stored as nothing
    # A Point's self: the bar writes its declared flow.
    pg.evaluate("()=>{closeSelectionSettings();selectPort('src','self');openSelectionSettings('port')}")
    pg.locator('#barPortFlow').select_option('in')
    pg.wait_for_timeout(120)
    assert pg.evaluate("()=>nodes.find(x=>x.id==='src').config.attachmentPoints") == [{'id': 'self', 'flow': 'in', 'channels': [{'id': 'main'}]}]
    assert pg.evaluate('()=>barPortFlow.value') == 'in'

    # Step 18: the Attachments control says what it means.
    open_panel(pg, 'g')
    assert pg.evaluate("()=>[...formAttachments.options].map(o=>[o.value,o.textContent])") == [['standard', 'Template ports'], ['none', 'Custom ports']]
    assert pg.evaluate('()=>formAttachments.value') == 'none'  # g's ports differ from its template
    pg.locator('#formAttachments').select_option('standard')
    pg.wait_for_timeout(120)
    assert status(pg) == 'Reset to template ports', status(pg)

    # Step 19: ten added ports all sit at distinct positions on the right side.
    pg.evaluate("()=>{SovSchematicAPI.create('component',{id:'ten',symbolId:'plane',x:900,y:260});render()}")
    open_panel(pg, 'ten')
    for _ in range(10):
        pg.locator('#portsAddBtn').click()
        pg.wait_for_timeout(60)
    ts = [x['t'] for x in pg.evaluate(STATE, 'ten')['specs']]
    assert len(ts) == 10 and len(set(ts)) == 10 and all(0 < t < 1 for t in ts), ts
    assert ts[:7] == [.5, .25, .75, .125, .375, .625, .875] and ts[7:] == [.0625, .1875, .3125], ts
    pg.close()

    # --- Amendment 3 --------------------------------------------------------------------------
    pg = fresh()
    # On the grid (24), so the clicks that select them do not also snap them into a history entry.
    pg.evaluate("""()=>{const A=SovSchematicAPI;A.create('component',{id:'g',symbolId:'act',x:432,y:360});
      A.create('component',{id:'k',symbolId:'act',x:168,y:768});A.create('component',{id:'pt',symbolId:'point',x:912,y:696});render()}""")
    pg.wait_for_timeout(300)
    K_UNTOUCHED = pg.evaluate("()=>JSON.stringify(nodes.find(n=>n.id==='k').config)")

    def click_k(pg):
        """A real click on the other Component `k`; it must be what lies under the pointer."""
        k = pg.evaluate("()=>{const n=nodes.find(x=>x.id==='k');return {x:n.x-30,y:n.y+20}}")
        c = client(pg, k['x'], k['y'])
        assert pg.evaluate("([x,y])=>document.elementFromPoint(x,y)?.closest('.node')?.dataset.id", [c['x'], c['y']]) == 'k'
        pg.mouse.click(c['x'], c['y'])
        pg.wait_for_timeout(450)

    # Step 21 (probe22), for each panel field: edit g's port, then click k before the edit has run.
    # The edit lands on g's port, k is untouched, and there is one history entry.
    for label, cls, value, check in (
        ('label', 'port-label', 'XG', lambda s: s['label'] == 'XG'),
        ('t', 'port-t', '0.35', lambda s: s['t'] == .35),
        ('channels', 'port-channels', 'main, bus', lambda s: s['channels'] == ['main', 'bus']),
        ('side', 'port-side', 'bottom', lambda s: s['side'] == 'bottom'),
        ('flow', 'port-flow', 'trigger', lambda s: s['flow'] == 'trigger'),
    ):
        open_panel(pg, 'g')
        c = pg.evaluate(UNDO_COUNT)
        if cls in ('port-side', 'port-flow'):
            row(pg, 'right', cls).select_option(value)
        else:
            row(pg, 'right', cls).fill(value)
        click_k(pg)
        assert pg.evaluate('()=>selected') == 'k', (label, pg.evaluate('()=>selected'))
        spec = next(x for x in pg.evaluate(STATE, 'g')['specs'] if x['id'] == 'right')
        assert check(spec), (label, spec)
        assert pg.evaluate("()=>JSON.stringify(nodes.find(n=>n.id==='k').config)") == K_UNTOUCHED, label
        assert pg.evaluate(UNDO_COUNT) == c + 1, (label, pg.evaluate('()=>historyState.undo.map(x=>x.label)'))

    # Step 22 (probe23): type in the bar's label, then click k. The edit lands on g's port, once.
    pg.evaluate("()=>{selectNode(null);selectPort('g','top');openSelectionSettings('port')}")
    c = pg.evaluate(UNDO_COUNT)
    pg.locator('#barPortLabel').click()
    pg.keyboard.press('Control+a')
    pg.keyboard.type('Bar-g')
    click_k(pg)
    assert pg.evaluate("()=>{const n=nodes.find(x=>x.id==='g'),s=Attachment.resolveSpec(n,'top');return [s.label??null,n.config.ports.control.label]}") == ['Bar-g', 'Bar-g']
    assert pg.evaluate("()=>JSON.stringify(nodes.find(n=>n.id==='k').config)") == K_UNTOUCHED
    assert pg.evaluate(UNDO_COUNT) == c + 1, pg.evaluate('()=>historyState.undo.map(x=>x.label)')
    # Leaving by Tab commits it too, once.
    pg.evaluate("()=>{selectNode(null);selectPort('g','top');openSelectionSettings('port')}")
    c = pg.evaluate(UNDO_COUNT)
    pg.locator('#barPortLabel').click()
    pg.keyboard.press('Control+a')
    pg.keyboard.type('Tabbed')
    pg.keyboard.press('Tab')
    pg.wait_for_timeout(450)
    assert pg.evaluate("()=>nodes.find(x=>x.id==='g').config.ports.control.label") == 'Tabbed'
    assert pg.evaluate(UNDO_COUNT) == c + 1

    # Step 23: a Point with no declared flow shows duplex in the bar and the inspector; choosing out stores it.
    pg.evaluate("()=>{selectNode(null);selectPort('pt','self');openSelectionSettings('port')}")
    assert pg.evaluate("()=>nodes.find(x=>x.id==='pt').config.attachmentPoints??null") is None
    assert pg.evaluate('()=>barPortFlow.value') == 'duplex'
    assert pg.locator('#pFlow').inner_text() == 'Input + Output', pg.locator('#pFlow').inner_text()
    pg.locator('#barPortFlow').select_option('out')
    pg.wait_for_timeout(200)
    assert pg.evaluate("()=>nodes.find(x=>x.id==='pt').config.attachmentPoints") == [{'id': 'self', 'flow': 'out', 'channels': [{'id': 'main'}]}]
    assert pg.evaluate('()=>barPortFlow.value') == 'out' and pg.locator('#pFlow').inner_text() == 'Output'

    # Undo and redo right after a deferred edit: the edit has landed first, and both restore exactly.
    open_panel(pg, 'g')
    h, c = pg.evaluate(HASH), pg.evaluate(UNDO_COUNT)
    row(pg, 'left', 'port-label').fill('U1')
    row(pg, 'left', 'port-label').press('Enter')
    pg.locator('#quickUndoBtn').click()
    pg.wait_for_timeout(200)
    assert pg.evaluate(HASH) == h and pg.evaluate(UNDO_COUNT) == c, 'undo right after a deferred edit'
    pg.locator('#quickRedoBtn').click()
    pg.wait_for_timeout(200)
    assert pg.evaluate("()=>nodes.find(x=>x.id==='g').config.ports.in.label") == 'U1' and pg.evaluate(UNDO_COUNT) == c + 1

    # An edit whose Component is deleted before it runs is dropped, and the status line says so. The
    # deletion is made in the same task as the change, which is the only way to beat the deferral.
    pg.evaluate("()=>{SovSchematicAPI.create('component',{id:'gone',symbolId:'act',x:700,y:200});render()}")
    open_panel(pg, 'gone')
    row(pg, 'right', 'port-label').fill('late')
    pg.evaluate("""()=>{const el=document.querySelector('#portsList .ports-row[data-port-id="right"] .port-label');
      el.dispatchEvent(new Event('change',{bubbles:true}));SovSchematicAPI.delete('component','gone')}""")
    pg.wait_for_timeout(200)
    assert status(pg) == 'Port edit dropped: gone no longer exists', status(pg)
    assert pg.evaluate("()=>nodes.some(n=>n.id==='gone')") is False
    pg.close()

    # --- Amendment 4: an edit is never pending --------------------------------------------------
    HIST = '()=>historyState.undo.map(x=>x.label)'
    G_RIGHT = "()=>{const n=nodes.find(x=>x.id==='g');return [Attachment.resolveSpec(n,'right').label??null,n.config.ports.out.label]}"

    def a4_page():
        pg = fresh()
        pg.evaluate("""()=>{const A=SovSchematicAPI;A.create('component',{id:'g',symbolId:'act',x:432,y:360});
          A.create('component',{id:'k',symbolId:'act',x:168,y:768});
          A.create('component',{id:'R',symbolId:'act',x:912,y:768,form:{dimension:1}});render()}""")
        pg.wait_for_timeout(300)
        return pg

    def drag_g(pg, dx, dy):
        n = pg.evaluate("()=>{const n=nodes.find(x=>x.id==='g');return {x:n.x,y:n.y}}")
        a, b = client(pg, n['x'] - 36, n['y'] + 24), client(pg, n['x'] - 36 + dx, n['y'] + 24 + dy)
        assert pg.evaluate("([x,y])=>document.elementFromPoint(x,y)?.closest('.node')?.dataset.id", [a['x'], a['y']]) == 'g'
        pg.mouse.move(a['x'], a['y'])
        pg.mouse.down()
        pg.mouse.move(a['x'] - 10, a['y'] - 10, steps=2)
        pg.mouse.move(b['x'], b['y'], steps=8)
        pg.mouse.up()
        pg.wait_for_timeout(500)
        return n

    # probe26: type in g's label (no Enter), then click Undo. The label edit is committed first and
    # Undo removes exactly it; Redo restores it.
    pg = a4_page()
    open_panel(pg, 'g')
    h0, c0, hist0 = pg.evaluate(HASH), pg.evaluate(UNDO_COUNT), pg.evaluate(HIST)
    row(pg, 'right', 'port-label').fill('U2')
    pg.locator('#quickUndoBtn').click()
    pg.wait_for_timeout(300)
    assert pg.evaluate(HASH) == h0 and pg.evaluate(HIST) == hist0, (pg.evaluate(HIST), hist0)
    assert pg.evaluate('()=>historyState.redo.length') == 1 and pg.evaluate(G_RIGHT) == [None, '']
    pg.locator('#quickRedoBtn').click()
    pg.wait_for_timeout(300)
    assert pg.evaluate(G_RIGHT) == ['U2', 'U2'] and pg.evaluate(UNDO_COUNT) == c0 + 1 and pg.evaluate(HIST)[-1] == 'Relabel port'
    pg.close()

    # probe27, panel and bar: with an edit typed, dragging g 200px moves it; the history holds the
    # label entry, then one Move entry.
    for where in ('panel', 'bar'):
        pg = a4_page()
        if where == 'panel':
            open_panel(pg, 'g')
            row(pg, 'right', 'port-label').fill('D1')
        else:
            pg.evaluate("()=>{selectPort('g','right');openSelectionSettings('port')}")
            pg.wait_for_timeout(150)
            pg.locator('#barPortLabel').click()
            pg.keyboard.press('Control+a')
            pg.keyboard.type('D1')
        c = pg.evaluate(UNDO_COUNT)
        before = drag_g(pg, -200, 200)
        after = pg.evaluate("()=>{const n=nodes.find(x=>x.id==='g');return {x:n.x,y:n.y}}")
        assert abs(after['x'] - (before['x'] - 200)) <= 24 and abs(after['y'] - (before['y'] + 200)) <= 24, (where, before, after)
        assert pg.evaluate(G_RIGHT) == ['D1', 'D1'], (where, pg.evaluate(G_RIGHT))
        assert pg.evaluate(HIST)[-2:] == ['Relabel port', 'Move Component'] and pg.evaluate(UNDO_COUNT) == c + 2, (where, pg.evaluate(HIST))
        pg.close()

    # An edit committed by Save: the saved file carries it.
    pg = a4_page()
    open_panel(pg, 'g')
    row(pg, 'right', 'port-label').fill('Saved')
    pg.locator('#fileBtn').click()
    with pg.expect_download() as info:
        pg.locator('#fileSaveBtn').click()
    saved = json.loads(Path(info.value.path()).read_text(encoding='utf-8'))
    doc = saved.get('document', saved)
    g_saved = next(c for c in doc['components'] if c['id'] == 'g')
    assert g_saved['config']['ports']['out']['label'] == 'Saved' and any(p.get('label') == 'Saved' for p in g_saved['config']['attachmentPoints']), g_saved['config']
    # An edit committed by Delete of another Component: selecting k commits it, then k is deleted.
    open_panel(pg, 'g')
    row(pg, 'right', 'port-label').fill('Kept')
    c = pg.evaluate(UNDO_COUNT)
    k = pg.evaluate("()=>{const n=nodes.find(x=>x.id==='k');return {x:n.x-30,y:n.y+20}}")
    kc = client(pg, k['x'], k['y'])
    pg.mouse.click(kc['x'], kc['y'])
    pg.wait_for_timeout(450)
    assert pg.evaluate('()=>selected') == 'k'
    pg.locator('#barDeleteSelection').click()
    pg.wait_for_timeout(300)
    assert pg.evaluate("()=>nodes.some(n=>n.id==='k')") is False and pg.evaluate(G_RIGHT) == ['Kept', 'Kept']
    assert pg.evaluate(HIST)[-2:] == ['Relabel port', 'Delete Component'] and pg.evaluate(UNDO_COUNT) == c + 2, pg.evaluate(HIST)

    # Step 26: a Path end's Direction shows its effective flow and is disabled, with a title saying why.
    for pid, flow, text in (('start', 'in', 'Input'), ('end', 'out', 'Output')):
        pg.evaluate("(pid)=>{selectNode(null);selectPort('R',pid);openSelectionSettings('port')}", pid)
        pg.wait_for_timeout(100)
        assert pg.evaluate('()=>barPortFlow.value') == flow and pg.locator('#pFlow').inner_text() == text, pid
        assert pg.locator('#barPortFlow').is_disabled() and 'role' in pg.locator('#barPortFlow').get_attribute('title'), pid
    # A 2D port's Direction stays editable.
    pg.evaluate("()=>{selectNode(null);selectPort('g','right');openSelectionSettings('port')}")
    assert pg.locator('#barPortFlow').is_enabled()
    pg.close()

    # Contract #50 step 7: with a Ports edit typed (not committed), a real click on the bar's settings
    # toggle commits the edit, once, and closes the panel. The deferred refresh rebuilds only a panel
    # that is still open and never opens one: the panel stays closed after it has run.
    pg = a4_page()
    open_panel(pg, 'g')
    c = pg.evaluate(UNDO_COUNT)
    row(pg, 'right', 'port-label').fill('Closed')
    pg.locator('#barSelectionSettings').click()
    pg.wait_for_timeout(450)
    assert pg.evaluate(G_RIGHT) == ['Closed', 'Closed'], pg.evaluate(G_RIGHT)
    assert pg.evaluate(HIST)[-1] == 'Relabel port' and pg.evaluate(UNDO_COUNT) == c + 1, pg.evaluate(HIST)
    assert pg.evaluate('()=>selectionSettingsPanel.hidden') is True, 'the settings toggle did not close the panel'
    assert pg.evaluate("()=>barSelectionSettings.getAttribute('aria-expanded')") == 'false'
    assert pg.evaluate('()=>selected') == 'g' and pg.evaluate('()=>!selectionBar.hidden')
    # The same edit with the panel left open: the refresh rebuilds the open panel, which shows the edit.
    open_panel(pg, 'g')
    row(pg, 'right', 'port-label').fill('Open')
    row(pg, 'right', 'port-label').press('Tab')
    pg.wait_for_timeout(450)
    assert pg.evaluate('()=>!selectionSettingsPanel.hidden') and row(pg, 'right', 'port-label').input_value() == 'Open'
    assert pg.evaluate(G_RIGHT) == ['Open', 'Open'], pg.evaluate(G_RIGHT)
    # A refresh that runs after the panel was closed by other means leaves it closed.
    pg.evaluate("""()=>{const n=nodes.find(x=>x.id==='g');setComponentPortLabel(n,'right','Late');closeSelectionSettings()}""")
    pg.wait_for_timeout(300)
    assert pg.evaluate(G_RIGHT) == ['Late', 'Late'] and pg.evaluate('()=>selectionSettingsPanel.hidden') is True
    pg.close()

    assert not errors, errors
    browser.close()
    print('PASS ports panel QA')
