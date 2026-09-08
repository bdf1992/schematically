# Logic runner delivery — 2026-09-07

Concern: [issue #6](https://github.com/bdf1992/schematically/issues/6), a first local
execution-and-memory slice for eventual SOV integration. Based on `dev` at
`30b9edf20191139d0cbfd0e57e0cdb358faeebe6`. No SOV standing or phase was changed.

## Observed

The repository gate `python scripts/qa.py` passed 40 suites and 19 JavaScript syntax
checks, including the new runtime and binding suites. Test time was 70.07 seconds
on this host. The pinned Playwright 1.57.0 browser download was unavailable; the
run used Chromium 149 through the repository's existing `CHROMIUM_PATH` override.
No substitute browser dependency was added to the repository. CI should confirm
the normal pinned browser before release.

`tests/logic_runtime_qa.mjs` exercises AND vectors, retained latch memory, queued
continuation, replay mismatch, changed definitions, geometry-only edits, invalid
inputs, incomplete tables, multiple drivers, surface and flow refusals, a twenty-node
chain, and a bounded feedback oscillator.

`tests/logic_bindings_qa.py` compares exact sessions across browser, HTTP and MCP,
downloads and reopens a run through File lifecycle, rejects a tampered trace without
replacing the diagram, resumes pending events, restarts the server, checks replay,
and refuses corrupt disk state. The browser panel was visually inspected with the
memory example; current inputs, outputs and the retained bit are visible.

## Requirement and dependency map

| Requirement | Owned implementation | Evidence / remaining dependency |
| --- | --- | --- |
| Same topology and boundaries as editor | `06-attachment-core.js`, `05-data-core.js`, `07-logic-core.js` | Existing boundary suites plus runtime refusal cases |
| Data-defined Boolean/finite-state behavior | `07-logic-core.js` | Complete table validation and latch golden cases |
| Deterministic delays, bounded cycles | `07-logic-core.js` | Logical time/sequence, resumed oscillator |
| Durable memory and pending events | `75-persistence.js`, server sidecar | Save/open and server restart parity |
| Human and agent execution parity | `85-api.js`, `90-logic-panel.js`, `mcp/server.mjs` | Exact session comparisons |
| Reconstructable local history | `07-logic-core.js` | Command replay checks state, queue and trace |
| Rich work payloads and external execution | Not implemented | A typed payload/rule extension and explicit adapter boundary |
| SOV authority, observation, settlement | Not implemented | SOV-owned grants, Record operations, independent observation and acceptance |

This is a development result for review, not full issue #6 completion or SOV Phase 2
readiness. The first vocabulary is authored in files/API; there is no rule-table
editor yet. The example proves a condition and retained result; routing packs,
arbitrary payload memory and external work are subsequent concerns. Run receipts
are local simulation records, and replay consistency does not authenticate their author.
