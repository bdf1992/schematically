# Data formats — 0.1

The editor now distinguishes a normal schematic file, a portable package, local workspace state, and CRUD envelopes.

## `.sov` — `soveraeign.schematic/document@0.1`

The normal editable schematic file. It contains semantic document state only:

- identity and revision;
- Components and their Form / Body / Frame / Regions;
- Wires and owned Wire Parts;
- References;
- spatial containment / surface membership;
- document-owned layout metadata.

It intentionally excludes local camera/grid/editor preferences so the schematic stays portable and deterministic.

MIME: `application/vnd.soveraeign.schematic+json`.

Schema: `formats/schematic.document.schema.json`.

## `.sovpak` — `soveraeign.schematic/package@0.1`

Portable package file. The package is a transparent JSON package rather than a binary archive so humans, MCP clients, version control, and validators can inspect it directly.

A package contains:

- `manifest` — package identity, timestamps, entrypoint, generator;
- `document` — the canonical `.sov` document;
- `workspace.view` — optional camera/grid/color/flow state;
- `templates[]` — the Component template catalogue needed by the package;
- `assets[]` — embedded package assets such as custom SVG graphics;
- `meta` — extension metadata.

MIME: `application/vnd.soveraeign.schematic-package+json`.

Schema: `formats/schematic.package.schema.json`.

A later release may define a compressed/binary container without changing the semantic package members.

## `soveraeign.schematic/workspace@0.1`

Browser-local recovery envelope. This is not the normal user file format. It contains the semantic document plus local view state such as camera, grid, flow visibility, and palette configuration.

Recovery is best-effort and must never make File → Open or File → Save fail if browser storage is unavailable.

Schema: `formats/schematic.workspace.schema.json`.

## `soveraeign.schematic/operation@0.1`

Transport-neutral CRUD request used by the browser API and MCP/HTTP adapters.

```json
{
  "schema": "soveraeign.schematic/operation@0.1",
  "id": "op-123",
  "op": "update",
  "resource": "component",
  "resourceId": "c1",
  "patch": {"config": {"label": "Worker"}},
  "query": {}
}
```

Supported resources: `component`, `wire`, `reference`.

Supported operations: `list`, `read`, `create`, `update`, `delete`.

Each operation returns `soveraeign.schematic/receipt@0.1` with before/after revisions and either a result or an error.

Schemas:

- `formats/schematic.operation.schema.json`
- `formats/schematic.receipt.schema.json`

## Boundary invariant

File import and CRUD Wire creation/update use the same reachability contract as the interactive editor:

> both endpoint Ports must be exposed to at least one shared surface.

Loading a file cannot be used to make a child Component implicitly reach through its containing Component boundary.


## Editor utility fields

Components and Wires may carry an `editor` object with `pinned`, `locked`, `hidden`, `opacity`, and `rate`. Named checkpoints persist in `document.meta.checkpoints`; each checkpoint stores a non-recursive document snapshot. Global rate is `document.meta.timeScale`.


### Access axis
Port Connections may carry `access: none | read | write | read-write`. Wire config may carry `forwardOperation` / `reverseOperation: none | read | write`. Direction, access, and authority are independent.


## Attachment compatibility

Normalized Components expose `parts.points` with canonical 0D identities. Wire endpoints additionally store `aAttachment` / `bAttachment` records containing canonical `pointId` values. Legacy `config.ports`, `parts.ports`, and `aSide` / `bSide` remain compatibility projections for document@0.1.

## Declared ports

A 2D Component's ports are declared data. `config.attachmentPoints` holds declared ports:

```json
{"id": "feed", "compatId": "feed", "side": "left", "t": 0.25, "flow": "in", "channels": [{"id": "main"}], "label": "Feed"}
```

- `side`: `left | right | top | bottom`; `t`: `0..1` along that side; `flow`: `in | out | control | duplex | trigger`.
- `channels`: an array of `{id}` with unique ids; absent means `[{"id": "main"}]`. A Wire binds two ports only when
  they share a channel id; the refusal is the same over UI, API, HTTP and MCP.
- `compatId` (the key into `config.ports`) defaults to `id`.
- `flow` is the port's direction. `defaultFlow` is a legacy alias, read only when `flow` is absent; when both are
  present, `flow` wins. Absent `t` reads as `0.5` and absent `flow` (and `defaultFlow`) as `duplex`.

