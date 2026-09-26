# Post-RC vision index

These documents preserve the broader language horizon. The RC has merged and
feature development proceeds from `dev`. The dated product milestones and first
user proof live in [the root roadmap](../../ROADMAP.md).

- `DATA-DRIVEN-SCHEMATIC-LANGUAGE.md` — root data-driven language, packs, skills, Space, and instruction-machine direction.
- `TOPOLOGY-CELL-GRAMMAR.md` — Point / Path / Surface cell/incidence grammar, Parts, boundary structure, parametric attachment, and `Wire → Path` direction.
- `LINEAR-NONLINEAR-SYSTEMS.md` — inventory of what the runtime computes by kind (linear, piecewise, nonlinear, combinatorial, fixpoint), and a first throughput optimization model over the same topology (`scripts/optimize_sov.py`).
- `OPTIMIZATION-VISUALIZATION.md` — plan for picturing optimization runs: a run record, and views for the plan on the diagram, curves, the landscape of local optima, the search, convergence and marginal value.
- `WHOLE-UNITS-AND-STATE.md` — units with material and work progress, a completion gate (AND over binary completions), and a draft `.sav` saved-state file that points at its `.sov` (`scripts/simulate_sov.py`).
- `LOGIC-GATES.md` — combinational and sequential gates as data (tables, thresholds, comparators, latches, flip-flops, C-element, Schmitt trigger), bits and levels, composites that add and count, and a catalog of further gates.
- `VISUAL-LANGUAGE.md` — discovery of what the renderer already offers, one visual grammar for solvers, units and gates, and the views for each (glyphs, live state, timing, levels, timeline, landscape, search outline, convergence).
- Issue #6 — small data-driven logic machine for particle routing.

Feature PRs return to `dev`; a later stabilization cut follows the release gate.
See `RC-FINISH-LINE.md` and `docs/BRANCHING.md`.

[Runner PR #33](https://github.com/bdf1992/schematically/pull/33) is the draft logic
and memory implementation. Its tested proposal does not make the full language,
Space, instruction machine, or SOV integration complete.
