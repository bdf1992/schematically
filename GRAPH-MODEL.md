# Graph Model · proposed (2026-09-25)

Status: **phase 1 implemented (2026-09-25)** in `src/07-graph-core.js`: junction
policies (§1), queries (§5) and the simulation with scenarios (§6, simulation only).
Proposed: subgraph instances and groups (§2), payload schemas (§4) and the live relay
(§6, live). "As built" below records where the implementation settled a detail.

This doc covers the graph primitives
that sit above Form: junctions, hyperedges, subgraphs, direction, typing, queries, and a
message runtime that runs first as a simulation and later live. `SECTION-MODEL.md`
covers what the inside of a node or edge looks like. `LAYOUT-MODEL.md` covers where
things are drawn.

## What exists today (the ground this builds on)

- **Direction:** each Wire is `none` / `forward` / `reverse` / `duplex`. A Wire can also
  require a matching return path (`reciprocity`), and its read/write operations are set
  per direction. Ports carry direction and access as independent settings.
- **Multiplicity:** a port has `connections[]`. Each connection has its own colour slot,
  channel marker and access, so parallel edges already exist.
- **Signals** (`src/25-signal.js`) are **derived state, not messages**:
  - components with `signalMode = source` are active
  - a component with `relay` ("On input") becomes active when a live wire reaches it,
    repeated for at most 6 passes
  - colour then diffuses as a weighted mix over live wires
  
  There is no time, no payload and no event.
- **Nesting:** Components inside open Components, with inward, outward and both-way
  points as the interface (`CANVAS-MODEL.md`).