`config.attachmentDefaults` says how the list is read. `standard` (explicit, or implied on a typed Component) is the
template's declared ports (`left`/`in`, `right`/`out`, `top`/`control` for the typed Component template) followed by
`attachmentPoints` as additions; `none` makes `attachmentPoints` the complete list. A Plane's default is `none`.
The loader never writes template ports into the stored array, and never refuses a list: it rewrites each stored list
into exactly the authored ports it exposes (`t` coerced to a number and clamped to `0..1`, an invalid `flow` read as
`duplex`, absent or empty `channels` read as `main`, entries with no valid side dropped). An entry whose id or
compat id collides with an earlier one is dropped too, unless a bound Wire end refers to it (by its original id or
its declared compat id) and that reference names no surviving port: that entry is instead kept under a fresh id
(`<id>~2`, `<id>~3`, ...) and the Wire end is rebound to it by `pointId`, so loading never unbinds a Wire on a
collision. A `pointId` reference names a surviving port by its id; a reference stored only as `aSide`/`bSide` names
one by its id or its compat id. A Wire on a duplicated id (two entries `a`) stays on the surviving `a`, and the copy
is dropped; a Wire stored as `bSide: "in"` beside an authored duplicate `in` stays on the template's `left` (whose
compat id is `in`), and no `in~2` is made.
A retype keeps the new template's ports in order, an authored port with a template id replacing it, followed by the
remaining authored ports, stored in the smallest form. It is refused with `PORT_IN_USE` when it would leave a bound
Wire end resolving to a different port id than before (a compat-id match to a different port counts as moving it),
unless the retype changes the component's effective dimension, the one case a bound end may still move by compat id
(a typed Component's `out` to a Point's `self`). A component `create` or `update` that sets
`attachmentPoints` is checked and stored in the smallest form, keeping order: `standard` plus additions when the list
begins with the template's ports in template order and unchanged, otherwise `none` plus the full list as given. It is
refused for a repeated id or compat id, an invalid side, t or flow, or a repeated channel id. Every component edit
(a port list, `attachmentDefaults: none`, a retype) is refused with `PORT_IN_USE` when it would remove a port a Wire
ends on or move it to a different port id, and with `CHANNEL_MISMATCH` when it would leave a Wire between two ports
sharing no channel, so a saved document always passes validation. See `ATTACHMENT-POINT-MODEL.md`, *Declared ports*.

The editor's Ports panel (in a 2D Component's settings, below Attachments) sends every edit the same way: the
complete port list, with `attachmentDefaults: none`, through the component `update`, which stores it in the smallest
form. See `ATTACHMENT-POINT-MODEL.md`, *The Ports panel*.


## Compact records (dev, 2026-09-01)

`.sov`, `.sovpak`, recovery snapshots, API `document.get`, and embedded checkpoints
are written through `SovSchematicData.compactDocument()`. It strips what the loader
rebuilds:

- component `canvas`, `boundary`, `parts`, `type`, `incomplete`;
- port-level mirrors of the active connection (`flow`, `access`, `colorSlot`,
  `color`, `channel*`, `side`) and realized `connection.color` / `connection.name`;
- `config.color`, and the presentation layout hints `svgRef`, `internalLayout`,
  `portTopology`, `boundaryColorMode`, `boundaryShape`;
- `placement` when it is plain surface placement (implied by `x`/`y`);
- wire `canvas`, `duplex`, and an empty `attachments[]`;
- the document-level root `canvas`.

`aSide` / `bSide` stay in the file because the document schema requires them.
Files that still carry the full projections load identically; nothing is removed
from the reader.

