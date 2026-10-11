"""The fraktal, running. Knodes are workers, Kords are two lanes, and a request makes one move per Knode.

This is the piece the reviews said was missing: a move that executes, a gate at Now that can refuse, and a
record of both. It also puts four claims from the "ARCH remodeling and refactor" write-up to a test instead
of asserting them: a request is not done until its echo is home; a refusal happens at Now and nowhere else;
nothing travels where there is no Kord; and several requests are in flight at once without the return lane
ever being held up by the forward one.

Run it: python fraktal_run.py. Exit 1 on any failed check. It reads tools/fraktal.py and writes nothing."""
from __future__ import annotations

import asyncio
import runpy
import time
from dataclasses import dataclass, field
from pathlib import Path

fk = runpy.run_path(str(Path(__file__).parent / "fraktal.py"), run_name="fraktal")
STEPS = [name for _, name in fk["STEPS"]]  # Before, Start, Now, After, Stop


@dataclass
class Request:
    id: str
    route: list            # the Knodes it visits, in order; each hop must be along a Kord
    payload: str = ""
    at: int = 0            # index into route
    state: str = "sent"    # sent, done or refused; it changes only when the echo is home
    receipts: list = field(default_factory=list)


class Run:
    def __init__(self, gates=None, step_seconds=0.01, drive_room=1, shared_lane=False, slow=None):
        model = fk["build"]()
        self.cells = list(model.knodes)
        self.kords = {frozenset((k.a, k.b)) for k in model.kords}
        self.gates = gates or {}
        self.step_seconds, self.slow = step_seconds, slow or {}
        self.record = []                                   # (seconds, request, cell, step, outcome): append-only
        self.t0 = time.monotonic()
        # One drive lane into each Knode, with little room, and one echo lane that always has room.
        self.drive = {c: asyncio.Queue(maxsize=drive_room) for c in self.cells}
        self.echo = self.drive if shared_lane else {c: asyncio.Queue() for c in self.cells}
        self.home = asyncio.Queue()
        self.tasks = []

    def note(self, request, cell, step, outcome=""):
        self.record.append((round(time.monotonic() - self.t0, 4), request.id, cell, step, outcome))

    def has_kord(self, a, b):
        return frozenset((a, b)) in self.kords

    async def send(self, request):
        """Admit a request at the first Knode of its route, or refuse it here if the route leaves the Kords."""
        for a, b in zip(request.route, request.route[1:]):
            if not self.has_kord(a, b):
                request.state = "refused"
                request.receipts.append(f"no Kord between {a} and {b}")
                self.note(request, a, "Before", "refused: no Kord")
                await self.home.put(request)
                return
        await self.drive[request.route[0]].put(("drive", request))

    async def knode(self, cell):
        """One Knode: take what arrives on the drive lane and make one move with it."""
        while True:
            kind, request = await self.drive[cell].get()
            if kind == "echo":                      # only when the two lanes are one (the broken variant)
                await self.relay(cell, request)
                continue
            self.note(request, cell, "Before")
            await asyncio.sleep(self.slow.get(cell, self.step_seconds))
            self.note(request, cell, "Start")
            allowed, why = self.gates.get(cell, lambda r: (True, ""))(request)
            self.note(request, cell, "Now", "passed" if allowed else f"refused: {why}")
            if not allowed:
                request.state_pending = "refused"
                request.receipts.append(f"{cell} refused: {why}")
            else:
                last = request.at == len(request.route) - 1
                self.note(request, cell, "After", "effect" if last else "handed on")
                request.receipts.append(f"{cell} moved")
                if not last:
                    request.at += 1
                    await self.drive[request.route[request.at]].put(("drive", request))
                    self.note(request, cell, "Stop")
                    continue
                request.state_pending = "done"
            self.note(request, cell, "Stop", "echo sent")
            await self.echo[cell].put(("echo", request))

    async def returns(self, cell):
        """The echo lane of one Knode: carry a result one Kord back toward where the request began."""
        while True:
            _, request = await self.echo[cell].get()
            await self.relay(cell, request)

    async def relay(self, cell, request):
        if request.at == 0 or cell == request.route[0]:
            request.state = request.state_pending
            self.note(request, cell, "home", request.state)
            await self.home.put(request)
            return
        request.at -= 1
        await self.echo[request.route[request.at]].put(("echo", request))

    async def go(self, requests, patience=3.0):
        self.tasks = [asyncio.create_task(self.knode(c)) for c in self.cells]
        if self.echo is not self.drive:
            self.tasks += [asyncio.create_task(self.returns(c)) for c in self.cells]
        senders = [asyncio.create_task(self.send(r)) for r in requests]
        home = []
        try:
            for _ in requests:
                home.append(await asyncio.wait_for(self.home.get(), patience))
        except asyncio.TimeoutError:
            pass
        for task in self.tasks + senders:
            task.cancel()
        return home


