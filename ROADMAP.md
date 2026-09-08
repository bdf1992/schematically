# Schematically product roadmap

This file owns product milestones and development priorities. `RC-FINISH-LINE.md`
continues to own release acceptance; `docs/vision/` holds the broader language horizon.

## Current baseline · 2026-09-07

The RC has merged to `main` through [PR #28](https://github.com/bdf1992/schematically/pull/28),
and `dev` exists. New feature work branches from `dev` and returns through PRs.
The inspected baseline is `dev` at `30b9edf` and `main` at `5622888`.
[PR #33](https://github.com/bdf1992/schematically/pull/33) proposes the deterministic
logic and memory runner. Its draft branch passed 40 Python QA suites and 19
JavaScript tests, plus the pinned-browser CI verification. That evidence applies
to its tested revision `3cc6e0c`, not to a merged release or completed product.

The immediate product direction is an executable system notebook: a person can
state a small requirement, model it, run it, inspect state and history, revise a
rule, and share a resumable example. The runtime proposal is a foundation for
this loop. Richer payloads, usable rule authoring, and a SOV adapter still need work.

## Product milestone scenarios · 2026-09-07

Prepared at Bdo's request. These assistant estimates are planning hypotheses for
review, not measured velocity or delivery commitments. Windows start on
**2026-09-07**, overlap, and assume continued development intensity with AI
assistance, one stable initial workflow, and time reserved for user trials and
repair. Weekly effort and paying-customer demand have not been established.

| Milestone | Planning window | Scope and observable exit |
| --- | --- | --- |
| Private alpha | 4–8 weeks | Review and land the runner; provide a small set of validated examples, approachable rule/state controls, and clear errors. An unfamiliar technical user completes a model/run/inspect/save/resume loop and reports the points where help was needed. |
| Focused schematically product | 2–4 months | Choose one audience and workflow from alpha evidence; support the required payloads and rules, reliable sharing/migration, onboarding, and recovery. Users repeat the workflow without Bdo guiding each step, and a trial establishes whether they value the result enough to keep using or pay for it. |
| Combined SOV pilot | 4–8 months | Depends on the focused workflow and a SOV adapter with identity, grants, versioned inputs, durable records, refusal, and safe retry/resume. A pilot user can trace diagram revision through execution and resulting evidence. The SOV roadmap owns the broader deployment forecast. |

**90-day candidate proof, by 2026-12-06:** an unfamiliar technical person models
a small workflow, runs it, inspects its memory and history, changes a rule, and
shares a resumable example without Bdo's guidance. Record task outcome, time,
assistance, and recovery failures. This is a proposed product test, not a release
acceptance rule or a promise that every horizon feature will be ready.

### Development sequence and boundaries

1. Review the proposed runner and preserve deterministic browser/API/MCP behavior.
2. Complete the human authoring and inspection loop around one worked example;
   extend payload and rule semantics only where that workflow requires them.
3. Trial with unfamiliar users, repair observed failures, and settle a focused
   product scope before expanding packs, Space, or instruction compilation.
4. Specify and exercise the SOV adapter against SOV's admitted interfaces and
   authority. Keep local execution usable independently of the integration.

Schematically owns diagrams, validated rules, deterministic local runs, and saved
state. [SOV's roadmap](https://github.com/bdf1992/Soveraeign/blob/main/ROADMAP.md)
owns governed execution and its node/team/federation forecasts. A `.sovrun` trace
from the proposal does not confer a SOV grant, independent findings, or settlement.
The integration should identify model/rule revisions, bound memory crossings,
link execution records, and prevent retries from duplicating external effects.
Product readiness does not open SOV Phase II or satisfy Phase 1.5 exit custodies.

### Forecast review

Review on **2026-10-05**, or earlier after the first external-user trial, a material
runner change, or a failed dependency. Bdo owns scope and acceptance. Each revision
should name its author/date, source revisions, range, assumptions, dependencies,
observable exit, next review trigger, and evidence of actual outcomes. Calibrate
from completed workflows and rework; do not infer delivery pace from commit count.

## Historical RC boundary

The following stabilization scope and gate preserve the release boundary that
preceded the current `dev` work. They are not the current implementation queue.

### Original NOW — `rc/0.1.0-rc1`

Only stabilization, primitive correction, compatibility, QA, and repository settlement belong here.

### Primitive/model
- finish the 0D attachment-point refactor;
- make 1D-hosted and 2D-hosted attachment interactions behaviorally identical except for geometry;
- keep root/nested/inline entities on one implementation path;
- keep Point / Path / Surface dimensional behavior real rather than cosmetic;
- do not freeze `dimension + 1` as a maximum attachment-count rule;
- preserve 0.1 compatibility projections and deterministic migration.

### Interaction/editor
- deterministic drag/settle/detach/growth;
- point/port hit priority over transforms;
- destructive Undo/Redo correctness;
- one state authority for Grid/appearance/file/editor utilities;
- exact carrier-to-inline-component geometry;
- correct duplex, channel, packet skin, direction, access, and boundary behavior already promised by Beta.

### API / MCP / files
- editor/API/MCP legality parity;
- deterministic `.sov` / `.sovpak` round-trip;
- exact schema/migration behavior;
- golden agent CRUD runs over the supported RC model.

### Quality / repository
- tracked manual defects;
- regression tests for fixed defects;
- golden corpus;
- mutation watcher;
- performance watcher;
- visual Light/Dark checks;
- repeated gesture stress tests;
- exact tested source committed to the RC branch;
- CI reproduces the local candidate;
- license + release metadata chosen;
- RC PR reviewed and merged to `main`.

### Original merge gate

The RC merges only when:

1. `RC-FINISH-LINE.md` is satisfied;
2. repository CI reproduces the candidate being manually tested;
3. no known blocker remains open without an explicit acceptance decision;
4. the RC PR contains the exact runtime, docs, schemas, examples, skills, and tests used for acceptance.

Merging the RC means **the 0.1 primitive foundation is accepted**, not that Beta is finished or bug-free.

## Development after the RC — `dev`

`dev` was created after the RC merged to `main`. Continue feature work from `dev`; do not branch new work from the historical RC candidate.

Post-RC work may then proceed on feature branches from `dev`, returning to `dev` through PRs. A later stabilization cut branches from `dev` into the next RC.

```text
rc/0.1.0-rc1
      ↓ accepted
    main
      ↓ branch after merge
     dev
   ↙  ↓  ↘
feature/*
      ↓
     dev
      ↓ stabilization cut
rc/<next>
```

### First post-RC candidates

1. **Topology grammar — Issue #7**
   - landed on `dev` 2026-09-01: Point / Path / Plane palette primitives with minimal default records; `config.attachmentDefaults` so a Plane exposes no built-in points; Points settle onto Paths, Plane boundaries, Wires, and open interiors through the one Component settle path; 0D grip/ring gesture; compact saved records; Wire as a carrier Path (1D form, carrier role, ends bound or free, end-handle rebind gesture, palette Path drops a free-ended carrier);
   - formal Point / Path / Surface cell/incidence model;
   - boundary operator / subcell vocabulary;
   - generic `Part` as owned addressable subcell/facet;
   - `Wire` becomes a carrier role/configuration of `1D Path` rather than a parallel geometric primitive (semantics landed; storing carriers and Components in one record kind remains, as a file-format transition);
   - parametric `stick_to(path[t])` and relative placement.

2. **Data-driven language — Issue #4**
   - data-backed built-in templates;
   - domain-pack schema;
   - technical shape/SVG grammar;
   - user favorites/custom templates;
   - pack/glyph authoring skills;
   - validators and golden examples.

3. **Logic machine — Issue #6**
   - experimental first slice on `feature/logic-memory-runner`: table-defined Boolean logic and finite memory, ordered events and delays, budgeted stepping, replay-validated `.sovrun`, browser/HTTP/MCP parity; see `LOGIC-RUNTIME.md`. This is not SOV Phase 2 qualification. Remaining: gate-authoring UI, routing pack, richer payload memory and a governed SOV adapter;
   - signal state distinct from moving particle/event;
   - deterministic `(logicalTime, sequence)` scheduler;
   - data-defined combinational gates;
   - delay/repeater and small stateful logic after the combinational baseline;
   - replayable execution receipts and golden truth-table runs.

4. **Space / instruction machine**
   - replace overloaded Canvas thinking with Space as admitted host grammar;
   - constrained subsets of types/materials/topology;
   - agent authoring within an admitted Space;
   - validated diagram → instruction/context projections.

5. **Real 3D, only when earned**
   - XYZ coordinates;
   - camera/orientation/projection;
   - faces/edges/volumes;
   - depth hit-testing and spatial containment;
   - attachment to genuine 3D surfaces.

## NEEDED — product capability space

These are needs to account for, not an implementation sequence:

- approachable human diagram authoring;
- stable and inspectable files;
- constrained agent authorship;
- topology, hosting, materials, color, type, marks, state, lifecycle, logic and time;
- API/MCP parity and receipts;
- migration/provenance/security for packs;
- deterministic validation and replay;
- scalable rendering;
- eventual spatial/3D semantics.

## NEVER — decision-making guardrails

- tool/operation count is not a success metric;
- SVG or color is never the hidden semantic source of truth;
- prompts do not substitute for structural constraints when validation can enforce them;
- do not fork implementations for root/nested/1D-hosted/agent-authored variants of the same primitive;
- do not expose inert configuration;
- do not call something 3D until the runtime has actual 3D semantics;
- do not widen an RC because a future idea is compelling.

## Historical RC issue classification

### RC NOW
- #1 — dimensional/form/history/label correctness
- #2 — Grid visibility authority
- #3 — 0D/Port/attachment-point refactor
- #5 — 1D/2D interaction parity

### AFTER MERGE / NEXT
- #4 — data-driven schematic language/domain packs/agent authoring
- #6 — data-driven logic machine for particle routing
- #7 — Point / Path / Surface cell grammar and `Wire → Path`

These labels record the RC split. Current development follows the baseline and product sequence above; they do not assert current issue status.
