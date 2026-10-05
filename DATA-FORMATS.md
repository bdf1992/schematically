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

Components and Wires may carry an `editor` object with `pinned`, `locked`, `hidden`, `opacity`, and `rate`. Named checkpoints persist in `document.meta.checkpoints`; each checkpoint stores a non-recursive document snapshot.

`document.meta.timeScale` is the document's own rate (issue #40: the document's rate beats the view's). It is a finite number >= 0, where 0 means paused; anything else - negative, `NaN`, `Infinity`, `null`, a string, a boolean - is refused with `TIME_SCALE_INVALID`, by file open, by `PUT /api/v1/document` and by `view.setGlobalRate` alike (one admission rule). A workspace never rewrites it: `view.playbackSpeed` is the view's own playback speed (the simulation clock), independent of the document's rate.

`document.meta.palette` is the document's own palette. It takes one of two shapes: a palette name, one of `okabe-ito`, `system-default`, `spectrum`, `cool`, `warm`, `earth` or `mono`; or `{"custom": ["#RRGGBB", ...]}` with exactly six hexes and no other key. It wins over the view's palette when the document opens; a document without it draws in the view's palette. A string that is not one of the seven names (`custom` and the empty string included) is refused with `PALETTE_UNKNOWN`, and any other shape (`null`, a number, a boolean, an array, a wrong count, a non-hex entry, an extra key) with `PALETTE_INVALID`, by file open, by `PUT /api/v1/document` and document replace, and by `view.setDocumentPalette` alike (one admission rule); a refused value is reported and changes nothing. Custom hexes are kept as written and realised through the same theme contrast floor as every palette, one row for both appearances. The palette picker (and `view.setColour`) writes the document while the document declares a palette and the view otherwise; `view.setDocumentPalette(null)` removes the declaration. A workspace or package view never carries the document's palette: `view.colorEngine` holds only the view's own palette and custom row.


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


## Status and waits-on (2026-10-01, `NOTATION-MODEL.md` "Domain notation: work-engine")

A Component or a Wire may say how far along it is and what it waits on. Both keys are optional and
absent is not written.

- **`config.status`**: a string, the `id` of an entry in the `statuses` list of the document's
  resolved notation (`SovSchematicNotation.resolve(doc).notation.statuses`). There is no built-in list:
  the values are the notation's (the `work-engine` notation declares `exists`, `partial`, `missing`,
  `proposed`). A status in a document whose notation declares no statuses is `STATUS_UNDECLARED`; a
  value the notation does not declare, or a value that is not a string, is `STATUS_UNKNOWN`, and the
  message lists the declared ids.
- **`config.waitsOn`**: an array of `{kind, id, label?}`, where `kind` is `person | rule | decision`,
  `id` is a non-empty string and `label`, when present, is a string; no other key is allowed. Anything
  else is `WAITS_ON_INVALID`, and the message names the index and the field
  (`config.waitsOn[1].kind must be one of person, rule, decision`).

```json
{"label": "Continuity records move to SQLite", "status": "proposed",
 "waitsOn": [{"kind": "person", "id": "bdo", "label": "Bdo"}, {"kind": "rule", "id": "R-29"}, {"kind": "decision", "id": "D1"}]}
```

A `create` or `update` carrying either key in a bad form is refused with the code (the error message
starts with it) on every surface, and the document is unchanged. An `update` with `status: null` or
`waitsOn: null` removes that key. Loading keeps the stored values as written and `validateDocument`
reports each finding as `component <id>: <CODE>: ...` or `wire <id>: <CODE>: ...` (marker rule
`status`). The schema (`formats/schematic.document.schema.json`) declares both keys on
`components[].config` and `wires[].config`.

### A Wire's kind (2026-10-04, `NOTATION-MODEL.md` "Kinds")

A Wire may say what kind of line it is. The key is optional and absent is not written.

- **`config.kind`** (Wires only): a string, the `id` of a wire kind in the `kinds` list of the
  document's resolved notation (`SovSchematicNotation.kindsOf(notation, 'wire')`). The entry declares
  the dash, weight and arrowhead the Wire is drawn in. There is no built-in wire kind: a kind in a
  document whose notation declares no wire kinds is `KIND_UNDECLARED`; a value the notation does not
  declare, or a value that is not a string, is `KIND_UNKNOWN`, and the message lists the declared ids.
  A Component takes no `config.kind`: a region's kind is what it is (a group, a plane, a container,
  a gate, an intake region).

```json
{"label": "approves", "kind": "control"}
```

It is validated the way a status is: a `create` or `update` with a bad kind is refused with the code
and the document is unchanged, an `update` with `kind: null` removes the key, and loading reports
`wire <id>: <CODE>: ...`. An entry of the notation's own `kinds` that breaks a rule is reported on
load as `notation: KIND_INVALID: ...`. All three codes carry the marker rule `status`. The schema
declares the key on `wires[].config`.


## Answers (2026-10-04, `NOTATION-MODEL.md` "Concerns")