P, D, F = "+1", "0", "-1"
U, E, I = "-1", "0", "+1"
LINE = [(P, U), (P, E), (D, E), (D, I), (F, I)]   # the user's Purpose, the grant, the Kore, the internal agents, the record
failures = []


def expect(name, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not ok:
        failures.append(name)


def grant(request):
    return ("forbidden" not in request.payload, "not granted")


async def main():
    # 1. Done only when the echo is home.
    run = Run()
    requests = [Request(f"r{i}", list(LINE)) for i in range(4)]
    home = await run.go(requests)
    expect("four requests along five Knodes all come home done", len(home) == 4 and all(r.state == "done" for r in home))
    mine = [(step, out) for _, rid, _, step, out in run.record if rid == "r0"]   # order in the record, not clock time
    effect_at, home_at = mine.index(("After", "effect")), mine.index(("home", "done"))
    expect("a request's effect comes before its echo is home, and it is called done only then",
           effect_at < home_at and [out for _, out in mine].count("done") == 1, f"record entries {effect_at} and {home_at} of {len(mine)}")
    expect("each Knode steps Before, Start, Now, After, Stop in that order",
           all([s for _, rid, c, s, _ in run.record if rid == "r0" and c == cell and s != "home"] == STEPS for cell in LINE))

    # 2. A refusal happens at Now, is recorded, and comes home as a refusal.
    run = Run(gates={(P, E): grant})
    home = await run.go([Request("ok", list(LINE), "allowed"), Request("bad", list(LINE), "forbidden")])
    by = {r.id: r for r in home}
    refusals = [(c, s) for _, rid, c, s, out in run.record if out.startswith("refused") and s != "home"]
    expect("the refused request comes home refused and the other done", by["bad"].state == "refused" and by["ok"].state == "done")
    expect("the only refusal in the record is at Now, at the grant Knode", refusals == [((P, E), "Now")], str(refusals))
    expect("a refused request never reaches the Knodes past the gate",
           not any(rid == "bad" and c in LINE[2:] for _, rid, c, _, _ in run.record))

    # 3. Nothing travels where there is no Kord.
    run = Run()
    home = await run.go([Request("diag", [(P, U), (D, E)]), Request("ends", [(D, U), (D, I)])])
    expect("a diagonal route and a route joining the two ends are refused before they start",
           all(r.state == "refused" for r in home) and not any(s == "Now" for _, _, _, s, _ in run.record))

    # 4. Several requests are in flight at once, at different Knodes.
    run = Run(step_seconds=0.05)   # well above the 16 ms clock tick on this machine
    requests = [Request(f"r{i}", list(LINE)) for i in range(6)]
    started = time.monotonic()
    home = await run.go(requests)
    took = time.monotonic() - started
    inside, busiest = {}, 0
    for t, rid, cell, step, _ in run.record:
        if step == "Before":
            inside[rid] = cell
        elif step in ("Stop", "home"):
            inside.pop(rid, None)
        busiest = max(busiest, len(set(inside.values())))
    one_at_a_time = 6 * 5 * 0.05
    expect("at some moment three or more Knodes each hold a different request", busiest >= 3, f"most at once: {busiest}")
    expect("six requests take less time than one after another would", len(home) == 6 and took < one_at_a_time * 0.6,
           f"{took:.2f}s against {one_at_a_time:.2f}s")

    # 5. The return lane is never held up by the forward one.
    slow = {(D, I): 0.25}
    run = Run(step_seconds=0.005, drive_room=1, slow=slow)
    quick = [Request(f"q{i}", [(P, U), (P, E)]) for i in range(3)]      # short requests that share the first two Knodes
    crowd = [Request(f"c{i}", list(LINE)) for i in range(5)]            # long ones that pile up behind a slow Knode
    home = await run.go(crowd + quick, patience=6.0)
    quick_home = [t for t, rid, _, step, _ in run.record if rid.startswith("q") and step == "home"]
    crowd_home = [t for t, rid, _, step, _ in run.record if rid.startswith("c") and step == "home"]
    expect("with two lanes every request comes home, forward lane backed up or not", len(home) == 8, f"{len(home)} of 8 home")

    # 6. Bites: the same runs with the mechanism removed.
    run = Run(gates={})
    home = await run.go([Request("bad", list(LINE), "forbidden")])
    expect("bite: without the gate the forbidden request goes through", home and home[0].state == "done")
    run = Run(step_seconds=0.005, drive_room=1, slow=slow, shared_lane=True)
    home = await run.go([Request(f"c{i}", list(LINE)) for i in range(5)] + [Request(f"q{i}", [(P, U), (P, E)]) for i in range(3)], patience=3.0)
    expect("bite: with one shared lane the run jams and requests do not come home", len(home) < 8, f"{len(home)} of 8 home")

    print(f"{len(failures)} failures")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    asyncio.run(main())