Saved documents carry authored truth only, and a document is the same document
wherever it is held (contract #50). The editor fills runtime defaults into the
records it holds (editor state, palette slots, presentation, wire markers and
channel indexes, clamped sizes, settled points), but none of them reaches a file,
`document.get()`, a checkpoint's document or a run: the editor keeps the compact
form of the document it opened or was given (`compactDocument` of the same load
`node` and the server make) beside its own compact form right after opening, and a
snapshot is the opened form with only what changed since carried over, key by key
(records matched by id). So a document opened and not edited, or edited and undone
back, saves exactly `compactDocument` of the file loaded headless, hashes the same
(`documentHash`) on every surface, and opening does not change its revision. History
and checkpoint restores keep the opened form; opening a file, `document.replace`,
New and recovery replace it.

### Default records

A default point contract is one connection, outside face, no label. Only the points
the effective dimension exposes get a contract: a Point owns `out` (its `self`), a
Path `in`/`out`, a standard 2D surface `in`/`out`/`control`, and a Plane
(`attachmentDefaults: none`) owns nothing until a Point is hosted on it.

`config.attachmentDefaults: standard | none` is stored when `none`, and when `standard`
overrides a Plane's preset of `none`. The symbol
ids `point`, `path`, `plane` carry Form presets; `port` is read as `point`.


## Carrier endpoints (dev, 2026-09-01)

A wire's `aAttachment` / `bAttachment` may be `{kind:'free',x,y}`; then `a` / `aSide`
(or `b` / `bSide`) are `null`. The schema's required keys are still present. A wire
carries `form.dimension: 1` and `role: 'carrier'`. `wire.create` accepts any mix of
bound (`a`/`aSide` or an `aAttachment` ref) and free ends; `wire.update` rebinds an end
with `a`/`aSide` or frees it with `aAttachment: {kind:'free',x,y}`. Validation requires
bound ends to exist and two bound ends to share a surface; free ends are always valid.


## State space contracts (slice 1a, `STATE-SPACE.md`)

The contract layer of the state space. Its code is `src/07-state-space.js`; validation is hand-written there, and the
four schemas below document the shapes (no JSON Schema evaluator is used).

- `soveraeign.schematic/state-record@0.1` — one state claim: `subject {entity, run, point?, channel?, attempt?}`,
  `vantage` (`relative` requires `reference`), `observable`, `kind`, `form`, `value` (typed by `form`), `time
  {logical, sequence, mode}`, `certainty {kind: exact}`, `observer`, `provenance {rule, inputs, threshold?}` (`threshold` a finite number), `perturbation`.
  Any other key, at any level, is refused. Schema: `formats/schematic.state-record.schema.json`.
- Pattern declaration — `id`, `version`, `class`, `stateful`, `blastRadius`, `validate`, `derive`; the patterns ship
  with the engine (`truth_table@1`, `merge@1`). Schema, with each pattern's parameters and derived contract:
  `formats/schematic.pattern.schema.json`.
- `soveraeign.schematic/definition@0.1` — `id`, `version`, `pattern` (`id@version`), `parameters`, `delay` (default
  0), `ports` (placement and labels of the generated ports, presentation only), `projection`. A stated `inputs`,
  `outputs`, `state` or `observables` must equal what the pattern derives (`CONTRACT_MISMATCH` otherwise). Schema:
  `formats/schematic.definition.schema.json`.
- `soveraeign.schematic/pack@0.1` — `{format, id, version, definitions[]}`, the minimal envelope until the domain
  pack format absorbs it. The built-ins are `data/core.logic.pack.json` (`logic.not`, `logic.and`, `logic.or`,
  `logic.xor`). Schema: `formats/schematic.pack.schema.json`.

A `.sov` carries three pieces of authored state-space data, and nothing a run computes:

- **`config.definition`** on a Component: the definition it is bound to, `id@version` (`"logic.and@1"`), or `null`
  (unbound; not written on save). Only binding sets it to a non-null value: `applyBind(doc, componentId, ref, packs)`
  resolves the definition, builds the patch (`bindDefinition` returns the same patch for inspection and applies
  nothing), checks that its ports equal the contract, and applies it through the data core's binding path
  (`applyBinding`), returning a receipt that is ok or refused with `error.code`. Binding also sets
  `attachmentDefaults: none` and exactly the contract's generated ports as `attachmentPoints`: one per input on the
  left and one per output on the right, spread evenly unless the definition's `ports` places them. The existing Wire
  checks apply (`PORT_IN_USE`). A definition whose contract has no ports (one on `merge@1`), and any Component whose
  effective dimension is not 2 (a Point, a Path, a Component hosted on a Path), is refused
  (`DEFINITION_NOT_BINDABLE`). Rebinding carries each channel `merge` to the same port id and channel id, and is
  refused with `MERGE_IN_USE` when the new contract drops a port or channel holding one. A component `update` or
  `create` that sets a non-null `config.definition` is refused with `DEFINITION_BIND_REQUIRED` on every surface;
  paste and Duplicate copy a bound Component's record as-is. A value that is neither `null` nor an `id@version`
  string is refused everywhere with `DEFINITION_INVALID`. While bound, an update other than unbinding is refused
  with `DEFINITION_PORTS` when the ports the Component exposes (ids, flows, channel ids, as
  `canonicalAttachmentPointDescriptors` reads them) would differ, which includes a change of host (`placement`) or
  of dimension (`form.dimension`), or when it would set `attachmentDefaults` to anything but `none` or change
  `symbolId`; `applySymbol` (the bar retype) refuses a bound Component the same way. Moving (`side`, `t`),
  relabelling and channel `merge` edits are allowed. Deleting a Component makes the Components on its interior fall
  back to its canvas; a `delete` that would change a bound one's exposed ports that way (the canvas is a Wire's) is
  refused with `DEFINITION_PORTS`, and nothing is deleted. Setting `config.definition` to `null` unbinds and leaves the
  ports as stored.
