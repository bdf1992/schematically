"""The fraktal as code: Knode, Kord, Korner, Kore, and the requirements they must meet, as checks.

One form at every level. A Knode makes one move through five positions and has eight ports. Nine Knodes,
twelve Kords and four Korners make a Fraktal; its shell has a Knode's eight ports, so it is one, and
any Knode may open into another Fraktal.

Second pass, after three independent reviews on 2026-10-10. What changed: every check reads the links
and the shell, never a flag set at build time; R6 is gone because every break of it was already a break
of R5 or R7; each bite must be reported by its own requirement and no other; what a check cannot test
is said beside it; and the kernel's import counts are printed beside what a random arrangement of the
same nine groups scores.

Third pass, after the fourth review: a link's direction and strand are held to the ports, a Korner's position
to the four it sits between and a Knode's key to its own layer and side; the drawing's shell is measured.

Run it: exit 1 when the model or a bite fails. Writes exports/fraktal-check.md. It runs cell_view.py for the
placement, which rewrites that script's own exports (kernel-cells*.sov and kernel-cells.md)."""
from __future__ import annotations

from dataclasses import dataclass, field

PLACES = ("-1", "0", "+1")
SEAMS = ("-0", "+0")
POSITIONS = ("-1", "-0", "0", "+0", "+1")
STEPS = (("-1", "Before"), ("-0", "Start"), ("0", "Now"), ("+0", "After"), ("+1", "Stop"))
LAYERS = {"+1": "Purpose", "0": "Dynamics", "-1": "Foundation"}
SIDES = {"-1": "user", "0": "external", "+1": "internal"}  # the owner's words; the middle one carries between the ends
ROWS = ("+1", "0", "-1")  # drawn top to bottom
COLS = ("-1", "0", "+1")  # drawn left to right

# The eight ports of a Knode: (edge, name, direction, strand). Drive carries a request, echo a result.
PORTS = (("west", "in", "in", "drive"), ("west", "out", "out", "echo"), ("east", "out", "out", "drive"), ("east", "in", "in", "echo"),
         ("north", "opened", "in", "drive"), ("north", "reports", "out", "echo"),
         ("south", "opens", "out", "drive"), ("south", "report", "in", "echo"))
OPPOSITE = {"west": "east", "east": "west", "north": "south", "south": "north"}
EDGE = {"west": lambda at: at[1] == "-1", "east": lambda at: at[1] == "+1",
        "north": lambda at: at[0] == "+1", "south": lambda at: at[0] == "-1"}


@dataclass
class Knode:
    layer: str
    side: str
    inside: "Fraktal | None" = None  # a Knode may open into a Fraktal
    ports: tuple = PORTS
    steps: tuple = STEPS

    @property
    def at(self):
        return (self.layer, self.side)


@dataclass
class Kord:
    """The seam between two side-neighbouring Knodes. Which strands it has is read from the links."""
    a: tuple
    b: tuple

    @property
    def at(self):
        (la, sa), (lb, sb) = self.a, self.b
        if la == lb:
            return (la, SEAMS[min(COLS.index(sa), COLS.index(sb))])
        return (("+0", "-0")[min(ROWS.index(la), ROWS.index(lb))], sa)

    @property
    def axis(self):
        return "side" if self.a[0] == self.b[0] else "layer"


@dataclass
class Korner:
    """Where four Knodes meet. It carries nothing."""
    at: tuple
    around: tuple


@dataclass
class Fraktal:
    knodes: dict = field(default_factory=dict)
    kords: list = field(default_factory=list)
    korners: list = field(default_factory=list)
    links: list = field(default_factory=list)  # (from knode, to knode, strand, count): the only record of what connects
    shell: dict = field(default_factory=dict)  # (edge, port name) -> the knodes that port reaches

    @property
    def kore(self):
        return self.knodes.get(("0", "0"))

    def strands(self, kord):
        have = {(a, b, s) for a, b, s, n in self.links if n}
        return {s for s, key in (("drive", (kord.a, kord.b, "drive")), ("echo", (kord.b, kord.a, "echo"))) if key in have}

    def closed_ports(self):
        """The ports the nine show when closed into one: read from the shell, not assumed."""
        by_name = {(edge, name): (edge, name, direction, strand) for edge, name, direction, strand in PORTS}
        return tuple(by_name[key] for key in self.shell if key in by_name and self.shell[key])


