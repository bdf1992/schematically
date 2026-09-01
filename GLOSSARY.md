# Glossary — 0.1

One term per concept. Human-facing prose (README, model docs, skills, in-app copy) uses the bold term. *Machine* gives the identifier, field, or enum value the code and schemas use; those are exact and do not change with wording. *See* names the document that owns the concept; other documents point there instead of restating it.

## Names

- **SOV Schematic** — the product. `schematically` is the repository. `soveraeign.schematic/*` is the schema namespace (for example `soveraeign.schematic/document@0.1`). `SovSchematicAPI` is the browser API object.
- **0.1** — the format and contract line. **Beta.24** is the build shown in the editor header. `rc/0.1.0-rc1` is the release branch.

## Sentence

**Parts compose. Components contain. Wires connect.** (`reference/REFERENCE.md`)

## Model

- **Component** — a closed boundary with behavior, content, and a Form. Nested Components use the same implementation as root Components. Machine: resource `component`; `symbolId` selects its template. See `README.md`, `reference/REFERENCE.md`.
- **Form** — the dimensional structure of a Component: dimension + Body + Frame + Regions. Machine: `form.dimension`, `form.body.{kind, material, thickness}`, `form.frame.{mode: none | frame | shell, thickness, depth}`, `form.regions.interior.state: closed | open`. See `FORM-MODEL.md`.
- **Dimension** — 0D Point, 1D Path, or 2D Surface. 3D Volume is reserved; the normalizer clamps anything else to 2. Machine: `form.dimension: 0 | 1 | 2`. See `FORM-MODEL.md`, `HORIZON-SPACE.md`.
- **Interior** — the Region inside a 2D Component. `open` means it hosts Components. Machine: `form.regions.interior.state`. See `FORM-MODEL.md`.
- **Part** — an owned, addressable section of a boundary or path. The post-RC cell grammar generalizes it. See `reference/REFERENCE.md`, `docs/vision/TOPOLOGY-CELL-GRAMMAR.md`.
- **Port** — a 0D attachment point: the only place a Wire can attach. A Port lives on a Component boundary, at the ends of a 1D Component, or on a Wire (as a 0D Component hosted by that Wire). Every Port has the same contract: face, direction, access, connection slots, label, color. Machine: authored in `config.ports.{in, out, control}` and `config.attachmentPoints[]`; normalized to `parts.points`; built-in ids `self`, `start`, `end`, `left`, `right`, `top`; Wire endpoints reference it by `aAttachment.pointId` / `bAttachment.pointId` (`aSide` / `bSide` are compatibility names). See `ATTACHMENT-POINT-MODEL.md`.
- **Attachment point** — the implementation name for Port. Use it only for the concern (`src/06-attachment-core.js`) and the records above. See `ATTACHMENT-POINT-MODEL.md`.
- **Face** — which side of its Component's boundary a Port is exposed to: Outside (the containing surface), Inside (the Component's own interior), or Both. Machine: `face: external | internal | both`. See `CANVAS-MODEL.md`.
- **Direction** (Port) — how a signal crosses at this Port: Input, Output, Input + Output, or Trigger. Machine: connection slot `flow: in | out | duplex | control`. See `reference/REFERENCE.md`.
- **Access** — what a Port can represent: None, Read, Write, or Read + Write. Never a permission. Machine: connection slot `access: none | read | write | read-write`. See `DATA-FORMATS.md`.
- **Connection slot** — one of a Port's channel entries; it holds `flow`, `access`, and a color slot. A connection slot is not a Wire. Machine: `connections[]`, `activeConnection`, `connectionCount` in `src/10-model.js`.
- **Wire** — an open 1D carrier joining two Ports that share a surface. A Wire can host Components inline. Machine: resource `wire`; endpoints `a` / `b`; `config.direction: none | forward | reverse | duplex`; `wire.duplex` is derived. See `README.md`, `CANVAS-MODEL.md`.
- **Operation** (packet) — what a packet on a Wire does in each direction: Signal, Read, or Write. Machine: `config.forwardOperation` / `config.reverseOperation: none | read | write` (`none` is shown as Signal). See `DATA-FORMATS.md`.
- **Return rule** — whether a Wire expects traffic back: No return rule, Return expected, or Return required. Shown as "Return" in the editor; called reciprocity in code. Machine: `config.reciprocity: none | expected | required`.
- **Authority** — permission. It is never inferred from direction, access, or operation; only an explicit Authority Component supplies it as a control input. See `reference/REFERENCE.md`.
- **Signal mode** — how a Component originates packets: Source (active without input), On input (relays what it receives), or Passive. Machine: `config.signalMode: source | relay | passive`. See `reference/REFERENCE.md`.
- **Packet** — the moving token drawn on a Wire. Its skin is the identity of the source Port. See `reference/REFERENCE.md`.
- **Channel marker** — the short text and color a Wire shows at an endpoint, taken from the connection slot it is bound to. Machine: `outMarker` / `inMarker`, `colorSlot`.
- **Rate** — packet travel speed: global time scale × source Component rate × Wire rate. Machine: `document.meta.timeScale`, `editor.rate`. See `EDITOR-KERNEL.md`.
- **Reference** — a labelled record with no geometry that other entities can point to. Machine: resource `reference` with `{id, kind, label, target, data}`. See `API.md`.
- **Template** — a Component type from the palette (Act, Hold, Buffer, Gate, Switch, Limit, and the rest). Templates are data. Machine: `symbolId`; the catalog is `SYMBOLS` in `src/00-state.js`.
- **Mark** — in 0.1, the glyph conventions used to read a drawing (→ flow, ○ terminal, ● join, ◇ conditional, ┃ stop). Post-RC, a modeled entity that can attach to any cell. See the in-app help and `docs/vision/TOPOLOGY-CELL-GRAMMAR.md`.

