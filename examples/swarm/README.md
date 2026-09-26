# Proposed collaboration platform

Open these files through the normal editor's File → Open command. These are the
three supplied architecture diagrams with presentation changes. The original
component IDs, semantic types, coordinates, Plane dimensions, parent/surface
membership, boundary placement, wire endpoints, direction and operations are
retained. Long captions remain in `meta.originalLabels` and
`meta.originalWireLabels`; the original contract notes are unchanged.

| File | Reading order |
| --- | --- |
| [Platform](01-platform.sov) | Participant request → service → contract evaluation → state/history; authority above, observations below. |
| [Service circuit](02-service-circuit.sov) | Admission and reservations → relay → effect adapter; reported outcomes → reconciliation → settlement. Authority, capacity and breaker control enter from above. |
| [Collaboration](03-collaboration.sov) | Publish → reserve → artifact; review evidence → settlement → discovery. |

Palette: C5 requests/actions, C6 authority/control, C4 observations/evidence,
C1 refusal/protection, M1 host/persistence fills. Both ends of each connection
carry the same slot. Labels and symbols carry meaning alongside color. The
admission-to-refusal wire retains the request/action slot: it shares Admission's
output channel with the reservation path; the Refusal component identifies the
outcome. No new channel or executable branch was invented to recolor that path.

Host regions and authority/capacity references are pinned. The other components
remain movable. Select a pinned item and use Settings → Pin to unpin it; Undo
restores the prior state. Pin controls geometry; it does not lock semantic edits.
Connected and unused template ports remain present. Team and history graphics
are presentation assets attached to their existing semantic types.

At 768px, use the overview to orient, then zoom and pan across the circuit or
double-click an object in Objects to focus it. Review the upper controls, main
request path and lower evidence path in turn. Fit alone is not a promise that a
dense graph can be read in one narrow frame.

The diagrams describe proposed contracts. They do not implement a runtime,
authorization enforcement, branching, reconciliation or replay.