def step_distance(a, b):
    return abs(ROWS.index(a[0]) - ROWS.index(b[0])), abs(COLS.index(a[1]) - COLS.index(b[1]))


def neighbours(at):
    r, c = ROWS.index(at[0]), COLS.index(at[1])
    for dr, dc, edge in ((0, 1, "east"), (1, 0, "south")):
        if r + dr < 3 and c + dc < 3:
            yield (ROWS[r + dr], COLS[c + dc]), edge


def build(depth=1):
    """The model as intended: every Kord whole, nothing diagonal, the Kore opened `depth - 1` more times."""
    f = Fraktal()
    for layer in ROWS:
        for side in COLS:
            f.knodes[(layer, side)] = Knode(layer, side)
    for at in f.knodes:
        for other, _ in neighbours(at):
            f.kords.append(Kord(at, other))
            f.links.append((at, other, "drive", 1))
            f.links.append((other, at, "echo", 1))
    for r in range(2):
        for c in range(2):
            around = tuple((ROWS[r + i], COLS[c + j]) for i in (0, 1) for j in (0, 1))
            f.korners.append(Korner((("+0", "-0")[r], SEAMS[c]), around))
    for edge, name, _, _ in PORTS:
        f.shell[(edge, name)] = [at for at in f.knodes if EDGE[edge](at)]
    if depth > 1:
        f.kore.inside = build(depth - 1)
    return f


# ---- The requirements. Each returns what breaks it. LIMITS says what a check does not test. ----------
def r1_same_form(f):
    """R1 One form at every level: closed, the nine show a Knode's eight ports, each reaching the three Knodes on its edge."""
    out = []
    want = {(edge, name, direction, strand) for edge, name, direction, strand in PORTS}
    if set(f.closed_ports()) != want:
        out.append(f"closed, the nine show {len(f.closed_ports())} of a Knode's 8 ports")
    for (edge, name), reached in f.shell.items():
        should = {at for at in f.knodes if edge in EDGE and EDGE[edge](at)}
        if set(reached) != should or len(reached) != len(set(reached)):
            out.append(f"outer port {edge} {name} does not reach exactly the three Knodes on that edge")
        for at in reached:
            if at in f.knodes and not any(e == edge and n == name for e, n, _, _ in f.knodes[at].ports):
                out.append(f"outer port {edge} {name} reaches {at}, which has no such port")
    return out


def r2_places(f):
    """R2 Positions: nine Knodes at places, twelve Kords on one seam each, four Korners on two, each Korner between its own four."""
    out = [f"Knode at {k.at} is not at a place" for k in f.knodes.values() if k.layer not in PLACES or k.side not in PLACES]
    out += [f"Knode {k.at} is filed under {at}" for at, k in f.knodes.items() if at != k.at]
    out += [f"Kord at {k.at} is not on exactly one seam" for k in f.kords if sum(p in SEAMS for p in k.at) != 1]
    for k in f.korners:
        if not all(p in SEAMS for p in k.at):
            out.append(f"Korner at {k.at} is not on two seams")
        rows, cols = {a[0] for a in k.around}, {a[1] for a in k.around}
        if len(set(k.around)) != 4 or len(rows) != 2 or len(cols) != 2 or any(step_distance(a, b) > (1, 1) for a in k.around for b in k.around):
            out.append(f"Korner at {k.at} is not between four Knodes that meet")
        elif k.at != (("+0", "-0")[min(ROWS.index(r) for r in rows)], SEAMS[min(COLS.index(c) for c in cols)]):
            out.append(f"Korner at {k.at} is not where its own four Knodes meet")
    for name, have, want in (("Knodes", len(f.knodes), 9), ("Kords", len(f.kords), 12), ("Korners", len(f.korners), 4)):
        if have != want:
            out.append(f"{have} {name}, want {want}")
    if len({k.at for k in f.kords} | {k.at for k in f.korners} | set(f.knodes)) != 25:
        out.append("the 25 positions of the five by five are not each used once")
    return out


