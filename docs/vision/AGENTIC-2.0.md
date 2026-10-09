# Schematically 2.0: the agentic interface and experience

> **Non-authoritative horizon, draft for Bdo's confirmation.** This records the
> expectations for an agentic Schematically, written 2026-10-09 from a conversation with
> Bdo. It widens no 0.1 contract. The numbered expectations in section 7 are the
> "numbered requirement list Bdo confirms before any build" that the workstation mission
> *Schematically: a slim human interface over state that modes and agents reach*
> (opened 2026-10-05) waits on. Until he confirms them they are proposals.

Bdo stated four things:

1. Schematically becomes agentic: the user and their agent are joined by a **system
   user** and a **system agent**.
2. The UI becomes **generative and stateful**.
3. It is built on the **bdo design system** (`bdos-design`) and moves that system forward.
4. It takes in **3D**, and the recent **schematify / graph-clustering** work.

The aim is to define what an agentic user experience should be today, using
Schematically as the worked case.

## 1. Where this starts from (observed 2026-10-09)

What 2.0 builds on, with the gap each part leaves.

| Area | What exists | Gap 2.0 must close |
| --- | --- | --- |
| One legality path | Every surface (browser, Browser API, HTTP, MCP) goes through `Data.applyOperation` (`src/05-data-core.js`), with optional `ifRevision` | — keep it |
| Agent verbs | ~40 MCP tools: CRUD, history, checkpoints, runs, `graph.query`, `layout`, `render` (PNG back to the agent) (`MCP.md`); the workstation serves five meta-verbs over them, including `schematically_image` | Verbs are not a session: the agent and the person never share one |
| Shared state | The MCP server loads the file once and keeps its own document and its own 120-snapshot history (`mcp/server.mjs`); the browser fetches nothing from it | **An agent's edit is invisible to an open editor until the file is reopened** |
| History | `{label, at, document}`: a whole-document snapshot, session-local (`src/15-editor-kernel.js`) | **No actor.** An agent's edit can't be told apart from the person's, attributed, or rejected on its own |
| Event log | `STATE-SPACE.md`: "the event log is authoritative; every other state is a fold". Built for runs only (`src/07-state-space.js`) | Editing does not use it |
| Generative constraint | `HORIZON-SPACE.md`: a partly configured **Space** is "a constrained generative environment"; the data-language vision compiles one model into a diagram for a person and bounded context for an agent | Vision only |
| Graph → schematic | On `dev`: `scripts/graph_to_sov.py` reads graphify or system-cartographer `graph.json`; `--level communities` draws one card per community, with a child `.sov` per community linked by a plain `documentRef` string; the layered layout packs groups into rows with bus channels | Levels are separate files joined by a string. Groups are "reading-only", and generic grouping is omitted in 0.1 |
| Clustering view | system-cartographer's WebGL `graph_view.py`: planes × clusters; a cluster opens by screen room and interest; open files at every zoom is still QUEUED | A separate viewer, not Schematically |
| 3D | `form.dimension` clamped to ≤ 2, global canvas fixed at 2, `frame.depth` drawn as a bevel; `ROADMAP.md`: "do not call something 3D until the runtime has actual 3D semantics" | Hard-blocked, deliberately |
| Styling | One `styles/app.css`, plus notation tokens pushed into CSS variables | No reference to bdos-design |
| bdos-design | DTCG tokens with resolver axes (theme, contrast, density, motion, text scale, brand); contrast and looks contracts; a catalog of parts; shadcn and audiocn ports; parity-by-replication; agent API "post a painting, patch its data" | No canvas, graph, presence, proposal or 3D parts. The Schematically/Booth consumer proof (`rift`) is QUEUED |

## 2. Four participants, one record

The 2.0 table has four seats. Each is a relation over the document, not a rank
(Soveraeign R-08: no participant holds two relations over the same scope).

| | Acts for the **user** | Acts for the **system** |
| --- | --- | --- |
| **Person-shaped** (judges, chooses, owns intent) | **User**: Bdo or whoever opened the document. Owns intent. Picks among variants. Accepts outcomes. | **System user**: the system's own principal. Scheduled and triggered passes, imports, linked documents, a workstation seat acting on the document (a `ws` sweep, a cartographer rescan). It has an identity and edits under it; it is never "nobody". |
| **Agent-shaped** (proposes, builds, explains) | **User's agent**: brought by the user from outside (a Claude Code session over MCP, BYOM, a workstation contractor). Carries the user's scope and nothing more. | **System agent**: resident in Schematically. Speaks the Space's grammar. It validates, lays out, clusters, generates surfaces, compiles the model into context for other agents, and explains refusals. It holds no intent of its own. |

*My reading, to confirm:* "system user" means the system as a participant with
standing to act (it edits under its own name), and "system agent" means Schematically's
own resident agent, as opposed to the agent the user brings. If Bdo meant something
else, section 2 is the part to redraw.

What makes these four one experience and not four interfaces:

