"""Layouts QA: one document, several arrangements (LAYOUT-MODEL.md).

The default layout is the components' own geometry; another layout is projected on screen and
folded back for files, history and every snapshot. Arrange lays out left to right; empty layouts
list what is unplaced; a pinned route keeps its shape in its layout only; the default can move;
the server serves the same operations over MCP.
"""
from __future__ import annotations
import json, os, shutil, socket, subprocess, tempfile, time
from pathlib import Path
from urllib import request
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')
SRC = (ROOT / 'examples/09-print-ai-proof-run.sov').read_text(encoding='utf-8')
ORIGINAL = {c['id']: (c.get('x'), c.get('y')) for c in json.loads(SRC)['components']}

with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1500, 'height': 900})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.set_content(HTML, wait_until='load'); page.wait_for_timeout(200)
    page.evaluate('([t])=>{SovSchematicAPI.file.open(t,"x.sov");fitDiagram()}', [SRC]); page.wait_for_timeout(120)
    A = 'window.SovSchematicAPI.layout'
    listed = page.evaluate(f'()=>{A}.list()')
    assert [v['id'] for v in listed['views']] == ['main'] and listed['default'] == 'main', listed

    # Arrange into a new layout: it is shown, it presents cleanly, and the default is untouched.
    r = page.evaluate(f"()=>{A}.apply({{into:'Overview'}})")
    assert r['ok'] and r['view'] == 'overview', r
    assert page.evaluate(f'()=>{A}.active()') == 'overview'
    ys = page.evaluate("()=>['case','ingest','evidence','customer'].map(id=>nodes.find(n=>n.id===id).y)")
    assert len(set(round(y) for y in ys)) == 1, f'the main line runs straight: {ys}'
    page.evaluate('()=>fitDiagram()'); page.wait_for_timeout(80)
    m = page.evaluate(f'()=>{A}.metrics({{static:true}})')
    assert m['score'] >= 9.5, m['counts']
    doc = page.evaluate('()=>SovSchematicAPI.file.document()')
    assert all((c.get('x'), c.get('y')) == ORIGINAL[c['id']] for c in doc['components'] if c['id'] in ORIGINAL and c['id'] not in ('run-in', 'run-out')), 'the file keeps the default geometry'
    assert 'overview' in doc['layout']['views'] and doc['layout']['views']['overview']['nodes']['case']['y'] == ys[0]

    # Switching shows each layout exactly; nothing leaks between them.
    page.evaluate(f"()=>{A}.switch('main')")
    assert page.evaluate("()=>[nodes.find(n=>n.id==='case').x,nodes.find(n=>n.id==='case').y]") == list(ORIGINAL['case'])
    page.evaluate(f"()=>{A}.switch('overview')")
    assert page.evaluate("()=>nodes.find(n=>n.id==='case').y") == ys[0]

    # A move in one layout stays in it; one undo reverts it and keeps the layout on screen.
    page.evaluate(f"()=>{A}.move('customer',{{dy:120}})")
    moved = page.evaluate("()=>nodes.find(n=>n.id==='customer').y")
    assert moved == ys[0] + 120
    assert next(c for c in page.evaluate('()=>SovSchematicAPI.file.document()')['components'] if c['id'] == 'customer')['y'] == ORIGINAL['customer'][1]
    page.evaluate('()=>SovSchematicAPI.history.undo()'); page.wait_for_timeout(50)
    assert page.evaluate(f'()=>{A}.active()') == 'overview' and page.evaluate("()=>nodes.find(n=>n.id==='customer').y") == ys[0]

    # Placement verbs refuse what they must.
    assert page.evaluate(f"()=>{A}.move('run-in',{{dx:10}})")['code'] == 'HOSTED'
    page.evaluate("()=>{entityEditorState(nodes.find(n=>n.id==='case')).pinned=true}")
    assert page.evaluate(f"()=>{A}.move('case',{{dx:10}})")['code'] == 'PINNED'
    page.evaluate("()=>{entityEditorState(nodes.find(n=>n.id==='case')).pinned=false}")
    assert page.evaluate(f"()=>{A}.place('customer',{{relation:'below',of:'case',gap:40}})")['ok']

    # An empty layout: everything unplaced, shown faint, until arranged.
    r = page.evaluate(f"()=>{A}.create({{name:'Ops',empty:true}})")
    assert r['ok'] and page.evaluate(f'()=>{A}.active()') == 'ops'
    unplaced = page.evaluate(f'()=>{A}.unplaced()')
    assert set(unplaced) >= {'case', 'run', 'customer'}, unplaced
    assert page.evaluate("()=>document.querySelectorAll('.node.unplaced').length") >= 3
    page.evaluate(f'()=>{A}.apply()')
    assert page.evaluate(f'()=>{A}.unplaced()') == []

    # A pinned route keeps its shape in its own layout; the router still owns it elsewhere.
    page.evaluate(f"()=>{A}.switch('overview')")
    r = page.evaluate(f"()=>{A}.route('k7',{{mode:'pinned',points:[{{x:1000,y:500}},{{x:1100,y:500}}]}})")
    assert r['ok'], r
    d = page.evaluate("()=>document.querySelector('.wire-group[data-wire-id=\"k7\"] path.wire').getAttribute('d')")
    assert '1000 500' in d.replace(',', ' ') or 'V 500' in d, d
    page.evaluate(f"()=>{A}.switch('main')")
    d2 = page.evaluate("()=>document.querySelector('.wire-group[data-wire-id=\"k7\"] path.wire').getAttribute('d')")
    assert 'V 500' not in d2 and '1000 500' not in d2, d2
    # A straight wire has nothing to pin, and says so.
    assert page.evaluate("()=>toggleWireRoutePin(wires.find(w=>w.id==='k3'),true)")['code'] == 'NO_ROUTE'
    # Wire Pin in the settings freezes the rendered route in the layout on screen.
    page.evaluate("()=>{const i=wires.findIndex(w=>w.id==='k7');selectWire(i);toggleWireRoutePin(wires[i],true)}")
    doc = page.evaluate('()=>SovSchematicAPI.file.document()')
    assert doc['layout']['views']['main']['routes'].get('k7', {}).get('mode') == 'pinned', doc['layout']['views']['main']

    # The default can move: the file's geometry becomes the overview's, and main is kept as a layout.
    page.evaluate(f"()=>{A}.switch('overview')")
    r = page.evaluate(f"()=>{A}.setDefault('overview')")
    assert r['ok'], r
    doc = page.evaluate('()=>SovSchematicAPI.file.document()')
    assert doc['layout']['default'] == 'overview' and next(c for c in doc['components'] if c['id'] == 'case')['y'] == ys[0]
    assert doc['layout']['views']['main']['nodes']['case']['x'] == ORIGINAL['case'][0]
    # A reopened file shows its default and keeps every layout.
    page.evaluate('(d)=>SovSchematicAPI.file.open(JSON.stringify(d),"y.sov")', doc); page.wait_for_timeout(80)
    assert page.evaluate(f'()=>{A}.active()') == 'overview'
    assert sorted(v['id'] for v in page.evaluate(f'()=>{A}.list()')['views']) == ['main', 'ops', 'overview']
    # Arrange holds the quality bar on every example: no defect that is never acceptable.
    NEVER = {'arrowless', 'unmarked-junction', 'route-escape', 'route-through-node', 'node-overlap', 'text-overflow'}
    for ex in sorted((ROOT / 'examples').glob('*.sov')):
        page.evaluate('([t])=>{SovSchematicAPI.file.open(t,"x.sov")}', [ex.read_text(encoding='utf-8')])
        page.evaluate(f"()=>{{{A}.apply({{into:'Auto'}});fitDiagram()}}"); page.wait_for_timeout(60)
        m = page.evaluate(f'()=>{A}.metrics({{static:true}})')
        assert m['score'] >= 9.5 and not (set(m['counts']) & NEVER), (ex.name, m['counts'], [f['detail'] for f in m['findings']][:6])
    assert not errors, errors
    browser.close()