## Surfaces and hosting

- **Surface** — where a Component lives and what a Port is exposed to: the root surface, a Component's open interior, or a Wire. Machine: `canvasId` with values `canvas:global`, `canvas:component:<id>`, `canvas:wire:<id>`. See `CANVAS-MODEL.md`.
- **Canvas** — the 0.1 machine name for surface. It is a model property, not a UI mode. Post-RC, the root concept becomes Space. See `CANVAS-MODEL.md`, `HORIZON-SPACE.md`.
- **Host / hosting / contained** — the relationship between a Component and the surface it lives on. Hosting changes relationship and scope, not implementation. Machine: `placement: {kind: surface, x, y}` or `{kind: wire, wireId, t}`; `parentId` is a compatibility projection. See `HOST-SURFACE-MODEL.md`.
- **Settle** — releasing a drag so that hosting takes effect, after a short dwell that shows a ghost of the prospective host. See `EDITOR-KERNEL.md`, `HOST-SURFACE-MODEL.md`.
- **Boundary / reach-through** — a Component boundary is real. A child can wire only to siblings and to Ports exposed to its own surface; crossing the parent boundary requires a parent Port whose face is Inside or Both. "Reach-through" is the forbidden shortcut. Machine: reachability in `src/05-data-core.js`; a refused write says `Boundary blocks …`. See `CANVAS-MODEL.md`, `AGENTS.md`.
- **Legality** — whether a mutation satisfies the model's rules (boundary reachability, Lock, Pin). Every entry point (UI, browser API, HTTP, MCP) applies the same rules. Machine: a receipt with `ok: false`. See `AGENTS.md`, `DATA-FORMATS.md`.
- **Agent surface** — one of the ways to reach the data core: browser API, HTTP, or MCP. This is a different sense of "surface" from the model term above; prose says "agent surface" or "entry point" when the distinction matters.
- **Space** — post-RC replacement for the root Canvas: a coordinate domain with an admitted grammar. Not part of 0.1. See `HORIZON-SPACE.md`.
- **Path** — post-RC, the generic 1D cell; Wire becomes a carrier role of Path. In 0.1, "Path" is also the 1D Body kind (`form.body.kind: path`) and a palette template (`symbolId: path`). See `docs/vision/TOPOLOGY-CELL-GRAMMAR.md`.

## Editor

- **Pin** — geometry frozen; content and settings stay editable. Machine: `editor.pinned`.
- **Lock** — semantic mutation refused; inspection and copy still work. Lock is stronger than Pin. Machine: `editor.locked`.
- **Hidden** — omitted from the canvas and hit-testing, kept in Objects. Not deletion. Machine: `editor.hidden`.
- **Opacity** — presentation only. Machine: `editor.opacity`.
- **History** — session-local undo/redo; one gesture produces one entry. Machine: `history.*`.
- **Checkpoint** — a named snapshot persisted in the `.sov` file, shown as "Versions" in the File menu. Machine: `document.meta.checkpoints`, `checkpoints.*`.
- **Recovery** — browser-local autosave, separate from Save. Machine: `soveraeign.schematic/workspace@0.1`.
- **Objects** — the Inspector view that lists every entity, including Hidden ones.
- **Appearance** — Light, Dark, or System editor chrome. It does not change the document's palette. Machine: `view.setAppearance`.

## Files and envelopes

- **`.sov`** — the editable document. Machine: `soveraeign.schematic/document@0.1`.
- **`.sovpak`** — a portable package: document + templates + assets + optional view state. Machine: `soveraeign.schematic/package@0.1`.
- **Operation / receipt** — the CRUD request and its revisioned result, shared by the browser API, HTTP, and MCP. Machine: `soveraeign.schematic/operation@0.1`, `soveraeign.schematic/receipt@0.1`. See `DATA-FORMATS.md`.