- **`config.delay`** on a Wire: its propagation delay in logical ticks, an integer >= 1. Absent means 1 and is not
  written. A Wire `update` with `delay: null` removes it. A Wire `create` or `update` carrying any other value is
  refused with `PATH_DELAY_INVALID` on every surface; loading keeps a stored value as written.
- **`merge`** on a declared port's channel: the `merge@1` parameters for same-tick arrivals there.
- **A Point's `self`.** A Point (0D) has one port, `self`, and may declare it, to give it channels and merges, as a
  single `attachmentPoints` entry `{id: 'self', flow?, channels}` with no `side` or `t`. Loading reads the placeholder
  form the first runtime wrote (with `side`/`t`) the same way and cleans it to this form; `compactDocument` writes this
  form. A `flow` equal to the default `duplex` is left out of the clean form, so the placeholder and clean forms, each
  with or without an explicit `flow: "duplex"`, store and hash (`documentHash`) the same. A component `create` or
  `update` on a Point may set it: `attachmentPoints` is then exactly one entry, `{id: 'self', flow?, channels}` (any
  other key, another id or a second entry is refused with `PORTS_INVALID`), checked like a declared port's (a valid
  flow; channels a non-empty list of unique, non-empty ids; a valid `merge`), stored in the clean form, and refused
  with `CHANNEL_MISMATCH` when a bound Wire would share no channel. An empty list removes the declaration. `self`
  itself always stays, so `PORT_IN_USE` never arises. The Point still exposes exactly `self`; its declared channels
  and merges are what `checkDocument` and the runtime read.

```json
{"id": "self", "channels": [{"id": "main", "merge": {"combine": "or"}}]}
```

```json
{"id": "in", "side": "left", "t": 0.5, "flow": "in",
 "channels": [{"id": "main", "merge": {"combine": "last", "order": {"kind": "declared", "paths": ["w1", "w2"]}}}]}
```