def r3_tileable(f):
    """R3 Tileable: every Knode has the eight ports, and across each shared edge an out faces an in of the same strand."""
    out = []
    want = {(edge, direction, strand) for edge, _, direction, strand in PORTS}
    side = lambda k, edge: {(d, s) for e, _, d, s in k.ports if e == edge}
    for at, knode in f.knodes.items():
        if {(e, d, s) for e, _, d, s in knode.ports} != want or len(knode.ports) != 8:
            out.append(f"{at} does not have the eight ports")
        for other, edge in neighbours(at):
            if other in f.knodes and {("in" if d == "out" else "out", s) for d, s in side(knode, edge)} != side(f.knodes[other], OPPOSITE[edge]):
                out.append(f"{at} and {other} do not plug together on the {edge} edge")
    return out


def r4_kords_whole(f):
    """R4 Every Kord is whole: one per pair of side-neighbours, and the links show both its drive and its echo strand."""
    out = []
    have = {frozenset((k.a, k.b)): k for k in f.kords}
    for at in f.knodes:
        for other, _ in neighbours(at):
            kord = have.get(frozenset((at, other)))
            if kord is None:
                out.append(f"no Kord between {at} and {other}")
                continue
            missing = sorted({"drive", "echo"} - f.strands(kord))
            if missing:
                out.append(f"Kord {kord.at} between {kord.a} and {kord.b} lacks {' and '.join(missing)}")
    seen = set()
    for a, b, strand, n in f.links:
        if not n:
            continue
        if strand not in ("drive", "echo"):
            out.append(f"link from {a} to {b} is on a strand no port has: {strand}")
        if a == b:
            out.append(f"{strand} link from {a} to itself")
        if (a, b, strand) in seen:
            out.append(f"{strand} link from {a} to {b} is listed twice")
        seen.add((a, b, strand))
        # The ports fix the direction: drive leaves by the east and south edges, echo by the west and north.
        if strand in ("drive", "echo") and sum(step_distance(a, b)) == 1 and (b in dict(neighbours(a))) != (strand == "drive"):
            out.append(f"{strand} link from {a} to {b} runs against the ports")
    return out


def r5_no_diagonal(f):
    """R5 No diagonal: no link joins two Knodes that differ in both layer and side."""
    return [f"{n} from {a} to {b} change layer and side at once" for a, b, _, n in f.links if n and all(step_distance(a, b))]


def r7_neighbours_only(f):
    """R7 Nearest neighbour: every link in one axis runs one step, along a Kord."""
    out = []
    for a, b, _, n in f.links:
        rows, cols = step_distance(a, b)
        if n and not (rows and cols) and rows + cols > 1:
            out.append(f"{n} from {a} to {b} skip a Knode")
    return out


def r8_five_steps(f):
    """R8 One move: every Knode steps through the five positions in order."""
    return [f"{k.at} does not step through -1, -0, 0, +0, +1" for k in f.knodes.values() if tuple(p for p, _ in k.steps) != POSITIONS]


def r9_nests(f):
    """R9 Nestable: an opened Knode's inside shows that Knode's own ports and meets R1 to R8 itself."""
    out = []
    for knode in f.knodes.values():
        inner = knode.inside
        if inner is None:
            continue
        if set(inner.closed_ports()) != set(knode.ports):
            out.append(f"inside {knode.at}: its shell does not show that Knode's ports")
        for req in REQUIREMENTS:
            out += [f"inside {knode.at}: {x}" for x in req(inner)]
    return out


