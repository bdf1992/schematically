"""Real Windows desktop/MCP qualification; run only through qualify_local.py.

Uses disposable fixtures, real HTTP/SDK calls and PID-owned WM_CLOSE messages.
The inherited supervisor Job Object owns descendants. This suite does not test
the actual Save As chooser; mocked chooser tests do not close that qualification gap.
Reference: https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getnamedsecurityinfow
Reference: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-postmessagew
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import uuid

EARLY = [
    'native/launch-ready', 'native-http/missing-auth', 'native-http/wrong-auth',
    'native-http/origin', 'native-http/host', 'native-http/protocol',
    'native-http/get', 'native-http/invalid-json', 'native-http/oversize',
    'native/build-revision', 'native/descriptor-private-acl',
]
SDK_IDS = ['native-sdk/connect', 'native-sdk/tools', 'native-sdk/docs',
           'native-sdk/live-read', 'native-sdk/guarded-edit', 'native-sdk/save-durable']
LATE = ['native/graceful-close-descriptor', 'native/reopen-saved',
        'native/reopen-graceful-close-descriptor', 'native/cold-profile-one-read-close',
        'native/cold-profile-two-read-close', 'native/malformed-launch-report',
        'native/missing-launch-report']
CASE_IDS = EARLY + SDK_IDS + LATE


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def private_acl(path):
    """Read actual DACL: protected, exactly owner-rights/System/Admin full access."""
    advapi = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    pointer = ctypes.c_void_p
    advapi.GetNamedSecurityInfoW.argtypes = [wintypes.LPCWSTR, ctypes.c_int,
        wintypes.DWORD, pointer, pointer, ctypes.POINTER(pointer), pointer,
        ctypes.POINTER(pointer)]
    advapi.GetNamedSecurityInfoW.restype = wintypes.DWORD
    advapi.GetSecurityDescriptorControl.argtypes = [pointer,
        ctypes.POINTER(wintypes.WORD), ctypes.POINTER(wintypes.DWORD)]
    advapi.GetSecurityDescriptorControl.restype = wintypes.BOOL
    advapi.GetAce.argtypes = [pointer, wintypes.DWORD, ctypes.POINTER(pointer)]
    advapi.GetAce.restype = wintypes.BOOL
    advapi.ConvertSidToStringSidW.argtypes = [pointer, ctypes.POINTER(wintypes.LPWSTR)]
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [pointer]
    kernel.LocalFree.restype = pointer

    class ACL(ctypes.Structure):
        _fields_ = [('revision', wintypes.BYTE), ('reserved', wintypes.BYTE),
                    ('size', wintypes.WORD), ('count', wintypes.WORD),
                    ('reserved2', wintypes.WORD)]

    class ACE(ctypes.Structure):
        _fields_ = [('type', wintypes.BYTE), ('flags', wintypes.BYTE),
                    ('size', wintypes.WORD)]

    dacl, descriptor = pointer(), pointer()
    status = advapi.GetNamedSecurityInfoW(str(path), 1, 4, None, None,
                                          ctypes.byref(dacl), None,
                                          ctypes.byref(descriptor))
    check(status == 0, f'Descriptor ACL read failed with Win32 status {status}')
    try:
        check(bool(dacl.value), 'Descriptor has a null/unrestricted DACL')
        control, revision = wintypes.WORD(), wintypes.DWORD()
        check(advapi.GetSecurityDescriptorControl(descriptor, ctypes.byref(control),
              ctypes.byref(revision)), 'Descriptor ACL control read failed')
        check(control.value & 0x1000, 'Descriptor DACL permits inherited grants')
        acl = ACL.from_address(dacl.value)
        check(acl.count == 3, 'Descriptor DACL does not have exactly three private grants')
        grants = []
        for index in range(acl.count):
            ace = pointer()
            check(advapi.GetAce(dacl, index, ctypes.byref(ace)), 'Descriptor ACE read failed')
            header = ACE.from_address(ace.value)
            check(header.type == 0 and header.flags == 0 and header.size >= 12,
                  'Descriptor has an unexpected/inherited ACE')
            mask = wintypes.DWORD.from_address(ace.value + 4).value
            check(mask == 0x1f01ff, 'Descriptor private grant is not full file access')
            sid = wintypes.LPWSTR()
            check(advapi.ConvertSidToStringSidW(pointer(ace.value + 8), ctypes.byref(sid)),
                  'Descriptor ACE SID conversion failed')
            try:
                grants.append(sid.value)
            finally:
                kernel.LocalFree(ctypes.cast(sid, pointer))
        check(set(grants) == {'S-1-3-4', 'S-1-5-18', 'S-1-5-32-544'},
              'Descriptor grants access beyond owner-rights/System/Administrators')
        return {'path': str(path), 'protected': True, 'grants': grants}
    finally:
        kernel.LocalFree(descriptor)


def post_close(pid, title, observations, phase='qualification', deadline=None):
    """Close exactly the owned editor, preserving Tao's internal event target."""
    check(deadline is not None and time.monotonic() < deadline, 'Native close effect deadline exhausted')
    user = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.EnumWindows.restype = wintypes.BOOL
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowThreadProcessId.restype = wintypes.DWORD
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetClassNameW.restype = ctypes.c_int
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetWindowTextW.restype = ctypes.c_int
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.GetWindowRect.restype = wintypes.BOOL
    user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                 wintypes.WPARAM, wintypes.LPARAM]
    user.PostMessageW.restype = wintypes.BOOL
    candidates = []

    @callback_type
    def visit(window, unused):
        owner = wintypes.DWORD()
        user.GetWindowThreadProcessId(window, ctypes.byref(owner))
        if owner.value == pid:
            class_name, caption = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(2048)
            class_length = user.GetClassNameW(window, class_name, len(class_name))
            caption_length = user.GetWindowTextW(window, caption, len(caption))
            rect = wintypes.RECT()
            rect_ok = bool(user.GetWindowRect(window, ctypes.byref(rect)))
            candidates.append({'handle': int(window), 'pid': owner.value,
                'class': class_name.value, 'title': caption.value,
                'rect': [rect.left, rect.top, rect.right, rect.bottom] if rect_ok else None,
                'propertiesReadable': bool(class_length and class_length < len(class_name) - 1
                    and caption_length < len(caption) - 1 and rect_ok)})
        return True

    enumerated = bool(user.EnumWindows(visit, 0))
    # tauri-runtime-wry 2.11.4 sets this class in WindowBuilder::new (lib.rs:856).
    # Tao's visible zero-size "Tao Thread Event Target" is also a top-level HWND;
    # sending WM_CLOSE to it destroys the dispatcher, rather than closing the editor.
    selected = [candidate for candidate in candidates
        if candidate['propertiesReadable'] and candidate['class'] == 'Tauri Window'
        and candidate['title'] == title
        and candidate['rect'][2] > candidate['rect'][0]
        and candidate['rect'][3] > candidate['rect'][1]]
    attempt = {'pid': pid, 'phase': phase, 'operation': 'close-main-window',
               'expectedTitle': title, 'candidates': candidates,
               'selectedHandles': [candidate['handle'] for candidate in selected],
               'enumerated': enumerated, 'messagePosted': False}
    observations.append(attempt)  # Retain selection evidence even if posting or waiting fails.
    check(enumerated, 'Own native window enumeration failed')
    check(len(selected) == 1, f'Expected exactly one owned Tauri editor window, found {len(selected)}')
    window = selected[0]['handle']
    owner = wintypes.DWORD()
    user.GetWindowThreadProcessId(window, ctypes.byref(owner))
    check(owner.value == pid, 'Selected native window changed ownership before close')
    check(time.monotonic() < deadline, 'Native close effect deadline exhausted before posting')
    attempt['messagePosted'] = bool(user.PostMessageW(window, 0x10, 0, 0))  # WM_CLOSE
    if not attempt['messagePosted']:
        attempt['win32Error'] = ctypes.get_last_error()
    check(attempt['messagePosted'], 'Owned native editor could not receive WM_CLOSE')
    return 1


