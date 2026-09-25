# Linear and nonlinear systems in Schematically

> **Non-authoritative horizon.** This records a discovery pass over what the runtime already computes, sorts it by kind, and starts an optimization model on top of the same topology. It does not widen 0.1 and does not change the file format. `ROADMAP.md` and `RC-FINISH-LINE.md` stay authoritative.

## Why this exists

A schematic already says what exists and what connects. The question here is whether the same model can say *how much*: given limits in time or materials and a target, what should each part do, and what is each limit worth? To answer that honestly, first sort out what the runtime already computes and which kind each computation is.

## 1. What already computes, and what kind it is

Every row below is code that runs today. "Kind" is the mathematical type; "where" is the place in the Point / Path / Plane topology it belongs to.

| System | Where it lives | Kind | What makes it linear or not |
| --- | --- | --- | --- |
| **Rate composition**: effective rate = global × source Component × Wire | `15-editor-kernel.js:200` | **Multiplicative** (linear in each factor, nonlinear together; linear in log-rate) | Each factor is clamped to [0.1, 8]: a saturating piecewise-linear limit |
| **Packet travel time**: clamp(L / 175, 0.72, 4.5) / rate | `55-render.js:306`, `:341` | **Piecewise linear** in path length, **hyperbolic** in rate | Two saturation corners, then 1/rate. Halving rate doubles time; doubling rate past the floor does nothing |
| **Signal activation**: sources on, relays on when a valid incoming Wire is live | `25-signal.js` `computeSignalState` | **Boolean fixpoint** (monotone OR over the graph) | Discrete and nonlinear, but monotone, so it converges. Bounded at 6 passes, which caps chain depth: a relay 7 hops from a source never lights |
| **Color diffusion**: each node becomes a weighted mean of itself (1.45) and its live inputs (1 each) | `25-signal.js`, `mixHex` in `00-state.js:182` | **Linear operator** x_{k+1} = W x_k, iterated 5 times | Linear in RGB; nonlinear only through 8-bit rounding and because sRGB is not perceptually linear. The steady state would be a linear solve, (I − W′)x = b |
| **Contrast floor**: move a color toward white or black until WCAG contrast ≥ floor | `00-state.js:210–229` | **1-D nonlinear constraint, solved by bisection** | Relative luminance is a gamma power curve, so contrast in t is monotone but not linear. The runtime already does constrained optimization: *smallest shift t such that contrast(t) ≥ floor* |
| **Wire routing**: choose the lowest-cost orthogonal route among candidates | `40-routing.js:117` `pathScore`, `:274` `routePoints` | **Combinatorial search** over a **linear weighted cost** | length + 46·bends + 2.2·backtrack + 90·crossings + 5·shared + 1.6·hugging. Bends and crossings are integers; hugging is a hinge (max(0, 12 − d)). Wires route one at a time against `occupied`, so the result depends on order: greedy, not a global optimum |
| **Route hysteresis**: keep the latched route unless a new one beats it by 72 | `40-routing.js:428`, `ROUTE_SWITCH_MARGIN` | **State-dependent** (memory) | The same geometry can produce two different routes depending on history. Deliberate, for stability while dragging |
| **Loop period**: shortest period P where every travel time d snaps to P/k within a budget | `scripts/loop_svg.py` `choose_period` | **Mixed-integer minimax**, solved by grid search | minimize P subject to max_i abs(P/k_i − d_i)/d_i ≤ budget, k_i integer. Nonconvex in P; grid search is the honest method |
| **Render cost**: 8.3 ms at 5 Components, 18 ms at 10 | `PERFORMANCE.md` | **Superlinear** in entity count | Each wire routes against every obstacle and every occupied segment: roughly O(W · (C + W) · candidates) |

### The shape of it

Sorted by kind, the runtime has one of each family already:

