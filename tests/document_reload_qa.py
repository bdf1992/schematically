"""Document reload QA: POST /documents/<id>/reload and /close on mcp/server.mjs.

A file rewritten outside the server is not seen by an open surface (it loads once and writes whole
state). reload re-reads the file at once; close drops the surface so the next call reads it again.
Without --db that is the whole story; with --db reload is refused (409) and close still answers 200.
"""
from __future__ import annotations
import json
import shutil
import socket
import subprocess
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


def options(url):
    req = request.Request(url, method='OPTIONS')
    with request.urlopen(req, timeout=15) as res:
        return res.status, {k.lower(): v for k, v in res.headers.items()}


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


def write_with_label(path, label):
    """A fresh copy of the example with its first component label changed to `label`."""
    doc = json.loads(EXAMPLE.read_text(encoding='utf-8'))
    count = 0

    def walk(node):
        nonlocal count
        if count:
            return
        if isinstance(node, dict):
            if node.get('label') == 'Source':
                node['label'] = label
                count += 1
                return
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc)
    assert count == 1, 'example has no Source label to change'
    path.write_text(json.dumps(doc, indent=2), encoding='utf-8')


def listing_row(base, ident):
    s, listing = http_json(base + '/documents')
    assert s == 200, (s, listing)
    return {x['id']: x for x in listing['documents']}.get(ident)


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    (td / 'root').mkdir()
    a, b = td / 'root/a.sov', td / 'root/b.sov'
    shutil.copy(EXAMPLE, a)
    shutil.copy(EXAMPLE, b)
    server, base = start(['--root', str(td / 'root')])
    try:
        # --- stale state: the open surface does not see a file rewritten outside
        r = rpc(base, '/d/a', 'tools/call', {'name': 'schematic.apply', 'arguments': {'operations': [apply_op('first-a', 900)]}})
        assert not r['result']['isError'], r
        b_before = b.read_bytes()
        write_with_label(a, 'disk-a')
        s, doc = http_json(base + '/d/a/api/v1/document')
        assert s == 200 and has_label(doc, 'first-a') and not has_label(doc, 'disk-a'), 'surface should still be stale'
        print('PASS an open surface does not see a file rewritten outside')

        # --- reload
        s, body = http_json(base + '/documents/a/reload', 'POST')
        assert s == 200 and body['ok'] is True and body['id'] == 'a' and body['open'] is True, (s, body)
        assert Path(body['file']).resolve() == a.resolve(), body
        s, doc = http_json(base + '/d/a/api/v1/document')
        assert s == 200 and has_label(doc, 'disk-a') and not has_label(doc, 'first-a'), 'reload did not show the disk content'
        assert 'disk-a' in a.read_text(encoding='utf-8') and 'first-a' not in a.read_text(encoding='utf-8')
        assert listing_row(base, 'a')['open'] is True
        print('PASS reload shows the file rewritten outside; the file keeps it')

        # --- close
        r = rpc(base, '/d/a', 'tools/call', {'name': 'schematic.apply', 'arguments': {'operations': [apply_op('second-a', 900)]}})
        assert not r['result']['isError'], r
        s, body = http_json(base + '/documents/a/close', 'POST')
        assert s == 200 and body == {'ok': True, 'id': 'a', 'open': False}, (s, body)
        assert listing_row(base, 'a')['open'] is False
        s, body = http_json(base + '/documents/a/close', 'POST')
        assert s == 200 and body['open'] is False, 'closing a closed document must answer the same 200'
        write_with_label(a, 'disk-2')
        s, doc = http_json(base + '/d/a/api/v1/document')
        assert s == 200 and has_label(doc, 'disk-2') and not has_label(doc, 'second-a'), 'next call must read the file'
        assert listing_row(base, 'a')['open'] is True
        print('PASS close drops the surface; the next call reads the file')

        # --- b untouched
        assert b.read_bytes() == b_before, 'b changed'
        s, doc = http_json(base + '/d/b/api/v1/document')
        assert s == 200 and not has_label(doc, 'disk-a') and not has_label(doc, 'disk-2')
        print('PASS document b untouched')

        # --- two ids, one file, one entry
        s, body = http_json(base + '/documents', 'POST', {'id': 'a2', 'file': str(a)})
        assert s == 201, (s, body)
        s, doc = http_json(base + '/d/a2/api/v1/document')
        assert s == 200 and has_label(doc, 'disk-2')
        s, body = http_json(base + '/documents/a2/close', 'POST')
        assert s == 200, (s, body)
        assert listing_row(base, 'a')['open'] is False and listing_row(base, 'a2')['open'] is False
        print('PASS two ids naming one file are closed together')

        # --- preflight
        for route in ('/documents/a/reload', '/documents/a/close'):
            s, h = options(base + route)
            assert s == 204 and h.get('access-control-allow-origin') == '*' and 'POST' in h.get('access-control-allow-methods', ''), (route, s, h)
            assert 'content-type' in h.get('access-control-allow-headers', ''), h
        print('PASS OPTIONS on both routes answers 204 with the CORS headers')

        # --- refusals
        b.unlink()
        s, body = http_json(base + '/documents/b/reload', 'POST')
        assert s == 404 and body['code'] == 'DOCUMENT_FILE_MISSING', (s, body)
        s, body = http_json(base + '/documents/nope/reload', 'POST')
        assert s == 404 and body['code'] == 'DOCUMENT_NOT_FOUND', (s, body)
        s, body = http_json(base + '/documents/nope/close', 'POST')
        assert s == 404 and body['code'] == 'DOCUMENT_NOT_FOUND', (s, body)
        s, body = http_json(base + '/documents/bad%20id/close', 'POST')
        assert s == 400 and body['code'] == 'DOCUMENT_ID_INVALID', (s, body)
        s, body = http_json(base + '/documents/bad%20id/reload', 'POST')
        assert s == 400 and body['code'] == 'DOCUMENT_ID_INVALID', (s, body)
        print('PASS missing file 404, unknown id 404, malformed id 400')
    finally:
        stop(server)

    # --- with --db
    shutil.copy(EXAMPLE, a)
    server, base = start(['--root', str(td / 'root'), '--db', str(td / 't.db')])
    try:
        s, body = http_json(base + '/documents/a/reload', 'POST')
        assert s == 409 and body['ok'] is False and body['code'] == 'DOCUMENT_DATABASE_BACKED', (s, body)
        assert '/documents/<id>/import' in body['message'] or '/import' in body['message'], body
        s, body = http_json(base + '/documents/a/close', 'POST')
        assert s == 200 and body['ok'] is True and body['open'] is False, (s, body)
        s, body = http_json(base + '/documents/nope/reload', 'POST')
        assert s == 404 and body['code'] == 'DOCUMENT_NOT_FOUND', (s, body)
        s, body = http_json(base + '/documents/bad%20id/reload', 'POST')
        assert s == 400 and body['code'] == 'DOCUMENT_ID_INVALID', (s, body)
        print('PASS with --db: reload 409, close 200')
    finally:
        stop(server)
print('PASS document reload QA')
