"""Desktop launch QA: the built shell opens a document.

desktop_shell_qa.py reads the shell's source; this runs it. The shell is launched the way a
double-click on a .sov launches it, with the document's path, plus `--smoke-report <file>`. In
that mode the page reports what it loaded through the shell's `report_loaded` command, which
writes the report and exits 0 when the document loaded and 1 when it did not; a shell whose page
never reports exits 2 after 30 s.

  --binary PATH   launch the built shell twice: with examples/01-source-hold.sov, which must exit
                  0 and report exactly the file's component and wire counts, then with a file that
                  is not a document, which must exit nonzero and report ok false.
  --self-check    run the same checks against stub shells (small Python scripts written to a
                  temporary directory): one that reports correctly must pass, and ones that
                  report ok false for a good file, report nothing, or report an empty editor must
                  each fail. This is the harness's own test, runnable without cargo.
  --page          drive the real page (index.html in Chromium) with a stand-in window.__TAURI__
                  and check the report it sends for both files. Needs playwright; no shell.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOOD_DOCUMENT = ROOT / 'examples' / '01-source-hold.sov'
NOT_A_DOCUMENT_TEXT = 'This file is plain text. It is not a SOV Schematic document.\n'
LAUNCH_TIMEOUT_S = 60


def document_counts(path: Path) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding='utf-8'))
    return len(data.get('components') or []), len(data.get('wires') or [])


def launch(command: list[str], document: Path, report_path: Path) -> tuple[int | None, dict | None, str]:
    """Run the shell on one document. Returns (exit code or None on timeout, report or None, output)."""
    if report_path.exists():
        report_path.unlink()
    try:
        done = subprocess.run(
            [*command, str(document), '--smoke-report', str(report_path)],
            capture_output=True,
            text=True,
            timeout=LAUNCH_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        return None, None, f'no exit within {LAUNCH_TIMEOUT_S} s; output: {exc.stdout!r} {exc.stderr!r}'
    report = None
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding='utf-8'))
        except ValueError as exc:
            return done.returncode, None, f'report is not JSON: {exc}'
    return done.returncode, report, (done.stdout + done.stderr).strip()


def check_shell(command: list[str], work: Path) -> list[str]:
    """Every way the shell fails to open a document correctly; empty when it opens both as it should."""
    failures: list[str] = []
    report_path = work / 'smoke-report.json'

    components, wires = document_counts(GOOD_DOCUMENT)
    code, report, output = launch(command, GOOD_DOCUMENT, report_path)
    if code != 0:
        failures.append(f'{GOOD_DOCUMENT.name}: exit {code}, expected 0 ({output})')
    if report is None:
        failures.append(f'{GOOD_DOCUMENT.name}: no load report written ({output})')
    else:
        expected = {'name': GOOD_DOCUMENT.name, 'components': components, 'wires': wires, 'ok': True}
        got = {key: report.get(key) for key in expected}
        if got != expected:
            failures.append(f'{GOOD_DOCUMENT.name}: reported {got}, file holds {expected}; error {report.get("error")!r}')

    not_a_document = work / 'not-a-document.sov'
    not_a_document.write_text(NOT_A_DOCUMENT_TEXT, encoding='utf-8')
    code, report, output = launch(command, not_a_document, report_path)
    if code is None or code == 0:
        failures.append(f'{not_a_document.name}: exit {code}, expected a nonzero exit ({output})')
    if report is None:
        failures.append(f'{not_a_document.name}: no load report written ({output})')
    elif report.get('ok') is not False:
        failures.append(f'{not_a_document.name}: reported ok {report.get("ok")!r}, expected false')
    return failures


STUB_HEAD = textwrap.dedent(
    '''
    import json, sys
    args = sys.argv[1:]
    report = args[args.index('--smoke-report') + 1]
    document = next(a for i, a in enumerate(args) if not a.startswith('-') and (i == 0 or args[i - 1] != '--smoke-report'))
    name = document.replace('\\\\', '/').rsplit('/', 1)[-1]
    def write(ok, components=0, wires=0, error=None):
        with open(report, 'w', encoding='utf-8') as f:
            json.dump({'name': name, 'components': components, 'wires': wires, 'ok': ok, 'error': error}, f)
    try:
        data = json.load(open(document, encoding='utf-8'))
        assert str(data.get('schema', '')).startswith('soveraeign.schematic/')
    except Exception as exc:
        data, problem = None, str(exc) or type(exc).__name__
    '''
)

# Each stub stands in for a built shell. Only the first behaves as the real one must.
STUBS = {
    'reports-correctly': '''
if data is None:
    write(False, error=problem); sys.exit(1)
write(True, len(data.get('components') or []), len(data.get('wires') or [])); sys.exit(0)
''',
    'reports-ok-false-for-a-good-file': '''
write(False, error='stub refuses every file'); sys.exit(1)
''',
    'reports-nothing': '''
sys.exit(0)
''',
    'reports-an-empty-editor': '''
write(True, 0, 0); sys.exit(0)
''',
}


def self_check() -> None:
    with tempfile.TemporaryDirectory(prefix='desktop-launch-qa-') as tmp:
        work = Path(tmp)
        results = {}
        for stub_name, body in STUBS.items():
            stub = work / f'{stub_name}.py'
            stub.write_text(STUB_HEAD + body, encoding='utf-8')
            results[stub_name] = check_shell([sys.executable, str(stub)], work)
        assert results['reports-correctly'] == [], results['reports-correctly']
        for stub_name, failures in results.items():
            if stub_name != 'reports-correctly':
                assert failures, f'the harness passed the {stub_name} stub'
                print(f'caught {stub_name}: {failures[0]}')
    print('PASS desktop launch QA self-check')


def page_check() -> None:
    """The page half of the seam, in Chromium: window.__TAURI__ is a stand-in that serves the
    launch document and records what report_loaded is called with."""
    import asyncio

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from playwright.async_api import async_playwright
    from browser_runtime import chromium_launch_kwargs

    stand_in = '''
    window.__smokeReports = [];
    window.__TAURI__ = {core: {invoke: async (command, args) => {
      if (command === 'opened_document') return window.__launchDocument;
      if (command === 'report_loaded') { window.__smokeReports.push(args); return null; }
      throw new Error('unknown command ' + command);
    }}};
    '''

    async def run(document: dict) -> list[dict]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
            page = await browser.new_page()
            await page.add_init_script(f'window.__launchDocument = {json.dumps(document)};' + stand_in)
            await page.goto((ROOT / 'index.html').resolve().as_uri(), wait_until='load')
            await page.wait_for_function('window.__smokeReports.length > 0', timeout=20000)
            reports = await page.evaluate('window.__smokeReports')
            await browser.close()
            return reports

    components, wires = document_counts(GOOD_DOCUMENT)
    good = asyncio.run(run({'name': GOOD_DOCUMENT.name, 'text': GOOD_DOCUMENT.read_text(encoding='utf-8')}))
    assert len(good) == 1, good
    assert {k: good[0][k] for k in ('name', 'components', 'wires', 'ok')} == {
        'name': GOOD_DOCUMENT.name, 'components': components, 'wires': wires, 'ok': True,
    }, (good, components, wires)
    bad = asyncio.run(run({'name': 'not-a-document.sov', 'text': NOT_A_DOCUMENT_TEXT}))
    assert len(bad) == 1 and bad[0]['ok'] is False and bad[0]['error'], bad
    print(f'page reported {GOOD_DOCUMENT.name}: {components} components, {wires} wires; '
          f'not-a-document.sov: ok false ({bad[0]["error"]})')
    print('PASS desktop launch QA page')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--binary', type=Path, help='the built desktop shell executable')
    mode.add_argument('--self-check', action='store_true', help='check the harness against stub shells')
    mode.add_argument('--page', action='store_true', help='check the page half of the seam in Chromium')
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    if args.page:
        page_check()
        return
    binary = args.binary.resolve()
    assert binary.is_file(), f'no built shell at {binary}'
    with tempfile.TemporaryDirectory(prefix='desktop-launch-qa-') as tmp:
        failures = check_shell([str(binary)], Path(tmp))
    for failure in failures:
        print(f'FAIL {failure}')
    assert not failures, f'{len(failures)} desktop launch check(s) failed'
    print(f'PASS desktop launch QA: {binary.name} opened {GOOD_DOCUMENT.name} and refused a non-document')


if __name__ == '__main__':
    main()
