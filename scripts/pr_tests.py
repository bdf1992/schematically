#!/usr/bin/env python3
"""The tests a pull request runs (D-0136): only what the change touches, stopped at 60 s.

    python scripts/pr_tests.py                 # changes since origin/dev (or $GITHUB_BASE_REF) plus the working tree
    python scripts/pr_tests.py --base HEAD~1   # another base
    python scripts/pr_tests.py --dry-run       # print the selection, run nothing
    python scripts/pr_tests.py --list-all      # the whole suite, release-only suites marked

Selection, in order: a changed test file runs itself; a changed source file runs the suite its name
gives (src/NN-<name>.js, scripts/<name>.py|mjs|cjs -> tests/<name>_qa.py; mcp/<name>.mjs ->
tests/mcp_<name>_qa.py) and then the suites scripts/test_map.json lists for it; a changed source file
with neither runs the table's "*" smoke set. Only paths matching the table's "no_tests" globs run
nothing; if every chosen suite is dropped (release-only, missing), the smoke set runs instead.
Suites under "release_only" never run here. Changed JS always gets node --check.

Suites run through scripts/qa.py's own runner (its queue order, run() and run_browser() pool), in a
child process this script kills, with its whole process tree, at 60 s. The table's selections were
sized from the per-suite seconds of CI run 39323974181 (2026-10-19); release_only holds every suite
that took over 60 s there, plus the stress, timing and desktop-launch suites.

Exit 0 pass or nothing to run, 1 failed or over the ceiling, 2 refused before running.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import runpy
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CEILING_SECONDS = 60
# The trunk pull requests merge into here is dev (docs/BRANCHING.md); main is the release line.
DEFAULT_BASE = 'origin/dev'
TEST_MAP = ROOT / 'scripts' / 'test_map.json'
JS_SUFFIXES = {'.js', '.mjs', '.cjs'}
PASS_LINE = re.compile(r'^QA PASS (\S+)')


class Refused(Exception):
    pass


def git(*args: str) -> list[str]:
    try:
        done = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True)
    except FileNotFoundError as error:
        raise Refused('git is not on PATH') from error
    if done.returncode != 0:
        raise Refused(f'git {" ".join(args)} failed: {done.stderr.strip()}')
    return [line for line in done.stdout.splitlines() if line.strip()]


def default_base() -> str:
    target = os.environ.get('GITHUB_BASE_REF', '').strip()
    return f'origin/{target}' if target else DEFAULT_BASE


def changed_files(base: str) -> list[str]:
    files = set(git('diff', '--name-only', f'{base}...HEAD'))
    files |= set(git('diff', '--name-only', 'HEAD'))
    files |= set(git('ls-files', '--others', '--exclude-standard'))
    return sorted(files)


def load_map() -> dict[str, list[str]]:
    try:
        table = json.loads(TEST_MAP.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise Refused(f'{TEST_MAP.relative_to(ROOT).as_posix()} unreadable: {error}') from error
    for key in ('*', 'release_only', 'no_tests'):
        if key not in table:
            raise Refused(f'scripts/test_map.json has no "{key}" entry')
    return table


def load_queue() -> dict[str, list[str]]:
    qa = runpy.run_path(str(ROOT / 'scripts' / 'qa.py'), run_name='pr_tests')
    return {key: list(qa[key]) for key in ('STATIC', 'BROWSER', 'TAIL')}


def is_test(path: str, queue: dict[str, list[str]]) -> bool:
    if any(path in suites for suites in queue.values()):
        return True
    return bool(re.fullmatch(r'tests/[^/]+(_qa\.py|_qa\.cjs|\.test\.cjs)', path))


def no_tests(path: str, table: dict[str, list[str]]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in table['no_tests'])


def by_convention(path: str) -> str | None:
    match = re.fullmatch(r'src/\d+-(.+)\.js', path) or re.fullmatch(r'scripts/(.+)\.(?:py|mjs|cjs)', path)
    name = match.group(1) if match else None
    mcp = re.fullmatch(r'mcp/(.+)\.mjs', path)
    if mcp:
        name = 'mcp_' + mcp.group(1)
    if not name:
        return None
    suite = f"tests/{name.replace('-', '_')}_qa.py"
    return suite if (ROOT / suite).is_file() else None


def by_table(path: str, table: dict[str, list[str]]) -> list[str]:
    chosen: list[str] = []
    for pattern, suites in table.items():
        if pattern in ('*', 'release_only', 'no_tests'):
            continue
        if fnmatch.fnmatchcase(path, pattern):
            chosen += suites
    return chosen


def select(changed: list[str], table: dict[str, list[str]], queue: dict[str, list[str]]) -> dict:
    release_only = set(table['release_only'])
    reasons: dict[str, str] = {}
    left: dict[str, str] = {}
    no_code: list[str] = []

    dropped: dict[str, str] = {}

    def want(suite: str, why: str) -> None:
        if not (ROOT / suite).is_file():
            dropped.setdefault(suite, f'{why}: no such file')
        elif suite in release_only:
            in_queue = any(suite in suites for suites in queue.values())
            runner = 'python scripts/release.py runs it' if in_queue else (
                'it runs under node scripts/test-arch-container.cjs --profile full-qa or release.yml, not scripts/qa.py')
            left.setdefault(suite, f'{why}: release-only, {runner}')
        else:
            reasons.setdefault(suite, why)

    for path in changed:
        if not (ROOT / path).exists():
            if is_test(path, queue):
                continue  # a deleted test runs nothing
        if is_test(path, queue):
            want(path, 'changed')
            continue
        # Convention and table first: a doc or fixture a test reads maps like code (R2).
        conv = by_convention(path)
        mapped = ([conv] if conv else []) + by_table(path, table)
        if not mapped and no_tests(path, table):
            no_code.append(path)
            continue
        for suite in mapped or table['*']:
            want(suite, path if mapped else f'{path} (unmapped: smoke)')
    if not reasons and (left or dropped):
        # Never pass on nothing (R3): every chosen suite was dropped, so the smoke set runs.
        for suite in table['*']:
            want(suite, 'smoke: every selected suite was dropped')
    js = [p for p in changed if Path(p).suffix in JS_SUFFIXES and (ROOT / p).is_file()]
    order = [*queue['STATIC'], *queue['BROWSER'], *queue['TAIL']]
    suites = sorted(reasons, key=lambda s: (order.index(s) if s in order else len(order), s))
    return {'suites': suites, 'reasons': reasons, 'release_only': left, 'js': js, 'no_code': no_code,
            'dropped': dropped, 'needs_browser': any(s not in queue['STATIC'] for s in suites)}


def run_selected(paths: list[str], workers: int) -> int:
    """The child: scripts/qa.py's runner on the chosen suites, in its queue order."""
    qa = runpy.run_path(str(ROOT / 'scripts' / 'qa.py'), run_name='pr_tests_child')
    static = [p for p in paths if p in qa['STATIC']]
    browser = [p for p in paths if p in qa['BROWSER']]
    tail = [p for p in paths if p in qa['TAIL']]
    other = [p for p in paths if p not in static + browser + tail]
    try:
        for path in static:
            qa['run'](path)
        if browser:
            qa['run_browser'](browser, workers)
        for path in other:
            if path.endswith('.cjs'):
                started = time.perf_counter()
                done = subprocess.run(['node', str(ROOT / path)], cwd=ROOT, capture_output=True, text=True)
                print(done.stdout, end='', flush=True)
                print(done.stderr, end='', file=sys.stderr, flush=True)
                state = 'PASS' if done.returncode == 0 else 'FAIL'
                print(f'QA {state} {path} ({time.perf_counter() - started:.2f}s)', flush=True)
                done.check_returncode()
            else:
                qa['run'](path)
        for path in tail:
            qa['run'](path)
    except subprocess.CalledProcessError:
        return 1
    return 0


