"""Form spine QA: every built-in attachment point is derived from one boundary relation.

The claim under test is that Point, endpoint, edge point and face are not separate systems.
A dimension-N Form is bounded by dimension-(N-1) Forms, recursively, and the 0D attachment
points every dimension exposes are that relation projected down. If someone re-enumerates a
dimension's points by hand, the provenance assertions below fail.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The exact contract 0.1 documents and the browser suites rely on. Deriving these from the
# boundary relation must not move a single id, compatId, side, role, flow or t.
EXPECTED_SPECS = {
    "0": [{"id": "self", "compatId": "out", "side": "point", "role": "self", "defaultFlow": "duplex", "t": 0.5}],
    "1": [
        {"id": "start", "compatId": "in", "side": "left", "role": "endpoint", "defaultFlow": "in", "t": 0},
        {"id": "end", "compatId": "out", "side": "right", "role": "endpoint", "defaultFlow": "out", "t": 1},
    ],
    "2": [
        {"id": "left", "compatId": "in", "side": "left", "role": "boundary", "defaultFlow": "in", "t": 0.5},
        {"id": "right", "compatId": "out", "side": "right", "role": "boundary", "defaultFlow": "out", "t": 0.5},
        {"id": "top", "compatId": "control", "side": "top", "role": "boundary", "defaultFlow": "control", "t": 0.5},
    ],
}

PROBE = r"""
const Form=require('./src/04-form-core.js');
const Attachment=require('./src/06-attachment-core.js');
const keys=['id','compatId','side','role','defaultFlow','t'];
const specs={};
for(const d of [0,1,2]){
  specs[d]=Attachment.pointSpecs({form:{dimension:d}}).map(s=>Object.fromEntries(keys.map(k=>[k,s[k]])));
}
process.stdout.write(JSON.stringify({
  specs,
  chain:Form.boundaryChain(3).map(l=>({dimension:l.dimension,bodyKind:l.bodyKind,
    elements:l.elements.map(e=>({id:e.id,dimension:e.dimension,bodyKind:e.bodyKind,mode:e.mode}))})),
  planeLeft:Form.terminalPoints(2,{sides:['left','right','top']})[0],
  corner:Form.elementAt(2,['left','start']),
  volumePoints:Form.terminalPoints(3).map(p=>({id:p.id,dimension:p.dimension,via:p.via})),
  missing:Form.elementAt(2,['nope']),
  bodyKinds:Form.BODY_KINDS
}));
"""

out = subprocess.run([__import__("shutil").which("node") or "node", "-e", PROBE],
                     cwd=ROOT, check=True, capture_output=True, text=True).stdout
data = json.loads(out)

# 1. Derivation changed nothing that already worked.
assert data["specs"] == EXPECTED_SPECS, data["specs"]

# 2. The boundary relation descends one dimension at a time, all the way to 0D.
chain = data["chain"]
assert [layer["dimension"] for layer in chain] == [3, 2, 1], chain
assert [layer["bodyKind"] for layer in chain] == ["volume", "surface", "path"], chain
for layer in chain:
    for element in layer["elements"]:
        assert element["dimension"] == layer["dimension"] - 1, element
assert {e["mode"] for e in chain[0]["elements"]} == {"face"}, chain[0]
assert {e["mode"] for e in chain[1]["elements"]} == {"edge"}, chain[1]
assert {e["mode"] for e in chain[2]["elements"]} == {"endpoint"}, chain[2]

# 3. A Plane's boundary point is a Point on the 1D Path that bounds it — not its own species.
plane_left = data["planeLeft"]
assert plane_left["dimension"] == 0, plane_left
assert plane_left["via"]["dimension"] == 1 and plane_left["via"]["bodyKind"] == "path", plane_left
assert plane_left["via"]["mode"] == "edge", plane_left

# 4. That bounding edge has its own 0D boundary, reached by the same relation.
corner = data["corner"]
assert corner["dimension"] == 0 and corner["mode"] == "endpoint", corner

# 5. 3D needs no new kind of thing: a volume's points fall out of faces already.
volume_points = data["volumePoints"]
assert len(volume_points) == 6, volume_points
assert all(p["dimension"] == 0 and p["via"]["bodyKind"] == "surface" for p in volume_points), volume_points

# 6. An unknown boundary id resolves to nothing rather than inventing an element.
assert data["missing"] is None, data["missing"]
assert data["bodyKinds"] == ["point", "path", "surface", "volume"], data["bodyKinds"]

# 7. The spine stays pure: no DOM, routing, or editor state in the Form module.
form_src = (ROOT / "src/04-form-core.js").read_text(encoding="utf-8")
for banned in ("document.", "window.", "querySelector", "render(", "nodes", "wires"):
    assert banned not in form_src, f"Form core must stay pure; found {banned!r}"

print("FORM SPINE PASS")
