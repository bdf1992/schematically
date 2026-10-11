"""Run admitted commands with process-tree containment and retained combined logs.

Windows uses suspended CreateProcessW, an explicit inherited-handle list, and a
kill-on-close Job Object assigned before ResumeThread. No breakaway or shell
fallback is enabled. POSIX uses a new session/process group; commands that detach
themselves from that group are outside this POSIX containment mechanism.

The execution deadline includes setup. Cleanup has a separate maximum five-second
grace, included in elapsedSeconds; callers must charge it to their total budget.
This helper does not admit a command, select suites, or establish test coverage.

Win32 reference: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw
https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


def supervised_parent(expected_pid):
    """Accept a direct supervisor, or one verified Windows venv launcher hop.

    This checks ancestry only; run_bounded separately establishes Job containment.
    API references: https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/ns-tlhelp32-processentry32w
    https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew
    """
    if not isinstance(expected_pid, (int, str)) or isinstance(expected_pid, bool):
        return False
    try:
        expected_pid = int(expected_pid)
    except ValueError:
        return False
    if expected_pid <= 0 or expected_pid == os.getpid():
        return False
    parent = os.getppid()
    if parent == expected_pid:
        return True
    if os.name != 'nt':
        return False
    from ctypes import wintypes as w
    k = ctypes.WinDLL('kernel32', use_last_error=True)

    class Entry(ctypes.Structure):
        _fields_ = [('dwSize', w.DWORD), ('cntUsage', w.DWORD),
                    ('th32ProcessID', w.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
                    ('th32ModuleID', w.DWORD), ('cntThreads', w.DWORD),
                    ('th32ParentProcessID', w.DWORD), ('pcPriClassBase', w.LONG),
                    ('dwFlags', w.DWORD), ('szExeFile', w.WCHAR * 260)]

    def api(name, args, result=w.BOOL):
        fn = getattr(k, name)
        fn.argtypes, fn.restype = args, result
        return fn

    snapshot = api('CreateToolhelp32Snapshot', [w.DWORD, w.DWORD], w.HANDLE)
    first = api('Process32FirstW', [w.HANDLE, ctypes.POINTER(Entry)])
    next_entry = api('Process32NextW', [w.HANDLE, ctypes.POINTER(Entry)])
    open_process = api('OpenProcess', [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
    query_image = api('QueryFullProcessImageNameW',
                      [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)])
    wait = api('WaitForSingleObject', [w.HANDLE, w.DWORD], w.DWORD)
    close = api('CloseHandle', [w.HANDLE])
    snap = snapshot(0x2, 0)  # TH32CS_SNAPPROCESS, read-only snapshot.
    if not snap or snap == ctypes.c_void_p(-1).value:
        return False
    entries = {}
    try:
        entry = Entry()
        entry.dwSize = ctypes.sizeof(Entry)
        more = first(snap, ctypes.byref(entry))
        wanted = {os.getpid(), parent, expected_pid}
        while more:
            if entry.th32ProcessID in wanted:
                entries[entry.th32ProcessID] = (entry.th32ParentProcessID, entry.szExeFile)
            if set(entries) == wanted:
                break
            more = next_entry(snap, ctypes.byref(entry))
    finally:
        close(snap)
    if (set(entries) != wanted or entries[os.getpid()][0] != parent
            or entries[parent][0] != expected_pid
            or entries[parent][1].casefold() != 'python.exe'):
        return False
    # Hold handles while validating both processes are still alive; no PID-only
    # acceptance of an exited supervisor or an unrelated executable named python.
    handles = []
    try:
        for pid in (expected_pid, parent):
            handle = open_process(0x1000 | 0x100000, False, pid)
            if not handle:
                return False
            handles.append(handle)
            if wait(handle, 0) != 0x102:  # WAIT_TIMEOUT means still running.
                return False
        image = ctypes.create_unicode_buffer(32768)
        length = w.DWORD(len(image))
        if not query_image(handles[1], 0, image, ctypes.byref(length)):
            return False
        if (os.path.normcase(os.path.realpath(image.value))
                != os.path.normcase(os.path.realpath(sys.executable))):
            return False
        return os.getppid() == parent and all(wait(handle, 0) == 0x102 for handle in handles)
    finally:
        for handle in handles:
            close(handle)


def _windows(argv, cwd, env, log, deadline):
    from ctypes import wintypes as w
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    size = ctypes.c_size_t
    pointer = ctypes.c_void_p

    class Startup(ctypes.Structure):
        _fields_ = [('cb', w.DWORD), ('lpReserved', w.LPWSTR),
                    ('lpDesktop', w.LPWSTR), ('lpTitle', w.LPWSTR),
                    ('dwX', w.DWORD), ('dwY', w.DWORD),
                    ('dwXSize', w.DWORD), ('dwYSize', w.DWORD),
                    ('dwXCountChars', w.DWORD), ('dwYCountChars', w.DWORD),
                    ('dwFillAttribute', w.DWORD), ('dwFlags', w.DWORD),
                    ('wShowWindow', w.WORD), ('cbReserved2', w.WORD),
                    ('lpReserved2', pointer), ('hStdInput', w.HANDLE),
                    ('hStdOutput', w.HANDLE), ('hStdError', w.HANDLE)]

    class StartupEx(ctypes.Structure):
        _fields_ = [('StartupInfo', Startup), ('lpAttributeList', pointer)]

    class ProcessInfo(ctypes.Structure):
        _fields_ = [('hProcess', w.HANDLE), ('hThread', w.HANDLE),
                    ('dwProcessId', w.DWORD), ('dwThreadId', w.DWORD)]

    class Security(ctypes.Structure):
        _fields_ = [('nLength', w.DWORD), ('lpSecurityDescriptor', pointer),
                    ('bInheritHandle', w.BOOL)]

    class BasicLimits(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64),
                    ('PerJobUserTimeLimit', ctypes.c_int64), ('LimitFlags', w.DWORD),
                    ('MinimumWorkingSetSize', size), ('MaximumWorkingSetSize', size),
                    ('ActiveProcessLimit', w.DWORD), ('Affinity', size),
                    ('PriorityClass', w.DWORD), ('SchedulingClass', w.DWORD)]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in (
            'ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
            'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', BasicLimits), ('IoInfo', IoCounters),
                    ('ProcessMemoryLimit', size), ('JobMemoryLimit', size),
                    ('PeakProcessMemoryUsed', size), ('PeakJobMemoryUsed', size)]

    class Accounting(ctypes.Structure):
        _fields_ = [(name, ctypes.c_int64) for name in (
            'TotalUserTime', 'TotalKernelTime', 'ThisPeriodTotalUserTime',
            'ThisPeriodTotalKernelTime')] + [(name, w.DWORD) for name in (
            'TotalPageFaultCount', 'TotalProcesses', 'ActiveProcesses',
            'TotalTerminatedProcesses')]

    def api(name, args, result=w.BOOL):
        fn = getattr(k, name)
        fn.argtypes, fn.restype = args, result
        return fn

    close = api('CloseHandle', [w.HANDLE])
    create_job = api('CreateJobObjectW', [pointer, w.LPCWSTR], w.HANDLE)
    set_job = api('SetInformationJobObject', [w.HANDLE, ctypes.c_int, pointer, w.DWORD])
    query_job = api('QueryInformationJobObject', [w.HANDLE, ctypes.c_int, pointer,
                                                 w.DWORD, pointer])
    assign = api('AssignProcessToJobObject', [w.HANDLE, w.HANDLE])
    terminate_job = api('TerminateJobObject', [w.HANDLE, w.UINT])
    terminate_process = api('TerminateProcess', [w.HANDLE, w.UINT])
    create_file = api('CreateFileW', [w.LPCWSTR, w.DWORD, w.DWORD, pointer,
                                     w.DWORD, w.DWORD, w.HANDLE], w.HANDLE)
    init_attributes = api('InitializeProcThreadAttributeList', [pointer, w.DWORD,
                                                               w.DWORD, ctypes.POINTER(size)])
    update_attributes = api('UpdateProcThreadAttribute', [pointer, w.DWORD, size,
                                                         pointer, size, pointer, pointer])
    delete_attributes = api('DeleteProcThreadAttributeList', [pointer], None)
    create_process = api('CreateProcessW', [w.LPCWSTR, w.LPWSTR, pointer, pointer,
                                          w.BOOL, w.DWORD, pointer, w.LPCWSTR,
                                          pointer, ctypes.POINTER(ProcessInfo)])
    resume = api('ResumeThread', [w.HANDLE], w.DWORD)
    wait = api('WaitForSingleObject', [w.HANDLE, w.DWORD], w.DWORD)
    get_exit = api('GetExitCodeProcess', [w.HANDLE, ctypes.POINTER(w.DWORD)])

    def checked(ok, operation):
        if not ok:
            error = ctypes.get_last_error()
            raise OSError(error, operation + ': ' + ctypes.FormatError(error))

    invalid_handle = ctypes.c_void_p(-1).value
    handles = []
    job = attrs = None
    attrs_ready = created = assigned = False
    process = ProcessInfo()
    try:
        job = create_job(None, None)
        checked(job, 'CreateJobObjectW')
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        checked(set_job(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)),
                'SetInformationJobObject')
        security = Security(ctypes.sizeof(Security), None, True)
        output = create_file(str(log), 0x40000000, 1 | 2, ctypes.byref(security),
                             2, 0x80, None)  # GENERIC_WRITE, CREATE_ALWAYS
        checked(output != invalid_handle and output, 'CreateFileW(log)')
        handles.append(output)
        stdin = create_file('NUL', 0x80000000, 1 | 2, ctypes.byref(security),
                            3, 0x80, None)  # GENERIC_READ, OPEN_EXISTING
        checked(stdin != invalid_handle and stdin, 'CreateFileW(NUL)')
        handles.append(stdin)
        required = size()
        init_attributes(None, 1, 0, ctypes.byref(required))
        checked(required.value > 0, 'InitializeProcThreadAttributeList(size)')
        attrs = ctypes.create_string_buffer(required.value)
        checked(init_attributes(attrs, 1, 0, ctypes.byref(required)),
                'InitializeProcThreadAttributeList')
        attrs_ready = True
        inherited = (w.HANDLE * 2)(stdin, output)
        checked(update_attributes(attrs, 0, 0x20002, inherited,
                                  ctypes.sizeof(inherited), None, None),
                'UpdateProcThreadAttribute(HANDLE_LIST)')
        startup = StartupEx()
        startup.StartupInfo.cb = ctypes.sizeof(StartupEx)
        startup.StartupInfo.dwFlags = 0x100 | 0x1  # Standard handles, hidden GUI startup.
        startup.StartupInfo.wShowWindow = 0
        startup.StartupInfo.hStdInput = stdin
        startup.StartupInfo.hStdOutput = startup.StartupInfo.hStdError = output
        startup.lpAttributeList = ctypes.cast(attrs, pointer)
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
        block = ctypes.create_unicode_buffer(
            '\0'.join(f'{key}={value}' for key, value in
                      sorted(env.items(), key=lambda pair: pair[0].upper())) + '\0\0')
        flags = 0x4 | 0x400 | 0x80000 | 0x08000000
        # CREATE_SUSPENDED | UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO | NO_WINDOW
        checked(create_process(argv[0], command, None, None, True, flags,
                               block, str(cwd), ctypes.byref(startup),
                               ctypes.byref(process)), 'CreateProcessW')
        created = True
        checked(assign(job, process.hProcess), 'AssignProcessToJobObject')
        assigned = True
        if time.monotonic() >= deadline:
            timed_out = True  # Never run a command after its setup exhausted the budget.
        else:
            checked(resume(process.hThread) != 0xffffffff, 'ResumeThread')
            remaining_ms = max(0, math.ceil((deadline - time.monotonic()) * 1000))
            waited = wait(process.hProcess, min(remaining_ms, 0xfffffffe))
            checked(waited in (0, 0x102), 'WaitForSingleObject')
            timed_out = waited == 0x102
        code = w.DWORD()
        if not timed_out:
            checked(get_exit(process.hProcess, ctypes.byref(code)), 'GetExitCodeProcess')
        # On both normal exit and timeout, stop background descendants before returning.
        checked(terminate_job(job, 124 if timed_out else 0), 'TerminateJobObject')
        cleanup_deadline = time.monotonic() + 5
        stopped = False
        while True:
            accounting = Accounting()
            checked(query_job(job, 1, ctypes.byref(accounting),
                              ctypes.sizeof(accounting), None),
                    'QueryInformationJobObject')
            if accounting.ActiveProcesses == 0:
                stopped = True
                break
            if time.monotonic() >= cleanup_deadline:
                break
            time.sleep(0.01)
        return {'exitCode': 124 if timed_out else code.value,
                'timedOut': timed_out, 'descendantsStopped': stopped}
    finally:
        # Failed assignment leaves a suspended uncontained process: terminate it directly.
        # Closing the job kills any assigned processes, including on Python exceptions.
        if created and not assigned:
            terminate_process(process.hProcess, 125)
            wait(process.hProcess, 5000)
        if job:
            close(job)
        if created:
            close(process.hThread)
            close(process.hProcess)
        if attrs_ready:
            delete_attributes(attrs)
        for handle in handles:
            close(handle)


def _posix(argv, cwd, env, log, deadline):
    with open(log, 'wb') as output:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=output, stderr=subprocess.STDOUT,
                                   start_new_session=True, close_fds=True)
        timed_out = False
        try:
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out = True
        finally:
            cleanup_deadline = time.monotonic() + 5
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            # Always reap the immediate child. Group existence may include zombies;
            # conservatively retain descendantsStopped=False until the group vanishes.
            try:
                process.wait(timeout=max(0, cleanup_deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
        stopped = False
        while True:
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                stopped = True
                break
            if time.monotonic() >= cleanup_deadline:
                break
            time.sleep(0.01)
        return {'exitCode': 124 if timed_out else process.returncode,
                'timedOut': timed_out, 'descendantsStopped': stopped}


def run_bounded(argv, cwd, env, log_path, seconds) -> dict:
    """Run an executable argv (no implicit shell); refuse invalid/unsupported setup.

    env is a complete child environment, or None to inherit a snapshot. Logs are
    binary combined stdout/stderr. Existing log files are replaced. Errors raise;
    descendantsStopped=False is never a successful containment result.
    """
    started = time.monotonic()
    if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('seconds must be finite and positive')
    if isinstance(argv, (str, bytes)) or not argv:
        raise ValueError('argv must be a nonempty executable argument sequence')
    argv = [os.fspath(arg) for arg in argv]
    if any(not isinstance(arg, str) or '\0' in arg for arg in argv):
        raise ValueError('argv must contain NUL-free strings')
    cwd = Path(cwd).resolve(strict=True)
    if not cwd.is_dir():
        raise ValueError('cwd must be a directory')
    child_env = dict(os.environ if env is None else env)
    if any(not isinstance(key, str) or not isinstance(value, str) or not key
           or '=' in key or '\0' in key or '\0' in value
           for key, value in child_env.items()):
        raise ValueError('environment must contain valid string keys and values')
    executable = argv[0]
    if os.path.dirname(executable):
        # Preserve proxy names such as cargo.exe -> rustup.exe: argv[0] selects
        # the proxy's operation. Resolving the final symlink changes its behavior.
        executable = os.path.abspath(os.path.join(cwd, executable))
    else:
        search_path = next((value for key, value in child_env.items() if key.upper() == 'PATH'), '')
        executable = shutil.which(executable, path=search_path)
    if not executable or not Path(executable).is_file():
        raise FileNotFoundError('executable not found: ' + argv[0])
    if os.name == 'nt' and Path(executable).suffix.lower() != '.exe':
        raise ValueError('Windows requires an explicit .exe; invoke script interpreters directly')
    argv[0] = executable
    log = Path(log_path).absolute()
    log.parent.mkdir(parents=True, exist_ok=True)
    deadline = started + seconds
    if os.name == 'nt':
        result = _windows(argv, cwd, child_env, log, deadline)
    elif os.name == 'posix':
        result = _posix(argv, cwd, child_env, log, deadline)
    else:
        raise RuntimeError('unsupported process containment platform: ' + os.name)
    result['elapsedSeconds'] = time.monotonic() - started
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', required=True, type=float)
    parser.add_argument('--cwd', required=True)
    parser.add_argument('--log', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    try:
        result = run_bounded(command, args.cwd, None, args.log, args.seconds)
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({'error': str(error), 'passed': False}))
        return 125
    print(json.dumps(result))
    if result['timedOut']:
        return 124
    if not result['descendantsStopped']:
        return 125
    return 0 if result['exitCode'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
