# Residuals: graph primitives, sections, notations (PR #42)

Session `claude/graph-primitives-node-edge-onshoh`, 2026-09-25 to 26. PR #42 merged into `dev`
at `2cd2b76`. Everything below is known, unfinished, and not in `dev`. Each item names where it
comes from and what would close it.

## 1. Runtime overlap with state space

Raised in the PR review. The reply accepted it as follow-up.

| Residual | Close by |
|---|---|
| `src/07-graph-core.js` runs its own simulation beside state space (#43, `STATE-SPACE.md`): messages, levels, clocks, effects, scenarios. State space is the canonical runtime. | Re-express the gates as `truth_table@1` definitions and clocks as `transition@1`. Move the editor's clock (`65-sim-control.js`) and narration onto state space. Then retire the simulation half of `07-graph-core.js`, keeping its queries. |
| Differences to reconcile. <br>• **Time:** `latencyMs` in real time, where state space uses integer ticks. <br>• **Levels:** continuous 0..1 with a float epsilon, where state space uses binary or fixed point. <br>• **Missing values:** a missing signal defaults to asserted 1, where state space refuses it (R-02). <br>• **Replay:** effect keys `<node>:<value>`, where state space uses a hash-chained ledger. | The migration above. |
| Words: `merge`, `edge` (a level transition), `signal` / `level`, `node`, `junction`, `hyperedge`. | Rename to the product's and state space's words in the migration. |
| Load position `07` is shared by `07-graph-core.js` and `07-state-space.js`. | Renumber or retire with the migration. |

## 2. Measures named by the layout review, not built

`docs/reviews/2026-09-25-examples.md`, `LAYOUT-MODEL.md` "Still not measured".

- **A faint control mark:** the control mark on a gate is drawn fainter than the in and out marks (example 08).
- **A join drawn as a splice:** two wires meet at a dot before a gate's single port (example 10, `Clock AND enable`). Example 10 should use the `logic` notation's `and2`.
- **Arrowheads on short wires:** a chevron crowds a junction when the wire is too short to keep it 24 away (example 09, the fork after Evaluate).
- **A card crowding its container's interior guide.**
- **One-sided low contrast on marks:** the checker judges a mark by the median of the ring around it, so a mark that fails on one side passes. The earlier dark-mode case was an amber tick on a white wire.

## 3. Cosmetics listed, not done

From the cosmetics review (`docs/cosmetics/`).

- **Wire halo:** the band under every wire (`.wire-voltage`, 8px at 10% opacity) makes wires look doubled on straight runs.
- **Arrow density:** two chevrons per wire whatever its length.
- **A pin with nothing on it:** an unwired terminal still draws its pin to the card edge (receipt, observe). This is by design, but it reads as a line to nowhere on a sink.
- **Colour along a wire:** example 07's gradient changes colour with no legend entry for what it means.
- **Container space:** example 09's container keeps empty space at its foot now that its title moved to the top.
- **Labels on screen at low zoom:** with `dev`'s 12px floor, labels are fitted at their base size, so on screen they overflow small cards when zoomed out. Pictures are right.

## 4. Model work deferred

- **Sections:** hosting in bands (band surfaces), span ends, carriers in lanes (`SECTION-MODEL.md`).
- **The live relay:** external handlers run live rather than stubbed (`GRAPH-MODEL.md`).
- **Groups and instances:** subgraphs.
- **Notations** (`NOTATION-MODEL.md` "Open"):
  - importing a symbol library (draw.io, KiCad) as a converter
  - cards with more terminals than fit on one side
  - right-to-left narration

## 5. Palette and contrast

- Spectrum, cool, warm and earth are hue families and are not colour-blind distinct. The audit reports this and does not fail on it. The custom palette is not checked for distinctness.
- The dark `okabe-ito` row was re-searched to hold 3:1 on a dark card (`#484B4E`). The light row assumes cards close to the canvas; a light theme with darker cards would need the same rule.

## 6. Two export semantics

`snapshotSvg()` (`file.svg`, File > Export) is the canvas as on screen. `render.svg` and `render.png` are pictures with labels at their base size. Both use one implementation. The difference is intended, and should be stated in `WORKSTATION.md` or the operator skill if agents confuse them.

## 7. Process

- **Workstation records:** this ran in a cloud session. No workstation task, claim, episode or receipt records the work; there is only this file, the PR and its commits. If the ledger needs it, receive it through `ws receive` as a handoff.
- **Layout review:** a second formal packet was not filled for the notation-era examples (13, and the cards with subtitles). They were reviewed by eye during the work; the next change to rendering should run `scripts/layout_review.py` on all of them.
- **Render speed:** the server's render service starts Chromium for each call, with a 90 s timeout. It is slow under repeated agent use.