- **linear**: color diffusion, the routing cost function itself;
- **piecewise linear / saturating**: rate clamps, travel-time clamps, the hugging hinge;
- **smooth nonlinear**: luminance/contrast, 1/rate;
- **discrete / combinatorial**: routing candidates, the loop period's integer divisors;
- **fixpoint / logical**: signal activation (the seed of the Issue #6 logic machine);
- **stateful**: route hysteresis.

And sorted by topology:

- **0D Points** carry direction and access: the constraints of the signal fixpoint (`endpointAllowsEmit`, `endpointAllowsAccess`).
- **1D Paths / Wires** carry rate, length and travel time: the *flow* quantities.
- **2D Planes** bound regions: today they bound legality (no reach-through). They are the natural place to bound *resources* too.
- **The global Space** carries the one global coefficient (time scale).

The palette already has a word for the missing piece: **LIMIT**, "restricts a flow dimension without judgement." It has no quantity behind it yet.

## 2. An optimization model on the same topology

`scripts/optimize_sov.py` is a first, working model. It reads the topology from a `.sov` and the quantities from a sidecar `<name>.opt.json`, so the document format does not change.

### The mapping

| Schematic | Optimization |
| --- | --- |
| Component (stage) | an activity level x_c, with an optional capacity |
| Component with role `source` | supply bound on its outflow |
| Component with role `sink` | earns value on its inflow |
| Wire a → b | a flow x_w |
| Wire into a stage, with `per` | a recipe: x_w = per · x_c (Leontief input) |
| Wires out of a stage | share its output: Σ x_out = yield · x_c |
| Point on a boundary | a relay: flow in = flow out |
| Plane | the scope of a resource: only Components inside draw on it. A Component outside that tries is refused (`OUT_OF_SCOPE`), the same rule as boundary legality |
| resource (labor hours, machine time, a material budget) | a limit row: Σ use_c · f(x_c) ≤ limit |

### Linear core, nonlinear effects

The core is a linear program. Nonlinear effects bend one term each:

- `saturation` on a value: k · (1 − e^{−q/k}). Each further unit sells for less. **Concave.**
- `congestion` on a resource use: x · (1 + (x / cap)^p). A stage near capacity costs more per unit. **Convex.**
- `economies` (x^p): cheaper at scale, or accelerating value. **Nonconvex in the direction that matters.**

Concave value and convex cost together form the **convex case**. There the solver turns each bent term into linear segments; because the slopes are ordered, the simplex fills them in order without integer variables, and the error shrinks as segments are added. The nonconvex case (economies of scale, setup costs, minimum batch sizes) needs integer choice. The solver **refuses** it with a reason (`NONCONVEX`) and does not return a plausible-looking wrong answer.

Every run returns:

- the plan: activity per stage, flow per wire;
- its value under the model *and* re-evaluated under the true curves (so approximation error is visible, not assumed);
- a **shadow price** per resource, supply and capacity: what one more unit of that limit is worth. This is the efficiency signal. It tells you which constraint to relax and which is free.

### The worked example

`examples/optimization/workshop.sov`: timber enters a Shop floor Plane through a boundary Point, is cut into blanks, and becomes chairs (4 blanks, 1.5 h) or tables (10 blanks, 4 h), which leave through two boundary Points to a market. Labor is 40 h a week, scoped to the Shop floor. The saw congests as it nears 90 blanks. Chairs sell into a small market that saturates.

```
$ python scripts/optimize_sov.py examples/optimization/workshop.sov --compare

linear model  (11 variables, 11 rows)
  plan value (as the model sees it) 1043.48 USD
  plan value (under the true curves) 340.16 USD   <- INFEASIBLE under the true curves
    chairs 17.39   cut 69.57   tables 0.00
    labor 48.31 / 40.00  shadow 26.09 USD/h  OVER

nonlinear model  (75 variables, 13 rows, 2 bent terms x 32 segments)
  plan value 710.79 USD (as modelled and as evaluated)
    chairs 1.25    cut 58.59   tables 5.36
    labor 40.00 / 40.00  shadow 14.18 USD/h
    timber            shadow  0.00 USD per board-ft
```

The linear model makes two mistakes, one for each effect:

1. **It overruns the labor limit by 8 hours.** It prices saw time at its uncongested rate, so its plan cannot run in 40 hours.
2. **It overproduces chairs.** It prices every chair at $60, but past the first few the market pays much less. Judged by the true curves, its plan is worth $340, not $1043.

The nonlinear plan mixes products because saturation creates an interior optimum. The shadow prices say what to do next: **one more labor hour is worth about $14; more timber is worth nothing** until labor is relieved. Refining the breakpoints moves the value only from 694 (4 segments) to 706 (8), 710.8 (32) and 711.1 (128). The error is bounded and visible.

## 3. How this fits the direction

- **Data-driven language (Issue #4).** Quantities belong in data, not code. The sidecar is a draft of what a domain pack's quantitative layer could look like: `uses`, `per`, `yield`, `capacity`, `effects`. A production-planning pack would supply the vocabulary; the kernel keeps the solver.
- **Logic machine (Issue #6).** Signal activation is the discrete fixpoint; this is the continuous one. Both run over the same topology, and both should be replayable with receipts.
- **Space (HORIZON-SPACE).** "A Space may admit only part of the grammar" extends naturally to quantities. A Space can admit resources and their limits, and a Plane scopes them.
- **LIMIT symbol.** Today it is a glyph. With a quantity behind it, it becomes the visible form of a resource row, and its shadow price is a natural thing to show on it.

Guardrails kept: nothing new is exposed in the editor (no inert configuration); SVG is not the source of any number; the `.sov` format is untouched; refusals carry a code and a next operation.

## 4. Residuals: what this does not do yet

| Gap | Kind | What closes it |
| --- | --- | --- |
| Whole units: the plan builds 1.25 chairs | integrality | branch-and-bound over the same simplex, or rounding with a feasibility repair |
| Economies of scale, setup cost, minimum batch | nonconvex | MILP (SOS2 segments, binary on/off); the solver refuses these today |
| Time as sequence, not just a budget: makespan, precedence, a stage that cannot start until another finishes | scheduling | a time-indexed or event-based model. The `(logicalTime, sequence)` scheduler in Issue #6 is the natural host |
| Rate and travel time as decision variables: choosing Wire rates under a latency target | hyperbolic (1/rate) | a geometric program: in log space the rate product and 1/rate both become linear |
| Stochastic arrivals, queueing delay ρ/(1 − ρ) | convex in load | fits the convex case now as a `congestion` with a different curve |
| Quantities stored in the document instead of a sidecar | format | a file-format decision, alongside the pending carrier/Component record merge. Not before |
| Editor, API or MCP surface for solving | parity | one data-core operation served to all three surfaces (the repo's parity rule), after the model settles |
| Solver scale | performance | dense tableau suits tens to a few hundred variables. Beyond that, a sparse or revised simplex, or an optional external solver |

### Also found: efficiency candidates in the runtime itself

These came out of the inventory. None is changed here.

- `computeSignalState` stops after 6 passes and `diffuse` after 5: chains deeper than that are silently truncated. A worklist (visit a node when an input changes) would be exact and usually faster.
- Diffusion is a linear system; its fixed point can be solved directly instead of iterated a fixed number of times.
- Routing is greedy per wire in index order. A second improvement pass, re-routing each wire against all the others, would lower total crossings without a global solver. `PERFORMANCE.md` already names incremental projection as the first scaling step.
- `choose_period` scans 2,100 grid points × every duration. Candidate periods only change at P = (k ± ½)·d, so an event-based scan would be exact and cheaper.

## Try it

```
python scripts/optimize_sov.py examples/optimization/workshop.sov             # the nonlinear plan
python scripts/optimize_sov.py examples/optimization/workshop.sov --compare   # linear vs nonlinear
python scripts/optimize_sov.py examples/optimization/workshop.sov --segments 128 --json
python tests/optimize_sov_qa.py                                              # the gate's check
```
