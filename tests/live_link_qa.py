"""Live link: the browser editor publishes what its operator is looking at.

An editor with the link started pushes a snapshot on every selection and revision
change. The server holds the latest one and serves it over HTTP and over the two
MCP tools, marking it stale once it stops arriving. The link is observation only:
pushing a snapshot never changes the server's document.
"""
import asyncio
import json
import os
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
HTML = ROOT / 'index.html'


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def http(method, url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data:
        request.add_header('content-type', 'application/json')
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read() or b'null')
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b'null')


def mcp(base, name, arguments=None):
    status, body = http('POST', f'{base}/mcp', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments or {}},
    })
    assert status == 200, (status, body)
    return body['result']['structuredContent']


def wait_for(predicate, timeout_s=10, label='condition'):
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


async def main():
    port = free_port()
    base = f'http://127.0.0.1:{port}'
    workdir = tempfile.mkdtemp(prefix='sov-live-')
    document_file = Path(workdir) / 'schematic.sov'
    server = subprocess.Popen(
        ['node', str(ROOT / 'mcp' / 'server.mjs'), '--port', str(port), '--file', str(document_file)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        wait_for(lambda: http('GET', f'{base}/')[0] == 200, label='server start')

        # With no editor pushing, the link reports itself absent rather than empty.
        status, idle = http('GET', f'{base}/api/v1/live')
        assert status == 200 and idle['connected'] is False and idle['snapshot'] is None, idle
        assert mcp(base, 'schematic.live.selection')['connected'] is False

        # A snapshot in the wrong schema is refused; the link is not a generic inbox.
        status, refused = http('POST', f'{base}/api/v1/live', {'schema': 'something/else@1'})
        assert status == 400 and refused['ok'] is False, refused

        names = [tool['name'] for tool in mcp_tools(base)]
        assert 'schematic.live.get' in names and 'schematic.live.selection' in names, names

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
            page = await browser.new_page(viewport={'width': 1400, 'height': 900})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            await page.set_content(HTML.read_text(encoding='utf-8'), wait_until='load')
            await page.wait_for_timeout(180)

            # The link is off until asked for, so an ordinary build makes no requests.
            assert (await page.evaluate('window.SovSchematicLive.status()'))['enabled'] is False
            started = await page.evaluate('(url)=>window.SovSchematicLive.start(url)', base)
            assert started['enabled'] is True and started['endpoint'] == base, started

            plane = await page.evaluate(
                "window.SovSchematicAPI.create('component',{symbolId:'plane',x:520,y:320}).result")
            await page.evaluate('(id)=>selectNode(id)', plane['id'])

            live = wait_for(
                lambda: (lambda s: s if s['connected'] and s['snapshot']['selection']['kind'] == 'component' else None)(
                    http('GET', f'{base}/api/v1/live')[1]),
                label='component selection')
            selection = live['snapshot']['selection']
            assert selection['ids'] == [plane['id']], selection
            assert selection['detail']['symbolId'] == 'plane', selection
            assert selection['detail']['dimension'] == 2, selection
            assert selection['detail']['record']['id'] == plane['id'], selection
            assert live['snapshot']['counts']['components'] >= 1, live['snapshot']['counts']
            assert live['snapshot']['file']['revision'] == await page.evaluate('diagram.revision')

            # The document body rides on the full snapshot only; the selection view drops it.
            assert live['snapshot']['document']['schema'].endswith('document@0.1'), live['snapshot']['document']
            assert 'document' not in mcp(base, 'schematic.live.selection')['snapshot']
            assert 'document' in mcp(base, 'schematic.live.get')['snapshot']

            # Selecting a Wire republishes with the endpoint topology of that Wire.
            a = await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:200,y:200}).result")
            b = await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:900,y:200}).result")
            wire = await page.evaluate(
                "([a,b])=>window.SovSchematicAPI.create('wire',{a,aSide:'out',b,bSide:'in'}).result",
                [a['id'], b['id']])
            await page.evaluate('(id)=>selectWire(wires.findIndex(w=>w.id===id))', wire['id'])
            wire_live = wait_for(
                lambda: (lambda s: s if s['snapshot'] and s['snapshot']['selection']['kind'] == 'wire' else None)(
                    mcp(base, 'schematic.live.selection')),
                label='wire selection')
            detail = wire_live['snapshot']['selection']['detail']
            assert detail['id'] == wire['id'], detail
            assert detail['a']['bound'] is True and detail['a']['componentId'] == a['id'], detail
            assert detail['b']['bound'] is True and detail['b']['componentId'] == b['id'], detail

            # Clearing the selection is itself a fact worth publishing.
            await page.evaluate('()=>selectNode(null)')
            cleared = wait_for(
                lambda: (lambda s: s if s['snapshot'] and s['snapshot']['selection']['kind'] == 'none' else None)(
                    mcp(base, 'schematic.live.selection')),
                label='cleared selection')
            assert cleared['snapshot']['selection']['detail'] is None, cleared

            # Observation only: the editor's pushes never entered the server's document.
            assert mcp(base, 'schematic.document.get')['components'] == [], 'live push mutated the server document'
            assert not document_file.exists(), 'live push wrote the server file'

            # Stopping the link leaves the last snapshot in place but ages it out.
            assert (await page.evaluate('window.SovSchematicLive.stop()'))['enabled'] is False
            assert not errors, errors
            await browser.close()

        assert http('GET', f'{base}/api/v1/live')[1]['snapshot'] is not None
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()

    print('live_link_qa ok')


def mcp_tools(base):
    status, body = http('POST', f'{base}/mcp', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
    assert status == 200, (status, body)
    return body['result']['tools']


if __name__ == '__main__':
    os.chdir(Path(__file__).resolve().parent)
    sys.exit(asyncio.run(main()) or 0)
