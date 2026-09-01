# SOV Schematic Author Skill — 0.1

## Purpose

Create or edit `.sov` schematics without bypassing the schematic model. Terms follow `GLOSSARY.md`.

## Operating rule

Prefer the browser API, REST API, or MCP tools over direct mutation of runtime arrays. A diagram is not merely SVG: Components, Wires, Forms, Ports, containment, editor states, and history have semantic meaning.

## Core primitives

- **Component** — a closed boundary with behavior/content and a Form.
- **Form** — dimension + Body + Frame + addressable Regions.
- **Part** — an owned/addressable section of a line or boundary.
- **Port** — a Part exposed to one or more surfaces. Port face controls boundary reachability.
- **Wire** — an open 1D carrier connecting two Ports that share an exposed surface.
- **Direction ≠ access ≠ authority** — a Port's direction and access are independent axes. Access constrains which Read/Write packet operations a Wire can represent; it never grants authority.
- **Hosting/settle** — a Component becomes contained by settling into an open interior Region. It remains the same Component implementation.

## Boundary invariant

Never create implicit reach-through across a containing Component.

A child may connect to siblings and Ports exposed to its containing surface. To cross the parent boundary, use an inside-facing or both-facing Port on the parent.

## Editing behavior

- Use history-aware semantic actions where available.
- Pin means geometry fixed; Lock means immutable.
- Hidden is recoverable projection state, not deletion.
- Opacity is presentation only.
- Checkpoints are named versions persisted in `.sov`; undo/redo are session history.
- A copied Component subtree carries only Wires whose two endpoints are inside the copied subtree.

## Authoring sequence

1. Establish Components and their Forms.
2. Open only the interior Regions that should host children.
3. Set Port faces/directions before crossing boundaries.
4. Connect legal Ports with Wires.
5. Set signal/rate behavior only after topology is valid.
6. Save a checkpoint at meaningful milestones.
7. Validate the document before export/share.

## Refusals

Refuse or repair:
- Wire endpoints on surfaces that do not intersect.
- Mutation of locked entities.
- geometry movement of pinned entities.
- nested-only Component logic.
- direct edits that create state not representable by `document@0.1`.