REQUIREMENTS = (r1_same_form, r2_places, r3_tileable, r4_kords_whole, r5_no_diagonal, r7_neighbours_only, r8_five_steps, r9_nests)
LIMITS = {
    "R1": "Form means the eight ports and which Knodes each reaches. Whether the nine behave as one Knode (one move, one gate) is not tested here; tools/fraktal_run.py runs a move.",
    "R2": "Counts and positions only. That three layers and three sides are the right number is taken as given.",
    "R3": "Ports are matched by direction and strand. What travels through a port, and whether two Knodes agree on its content, is not modelled.",
    "R4": "A strand exists if one link says so. Nothing checks that a real line, call or record stands behind the link.",
    "R7": "Distance is counted on the three by three. A link between levels, from a Knode to one inside another, cannot be written, so it is not checked.",
    "R5": "It reads links between Knodes only; what a Korner is for is not modelled, so nothing is checked at one.",
    "R8": "Order only. No move is executed and no refusal exists in the model, so 'only Now may refuse' is not tested.",
    "R9": "The shell is compared with the Knode's ports by kind; no link joins an outer port to an inner one.",
}
DROPPED = "R6 (the two ends never connect directly) is not a check: every break of it is a break of R5 or of R7."


def key(req):
    return req.__doc__.split()[0]


def check(f):
    return {key(r): (r.__doc__.split(":")[0][len(key(r)) + 1:], r.__doc__, r(f)) for r in REQUIREMENTS}


def count(f):
    return len(f.knodes) + sum(count(k.inside) for k in f.knodes.values() if k.inside)


def bites():
    """Break the model once for each requirement. A bite counts only if that requirement reports it and no other does."""
    cases = {
        "R1": lambda f: f.shell.pop(("west", "in")),
        "R2": lambda f: f.korners.pop(),
        "R3": lambda f: setattr(f.knodes[("+1", "0")], "ports", PORTS[1:]),
        "R4": lambda f: f.links.remove((("+1", "0"), ("+1", "-1"), "echo", 1)),
        "R5": lambda f: f.links.append((("+1", "-1"), ("0", "0"), "drive", 1)),
        "R7": lambda f: f.links.append((("+1", "0"), ("-1", "0"), "drive", 1)),
        "R8": lambda f: setattr(f.knodes[("0", "0")], "steps", STEPS[::-1]),
        "R9": lambda f: f.kore.inside.shell.pop(("north", "opened")),
    }
    out = {}
    for name, change in cases.items():
        f = build(depth=2)
        change(f)
        out[name] = sorted(k for k, (_, _, breaks) in check(f).items() if breaks)
    return out


def survivors():
    """Breaks an earlier pass let through. Each must now be reported by something."""
    cases = {
        "every link deleted": lambda f: f.links.clear(),
        "every link reversed": lambda f: f.links.__setitem__(slice(None), [(b, a, s, n) for a, b, s, n in f.links]),
        "no Knodes, Kords or Korners": lambda f: (f.knodes.clear(), f.kords.clear(), f.korners.clear()),
        "every Knode cut to four ports": lambda f: [setattr(k, "ports", PORTS[:4]) for k in f.knodes.values()],
        "an outer port reaching one Knode three times": lambda f: f.shell.__setitem__(("west", "in"), [("+1", "-1")] * 3),
        "an outer port reaching the wrong three": lambda f: f.shell.__setitem__(("west", "in"), f.shell[("east", "out")]),
        "an extra drive link running west": lambda f: f.links.append((("+1", "0"), ("+1", "-1"), "drive", 1)),
        "a link from a Knode to itself": lambda f: f.links.append((("0", "0"), ("0", "0"), "drive", 1)),
        "a link listed twice": lambda f: f.links.append(f.links[0]),
        "a link on a strand no port has": lambda f: f.links.append((("+1", "-1"), ("+1", "0"), "gossip", 1)),
        "a Korner moved to another Korner's position": lambda f: setattr(f.korners[0], "at", f.korners[3].at),
        "a Knode filed under another's key": lambda f: f.knodes.__setitem__(("+1", "-1"), f.knodes[("-1", "+1")]),
    }
    out = {}
    for name, change in cases.items():
        f = build()
        change(f)
        out[name] = sorted(k for k, (_, _, breaks) in check(f).items() if breaks)
    return out


# ---- The same requirements put to the drawing and to the kernel ----------------------------------------
def tile(pid):
    return (ROWS[int(pid[1])], COLS[int(pid[2])])


