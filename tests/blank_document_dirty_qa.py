import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs

ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'index.html'
EXAMPLE=ROOT/'examples'/'01-source-hold.sov'

# A blank, untouched document is not dirty. Opening a file over one must never ask the user
# to discard changes that do not exist; one real edit must make the same prompt necessary.

async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page=await browser.new_page()
        dialogs=[]
        page.on('dialog', lambda dialog: (dialogs.append(dialog.message), asyncio.create_task(dialog.accept())))
        errors=[]
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        await page.goto(HTML.resolve().as_uri(), wait_until='load')
        await page.wait_for_timeout(250)

        # 1. A fresh editor's document is untouched; opening a file over it asks nothing.
        info=await page.evaluate('window.SovSchematicAPI.file.info()')
        assert info['dirty'] is False,info
        await page.locator('#fileOpenInput').set_input_files(str(EXAMPLE))
        await page.wait_for_timeout(200)
        assert len(dialogs)==0,dialogs
        info=await page.evaluate('window.SovSchematicAPI.file.info()')
        assert info['name']=='01-source-hold.sov' and info['dirty'] is False,info

        # 2. File -> New over a document nobody has touched since it was opened asks nothing.
        await page.evaluate('window.newSchematic()')
        await page.wait_for_timeout(120)
        assert len(dialogs)==0,dialogs
        info=await page.evaluate('window.SovSchematicAPI.file.info()')
        assert info['name']=='Untitled.sov' and info['dirty'] is False,info

        # 3. One edit makes the blank document dirty; opening a file now asks exactly once.
        await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:240,y:180})")
        info=await page.evaluate('window.SovSchematicAPI.file.info()')
        assert info['dirty'] is True,info
        before=len(dialogs)
        await page.locator('#fileOpenInput').set_input_files(str(EXAMPLE))
        await page.wait_for_timeout(200)
        assert len(dialogs)-before==1,dialogs
        info=await page.evaluate('window.SovSchematicAPI.file.info()')
        assert info['name']=='01-source-hold.sov' and info['dirty'] is False,info

        # 4. Restoring browser recovery counts the document as dirty: the recovered snapshot is
        # not the file on disk, even though nothing has been typed since the restore.
        await page.evaluate('window.SovSchematicAPI.document.saveRecovery()')
        before=len(dialogs)
        await page.evaluate('window.SovSchematicAPI.document.restoreRecovery()')
        await page.wait_for_timeout(120)
        assert len(dialogs)==before,dialogs
        info=await page.evaluate('window.SovSchematicAPI.file.info()')
        assert info['name']=='Recovered.sov' and info['dirty'] is True,info

        assert not errors,errors
        await browser.close()
        print('PASS blank document dirty QA')

asyncio.run(main())
