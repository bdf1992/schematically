"""Real file Open/Save and projection parity for large authored regions (#38).

These synthetic documents exercise the sizes reported in the handoff; they are
not substitutes for the owner's missing architecture fixtures.
"""
import json
import subprocess
import tempfile
import socket
import time
from pathlib import Path
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]


def fixture(w, h):
    return {
        'schema': 'soveraeign.schematic/document@0.1', 'id': 'region-parity',
        'components': [
            {'id': 'host', 'symbolId': 'plane', 'x': 700, 'y': 450,
             'config': {'label': 'Service boundary', 'presentation': {'size': {'w': w, 'h': h}}}},
            {'id': 'child', 'symbolId': 'hold', 'x': 700 + w / 2 - 130, 'y': 500,
             'parentId': 'host', 'canvasId': 'canvas:component:host', 'config': {'label': 'State'}},
            {'id': 'entry', 'symbolId': 'point', 'x': 700 - w / 2, 'y': 500,
             'parentId': 'host', 'canvasId': 'canvas:component:host',
             'placement': {'kind': 'edge', 'hostId': 'host', 'side': 'left', 't': .5 + 50 / h},
             'config': {'ports': {'out': {'face': 'both'}}}},
        ],
        'wires': [{'id': 'flow', 'a': 'entry', 'aSide': 'out', 'b': 'child', 'bSide': 'in',
                   'canvasId': 'canvas:component:host'}], 'references': [],
    }


