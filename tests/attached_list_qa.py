"""The Attachments selector is an Attached list (issue #21).

The Form section used to carry a switch over a template rule ("Template ports" or "Custom ports").
What the user needs to see is what is attached: every port with the Wires that end on it, then every
Point hosted on the boundary, each row selecting its point. "Reset to template ports" is the one
control over the template's ports, through the same update as any port edit. `attachmentDefaults`
stays in the file and out of the UI. Driven through the real controls.
"""
from __future__ import annotations
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')

ROWS = "()=>[...document.querySelectorAll('#portsList .ports-row')].map(r=>[r.dataset.portId,r.querySelector('.port-attached').textContent])"
HOSTED = """()=>[...document.querySelectorAll('#portsList .hosted-row')].map(r=>({id:r.dataset.pointComponentId,
  side:r.querySelector('.port-side').value,t:Number(r.querySelector('.port-t').value),flow:r.querySelector('.port-flow').value,
  channels:r.querySelector('.port-channels').value,attached:r.querySelector('.port-attached').textContent,
  readonly:[...r.querySelectorAll('input')].every(i=>i.readOnly)}))"""
STATE = "(id)=>{const n=nodes.find(x=>x.id===id);return {mode:n.config.attachmentDefaults??null,stored:n.config.attachmentPoints??null,ids:Attachment.pointSpecs(n).map(s=>s.id)}}"
UNDO_COUNT = '()=>historyState.undo.length'


def open_panel(page, cid):
    page.evaluate("(id)=>{closeSelectionSettings();selectNode(id);openSelectionSettings('component');formSettings.open=true}", cid)
    page.wait_for_timeout(150)


with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(300)
    page.evaluate('newSchematic()')
    scene = page.evaluate("""()=>{const A=SovSchematicAPI;
      A.create('component',{id:'g',symbolId:'act',x:640,y:400});
      A.create('component',{id:'src',symbolId:'point',x:220,y:400});
      A.create('component',{id:'dst',symbolId:'point',x:1060,y:300});
      A.create('component',{id:'pl',symbolId:'plane',x:640,y:720});
      const w=A.create('wire',{id:'w',a:'src',aSide:'self',b:'g',bAttachment:{pointId:'left'},config:{label:'feed'}});
      // A Point hosted on g's right edge (the settle gesture's own hosting step, on the live record),
      // and a Wire from it.
      A.create('component',{id:'hp',symbolId:'point',x:700,y:400});
      const hp=nodes.find(n=>n.id==='hp'),g=nodes.find(n=>n.id==='g'),s=componentSize(g),c=componentHostCandidateAtPoint(hp,g.x+s.w/2,g.y+6);applyComponentHost(hp,c);
      const k=A.create('wire',{id:'k',a:'hp',aSide:'self',b:'dst',bSide:'self'});
      render();return {w:w.ok,k:k.ok,host:hp.placement?.kind,hostId:hp.placement?.hostId,side:hp.placement?.side}}""")
    assert scene['w'] and scene['k'] and scene['host'] == 'edge' and scene['hostId'] == 'g' and scene['side'] == 'right', scene
    page.wait_for_timeout(150)

    # 1. No selector. The list: every port with what ends on it.
    open_panel(page, 'g')
    assert page.evaluate("()=>document.getElementById('formAttachments')") is None
    rows = page.evaluate(ROWS)
    assert [r[0] for r in rows] == ['left', 'right', 'top'], rows
    assert rows[0][1] == '1 wire · feed' and rows[1][1] == 'no wire' and rows[2][1] == 'no wire', rows

    # 2. The hosted Point has a read-only row of its own, with its side, position, flow, channels and Wire.
    hosted = page.evaluate(HOSTED)
    assert len(hosted) == 1 and hosted[0]['id'] == 'hp' and hosted[0]['side'] == 'right' and 0 < hosted[0]['t'] < 1, hosted
    assert hosted[0]['flow'] == 'duplex' and hosted[0]['channels'] == 'main' and hosted[0]['readonly'], hosted
    assert hosted[0]['attached'] == 'hosted Point · 1 wire · k', hosted

    # 3. Select on the hosted row selects the Point; the id cell of a port row selects that port.
    page.locator('#portsList .hosted-row .port-select').click()
    page.wait_for_timeout(120)
    assert page.evaluate('()=>selected') == 'hp' and page.evaluate('()=>selectionSettingsPanel.hidden')
    open_panel(page, 'g')
    page.locator('#portsList .ports-row[data-port-id="right"] .port-id').click()
    page.wait_for_timeout(120)
    assert page.evaluate('()=>selected') == 'point:component:g:right', page.evaluate('()=>selected')

    # 4. Reset stands only where a template port is missing, moved or changed; an added port is not
    #    the template's and stays. It puts the template's ports back in one transition, through the
    #    data core.
    open_panel(page, 'g')
    assert page.evaluate('()=>portsResetBtn.disabled') and "template's" in page.evaluate('()=>portsResetBtn.title')
    page.locator('#portsAddBtn').click()
    page.wait_for_timeout(450)
    s = page.evaluate(STATE, 'g')
    assert s['mode'] is None and [p['id'] for p in s['stored']] == ['p1'] and s['ids'] == ['left', 'right', 'top', 'p1'], s
    open_panel(page, 'g')
    assert page.evaluate('()=>portsResetBtn.disabled'), 'an addition alone does not call for a reset'
    page.locator('#portsList .ports-row[data-port-id="right"] .port-side').select_option('bottom')
    page.wait_for_timeout(450)
    s = page.evaluate(STATE, 'g')
    assert s['mode'] == 'none' and [p['id'] for p in s['stored']] == ['left', 'right', 'top', 'p1'], s
    open_panel(page, 'g')
    assert not page.evaluate('()=>portsResetBtn.disabled')
    c0 = page.evaluate(UNDO_COUNT)
    page.locator('#portsResetBtn').click()
    page.wait_for_timeout(450)
    assert page.locator('#status').inner_text() == 'Reset to template ports'
    s = page.evaluate(STATE, 'g')
    assert s['mode'] is None and [p['id'] for p in s['stored']] == ['p1'] and s['ids'] == ['left', 'right', 'top', 'p1'], s
    assert page.evaluate("()=>Attachment.resolveSpec(nodes.find(n=>n.id==='g'),'right').side") == 'right'
    assert page.evaluate(UNDO_COUNT) == c0 + 1
    open_panel(page, 'g')
    assert page.evaluate('()=>portsResetBtn.disabled')
    # The Wire on `left` rode through: the port it ends on kept its id.
    assert page.evaluate(ROWS)[0] == ['left', '1 wire · feed']

    # 5. A Plane: its template declares no ports, so there is nothing to put back and reset is
    #    disabled; a Point hosted on it is listed the same way.
    page.evaluate("""()=>{const A=SovSchematicAPI;A.create('component',{id:'hp2',symbolId:'point',x:500,y:720});
      const hp2=nodes.find(n=>n.id==='hp2'),pl=nodes.find(n=>n.id==='pl'),s=componentSize(pl),c=componentHostCandidateAtPoint(hp2,pl.x,pl.y-s.h/2);applyComponentHost(hp2,c);render()}""")
    page.wait_for_timeout(150)
    open_panel(page, 'pl')
    assert page.evaluate(ROWS) == [] and page.evaluate('()=>portsResetBtn.disabled')
    hosted = page.evaluate(HOSTED)
    assert [h['id'] for h in hosted] == ['hp2'] and hosted[0]['side'] == 'top' and hosted[0]['attached'] == 'hosted Point · no wire', hosted

    assert not errors, errors
    browser.close()
    print('PASS attached list QA')
