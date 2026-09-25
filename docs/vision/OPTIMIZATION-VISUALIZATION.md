# Visualizing optimization runs

> **Non-authoritative plan.** This plans how the runs of `scripts/optimize_sov.py` become pictures. Nothing here is built yet. It does not widen 0.1. `LINEAR-NONLINEAR-SYSTEMS.md` describes the solvers themselves. `VISUAL-LANGUAGE.md` extends this plan to the simulator and the logic runtime and fixes one visual grammar for all three.

## What needs to be seen

A run answers four questions. Each needs its own picture, because each lives in a different space:

| Question | Space it lives in | View |
| --- | --- | --- |
| What does the plan do, and where? | the schematic's own topology | **A. Plan overlay** on the diagram |
| How wrong is the model's curve? | one effect: quantity → use or value | **B. Curve view** |
| Where are the good plans, and where are the traps? | the free decisions (chairs × tables) | **C. Landscape** |
| How did the solver get there, and how sure is it? | the search itself | **D. Search tree**, **E. Convergence** |
| What is one more unit of a limit worth? | one limit swept over a range | **F. Marginal value** |
| How do runs differ? | runs × methods | **G. Run ledger** and diff |

A and G are about the *plan*. B, C and F are about the *problem*. D and E are about the *method*. Keeping these apart is the typology. Mixing them is how a picture ends up suggesting a local answer is the answer.

## Rules every view keeps

1. **A run is a record; a picture is a projection of it.** The solver writes a run record. Views read it and never compute. The same rule as the editor's: SVG is never the source of truth. A view that needs a number the record lacks is a change to the record, not to the view.
2. **The certificate is always visible.** Every value carries its kind: *global* (proven: LP duality, a branch-and-bound bound met), *local* (a climb stopped here), *measured* (solved again with the limit raised), or *approximate* (segments). Encoding: global is solid, local is hollow or dashed, measured is a step, approximate is a band. Never color alone, and every view has a legend line naming the kind.
3. **Units and scale on every mark.** A flow is "58.6 blanks/week", not a thickness alone.
4. **Error direction is shown, not implied.** Segment error is safe for convex bends and optimistic for nonconvex ones. The curve view shades the region between chord and curve and labels which side it errs on.
5. **Light and dark, from the app's own ink.** Colors come from the existing surface-relative palette (`themeColor`, `ensureContrast`) so overlays sit on the diagram the way its wires do.
6. **Deterministic.** The same run record renders to byte-identical SVG, so a picture can be checked in and diffed like the `examples/*.svg` exports.

## The run record

A new draft schema, `soveraeign.schematic/optimization-run@0.0-draft`, written by `optimize_sov.py --record run.json`. It holds what the report prints today, plus the traces the views need. Most of the traces are not recorded yet.

```text
run
├─ inputs        document id + sha256, model path + sha256, method, segments, starts, seed, node limit
├─ certificate   global | local | approximate, with status (optimal | node_limit) and gap
├─ plan          activity per stage, flow per wire (ids as in the document)
├─ evaluated     true value; use / limit / binding per resource; supply use
├─ prices        per limit: value, kind (exact | local | measured)
├─ bends         per bent term: label, shape, breakpoints, chord values, true values, operating point, ordered?
├─ search        (exact)  branch-and-bound nodes: id, parent, variable, bound side, LP value,
│                          outcome (branched | pruned | incumbent | infeasible), incumbent after
├─ climbs        (gradient) per start: start point, path of (y, value, worst violation) per step,
│                          outer iterations (rho, multipliers), optimum id it ended in
├─ optima        (gradient) distinct optima: point, value, violation, basin share
└─ sweeps        optional: limit → objective, for view F; optional: enumerated grid, for view C
```

Traces can be large. Climbs record every accepted step, but a path is thinned to its turning points (Ramer–Douglas–Peucker at 0.2% of the box) before it is written. The branch-and-bound log is capped at the node limit. A record states what it thinned.

## The views

### A. Plan overlay: the plan on the diagram

The diagram is already the best map of the system, so the plan is drawn on it rather than beside it.

