"""Native persistence page contract with mocked Tauri effects; not a native disk qualification.

Run only through the supervised QA entrypoint. The built index.html must match the source under
test. Real Rust write failure, atomic replacement and native reopen require the desktop gate.
"""
import asyncio
import argparse
import json
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
CASE_IDS=['native-launch-handle','native-save-current','native-save-failure-stays-dirty','native-save-cancel-stays-dirty','native-format-change-save-as','native-new-clears-association','native-api-open-clears-association','native-unreadable-launch-reports-failure']
if '--collect' in sys.argv:
    print(json.dumps(CASE_IDS))
    raise SystemExit(0)
parser=argparse.ArgumentParser()
parser.add_argument('--coverage-dir',type=Path,required=True)
options=parser.parse_args()
options.coverage_dir.mkdir(parents=True,exist_ok=True)
DOCUMENT = json.loads((ROOT / 'examples/01-source-hold.sov').read_text(encoding='utf-8'))
MOCK = """
window.__nativeCalls=[];
window.__native={token:'launch-token',name:'Native.sov',saved:null,cancel:false,fail:false};
window.__TAURI__={core:{invoke:async(command,args={})=>{
  window.__nativeCalls.push({command,args});
  if(command==='opened_document') {
    if(window.__launchError)throw new Error(window.__launchError);
    return window.__launchDocument;
  }
  if(command==='report_loaded')return null;
  if(command==='desktop_reset_document'){window.__native.token=null;return null;}
  if(command==='desktop_open_document')return window.__openDocument||null;
  if(command==='desktop_save_document'){
    if(window.__native.fail)throw new Error('Native disk denied');
    if(window.__native.cancel)return null;
    if(!args.saveAs&&args.token!==window.__native.token)throw new Error('Native file handle is stale');
    window.__native.saved=args.text;
    window.__native.token=`saved-${window.__nativeCalls.length}`;
    return {name:args.saveAs?args.name:window.__native.name,token:window.__native.token};
  }
  throw new Error('Unexpected command '+command);
}}};
"""


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = await browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        launch = {'name': 'Native.sov', 'text': json.dumps(DOCUMENT), 'token': 'launch-token'}
        await page.add_init_script('window.__launchDocument=' + json.dumps(launch) + ';' + MOCK)
        await page.goto((ROOT / 'index.html').as_uri(), wait_until='load')
        await page.evaluate('window.SovDesktopPersistenceReady')
        assert await page.evaluate('currentFileHandle.native&&currentFileHandle.token') == 'launch-token'
        assert await page.evaluate('SovSchematicAPI.file.info().name') == 'Native.sov'
        print('CASE PASS native-launch-handle')

        result = await page.evaluate('saveSchematicFile()')
        assert result['mode'] == 'native'
        saved = await page.evaluate('JSON.parse(window.__native.saved)')
        assert saved['id'] == DOCUMENT['id']
        command = await page.evaluate("window.__nativeCalls.filter(c=>c.command==='desktop_save_document').at(-1)")
        assert command['args']['token'] == 'launch-token' and command['args']['saveAs'] is False
        assert 'path' not in command['args'] and not await page.evaluate('isFileDirty()')
        print('CASE PASS native-save-current')

        await page.evaluate("SovSchematicAPI.create('component',{id:'native-qa-added',symbolId:'buffer',x:80,y:80})")
        assert await page.evaluate('isFileDirty()')
        await page.evaluate('window.__native.fail=true')
        failure = await page.evaluate("saveSchematicFile().then(()=>null,error=>String(error))")
        assert 'Native disk denied' in failure and await page.evaluate('isFileDirty()')
        print('CASE PASS native-save-failure-stays-dirty')

        await page.evaluate('window.__native.fail=false;window.__native.cancel=true')
        before = await page.evaluate('currentFileHandle.token')
        assert (await page.evaluate('saveSchematicFile({saveAs:true})'))['mode'] == 'cancelled'
        assert await page.evaluate('currentFileHandle.token') == before and await page.evaluate('isFileDirty()')
        print('CASE PASS native-save-cancel-stays-dirty')

        await page.evaluate('window.__native.cancel=false')
        result = await page.evaluate("saveSchematicFile({format:'package'})")
        command = await page.evaluate("window.__nativeCalls.filter(c=>c.command==='desktop_save_document').at(-1)")
        assert result['format'] == 'package' and command['args']['saveAs'] is True
        assert json.loads(command['args']['text'])['schema'].endswith('/package@0.1')
        print('CASE PASS native-format-change-save-as')

        await page.evaluate('window.confirm=()=>true;newSchematic()')
        await page.wait_for_function('window.__native.token===null')
        assert await page.evaluate('currentFileHandle===null')
        assert (await page.evaluate('saveSchematicFile()'))['mode'] == 'native'
        command = await page.evaluate("window.__nativeCalls.filter(c=>c.command==='desktop_save_document').at(-1)")
        assert command['args']['saveAs'] is True and command['args']['token'] is None
        print('CASE PASS native-new-clears-association')

        await page.evaluate('SovSchematicAPI.file.open(' + json.dumps(DOCUMENT) + ", 'API.sov')")
        await page.wait_for_function('window.__native.token===null')
        assert await page.evaluate('currentFileHandle===null')
        print('CASE PASS native-api-open-clears-association')

        await page.evaluate("window.__launchError='Could not read launch file';window.__nativeCalls=[]")
        await page.evaluate('openDesktopLaunchDocument()')
        report = await page.evaluate("window.__nativeCalls.find(c=>c.command==='report_loaded').args")
        assert report['ok'] is False and 'Could not read launch file' in report['error']
        assert await page.evaluate("statusEl.textContent.includes('Open failed')")
        print('CASE PASS native-unreadable-launch-reports-failure')

        assert not errors, errors
        counters=await page.evaluate('globalThis.__coverage__ || {}')
        (options.coverage_dir/f'native-persistence-{os.getpid()}.json').write_text(json.dumps(counters),encoding='utf-8')
        await browser.close()
    print('PASS native persistence page contract: 8 cases; native disk effects remain separate')


if __name__ == '__main__':
    asyncio.run(main())
