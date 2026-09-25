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
| Component (stage) | an activity level x_c, with an optional capacity; `integer` holds it to whole units |
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

Concave value and convex cost together form the **convex case**. There the solver turns each bent term into linear segments; because the slopes are ordered, the simplex fills them in order without integer variables, and the error shrinks as segments are added. The nonconvex case (economies of scale, accelerating value) needs integer choice: the solver orders the segments with binaries and searches them by branch and bound (see *Cheaper at scale* below). Setup costs and minimum batch sizes are not modelled yet.

Every run returns:

- the plan: activity per stage, flow per wire;
- its value under the model *and* re-evaluated under the true curves (so approximation error is visible, not assumed);
- a **shadow price** per resource, supply and capacity: what one more unit of that limit is worth. This is the efficiency signal. It tells you which constraint to relax and which is free.

### The worked example

`examples/optimization/workshop.sov`: timber enters a Shop floor Plane through a boundary Point, is cut into blanks, and becomes chairs (4 blanks, 1.5 h) or tables (10 blanks, 4 h), which leave through two boundary Points to a market. Labor is 40 h a week, scoped to the Shop floor. The saw congests as it nears 90 blanks. Chairs sell into a small market that saturates.

```
$ python scripts/optimize_sov.py examples/optimization/workshop.sov --compare --relax   # fractions allowed

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

### Whole units: branch and bound

A stage marked `"integer": true` in the model is held to whole units. The chairs and tables in the workshop are. The solver runs **branch and bound** on top of the same simplex:

1. Solve the LP with fractions allowed (the *relaxation*). Its value is an upper bound on every whole-unit plan.
2. Pick the most fractional integer variable, say chairs = 1.25, and split into two sub-problems: chairs ≤ 1 and chairs ≥ 2.
3. Solve each sub-problem's LP. Keep the best whole plan found so far (the *incumbent*). Discard any sub-problem whose LP bound cannot beat it.
4. Stop when no open sub-problem's bound beats the incumbent. The plan is then **proven** optimal. If the node limit stops the search first, the answer is labelled `node_limit` and says how far short it may be.

```
nonlinear model  (whole units)
  plan value 702.05 USD (under the true curves)
    chairs 2   cut 58   tables 5
    labor 39.42 / 40.00
  whole units (chairs, tables): optimal after 4 nodes; relaxation 710.79, price of whole units 8.96 USD
    one more labor gains 0.00 USD (measured; the shadow prices are the relaxation's)
```

Two things change once units are whole:

- **The price of whole units** is the relaxation minus the integer optimum: $8.96 here. It measures what indivisibility costs, and it is a gap you can act on: smaller batches, or a divisible product.
- **Marginal value becomes lumpy.** The relaxation says an hour of labor is worth $14.18, and it is, *per fraction of a chair*. With whole units, one more hour buys nothing, because the next chair needs 2.3 hours. So the solver *measures* the marginal value by solving again with the limit raised, and reports it next to the shadow price, not in place of it. The gap between the two is information: labor pays only in steps.

The QA checks the result against a path branch and bound did not choose: it enumerates every (chairs, tables) pair in the workshop, solves the rest of the LP for each, and requires the same optimum. It also checks a knapsack, a general integer program, an infeasible one (2x = 1), and that a search stopped early reports a bound that is still an upper bound.

### Cheaper at scale: ordered segments (SOS2)

A learning curve makes the twentieth chair of a batch quicker than the first. Labor use becomes x^0.7: concave, cheaper at scale. Split into segments, the late segments are the cheap ones. An LP free to choose would fill them first and claim a curve that does not exist: chairs at their cheapest rate from the very first one.

The fix forces order. For each boundary between segment k and k + 1 there is a binary z_k, meaning "segment k is full":

```
s_k     ≥ w · z_k        z_k = 1 only if segment k is full
s_{k+1} ≤ w · z_k        segment k+1 may hold anything only if z_k = 1
```

This is the incremental form of SOS2 (special ordered sets of type 2): at most two adjacent breakpoints are active, so the plan stays on the curve. The binaries go to the same branch and bound as whole units. The ordering binaries are never relaxed, even with `--relax`, because without them the curve is not the one declared. The result is global to the breakpoint error, not a local optimum.

`examples/optimization/workshop.learning.opt.json` is a second sidecar for the **same** `workshop.sov`. Only the quantities change: a learning curve on chairs, and a wider chair market in place of the saturating one. It demonstrates the separation of topology and quantity.

```
$ python scripts/optimize_sov.py examples/optimization/workshop.sov \
      --model examples/optimization/workshop.learning.opt.json --segments 20 --compare

linear model (no learning curve)          chairs 12  tables 2   780.00 USD  labor 37.90 / 40
nonlinear model                           chairs 18  tables 0   810.00 USD  labor 34.96 / 40
  nonconvex bends: 19 ordering binaries, optimal after 8 nodes;
    without ordering the LP would claim 826.35 USD
  whole units: optimal after 16 nodes; relaxation 823.26
    one more labor gains 15.00 USD (measured)
```

What this shows:

- **The global answer commits to scale.** Eighteen chairs and no tables: once chairs get cheap, the workshop should specialise. The model that ignores learning splits production and leaves $30 a week on the table.
- **The landscape really has local optima.** The QA enumerates every whole plan under the true curves and finds six where no single step (one more or fewer of either product, or a swap) improves: (18, 0) at $810, then (15, 1), (12, 2), (9, 3), (5, 4) and (2, 5) down to $690. A hill-climber stops at whichever it reaches first. The linear model lands on (12, 2), one of them. Branch and bound over the ordering finds (18, 0) and proves it.
- **Without ordering the LP lies.** It claims $826.35, a value no plan can reach.
- **Marginal value is not local.** The chosen plan leaves 5 hours of labor unused, so the local shadow price of labor is small ($2.68). Yet one more hour is worth $15: at 41 hours a different plan (13 chairs, 2 tables, 40.65 h) becomes reachable and is worth $825. A shadow price cannot see a better plan in another valley. The measured marginal can. Both are reported, and the shadow price is labelled `local`.
- **Error direction.** For the convex bends, straight segments err on the safe side: chords over-state congestion and under-state saturating value. For the nonconvex ones they err optimistically: chords under-state cheaper-at-scale use and over-state accelerating value. The solver always re-evaluates the plan under the true curves, and that is where an optimistic error shows up. Choosing `--segments` so the breakpoints fall on whole units (20 segments over 20 chairs here) makes the pieces exact at every whole plan.

The QA checks all of this against paths the solver did not choose: the brute-force landscape, the count of local optima, the segment order in the solution, and a mutation check (with ordering switched off the test fails, picking (13, 2)). An accelerating-value case (table price rising as x^1.3) is also checked against enumeration.

### Projected gradient with multistart

`--method gradient` climbs the **true** curves: no segments, no binaries. That makes it the method that works for any smooth effect, separable or not, and an independent check on the exact solver, since it shares none of its machinery. It is also the method that can stop in the wrong valley, so every answer is labelled `local`.

How a climb works:

1. **Eliminate the recipes.** Recipes, yields and relays are linear equalities. Gauss–Jordan elimination writes every plan as x = x₀ + N·y over a few free activities y, the ones nearest the market (chairs and tables here). Each step stays on the recipes exactly.
2. **Project onto the linear limits.** Capacities, supplies and the bounds of the eliminated quantities (the cut can't go negative) are linear in y. After each step the point is projected back onto them exactly, using Dykstra's alternating projections.
3. **Penalize the curved limits.** Resource limits on the true curves (congested saw time, learning-curve labor) are held by an augmented Lagrangian. A multiplier per limit rises while the limit is violated, and the penalty stiffens only if violation stops falling.
4. **Step uphill** along a central-difference gradient (one-sided at a bound), halving the step until the rise is a fair share of what the gradient promised (Armijo).

Starts go to every corner of the search box first, then the centre, then random points. The corners matter: traps sit on edges, and random points almost never land exactly on one.

```
$ python scripts/optimize_sov.py examples/optimization/workshop.sov \
      --model examples/optimization/workshop.learning.opt.json --method both --segments 64

projected gradient + augmented Lagrangian, multistart  (24 starts, seed 0; free: chairs, tables)
  certificate: local (each answer is where a climb stopped; none is proven best)
  distinct optima: 2
       823.07 USD   chairs   13.64  tables    1.74   reached from 23/24 starts
       701.39 USD   chairs    0.00  tables    5.84   reached from 1/24 starts

exact (fractional units, 64 segments): plan worth 823.25 USD under the true curves
  best local answer is 0.18 USD short (0.02%)
  worst local answer is 121.86 USD short; 1/24 starts ended below the best
```

What this shows:

- **The trap is the all-tables edge.** With no chairs in production, the first chair's labor rate is effectively infinite: x^0.7 has an infinite slope at zero. So from a tables-only plan on the labor limit, every small move toward chairs loses value. It is a true local optimum, $122 below the best. The QA checks that by probing its neighbourhood directly, not by trusting the climber.
- **Its basin is thin.** Only climbs that start within about 0.4 chairs of zero, on the labor limit, fall in. One start in 24 did: the (0 chairs, 8 tables) corner. **With random starts alone, all 24 climbs agree and the trap is never seen.** The QA's mutation check confirms this: remove the corner starts and the test fails. "Every start agreed" is evidence about the starts, not the landscape.
- **The good basin is close to exact.** The best climb is 0.02% short of the proven optimum, from stopping tolerances.
- **On the convex workshop** every start reaches the same optimum, as convexity guarantees. The climb even comes out $0.35 ahead of the 32-segment exact plan, because it climbs the curve the segments approximate. That is the segment error, measured.
- **Whole units versus fractions give different landscapes.** The six local optima found last round lived in the whole-unit grid, where a step is one chair. With fractions allowed, the same economics leave only one trap. Local optima belong to a problem *and* the moves allowed in it.

## 3. How this fits the direction

- **Data-driven language (Issue #4).** Quantities belong in data, not code. The sidecar is a draft of what a domain pack's quantitative layer could look like: `uses`, `per`, `yield`, `capacity`, `effects`. A production-planning pack would supply the vocabulary; the kernel keeps the solver.
- **Logic machine (Issue #6).** Signal activation is the discrete fixpoint; this is the continuous one. Both run over the same topology, and both should be replayable with receipts.
- **Space (HORIZON-SPACE).** "A Space may admit only part of the grammar" extends naturally to quantities. A Space can admit resources and their limits, and a Plane scopes them.
- **LIMIT symbol.** Today it is a glyph. With a quantity behind it, it becomes the visible form of a resource row, and its shadow price is a natural thing to show on it.

Guardrails kept: nothing new is exposed in the editor (no inert configuration); SVG is not the source of any number; the `.sov` format is untouched; refusals carry a code and a next operation.

## 4. Which algorithms fit which shape

Every term in the model already declares its shape: `curve()` classifies each effect as linear, concave or convex. So the model can pick a method from the shape of the problem instead of the user choosing it. The more important choice is **what kind of answer each method can certify**. There are three kinds, and a result should always say which it is:

- **global**: proven best, by LP duality or by a branch-and-bound bound meeting the incumbent;
- **local**: no small move improves it (the KKT conditions hold), but a better plan may exist elsewhere;
- **heuristic**: a good plan, no proof of anything.

| Problem shape | Where it shows up here | Method | Answer | Status |
| --- | --- | --- | --- | --- |
| Linear | recipes, yields, supplies, linear resources | **Simplex** (two-phase, Bland) | global, with shadow prices | **built** |
| Convex separable: concave value, convex cost | saturation, congestion | **Piecewise-linear LP**: segments filled in order | global to a stated breakpoint error | **built** |
| Linear or convex + whole units | integer stages | **Branch and bound** over the LP | global, or a stated gap at the node limit | **built** |
| Convex smooth, not separable, or needing exact curves | interacting stages; a queue delay ρ/(1 − ρ) | **Projected gradient** (built, below); interior point or Frank–Wolfe at scale | global (convexity makes every local optimum global) | **built** (projected gradient) |
| Nonconvex separable: economies of scale, accelerating value | `economies`: a learning curve, a volume price | **SOS2 piecewise + branch and bound**: binary variables force the segments to fill in order | **global** to breakpoint error | **built** |
| Fixed costs, setup, minimum batch | "if a stage runs at all, it costs S" | **MILP**: an on/off binary per stage, x ≤ cap·z | global | next, same machinery |
| General nonconvex smooth | products of decisions, e.g. rate × rate on a Wire chain | **Projected gradient + augmented Lagrangian** (built); SQP for faster convergence | **local** | **built** |
| … the same, needing confidence | | **Multistart** from box corners and random points (built); basin hopping, simulated annealing | heuristic: better odds, no proof | **built** (multistart) |
| … the same, needing proof | | **Spatial branch and bound** with McCormick envelopes | global, slow | only if earned |
| Rates and latency: products and 1/rate | rate composition, travel time | **Geometric programming**: in log space both become linear or convex | global | fits cleanly: rates are already multiplicative |
| Sequence in time: precedence, makespan | "B cannot start until A finishes" | **Time-indexed MILP** or **constraint programming** | global or bounded | with the Issue #6 scheduler |
| Pure network structure | a flow graph with no recipes | **Network simplex / min-cost flow** | global, much faster | only if scale demands it |
| Discrete geometry | wire routing | **Dynamic programming, A\***, local search | global per wire today; a local search pass could lower total crossings | runtime, separate concern |

### Gradient descent and local optima

Gradient descent follows the slope downhill (or uphill, for a maximum). On a convex problem that is enough: there is one valley, so where it stops is the best. On a nonconvex problem it stops in *a* valley, the first one it rolls into. With economies of scale that is the typical failure. Starting from a small plan, each extra unit looks expensive, so descent stays small, while the real optimum is to commit to a large batch where units become cheap. It is a local optimum and it can be far from the global one.

Three responses, in order of preference here:

1. **Avoid needing it.** Most effects a schematic declares are *separable*: each bends one stage's term. Separable nonconvex curves are exactly solvable, to breakpoint error, by SOS2 piecewise + branch and bound. That is now built, and the learning-curve example shows it finding the global plan in a landscape with six local optima.
2. **When the problem is truly nonconvex and not separable**, run a local method (projected gradient is now built; see below) and label the result `local`. Run it from several starting points (multistart) and report how many distinct optima were found and how far apart they are. That spread is the honest measure of how rough the landscape is.
3. **Use the exact methods as a witness.** On problems small enough for both, compare the local answer with the global one. The difference is the measured cost of the local method on that shape, which is the evidence for when it is safe to use.

The same typing applies to efficiency measurements. A shadow price is exact for an LP. It is a local slope for a smooth nonconvex problem, and it is not defined at all for whole units, where the solver measures the step instead. The report should say which of the three it is.

## 5. Residuals: what this does not do yet

| Gap | Kind | What closes it |
| --- | --- | --- |
| Setup cost, minimum batch | nonconvex, discontinuous | an on/off binary per stage (x ≤ cap·z, cost S·z, x ≥ min·z) over the existing branch and bound |
| Optimistic error on nonconvex bends | approximation | segments whose breakpoints fall on whole units (exact there), or refine until the true-curve check passes; an automatic refinement loop could do this |
| Branch and bound at scale | performance | every node re-solves the dense LP from scratch; 32 segments per nonconvex bend with measured marginals takes about 7 s on the example. Warm-starting from the parent's basis (dual simplex), cutting planes and a rounding heuristic are the usual next steps |
| Faster local convergence | local methods | the climber uses finite differences and a first-order step (about 150 steps a climb). Analytic gradients from `curve()` and a quasi-Newton or SQP step would cut that sharply |
| Whole units in local search | integrality | the climber is fractional; rounding its answer, or a local search over whole-unit moves (the six-optimum grid), would give a local whole-unit method to set against branch and bound |
| Choosing starts well | heuristic | corners, centre and random points today; Latin hypercube sampling, or starts at the vertices of the linear relaxation, cover more for the same count |
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

## Seeing the runs

`OPTIMIZATION-VISUALIZATION.md` plans how these runs become pictures: the plan drawn on the diagram, each bent curve against its segments, the landscape with its traps and climbs, the branch-and-bound tree, convergence, and marginal value as a step function.

## Try it

```
python scripts/optimize_sov.py examples/optimization/workshop.sov             # the nonlinear plan
python scripts/optimize_sov.py examples/optimization/workshop.sov --compare   # linear vs nonlinear
python scripts/optimize_sov.py examples/optimization/workshop.sov --relax      # allow fractional units
python scripts/optimize_sov.py examples/optimization/workshop.sov --model examples/optimization/workshop.learning.opt.json --segments 20 --compare
python scripts/optimize_sov.py examples/optimization/workshop.sov --segments 128 --json
python scripts/optimize_sov.py examples/optimization/workshop.sov --model examples/optimization/workshop.learning.opt.json --method both   # local vs global
python tests/optimize_sov_qa.py                                              # the gate's check
```
