"""A document can carry its own palette (meta.palette).

Node: admitPalette's table, and validateDocument's refusal/admission of it.
HTTP/MCP: PUT /api/v1/document refuses an unknown palette name and keeps a known one.
Browser: the document's palette wins over the view's when the document opens; custom
hexes are realised as the view's custom row is; a refused value changes nothing; the
picker writes the document while the document declares a palette and the view otherwise;
save, package export and reopen keep meta.palette as authored and never put it in the view.
"""
from __future__ import annotations
import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib import request, error

from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
NAMES = ['okabe-ito', 'system-default', 'spectrum', 'cool', 'warm', 'earth', 'mono']
# Six hexes, case as an author might write it; #FFFFEE cannot hold any theme's floor on a light canvas.
HEXES = ['#C84E64', '#FFFFEE', '#aBcDeF', '#58A27C', '#4e86be', '#8B63B2']
FIVE = HEXES[:5]


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


# --- (a) Node: admitPalette's own table, and validateDocument reading it. ---------------------
node_script = r"""
import {pathToFileURL} from 'node:url';
await import(pathToFileURL(process.env.ATTACHMENT_CORE).href);
await import(pathToFileURL(process.env.DATA_CORE).href);
const Data=globalThis.SovSchematicData;
const input=JSON.parse(process.env.PALETTE_TABLE);
const results={names:[...Data.PALETTE_NAMES]};
results.absent=Data.admitPalette(undefined);
results.named=input.names.map(v=>Data.admitPalette(v));
results.custom=Data.admitPalette({custom:input.hexes});
results.unknown=input.unknown.map(v=>Data.admitPalette(v));
results.invalid=input.invalid.map(v=>Data.admitPalette(v));

const bad=Data.makeDocument({id:'schematic-1'});
bad.meta.palette='nope';
results.refusedNope=Data.validateDocument(bad);
const good=Data.makeDocument({id:'schematic-1'});
good.meta.palette='spectrum';
results.admittedSpectrum=Data.validateDocument(good);

console.log(JSON.stringify(results));
"""

UNKNOWN = ['nope', 'custom', '']
INVALID = [None, 5, True, [], {'custom': FIVE}, {'custom': FIVE + ['red']}, {'custom': HEXES, 'extra': 1}, {'slots': HEXES}]


