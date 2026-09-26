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
- **Form panel.** The attachments control reads "Template ports" (`standard`: the template's ports, then any
  additions) and "Custom ports" (`none`: the authored list is the complete set). Choosing "Template ports" where the
  ports differ from the template's resets them and says so ("Reset to template ports"); "Custom ports" is refused
  while a Wire ends on a template port.

- **A Point's `self`.** A component `update` (or `create`) on a Point may set `attachmentPoints` to the single entry
  `{id: 'self', flow?, channels}`, checked like a declared port's channels and flow and stored in the clean form, which
  leaves out a `flow` equal to the default `duplex`; loading cleans the placeholder form the same way, so every form of
  one declaration has one `documentHash`. `CHANNEL_MISMATCH` applies against bound Wires; `self` always stays.

### The Ports panel (landed, contract 0b-2)

A 2D Component's settings panel has a **Ports** section below the Attachments control; it is hidden for 0D and 1D
Components (by effective dimension). It lists every effective port in order, one row each: the id (read-only), label,
side (`left | right | top | bottom`), position `t` (0-1, step 0.05), flow (`in | out | duplex | control | trigger`),
channels (comma-separated ids) and a Remove button. "Add port" appends `p1`, `p2`, ... (the first id free as an id or
compat id) on the right, at the first of .5, .25, .75, .125, .375, .625, .875 no other right-side port uses, and once
those are used at the midpoint of the largest free gap on that side (between its ports and the ends 0 and 1; ties to
the lowest t), so added ports never stack; duplex, on `main`; it is drawn at once and is immediately wireable.

An edit is never pending. Its target (the row's Component and port) is bound when its `change` fires, and its data
change and history transition happen inside that event; a pointerdown anywhere else first blurs a focused port field,
in the capture phase, so the edit commits before the click can change the selection, start a drag, undo, save or
delete. Only the refresh (the canvas render, the panel or bar rebuild, focus) waits until the event is over; it
changes neither data nor history, so Tab and Shift+Tab move through a row as usual while each edit rebuilds the rows.
If the bound Component no longer exists, the edit is dropped and the status line says so. A component `update` keeps
the record's identity, so a gesture that began on it keeps holding the updated record.

- **One path.** Every edit sends the Component's complete port list, with `attachmentDefaults: none`, through the data
  core's component `update`, which stores it in the smallest form and applies every refusal. One edit is one history
  transition. A refusal (`t` outside 0-1, an empty or repeated channel list, `PORT_IN_USE` for removing a port a Wire
  ends on, `CHANNEL_MISMATCH`) changes nothing, the rows are rebuilt from the record so the edited row reverts, and
  the refusal is the status line.
- **One label.** A port's label is one value. The panel's label field and the port bar's label both write the declared
  `label` and the drawn label (`config.ports[compatId].label`) together in one update, and both show the drawn label.
  A Point's `self` and a 1D endpoint declare no label; for them only the drawn label is written. The bar's label
  binds its port when editing starts and commits once, when it is left by Tab, Enter or a click elsewhere (committed
  in the click's capture phase, before the click does anything else).
- **One flow.** A port's direction is its declared `flow`. The panel's flow and the port bar's Direction (which offers
  `trigger`) both write it through the data core, with the contract's drawn flow (its active connection's) mirrored in
  the same update (`trigger` is drawn as `control`), and both show it, as does the inspector's Direction line. A port
  that declares no flow shows its default: `duplex` for a Point's `self`, as `checkDocument` and the runtime read it. A Component with no declared list stores the
  list in the smallest form, as any port edit does; a Point's bar change sets its `self` declaration. A Path end's
  direction is its role (`start` receives, `end` emits): the bar and the inspector show that effective flow, and the
  bar's Direction is disabled there, with a title saying so.
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
- **Children fall back through the same guard.** When a Component stops hosting (its interior closes, it is retyped
  or changes dimension, or it is deleted), the Components on its interior fall back to its own canvas.
  `componentFallbackPlan` in `30-canvas.js` decides that before the edit, `componentHostPlanRefusal` checks every
  child with the hosting guard, and `applyComponentHostPlan` applies it through `applyComponentHost`. One refused
  child refuses the whole edit: nothing changes, `DEFINITION_PORTS` is the status line, and no history entry is left.
  For example, a bound Component inside an open Component that sits on a Wire would otherwise fall onto the Wire's
  canvas and expose `start`/`end`. Deleting such a host is refused by the data core too (`remove`), so the API, HTTP
  and MCP refuse it the same way.

Still planned: a Wire carrying several channels at run time, and the channel-merge editor.
## Points anywhere on the perimeter (dev, 2026-09-25)

A 2D card's own boundary points (the built-in `left`/`right`/`top`, and data-declared
`config.attachmentPoints`) are no longer fixed to their default side.
`config.ports.<compatId>.boundary = {side, t}` places one anywhere on the perimeter.
- `side` is `left`, `right`, `top` or `bottom`.
- `t` runs along that side, from 0 to 1.

The attachment core (`pointSpecs`) applies the placement and marks the spec `placed`. So
routing, reachability, rendering, the data core and the graph engine all read one
position.

- **Gesture:** Alt-drag a point to slide it round the card, corners included. It uses the
  same edge resolver that hosts a free Point on a boundary. It snaps to eighths of a side;
  holding Shift as well places it freely. One gesture is one history step. A pinned or
  locked card refuses.
- **Agent path:** a CRUD patch such as
  `{config: {ports: {out: {boundary: {side: 'bottom', t: .25}}}}}`. It is the same over
  the Browser API, HTTP and MCP, with the same receipts and lock refusals. Patching
  `boundary: null` returns the point to its default.

## Seamless terminals (dev, 2026-09-25)

- A point sits **on** the boundary, never standing off it, so a wire meets the body edge
  with no gap. The face (internal / external / both) is shown by the point's style.
- A card's symbol axis is its centre line: the glyph is positioned so its terminal axis
  (`INLINE_TERMINAL_Y`) lands at mid-height. An unplaced side point therefore sits on the
  axis for every symbol, and cards aligned by centre are joined by straight wires.
- A wired side point on the axis draws an inner lead from the body edge to the symbol's
  own lead (`.component-lead`). Wire, edge and glyph read as one line.
- A placed point is off the axis and draws no lead.
