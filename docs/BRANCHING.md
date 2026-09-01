# Branching and release flow

## Current stabilization

`rc/0.1.0-rc1` is the only implementation line for the current RC. It accepts:

- release-blocking defect fixes;
- primitive refactors required by `RC-FINISH-LINE.md`;
- regression/golden/performance/mutation tests;
- docs/schema/example/API/MCP changes required to keep the tested RC coherent.

It does **not** accept implementation of NEXT/post-RC features.

## RC merge

When the finish line and repository CI are satisfied:

```text
rc/0.1.0-rc1 → main
```

The merge records an accepted 0.1 primitive baseline. It does not claim the broader Beta/product vision is complete.

## Development after RC merge

Only after that merge:

```text
main → dev
```

Create `dev` from the accepted `main` head. Post-RC feature work branches from `dev` and returns through PRs.

```text
main
 └─ dev
    ├─ feature/topology-cell-grammar
    ├─ feature/data-driven-packs
    ├─ feature/logic-machine
    └─ feature/space
```

When the next set of development concerns is coherent enough to stabilize, cut the next RC from `dev`.

## Why not branch dev before the RC merges?

A pre-merge `dev` branch would bind speculative work to an unaccepted RC state, create avoidable rebase/cherry-pick pressure during final QA, and make it easier for NEXT work to leak back into release acceptance.

Vision documents and NEXT issues may be refined during RC QA; implementation waits for the accepted baseline.