def run_node():
    table = json.dumps({'names': NAMES, 'hexes': HEXES, 'unknown': UNKNOWN, 'invalid': INVALID})
    env = dict(**os.environ, ATTACHMENT_CORE=str(ROOT / 'src/06-attachment-core.js'),
               DATA_CORE=str(ROOT / 'src/05-data-core.js'), PALETTE_TABLE=table)
    proc = subprocess.run(['node', '--input-type=module', '-e', node_script], cwd=ROOT, capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


results = run_node()
assert results['names'] == NAMES, results['names']
assert results['absent'] == {'ok': True, 'present': False}, results['absent']
for name, entry in zip(NAMES, results['named']):
    assert entry == {'ok': True, 'present': True, 'value': name}, (name, entry)
assert results['custom'] == {'ok': True, 'present': True, 'value': {'custom': HEXES}}, results['custom']
for value, entry in zip(UNKNOWN, results['unknown']):
    assert entry['ok'] is False and entry['code'] == 'PALETTE_UNKNOWN', (value, entry)
    assert entry['message'] == f'PALETTE_UNKNOWN: meta.palette {json.dumps(value)} is not a known palette; known: {", ".join(NAMES)}', entry
for value, entry in zip(INVALID, results['invalid']):
    assert entry['ok'] is False and entry['code'] == 'PALETTE_INVALID', (value, entry)
    assert entry['message'].startswith('PALETTE_INVALID: meta.palette must be a palette name or {custom: [six #RRGGBB hexes]}, not '), entry
assert results['refusedNope']['ok'] is False, results['refusedNope']
assert any('PALETTE_UNKNOWN' in e for e in results['refusedNope']['errors']), results['refusedNope']
assert results['admittedSpectrum']['ok'] is True, results['admittedSpectrum']
print('PASS document palette (a): admitPalette table, validateDocument refuses nope and admits spectrum')


# --- (b) HTTP: PUT /api/v1/document, over a copy of a swarm fixture. --------------------------
with tempfile.TemporaryDirectory() as td:
    source = ROOT / 'examples/swarm/01-platform.sov'
    file = Path(td) / 'palette-http.sov'
    file.write_text(source.read_text(encoding='utf-8'), encoding='utf-8', newline='\n')
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
        assert status == 200 and 'palette' not in doc['meta'], doc['meta']

        bad = json.loads(json.dumps(doc))
        bad['meta']['palette'] = 'nope'
        status, refused = http_json(base + '/api/v1/document', 'PUT', bad)
        assert status == 400 and not refused['ok'], (status, refused)
        assert any('PALETTE_UNKNOWN' in e for e in refused['errors']), refused

        status, still = http_json(base + '/api/v1/document')
        assert status == 200 and still == doc, 'GET changed after a refused PUT'

        good = json.loads(json.dumps(doc))
        good['meta']['palette'] = 'spectrum'
        status, accepted = http_json(base + '/api/v1/document', 'PUT', good)
        assert status == 200, (status, accepted)
        status, after = http_json(base + '/api/v1/document')
        assert status == 200 and after['meta']['palette'] == 'spectrum', after['meta']
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
print('PASS document palette (b): PUT nope answers 400 PALETTE_UNKNOWN and GET is unchanged, PUT spectrum is kept')


# --- Browser ----------------------------------------------------------------------------------
PLAIN = json.loads((ROOT / 'examples/06-read-write-evidence.sov').read_text(encoding='utf-8'))
assert 'palette' not in PLAIN.get('meta', {}), 'the fixture must not declare a palette'


def with_palette(value):
    doc = json.loads(json.dumps(PLAIN))
    doc.setdefault('meta', {})['palette'] = value
    return doc


with tempfile.TemporaryDirectory() as td, sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs())
    page = browser.new_page(accept_downloads=True)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.on('dialog', lambda d: d.accept())
    page.add_init_script('window.showSaveFilePicker=undefined;window.showOpenFilePicker=undefined;')
    page.goto((ROOT / 'index.html').as_uri())
    page.wait_for_function('()=>!!window.SovSchematicAPI')

    def replace(doc):
        return page.evaluate('(doc)=>window.SovSchematicAPI.document.replace(doc)', doc)

    def six():
        return page.evaluate('()=>activePalette().slice(6)')

    def colour():
        return page.evaluate('()=>window.SovSchematicAPI.view.colour()')

    def meta():
        return page.evaluate('()=>snapshotDocument().meta')

    def write_sov(name, doc):
        path = Path(td) / name
        path.write_text(json.dumps(doc, indent=2), encoding='utf-8', newline='\n')
        return path

    def open_file(path):
        page.locator('#fileOpenInput').set_input_files(str(path))
        page.wait_for_function('(name)=>SovSchematicAPI.file.info().name===name', arg=path.name)

    page.evaluate("()=>{window.SovSchematicAPI.view.setAppearance('light');window.SovSchematicAPI.view.setColour({theme:'pastel',palette:'okabe-ito'})}")
    replace(PLAIN)

    # (c) The names the data core admits are the names the picker lists, custom apart.
    names = page.evaluate('()=>[...SovSchematicData.PALETTE_NAMES]')
    listed = colour()['palettes']
    assert sorted(names) == sorted(n for n in listed if n != 'custom'), (names, listed)
    options = page.evaluate("()=>[...document.querySelectorAll('#colorPaletteInput option')].map(o=>o.value)")
    assert sorted(names) == sorted(n for n in options if n != 'custom'), (names, options)
    print('PASS document palette (c): PALETTE_NAMES equals view.colour().palettes without custom')

    # (d) The document's palette wins over the view's.
    page.evaluate("()=>window.SovSchematicAPI.view.setColour({palette:'spectrum'})")
    spectrum_six = six()
    page.evaluate("()=>window.SovSchematicAPI.view.setColour({palette:'okabe-ito'})")
    okabe_six = six()
    assert len(spectrum_six) == 6 and spectrum_six != okabe_six, (spectrum_six, okabe_six)

    replace(with_palette('spectrum'))
    assert six() == spectrum_six, ('a document declaring spectrum must draw spectrum over the view', six(), spectrum_six)
    seen = colour()
    assert seen['palette'] == 'spectrum' and seen['source'] == 'document' and seen['viewPalette'] == 'okabe-ito', seen
    assert page.evaluate('()=>colorPaletteInput.value') == 'spectrum'
    assert page.evaluate('()=>colorEngine.palette') == 'okabe-ito'
    assert page.evaluate('()=>paletteSettings.dataset.paletteSource') == 'document'
    assert page.evaluate('()=>window.SovSchematicAPI.view.documentPalette()') == 'spectrum'
    assert page.evaluate('()=>window.SovSchematicAPI.view.paletteAudit().palette') == 'spectrum'

    replace(PLAIN)
    assert six() == okabe_six, ('a document without meta.palette must draw the view palette', six(), okabe_six)
    seen = colour()
    assert seen['palette'] == 'okabe-ito' and seen['source'] == 'view' and seen['viewPalette'] == 'okabe-ito', seen
    assert page.evaluate('()=>colorPaletteInput.value') == 'okabe-ito'
    assert page.evaluate('()=>paletteSettings.dataset.paletteSource') == 'view'
    assert page.evaluate('()=>window.SovSchematicAPI.view.documentPalette()') is None
    print('PASS document palette (d): meta.palette spectrum draws over the view okabe-ito, absent draws the view')

    # (e) Custom hexes take the view's custom row's path, in both appearances and all three themes.
    default_custom = page.evaluate('()=>[...colorEngine.custom]')
    cells = 0
    for appearance in ('light', 'dark'):
        for theme in ('pastel', 'subtle', 'reading'):
            page.evaluate('([a,t])=>{window.SovSchematicAPI.view.setAppearance(a);window.SovSchematicAPI.view.setColour({theme:t})}', [appearance, theme])
            replace(with_palette({'custom': HEXES}))
            cell = page.evaluate('''(hexes)=>({
                drawn:activePalette().slice(6),
                mapped:hexes.map(h=>themeColor(h)),
                floor:themeContrastFloor(),
                ratios:activePalette().slice(6).map(c=>contrastRatio(c,canvasTone())),
                name:effectivePaletteName(),
                viewRow:[...colorEngine.custom],
                editorShown:!customPaletteEditor.hidden
            })''', HEXES)
            assert cell['drawn'] == cell['mapped'], (appearance, theme, cell)
            assert cell['name'] == 'custom' and cell['editorShown'], (appearance, theme, cell)
            assert cell['viewRow'] == default_custom, ('the document must not write the view row', cell)
            assert all(r >= cell['floor'] for r in cell['ratios']), (appearance, theme, cell)
            replace(PLAIN)
            view_drawn = page.evaluate('''(hexes)=>{
                const kept=[...colorEngine.custom];
                colorEngine.custom.splice(0,6,...hexes);colorEngine.palette='custom';applyColorEngine();
                const drawn=activePalette().slice(6);
                colorEngine.custom.splice(0,6,...kept);colorEngine.palette='okabe-ito';applyColorEngine();
                return drawn;
            }''', HEXES)
            assert view_drawn == cell['drawn'], (appearance, theme, view_drawn, cell['drawn'])
            cells += 1
    assert cells == 6
    page.evaluate("()=>{window.SovSchematicAPI.view.setAppearance('light');window.SovSchematicAPI.view.setColour({theme:'pastel'})}")
    assert six() == okabe_six
    print('PASS document palette (e): custom hexes draw as the view custom row does and hold the floor in 6 theme x appearance cells')

    # (f) A refused value changes nothing: document.replace, file open, view.setDocumentPalette.
    opened = write_sov('palette-open.sov', with_palette('spectrum'))
    open_file(opened)
    before = page.evaluate('()=>JSON.stringify(snapshotDocument())')
    thrown = page.evaluate('(doc)=>{try{window.SovSchematicAPI.document.replace(doc);return null}catch(e){return String(e.message)}}', with_palette('nope'))
    assert thrown and 'PALETTE_UNKNOWN' in thrown, thrown
    assert page.evaluate('()=>JSON.stringify(snapshotDocument())') == before, 'a refused replace changed the open document'

    nope_file = write_sov('palette-nope.sov', with_palette('nope'))
    page.locator('#fileOpenInput').set_input_files(str(nope_file))
    page.wait_for_function("()=>statusEl.textContent.includes('Open failed')")
    status_text = page.evaluate('()=>statusEl.textContent')
    assert 'PALETTE_UNKNOWN' in status_text, status_text
    assert page.evaluate('()=>SovSchematicAPI.file.info().name') == opened.name
    assert page.evaluate('()=>JSON.stringify(snapshotDocument())') == before, 'a refused file open changed the open document'

    refusal = page.evaluate("()=>window.SovSchematicAPI.view.setDocumentPalette('nope')")
    assert isinstance(refusal, dict) and refusal.get('code') == 'PALETTE_UNKNOWN', refusal
    assert 'PALETTE_UNKNOWN' in page.evaluate('()=>statusEl.textContent')
    assert meta()['palette'] == 'spectrum'
    refusal = page.evaluate('(five)=>window.SovSchematicAPI.view.setDocumentPalette({custom:five})', FIVE)
    assert isinstance(refusal, dict) and refusal.get('code') == 'PALETTE_INVALID', refusal
    assert meta()['palette'] == 'spectrum' and six() == spectrum_six
    assert page.evaluate('()=>colorPaletteInput.value') == 'spectrum'
    print('PASS document palette (f): replace, file open and view.setDocumentPalette refuse and change nothing')

    # (g) The picker writes the document while the document declares a palette, the view otherwise.
    assert page.evaluate('()=>SovSchematicAPI.file.info().dirty') is False
    page.click('#paletteBtn')
    page.select_option('#colorPaletteInput', 'warm')
    assert meta()['palette'] == 'warm', meta()
    assert page.evaluate('()=>colorEngine.palette') == 'okabe-ito'
    assert page.evaluate('()=>SovSchematicAPI.file.info().dirty') is True
    warm_six = six()
    assert warm_six != spectrum_six
    assert page.evaluate('()=>window.SovSchematicAPI.history.undo()') is True
    assert meta()['palette'] == 'spectrum', meta()
    assert six() == spectrum_six and page.evaluate('()=>colorPaletteInput.value') == 'spectrum'

    # Picking custom on a document starts from the row drawn; a swatch edit writes the document's
    # row, the palette cache follows it, and undo takes the one edit back.
    page.select_option('#colorPaletteInput', 'custom')
    assert meta()['palette'] == {'custom': default_custom}, meta()
    set_result = page.evaluate('(hexes)=>window.SovSchematicAPI.view.setDocumentPalette({custom:hexes})', HEXES)
    assert set_result == {'custom': HEXES}, set_result
    page.evaluate('()=>commitHistoryCapture()')
    custom_six = six()
    edited = page.evaluate('''()=>{
        const input=customPaletteSwatches.children[2];
        input.value='#123456';input.dispatchEvent(new Event('input',{bubbles:true}));
        return {row:[...diagram.meta.palette.custom],view:[...colorEngine.custom],drawn:activePalette().slice(6),mapped:themeColor('#123456'),swatches:customPaletteSwatches.children.length};
    }''')
    assert edited['row'] == HEXES[:2] + ['#123456'] + HEXES[3:], edited
    assert edited['view'] == default_custom, edited
    assert edited['drawn'][2] == edited['mapped'] and edited['drawn'] != custom_six, edited
    assert edited['swatches'] == 6, edited
    assert page.evaluate('()=>window.SovSchematicAPI.history.undo()') is True
    assert meta()['palette'] == {'custom': HEXES}, meta()
    assert six() == custom_six
    assert page.evaluate('()=>customPaletteSwatches.children[2].value') == HEXES[2].lower()
    assert page.evaluate('()=>window.SovSchematicAPI.history.redo()') is True
    assert meta()['palette']['custom'][2] == '#123456' and six() == edited['drawn']

    replace(PLAIN)
    page.select_option('#colorPaletteInput', 'cool')
    assert page.evaluate('()=>colorEngine.palette') == 'cool'
    assert 'palette' not in meta(), meta()
    cool_six = six()
    assert colour()['source'] == 'view' and cool_six != okabe_six

    assert page.evaluate("()=>window.SovSchematicAPI.view.setDocumentPalette('warm')") == 'warm'
    assert six() == warm_six and colour()['source'] == 'document'
    assert page.evaluate('()=>window.SovSchematicAPI.view.setDocumentPalette(null)') is None
    assert 'palette' not in meta(), meta()
    assert six() == cool_six and colour()['source'] == 'view' and page.evaluate('()=>colorPaletteInput.value') == 'cool'
    page.click('#paletteBtn')
    print('PASS document palette (g): the picker writes meta.palette with undo while declared, the view otherwise; null removes it')

    # (h) Save and package export keep meta.palette as authored; the view never carries it.
    def reopen_via(button, name):
        with page.expect_download() as info:
            page.click('#fileBtn')
            page.click(button)
        saved = Path(td) / name
        info.value.save_as(saved)
        open_file(saved)
        return saved, page.evaluate('snapshotDocument()')

    open_file(write_sov('palette-named.sov', with_palette('spectrum')))
    assert page.evaluate('()=>colorEngine.palette') == 'cool'
    saved_sov, reopened = reopen_via('#fileSaveBtn', 'palette-roundtrip-name.sov')
    assert json.loads(saved_sov.read_text(encoding='utf-8'))['meta']['palette'] == 'spectrum'
    assert reopened['meta']['palette'] == 'spectrum' and six() == spectrum_six, reopened['meta']
    saved_pak, reopened = reopen_via('#fileExportPakBtn', 'palette-roundtrip-name.sovpak')
    package = json.loads(saved_pak.read_text(encoding='utf-8'))
    assert package['document']['meta']['palette'] == 'spectrum', package['document']['meta']
    assert package['workspace']['view']['colorEngine']['palette'] == 'cool', package['workspace']['view']['colorEngine']
    assert 'spectrum' not in json.dumps(package['workspace']), 'the package view carries the document palette'
    assert reopened['meta']['palette'] == 'spectrum' and six() == spectrum_six, reopened['meta']

    # A package whose view palette is cool and whose document declares spectrum draws spectrum,
    # opened over a page whose own view is on another palette.
    replace(PLAIN)
    page.evaluate("()=>window.SovSchematicAPI.view.setColour({palette:'okabe-ito'})")
    assert six() == okabe_six
    again = Path(td) / 'palette-reopen-cool.sovpak'
    again.write_text(saved_pak.read_text(encoding='utf-8'), encoding='utf-8', newline='\n')
    open_file(again)
    seen = colour()
    assert seen['palette'] == 'spectrum' and seen['source'] == 'document' and seen['viewPalette'] == 'cool', seen
    assert six() == spectrum_six

    open_file(write_sov('palette-custom.sov', with_palette({'custom': HEXES})))
    assert meta()['palette'] == {'custom': HEXES} and six() == custom_six
    saved_sov, reopened = reopen_via('#fileSaveBtn', 'palette-roundtrip-custom.sov')
    assert json.loads(saved_sov.read_text(encoding='utf-8'))['meta']['palette'] == {'custom': HEXES}
    assert reopened['meta']['palette'] == {'custom': HEXES}, reopened['meta']
    saved_pak, reopened = reopen_via('#fileExportPakBtn', 'palette-roundtrip-custom.sovpak')
    package = json.loads(saved_pak.read_text(encoding='utf-8'))
    assert package['document']['meta']['palette'] == {'custom': HEXES}, package['document']['meta']
    assert package['workspace']['view']['colorEngine'] == {**package['workspace']['view']['colorEngine'], 'palette': 'cool', 'custom': default_custom}
    assert reopened['meta']['palette'] == {'custom': HEXES} and six() == custom_six, reopened['meta']
    print('PASS document palette (h): .sov and .sovpak keep a name and {custom} as written; the package view keeps the view palette')

    # (i) Nothing above logged an error.
    assert not errors, errors
    browser.close()
print('PASS document palette (i): the page logs no errors')
