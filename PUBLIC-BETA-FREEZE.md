# Public Beta Freeze Candidate — 0.1

Status: **PRE-FREEZE RELEASE CANDIDATE**

This line is intended to become the first public repository baseline after repository creation and license selection.

## Frozen public contracts for 0.1

- `.sov` logical schema: `document@0.1`
- `.sovpak` logical schema: `package@0.1`
- CRUD envelope/result: `operation@0.1` / `receipt@0.1`
- Components, Wires, References as top-level CRUD resources
- Ports and Wire Parts as owned nested records
- boundary reachability: no implicit reach-through
- containment/hosting does not create a second Component implementation
- deterministic standalone build from modular source
- browser API and file-backed HTTP/MCP adapters over the common data core

## Included editor kernel

- semantic undo/redo history
- named persisted checkpoints
- semantic copy/paste/duplicate
- multi-select + marquee
- settle/hosting ghost
- Pin / Lock / Hidden / Opacity
- Objects panel + quick search/command
- Light / Dark / System appearance
- shortcut help
- global / Component / Wire rate composition

## Known Beta limits

- signal execution is a structural/visual Beta model, not a complete timed circuit simulator;
- 3-D Form is represented but not yet a full spatial renderer;
- z-order/depth-of-field and temporal spatial traversal are intentionally deferred;
- generic grouping is intentionally omitted in favor of structural hosting;
- rotation remains deferred until Port/routing transforms have a defined semantic contract;
- licensing is intentionally not chosen by the build process and must be selected before public reuse terms are claimed.

## Freeze rule

After the repository baseline is cut, changes to frozen format/API invariants require explicit versioning or a documented compatibility migration. UI refinement may continue without silently changing those contracts.



### Beta.24 access axis
Port Connections may carry `access: none | read | write | read-write`. Wire config may carry `forwardOperation` / `reverseOperation: none | read | write`. Direction, access, and authority are independent.


## Beta.24 final engineering gate

Regression, performance regression, boundary legality, Read/Write, and targeted mutation gates pass. Remaining pre-repository gate: human manual QA plus license/repository creation. See `MODULE-QA.md` and `PERFORMANCE.md`.
