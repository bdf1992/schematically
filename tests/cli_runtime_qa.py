"""Real granted Node and Python execution through the desktop MCP, supervised only.

The test owns its fixture, host registry, grants, WebView profile and markers.
The runtime owns execution containment; this driver verifies its real effects.
No filesystem/network sandbox is claimed. Collection performs no effects.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

CASE_IDS = tuple('cli/' + name for name in (
    'provider-list', 'missing-grant', 'expired-grant', 'stale-document',
    'stale-code', 'changed-executable', 'real-node-output', 'request-replay',
    'changed-replay-refused', 'consumed-grant', 'timeout-before-effects', 'timeout-descendants',
    'cancel-descendants', 'output-overflow', 'durable-results-reopen',
    'no-automatic-document-mutation', 'app-close-descendants',
    'corrupt-output-recovery-refused', 'terminal-recording-failure-held',
    'python-output', 'python-language-refused',
))


def sha(value):
    return hashlib.sha256(value).hexdigest()


def gone(pid):
    """Read only this suite's observed child PID; permission failure is not proof."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return ctypes.get_last_error() == 87  # ERROR_INVALID_PARAMETER: no such PID.
    try:
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise OSError(ctypes.get_last_error(), 'cannot inspect owned CLI child')
        return code.value != 259
    finally:
        kernel.CloseHandle(handle)


