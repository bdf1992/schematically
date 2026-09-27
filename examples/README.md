# Classic examples

These files are executable reference material for the 0.1 contract.

| File | Demonstrates |
| --- | --- |
| `01-source-hold.sov` | Simple forward source → relay flow |
| `02-duplex-buffer.sov` | Duplex Wire and expected return relationship |
| `03-contained-stage.sov` | Ordinary Component hosted by an open interior Region |
| `04-boundary-port.sov` | Explicit boundary crossing through an inside-facing parent Port |
| `05-rate-chain.sov` | Global × source Component × Wire rate composition |
| `09-print-ai-proof-run.sov` | The Print AI proof-resolution run: an adopted AI step, an eval gate, a monitored fan-out, a human pause, and a mediated effect with replay identity. It carries five saved scenarios; run them with `sim.scenario(id)` (`GRAPH-MODEL.md`) |
| `10-clocked-signals.sov` | Time and levels: a square clock ANDed with a lever lights a lamp; a continuous sine is thresholded, and each rising crossing starts a job. Three scenarios check the edges (`+` and `−`) |
| `11-sections.sov` | Sections: disk, circle, a cell with a skin (and a child inside it), coated, double wall; wires as line, strip, lanes and pipe (`SECTION-MODEL.md`) |
| `12-membrane.sov` | Exposure by position: a channel and a pore through a cell's skin carry work in and out; a receptor on the outer line reaches only the outside |
| `13-half-adder.sov` | A domain notation (`NOTATION-MODEL.md`): `notation: 'logic'` draws IEEE 91 gates whose terminals are real points; the simulation runs each gate's combine. Subtitles, a narration track, and a crossing drawn as a hop |
| `08-gated-service.sov` | Authored by hand in the `skills/author-offline` form: a Plane with three boundary Points, an authority into a gate's control, a receipt |
| `09-proposed-service-review.sov` | Proposed request/control/evidence lanes, palette slots, pinned host/reference, team/history custom SVG. Describes an architecture; does not execute authority. |
| `classic-reference.sovpak` | Portable reference package containing metadata and embedded copies of the classic examples |

All `.sov` examples pass `SovSchematicData.validateDocument()`.

- `06-read-write-evidence.sov` — Write into a durable Record and Read for a Witness (an observer); demonstrates direction vs access without treating either as authority.
- `07-plane-with-points.sov` — a Plane with two boundary-hosted Points (face `both`) carrying a Source → Stage → Record chain across its boundary; written in the compact record form.
- `09-typed-captions.sov` — typed Components (ACT, GATE, HOLD) that author no label and no label mode, so the only text they can show is their type caption; one labelled RECEIPT proves an authored label still wins. `tests/golden_rendered_text_qa.py` reads what these documents actually draw.

Render any of these to a standalone SVG with `python scripts/export_svg.py examples/<name>.sov`.

The [reviewed swarm diagrams](swarm/README.md) preserve the supplied platform, service
and collaboration topology while adding concise captions, palette roles, pins and
portable graphics. Read the narrow-view guidance and package rate caveat in the
[acceptance report](../docs/qa/authoring-38/original-review/README.md).
