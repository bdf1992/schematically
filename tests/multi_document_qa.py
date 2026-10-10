"""Multi-document QA: one mcp/server.mjs process serves any number of documents by id.

Starts one server with --root <dir> --file <default>, registers and uses documents by id under
/d/<id>/..., and asserts each document's state, file and history stay its own. Then restarts the
server with --root only and asserts a restart loses nothing and that there is no default document.
"""
from __future__ import annotations
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/01-source-hold.sov'


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def http_json(url, method='GET', payload=None, raw=None):
    body = raw if raw is not None else (None if payload is None else json.dumps(payload).encode())
    req = request.Request(url, data=body, method=method, headers={'content-type': 'application/json'})
    try:
        with request.urlopen(req, timeout=15) as res:
            return res.status, json.loads(res.read() or b'null')
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b'null')


def rpc(base, prefix, method, params, call_id=1):
    status, data = http_json(base + prefix + '/mcp', 'POST', {'jsonrpc': '2.0', 'id': call_id, 'method': method, 'params': params})
    assert status == 200, (prefix, status, data)
    return data


def apply_op(label, x):
    return {'op': 'create', 'resource': 'component', 'value': {'symbolId': 'act', 'x': x, 'y': 200, 'config': {'label': label}}}


def start(args):
    port = free_port()
    base = f'http://127.0.0.1:{port}'
    server = subprocess.Popen(['node', str(ROOT / 'mcp/server.mjs'), '--port', str(port), *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for _ in range(200):
        try:
            status, _ = http_json(base + '/documents')
            if status == 200:
                return server, base
        except Exception:
            pass
        if server.poll() is not None:
            break
        time.sleep(.05)
    out = ''
    try:
        server.kill()
        out = server.stdout.read() if server.stdout else ''
    except Exception:
        pass
    raise AssertionError('server did not start: ' + out)


def stop(server):
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()


def has_label(doc, label):
    return label in json.dumps(doc)


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    (td / 'root').mkdir()
    (td / 'outside').mkdir()
    a, b = td / 'root/a.sov', td / 'root/b.sov'
    c, d = td / 'outside/c.sov', td / 'outside/d.sov'
    for f in (a, b, c, d):
        shutil.copy(EXAMPLE, f)
    example_bytes = EXAMPLE.read_bytes()
    server, base = start(['--root', str(td / 'root'), '--file', str(d)])
    try:
        # --- register ids
        s, body = http_json(base + '/documents', 'POST', {'id': 'gamma', 'file': str(c)})
        assert s == 201 and body['ok'] and body['id'] == 'gamma', (s, body)
        s, body = http_json(base + '/documents', 'POST', {'id': 'gamma', 'file': str(c)})
        assert s == 200 and body['ok'], (s, body)
        s, body = http_json(base + '/documents', 'POST', {'id': 'gamma', 'file': str(td / 'outside/other.sov')})
        assert s == 409 and body['code'] == 'DOCUMENT_ID_TAKEN', (s, body)
        s, body = http_json(base + '/documents', 'POST', {'id': 'rel', 'file': 'relative/x.sov'})
        assert s == 400 and body['code'] == 'DOCUMENT_FILE_INVALID', (s, body)
        s, body = http_json(base + '/documents', 'POST', {'id': 'bad id', 'file': str(c)})
        assert s == 400 and body['code'] == 'DOCUMENT_ID_INVALID', (s, body)
        s, body = http_json(base + '/documents', 'POST', raw=b'not json')
        assert s == 400 and body['code'] == 'DOCUMENT_FILE_INVALID', (s, body)
        print('PASS documents registered, repeated, refused')

        # --- write to three documents by id
        r = rpc(base, '/d/a', 'tools/call', {'name': 'schematic.apply', 'arguments': {'operations': [apply_op('doc-a', 900)]}})
        assert not r['result']['isError'], r
        s, body = http_json(base + '/d/b/api/v1/apply', 'POST', {'operations': [apply_op('doc-b', 900)]})
        assert s == 200, (s, body)
        r = rpc(base, '/d/gamma', 'tools/call', {'name': 'schematic.apply', 'arguments': {'operations': [apply_op('doc-gamma', 900)]}})
        assert not r['result']['isError'], r
        names = {'a': 'doc-a', 'b': 'doc-b', 'gamma': 'doc-gamma'}
        for ident, label in names.items():
            s, doc = http_json(base + f'/d/{ident}/api/v1/document')
            assert s == 200, (ident, s)
            assert has_label(doc, label), (ident, 'missing own label')
            for other in names.values():
                if other != label:
                    assert not has_label(doc, other), (ident, 'holds', other)
        s, doc = http_json(base + '/api/v1/document')
        assert s == 200 and not any(has_label(doc, l) for l in names.values()), 'default document holds an id\'s label'
        for f, label in ((a, 'doc-a'), (b, 'doc-b'), (c, 'doc-gamma')):
            text = f.read_text(encoding='utf-8')
            assert label in text, (f, label)
            assert not any(o in text for o in names.values() if o != label), (f, 'mixed')
        assert d.read_bytes() == example_bytes, 'default document changed'
        print('PASS three documents written by id and read back unmixed')

        # --- same tool surface, refusals
        base_tools = sorted(t['name'] for t in rpc(base, '', 'tools/list', {})['result']['tools'])
        a_tools = sorted(t['name'] for t in rpc(base, '/d/a', 'tools/list', {})['result']['tools'])
        assert base_tools == a_tools
        s, body = http_json(base + '/d/nope/api/v1/document')
        assert s == 404 and body['code'] == 'DOCUMENT_NOT_FOUND', (s, body)
        assert not (td / 'root/nope.sov').exists()
        s, body = http_json(base + '/d/bad%20id/mcp', 'POST', {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'})
        assert s == 400 and body['code'] == 'DOCUMENT_ID_INVALID', (s, body)
        print('PASS tool list equal, unknown id 404, invalid id 400')

        # --- listing and root description
        s, listing = http_json(base + '/documents')
        assert s == 200, (s, listing)
        got = {x['id']: x for x in listing['documents']}
        assert [x['id'] for x in listing['documents']] == sorted(got), listing
        for ident, f in (('a', a), ('b', b), ('gamma', c)):
            assert ident in got and got[ident]['open'] is True, (ident, listing)
            assert Path(got[ident]['file']).resolve() == f.resolve(), (ident, got[ident])
        assert listing['root'] and Path(listing['root']).resolve() == (td / 'root').resolve()
        assert listing['default'] and Path(listing['default']).resolve() == d.resolve()
        s, desc = http_json(base + '/d/a')
        assert s == 200 and desc['mcp'] == '/d/a/mcp' and desc['api'] == '/d/a/api/v1' and desc['editor'] == '/d/a/editor', (s, desc)
        print('PASS /documents listing and /d/<id> description')

        # --- history is per document
        r = rpc(base, '/d/a', 'tools/call', {'name': 'schematic.history.undo', 'arguments': {}})
        assert not r['result']['isError'], r
        s, doc_a = http_json(base + '/d/a/api/v1/document')
        s, doc_b = http_json(base + '/d/b/api/v1/document')
        assert not has_label(doc_a, 'doc-a') and has_label(doc_b, 'doc-b')
        assert 'doc-a' not in a.read_text(encoding='utf-8') and 'doc-b' in b.read_text(encoding='utf-8')
        print('PASS undo on a leaves b')
    finally:
        stop(server)

    # --- restart with --root only
    server, base = start(['--root', str(td / 'root')])
    try:
        s, doc = http_json(base + '/d/b/api/v1/document')
        assert s == 200 and has_label(doc, 'doc-b'), (s,)
        s, body = http_json(base + '/mcp', 'POST', {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'})
        assert s == 404 and body['code'] == 'DOCUMENT_NOT_NAMED', (s, body)
        s, listing = http_json(base + '/documents')
        s2, rootdesc = http_json(base + '/')
        assert s2 == 200 and rootdesc['documents'] == '/documents' and rootdesc['document'] is None, rootdesc
        assert listing['default'] is None, listing
        print('PASS restart loses nothing; no default document without --file')
    finally:
        stop(server)
print('PASS multi-document QA')
