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
its declared compat id): that entry is instead kept under a fresh id (`<id>~2`, `<id>~3`, ...) and the Wire end is
rebound to it by `pointId`, so loading never unbinds a Wire on a collision.
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

- **`config.definition`** on a Component: the definition it is bound to, `id@version` (`"logic.and@1"`). Binding
  (`bindDefinition`, applied as a component `update`) also sets `attachmentDefaults: none` and exactly the
  contract's generated ports as `attachmentPoints`: one per input on the left and one per output on the right,
  spread evenly unless the definition's `ports` places them. The existing Wire checks apply (`PORT_IN_USE`). A
  definition whose contract has no ports (one on `merge@1`) is refused (`DEFINITION_NOT_BINDABLE`). Rebinding carries
  each channel `merge` to the same port id and channel id, and is refused with `MERGE_IN_USE` when the new contract
  drops a port or channel holding one. While bound, an update that does not itself set `config.definition` is
  refused with `DEFINITION_PORTS` when it would change the port ids, a port's `flow` or channel ids, set
  `attachmentDefaults` to anything but `none`, or change `symbolId`; moving, relabelling and channel `merge` edits
  are allowed. Setting `config.definition` to `null` unbinds and leaves the ports as stored.
- **`config.delay`** on a Wire: its propagation delay in logical ticks, an integer >= 1. Absent means 1 and is not
  written. A Wire `create` or `update` carrying any other value is refused with `PATH_DELAY_INVALID` on every
  surface; loading keeps a stored value as written.
- **`merge`** on a declared port's channel: the `merge@1` parameters for same-tick arrivals there.

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
