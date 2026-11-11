#!/usr/bin/env python3
"""The whole suite on this PC, then the release (D-0136).

    python scripts/release.py v1.2.3 --dry-run   # each precondition, the suite and the steps; runs nothing
    python scripts/release.py v1.2.3             # whole suite, then the local annotated tag, then stops
    python scripts/release.py v1.2.3 --publish   # ... and pushes the tag and publishes the release

This repository is public, so pushing a tag and publishing a release speaks publicly as its owner
(D-0134 high tier): without --publish the command stops after the local tag and prints the one-line
brief to accept. Pushing a v* tag starts .github/workflows/release.yml, which builds the web
deployment and the desktop installers and creates the GitHub release with them attached; so with
--publish this command pushes the tag and leaves the release to that workflow instead of creating a
second, empty one with gh release create.

The suite is scripts/qa.py, every suite in it (no --quick), with test-budget.arch.json's full-qa
worker count and its seconds as the limit. The result is written to
<temp>/release-receipts/<version>.json.

Exit 0 released (or tagged, or dry run), 1 suite failed or over its limit, 2 refused.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = True
RELEASE_BRANCH = 'origin/main'
VERSION = re.compile(r'v(\d+)\.(\d+)\.(\d+)')
TAG_WORKFLOW = ROOT / '.github' / 'workflows' / 'release.yml'


def git(*args: str, check: bool = True) -> str:
    done = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True)
    if check and done.returncode != 0:
        raise RuntimeError(f'git {" ".join(args)} failed: {done.stderr.strip()}')
    return done.stdout.strip() if done.returncode == 0 else ''


def parse(version: str) -> tuple[int, int, int] | None:
    match = VERSION.fullmatch(version)
    return tuple(int(part) for part in match.groups()) if match else None


def declared_version() -> tuple[str, str] | None:
    """package.json or pyproject.toml, where the repository declares one."""
    package = ROOT / 'package.json'
    if package.is_file():
        value = json.loads(package.read_text(encoding='utf-8')).get('version')
        if value:
            return 'package.json', str(value)
    pyproject = ROOT / 'pyproject.toml'
    if pyproject.is_file():
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding='utf-8'))
        if match:
            return 'pyproject.toml', match.group(1)
    return None


def full_qa_policy() -> tuple[int, int]:
    policy = json.loads((ROOT / 'test-budget.arch.json').read_text(encoding='utf-8'))
    workers = policy.get('maximumWorkers')
    seconds = policy.get('profiles', {}).get('full-qa', {}).get('maximumSeconds')
    if not isinstance(workers, int) or not isinstance(seconds, int):
        raise RuntimeError('test-budget.arch.json declares no maximumWorkers or full-qa maximumSeconds')
    return workers, seconds


def preconditions(version: str) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    wanted = parse(version)
    checks.append(('version is vMAJOR.MINOR.PATCH', wanted is not None, version))
    # A pre-release tag (v0.1.0-pre-scale) counts as its vMAJOR.MINOR.PATCH core.
    cores = {t: tuple(int(x) for x in m.groups()) for t in git('tag', '--list', 'v*').splitlines()
             if (m := VERSION.match(t))}
    newest = max(cores, key=cores.get) if cores else None
    newer = wanted is not None and (newest is None or wanted > cores[newest])
    checks.append(('version is newer than every v* tag', newer, f'newest tag {newest or "none"}'))
    declared = declared_version()
    if declared:
        checks.append((f'version equals {declared[0]}', version.lstrip('v') == declared[1], declared[1]))
    else:
        checks.append(('declared version', True, 'none declared (no package.json or pyproject.toml version)'))
    dirty = git('status', '--porcelain')
    checks.append(('working tree is clean', not dirty, f'{len(dirty.splitlines())} changed path(s)' if dirty else 'clean'))
    head = git('rev-parse', 'HEAD')
    release = git('rev-parse', '--verify', '--quiet', RELEASE_BRANCH, check=False)
    checks.append((f'HEAD equals {RELEASE_BRANCH}', bool(release) and head == release,
                   f'HEAD {head[:12]}, {RELEASE_BRANCH} {release[:12] or "missing"}'))
    return checks


def kill_tree(process: subprocess.Popen) -> None:
    if os.name == 'nt':
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], capture_output=True)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def run_suite(command: list[str], limit: int) -> dict:
    started = time.monotonic()
    extra = {'start_new_session': True} if os.name != 'nt' else {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
    child = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, text=True, encoding='utf-8',
                             errors='replace', **extra)
    counts = {'passed': 0, 'failed': 0}
    summary: list[str] = []

    def pump() -> None:
        assert child.stdout is not None
        for line in child.stdout:
            print(line, end='', flush=True)
            if line.startswith('QA PASS '):
                counts['passed'] += 1
            elif line.startswith('QA FAIL '):
                counts['failed'] += 1
            elif line.startswith('RC QA PASS'):
                summary.append(line.strip())

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    timed_out = False
    try:
        child.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_tree(child)
    reader.join(timeout=10)
    return {'command': command, 'limit_seconds': limit, 'seconds': round(time.monotonic() - started, 1),
            'exit_code': child.returncode, 'timed_out': timed_out, 'summary': summary[-1] if summary else None,
            **counts}


def write_receipt(version: str, receipt: dict) -> Path:
    folder = Path(tempfile.gettempdir()) / 'release-receipts'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{version}.json'
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('version', help='vMAJOR.MINOR.PATCH, newer than every v* tag')
    parser.add_argument('--dry-run', action='store_true', help='print preconditions, suite and steps; run nothing')
    parser.add_argument('--publish', action='store_true', help='push the tag and publish (public repository)')
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return 2 if error.code else 0
    try:
        workers, limit = full_qa_policy()
    except (OSError, ValueError, RuntimeError) as error:
        print(f'release: refused: {error}')
        return 2
    command = [sys.executable, str(ROOT / 'scripts' / 'qa.py'), '--workers', str(workers)]
    version = args.version
    if not args.dry_run:
        fetched = subprocess.run(['git', 'fetch', 'origin', 'main', '--tags'], cwd=ROOT, capture_output=True, text=True)
        if fetched.returncode != 0:
            print(f'release: refused: git fetch origin main --tags failed: {fetched.stderr.strip()}')
            return 2
    try:
        checks = preconditions(version)
    except RuntimeError as error:
        print(f'release: refused: {error}')
        return 2
    holds = all(ok for _, ok, _ in checks)
    tag_message = f'{version}: whole suite passed on this PC'
    if args.dry_run:
        print(f'release: dry run for {version} ({RELEASE_BRANCH} as last fetched; nothing runs)')
        for name, ok, detail in checks:
            print(f'  {"holds" if ok else "FAILS"}  {name}: {detail}')
        print(f'  suite  {" ".join(["python", "scripts/qa.py", "--workers", str(workers)])} '
              f'(every suite, release-only ones included; limit {limit} s from test-budget.arch.json full-qa)')
        print('  note   not in scripts/qa.py: tests/arch_observation.test.cjs and tests/qa_scheduler_qa.py run under '
              'node scripts/test-arch-container.cjs --profile full-qa; tests/desktop_launch_qa.py runs in release.yml')
        print(f'  step   write <temp>/release-receipts/{version}.json')
        print(f'  step   git tag -a {version} -m "{tag_message}"')
        if PUBLIC:
            print(f'  step   stop: public repository; brief to accept: push {version} and publish the release '
                  f'(then rerun with --publish)')
        print(f'  step   with --publish: git push origin {version}')
        if TAG_WORKFLOW.is_file():
            print('  step   with --publish: the tag starts .github/workflows/release.yml, which creates the release '
                  'with the web zip and installers attached')
        else:
            print(f'  step   with --publish: gh release create {version} --verify-tag --generate-notes '
                  '--notes-file <receipt summary>')
        print(f'release: dry run: preconditions {"hold" if holds else "do not hold"}; exit 0')
        return 0
    for name, ok, detail in checks:
        print(f'release: {"holds" if ok else "FAILS"}  {name}: {detail}')
    if not holds:
        print('release: refused: a precondition does not hold')
        return 2
    revision = git('rev-parse', 'HEAD')
    result = run_suite(command, limit)
    receipt = {'version': version, 'revision': revision, 'cwd': str(ROOT), 'workers': workers, **result,
               'passed_suite': result['exit_code'] == 0 and not result['timed_out'] and result['failed'] == 0}
    receipt_path = write_receipt(version, receipt)
    print(f'release: receipt {receipt_path}')
    if not receipt['passed_suite']:
        why = f'over its {limit} s limit' if result['timed_out'] else f'exit {result["exit_code"]}'
        print(f'release: suite failed ({why}, {result["passed"]} passed, {result["failed"]} failed '
              f'in {result["seconds"]} s); no tag')
        return 1
    git('tag', '-a', version, '-m', tag_message)
    print(f'release: tagged {version} at {revision[:12]} ({result["passed"]} suites passed in {result["seconds"]} s)')
    if PUBLIC and not args.publish:
        print(f'release: public repository, stopped after the local tag. Brief: push {version} and publish the release')
        return 0
    pushed = subprocess.run(['git', 'push', 'origin', version], cwd=ROOT)
    if pushed.returncode != 0:
        print(f'release: git push origin {version} failed; the local tag stays')
        return 1
    if TAG_WORKFLOW.is_file():
        print(f'release: pushed {version}; .github/workflows/release.yml builds and creates the release')
        return 0
    notes = receipt_path.with_suffix('.md')
    notes.write_text(f'{tag_message}: {result["summary"] or ""} ({result["seconds"]} s)\n', encoding='utf-8', newline='\n')
    created = subprocess.run(['gh', 'release', 'create', version, '--verify-tag', '--generate-notes',
                              '--notes-file', str(notes)], cwd=ROOT)
    return 0 if created.returncode == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