- **`JOIN` and `CROSS` symbols** are meaning only ("paths are connected" / "paths cross
  without connecting"). They have no behaviour.
- **Integration** today means editing the document: Browser API, HTTP and MCP perform
  CRUD, undo and checkpoints, and return receipts. Nothing runs.

## Words

| Word | Meaning |
| --- | --- |
| **Carrier** | A 1D Form with two ends (a Wire, or a Path Component). Unchanged. |
| **Junction** | A 0D Point where three or more carrier ends are bound. It has a flow **policy**. |
| **Hyperedge** | A junction together with the carriers bound to it. It is a reading of the graph, not a separate record. |
| **Signal** | A level: continuous, derived, shown as activity and colour. What exists now. |
| **Message** | An event: discrete, time-stamped, carries a payload, travels carrier by carrier. New. |
| **Channel** | The routing key of a message. Shown as its **colour**. |
| **Handler** | Code outside the document that transforms messages for a Component. The document names it and never contains it. |
| **Relay** | The runtime service that moves messages, calls handlers, and exposes the document boundary to the outside. |
| **Merge** / **Join** | Merge: any input passes through. Join: waits for all inputs, then emits once. These are two different policies. |

`JOIN` the symbol currently means "connected", which collides with the join policy (one
concept, one word). The proposal: the `JOIN` symbol migrates to a **junction** Point, and
the word *join* is kept for the wait-for-all policy.

## 1. Junctions and hyperedges

A plain Point with two carrier ends passes messages straight through. A Point with three
or more ends is a junction, and its `config.flow` says what happens there:

```text
config.flow
├─ policy: fanout | distribute | merge | join | select
├─ by:     round-robin | channel | key      (distribute only)
├─ key:    <payload path>                   (distribute by key)
├─ window: { count?, timeoutMs? }           (join only: all inputs, or zip by count)
└─ handler: <name>                          (select only: an external handler picks the outputs)
```

| Policy | Input → output | Typical use |
| --- | --- | --- |
| **fanout** | one message in, a copy to every outgoing end | broadcast, pub/sub |
| **distribute** | one message in, exactly one outgoing end chosen | load balancing; routing by colour |
| **merge** | any incoming end → every outgoing end, in arrival order | collecting streams |
| **join** | waits until every incoming end has delivered, then emits one combined message | synchronisation, barriers, zip |
| **select** | a handler chooses the outgoing ends per message | content-based routing |

Which ends count as incoming and which as outgoing is **derived** from each carrier's
direction at that end. A duplex carrier counts as both, and the junction never echoes a
message back down the end it arrived on.

A junction is how this model stores a hyperedge: the edge becomes a small node that
every end connects to. That means hyperedges need no new record kind, and every existing
rule (reachability, hosting, selection) applies to them unchanged.

**Colour distribution is routing.** A carrier may declare `accepts: [channel…]`. A
distribute junction with `by: channel` sends each message down the ends that accept its
channel. The colour a person sees on a carrier is the routing a message gets there. The
colour diffusion that exists today stays as the *signal* view of the same graph.

Junctions of multi-line carriers (strips, pipes) are the open item in `SECTION-MODEL.md`.
A junction joins each space band of every strip that meets it, using the same policy.

## 2. Subgraphs, instances and groups

- **Compound node:** already exists as an open Component. Its boundary points are its
  interface, and there is no reach-through.
- **Collapse / expand:** the subgraph is shown as its boundary only. This is a
  **layout** choice (see `LAYOUT-MODEL.md`), not a change to the graph. Two layouts of
  the same document can collapse different subgraphs.
- **Definition and instance:**
  - a Component may carry `definitionId`, which refers to a subgraph definition held in
    `document.references`
  - instances share the definition's structure and boundary points, and override only
    declared parameters
  - editing the definition changes every instance
  - detaching turns an instance into an ordinary copy, and is a recorded operation
- **Group:** membership that does not own anything:
  `document.groups: [{id, name, members[]}]`. It is a separate relation from
  containment. An entity may belong to many groups, but sits inside only one surface.
  Layouts filter and style by group (for example an "ops", "security" or "data" view).

## 3. Direction and cycles

- Direction stays per carrier, as today. A graph-level question such as "is this a DAG?"
  is a query (section 5), not a stored flag.
- **Cycles:** for signals, the 6-pass fixed point stays. For messages, a cycle is
  allowed only if it takes time: at least one carrier on it has latency above zero, or
  it passes through a `BUFFER` / `HOLD`. A zero-latency cycle is refused when the
  simulation starts, and the refusal names the cycle's members. A zero-latency cycle
  would otherwise deliver in an endless loop within a single instant.

## 4. Typing

- A connection may declare `schema`: a JSON Schema, inline or as a `$ref` into
  `document.references`. It describes the payload that crosses that point.
- Connecting two points whose schemas are both declared and incompatible is refused,
  in the same place `compatId` is checked today, and identically on every surface.
- An undeclared schema is not a default. The point is untyped and the query
  `graph.untyped()` lists it. (Absence is reported, never filled in.)

## 5. Queries (read-only verbs)

Every query is one verb, served identically on the Browser API, HTTP and MCP:

| Verb | Returns |
| --- | --- |
| `graph.reach(from, {direction, channel?})` | the set of points and components reachable from `from` |
| `graph.paths(a, b, {limit})` | simple paths from a to b, following direction |
| `graph.cycles()` | every cycle, each marked as timed or zero-latency |
| `graph.order()` | a topological order, or a refusal naming a cycle |
| `graph.cut(a, b)` | a minimal set of carriers whose removal separates a from b |
| `graph.boundary(componentId)` | the interface of a subgraph: its points, faces and schemas |
| `graph.untyped()` | points with no declared schema |
| `graph.export(format)` | the graph as JSON Graph Format, GraphML or DOT, for other tools and agents |

Junctions export as hyperedges in formats that support them, and as a node with edges
in formats that don't.

## 6. Messages: simulation first, then live

### The engine

One discrete-event engine serves both modes.

- **Message:** `{id, channel, payload, schema?, origin, at, trace[]}`.
  - `origin` is the point it entered at.
  - `trace` lists every point, junction and handler it passed through, with the time of
    each.
- **Carrier:**
  - `latency` is derived from route length × the existing per-wire and global rate, or
    declared as `latencyMs`
  - optional `capacity` (messages in flight); when it is full, the message is held at
    the sending end
  - passing a carrier obeys the same checks as `wireDirectionActive` today: direction,
    emit and receive permission, and read/write access
- **Component behaviour** on receiving a message, by `signalMode`:
  - `passive`: absorbs it
  - `relay`: forwards it to its outgoing points
  - `source`: emits on a schedule or on inject
  - a Component with `behavior.handler` hands the message to that external handler,
    which returns zero or more messages, each tagged with the point it leaves from
- **Built-in symbols get runtime meaning:**
  - `BUFFER` queues and releases
  - `GATE` passes or refuses by calling a handler; a refusal is recorded
  - `SWITCH` follows its control point
  - `LIMIT` enforces a rate
  - `REFUSE` terminates and records
  - `RECEIPT` records every crossing
- **Signals from messages:** while the engine runs, "active" can be read as "carried a
  message within the last window". Signal mode keeps its derived meaning when nothing is
  running.
- **The event log** is runtime state, not document state. A **scenario** can be saved
  in `document.references` for re-use as a test fixture: an ordered list of injects with
  their times, and optionally the expected taps.

### Simulation (phase 1)

- Runs in the editor and headless (the same engine the server imports, as the data
  core is shared today).
- Uses a virtual clock with `step`, `run(until)`, `pause` and `reset`. It is
  deterministic for a given scenario and seed.
- Handlers in simulation are one of:
  - `stub` (pass-through)
  - `fixture` (canned responses keyed by input)
  - `live` (calls the real handler; opt-in per handler)
- Messages are drawn as the existing packets, coloured by channel. The trace of any
  message can be selected and highlighted along its path.
- Verbs:
  - `sim.inject(point, message)`
  - `sim.step(n)`
  - `sim.run({until})`
  - `sim.trace(messageId)`
  - `sim.taps(point)`
  - `sim.scenario.save / load / run`
  
  A scenario run returns a receipt that compares the taps with the expected taps. That
  receipt is test evidence.

### Live (phase 2)

- The same engine on a real clock. The relay is a process started by `mcp/server.mjs`,
  or next to it.
- **The document is the outermost Plane.** Its boundary points (`document.canvas`
  points with `face = external`) are the only integration surface. An outside system
  reaches exactly what the diagram exposes, and no-reach-through holds for the world as
  it does for nested Components.
- A boundary point may be bound to a **transport** in the relay's own configuration,
  never in the document:
  - HTTP inject (`POST /api/v1/points/<id>/messages`)
  - tap as server-sent events (`GET /api/v1/points/<id>/stream`)
  - an outgoing webhook
  - MCP tools `relay.emit` and `relay.subscribe`
- **Handlers are registered with the relay by name**, as a module path, a process, or an
  HTTP endpoint. The document holds only the name. A name with no registered handler
  refuses its messages when live, and records that. It is never silently passed through.
- Every crossing of the document boundary writes a receipt: time, point, channel and
  payload digest. Live receipts are runtime state, like the event log.

## 7. Order of work

1. Junction Point and `config.flow`. Migrate the `JOIN` symbol. Add `accepts` on
   carriers. Refusals for a policy an end count can't support (for example a join
   with a single input).
