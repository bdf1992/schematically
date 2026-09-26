"""Access panel QA: a person sets who a component acts as and a plane's access list in the
settings panel; the edit is ordinary config (history, lock), and the running clock obeys it.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1500, 'height': 1000})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.set_content(HTML, wait_until='load'); page.wait_for_timeout(200)
    page.evaluate('([t])=>{SovSchematicAPI.file.open(t,"x.sov");fitDiagram()}', [(ROOT / 'examples/09-print-ai-proof-run.sov').read_text(encoding='utf-8')])
    page.wait_for_timeout(120)

    # The run shows its access list as declared.
    page.evaluate("()=>{selectNode('run');openSelectionSettings('component');syncComponentVisualPanel(nodes.find(n=>n.id==='run'))}"); page.wait_for_timeout(60)
    page.evaluate("()=>{document.getElementById('accessSettings').open=true}")
    assert page.is_visible('#accessAclBlock')
    assert page.input_value('#accessAclMode') == 'deny'
    rows = page.evaluate("()=>[...document.querySelectorAll('#accessEntries .access-entry:not(.access-head)')].map(r=>[r.querySelector('input').value,...[...r.querySelectorAll('select')].map(s=>s.value)])")
    assert rows == [['intake:*', 'allow', '', '', ''], ['svc:mailer', '', 'allow', '', '']], rows

    # Deny exit to the mailer through the panel: the running clock refuses the effect's exit.
    page.select_option('#accessEntries .access-entry:nth-child(3) select:nth-of-type(2)', 'deny')
    acl = page.evaluate("()=>SovSchematicAPI.file.document().components.find(c=>c.id==='run').config.acl")
    assert acl['entries'][1]['deny'] == ['exit'] and acl['entries'][1]['allow'] == [], acl
    page.evaluate("()=>{const A=SovSchematicAPI.clock;A.step();A.send('case');A.advance(200)}")
    park = page.evaluate("()=>SovSchematicAPI.clock.state().parked[0].id")
    page.evaluate("(id)=>{SovSchematicAPI.clock.resume(id,'approve');SovSchematicAPI.clock.advance(200)}", park)
    reasons = page.evaluate("()=>SovSchematicAPI.clock.inspect('refusals').refusals.map(r=>r.reason)")
    assert any('svc:mailer is denied exit' in r for r in reasons), reasons
    assert page.evaluate("()=>SovSchematicAPI.clock.inspect('taps','customer').arrivals.filter(m=>m.channel==='proof').length") == 0
    # One edit, one undo.
    page.evaluate("()=>SovSchematicAPI.history.undo()"); page.wait_for_timeout(50)
    acl = page.evaluate("()=>SovSchematicAPI.file.document().components.find(c=>c.id==='run').config.acl")
    assert acl['entries'][1]['allow'] == ['exit'], acl

    # A principal for a participant, set and cleared.
    page.evaluate("()=>{selectNode('evaluate');openSelectionSettings('component');syncComponentVisualPanel(nodes.find(n=>n.id==='evaluate'))}"); page.wait_for_timeout(60)
    page.evaluate("()=>{document.getElementById('accessSettings').open=true}")
    assert not page.is_visible('#accessAclBlock'), 'a card without an open interior has no access list'
    page.fill('#accessPrincipal', 'ai:judge'); page.press('#accessPrincipal', 'Enter'); page.dispatch_event('#accessPrincipal', 'change')
    assert page.evaluate("()=>SovSchematicAPI.file.document().components.find(c=>c.id==='evaluate').config.principal") == 'ai:judge'
    # Locked: the edit is refused and nothing changes.
    page.evaluate("()=>{entityEditorState(nodes.find(n=>n.id==='evaluate')).locked=true}")
    page.fill('#accessPrincipal', 'ai:other'); page.dispatch_event('#accessPrincipal', 'change')
    assert page.evaluate("()=>SovSchematicAPI.file.document().components.find(c=>c.id==='evaluate').config.principal") == 'ai:judge'
    assert not errors, errors
    browser.close()
print('PASS access panel QA')
