"""Check the Work Engine map: map.sov against source/gapmap.json, and map.svg.

Run from the repository root: python docs/workengine/check_map.py
  --picture PNG  also load map.svg in headless Chromium, measure it the way
                 tests/export_picture_fit_qa.py does (titles inside their cards, no caption on a
                 caption or a card), and save a screenshot to PNG. Needs Playwright.

Checks, each failure named:
- every record, surface and query of gapmap.json appears exactly once, as a card of its kind
  (we-record, we-surface, we-specification), with the gap map's status;
- every record and surface name appears in map.svg;
- node scripts/validate_sov.mjs docs/workengine/map.sov passes;
- no two card rectangles (x, y and presentation size) overlap.
Exits 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import json
import subprocess
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def cards_of(doc: dict, symbol: str) -> list[dict]:
    return [c for c in doc["components"] if c.get("symbolId") == symbol]


def rect(c: dict) -> tuple[float, float, float, float]:
    s = c["config"].get("presentation", {}).get("size", {})
    w, h = float(s.get("w", 112)), float(s.get("h", 84))
    return c["x"] - w / 2, c["y"] - h / 2, c["x"] + w / 2, c["y"] + h / 2


def check_document(gap: dict, doc: dict) -> list[str]:
    problems = []
    kinds = [("record", "we-record", gap["records"], "name"),
             ("surface", "we-surface", gap["surfaces"], "name"),
             ("query", "we-specification", gap["queries"], "needs")]
    for kind, symbol, items, key in kinds:
        cards = cards_of(doc, symbol)
        for item in items:
            found = [c for c in cards if c["config"].get("label") == item[key]]
            if len(found) != 1:
                problems.append(f"{kind} {item[key]!r} appears {len(found)} times as a {symbol} card")
                continue
            status = found[0]["config"].get("status")
            if status != item["status"]:
                problems.append(f"{kind} {item[key]!r} has status {status!r}, gapmap says {item['status']!r}")
        if len(cards) != len(items):
            problems.append(f"{len(cards)} {symbol} cards for {len(items)} {kind}s in gapmap.json")
    placed = [c for c in doc["components"] if c.get("symbolId") != "group"]
    for i, a in enumerate(placed):
        ax0, ay0, ax1, ay1 = rect(a)
        for b in placed[i + 1:]:
            bx0, by0, bx1, by1 = rect(b)
            if ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1:
                problems.append(f"cards {a['id']} and {b['id']} overlap")
    return problems


def check_svg(gap: dict, svg: Path) -> list[str]:
    if not svg.is_file():
        return [f"{svg.name} does not exist"]
    text = svg.read_text(encoding="utf-8")
    return [f"{svg.name} lacks the name {item['name']!r}"
            for item in gap["records"] + gap["surfaces"]
            if escape(item["name"], quote=False) not in text]


def check_picture(svg: Path, png: Path) -> list[str]:
    sys.path.insert(0, str(ROOT / "tests"))
    from export_picture_fit_qa import MEASURE_JS  # noqa: E402
    from browser_runtime import chromium_launch_kwargs  # noqa: E402
    from playwright.sync_api import sync_playwright  # noqa: E402
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs())
        page = browser.new_page(viewport={"width": 2400, "height": 1600})
        page.set_content(svg.read_text(encoding="utf-8"), wait_until="load")
        bad = page.evaluate(MEASURE_JS)
        page.screenshot(path=str(png), full_page=True)
        browser.close()
    return [f"picture: {' '.join(str(x) for x in b[:3])}" for b in bad]


def main(argv: list[str]) -> int:
    gap = json.loads((HERE / "source" / "gapmap.json").read_text(encoding="utf-8"))
    problems = []
    try:
        doc = json.loads((HERE / "map.sov").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        problems.append(f"map.sov does not parse: {exc}")
        doc = None
    if doc:
        problems += check_document(gap, doc)
    problems += check_svg(gap, HERE / "map.svg")
    run = subprocess.run(["node", str(ROOT / "scripts" / "validate_sov.mjs"), str(HERE / "map.sov")],
                         capture_output=True, text=True, cwd=ROOT)
    if run.returncode:
        problems.append("validate_sov.mjs failed: " + (run.stdout + run.stderr).strip().replace("\n", " | "))
    if "--picture" in argv:
        problems += check_picture(HERE / "map.svg", Path(argv[argv.index("--picture") + 1]))
    if problems:
        for p in problems:
            print("FAIL", p)
        return 1
    print(f"ok  map.sov, map.svg: {len(gap['records'])} records, {len(gap['surfaces'])} surfaces, "
          f"{len(gap['queries'])} queries, each once with its status; validate_sov passes; no card overlaps")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