# The server serves the same operations to an agent over MCP.
def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); n = s.getsockname()[1]; s.close(); return n
with tempfile.TemporaryDirectory() as td:
    f = Path(td) / 'doc.sov'; shutil.copy(ROOT / 'examples/09-print-ai-proof-run.sov', f)
    port = free_port()
    proc = subprocess.Popen(['node', str(ROOT / 'mcp/server.mjs'), '--port', str(port), '--file', str(f)], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    base = f'http://127.0.0.1:{port}'
    try:
        for _ in range(80):
            try: request.urlopen(base + '/api/v1/formats', timeout=1); break
            except Exception: time.sleep(.05)
        def rpc(args):
            body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'schematic.layout', 'arguments': args}}).encode()
            return json.loads(request.urlopen(request.Request(base + '/mcp', data=body, headers={'content-type': 'application/json'}), timeout=30).read())['result']
        r = rpc({'op': 'apply', 'into': 'Agent view'})
        assert not r['isError'] and r['structuredContent']['view'] == 'agent-view', r
        r = rpc({'op': 'place', 'view': 'agent-view', 'id': 'customer', 'relation': 'below', 'of': 'case'})
        assert not r['isError'], r
        r = rpc({'op': 'move', 'id': 'run-in', 'dx': 5})
        assert r['isError'] and r['structuredContent']['code'] == 'HOSTED', r
        saved = json.loads(f.read_text())
        assert 'agent-view' in saved['layout']['views'] and next(c for c in saved['components'] if c['id'] == 'case')['x'] == ORIGINAL['case'][0]
    finally:
        proc.kill()
print('PASS layouts QA')
