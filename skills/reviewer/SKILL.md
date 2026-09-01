# SOV Schematic Reviewer Skill — 0.1 Public Beta

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
10. Report limitations separately from defects.

## Public-beta quality bar

A green review means:
- standalone `index.html` boots;
- modular source rebuilds deterministically;
- browser QA passes without page errors;
- `.sov` and `.sovpak` parse/round-trip;
- API and MCP tools operate on the same semantic core;
- locked/pinned/boundary invariants cannot be bypassed by ordinary editor operations.


## Read/write axis
Treat direction, access, and authority as separate. `direction ≠ access ≠ authority`. A Port access value constrains representable Read/Write packet operations; it does not grant authority.
