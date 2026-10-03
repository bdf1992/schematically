"""Sim parity QA (contract 08 of the one-runtime plan): dev's sim-facing suites on the state-space engine.

tests/graph_core_qa.py, tests/notation_qa.py and tests/section_exposure_qa.py run unchanged, each
with NODE_OPTIONS=--require tests/sim_surface_shim.js, which replaces src/07-graph-core.js's
createSimulation, runScenario, createSession and tools with src/07-state-surface.js's (a no-op by
contract 09 of the one-runtime plan, which made that replacement the graph core's own code: the
shim stays so this suite still names what it is proving). section_exposure_qa's browser part still
runs the page's own graph core, which now points at the surface too (contract 09).

Contract 08 named one difference here, graph_core_qa.py:163 (planeDoc(acl,0), an anonymous lever
and a principalled one driving the Vault door in the same tick): the state-space engine merges
same-tick level arrivals by a seeded draw recorded in the run's ledger (STATE-SPACE.md, Settled
item 15), where the retired message engine always took the arrival scheduled last. Contract 09
rewrote that assertion to check the run's own recorded draw instead of a fixed outcome, so all
three suites now pass on the surface with no exception.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHIM = (ROOT / 'tests' / 'sim_surface_shim.js').resolve()
SUITES = ['tests/graph_core_qa.py', 'tests/notation_qa.py', 'tests/section_exposure_qa.py']


def shim_env() -> dict[str, str]:
    env = dict(os.environ)
    # The path is quoted so a space in it survives NODE_OPTIONS' own word splitting.
    env['NODE_OPTIONS'] = (env.get('NODE_OPTIONS', '') + f' --require "{SHIM.as_posix()}"').strip()
    return env


def main() -> None:
    env = shim_env()
    failed = []
    for suite in SUITES:
        proc = subprocess.run([sys.executable, suite], cwd=ROOT, env=env, capture_output=True, text=True)
        print(f"{'PASS' if proc.returncode == 0 else 'FAIL'} {suite}")
        if proc.returncode != 0:
            tail = (proc.stdout + proc.stderr).strip().splitlines()[-12:]
            failed.append(suite)
            print('\n'.join('    ' + line for line in tail))
    if failed:
        raise SystemExit(f'SIM PARITY FAIL: {len(failed)} of {len(SUITES)} suites fail on the state-space surface: {", ".join(failed)}')
    print(f'SIM PARITY PASS: {len(SUITES)} dev suites on the state-space surface, no exception')


if __name__ == '__main__':
    main()
