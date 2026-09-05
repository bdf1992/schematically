# 0D / Attachment Concern Audit — Beta.24

## Result

The editor now treats **Port as a compatibility/UI name for the canonical 0D attachment-point primitive**.

### Authoritative concern

`src/06-attachment-core.js` owns only pure topology and compatibility mapping:

- intrinsic form dimension,
- host dimension,
- effective connectivity dimension,
- canonical 0D point identities,
- compatibility IDs for 0.1 files,
- owned Wire point normalization,
- Wire endpoint reference normalization.

It has no DOM, routing, rendering, selection, or editor authority.

## Canonical dimensional topology

| Effective dimension | Canonical 0D points | 0.1 compatibility names |
| --- | --- | --- |
| 0D | `self` | `out` |
| 1D | `start`, `end` | `in`, `out` |
| 2D | built-in `left`, `right`, `top` + optional data-declared boundary points | `in`, `out`, `control` + declared compatibility IDs |

A richer form settled onto a lower-dimensional host projects connectivity to that host. In particular, a 2D Component placed inline on a Wire exposes only `start` and `end`.

## Debt removed

- Port cardinality no longer has independent truth in render code.
- Port geometry no longer has independent truth in the settings UI.
- A 0D Component no longer conceptually contains another Port; it is the attachment point.
- 1D inline Components no longer inherit an accidental 2D top/control Port.
- Component rendering consumes attachment descriptors.
- hit testing and wiring consume the same canonical point IDs.
- connection legality resolves new point IDs and old Port IDs through one compatibility map.
- Wire-owned taps normalize to the same `attachment-point` kind instead of maintaining another Port-shaped record.
- Wire endpoint references now preserve canonical point IDs (`aAttachment` / `bAttachment`) while old `aSide` / `bSide` remain projections.

## Compatibility debt intentionally retained for 0.1

The following fields remain so existing `.sov` files and the MCP/API surface do not break during the RC:

- `component.config.ports.in/out/control`
- `component.parts.ports`
- `wire.aSide` / `wire.bSide`
- UI function names containing `Port`

New normalized runtime truth is:

- `component.parts.points`
- `wire.aAttachment.pointId` / `wire.bAttachment.pointId`
- canonical identities `self/start/end/left/right/top`

A later file-format revision can delete the compatibility projections after an explicit migration boundary.

## Defects caught by the refactor

The regression suite exposed a route-collapse bug where legacy `aSide/bSide` values were passed directly into geometry keyed by canonical point IDs. `portPos()` now resolves both forms through the attachment core before reading geometry.

## Remaining risks

- Wire endpoint selection is still mostly projected through the bound Component point rather than a fully independent Wire-endpoint selection surface.
- Port wording remains in parts of the UI for user familiarity during Beta.
- Full cell/facet grammar is post-RC, but the 0.1 core already permits data-declared extra 2D boundary points (`side + t`) so the built-in three-point template cannot become a hard maximum.


## Beta.24 debt removal

- Removed new creation of Wire-owned Port/tap records.
- `+ Port` now creates a hosted 0D Component.
- Legacy Wire point attachments migrate to hosted 0D Components.
- Host-aware exposure maps a point on a Wire to the Wire's inner 1D surface and its outer containing surface.
- The ordinary Component gesture path is now authoritative for Wire taps as well as 2D boundary points.

Remaining compatibility debt: legacy `wire.attachments[]` point records are accepted as migration input, and the legacy Wire-port UI branch remains defensive compatibility code only.


## Beta.24 active-path audit

After migration became authoritative, the remaining Wire-owned point UI/render branches were removed from active code. The editor now has one attachment interaction path: Component-owned canonical 0D points. `wire.attachments[]` point handling remains only in the transport migration adapter in `05-data-core.js`; it is not rendered, selectable, editable, or created by current UI/API operations.
