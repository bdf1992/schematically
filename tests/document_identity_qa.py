"""A document is the same document wherever it is held (contract #50, issue #50; STATE-SPACE.md "Document
identity is content").

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
        print(f'identity: {len(EXAMPLES)} examples hash, compact and save as loaded headless; edit and undo save the same bytes')

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
