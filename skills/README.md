# Agent skills

- `author/SKILL.md` — author valid semantic schematics.
- `author-offline/SKILL.md` — write a `.sov` by hand with no editor or API; validate with `scripts/validate_sov.mjs`, render with `scripts/export_svg.py`.
- `operator/SKILL.md` — operate `.sov` / `.sovpak`, Browser API, HTTP, and MCP.
- `reviewer/SKILL.md` — independently review a schematic or build.
- `layout-review/SKILL.md` — look at the rendered pictures in a reader's voice, score them, and turn every disagreement with the audit into a measure (`scripts/layout_review.py`, `scripts/contrast_audit.py`).

The skills intentionally point agents back to the same public formats and CRUD semantics used by the interactive editor.
