"""The run-artifact directory every QA suite writes its byproducts into, outside the working tree.

Known method: pytest's `tmp_path`/`basetemp` and Playwright's `--output-dir` both keep a run's
byproducts out of the source tree; `out_dir()` is the same idea for this repo's own QA suites.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ENV_VAR = "SCHEMATIC_QA_OUT"

TRACKED_ARTIFACTS = (
    "tests/beta17-read-write.png",
    "tests/beta18-inline-wire.png",
    "tests/file-menu.png",
    "tests/saved-test.sov",
    "tests/saved-test.sovpak",
)

# Text any of the three writer suites still carrying means they write into ROOT/tests again.
_FORBIDDEN_SNIPPETS = (
    "ROOT/'tests'/'saved-test",
    "ROOT/'tests'/'file-menu",
    "ROOT/'tests/beta",
)

_SUITES_TO_SCAN = (
    "tests/file_surface_qa.py",
    "tests/read_write_access_qa.py",
    "tests/wire_host_inline_qa.py",
)


def out_dir() -> Path:
    """The directory this run's byproducts belong in: `SCHEMATIC_QA_OUT` when set, else a
    `schematically-qa` directory under `tempfile.gettempdir()` - so a suite run on its own, with
    no parent process setting the environment variable, still writes outside the tree."""
    configured = os.environ.get(ENV_VAR)
    path = Path(configured) if configured else Path(tempfile.gettempdir()) / "schematically-qa"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _git_porcelain_status() -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", *TRACKED_ARTIFACTS],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _modified_tracked_artifacts() -> list[str]:
    modified = []
    for line in _git_porcelain_status().splitlines():
        line = line.strip()
        if not line:
            continue
        path = line.split(maxsplit=1)[1] if " " in line else line
        modified.append(path)
    return modified


def _suites_still_writing_into_tree() -> list[str]:
    offenders = []
    for rel in _SUITES_TO_SCAN:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if any(snippet in text for snippet in _FORBIDDEN_SNIPPETS):
            offenders.append(rel)
    return offenders


def check() -> int:
    """`python tests/qa_out.py --check`'s body: exit 1 if a tracked artifact shows modified in the
    repository status, or if a writer suite still names the old in-tree path; 0 and a report of what
    was checked otherwise."""
    modified = _modified_tracked_artifacts()
    offenders = _suites_still_writing_into_tree()
    print(f"checked tracked artifacts: {', '.join(TRACKED_ARTIFACTS)}")
    print(f"checked suites for in-tree writes: {', '.join(_SUITES_TO_SCAN)}")
    if modified:
        print(f"FAIL: tracked artifacts modified by the run: {', '.join(modified)}")
    if offenders:
        print(f"FAIL: suites still writing into tests/: {', '.join(offenders)}")
    if modified or offenders:
        return 1
    print("PASS: no tracked artifact modified, no suite writes into tests/")
    return 0


def main() -> int:
    if "--check" in sys.argv[1:]:
        return check()
    print(out_dir())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