- **One record.** Every act by any of the four is an attributed event:
  `{actor, seat, on_behalf_of, operation, basis, revision, at}`. The editor's history,
  the MCP server's history, runs and generated surfaces are all folds over that one log.
  This finishes `STATE-SPACE.md`'s own principle by extending it from runs to editing.
- **One legality path.** `Data.applyOperation` stays the only door. A seat changes what
  the Space admits for that actor, never which code path runs (the roadmap's NEVER list:
  "do not fork implementations for … agent-authored variants").
- **One live session.** The person and every agent connected to a document see the
  same revision as it changes. Presence (who is here, what they are looking at, what
  they are doing) is shown and is itself state.

## 3. Generative and stateful UI

**Generative:** the screen is composed for the moment from three inputs: the document's
state, what the Space admits, and what the person (or an agent) is doing. It is not a
fixed set of panels. The main screen stays slim: canvas plus the few frequent edits. Every
other control is *summoned*: by selection, by asking, by an agent offering it.

**Stateful:** what is generated is not chat output that scrolls away. A generated
surface is a record: a declared composition of bdos-design catalog parts bound to
document state. It has an id, an origin (who generated it, from what request), a revision,
and a lifetime. It can be pinned, saved into the workspace or document, reopened,
diffed, and handed from one participant to another. This applies bdos-design's own rule
(paint-by-numbers): *a state is a patch on that data, never a second drawing*.

Three primitives carry it:

1. **Surface.** `surface@0.1`: parts from the catalog, each bound to a path in the
   document or the event log, plus the verbs it may issue. The inspector, a table of all
   wires, a layout-candidates comparison, a run timeline, and a judgement request to the
   user are all surfaces. People and agents both create them; the system agent creates
   most of them. Hand-built panels in 2.0 are surfaces whose origin is "shipped".
2. **Proposal.** An agent's change is either applied (when the Space admits it for that
   actor) or held as a proposal: an overlay drawn on the canvas as a ghost, with a diff,
   an author and a reason. The person accepts or rejects it, all or in part, and the
   choice is an event. Variants are proposals side by side. The person picks; the agent
   never picks for them (dress-the-set: "the person picks between variants").
3. **Space as the generator's grammar.** The Space declares which parts, notations,
   dimensions, verbs and actors it admits. The UI generator offers only what the Space
   admits, and an agent authors only inside it. That makes "25% configured" a feature: a
   narrow Space produces a narrow, legible interface.

What the person should be able to rely on:

- Nothing they placed moves without their act. A generated surface may appear and
  disappear, but it never rearranges pinned or locked work.
