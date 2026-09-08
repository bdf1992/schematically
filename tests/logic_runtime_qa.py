"""Run the shared runtime's deterministic golden and defeating cases."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
subprocess.run(['node',str(ROOT/'tests/logic_runtime_qa.mjs')],cwd=ROOT,check=True)