`combine` is `or | and | min | max | sum` (order-free; `order` is refused) or `first | last | queue`
(order-dependent; `order` defaults to `{kind: stochastic}`). `order` is `{kind: declared, paths: [wire ids]}`,
`{kind: stochastic}` or `{kind: observed}`. A channel without `merge` is stored as `{id}` only. A component `create`
or `update` whose port list carries an invalid `merge` is refused with `MERGE_INVALID` on every surface; loading
keeps a stored `merge` as written. Paste and Duplicate map each `declared` order's `paths` through the copied Wires'
new ids; a Wire not copied leaves the list, and an order left empty is removed (the merge's default order applies).

`checkDocument(doc, packs)` reports the load checks without throwing or changing the document: `PATH_DELAY_INVALID`,
`PATH_DIRECTION_FLOW` (none of the Wire's declared directions is admitted by its ports' flows: `out` and `duplex`
emit; `in`, `duplex`, `control` and `trigger` receive; `duplex` declares forward and reverse, so a duplex Wire from
`out` to `in` carries forward only and passes; `none` is never refused), `CHANNEL_MISMATCH`,
`DEFINITION_UNRESOLVED`, `DEFINITION_INVALID` (the definition resolves but does not validate),
`DEFINITION_NOT_BINDABLE`, `DEFINITION_PORTS` and `MERGE_INVALID` (including a `declared` order naming a Wire that does not end on the port). A refused document
still opens.

## Runs and `.sovtrace` (slice 1b, `STATE-SPACE.md`)

A run is one replay key plus a budget, folded by `src/07-state-space.js`: `startRun({doc, packs, inputs, seed,
budget})` returns `{ok: true, run}` (a plain JSON-safe object) or a typed refusal; `step(run)` processes the earliest
tick with scheduled work in place and returns `{ok, tick, records}` (`tick: null` when nothing is scheduled; tick 0
is always processed first: power-on);
`traceOf(run)` returns the trace; `replay({trace, doc, packs})` re-runs it; `validateTrace(trace)` checks it. None of
them changes `doc` or `packs`, and nothing a run computes is written to the `.sov`. The runtime version is
`state-space@1`; slice 1b runs binary channels only.

- **Power-on.** Tick 0's evaluate phase evaluates every device from the state committed after tick 0's inputs,
  whether or not an input changed; outputs that differ from the starting `false` are recorded (with no input records
  in their provenance when they read only the unrecorded starting state) and emit. A NOT gives Q = NOT A, and a NOT
  feeding itself alternates until the budget.
- **Inputs** are `{entity, point, channel?, value, at}`: at tick `at` the port takes the boolean `value` and emits it;
  `channel` defaults to `main`, and a port may be named by its compat id (stored as its port id). `budget` defaults to
  10000 processed events (inputs, arrivals, output changes) and `seed` to `"0"`.
- **Refusals at start:** `RUN_REFUSED` (with `refusals`) when `checkDocument` does not pass; `MERGE_FORM` for a
  channel merge with `combine: sum`; `INPUT_INVALID` for an unknown entity, port or channel, a non-boolean `value`, an
  `at` that is not an integer >= 0, a port a definition owns as an output, two inputs at the same `(entity, point, channel, at)`, a non-string `seed` or a
  `budget` that is not an integer >= 0. `step` refuses with `BUDGET_SPENT` (`tick`, `left`: what is still queued)
  and applies nothing of that tick.
- **Merges on a Point** are declared on its `self` entry (above; `examples/state/merge.sov`). Without a merge,
  same-tick fan-in uses `{combine: last, order: {kind: stochastic}}`.

A trace, `soveraeign.schematic/trace@0.1` (schema `formats/schematic.trace.schema.json`, MIME
`application/vnd.soveraeign.schematic-trace+json`), is `{format, replayKey, documentRevision, budget, through, head,
ledger, records?}`, and its file encoding is `canonicalize(traceOf(run))`: RFC 8785, sorted keys, no whitespace, no final
newline.

- `replayKey` is `{documentId, documentHash, definitions (every resolved id@version, sorted), runtimeVersion,
  traceFormat, inputs (in (at, entity, point, channel) order), seed}`. `documentRevision` is a label only.
- `through` is the last tick processed (`null` before any) and `head` the hash of the last ledger entry. A trace may
  be taken after any number of steps.
- `ledger` holds what a replay cannot recompute, hash-chained: every entry is `{seq, kind, body, prev, hash}` with
  `seq` from 0, `prev` the previous entry's `hash` (64 zeros first) and `hash =
  sha256Hex(canonicalize({seq, kind, body, prev}))`. The kinds are `start` (body: `{replayKey, budget}`, so the budget is covered by the chain), `input` (one per
  input, in input order) and `draw` (one per stochastic merge order: `{tick, entity, point, channel, paths, order}`,
  `order = drawOrder(seed, ['merge', tick, entity, point, channel], paths)`).
- `records`, optional, are the derived state records (`state-record@0.1`), kept for audit: `vantage: space`, `observable:
  logic.level`, `form: binary`, `kind: registered` (observer `input`) or `derived` (observer `path:<wireId>`,
  `rule:<id@version>` or `engine:merge@1`), ids `sr-<run>-<seq6>`, `time.sequence` assigned per tick by sorting on
  `(entity, point, channel, observable, kind)`. An arrival that an input (or a device's delayed output) overrides is
  recorded with `provenance.rule: overridden`. The run id is the first 12 hex digits of the replay key's hash.

`validateTrace` checks the shape and recomputes the chain from the start: a change to any byte of an entry fails that
entry and every entry after it; the start entry must carry the trace's `replayKey` and `budget`, and `head` must equal
the last entry's hash (a truncated ledger fails there, with `entry` the index of the first missing entry). `replay`
refuses with `TRACE_INVALID` (naming the first bad `entry`),
`REPLAY_KEY_MISMATCH` (naming the differing `fields`; the inputs and seed are the trace's own) or `REPLAY_DIVERGED`
(a recorded draw that does not re-derive from the seed, a run that cannot reach `through`, or a ledger entry or,
when the trace carries them, a record that differs in canonical bytes), and otherwise processes exactly the ticks up
to `through` and returns the recomputed records. Golden runs live in `examples/state/`: `and.sov` with `and.00` to
`and.11.sovtrace`; `not.sov` with `not.0` and `not.1.sovtrace`; `not-loop.sov` with `not-loop.sovtrace` (budget
40, taken at `BUDGET_SPENT`); and `merge.sov`, `merge.or.sov`, `merge.stochastic.sov` with `merge.declared`,
`merge.or` and `merge.stochastic.sovtrace`.

## Settle, query and the run receipt (slice 1c, `STATE-SPACE.md`)

`settle(run)` steps until one of three results: `{kind: 'quiet'}` (nothing scheduled); `{kind: 'oscillating', period,
subjects}` (the state that determines the future repeated: after each processed tick the runtime hashes the committed
signal state, the queue buffers and the pending schedule with times relative to that tick, provenance left out;
`period` is the ticks between the repeat and its first occurrence, `subjects` the sorted `entity.port.channel` whose
committed value changed within that period); or `{kind: 'budget', left}` when a step is refused with `BUDGET_SPENT`.
Any other refusal is returned as is. `not-loop.sov` (budget 40) settles as `{kind: 'oscillating', period: 2, subjects:
['G.a.main', 'G.q.main']}`. A stochastic merge draw is keyed by the absolute tick, which the hash does not hold: on a
cycle through such a port, `oscillating` means the state repeated.

`query(run, {entity, point?, channel?, observable})` returns every record of the run whose subject matches (an omitted
`point` or `channel` matches any) and whose `observable` is the one asked, in record order, as copies; it refuses with
`QUERY_INVALID` and never writes to the run.

Every run operation on every surface returns one receipt, `soveraeign.schematic/run-receipt@0.1` (schema
`formats/schematic.run-receipt.schema.json`, built by `runReceipt(operation, run, result, tickBefore?, handle?)`):
`{schema, operation, runId, handle, ok, tickBefore, tickAfter, head, result, error}`. `operation` is the tool name
(`schematic.run.start`, `.step`, `.settle`, `.trace`, `schematic.state.query`, `schematic.run.replay`, and a registry's
`schematic.run.drop`); `runId` is the
run's content-derived id and `handle` its address on the surface (null for a replay, a refusal with no run, and a
receipt built outside a registry); `head` is the ledger head hash after the operation; `error` is `{code, message,
details?}` on a refusal (then `result` is null), `details` holding what the refusal names besides its code and message:
`refusals` for `RUN_REFUSED`, `{tick, left}` for `BUDGET_SPENT`, `fields` for `REPLAY_KEY_MISMATCH`, `{entry, errors}`
for `TRACE_INVALID`, `definitions` for "this page carries no packs"; `runId`, `handle`, the ticks and `head` are null
when there is no run. `result` is, per operation: start, the start entry's body `{replayKey, budget}`; step, `{tick,
records}`; settle, the result above; trace, the trace; query, the records; replay, `{records}`.

Runs live beside the document, never in it. `createRunRegistry({packs, document})` is the registry each surface keeps
in memory. Each successful start registers the run under a new handle, `<runId>.<n>`, `n` counting the registry's
starts from 1 (for example `dd38fae2158e.3`): two starts with the same replay key share the run id (record ids depend on
it) but are two runs, and neither touches the other. Step, settle, trace and query take the handle; an unknown handle
(a bare run id included) is refused with `RUN_NOT_FOUND`. A replay is not registered. Every run starts from
`document()`, the surface's current document, and `packs` is the raw pack JSON: a pack that does not load refuses every
start and replay with `PACK_INVALID`, and an empty list refuses a document that references a definition with
`PACK_INVALID`, "this page carries no packs". A start through a registry with a budget over `BUDGET_LIMIT`
(1,000,000) is refused with `INPUT_INVALID`; `startRun` itself is not capped. A registry holds at most 64 runs
(`RUN_LIMIT`): a start beyond that is refused with `RUN_LIMIT` and nothing is evicted. `drop(handle)` removes a run and
returns its receipt as it stood (`operation` `schematic.run.drop`, `result` null; `RUN_NOT_FOUND` for an unknown
handle), after which a start succeeds. No run operation captures history,
changes the document or its revision, or saves recovery. The browser reads its packs from `<script
type="application/json" id="sov-packs">`, into which `build.py` inlines every `data/*.pack.json`; the MCP/HTTP server
reads `data/*.pack.json` at start.

`settle` is linear in the ticks it processes: each tick costs a summary kept incrementally (the true signal keys'
count and code sum, each queue's length, relative next and positional code sum, the pending count and code sums with
relative times); the full hash is computed only when a summary repeats, for that tick and for each earlier tick with
the same summary (its state rebuilt from the kept pending list, the queue's item log and the later signal flips).
Equal states have equal summaries, so results are those of hashing every tick.
