"""A document is the same document wherever it is held (contract #50, issue #50; STATE-SPACE.md "Document
identity is content" and "One normalizer").

For every examples/*.sov and examples/state/*.sov, against the same file loaded headless under node (the data
core the HTTP/MCP server runs):

- step 1: `documentHash` of the document the editor holds after opening it (`SovSchematicAPI.document.get()`)
  equals `documentHash` of the file loaded headless, and the two compact forms are equal;
- step 2: opening does not change the revision or make the file dirty; File > Save of the document opened and
  not edited writes exactly `compactDocument` of the file loaded headless (both clocks fixed at one instant, so
  a filled-in `meta.updatedAt` is the same on both sides); an edit undone back to the start saves the same bytes;
- step 3: the golden and.11.sovtrace replays `ok` in the browser against the opened and.sov, over
  `SovSchematicAPI.run.replay`; a trace made on the server (started with the raw file) replays in the browser,
  and a trace made in the browser replays on the server, for and.sov and not-loop.sov.

Amendment 1 (one normalizer, steps 11-14):

- step 11: the saved form is minimal: no saved record carries a value equal to its default (the data core's
  defaults table), for every example, and a saved form loads back to itself (normalize then compact);
- steps 12-13: for every example and each edit below, the browser (the real UI for a gesture, else
  `SovSchematicAPI`) and headless `applyOperation` compute an identical `compactDocument` and `documentHash`:
  resizing a Plane (to 400 and to 600, which the bound clamps to 520), moving a Plane that has edge Points (a
  drag), moving a Component by drag, deleting a record and re-creating one with the same id, paste, palette drops
  (a Component into a Plane's interior, a Point onto a Plane's edge) and port edits (the Ports panel and the API).
  A gesture's headless equivalent is the operation it amounts to, read from the browser's result;
- step 14: open, Save, reopen, Save gives identical bytes, for every example and after every edit; a
  checkpoint stores the same minimal form; restoring recovery gives back the snapshot exactly, adding no
  `meta.timeScale` and no revision.

Amendment 2 (steps 18-20):

- step 18: a legacy record (01 with `colorSlot` removed and `config.color` #D94C4C / #2E7DD1) loads slots 6 and
  10, as at 6a39efd, headless and in the browser in either appearance, and saves them;
- step 19: a Wire-hosted Component has no x/y headless: normalize, `read`, HTTP GET /api/v1/document and MCP
  schematic.document.get;
- step 20: an update setting x or y on a host-derived position (Wire, Path, edge) is refused with
  POSITION_DERIVED, with no history, on the browser API, HTTP and MCP; the same patch with a placement is not.
"""
from __future__ import annotations
import datetime
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from urllib import request, error

from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'examples/state'
EXAMPLES = sorted(ROOT.glob('examples/*.sov')) + sorted(STATE.glob('*.sov'))
FIXED = datetime.datetime(2026, 9, 26, 12, 0, 0, tzinfo=datetime.timezone.utc)
FIXED_MS = int(FIXED.timestamp() * 1000)
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')

# Headless: the data core under node with its clock fixed at FIXED, so a filled-in updatedAt is FIXED.
HEADLESS = r"""
const FIXED=Number(process.argv[1]),Real=Date;
globalThis.Date=class extends Real{constructor(...a){if(a.length)super(...a);else super(FIXED)}static now(){return FIXED}};
const path=require('path'),fs=require('fs'),root=process.argv[2];
require(path.join(root,'src/03-canonical.js'));require(path.join(root,'src/06-attachment-core.js'));
const D=require(path.join(root,'src/05-data-core.js'));
const out={};
for(const f of process.argv.slice(3)){
  const doc=D.documentFromFilePayload(JSON.parse(fs.readFileSync(f,'utf8'))),compact=D.compactDocument(doc);
  out[path.relative(root,f)]={hash:D.documentHash(doc),compact,text:JSON.stringify(compact,null,2),revision:doc.revision};
}
process.stdout.write(JSON.stringify(out));
"""

OPEN = '''([text,name])=>{SovSchematicAPI.file.open(text,name);const doc=SovSchematicAPI.document.get();
  return {hash:SovSchematicData.documentHash(doc),compact:SovSchematicData.compactDocument(doc),revision:diagram.revision,info:SovSchematicAPI.file.info()}}'''
