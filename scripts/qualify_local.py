"""Bounded, collected-case qualification of the frozen local core.

Preparation is separate and must already be admitted and recorded. This runner
never installs dependencies or compiles native code. Its supervising process
contains the complete worker; every child stage reserves five seconds for cleanup.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sys
import time

from bounded_process import run_bounded, supervised_parent
from llvm_tools import normalize_export
from prepare_local import dependency_inputs

ROOT = Path(__file__).resolve().parents[1]
SCOPE = [
    'build.py', 'src/75-persistence.js', 'src/85-api.js', 'src/89-desktop-mcp.js',
    'mcp/store-file.mjs', 'mcp/surface.mjs', 'desktop/src-tauri/src/main.rs',
    'desktop/src-tauri/src/files.rs', 'desktop/src-tauri/src/mcp.rs',
]
SUITE_QUEUE = [
    {'id': 'native-persistence-browser', 'driver': 'tests/native_persistence_qa.py', 'runner': 'python'},
    {'id': 'desktop-mcp-browser', 'driver': 'tests/desktop_mcp_qa.py', 'runner': 'python'},
    {'id': 'headless-local', 'driver': 'tests/headless_local_qa.mjs', 'runner': 'node'},
    {'id': 'build-local', 'driver': 'tests/build_local_qa.py', 'runner': 'pythonCoverage'},
    {'id': 'native-mcp', 'driver': 'tests/native_mcp_qa.py', 'runner': 'python'},
    {'id': 'rust-unit', 'runner': 'rustTestBinary'},
]


def validate_policy(policy):
    expected = {
        'routine': {'maximumCases': 250, 'maximumSeconds': 180, 'minimumExecutableLineCoverage': 75},
        'regression': {'maximumCases': 10000, 'maximumSeconds': 1200, 'minimumExecutableLineCoverage': 75},
    }
    if policy.get('sourceScope') != SCOPE or policy.get('profiles') != expected:
        raise ValueError('policy differs from bound source scope or resource/coverage limits')
    if policy.get('suiteQueue') != SUITE_QUEUE:
        raise ValueError('policy differs from the complete bound six-suite queue')


def digest(path):
    hasher = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def load(path):
    path = Path(path)
    if path.stat().st_size > 128 * 1024 * 1024:
        raise ValueError('JSON input exceeds 128 MiB ceiling: ' + str(path))
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    with open(path, 'x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def file_path(value):
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ValueError('prepared paths must be absolute')
    path = Path(value).resolve(strict=True)
    if not path.is_file():
        raise ValueError('prepared file absent: ' + str(path))
    return path


def source_identity(root):
    result = {}
    for relative in SCOPE:
        path = (root / relative).resolve(strict=True)
        if not path.is_file() or not path.is_relative_to(root):
            raise ValueError('scoped production file absent/escaped: ' + relative)
        result[relative] = digest(path)
    return result


def frozen_files(identity, expected_paths, label):
    """Verify exact preparation-time hashes, never adopt current files as baseline."""
    if not isinstance(identity, dict):
        raise ValueError(label + ' identity must be a hash map')
    expected = {str(path.resolve(strict=True)) for path in expected_paths}
    if set(identity) != expected:
        raise ValueError(label + ' identity has missing or extra paths')
    for path, expected_hash in identity.items():
        if (not isinstance(expected_hash, str)
                or not re.fullmatch(r'[0-9a-f]{64}', expected_hash)
                or digest(path) != expected_hash):
            raise ValueError(label + ' changed since preparation: ' + path)


def copy_identity(root):
    """Return every regular file; reject links so the tree cannot escape its root."""
    result = {}
    for path in root.rglob('*'):
        if path.is_symlink() or path.is_junction():
            raise ValueError('test copy contains a link/junction: ' + str(path))
        if path.is_dir():
            continue
        if not path.is_file() or not path.resolve(strict=True).is_relative_to(root):
            raise ValueError('test copy contains a nonregular/escaped file: ' + str(path))
        result[str(path.resolve(strict=True))] = digest(path)
    return result


def legacy_queue(root, policy):
    path = root / policy['regressionQueue']['inventory']
    tree = ast.parse(path.read_text(encoding='utf-8'))
    lists = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in policy['regressionQueue']['lists']:
                    value = ast.literal_eval(node.value)
                    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                        raise ValueError('malformed retained legacy QA queue')
                    lists[target.id] = value
    if set(lists) != set(policy['regressionQueue']['lists']):
        raise ValueError('legacy QA suite inventory could not be retained completely')
    return {**policy['regressionQueue'], 'sha256': digest(path),
            'queues': lists, 'suiteCount': sum(map(len, lists.values()))}


def initial_identity(initial, source_root, copy_root, expected):
    envelope = load(initial)
    if Path(envelope.get('sourceRoot', '')).resolve() != source_root:
        raise ValueError('JS initial source root mismatch')
    if Path(envelope.get('copyRoot', '')).resolve() != copy_root:
        raise ValueError('JS initial test copy mismatch')
    actual = {}
    identities = []
    for item in envelope.get('files', []):
        relative = item['relativePath']
        if relative in actual or relative not in expected:
            raise ValueError('JS initial contains duplicate/extra production scope')
        original = (source_root / relative).resolve(strict=True)
        instrumented = (copy_root / relative).resolve(strict=True)
        if not instrumented.is_relative_to(copy_root):
            raise ValueError('instrumented file escaped test copy')
        if Path(item['sourceId']).resolve() != original or item['sourceHash'] != digest(original):
            raise ValueError('JS initial source hash mismatch: ' + relative)
        if item['instrumentedHash'] != digest(instrumented):
            raise ValueError('instrumented source hash mismatch: ' + relative)
        actual[relative] = item['sourceHash']
        identities.append(instrumented)
    if set(actual) != set(expected):
        raise ValueError('JS initial does not cover every scoped JS file')
    return identities


class Session:
    def __init__(self, prepared, policy, profile, out, deadline):
        self.prepared, self.policy, self.profile = prepared, policy, profile
        self.out, self.deadline = out, deadline
        self.records = []
        self.env = dict(os.environ)

    def check_time(self):
        if time.monotonic() >= self.deadline:
            raise TimeoutError('whole-run deadline exhausted')

    def run(self, label, argv, cwd=None, extra_env=None):
        self.check_time()
        remaining = self.deadline - time.monotonic() - 5
        if remaining <= 0:
            raise TimeoutError('no command allowance remains after cleanup reserve')
        env = {**self.env, **(extra_env or {})}
        path = self.out / f'{len(self.records):02d}-{label}.log'
        result = run_bounded(argv, cwd or self.copy_root, env, path, remaining)
        record = {'stage': label, 'command': list(map(str, argv)), 'cwd': str(cwd or self.copy_root),
                  'log': str(path), 'logSha256': digest(path), **result}
        self.records.append(record)
        self.check_time()
        if result['exitCode'] != 0 or result['timedOut'] or not result['descendantsStopped']:
            raise RuntimeError('bounded stage failed: ' + label)
        return path.read_text(encoding='utf-8', errors='replace')

    def prepare(self):
        p = self.prepared
        self.source_root = Path(p['sourceRoot']).resolve(strict=True)
        self.copy_root = Path(p['testCopyRoot']).resolve(strict=True)
        if self.source_root != ROOT:
            raise ValueError('prepared source root is not this qualification checkout')
        if not self.source_root.is_dir() or not self.copy_root.is_dir() or self.source_root == self.copy_root:
            raise ValueError('requires distinct existing production and test copy directories')
        self.paths = {key: file_path(p[key]) for key in (
            'python', 'node', 'rustTestBinary', 'nativeBinary', 'llvmProfdata', 'llvmCov',
            'jsInitial', 'browserExecutable')}
        if not self.paths['jsInitial'].is_relative_to(self.copy_root):
            raise ValueError('JS initial map must be part of the frozen test copy')
        self.env.update({'SOV_SOURCE_ROOT': str(self.source_root),
                         'SOV_NATIVE_BINARY': str(self.paths['nativeBinary']),
                         'SOV_NODE_BINARY': str(self.paths['node']),
                         'CHROMIUM_PATH': str(self.paths['browserExecutable']),
                         'PYTHONUNBUFFERED': '1', 'PYTHONDONTWRITEBYTECODE': '1',
                         'NO_COLOR': '1'})
        if p.get('buildRevision'):
            self.env['SOV_BUILD_REVISION'] = p['buildRevision']
        self.before = source_identity(self.source_root)
        if p['sourceIdentity'] != self.before:
            raise ValueError('prepared source assertion differs from complete current source identity')
        if not isinstance(p.get('toolVersions'), dict) or not p['toolVersions']:
            raise ValueError('prepared toolVersions identity is missing')
        if not isinstance(p.get('dependencyFiles'), list) or not p['dependencyFiles']:
            raise ValueError('prepared dependencyFiles identity is missing')
        dependencies = [file_path(path) for path in p['dependencyFiles']]
        if len(set(dependencies)) != len(dependencies):
            raise ValueError('prepared dependencyFiles contains duplicates')
        if {str(path) for path in dependencies} != set(dependency_inputs()):
            raise ValueError('prepared dependencies differ from complete canonical build/harness inventory')
        frozen_files(p.get('dependencyIdentity'), dependencies, 'dependency')
        binaries = [self.paths[key] for key in ('nativeBinary', 'rustTestBinary')]
        frozen_files(p.get('binaryIdentity'), binaries, 'binary')
        artifacts = [self.paths[key] for key in (
            'python', 'node', 'llvmProfdata', 'llvmCov', 'browserExecutable',
            'nativeBinary', 'rustTestBinary')]
        frozen_files(p.get('artifactIdentity'), artifacts, 'artifact')
        self.copy_before = copy_identity(self.copy_root)
        if p.get('testCopyIdentity') != self.copy_before:
            raise ValueError('complete test copy differs from preparation identity')
        self.legacy = legacy_queue(self.source_root, self.policy)
        js_scope = [name for name in SCOPE if name.endswith(('.js', '.mjs'))]
        instrumented = initial_identity(self.paths['jsInitial'], self.source_root,
                                        self.copy_root, js_scope)
        inputs = list(self.paths.values()) + instrumented + [
            ROOT / 'scripts/qualify_local.py', ROOT / 'scripts/bounded_process.py',
            ROOT / 'scripts/llvm_tools.py', ROOT / 'test-budget.json',
            self.source_root / 'scripts/js_coverage.mjs', self.source_root / 'scripts/qa.py',
            self.source_root / 'package.json', self.source_root / 'package-lock.json',
            self.source_root / 'desktop/src-tauri/Cargo.toml',
            self.source_root / 'desktop/src-tauri/Cargo.lock',
            self.copy_root / 'index.html', self.copy_root / 'tests/browser_runtime.py',
        ]
        inputs += dependencies
        for suite in self.policy['suiteQueue']:
            if 'driver' in suite:
                inputs += [self.copy_root / suite['driver']]
        # Runtime dependencies/fixtures are inputs, not added to production denominator.
        for root in (self.source_root, self.copy_root):
            for pattern in ('src/*.js', 'mcp/*.mjs', 'styles/*.css', 'data/*.json',
                            'examples/**/*.sov', 'docs/local-core/*.md'):
                inputs += list(root.glob(pattern))
            for relative in ('index.source.html', 'API.md', 'DATA-FORMATS.md',
                             'STATE-SPACE.md', 'MODULES.md'):
                if (root / relative).is_file():
                    inputs.append(root / relative)
        self.inputs = {}
        for path in inputs:
            self.check_time()
            path = path.resolve(strict=True)
            if not path.is_file():
                raise ValueError('required harness/dependency input absent: ' + str(path))
            self.inputs[str(path)] = digest(path)
        self.js_dir = self.out / 'js-snapshots'
        self.python_dir = self.out / 'python-coverage'
        self.rust_dir = self.out / 'rust-coverage'
        for directory in (self.js_dir, self.python_dir, self.rust_dir):
            directory.mkdir()
        self.env['COVERAGE_FILE'] = str(self.python_dir / '.coverage')
        self.env['LLVM_PROFILE_FILE'] = str(self.rust_dir / '%m-%p.profraw')
        self.versions = {}
        for key in ('python', 'node', 'llvmProfdata', 'llvmCov'):
            self.versions[key] = self.run('version-' + key, [str(self.paths[key]), '--version']).strip()
        code = ('import importlib.metadata as m,json;'
                'print(json.dumps(sorted((d.metadata.get("Name",""),d.version) for d in m.distributions())))')
        self.python_dependencies = json.loads(self.run('python-dependencies',
            [str(self.paths['python']), '-c', code]))

    def collect(self):
        collected = []
        seen = set()
        for suite in self.policy['suiteQueue']:
            runner = suite['runner']
            if runner == 'rustTestBinary':
                command = [str(self.paths['rustTestBinary']), '--list']
                output = self.run('collect-' + suite['id'], command)
                cases = ['rust::' + match.group(1) for match in
                         re.finditer(r'^(.+): test$', output, re.MULTILINE)]
                counts = re.search(r'^(\d+) tests?, (\d+) benchmarks?$', output, re.MULTILINE)
                if not counts or int(counts.group(1)) != len(cases) or int(counts.group(2)):
                    raise ValueError('Rust test collection summary mismatch or benchmarks present')
            else:
                interpreter = self.paths['node' if runner == 'node' else 'python']
                command = [str(interpreter), str(self.copy_root / suite['driver']), '--collect']
                envelope = json.loads(self.run('collect-' + suite['id'], command))
                if isinstance(envelope, list):
                    cases = envelope
                elif (isinstance(envelope, dict) and isinstance(envelope.get('cases'), list)
                      and type(envelope.get('count')) is int
                      and envelope['count'] == len(envelope['cases'])):
                    cases = envelope['cases']
                else:
                    raise ValueError('driver collection must be a case array or consistent cases/count envelope')
            if (not cases or any(not isinstance(case, str) or not case or '\n' in case
                                 or '\r' in case for case in cases)
                    or len(set(cases)) != len(cases) or seen.intersection(cases)):
                raise ValueError('empty/malformed/duplicate collected case IDs')
            seen.update(cases)
            collected.append({**suite, 'cases': cases, 'count': len(cases),
                              'collectionCommand': command})
            if len(seen) > self.profile['maximumCases']:
                raise ValueError('collected cases exceed profile ceiling before execution')
        write(self.out / 'collection.json', {'cases': len(seen), 'queue': collected})
        self.collected = collected
        return len(seen)

    def execute(self):
        self.results = [{'suite': suite['id'], 'status': 'UNEXECUTED', 'passed': [],
                         'failed': [], 'skipped': [], 'missingIds': list(suite['cases']),
                         'extraIds': [], 'duplicateIds': [], 'executedIds': [],
                         'caseResults': [{'id': case, 'status': 'UNREPORTED'} for case in suite['cases']]}
                        for suite in self.collected]

        def retain_aborted(record, suite, result, error):
            result['failure'] = {'type': type(error).__name__, 'message': str(error)}
            if record is None or record.get('stage') != 'run-' + suite['id']:
                return
            result.update(log=record['log'], logSha256=record['logSha256'], exitCode=record['exitCode'])
            output = Path(record['log']).read_text(encoding='utf-8', errors='replace')
            if suite['runner'] == 'rustTestBinary':
                passed = ['rust::' + name for name in re.findall(r'^test (.+?) \.\.\. ok$', output, re.MULTILINE)]
                failed = ['rust::' + name for name in re.findall(r'^test (.+?) \.\.\. FAILED$', output, re.MULTILINE)]
                skipped = ['rust::' + name for name in re.findall(r'^test (.+?) \.\.\. ignored(?:,.*)?$', output, re.MULTILINE)]
            else:
                passed = re.findall(r'^CASE PASS ([^\r\n]+)$', output, re.MULTILINE)
                failed = [marker.partition(': ')[0] for marker in re.findall(r'^CASE FAIL ([^\r\n]+)$', output, re.MULTILINE)]
                skipped = [marker.partition(': ')[0] for marker in re.findall(r'^CASE SKIP ([^\r\n]+)$', output, re.MULTILINE)]
            markers, collected = Counter([*passed, *failed, *skipped]), set(suite['cases'])
            result.update(passed=passed, failed=failed, skipped=skipped,
                          missingIds=sorted(collected - set(markers)), extraIds=sorted(set(markers) - collected),
                          duplicateIds=sorted(case for case, count in markers.items() if count != 1),
                          executedIds=sorted(collected.intersection([*passed, *failed])),
                          caseResults=[{'id': case, 'status': 'UNREPORTED' if case not in markers else
                                        'AMBIGUOUS' if markers[case] != 1 else 'FAIL' if case in failed else
                                        'SKIP' if case in skipped else 'PASS'} for case in suite['cases']])

        def require_clean_native_receipt(output, suite, result):
            # Process containment alone does not establish that the driver
            # removed its descriptors or met its own shorter queue deadline.
            summaries = []
            for line in output.splitlines():
                try:
                    value = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if isinstance(value, dict) and value.get('suite') == 'native-mcp':
                    summaries.append(value)
            if len(summaries) != 1:
                raise ValueError('native continuation requires one retained receipt summary')
            summary = summaries[0]
            raw_path = summary.get('evidence')
            if not isinstance(raw_path, str) or not Path(raw_path).is_absolute():
                raise ValueError('native receipt path must be absolute')
            owned = self.out.resolve(strict=True)
            lexical = Path(os.path.abspath(raw_path))
            path = lexical.resolve(strict=True)
            if (not lexical.is_relative_to(owned) or not path.is_relative_to(owned)
                    or lexical != path or path.name != 'native-evidence.json'
                    or path.parent.parent != owned
                    or not re.fullmatch(r'native-runtime-[0-9a-f]{32}', path.parent.name)
                    or not path.is_file()):
                raise ValueError('native receipt escapes or differs from its owned output')
            candidates = list(owned.glob('native-runtime-*/native-evidence.json'))
            if len(candidates) != 1 or candidates[0].resolve(strict=True) != path:
                raise ValueError('native retained receipt is missing or ambiguous')
            if path.stat().st_size > 1024 * 1024:
                raise ValueError('native receipt exceeds 1 MiB ceiling')
            receipt = load(path)
            result.update(nativeEvidencePath=str(path), nativeEvidenceSha256=digest(path))
            revision = self.prepared.get('buildRevision')
            if (not isinstance(receipt, dict) or receipt.get('suite') != suite['id']
                    or not isinstance(revision, str) or not revision or revision == 'unversioned'
                    or receipt.get('buildRevision') != revision
                    or type(receipt.get('collected')) is not int
                    or receipt['collected'] != len(suite['cases'])
                    or file_path(receipt.get('nativeBinary')) != self.paths['nativeBinary']
                    or receipt.get('nativeBinarySha256') !=
                        self.prepared['binaryIdentity'][str(self.paths['nativeBinary'])]
                    or file_path(receipt.get('nodeBinary')) != self.paths['node']
                    or receipt.get('nodeBinarySha256') !=
                        self.prepared['artifactIdentity'][str(self.paths['node'])]
                    or receipt.get('sdkConsumerSha256') != self.prepared['dependencyIdentity'][
                        str((self.source_root / 'tests/sdk_consumer.mjs').resolve(strict=True))]
                    or summary.get('passed') is not False):
                raise ValueError('native receipt suite/build/binary identity is inconsistent')
            elapsed = receipt.get('elapsedSeconds')
            effect_elapsed = receipt.get('effectElapsedSeconds')
            if (type(elapsed) not in (int, float) or not 0 <= elapsed <= 60
                    or type(effect_elapsed) not in (int, float) or not 0 <= effect_elapsed < 55
                    or effect_elapsed > elapsed or receipt.get('effectDeadlineReached') is not False
                    or summary.get('elapsedSeconds') != elapsed
                    or receipt.get('cleanupFailures') != []
                    or receipt.get('staleOwnedDescriptors') != []
                    or 'cleanupFailure' in receipt or 'deadlineFailure' in receipt
                    or 'effectDeadlineFailure' in receipt):
                raise ValueError('native receipt has missing/failed cleanup or deadline evidence')
            reported = receipt.get('results')
            expected = Counter((case, 'PASS') for case in result['passed'])
            expected.update((case, 'FAIL') for case in result['failed'])
            expected.update((case, 'SKIP') for case in result['skipped'])
            if (not isinstance(reported, list)
                    or any(not isinstance(item, dict) or not isinstance(item.get('id'), str)
                           or item.get('status') not in ('PASS', 'FAIL', 'SKIP') for item in reported)
                    or Counter((item['id'], item['status']) for item in reported) != expected):
                raise ValueError('native receipt case results differ from retained log')
            result['nativeEvidenceDisposition'] = 'clean-contained-case-failure'

        for suite, result in zip(self.collected, self.results):
            self.check_time()
            runner = suite['runner']
            if runner == 'rustTestBinary':
                command = [str(self.paths['rustTestBinary']), '--test-threads=1',
                           '--nocapture', '--color', 'never']
            else:
                interpreter = self.paths['node' if runner == 'node' else 'python']
                prefix = [str(interpreter)]
                if runner == 'pythonCoverage':
                    prefix += ['-m', 'coverage', 'run', '--parallel-mode',
                               '--source=' + str(self.source_root)]
                command = [*prefix, str(self.copy_root / suite['driver']),
                           '--coverage-dir', str(self.js_dir)]
            label = 'run-' + suite['id']
            result.update(status='ABORTED', command=command)
            record_count = len(self.records)
            exit_failure = None
            try:
                output = self.run(label, command)
            except RuntimeError as error:
                # Continue only a completed, contained stage's nonzero exit.
                # A stale record, launch failure, timeout, failed cleanup or
                # whole-run deadline cannot authorize another suite.
                record = self.records[-1] if len(self.records) == record_count + 1 else None
                if (str(error) != 'bounded stage failed: ' + label or record is None
                        or record['stage'] != label or type(record.get('exitCode')) is not int
                        or record['exitCode'] == 0 or record.get('timedOut') is not False
                        or record.get('descendantsStopped') is not True):
                    retain_aborted(record, suite, result, error)
                    raise
                retain_aborted(record, suite, result, error)
                self.check_time()
                output = Path(record['log']).read_text(encoding='utf-8', errors='replace')
                if suite['id'] == 'native-mcp':
                    try:
                        require_clean_native_receipt(output, suite, result)
                    except Exception as receipt_error:
                        result['nativeEvidenceDisposition'] = 'refused'
                        result['failure'] = {'type': type(receipt_error).__name__,
                                             'message': str(receipt_error)}
                        raise RuntimeError('native continuation refused: ' + str(receipt_error)) from receipt_error
                    self.check_time()
                exit_failure = {'type': 'NonzeroExit', 'exitCode': record['exitCode'],
                                'message': str(error)}
            except Exception as error:
                record = self.records[-1] if len(self.records) == record_count + 1 else None
                retain_aborted(record, suite, result, error)
                raise
            stage = self.records[-1]
            result.update(log=stage['log'], logSha256=stage['logSha256'], exitCode=stage['exitCode'])
            failures = []
            if exit_failure:
                failures.append(exit_failure)
            if runner == 'rustTestBinary':
                passed = ['rust::' + match.group(1) for match in
                          re.finditer(r'^test (.+?) \.\.\. ok$', output, re.MULTILINE)]
                failed = ['rust::' + match.group(1) for match in
                          re.finditer(r'^test (.+?) \.\.\. FAILED$', output, re.MULTILINE)]
                skipped = ['rust::' + match.group(1) for match in
                           re.finditer(r'^test (.+?) \.\.\. ignored(?:,.*)?$', output, re.MULTILINE)]
                summary = re.search(r'test result: (?:ok|FAILED)\. (\d+) passed; (\d+) failed; '
                                    r'(\d+) ignored; (\d+) measured; (\d+) filtered out', output)
                counts = list(map(int, summary.groups())) if summary else None
                result['rustSummary'] = counts
                result['rustSummaryStatus'] = summary.group(0).split('.')[0] if summary else None
                if counts != [len(passed), len(failed), len(skipped), 0, 0]:
                    failures.append({'type': 'RustSummaryMismatch',
                                     'message': 'Rust result summary absent/inconsistent or measured/filtered cases'})
                if summary and not summary.group(0).startswith('test result: ok.'):
                    failures.append({'type': 'RustFailedSummary', 'message': 'Rust reported FAILED'})
            else:
                passed = re.findall(r'^CASE PASS ([^\r\n]+)$', output, re.MULTILINE)
                failed = [marker.partition(': ')[0] for marker in
                          re.findall(r'^CASE FAIL ([^\r\n]+)$', output, re.MULTILINE)]
                skipped = [marker.partition(': ')[0] for marker in
                           re.findall(r'^CASE SKIP ([^\r\n]+)$', output, re.MULTILINE)]
                if len(re.findall(r'^CASE (?:PASS|FAIL|SKIP)\b', output, re.MULTILINE)) != len(passed) + len(failed) + len(skipped):
                    failures.append({'type': 'MalformedCaseMarker', 'message': 'Case status line has no readable ID'})
            markers = Counter([*passed, *failed, *skipped])
            collected = set(suite['cases'])
            missing = sorted(collected - set(markers))
            extra = sorted(set(markers) - collected)
            duplicates = sorted(case for case, count in markers.items() if count != 1)
            case_results = []
            for case in suite['cases']:
                status = ('UNREPORTED' if case not in markers else
                          'AMBIGUOUS' if markers[case] != 1 else
                          'FAIL' if case in failed else 'SKIP' if case in skipped else 'PASS')
                case_results.append({'id': case, 'status': status})
            if failed or skipped:
                failures.append({'type': 'CaseFailureOrSkip', 'failedIds': failed, 'skippedIds': skipped})
            if Counter(passed) != Counter(suite['cases']):
                failures.append({'type': 'CaseCountMismatch', 'missingIds': missing,
                                 'extraIds': extra, 'duplicateIds': duplicates,
                                 'message': 'PASS marker counts differ from complete collected cases'})
            if extra or duplicates:
                failures.append({'type': 'InvalidCaseMarkers', 'extraIds': extra, 'duplicateIds': duplicates})
            result.update(status='FAIL' if failures else 'PASS', passed=passed, failed=failed,
                          skipped=skipped, missingIds=missing, extraIds=extra,
                          duplicateIds=duplicates, caseResults=case_results,
                          executedIds=sorted(collected.intersection([*passed, *failed])),
                          failures=failures)
            self.check_time()
        return all(result['status'] == 'PASS' for result in self.results)

    def coverage(self):
        js_output = self.out / 'js-coverage.json'
        self.run('merge-js', [str(self.paths['node']),
                 str(self.source_root / 'scripts/js_coverage.mjs'), 'merge',
                 '--initial', str(self.paths['jsInitial']), '--coverage-dir', str(self.js_dir),
                 '--out', str(js_output)], cwd=self.source_root)
        js = load(js_output)
        js_files = js['files']
        if {file['file'] for file in js_files} != {name for name in SCOPE if name.endswith(('.js', '.mjs'))}:
            raise ValueError('merged JS coverage scope mismatch')
        # Interpreter is the prepared Python, so use it for the API analysis too.
        python_output = self.out / 'python-coverage.json'
        analyzer = ('import coverage,json,pathlib;'
            'root=pathlib.Path(__import__("os").environ["SOV_SOURCE_ROOT"]);'
            'c=coverage.Coverage(data_file=__import__("os").environ["COVERAGE_FILE"]);'
            'c.combine(data_paths=[' + repr(str(self.python_dir)) + '],strict=True,keep=True);c.load();'
            'a=c.analysis2(str(root/"build.py"));'
            'excluded=a[2];'
            'result={"file":"build.py","executableLines":a[1],'
            '"hitLines":sorted(set(a[1])-set(a[3])),"excludedLines":excluded,'
            '"measurement":"coverage.py compiled executable-line analysis"};'
            'pathlib.Path(' + repr(str(python_output)) + ').write_text(json.dumps(result),encoding="utf-8")')
        self.run('merge-python', [str(self.paths['python']), '-c', analyzer])
        python_file = load(python_output)
        if python_file['excludedLines']:
            raise ValueError('Python coverage excluded production lines')
        raw = sorted(self.rust_dir.glob('*.profraw'))
        if not raw:
            raise ValueError('no Rust raw coverage retained')
        profile_path = self.rust_dir / 'merged.profdata'
        self.run('merge-rust', [str(self.paths['llvmProfdata']), 'merge', '-sparse',
                 *map(str, raw), '-o', str(profile_path)])
        rust_scope = [str(self.source_root / name) for name in SCOPE if name.endswith('.rs')]
        production_log = self.run('export-rust-production', [str(self.paths['llvmCov']), 'export',
                         str(self.paths['nativeBinary']), '--instr-profile', str(profile_path), *rust_scope])
        production = normalize_export(json.loads(production_log), rust_scope)
        write(self.out / 'rust-production-coverage.json', production)
        export_log = self.run('export-rust-with-unit', [str(self.paths['llvmCov']), 'export',
                     str(self.paths['nativeBinary']), '--object', str(self.paths['rustTestBinary']),
                     '--instr-profile', str(profile_path), *rust_scope])
        export = json.loads(export_log)
        combined = normalize_export(export, rust_scope)
        write(self.out / 'rust-unit-and-production-coverage.json', combined)
        combined_files = {file['file']: file for file in combined['files']}
        rust = production
        for file in rust['files']:
            measured = combined_files[file['file']]
            if measured['sourceHash'] != file['sourceHash']:
                raise ValueError('native/unit Rust source identity mismatch')
            production_lines = set(file['executableLines'])
            if not production_lines.issubset(measured['executableLines']):
                raise ValueError('combined Rust map is missing native production lines')
            file['hitLines'] = sorted(production_lines.intersection(measured['hitLines']))
            file['testOnlyMappedLines'] = sorted(set(measured['executableLines']) - production_lines)
        rust['hitLineCount'] = sum(len(file['hitLines']) for file in rust['files'])
        rust['coveragePercent'] = 100 * rust['hitLineCount'] / rust['executableLineCount']
        rust['denominatorBasis'] = 'native production binary map; unit hits intersected with production lines'
        write(self.out / 'rust-coverage.json', rust)
        all_files = []
        for record in [*js_files, python_file, *rust['files']]:
            self.check_time()
            name = record['file']
            if Path(name).is_absolute():
                name = Path(name).resolve().relative_to(self.source_root).as_posix()
            if name not in SCOPE:
                raise ValueError('coverage record outside exact product scope')
            lines, hits = record['executableLines'], record['hitLines']
            if (not isinstance(lines, list) or not isinstance(hits, list)
                    or any(type(line) is not int or line < 1 for line in [*lines, *hits])
                    or len(set(lines)) != len(lines) or len(set(hits)) != len(hits)
                    or not set(hits).issubset(lines)):
                raise ValueError('malformed executable-line coverage')
            measured_hash = record.get('sourceHash', self.before[name])
            if measured_hash != self.before[name]:
                raise ValueError('coverage source identity mismatch')
            all_files.append({'file': name, 'sourceHash': measured_hash,
                              'executableLines': lines, 'hitLines': hits,
                              'coveragePercent': 100 * len(hits) / len(lines) if lines else None})
        if len(all_files) != len(SCOPE) or {file['file'] for file in all_files} != set(SCOPE):
            raise ValueError('one or more complete scoped files missing from coverage denominator')
        total = sum(len(file['executableLines']) for file in all_files)
        covered = sum(len(file['hitLines']) for file in all_files)
        if not total:
            raise ValueError('no executable production source mapped')
        result = {'files': all_files, 'totalExecutableLines': total,
                  'totalHitLines': covered, 'coveragePercent': 100 * covered / total,
                  'minimumExecutableLineCoverage': self.profile['minimumExecutableLineCoverage']}
        write(self.out / 'coverage.json', result)
        return result

    def fresh(self):
        after = source_identity(self.source_root)
        if after != self.before:
            raise ValueError('production source changed during qualification')
        if set(dependency_inputs()) != set(self.prepared['dependencyFiles']):
            raise ValueError('dependency inventory changed during qualification')
        if copy_identity(self.copy_root) != self.copy_before:
            raise ValueError('complete test copy changed during qualification')
        for path, expected in self.inputs.items():
            self.check_time()
            if digest(path) != expected:
                raise ValueError('dependency/tool/harness/prepared artifact changed: ' + path)
        return after


def worker(args):
    if not supervised_parent(os.environ.get('SOV_QUALIFY_PARENT')):
        raise RuntimeError('qualification worker requires supervising parent')
    policy = load(ROOT / 'test-budget.json')
    validate_policy(policy)
    prepared = load(args.prepared)
    out = Path(args.out).resolve(strict=True)
    started = time.monotonic()
    session = Session(prepared, policy, policy['profiles'][args.profile], out, args.deadline)
    evidence = {'policy': policy, 'profile': args.profile, 'passed': False,
                'sourceScope': SCOPE, 'preparedPath': str(Path(args.prepared).resolve()),
                'preparedSha256': digest(args.prepared), 'records': session.records,
                'reportingCeiling': 'measured qualification; independent acceptance remains required'}
    try:
        session.prepare()
        evidence.update({'sourceIdentityBefore': session.before,
                         'inputIdentity': session.inputs, 'toolVersions': session.versions,
                         'preparedToolVersions': prepared['toolVersions'],
                         'pythonDependencies': session.python_dependencies,
                         'legacyRegressionQueue': session.legacy,
                         'environment': {'platform': platform.platform(), 'python': sys.version,
                             'CHROMIUM_PATH': session.env['CHROMIUM_PATH'],
                             'LLVM_PROFILE_FILE': session.env['LLVM_PROFILE_FILE'],
                             'COVERAGE_FILE': session.env['COVERAGE_FILE']}})
        if args.profile == 'regression':
            evidence['unmetChecks'] = ['legacy-regression-case-adapters']
            raise RuntimeError('required legacy regression queue has no reliable case adapters; retained without execution')
        evidence['collectedCases'] = session.collect()
        suites_passed = session.execute()
        evidence['results'] = session.results
        evidence['executedCases'] = sum(len(result['executedIds']) for result in session.results)
        evidence['passedCases'] = sum(case['status'] == 'PASS' for result in session.results for case in result['caseResults'])
        evidence['coverage'] = session.coverage()
        evidence['sourceIdentityAfter'] = session.fresh()
        session.check_time()
        if evidence['coverage']['coveragePercent'] < session.profile['minimumExecutableLineCoverage']:
            raise RuntimeError('complete scoped executable-line coverage below required floor')
        if not suites_passed:
            raise RuntimeError('one or more suites failed, skipped cases or reported incomplete/inconsistent case evidence')
        evidence['passed'] = True
    except Exception as error:
        evidence['failure'] = {'type': type(error).__name__, 'message': str(error)}
        try:
            if hasattr(session, 'before'):
                evidence['sourceIdentityAfter'] = source_identity(session.source_root)
        except Exception as freshness_error:
            evidence['freshnessFailure'] = str(freshness_error)
    finally:
        if hasattr(session, 'results'):
            evidence['results'] = session.results
            evidence['executedCases'] = sum(len(result['executedIds']) for result in session.results)
            evidence['passedCases'] = sum(case['status'] == 'PASS' for result in session.results for case in result['caseResults'])
            evidence['caseCountBasis'] = 'distinct collected IDs with explicit PASS/FAIL markers; skips and unreported IDs are not counted as executed'
            evidence['failedSuites'] = [result['suite'] for result in session.results if result['status'] != 'PASS']
        evidence['workerElapsedSeconds'] = time.monotonic() - started
        write(out / 'evidence.json', evidence)
    print(json.dumps({'evidence': str(out / 'evidence.json'), 'passed': evidence['passed'],
                      'failure': evidence.get('failure')}))
    return 0 if evidence['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=['routine', 'regression'], required=True)
    parser.add_argument('--prepared', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--_worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--deadline', type=float, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args._worker:
        return worker(args)
    started = time.monotonic()
    policy = load(ROOT / 'test-budget.json')
    validate_policy(policy)
    profile = policy['profiles'][args.profile]
    prepared_path = file_path(str(Path(args.prepared).absolute()))
    prepared = load(prepared_path)
    initial_prepared_hash = digest(prepared_path)
    initial_policy_hash = digest(ROOT / 'test-budget.json')
    python = file_path(prepared['python'])
    out = Path(args.out).absolute()
    if out.exists():
        raise ValueError('out must be a new evidence directory')
    out.mkdir(parents=True)
    deadline = started + profile['maximumSeconds'] - 5
    command = [str(python), str(Path(__file__).resolve()), '--_worker',
               '--profile', args.profile, '--prepared', str(prepared_path),
               '--out', str(out), '--deadline', str(deadline)]
    env = dict(os.environ)
    env['SOV_QUALIFY_PARENT'] = str(os.getpid())
    result = run_bounded(command, ROOT, env, out / 'supervisor.log',
                         max(0.001, deadline - time.monotonic()))
    elapsed = time.monotonic() - started
    receipt = {'command': command, 'policyVersion': policy['version'],
               'policySha256': initial_policy_hash, 'profile': args.profile,
               'preparedSha256': initial_prepared_hash, 'elapsedSeconds': elapsed, **result}
    receipt['elapsedSeconds'] = elapsed
    evidence_path = out / 'evidence.json'
    evidence = load(evidence_path) if evidence_path.exists() else {}
    identities_fresh = bool(evidence.get('sourceIdentityAfter')
        and source_identity(Path(prepared['sourceRoot']).resolve(strict=True))
        == evidence['sourceIdentityAfter'])
    prepared_fresh = digest(prepared_path) == initial_prepared_hash
    policy_fresh = digest(ROOT / 'test-budget.json') == initial_policy_hash
    # Charge evidence loading and final identity checks before deciding the result.
    elapsed = time.monotonic() - started
    receipt['elapsedSeconds'] = elapsed
    receipt['passed'] = bool(evidence.get('passed') and result['exitCode'] == 0
        and not result['timedOut'] and result['descendantsStopped']
        and elapsed <= profile['maximumSeconds']
        and identities_fresh and prepared_fresh and policy_fresh)
    write(out / 'supervision.json', receipt)
    elapsed = time.monotonic() - started
    receipt['elapsedSeconds'] = elapsed
    if elapsed > profile['maximumSeconds']:
        receipt['passed'] = False
        receipt['failure'] = 'final receipt exceeded whole-run elapsed ceiling'
    # Update the retained receipt with the elapsed time including its first write.
    with open(out / 'supervision.json', 'w', encoding='utf-8', newline='\n') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'evidence': str(evidence_path), 'supervision': str(out / 'supervision.json'),
                      'passed': receipt['passed'], 'elapsedSeconds': elapsed}))
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(json.dumps({'error': str(error), 'passed': False}))
        raise SystemExit(1)
