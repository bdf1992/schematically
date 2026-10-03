# Residuals: the one-runtime plan (contracts 01-10)

Plan: `control/sketchbooks/ep-root-20260926/plans/unify-runtime.md`, written 2026-09-26.
Contracts 01-09 landed on dev through `3348a81` (contract 09's merge, 2026-10-03). This
contract (10) deletes dev's own message engine from `src/07-graph-core.js` and updates
the docs that described it. Branch `feat/contract-10-of-the-one-runtime-plan-cont`.

## 1. What moved where

Line numbers on the left are `src/07-graph-core.js` at `7b939e3`, the plan's parity
reference (the file the plan's Inventory table cites, at `83d5b5a`, has the same
functions a few lines later; 7b939e3 is the pin this contract's acceptance checks use).

| 7b939e3 lines | Was | Is now |
|---|---|---|
| 18-257 | graph reading: `refusal`, `wireDirection`, `flowConfig`, `COMBINES`, `signalConfig`, `aclConfig`, `principalMatches`, `aclDecide`, `build`, `crossingAt`, `junctions`, `reach`, `paths`, `cycles`, `order`, `cut`, `boundary`, `untyped`, `exportGraph`, `QUERIES`, `query` | unchanged, still in `src/07-graph-core.js` (now lines 1-238) |
| 264-265 | `readPath`, `fnv` | deleted; `src/07-state-space.js` carries its own copies (lines 269, 271), used by its handler, merge-by-key and effect-key code. Nothing left in the graph core needed them |
| 270-283 | `callHandler` (dev's declarative handler dispatch: `stub`, `fixture`) | deleted; the pattern lives in `src/07-state-space.js`'s `handlerPattern` (one of the `FLOW_PATTERNS`, `src/07-state-space.js:405`), reached through `flow.handler` in `data/core.flow.pack.json:143` |
| 285-607 | `createSimulation`: the event queue, `schedule`/`send`/`forward`/`emitOutputs`/`runHandler`/`arrive`/`continueAt`/`release`, levels (`setLevel`/`COMBINE`/`recompute`/`levelArrive`), clocks (`waveAt`/`nextClockTime`/`clockTick`), the `sim` object | deleted; superseded by `src/07-state-space.js`'s run engine (ticks, delta rounds, the `truthTable`/`merge`/`combinePattern` patterns at `src/07-state-space.js:150,197,235`, the `FLOW_PATTERNS` at `:405`, and the clock mechanism `implyGraph`/`clockEdge`/`waveAt` at `:733-795`), served to callers as `createSimulation` by `src/07-state-surface.js:72` |
| 608-645 | `runScenario` | deleted; `src/07-state-surface.js:325` |
| 646 | `scenariosOf` | deleted; `src/07-state-surface.js:364` |
| 647-683 | `createSession` (the `actions` dispatch table for `graph.query` and every `sim.*` verb) | deleted; `src/07-state-surface.js:365` |
| 684-704 | `tools` (the 15 `schematic.sim.*` MCP tool schemas plus `schematic.graph.query`) | deleted; `src/07-state-surface.js:403` |
| 706 (`return {...}`) | exported `createSimulation, runScenario, createSession, tools` as the functions above | now four one-line delegations (`src/07-graph-core.js:246-249`, landed at contract 09, 73a0e08): `const createSimulation=(...a)=>surface().createSimulation(...a)` etc., `surface()` resolving to `SovSchematicSimSurface` (`require('./07-state-surface.js')` under node, `root.SovSchematicSimSurface` in the browser) |

Pack definitions the engine reads instead of code: `data/core.logic.pack.json` (`logic.not/and/or/xor`,
unchanged by this plan, asserted by `tests/state_space_contracts_qa.py`) and
`data/core.flow.pack.json` (`flow.fanout/distribute/select/join/buffer/limit/switch/gate/observe/
receipt/refuse/hold/handler/effect/park`, added by contracts 06-07). Levels and combine logic are
the engine's own closed pattern registry (`PATTERNS` and `FLOW_PATTERNS`, `src/07-state-space.js:
404-405`), not a pack, because the plan's Q8 and STATE-SPACE.md's "Ownership" rule (`Settled` item 10)
keep the engine's small closed set of patterns in the engine and let packs only instantiate them with
data. Clocks did not become a named pattern (`transition@1`) as the plan's Inventory table guessed:
`signalConfig`'s declared `clock` is read directly by `implyGraph`/`clockEdge`/`waveAt`
(`src/07-state-space.js:733-795`), which is a built-in of the run engine, like the merge and combine
patterns, not a device a pack defines. Nothing in dev or in `tests/state_space_contracts_qa.py` names
`transition@1` or `register@1`, so this is not a byte-level inconsistency, only a naming the plan did
not predict before the work.

## 2. The eight owner calls

The plan's Q1-Q8 are real questions a Bdo ruling left open; each contract (01 for Q1/Q2/Q7, 02 for
Q2, 04 for Q6, 08-09 for Q4/Q5) was written to the recommended answer below and nothing surfaced
a reason to answer otherwise:

1. **Q1 (Path delay default).** Recommended and taken: 10 ms for an undeclared wire, matching dev's
   buffer test (contract 01).
2. **Q2 (undeclared card at power-on).** Recommended and taken: start false, absorb; an explicit
   `signalMode: source` still starts high (contracts 01-02).
3. **Q3 (idle editor colouring as a settled-run projection).** Recommended and taken: out of this
   programme; `src/25-signal.js`'s `computeSignalState` stays its own computation of reachability
   and colour, not behaviour.
4. **Q4 (keep `createSimulation`/`runScenario`/`createSession`/`tools` as delegations).** Recommended
   and taken at contract 09 (73a0e08): one-line delegations to `src/07-state-surface.js`, so
   `graph_core_qa`, `notation_qa` and `section_exposure_qa` stayed byte-identical in their assertions
   through contract 09, and this contract (10) could delete the engine body without touching a
   caller's name.
5. **Q5 (mutation_watch retargeting).** Recommended and taken at contract 09: `derived-signal-can-be-
   set` now targets `src/07-state-surface.js` and `power-on-undoes-explicit-set` targets
   `src/07-state-space.js` (`tests/mutation_watch.py:136-141, 216-221`); `acl-deny-does-not-win` keeps
   its original target, `src/07-graph-core.js`'s `aclDecide`, which this contract did not move.
6. **Q6 (effect key).** Recommended and taken: dev's business key (`node:value`), not a run-scoped key;
   `src/07-state-space.js`'s `effectPattern` keys the same way, so a replayed effect is not sent twice.
7. **Q7 (delay 0 is a zero-delay cycle risk, not a refused value).** Recommended and taken at
   contract 01: `config.delay: 0` is admitted everywhere; the state-space fixtures that had used `0`
   as their refused-value example moved to `-1`.
8. **Q8 (continuous values as integers).** Recommended and taken: micro-units (0..1000000) with a
   software cosine (`cosTurnMicro`) for the sine wave, so a browser and node replay byte-identically.

One related call outside Q1-Q8, found while building contract 08: the judging seat proposed a ninth
rule (undeclared same-tick level merge takes the arrival scheduled last) and withdrew it the same day
because it reversed `STATE-SPACE.md` Settled item 15 for level channels; canon does not move inside a
contract. The stochastic recorded-draw merge (Settled item 15) stands unchanged, and
`tests/graph_core_qa.py:163-173`'s assertion (added at contract 09) checks the run's own recorded
draw rather than a fixed outcome, for both possible draws.

## 3. Behaviour that differs from dev, and the test that shows it

None found at this contract that is not already named and tested on dev. The one behavioural
difference the programme introduced — same-tick level merges are resolved by the seeded draw
recorded in the run's ledger, where dev's old engine always took the arrival scheduled last — was
introduced at contract 02 and is exercised by `tests/graph_core_qa.py`'s `planeDoc(acl,0)` case
(lines 163-173): it runs the case under six seeds, asserts the run always records a draw between
the two wires that reach the door (`k3`, `k4`), and asserts the refusal follows whichever one the
draw puts last. `python tests/sim_parity_qa.py` (this contract) reports `no exception`: all three
dev sim-facing suites (`graph_core_qa`, `notation_qa`, `section_exposure_qa`) pass unchanged on the
state-space engine.

Two acceptance checks in this contract's own list fail for reasons that predate it, named so the
next actor does not chase them:

- `git diff --exit-code 7b939e3 HEAD -- tests/graph_core_qa.py ...`: `tests/graph_core_qa.py` differs
  from `7b939e3` at the same lines 163-173 above. That edit landed in an earlier contract (08/09,
  already on dev before this branch started: confirmed with `git diff 7b939e3 3348a81 --
  tests/graph_core_qa.py`, which shows the identical diff). This contract touched no test file.
- `git diff --exit-code e0cca7b HEAD -- examples/*.sov ...`: `examples/09-print-ai-proof-run.sov`
  differs from `e0cca7b` (`score: 0.93` vs `score: 930`). This is schematically#89 (`75f8de4`),
  already on dev before this branch started (same confirmation as above): the lesson from contract
  08 names this and anchors byte-unchanged checks at `75f8de4`/`origin/dev` for later contracts.

## 4. Acceptance run (2026-10-03)

- `old_engine_gone.py`: pass — nothing of `createSimulation`/`runScenario`/`createSession`/
  `callHandler`/`waveAt`/`nextClockTime`/`COMBINE=`/`schedule(`/`levelArrive`/`clockTick`/
  `continueAt`/`emitOutputs` remains in `src/07-graph-core.js`; the surface serves the API.
- `python build.py && git diff --exit-code -- index.html`: clean once this contract's changes are
  committed (the build regenerates `index.html` from the shrunk source; checked after `git add`).
- `tests/graph_core_qa.py`, `notation_qa.py`, `sim_parity_qa.py`, `sim_control_qa.py`,
  `section_exposure_qa.py`, `access_panel_qa.py`, `agent_api_mcp_golden_qa.py`,
  `skills_conformance_qa.py`, `state_space_effects_qa.py`, `mutation_watch.py`: all pass.
- `tests/state_space_contracts_qa.py` (lesson from contract 09, not in the named acceptance list but
  run anyway since it proves every example still loads over the one engine): pass, all 16 examples.
- `node tests/mcp_surface_check.mjs` (same lesson): pass, no error; `mcp/server.mjs` still loads
  `07-state-space.js` then `07-state-surface.js` then `07-graph-core.js`.
