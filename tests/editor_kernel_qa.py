import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'index.html'
async def main():
  async with async_playwright() as p:
    browser=await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page=await browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    await page.set_content(HTML.read_text(),wait_until='load');await page.wait_for_timeout(350)
    # Create two components.
    await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:250,y:220,config:{label:'Alpha'}})")
    await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'buffer',x:460,y:260,config:{label:'Beta'}})")
    await page.wait_for_timeout(450);await page.evaluate("commitHistoryCapture('Create QA components')")
    ids=await page.evaluate("window.SovSchematicAPI.list('component').result.map(x=>x.id)")
    assert len(ids)==2
    # Multi-select + semantic copy/paste.
    await page.evaluate('(ids)=>{setComponentSelection(ids,ids[1]);selectNode(ids[1],{focus:false,preserveSet:true});copySelection();pasteClipboard();}',ids)
    await page.wait_for_timeout(150)
    count=await page.evaluate("window.SovSchematicAPI.list('component').result.length")
    assert count==4
    # Undo/redo the paste.
    await page.wait_for_timeout(450);await page.evaluate('commitHistoryCapture()');assert await page.evaluate('undoHistory()')
    await page.wait_for_timeout(100);assert await page.evaluate("window.SovSchematicAPI.list('component').result.length")==2
    assert await page.evaluate('redoHistory()');await page.wait_for_timeout(100);assert await page.evaluate("window.SovSchematicAPI.list('component').result.length")==4
    # Pin/lock are effectful and persisted.
    first=(await page.evaluate("window.SovSchematicAPI.list('component').result"))[0]['id']
    state=await page.evaluate('(id)=>{const n=nodes.find(x=>x.id===id);entityEditorState(n).pinned=true;entityEditorState(n).locked=true;render();return entityEditorState(n)}',first)
    assert state['pinned'] and state['locked']
    # Checkpoint persists.
    cp=await page.evaluate("createCheckpoint('QA checkpoint')");assert cp['name']=='QA checkpoint'
    assert len(await page.evaluate('listCheckpoints()'))>=1
    # Search overlay and Objects fallback.
    await page.evaluate("selectNode(null);openQuickSearch('Alpha')");await page.wait_for_timeout(80)
    assert await page.locator('#quickSearch').is_visible();assert await page.locator('.search-match').count()>=1
    await page.evaluate('closeQuickSearch()');assert await page.locator('#objectsList .object-row').count()>=4
    # Appearance and rate affect state.
    await page.evaluate("appearanceMode='dark';applyAppearanceMode();setGlobalTimeScale(2)")
    assert await page.evaluate("document.documentElement.dataset.appearance")=='dark'
    assert await page.evaluate('globalTimeScale()')==2
    # No legacy KEYS badge.
    assert 'KEYS' not in await page.locator('body').inner_text()
    assert not errors,errors
    await browser.close();print('PASS editor kernel QA')
asyncio.run(main())