- **Wires** carry their flow: a label ("58.6 blanks") at the route's midpoint, and a translucent band under the wire whose width scales with the square root of the flow, so area tracks quantity. The band is a separate overlay layer. The wire itself, its color, packets and rate are untouched: packet travel is a claim about rate, and the plan is not allowed to change it.
- **Stages** carry activity against capacity as a thin ring around the component: filled fraction = utilization. A stage at capacity gets a closed ring and a *binding* tick. Whole-unit stages show the integer ("18 chairs").
- **Planes** carry the resources they scope: a gauge on the boundary for each (labor 34.96 / 40 h). A binding limit is drawn at full length with its price chip ("$2.68/h local · $15 measured").
- **Sources** show supply used against supply; **sinks** show value delivered.
- **Diff mode** (two runs): each wire shows the change in flow as +/−, each gauge shows both fills. This is the linear vs nonlinear comparison drawn on the system: the linear plan's chair wire is fat and the labor gauge overflows past its limit, in a hatched overflow segment.

Built on the existing headless export. `export_svg.py` renders the document; the overlay is then placed by the element ids the renderer already writes (`data-id` on components, `data-wire-id` on wires) and the route geometry already in the page. No render code changes for the headless version.

### B. Curve view: the model's curve against the true one

One small chart per bent term (saw congestion, chair saturation, the learning curve):

- x: the stage's quantity, 0 → its bound; y: use or value.
- The true curve as a line; the segments as a polyline with breakpoints marked; the region between them shaded and labelled *safe* or *optimistic*.
- The operating point from the run, with its true and modelled values.
- A strip beneath: error at the operating point for 4, 8, 16, 32, 64 segments.

This is the picture that explains linear vs nonlinear in one glance. The linear model is the tangent at zero drawn on the same axes: for the saw it runs under the congestion curve, which is exactly why its plan overran labor by 8 hours.

### C. Landscape: where the good plans and the traps are

For two free decisions (chairs × tables in both workshop models), the whole problem fits on one plane:

- **Background:** true value as filled contours over the feasible region. Infeasible area is hatched, not colored, so it cannot be read as low value.
- **Limits as curves:** the labor limit is a curve (congestion and learning bend it), the timber limit a straight line. The binding one at the optimum is emphasised and labelled.
- **Whole-unit grid** (when units are integer): a dot per feasible whole plan; local optima of the grid ringed (six in the learning model), the global one filled.
- **Climbs:** each start's path from its start marker to where it stopped, colored by the optimum it reached. The basin share goes in the legend ("23/24 → $823.07; 1/24 → $701.39"). The all-tables trap reads as a path running down the chairs = 0 edge and stopping.
- **Exact answer:** a filled marker, labelled *global*. Local optima are hollow and labelled *local*.

More than two free decisions: pairwise slices through the best plan (a small grid of landscapes, other decisions held at their optimum), labelled as slices. A slice can hide a trap, and the label says so.

### D. Search tree: how branch and bound spent its nodes

- A tree, root on top: each node is an LP, labelled with its bound; each edge is the branch (chairs ≤ 1, chairs ≥ 2).
- Outcome by shape and fill: branched (open), pruned (struck through, with the incumbent that pruned it), incumbent (filled), infeasible (crossed).
- Beside it, the **gap chart**: best bound and incumbent against nodes explored. The lines meet at *optimal*. A run stopped at the node limit shows the gap left open, which is the honest picture of a `node_limit` answer.

For nonconvex bends, the ordering binaries are drawn in the tree like any other branch. Their labels name the segment ("learning curve: segment 7 full").

### E. Convergence: how far each method is from done

- **Segments:** true value of the plan against segment count (log scale), with the exact answer as a reference line. Shows the error closing, and shows an optimistic model's plan turning infeasible below a threshold (the learning curve at 20 segments).
- **Climbs:** value and worst violation against step for each start, one small line per start, colored by basin. The augmented Lagrangian's penalty increases are ticks on the axis.
- **Basin share:** one bar per distinct optimum, length = share of starts. Beside it a note on how the starts were placed (corners, centre, random), since a missing bar can mean a missing start.

### F. Marginal value: what one more unit is worth

