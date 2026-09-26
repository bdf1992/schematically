"""Fresh authored example: graphics, readable labels, ports, pins and real file round trips.

Optional --out DIR retains normal-editor/export screenshots as review evidence.
"""
import argparse
import json
import sys
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT=Path(__file__).resolve().parents[1]

SOURCE=ROOT/'examples/09-proposed-service-review.sov'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory() as td, sync_playwright() as p:
        out=args.out or Path(td)
        out.mkdir(parents=True,exist_ok=True)
        browser=p.chromium.launch(**chromium_launch_kwargs())
        for width in (768,1440):
            for theme in ('light','dark'):
                page=browser.new_page(viewport={'width':width,'height':900},accept_downloads=True)
                page.add_init_script('window.showSaveFilePicker=undefined;window.showOpenFilePicker=undefined;')
                errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('dialog',lambda d:d.accept())
                page.goto((ROOT/'index.html').as_uri())
                page.locator('#fileOpenInput').set_input_files(str(SOURCE))
                page.wait_for_function("nodes.some(n=>n.id==='service')")
                page.evaluate('(theme)=>{SovSchematicAPI.view.setAppearance(theme);fitDiagram()}',theme)
                original=page.evaluate('snapshotDocument()')
                assert page.locator('.node .custom-graphic').count()==2
                slots=page.evaluate("wires.map(w=>[w.id,endpointConnection(w,'a').colorSlot,endpointConnection(w,'b').colorSlot])")
                assert slots==[['request',10,10],['admit',10,10],['control',11,11],['record',9,9]],slots
                assert page.locator('#objectsList .is-pinned').count()==2
                # Screen pixels, not the nominal zoom readout. Check independently
                # that essential labels neither clip nor overlap other labels/nodes.
                review=page.evaluate('''()=>{
                  const labels=[...workspace.querySelectorAll('.component-label,.dimensional-point-label,.connection-label')];
                  const viewport=workspace.getBoundingClientRect();
                  const overlaps=(a,b)=>a.left<b.right-1&&a.right>b.left+1&&a.top<b.bottom-1&&a.bottom>b.top+1;
                  const bad=[];
                  for(let i=0;i<labels.length;i++){
                    const el=labels[i],r=el.getBoundingClientRect(),m=el.getScreenCTM();
                    const pixels=parseFloat(getComputedStyle(el).fontSize)*Math.hypot(m.a,m.b);
                    if(pixels<11.9||r.left<viewport.left||r.right>viewport.right||r.top<viewport.top||r.bottom>viewport.bottom)bad.push(['clipped/small',el.textContent,pixels]);
                    for(let j=i+1;j<labels.length;j++)if(overlaps(r,labels[j].getBoundingClientRect()))bad.push(['labels',el.textContent,labels[j].textContent]);
                    for(const body of workspace.querySelectorAll('.node:not(.is-container)>.body'))if(body.closest('.node')!==el.closest('.node')&&overlaps(r,body.getBoundingClientRect()))bad.push(['node',el.textContent,body.closest('.node').dataset.id]);
                  }
                  return bad;
                }''')
                assert not review,(width,theme,review)
                page.screenshot(path=str(out/f'fresh-{width}-{theme}.png'))
                # The selected custom shape keeps its actual semantic ports.
                page.evaluate("selectNode('team',{focus:false})")
                assert page.locator('.node[data-id="team"] .port-hit').count()>0
                assert page.locator('.node[data-id="team"] .custom-graphic').count()==1
                # A pinned host refuses a pointer drag. Semantic label edits work.
                page.evaluate("selectNode('service',{focus:false})")
                box=page.locator('.node[data-id="service"]>.body').bounding_box()
                page.mouse.move(box['x']+24,box['y']+24)
                page.mouse.down();page.mouse.move(box['x']+80,box['y']+60,steps=5);page.mouse.up()
                assert page.evaluate("nodes.find(n=>n.id==='service').x")==680
                result=page.evaluate("SovSchematicAPI.update('component','service',{config:{label:'Reviewed service'}})")
                assert result['ok']
                page.evaluate('SovSchematicAPI.history.undo()')
                # Normal Pin checkbox and history; a parent carries pinned children.
                page.evaluate("selectNode('service',{focus:false});openSelectionSettings('component')")
                page.locator('#entityPin').uncheck()
                page.wait_for_timeout(300)
                assert not page.evaluate("nodes.find(n=>n.id==='service').editor.pinned")
                page.evaluate('closeSelectionSettings();workspace.focus()')
                before=page.evaluate("nodes.filter(n=>['service','grant'].includes(n.id)).map(n=>n.x)")
                page.keyboard.press('ArrowRight');page.wait_for_timeout(300)
                after=page.evaluate("nodes.filter(n=>['service','grant'].includes(n.id)).map(n=>n.x)")
                assert after[0]>before[0] and after[0]-before[0]==after[1]-before[1],(before,after)
                page.evaluate('SovSchematicAPI.history.undo();SovSchematicAPI.history.undo()')
                assert page.evaluate("nodes.find(n=>n.id==='service').editor.pinned")
                for button,suffix in (('#fileSaveBtn','sov'),('#fileExportPakBtn','sovpak')):
                    with page.expect_download() as info:
                        page.click('#fileBtn');page.click(button)
                    saved=Path(td)/f'reopened.{suffix}'
                    info.value.save_as(saved)
                    page.locator('#fileOpenInput').set_input_files(str(saved))
                    page.wait_for_function('(name)=>SovSchematicAPI.file.info().name===name',arg=saved.name)
                    actual=page.evaluate('snapshotDocument()')
                    assert actual['components']==original['components'],(width,theme,suffix)
                    assert actual['wires']==original['wires']
                    assert page.locator('.node .custom-graphic').count()==2
                    if suffix=='sovpak':
                        assert len(json.loads(saved.read_text(encoding='utf-8'))['assets'])==2
                page.evaluate('selectNode(null);fitDiagram()')
                page.screenshot(path=str(out/f'reopened-{width}-{theme}.png'))
                with page.expect_download() as info:
                    page.click('#fileBtn');page.click('#fileExportSvgBtn')
                native=out/f'native-{width}-{theme}.svg'
                info.value.save_as(native)
                exported=native.read_text(encoding='utf-8')
                assert 'background-color:' in exported and 'font-size:' in exported
                assert 'class="port-hit"' not in exported
                assert not errors,errors
                page.close()
        browser.close()
        for theme in ('light','dark'):
            subprocess.run([sys.executable,str(ROOT/'scripts/export_svg.py'),str(SOURCE),
                            '--out',str(out/theme),'--appearance',theme],check=True,cwd=ROOT)
            svg=out/theme/(SOURCE.stem+'.svg')
            text=svg.read_text(encoding='utf-8')
            assert text.count('class="custom-graphic"')==2
            assert '<script' not in text and 'javascript:' not in text
            browser=p.chromium.launch(**chromium_launch_kwargs())
            page=browser.new_page(viewport={'width':1440,'height':900})
            page.goto(svg.as_uri())
            page.screenshot(path=str(out/f'export-{theme}.png'))
            browser.close()
    print('PASS fresh authoring review: two themes, two widths, graphics, ports, pins, file/package/SVG')


if __name__=='__main__':
    main()
