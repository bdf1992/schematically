"""Address open: a link with open=<relative path> loads that same-origin document.

The editor reads the open parameter at start and hands the fetched text to the same
parseFilePayload / applyOpenedPayload seam file Open uses. A target with a scheme, a host,
a leading slash, a backslash or a parent segment is refused in the status line and no
request is made for it.
"""
import asyncio
import http.server
import json
import os
import socket
import sys
import threading
import urllib.parse
from pathlib import Path

from browser_runtime import chromium_launch_kwargs
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = 'examples/13-half-adder.sov'

COUNTS = 'JSON.stringify([snapshotDocument().components.length, snapshotDocument().wires.length])'


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *args):
        pass


async def run_case(browser, base, query, ready):
    """Open a fresh context at the query, wait on the status text, return (status, counts, urls)."""
    context = await browser.new_context(viewport={'width': 1400, 'height': 900})
    try:
        page = await context.new_page()
        errors = []
        urls = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda r: urls.append(r.url))
        suffix = '?' + urllib.parse.urlencode(query) if query else ''
        await page.goto(f'{base}/index.html{suffix}', wait_until='load')
        await page.wait_for_function(
            '(want)=>{const t=document.getElementById("status")?.textContent||"";return want===""?t!=="" : t.startsWith(want)}',
            arg=ready, timeout=15000)
        status = await page.evaluate('document.getElementById("status").textContent')
        counts = json.loads(await page.evaluate(COUNTS))
        assert not errors, errors
        return status, counts, urls
    finally:
        await context.close()


async def main():
    port = free_port()
    base = f'http://127.0.0.1:{port}'
    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))

            # Case one: no query. The blank baseline. The page writes some status at start.
            context = await browser.new_context(viewport={'width': 1400, 'height': 900})
            page = await context.new_page()
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            await page.goto(f'{base}/index.html', wait_until='load')
            await page.wait_for_function('()=>typeof snapshotDocument==="function"&&document.getElementById("status")!==null')
            baseline = json.loads(await page.evaluate(COUNTS))
            assert not errors, errors
            await context.close()

            # Case two: a same-origin example opens.
            status, counts, _ = await run_case(browser, base, {'open': EXAMPLE}, 'Opened')
            doc = json.loads((ROOT / EXAMPLE).read_text(encoding='utf-8'))
            want = [len(doc['components']), len(doc['wires'])]
            assert status.startswith('Opened') and status.endswith('13-half-adder.sov'), status
            assert counts == want and min(want) > 0, (counts, want)
            assert counts != baseline, (counts, baseline)

            # Case three: a missing file fails by status, document untouched.
            status, counts, _ = await run_case(browser, base, {'open': 'examples/does-not-exist.sov'}, 'Open failed')
            assert status.startswith('Open failed') and 'HTTP 404' in status, status
            assert counts == baseline, (counts, baseline)

            # Case four: refused targets, no request for them.
            refused = [
                'http://127.0.0.1:1/x.sov',
                '//127.0.0.1:1/x.sov',
                '/examples/13-half-adder.sov',
                '../examples/13-half-adder.sov',
                'examples\\13-half-adder.sov',
                'javascript:alert',
            ]
            for target in refused:
                status, counts, urls = await run_case(browser, base, {'open': target}, 'Open refused')
                assert status.startswith('Open refused'), (target, status)
                assert counts == baseline, (target, counts, baseline)
                assert all(u.startswith(base) for u in urls), (target, urls)
                assert not any(urllib.parse.urlsplit(u).path.endswith('.sov') for u in urls), (target, urls)

            await browser.close()
    finally:
        server.shutdown()
        server.server_close()

    print('address_open_qa ok')


if __name__ == '__main__':
    os.chdir(Path(__file__).resolve().parent)
    sys.exit(asyncio.run(main()) or 0)
