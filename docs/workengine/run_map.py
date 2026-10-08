"""Run the Work Engine map: each card's level comes from a run on the state-space engine.

Run from the repository root:
  python docs/workengine/run_map.py --out PATH   write a runnable copy of map.sov to PATH
  python docs/workengine/run_map.py --list       run that copy and list every query against its painted status

The rule (GAPS.md "The map runs"). A record is on only when its gap map status is exists; partial
and missing are off. A query is on only when every record its backing names is on. A backing name
the gap map holds no record for counts as off. A backing name resolves to a record as build_map.py
resolves it: by backing_names, then by the record name, then by the part of a record name before
its slash.

The copy differs from docs/workengine/map.sov in exactly three ways:
- each we-record card gains config.signal: asserted, binary, value 1 when its status is exists, else 0;
- each we-specification card gains config.signal: derived, binary, combine and, when every backing
  name resolves to a record (the backs wires of map.sov carry the records to its in port);
  asserted, binary, value 0 when a backing name resolves to no record;
- two references of kind scenario are appended: s-as-read and s-all-records-exist.

map.sov is read and never written. The output is deterministic: the same map.sov and gapmap.json
give the same bytes. Standard library only; --list needs node.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

from build_map import backing_names  # noqa: E402

SOURCE = HERE / "source" / "gapmap.json"
MAP = HERE / "map.sov"
COMBINE = "and"
SETTLE_MS = 100

# The DOM-free cores in the order MODULES.md gives, up to the sim surface.
CORES = ["03-canonical.js", "03-notation-core.js", "06-attachment-core.js", "05-data-core.js",
         "07-state-space.js", "07-state-surface.js"]
NODE_RUN = r"""
const fs=require('fs'),path=require('path');
const root=process.argv[1],doc=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
let Surface=null;
for(const name of JSON.parse(process.argv[3]))Surface=require(path.join(root,'src',name));
const made=Surface.createSimulation(doc);
if(!made.ok){console.log(JSON.stringify({ok:false,at:'createSimulation',code:made.code,message:made.message}));process.exit(0)}
const moved=made.sim.advance(Number(process.argv[4]));
if(!moved.ok){console.log(JSON.stringify({ok:false,at:'advance',code:moved.code,message:moved.message}));process.exit(0)}
const levels=made.sim.levels();
console.log(JSON.stringify({ok:true,levels:Object.fromEntries(Object.entries(levels).map(([id,l])=>[id,l.value]))}));
"""


def resolve(name: str, records: dict[str, dict], alias: dict[str, str]) -> dict | None:
    """The record a backing name means, as build_map.py's build resolves it, or None."""
    return records.get(alias.get(name, name))


def reading(gap: dict, doc: dict) -> dict:
    """What the rule gives for this gap map, against the cards of this document.

    records: gap map order, each {id, name, on}. queries: map order (the order of the
    we-specification cards), each {id, status, names, off, unresolved, derived, level}.
    """
    by_name = {r["name"]: r for r in gap["records"]}
    alias = {r["name"].split(" / ")[0]: r["name"] for r in gap["records"] if " / " in r["name"]}
    record_card = {c["config"]["label"]: c["id"] for c in doc["components"] if c.get("symbolId") == "we-record"}
    query_card = {c["config"]["label"]: c["id"] for c in doc["components"] if c.get("symbolId") == "we-specification"}
    records = [{"id": record_card[r["name"]], "name": r["name"], "on": r["status"] == "exists"} for r in gap["records"]]
    by_needs = {}
    for q in gap["queries"]:
        names = backing_names(q["backing"])
        found = [resolve(n, by_name, alias) for n in names]
        unresolved = [n for n, r in zip(names, found) if r is None]
        off = [n for n, r in zip(names, found) if r is None or r["status"] != "exists"]
        by_needs[q["needs"]] = {"id": query_card[q["needs"]], "status": q["status"], "names": names, "off": off,
                                "unresolved": unresolved, "derived": not unresolved, "level": 0 if off else 1}
    order = [c["config"]["label"] for c in doc["components"] if c.get("symbolId") == "we-specification"]
    return {"records": records, "queries": [by_needs[label] for label in order]}


def runnable(gap: dict, source: dict) -> dict:
    """A copy of the map with signals on its record and query cards and the two scenarios."""
    doc = copy.deepcopy(source)
    read = reading(gap, doc)
    on = {r["id"]: r["on"] for r in read["records"]}
    queries = {q["id"]: q for q in read["queries"]}
    for c in doc["components"]:
        if c.get("symbolId") == "we-record":
            c["config"]["signal"] = {"mode": "asserted", "kind": "binary", "value": 1 if on[c["id"]] else 0}
        elif c.get("symbolId") == "we-specification":
            if queries[c["id"]]["derived"]:
                c["config"]["signal"] = {"mode": "derived", "kind": "binary", "combine": COMBINE}
            else:
                c["config"]["signal"] = {"mode": "asserted", "kind": "binary", "value": 0}
    as_read = {"id": "s-as-read", "kind": "scenario", "label": "The gap map as read", "data": {
        "steps": [{"advance": SETTLE_MS}],
        "expect": {"levels": {q["id"]: q["level"] for q in read["queries"]}}}}
    all_exist = {"id": "s-all-records-exist", "kind": "scenario", "label": "Every record exists", "data": {
        "steps": [{"set": {"node": r["id"], "value": 1}} for r in read["records"] if not r["on"]] + [{"advance": SETTLE_MS}],
        "expect": {"levels": {q["id"]: 1 if q["derived"] else 0 for q in read["queries"]}}}}
    doc.setdefault("references", []).extend([as_read, all_exist])
    return doc


def load() -> tuple[dict, dict]:
    return json.loads(SOURCE.read_text(encoding="utf-8")), json.loads(MAP.read_text(encoding="utf-8"))


def write(doc: dict, target: Path) -> None:
    target.write_bytes((json.dumps(doc, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))


def disagrees(status: str, level: int) -> bool:
    return (status == "exists" and level == 0) or (status in ("partial", "missing") and level == 1)


def listing() -> int:
    gap, source = load()
    doc = runnable(gap, source)
    read = reading(gap, doc)
    with tempfile.TemporaryDirectory() as tmp:
        copy_file = Path(tmp) / "map-run.sov"
        write(doc, copy_file)
        proc = subprocess.run(["node", "-e", NODE_RUN, str(ROOT), str(copy_file), json.dumps(CORES), str(SETTLE_MS)],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode:
        print("node failed: " + (proc.stdout + proc.stderr).strip())
        return 1
    out = json.loads(proc.stdout)
    if not out["ok"]:
        print(f"refused at {out['at']}: {out['code']}: {out['message']}")
        return 1
    count = 0
    for q in read["queries"]:
        level = 1 if out["levels"][q["id"]] >= 1 else 0
        bad = disagrees(q["status"], level)
        count += bad
        print(f"{'DISAGREE' if bad else 'agree'} {q['id']} painted={q['status']} run={level} off={','.join(q['off'])}")
    print(f"disagreements: {count} of {len(read['queries'])}")
    return 0


def main(argv: list[str]) -> int:
    if "--list" in argv:
        return listing()
    if "--out" in argv:
        target = Path(argv[argv.index("--out") + 1]).resolve()
        if target == MAP.resolve():
            print("refused: --out names docs/workengine/map.sov, which this script never writes")
            return 1
        gap, source = load()
        write(runnable(gap, source), target)
        print(f"ok  {target}")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
