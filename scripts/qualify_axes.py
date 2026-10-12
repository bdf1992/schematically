"""Run the axes task's bounded, case-collected acceptance profile."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import unquote, urlparse

from bounded_process import run_bounded

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / 'test-budget.json'
EVIDENCE_ROOT = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'Schematically/test-evidence/schematically-a-document-declares-axes-a-card-stores-its-values'
MARKER = re.compile(r'^QA_CASE ([a-z0-9-]+)$', re.MULTILINE)
AXIS_MARKER = re.compile(r'^\(([a-k])\)', re.MULTILINE)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(paths: list[str]) -> dict[str, str]:
    files = set()
    for name in paths:
        path = ROOT / name
        if any(char in name for char in '*?['):
            files.update(p for p in ROOT.glob(name) if p.is_file())
        elif path.is_dir():
            files.update(p for p in path.rglob('*') if p.is_file())
        elif path.is_file():
            files.add(path)
        else:
            raise FileNotFoundError(f'budget input is missing: {name}')
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(files)}


def executable_lines(source: str) -> list[tuple[int, str]]:
    return [(i, line) for i, line in enumerate(source.splitlines(), 1)
            if line.strip() and not line.lstrip().startswith('//')]


def utf16_len(text: str) -> int:
    return len(text.encode('utf-16-le')) // 2


def module_coverage(policy: dict, node_dir: Path, browser_paths: list[Path]) -> list[dict]:
    observations: dict[str, list[dict]] = {name: [] for name in policy['sourceScope']}
    for result_file in node_dir.glob('*.json'):
        try:
            records = json.loads(result_file.read_text(encoding='utf-8')).get('result', [])
        except (OSError, ValueError):
            continue
        for record in records:
            url = record.get('url', '')
            if not url.startswith('file:'):
                continue
            file = unquote(urlparse(url).path).lstrip('/')
            if os.name == 'nt' and re.match(r'^[A-Za-z]:', file) is None:
                continue
            try:
                name = Path(file).resolve().relative_to(ROOT.resolve()).as_posix()
            except (ValueError, OSError):
                continue
            if name in observations:
                observations[name].append({'functions': record.get('functions', []), 'startOffset': 0})
    for path in browser_paths:
        if not path.exists():
            continue
        try:
            modules = json.loads(path.read_text(encoding='utf-8')).get('modules', [])
        except (OSError, ValueError):
            continue
        for module in modules:
            if module['file'] in observations:
                observations[module['file']].append({
                    'functions': module.get('functions', []),
                    'source': module.get('source', ''),
                })
    report = []
    for name in policy['sourceScope']:
        source = (ROOT / name).read_text(encoding='utf-8')
        positions = []
        offset = 0
        for line in source.splitlines():
            if line.strip() and not line.lstrip().startswith('//'):
                column = len(line) - len(line.lstrip())
                positions.append(utf16_len(source[:offset + column]))
            offset += len(line) + 1
        covered = set()
        for record in observations[name]:
            start = 0
            if 'source' in record:
                embedded = record['source']
                where = embedded.find(source.strip())
                if where < 0:
                    continue
                start = utf16_len(embedded[:where])
            ranges = [r for fn in record['functions'] for r in fn.get('ranges', [])]
            ranges.sort(key=lambda r: r['endOffset'] - r['startOffset'])
            for i, pos in enumerate(positions):
                match = next((r for r in ranges if r['startOffset'] <= start + pos < r['endOffset']), None)
                if match and match.get('count', 0) > 0:
                    covered.add(i)
        report.append({'file': name, 'lines': len(positions), 'covered': len(covered),
                       'percent': round(100 * len(covered) / max(1, len(positions)), 2),
                       'observations': len(observations[name]), 'sha256': sha(ROOT / name)})
    return report


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] != '--profile' or sys.argv[2] != 'routine':
        print('usage: python scripts/qualify_axes.py --profile routine', file=sys.stderr)
        return 2
    policy = json.loads(POLICY_PATH.read_text(encoding='utf-8'))
    profile = policy['profile']
    started = time.monotonic()
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + f'-{os.getpid()}'
    out = EVIDENCE_ROOT / stamp
    out.mkdir(parents=True, exist_ok=False)
    node_dir = out / 'node-coverage'
    node_dir.mkdir()
    all_scopes = [*policy['sourceScope'], *policy['staticScope'], *policy['harnessScope'], *policy['dependencyScope']]
    before = identity(all_scopes)
    expected = profile['caseMarkers']
    command_rows = []
    cases: list[str] = []
    passed = True
    env = dict(os.environ)
    env['NODE_V8_COVERAGE'] = str(node_dir)
    for index, command in enumerate(policy['commands']):
        remaining = profile['maximumSeconds'] - (time.monotonic() - started) - 5
        if remaining <= 0:
            passed = False
            command_rows.append({'command': command, 'failure': 'routine time budget exhausted before launch'})
            break
        if command[1] in {'tests/declared_axes_qa.py', 'tests/card_badges_qa.py', 'tests/status_chip_qa.py'}:
            output_path = out / f'browser-{Path(command[1]).stem}.json'
            env['SCHEMATIC_QA_BROWSER_COVERAGE'] = str(output_path)
        else:
            env.pop('SCHEMATIC_QA_BROWSER_COVERAGE', None)
        log = out / f'{index:02d}-{Path(command[1]).stem}.log'
        try:
            result = run_bounded([sys.executable, *command[1:]], ROOT, env, log, remaining)
            stdout = log.read_text(encoding='utf-8', errors='replace')
        except Exception as error:
            result = {'exitCode': None, 'timedOut': False, 'descendantsStopped': False,
                      'failure': f'{type(error).__name__}: {error}'}
            stdout = log.read_text(encoding='utf-8', errors='replace') if log.exists() else ''
        if command[1] == 'tests/declared_axes_qa.py':
            found = [f'axes-{m}' for m in AXIS_MARKER.findall(stdout)]
            want = [f'axes-{m}' for m in expected['declared-axes']]
        elif command[1].endswith('_qa.py'):
            name = Path(command[1]).stem.removesuffix('_qa').replace('_', '-')
            found = MARKER.findall(stdout)
            want = expected.get(name, [])
            found = [f'{name}-{value}' for value in found]
            want = [f'{name}-{value}' for value in want]
        else:
            found, want = [], []
        cases.extend(found)
        markers_match = found == want and len(set(found)) == len(found)
        command_ok = result.get('exitCode') == 0 and not result.get('timedOut') and result.get('descendantsStopped') is True
        command_rows.append({'command': command, **result, 'log': str(log), 'caseIds': found,
                             'expectedCaseIds': want, 'caseMarkersComplete': markers_match,
                             'passed': command_ok and markers_match})
        passed &= command_ok and markers_match
        if not command_ok or not markers_match:
            break
    browser_paths = list(out.glob('browser-*.json'))
    coverage = module_coverage(policy, node_dir, browser_paths)
    total, hit = sum(x['lines'] for x in coverage), sum(x['covered'] for x in coverage)
    coverage_pct = 100 * hit / max(1, total)
    after = identity(all_scopes)
    elapsed = time.monotonic() - started
    checks = {
        'sourceFresh': before == after,
        'casesWithinLimit': 0 < len(cases) <= profile['maximumCases'],
        'coverageWithinLimit': coverage_pct >= profile['minimumExecutableLineCoverage'],
        'elapsedWithinLimit': elapsed <= profile['maximumSeconds'],
        'allCommandsPassed': passed and len(command_rows) == len(policy['commands']),
        'allSourceObserved': all(row['observations'] > 0 for row in coverage),
    }
    try:
        node_version = subprocess.check_output(['node', '--version'], text=True, timeout=5).strip()
    except Exception as error:
        node_version = f'unavailable: {type(error).__name__}: {error}'
    browser_versions = []
    for path in browser_paths:
        try:
            version = json.loads(path.read_text(encoding='utf-8')).get('browserVersion')
            if version:
                browser_versions.append({'evidence': str(path), 'version': version})
        except (OSError, ValueError):
            continue
    try:
        from importlib.metadata import version as package_version
        playwright_version = package_version('playwright')
    except Exception as error:
        playwright_version = f'unavailable: {type(error).__name__}: {error}'
    evidence = {
        'formatVersion': 1, 'task': policy['task'], 'policyVersion': policy['version'],
        'policySha256': sha(POLICY_PATH), 'profile': profile, 'command': [sys.executable, 'scripts/qualify_axes.py', '--profile', 'routine'],
        'python': sys.version, 'node': node_version,
        'dependencies': {'playwright': playwright_version, 'browsers': browser_versions,
                         'sourceFiles': before},
        'environment': {k: env.get(k) for k in ('NODE_V8_COVERAGE', 'SCHEMATIC_QA_BROWSER_COVERAGE')},
        'sourceIdentityBefore': before, 'sourceIdentityAfter': after,
        'caseCount': len(cases), 'caseIds': cases, 'commands': command_rows,
        'coverage': {'coveredExecutableLines': hit, 'executableLines': total, 'percent': round(coverage_pct, 2), 'files': coverage},
        'elapsedSeconds': round(elapsed, 3), 'checks': checks, 'passed': all(checks.values())
    }
    (out / 'evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps({'evidence': str(out / 'evidence.json'), 'caseCount': len(cases),
                      'coveragePercent': round(coverage_pct, 2), 'elapsedSeconds': round(elapsed, 3),
                      'passed': evidence['passed']}))
    return 0 if evidence['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