def kill_tree(process: subprocess.Popen) -> None:
    if os.name == 'nt':
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], capture_output=True)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def run(selection: dict, workers: int) -> int:
    started = time.monotonic()
    passed = 0
    ran: list[str] = []
    for path in selection['js']:
        done = subprocess.run(['node', '--check', str(ROOT / path)], cwd=ROOT, capture_output=True, text=True)
        ran.append(f'node --check {path}')
        if done.returncode != 0:
            print(done.stderr, end='', file=sys.stderr)
            print(f'pr-tests: node --check failed on {path}; {passed} passed in {time.monotonic() - started:.1f} s')
            return 1
        passed += 1
    if selection['suites']:
        command = [sys.executable, str(Path(__file__).resolve()), '--run-selected', '--workers', str(workers),
                   *selection['suites']]
        extra = {'start_new_session': True} if os.name != 'nt' else {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
        child = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, text=True, encoding='utf-8',
                                 errors='replace', **extra)
        finished: list[str] = []

        def pump() -> None:
            assert child.stdout is not None
            for line in child.stdout:
                print(line, end='', flush=True)
                match = PASS_LINE.match(line)
                if match:
                    finished.append(match.group(1))

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        remaining = CEILING_SECONDS - (time.monotonic() - started)
        try:
            child.wait(timeout=max(remaining, 0.1))
        except subprocess.TimeoutExpired:
            kill_tree(child)
            reader.join(timeout=5)
            pending = [s for s in selection['suites'] if s not in finished]
            what = ', '.join(ran + selection['suites'])
            print(f'pr-tests: still running at the ceiling: {", ".join(pending)}')
            print(f'over the {CEILING_SECONDS} s pull-request ceiling: {what}; move the slow test to the release suite')
            return 1
        reader.join(timeout=5)
        passed += len(finished)
        if child.returncode != 0:
            failed = [s for s in selection['suites'] if s not in finished]
            print(f'pr-tests: failed: {", ".join(failed)}; {passed} passed in {time.monotonic() - started:.1f} s')
            return 1
    print(f'pr-tests: {passed} passed in {time.monotonic() - started:.1f} s')
    return 0


