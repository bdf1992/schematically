# Original swarm bundle review

The supplied `swarm-schematic-review.zip` has SHA-256
`5d80bf75efa2dd3a61f795f48959771b47b98b3af9b468ab6aaf08c8937f4d63`.
It contains the three `.sov` documents, a README and `swarm-review.html`; it
contains no screenshot files. Embedded prose was reviewed as artifact content,
not as authority to change the engineering scope. The original files are retained
byte-for-byte in [the regression fixtures](../../../../tests/fixtures/swarm-originals).

The review compared the original documents in the normal standalone editor at
base `9919db6`, the supplied wrapper, and PR #39. Local Chromium 143.0.7499.4
opened the actual files; browser screenshots, rendered rectangles and real
downloads were observed. Both 768px and 1440px widths, light and dark, were checked.
This supersedes the earlier report's missing-document limitation. The four
historical screenshots remain unavailable; the before pictures below are fresh
reproductions from the original documents and the recorded base editor.

## Findings and disposition

| Concern | Observation and disposition |
| --- | --- |
| Geometry | The base browser shrinks each host to 520×420. The revised editor paints and saves the authored 940×650, 1170×730 and 1010×620 rectangles. Full child rectangles fit their hosts. All component positions, IDs, types, parent/surface membership, boundary placement and wire endpoints survive normal Save, package export and reopen. Zero-dimensional Point presentation sizes still follow the shared minimum policy; their actual point footprint and authored placement are preserved. |
| Label placement | On `32f5b01`, service `w10` overlapped Adapter, `w13` overlapped Queue, and collaboration `w11` overlapped Contributor. The renderer now measures label rectangles and places them beside an existing route segment while avoiding bodies, labels and other wire centerlines. Model and route coordinates do not change. A crowded route has a finite fallback, so this is not automatic layout or a promise that every graph fits every screen. |
| Authoring | The originals have no explicit component palette slots or pins. Revised [native documents](../../../../examples/swarm) keep the topology and geometry, shorten captions, retain the original captions and all contract notes in metadata, and assign stable connection slots at both ends. Duplicate request/discovery wire captions were removed only where the adjacent labelled interface already says the same thing; original captions remain recorded. |
| Pins and ports | Hosts and authority/capacity references are pinned; draft components remain movable. Original-file tests select every connected component and verify its actual port hit targets and exposed surfaces. No connected or unused template port was deleted. Existing Pin/Unpin/Undo, semantic-edit and parent/pinned-child tests remain in the full gate. |
| Graphics and export | Team and history presentations reuse the two portable SVG assets from the fresh example, preserving semantic types and ports. The revised diagrams retain them through file/package round trips and normal SVG export in both themes. Source sanitization is unchanged. |
| Wrapper | It embeds the old size-clamping editor. Its 20px override matches component/outside labels; its 16px `.wire-label` override matches no wire-label elements because the renderer uses `.connection-label`. This enlarges one label class while leaving the other small. The wrapper has a separate styled export button as well as the old File-menu export. No baseline editor CSS was changed to compensate for these wrapper overrides. Use the revised native files with the current editor. |

The three revised overviews have no measured label/label or label/body overlaps
at 1440px in either theme. At 768px, Fit provides orientation; a few short gaps
remain too tight for the minimum readable labels. The focused captures use the
normal zoom buttons and actual middle-button pan gestures on the same document.
They cover those crowded spans without changing the saved geometry. Content
outside a focused viewport is intentionally off-screen, not removed from the graph.

The service's admission output feeds both reservation and refusal paths. Both
retain the existing request/action channel color; the Refusal component is red.
Creating separate channels or executable branch conditions merely to recolor the
drawing would change the proposal and was not done. Runtime guarantees remain
outside this engineering handoff.

## Visual evidence

Each name below links to an actual browser screenshot. `before` is the original
file in the base normal editor; `after` is the revised native file in the updated
normal editor. The wrapper is a separate comparison.

| Diagram | Before, 768 light | After, 768 light | Before, 1440 dark | After, 1440 dark |
| --- | --- | --- | --- | --- |
| Platform | [before](01-platform-before-768-light.png) | [after](01-platform-after-768-light.png) | [before](01-platform-before-1440-dark.png) | [after](01-platform-after-1440-dark.png) |
| Service | [before](02-service-circuit-before-768-light.png) | [after](02-service-circuit-after-768-light.png) | [before](02-service-circuit-before-1440-dark.png) | [after](02-service-circuit-after-1440-dark.png) |
| Collaboration | [before](03-collaboration-before-768-light.png) | [after](03-collaboration-after-768-light.png) | [before](03-collaboration-before-1440-dark.png) | [after](03-collaboration-after-1440-dark.png) |

The complementary 768 dark and 1440 light captures are in this directory with the
same naming pattern. Wrapper comparisons: [platform](01-platform-wrapper-1440-light.png),
[service](02-service-circuit-wrapper-1440-light.png),
[collaboration](03-collaboration-wrapper-1440-light.png).

Focused 768px reviews: [platform](01-platform-focus-1-768-light.png),
[service admission](02-service-circuit-focus-1-768-light.png),
[service outcomes](02-service-circuit-focus-2-768-light.png),
[collaboration](03-collaboration-focus-1-768-light.png). Matching dark captures are
included. Browser captures of the standalone exports use the `-export.png` suffix.
Standalone exports: [platform light](01-platform-1440-light.svg),
[platform dark](01-platform-1440-dark.svg), [service light](02-service-circuit-1440-light.svg),
[service dark](02-service-circuit-1440-dark.svg), [collaboration light](03-collaboration-1440-light.svg),
[collaboration dark](03-collaboration-1440-dark.svg).

## Verification and delegation

The original-file regression and label-placement fix ran under separate written
workstation contracts and isolated worktrees. The first external test carrier
could not access the supplied input directory and made no changes; an in-session
carrier with access to the supplied workspace completed the same contract.
The root session independently inspected both diffs and reran their acceptance
commands through `ws contract audit` before integration.

- Original fixture carrier: `0748d9798ba60f949b0ebe27dbc46eeb2b170309`.
- Wire label carrier: `e62b934c388140d9cee78d9dea9e00803a1187f5`.
- Contract corrections: raw package representation may include derived defaults,
  while authored fields and reopened records must match; a local `.gitattributes`
  rule preserves the original fixture bytes on Windows checkout. Neither
  correction weakens a geometry or topology assertion.

The combined final gate passed **50 suites and 17 JavaScript syntax checks**
(121.92 seconds); see [the complete log](qa.log). Both independent contract audits
passed with zero files outside their declared paths.

Reproduce the focused checks:

```sh
python tests/swarm_originals_qa.py
python tests/wire_label_clearance_qa.py
python tests/swarm_review_qa.py --out swarm-evidence
python scripts/qa.py
```

Issue #16 was closed after independently rerunning its primitive-label regression
and observing original Plane/Point labels; its fix was already merged in #32.
Issue #38 tracks this review and PR #39. Neither a merge nor a release is part of
this handoff. Historical screenshot comparison remains an evidence gap. A separate reproduced
rate-policy defect is escalated in [issue #40](https://github.com/bdf1992/schematically/issues/40):
package reopen overwrites authored `meta.timeScale: 0` with the derived view rate `0.1`.
The presentation regression verifies retained metadata captions/notes, geometry, colors
and graphics; it does not claim rate equivalence or that zero pauses execution.