- Any change can be traced to its author and undone per author ("reject everything the
  agent did since 14:10").
- Generated surfaces settle. The same request on the same state gives the same surface,
  so the interface is learnable and not a slot machine.
- One place to talk. Asking in words, asking by pointing, and an agent asking the person
  all arrive at the same thread, scoped to the selection or the Space.

## 4. Agent experience (AX): the agent's side of the same screen

An agent is a first-class user, so it gets an experience, not just an API.

- **It sees what the person sees.** It can read the person's viewport, selection, current
  level and open surfaces, and get the render as an image (already built:
  `schematically_image`).
- **It gets bounded context, not the whole file.** The system agent compiles the
  Space plus the selection into context for the agent: admitted grammar, the
  neighbourhood, open proposals and refusals (the data-language vision's "instruction
  compilation").
- **Every refusal is typed and carries a next step** (`{ok:false, code, reason, next}`,
  already the workstation's verb shape). "Not admitted in this Space" names the Space
  rule.
- **It can address the person through the interface**: a judgement request is a
  surface on the canvas next to what it concerns, not a paragraph in a chat.
- **Its work is legible while in progress.** A building proposal shows on the canvas as
  it grows (R-30: Bdo sees work while it is built).

## 5. Graph, clusters and levels: schematify brought in

The graph work becomes a native part of the model, not a file exporter:

- **Import is a verb**: `graph.import {source: graphify|cartographer, level}` runs
  in-app over the same code as `graph_to_sov.py`, and the import is an event by the
  system user.
- **A cluster is a Plane with an open interior**, not a card pointing at another file
  through a `documentRef` string. `form.interior.state=open` already lets a Component host
  children. Community → file → definition becomes one document with nested hosts.
- **Level is a view property**, not a separate document. Collapse and expand per
  layout view (`LAYOUT-MODEL.md` already names per-layout group collapse as not built).
  Semantic zoom opens a cluster when it has room on screen or holds interest; this is
  the cartographer view's rule, adopted with its open fault list.
- **Clustering is the system agent's job and is shown with its basis.** Edges keep
  `EXTRACTED | INFERRED | AMBIGUOUS`. Re-clustering is a proposal like any other, so a
  person's hand grouping is never silently overwritten.
- **Groups stop being reading-only.** This is the 0.1 omission ("generic grouping") that
  2.0 has to settle first, because clusters, levels and 3D planes all stand on it.

## 6. 3D, earned

The roadmap rule stays: nothing is called 3D until the runtime has 3D semantics. The
proposal is to earn it in the order the content needs:

1. **Planes in depth (first).** A Space gains a z coordinate per Plane and a camera
   (orbit, perspective/orthographic, the frame code Foundry already ported). Each
   Plane remains a 2D Space; wires may run between Planes. This is genuinely 3D (XYZ,
   camera, depth hit-testing between Planes) without volumes. It fits the content we
   already have: architecture layers, cartographer planes, levels of a cluster stacked
   behind each other.
2. **Volumes (later, only for content that needs them).** `form.dimension = 3` with
   faces, spatial containment and attachment to 3D surfaces, as `HORIZON-SPACE.md` lists.

2D stays the default projection. 3D is another projection of the same model, chosen per
view, never a fork of the document.

## 7. Expectations to confirm (numbered)

Each one is stated so it can be shown working or not. **Floor** items are needed before
the rest can be honest.

**Floor: shared, attributed state**
1. Every edit from any surface is an event naming its actor, seat and on-behalf-of; undo
   and history are folds over that log.
2. The person and every connected agent see one live revision of an open document; an
   agent's edit appears in the open editor within one second, attributed.
3. Presence: who is connected, what each is looking at, what each is doing.
4. Per-actor reject: undo everything one actor did since a point, leaving the others' work.

**Participants**
5. The four seats (user, user's agent, system user, system agent) exist as declared
   identities with what each Space admits for each.
6. The system agent validates, lays out, clusters and explains; it never accepts its own
   proposal.
7. The system user's acts (import, rescan, scheduled pass) are attributed like anyone's.

**Generative, stateful UI**
8. Main screen: canvas plus the frequent edits only, with the control count measured
   against an inventory (the 2026-10-05 mission's own measure).
9. Every other control is reachable as a surface, summoned by selection, by asking, or
   by an agent, and every removed control names its route.
10. Surfaces are records (`surface@0.1`): id, origin, bindings, revision; pin, save,
    reopen, diff and hand-off.
11. Agent changes outside what the Space admits for it arrive as proposals: ghosts with a
    diff, accepted or rejected in whole or in part.
12. Variants are shown side by side; the person picks.
13. Same request + same state = same surface.

**Agent experience**
14. An agent can read the person's view state and get the render as an image.
15. An agent gets compiled, bounded context from the Space and selection.
16. An agent can raise a judgement request as a surface anchored to what it concerns.

**Design system**
17. Schematically's chrome is built from released bdos-design tokens and catalog parts;
    `styles/app.css` keeps only what the catalog doesn't yet have, by name.
18. Notation colours bind to bdos-design meaning roles (one meaning per colour), so
    theme, contrast, density and motion axes reach the diagram too.
19. Schematically contributes the parts the catalog lacks, each with a parity reference
    (tldraw, Miro, draw.io, Figma, Linear): canvas, node card, wire, minimap, presence
    cursor, proposal ghost, provenance badge, surface frame, camera control.
20. Schematically is bdos-design's consumer proof (the queued `rift` task): a pinned
    release with digest and rollback.

**Graph and levels**
21. Graph import is an in-app verb over `graph_to_sov`'s rules.
22. Clusters are nested hosts in one document; level is a per-view collapse state.
23. Semantic zoom opens clusters by room and interest; a one-member file reads as one file
    at every zoom.
24. Groups are first-class and editable; re-clustering is a proposal.

**3D**
25. Planes in depth: z per Plane, camera, inter-Plane wires, depth hit-testing.
26. Volumes only when content needs them, behind the roadmap's 3D rule.
27. 3D is a projection per view; the document never forks.

## 8. Order (proposal)

1. The floor (1–4). Without it every later item would be an agent acting on a
   different document from the one the person is watching.
2. bdos-design under the chrome (17–18), with the slim main screen (8–9). These run
   together because the inventory decides which parts are needed.
3. Surfaces and proposals (10–13), with the system agent (6) as their first author.
4. Groups, then graph levels (21–24).
5. Planes in depth (25), then 3D's later items.

## 9. Open questions for Bdo

- Section 2's reading of "system user" and "system agent": right, or redraw?
- Which model is the system agent: a local model (BYOM/ollama), the user's Claude, or
  either under a declared binding?
- Where 2.0 is judged first: the browser app, the Tauri desktop, or inside a booth beside
  the four references (shadcn, Miro, draw.io, Mermaid)?

## Residuals noticed while mapping

- `STATE-SPACE.md` and `LAYOUT-MODEL.md` both say "nothing here is implemented", but
  their code exists. A cold agent reading the header gets the wrong answer.
- `graph_to_sov.py` is on `dev`, not on `main`. A `main` checkout appears to have no graph
  import at all.
- bdos-design is not checked out in the cloud sessions (only `Soveraeign`, `bdos`,
  `schematically` and `workstation` are). Its push task is still QUEUED although PR #27
  merged.
