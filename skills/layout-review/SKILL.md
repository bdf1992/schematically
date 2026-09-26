# Layout review skill

## Purpose

Judge how a schematic presents by looking at it, and hold the scorer to what you saw. The audit
(`layout.metrics`, `layout.contrast`) counts only what it was taught to count. It gave every
example 10/10 while the pictures read 6 to 9 (docs/reviews/2026-09-25-examples.md). This skill
closes that loop. You read the pictures in character and score them yourself. Every disagreement
becomes a measure.

## When to use

- After changing rendering, routing, layout or the examples, before calling the change done.
- When someone says a diagram "looks bad" and the audit says it is fine.
- On any document you are about to hand to a reader.

## Steps

1. Render the packet.
   `python scripts/layout_review.py [a.sov ...] --out review/`
   It writes `review/<doc>/light.png` and `dark.png`, `packet.json`, and `REVIEW.md`, and prints an
   `IMPROV <doc>/<slot>` call for every line it needs from you.
2. Look at every picture with the Read tool, light and dark. Do not answer from the audit text or from
   the document JSON. The slots ask about the picture.
3. Answer each call on its `[doc/slot]:` line in `REVIEW.md`:
   - `read-cold` and `trace` are improvised: speak as the cast reader (newcomer, operator, auditor,
     author, or the audience a layout names), in first person. Say what the diagram tells *them*
     and where their eye hesitated. Name stops by the labels the picture shows.
   - `score` is yours, out of character: a number from 0 to 10, then one clause of reason. Give it
     before you re-read the audit's number.
   - `gap`: if your score and the audit's differ by 2 or more, name what the audit missed as a rule
     a script could measure ("a label closer than 0.6 of its font size to a card that is not its
     own"). A feeling ("looks busy") is not a rule. Otherwise write `none`.
   - `line` is the one sentence you would say to the diagram's author.
   - `packet/ranking` and `packet/next-measure` judge the whole set.
4. Check. `python scripts/layout_review.py --check review/` refuses the packet if any of these hold:
   - a slot is empty
   - a trace names fewer than two real labels
   - a score is not a number
   - a disagreement names no measure
   - a document or the build changed after rendering

   When it accepts, it prints the calibration (the mean distance between your scores and the audit's)
   and writes `verdict.json`.
5. Close each gap:
   - Add the rule to `src/57-layout-metrics.js` with a rubric weight.
   - Add a planted failing case to `tests/layout_quality_qa.py`.
   - Then fix the defect where it lives: the renderer, the router, or the document.

   If the measure contradicts your gap (it happened: "twice the Manhattan distance" was false),
   keep the measure and correct the claim.
6. Record it. Keep the filled review under `docs/reviews/<date>-<subject>.md`, without the pictures,
   with a "What changed" table of each gap, its measure and its fix, including the gaps not yet
   measured.

## Colour

`python scripts/contrast_audit.py` measures every label (WCAG 2.2 SC 1.4.3: 4.5:1, large text 3:1)
and every mark (SC 1.4.11: 3:1) against what is painted beneath it, in light and dark. It also
measures each palette as realised: each theme's contrast floor, plus colour-blind distinctness under
protan, deutan and tritan simulation. `--write` regenerates `contrast-audit.md`. A contrast finding
also costs layout score (`text-contrast`, `mark-contrast`).

## Rules

- The numbers are the audit's; the reading is yours. Never edit a score to agree with the other.
- Every improv slot must be in the reader's voice, not a summary of the audit.
- A review that finds nothing on a 10/10 packet is suspect: look again at labels near lines, empty
  frames, routes leaving the picture, marks crowding marks, and text size.