A notation declares the questions a schematic should answer (its `concerns`), and a document carries
the answers. Every key is optional and absent is not written: a document with no answers has no
`answers` key anywhere, and the data core never adds an empty one.

- **`meta.answers`**: the document's answers to the document concerns of its resolved notation
  (`SovSchematicNotation.concernsOf(notation, 'document')`). The built-in `schematic` notation
  declares `what`, `why`, `alternatives` and `smaller`.
- **`config.answers`** on a Component or a Wire: its answers to the notation's component concerns or
  wire concerns. There is no built-in one of either. A component concern that names `symbols` is
  asked only of Components with one of those symbol ids: an answer to it on any other Component is
  `ANSWER_UNKNOWN` (the message lists the ids asked of that symbol) and the report holds no row for it.

Each is an object whose keys are concern ids and whose values are non-empty strings after trimming.

```json
{"meta": {"answers": {"what": "A half adder.", "why": "To teach carry."}}}
```

```json
{"label": "Smelter", "answers": {"made-by": "Smelt two ore."}}
```

| Code | When |
| --- | --- |
| `ANSWER_INVALID` | `answers` is not an object, or a value is not a non-empty string; the message names the key (`config.answers.made-by must be a non-empty string`) |
| `ANSWER_UNDECLARED` | a key is set and the notation declares no concerns for that `applies` (a card's answer in a `schematic` document) |
| `ANSWER_UNKNOWN` | the key is not a concern the notation declares for that `applies`; the message lists the declared ids |
| `ANSWER_TARGET_UNKNOWN` | `answerConcerns` only: an entry's `target` names no Component and no Wire |

A `create` or `update` of a Component or a Wire carrying a bad `config.answers` is refused with the
code (the error message starts with it) and the document is unchanged. An `update` merges
`config.answers` per key into the answers already there: a non-empty string sets that concern's
answer, `null` removes that one answer (`{"answers": {"made-by": null}}`), and `answers: null`
removes them all. When the last answer goes, the `answers` key goes with it, so no empty object is
stored. A `null` for a key the notation does not declare is refused like any other value for it, and
on `create` a `null` is `ANSWER_INVALID`. Loading keeps the
stored values as written and `validateDocument` reports each finding as `<CODE>: meta.answers...`,
`component <id>: <CODE>: ...` or `wire <id>: <CODE>: ...`, and each broken entry of the notation's own
`concerns` as `notation: CONCERN_INVALID: ...` (marker rule `status`). Saving, opening and compacting
keep `meta.answers` and every `config.answers`. The schema
(`formats/schematic.document.schema.json`) declares the key on `meta`, `components[].config` and
`wires[].config`.

**The report.** `SovSchematicData.concernReport(doc)` returns `{notation, rows, answered, open}`
and changes nothing. `rows` holds one row per declared concern per thing it applies to: the document
concerns in declared order with `target: null`; then each Component in document order with each
component concern and `target` the Component's id; then each Wire the same way. A row is `{concern,
applies, target, title, question, answered, answer}`: `title` is the entry's title or its id, and
`answer` is present only when `answered` is true. `answered` and `open` are the two counts. An
unanswered concern is open: it is information, never an error. An answer the notation does not
declare is not a row; it is one of the codes above. `concernReport(doc, {open: true})` keeps only
the open rows; the two counts stay those of every row.

**The write.** `SovSchematicData.answerConcerns(doc, {answers, ifRevision})` is the one verb that
sets or removes answers on the document, Components and Wires together. `answers` is a non-empty
list of `{concern, target, answer}`: `target` is absent or `null` for the document, else the id of a
Component or a Wire; `answer` is a non-empty string to set, `null` to remove.

```json
{"answers": [
  {"concern": "what", "answer": "An ore line."},
  {"concern": "made-by", "target": "smelter", "answer": "Smelt two ore."},
  {"concern": "carries", "target": "belt", "answer": null}
]}
```

It is all or none and moves the document one revision. Every entry is checked before anything is
written; each Component and Wire named gets one `update` and they run through `applyBatch`, so
locks, refusals and the receipt are an update's; the document's own entries are written into
`meta.answers` in that same revision. The receipt is `applyBatch`'s with `result.report: {answered,
open}`, the report's two counts after the write. Removing an answer that is not set is admitted and
changes nothing for that entry. Refusals, each changing nothing, with `error.index` the entry:

- `ANSWER_INVALID`: `answers` is empty or not a list, an entry is not an object, it has a key
  outside `concern`, `target`, `answer`, its `concern` is not a non-empty string, or its `answer` is
  neither a non-empty string nor `null`;
- `ANSWER_TARGET_UNKNOWN`: `target` names no Component and no Wire;
- `ANSWER_UNKNOWN` and `ANSWER_UNDECLARED`: as above, for that target's `applies` (a removal too);
- a stale `ifRevision` (`Stale revision: expected <n>, document is at <m>`), as `applyBatch`.

Every surface calls it and holds no rule of its own: `schematic.concerns.answer` (MCP),
`POST /api/v1/concerns` (HTTP) and `SovSchematicAPI.concerns.answer` (browser); the report is
`schematic.concerns`, `GET /api/v1/concerns` and `SovSchematicAPI.concerns.list`.

**The validator flag.** `node scripts/validate_sov.mjs --concerns file.sov` prints, after the `ok`
line of a valid file, one line per open row and then the counts. The exit code is the same with and
without the flag.

```
ok   line.sov  (2 components, 1 wires)
open  document - why: Why would the plant run this line?
open  component smelter repeatable: Is this made once or over and over?
open  wire belt carries: What moves along this, and how much?
concerns: 6 answered, 3 open
```


## Badges (2026-10-04, `NOTATION-MODEL.md` "Statuses")

A Component may carry small chips of text and a palette colour, with no status's meaning.

- **`config.badges`**: an array of at most 4 entries `{label, colorSlot?}`. `label` is a string of 1 to
  24 characters after trimming; `colorSlot` is an integer 0 to 11, and absent means 0; no other key is
  allowed. Anything else is `BADGE_INVALID`, and the message names the index and the field
  (`config.badges[1].label must be a non-empty string`; more than 4 entries; not an array).

```json
{"label": "Booth", "badges": [{"label": "Record"}, {"label": "Owned by seat", "colorSlot": 7}]}
```

A `create` or `update` of a Component carrying a bad `badges` is refused with the code and the document
is unchanged; an `update` with `badges: null` removes the key. Loading keeps the stored value and
`validateDocument` reports `component <id>: BADGE_INVALID: ...` (marker rule `status`). Badges are
presentation: they change no other validation, the runtime or the legend. The schema declares the key
on `components[].config`.

Drawing (`appendComponentBadges`, 2D cards): one chip per badge in a row from the card's top-left
corner, 6 in from the left and top edges and 4 apart. Each chip has the status chip's geometry (height
caption size x 1.5, width label length x caption size x 0.6 + caption size, fully rounded), is filled
with its slot colour at .16 over the card fill, edged in the slot colour at width 1, and holds the label
in the caption role with ink at 4.6:1 against that fill. Class `card-badge`, `data-badge-index`. A badge
that would come within 4 of the status chip or within 6 of the card's right edge is not drawn; the last
chip drawn then reads `+N`, N the badges without a chip of their own, and its `<title>` lists their
labels.


## Card shape (2026-10-04, `SECTION-MODEL.md` "Card shapes")

A card may be drawn as a cylinder (a store) or a parallelogram (input and output), after the ISO 5807
flowchart symbols.

- **`config.presentation.shape`**: `rect`, `cylinder` or `parallelogram`. Absent means `rect`, and
  `rect` is admitted on any Component. `cylinder` and `parallelogram` belong to a 2D Component that is
  not a group and has a closed interior. Any other value, or either shape on any other Component, is
  `SHAPE_INVALID` (`config.presentation.shape must be one of rect, cylinder, parallelogram, not "disk"`).
  `disk` names a section preset (`SECTION-MODEL.md` "Presets"), never a shape.

```json
{"label": "Store", "presentation": {"shape": "cylinder"}}
```

A `create` or `update` of a Component carrying a bad `shape` is refused with the code and the document
is unchanged; an `update` with `shape: null` removes the key. Loading keeps the stored value and
`validateDocument` reports `component <id>: SHAPE_INVALID: ...`; a card whose shape is not admitted is
drawn as a rectangle. The shape is presentation: it changes no port position, no route, no layout
metric and nothing the runtime reads. The schema declares the key on `components[].config.presentation`.
The selection panel's Boundary row shows it. QA: `tests/card_shapes_qa.py`.


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
- **`config.delay`** on a Wire: its propagation delay in logical ticks, an integer >= 0. Absent means 1 and is not
  written. `0` is a zero-delay Path; a cycle made only of zero-delay legs is refused when the run starts, with
  `ZERO_DELAY_CYCLE`. A Wire `update` with `delay: null` removes it. A Wire `create` or `update` carrying any
  other value is refused with `PATH_DELAY_INVALID` on every surface; loading keeps a stored value as written.
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
(`schematic.run.start`, `.step`, `.settle`, `.trace`, `schematic.state.query`, `schematic.run.replay`); `runId` is the
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
(1,000,000) is refused with `INPUT_INVALID`; `startRun` itself is not capped. No run operation captures history,
changes the document or its revision, or saves recovery. The browser reads its packs from `<script
type="application/json" id="sov-packs">`, into which `build.py` inlines every `data/*.pack.json`; the MCP/HTTP server
reads `data/*.pack.json` at start.

`settle` is linear in the ticks it processes: each tick costs a summary kept incrementally (the true signal keys'
count and code sum, each queue's length, relative next and positional code sum, the pending count and code sums with
relative times); the full hash is computed only when a summary repeats, for that tick and for each earlier tick with
the same summary (its state rebuilt from the kept pending list, the queue's item log and the later signal flips).
Equal states have equal summaries, so results are those of hashing every tick.
