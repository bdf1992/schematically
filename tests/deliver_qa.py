"""Node-only delivery QA (bin/schematically.mjs).

Delivers documents with nothing but Node into a temporary directory, opens each result from disk
in headless Chromium with every non-file request refused, and checks:

- `demo` writes a document with no coordinates, lays it out, and delivers it;
- every delivered page draws itself in the reader's browser with no error and no network request,
  removes its drawing frame, and shows one card per component of the document;
- the delivered page holds the same cards, wires and arcs as scripts/export_html.py makes for the
  same document (both read the editor through sovExtract in the template);
- a document that fails its check exits 1 with JSON diagnostics and leaves the last good file
  byte for byte, and no candidate file behind;
- a usage error exits 2;
- the installable skill (skills/schematically) carries every file the command reads, byte-equal to
  its source (build.py writes the copy), and its own copy delivers the document SKILL.md teaches.
"""
from __future__ import annotations
import ast
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
from export_html import export_documents  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

CLI = ROOT / 'bin' / 'schematically.mjs'
SKILL = ROOT / 'skills' / 'schematically'
BUNDLE = ast.literal_eval(re.search(r'SKILL_BUNDLE=(\[.*?\])', (ROOT / 'build.py').read_text(encoding='utf-8'), re.S).group(1))
# Kept small: the parity half runs the headless export, which opens the editor once per file.
EXAMPLES = ['04-boundary-port.sov', '08-gated-service.sov', '13-half-adder.sov']
SHAPE_JS = """() => {
  const D = window.SovViewer.data;
  return {nodes: D.nodes.map(n => n.id).sort(), wires: D.wires.map(w => w.id).sort(),
          arcs: D.arcs.map(a => [a.wire, a.from, a.to, a.control].join('|')).sort(),
          drawn: [...document.querySelectorAll('#stage g.node[data-id]')].map(g => g.dataset.id).sort(),
          frames: document.querySelectorAll('iframe').length, title: document.title};
}"""


def cli(*args: str, entry: Path = CLI) -> subprocess.CompletedProcess:
    return subprocess.run(['node', str(entry), *args], capture_output=True, text=True, timeout=120)


def check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def open_delivered(browser, path: Path) -> tuple[dict, list[str], list[str]]:
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    errors: list[str] = []
    requests: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('request', lambda req: requests.append(req.url)
            if not req.url.startswith(('file:', 'data:', 'blob:', 'about:')) else None)
    page.route('**/*', lambda route: route.continue_() if route.request.url.startswith(('file:', 'data:', 'blob:', 'about:')) else route.abort())
    page.goto(path.resolve().as_uri())
    page.wait_for_function('() => !!window.SovViewer', timeout=60_000)
    shape = page.evaluate(SHAPE_JS)
    page.close()
    return shape, errors, requests


def main() -> int:
    from playwright.sync_api import sync_playwright
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)

        demo = cli('demo', str(out / 'demo'), '--json')
        check(demo.returncode == 0, f'demo exited {demo.returncode}: {demo.stdout}{demo.stderr}', failures)
        record = json.loads(demo.stdout or '{}')
        check(record.get('ok') is True and record.get('laidOut') is True, f'demo did not lay out and deliver: {record}', failures)

        delivered = {}
        for name in EXAMPLES:
            target = out / 'node' / name.replace('.sov', '.html')
            run = cli('deliver', str(ROOT / 'examples' / name), str(target), '--json')
            check(run.returncode == 0 and json.loads(run.stdout).get('ok'), f'{name}: deliver failed: {run.stdout}{run.stderr}', failures)
            delivered[name] = target

        exported = {Path(r['source']).name: r['target'] for r in
                    export_documents([ROOT / 'examples' / n for n in EXAMPLES], out / 'python')}

        with sync_playwright() as p:
            browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
            shape, errors, requests = open_delivered(browser, out / 'demo' / 'web-request.html')
            check(not errors and not requests, f'demo page: errors {errors}, requests {requests}', failures)
            check(shape['drawn'] == ['api', 'browser', 'cache', 'db'], f'demo page drew {shape["drawn"]}', failures)
            for name, target in delivered.items():
                doc = json.loads((ROOT / 'examples' / name).read_text(encoding='utf-8'))
                ids = sorted(c['id'] for c in doc['components'])
                shape, errors, requests = open_delivered(browser, target)
                check(not errors, f'{name}: page errors {errors}', failures)
                check(not requests, f'{name}: network requests {requests}', failures)
                check(shape['frames'] == 0, f'{name}: the drawing frame was left in the page', failures)
                check(shape['nodes'] == ids, f'{name}: cards {shape["nodes"]} != components {ids}', failures)
                check(set(shape['drawn']) <= set(ids) and shape['drawn'], f'{name}: drawn cards {shape["drawn"]}', failures)
                reference, _, _ = open_delivered(browser, exported[name])
                for key in ('nodes', 'wires', 'arcs', 'drawn', 'title'):
                    check(shape[key] == reference[key], f'{name}: {key} differs from export_html: {shape[key]} != {reference[key]}', failures)
            browser.close()

        good = delivered[EXAMPLES[0]]
        before = good.read_bytes()
        broken = out / 'broken.sov'
        broken.write_text(json.dumps({'schema': 'soveraeign.schematic/document@0.1', 'id': 'broken', 'revision': 0,
                                      'components': [{'id': 'a', 'symbolId': 'act'}],
                                      'wires': [{'id': 'w', 'a': 'a', 'aSide': 'out', 'b': 'missing', 'bSide': 'in'}],
                                      'references': []}), encoding='utf-8')
        bad = cli('deliver', str(broken), str(good), '--json')
        result = json.loads(bad.stdout or '{}')
        check(bad.returncode == 1, f'a broken document exited {bad.returncode}', failures)
        check(result.get('ok') is False and result.get('diagnostics') and all({'code', 'subject', 'message'} <= set(d) for d in result['diagnostics']),
              f'a broken document gave no diagnostics: {result}', failures)
        check(good.read_bytes() == before, 'a failed deliver changed the last good file', failures)
        check(not list(good.parent.glob('*.tmp')), 'a candidate file was left behind', failures)

        for rel in BUNDLE:
            copy = SKILL / rel
            check(copy.exists() and copy.read_bytes() == (ROOT / rel).read_bytes(), f'skill bundle {rel} is missing or stale; run python build.py', failures)
        taught = re.search(r'```json\n(.*?)```', (SKILL / 'SKILL.md').read_text(encoding='utf-8'), re.S).group(1)
        (out / 'taught.sov').write_text(taught, encoding='utf-8')
        run = cli('deliver', str(out / 'taught.sov'), '--json', entry=SKILL / 'bin' / 'schematically.mjs')
        check(run.returncode == 0 and json.loads(run.stdout).get('laidOut') is True, f'the SKILL.md document did not deliver: {run.stdout}{run.stderr}', failures)

        usage = cli('deliver')
        check(usage.returncode == 2, f'a usage error exited {usage.returncode}', failures)
        flag = cli('validate', str(ROOT / 'examples' / EXAMPLES[0]), '--nope')
        check(flag.returncode == 2, f'an unknown flag exited {flag.returncode}', failures)

    for f in failures:
        print('FAIL', f)
    print('deliver QA:', 'FAIL' if failures else 'PASS', f'({len(EXAMPLES)} examples + demo)')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
