# MCP + HTTP surface — 0.1

`mcp/server.mjs` imports the same `src/05-data-core.js` the browser uses. Default durable server file: `data/schematic.sov`. Terms follow `GLOSSARY.md`.

## MCP

```text
POST /mcp
```

Tools, as listed in `mcp/tools.json`:

- `schematic.list`, `schematic.get`, `schematic.create`, `schematic.update`, `schematic.delete`
- `schematic.document.get`, `schematic.document.replace`
- `schematic.history.undo`, `schematic.history.redo`
- `schematic.checkpoint.list`, `schematic.checkpoint.create`, `schematic.checkpoint.restore`

Resources: `component`, `wire`, `reference`.

## HTTP

`GET /api/v1/formats` advertises the document, package, workspace, operation, and receipt schemas. `/api/v1/components`, `/api/v1/wires`, and `/api/v1/references` expose the same CRUD as the MCP tools.

The server persists the canonical `.sov` document. `.sovpak` is a package around that same document, not a second mutable authority.

## Boundary rule

MCP and HTTP Wire writes use the same reachability function as the UI. A child Component cannot use an API mutation to reach an outer Port that is not exposed to its surface. A refused write returns a receipt with `ok: false` and does not enter history.

## Direction, access, operation

Same fields as the browser API: `DATA-FORMATS.md` defines `flow`, `access`, `forwardOperation`, and `reverseOperation`. None of them grants authority.

## Port ids

Agent calls may name Wire endpoints with canonical Port ids or document@0.1 compatibility ids; `API.md` lists both. The shared data core validates both. MCP has no separate legality implementation.
