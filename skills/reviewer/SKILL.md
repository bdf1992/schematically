# SOV Schematic Reviewer Skill — 0.1

## Purpose

Review a schematic independently for structural coherence, boundary correctness, and public-format validity.

## Review order

1. Validate document schema and unique IDs.
2. Confirm every Wire endpoint Component exists.
3. Recompute Port surface reachability for every Wire.
4. Check containment: a hosted Component remains an ordinary Component with a host/surface relationship only.
5. Verify no implicit boundary reach-through.
6. Inspect Pin/Lock/Hidden state for surprising operational restrictions.
7. Inspect Form controls for observable meaning: material, body thickness, frame, frame depth, interior state.
8. Confirm checkpoints are non-recursive snapshots and current document remains loadable.
9. Exercise API/MCP CRUD rather than trusting UI appearance.
10. Compare admitted dimensions with painted bounds and saved/reopened geometry, including nested children, boundary attachments and wire endpoints. A headless validation pass cannot detect a browser-only rewrite.
11. Inspect the normal editor and standalone SVG at 768px and 1440px in light/dark. Check actual screen text size, label/node/wire clearance, title separation, continuous routes and unambiguous crossings. Use overview plus focus/pan/zoom when needed; retain before/after images. Compare wrapper CSS separately.
12. Trace Component boundary/interior and endpoint connection color slots. Verify authored meaning survives `.sov`/`.sovpak`; derived hex colors are not authority. Check custom graphics for aspect, padding, contrast, selection and export with editable labels/ports.
13. Exercise Pin, parent movement, Unpin and Undo. A parent currently carries pinned descendants; pin the ancestor for a stationary structure. Semantic edits remain possible on pinned unlocked components. Audit quiet unused ports separately from absent ports and retain connected endpoints.
14. Report authoring defects, editor defects, wrapper issues and missing evidence separately. Proposed architecture does not establish runtime security or external-effect guarantees.

## Quality bar

A green review means:
- standalone `index.html` boots;
- modular source rebuilds deterministically;
- browser QA passes without page errors;
- `.sov` and `.sovpak` parse/round-trip;
- API and MCP tools operate on the same semantic core;
- locked/pinned/boundary invariants cannot be bypassed by ordinary editor operations.


## Read/write axis
Treat direction, access, and authority as separate. `direction ≠ access ≠ authority`. A Port access value constrains representable Read/Write packet operations; it does not grant authority.