2. Queries, and `graph.export`.
3. Groups, and definitions/instances.
4. The simulation engine, its verbs, scenarios, and packet and trace rendering.
5. Payload schemas on connections.
6. The live relay: boundary transports, the handler registry, receipts.

Each step keeps the rule already in `AGENTS.md`: Browser API, HTTP and MCP go through
the shared data core, and a refusal is identical on every surface.

## As built (phase 1)

Settled details:

**Surfaces**
- One module, `src/07-graph-core.js` (`SovSchematicGraph`), is loaded by the browser
  and by `mcp/server.mjs`. Each surface dispatches through one `createSession()`, so
  the Browser API (`graph.*`, `sim.*`), MCP (`schematic.graph.query`,
  `schematic.sim.*`) and HTTP (`/api/v1/graph/<verb>`, `/api/v1/sim/<action>`) return
  the same values and the same refusals.
- The simulation reads a snapshot of the document and never mutates it.
  `sim.inspect('state')` reports `stale: true` once the document's revision moves on.

**Direction and ports**
- Passability is the signal's rule (`wireDirectionActive`): wire direction, whether
  the sending port can emit and the receiving port can receive, and read/write access.
- A port with no authored connections takes the data core's default for its id, which
  is also what the editor normalizes to. Wires that fail are listed by the query
  `blocked`, with the reason.

