"""Reviewed source diagrams preserve topology, palette, pins and graphic assets.

--out DIR retains real editor screenshots and standalone SVG downloads.
"""
import argparse
import json
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
LABELS = '.component-label,.outside-label,.dimensional-point-label,.connection-label'


def topology(doc):
    return {
        'components': [{k: c.get(k) for k in ('id', 'symbolId', 'x', 'y', 'parentId', 'canvasId', 'placement')}
                       for c in doc['components']],
        'wires': [{**{k: w.get(k) for k in ('id', 'a', 'aSide', 'b', 'bSide', 'canvasId')},
                   **{k: w.get('config', {}).get(k) for k in ('direction', 'forwardOperation', 'reverseOperation')}}
                  for w in doc['wires']],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as td, sync_playwright() as p:
        out = args.out or Path(td)
        out.mkdir(parents=True, exist_ok=True)
        browser = p.chromium.launch(**chromium_launch_kwargs())
        for source in sorted((ROOT/'examples/swarm').glob('*.sov')):
            raw = json.loads(source.read_text(encoding='utf-8'))
            original = json.loads((ROOT/'tests/fixtures/swarm-originals'/source.name).read_text(encoding='utf-8'))
            assert topology(raw) == topology(original), source.name
            assert raw['meta']['notes'] == original['meta']['notes']
            for a, b in zip(raw['components'], original['components']):
                assert a['config']['presentation']['size'] == b['config']['presentation']['size']
                assert raw['meta']['originalLabels'][a['id']] == b['config']['label']
            expected_pins = sorted(c['id'] for c in raw['components'] if c.get('editor', {}).get('pinned'))
            expected_graphics = sum(c['config']['presentation']['graphic']['kind'] == 'custom' for c in raw['components'])
            assert expected_pins and len(expected_pins) < len(raw['components'])
            assert expected_graphics >= 1
            for width in (768, 1440):
                for theme in ('light', 'dark'):
                    page = browser.new_page(viewport={'width': width, 'height': 900}, accept_downloads=True)
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.on('dialog', lambda d: d.accept())
                    page.add_init_script('window.showSaveFilePicker=undefined;window.showOpenFilePicker=undefined;')
                    page.goto((ROOT/'index.html').as_uri())
                    page.locator('#fileOpenInput').set_input_files(str(source))
                    page.wait_for_function('(id)=>nodes.some(n=>n.id===id)', arg=raw['components'][0]['id'])
                    page.evaluate('(t)=>{SovSchematicAPI.view.setAppearance(t);fitDiagram()}', theme)
                    page.wait_for_timeout(100)
                    admitted = page.evaluate('snapshotDocument()')
                    assert page.locator('.custom-graphic').count() == expected_graphics
                    assert sorted(c['id'] for c in admitted['components'] if c.get('editor', {}).get('pinned')) == expected_pins
                    colors = page.evaluate("wires.map(w=>[w.id,endpointConnection(w,'a').colorSlot,endpointConnection(w,'b').colorSlot])")
                    assert all(a == b and a in (6, 9, 10, 11) for _, a, b in colors), colors
                    label_pixels = page.evaluate('''sel=>[...workspace.querySelectorAll(sel)].map(el=>{
                      const m=el.getScreenCTM();return [el.textContent,parseFloat(getComputedStyle(el).fontSize)*Math.hypot(m.a,m.b)];
                    })''', LABELS)
                    assert all(px >= 11.9 for _, px in label_pixels), label_pixels
                    stem = f'{source.stem}-{width}-{theme}'
                    page.screenshot(path=str(out/(stem+'.png')))
                    for button, suffix in (('#fileSaveBtn', 'sov'), ('#fileExportPakBtn', 'sovpak')):
                        with page.expect_download() as info:
                            page.click('#fileBtn'); page.click(button)
                        saved = Path(td)/f'{source.stem}-saved.{suffix}'
                        info.value.save_as(saved)
                        page.locator('#fileOpenInput').set_input_files(str(saved))
                        page.wait_for_function('(name)=>SovSchematicAPI.file.info().name===name', arg=saved.name)
                        reopened = page.evaluate('snapshotDocument()')
                        assert reopened['components'] == admitted['components'], (stem, suffix, 'components')
                        assert reopened['wires'] == admitted['wires'], (stem, suffix, 'wires')
                        # updatedAt is volatile; timeScale package precedence is a separately
                        # rate-policy defect (#40), outside this presentation acceptance.
                        for key in raw['meta']:
                            if key != 'timeScale':
                                assert reopened['meta'][key] == admitted['meta'][key], (stem, suffix, key)
                        assert page.locator('.custom-graphic').count() == expected_graphics
                        if suffix == 'sovpak':
                            package = json.loads(saved.read_text(encoding='utf-8'))
                            assert package['assets'], stem
                    page.evaluate('selectNode(null);fitDiagram()')
                    with page.expect_download() as info:
                        page.click('#fileBtn'); page.click('#fileExportSvgBtn')
                    exported = out/(stem+'.svg')
                    info.value.save_as(exported)
                    text = exported.read_text(encoding='utf-8')
                    assert text.count('class="custom-graphic"') == expected_graphics
                    assert 'font-size:' in text and '<script' not in text and 'javascript:' not in text
                    # Normal view controls provide intentional pan/zoom at narrow widths.
                    if width == 768:
                        before = page.evaluate('snapshotDocument()')
                        zoom_before = page.evaluate('currentZoom()')
                        page.locator('#zoomInBtn').click()
                        assert page.evaluate('currentZoom()') > zoom_before
                        assert page.evaluate('snapshotDocument()') == before
                    assert not errors, errors
                    page.close()
        browser.close()
    print('PASS reviewed swarm fixtures: topology, captions, palette, pins, graphics, file/package/SVG, both widths/themes')


if __name__ == '__main__':
    main()