def transport_parity(td):
    """HTTP and MCP use the same admitted sizes as file load and browser CRUD."""
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    proc = subprocess.Popen(['node', str(ROOT/'mcp/server.mjs'), '--port', str(port),
                             '--file', str(Path(td)/'transport.sov')], cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    def call(path, method='GET', payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        req = Request(f'http://127.0.0.1:{port}'+path, data=data, method=method,
                      headers={'content-type':'application/json'})
        with urlopen(req, timeout=4) as response:
            return json.load(response)
    try:
        for _ in range(60):
            try:
                call('/api/v1/formats')
                break
            except OSError:
                time.sleep(.05)
        else:
            raise AssertionError('HTTP server did not start')
        for w, h in [(940,650),(1170,730),(1010,620),(0,-1)]:
            size={'w':w,'h':h}
            expected={'w':max(80,w),'h':max(64,h)}
            entity={'id':f'host-{w}','symbolId':'plane','config':{'presentation':{'size':size}}}
            created=call('/api/v1/components','POST',entity)
            assert created['ok'] and created['result']['config']['presentation']['size']==expected, created
            response=call('/mcp','POST',{'jsonrpc':'2.0','id':1,'method':'tools/call',
                'params':{'name':'schematic.update','arguments':{'resource':'component','id':entity['id'],
                    'patch':{'config':{'presentation':{'size':size}}}}}})
            receipt=response['result']['structuredContent']
            assert receipt['ok'] and receipt['result']['config']['presentation']['size']==expected, response
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def main():
    with tempfile.TemporaryDirectory() as td, sync_playwright() as p:
        transport_parity(td)
        browser = p.chromium.launch(**chromium_launch_kwargs())
        page = browser.new_page(accept_downloads=True)
        # Exercise the browser's normal download fallback without an OS picker.
        page.add_init_script('window.showSaveFilePicker=undefined;window.showOpenFilePicker=undefined;')
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('dialog', lambda d: d.accept())
        for w, h in [(940, 650), (1170, 730), (1010, 620)]:
            doc = fixture(w, h)
            source = Path(td) / 'region.sov'
            source.write_text(json.dumps(doc), encoding='utf-8')
            core = json.loads(subprocess.check_output([
                'node', '-e', "const D=require('./src/05-data-core.js'); const fs=require('fs');"
                "console.log(JSON.stringify(D.makeDocument(JSON.parse(fs.readFileSync(process.argv[1],'utf8')))));",
                str(source)], cwd=ROOT, text=True))
            page.goto((ROOT / 'index.html').as_uri())
            page.locator('#fileOpenInput').set_input_files(str(source))
            page.wait_for_function("nodes.some(n=>n.id==='host')")
            state = page.evaluate('''() => {
              const host=nodes.find(n=>n.id==='host'), child=nodes.find(n=>n.id==='child');
              const before=JSON.stringify(snapshotDocument());
              render(); render(); fitDiagram();
              const size=componentSize(host), cs=componentSize(child);
              const body=document.querySelector('.node[data-id="host"] .body').getBBox();
              return {size, painted:{w:body.width,h:body.height}, stable:before===JSON.stringify(snapshotDocument()),
                contains:child.x+cs.w/2<=host.x+size.w/2,
                min:transformMinimumSize(host)};
            }''')
            assert state['size'] == core['components'][0]['config']['presentation']['size'] == {'w': w, 'h': h}, state
            assert state['painted'] == {'w': w, 'h': h}, state
            assert state['stable'] and state['contains'], state
            assert state['min']['w'] > 520, state
            with page.expect_download() as info:
                page.click('#fileBtn')
                page.click('#fileSaveBtn')
            saved = Path(td) / 'saved.sov'
            info.value.save_as(saved)
            page.locator('#fileOpenInput').set_input_files(str(saved))
            page.wait_for_function("SovSchematicAPI.file.info().name==='saved.sov'")
            reopened = page.evaluate('snapshotDocument()')
            for actual in (json.loads(saved.read_text(encoding='utf-8')), reopened):
                host, child, point = actual['components']
                assert host['config']['presentation']['size'] == {'w': w, 'h': h}
                assert child['parentId'] == point['parentId'] == 'host'
                assert child['canvasId'] == point['canvasId'] == 'canvas:component:host'
                assert point['placement'] == doc['components'][2]['placement']
                for key in ('a', 'aSide', 'b', 'bSide', 'canvasId'):
                    assert actual['wires'][0][key] == doc['wires'][0][key]
            # Inspector and actual pointer resize may exceed the former ceiling.
            page.evaluate("selectNode('host',{focus:false});openSelectionSettings('component')")
            page.locator('summary').filter(has_text='graphic · size · material').click()
            page.locator('#visualWidth').fill('1280')
            page.locator('#visualWidth').dispatch_event('change')
            page.locator('#visualHeight').fill('800')
            page.locator('#visualHeight').dispatch_event('change')
            assert page.evaluate("componentSize(nodes.find(n=>n.id==='host'))") == {'w':1280,'h':800}
            page.evaluate('closeSelectionSettings(); fitDiagram()')
            handle=page.locator('.node[data-id="host"] .transform-handle[data-transform="xy"]')
            box=handle.bounding_box()
            page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
            page.mouse.down()
            page.mouse.move(box['x']+box['width']/2+35,box['y']+box['height']/2+20,steps=5)
            page.mouse.up()
            resized=page.evaluate("componentSize(nodes.find(n=>n.id==='host'))")
            assert resized['w']>1280 and resized['h']>800, resized
            for size, expected in [({'w':1170,'h':730},{'w':1170,'h':730}),
                                   ({'w':0,'h':-1},{'w':80,'h':64})]:
                receipt=page.evaluate("size=>SovSchematicAPI.update('component','host',{config:{presentation:{size}}})",size)
                assert receipt['ok'] and receipt['result']['config']['presentation']['size']==expected,receipt
                assert page.evaluate("componentSize(nodes.find(n=>n.id==='host'))")==expected
            # Bounds must include nested labels even when they extend outside
            # their host's rectangle; fitting only root bodies used to clip them.
            covered=page.evaluate('''()=>{
              SovSchematicAPI.update('component','child',{config:{label:'A deliberately long nested label reaching beyond its host'}});
              const label=document.querySelector('.node[data-id="child"] text.component-label');
              const r=label.getBoundingClientRect(),inverse=workspace.getScreenCTM().inverse();
              const right=new DOMPoint(r.right,r.bottom).matrixTransform(inverse);
              return diagramBounds().r>=right.x-.01;
            }''')
            assert covered,'Fit clipped a nested label'
        assert not errors, errors
        browser.close()
    print('PASS large region browser/headless Open/Save/reopen parity (three sizes)')


if __name__ == '__main__':
    main()
