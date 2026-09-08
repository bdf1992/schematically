# Logic execution and retained memory — experimental 0.1

Implements a bounded first slice of [issue #6](https://github.com/bdf1992/schematically/issues/6).
The diagram owns definitions and topology. A run owns current Boolean values, finite
memory, pending events and a deterministic trace. Editor undo is not runtime memory.

## Definition

`document.meta.logic` has schema `soveraeign.schematic/logic@0.1` and a `definitions`
map. Components opt in with `config.logic.definition` and may set `config.logic.delay`
(nonnegative integer ticks). Each definition declares `inputs`, `outputs`, `state`,
`initial`, and a complete `table`. A table row is `[...inputs, ...priorState,
...outputs, ...nextState]`. Bits are exactly 0 or 1. No expression evaluation,
scripts, provider invocation or external effects are admitted. A `kind: source`
definition has no inputs/state and one output; its `initial` is one bit. Other
definitions have `kind: table`. At most eight input-plus-state bits are admitted.

Inputs and outputs name existing attachment IDs or compatibility port IDs; aliases
are normalized by the shared attachment core. Every connected runtime endpoint uses
one connection, index zero. Carriers obey shared surface reachability, endpoint flow
and explicit direction. Unsupported channels, external read/write operations,
free runtime ends and multiple drivers of one input refuse compilation. Non-runtime
diagram components remain useful context, but cannot silently terminate runtime paths.
An input with no driver has value zero. Carrier delay is `config.logic.delay`, default
one tick. A component's delay applies before changed outputs reach outgoing carriers.

## Execution

Initialization gives every input zero, loads declared initial memory, and evaluates
every component in sorted ID order. Initialization reads initial memory without
transitioning it. All initial outputs propagate, including zero. Each later event
updates one input, evaluates its table against current inputs and previous memory,
and atomically records next memory and outputs. Changed outputs schedule arrivals.
Equal-time events use a monotonically increasing sequence. This is transport-delay
semantics: pulses are retained; no inertial cancellation or synchronous batch is implied.

`start`, `input`, `step`, `run`, `get`, `restore` and `replay` are shared browser,
HTTP and MCP commands. `input` schedules a source value at or after current logical
time. `step` consumes one event; `run` consumes at most its budget (1–1000 events).
A nonempty queue at the budget returns `PAUSED_BUDGET`, with its continuation intact.
The lifetime ceiling is 20,000 processed events or commands, 5,000 queued events,
256 runtime components and 4,096 diagram carriers. Capacity exhaustion refuses the
whole command without changing the prior run. No wall-clock animation drives logic.

## Persistence and replay

`.sov` remains authored truth. `.sovrun` uses `soveraeign.schematic/run-file@0.1` and
contains the diagram and a `soveraeign.schematic/run@0.1` session. The exact canonical
compiled program is the compatibility pin (not an authentication claim). Layout edits
may continue a run; changing executable definitions, routing or delays requires a new
run. Successful commands retain their canonical input in order. Restore re-executes
those inputs and requires exact agreement with the saved state, queue and trace.
This detects inconsistent snapshots; it does not authenticate the author of a history.
Browser Save Run / Open Run preserve this envelope. The server persists run state in
`<document file>.run.json`; missing state means no run, corrupt state is reported and
is not silently replaced. A deliberate `start` creates a new run.

## Phase 2 boundary

This is a deterministic local provider candidate, not SOV commissioning or Phase 2
acceptance. Trace entries describe local simulation. They are not SOV grants,
independent observations, accepted Findings or settled receipts. A future SOV adapter
must bind an exact definition and run to its own operation, grant and Record service.
Arbitrary payload memory, model calls, scheduler services and institution definitions
remain outside this Boolean/finite-state slice.

## Acceptance cases

- AND uses retained values of both inputs; all input vectors give the declared result.
- An enabled latch retains a bit when its input changes while disabled.
- A chain longer than six links reaches its sink; cycles yield with queued work.
- Save between events, reload and continue produces the uninterrupted final trace.
- Altered memory, traces, topology and illegal crossings refuse without mutation.
- Browser, HTTP and MCP use the same runtime, including after server restart.

Dependency path: attachment core → data-core legality → logic compiler → event runner
→ browser/server bindings → persistence and replay → later SOV provider adapter.
