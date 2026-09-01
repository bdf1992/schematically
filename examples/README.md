# Classic examples

These files are executable reference material for the 0.1 contract.

| File | Demonstrates |
| --- | --- |
| `01-source-hold.sov` | Simple forward source → relay flow |
| `02-duplex-buffer.sov` | Duplex Wire and expected return relationship |
| `03-contained-stage.sov` | Ordinary Component hosted by an open interior Region |
| `04-boundary-port.sov` | Explicit boundary crossing through an inside-facing parent Port |
| `05-rate-chain.sov` | Global × source Component × Wire rate composition |
| `classic-reference.sovpak` | Portable reference package containing metadata and embedded copies of the classic examples |

All `.sov` examples pass `SovSchematicData.validateDocument()`.

- `06-read-write-evidence.sov` — Write into a durable RECORD and Read for a WITNESS/Observer; demonstrates direction vs access without treating either as authority.
