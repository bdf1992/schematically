# Attachment Point Model — 0.1

Port is no longer an independent geometry subsystem. The canonical primitive is a **0D attachment point**.

## Cardinality

Connectivity uses the effective dimension of a Component in its current host surface. Dimension constrains host geometry; it does **not** impose a universal attachment-count maximum:

- 0D → one `self` point.
- 1D → `start` + `end` endpoints.
- 2D → `left` + `right` + `top` as the built-in template defaults; a template may declare additional boundary points by `side + t`.
- A richer Component settled onto a 1D Wire is connectivity-constrained to 1D and therefore exposes only `start` and `end`.

## Contract

Every attachment point owns the same contract: face, direction, access, connection slots, label, and color. Geometry is derived from the host topology.

A 0D Component **is** its attachment point. It does not contain another Port.

## Compatibility

0.1 keeps legacy projections so existing `.sov` documents remain readable:

- `config.ports.in/out/control` stores the authored point contract.
- `parts.ports` is a compatibility projection.
- `parts.points` is the authoritative normalized point projection.
- Wire `aSide/bSide` remain compatibility names while `aAttachment/bAttachment.pointId` stores `start/end/self/left/right/top`.

The compatibility layer is intentionally removable in a future file-format transition.


## Interaction authority

A Wire tap is no longer an authoritative `wire.attachments[]` Port. It is an ordinary **0D Component hosted by the Wire**. Legacy Wire Port/point attachments are migrated into hosted 0D Components during document normalization.

This removes the last intentional event-system distinction between a point on a 1D carrier and a point on a 2D boundary: both use Component attachment descriptors, hit testing, selection, wiring, history, and CRUD. Host dimension changes geometry and exposure surfaces only.
