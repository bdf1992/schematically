# Post-RC vision index

These documents preserve future direction without widening the current release candidate.

- `DATA-DRIVEN-SCHEMATIC-LANGUAGE.md` — root data-driven language, packs, skills, Space, and instruction-machine direction.
- `TOPOLOGY-CELL-GRAMMAR.md` — Point / Path / Surface cell/incidence grammar, Parts, boundary structure, parametric attachment, and `Wire → Path` direction.
- `LINEAR-NONLINEAR-SYSTEMS.md` — inventory of what the runtime computes by kind (linear, piecewise, nonlinear, combinatorial, fixpoint), and a first throughput optimization model over the same topology (`scripts/optimize_sov.py`).
- `OPTIMIZATION-VISUALIZATION.md` — plan for picturing optimization runs: a run record, and views for the plan on the diagram, curves, the landscape of local optima, the search, convergence and marginal value.
- `WHOLE-UNITS-AND-STATE.md` — units with material and work progress, a completion gate (AND over binary completions), and a draft `.sav` saved-state file that points at its `.sov` (`scripts/simulate_sov.py`).
- Issue #6 — small data-driven logic machine for particle routing.

Implementation begins from `dev` only after the accepted RC merges to `main`. See root `ROADMAP.md`, `RC-FINISH-LINE.md`, and `docs/BRANCHING.md`.
