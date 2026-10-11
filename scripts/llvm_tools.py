"""Acquire matching Rust LLVM tools in a supplied cell; normalize LLVM coverage.

fetch launches a bounded 180-second worker; no global rustup state is changed.
It accepts only the official HTTPS Rust distribution, checks the versioned
manifest and component SHA-256, and bounds all downloaded bytes to 250 MiB.
Failed acquisition artifacts are retained for diagnosis, never silently reused.

report requires full llvm-cov export JSON (not --summary-only/--skip-functions).
Its line semantics follow LLVM 21 LineCoverageStats and must agree with the
exported per-file summary. Missing scoped maps are errors, including uncalled
production functions; callers must compile with full -C instrument-coverage.
Input source hashes must also match the caller's frozen build receipt.

References:
https://doc.rust-lang.org/rustc/instrument-coverage.html
https://llvm.org/docs/CommandGuide/llvm-cov.html
https://raw.githubusercontent.com/llvm/llvm-project/release/21.x/llvm/lib/ProfileData/Coverage/CoverageMapping.cpp
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import time
import tomllib
import urllib.parse
import urllib.request

DOWNLOAD_LIMIT = 250 * 1024 * 1024
EXPANDED_LIMIT = 1024 * 1024 * 1024
FETCH_SECONDS = 180
TARGET = 'x86_64-pc-windows-msvc'


def _sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _json_write(path, value):
    with open(path, 'x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def _official(url):
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme != 'https' or parts.hostname != 'static.rust-lang.org'
            or parts.port not in (None, 443) or parts.username or parts.password
            or not parts.path.startswith('/dist/') or parts.query or parts.fragment):
        raise ValueError('refused nonofficial Rust distribution URL')
    return url


class _OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, _official(newurl))


def _download(url, destination, remaining, deadline, per_file_limit):
    _official(url)
    opener = urllib.request.build_opener(_OfficialRedirect())
    timeout = min(10, deadline - time.monotonic())
    if timeout <= 0:
        raise TimeoutError('acquisition deadline exhausted')
    request = urllib.request.Request(url, headers={'User-Agent': 'Schematically-WS-LLVM/1'})
    total = 0
    digest = hashlib.sha256()
    with opener.open(request, timeout=timeout) as response:
        _official(response.geturl())
        if response.status != 200:
            raise ValueError('distribution response was not HTTP 200')
        advertised = response.headers.get('Content-Length')
        if advertised is not None and int(advertised) > min(remaining, per_file_limit):
            raise ValueError('distribution download exceeds declared byte ceiling')
        with open(destination, 'xb') as stream:
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError('acquisition deadline exhausted')
                chunk = response.read(min(1024 * 1024, remaining - total + 1,
                                          per_file_limit - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > remaining or total > per_file_limit:
                    raise ValueError('distribution download exceeds declared byte ceiling')
                stream.write(chunk)
                digest.update(chunk)
    return total, digest.hexdigest()


def _extract(archive, destination, deadline):
    destination.mkdir()
    total = 0
    files = 0
    seen = set()
    with tarfile.open(archive, mode='r:xz') as bundle:
        for member in bundle:
            if time.monotonic() >= deadline:
                raise TimeoutError('acquisition deadline exhausted during extraction')
            pure = PurePosixPath(member.name)
            parts = pure.parts
            if (pure.is_absolute() or not parts or '\\' in member.name
                    or any(part in ('', '.', '..') or ':' in part for part in parts)
                    or any(part.rstrip(' .') != part for part in parts)):
                raise ValueError('unsafe archive member path')
            # Avoid Windows device-name aliases even on a different host.
            if any(part.split('.')[0].upper() in {
                    'CON', 'PRN', 'AUX', 'NUL',
                    *[f'COM{i}' for i in range(1, 10)],
                    *[f'LPT{i}' for i in range(1, 10)]} for part in parts):
                raise ValueError('unsafe archive device name')
            key = '/'.join(parts).casefold()
            if key in seen:
                raise ValueError('duplicate archive member path')
            seen.add(key)
            path = destination.joinpath(*parts)
            if not path.resolve().is_relative_to(destination.resolve()):
                raise ValueError('archive path escaped installation directory')
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise ValueError('archive links/devices/special files are forbidden')
            files += 1
            total += member.size
            if member.size < 0 or files > 10000 or total > EXPANDED_LIMIT:
                raise ValueError('archive exceeds extraction ceiling')
            path.parent.mkdir(parents=True, exist_ok=True)
            source = bundle.extractfile(member)
            if source is None:
                raise ValueError('archive regular-file payload is absent')
            copied = 0
            with source, open(path, 'xb') as output:
                while True:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('acquisition deadline exhausted during extraction')
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    copied += len(chunk)
                    if copied > member.size:
                        raise ValueError('archive payload exceeded declared size')
                    output.write(chunk)
            if copied != member.size:
                raise ValueError('archive payload size mismatch')
    return {'files': files, 'bytes': total}


def _fetch_worker(version, target, out):
    started = time.monotonic()
    deadline = started + FETCH_SECONDS
    base = f'https://static.rust-lang.org/dist/channel-rust-{version}.toml'
    manifest_path = out / 'distribution.toml'
    checksum_path = out / 'distribution.toml.sha256'
    used, manifest_hash = _download(base, manifest_path, DOWNLOAD_LIMIT, deadline,
                                    4 * 1024 * 1024)
    count, _ = _download(base + '.sha256', checksum_path, DOWNLOAD_LIMIT - used,
                         deadline, 4096)
    used += count
    published = checksum_path.read_text(encoding='ascii').split()[0]
    if not re.fullmatch(r'[0-9a-fA-F]{64}', published) or manifest_hash != published.lower():
        raise ValueError('Rust manifest SHA-256 mismatch')
    manifest = tomllib.loads(manifest_path.read_text(encoding='utf-8'))
    if str(manifest.get('manifest-version')) != '2':
        raise ValueError('unsupported Rust distribution manifest version')
    rust_version = manifest['pkg']['rust']['version'].split()[0]
    component = manifest['pkg']['llvm-tools-preview']
    if rust_version != version or component['version'].split()[0] != version:
        raise ValueError('distribution version does not match requested compiler')
    package = component['target'][target]
    if package.get('available') is not True:
        raise ValueError('matching LLVM tools component is unavailable')
    archive_url = _official(package['xz_url'])
    expected = package['xz_hash']
    if not re.fullmatch(r'[0-9a-fA-F]{64}', expected):
        raise ValueError('component manifest lacks a valid SHA-256')
    archive = out / 'llvm-tools.tar.xz'
    count, archive_hash = _download(archive_url, archive, DOWNLOAD_LIMIT - used,
                                    deadline, DOWNLOAD_LIMIT - used)
    used += count
    if archive_hash != expected.lower():
        raise ValueError('LLVM tools archive SHA-256 mismatch')
    extracted = out / 'component'
    extraction = _extract(archive, extracted, deadline)
    tools = {}
    for name in ('llvm-cov.exe', 'llvm-profdata.exe'):
        candidates = list(extracted.rglob(name))
        candidates = [path for path in candidates
                      if path.parts[-4:] == ('rustlib', target, 'bin', name)]
        if len(candidates) != 1:
            raise ValueError('component does not provide exactly one matching ' + name)
        tools[name] = {'path': str(candidates[0].resolve()), 'sha256': _sha(candidates[0])}
    receipt = {
        'schema': 'schematically-llvm-acquisition@1',
        'completedAt': datetime.now(timezone.utc).isoformat(),
        'rustVersion': version, 'target': target,
        'manifest': {'url': base, 'path': str(manifest_path), 'sha256': manifest_hash,
                     'distributionDate': manifest.get('date')},
        'archive': {'url': archive_url, 'path': str(archive), 'sha256': archive_hash,
                    'bytes': count},
        'tools': tools, 'extraction': extraction,
        'limits': {'downloadBytes': DOWNLOAD_LIMIT, 'seconds': FETCH_SECONDS,
                   'expandedBytes': EXPANDED_LIMIT},
        'downloadedBytes': used, 'elapsedSeconds': time.monotonic() - started,
        'helperSha256': _sha(Path(__file__)),
    }
    if receipt['elapsedSeconds'] >= FETCH_SECONDS:
        raise TimeoutError('acquisition exhausted its elapsed ceiling')
    _json_write(out / 'acquisition.json', receipt)
    return receipt


def fetch_tools(version, target, out):
    """Acquire in a new or empty explicitly supplied directory; no executables run."""
    from bounded_process import run_bounded
    if not re.fullmatch(r'\d+\.\d+\.\d+', version) or target != TARGET:
        raise ValueError('requires an exact Rust semver and x86_64-pc-windows-msvc')
    out = Path(out)
    if not out.is_absolute():
        raise ValueError('out must be an absolute WS cell path')
    out = out.resolve()
    rustup_roots = [(Path.home() / '.rustup').resolve()]
    if os.environ.get('RUSTUP_HOME'):
        rustup_roots.append(Path(os.environ['RUSTUP_HOME']).resolve())
    if any(out.is_relative_to(root) for root in rustup_roots):
        raise ValueError('global rustup installation is forbidden')
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError('acquisition directory must be new or empty')
    out.mkdir(parents=True, exist_ok=True)
    argv = [sys.executable, str(Path(__file__).resolve()), '_fetch',
            '--version', version, '--target', target, '--out', str(out)]
    child_env = dict(os.environ)
    child_env['SCHEMATICALLY_LLVM_FETCH_PARENT'] = str(os.getpid())
    result = run_bounded(argv, Path(__file__).resolve().parent, child_env,
                         out / 'fetch.log', FETCH_SECONDS)
    _json_write(out / 'process.json', {'command': argv, **result})
    if result['exitCode'] != 0 or result['timedOut'] or not result['descendantsStopped']:
        raise RuntimeError('bounded acquisition failed; inspect retained fetch.log/process.json')
    receipt = json.loads((out / 'acquisition.json').read_text(encoding='utf-8'))
    receipt['processEvidence'] = str(out / 'process.json')
    return receipt


def _identity(path):
    return os.path.normcase(str(Path(path).resolve(strict=True)))


def _lines(segments, line_count):
    """LLVM21 LineCoverageStats/Iterator semantics, including skipped/gap regions."""
    if not isinstance(segments, list) or not segments:
        raise ValueError('scoped file has no LLVM segments')
    previous = (0, 0)
    previous_has_count = True
    for segment in segments:
        if (not isinstance(segment, list) or len(segment) != 6
                or any(type(value) is not int or value < 0 for value in segment[:3])
                or segment[0] < 1 or segment[1] < 1
                or any(type(value) is not bool for value in segment[3:])
                or tuple(segment[:2]) < previous
                or (tuple(segment[:2]) == previous and previous_has_count)
                or segment[0] > line_count + 1):
            raise ValueError('malformed/unsorted/out-of-source LLVM segment')
        previous = tuple(segment[:2])
        previous_has_count = segment[3]
    executable, hits = set(), set()
    wrapped = None
    index = 0
    for line in range(segments[0][0], segments[-1][0] + 1):
        current = []
        while index < len(segments) and segments[index][0] == line:
            current.append(segments[index])
            index += 1
        entries = [s for s in current if not s[5] and s[3] and s[4]]
        skipped = bool(current and not current[0][3] and current[0][4])
        mapped = (not skipped and (bool(wrapped and wrapped[3]) or bool(entries)))
        mapped = mapped or any(s[4] and s[3] for s in current)
        if mapped:
            if line > line_count:
                raise ValueError('executable LLVM segment outside source lines')
            executable.add(line)
            count = max([wrapped[2] if wrapped else 0, *[s[2] for s in entries]])
            if count > 0:
                hits.add(line)
        if current:
            wrapped = current[-1]
    return executable, hits


def _region_segments(regions):
    """LLVM21 CoverageMapping.cpp SegmentBuilder, for independent summaries.

    Regions are the full exported eight-field CountedRegion arrays. This
    reconstructs the producer's segments rather than inferring executable
    lines from source text or counting an enclosing function's entire span.
    """
    ordered = sorted((list(region) for region in regions),
                     key=lambda r: (r[0], r[1], -r[2], -r[3], r[7]))
    combined = []
    for region in ordered:
        if combined and combined[-1][:4] == region[:4]:
            if combined[-1][7] == region[7]:
                combined[-1][4] += region[4]
        else:
            combined.append(region)
    segments, active = [], []

    def start(region, loc, entry, skipped=False):
        has_count = not skipped and region[7] != 2
        if segments and not entry and not skipped:
            last = segments[-1]
            if last[3] == has_count and last[2] == region[4] and not last[4]:
                return
        segments.append([*loc, region[4] if has_count else 0,
                         has_count, entry, has_count and region[7] == 3])

    def complete(loc, first):
        active[first:] = sorted(active[first:], key=lambda r: tuple(r[2:4]))
        for index in range(first + 1, len(active)):
            current, previous = active[index], active[index - 1]
            end = tuple(previous[2:4])
            if loc is not None and end == loc:
                break
            if end == tuple(current[2:4]):
                continue
            for later in active[index + 1:]:
                if current[2:4] == later[2:4]:
                    current = later
            start(current, end, False)
        last = active[-1]
        if first and tuple(last[2:4]) != loc:
            start(active[first - 1], tuple(last[2:4]), False)
        elif not first and (loc is None or loc != tuple(last[2:4])):
            start(last, tuple(last[2:4]), False, True)
        del active[first:]

    for index, region in enumerate(combined):
        loc = tuple(region[:2])
        remaining = [r for r in active if tuple(r[2:4]) > loc]
        completed = [r for r in active if tuple(r[2:4]) <= loc]
        active[:] = remaining + completed
        if completed:
            complete(loc, len(remaining))
        gap = region[7] == 3
        if loc == tuple(region[2:4]):
            skipped = index + 1 == len(combined) or region[7] == 2
            start(active[-1] if active else region, loc, not gap, skipped)
            if skipped and active:
                start(active[-1], loc, False)
            continue
        if index + 1 == len(combined) or loc != tuple(combined[index + 1][:2]):
            start(region, loc, not gap)
        active.append(region)
    if active:
        complete(None, 0)
    return segments


def _function_summary(unit, filename, line_count):
    """Rebuild LLVM file summary's summed instantiation-group line measure.

    CoverageReport::prepareSingleFileReport sums function groups, so overlapping
    functions count a source line more than once. That is a different measure
    from the unique file segments used by our executable-line denominator.
    """
    groups, file_regions = {}, []
    for function in unit['functions']:
        filenames = function.get('filenames')
        if not isinstance(filenames, list) or filename not in filenames:
            continue
        regions = function.get('regions')
        if (not filenames or any(not isinstance(name, str) for name in filenames)
                or not isinstance(regions, list) or not regions
                or type(function.get('count')) is not int or function['count'] < 0):
            raise ValueError('malformed scoped LLVM function/region map')
        for region in regions:
            if (not isinstance(region, list) or len(region) != 8
                    or any(type(value) is not int or value < 0 for value in region)
                    or any(value < 1 for value in region[:4])
                    or tuple(region[:2]) > tuple(region[2:4])
                    or region[5] >= len(filenames) or region[6] >= len(filenames)
                    or region[7] not in (0, 1, 2, 3)):
                raise ValueError('malformed/unsupported scoped LLVM counted region')
        file_ids = {i for i, name in enumerate(filenames) if name == filename}
        file_regions.extend(r for r in regions if r[5] in file_ids)
        expanded = {r[6] for r in regions if r[7] == 1}
        main_ids = set(range(len(filenames))) - expanded
        if not main_ids:
            continue
        main_id = min(main_ids)
        if filenames[main_id] != filename:
            continue
        main_regions = [r for r in regions if r[5] == main_id]
        if not main_regions:
            raise ValueError('LLVM function main view has no region')
        executable, hits = _lines(_region_segments(main_regions), line_count)
        group = tuple(main_regions[0][:2])
        previous = groups.get(group, (0, 0, 0))
        groups[group] = (max(previous[0], len(executable)),
                         max(previous[1], len(hits)), previous[2] + function['count'])
    if not groups or not file_regions:
        raise ValueError('missing scoped LLVM instantiation groups')
    return {'count': sum(value[0] for value in groups.values()),
            'covered': sum(value[1] for value in groups.values()),
            'functions': len(groups),
            'coveredFunctions': sum(value[2] > 0 for value in groups.values()),
            'segments': _region_segments(file_regions)}


def normalize_export(export, scope):
    """Return complete scoped Rust line coverage; fail any missing map/summary."""
    if not isinstance(scope, list) or not scope:
        raise ValueError('scope must be a nonempty array of absolute Rust paths')
    paths = []
    for value in scope:
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError('scope contains a nonabsolute source path')
        path = Path(value).resolve(strict=True)
        if path.suffix != '.rs' or not path.is_file():
            raise ValueError('scope must contain Rust source files')
        paths.append(path)
    if len({_identity(path) for path in paths}) != len(paths):
        raise ValueError('duplicate scoped Rust source')
    if (not isinstance(export, dict) or export.get('type') != 'llvm.coverage.json.export'
            or export.get('version') not in ('2.0.1', '3.0.1')
            or not isinstance(export.get('data'), list) or not export['data']):
        raise ValueError('unsupported LLVM JSON export')
    wanted = {_identity(path) for path in paths}
    records = {key: [] for key in wanted}
    functions = {key: [] for key in wanted}
    for unit in export['data']:
        if not isinstance(unit.get('files'), list) or not isinstance(unit.get('functions'), list):
            raise ValueError('requires full file segments and function export')
        for record in unit['files']:
            filename = record.get('filename')
            if not isinstance(filename, str) or not Path(filename).is_absolute():
                continue
            # Unrelated dependency/macros may name source unavailable on this host.
            key = os.path.normcase(str(Path(filename).resolve()))
            if key in wanted:
                records[key].append((record, unit))
        for function in unit['functions']:
            filenames = function.get('filenames', [])
            for filename in set(filenames):
                if not Path(filename).is_absolute():
                    continue
                key = os.path.normcase(str(Path(filename).resolve()))
                if key in wanted:
                    if type(function.get('count')) is not int or function['count'] < 0:
                        raise ValueError('malformed LLVM function count')
                    functions[key].append({'name': function.get('name'),
                                           'count': function['count']})
    files = []
    for path in paths:
        key = _identity(path)
        if not records[key] or not functions[key]:
            raise ValueError('missing full scoped LLVM map: ' + str(path))
        source = path.read_bytes()
        line_count = len(source.decode('utf-8').splitlines())
        all_lines, hit_lines = set(), set()
        reported_summaries = []
        for record, unit in records[key]:
            executable, hits = _lines(record.get('segments'), line_count)
            summary = record.get('summary', {}).get('lines', {})
            reconstructed = _function_summary(unit, record['filename'], line_count)
            if reconstructed['segments'] != record['segments']:
                raise ValueError('full function regions disagree with LLVM file segments: ' + str(path))
            function_summary = record.get('summary', {}).get('functions', {})
            if (type(summary.get('count')) is not int or type(summary.get('covered')) is not int
                    or type(function_summary.get('count')) is not int
                    or type(function_summary.get('covered')) is not int
                    or summary['count'] != reconstructed['count']
                    or summary['covered'] != reconstructed['covered']
                    or function_summary.get('count') != reconstructed['functions']
                    or function_summary.get('covered') != reconstructed['coveredFunctions']):
                raise ValueError('reconstructed function groups disagree with LLVM summary: ' + str(path))
            reported_summaries.append({'count': summary['count'], 'covered': summary['covered'],
                'basis': 'LLVM sum of function instantiation-group line counts; source lines may repeat'})
            all_lines.update(executable)
            hit_lines.update(hits)
        if not all_lines:
            raise ValueError('scoped Rust file has no executable coverage map: ' + str(path))
        files.append({'file': str(path), 'sourceHash': hashlib.sha256(source).hexdigest(),
                      'executableLines': sorted(all_lines), 'hitLines': sorted(hit_lines),
                      'missedFunctions': [f for f in functions[key] if f['count'] == 0],
                      'llvmReportedLineSummaries': reported_summaries,
                      'functionMapCount': len(functions[key])})
    total = sum(len(file['executableLines']) for file in files)
    covered = sum(len(file['hitLines']) for file in files)
    return {'schema': 'schematically-llvm-coverage@1', 'language': 'Rust',
            'measure': 'LLVM21 unique file LineCoverageStats; full regions and function-group summaries checked independently',
            'exportVersion': export['version'], 'files': files,
            'executableLineCount': total, 'hitLineCount': covered,
            'coveragePercent': covered * 100 / total}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('fetch', '_fetch'):
        command = commands.add_parser(name)
        command.add_argument('--version', required=True)
        command.add_argument('--target', required=True)
        command.add_argument('--out', required=True)
    report = commands.add_parser('report')
    report.add_argument('--export', required=True, dest='export_path')
    report.add_argument('--scope', required=True, help='JSON array or path to JSON array file')
    report.add_argument('--out', required=True, help='new JSON report file')
    args = parser.parse_args()
    try:
        if args.command == 'fetch':
            result = fetch_tools(args.version, args.target, args.out)
        elif args.command == '_fetch':
            # Private worker is launched only by fetch_tools through its supervisor.
            if os.environ.get('SCHEMATICALLY_LLVM_FETCH_PARENT') != str(os.getppid()):
                raise RuntimeError('private acquisition worker requires its supervising parent')
            result = _fetch_worker(args.version, args.target, Path(args.out).resolve())
        else:
            export_path = Path(args.export_path).resolve(strict=True)
            if export_path.stat().st_size > 128 * 1024 * 1024:
                raise ValueError('LLVM export exceeds input ceiling')
            scope = json.loads(args.scope if args.scope.lstrip().startswith('[')
                               else Path(args.scope).read_text(encoding='utf-8'))
            result = normalize_export(json.loads(export_path.read_text(encoding='utf-8')), scope)
            result['exportSha256'] = _sha(export_path)
            result['helperSha256'] = _sha(Path(__file__))
            out = Path(args.out).absolute()
            out.parent.mkdir(parents=True, exist_ok=True)
            _json_write(out, result)
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, tarfile.TarError) as error:
        print(json.dumps({'error': str(error), 'passed': False}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