DRIVE_PORTS, ECHO_PORTS = ("r-out", "s-out"), ("l-out", "n-out")


def from_drawing(doc):
    """Bdo's cell.sov as a Fraktal. A strand exists where he drew a line between two tiles; which strand it is
    is read from the port either end is on, so the order the file lists the two ends in does not matter."""
    f = build()
    f.links = []
    for w in doc["wires"]:
        ends = (w["a"], w["b"])
        if w.get("canvasId") != "canvas:global" or ends[0][:3] == ends[1][:3]:
            continue
        source = next((e for e in ends if e.endswith(DRIVE_PORTS + ECHO_PORTS)), None)
        if source is None:
            continue
        target = ends[1] if source == ends[0] else ends[0]
        f.links.append((tile(source), tile(target), "drive" if source.endswith(DRIVE_PORTS) else "echo", 1))
    # The shell is measured: an outer port reaches the tiles that sit directly inside a plane around the nine.
    outer = [c["id"] for c in doc["components"] if c["symbolId"] == "plane" and not c.get("parentId") and not c["id"].startswith("t")]
    inside = [tile(c["id"]) for c in doc["components"] if c.get("parentId") in outer and len(c["id"]) == 3 and c["id"][0] == "t" and c["id"][1:].isdigit()]
    f.shell = {(edge, name): [at for at in inside if EDGE[edge](at)] for edge, name, _, _ in PORTS} if outer else {}
    return f


def from_imports(between, position=None):
    """The kernel's code as links: an import between two tiles, at the positions given (the drawn ones by default)."""
    position = position or {f"t{r}{c}": (ROWS[r], COLS[c]) for r in range(3) for c in range(3)}
    f = build()
    f.links = [(position[a], position[b], "import", n) for (a, b), n in sorted(between.items())]
    return f


def import_score(f):
    diagonal = sum(n for a, b, _, n in f.links if all(step_distance(a, b)))
    skip = sum(n for a, b, _, n in f.links if not all(step_distance(a, b)) and sum(step_distance(a, b)) > 1)
    total = sum(n for _, _, _, n in f.links)
    return {"along a Kord": total - diagonal - skip, "diagonal": diagonal, "skip": skip, "total": total}


def shuffled(between, runs=2000, seed=20261010):
    """What any arrangement of the same nine groups scores: the tiles dealt to random positions."""
    import random
    import statistics
    rng = random.Random(seed)
    tiles = [f"t{r}{c}" for r in range(3) for c in range(3)]
    places = [(ROWS[r], COLS[c]) for r in range(3) for c in range(3)]
    scores = []
    for _ in range(runs):
        rng.shuffle(places)
        scores.append(import_score(from_imports(between, dict(zip(tiles, places)))))
    placed = import_score(from_imports(between))
    return {k: statistics.median(s[k] for s in scores) for k in ("along a Kord", "diagonal", "skip")}, \
        {"along a Kord": sum(1 for s in scores if s["along a Kord"] >= placed["along a Kord"]) / runs,
         "diagonal": sum(1 for s in scores if s["diagonal"] <= placed["diagonal"]) / runs,
         "skip": sum(1 for s in scores if s["skip"] >= placed["skip"]) / runs}


