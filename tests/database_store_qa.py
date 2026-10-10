"""Database store QA: mcp/server.mjs --db keeps documents, revisions and profiles in a node:sqlite file.

Starts a server with --root and --db, registers, writes, imports and exports documents, restarts it
under another profile and asserts that nothing registered is lost, that every document is owned by the
profile that created it, and that the revisions table holds each text in order with its origin. Last,
a server without --db answers as it did before.
"""
from __future__ import annotations
import json
import shutil
import socket
import sqlite3
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


def rows(listing):
    return {x['id']: x for x in listing['documents']}


probe = subprocess.run(['node', '-e', "require('node:sqlite')"], capture_output=True, text=True)
assert probe.returncode == 0, ('node does not load node:sqlite without a flag', probe.stderr.strip()[-300:])
print('PASS node loads node:sqlite with no flag')

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    (td / 'src').mkdir()
    (td / 'root').mkdir()
    for f in (td / 'src/one.sov', td / 'src/two.sov', td / 'src/three.sov', td / 'root/r.sov'):
        shutil.copy(EXAMPLE, f)
    example_bytes = EXAMPLE.read_bytes()
    db_file = td / 'data/docs.db'
    assert not db_file.parent.exists()

    server, base = start(['--root', str(td / 'root'), '--db', str(db_file)])
    try:
        # --- register
        s, body = http_json(base + '/documents', 'POST', {'id': 'one', 'file': str(td / 'src/one.sov')})
        assert s == 201 and body['ok'] and body['profile'] == 'bdo' and body['revision'] == 1, (s, body)
        s, body = http_json(base + '/documents', 'POST', {'id': 'one', 'file': str(td / 'src/one.sov')})
        assert s == 200 and body['ok'] and body['revision'] == 1, (s, body)
        s, body = http_json(base + '/documents', 'POST', {'id': 'one', 'file': str(td / 'src/two.sov')})
        assert s == 409 and body['code'] == 'DOCUMENT_ID_TAKEN', (s, body)
        s, body = http_json(base + '/documents', 'POST', {'id': 'blank'})
        assert s == 201 and body['file'] is None and body['revision'] == 0, (s, body)
        s, body = http_json(base + '/documents', 'POST', {'id': 'rel', 'file': 'relative/x.sov'})
        assert s == 400 and body['code'] == 'DOCUMENT_FILE_INVALID', (s, body)
        for ident in ('two', 'three'):
            s, body = http_json(base + '/documents', 'POST', {'id': ident, 'file': str(td / f'src/{ident}.sov')})
            assert s == 201 and body['revision'] == 1, (ident, s, body)
        print('PASS documents registered, repeated, refused')

        # --- write by id
        r = rpc(base, '/d/one', 'tools/call', {'name': 'schematic.apply', 'arguments': {'operations': [apply_op('doc-one', 900)]}})
        assert not r['result']['isError'], r
        s, body = http_json(base + '/d/two/api/v1/apply', 'POST', {'operations': [apply_op('doc-two', 900)]})
        assert s == 200, (s, body)
        s, body = http_json(base + '/d/two/api/v1/apply', 'POST', {'operations': [apply_op('doc-two-b', 1000)]})
        assert s == 200, (s, body)
        s, listing = http_json(base + '/documents')
        assert s == 200 and listing['database'] and Path(listing['database']).resolve() == db_file.resolve(), listing
        assert listing['profile'] == 'bdo', listing
        got = rows(listing)
        assert [x['id'] for x in listing['documents']] == sorted(got), listing
        assert got['one']['revision'] == 2 and got['one']['profile'] == 'bdo' and got['one']['open'] is True, got['one']
        assert got['two']['revision'] == 3 and got['two']['profile'] == 'bdo' and got['two']['open'] is True, got['two']
        assert got['r']['profile'] is None and got['r']['revision'] is None and got['r']['open'] is False, got['r']
        assert (td / 'src/one.sov').read_bytes() == example_bytes and (td / 'src/two.sov').read_bytes() == example_bytes, 'a mutation wrote the source file'
        print('PASS writes land in the database and not in the source files')

        # --- import on first use
        s, doc = http_json(base + '/d/r/api/v1/document')
        assert s == 200, (s, doc)
        s, listing = http_json(base + '/documents')
        got = rows(listing)
        assert got['r']['profile'] == 'bdo' and got['r']['revision'] == 1, got['r']
        print('PASS a file under --root is imported on first use')

        # --- export
        s, body = http_json(base + '/documents/three/export', 'POST', {'file': str(td / 'out/three.sov')})
        assert s == 200 and body['ok'], (s, body)
        out3 = (td / 'out/three.sov').read_bytes()
        assert out3 == example_bytes and json.loads(out3) == json.loads(example_bytes), 'export is not equal to the import'
        s, body = http_json(base + '/documents/one/export', 'POST', {'file': str(td / 'out/one.sov')})
        assert s == 200 and body['ok'], (s, body)
        assert has_label(json.loads((td / 'out/one.sov').read_text(encoding='utf-8')), 'doc-one')
        s, body = http_json(base + '/documents/blank/export', 'POST', {'file': str(td / 'out/blank.sov')})
        assert s == 409 and body['code'] == 'DOCUMENT_EMPTY', (s, body)
        assert not (td / 'out/blank.sov').exists()
        print('PASS export writes the last revision and refuses an empty document')

        # --- import again
        s, body = http_json(base + '/documents', 'POST', {'id': 'two', 'file': str(td / 'src/two.sov')})
        assert s == 200, (s, body)
        s, doc = http_json(base + '/d/two/api/v1/document')
        assert has_label(doc, 'doc-two'), 'registering again changed the document'
        s, body = http_json(base + '/documents/two/import', 'POST', {})
        assert s == 200 and body['revision'] == 4, (s, body)
        s, doc = http_json(base + '/d/two/api/v1/document')
        assert s == 200 and not has_label(doc, 'doc-two') and not has_label(doc, 'doc-two-b'), 'import did not replace the document'
        s, body = http_json(base + '/documents/nope/import', 'POST', {})
        assert s == 404 and body['code'] == 'DOCUMENT_NOT_FOUND', (s, body)
        s, body = http_json(base + '/documents/one/import', 'POST', {'file': str(td / 'src/missing.sov')})
        assert s == 404 and body['code'] == 'DOCUMENT_FILE_MISSING', (s, body)
        print('PASS import replaces the working copy; unknown id and missing file refused')
    finally:
        stop(server)

    # --- restart under another profile, no --root
    server, base = start(['--db', str(db_file), '--profile', 'ada'])
    try:
        s, doc = http_json(base + '/d/one/api/v1/document')
        assert s == 200 and has_label(doc, 'doc-one'), (s,)
        s, listing = http_json(base + '/documents')
        got = rows(listing)
        assert listing['profile'] == 'ada', listing
        assert got['one']['revision'] == 2 and got['one']['profile'] == 'bdo', got['one']
        assert got['two']['revision'] == 4 and got['two']['profile'] == 'bdo', got['two']
        s, body = http_json(base + '/documents', 'POST', {'id': 'ada-doc'})
        assert s == 201 and body['profile'] == 'ada' and body['revision'] == 0, (s, body)
        s, body = http_json(base + '/profiles/bdo/documents')
        names = {x['id'] for x in body['documents']}
        assert s == 200 and {'one', 'two', 'three', 'blank', 'r'} <= names and 'ada-doc' not in names, (s, body)
        s, body = http_json(base + '/profiles/ada/documents')
        assert s == 200 and [x['id'] for x in body['documents']] == ['ada-doc'], (s, body)
        s, body = http_json(base + '/profiles/zed/documents')
        assert s == 404 and body['code'] == 'PROFILE_NOT_FOUND', (s, body)
        s, body = http_json(base + '/profiles')
        assert s == 200 and {'ada', 'bdo'} <= {p['id'] for p in body['profiles']}, (s, body)
        print('PASS restart keeps every document, each under its own profile')
    finally:
        stop(server)

    con = sqlite3.connect(str(db_file))
    try:
        assert con.execute('PRAGMA user_version').fetchone()[0] == 1
        origins = [r[0] for r in con.execute("SELECT origin FROM revisions WHERE document='two' ORDER BY revision")]
        assert origins == ['import', 'write', 'write', 'import'], origins
    finally:
        con.close()
    print('PASS schema version 1; revisions keep their origins in order')

    # --- without --db nothing changes
    server, base = start(['--root', str(td / 'root')])
    try:
        s, listing = http_json(base + '/documents')
        assert s == 200 and 'database' not in listing, listing
        s, body = http_json(base + '/profiles')
        assert s != 200, (s, body)
        print('PASS a server without --db has no database and no profiles')
    finally:
        stop(server)
print('PASS database store QA')