**Messages and nodes**
- `inject(node)` makes the node emit the message: it leaves by that node's outgoing
  wires.
- A node with no declared `config.flow.policy` fans out. The query `junctions` reports
  `declared: false` for such a node, so the default is visible, not hidden.
- A message whose channel no outgoing end accepts is **refused**, never dropped.
  "Delivered" means only that the node is a sink.
- Control points: a message into a `control` port latches the node open (or closed,
  with `payload.open = false`).
  - A `GATE` with no handler passes only while open, and refuses when nothing is wired
    to its control point.
  - A `SWITCH` starts closed.
  - A `LIMIT` with no `config.flow.rate` refuses.
  - A `BUFFER` holds up to `config.flow.capacity` and releases one message every
    `releaseMs`.
- A human step is `config.behavior.human: {prompt}`. The message parks there until
  `resume(parkId, {decision: approve | reject, payload?})`.

**Effects**
- An effect is `config.behavior.effect: {key: <path into the message>}`, optionally
  with a `handler` that performs it.
- The ledger key is `<node>:<value>`. A confirmed key is **replayed**: logged as
  `effect-replayed`, not performed, and not forwarded.
- A handler that throws leaves the key **ambiguous**. Retries are refused until
  `reconcile(key, {confirmed})`.
- A missing key is refused.
- The ledger survives `snapshot()` → `createSimulation(doc, {restore})`, and can be
  handed to a fresh engine with `{effects}`.

**Handlers**
- A node naming a handler nobody registered refuses its messages.
- Declarative handlers: `{kind: 'stub'}` passes through;
  `{kind: 'fixture', key, responses, otherwise?, merge?}` answers from a table.
- Code callers may pass functions.

**Scenarios**
- Stored as `document.references` with `kind: 'scenario'`, as
  `data: {handlers, steps, expect}`.
- Steps are `inject`, `resume`, `restart` (snapshot, then a new engine), `reconcile`
  and `run`.
- `expect` counts taps, refusals, parked messages, effects by status, and log events.
  The run returns each check with its expected and actual values.

## Signals, time and the clock (built 2026-09-25)

Messages are events. **Levels** are state. Both run on one engine and one clock.

### What a level is

| | Binary | Continuous |
| --- | --- | --- |
| Values | 0 or 1 | 0 to 1 |
| Edge `+` | 0 → 1 | the level rises by more than `epsilon` |
| Edge `−` | 1 → 0 | the level falls by more than `epsilon` |

A level is either asserted or derived.

**Asserted.** The state is declared and changes only by an operation. Examples: a
`LEVER`, a source, a `CLOCK`.
- Operations: `sim.set(node, value)`, a scheduled `sim.at(time, {set | toggle})`, or a
  message whose payload is `{set: v}` or `{toggle: true}`.
- Declared in the document as `config.signal = {value, kind}`.
- Setting a derived signal is refused with `DERIVED_SIGNAL`.

**Derived.** Computed from the node's inputs as they change over time:
`config.signal = {mode: 'derived', kind, combine, threshold}`.
- `combine` is one of `or`, `and`, `not`, `max`, `min`, `mean`, `sum`.
- A binary node thresholds a continuous input.
- An input on a `control` point gates the output: the output is 0 unless the control
  level is at or above `threshold`.

