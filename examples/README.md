# Classic examples

These files are executable reference material for the 0.1 contract.

| File | Demonstrates |
| --- | --- |
| `01-source-hold.sov` | Simple forward source → relay flow |
| `02-duplex-buffer.sov` | Duplex Wire and expected return relationship |
| `03-contained-stage.sov` | Ordinary Component hosted by an open interior Region |
| `04-boundary-port.sov` | Explicit boundary crossing through an inside-facing parent Port |
| `05-rate-chain.sov` | Global × source Component × Wire rate composition |
| `08-gated-service.sov` | Authored by hand in the `skills/author-offline` form: a Plane with three boundary Points, an authority into a gate's control, a receipt |
| `classic-reference.sovpak` | Portable reference package containing metadata and embedded copies of the classic examples |

All `.sov` examples pass `SovSchematicData.validateDocument()`.

- `06-read-write-evidence.sov` — Write into a durable RECORD and Read for a WITNESS/Observer; demonstrates direction vs access without treating either as authority.
- `07-plane-with-points.sov` — a Plane with two boundary-hosted Points (face `both`) carrying a Source → Stage → Record chain across its boundary; written in the compact record form.

Render any of these to a standalone SVG with `python scripts/export_svg.py examples/<name>.sov`.
