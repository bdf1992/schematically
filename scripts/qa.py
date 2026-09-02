#!/usr/bin/env python3
"""Single authoritative RC QA runner used locally and in CI."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]

STATIC=[
    'tests/dimensional_form_qa.py',
    'tests/pre_repo_hardening_qa.py',
    'tests/author_offline_qa.py',
    'tests/file_load_presets_qa.py',
    'tests/file_load_wire_canvas_qa.py',
    'tests/desktop_shell_qa.py',
]
BROWSER=[
    'tests/attachment_point_refactor_qa.py',
    'tests/configurable_attachment_defaults_qa.py',
    'tests/primitive_forms_qa.py',
    'tests/document_compaction_qa.py',
    'tests/carrier_path_qa.py',
    'tests/attachment_interaction_parity_qa.py',
    'tests/attachment_growth_direction_qa.py',
    'tests/attachment_terminal_identity_qa.py',
    'tests/boundary_legality_qa.py',
    'tests/read_write_access_qa.py',
    'tests/wire_host_inline_qa.py',
    'tests/host_surface_qa.py',
    'tests/local_surface_wires_qa.py',
    'tests/plane_boundary_routing_qa.py',
    'tests/tray_settle_qa.py',
    'tests/beta20_ports_history_qa.py',
    'tests/grid_visibility_qa.py',
    'tests/editor_kernel_qa.py',
    'tests/editor_kernel_extended_qa.py',
    'tests/file_surface_qa.py',
    'tests/svg_export_qa.py',
    'tests/loop_svg_qa.py',
    'tests/menu_dismissal_qa.py',
    'tests/appearance_history_qa.py',
    'tests/agent_api_mcp_golden_qa.py',
    'tests/skills_conformance_qa.py',
    'tests/render_idempotence_qa.py',
    'tests/drag_lifecycle_stress_qa.py',
    'tests/performance_regression_qa.py',
]
TAIL=[
    'tests/mutation_watch.py',
    'scripts/golden_run.py',
]

def run(path:str)->float:
    start=time.perf_counter()
    subprocess.run([sys.executable,str(ROOT/path)],cwd=ROOT,check=True)
    elapsed=time.perf_counter()-start
    print(f'QA PASS {path} ({elapsed:.2f}s)',flush=True)
    return elapsed

def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--quick',action='store_true',help='Skip stress/performance browser tests.')
    args=parser.parse_args()
    subprocess.run([sys.executable,str(ROOT/'build.py')],cwd=ROOT,check=True)
    browser=BROWSER if not args.quick else [p for p in BROWSER if p not in {'tests/drag_lifecycle_stress_qa.py','tests/performance_regression_qa.py'}]
    total=0.0
    for path in [*STATIC,*browser,*TAIL]: total+=run(path)
    # Node syntax is intentionally part of the same local/CI contract.
    js=[*sorted((ROOT/'src').glob('*.js')),*sorted((ROOT/'mcp').glob('*.mjs'))]
    for path in js:
        subprocess.run(['node','--check',str(path)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    print(f'RC QA PASS: {len(STATIC)+len(browser)+len(TAIL)} suites + {len(js)} JS syntax checks ({total:.2f}s test time)')
    return 0

if __name__=='__main__': raise SystemExit(main())
