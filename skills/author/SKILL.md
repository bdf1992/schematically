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
- **Wire** — a carrier Path: a 1-D form whose ends are each bound to a Port (`a`/`aSide`, `b`/`bSide`) or free (`aAttachment: {kind:'free',x,y}`). Two bound ends must share an exposed surface. Create a free-ended carrier with `wire.create` using free attachments; bind or free an end later with `wire.update`.
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
7. Validate, inspect the normal editor and exported SVG in both appearances, then save and reopen. Structural validation alone is not visual QA.

## Layout and review

List topology before layout: participant/service roles, typed Components, exposed ports, parent/surface membership and each wire endpoint. Proposed architecture describes contracts and authority; it does not prove runtime enforcement or external-effect guarantees.

Dimension admission belongs to `05-data-core.js`: presentation width/height default to 112/84, normalize to minima 80/64, and have no browser-only maximum. Plane presets default to 320/220; Points keep a 24-unit footprint. Size hosts from full child extents, boundary points, labels and routing lanes. Rendering must preserve admitted geometry.

Reserve a main request lane, a separate control/feedback lane, title clearance and space on both sides of each crossing. Start with about 200 units between ordinary component centres and 100 units between a crossing and a child edge, then inspect. These are starting clearances, not model limits. Do not change topology to shorten routes. Use brief labels with explanations in `meta.description`, References or the inspector. At 768px and 1440px review an overview, then use zoom/pan or double-click an Objects entry to focus it when needed. Record which views were inspected.

Use a small stable palette and pair it with text or shape. For the default spectrum palette, one useful mapping is C5 (slot 10) requests/actions, C6 (11) authority/control, C4 (9) observations/evidence, C1 (6) refusal/protection; M1 (0) keeps hosts restrained. These roles are chosen by the author, not executable permissions.

`config.colorSlot` colors the Component boundary; `config.presentation.interiorColorSlot` colors its interior separately. Wire colors come from the selected endpoint `config.ports.<id>.connections[index].colorSlot`; author both ends deliberately. A legacy wire `config.colorSlot` migrates once into the A-side connection and is removed. Realized hex colors are derived, not the palette authority. Inspect both themes and standalone export.

Audit ports against the endpoint list before reducing clutter. A bare Plane exposes no built-in points; typed Components have their template contracts. An unused quiet port remains an affordance. Keep connected ports and explicit crossings; use supported attachment descriptors for a different interface. Never delete an endpoint to hide it.

After layout review, pin settled hosts and reference components through Settings → Pin; leave drafts movable. Pin freezes direct geometry gestures; Lock freezes semantic mutation. Existing parent movement carries descendants, including pinned children: pin the ancestor too when the structure must stay in place. Objects marks pinned entries; Settings → Pin also unpins, and Undo reverses it. Exercise gestures and save/reopen, not only the flag.

Custom SVG lives in `config.presentation.graphic: {kind:'custom', svg:'<svg …>'}`. Keep `symbolId` and real ports authoritative. Use a valid viewBox, margin inside the bounds, simple portable shapes and `currentColor`; the renderer sanitizes supported SVG and preserves aspect ratio in the graphic box. Inspect the selected node, thumbnail when applicable, `.sov`, `.sovpak` and standalone SVG. Keep labels and ports separate. `examples/09-proposed-service-review.sov` demonstrates team/history graphics without external assets.

If browser access or source fixtures are missing, name the missing evidence instead of declaring appearance verified. Compare wrapper CSS separately from the normal editor.

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
