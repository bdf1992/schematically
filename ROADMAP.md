# Schematically roadmap boundary

This file answers one question: **what belongs in the current RC, and what starts only after the RC merges?**

`RC-FINISH-LINE.md` is authoritative for release acceptance. `docs/vision/` and NEXT issues preserve post-RC direction without widening the release candidate.

## NOW — `rc/0.1.0-rc1`

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

## MERGE GATE

The RC merges only when:

1. `RC-FINISH-LINE.md` is satisfied;
2. repository CI reproduces the candidate being manually tested;
3. no known blocker remains open without an explicit acceptance decision;
4. the RC PR contains the exact runtime, docs, schemas, examples, skills, and tests used for acceptance.

Merging the RC means **the 0.1 primitive foundation is accepted**, not that Beta is finished or bug-free.

## AFTER RC MERGE — `dev`

Create `dev` from the newly merged `main`. Do **not** create post-RC implementation branches from the pre-merge RC candidate; this avoids carrying a speculative fork across release settlement.

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
   - landed on `dev` 2026-09-01: Point / Path / Plane palette primitives with minimal default records; `config.attachmentDefaults` so a Plane exposes no built-in points; Points settle onto Paths, Plane boundaries, Wires, and open interiors through the one Component settle path; 0D grip/ring gesture; compact saved records;
   - formal Point / Path / Surface cell/incidence model;
   - boundary operator / subcell vocabulary;
   - generic `Part` as owned addressable subcell/facet;
   - `Wire` becomes a carrier role/configuration of `1D Path` rather than a parallel geometric primitive;
   - parametric `stick_to(path[t])` and relative placement.

2. **Data-driven language — Issue #4**
   - data-backed built-in templates;
   - domain-pack schema;
   - technical shape/SVG grammar;
   - user favorites/custom templates;
   - pack/glyph authoring skills;
   - validators and golden examples.

3. **Logic machine — Issue #6**
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

## Issue classification

### RC NOW
- #1 — dimensional/form/history/label correctness
- #2 — Grid visibility authority
- #3 — 0D/Port/attachment-point refactor
- #5 — 1D/2D interaction parity

### AFTER MERGE / NEXT
- #4 — data-driven schematic language/domain packs/agent authoring
- #6 — data-driven logic machine for particle routing
- #7 — Point / Path / Surface cell grammar and `Wire → Path`

Post-RC issues may refine the horizon now, but implementation begins from `dev` after the accepted RC is merged.