A limit swept over a range (labor 30 → 50 h), each point a full solve:

- the objective as a step function (whole units make it lumpy);
- the shadow price drawn as a short tangent segment at the current limit, labelled with its kind;
- the step at 41 h annotated: "+$15: a different plan (13 chairs, 2 tables) becomes reachable".

This is the picture for the finding that a local price cannot see a better plan in another valley. The sweep is recorded in the run (`sweeps`), so the view stays a pure projection. A sweep costs one solve per point, so it is opt-in (`--sweep labor=30:50:1`).

### G. Run ledger and diff

A table of runs for one document: method, certificate and status, value (modelled and true), feasibility, binding limits, time, inputs hash. Selecting two runs opens diff mode in view A. The ledger is how a person reads the typology: which answers are proven, which are local, which are approximate.

## Where the views live

Delivered in the order that each stage proves the next:

| Phase | Surface | Views | What it needs |
| --- | --- | --- | --- |
| 1 | **Headless files.** `scripts/plot_run.py run.json --out dir/` writes one standalone SVG per view: pure Python, no plotting dependency, the same way `export_svg` writes files people embed in markdown | B, C, D, E, F | the run record, with traces (`--record`) |
| 2 | **Overlay on the export.** `export_svg.py a.sov --run run.json` adds the plan layer to the diagram export | A, A-diff | phase 1's record; element ids already in the render |
| 3 | **A run page.** One HTML page per run, or per pair of runs, bundling the diagram overlay with B–F and the ledger. It is the artifact to share or review | all | phases 1 and 2 |
| 4 | **In the editor**, post-RC. A new owning module (per `MODULES.md`, one concern) renders the overlay live; `optimize.run` becomes a data-core operation served identically to UI, API and MCP (the parity rule) | A, G first | the record schema settled; a decision to put quantities in the file or keep the sidecar |

Phase 4 waits on two things the repo already guards: the RC boundary, and the rule against inert configuration. An optimization panel in the editor ships only when every control on it changes something observable.

## How each view is checked

Each view gets a QA suite in the style of `svg_export_qa.py` and `loop_svg_qa.py`: the picture's claims are checked against the record, by a path the renderer did not choose.

- **Determinism:** the same record renders byte-identical SVG, twice.
- **A:** every wire label equals the plan's flow for that wire id. Every gauge's fill equals use/limit, and exceeds its track exactly when the record says the limit is broken.
- **B:** breakpoints plotted equal the record's; the shaded side matches the bend's shape (convex → safe).
- **C:** the global marker sits at the record's best plan; every ringed dot is a grid local optimum by the QA's own neighbourhood check (the one `optimize_sov_qa.py` already has); every climb ends at its optimum's marker.
- **D:** node count and outcomes equal the log; the gap chart's last bound and incumbent equal the record's.
- **F:** each step's height equals the difference of two recorded solves.
- **Legibility:** every label passes the app's contrast floor in light and dark (`ensureContrast`), checked on the rendered file.

## Work, in order

1. **Record traces** in `optimize_sov.py`: bend geometry, branch-and-bound log, climb paths, optimum ids; `--record` writes the run schema; `formats/schematic.optimization-run.schema.json` validates it. Small, and everything else depends on it.
2. **Curve view (B)** and **landscape (C)**: the two views that explain the most. They make linear vs nonlinear and local vs global visible.
3. **Search tree and convergence (D, E).**
4. **Plan overlay (A) and diff** on the headless export.
5. **Marginal sweep (F)**, with `--sweep`.
6. **Run page** bundling all views.
7. Editor surface, after the RC and the file-format decision.

Steps 1 to 5 are stated, mapped work: each is a candidate for a contract with its acceptance being the QA above.

## Decisions this plan needs

- **Where people should see runs first:** as files next to the document (phase 1), or as a shareable run page (phase 3). The order above assumes files first.
- **Whether the plan may touch the wire's own stroke.** This plan says no: the plan is an overlay band, and the wire keeps its semantics. The alternative, the wire's width standing for flow, reads more directly but gives the wire a second meaning.
- **Sidecar or file** for quantities and runs. This plan keeps runs as separate records, so it works with either answer.