def execute(coverage_dir):
    # Import only after --collect has returned, before any native effects.
    from native_mcp_qa import NativeSuite, check

    class CliSuite(NativeSuite):
        def __init__(self, directory):
            super().__init__(directory)
            self.deadline = self.started + 25
            self.node = Path(self.node).resolve(strict=True)
            self.current = CASE_IDS[0]
            self.node_hash = sha(self.node.read_bytes())
            self.python = Path(sys.executable).resolve(strict=True)
            self.python_hash = sha(self.python.read_bytes())
            self.provider = {'id': 'node-cli', 'version': '1', 'language': 'javascript',
                'executable': str(self.node), 'executableSha256': self.node_hash,
                'limits': {'timeoutMs': 5000, 'maxOutputBytes': 4096,
                           'maxProcesses': 4, 'maxMemoryBytes': 536870912}}
            self.grants = []
            self.attempts = []
            self.markers = []
            self.preflight_marker = self.work / 'preflight-effect.json'
            self.document = json.loads(self.fixture.read_text(encoding='utf-8'))
            self.authored = self.document.get('document', self.document)
            self.document_id = self.authored['id']
            self.sources = {'success': 'let text="";for await(const part of process.stdin)text+=part;const value=JSON.parse(text);process.stdout.write(JSON.stringify({answer:value.value+1}));',
                            'python-output': 'import json,sys\nvalue=json.load(sys.stdin)\nprint(json.dumps({"answer":value["value"]+1},separators=(",",":")))\n',
                            'preflight': 'import fs from "node:fs";fs.writeFileSync(' + json.dumps(str(self.preflight_marker)) + ',"effect-ran");process.stdout.write("effect-ran");',
                            'overflow': 'process.stdout.write("x".repeat(16384));',
                            'record-failure': 'import fs from "node:fs";import path from "node:path";import {fileURLToPath} from "node:url";const receipt=path.join(path.dirname(fileURLToPath(import.meta.url)),"receipt.json");fs.unlinkSync(receipt);fs.mkdirSync(receipt);process.stdout.write("record-failure");'}
            for kind in ('timeout', 'cancel', 'shutdown'):
                # Python shares this fixture while retaining its declared language.
                marker = self.work / (kind + '-children.json')
                self.markers.append(marker)
                self.sources[kind] = ('import {spawn} from "node:child_process";import fs from "node:fs";'
                    'const child=spawn(process.execPath,["-e","setInterval(()=>{},1000)"],{stdio:"ignore"});'
                    'fs.writeFileSync(' + json.dumps(str(marker)) + ',JSON.stringify({parentPid:process.pid,childPid:child.pid}));'
                    'setInterval(()=>{},1000);')
            for kind, source in self.sources.items():
                language = 'python' if kind == 'python-output' else 'javascript'
                self.authored.setdefault('references', []).append({'id': 'cli-code-' + kind,
                    'kind': 'code', 'data': {'schema': 'schematically.code@1',
                    'language': language, 'source': source, 'sha256': sha(source.encode())}})
            self.fixture.write_text(json.dumps(self.document), encoding='utf-8')

        def timeout(self, maximum):
            left = min(maximum, self.deadline - time.monotonic())
            if left <= 0:
                raise TimeoutError('CLI queue exhausted its 25-second effects allowance')
            return left

        def passed(self, case_id):
            check(case_id in CASE_IDS and not any(r['id'] == case_id for r in self.results),
                  'invalid or duplicate CLI case ID')
            self.results.append({'id': case_id, 'status': 'PASS'})
            print('CASE PASS ' + case_id, flush=True)

        def case(self, name):
            self.current = 'cli/' + name

        def registry(self):
            value = {'schema': 'schematically.cli-host@1', 'providers': [self.provider],
                     'grants': self.grants}
            path = self.runtime_home / 'providers.json'
            temporary = path.with_suffix('.pending')
            temporary.write_text(json.dumps(value), encoding='utf-8')
            os.replace(temporary, path)

        def launch(self, path, report=None, profile=None):
            self.timeout(10)
            check(report is None, 'CLI suite does not launch smoke processes')
            environment = dict(os.environ)
            environment.update(WEBVIEW2_USER_DATA_FOLDER=str(self.webview_profile),
                               SOV_RUNTIME_DIR=str(self.runtime_home))
            debug_port = self.debug_environment(environment)
            log = tempfile.TemporaryFile(mode='w+b')
            try:
                process = subprocess.Popen([str(self.binary), str(path)], cwd=self.work,
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, env=environment)
            except BaseException:
                log.close()
                raise
            self.processes.append(process)
            self.debug_ports[process.pid] = debug_port
            self.process_logs.append((process, log))
            self.observations.append({'operation': 'launch-cli-desktop', 'pid': process.pid,
                'runtimeHome': str(self.runtime_home), 'webviewProfile': str(self.webview_profile)})
            return process

        def call(self, descriptor, name, arguments=None, refuse=False, reason=None):
            result = self.rpc(descriptor, 'tools/call', {'name': name, 'arguments': arguments or {}})
            if refuse:
                check(result.get('isError') is True, 'Runtime request unexpectedly admitted: ' + name)
                if reason:
                    check(reason in json.dumps(result), 'Runtime refused for an unrelated reason: ' + self.redact(json.dumps(result)))
                self.observations.append({'operation': 'refused', 'tool': name,
                                          'result': self.redact(json.dumps(result))})
                return result
            check(result.get('isError') is False, 'Runtime tool refused: ' + self.redact(json.dumps(result)))
            content = result.get('structuredContent')
            return content if content is not None else json.loads(result['content'][0]['text'])

        def info(self, descriptor):
            return self.call(descriptor, 'schematic.file.info')

        def request_args(self, descriptor, request_id, kind='success', grant_id=None, value=41, provider_id='node-cli'):
            info = self.info(descriptor)
            return {'requestId': request_id, 'providerId': provider_id, 'providerVersion': '1',
                'grantId': grant_id or ('grant-' + request_id), 'referenceId': 'cli-code-' + kind,
                'codeHash': sha(self.sources[kind].encode()), 'input': {'value': value},
                'documentId': info['documentId'], 'ifRevision': info['revision'],
                'stateToken': info['stateToken']}

        def grant(self, args, expired=False):
            self.grants.append({'id': args['grantId'], 'providerId': args['providerId'],
                'providerVersion': '1', 'documentId': args['documentId'],
                'sourceHash': args['codeHash'], 'requestId': args['requestId'],
                'expiresAtUnixMs': int(time.time() * 1000) + (-1000 if expired else 60000)})
            self.registry()

        def start(self, descriptor, args):
            self.call(descriptor, 'schematic.runtime.start', args)
            self.attempts.append(dict(args))

        def terminal(self, descriptor, request_id, outcome):
            until = time.monotonic() + self.timeout(3)
            while time.monotonic() < until:
                receipt = self.call(descriptor, 'schematic.runtime.status',
                    {'requestId': request_id, 'documentId': self.document_id})
                if receipt.get('phase') == 'terminal' or receipt.get('outcome') == outcome:
                    check(receipt.get('outcome') == outcome, 'Unexpected CLI terminal outcome')
                    check(receipt.get('descendantsStopped') is True and not receipt.get('recordingError'),
                          'CLI terminal receipt lacks verified cleanup/recording')
                    args = next(a for a in self.attempts if a['requestId'] == request_id)
                    frozen = receipt.get('request', {})
                    expected = {'requestId': args['requestId'], 'providerId': args['providerId'],
                        'providerVersion': args['providerVersion'], 'grantId': args['grantId'],
                        'documentId': args['documentId'], 'revision': args['ifRevision'],
                        'stateToken': args['stateToken'], 'referenceId': args['referenceId'],
                        'source': self.sources[args['referenceId'].removeprefix('cli-code-')],
                        'sourceHash': args['codeHash'], 'inputJson': json.dumps(args['input'], separators=(',', ':'))}
                    expected['inputHash'] = sha(expected['inputJson'].encode())
                    check(receipt.get('schema') == 'schematically.cli-receipt@1' and frozen == expected,
                          'Runtime receipt lost exact frozen request identities')
                    check(receipt.get('requestHash') == sha(json.dumps(expected, separators=(',', ':'), ensure_ascii=False).encode()),
                          'Runtime request hash differs from frozen identities')
                    expected_executable_hash = self.python_hash if args['providerId'] == 'python-cli' else self.node_hash
                    check(receipt.get('provider', {}).get('executableSha256') == expected_executable_hash,
                          'Runtime receipt lost executable identity')
                    stdout, stderr = receipt.get('stdout'), receipt.get('stderr')
                    check(isinstance(stdout, str) and isinstance(stderr, str), 'Runtime output missing')
                    check(receipt.get('stdoutHash') == sha(stdout.encode())
                          and receipt.get('stderrHash') == sha(stderr.encode())
                          and receipt.get('outputHash') == sha(stdout.encode() + b'\0' + stderr.encode()),
                          'Runtime output hash differs from actual retained bytes')
                    retained = self.call(descriptor, 'schematic.runtime.results',
                        {'requestId': request_id, 'documentId': self.document_id})
                    path = self.runtime_home / 'attempts' / sha(request_id.encode())
                    check(retained == receipt and json.loads((path / 'receipt.json').read_text()) == receipt,
                          'Terminal status was published before durable recording')
                    check((path / 'stdout.bin').read_bytes() == stdout.encode()
                          and (path / 'stderr.bin').read_bytes() == stderr.encode(),
                          'Terminal output does not match durable output artifacts')
                    self.observations.append({'operation': 'terminal', 'receipt': receipt})
                    return receipt
                time.sleep(min(0.025, max(0, until - time.monotonic())))
            raise TimeoutError('CLI terminal receipt not ready within three seconds')

        def marker(self, kind):
            path = self.work / (kind + '-children.json')
            until = time.monotonic() + self.timeout(2)
            while not path.is_file() and time.monotonic() < until:
                time.sleep(min(0.025, max(0, until - time.monotonic())))
            check(path.is_file(), 'Granted program did not produce an actual descendant marker')
            value = json.loads(path.read_text())
            check(all(type(value.get(k)) is int and value[k] > 0 for k in ('parentPid', 'childPid')),
                  'Malformed owned descendant PID marker')
            self.observations.append({'operation': 'owned-descendants', 'kind': kind, **value})
            return value

        def stopped(self, marker):
            check(gone(marker['parentPid']) and gone(marker['childPid']),
                  'CLI parent or descendant survived terminal cleanup')

        def close_held(self, process, descriptor_path):
            from native_mcp_qa import post_close
            post_close(process.pid, self.window_title, self.observations, deadline=self.deadline)
            process.wait(timeout=self.timeout(4))
            check(process.returncode == 1, 'Recording/unknown completion hold did not return explicit exit1')
            check(not descriptor_path.exists(), 'Held runtime close retained desktop descriptor')
            self.observations.append({'operation': 'held-runtime-close', 'pid': process.pid,
                                      'exitCode': process.returncode, 'descriptorRemoved': True})

        def run_cli(self):
            process = self.launch(self.fixture)
            descriptor_path, descriptor = self.ready(process)
            before = self.call(descriptor, 'schematic.document.get')
            self.case('provider-list')
            check(self.call(descriptor, 'schematic.runtime.providers') == {'providers': []},
                  'Unregistered native runtime did not default to denied')
            self.call(descriptor, 'schematic.runtime.start', self.request_args(descriptor, 'unregistered'),
                      refuse=True, reason='PROVIDER_UNAVAILABLE')
            check(not (self.runtime_home / 'attempts' / sha(b'unregistered')).exists(),
                  'Unregistered runtime created an execution attempt')
            self.registry()
            providers = self.call(descriptor, 'schematic.runtime.providers')
            check(any(p.get('id') == 'node-cli' and p.get('version') == '1' for p in providers.get('providers', [])),
                  'Registered Node provider not listed')
            self.passed(self.current)
            for name in ('missing-grant', 'expired-grant', 'stale-document', 'stale-code', 'changed-executable'):
                self.case(name)
                args = self.request_args(descriptor, name)
                if name != 'missing-grant':
                    self.grant(args, expired=name == 'expired-grant')
                if name == 'stale-document': args['documentId'] = 'wrong-document'
                if name == 'stale-code': args['codeHash'] = '0' * 64
                if name == 'changed-executable':
                    self.provider['executableSha256'] = '0' * 64
                    self.registry()
                reason = {'missing-grant': 'Execution grant not found',
                          'expired-grant': 'Execution grant expired',
                          'stale-document': 'DOCUMENT_CHANGED', 'stale-code': 'CODE_CHANGED',
                          'changed-executable': 'executable hash changed'}[name]
                self.call(descriptor, 'schematic.runtime.start', args, refuse=True, reason=reason)
                attempts = self.runtime_home / 'attempts' / sha(args['requestId'].encode())
                check(not attempts.exists(), 'Refused request created an execution attempt')
                self.provider['executableSha256'] = self.node_hash
                self.registry()
                self.passed(self.current)
            self.case('real-node-output')
            args = self.request_args(descriptor, 'success')
            self.grant(args)
            self.start(descriptor, args)
            completed = self.terminal(descriptor, 'success', 'succeeded')
            check(completed.get('exitCode') == 0 and json.loads(completed['stdout']) == {'answer': 42},
                  'Granted Node execution did not produce actual expected output')
            self.passed(self.current)
            self.case('request-replay')
            replay = self.call(descriptor, 'schematic.runtime.start', args)
            check(replay == completed, 'Exact replay did not return the retained attempt')
            self.passed(self.current)
            self.case('changed-replay-refused')
            self.call(descriptor, 'schematic.runtime.start', {**args, 'input': {'value': 100}}, refuse=True,
                      reason='Request replay identities differ')
            self.passed(self.current)
            self.case('consumed-grant')
            grant = next(g for g in self.grants if g['id'] == args['grantId'])
            grant['requestId'] = 'consumed-again'
            self.registry()
            self.call(descriptor, 'schematic.runtime.start', {**args, 'requestId': 'consumed-again'}, refuse=True,
                      reason='Single-use execution grant consumed')
            consumed = self.runtime_home / 'consumed' / sha(args['grantId'].encode())
            check(consumed.is_file(), 'Successful granted execution did not retain grant consumption')
            self.passed(self.current)
            self.case('timeout-before-effects')
            self.provider['limits']['timeoutMs'] = 1
            self.registry()
            preflight = self.request_args(descriptor, 'preflight-expiry', kind='preflight')
            self.grant(preflight)
            self.start(descriptor, preflight)
            receipt = self.terminal(descriptor, 'preflight-expiry', 'timed-out')
            check(receipt.get('pid') is None
                  and receipt.get('assignedBeforeResume') is not True,
                  'Preflight expiry recorded a process-launch identity')
            check(receipt['stdout'] == '' and receipt['stderr'] == ''
                  and not self.preflight_marker.exists(),
                  'Preflight expiry admitted authored execution effects')
            self.observations.append({'operation':'preflight-expiry', 'pid':receipt.get('pid'),
                'pidFieldPresent':'pid' in receipt,
                'markerAbsent':True, 'timeoutMs':1,
                'timingDeterminismGuaranteed':False})
            self.passed(self.current)
            self.case('timeout-descendants')
            self.provider['limits']['timeoutMs'] = 3000
            self.registry()
            timed = self.request_args(descriptor, 'timeout', kind='timeout')
            self.grant(timed)
            self.start(descriptor, timed)
            marker = self.marker('timeout')
            self.terminal(descriptor, 'timeout', 'timed-out')
            self.stopped(marker)
            self.passed(self.current)
            self.provider['limits']['timeoutMs'] = 5000
            self.registry()
            self.case('cancel-descendants')
            cancelled = self.request_args(descriptor, 'cancel', kind='cancel')
            self.grant(cancelled)
            self.start(descriptor, cancelled)
            marker = self.marker('cancel')
            info = self.info(descriptor)
            self.call(descriptor, 'schematic.runtime.cancel', {'requestId': 'cancel',
                'documentId': info['documentId'], 'ifRevision': info['revision'], 'stateToken': info['stateToken']})
            self.terminal(descriptor, 'cancel', 'cancelled')
            self.stopped(marker)
            self.passed(self.current)
            self.case('output-overflow')
            self.provider['limits']['maxOutputBytes'] = 1024
            self.registry()
            overflow = self.request_args(descriptor, 'overflow', kind='overflow')
            self.grant(overflow)
            self.start(descriptor, overflow)
            self.terminal(descriptor, 'overflow', 'output-overflow')
            self.passed(self.current)
            self.case('durable-results-reopen')
            self.close(process, descriptor_path)
            process = self.launch(self.fixture)
            descriptor_path, descriptor = self.ready(process)
            retained = self.call(descriptor, 'schematic.runtime.results',
                {'requestId': 'success', 'documentId': self.document_id})
            check(retained == completed, 'Terminal result changed or disappeared after desktop reopen')
            self.passed(self.current)
            self.case('no-automatic-document-mutation')
            check(self.call(descriptor, 'schematic.document.get') == before,
                  'Runtime automatically changed the authored document')
            check(not self.info(descriptor)['dirty'], 'Runtime automatically dirtied the document')
            self.passed(self.current)
            self.case('app-close-descendants')
            self.provider['limits']['maxOutputBytes'] = 4096
            self.registry()
            shutdown = self.request_args(descriptor, 'shutdown', kind='shutdown')
            self.grant(shutdown)
            self.start(descriptor, shutdown)
            marker = self.marker('shutdown')
            self.close(process, descriptor_path)
            self.stopped(marker)
            # The persisted shutdown terminal must be a real receipt, not a
            # driver-written substitute or a count of a suite as one case.
            receipts = []
            for path in (self.runtime_home / 'attempts').glob('*/receipt.json'):
                if path.stat().st_size > 2 * 1024 * 1024:
                    continue
                value = json.loads(path.read_text(encoding='utf-8'))
                if isinstance(value, dict) and value.get('schema') == 'schematically.cli-receipt@1':
                    request = value.get('request', value)
                    if request.get('requestId') == 'shutdown': receipts.append((path, value))
            check(len(receipts) == 1, 'Shutdown did not retain one terminal attempt receipt')
            path, receipt = receipts[0]
            check(receipt.get('descendantsStopped') is True and receipt.get('phase') == 'terminal'
                  and receipt.get('outcome') == 'cancelled' and not receipt.get('recordingError'),
                  'Shutdown receipt lacks cancellation/cleanup evidence')
            self.observations.append({'operation': 'shutdown-receipt', 'path': str(path),
                                      'sha256': sha(path.read_bytes()), 'receipt': receipt})
            self.passed(self.current)
            self.case('corrupt-output-recovery-refused')
            artifact = self.runtime_home / 'attempts' / sha(b'success') / 'stdout.bin'
            process = self.launch(self.fixture)
            descriptor_path, descriptor = self.ready(process)
            check(self.call(descriptor, 'schematic.runtime.results',
                {'requestId': 'success', 'documentId': self.document_id}) == completed,
                'Valid artifact could not be read before the corruption probe')
            artifact.write_bytes(b'corrupted-owned-output')
            self.call(descriptor, 'schematic.runtime.results',
                {'requestId': 'success', 'documentId': self.document_id}, refuse=True,
                reason='Retained terminal evidence changed')
            unknown = self.call(descriptor, 'schematic.runtime.status',
                {'requestId': 'success', 'documentId': self.document_id})
            check(unknown.get('phase') == 'unknown' and unknown.get('recordingError'),
                  'Live host accepted a result after durable output corruption')
            self.close_held(process, descriptor_path)
            process = self.launch(self.fixture)
            descriptor_path, descriptor = self.ready(process)
            self.call(descriptor, 'schematic.runtime.results',
                {'requestId': 'success', 'documentId': self.document_id}, refuse=True,
                reason='verified terminal receipt')
            unknown = self.call(descriptor, 'schematic.runtime.status',
                {'requestId': 'success', 'documentId': self.document_id})
            check(unknown.get('phase') == 'unknown' and unknown.get('outcome') == 'unknown'
                  and unknown.get('recordingError'), 'Corrupted output reopened as accepted terminal result')
            self.call(descriptor, 'schematic.runtime.start', self.request_args(descriptor, 'held-after-corruption'),
                      refuse=True, reason='admission held')
            self.close_held(process, descriptor_path)
            self.passed(self.current)

            self.case('python-output')
            node_provider = self.provider
            self.runtime_home = self.work / 'python-host'
            self.runtime_home.mkdir()
            self.grants = []
            self.provider = {'id': 'python-cli', 'version': '1', 'language': 'python',
                'executable': str(self.python), 'executableSha256': self.python_hash,
                'limits': {'timeoutMs': 5000, 'maxOutputBytes': 4096,
                           'maxProcesses': 4, 'maxMemoryBytes': 536870912}}
            self.registry()
            process = self.launch(self.fixture)
            descriptor_path, descriptor = self.ready(process)
            args = self.request_args(descriptor, 'python-output', kind='python-output', provider_id='python-cli')
            self.grant(args)
            self.start(descriptor, args)
            python_result = self.terminal(descriptor, 'python-output', 'succeeded')
            check(json.loads(python_result['stdout']) == {'answer': 42},
                  'Granted Python execution did not produce the expected output')
            self.passed(self.current)
            self.case('python-language-refused')
            mismatch = self.request_args(descriptor, 'python-language-refused', kind='success', provider_id='python-cli')
            self.call(descriptor, 'schematic.runtime.start', mismatch, refuse=True,
                      reason='PROVIDER_LANGUAGE_MISMATCH')
            check(not (self.runtime_home / 'attempts' / sha(b'python-language-refused')).exists(),
                  'Language mismatch created an execution attempt')
            self.passed(self.current)
            self.close(process, descriptor_path)
            self.provider = node_provider

            self.case('terminal-recording-failure-held')
            self.runtime_home = self.work / 'recording-failure-host'
            self.runtime_home.mkdir()
            self.grants = []
            self.registry()
            process = self.launch(self.fixture)
            descriptor_path, descriptor = self.ready(process)
            broken = self.request_args(descriptor, 'record-failure', kind='record-failure')
            self.grant(broken)
            self.start(descriptor, broken)
            until = time.monotonic() + self.timeout(3)
            while time.monotonic() < until:
                unknown = self.call(descriptor, 'schematic.runtime.status',
                    {'requestId': 'record-failure', 'documentId': self.document_id})
                if unknown.get('recordingError'): break
                time.sleep(min(0.025, max(0, until - time.monotonic())))
            check(unknown.get('phase') == 'unknown' and unknown.get('outcome') == 'unknown'
                  and unknown.get('recordingError') and unknown.get('descendantsStopped') is True,
                  'Failed terminal recording was reported as accepted completion')
            attempt = self.runtime_home / 'attempts' / sha(b'record-failure')
            check((attempt / 'receipt.json').is_dir() and (attempt / 'intent.json').is_file(),
                  'Trusted code did not cause the actual owned terminal recording failure')
            check(type(unknown.get('pid')) is int and gone(unknown['pid']),
                  'Recording-failure process survived verified cleanup')
            self.call(descriptor, 'schematic.runtime.results',
                {'requestId': 'record-failure', 'documentId': self.document_id}, refuse=True,
                reason='verified terminal receipt')
            self.call(descriptor, 'schematic.runtime.start', self.request_args(descriptor, 'held-after-recording'),
                      refuse=True, reason='admission held')
            self.observations.append({'operation': 'terminal-recording-failure', 'receipt': unknown,
                                      'ownedAttempt': str(attempt)})
            self.close_held(process, descriptor_path)
            self.passed(self.current)

    suite = None
    failed = False
    try:
        suite = CliSuite(coverage_dir)
        suite.run_cli()
    except Exception as problem:
        failed = True
        case_id = suite.current if suite else CASE_IDS[0]
        message = suite.redact(problem) if suite else str(problem)
        print('CASE FAIL ' + case_id + ': ' + message, flush=True)
        if suite: suite.results.append({'id': case_id, 'status': 'FAIL', 'error': message})
    finally:
        if suite:
            effect_elapsed = time.monotonic() - suite.started
            reached = time.monotonic() >= suite.deadline
            cleanup = suite.cleanup()
            stale = [str(suite.descriptor_dir / f'{p.pid}.json') for p in suite.processes
                     if p.poll() is not None and (suite.descriptor_dir / f'{p.pid}.json').exists()]
            # Independently inspect observed child identities after final cleanup.
            for marker in suite.markers:
                if marker.is_file():
                    try:
                        value = json.loads(marker.read_text())
                        if not gone(value['parentPid']) or not gone(value['childPid']):
                            cleanup.append({'operation': 'CLI descendants', 'error': 'Owned descendant survives'})
                    except Exception as problem:
                        cleanup.append({'operation': 'CLI descendants', 'error': suite.redact(problem)})
            elapsed = time.monotonic() - suite.started
            failed = failed or reached or bool(cleanup or stale) or elapsed > 30
            evidence = {'suite': 'cli-runtime', 'collected': len(CASE_IDS), 'results': suite.results,
                'observations': suite.observations, 'buildRevision': suite.build,
                'nativeBinary': str(suite.binary), 'nativeBinarySha256': sha(suite.binary.read_bytes()),
                'nodeBinary': str(suite.node), 'nodeBinarySha256': sha(suite.node.read_bytes()),
                'driverSha256': sha((suite.root / 'tests/cli_runtime_qa.py').read_bytes()),
                'runtimeHome': str(suite.runtime_home), 'webviewProfile': str(suite.webview_profile),
                'cleanupFailures': cleanup, 'staleOwnedDescriptors': stale,
                'effectElapsedSeconds': effect_elapsed, 'effectDeadlineReached': reached,
                'elapsedSeconds': elapsed, 'limits': {'effectSeconds': 25, 'totalSeconds': 30}}
            if reached: evidence['effectDeadlineFailure'] = 'CLI effects exceeded 25 seconds'
            if stale: evidence['cleanupFailure'] = 'Owned desktop descriptor retained'
            if elapsed > 30: evidence['deadlineFailure'] = 'CLI total exceeded 30 seconds'
            path = suite.work / 'cli-evidence.json'
            path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
            print(json.dumps({'suite': 'cli-runtime', 'evidence': str(path),
                              'passed': not failed, 'elapsedSeconds': elapsed}), flush=True)
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    parser.add_argument('--coverage-dir', type=Path)
    options = parser.parse_args()
    if options.collect:
        print(json.dumps(list(CASE_IDS)))
        return 0
    if options.coverage_dir is None: parser.error('--coverage-dir is required')
    return execute(options.coverage_dir)


if __name__ == '__main__':
    raise SystemExit(main())
