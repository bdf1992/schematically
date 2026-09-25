# Whole units, completion, and saved state

> **Non-authoritative horizon.** A first working slice of discrete units with progress, a completion gate, and a draft saved-state file (`.sav`). It does not change the `.sov` format or widen 0.1. The runtime direction is Issue #6's; this is one proof of it over the optimization examples.

## The idea

A chair is not 0.37 of a chair. It is either finished or it is not, and only a finished chair can be counted, sold or used downstream. Getting there takes progress of more than one kind:

- **materials**: four blanks have to arrive;
- **work**: 1.5 hours of labor (fewer, later in a batch, on a learning curve) have to be done.

Each requirement is a progress signal between 0 and 1. The **completion gate** reads each one as a binary completion (done or not) and fires only when all of them are done. Firing creates exactly one unit. Partial progress is state; only a firing is a count.

This is the split Issue #6 draws for the logic machine:

| Issue #6 | Here |
| --- | --- |
| signal state: the current value at an attachment | progress per requirement, held by the unit in progress |
| particle/event: a transition moving through topology | a completed unit moving to the next stage, or being counted at a sink |
| a data-defined gate evaluated on current input state | the completion gate: AND over binary completions, a truth table whose output is 1 only on the all-ones row |
| `(logicalTime, sequence)` ordering | every step is an event ordered by (time, sequence) |
| replayable trace | the event log; counts rebuild from it alone |

## Two kinds of whole units, and how they meet

There are now two meanings of "whole units", and they check each other:

- **Planning** (`optimize_sov.py`, stages marked `integer`): branch and bound chooses how many whole chairs and tables a horizon should make.
- **Execution** (`simulate_sov.py`): units are built one at a time; a unit exists only once its gate fires.

The simulator takes the optimizer's whole-unit plan as its targets and executes it. The QA requires two things:

- **The plan completes exactly:** 2 chairs and 5 tables on the base workshop; 18 chairs on the learning curve.
- **The work adds up to the optimizer's number:** the n-th unit of a horizon takes the curve's n-th step, use × (f(n) − f(n−1)). Those steps telescope, so a horizon's work equals the true curve: 39.42 h and 34.96 h, matching the optimizer to within 10⁻⁹.

Execution also reports what planning cannot see. The fractional optimum on the learning curve (13.64 chairs, 1.74 tables), rounded up to 14 and 2, is **not buildable**: it needs 76 blanks and a week's timber makes 72. The simulator builds 14 chairs and one table, then stalls with the second table's materials 60% in:

```
$ python scripts/simulate_sov.py examples/optimization/workshop.sov \
      --model examples/optimization/workshop.learning.opt.json --target chairs=14,tables=2

horizon 1  (clock 37.13 h, 335 events)
  chairs     completed  14 this horizon (14 total), stock 0
  tables     completed   1 this horizon (1 total), stock 0; in progress: materials [w-table-blanks 60%]
  cut        completed  72 this horizon (72 total), stock 0
  counted    w-chair-sales 14  w-table-sales 1
  stalled: tables short 1 (waiting on materials); cut short 4 (waiting on materials)
```

That table is not counted. It is carried.

## How the simulator runs

- **One worker, so the clock is the work done.** Stages are served nearest the market first: the first stage that can take material or do work does, else the next one upstream. That is a pull system.
- **Materials are pulled toward each input's `per`**, partially if that is all there is. Work on a unit starts once all its materials are in. A new unit is opened only while its stage still has budget, so materials are never drawn into a unit nobody has time to make.
- **Budgets and supplies refresh each horizon.** Labor resets; timber is delivered again, and leftover timber stays in stock.
- **Work in progress carries over.** A unit's time is fixed when its work starts, from its index within that horizon, and a carried unit finishes at that fixed time.
- **A recipe that splits a whole upstream unit** (4.5 blanks per chair) is refused (`FRACTIONAL_RECIPE`): a made unit cannot be halved.

## `.sav`: where the state lives

State cannot live in the `.sov`. `DATA-FORMATS.md` keeps a document to authored truth and rebuilds every runtime projection on load. So state goes in its own file, `soveraeign.schematic/state@0.0-draft`:

```text
.sav
├─ document    id, revision, file name, semantic fingerprint of the .sov it belongs to
├─ model       file name, semantic fingerprint of the quantities it was run with
├─ clock       time, sequence, horizon
├─ sources     stock on hand (timber left)
├─ stages      per stage: stock of finished units, completed (total and this horizon),
│              the unit in progress: materials received per input, work done / needed per resource
├─ counts      units counted per sink wire, always whole
├─ resources   this horizon's use against limit
└─ events      the ordered log: horizon, material, start, work, completed, counted, stalled | met
```

Loading a `.sav` against a document or model that differs in meaning from the one it names is refused (`DOCUMENT_CHANGED`, `MODEL_CHANGED`), with a next operation. **Save and resume equals running straight through:** the QA runs three horizons without stopping and three with a save and load between each, and requires the two states to be identical byte for byte. `examples/optimization/workshop.learning.week1.sav` is the example: week one, ending with the part-kitted table. The QA loads it and checks that week two finishes that table first.

### Decided: the save points at the document, pinned by meaning

**Option a** (decided): a `.sav` names its `.sov`; the `.sov` knows nothing of saves. The other options were:
- **b**, the document registering its saves: circular, because registering a save changes the document it pins.
- **c**, a `.sovpak` bundling a document with its saves: still open for when saves need to travel.

**The pin is a semantic fingerprint** (decided), `scripts/sov_fingerprint.py`, written `sem1:<sha256>`:

- The document is first normalized through the editor's own data core (`scripts/normalize_sov.mjs`). A hand-authored file, the same file after one editor save, and after two all have one fingerprint; the QA checks this for every example.
- Then an **allowlist** of meaning is hashed:
  - what exists: id and type;
  - what contains or hosts it: parent, surface, host kind and host id;
  - dimension and whether its interior is open;
  - signal mode, port faces, declared attachment points and `config.logic`;
  - what each wire joins, through which points, and its direction and operations.
- Everything else is left out: position, size, where along a side a point sits, labels, colors, titles, editor flags, revision.
- A new field counts only if it is added to the list on purpose, so a presentation field can never invalidate saves by accident.
- For the model, only `note` fields are ignored; every number counts.

The QA checks both directions:
- **Keep the save:** moving a component, relabelling it, sliding a point along its side, retitling, reordering or bumping the revision, rewording a note.
- **Refuse the save:** moving a wire's end, retyping a component, lifting it out of its Plane, re-hosting a point, changing a limit.

## Residuals

| Gap | What closes it |
| --- | --- |
| One worker; every stage shares one clock | stations or workers as resources with their own clocks, so stages run in parallel; then time and labor separate |
| A fixed dispatch rule (nearest the market first) | dispatch as declared policy data, and the optimizer's sequencing, once time is a decision (the scheduling row in `LINEAR-NONLINEAR-SYSTEMS.md`) |
| Partial pulls can deadlock two stages competing for one input | reservation: a unit claims its full kit or nothing, or an explicit priority |
| A learning curve restarts each horizon | curve index across horizons, if learning is meant to persist |
| The event log is most of the file (70 KB for one week) | snapshot plus log as separate members, or logs as receipts beside the save |
| Gate rules other than AND (any-of, k-of-n, threshold) | the gate as a data-defined truth table (Issue #6's shape); AND is the only rule so far |
| Editor, API, MCP | the runtime in the data core, with the same legality and receipts on every surface; post-RC |

## Visualization

These runs feed `OPTIMIZATION-VISUALIZATION.md` directly. View A's stage ring becomes the unit in progress: one arc per requirement, filled to its progress, closing when the gate fires. Counts on sink wires tick in whole steps. A stall is drawn at the stage that stalled, with its reason. The event log is what an animated replay steps through.

## Decisions

- **Save relation:** option a, decided. Option c (a package bundling saves) remains for when saves need to travel.
- **Pin:** a semantic fingerprint, decided.
- **Name:** `.sav` it is. The schema tag keeps the family name: `soveraeign.schematic/state`.

## Try it

```
python scripts/simulate_sov.py examples/optimization/workshop.sov
python scripts/simulate_sov.py examples/optimization/workshop.sov --model examples/optimization/workshop.learning.opt.json \
    --target chairs=14,tables=2 --out week1.sav
python scripts/simulate_sov.py examples/optimization/workshop.sov --model examples/optimization/workshop.learning.opt.json \
    --target chairs=14,tables=2 --sav week1.sav --out week2.sav
python tests/simulate_sov_qa.py
```
