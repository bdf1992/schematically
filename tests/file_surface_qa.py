import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs

ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'index.html'

async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page=await browser.new_page(accept_downloads=True)
        errors=[]
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        await page.set_content(HTML.read_text(), wait_until='load')
        await page.wait_for_timeout(250)
        assert await page.locator('#fileBtn').count()==1
        assert await page.locator('#saveBtn').count()==0
        assert await page.locator('#clearBtn').count()==0
        assert await page.locator('#exportBtn').count()==0
        await page.click('#fileBtn')
        assert await page.locator('#fileMenu').is_visible()
        assert await page.locator('#fileExportPakBtn').count()==1
        # Browser API + package contract
        pkg=await page.evaluate('window.SovSchematicAPI.file.package()')
        assert pkg['schema']=='soveraeign.schematic/package@0.1'
        assert pkg['document']['schema']=='soveraeign.schematic/document@0.1'
        assert isinstance(pkg['templates'],list) and len(pkg['templates'])>=1
        # Save .sov fallback download
        await page.click('#fileBtn') if not await page.locator('#fileMenu').is_visible() else None
        async with page.expect_download() as info:
            await page.click('#fileSaveBtn')
        dl=await info.value
        sov_path=ROOT/'tests'/'saved-test.sov'
        await dl.save_as(sov_path)
        sov=json.loads(sov_path.read_text())
        assert sov['schema']=='soveraeign.schematic/document@0.1'
        # Export package
        await page.click('#fileBtn')
        async with page.expect_download() as info2:
            await page.click('#fileExportPakBtn')
        dl2=await info2.value
        pak_path=ROOT/'tests'/'saved-test.sovpak'
        await dl2.save_as(pak_path)
        pak=json.loads(pak_path.read_text())
        assert pak['schema']=='soveraeign.schematic/package@0.1'
        assert pak['workspace']['view'] is not None
        assert len(pak['templates'])>=1
        # API parse accepts both formats
        parse_doc=await page.evaluate('(text)=>window.SovSchematicAPI.file.parse(text)', sov_path.read_text())
        parse_pak=await page.evaluate('(text)=>window.SovSchematicAPI.file.parse(text)', pak_path.read_text())
        assert parse_doc['format']=='document'
        assert parse_pak['format']=='package'
        # Open input accepts the real .sov file. Current doc initially empty so no destructive dialog needed after save.
        await page.click('#fileBtn')
        await page.locator('#fileOpenInput').set_input_files(str(sov_path))
        await page.wait_for_timeout(200)
        info=await page.evaluate('window.SovSchematicAPI.file.info()')
        assert info['name']=='saved-test.sov'
        assert 'failed' not in (await page.locator('#status').inner_text()).lower()
        # File -> New owns destructive clear semantics and returns to unsaved file state.
        await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:240,y:180})")
        page.on('dialog', lambda dialog: asyncio.create_task(dialog.accept()))
        await page.evaluate('window.newSchematic()')
        await page.wait_for_timeout(120)
        count=await page.evaluate("window.SovSchematicAPI.list('component').result.length")
        assert count==0
        new_info=await page.evaluate('window.SovSchematicAPI.file.info()')
        assert new_info['name']=='Untitled.sov' and new_info['dirty'] is True
        await page.evaluate('window.setFileMenu(true)')
        await page.screenshot(path=str(ROOT/'tests'/'file-menu.png'), full_page=False)
        assert not errors, errors
        await browser.close()
        print('PASS file surface QA')

asyncio.run(main())
