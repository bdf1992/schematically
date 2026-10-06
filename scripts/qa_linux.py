#!/usr/bin/env python3
"""Run the four font-dependent QA suites in a Linux container, as CI does.

Run on a Windows host with Docker Desktop running:
    python scripts/qa_linux.py [--tree PATH] [--suite PATH ...] [--print-command]

The tree is mounted read-only at /src. Inside the container (--inside) it is copied to /work,
built and tested there, so a run changes no file on the host. Exit 0: every suite passed.
Exit 1: a suite or build.py failed. Exit 2: the container could not run.
Standard library only; both halves take the process runner as a parameter.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve()
REPO = SCRIPT.parents[1]
DOCKERFILE = SCRIPT.with_name('qa_linux.Dockerfile')
IMAGE = 'schematically-qa-linux'
DEFAULT_SUITES = [
    'tests/layouts_qa.py',
    'tests/layout_quality_qa.py',
    'tests/authoring_review_qa.py',
    'tests/golden_rendered_text_qa.py',
]
TAR_EXCLUDES = [
    './.git', './node_modules', './desktop/src-tauri/target', './_site', './.venv',
    './review', './tests/journey', '__pycache__',
]
NO_ENGINE = 'Docker engine not reachable; start Docker Desktop with docker desktop start'


def run_process(argv, quiet=False, cwd=None) -> int:
    """Run argv; output goes through unchanged unless quiet. Returns the exit code."""
    out = subprocess.DEVNULL if quiet else None
    try:
        return subprocess.run(argv, cwd=cwd, stdout=out, stderr=out).returncode
    except OSError:
        return 127


def playwright_pin(tree: Path):
    req = tree / 'requirements-dev.txt'
    if not req.is_file():
        return None
    m = re.search(r'^playwright==([0-9][\w.]*)\s*$', req.read_text(encoding='utf-8'), re.M)
    return m.group(1) if m else None


def image_tag(tree: Path) -> str:
    h = hashlib.sha256(DOCKERFILE.read_bytes() + (tree / 'requirements-dev.txt').read_bytes())
    return h.hexdigest()[:12]


def base_tag(pin: str) -> str:
    return f'v{pin}-noble'


def build_argv(image: str, pin: str, context: str) -> list:
    return ['docker', 'build', '--build-arg', f'PLAYWRIGHT_VERSION={pin}', '-t', image, context]


def run_argv(image: str, tree: Path, suites: list) -> list:
    return [
        'docker', 'run', '--rm', '--init', '--ipc=host',
        '--mount', f'type=bind,source={tree},target=/src,readonly',
        '--mount', f'type=bind,source={SCRIPT},target=/qa_linux.py,readonly',
        image, 'python3', '/qa_linux.py', '--inside', *suites,
    ]


def host_half(tree: Path, suites: list, print_command: bool, runner=run_process) -> int:
    pin = playwright_pin(tree)
    if pin is None:
        print(f'no playwright==X.Y.Z pin in {tree / "requirements-dev.txt"}', file=sys.stderr)
        return 2
    image = f'{IMAGE}:{image_tag(tree)}'
    if print_command:
        print(json.dumps({
            'image': image,
            'build': build_argv(image, pin, '<build context: Dockerfile + requirements-dev.txt>'),
            'run': run_argv(image, tree, suites),
        }, indent=2))
        return 0
    for s in suites:
        if not (tree / s).is_file():
            print(f'suite not found under the tree: {s}', file=sys.stderr)
            return 2
    if runner(['docker', 'version', '--format', '{{.Server.Version}}'], quiet=True) != 0:
        print(NO_ENGINE, file=sys.stderr)
        return 2
    if runner(['docker', 'image', 'inspect', image], quiet=True) != 0:
        with tempfile.TemporaryDirectory() as ctx:
            shutil.copyfile(DOCKERFILE, Path(ctx) / 'Dockerfile')
            shutil.copyfile(tree / 'requirements-dev.txt', Path(ctx) / 'requirements-dev.txt')
            if runner(build_argv(image, pin, ctx)) != 0:
                print('docker build failed', file=sys.stderr)
                return 2
    code = runner(run_argv(image, tree, suites))
    return code if code in (0, 1) else 2


def inside_half(suites: list, runner=run_process, src='/src', work='/work') -> int:
    excludes = ' '.join(f'--exclude={e}' for e in TAR_EXCLUDES)
    copy = f'mkdir -p {work} && tar -C {src} {excludes} -cf - . | tar -C {work} -xf -'
    if runner(['sh', '-c', copy]) != 0:
        print('QA FAIL copy of /src to /work', flush=True)
        return 1
    runner(['fc-match', 'sans-serif'])
    runner(['fc-match', 'system-ui'])
    failed = 0
    build_failed = False
    start = time.perf_counter()
    code = runner(['python3', 'build.py'], cwd=work)
    if code != 0:
        build_failed = True
        print(f'QA FAIL build.py (exit {code}, {time.perf_counter() - start:.2f}s)', flush=True)
    for s in suites:
        start = time.perf_counter()
        code = runner(['python3', s], cwd=work)
        elapsed = time.perf_counter() - start
        if code == 0:
            print(f'QA PASS {s} ({elapsed:.2f}s)', flush=True)
        else:
            failed += 1
            print(f'QA FAIL {s} (exit {code}, {elapsed:.2f}s)', flush=True)
    if failed or build_failed:
        note = ' (build.py failed)' if build_failed else ''
        print(f'LINUX QA FAIL: {failed} of {len(suites)} suites{note}', flush=True)
        return 1
    print(f'LINUX QA PASS: {len(suites)} suites', flush=True)
    return 0


def main(argv=None, runner=run_process) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--tree', default=str(REPO))
    p.add_argument('--suite', action='append')
    p.add_argument('--print-command', action='store_true')
    p.add_argument('--inside', action='store_true')
    a = p.parse_args(argv)
    suites = a.suite or list(DEFAULT_SUITES)
    if a.inside:
        return inside_half(suites, runner)
    return host_half(Path(a.tree).resolve(), suites, a.print_command, runner)


if __name__ == '__main__':
    raise SystemExit(main())
