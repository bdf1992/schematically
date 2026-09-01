# SOV Schematic Operator Skill — 0.1 Public Beta

## Purpose

Operate SOV Schematic through its public data, browser API, HTTP, and MCP surfaces.

## Canonical formats

- `.sov` = `soveraeign.schematic/document@0.1`
- `.sovpak` = `soveraeign.schematic/package@0.1`
- browser recovery = `workspace@0.1`
- mutation envelope = `operation@0.1`
- mutation result = `receipt@0.1`

## Browser API

Use `window.SovSchematicAPI`.

Primary operations:
- `list(resource)`
- `get(resource,id)`
- `create(resource,value)`
- `update(resource,id,patch)`
- `delete(resource,id)`
- `document.get()` / `document.replace(doc)`
- `history.list()` / `undo()` / `redo()`
- `checkpoints.list()` / `create(name)` / `restore(id)`
- `selection.copy()` / `paste()` / `duplicate()`
- `view.setAppearance(mode)` / `setGlobalRate(value)`

Resources in 0.1: `component`, `wire`, `reference`. Ports and Wire Parts remain owned nested records.

## MCP

Discover tools with `tools/list`. CRUD tools share the same transport-neutral data core as the browser and HTTP adapters.

Additional server tools:
- `schematic.history.undo`
- `schematic.history.redo`
- `schematic.checkpoint.list`
- `schematic.checkpoint.create`
- `schematic.checkpoint.restore`

## Mutation discipline

1. Read current state/revision.
2. Apply one coherent semantic mutation.
3. Inspect the receipt.
4. Re-read when topology/reachability may have changed.
5. Use checkpoints for named durable milestones.

Do not treat successful transport as semantic validity. A valid Wire must still satisfy Port/surface reachability.


## Read/write axis
Treat direction, access, and authority as separate. `direction ≠ access ≠ authority`. A Port access value constrains representable Read/Write packet operations; it does not grant authority.
