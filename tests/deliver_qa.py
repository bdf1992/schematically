"""Check-and-deliver QA (scripts/validate_sov.mjs --json, scripts/deliver_sov.py, schematic.deliver).

(a) the rule table: codes are unique SOVnnn, every pattern compiles, and docs/RULE-CODES.md lists
    exactly the table's codes;
(b) validate --json: every example passes with no findings; each broken variant of one example
    reports the code its breakage belongs to, names the element, and carries a filled repair; no
    variant falls through to SOV999;
(c) deliver: a good document is delivered; a failing candidate (refused at validate, and refused
    at render with the renderer made to fail) leaves the previous good viewer byte for byte and
    with its modification time; a good document then replaces it;
(d) schematic.deliver over MCP: listed in tools/list with an input schema; one example round-trips
    to <name>.html beside its file; out outside the folder is refused; a server holding an invalid
    file refuses and keeps the viewer already there.
"""
from __future__ import annotations
import copy
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib import request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
import deliver_sov  # noqa: E402
import export_html  # noqa: E402

os.environ.setdefault('SOV_RENDER_PYTHON', sys.executable)
EXAMPLE = ROOT / 'examples' / '04-boundary-port.sov'
RULES = json.loads((ROOT / 'scripts' / 'sov_rules.json').read_text(encoding='utf-8'))['rules']


def validate(*paths: Path) -> tuple[int, dict]:
    proc = subprocess.run(['node', str(ROOT / 'scripts' / 'validate_sov.mjs'), '--json', *map(str, paths)],
                          capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
    return proc.returncode, json.loads(proc.stdout)


def stamp(path: Path) -> tuple[bytes, int]:
    return path.read_bytes(), path.stat().st_mtime_ns


# (a) the rule table and its document
codes = [r['code'] for r in RULES]
assert len(codes) == len(set(codes)), 'duplicate rule code'
assert all(re.fullmatch(r'SOV\d{3}', c) for c in codes), codes
for r in RULES:
    if r['match']:
        re.compile(r['match'])
    assert r['severity'] in ('error', 'warning') and r['repair'] and r['title'], r['code']
documented = set(re.findall(r'\bSOV\d{3}\b', (ROOT / 'docs' / 'RULE-CODES.md').read_text(encoding='utf-8')))
assert documented == set(codes), ('docs/RULE-CODES.md differs from scripts/sov_rules.json', sorted(documented ^ set(codes)))
print(f'(a) {len(codes)} rule codes, unique, all listed in docs/RULE-CODES.md')

# (b) validate --json
examples = sorted((ROOT / 'examples').glob('*.sov'))
rc, report = validate(*examples)
assert rc == 0 and report['ok'] and all(f['ok'] and not f['findings'] for f in report['files']), report
base = json.loads(EXAMPLE.read_text(encoding='utf-8'))


def variant(mutate):
    d = copy.deepcopy(base)
    mutate(d)
    return d


VARIANTS = {
    'SOV204': ('c1', variant(lambda d: d['components'].append(copy.deepcopy(d['components'][0])))),
    'SOV301': ('k1', variant(lambda d: d['wires'][0].update(a='no-such-card'))),
    'SOV205': (base['id'], variant(lambda d: d.update(narration=[{'at': 1}]))),
    'SOV206': (base['id'], variant(lambda d: d['meta'].update(timeScale=-1))),
    'SOV207': (base['id'], variant(lambda d: d['meta'].update(palette='neon'))),
    'SOV404': ('c1', variant(lambda d: d['components'][0].setdefault('config', {}).update(status='done'))),
    'SOV304': ('k1', variant(lambda d: d['wires'][0].update(canvasId='canvas:component:c2'))),
    'SOV104': (base['id'], variant(lambda d: d.update(schema='something/else@9'))),
}
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    paths = {}
    for code, (_, doc) in VARIANTS.items():
        paths[code] = td / f'{code}.sov'
        paths[code].write_text(json.dumps(doc), encoding='utf-8')
    (td / 'SOV102.sov').write_text('{"schema": ', encoding='utf-8')
    rc, report = validate(*paths.values(), td / 'SOV102.sov', td / 'SOV101.sov')
    assert rc == 1 and not report['ok']
    by_file = {Path(f['file']).stem: f for f in report['files']}
    for code in [*VARIANTS, 'SOV102', 'SOV101']:
        got = by_file[code]
        assert not got['ok'], code
        found = [f['code'] for f in got['findings']]
        assert code in found, (code, got['findings'])
        assert 'SOV999' not in found, (code, got['findings'])
        hit = next(f for f in got['findings'] if f['code'] == code)
        if code in VARIANTS:
            assert hit['id'] == VARIANTS[code][0], (code, hit)
        assert hit['repair'] and '{id}' not in hit['repair'] and '{detail}' not in hit['repair'], hit
print(f'(b) {len(examples)} examples pass with no findings; {len(VARIANTS) + 2} broken variants report their codes with an id and a repair')

# (c) deliver keeps the last good viewer
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    good, bad, target = td / 'good.sov', td / 'bad.sov', td / 'site' / 'viewer.html'
    shutil.copy(EXAMPLE, good)
    bad.write_text(json.dumps(VARIANTS['SOV301'][1]), encoding='utf-8')
    first = deliver_sov.deliver(good, target)
    assert first['delivered'] and first['previous'] == 'none' and first['stage'] == 'write', first
    assert base['id'] in target.read_text(encoding='utf-8')
    before = stamp(target)
    time.sleep(0.05)
    refused = deliver_sov.deliver(bad, target)
    assert not refused['delivered'] and refused['stage'] == 'validate' and refused['previous'] == 'kept', refused
    assert 'SOV301' in [f['code'] for f in refused['findings']]
    assert stamp(target) == before, 'a candidate refused at validate changed the last good viewer'
    # The renderer fails: refused at render, viewer untouched, no temporary file left behind.
    real = export_html.export_documents
    export_html.export_documents = lambda paths, out_dir=None, pad=48: (_ for _ in ()).throw(RuntimeError('Error: drawing failed'))
    try:
        refused = deliver_sov.deliver(good, target)
    finally:
        export_html.export_documents = real
    assert not refused['delivered'] and refused['stage'] == 'render' and refused['previous'] == 'kept', refused
    assert [f['code'] for f in refused['findings']] == ['SOV601'], refused['findings']
    assert stamp(target) == before, 'a candidate refused at render changed the last good viewer'
    # The viewer draws another document than the one checked: refused (SOV603) by the render checks.
    record = {'errors': [], 'svg_bytes': {'light': 9000, 'dark': 9000}, 'id': 'other', 'nodes': 1, 'blocked': []}
    assert [f['code'] for f in deliver_sov.render_checks(record, {'components': 3}, base['id'])] == ['SOV603']
    record.update(svg_bytes={'light': 0, 'dark': 9000}, id=base['id'], nodes=3)
    assert [f['code'] for f in deliver_sov.render_checks(record, {'components': 3}, base['id'])] == ['SOV602']
    assert sorted(p.name for p in target.parent.iterdir()) == ['viewer.html'], list(target.parent.iterdir())
    proc = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'deliver_sov.py'), str(bad), '--out', str(target), '--json'],
                          capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
    assert proc.returncode == 1 and json.loads(proc.stdout)['previous'] == 'kept' and stamp(target) == before, proc.stdout
    again = deliver_sov.deliver(good, target)
    assert again['delivered'] and again['previous'] == 'replaced', again
