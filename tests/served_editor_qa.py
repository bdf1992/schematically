"""Served editor: GET /editor on a document server shows that server's document.

The server puts its document in the page as an inert JSON script element (sov-served-document),
the editor reads it at start through the same parseFilePayload / applyOpenedPayload seam File Open
uses, and makes no request for it. /index.html stays the blank build. An open parameter in the
address wins over the served document. A document whose text holds a closing script tag cannot
end the element.
"""
import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from browser_runtime import chromium_launch_kwargs
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples' / '13-half-adder.sov'
TAG = 'sov-served-document'

COUNTS = 'JSON.stringify([snapshotDocument().components.length, snapshotDocument().wires.length])'


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def get(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read().decode('utf-8')


def wait_for(predicate, timeout_s=15, label='condition'):
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            last = predicate()
            if last:
                return last
        except Exception as error:  # server not up yet
            last = error
        time.sleep(0.15)
    raise AssertionError(f'timed out waiting for {label}: {last!r}')


class Server:
    def __init__(self, document_file):
        self.port = free_port()
        self.base = f'http://127.0.0.1:{self.port}'
        self.process = subprocess.Popen(
            ['node', str(ROOT / 'mcp' / 'server.mjs'), '--port', str(self.port), '--file', str(document_file)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        wait_for(lambda: get(f'{self.base}/'), label='server start')

    def stop(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()


async def open_page(browser, url):
    context = await browser.new_context(viewport={'width': 1400, 'height': 900})
    page = await context.new_page()
    record = {'errors': [], 'logs': [], 'urls': []}
    page.on('pageerror', lambda e: record['errors'].append(str(e)))
    page.on('console', lambda m: record['logs'].append((m.type, m.text)))
    page.on('request', lambda r: record['urls'].append(r.url))
    await page.goto(url, wait_until='load')
    await page.wait_for_function('()=>typeof snapshotDocument==="function"&&document.getElementById("status")!==null')
    return context, page, record


async def status_and_counts(page):
    status = await page.evaluate('document.getElementById("status").textContent')
    return status, json.loads(await page.evaluate(COUNTS))


async def main():
    workdir = Path(tempfile.mkdtemp(prefix='sov-served-'))
    servers = []
    try:
        # (a) and (b): the half adder served from a copy named half-adder-copy.sov.
        half_dir = workdir / 'half'
        half_dir.mkdir()
        copy = half_dir / 'half-adder-copy.sov'
        shutil.copyfile(EXAMPLE, copy)
        doc = json.loads(EXAMPLE.read_text(encoding='utf-8'))
        want = [len(doc['components']), len(doc['wires'])]
        assert min(want) > 0, want
        half = Server(copy)
        servers.append(half)

        editor_body = get(f'{half.base}/editor')
        index_body = get(f'{half.base}/index.html')
        # (b)
        assert editor_body.count(TAG) == 1, editor_body.count(TAG)
        assert TAG not in index_body
        print('(b) /editor tags:', editor_body.count(TAG), '/index.html tags:', index_body.count(TAG))

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))

            context, page, record = await open_page(browser, f'{half.base}/editor')
            status, counts = await status_and_counts(page)
            assert status.startswith('Opened') and status.endswith('half-adder-copy.sov'), status
            assert counts == want, (counts, want)
            assert not any(u.split('?')[0].endswith('/api/v1/document') for u in record['urls']), record['urls']
            # (e)
            assert not record['errors'], record['errors']
            print('(a) status:', status, 'counts:', counts, 'want:', want, 'requests:', len(record['urls']))
            await context.close()

            # Blank build stays reachable through /index.html.
            context, page, record = await open_page(browser, f'{half.base}/index.html')
            _, blank = await status_and_counts(page)
            assert blank != want, (blank, want)
            assert not record['errors'], record['errors']
            print('(b) /index.html counts:', blank)
            await context.close()

            # (d) an explicit open parameter wins over the served document.
            context, page, record = await open_page(browser, f'{half.base}/editor?open=no-such-file.sov')
            await page.wait_for_function('()=>document.getElementById("status").textContent.startsWith("Open failed")', timeout=15000)
            status, counts = await status_and_counts(page)
            assert counts != want, (counts, want)
            print('(d) status:', status, 'counts:', counts)
            await context.close()

            # (c) a label that closes a script tag and opens another cannot end the element.
            label = '</script><script>window.__served_x=1</script>'
            hostile = {
                'schema': doc['schema'], 'id': 'hostile', 'revision': 0, 'notation': doc.get('notation', 'logic'),
                'meta': {}, 'components': [
                    {'id': 'act-1', 'symbolId': 'act', 'x': 200, 'y': 200, 'config': {'label': label}},
                ], 'wires': [],
            }
            hostile_dir = workdir / 'hostile'
            hostile_dir.mkdir()
            hostile_file = hostile_dir / 'hostile.sov'
            hostile_file.write_text(json.dumps(hostile), encoding='utf-8')
            second = Server(hostile_file)
            servers.append(second)
            body = get(f'{second.base}/editor')
            assert body.count(TAG) == 1, body.count(TAG)
            context, page, record = await open_page(browser, f'{second.base}/editor')
            injected = await page.evaluate('typeof window.__served_x')
            assert injected == 'undefined', injected
            labels = await page.evaluate('snapshotDocument().components.map(c=>c.config&&c.config.label)')
            assert label in labels, labels
            assert not record['errors'], record['errors']
            assert not [m for m in record['logs'] if m[0] == 'error'], record['logs']
            print('(c) injected:', injected, 'labels:', labels)
            await context.close()

            await browser.close()
    finally:
        for server in servers:
            server.stop()
        shutil.rmtree(workdir, ignore_errors=True)

    print('served_editor_qa ok')


if __name__ == '__main__':
    os.chdir(Path(__file__).resolve().parent)
    sys.exit(asyncio.run(main()) or 0)
