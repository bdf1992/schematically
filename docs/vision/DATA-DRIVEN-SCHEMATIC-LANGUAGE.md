# Post-RC vision: data-driven schematic language

> **Non-authoritative horizon.** This document records product direction after the current RC. It does not widen 0.1 acceptance criteria. See `../acceptance/RC-FINISH-LINE.md` and `ROADMAP.md` for the release boundary; see Issue #4 for the root agenda.

## Thesis

Schematically should become a data-driven technical language whose easiest human projection happens to look like a diagram.

A single validated model should be able to carry:

- statics — what exists;
- topology — what connects, contains, hosts, crosses, or touches;
- semantics — what entities and relations mean;
- dynamics — what moves, propagates, reads, writes, transforms, or triggers;
- lifecycle/state — what can change and which transitions are valid;
- logic/constraints — what is permitted, required, conditional, or refused;
- projection — how the model is rendered for a person;
- instruction compilation — how the same model becomes bounded context for an agent/runtime.

The interaction goal remains as approachable as a normal diagram or a small structured data file.

## Small kernel, large data surface

Prefer a compact runtime kernel plus validated packs/drivers over hundreds of domain-specific operations.

The kernel should know general primitives such as:

```text
Space
Point / 0D
Path / 1D
Surface / 2D
Attachment
Carrier
Component
Part
Mark
Material
Channel
Packet
State
Transition
Rule
Constraint
Host
Placement
Projection
```

It should not need intrinsic code for every domain object such as router, database, motor, invoice, witness, printer, firewall, or pump.

A target heuristic is that a large majority of expressive vocabulary — roughly 75% as a design direction, not a release metric — can be supplied as validated data.

## Post-RC topology direction

The first structural generalization after RC should formalize Point / Path / Surface as a cell/incidence grammar rather than extend the current Beta's default attachment-count templates.

Key direction:

```text
∂(Point)   = none
∂(Path)    = endpoint Points
∂(Surface) = boundary Paths
```

`Part` becomes an owned addressable subcell/facet; a Point may attach parametrically to a Path at `t ∈ [0,1]`; and `Wire` becomes a carrier/conductive role of a generic `1D Path` rather than a parallel geometric primitive.

This is **after RC merge**. The current RC only needs attachment descriptors and host-independent interactions clean enough that this can be introduced without another renderer/event-system fork.

## Domain packs

A domain pack may eventually provide:

```text
pack/
├─ manifest
├─ grammar/
│  ├─ component templates
│  ├─ parts / attachment points
│  ├─ carriers / paths
│  ├─ marks
│  ├─ materials
│  ├─ topology rules
│  └─ state / transition rules
├─ glyphs/
│  └─ SVG primitives
├─ palettes/
├─ validators/
├─ examples/
├─ prompt projections/
└─ skills/
```

A new domain should primarily require publishing definitions, glyphs, validation, examples, and pedagogy rather than adding new core runtime paths.

## Technical shape language

Research proven visual traditions and derive a constrained common grammar rather than a universal icon vocabulary.

Useful source traditions include circuit schematics, mechanical/architectural blueprints, block diagrams, statecharts, Petri nets, dataflow diagrams, process diagrams, and technical drawing conventions.

Candidate common grammar:

```text
0D Point     → attachment / terminal / junction / anchor
1D Path      → carrier / relation / trajectory / boundary segment
2D Surface   → body / region / boundary / plane
future Space → host coordinate volume when real XYZ semantics exist

shape/form   → structural kind
boundary     → separation / interface
path         → relation or carrier
mark         → qualifier / state / control / evidence
color slot   → class/channel/material realization; never sole semantic truth
packet       → moving operation/state
group/host   → composition
text         → authored label/reference; not hidden semantic authority
```

The SVG is a projection of semantic data, not the source of truth.

## Agent-authored packs and user vocabulary

Skills should eventually teach agents to:

1. inspect the admitted grammar;
2. research a domain's established notation and conventions;
3. map the domain to Schematically primitives;
4. author SVG glyphs from the technical shape language;
5. define templates, materials, attachment rules, semantics, and validation;
6. create golden examples;
7. validate human readability and machine structure;
8. publish or install the pack without modifying core runtime code.

Users should be able to maintain favorites/custom templates through the same data path.

## Space

The eventual root host abstraction is **Space**, replacing the overloaded historical Canvas concept.

A Space defines coordinates, admitted grammar, available materials/types, constraints, and contents. A Space may intentionally expose only part of the global grammar.

Example:

```text
Space: Evidence Review

Allowed
- Observe
- Receipt
- Read / Write
- 0D attachments
- 1D carriers
- selected 2D surfaces

Disallowed
- arbitrary transforms
- arbitrary writes
- unapproved templates/materials
```

An agent operating in a partially configured Space should be structurally unable to author outside that admitted vocabulary rather than merely being prompted not to.

## Prompt / instruction machine

A validated schematic can become bounded agent context:

```text
Space + packs + schematic + task
            ↓
validated semantic graph
            ↓
role/task projection
            ↓
agent instruction/context packet
```

Possible projections include concise natural language, JSON/JSONL, role-specific neighborhoods, allowed operations, runtime constraints, tests, and evidence/read/write boundaries.

The diagram remains the approachable authoring surface; the compiled projection becomes the operational surface.

## Logic/runtime proof

Issue #6 records a first post-RC runtime proof: a small data-driven logic machine over the same Point / Path / Surface topology.

The important split is:

```text
signal state     = current value at an attachment/channel
particle/event   = transition/pulse propagating through topology
```

The runtime should support deterministic combinational logic first, then delays and small stateful logic, while preserving replayable receipts and editor/API/MCP parity.

## Proof strategy

Do not prove the architecture by building dozens of domains. Prove that the second and third domains are dramatically cheaper than the first.

A strong demonstration would:

1. define a Space admitting only a subset of grammar;
2. install a small domain pack;
3. ask an agent to model a requirement from natural language;
4. require the agent to use only admitted entities/relations;
5. validate the resulting document;
6. render it clearly for a human;
7. compile it into bounded agent instructions;
8. run structural/dynamic golden tests.

The architecture is succeeding when a useful unfamiliar domain can be added mainly through a validated pack + skills + examples rather than new core operations.

## Roadmap classification

### Now
Current RC commitments are defined only by `../acceptance/RC-FINISH-LINE.md` and summarized in `ROADMAP.md`.

### Next
After RC merge: topology/cell-incidence grammar, `Wire → Path` semantic collapse, technical-shape research, first domain-pack schema, data-backed built-ins, pack/glyph authoring skills, user favorites, the small logic machine, constrained Space admission, agent authoring benchmarks, and instruction compilation.

### Needed
Human usability, agent discoverability and constrained agency, topology/hosting/dimensions/materials, attachment and channel semantics, lifecycle/time/rules, migrations, deterministic files, CI/golden corpora, provenance/security, and eventually real 3D spatial semantics.

### Never
Do not optimize for tool count; do not add bespoke runtime code when validated data suffices; do not let SVG/color become semantic truth; do not fork root/nested/Path-hosted implementations; do not expose inert settings; do not fake 3D; do not substitute prompts for enforceable constraints; do not let post-RC ambition widen current RC acceptance.