STATE_OF = '()=>({revision:diagram.revision,dirty:SovSchematicAPI.file.info().dirty,undo:historyState.undo.length})'
# One edit through the browser API (each is one history transition), then undo back to the start.
# Headless: the file loaded, the operations applied through applyOperation, the result compacted.
HEADLESS_OPS = r"""
const FIXED=Number(process.argv[1]),Real=Date;
globalThis.Date=class extends Real{constructor(...a){if(a.length)super(...a);else super(FIXED)}static now(){return FIXED}};
const path=require('path'),fs=require('fs'),root=process.argv[2];
require(path.join(root,'src/03-canonical.js'));require(path.join(root,'src/06-attachment-core.js'));
const D=require(path.join(root,'src/05-data-core.js'));
const input=JSON.parse(fs.readFileSync(0,'utf8')),doc=D.documentFromFilePayload(JSON.parse(input.text));
const receipts=input.ops.map(([op,resource,resourceId,value,patch])=>D.applyOperation(doc,{op,resource,resourceId,value,patch}));
const compact=D.compactDocument(doc);
// Minimal: compacting the saved form again, after a load, gives it back.
const again=D.compactDocument(D.documentFromFilePayload(JSON.parse(JSON.stringify(compact))));
process.stdout.write(JSON.stringify({receipts,compact,hash:D.documentHash(doc),fixed:JSON.stringify(again)===JSON.stringify(compact)}));
"""
# Values equal to their defaults, anywhere in a saved record (step 11).
DEFAULTS = r"""(doc)=>{const D=SovSchematicData,found=[];
  for(const c of doc.components){const d=D.componentDefaults(c),cfg=c.config||{},p=cfg.presentation||{};
    for(const [k,v] of Object.entries(c.editor||{}))if(D.EDITOR_DEFAULTS[k]===v)found.push(`${c.id}.editor.${k}`);
    if(c.canvasId==='canvas:global')found.push(`${c.id}.canvasId`);if('parentId' in c)found.push(`${c.id}.parentId`);
    if(cfg.label==='')found.push(`${c.id}.label`);if(cfg.colorSlot===0)found.push(`${c.id}.colorSlot`);if(cfg.signalMode===d.signalMode)found.push(`${c.id}.signalMode`);
    for(const k of ['text','padding'])if(p[k]!==undefined&&p[k]===({text:'',padding:16})[k])found.push(`${c.id}.presentation.${k}`);
    if(p.backdrop===d.backdrop)found.push(`${c.id}.presentation.backdrop`);
    for(const k of ['kind','ref','svg'])if(p.graphic&&p.graphic[k]===d.graphic[k])found.push(`${c.id}.graphic.${k}`);
    for(const k of ['w','h'])if(p.size&&p.size[k]===d.size[k])found.push(`${c.id}.size.${k}`);
    for(const [id,port] of Object.entries(cfg.ports||{})){if(port.label==='')found.push(`${c.id}.ports.${id}.label`);if(port.face==='external')found.push(`${c.id}.ports.${id}.face`);
      if(port.connectionCount===1)found.push(`${c.id}.ports.${id}.connectionCount`);if(port.activeConnection===0)found.push(`${c.id}.ports.${id}.activeConnection`)}
    if(c.placement&&['edge','path','wire'].includes(c.placement.kind)&&('x' in c||'y' in c))found.push(`${c.id}.x/y (derived)`)}
  for(const w of doc.wires){for(const [k,v] of Object.entries(w.config||{}))if(D.WIRE_CONFIG_DEFAULTS[k]===v)found.push(`${w.id}.config.${k}`);
    for(const [k,v] of Object.entries(w.editor||{}))if(D.EDITOR_DEFAULTS[k]===v)found.push(`${w.id}.editor.${k}`);if(w.role==='carrier')found.push(`${w.id}.role`)}
  return found}"""
CLIENT = "([x,y])=>{const p=workspace.createSVGPoint();p.x=x;p.y=y;const c=p.matrixTransform(workspace.getScreenCTM());return {x:c.x,y:c.y}}"
EDIT = '''()=>{const A=SovSchematicAPI,c=nodes[0];
  const r=c?A.update('component',c.id,{x:c.x+48,config:{label:'edited'}}):A.create('component',{symbolId:'act',x:300,y:200});
  return {ok:r.ok,undo:historyState.undo.length,revision:diagram.revision}}'''


def headless(files):
    proc = subprocess.run(['node', '-e', HEADLESS, str(FIXED_MS), str(ROOT), *map(str, files)], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0));return s.getsockname()[1]


