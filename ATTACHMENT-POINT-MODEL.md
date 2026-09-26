# Attachment Point Model — 0.1

Port is no longer an independent geometry subsystem. The canonical primitive is a **0D attachment point**.

## Cardinality

Connectivity uses the effective dimension of a Component in its current host surface. Dimension constrains host geometry; it does **not** impose a universal attachment-count maximum:

- 0D → one `self` point.
- 1D → `start` + `end` endpoints.
- 2D → the ports its template declares (the typed Component template declares `left` + `right` + `top`), plus any authored boundary points by `side + t`; see *Declared ports*.
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


## Primitives and hosted Points (dev, 2026-09-01)

Point, Path, and Plane are palette primitives. Their symbol ids are `point`, `path`,
and `plane`; the legacy `port` id normalizes to `point` on load.

The 2D built-in set (`left`/`right`/`top`) is a template default, not a minimum.
`config.attachmentDefaults` is `standard` (typed Components) or `none` (a Plane).
With `none` the surface exposes only its data-declared `config.attachmentPoints`
and whatever Points are hosted on it. A Wire cannot end on a surface that exposes
no point; the refusal is the same over UI, API, HTTP, and MCP.

A hosted Point is an ordinary 0D Component whose placement is parametric on its host:

| Host | `placement` | Exposure of its `self` point |
| --- | --- | --- |
| Wire | `{kind: wire, wireId, t}` | inside → the Wire's 1D surface · outside → the Wire's canvas |
| 1D Path Component | `{kind: path, hostId, t}` | inside → the Path's local surface · outside → the Path's canvas |
| 2D Plane boundary | `{kind: edge, hostId, side, t}` | inside → the Plane's interior · outside → the Plane's canvas |
| 2D Plane interior | `{kind: surface}` with `canvasId` = the Plane's interior | ordinary interior membership |

`t` survives host movement and resize; world `x`/`y` are derived. Boundary-hosted
Points do not constrain the host's minimum size. Turning `attachmentDefaults` off
(or retyping a Component to a primitive) is refused while a Wire still ends on a
built-in point, so a carrier is never orphaned silently.

Gesture on a 0D form: the inner grip moves it (drag) or selects it (click); the
outer ring is the wiring target. Both are on the same `.node`; no second event path.


## Wire as carrier Path (dev, 2026-09-01)

A Wire record is a 1D Path (`form.dimension = 1`, `role = 'carrier'`). Its ends are
`aAttachment` / `bAttachment`, each either

- bound: `{kind: 'attachment-ref', componentId, pointId}` with `a` / `aSide` projected, or
- free: `{kind: 'free', x, y}` with `a` / `aSide` null.

The boundary of a carrier is its two end Points; binding identifies an end Point with a
Component's attachment point. The surface a carrier runs on is shared by two bound ends,
adopted from a single bound end (the current surface is kept when that end exposes it),
or the surface it was dropped on when both ends are free. Binding an end whose partner is
bound is refused when the two points share no surface; the refusal is the same over
gesture, API, HTTP, and MCP. A free end carries no signal, no packets, and no channel
marker.

Storage: carriers still live in `document.wires` and Components in `document.components`.
That split is compatibility debt of the same kind as `config.ports` versus `parts.points`;
folding carriers into one record kind is a file-format transition, not a runtime change.


## Declared ports (landed, 2026-09-25)

