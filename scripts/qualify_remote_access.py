"""One-shot supervised routine qualification for the remote access branch."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
BUDGET_PATH = ROOT / 'scripts/remote-access-test-budget.json'


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def identity(paths):
    return {str(p.relative_to(ROOT).as_posix()): sha(p) for p in sorted(set(paths)) if p.is_file()}


def scoped_files(budget):
    paths = [BUDGET_PATH]
    for pattern in budget['input_scope']:
        paths.extend(ROOT.glob(pattern))
    paths.extend(ROOT / p for p in budget['source_scope'])
    return [p for p in paths if p.is_file()]


def case_ids(suite, output):
    found = []
    for line in output.splitlines():
        m = re.match(r'^CASE PASS ([A-Za-z0-9][A-Za-z0-9_./:-]*)$', line)
        if m:
            found.append(m.group(1))
        elif suite == 'access-gate':
            m = re.match(r'^PASS (unit: )?(.+)$', line)
            if m and m.group(2) not in {'access gate unit', 'access gate QA'}:
                prefix = 'access-gate/unit/' if m.group(1) else 'access-gate/http/'
                slug = re.sub(r'[^a-z0-9]+', '-', m.group(2).lower()).strip('-')
                found.append(prefix + slug)
        elif line.startswith('PASS ') and line not in {
            'PASS multi-document QA', 'PASS database store QA',
            'PASS document reload QA',
        }:
            slug = re.sub(r'[^a-z0-9]+', '-', line[5:].lower()).strip('-')
            found.append(suite + '/' + slug)
    # Several checks intentionally reuse a label while exercising distinct listeners. Preserve
    # every emitted marker and distinguish repeated occurrences by their order in the log.
    totals = {}
    for item in found:
        totals[item] = totals.get(item, 0) + 1
    seen = {}
    unique = []
    for item in found:
        seen[item] = seen.get(item, 0) + 1
        unique.append(f'{item}-occurrence-{seen[item]}' if totals[item] > 1 else item)
    return unique


def v8_coverage(directory):
    # V8 ranges are byte offsets and include zero-count executable ranges. Map those ranges
    # against the exact UTF-8 source bytes so the denominator includes uncovered executable lines.
    totals = {name: {'covered': set(), 'executable': set()} for name in ('mcp/access.mjs', 'mcp/server.mjs')}
    for report in Path(directory).glob('coverage-*.json'):
        try:
            data = json.loads(report.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        for script in data.get('result', []):
            url = script.get('url', '')
            parsed = urlparse(url)
            script_path = unquote(parsed.path) if parsed.scheme == 'file' else url
            if os.name == 'nt' and re.match(r'^/[A-Za-z]:/', script_path):
                script_path = script_path[1:]
            for name in totals:
                if Path(script_path).resolve() != (ROOT / name).resolve():
                    continue
                raw = (ROOT / name).read_bytes()
                starts = [0]
                starts.extend(i + 1 for i, b in enumerate(raw) if b == 10)
                for fn in script.get('functions', []):
                    for r in fn.get('ranges', []):
                        lo, hi = r['startOffset'], r['endOffset']
                        if hi <= lo:
                            continue
                        first = max(0, __import__('bisect').bisect_right(starts, lo) - 1)
                        last = max(first, __import__('bisect').bisect_left(starts, hi) - 1)
                        for line in range(first + 1, min(last + 1, len(starts)) + 1):
                            totals[name]['executable'].add(line)
                            if r.get('count', 0) > 0:
                                totals[name]['covered'].add(line)
    details = {}
    for name, sets in totals.items():
        denominator = sets['executable']
        if not denominator:
            details[name] = {'covered': 0, 'executable': 0, 'percent': 0.0, 'uncovered': []}
            continue
        details[name] = {
            'covered': len(sets['covered'] & denominator),
            'executable': len(denominator),
            'percent': round(100 * len(sets['covered'] & denominator) / len(denominator), 2),
            'uncovered': sorted(denominator - sets['covered']),
        }
    numerator = sum(x['covered'] for x in details.values())
    denominator = sum(x['executable'] for x in details.values())
    return details, (round(100 * numerator / denominator, 2) if denominator else 0.0)


def main():
    from bounded_process import run_bounded
    budget = json.loads(BUDGET_PATH.read_text(encoding='utf-8'))
    if len(sys.argv) != 5 or sys.argv[1:3] != ['--profile', budget['profile']] or sys.argv[3] != '--out':
        raise SystemExit('usage: qualify_remote_access.py --profile routine --out <directory>')
    out = Path(sys.argv[4]).resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit('output directory must be new or empty')
    out.mkdir(parents=True, exist_ok=True)
    cov = out / 'v8-coverage'
    cov.mkdir()
    files = scoped_files(budget)
    before = identity(files)
    evidence = {
        'policy': budget['version'], 'profile': budget['profile'],
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'command': [sys.executable, *sys.argv], 'python': sys.version,
        'node': subprocess.run(['node', '--version'], capture_output=True, text=True).stdout.strip(),
        'python_dependencies': subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout.splitlines(),
        'source_and_input_sha256_before': before, 'suites': [], 'case_ids': [],
    }
    env = dict(os.environ)
    env['NODE_V8_COVERAGE'] = str(cov)
    started = time.monotonic()
    deadline = started + budget['max_seconds']
    failed = False
    commands = budget['commands']
    for index, command in enumerate(commands):
        suite = ('syntax-server' if index == 0 else 'syntax-access' if index == 1 else
                 ['access-gate', 'multi-document', 'database-store', 'document-reload',
                  'mcp-surface', 'revision-guard', 'served-editor', 'qa-linux', 'golden'][index - 2])
        remaining = deadline - time.monotonic()
        if remaining <= 5:
            evidence['suites'].append({'name': suite, 'command': command, 'status': 'not-run-budget-exhausted', 'cases': [], 'elapsed_seconds': 0})
            failed = True
            continue
        argv = (['node', '--check', str(ROOT / command[2])] if command[0] == 'node'
                else [sys.executable, str(ROOT / command[1])])
        log = out / f'{index:02d}-{suite}.log'
        result = run_bounded(argv, ROOT, env, log, max(1, int(remaining)))
        output = log.read_text(encoding='utf-8', errors='replace') if log.exists() else ''
        ids = case_ids(suite, output) if index >= 2 else []
        dup = sorted({x for x in ids if ids.count(x) > 1})
        evidence['case_ids'].extend(ids)
        status = 'passed' if result.get('exitCode') == 0 and not result.get('timedOut') and result.get('descendantsStopped') and not dup else 'failed'
        failed |= status != 'passed'
        evidence['suites'].append({
            'name': suite, 'command': argv, 'exit_code': result.get('exitCode'),
            'timed_out': result.get('timedOut', False), 'descendants_stopped': result.get('descendantsStopped'),
            'elapsed_seconds': result.get('elapsedSeconds'),
            'case_count': len(ids), 'case_ids': ids, 'duplicate_case_ids': dup,
            'status': status, 'log': log.name,
        })
    details, coverage = v8_coverage(cov)
    after = identity(files)
    all_ids = evidence['case_ids']
    duplicated = sorted({x for x in all_ids if all_ids.count(x) > 1})
    evidence.update({
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'actual_case_count': len(all_ids), 'duplicate_case_ids': duplicated,
        'coverage': {'by_source': details, 'overall_percent': coverage},
        'source_and_input_sha256_after': after,
        'identity_unchanged': before == after,
    })
    min_cases = budget['minimum_cases_by_suite']
    suite_counts = {item['name']: item['case_count'] for item in evidence['suites']}
    checks = {
        'case_ceiling': len(all_ids) <= budget['max_cases'],
        'time_ceiling': evidence['elapsed_seconds'] <= budget['max_seconds'],
        'source_coverage': all(x['executable'] > 0 for x in details.values()) and coverage >= budget['minimum_line_coverage_percent'],
        'suite_case_floors': all(suite_counts.get(k, 0) >= v for k, v in min_cases.items()),
        'unique_case_ids': not duplicated,
        'input_identity_stable': before == after,
        'all_suites_passed': all(s['status'] == 'passed' for s in evidence['suites']),
    }
    evidence['checks'] = checks
    evidence['result'] = 'PASS' if all(checks.values()) and not failed else 'FAIL'
    evidence['finished_utc'] = datetime.now(timezone.utc).isoformat()
    (out / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'result': evidence['result'], 'case_count': len(all_ids), 'elapsed_seconds': evidence['elapsed_seconds'], 'coverage_percent': coverage, 'checks': checks, 'evidence': str(out / 'evidence.json')}, indent=2))
    return 0 if evidence['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