class NativeSuite:
    def __init__(self, coverage_dir):
        check(os.name == 'nt', 'Real native suite requires Windows; unsupported hosts fail')
        self.started = time.monotonic()
        self.deadline = self.started + 55  # Leave five seconds for owned-process cleanup.
        self.root = Path(os.environ['SOV_SOURCE_ROOT']).resolve(strict=True)
        self.binary = Path(os.environ['SOV_NATIVE_BINARY']).resolve(strict=True)
        self.build = os.environ['SOV_BUILD_REVISION']
        check(self.build and self.build != 'unversioned', 'A stamped candidate revision is required')
        self.node = os.environ.get('SOV_NODE_BINARY') or shutil.which('node')
        check(self.node and Path(self.node).is_file(), 'Measured Node executable is unavailable')
        config = json.loads((self.root / 'desktop/src-tauri/tauri.conf.json').read_text(encoding='utf-8'))
        check(config['identifier'] == 'com.soveraeign.schematic', 'Unexpected native descriptor owner')
        windows = config['app']['windows']
        check(len(windows) == 1 and isinstance(windows[0].get('title'), str)
              and windows[0]['title'], 'Native qualification requires one declared editor title')
        self.window_title = windows[0]['title']
        local = Path(os.environ['LOCALAPPDATA']).resolve(strict=True)
        self.descriptor_dir = local / config['identifier'] / 'mcp'
        self.work = coverage_dir.resolve().parent / ('native-runtime-' + uuid.uuid4().hex)
        self.work.mkdir()
        self.runtime_home = self.work / 'runtime-host'
        self.runtime_home.mkdir()
        self.webview_profile = self.work / 'webview-profile'
        self.webview_profile.mkdir()
        self.processes = []
        self.process_logs = []
        self.tokens = []
        self.results = []
        self.observations = []
        self.current = CASE_IDS[0]
        self.fixture = self.work / 'Native-Qualification.sov'
        shutil.copyfile(self.root / 'examples/01-source-hold.sov', self.fixture)

    def timeout(self, maximum):
        value = min(maximum, self.deadline - time.monotonic())
        if value <= 0:
            raise TimeoutError('Native queue exhausted its 55-second effect allowance')
        return value

    def redact(self, value):
        text = str(value)
        for token in self.tokens:
            text = text.replace(token, '[redacted]')
        text = re.sub(r'Bearer\s+[^\s"\']+', 'Bearer [redacted]', text, flags=re.I)
        return re.sub(r'(["\']?token["\']?\s*[:=]\s*)["\']?[^\s,"\'}]+["\']?',
                      r'\1[redacted]', text, flags=re.I)

    def passed(self, case_id):
        check(case_id in CASE_IDS, 'Unknown native case ID')
        check(not any(result['id'] == case_id for result in self.results), 'Duplicate native pass ID')
        self.results.append({'id': case_id, 'status': 'PASS'})
        print('CASE PASS ' + case_id, flush=True)

    def launch(self, path, report=None, profile=None):
        self.timeout(10)
        profile = self.webview_profile if profile is None else profile
        profile = profile.resolve(strict=True)
        check(profile.is_dir() and profile.is_relative_to(self.work.resolve(strict=True))
              and profile != self.work.resolve(strict=True), 'Native test profile must remain under owned work')
        arguments = [str(self.binary), str(path)]
        if report is not None:
            arguments += ['--smoke-report', str(report)]
        # Inherits the supervisor's Windows Job and LLVM_PROFILE_FILE; no breakaway.
        # Retain only a redacted final log. The raw owned temporary handle is deleted
        # when cleanup closes it; no secret-bearing stdout is printed into evidence.
        log = tempfile.TemporaryFile(mode='w+b')
        environment = os.environ.copy()
        # Microsoft WebView2 environment override: isolate qualification recovery
        # and cache state; reuse only this suite's profile for its close/reopen checks.
        environment['WEBVIEW2_USER_DATA_FOLDER'] = str(profile)
        environment['SOV_RUNTIME_DIR'] = str(self.runtime_home)
        try:
            process = subprocess.Popen(arguments, cwd=self.work, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, env=environment)
        except BaseException:
            log.close()
            raise
        self.processes.append(process)
        self.process_logs.append((process, log))
        self.observations.append({'operation': 'launch-native', 'pid': process.pid,
            'buildRevision': self.build, 'elapsedSeconds': time.monotonic() - self.started,
            'logPath': str(self.work / f'native-{process.pid}.log'),
            'webviewProfile': str(profile),
            'webviewProfilePresent': profile.is_dir(),
            'smoke': report is not None})
        return process

    def request(self, descriptor, method='POST', raw=None, headers=None, authorize=True, deadline=None):
        endpoint = urllib.parse.urlsplit(descriptor['endpoint'])
        check(endpoint.scheme == 'http' and endpoint.hostname == '127.0.0.1'
              and endpoint.path == '/mcp' and endpoint.port is not None
              and not endpoint.username and not endpoint.password,
              'Native endpoint escaped the expected loopback transport')
        body = raw if raw is not None else b'{"jsonrpc":"2.0","id":1,"method":"ping"}'
        outgoing = {'Host': endpoint.netloc, 'Content-Type': 'application/json'}
        if authorize:
            outgoing['Authorization'] = 'Bearer ' + descriptor['token']
        outgoing.update(headers or {})
        limit = 3 if deadline is None else min(3, deadline - time.monotonic())
        check(limit > 0, 'Native request deadline expired before transport')
        connection = http.client.HTTPConnection(endpoint.hostname, endpoint.port,
                                                timeout=self.timeout(limit))
        try:
            connection.request(method, endpoint.path, body=body, headers=outgoing)
            response = connection.getresponse()
            return response.status, response.read(2 * 1024 * 1024)
        finally:
            connection.close()

    def rpc(self, descriptor, method, params=None):
        body = json.dumps({'jsonrpc': '2.0', 'id': 7, 'method': method,
                           'params': params or {}}).encode()
        status, text = self.request(descriptor, raw=body)
        check(status == 200, f'Native RPC HTTP status {status}')
        answer = json.loads(text)
        check('error' not in answer and 'result' in answer, 'Native RPC refused the request')
        return answer['result']

    def tool(self, descriptor, name):
        result = self.rpc(descriptor, 'tools/call', {'name': name, 'arguments': {}})
        check(result.get('isError') is False, 'Native read tool returned a refusal')
        return result.get('structuredContent') or json.loads(result['content'][0]['text'])

    def ready(self, process):
        started = time.monotonic()
        until = started + self.timeout(10)
        path = self.descriptor_dir / f'{process.pid}.json'
        counts = dict.fromkeys(['descriptorMissing', 'descriptorOSError', 'descriptorInvalid',
                              'transportOSError', 'http503', 'unexpected', 'ready'], 0)
        observation = {'operation': 'native-readiness', 'pid': process.pid,
            'buildRevision': self.build, 'descriptorPath': str(path),
            'attempts': 0, 'counts': counts, 'lastPhase': 'not-attempted', 'ready': False}
        self.observations.append(observation)
        try:
            while time.monotonic() < until:
                check(process.poll() is None, 'Native process exited before editor readiness')
                observation['attempts'] += 1
                try:
                    descriptor = json.loads(path.read_text(encoding='utf-8'))
                except FileNotFoundError:
                    counts['descriptorMissing'] += 1
                    observation['lastPhase'] = 'descriptorMissing'
                    descriptor = None
                except OSError as problem:
                    counts['descriptorOSError'] += 1
                    observation['lastPhase'] = 'descriptorOSError'
                    observation['lastError'] = {'type': type(problem).__name__,
                        'errno': problem.errno, 'winerror': getattr(problem, 'winerror', None)}
                    descriptor = None
                except json.JSONDecodeError:
                    counts['descriptorInvalid'] += 1
                    observation['lastPhase'] = 'descriptorInvalid'
                    descriptor = None
                if descriptor is None:
                    time.sleep(min(0.05, max(0, until - time.monotonic())))
                    continue
                check(isinstance(descriptor, dict), 'Native descriptor is not an object')
                check(descriptor.get('pid') == process.pid, 'Descriptor PID differs from owned process')
                token = descriptor.get('token')
                check(isinstance(token, str) and len(token) >= 32, 'Native descriptor secret is absent')
                if token not in self.tokens:
                    self.tokens.append(token)
                observation['descriptorBuild'] = self.redact(descriptor.get('build'))
                observation.setdefault('descriptorObservedSeconds', time.monotonic() - started)
                try:
                    status, data = self.request(descriptor, deadline=until)
                except OSError as problem:
                    counts['transportOSError'] += 1
                    observation['lastPhase'] = 'transportOSError'
                    observation['lastError'] = {'type': type(problem).__name__,
                        'errno': problem.errno, 'winerror': getattr(problem, 'winerror', None)}
                    time.sleep(min(0.05, max(0, until - time.monotonic())))
                    continue
                observation['lastHttpStatus'] = status
                if time.monotonic() >= until:
                    observation['lastPhase'] = 'deadline-after-response'
                    raise TimeoutError('Native readiness response arrived after its ten-second deadline')
                if status == 503:
                    counts['http503'] += 1
                    observation['lastPhase'] = 'http503'
                    time.sleep(min(0.05, max(0, until - time.monotonic())))
                    continue
                try:
                    answer = json.loads(data)
                except json.JSONDecodeError:
                    answer = None
                if status == 200 and isinstance(answer, dict) and answer.get('result') == {}:
                    if time.monotonic() >= until:
                        observation['lastPhase'] = 'deadline-before-accept'
                        raise TimeoutError('Native readiness exceeded its ten-second deadline before acceptance')
                    counts['ready'] += 1
                    observation['lastPhase'] = 'ready'
                    observation['ready'] = True
                    return path, descriptor
                counts['unexpected'] += 1
                observation['lastPhase'] = 'unexpected'
                raise AssertionError(f'Unexpected native readiness response (HTTP {status})')
            raise TimeoutError('Native descriptor/editor did not become ready within ten seconds')
        finally:
            observation.update({'elapsedSeconds': time.monotonic() - started,
                'suiteElapsedSeconds': time.monotonic() - self.started,
                'deadlineReached': time.monotonic() >= until,
                'descriptorPresent': path.is_file(), 'processPoll': process.poll()})

    def close(self, process, descriptor_path):
        check(process.poll() is None, 'Native process exited before graceful close')
        close_until = time.monotonic() + self.timeout(4)
        windows = post_close(process.pid, self.window_title, self.observations, deadline=close_until)
        remaining = close_until - time.monotonic()
        check(remaining > 0, 'Native close deadline exhausted before process wait')
        process.wait(timeout=remaining)
        check(process.returncode == 0, 'Graceful native close had a nonzero exit')
        check(not descriptor_path.exists(), 'Graceful native close retained its MCP descriptor')
        self.observations.append({'pid': process.pid, 'closeWindows': windows,
                                  'exitCode': process.returncode, 'descriptorRemoved': True})

    def sdk(self, descriptor_path):
        self.current = SDK_IDS[0]
        command = [str(self.node), str(self.root / 'tests/sdk_consumer.mjs'),
                   '--descriptor', str(descriptor_path), '--fixture', str(self.fixture)]
        sdk = subprocess.Popen(command, cwd=self.root, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, encoding='utf-8')
        self.processes.append(sdk)
        try:
            output, _ = sdk.communicate(timeout=self.timeout(12))
        finally:
            if sdk.poll() is not None and sdk.stdout is not None:
                sdk.stdout.close()
        redacted = self.redact(output)
        (self.work / 'sdk-consumer.log').write_text(redacted, encoding='utf-8')
        for line in redacted.splitlines():
            if line.startswith('CASE PASS '):
                self.passed(line[len('CASE PASS '):])
            elif line.startswith('CASE FAIL '):
                print(line, flush=True)
        actual = re.findall(r'^CASE PASS ([^\r\n]+)$', redacted, re.MULTILINE)
        check(sdk.returncode == 0 and actual == SDK_IDS, 'Original SDK consumer failed or case IDs changed')
        saved = json.loads(self.fixture.read_text(encoding='utf-8'))
        document = saved.get('document', saved)
        ids = [component['id'] for component in document['components']
               if component['id'].startswith('sdk-qualification-')]
        check(len(ids) == 1, 'SDK durable fixture does not have exactly one created component')
        return ids[0]

    def smoke_failure(self, path, case_id):
        self.current = case_id
        report = self.work / (case_id.split('/')[-1] + '.json')
        process = self.launch(path, report)
        process.wait(timeout=self.timeout(10))
        check(process.returncode == 1, 'Invalid launch did not return the documented failure exit')
        check(report.is_file(), 'Invalid launch produced no explicit smoke report')
        body = json.loads(report.read_text(encoding='utf-8'))
        check(body.get('ok') is False and isinstance(body.get('error'), str)
              and body['error'], 'Invalid launch report did not name a failure')
        check(not (self.descriptor_dir / f'{process.pid}.json').exists(),
              'Invalid smoke launch retained an MCP descriptor')
        self.observations.append({'pid': process.pid, 'smokeReport': str(report),
                                  'exitCode': process.returncode, 'ok': False})
        self.passed(case_id)

    def run(self):
        process = self.launch(self.fixture)
        descriptor_path, descriptor = self.ready(process)
        document = self.tool(descriptor, 'schematic.document.get')
        fixture = json.loads(self.fixture.read_text(encoding='utf-8'))
        check(document['id'] == fixture['id'], 'Native editor did not load its copied fixture')
        self.passed('native/launch-ready')
        probes = [
            ('native-http/missing-auth', 403, {'authorize': False}),
            ('native-http/wrong-auth', 403, {'headers': {'Authorization': 'Bearer incorrect'}}),
            ('native-http/origin', 403, {'headers': {'Origin': 'http://localhost'}}),
            ('native-http/host', 403, {'headers': {'Host': 'example.invalid'}}),
            ('native-http/protocol', 400, {'headers': {'MCP-Protocol-Version': '1900-01-01'}}),
            ('native-http/get', 405, {'method': 'GET'}),
            ('native-http/invalid-json', 400, {'raw': b'{broken'}),
            ('native-http/oversize', 413, {'raw': b'x' * (1048576 + 1)}),
        ]
        for case_id, expected, options in probes:
            self.current = case_id
            status, body = self.request(descriptor, **options)
            check(status == expected, f'Native transport expected {expected}, received {status}')
            if case_id == 'native-http/invalid-json':
                check(json.loads(body)['error']['code'] == -32700, 'Native parse error lacks protocol code')
            self.passed(case_id)
        self.current = 'native/build-revision'
        check(descriptor['build'] == self.build, 'Native transport build stamp differs from prepared revision')
        info = self.tool(descriptor, 'schematic.file.info')
        check(info['build'] == self.build, 'Native webview build stamp differs from prepared revision')
        self.passed(self.current)
        self.current = 'native/descriptor-private-acl'
        self.observations += [private_acl(self.descriptor_dir), private_acl(descriptor_path)]
        self.passed(self.current)
        created_id = self.sdk(descriptor_path)
        self.current = 'native/graceful-close-descriptor'
        self.close(process, descriptor_path)
        self.passed(self.current)
        self.current = 'native/reopen-saved'
        reopened = self.launch(self.fixture)
        reopened_path, reopened_descriptor = self.ready(reopened)
        restored = self.tool(reopened_descriptor, 'schematic.document.get')
        check(any(component['id'] == created_id for component in restored['components']),
              'Real reopened editor omits SDK-saved mutation')
        check(not self.tool(reopened_descriptor, 'schematic.file.info')['dirty'],
              'Reopened saved fixture unexpectedly became dirty')
        self.passed(self.current)
        self.current = 'native/reopen-graceful-close-descriptor'
        self.close(reopened, reopened_path)
        self.passed(self.current)
        for suffix in ('one', 'two'):
            self.current = f'native/cold-profile-{suffix}-read-close'
            profile = self.work / f'webview-cold-{suffix}-{uuid.uuid4().hex}'
            profile.mkdir()
            cold = self.launch(self.fixture, profile=profile)
            cold_path, cold_descriptor = self.ready(cold)
            cold_document = self.tool(cold_descriptor, 'schematic.document.get')
            cold_info = self.tool(cold_descriptor, 'schematic.file.info')
            check(cold_document['id'] == fixture['id']
                  and any(component['id'] == created_id for component in cold_document['components']),
                  'Cold-profile editor did not reopen the durable fixture mutation')
            check(cold_info['name'] == self.fixture.name and cold_info['dirty'] is False
                  and cold_info['build'] == self.build,
                  'Cold-profile editor file identity, durable state or build differs')
            self.close(cold, cold_path)
            self.passed(self.current)
        malformed = self.work / 'Malformed.sov'
        malformed.write_text('{broken', encoding='utf-8')
        self.smoke_failure(malformed, 'native/malformed-launch-report')
        self.smoke_failure(self.work / 'Missing.sov', 'native/missing-launch-report')

    def cleanup(self):
        until = time.monotonic() + 5
        failures = []
        for process in self.processes:
            if process.poll() is not None:
                continue
            try:
                # Attempt WM_CLOSE only for our native PID; SDK is a console child.
                if Path(process.args[0]).resolve() == self.binary:
                    post_close(process.pid, self.window_title, self.observations, 'cleanup', deadline=until)
                    process.wait(timeout=max(0.001, min(1, until - time.monotonic())))
                else:
                    process.terminate()
                    process.wait(timeout=max(0.001, min(1, until - time.monotonic())))
            except Exception:
                try:
                    process.kill()  # Only this Popen-owned PID; never a name/process-tree kill.
                    process.wait(timeout=max(0.001, until - time.monotonic()))
                except Exception as problem:
                    failures.append({'pid': process.pid, 'error': self.redact(problem)})
        # communicate's timeout leaves its pipe owned by this suite; close it
        # after the cleanup above has stopped that child, including failed runs.
        for process in self.processes:
            if process.stdout is not None:
                if process.poll() is None:
                    failures.append({'pid': process.pid, 'operation': 'close-sdk-pipe',
                                     'error': 'Owned child remains live; pipe close cannot safely wait'})
                    continue
                try:
                    process.stdout.close()
                except Exception as problem:
                    failures.append({'pid': process.pid, 'operation': 'close-sdk-pipe',
                                     'error': self.redact(problem)})
        for process, log in self.process_logs:
            path = self.work / f'native-{process.pid}.log'
            try:
                log.flush()
                log.seek(0, os.SEEK_END)
                total_bytes = log.tell()
                log.seek(0)
                # Bound diagnostic retention and decoding work even if a child is noisy.
                content = log.read(1024 * 1024).decode('utf-8', errors='replace')
                path.write_text(self.redact(content), encoding='utf-8')
                self.observations.append({'operation': 'native-log', 'pid': process.pid,
                    'path': str(path), 'rawBytes': total_bytes,
                    'truncated': total_bytes > 1024 * 1024, 'processPoll': process.poll()})
            except Exception as problem:
                failures.append({'pid': process.pid, 'operation': 'retain-native-log',
                                 'error': self.redact(problem)})
            finally:
                log.close()
        self.process_logs.clear()
        return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    parser.add_argument('--coverage-dir', type=Path)
    options = parser.parse_args()
    if options.collect:
        print(json.dumps(CASE_IDS))
        return 0  # No environment reads, fixtures, Windows APIs, processes or network.
    if options.coverage_dir is None:
        parser.error('--coverage-dir is required for execution')
    suite = None
    failed = False
    try:
        suite = NativeSuite(options.coverage_dir)
        suite.run()
    except Exception as problem:
        failed = True
        case_id = suite.current if suite is not None else CASE_IDS[0]
        message = suite.redact(problem) if suite is not None else str(problem)
        print(f'CASE FAIL {case_id}: {message}', flush=True)
        if suite is not None:
            suite.results.append({'id': case_id, 'status': 'FAIL', 'error': message})
    finally:
        if suite is not None:
            effect_elapsed = time.monotonic() - suite.started
            effect_deadline_reached = time.monotonic() >= suite.deadline
            failed = failed or effect_deadline_reached
            cleanup_failures = suite.cleanup()
            failed = failed or bool(cleanup_failures)
            evidence = {'suite': 'native-mcp', 'collected': len(CASE_IDS),
                        'results': suite.results, 'observations': suite.observations,
                        'cleanupFailures': cleanup_failures,
                        'remainingGaps': ['Actual Save As chooser interaction is not qualified.'],
                        'webviewProfile': str(suite.webview_profile),
                        'runtimeHome': str(suite.runtime_home),
                        'webviewProfilePresent': suite.webview_profile.is_dir(),
                        'nativeBinary': str(suite.binary),
                        'nativeBinarySha256': hashlib.sha256(suite.binary.read_bytes()).hexdigest(),
                        'sdkConsumerSha256': hashlib.sha256((suite.root / 'tests/sdk_consumer.mjs').read_bytes()).hexdigest(),
                        'nodeBinary': str(suite.node),
                        'nodeBinarySha256': hashlib.sha256(Path(suite.node).read_bytes()).hexdigest(),
                        'staleOwnedDescriptors': [str(suite.descriptor_dir / f'{process.pid}.json')
                            for process in suite.processes
                            if Path(process.args[0]).resolve() == suite.binary
                            and process.poll() is not None
                            and (suite.descriptor_dir / f'{process.pid}.json').exists()],
                        'buildRevision': suite.build}
            evidence['effectElapsedSeconds'] = effect_elapsed
            evidence['effectDeadlineReached'] = effect_deadline_reached
            if effect_deadline_reached:
                evidence['effectDeadlineFailure'] = 'Native effects reached the 55-second limit before cleanup'
            evidence['elapsedSeconds'] = time.monotonic() - suite.started
            if evidence['staleOwnedDescriptors']:
                failed = True
                evidence['cleanupFailure'] = 'An owned native descriptor survived process exit'
            if evidence['elapsedSeconds'] > 60:
                failed = True
                evidence['deadlineFailure'] = 'Native queue exceeded its 60-second limit'
            (suite.work / 'native-evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
            print(json.dumps({'suite': 'native-mcp', 'evidence': str(suite.work / 'native-evidence.json'),
                              'passed': not failed, 'elapsedSeconds': evidence['elapsedSeconds']}))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
