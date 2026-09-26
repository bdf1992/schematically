"""Server render QA: an agent with only MCP or HTTP can see the diagram and measure it.

schematic.render returns the editor's own picture (svg as text, png as image content);
schematic.layout.metrics returns the audit; HTTP serves render.svg / render.png /
layout/metrics. Without a renderer the call is refused with RENDERER_UNAVAILABLE, typed.
"""
from __future__ import annotations
import base64, json, os, shutil, socket, subprocess, tempfile, time
from pathlib import Path
from urllib import request

ROOT = Path(__file__).resolve().parents[1]

def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close(); return port

def start(file, env):
    port = free_port()
    proc = subprocess.Popen(['node', str(ROOT / 'mcp/server.mjs'), '--port', str(port), '--file', file], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    base = f'http://127.0.0.1:{port}'
    for _ in range(80):
        try:
            request.urlopen(base + '/api/v1/formats', timeout=1); return proc, base
        except Exception:
            time.sleep(.05)
    proc.kill(); raise AssertionError('server did not start')

def rpc(base, name, args):
    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': args}}).encode()
    req = request.Request(base + '/mcp', data=body, headers={'content-type': 'application/json'})
    return json.loads(request.urlopen(req, timeout=120).read())['result']

with tempfile.TemporaryDirectory() as td:
    doc = Path(td) / 'doc.sov'; shutil.copy(ROOT / 'examples/09-print-ai-proof-run.sov', doc)
    proc, base = start(str(doc), dict(os.environ))
    try:
        r = rpc(base, 'schematic.render', {'format': 'png'})
        assert not r['isError'], r
        kinds = [c['type'] for c in r['content']]
        assert kinds == ['image', 'text'], kinds
        png = base64.b64decode(r['content'][0]['data'])
        assert png[:8] == b'\x89PNG\r\n\x1a\n' and len(png) > 20000, len(png)
        assert r['structuredContent']['score'] >= 9.5 and 'png' not in r['structuredContent']
        r = rpc(base, 'schematic.render', {'format': 'svg'})
        svg = r['structuredContent']['svg']
        assert svg.startswith('<svg') and 'Proof-resolution' in svg and 'simLayer' in svg and '<text' in svg
        # The legend rides below the picture when asked, and never otherwise.
        assert 'picture-legend' not in svg
        r = rpc(base, 'schematic.render', {'format': 'svg', 'legend': True})
        assert 'picture-legend' in r['structuredContent']['svg'], 'schematic.render legend: true'
        legend_http = request.urlopen(base + '/api/v1/render.svg?legend=true', timeout=120).read().decode('utf-8')
        assert 'picture-legend' in legend_http
        r = rpc(base, 'schematic.layout.metrics', {})
        assert not r['isError'] and r['structuredContent']['score'] >= 9.5 and 'rubric' in r['structuredContent'], r
        res = request.urlopen(base + '/api/v1/render.svg', timeout=120)
        assert res.headers['content-type'].startswith('image/svg+xml') and res.read().startswith(b'<svg')
        res = request.urlopen(base + '/api/v1/render.png?appearance=dark', timeout=120)
        assert res.headers['content-type'] == 'image/png' and res.read()[:4] == b'\x89PNG'
        metrics = json.loads(request.urlopen(base + '/api/v1/layout/metrics', timeout=120).read())
        assert metrics['ok'] and 'findings' in metrics
    finally:
        proc.kill()
    # No renderer: refused, typed, over MCP and HTTP alike.
    env = dict(os.environ); env['SOV_RENDER_PYTHON'] = str(Path(td) / 'no-such-python')
    proc, base = start(str(doc), env)
    try:
        r = rpc(base, 'schematic.render', {'format': 'png'})
        assert r['isError'] and r['structuredContent']['code'] == 'RENDERER_UNAVAILABLE', r
        try:
            request.urlopen(base + '/api/v1/render.svg', timeout=30); raise AssertionError('expected 503')
        except Exception as e:
            assert getattr(e, 'code', None) == 503, e
    finally:
        proc.kill()
print('PASS server render QA')
