"""Watch mode: an edit to the source reaches the open editor by itself.

With `--watch`, a change to the authoring inputs rebuilds index.html and tells every
open editor over the event stream to reload. The drawing on the canvas is not the
server's document, so the editor stashes it first and picks it up again on load,
along with the selection and the camera. That stash is separate from
File > Restore Recovery, which stays a deliberate act by a person.
"""
import asyncio
import io
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from browser_runtime import chromium_launch_kwargs
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
WATCHED = ROOT / 'src' / '00-state.js'


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def wait_for(predicate, timeout_s=30, label='condition'):
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            last = predicate()
            if last:
                return last
        except Exception as error:
            last = error
        time.sleep(0.2)
    raise AssertionError(f'timed out waiting for {label}: {last!r}')


def get(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read())


async def main():
    port = free_port()
    base = f'http://127.0.0.1:{port}'
    workdir = tempfile.mkdtemp(prefix='sov-reload-')
    original = io.open(WATCHED, encoding='utf-8', newline='').read()
    newline = '\r\n' if '\r\n' in original else '\n'
    server = subprocess.Popen(
        ['node', str(ROOT / 'mcp' / 'server.mjs'), '--port', str(port), '--watch',
         '--file', str(Path(workdir) / 'schematic.sov')],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        wait_for(lambda: get(f'{base}/')['editor'] == '/editor', label='server start')

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
            page = await browser.new_page(viewport={'width': 1400, 'height': 900})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))

            # Served from the server, ?live=1 needs no port named: it is same-origin.
            await page.goto(f'{base}/editor?live=1', wait_until='load')
            await page.wait_for_timeout(500)
            status = await page.evaluate('window.SovSchematicLive.status()')
            assert status['enabled'] is True and status['endpoint'] == base, status

            await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:400,y:300})")
            path = await page.evaluate(
                "window.SovSchematicAPI.create('component',{symbolId:'path',x:820,y:420}).result")
            await page.evaluate('(id)=>selectNode(id)', path['id'])
            await page.wait_for_timeout(400)
            before = await page.evaluate('({count:nodes.length,selected,revision:diagram.revision})')
            assert before['count'] == 2, before

            # The link is carrying that selection before anything reloads.
            live = wait_for(lambda: (lambda s: s if s['connected'] and
                                     s['snapshot']['selection']['ids'] == [path['id']] else None)(
                get(f'{base}/api/v1/live?selection=1')), label='selection on the link')
            assert live['snapshot']['selection']['kind'] == 'component', live

            # An edit to a watched file is all it takes.
            io.open(WATCHED, 'w', encoding='utf-8', newline='').write(
                original + newline + '// live_reload_qa marker' + newline)
            await page.wait_for_event('load', timeout=40000)
            await page.wait_for_timeout(1200)

            after = await page.evaluate(
                '({count:nodes.length,selected,revision:diagram.revision,status:statusEl.textContent})')
            assert after['count'] == before['count'], f'the drawing was lost: {before} -> {after}'
            assert after['selected'] == before['selected'], f'the selection was lost: {before} -> {after}'
            assert after['status'] == 'Reloaded on rebuild', after

            # The carry is consumed, not left lying about for the next load to pick up.
            assert await page.evaluate(
                "()=>{try{return localStorage.getItem('sov.live.carry')===null}catch(_){return true}}")

            # The editor is pushing again after the reload, under a new session id.
            wait_for(lambda: get(f'{base}/api/v1/live')['connected'], label='link back up')
            assert (await page.evaluate('window.SovSchematicLive.status()'))['enabled'] is True

            assert not errors, errors
            await browser.close()
    finally:
        io.open(WATCHED, 'w', encoding='utf-8', newline='').write(original)
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        # Leave the build matching the restored source.
        subprocess.run([sys.executable, str(ROOT / 'build.py')], cwd=ROOT,
                       stdout=subprocess.DEVNULL, check=False)

    print('live_reload_qa ok')


if __name__ == '__main__':
    sys.exit(asyncio.run(main()) or 0)
