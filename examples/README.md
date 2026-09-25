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

`optimization/workshop.sov` with its sidecar `workshop.opt.json` is the worked example for `scripts/optimize_sov.py`: a Shop floor Plane that scopes a labor budget, with congestion on the saw and a saturating chair market. See `docs/vision/LINEAR-NONLINEAR-SYSTEMS.md`. `optimization/workshop.learning.opt.json` is a second sidecar for the same document: a learning curve on chairs (cheaper at scale, nonconvex), solved globally with ordered segments. `optimization/workshop.learning.week1.sav` is a saved state (`scripts/simulate_sov.py`): week one of that workshop, ending with a table part-kitted and not counted.

`logic/` holds circuits for `scripts/logic_sov.py`, written by `scripts/build_logic_examples.py`. Combinational: every table gate (`gates.sov`), half and full adders, 4- and 8-bit adders, a 4-bit adder/subtractor, XOR from NANDs, a multiplexer, a window comparator. Sequential: an SR latch from NORs, a 4-bit register, an accumulator (adder plus register, fed back), ripple and synchronous counters, a comparator beside a Schmitt trigger, a reorder control with hysteresis, and completion by AND beside a C-element. See `docs/vision/LOGIC-GATES.md`.
