"""The document's rate beats the view's (issue #40).

Node: admitTimeScale's table, and validateDocument's refusal/admission of it.
HTTP/MCP: GET/PUT /api/v1/document keep or refuse meta.timeScale the same way.
Browser: an authored meta.timeScale survives save, package export and reopen;
zero is paused (no wire packet animates); the view's own playback speed never
moves the document's rate.
"""
from __future__ import annotations
import json
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib import request, error

from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def http_json(url, method='GET', payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = request.Request(url, data=body, method=method, headers={'content-type': 'application/json'})
    try:
        with request.urlopen(req, timeout=4) as res:
            return res.status, json.loads(res.read())
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# --- Node: admitTimeScale's own table, and validateDocument reading it. ----------------------
node_script = r"""
import {pathToFileURL} from 'node:url';
await import(pathToFileURL(process.env.ATTACHMENT_CORE).href);
await import(pathToFileURL(process.env.DATA_CORE).href);
const Data=globalThis.SovSchematicData;
const results={};

// undefined, 0, 0.5, 2, 20, -1, NaN, Infinity, null, '2', true.
const table=[undefined,0,0.5,2,20,-1,NaN,Infinity,null,'2',true];
results.admitted=table.map(v=>Data.admitTimeScale(v));

const doc=Data.makeDocument({id:'schematic-1'});
doc.meta.timeScale=-1;
results.refusedNegative=Data.validateDocument(doc);

const doc0=Data.makeDocument({id:'schematic-1'});
doc0.meta.timeScale=0;
results.admittedZero=Data.validateDocument(doc0);

console.log(JSON.stringify(results));
"""


def run_node():
    import os
    env = dict(**os.environ, ATTACHMENT_CORE=str(ROOT / 'src/06-attachment-core.js'), DATA_CORE=str(ROOT / 'src/05-data-core.js'))
    proc = subprocess.run(['node', '--input-type=module', '-e', node_script], cwd=ROOT, capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


results = run_node()
admitted = results['admitted']
assert admitted[0] == {'ok': True, 'present': False}, admitted[0]  # undefined
assert admitted[1] == {'ok': True, 'present': True, 'value': 0}, admitted[1]  # 0
assert admitted[2] == {'ok': True, 'present': True, 'value': 0.5}, admitted[2]  # 0.5
assert admitted[3] == {'ok': True, 'present': True, 'value': 2}, admitted[3]  # 2
assert admitted[4] == {'ok': True, 'present': True, 'value': 20}, admitted[4]  # 20 (no upper bound on admission)
for i, label in ((5, -1), (6, 'NaN'), (7, 'Infinity'), (8, None), (9, '2'), (10, True)):
    entry = admitted[i]
    assert entry['ok'] is False and entry['code'] == 'TIME_SCALE_INVALID', (label, entry)
    assert entry['message'].startswith('TIME_SCALE_INVALID: meta.timeScale must be a finite number >= 0, not '), entry

assert results['refusedNegative']['ok'] is False, results['refusedNegative']
assert any('TIME_SCALE_INVALID' in e for e in results['refusedNegative']['errors']), results['refusedNegative']
assert results['admittedZero']['ok'] is True, results['admittedZero']
print('PASS timescale policy: admitTimeScale table, validateDocument -1/0')


# --- HTTP: GET/PUT /api/v1/document, over a copy of a swarm fixture (meta.timeScale 0). -------
with tempfile.TemporaryDirectory() as td:
    source = ROOT / 'examples/swarm/01-platform.sov'
    file = Path(td) / 'timescale-http.sov'
    file.write_text(source.read_text(encoding='utf-8'), encoding='utf-8')
    port = free_port()
    base = f'http://127.0.0.1:{port}'
    proc = subprocess.Popen(['node', str(ROOT / 'mcp/server.mjs'), '--port', str(port), '--file', str(file)],
                             cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(50):
            try:
                status, _ = http_json(base + '/api/v1/formats')
                if status == 200:
                    break
            except Exception:
                time.sleep(.05)
        else:
            raise AssertionError('server did not start')

        status, doc = http_json(base + '/api/v1/document')
        assert status == 200 and doc['meta']['timeScale'] == 0, doc

        bad = json.loads(json.dumps(doc))
        bad['meta']['timeScale'] = -1
        status, refused = http_json(base + '/api/v1/document', 'PUT', bad)
        assert status == 400 and not refused['ok'], refused
        assert any('TIME_SCALE_INVALID' in e for e in refused['errors']), refused

        status, still = http_json(base + '/api/v1/document')
        assert status == 200 and still['meta']['timeScale'] == 0, still
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
print('PASS timescale policy: GET keeps 0, PUT -1 refused by TIME_SCALE_INVALID')


# --- Browser: a 0 rate draws packets stopped, not moving. --------------------------------------
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')
EVIDENCE = json.loads((ROOT / 'examples/06-read-write-evidence.sov').read_text(encoding='utf-8'))
with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs())
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(200)
    page.evaluate('(doc)=>window.SovSchematicAPI.document.replace(doc)', EVIDENCE)
    page.evaluate('fitDiagram()')
    page.wait_for_timeout(200)

    # A live rate (1) animates: at least one packet carries an animateMotion element.
    moving = page.evaluate("()=>document.querySelectorAll('.wire-packet').length>0 && document.querySelectorAll('.wire-packet animateMotion').length>0")
    assert moving, 'expected at least one animated wire packet at the default rate'

    # The document's own rate at 0 pauses every packet: no animateMotion anywhere, packets stay.
    refusal = page.evaluate('()=>window.SovSchematicAPI.view.setGlobalRate(0)')
    assert refusal == 0, refusal
    page.wait_for_timeout(150)
    packetCount = page.evaluate("()=>document.querySelectorAll('.wire-packet').length")
    motionCount = page.evaluate("()=>document.querySelectorAll('.wire-packet animateMotion').length")
    assert packetCount > 0 and motionCount == 0, (packetCount, motionCount)

    # Rate back to 1: packets animate again.
    page.evaluate('()=>window.SovSchematicAPI.view.setGlobalRate(1)')
    page.wait_for_timeout(150)
    assert page.evaluate("()=>document.querySelectorAll('.wire-packet animateMotion').length") > 0

    assert not errors, errors
    browser.close()
print('PASS timescale policy: rate 0 pauses every packet, no animateMotion')


# --- Browser: an authored meta.timeScale survives save, package export and reopen; -------------
# the document's rate wins over the view's playback speed, which is kept apart in
# workspace.view.playbackSpeed and never written back into meta.timeScale.
with tempfile.TemporaryDirectory() as td, sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs())
    page = browser.new_page(accept_downloads=True)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('dialog', lambda d: d.accept())
    page.add_init_script('window.showSaveFilePicker=undefined;window.showOpenFilePicker=undefined;')
    page.goto((ROOT / 'index.html').as_uri())

    source = ROOT / 'examples/swarm/01-platform.sov'
    page.locator('#fileOpenInput').set_input_files(str(source))
    page.wait_for_function('(id)=>nodes.some(n=>n.id===id)', arg=json.loads(source.read_text(encoding='utf-8'))['components'][0]['id'])

    doc = page.evaluate('snapshotDocument()')
    assert doc['meta']['timeScale'] == 0, doc['meta']
    assert page.evaluate('globalTimeScale()') == 0

    def reopen_via(button, suffix):
        with page.expect_download() as info:
            page.click('#fileBtn')
            page.click(button)
        saved = Path(td) / f'timescale-roundtrip.{suffix}'
        info.value.save_as(saved)
        page.locator('#fileOpenInput').set_input_files(str(saved))
        page.wait_for_function('(name)=>SovSchematicAPI.file.info().name===name', arg=saved.name)
        return page.evaluate('snapshotDocument()')

    reopened_sov = reopen_via('#fileSaveBtn', 'sov')
    assert reopened_sov['meta']['timeScale'] == 0, reopened_sov['meta']
    assert page.evaluate('globalTimeScale()') == 0

    reopened_pak = reopen_via('#fileExportPakBtn', 'sovpak')
    assert reopened_pak['meta']['timeScale'] == 0, reopened_pak['meta']
    assert page.evaluate('globalTimeScale()') == 0

    # The document's own rate and the view's playback speed move independently.
    set_result = page.evaluate('()=>window.SovSchematicAPI.view.setGlobalRate(2)')
    assert set_result == 2, set_result
    speed_result = page.evaluate('()=>window.SovSchematicAPI.clock.setSpeed(4)')
    assert speed_result == 4, speed_result

    # Export at speed 4, then perturb the runtime speed before reopening: reopening must
    # restore it from the package's workspace.view.playbackSpeed, not from leftover state.
    with page.expect_download() as info:
        page.click('#fileBtn')
        page.click('#fileExportPakBtn')
    saved = Path(td) / 'timescale-roundtrip-rate2.sovpak'
    info.value.save_as(saved)
    page.evaluate('()=>window.SovSchematicAPI.clock.setSpeed(1)')
    page.locator('#fileOpenInput').set_input_files(str(saved))
    page.wait_for_function('(name)=>SovSchematicAPI.file.info().name===name', arg=saved.name)
    reopened_pak2 = page.evaluate('snapshotDocument()')
    assert reopened_pak2['meta']['timeScale'] == 2, reopened_pak2['meta']
    assert page.evaluate('()=>simClock.speed') == 4, page.evaluate('()=>simClock.speed')

    # A refused rate changes nothing: meta.timeScale stays at 2.
    refusal = page.evaluate('()=>window.SovSchematicAPI.view.setGlobalRate(-1)')
    assert isinstance(refusal, dict) and refusal.get('code') == 'TIME_SCALE_INVALID', refusal
    assert page.evaluate('snapshotDocument()')['meta']['timeScale'] == 2

    assert not errors, errors
    browser.close()
print('PASS timescale policy: meta.timeScale survives save/package/reopen, view speed stays apart')
