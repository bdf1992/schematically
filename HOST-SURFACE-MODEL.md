# Host Surface Model — 0.1

A Component is not a box. It is a semantic entity that can be projected on different host surfaces.

**Host determines placement dimension. Form determines geometry. Presentation determines backdrop.**

- Root or Component interior: `placement = {kind: surface, x, y}`.
- Wire: `placement = {kind: wire, wireId, t}` where `t` is normalized along the 1D path.
- `parentId` is only a compatibility projection for Component-on-Component hosting.

The same drag/settle resolver chooses an open Component interior first, otherwise a nearby Wire, otherwise the world. A Wire-hosted Component uses the normal Component record, normal selection/settings/history/CRUD, and `backdrop:auto` projects it without a box.

`presentation.backdrop`: `auto | none | body | frame`.

Placement/projection is structural. It does not infer packet-processing semantics solely from being visually inline; those semantics must remain explicit.


## Inline anchoring

A Component settled onto a Wire is projected from the Wire's local geometry rather than merely positioned nearby:

- placement authority remains `wireId + t`;
- world `x/y` and angle are derived from the host Wire path;
- the Component rotates to the local Wire tangent;
- built-in inline symbols align their declared terminal axis to the host carrier;
- the host Wire is visually cut only between the Component's terminal endpoints, so the Wire and symbol meet with zero gap;
- the same settle dwell/ghost mechanism is used for 1-D Wire hosts and 2-D Component hosts.

The derived pose is runtime projection and is not additional persisted truth.
