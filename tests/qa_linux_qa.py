"""scripts/qa_linux.py: argv, exit codes and the inside half, with no browser and no Docker."""
import contextlib
import importlib.util
import io
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('qa_linux', ROOT / 'scripts/qa_linux.py')
ql = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ql)

checks = []


def check(name, cond):
    checks.append((name, bool(cond)))
    if not cond:
        raise AssertionError(name)


def call(argv, runner):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = ql.main(argv, runner)
    return code, out.getvalue(), err.getvalue()


def boom(*a, **k):
    raise AssertionError('the runner must not be called')


req = (ROOT / 'requirements-dev.txt').read_text(encoding='utf-8')
pin = re.search(r'^playwright==(\S+)$', req, re.M).group(1)
dockerfile = (ROOT / 'scripts/qa_linux.Dockerfile').read_text(encoding='utf-8')
qa_py = (ROOT / 'scripts/qa.py').read_text(encoding='utf-8')

# image base tag and the Dockerfile's build argument
check('pin parsed from requirements-dev.txt', ql.playwright_pin(ROOT) == pin)
check('base tag is v + pin + -noble', ql.base_tag(pin) == f'v{pin}-noble')
froms = [l for l in dockerfile.splitlines() if l.startswith('FROM ')]
check('final FROM uses the build argument',
      froms[-1] == 'FROM mcr.microsoft.com/playwright/python:v${PLAYWRIGHT_VERSION}-noble')
check('ARG before the first FROM', dockerfile.splitlines()[0] == 'ARG PLAYWRIGHT_VERSION')
check('image tag is 12 hex digits', re.fullmatch(r'[0-9a-f]{12}', ql.image_tag(ROOT)))

# default suites
check('default suites are the four font suites', ql.DEFAULT_SUITES == [
    'tests/layouts_qa.py', 'tests/layout_quality_qa.py',
    'tests/authoring_review_qa.py', 'tests/golden_rendered_text_qa.py'])
for s in ql.DEFAULT_SUITES:
    check(f'{s} exists', (ROOT / s).is_file())
    check(f'{s} is listed in scripts/qa.py', f"'{s}'" in qa_py)
check('qa_linux_qa.py is listed in STATIC', "'tests/qa_linux_qa.py'" in qa_py.split('BROWSER=')[0])

# run argv: two read-only mounts, nothing writable
argv = ql.run_argv('img:tag', ROOT, ql.DEFAULT_SUITES)
mounts = [argv[i + 1] for i, a in enumerate(argv) if a == '--mount']
check('two mounts', len(mounts) == 2)
check('every mount is a read-only bind', all(m.startswith('type=bind,') and m.endswith(',readonly') for m in mounts))
check('tree at /src', any(f'target=/src,' in m for m in mounts))
check('script at /qa_linux.py', any('target=/qa_linux.py,' in m for m in mounts))
check('no -v writable mount', '-v' not in argv and '--volume' not in argv)
check('inside command follows the image', argv[-len(ql.DEFAULT_SUITES) - 4:-len(ql.DEFAULT_SUITES)]
      == ['img:tag', 'python3', '/qa_linux.py', '--inside'])

# --print-command calls nothing
code, out, err = call(['--print-command'], boom)
check('--print-command exits 0', code == 0)
printed = __import__('json').loads(out)
check('--print-command names image, build and run',
      printed['image'].startswith('schematically-qa-linux:') and printed['build'][:2] == ['docker', 'build']
      and printed['run'][:2] == ['docker', 'run'])

# a missing suite exits 2 before docker is called
code, out, err = call(['--suite', 'tests/no_such_qa.py'], boom)
check('missing suite exits 2', code == 2 and 'tests/no_such_qa.py' in err)


def host_runner(version=0, inspect=0, final=0):
    calls = []

    def runner(argv, quiet=False, cwd=None):
        calls.append(argv)
        if argv[:2] == ['docker', 'version']:
            return version
        if argv[:3] == ['docker', 'image', 'inspect']:
            return inspect
        if argv[:2] == ['docker', 'run']:
            return final
        return 0
    runner.calls = calls
    return runner


r = host_runner(version=1)
code, out, err = call([], r)
check('no engine exits 2', code == 2)
check('no engine prints the start line',
      'Docker engine not reachable; start Docker Desktop with docker desktop start' in err + out)
check('no engine runs nothing else', all(c[:2] == ['docker', 'version'] for c in r.calls))

for final, want in ((0, 0), (1, 1), (125, 2)):
    r = host_runner(final=final)
    code, out, err = call([], r)
    check(f'container exit {final} gives {want}', code == want)
    check(f'container exit {final} builds nothing when the image is present',
          not any(c[:2] == ['docker', 'build'] for c in r.calls))

r = host_runner(inspect=1)
call([], r)
check('absent image is built before the run', [c[1] for c in r.calls if c[0] == 'docker'][-2:] == ['build', 'run'])

# the inside half: the second of three suites fails, the third still runs
suites = ['tests/a_qa.py', 'tests/b_qa.py', 'tests/c_qa.py']
ran = []


def inside_runner(argv, quiet=False, cwd=None):
    ran.append(argv)
    return 1 if argv == ['python3', 'tests/b_qa.py'] else 0


code, out, err = call(['--inside', *[x for s in suites for x in ('--suite', s)]], inside_runner)
check('inside returns 1 when a suite fails', code == 1)
check('the suite after the failure still ran', ['python3', 'tests/c_qa.py'] in ran)
check('two QA PASS lines', len(re.findall(r'^QA PASS tests/\w+\.py \(\d+\.\d\ds\)$', out, re.M)) == 2)
check('one QA FAIL line', len(re.findall(r'^QA FAIL tests/b_qa\.py \(exit 1, \d+\.\d\ds\)$', out, re.M)) == 1)
check('last line counts the failure', out.splitlines()[-1] == 'LINUX QA FAIL: 1 of 3 suites')
check('both fc-match lines are asked', ['fc-match', 'sans-serif'] in ran and ['fc-match', 'system-ui'] in ran)
check('build.py runs before the suites', ran.index(['python3', 'build.py']) < ran.index(['python3', 'tests/a_qa.py']))
check('the copy leaves out .git', any('--exclude=./.git' in ' '.join(c) for c in ran))

ran.clear()
code, out, err = call(['--inside', '--suite', 'tests/a_qa.py'], lambda *a, **k: 0)
check('inside passes when all pass', code == 0 and out.splitlines()[-1] == 'LINUX QA PASS: 1 suites')

# no playwright pin
with tempfile.TemporaryDirectory() as d:
    (Path(d) / 'requirements-dev.txt').write_text('PyYAML==6.0.1\n', encoding='utf-8', newline='\n')
    code, out, err = call(['--tree', d], boom)
    check('no pin exits 2', code == 2)

print(f'PASS {len(checks)} checks')
