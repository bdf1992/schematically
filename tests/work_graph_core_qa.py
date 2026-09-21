"""Native graph projection and observation contracts, including defeating cases."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
subprocess.run(['node',str(ROOT/'tests/work_graph_core.test.cjs')],cwd=ROOT,check=True)
