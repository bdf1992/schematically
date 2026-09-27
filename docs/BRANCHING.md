# Branching and release flow

## Current development · 2026-09-07

The RC has merged to `main` through [PR #28](https://github.com/bdf1992/schematically/pull/28),
and `dev` exists. Feature work branches from `dev` and returns to `dev` through PRs.
See [the roadmap](../ROADMAP.md) for the inspected revisions and product priorities.

When development is coherent enough to stabilize, cut the next `rc/<version>`
from `dev`. That candidate accepts release-blocking fixes and the tests,
documentation, schemas, examples, and API/MCP changes needed to keep it coherent.
Future feature implementation continues separately on `dev`.

## Release gate

`RC-FINISH-LINE.md` owns release acceptance. The candidate must contain the exact
source used for acceptance and pass repository CI before merging to `main`.
Acceptance of a primitive baseline does not complete the broader product vision.

## Historical 0.1 branch boundary

During stabilization, `rc/0.1.0-rc1` was the sole RC implementation line.
Post-RC feature implementation waited until the accepted baseline merged to
`main`, then `dev` was created from that baseline. That ordering avoided binding
speculative work to an unaccepted RC. It is completed history, not an instruction
to recreate `dev` or return current feature work to the old candidate.
