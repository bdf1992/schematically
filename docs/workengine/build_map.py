"""Build docs/workengine/map.sov from docs/workengine/source/gapmap.json.

Run from the repository root: python docs/workengine/build_map.py
  --refresh-source  copy gapmap.json from the workstation sketchbook first
  --layered         place cards with node scripts/layout_sov.mjs instead of the group grid
  --no-buses        order the cards only; leave every wire to the router (no harness)
  --out PATH        write the map to PATH instead of docs/workengine/map.sov

Each group's cards are ordered by barycentre against the wires to the other groups (8 sweeps,
surfaces, records, queries and back, ties by source order), then placed as a grid. By default
the map is then given two harnesses with node scripts/layout_sov.mjs (surfaces to records,
records to queries): one trunk per wire label in the gap between two groups, streets in the row
gaps, and every wire between the two groups routed on them (LAYOUT-MODEL.md "As built: buses").
Both harnesses take --lanes port: wires that leave one port share a lane.
GROUP_GAP and ROW_GAP are the sizes those harnesses need.

The output is deterministic: the same gapmap.json gives the same map.sov byte for byte.
Standard library only.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SOURCE = HERE / "source" / "gapmap.json"
TARGET = HERE / "map.sov"
NOTATION = ROOT / "data" / "work-engine.notation.json"
SKETCHBOOK = Path("C:/Users/bdf19/workstation/control/sketchbooks/ep-CatalystCoreV2-sandbox-8d673072/gapmap.json")
GLOBAL = "canvas:global"

# Which open decision a card waits on: the decision is attached to every record or surface
# whose evidence text contains one of these phrases. This table is a reading of the gap map,
# not data in it; decisions whose phrases no evidence contains are attached to no card and
# are listed in the document description.
DECISION_PHRASES = {
    1: ["not atomic", "Not transactional"],
    2: ["audience"],
    3: ["discard", "private mode"],
    4: ["workflow subscriptions"],
    5: ["Push and mobile"],
    6: ["No feed"],
    7: ["capacity"],
    8: ["Cross-host identity", "hook parity"],
    9: ["mailroom"],
    10: ["Judgement"],
    11: ["identity binding"],
    12: ["Campaign"],
    13: ["federation"],
    14: ["Unity binding"],
    15: ["24 fps"],
}

# Layout of the group grid (canvas units).
TITLE_CHAR = 7.6      # width of one title character at the base title size
CARD_H = 120
SUB_CHAR = 5.4        # width of one subtitle character
ROW_GAP = 110         # room under a card for its status and waits-on line
COL_GAP = 140         # room for a waits-on line wider than its card
GROUP_GAP = 260       # surfaces to records: the harness's two trunks (20 lanes) need 184 between regions
QUERY_GAP = 320       # records to queries: the harness's one trunk of 35 lanes (59 wires, lanes port) needs 258 between regions
MIGRATION_GAP = 80    # the migration card's right edge to the surfaces' left column
# A gap between group regions is the gap between cards less two GROUP_PAD (24) of region padding.
# Every gap is only as wide as its harness needs: a wider picture is fitted smaller, and labels
# that keep their screen size then crowd each other. GROUP_GAP and ROW_GAP above already hold
# at or above what the harness receipts ask for.

LABEL_MARGIN = 16     # src/08-layout-core.js layered's own default margin, mirrored here
# SCHEMATIC.tokens.type.caption.size (src/03-notation-core.js); work-engine.notation.json
# carries no "tokens" override, so the Work Engine map draws its captions at this size too.
CAPTION_SIZE = 9.0


def label_estimate(text: str, margin: int = LABEL_MARGIN) -> float:
    """src/08-layout-core.js layered's own estimate: characters at the caption size, 0.6 of its
    size each, plus the margin on both sides."""
    return len(text) * CAPTION_SIZE * 0.6 + 2 * margin


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def short_decision(n: int, text: str) -> str:
    head = re.sub(r"^D\d+\s+", "", text)
    head = re.split(r"[:(;]", head, maxsplit=1)[0].strip()
    words = head.split()
    return " ".join(words[:4])


def card_width(label: str, lines: int = 1, floor: int = 200, cap: int = 520) -> int:
    need = math.ceil(len(label) * TITLE_CHAR / lines) + 56
    return int(min(cap, max(floor, math.ceil(need / 20) * 20)))


def order_by_barycentre(groups: list[list[dict]], wires: list[dict], sweeps: int = 8) -> None:
    """Sort each group's cards, in place, by the mean position of what they are wired to in the
    other groups. A card's position is its rank in its group scaled to 0..1. Sweeps go first to
    last group and back, alternating; a card with no such wire keeps its place; ties keep source order."""
    source = {c["id"]: i for g in groups for i, c in enumerate(g)}
    group_of = {c["id"]: k for k, g in enumerate(groups) for c in g}
    neighbours: dict[str, list[str]] = {cid: [] for cid in group_of}
    for w in wires:
        a, b = w["a"], w["b"]
        if a in group_of and b in group_of and group_of[a] != group_of[b]:
            neighbours[a].append(b)
            neighbours[b].append(a)
    for sweep in range(sweeps):
        for k in (range(len(groups)) if sweep % 2 == 0 else reversed(range(len(groups)))):
            pos = {c["id"]: (i / (len(g) - 1) if len(g) > 1 else 0.5) for g in groups for i, c in enumerate(g)}

            def key(c: dict) -> tuple[float, int]:
                ns = neighbours[c["id"]]
                return (sum(pos[n] for n in ns) / len(ns) if ns else pos[c["id"]], source[c["id"]])
            groups[k].sort(key=key)


def backing_names(backing: str) -> list[str]:
    names = []
    for part in re.sub(r"\s*\(.*?\)", "", backing).split(","):
        part = part.split(".")[0].strip()
        if part:
            names.append(part)
    return names


def build(gap: dict) -> tuple[dict, dict]:
    notation = json.loads(NOTATION.read_text(encoding="utf-8"))
    records, surfaces, queries = gap["records"], gap["surfaces"], gap["queries"]
    decisions = gap.get("open_decisions", [])
    rec_id = {r["name"]: "rec-" + slug(r["name"]) for r in records}
    # A query may name a record by the part before " / " (Publication for Publication / edition).
    rec_alias = {r["name"].split(" / ")[0]: r["name"] for r in records if " / " in r["name"]}
    sur_id = {s["name"]: "sur-" + slug(s["name"]) for s in surfaces}

    waits: dict[str, list[dict]] = {}
    attached: dict[int, list[str]] = {}
    for n, text in enumerate(decisions, start=1):
        phrases = DECISION_PHRASES.get(n, [])
        label = f"D{n} {short_decision(n, text)}"
        for item, ids in ((records, rec_id), (surfaces, sur_id)):
            for r in item:
                if any(p in r.get("evidence", "") for p in phrases):
                    waits.setdefault(ids[r["name"]], []).append({"kind": "decision", "id": f"D{n}", "label": label})
                    attached.setdefault(n, []).append(r["name"])

    components: list[dict] = []
    wires: list[dict] = []

    def card(cid, symbol, label, status, slot, subtitle=None, width=None, lines=1, extra=None):
        w = width or card_width(label, lines)
        if subtitle:
            w = int(min(600, max(w, math.ceil((len(subtitle) * SUB_CHAR + 40) / 20) * 20)))
        cfg = {"label": label, "colorSlot": slot, "status": status,
               "presentation": {"size": {"w": w, "h": CARD_H}}}
        if subtitle:
            cfg["subtitle"] = subtitle
        if cid in waits:
            cfg["waitsOn"] = waits[cid]
        if extra:
            cfg.update(extra)
        comp = {"id": cid, "symbolId": symbol, "x": 0, "y": 0, "canvasId": GLOBAL, "config": cfg}
        components.append(comp)
        return comp

    # Tracks: a surface's tracks are channels on its tracks-out port; Recording takes them all in.
    def channels(tracks):
        out = []
        for t in tracks:
            cid = slug(t.split()[0])
            if cid and cid not in out:
                out.append(cid)
        return out

    all_channels: list[str] = []
    for s in surfaces:
        for c in channels(s.get("tracks", [])):
            if c not in all_channels:
                all_channels.append(c)

    rec_cards, sur_cards, spec_cards = [], [], []
    for r in records:
        extra = None
        if r["name"] == "Recording":
            extra = {"attachmentPoints": [{"id": "tracks-in", "side": "left", "t": 0.75, "flow": "in", "label": "Tracks",
                                           "channels": [{"id": c} for c in all_channels]}]}
        rec_cards.append(card(rec_id[r["name"]], "we-record", r["name"], r["status"], 6,
                              subtitle=r.get("owner_task"), extra=extra))
    for s in surfaces:
        ch = channels(s.get("tracks", []))
        extra = None
        if ch:
            extra = {"attachmentPoints": [{"id": "tracks-out", "side": "right", "t": 0.75, "flow": "out", "label": "Tracks",
                                           "channels": [{"id": c} for c in ch]}]}
        sur_cards.append(card(sur_id[s["name"]], "we-surface", s["name"], s["status"], 7,
                              subtitle=f"{s['kind']} surface", width=card_width(s["name"], 2, floor=240, cap=300),
                              lines=2, extra=extra))
    unmatched: list[str] = []
    for i, q in enumerate(queries, start=1):
        qid = f"spec-{i:02d}-{q['screen']}"
        spec_cards.append(card(qid, "we-specification", q["needs"], q["status"], 8,
                               subtitle=f"{q['screen']} screen · {q['latency']}",
                               width=card_width(q["needs"], 2, floor=280, cap=460), lines=2))
        for name in backing_names(q["backing"]):
            name = rec_alias.get(name, name)
            if name in rec_id:
                wires.append({"id": f"w-backs-{slug(name)}-{i:02d}", "a": rec_id[name], "aSide": "out", "b": qid,
                              "bSide": "in", "canvasId": GLOBAL, "config": {"label": "backs"}})
            else:
                unmatched.append(f"{qid}: {name}")

    # Migration named by decision D1 (a proposed work item; its waits-on is D1, rule R-29 and Bdo).
    migration = None
    if decisions and decisions[0].startswith("D1"):
        migration = card("mig-continuity-to-sqlite", "we-migration",
                         "Continuity records move to a transactional SQLite store", "proposed", 8,
                         subtitle="Migration · D1", width=card_width("Continuity records move to a transactional SQLite store", 2, floor=280),
                         lines=2,
                         extra={"waitsOn": [{"kind": "person", "id": "bdo", "label": "Bdo"},
                                            {"kind": "rule", "id": "R-29"},
                                            {"kind": "decision", "id": "D1", "label": f"D1 {short_decision(1, decisions[0])}"}]})
        store = sur_id.get("Workstation control store")
        if store:
            wires.append({"id": "w-moves-control-store", "a": migration["id"], "aSide": "out", "b": store, "bSide": "in",
                          "canvasId": GLOBAL, "config": {"label": "moves records out of", "status": "proposed"}})

    for s in surfaces:
        sid = sur_id[s["name"]]
        if "Surface registration" in rec_id:
            wires.append({"id": f"w-registered-{slug(s['name'])}", "a": sid, "aSide": "out", "b": rec_id["Surface registration"],
                          "bSide": "in", "canvasId": GLOBAL, "config": {"label": "registered by"}})
        if channels(s.get("tracks", [])) and "Recording" in rec_id:
            wires.append({"id": f"w-tracks-{slug(s['name'])}", "a": sid, "aSide": "tracks-out", "b": rec_id["Recording"],
                          "bSide": "tracks-in", "canvasId": GLOBAL, "config": {"label": "feeds tracks"}})

    # Group grid: surfaces | records | queries, each a block of columns. The gap between two
    # adjacent columns of one group is at least COL_GAP, widened to the widest label estimate
    # among the wires between a card in one of the two columns and a card in the other.
    def column_gaps(cards: list[dict], cols: int) -> list[int]:
        col_of = {c["id"]: i % cols for i, c in enumerate(cards)}
        gaps = []
        for k in range(cols - 1):
            need = COL_GAP
            for w in wires:
                a, b = w.get("a"), w.get("b")
                if a not in col_of or b not in col_of or {col_of[a], col_of[b]} != {k, k + 1}:
                    continue
                label = w.get("config", {}).get("label")
                if label:
                    need = max(need, math.ceil(label_estimate(label)))
            gaps.append(need)
        return gaps

    def place(cards, x0, cols, y0=0):
        widths = [max(c["config"]["presentation"]["size"]["w"] for c in cards[k::cols]) for k in range(cols)]
        gaps = column_gaps(cards, cols)
        x = x0
        lefts = []
        for i, w in enumerate(widths):
            lefts.append(x)
            x += w + (gaps[i] if i < len(gaps) else COL_GAP)
        for i, c in enumerate(cards):
            col, row = i % cols, i // cols
            c["x"] = lefts[col] + widths[col] / 2
            c["y"] = y0 + row * (CARD_H + ROW_GAP) + CARD_H / 2
        return x - (gaps[-1] if gaps else COL_GAP)

    # Card order: barycentre against the wires to the other groups, before any card is placed.
    order_by_barycentre([sur_cards, rec_cards, spec_cards], wires)
    right = place(sur_cards, 0, 2)
    right = place(rec_cards, right + GROUP_GAP, 4)
    if migration:
        # Top left, beside the surfaces: its wire to the control store (a left-hand port) stays
        # inside the picture, and the picture's top stays above the first row of every group.
        migration["x"] = -MIGRATION_GAP - migration["config"]["presentation"]["size"]["w"] / 2
        migration["y"] = -CARD_H - ROW_GAP + CARD_H / 2
    place(spec_cards, right + QUERY_GAP, 2)

    def group(gid, label, slot, members):
        xs = [m["x"] for m in members]
        ys = [m["y"] for m in members]
        return {"id": gid, "symbolId": "group", "x": round((min(xs) + max(xs)) / 2), "y": round((min(ys) + max(ys)) / 2),
                "canvasId": GLOBAL, "config": {"label": label, "colorSlot": slot, "members": [m["id"] for m in members],
                                                "presentation": {"graphic": {"kind": "none"}}}}

    groups = [group("records", "Records", 2, rec_cards), group("surfaces", "Surfaces", 4, sur_cards),
              group("queries", "Screen queries (specifications)", 5, spec_cards)]
    for c in components:
        c["x"], c["y"] = round(c["x"]), round(c["y"])

    unattached = [f"D{n}" for n in range(1, len(decisions) + 1) if n not in attached]
    meta = gap.get("meta", {})
    doc = {
        "schema": "soveraeign.schematic/document@0.1",
        "id": "workengine-map",
        "revision": 0,
        "notation": "work-engine",
        "meta": {
            "title": f"Work Engine map: {len(records)} records, {len(surfaces)} surfaces, {len(queries)} screen queries",
            "description": (
                f"Generated by docs/workengine/build_map.py from docs/workengine/source/gapmap.json (read {meta.get('read_on', '?')}). "
                "Each card's status is the gap map's (exists, partial, missing); a record's subtitle is its owning task. "
                "Open decisions are waits-on entries on the cards whose evidence names them (DECISION_PHRASES in build_map.py). "
                f"Decisions attached to no card: {', '.join(unattached) or 'none'}. "
                f"Backing names that are not records in the gap map: {'; '.join(unmatched) or 'none'}."
            ),
        },
        "components": groups + components,
        "wires": wires,
        "references": [{"id": "notation-work-engine", "kind": "notation", "label": "Work Engine", "data": notation}],
    }
    report = {"unattached": unattached, "unmatched": unmatched, "attached": attached}
    return doc, report


HARNESSES = ["surfaces,records", "records,queries"]


def write(doc: dict, target: Path) -> None:
    target.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str]) -> int:
    if "--refresh-source" in argv:
        SOURCE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SKETCHBOOK, SOURCE)
        print(f"copied {SKETCHBOOK} -> {SOURCE}")
    target = Path(argv[argv.index("--out") + 1]).resolve() if "--out" in argv else TARGET
    gap = json.loads(SOURCE.read_text(encoding="utf-8"))
    doc, report = build(gap)
    write(doc, target)
    layered, buses = "--layered" in argv, "--no-buses" not in argv
    if layered or buses:
        # One pass of the shared layout core: arrange (only with --layered), then each harness in turn.
        cmd = ["node", str(ROOT / "scripts" / "layout_sov.mjs"), str(target)]
        if not layered:
            cmd.append("--no-arrange")
        if buses:
            for pair in HARNESSES:
                cmd += ["--harness", pair]
            cmd += ["--lanes", "port"]
        run = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        print(run.stdout.strip())
        if run.returncode:
            print(run.stderr.strip())
            return run.returncode
    cards = sum(1 for c in doc["components"] if c["symbolId"] != "group")
    shown = target.relative_to(ROOT).as_posix() if target.is_relative_to(ROOT) else str(target)
    print(f"ok  {shown}: {cards} cards, {len(doc['wires'])} wires{'' if buses else ' (no buses)'}")
    print(f"    decisions on cards: {', '.join(f'D{n}' for n in sorted(report['attached']))}")
    print(f"    decisions on no card: {', '.join(report['unattached']) or 'none'}")
    print(f"    backing names with no record: {'; '.join(report['unmatched']) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