def http_json(url, method='GET', payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = request.Request(url, data=body, method=method, headers={'content-type': 'application/json'})
    try:
        with request.urlopen(req, timeout=30) as res:
            return res.status, json.loads(res.read())
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


class Server:
    """The HTTP/MCP server started with the raw example file as its file."""

    def __init__(self, source: Path, td: str):
        self.file = Path(td) / source.name;self.file.write_text(source.read_text(encoding='utf-8'), encoding='utf-8')
        self.port = free_port();self.base = f'http://127.0.0.1:{self.port}'
        self.proc = subprocess.Popen(['node', str(ROOT / 'mcp/server.mjs'), '--port', str(self.port), '--file', str(self.file)], cwd=ROOT,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for _ in range(100):
            try:
                if http_json(self.base + '/api/v1/formats')[0] == 200:return
            except Exception:time.sleep(.05)
        raise AssertionError('server did not start')

    def close(self):
        self.proc.terminate()
        try:self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:self.proc.kill()


def open_page(browser):
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    page.clock.set_fixed_time(FIXED)
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(200)
    return page


def save(page):
    """File > Save, through the menu: the bytes the editor writes."""
    page.locator('#fileBtn').click()
    with page.expect_download() as info:
        page.locator('#fileSaveBtn').click()
    return Path(info.value.path()).read_text(encoding='utf-8')


def legacy_color_document():
    """The reviewer's fixture: 01 with colorSlot removed and a legacy hex colour on each component."""
    doc = json.loads((ROOT / 'examples/01-source-hold.sov').read_text(encoding='utf-8'))
    for c, hex_ in zip(doc['components'], ('#D94C4C', '#2E7DD1')):
        c['config'].pop('colorSlot', None);c['config']['color'] = hex_
    return json.dumps(doc)


def wire_hosted_document():
    """01 with a Point hosted on its Wire k1 (x/y written, as an old file may carry them)."""
    doc = json.loads((ROOT / 'examples/01-source-hold.sov').read_text(encoding='utf-8'))
    doc['components'].append({'id': 'tap', 'symbolId': 'point', 'x': 999, 'y': 999, 'canvasId': 'canvas:wire:k1', 'placement': {'kind': 'wire', 't': 0.5}})
    return json.dumps(doc)


def headless_ops(text, ops):
    proc = subprocess.run(['node', '-e', HEADLESS_OPS, str(FIXED_MS), str(ROOT)], input=json.dumps({'text': text, 'ops': ops}), cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def held_doc(page):
    return page.evaluate('()=>{const d=SovSchematicAPI.document.get();return {compact:SovSchematicData.compactDocument(d),hash:SovSchematicData.documentHash(d)}}')


def record(page, rid):
    """A component's saved record, as the browser holds it."""
    return next((c for c in page.evaluate('()=>SovSchematicAPI.document.get()')['components'] if c['id'] == rid), None)


def drag(page, rid, dx, dy, grab=(0, 0)):
    """A real pointer drag of a component by (dx, dy) world units, grabbed at an offset from its centre."""
    n = page.evaluate("(id)=>{const n=nodes.find(x=>x.id===id);return {x:n.x,y:n.y}}", rid)
    a = page.evaluate(CLIENT, [n['x'] + grab[0], n['y'] + grab[1]]);b = page.evaluate(CLIENT, [n['x'] + grab[0] + dx, n['y'] + grab[1] + dy])
    assert page.evaluate("([x,y])=>document.elementFromPoint(x,y)?.closest('.node')?.dataset.id", [a['x'], a['y']]) == rid, rid
    page.mouse.move(a['x'], a['y']);page.mouse.down()
    page.mouse.move(a['x'] + 8, a['y'] + 8, steps=2);page.mouse.move(b['x'], b['y'], steps=8)
    page.mouse.up();page.wait_for_timeout(500)


def palette_drop(page, symbol, world, dwell=0):
    box = page.locator(f'.symbol-card[data-symbol-id="{symbol}"]').bounding_box()
    cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    to = page.evaluate(CLIENT, list(world))
    before = set(page.evaluate('()=>nodes.map(n=>n.id)'))
    page.mouse.move(cx, cy);page.mouse.down();page.mouse.move(cx + 30, cy + 30, steps=3);page.mouse.move(to['x'], to['y'], steps=6)
    page.wait_for_timeout(dwell);page.mouse.up();page.wait_for_timeout(400)
    new = [i for i in page.evaluate('()=>nodes.map(n=>n.id)') if i not in before]
    assert len(new) == 1, new
    return new[0]


def records(page):
    return {c['id']: c for c in page.evaluate('()=>SovSchematicAPI.document.get()')['components']}


def moved(before, page):
    """The updates a move amounts to: each component the gesture moved (the dragged one, and what it
    carries), its new position and host."""
    ops = []
    for rid, r in records(page).items():
        patch = {k: r[k] for k in ('x', 'y', 'canvasId', 'placement') if k in r and r.get(k) != before[rid].get(k)}
        if patch:ops.append(['update', 'component', rid, None, patch])
    assert ops, 'the drag moved nothing'
    return ops


def created(page, rid):
    return [['create', 'component', None, record(page, rid), None]]


# Each edit: (name, example, browser action -> the headless operations it amounts to).
def e_resize(w):
    def act(page):
        ops = [['update', 'component', 'svc', None, {'config': {'presentation': {'size': {'w': w, 'h': 260}}}}]]
        assert page.evaluate('(p)=>SovSchematicAPI.update("component","svc",p).ok', ops[0][4])
        return ops
    return act


def e_move_plane(page):
    before = records(page);drag(page, 'svc', 96, 48, grab=(-250, 0))
    assert page.evaluate("()=>nodes.find(n=>n.id==='permit').placement.kind") == 'edge'
    return moved(before, page)


def e_move_component(page):
    before = records(page);drag(page, 'grant', 0, -120)
    return moved(before, page)


def e_recreate(page, rid):
    value = {'id': rid, 'symbolId': 'act', 'x': 100, 'y': 100}
    ops = [['delete', 'component', rid, None, None], ['create', 'component', None, value, None]]
    assert page.evaluate('([id,v])=>[SovSchematicAPI.delete("component",id).ok,SovSchematicAPI.create("component",v).ok]', [rid, value]) == [True, True]
    return ops


def e_paste(page, rid):
    before = set(page.evaluate('()=>nodes.map(n=>n.id)'));wires_before = set(page.evaluate('()=>wires.map(w=>w.id)'))
    page.evaluate("(id)=>{selectNode(id);copySelection()}", rid)
    page.evaluate('()=>pasteClipboard()')
    page.wait_for_timeout(500)
    new = [i for i in page.evaluate('()=>nodes.map(n=>n.id)') if i not in before]
    assert new, ('nothing pasted', rid, page.evaluate('()=>statusEl.textContent'))
    # A host is pasted with what it hosts, and the Wires among the copies.
    new_wires = [w for w in page.evaluate('()=>SovSchematicAPI.document.get()')['wires'] if w['id'] not in wires_before]
    return [op for i in new for op in created(page, i)] + [['create', 'wire', None, w, None] for w in new_wires]


def e_drop_interior(page):
    rid = palette_drop(page, 'act', (560, 300), dwell=450)
    assert record(page, rid).get('canvasId') == 'canvas:component:svc', record(page, rid)
    return created(page, rid)


def e_drop_edge(page):
    rid = palette_drop(page, 'point', (900, 330), dwell=60)
    assert record(page, rid)['placement']['kind'] == 'edge', record(page, rid)
    return created(page, rid)


def e_port_api(page):
    ops = [['update', 'component', 'check', None, {'config': {'ports': {'out': {'label': 'P'}}}}]]
    assert page.evaluate('(p)=>SovSchematicAPI.update("component","check",p).ok', ops[0][4])
    return ops


def e_port_panel(page):
    """A port label typed in the Ports panel: the panel sends the complete port list, as the headless op does."""
    page.evaluate("()=>{selectNode('check');openSelectionSettings('component')}");page.wait_for_timeout(200)
    ports = page.evaluate("()=>componentPortList(nodes.find(n=>n.id==='check'))")
    page.locator('#portsList .ports-row[data-port-id="right"] .port-label').fill('Q1')
    page.locator('#portsList .ports-row[data-port-id="right"] .port-label').press('Tab');page.wait_for_timeout(400)
    for port in ports:
        if port['id'] == 'right':port['label'] = 'Q1'
    return [['update', 'component', 'check', None, {'config': {'attachmentDefaults': 'none', 'attachmentPoints': ports, 'ports': {'out': {'label': 'Q1'}}}}]]


EDITS = [
    ('resize a Plane', '08-gated-service.sov', e_resize(400)),
    ('resize a Plane to a clamped value', '08-gated-service.sov', e_resize(600)),
    ('move a Plane with edge Points (drag)', '08-gated-service.sov', e_move_plane),
    ('move a Component (drag)', '08-gated-service.sov', e_move_component),
    ('delete and re-create with the same id', '08-gated-service.sov', lambda page: e_recreate(page, 'permit')),
    ('paste', '08-gated-service.sov', lambda page: e_paste(page, 'grant')),
    ('palette drop into a Plane', '08-gated-service.sov', e_drop_interior),
    ('palette drop onto a Plane edge', '08-gated-service.sov', e_drop_edge),
    ('port edit (API)', '08-gated-service.sov', e_port_api),
    ('port edit (Ports panel)', '08-gated-service.sov', e_port_panel),
]


def plain_component(path):
    """The first surface-placed component of an example not bound to a definition (a bound copy has no API
    create: only a paste keeps config.definition), or None."""
    for c in json.loads(path.read_text(encoding='utf-8'))['components']:
        if (c.get('placement') or {}).get('kind', 'surface') == 'surface' and (c.get('config') or {}).get('definition') is None:
            return c['id']
    return None


EDITS += [(f'{label} ({path.name})', str(path.relative_to(ROOT / 'examples')), (lambda f, rid: lambda page: f(page, rid))(act, plain_component(path)))
          for path in EXAMPLES if path.name != '08-gated-service.sov' and plain_component(path)
          for label, act in (('delete and re-create with the same id', e_recreate), ('paste', e_paste))]


def fixpoint(browser, text, label, errors):
    """Open, Save, reopen, Save: identical bytes the second time."""
    page = open_page(browser);page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.evaluate('([t,n])=>{SovSchematicAPI.file.open(t,n)}', [text, 'a.sov']);first = save(page);page.close()
    page = open_page(browser);page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.evaluate('([t,n])=>{SovSchematicAPI.file.open(t,n)}', [first, 'b.sov']);second = save(page)
    minimal = page.evaluate(DEFAULTS, json.loads(second));page.close()
    assert second == first, (label, 'open, save, reopen, save is not a fixpoint')
    assert minimal == [], (label, 'the saved form carries default values', minimal)
    return first


def main() -> None:
    assert len(EXAMPLES) >= 16, EXAMPLES
    files = headless(EXAMPLES)
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        errors = []
        for path in EXAMPLES:
            rel = str(path.relative_to(ROOT));want = files[rel];text = path.read_text(encoding='utf-8')
            page = open_page(browser);page.on('pageerror', lambda exc: errors.append(str(exc)))
            # Step 1: one hash, one compact form.
            held = page.evaluate(OPEN, [text, path.name])
            assert held['hash'] == want['hash'], (rel, 'the editor hashes the document differently', held['hash'], want['hash'])
            assert held['compact'] == want['compact'], (rel, 'the editor holds a different compact form')
            # Step 2: opening changes neither the revision nor the file state; Save writes the file's compact form.
            assert held['revision'] == want['revision'] and held['info']['revision'] == want['revision'], (rel, held['revision'], want['revision'])
            assert held['info']['dirty'] is False, (rel, held['info'])
            page.wait_for_timeout(500)  # past any scheduled capture or autosave
            assert page.evaluate(STATE_OF) == {'revision': want['revision'], 'dirty': False, 'undo': 0}, (rel, page.evaluate(STATE_OF))
            assert save(page) == want['text'], (rel, 'open then save is not a no-op')
            assert page.evaluate(STATE_OF)['revision'] == want['revision'], rel
            # An edit, undone back to the start, saves the same bytes.
            edit = page.evaluate(EDIT)
            assert edit['ok'] and edit['undo'] == 1 and edit['revision'] > want['revision'], (rel, edit)
            page.wait_for_timeout(500)
            assert save(page) != want['text'], (rel, 'the edit did not reach the saved file')
            assert page.evaluate('()=>SovSchematicAPI.history.undo()') is True, rel
            page.wait_for_timeout(500)
            after = page.evaluate('()=>({hash:SovSchematicData.documentHash(SovSchematicAPI.document.get()),revision:diagram.revision})')
            assert after == {'hash': want['hash'], 'revision': want['revision']}, (rel, after)
            assert save(page) == want['text'], (rel, 'edit then undo does not save the file it opened')
            page.close()
            fixpoint(browser, text, rel, errors)
        print(f'identity: {len(EXAMPLES)} examples hash, compact and save as loaded headless; edit and undo save the same bytes; save is a minimal fixpoint')

        # Steps 12-14: each edit computes the same document in the browser and headless, and saves as a fixpoint.
        for name, example, act in EDITS:
            text = (ROOT / 'examples' / example).read_text(encoding='utf-8')
            page = open_page(browser);page.on('pageerror', lambda exc: errors.append(str(exc)))
            page.evaluate('([t,n])=>{SovSchematicAPI.file.open(t,n)}', [text, example]);page.wait_for_timeout(300)
            ops = act(page);page.wait_for_timeout(500)
            # Save commits the editor's revision (the editor advances it once per edit, when it is next read).
            saved = save(page);got = held_doc(page);want = headless_ops(text, ops)
            assert all(r['ok'] for r in want['receipts']), (name, [r['error'] for r in want['receipts']])
            assert want['fixed'], (name, 'the headless saved form is not a fixpoint')
            b, h = dict(got['compact']), dict(want['compact'])
            assert json.loads(saved) == got['compact'], (name, 'Save wrote a different form from document.get()')
            # A drag or a paste is one revision in the editor and one operation per record headless: for those the
            # revision (a label, not identity) is compared only when the edit is one operation.
            if len(ops) > 1 and ('(drag)' in name or name.startswith('paste')):b.pop('revision');h.pop('revision')
            assert b == h, (name, 'browser and headless compute different documents', [k for k in h if b.get(k) != h.get(k)],
                            [(x, y) for x, y in zip(b['components'], h['components']) if x != y][:2])
            assert got['hash'] == want['hash'], (name, 'the hashes differ')
            page.close()
            fixpoint(browser, saved, name, errors)
        print(f'edits: {len(EDITS)} edits (ten on 08; delete/re-create and paste on every other example with an unbound surface component) compute the same compact document and hash in the browser and headless, and save as fixpoints')

        # Step 14: a checkpoint stores the minimal form.
        page = open_page(browser);page.on('pageerror', lambda exc: errors.append(str(exc)))
        text8 = (ROOT / 'examples/08-gated-service.sov').read_text(encoding='utf-8')
        page.evaluate('([t,n])=>{SovSchematicAPI.file.open(t,n)}', [text8, '08.sov'])
        page.evaluate('()=>SovSchematicAPI.update("component","grant",{config:{presentation:{size:{w:140,h:84}}}})')
        cp = page.evaluate("()=>{const c=SovSchematicAPI.checkpoints.create('cp');return {cp:c,doc:SovSchematicAPI.document.get()}}")
        cpdoc = cp['doc']['meta']['checkpoints'][0]['document']
        assert cpdoc['components'] == cp['doc']['components'] and cpdoc['wires'] == cp['doc']['wires'], 'a checkpoint stores a different form'
        assert page.evaluate(DEFAULTS, cpdoc) == [], page.evaluate(DEFAULTS, cpdoc)
        page.close()
        print('checkpoints: a checkpoint stores the minimal form')

        # Step 14: recovery restores the snapshot exactly: no meta.timeScale, no revision, unless changed.
        page = browser.new_page(viewport={'width': 1400, 'height': 900});page.clock.set_fixed_time(FIXED)
        page.on('pageerror', lambda exc: errors.append(str(exc)));page.on('dialog', lambda d: d.accept())
        page.goto((ROOT / 'index.html').resolve().as_uri(), wait_until='load');page.wait_for_timeout(200)  # a file URL has localStorage
        page.evaluate('([t,n])=>{SovSchematicAPI.file.open(t,n)}', [text8, '08.sov'])
        page.evaluate('()=>SovSchematicAPI.update("component","grant",{x:200})');page.wait_for_timeout(900)
        snap = page.evaluate('()=>SovSchematicAPI.document.get()')
        stored = page.evaluate('()=>JSON.parse(localStorage.getItem(LOCAL_RECOVERY_KEY))')
        assert stored['document'] == snap and 'timeScale' not in snap['meta'], 'recovery holds a different document'
        page.evaluate('(t)=>{SovSchematicAPI.file.open(t,"01.sov")}', (ROOT / 'examples/01-source-hold.sov').read_text(encoding='utf-8'))
        page.evaluate('(w)=>localStorage.setItem(LOCAL_RECOVERY_KEY,JSON.stringify(w))', stored)
        assert page.evaluate('()=>restoreRecovery()') is True;page.wait_for_timeout(900)
        back = page.evaluate('()=>SovSchematicAPI.document.get()')
        assert back == snap and 'timeScale' not in back['meta'] and back['revision'] == snap['revision'], ('recovery changed the document', back['meta'], back['revision'], snap['revision'])
        # A rate the user set is the document's, and comes back with it.
        page.evaluate('()=>SovSchematicAPI.view.setGlobalRate(2)');page.wait_for_timeout(900)
        rated = page.evaluate('()=>SovSchematicAPI.document.get()')
        assert rated['meta']['timeScale'] == 2 and rated['revision'] == snap['revision'] + 1, rated['meta']
        stored = page.evaluate('()=>JSON.parse(localStorage.getItem(LOCAL_RECOVERY_KEY))')
        page.evaluate('(t)=>{SovSchematicAPI.file.open(t,"01.sov")}', (ROOT / 'examples/01-source-hold.sov').read_text(encoding='utf-8'))
        page.evaluate('(w)=>localStorage.setItem(LOCAL_RECOVERY_KEY,JSON.stringify(w))', stored)
        assert page.evaluate('()=>restoreRecovery()') is True;page.wait_for_timeout(900)
        assert page.evaluate('()=>SovSchematicAPI.document.get()') == rated, 'recovery changed a document with a rate'
        page.close()
        print('recovery: restores the snapshot exactly, adding no timeScale and no revision')

        # Step 18: legacy colours load as before, identically headless and in the browser, whatever the appearance.
        legacy = legacy_color_document()
        want = headless_ops(legacy, [])
        assert [c['config'].get('colorSlot') for c in want['compact']['components']] == [6, 10], want['compact']['components']
        for appearance in ('light', 'dark'):
            page = open_page(browser);page.on('pageerror', lambda exc: errors.append(str(exc)))
            page.evaluate('(m)=>SovSchematicAPI.view.setAppearance(m)', appearance)
            page.evaluate('([t,n])=>{SovSchematicAPI.file.open(t,n)}', [legacy, 'legacy.sov'])
            assert page.evaluate("()=>nodes.map(n=>n.config.colorSlot)") == [6, 10], (appearance, page.evaluate("()=>nodes.map(n=>n.config.colorSlot)"))
            saved = save(page)
            assert json.loads(saved) == want['compact'] and held_doc(page)['hash'] == want['hash'], (appearance, 'the legacy file saves differently')
            page.close()
        print('legacy colours: #D94C4C and #2E7DD1 load and save as slots 6 and 10, headless and in the browser (light and dark)')

        # Step 19: no false positions. Step 20: derived positions are refused, not ignored.
        hosted = wire_hosted_document()
        want = headless_ops(hosted, [])
        tap = next(c for c in want['compact']['components'] if c['id'] == 'tap')
        assert 'x' not in tap and 'y' not in tap, tap
        probe = r"""
const D=require(process.argv[1]),fs=require('fs');const doc=D.documentFromFilePayload(JSON.parse(fs.readFileSync(0,'utf8')));
const tap=doc.components.find(c=>c.id==='tap'),read=D.read(doc,'component','tap'),normalized='x' in tap||'y' in tap;
const refused=D.applyOperation(doc,{op:'update',resource:'component',resourceId:'tap',patch:{x:5}});
const moved=D.applyOperation(doc,{op:'update',resource:'component',resourceId:'tap',patch:{x:5,y:6,canvasId:'canvas:global',placement:{kind:'surface'}}});
process.stdout.write(JSON.stringify({normalized,read:'x' in read||'y' in read,refused:refused.ok?null:refused.error.message,moved:moved.ok&&[moved.result.x,moved.result.y,moved.result.placement.kind]}));
"""
        proc = subprocess.run(['node', '-e', probe, str(ROOT / 'src/05-data-core.js')], input=hosted, cwd=ROOT, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        hl = json.loads(proc.stdout)
        assert hl['normalized'] is False and hl['read'] is False, hl
        assert hl['refused'] and hl['refused'].startswith('POSITION_DERIVED'), hl
        assert hl['moved'] == [5, 6, 'surface'], hl
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / 'hosted.sov';src.write_text(hosted, encoding='utf-8')
            server = Server(src, td)
            try:
                status, doc = http_json(server.base + '/api/v1/document')
                assert status == 200 and not any(k in next(c for c in doc['components'] if c['id'] == 'tap') for k in ('x', 'y')), doc
                status, res = http_json(server.base + '/mcp', 'POST', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'schematic.document.get', 'arguments': {}}})
                mdoc = res['result']['structuredContent']
                assert not any(k in next(c for c in mdoc['components'] if c['id'] == 'tap') for k in ('x', 'y')), mdoc
                status, r = http_json(server.base + '/api/v1/components/tap', 'PATCH', {'y': 7})
                assert status == 400 and r['ok'] is False and r['error']['message'].startswith('POSITION_DERIVED'), (status, r)
                status, res = http_json(server.base + '/mcp', 'POST', {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'schematic.update', 'arguments': {'resource': 'component', 'id': 'tap', 'patch': {'x': 7}}}})
                assert res['result']['isError'] and res['result']['structuredContent']['error']['message'].startswith('POSITION_DERIVED'), res
                status, res = http_json(server.base + '/mcp', 'POST', {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'schematic.history.undo', 'arguments': {}}})
                assert res['result']['structuredContent'] == {'error': 'Nothing to undo'}, 'a refused update entered the server history'
            finally:
                server.close()
        page = open_page(browser);page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.evaluate('([t,n])=>{SovSchematicAPI.file.open(t,n)}', [hosted, 'hosted.sov']);page.wait_for_timeout(300)
        assert 'x' not in record(page, 'tap'), record(page, 'tap')
        page.evaluate('([t,n])=>{SovSchematicAPI.file.open(t,n)}', [(ROOT / 'examples/07-plane-with-points.sov').read_text(encoding='utf-8'), '07.sov']);page.wait_for_timeout(300)
        before = page.evaluate('()=>[historyState.undo.length,diagram.revision,SovSchematicAPI.document.get()]')
        r = page.evaluate('()=>SovSchematicAPI.update("component","pin-in",{y:340})')
        assert r['ok'] is False and r['error']['message'].startswith('POSITION_DERIVED'), r
        page.wait_for_timeout(500)
        assert page.evaluate('()=>[historyState.undo.length,diagram.revision,SovSchematicAPI.document.get()]') == before, 'a refused update changed the editor'
        page.close()
        print('positions: a Wire-hosted Component has no x/y headless, over HTTP or MCP; x/y on a derived position is POSITION_DERIVED everywhere')

        # Step 3: traces cross surfaces.
        golden = json.loads((STATE / 'and.11.sovtrace').read_text(encoding='utf-8'))
        jobs = {'and.sov': {'inputs': [{'entity': 'A', 'point': 'self', 'value': True, 'at': 0}, {'entity': 'B', 'point': 'self', 'value': True, 'at': 0}]},
                'not-loop.sov': {'budget': 40}}
        with tempfile.TemporaryDirectory() as td:
            for name, start in jobs.items():
                source = STATE / name
                page = open_page(browser);page.on('pageerror', lambda exc: errors.append(str(exc)))
                page.evaluate('([text,name])=>{SovSchematicAPI.file.open(text,name)}', [source.read_text(encoding='utf-8'), name])
                server = Server(source, td)
                try:
                    if name == 'and.sov':
                        replayed = page.evaluate('(t)=>SovSchematicAPI.run.replay(t)', golden)
                        assert replayed['ok'] and replayed['result'] == {'records': golden['records']} and replayed['head'] == golden['head'], replayed
                    # Browser trace -> server replay.
                    b = page.evaluate('''(args)=>{const R=SovSchematicAPI.run,s=R.start(args);R.settle(s.handle);return R.trace(s.handle)}''', start)
                    assert b['ok'], b
                    status, on_server = http_json(server.base + '/api/v1/replay', 'POST', b['result'])
                    assert status == 200 and on_server['ok'] and on_server['result'] == {'records': b['result']['records']}, (name, status, on_server)
                    # Server trace -> browser replay.
                    status, s = http_json(server.base + '/api/v1/runs', 'POST', start);assert status == 201, s
                    handle = request.quote(s['handle'], safe='')
                    status, _ = http_json(server.base + f'/api/v1/runs/{handle}/settle', 'POST', {});assert status == 200
                    status, t = http_json(server.base + f'/api/v1/runs/{handle}/trace');assert status == 200 and t['ok'], t
                    in_browser = page.evaluate('(t)=>SovSchematicAPI.run.replay(t)', t['result'])
                    assert in_browser['ok'] and in_browser['result'] == {'records': t['result']['records']}, (name, in_browser)
                    # The two traces are one trace: the same document, key and records.
                    assert json.dumps(b['result'], sort_keys=True) == json.dumps(t['result'], sort_keys=True), (name, 'browser and server traces differ')
                finally:
                    server.close()
                page.close()
        print('traces: golden and.11 replays in the browser; server and browser traces replay on each other (and.sov, not-loop.sov)')
        browser.close()
    assert not errors, errors
    print('PASS document identity QA')


if __name__ == '__main__':
    main()