def first_line(base: str, changed: list[str], selection: dict) -> str:
    chose = ', '.join(selection['suites']) or 'no suites'
    js = f' + node --check on {len(selection["js"])} JS file(s)' if selection['js'] else ''
    return f'pr-tests: {len(changed)} changed file(s) against {base}; chose {chose}{js}'


def describe(selection: dict) -> None:
    for suite in selection['suites']:
        print(f'  run   {suite}  <- {selection["reasons"][suite]}')
    for path in selection['js']:
        print(f'  check node --check {path}')
    for suite, why in selection['release_only'].items():
        print(f'  left  {suite}  <- {why}')
    for suite, why in selection['dropped'].items():
        print(f'  drop  {suite}  <- {why}')
    for path in selection['no_code']:
        print(f'  skip  {path}  (matches "no_tests")')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--base', help=f'compare HEAD with this ref (default {DEFAULT_BASE}, or origin/$GITHUB_BASE_REF)')
    parser.add_argument('--dry-run', action='store_true', help='print the selection and run nothing')
    parser.add_argument('--json', action='store_true', help='with --dry-run: print the selection as JSON')
    parser.add_argument('--list-all', action='store_true', help='print the whole suite and exit')
    parser.add_argument('--workers', type=int, default=4, choices=range(1, 9), help='parallel page checks (default 4)')
    parser.add_argument('--run-selected', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('suites', nargs='*', help=argparse.SUPPRESS)
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return 2 if error.code else 0
    if args.run_selected:
        return run_selected(args.suites, args.workers)
    if args.suites:
        print(f'pr-tests: refused: unexpected arguments {args.suites}')
        return 2
    try:
        table = load_map()
        queue = load_queue()
        if args.list_all:
            release_only = set(table['release_only'])
            everything = [*queue['STATIC'], *queue['BROWSER'], *queue['TAIL']]
            everything += [s for s in table['release_only'] if s not in everything]
            for suite in everything:
                print(f'{"release-only " if suite in release_only else ""}{suite}')
            print('node --check src/*.js mcp/*.mjs')
            print(f'pr-tests: {len(everything)} suites, {len(release_only)} release-only')
            return 0
        base = args.base or default_base()
        changed = changed_files(base)
        selection = select(changed, table, queue)
    except Refused as error:
        print(f'pr-tests: refused: {error}')
        return 2
    if args.dry_run and args.json:
        print(json.dumps({'base': base, 'changed': changed, **selection}, indent=2, sort_keys=True))
        return 0
    print(first_line(base, changed, selection))
    describe(selection)
    if not selection['suites'] and not selection['js']:
        print('pr-tests: nothing to run: every changed path matches "no_tests"; 0 passed in 0.0 s')
        return 0
    if args.dry_run:
        print(f'pr-tests: dry run: would run {len(selection["suites"])} suite(s) and '
              f'{len(selection["js"])} node check(s) under the {CEILING_SECONDS} s ceiling')
        return 0
    if selection['suites']:
        # The page the browser suites open is built first, outside the ceiling, as scripts/qa.py does.
        subprocess.run([sys.executable, str(ROOT / 'build.py')], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    return run(selection, args.workers)


if __name__ == '__main__':
    raise SystemExit(main())