print('(c) a failing candidate (validate or render) leaves the last good viewer untouched; a good one replaces it')


# (d) schematic.deliver over MCP
def free_port() -> int:
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def start(file: Path):
    port = free_port()
    proc = subprocess.Popen(['node', str(ROOT / 'mcp' / 'server.mjs'), '--port', str(port), '--file', str(file)],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base_url = f'http://127.0.0.1:{port}'
    for _ in range(100):
        try:
            request.urlopen(base_url + '/api/v1/formats', timeout=1)
            return proc, base_url
        except Exception:  # noqa: BLE001
            time.sleep(0.05)
    proc.kill()
    raise AssertionError('server did not start')


def rpc(base_url: str, method: str, params: dict) -> dict:
    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode()
    req = request.Request(base_url + '/mcp', data=body, headers={'content-type': 'application/json'})
    return json.loads(request.urlopen(req, timeout=170).read())['result']


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    doc = td / 'boundary.sov'
    shutil.copy(EXAMPLE, doc)
    proc, url = start(doc)
    try:
        tools = {t['name']: t for t in rpc(url, 'tools/list', {})['tools']}
        assert 'schematic.deliver' in tools and tools['schematic.deliver']['inputSchema']['type'] == 'object'
        r = rpc(url, 'tools/call', {'name': 'schematic.deliver', 'arguments': {}})
        report = r['structuredContent']
        assert not r['isError'] and report['delivered'] and Path(report['target']) == td / 'boundary.html', report
        assert Path(report['source']) == doc, report
        assert base['id'] in (td / 'boundary.html').read_text(encoding='utf-8')
        r = rpc(url, 'tools/call', {'name': 'schematic.deliver', 'arguments': {'out': '../escape.html'}})
        assert r['isError'] and r['structuredContent']['code'] == 'DELIVER_TARGET_REFUSED', r
        assert not (td.parent / 'escape.html').exists()
    finally:
        proc.kill()
    before = stamp(td / 'boundary.html')
    doc.write_text(json.dumps(VARIANTS['SOV301'][1]), encoding='utf-8')
    proc, url = start(doc)
    try:
        r = rpc(url, 'tools/call', {'name': 'schematic.deliver', 'arguments': {}})
        report = r['structuredContent']
        assert r['isError'] and not report['delivered'] and report['previous'] == 'kept', report
        assert 'SOV301' in [f['code'] for f in report['findings']], report['findings']
        assert stamp(td / 'boundary.html') == before, 'MCP deliver of an invalid document changed the viewer'
    finally:
        proc.kill()
print('(d) schematic.deliver round-trips one example over MCP; an invalid document is refused and the viewer kept')
print('PASS deliver QA')
