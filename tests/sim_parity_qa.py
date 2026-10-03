"""Sim parity QA (contract 08 of the one-runtime plan): dev's sim-facing suites on the state-space engine.

tests/graph_core_qa.py, tests/notation_qa.py and tests/section_exposure_qa.py run unchanged, each
with NODE_OPTIONS=--require tests/sim_surface_shim.js, which replaces src/07-graph-core.js's
createSimulation, runScenario, createSession and tools with src/07-state-surface.js's. Every node
process those suites start sees the surface; section_exposure_qa's browser part still runs the page's
own graph core until contract 09 points the canvas at the surface. Passes when all three pass.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHIM = (ROOT / 'tests' / 'sim_surface_shim.js').resolve()
SUITES = ['tests/graph_core_qa.py', 'tests/notation_qa.py', 'tests/section_exposure_qa.py']


def main() -> None:
    env = dict(os.environ)
    # The path is quoted so a space in it survives NODE_OPTIONS' own word splitting.
    env['NODE_OPTIONS'] = (env.get('NODE_OPTIONS', '') + f' --require "{SHIM.as_posix()}"').strip()
    failed = []
    for suite in SUITES:
        proc = subprocess.run([sys.executable, suite], cwd=ROOT, env=env, capture_output=True, text=True)
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-12:]
        print(f"{'PASS' if proc.returncode == 0 else 'FAIL'} {suite}")
        if proc.returncode != 0:
            failed.append(suite)
            print('\n'.join('    ' + line for line in tail))
    if failed:
        raise SystemExit(f'SIM PARITY FAIL: {len(failed)} of {len(SUITES)} suites fail on the state-space surface: {", ".join(failed)}')
    print(f'SIM PARITY PASS: {len(SUITES)} dev suites on the state-space surface')


if __name__ == '__main__':
    main()
