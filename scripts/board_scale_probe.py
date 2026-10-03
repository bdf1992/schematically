"""Board scale probe: how the Work Engine board renders at 100, 1000 and 4000 pieces.

    python scripts/board_scale_probe.py            # measure, write docs/workengine/board-scale.json
    python scripts/board_scale_probe.py --check    # read that file only; exit 1 unless complete
    python scripts/board_scale_probe.py --sizes 100 --shot board.png   # also save a picture
    python scripts/board_scale_probe.py --view docs/workengine/board-sample.sov --shot sample.png

Each board has the shape of docs/workengine/board-sample.sov: task cards carrying a status from
the Work Engine notation (exists, partial, missing, proposed) and a subtitle, every tenth card
waiting on someone (config.waitsOn), cards collected 20 to a reading-only group, and one
"depends on" Wire per piece after the first. The notation is the one board-sample.sov carries.

Each size is opened in headless Chromium the way tests/performance_regression_qa.py opens a
document: index.html is set as the page content, then the document goes in through
SovSchematicAPI.document.replace. Three numbers per size, as the scale gate (_ref-SCALE-GATE.md
section 4) budgets them:

- cold_ms: replace + fit to extents, through the next two animation frames (the first painted
  frame after load);
- pan_frame_ms: move the camera a tenth of a view width (applyCamera, the editor's own pan
  path), through two animation frames; the median of five;
- zoom_frame_ms: zoomAt(1.25) and back, the editor's own wheel-zoom path, through two animation
  frames; the median of five.

The frame wait is the one _ref-scale_benchmark.py uses (two requestAnimationFrame callbacks),
except that the clock starts before the camera change, so the change's own cost is counted.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "workengine" / "board-scale.json"
SAMPLE = ROOT / "docs" / "workengine" / "board-sample.sov"
SIZES = [100, 1000, 4000]
GROUP_SIZE = 20
NUMBERS = ("cold_ms", "pan_frame_ms", "zoom_frame_ms")
STATUSES = ("exists", "exists", "partial", "missing", "proposed")
SYMBOLS = ("act", "we-specification", "act", "we-migration")
CARD = {"w": 112, "h": 84}
COL_STEP, ROW_STEP = 258, 140
GROUP_COLS, GROUP_ROWS = 5, 4
GROUP_GAP_X, GROUP_GAP_Y = 160, 200


def _ports() -> dict:
    def port(flow: str) -> dict:
        return {
            "face": "external",
            "label": "",
            "connectionCount": 1,
            "activeConnection": 0,
            "connections": [{"id": "connection-1", "colorSlot": 0, "flow": flow, "access": "read-write"}],
        }

    return {"in": port("in"), "out": port("out"), "control": port("control")}


def _form() -> dict:
    return {
        "body": {"kind": "surface", "material": "generic", "thickness": 0},
        "dimension": 2,
        "frame": {"mode": "none", "thickness": 0, "depth": 0},
        "regions": {"interior": {"state": "closed"}},
    }


def notation_reference() -> dict:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    refs = [r for r in sample.get("references", []) if r.get("kind") == "notation"]
    if not refs:
        raise SystemExit(f"{SAMPLE} carries no notation reference")
    return refs[0]


def make_board(pieces: int, notation: dict, *, with_wires: bool = True, with_groups: bool = True) -> dict:
    """A board of `pieces` task cards in groups of GROUP_SIZE, one dependency Wire per piece.
    `with_wires` / `with_groups` False leave the Wires or the groups out, to see which part of the
    cost they carry (the recorded runs keep both)."""
    groups = (pieces + GROUP_SIZE - 1) // GROUP_SIZE
    per_row = max(1, round((groups * 1.6) ** 0.5))
    group_w = GROUP_COLS * COL_STEP + GROUP_GAP_X
    group_h = GROUP_ROWS * ROW_STEP + GROUP_GAP_Y
    components: list[dict] = []
    wires: list[dict] = []
    for g in range(groups):
        gx, gy = (g % per_row) * group_w, (g // per_row) * group_h
        members = []
        for k in range(GROUP_SIZE):
            i = g * GROUP_SIZE + k
            if i >= pieces:
                break
            pid = f"t{i + 1:04d}"
            members.append(pid)
            config = {
                "label": f"Task {i + 1}: a piece of work on the board",
                "status": STATUSES[i % len(STATUSES)],
                "subtitle": "ACTIVE" if i % 3 else "CLOSED",
                "ports": _ports(),
                "presentation": {"size": dict(CARD)},
            }
            if i % 10 == 9:
                config["waitsOn"] = [{"id": "contractor", "kind": "person", "label": "contractor: run the contract"}]
            components.append(
                {
                    "config": config,
                    "id": pid,
                    "symbolId": SYMBOLS[i % len(SYMBOLS)],
                    "form": _form(),
                    "x": gx + (k % GROUP_COLS) * COL_STEP,
                    "y": gy + (k // GROUP_COLS) * ROW_STEP,
                }
            )
            if i:
                # Inside a group a piece depends on the one before it; the first piece of a group
                # depends on the first piece of the group before, so wires also cross groups.
                dep = i - 1 if k else i - GROUP_SIZE
                a = f"t{dep + 1:04d}"
                wires.append(
                    {
                        "a": a,
                        "aSide": "out",
                        "b": pid,
                        "bSide": "in",
                        "config": {"label": "depends on", "forwardOperation": "none", "reverseOperation": "none"},
                        "id": f"dep-{a}-{pid}",
                        "aAttachment": {"kind": "attachment-ref", "componentId": a, "pointId": "right"},
                        "bAttachment": {"kind": "attachment-ref", "componentId": pid, "pointId": "left"},
                        "form": {"dimension": 1, "body": {"kind": "path", "material": "generic", "thickness": 0}},
                        "role": "carrier",
                        "canvasId": "canvas:global",
                    }
                )
        components.insert(
            len(components) - len(members),
            {
                "config": {
                    "label": f"Case {g + 1}",
                    "members": members,
                    "presentation": {"graphic": {"kind": "none"}, "size": {"w": 320, "h": 220}},
                    "attachmentDefaults": "none",
                    "ports": {},
                },
                "id": f"case-{g + 1:03d}",
                "symbolId": "group",
                "form": _form(),
            },
        )
    if not with_groups:
        components = [c for c in components if c["symbolId"] != "group"]
    if not with_wires:
        wires = []
    return {
        "schema": "soveraeign.schematic/document@0.1",
        "id": f"board-scale-{pieces}",
        "revision": 0,
        "meta": {"title": f"Board scale probe, {pieces} pieces"},
        "components": components,
        "wires": wires,
        "references": [notation],
        "layout": {"default": "main", "views": {"main": {"name": "Main", "routes": {}, "buses": {}}}},
        "notation": "work-engine",
    }


MEASURE_JS = r"""
async (doc) => {
  const frames = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  const median = xs => { const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
  await frames();
  const t0 = performance.now();
  SovSchematicAPI.document.replace(doc);
  fitDiagram();
  await frames();
  const cold = performance.now() - t0;
  const pans = [], zooms = [];
  for (let i = 0; i < 5; i++) {
    let s = performance.now();
    camera = {...camera, x: camera.x + camera.w / 10 * (i % 2 ? -1 : 1)};
    applyCamera();
    await frames();
    pans.push(performance.now() - s);
    s = performance.now();
    zoomAt(i % 2 ? 1 / 1.25 : 1.25);
    await frames();
    zooms.push(performance.now() - s);
  }
  return {
    cold_ms: cold,
    pan_frame_ms: median(pans), pan_frame_max_ms: Math.max(...pans),
    zoom_frame_ms: median(zooms), zoom_frame_max_ms: Math.max(...zooms),
    components: nodes.length, wires: wires.length,
    svg_elements: workspace.querySelectorAll('*').length,
    heap_mb: performance.memory ? performance.memory.usedJSHeapSize / 1048576 : null,
  };
}
"""


def measure(sizes: list[int], shot: Path | None, *, with_wires: bool = True, with_groups: bool = True) -> list[dict]:
    sys.path.insert(0, str(ROOT / "tests"))
    from browser_runtime import chromium_launch_kwargs  # noqa: PLC0415
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    notation = notation_reference()
    runs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs())
        for n in sizes:
            doc = make_board(n, notation, with_wires=with_wires, with_groups=with_groups)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.set_default_timeout(0)
            page.set_content(html, wait_until="load")
            page.wait_for_timeout(150)
            wall = time.time()
            r = page.evaluate(MEASURE_JS, doc)
            r = {k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items()}
            r["pieces"] = n
            r["groups"] = sum(1 for c in doc["components"] if c["symbolId"] == "group")
            r["wall_s"] = round(time.time() - wall, 1)
            runs.append(r)
            print(
                f"pieces={n:<5} cold={r['cold_ms']:.0f}ms pan={r['pan_frame_ms']:.1f}ms "
                f"zoom={r['zoom_frame_ms']:.1f}ms svg={r['svg_elements']} wall={r['wall_s']}s",
                flush=True,
            )
            if shot is not None and n == sizes[0]:
                page.evaluate("fitDiagram()")
                page.wait_for_timeout(200)
                page.screenshot(path=str(shot))
            page.close()
        browser.close()
    return runs


def picture(doc_file: Path, shot: Path) -> int:
    """Open one .sov the same way and save a picture of it fitted to the window; measures nothing."""
    sys.path.insert(0, str(ROOT / "tests"))
    from browser_runtime import chromium_launch_kwargs  # noqa: PLC0415
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    doc = json.loads(doc_file.read_text(encoding="utf-8"))
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs())
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.set_content(html, wait_until="load")
        page.wait_for_timeout(150)
        drawn = page.evaluate(
            "(d)=>{SovSchematicAPI.document.replace(d);fitDiagram();"
            "return {nodes:nodes.map(n=>[n.id,Math.round(n.x),Math.round(n.y)]),"
            "drawn:[...workspace.querySelectorAll('.node[data-id]')].map(e=>e.dataset.id),"
            "camera:{...camera}}}",
            doc,
        )
        page.wait_for_timeout(300)
        # The editor's side panels cover part of the workspace, so frame the cards' own extent
        # in the workspace element and picture that element alone.
        page.evaluate(
            "()=>{let l=1e9,r=-1e9,t=1e9,b=-1e9;for(const n of nodes){if(!Number.isFinite(n.x))continue;"
            "const s=componentSize(n);l=Math.min(l,n.x-s.w/2);r=Math.max(r,n.x+s.w/2);t=Math.min(t,n.y-s.h/2);b=Math.max(b,n.y+s.h/2)}"
            "const box=workspace.getBoundingClientRect(),pad=90,w=r-l+pad*2,h=b-t+pad*2,a=box.width/box.height;"
            "const W=Math.max(w,h*a),H=W/a;camera={x:(l+r)/2-W/2,y:(t+b)/2-H/2,w:W,h:H};applyCamera()}"
        )
        page.wait_for_timeout(300)
        page.locator("#workspace").screenshot(path=str(shot))
        missing = sorted({n[0] for n in drawn["nodes"]} - set(drawn["drawn"]))
        print(f"components {len(drawn['nodes'])}, drawn {len(set(drawn['drawn']))}, not drawn {missing}")
        browser.close()
    print(f"wrote {shot}")
    return 0


def check() -> int:
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"FAIL {OUT}: {exc}")
        return 1
    problems = []
    if sorted(data.get("sizes", [])) != SIZES:
        problems.append(f"sizes are {data.get('sizes')}, expected {SIZES}")
    by_size = {r.get("pieces"): r for r in data.get("runs", []) if isinstance(r, dict)}
    for n in SIZES:
        run = by_size.get(n)
        if run is None:
            problems.append(f"no run for {n} pieces")
            continue
        for key in NUMBERS:
            value = run.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                problems.append(f"{n} pieces: {key} is {value!r}")
    if problems:
        for line in problems:
            print("FAIL", line)
        return 1
    for n in SIZES:
        r = by_size[n]
        print(f"ok   {n} pieces: cold {r['cold_ms']} ms, pan frame {r['pan_frame_ms']} ms, zoom frame {r['zoom_frame_ms']} ms")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="only read board-scale.json; exit 1 unless every size has all three numbers")
    ap.add_argument("--sizes", type=int, nargs="+", default=SIZES, help="piece counts to measure")
    ap.add_argument("--shot", type=Path, default=None, help="save a picture of the smallest board here")
    ap.add_argument("--out", type=Path, default=OUT, help="where to write the results")
    ap.add_argument("--view", type=Path, default=None, help="with --shot: picture this .sov instead of measuring")
    ap.add_argument("--no-wires", action="store_true", help="leave the dependency Wires out (to split the cost; not for the recorded file)")
    ap.add_argument("--no-groups", action="store_true", help="leave the case groups out (to split the cost; not for the recorded file)")
    args = ap.parse_args(argv)
    if args.check:
        return check()
    if args.view is not None:
        if args.shot is None:
            ap.error("--view needs --shot")
        return picture(args.view, args.shot)
    if (args.no_wires or args.no_groups) and args.out == OUT:
        ap.error("--no-wires and --no-groups are for a split, not the recorded file: give --out")
    runs = measure(args.sizes, args.shot, with_wires=not args.no_wires, with_groups=not args.no_groups)
    result = {
        "sizes": args.sizes,
        "runs": runs,
        "measured": time.strftime("%Y-%m-%d"),
        "host": {"os": platform.platform(terse=True), "python": platform.python_version()},
        "method": "scripts/board_scale_probe.py: index.html as page content, SovSchematicAPI.document.replace, "
        "two animation frames per measured step; pan and zoom are medians of five",
        "frontend": "F0 (SVG DOM), backend B1 (indexed JS arrays) as on dev",
    }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
