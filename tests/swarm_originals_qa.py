"""Original swarm review documents retain geometry and topology through real file I/O.

Fixtures are byte-identical copies from the owner's swarm-schematic-review.zip.
This checks document/painted geometry and usable port targets, not visual quality.
"""
import hashlib
import json
import math
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/swarm-originals'
HASHES = {
    '01-platform.sov': '78706443c685bd53b1d980046980869341a1db33ac83c8afda8f2a7946705342',
    '02-service-circuit.sov': 'd645604d7b6d08d499bc19ba124a651f1bcc6f694a8f867e408878a87f5a49a1',
    '03-collaboration.sov': '1b7560782d624f03f5a8092da0b991053ae39b079d5ec33489d563a9a8e500e9',
}


def unchanged_fixtures():
    for name, expected in HASHES.items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == expected, name


def assert_authored_document(actual, source, stage):
    """Compare against the supplied file, allowing only omitted schema defaults."""
    for collection in ('components', 'wires'):
        expected = {item['id']: item for item in source[collection]}
        found = {item['id']: item for item in actual[collection]}
        assert len(found) == len(actual[collection]) == len(expected), (stage, collection)
        assert found.keys() == expected.keys(), (stage, collection, found.keys(), expected.keys())
        for entity_id, authored in expected.items():
            current = found[entity_id]
            context = (stage, collection, entity_id)
            if collection == 'components':
                for key in ('symbolId', 'parentId'):
                    assert current.get(key) == authored.get(key), (context, key, current.get(key))
                canvas = authored.get('canvasId', 'canvas:global')
                assert current.get('canvasId', 'canvas:global') == canvas, (context, 'canvasId')
                if 'placement' in authored:
                    assert current['placement'] == authored['placement'], (context, 'placement')
                for axis in ('x', 'y'):
                    assert math.isclose(current[axis], authored[axis], abs_tol=1e-7), (context, axis, current[axis], authored[axis])
                # Point footprints are fixed by their 0D form, independent of
                # presentation.size. All authored rectangular sizes must survive.
                if authored['symbolId'] != 'point':
                    assert current['config']['presentation']['size'] == authored['config']['presentation']['size'], (context, 'size')
            else:
                for key in ('a', 'aSide', 'b', 'bSide', 'canvasId'):
                    assert current[key] == authored[key], (context, key, current[key], authored[key])
                for key, default in (('direction', 'forward'), ('forwardOperation', 'none'), ('reverseOperation', 'none')):
                    assert current['config'].get(key, default) == authored['config'].get(key, default), (context, key)


def assert_painted_geometry(page, source, stage):
    painted = page.evaluate('''() => nodes.map(n => {
      const group=[...document.querySelectorAll('.node')].find(el=>el.dataset.id===n.id);
      const body=group.querySelector(':scope > .body');
      const rect=body?.getBBox();
      return {id:n.id,x:n.x,y:n.y,size:componentSize(n),
        body:rect?{w:rect.width,h:rect.height}:null};
    })''')
    by_id = {node['id']: node for node in painted}
    authored = {node['id']: node for node in source['components']}
    for node in source['components']:
        if node['symbolId'] == 'point':
            continue
        size = node['config']['presentation']['size']
        actual = by_id[node['id']]
        assert actual['size'] == size, (stage, node['id'], actual)
        assert actual['body'] == size, (stage, node['id'], 'painted rectangle', actual)
        parent_id = node.get('parentId')
        if parent_id:
            parent = authored[parent_id]
            host_size = parent['config']['presentation']['size']
            for axis, extent in (('x', 'w'), ('y', 'h')):
                assert abs(actual[axis] - parent[axis]) + size[extent] / 2 <= host_size[extent] / 2, (stage, node['id'], 'outside authored host', axis)


def assert_connected_ports(page, source, stage):
    endpoints = {}
    for wire in source['wires']:
        for end in ('a', 'b'):
            endpoints.setdefault(wire[end], set()).add((wire[end + 'Side'], wire['canvasId']))
    for component_id, ports in endpoints.items():
        page.evaluate('(id)=>selectNode(id,{focus:false})', component_id)
        for side, canvas in ports:
            target = page.locator(f'.node[data-id="{component_id}"].selected .port-hit[data-side="{side}"]')
            assert target.count() == 1, (stage, component_id, side, 'missing actual port target')
            assert target.is_visible(), (stage, component_id, side, 'hidden port target')
            assert target.evaluate("el=>getComputedStyle(el).pointerEvents!=='none'&&Number(el.getAttribute('r'))>0"), (stage, component_id, side, 'inactive port target')
            assert canvas in target.get_attribute('data-canvas-ids').split(), (stage, component_id, side, canvas, 'port surface')


def check_editor(page, source, stage):
    actual = page.evaluate('snapshotDocument()')
    assert_authored_document(actual, source, stage)
    assert_painted_geometry(page, source, stage)
    assert_connected_ports(page, source, stage)
    assert page.evaluate('snapshotDocument()') == actual, (stage, 'inspection changed document')
    return actual


def main():
    unchanged_fixtures()
    try:
        with tempfile.TemporaryDirectory() as td, sync_playwright() as p:
            browser = p.chromium.launch(**chromium_launch_kwargs())
            for name in HASHES:
                path = FIXTURES / name
                source = json.loads(path.read_text(encoding='utf-8'))
                page = browser.new_page(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
                page.add_init_script('window.showSaveFilePicker=undefined;window.showOpenFilePicker=undefined;')
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('dialog', lambda dialog: dialog.accept())
                page.goto((ROOT / 'index.html').as_uri())
                page.locator('#fileOpenInput').set_input_files(str(path))
                page.wait_for_function('(name)=>SovSchematicAPI.file.info().name===name', arg=name)
                baseline = check_editor(page, source, name + ' Open')
                for button, suffix in (('#fileSaveBtn', 'sov'), ('#fileExportPakBtn', 'sovpak')):
                    with page.expect_download() as download:
                        page.click('#fileBtn')
                        page.click(button)
                    saved = Path(td) / f'{path.stem}-reopened.{suffix}'
                    download.value.save_as(saved)
                    payload = json.loads(saved.read_text(encoding='utf-8'))
                    saved_doc = payload['document'] if suffix == 'sovpak' else payload
                    assert_authored_document(saved_doc, source, name + ' download ' + suffix)
                    # Packages include derived schema defaults; compare the
                    # authored fields here and the full compact snapshot on reopen.
                    if suffix == 'sov':
                        for collection in ('components', 'wires'):
                            assert saved_doc[collection] == baseline[collection], (name, suffix, 'download changed', collection)
                    page.locator('#fileOpenInput').set_input_files(str(saved))
                    page.wait_for_function('(name)=>SovSchematicAPI.file.info().name===name', arg=saved.name)
                    reopened = check_editor(page, source, name + ' reopen ' + suffix)
                    for collection in ('components', 'wires'):
                        assert reopened[collection] == baseline[collection], (name, suffix, 'reopen changed', collection)
                assert not errors, (name, errors)
                page.close()
                print(f'PASS {name}: authored sizes, painted rectangles, containment, topology, ports, Save/package/reopen')
            browser.close()
    finally:
        unchanged_fixtures()
    print('PASS all three original swarm fixtures; source bytes unchanged')


if __name__ == '__main__':
    main()
