"""Check the Work Engine sample: sample.sov, sample.svg and gaps.json.

Run from the repository root: python docs/workengine/check_sample.py
Exits 0 when every check passes, 1 otherwise. Standard library only.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

NAMES = [
    "Case",
    "Recording",
    "Anchor",
    "Contribution",
    "Surface registration",
    "Web booth",
    "Delivery broker",
    "Foundry render engine",
    "Continuity records move from JSON files to a transactional SQLite store",
    "Web booth feeds Recording",
]
KEYS = {"id", "capability", "tried", "workaround", "severity", "source_files", "task_objective"}


def main() -> int:
    problems = []

    sov_path = HERE / "sample.sov"
    try:
        sov_text = sov_path.read_text(encoding="utf-8")
        json.loads(sov_text)
    except (OSError, ValueError) as exc:
        problems.append(f"sample.sov does not parse as JSON: {exc}")
        sov_text = ""
    for name in NAMES:
        if name not in sov_text:
            problems.append(f"sample.sov lacks the name {name!r}")

    svg_path = HERE / "sample.svg"
    if not svg_path.is_file():
        problems.append("sample.svg does not exist")
    else:
        svg_text = svg_path.read_text(encoding="utf-8")
        for name in NAMES:
            if name not in svg_text:
                problems.append(f"sample.svg lacks the name {name!r}")

    try:
        gaps = json.loads((HERE / "gaps.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        problems.append(f"gaps.json does not parse: {exc}")
        gaps = None
    if not isinstance(gaps, list) or not gaps:
        problems.append("gaps.json is not a non-empty list")
        gaps = []
    for i, gap in enumerate(gaps):
        if not isinstance(gap, dict):
            problems.append(f"gaps.json entry {i} is not an object")
            continue
        missing = KEYS - gap.keys()
        if missing:
            problems.append(f"gaps.json {gap.get('id', i)} lacks keys {sorted(missing)}")
        files = gap.get("source_files")
        if not isinstance(files, list):
            problems.append(f"gaps.json {gap.get('id', i)} source_files is not a list")
            continue
        for rel in files:
            if not (ROOT / rel).exists():
                problems.append(f"gaps.json {gap.get('id', i)} names a path that does not exist: {rel}")

    if problems:
        for p in problems:
            print("FAIL", p)
        return 1
    print(f"ok  sample.sov, sample.svg: {len(NAMES)} names; gaps.json: {len(gaps)} gaps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
