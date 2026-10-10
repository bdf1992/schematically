"""MCP surface QA: one request-handling core behind two transports.

tests/mcp_surface_check.mjs drives mcp/surface.mjs directly, over a memory store seeded with
examples/01-source-hold.sov. This test sends the identical sequence over HTTP to mcp/server.mjs,
started with --file pointed at a temporary copy of the same example, and asserts the two bodies
agree once their volatile fields (timestamps and the ids derived from them) are removed. It also
asserts the memory store's writes counter, and that mcp/surface.mjs and mcp/store-memory.mjs
import no node: module.
"""
from __future__ import annotations
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]

# --- the import-free boundary: surface.mjs and store-memory.mjs read no node: module.
IMPORT_LINE = re.compile(r'^\s*(?:import\b.*?[\'"]node:[^\'"]+[\'"]|.*require\([\'"]node:[^\'"]+[\'"]\))', re.MULTILINE)
for name in ('mcp/surface.mjs', 'mcp/store-memory.mjs'):
    text = (ROOT / name).read_text(encoding='utf-8')
    hit = IMPORT_LINE.search(text)
    assert not hit, f'{name} imports a node: module: {hit.group(0)!r}'
print('PASS mcp surface + store-memory import no node: module')

# --- the surface-side sequence, run through mcp_surface_check.mjs over a memory store.
proc = subprocess.run(['node', str(ROOT / 'tests/mcp_surface_check.mjs')], cwd=ROOT, capture_output=True, text=True)
assert proc.returncode == 0, proc.stdout + proc.stderr
surface_side = json.loads(proc.stdout.strip().splitlines()[-1])


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def http_json(url, method='GET', payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = request.Request(url, data=body, method=method, headers={'content-type': 'application/json'})
    try:
        with request.urlopen(req, timeout=10) as res:
            return res.status, json.loads(res.read())
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def rpc(base, method, params, call_id):
    status, data = http_json(base + '/mcp', 'POST', {'jsonrpc': '2.0', 'id': call_id, 'method': method, 'params': params})
    assert status == 200, (status, data)
    return data


AREA = {'x': -1000000, 'y': -1000000, 'width': 2000000, 'height': 2000000}
APPLY_OPS = [{'op': 'create', 'resource': 'component', 'value': {'symbolId': 'act', 'x': 900, 'y': 200, 'config': {'label': 'mcp-surface-check'}}}]

with tempfile.TemporaryDirectory() as td:
    doc_file = Path(td) / 'mcp-surface-check.sov'
    shutil.copy(ROOT / 'examples/01-source-hold.sov', doc_file)
    port = free_port()
    base = f'http://127.0.0.1:{port}'
    server = subprocess.Popen(['node', str(ROOT / 'mcp/server.mjs'), '--port', str(port), '--file', str(doc_file)], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(80):
            try:
                status, _ = http_json(base + '/api/v1/formats')
                if status == 200:
                    break
            except Exception:
                time.sleep(.05)
        else:
            raise AssertionError('server did not start: ' + (server.stdout.read() if server.stdout else ''))

        initialize = rpc(base, 'initialize', {'protocolVersion': '2026-07-28'}, 1)
        tools_list = rpc(base, 'tools/list', {}, 2)
        tool_names = sorted(t['name'] for t in tools_list['result']['tools'])
        guide_index = rpc(base, 'tools/call', {'name': 'schematic.guide', 'arguments': {}}, 3)
        read_whole = rpc(base, 'tools/call', {'name': 'schematic.read', 'arguments': {'area': AREA}}, 4)
        apply = rpc(base, 'tools/call', {'name': 'schematic.apply', 'arguments': {'operations': APPLY_OPS}}, 5)
        doc_status, document_body = http_json(base + '/api/v1/document')
        assert doc_status == 200
        run_status, run_start_body = http_json(base + '/api/v1/runs', 'POST', {})
        assert run_status == 201, run_start_body
        handle = run_start_body['handle']
        step_status, run_step_body = http_json(base + f'/api/v1/runs/{handle}/step', 'POST')
        assert step_status == 200, run_step_body
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()

http_side = {
    'initialize': initialize,
    'toolNames': tool_names,
    'guideIndex': guide_index,
    'readWhole': read_whole,
    'apply': apply,
    'document': document_body,
    'runStart': run_start_body,
    'runStep': run_step_body,
}


def strip_run_receipt(body):
    # runId/handle: content-derived from the document, which carries meta.updatedAt, so a run
    # started against the same document at two different real times still gets two different ids.
    body.pop('runId', None)
    body.pop('handle', None)
    return body


# meta.updatedAt: Data.touch() stamps the real clock on every mutation. The surface side's
# httpCall wraps {status, body}; the HTTP side is the raw decoded body.
surface_side['document']['body'].get('meta', {}).pop('updatedAt', None)
http_side['document'].get('meta', {}).pop('updatedAt', None)
# the apply receipt's own batch id, mcp-<Date.now()> (surface.mjs executeAuthorTool); 'content'
# duplicates structuredContent as formatted text, operationId and all, so it carries the same
# volatile id and is dropped rather than re-stripped inside its own JSON string.
surface_side['apply']['result']['structuredContent'].pop('operationId', None)
http_side['apply']['result']['structuredContent'].pop('operationId', None)
surface_side['apply']['result'].pop('content', None)
http_side['apply']['result'].pop('content', None)
# runStart/runStep carry their own body shape: the surface side's httpCall wraps {status, body},
# the HTTP side is the raw decoded JSON body — flatten both to the same shape before comparing.
surface_run_start = strip_run_receipt(dict(surface_side['runStart']['body']))
surface_run_step = strip_run_receipt(dict(surface_side['runStep']['body']))
http_run_start = strip_run_receipt(dict(run_start_body))
http_run_step = strip_run_receipt(dict(run_step_body))

assert surface_side['initialize']['result']['protocolVersion'] == http_side['initialize']['result']['protocolVersion']
assert surface_side['toolNames'] == http_side['toolNames'], (surface_side['toolNames'], http_side['toolNames'])
assert surface_side['guideIndex'] == http_side['guideIndex'], (surface_side['guideIndex'], http_side['guideIndex'])
assert surface_side['readWhole'] == http_side['readWhole'], (surface_side['readWhole'], http_side['readWhole'])
assert surface_side['apply'] == http_side['apply'], (surface_side['apply'], http_side['apply'])
assert surface_side['document']['status'] == 200
assert surface_side['document']['body'] == http_side['document'], (surface_side['document']['body'], http_side['document'])
assert surface_run_start == http_run_start, (surface_run_start, http_run_start)
assert surface_run_step == http_run_step, (surface_run_step, http_run_step)
assert surface_side['writes'] == 1, surface_side['writes']
print('PASS mcp surface parity: memory-store surface.mjs agrees with the HTTP entrypoint')