**Legacy components.** Without `config.signal`, the legacy `signalMode` decides, with the
editor's own default: an absent mode is a source.
- `source` is asserted at 1.
- `relay` is derived by `or`.
- `passive` is derived and drives nothing out.

### How levels travel

Levels move over the same arcs as messages, after each wire's latency, and obey the
same passability rules. Every change is recorded as an **edge**: `{at, node, from, to,
polarity, cause}`, readable with `sim.edges({node, since})`.

An edge can start work. `config.signal.on: '+' | '-' | '±'` makes the node emit a
message on that polarity, on `config.signal.channel` (default `edge`). This is how a
step-based effect or a schedule is modelled: a clock's rising edge is a job.

### Clocks and driving time

A **clock** is an asserted node with
`config.signal.clock = {periodMs, phaseMs, duty, wave, sampleMs, cycles}`.
- `wave` is `square` (binary), or `saw`, `triangle` or `sine` (continuous, sampled every
  `sampleMs`).
- `cycles` stops the clock after that many periods.
- A clock without a period is refused with `CLOCK_HAS_NO_PERIOD`.

**Time is the driver.**
- `sim.advance(ms)` runs everything due up to `now + ms`.
- `sim.tick()` takes the next instant and everything due in it.
- `sim.at(time, action)` schedules an operation.

The editor, an agent (MCP `schematic.sim.advance` / `tick` / `at` / `set`) and an outside
process drive the same engine, which makes it the control plane of the canvas.

**Power on.** At time 0, asserted levels above 0 drive out, and clocks start. A snapshot
keeps levels, inputs, edges and the clock's schedule.

### The canvas control plane

The editor's transport (▶ / ❚❚, ⏭ next instant, ⟲ reset, speed, time readout) drives one
engine over the live document (`src/65-sim-control.js`, Browser API `clock.*`).

**What the canvas shows while the clock runs:**
- Each wired node shows its level: a dot for binary, a meter for continuous.
- A high wire turns amber.
- Edges flash `+` in amber and `−` in blue.
- The legacy packet animation stands down, so the canvas has one source of truth.

**What you can do on the canvas:**
- Click a lever's switch to toggle it.
- Press an entry node's ➤ to send the message its saved scenario injects.
- Approve (✓) or reject (✗) a waiting human step in place.

**Rules it keeps:**
- The document is the authority: editing it restarts the clock from time 0.
- The overlay is never saved and never exported.
- A handler that no saved scenario supplies is stubbed, and the readout names it.

## Access control on a plane (built 2026-09-25)

A plane (any Component with an open interior) may declare
`config.acl = {default: 'deny' | 'allow', entries: [{principal, allow: [ops], deny: [ops]}]}`.

- The operations are `enter`, `exit`, `read` and `write`.
- A principal pattern is exact (`svc:mailer`), a prefix (`svc:*`), or `*`.
- **Order does not matter.** Any matching deny refuses. Otherwise any matching allow
  admits. Otherwise the default applies, which is deny unless declared.
- **An anonymous crossing is refused.** A plane with an ACL admits no one who does not
  say who they are.

**Who is acting.**
- A message carries a `principal`. It is set on `inject` and inherited by its copies.
- A component with `config.principal` acts in its own name: messages it forwards carry
  its principal.
- A level carries the principal of the node driving it.

**Where it is checked.** The check happens where a message or a level turns from one side
of the plane's boundary to the other: at a boundary Point of the plane, or at the plane's
own port.
- Crossing from outside to inside is `enter`; from inside to outside is `exit`.
- A wire with a `read` or `write` operation is checked for that operation too.
- A refusal names the principal, the operation and the plane. Refused levels are listed
  with `level: true`.

`graph.query('acl')` lists the planes with an ACL and the principals in the document.
`graph.query('acl', {componentId, principal, op})` answers one question without running
anything.

Example 09's run admits `intake:*` and lets only `svc:mailer` leave. The graph test
swaps Notify's principal for `ai:rogue` and shows the approved proof refused at the exit.

## Print AI mapping (example 09)