Decided with the state space design (`STATE-SPACE.md`, *Ports*); the data model landed with contract 0b-1
(issue #45), definition-generated ports with slice 1a, and the ports UI with contract 0b-2 (*The Ports panel*, below).

What is implemented:

- **No hard-coded 2D set.** `06-attachment-core.js` holds no port set. A 2D Component's point specs come from
  declared data only: its template's declared ports, which the data core registers with
  `Attachment.useTemplatePorts`, and its authored `config.attachmentPoints`. 0D (`self`) and 1D (`start`, `end`)
  are unchanged.
- **The trio is template data.** `05-data-core.js` declares `left` (`in`), `right` (`out`) and `top` (`control`),
  each at `t: .5` with flow equal to its compat id, as the typed Component template (`templatePorts(symbolId)`).
  The primitives declare no ports of their own; a Plane's default is `'none'`, and an authored `'standard'` on a
  Plane still means the Component template's ports.
- **Shape.** `{id, compatId?, side: left | right | top | bottom, t: 0..1, flow: in | out | control | duplex |
  trigger, channels: [{id}], label?}`. Absent `channels` reads as `[{id: 'main'}]`. `flow` is the direction;
  an older entry's `defaultFlow` is read only when `flow` is absent.
- **Stored forms keep their meaning.** `'standard'` (explicit or implied) is the template's ports followed by the
  authored `attachmentPoints` as additions; `'none'` is the authored list as the complete set. Loading and
  normalizing never write template ports into the stored array, so every existing file loads, binds and saves
  exactly as before, and `compactDocument` is unchanged.
- **Edits.** A component `create` or `update` that sets `config.attachmentPoints` supplies the complete list
  (under `'none'`) or the additions (under `'standard'`). `setDeclaredPorts` checks it strictly and stores it in
  the smallest form, keeping order: `'standard'` plus additions when the list begins with the template's ports in
  template order and unchanged (same id, compat id, side, t, flow, channels, label), otherwise `'none'` plus the
  full list as given. It refuses a repeated id or compat id, an invalid side, t or flow, and a channel id repeated
  within a port. A refusal is a failed receipt with no history entry and no revision change; browser API, HTTP and
  MCP share this one path.
- **Load cleans, never refuses.** Normalization rewrites each stored `attachmentPoints` list into exactly the
  authored ports the loader exposes (`cleanStoredPorts`): `t` coerced and clamped, an invalid flow read as
  `duplex`, empty channels read as `main`, entries with no valid side dropped. After loading, the stored list
  equals the effective list; files without such lists save exactly as before.
- **Load cleaning never unbinds a Wire on a collision (#46).** When an entry's id or compat id collides with an
  earlier one (`customPointSpecs`), it is normally dropped. `cleanStoredPorts` keeps it instead, under a fresh id
  (`<id>~2`, `<id>~3`, ...: the first not taken), whenever a bound Wire end still refers to it, by the entry's
  original id or by its declared compat id, and that reference is not the id of a surviving port: that end is
  rebound to the fresh id by `pointId`, so it never resolves through a different, colliding entry's compat id
  instead. A reference that names a surviving port stays on that port (a Wire on one of two `a` entries stays
  on the first; #47), so a bound Component's owned ports stay the contract's. A `pointId` names a surviving port by
  its id; a reference stored only as a compatibility side (`aSide`/`bSide`) names one by its id or its compat id, so a
  Wire stored as `in` beside an authored duplicate `in` stays on the template's `left` and no `in~2` is made (0b-2).
  A collision no bound Wire needs is still dropped, as before. This keeps cleaning idempotent: once ids no longer
  collide, nothing further moves.
- **Retype.** `applySymbol` gives the new template's ports in template order, an authored port with the same id
  replacing the template's (keeping its side, t, flow, channels and label), then the remaining authored ports in
  stored order, stored in the smallest form. A Component bound to a definition is not retyped (`DEFINITION_PORTS`):
  its ports are the definition's (#47).
- **A retype never moves a bound Wire to a different port id (#46).** `assertWiresSurviveEdit` refuses a retype
  (`update` changing `symbolId`, or `applySymbol(component, symbolId, doc)`) that leaves a Wire's end resolving to
  a different port id than before, with `PORT_IN_USE`, whenever the retype leaves the effective dimension
  unchanged: for example, a Plane authoring `{id:'in', side:'bottom'}` with a Wire bound to `in`, retyped to a
  typed Component — `in` has no same-id template port, and the Wire would move to `left` by compat id (`in` is
  `left`'s compat id), so the retype is refused. The one kept exception is a change of effective dimension, which
  may still move a bound end by compat id, as reconciliation has always done: retyping a typed Component to a
  Point keeps a Wire on `out` bound to the Point's `self`.
- **Paste and Duplicate** build and check every record against a staged copy of the document before inserting
  any: a refusal inserts nothing and leaves history unchanged; success is one history transition.
- **Wires survive every edit.** `assertWiresSurviveEdit` runs on every component update (port list,
  `attachmentDefaults: 'none'`, retype by `symbolId`), on `applySymbol(component, symbolId, doc)` (the bar retype)
  and on the Form panel switch. It refuses an edit that would remove a port a Wire ends on (`PORT_IN_USE`) or leave
  a Wire between two ports sharing no channel (`CHANNEL_MISMATCH`), so a saved document always validates. When an
  edit changes the effective dimension, a Wire end keeps its port by compat id (`left`/`in` -> `start`), as
  reconciliation has always rebound it.
- **Channels.** `connectionReachability` also requires the two ports to share a channel id
  (`CHANNEL_MISMATCH`), so binding by gesture, `wire.create`, `wire.update`, carrier rebinding and document
  validation all refuse the same way. Ports without declared channels share `main`, so no existing document is
  refused.
- **Form panel.** The attachments control is unchanged: `standard` restores the template's ports, and `none`
  removes them, refused while a Wire ends on one.

- **A Point's `self`.** A component `update` (or `create`) on a Point may set `attachmentPoints` to the single entry
  `{id: 'self', flow?, channels}`, checked like a declared port's channels and flow and stored in the clean form, which
  leaves out a `flow` equal to the default `duplex`; loading cleans the placeholder form the same way, so every form of
  one declaration has one `documentHash`. `CHANNEL_MISMATCH` applies against bound Wires; `self` always stays.

### The Ports panel (landed, contract 0b-2)

A 2D Component's settings panel has a **Ports** section below the Attachments control; it is hidden for 0D and 1D
Components (by effective dimension). It lists every effective port in order, one row each: the id (read-only), label,
side (`left | right | top | bottom`), position `t` (0-1, step 0.05), flow (`in | out | duplex | control | trigger`),
channels (comma-separated ids) and a Remove button. "Add port" appends `p1`, `p2`, ... (the first id free as an id or
compat id) on the right, at the first of .5, .25, .75, .125, .375, .625, .875 no other right-side port uses (else
.5), duplex, on `main`; it is drawn at once and is immediately wireable.

- **One path.** Every edit sends the Component's complete port list, with `attachmentDefaults: none`, through the data
  core's component `update`, which stores it in the smallest form and applies every refusal. One edit is one history
  transition. A refusal (`t` outside 0-1, an empty or repeated channel list, `PORT_IN_USE` for removing a port a Wire
  ends on, `CHANNEL_MISMATCH`) changes nothing, the rows are rebuilt from the record so the edited row reverts, and
  the refusal is the status line. A label edit also writes the port contract's label (`config.ports[compatId].label`,
  the label the canvas draws) in the same update.
- **Moving a port** happens only here (side, `t`): dragging a port starts a Wire.
- **Definition-owned ports.** On a Component with `config.definition`, the id, flow, channels and Remove controls are
  disabled with a title naming the definition, and "Add port" is disabled; label, side and `t` stay editable.
- **Guarded gestures.** One hosting guard, `componentHostRefusal` in `30-canvas.js`, is checked by
  `applyComponentHost` (the one place a Component's host changes) before anything is applied. It asks the data core's
  owned-port rule (`assertDefinitionPortsKept`), so settling a bound Component on a Wire, a Path or a Plane boundary,
  or any host that would change the ports it exposes, is refused with `DEFINITION_PORTS` in the status line, by a
  pointer drag or an arrow-key move alike, and every Component the gesture moved returns to where it was, with no
  history entry. A pointer drag asks the same guard for every root before applying any, so one refusal refuses the
  whole group. Settling into an open interior stays allowed. The Form panel's dimension and Attachments controls ask
  the same owned-port rule; the bar retype was already refused (`applySymbol`).

Still planned: a Wire carrying several channels at run time, and the channel-merge editor.
