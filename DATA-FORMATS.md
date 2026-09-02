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

## Template attachment seam

A 2D Component may declare additional boundary attachment descriptors under `config.attachmentPoints`, e.g. `{id, compatId?, side: left|right|top|bottom, t: 0..1, defaultFlow?}`. Built-in dimensional attachment sets remain defaults. Full Part/facet/cell grammar is intentionally post-RC.


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

`config.attachmentDefaults: standard | none` is stored only when `none`. The symbol
ids `point`, `path`, `plane` carry Form presets; `port` is read as `point`.
