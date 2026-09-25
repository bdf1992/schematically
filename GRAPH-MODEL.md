# Graph Model · proposed (2026-09-25)

Status: **proposed**. Nothing here is implemented. This doc covers the graph primitives
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

## Open

1. **Where junction policy lives for duplex carriers:** is one policy right for both
   directions, or does each direction need its own?
2. **Instance parameters:** which fields of a definition an instance may override.
   Proposal: labels, colours, and declared `params` only; structure never.
3. **Scheduling a `source`:** an interval, a cron expression, or inject only in
   phase 1. Proposal: inject only, since scenarios cover repetition.
