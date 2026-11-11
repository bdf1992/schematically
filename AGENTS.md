# Agent Contract

SOV Schematic is a semantic editor, not an SVG drawing program.

Before changing behavior, identify the owning concern in `MODULES.md`. Do not duplicate model, routing, rendering, interaction, persistence, or API logic in another module.

## Invariants

- Components inside Components use the same Component implementation as root Components.
- Ports outrank transform handles in pointer hit-testing.
- No implicit reach-through across Component boundaries.
- Wires connect endpoints only when their exposed surfaces intersect.
- Pin freezes geometry. Lock freezes semantic mutation.
- Hidden is recoverable and is not deletion.
- One pointer gesture should produce one meaningful history transition.
- Visible settings must have observable effects.
- `index.source.html` + modular source are canonical development inputs; `index.html` is the deterministic standalone build.
- Browser API, HTTP, and MCP should delegate to shared data semantics rather than inventing parallel CRUD rules.

Run the QA scripts in `tests/` before claiming a change is settled.

Pull requests run `python scripts/pr_tests.py`: only the suites the change touches, stopped at 60 s.
Releases run `python scripts/release.py vX.Y.Z`: the whole suite on this PC, then the tag.
