#!/usr/bin/env python3
"""One release path: a v* tag builds the web deployment and the desktop installers, each stamped.

Static checks on .github/workflows/release.yml and ci.yml, then a real build with SOV_BUILD_REVISION
set: the revision reaches desktop/dist/index.html only, and the committed index.html is unchanged.
"""
from __future__ import annotations
from pathlib import Path
import os
import subprocess
import sys

try:
    import yaml
except ImportError:
    raise SystemExit('FAIL release path QA: PyYAML is needed to parse the workflows (add it to requirements-dev.txt)')

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'v0.0.0-test 0000000'
META = f'<meta name="sov-revision" content="{REVISION}">'


def load(name: str) -> dict:
    return yaml.safe_load((ROOT / '.github/workflows' / name).read_text(encoding='utf-8'))


def triggers(workflow: dict) -> dict:
    # YAML 1.1 reads the bare key `on` as the boolean True.
    return workflow['on'] if 'on' in workflow else workflow[True]


def step_text(job: dict) -> str:
    return '\n'.join(str(value) for step in job.get('steps', []) for value in step.values() if not isinstance(value, dict)) + \
        '\n'.join(str(v) for step in job.get('steps', []) for v in (step.get('with') or {}).values())


def needs(job: dict) -> set[str]:
    value = job.get('needs', [])
    return {value} if isinstance(value, str) else set(value)


def build(revision: str | None) -> None:
    env = {k: v for k, v in os.environ.items() if k != 'SOV_BUILD_REVISION'}
    if revision is not None:
        env['SOV_BUILD_REVISION'] = revision
    subprocess.run([sys.executable, str(ROOT / 'build.py')], cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)


def committed(path: str) -> bytes:
    return subprocess.run(['git', 'show', f'HEAD:{path}'], cwd=ROOT, check=True, capture_output=True).stdout


def workflows_part() -> None:
    release = load('release.yml')
    tags = triggers(release)['push']['tags']
    assert any(tag.startswith('v') for tag in tags), f'release.yml must run on v* tags: {tags}'
    assert set(triggers(release)) == {'push'}, 'release.yml runs on a tag push only'
    jobs = release['jobs']
    assert set(jobs) == {'verify', 'web', 'pages', 'desktop', 'release'}, sorted(jobs)
    assert needs(jobs['verify']) == set()
    assert needs(jobs['web']) == {'verify'}
    assert needs(jobs['pages']) == {'web'}
    assert needs(jobs['desktop']) == {'verify'}
    assert needs(jobs['release']) == {'web', 'pages', 'desktop'}
    assert jobs['desktop']['runs-on'] == 'windows-latest'
    assert 'python scripts/qa.py' in step_text(jobs['verify'])
    assert 'SOV_BUILD_REVISION' in jobs['web']['env'] and 'SOV_BUILD_REVISION' in jobs['desktop']['env']
    assert 'python scripts/stage_site.py' in step_text(jobs['web'])
    assert 'schematically-web-${{ github.ref_name }}.zip' in step_text(jobs['web'])
    assert 'actions/upload-pages-artifact' in str(jobs['web']['steps'])
    assert jobs['pages']['environment']['name'] == 'github-pages'
    assert jobs['pages']['permissions'] == {'pages': 'write', 'id-token': 'write'}
    assert 'actions/deploy-pages' in str(jobs['pages']['steps'])
    desktop = step_text(jobs['desktop'])
    for needle in ('python build.py', 'dtolnay/rust-toolchain@stable', 'cargo install tauri-cli --version "^2" --locked',
                   'cargo tauri build', 'python tests/desktop_launch_qa.py --binary', 'bundle/msi/*.msi', 'bundle/nsis/*-setup.exe'):
        assert needle in desktop, f'desktop job lacks {needle}'
    assert jobs['release']['permissions'] == {'contents': 'write'}
    upload = step_text(jobs['release'])
    assert 'gh release create' in upload and 'secrets.GITHUB_TOKEN' in str(jobs['release']['steps'])
    for needle in ('schematically-web-${{ github.ref_name }}.zip', '*.msi', '*-setup.exe', 'REVISION.txt'):
        assert needle in upload, f'release job upload list lacks {needle}'

    ci = load('ci.yml')
    assert 'deploy' not in ci['jobs'], 'ci.yml deploys nothing: the web is deployed from a tag'
    assert 'verify' in ci['jobs']
    assert ci['jobs']['verify']['timeout-minutes'] >= 45, 'verify needs room: qa.py runs 14 to 18 minutes'
    assert ci['concurrency']['cancel-in-progress'] is True, 'a superseded run on the same ref is cancelled'
    ci_on = triggers(ci)
    assert ci_on['push']['branches'] == ['dev', 'main'] and 'pull_request' in ci_on, ci_on
    assert 'upload-pages-artifact' not in (ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert 'deploy-pages' not in (ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8')


def build_part() -> None:
    head_index = committed('index.html')
    try:
        build(REVISION)
        dist = (ROOT / 'desktop/dist/index.html').read_text(encoding='utf-8')
        assert dist.count(META) == 1, 'desktop/dist/index.html must carry the sov-revision meta once'
        assert (ROOT / 'index.html').read_bytes() == head_index, 'index.html must stay byte-identical to HEAD: it never carries the meta'
        assert META.encode() not in head_index, 'the committed index.html never carries the meta'
    finally:
        build(None)
    assert META not in (ROOT / 'desktop/dist/index.html').read_text(encoding='utf-8'), 'a build without SOV_BUILD_REVISION carries no meta'
    assert (ROOT / 'index.html').read_bytes() == head_index


workflows_part()
build_part()
print('PASS release path QA: v* tag runs verify, web, pages, desktop, release; the revision is stamped on the desktop page only')
