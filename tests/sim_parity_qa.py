"""Sim parity QA (contract 08 of the one-runtime plan): dev's sim-facing suites on the state-space engine.

tests/graph_core_qa.py, tests/notation_qa.py and tests/section_exposure_qa.py run unchanged, each
with NODE_OPTIONS=--require tests/sim_surface_shim.js, which replaces src/07-graph-core.js's
createSimulation, runScenario, createSession and tools with src/07-state-surface.js's. Every node
process those suites start sees the surface; section_exposure_qa's browser part still runs the page's
own graph core until contract 09 points the canvas at the surface.

One assertion is a named, intended difference: graph_core_qa.py:163, planeDoc(acl,0), where an
anonymous lever and a principalled one drive the Vault door in the same tick. The graph core takes
the arrival scheduled last (the anonymous one) and refuses it at the door; the state-space engine
merges same-tick level arrivals by a seeded draw recorded in the run's ledger (STATE-SPACE.md,
Settled item 15, Intended differences from the graph core). So graph_core_qa passes here when it
passes or fails at exactly that line, and the rest of its script, with that one line replaced by a
check that the run agrees with its own recorded draw, passes. Any other failure fails this suite.
"""
from __future__ import annotations
import ast
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHIM = (ROOT / 'tests' / 'sim_surface_shim.js').resolve()
GRAPH_CORE = 'tests/graph_core_qa.py'
SUITES = [GRAPH_CORE, 'tests/notation_qa.py', 'tests/section_exposure_qa.py']

# The one expected difference: its location and its exact text, so a moved or edited line is noticed.
EXPECTED_LINE = 163
EXPECTED_TEXT = (" {const {sim:s2}=G.createSimulation(planeDoc(acl,0));s2.run();assert.ok(s2.refusals().some(r=>r.level&&"
                 "r.node==='door'&&/anonymously/.test(r.reason)),'anonymous level refused at the door');"
                 "assert.equal(s2.levels().inside.value,0)}")
EXPECTED_MESSAGE = 'anonymous level refused at the door'
# In its place: for several seeds, the door refuses the anonymous level exactly when the run's
# recorded draw at the door puts the anonymous lever's wire (k4) last, the inside level stays 0
# either way, and the seeds exercise both draw outcomes. The default seed is one of them.
DRAW_CHECK = (" {const drawn=seed=>{const {sim:s2}=G.createSimulation(planeDoc(acl,0),seed===undefined?{}:{seed});s2.run();"
              "const draw=s2.currentRun().ledger.find(e=>e.kind==='draw'&&e.body.entity==='door');"
              "assert.ok(draw,'the run records a draw at the door');assert.deepEqual([...draw.body.order].sort(),['k3','k4']);"
              "const refused=s2.refusals().some(r=>r.level&&r.node==='door'&&/anonymously/.test(r.reason));"
              "assert.equal(refused,draw.body.order.at(-1)==='k4','the door refuses the anonymous level exactly when the recorded draw puts k4 last');"
              "assert.equal(s2.levels().inside.value,0);return draw.body.order.at(-1)};"
              "const lasts=[undefined,'0','1','2','3','4','5'].map(drawn);"
              "assert.equal(lasts[0],lasts[1],'the default seed is seed 0');"
              "assert.deepEqual([...new Set(lasts)].sort(),['k3','k4'],'the seeds exercise both draw outcomes')}")


def shim_env() -> dict[str, str]:
    env = dict(os.environ)
    # The path is quoted so a space in it survives NODE_OPTIONS' own word splitting.
    env['NODE_OPTIONS'] = (env.get('NODE_OPTIONS', '') + f' --require "{SHIM.as_posix()}"').strip()
    return env


def error_line(out: str) -> str:
    """The thrown error's own line (AssertionError [ERR_ASSERTION]: ...), else the start of the output."""
    return next((t.strip() for t in out.splitlines() if re.match(r'\s*\w*Error\b', t)), out.strip()[:300])


def graph_core_script() -> tuple[str, int]:
    """graph_core_qa.py's SCRIPT and the file line its first script line sits on."""
    tree = ast.parse((ROOT / GRAPH_CORE).read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SCRIPT' for t in node.targets):
            return node.value.value, node.value.lineno
    raise SystemExit(f'SIM PARITY FAIL: {GRAPH_CORE} has no SCRIPT')


def check_graph_core(env: dict[str, str], proc: subprocess.CompletedProcess) -> list[str]:
    """Problems with graph_core_qa on the surface; empty when only the named difference differs."""
    problems = []
    script, first = graph_core_script()
    lines = script.split('\n')
    index = EXPECTED_LINE - first
    if not (0 <= index < len(lines)) or lines[index] != EXPECTED_TEXT:
        return [f'{GRAPH_CORE}:{EXPECTED_LINE} is no longer the planeDoc(acl,0) assertion this suite names']
    if proc.returncode != 0:
        out = proc.stdout + proc.stderr
        frame = re.search(r'at \[eval\]:(\d+):\d+', out)
        line = first + int(frame.group(1)) - 1 if frame else None
        if 'AssertionError' not in out or EXPECTED_MESSAGE not in out or line != EXPECTED_LINE:
            problems.append(f'{GRAPH_CORE} fails at line {line}, not only at the named difference (line {EXPECTED_LINE}): {error_line(out)}')
            return problems
        print(f'    expected difference: {GRAPH_CORE}:{EXPECTED_LINE} ({EXPECTED_MESSAGE}), STATE-SPACE.md Settled item 15')
    # The rest of the script, with the named line replaced by the draw check, must pass.
    lines[index] = DRAW_CHECK
    rest = subprocess.run(['node', '-e', '\n'.join(lines)], cwd=ROOT, env=env, capture_output=True, text=True)
    if rest.returncode != 0 or 'GRAPH CORE PASS' not in rest.stdout:
        out = rest.stdout + rest.stderr
        frame = re.search(r'at \[eval\]:(\d+):\d+', out)
        problems.append(f'{GRAPH_CORE} with line {EXPECTED_LINE} as the draw check fails at line '
                        f'{first + int(frame.group(1)) - 1 if frame else None}: {error_line(out)}')
    else:
        print(f'    {GRAPH_CORE} passes with line {EXPECTED_LINE} checked against the run\'s recorded draw')
    return problems


def main() -> None:
    env = shim_env()
    failed = []
    for suite in SUITES:
        proc = subprocess.run([sys.executable, suite], cwd=ROOT, env=env, capture_output=True, text=True)
        if suite == GRAPH_CORE:
            problems = check_graph_core(env, proc)
            print(f"{'FAIL' if problems else 'PASS'} {suite}")
            for p in problems:
                print('    ' + p)
            if problems:
                failed.append(suite)
            continue
        print(f"{'PASS' if proc.returncode == 0 else 'FAIL'} {suite}")
        if proc.returncode != 0:
            tail = (proc.stdout + proc.stderr).strip().splitlines()[-12:]
            failed.append(suite)
            print('\n'.join('    ' + line for line in tail))
    if failed:
        raise SystemExit(f'SIM PARITY FAIL: {len(failed)} of {len(SUITES)} suites fail on the state-space surface: {", ".join(failed)}')
    print(f'SIM PARITY PASS: {len(SUITES)} dev suites on the state-space surface, one named difference ({GRAPH_CORE}:{EXPECTED_LINE})')


if __name__ == '__main__':
    main()