`examples/09-print-ai-proof-run.sov` models the Print AI deck's (2026-09-23) active run:
"Proof-resolution @ v3" — Ingest → Evaluate → Human review → Notify. Its five saved
scenarios are the deck's claims, run as evidence.

| Deck concept | In this model |
| --- | --- |
| Case | a source Component outside the run (`case`) |
| Run @ version, the platform boundary | an open Plane whose boundary Points are the only way in (`case in`) and out (`effect out`) |
| Participant AI workflow, adopted and opaque | a Component naming an external handler (`ingest`). It is stubbed in simulation, and in live it will be registered with the relay. |
| Eval / judgement | a `GATE` with a handler (`evaluate`) whose refusal stops the run before any person is asked |
| Monitoring | a fan-out junction (`split`) into an `OBSERVE` (`monitor`) that records observations off the action path |
| ACLs enforce authority, not the prompt | the run's `config.acl`: `intake:*` may enter, only `svc:mailer` may exit; every participant acts under `config.principal` |
| Human gate, where waiting is not computing | `behavior.human` on `review`: the message parks, and the engine is idle until `resume` |
| Mediated effect with stable replay identity | `behavior.effect` on `notify`, keyed by `payload.caseId` |
| Evidence | a `RECEIPT` (`evidence`), plus the engine's log, traces and refusals |
| REQ.EFFECT.HAS_STABLE_REPLAY_IDENTITY | scenario `s-retry`: a retried case messages the customer once |
| INV.RECOVERY.PRESERVES_COMPLETED_EFFECT_IDENTITY | scenario `s-restart`: a restart while parked, and again after the effect; still one message |
| Kill around an effect; reconcile ambiguous work (deck §14.2) | `tests/graph_core_qa.py`: a throwing handler leaves the effect ambiguous, and retry is refused until it is reconciled |

`tests/graph_core_qa.py` also removes the effect identity and confirms that `s-retry`
then fails, with the customer messaged twice. The scenarios can therefore catch the
failure they claim to rule out.

Not yet modelled from the deck:
- version pinning (a run bound to v3 while v4 is published): needs definitions and
  instances (§2)
- Case ↔ Session ↔ Run: needs sessions as participants
- usage and cost meters
- the live relay

## Observed while building (defects outside this change)

1. **A Point's `out` port defaults to out-only** in both the data core
   (`STANDARD_POINT_FLOWS`) and the editor (`componentConfig` defaults). But the
   Point's own attachment spec declares `defaultFlow: 'duplex'`
   (`src/06-attachment-core.js`).
   - Effect: a boundary Point authored with only a `face` cannot receive, so Classic
     08's `permit`, `ingress` and `egress` block wires `k1`, `k3` and `k6`, in the
     signal view as well as the simulation.
   - Example 09 declares its Points `duplex` explicitly.
   - Proposed fix: let the spec's `defaultFlow` win for a 0D `self` point.
2. **The derived signal stops after 6 passes** (`computeSignalState`). A chain deeper
   than 6 hops never lights its far end. In example 09, `evidence`, `run-out` and
   `customer` stay dark although messages reach them.
3. **Component size is clamped silently** in the editor (w ≤ 520, h ≤ 420,
   `src/10-model.js:323`). The data core accepts any size of at least 80 × 64, so a
   file can declare a size the screen never shows.
4. **The router leaves a container at its boundary Points**. In example 09, `case in` →
   Ingest loops out over the plane's top edge, and split → Monitor dips below its
   bottom edge. These are the `throughNode` / escaping-route cases `LAYOUT-MODEL.md`
   §5 is meant to measure.

## Open

1. **Where junction policy lives for duplex carriers:** is one policy right for both
   directions, or does each direction need its own?
2. **Instance parameters:** which fields of a definition an instance may override.
   Proposal: labels, colours, and declared `params` only; structure never.
3. **Scheduling a `source`:** an interval, a cron expression, or inject only in
   phase 1. Proposal: inject only, since scenarios cover repetition.