if __name__ == "__main__":
    import contextlib
    import io
    import json
    import runpy
    from pathlib import Path

    here = Path(__file__).parent
    with contextlib.redirect_stdout(io.StringIO()):
        cells = runpy.run_path(str(here / "cell_view.py"))
    drawing = json.loads(cells["SOURCE"].read_text(encoding="utf-8"))
    model, drawn, code = build(depth=3), from_drawing(drawing), from_imports(cells["between"])
    bitten, survived = bites(), survivors()
    bites_ok = all(v == [k] for k, v in bitten.items())
    survivors_ok = all(survived.values())

    md = ["# Fraktal requirements, checked by code", "",
          "Written by `tools/fraktal.py`, third pass, after four independent reviews on 2026-10-10.",
          "The requirements are functions over the links and the shell; each returns what breaks it.", "",
          "## The model, Kore opened twice (depth 3)", "", f"{count(model)} Knodes counted through every level.", "",
          "| Requirement | Holds | Breaks | What this check does not test |", "|---|---|---|---|"]
    got = check(model)
    for k, (short, doc, breaks) in got.items():
        md.append(f"| {doc.rstrip('.')} | {'yes' if not breaks else 'no'} | {'; '.join(breaks[:3])} | {LIMITS.get(k, '')} |")
    md += ["", DROPPED, "", "## Does each check bite", "",
           "The model is broken once for each requirement. A bite counts only if that requirement reports it and no other does.", "",
           "| Broken for | Reported by | Counts |", "|---|---|---|"]
    md += [f"| {k} | {', '.join(v) or 'nothing'} | {'yes' if v == [k] else 'no'} |" for k, v in bitten.items()]
    md += ["", "Breaks the first pass let through, and what reports each now:", "", "| Break | Reported by |", "|---|---|"]
    md += [f"| {k} | {', '.join(v) or 'NOTHING'} |" for k, v in survived.items()]

    md += ["", "## Your drawing, cell.sov, as drawn", "",
           "Tested on what a drawing can show: whether the nine have an outer shell, and which lines run between tiles.", "",
           "| Requirement | Holds | Breaks |", "|---|---|---|"]
    dgot = check(drawn)
    for k in ("R1", "R4", "R5", "R7"):
        short, doc, breaks = dgot[k]
        md.append(f"| {doc.rstrip('.')} | {'yes' if not breaks else 'no'} | {len(breaks)}: {'; '.join(breaks[:6])} |" if breaks else f"| {doc.rstrip('.')} | yes | |")
    md += ["", "R4 here is the model asking for more than you drew. Which pairs connect is still open in your own notes, so read the", "list as the lines the model would add, not as faults in the drawing."]

    score = import_score(code)
    base, share = shuffled(cells["between"])
    info, hold_of, HOLD = cells["info"], cells["hold_of"], cells["HOLD"]
    defaulted = [m for m in hold_of if (info[m].get("layer"), info[m].get("component")) not in HOLD]
    md += ["", "## The kernel's imports, at structure digest " + cells["typ"]["digest"][:16], "",
           "An import between two tiles is counted once per importing module and imported module (a directed pair).", "",
           "| | As placed | Median of 2,000 random placements |", "|---|---|---|"]
    for k in ("along a Kord", "diagonal", "skip"):
        md.append(f"| Imports that run {k if k == 'along a Kord' else ('diagonally' if k == 'diagonal' else 'past a Knode')} | {score[k]:,} | {base[k]:,.0f} |")
    md += [f"| All imports between tiles | {score['total']:,} | {score['total']:,} |", "",
           f"**These counts are not evidence about the kernel.** {share['along a Kord']:.0%} of random placements put as many imports along a Kord as this one does, "
           "so the placement fits the grid no better than chance.",
           f"Taken one kind at a time it is less even: {share['diagonal']:.0%} of random placements have as few diagonal imports, and "
           f"{share['skip']:.0%} have as many that pass a Knode. The placement trades diagonals for skips; the total along a Kord does not move.",
           f"{len(defaulted)} of {len(hold_of)} files are placed by a layer default and not by a choice; that default puts the shared record code "
           "(models, store, refusal, ids, paths) in a corner tile, which only two tiles touch.",
           "The placement was authored in one evening. Until it is redone with the shared code set apart, the import counts say nothing either way."]
    (cells["OUT"] / "fraktal-check.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")

    print("model:", {k: len(b) for k, (_, _, b) in got.items()})
    print("bites (each must be reported by itself only):", bitten, "ok" if bites_ok else "FAIL")
    print("earlier survivors now reported by:", survived, "ok" if survivors_ok else "FAIL")
    print("drawing:", {k: len(dgot[k][2]) for k in ("R1", "R4", "R5", "R7")})
    print("imports as placed:", score, "random median:", base, "share of random at least as good:", share)
    raise SystemExit(0 if not any(b for _, _, b in got.values()) and bites_ok and survivors_ok else 1)
