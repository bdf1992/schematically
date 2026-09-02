# SOV Schematic Author Skill — 0.1

## Purpose

Create or edit `.sov` schematics without bypassing the schematic model.

## Operating rule

Prefer the browser API, REST API, or MCP tools over direct mutation of runtime arrays. A diagram is not merely SVG: Components, Wires, Forms, Ports, containment, editor states, and history have semantic meaning.

## Core primitives

- **Point / Path / Plane** — the dimensional basis (`symbolId: point | path | plane`). A Point is an attachment; drop or create it with `placement` on a Path (`{kind:'path',hostId,t}`), a Plane boundary (`{kind:'edge',hostId,side,t}`), or a Wire (`{kind:'wire',wireId,t}`). A Plane exposes no built-in points (`config.attachmentDefaults:'none'`); wire to the Points hosted on it.
- **Component** — a typed Plane: a closed boundary with behavior/content and a Form. Typed Components keep the template defaults `in`/`out`/`control`.
- **Form** — dimension + Body + Frame + addressable Regions.
- **Part** — an owned/addressable section of a line or boundary.
- **Port** — a Part exposed to one or more surfaces. Port face controls boundary reachability.
- **Wire** — an open 1-D carrier/path connecting Ports that share an exposed surface.
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

1. Establish Components and their Forms. For a bare region, create a Plane and host Points on its boundary where crossings are needed.
2. Open only the interior Regions that should host children.
3. Set Port faces/directions before crossing boundaries. A boundary-hosted Point with face `both` is the explicit crossing.
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
- direct edits that create state not representable by `document@0.1`;
- Wires ending on a surface that exposes no point (a Plane with no hosted Points), or removing built-in points while a Wire still ends on one.


## Read/write axis
Treat direction, access, and authority as separate. `direction ≠ access ≠ authority`. A Port access value constrains representable Read/Write packet operations; it does not grant authority.
