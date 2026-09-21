# Work graph profile 0.1

A WS mission opens as native Schematically Components, attachment points and Wires.
Its source readings are separately held in the existing `.sovpak` envelope. This is
a **read-only snapshot projection and inspector**, not a workflow executor, task
database, permission system, or RSTS kernel implementation.

Built from development baseline `fd4a10245c21dbabecc3c919da5f0fbb38bcb3bf`.
The Boolean execution proposal in PR #33 is not a dependency or a merged capability
of this slice. Nothing here claims live JEV participation or SOV acceptance.

## Try it

Open `index.html`, then File → Open → `examples/workstation-review.sovpak`.
Choose **Graph view**, select the mission and then a task. A task holds its contract,
candidate reference, evidence references and unresolved obligations when supplied.
The inspector follows these native subjects, their containing systems, and incident
relationships. Source fields appear as readable structured values, not a JSON dump.
Graph view hides editing controls; the same native canvas still supports selection,
pan, zoom and geometry. Toggle Graph view off to return to the full editor.

The example is synthetic and visibly labelled **Fixture · not live work**. It has
three tasks, two declared dependency Wires, one dependency outside the supplied
snapshot and two unresolved wait descriptions. A `requires` Wire is not a transport
observation. There is no animated evidence of work being delivered.

## Use with workstation records

From Schematically's repository, with Python 3.11+ and Node 22+:

```powershell
python scripts/export_workstation_mission.py --root C:/Users/bdf19/workstation --mission YOUR-MISSION-ID --out C:/Temp/mission-input.json
node scripts/workstation_graph.mjs C:/Temp/mission-input.json C:/Temp/mission.sovpak
```

Open the resulting package in this build. Both scripts refuse to overwrite an
existing output. The exporter refuses output under the WS root, reads only declared
mission/task files, imports no WS kernel, and executes no WS operation. Test roots
are temporary. These are new Schematically scripts, **not invented `ws` commands**.

The exported packet can contain private objectives, contracts, paths and evidence
references. Keep it local; review it before sharing or sending it to any model.
The exporter omits fields outside the explicit mission/task field allowlist,
including `github_authority`, but is not a secret scrubber for arbitrary prose or
contract content. No request to a model or external service is made.

The exporter censuses task files, selects records explicitly charged to the mission,
rereads files to detect ordinary collection races and hashes the read bytes and
relative names. The result says **sampled-files**, never atomic or live. A change
and restoration between reads can escape this check; it is not a lock or a signature.
The source digest includes the task census, so another task file can change the
frontier even when this mission's projected fields are unchanged.

A WS client may instead build the packet from its own readers:

```javascript
const input = {
  mission: {id: "m1", repository: "example", title: "One outcome"},
  tasks: [{id: "t1", repository: "example", mission: "m1",
           title: "Inspect the candidate", dependencies: [],
           workstation_state: "QUEUED", waiting_on: null}],
  source: {
    system: "workstation:my-node",
    revision: "the-source-revision-or-content-digest",
    capturedAt: "2026-09-21T00:00:00Z",
    consistency: "provided-snapshot",
    coverage: "One mission and one selected task; no runtime or evidence resolution."
  }
};
const packageFile = SovSchematicAPI.graph.projectWorkstation(input);
SovSchematicAPI.graph.openWorkstation(input); // deliberate native file replacement
const reading = SovSchematicAPI.graph.inspect("ws:task:t1");
```

`projectWorkstation` is pure; `openWorkstation` deliberately opens the resulting
package in the browser, like the existing API file-open path. It is not a WS write.
It does not provide a cross-origin iframe bridge: an embedding host must use its
existing trusted application boundary. This PR does not install or modify WS Lens.

The `source` object always names system, revision, timezone-qualified capture time,
coverage, and one of `repository-snapshot`, `sampled-files`, `provided-snapshot`,
`fixture`. Optional `baseUrl` supports explicit user-clicked HTTP/HTTPS source links.
The source issuer supplies these claims; the graph cannot authenticate them.

At most 100 supplied tasks are admitted. Every supplied task must name the selected
mission and repository. Duplicate identities, duplicate dependency IDs, missing
frontiers and malformed contracts refuse. Unknown task status words stay source
values, not newly inferred readiness. Absent `dependencies` is a gap; an empty list
is a recorded empty list. Prose `waiting_on` stays prose with an unresolved marker.
An absent dependency target remains a gap; no placeholder task state is invented.

## Common Browser / HTTP / MCP surface

Three stateless functions use exactly the same shared code:

| MCP tool | HTTP POST | Arguments |
| --- | --- | --- |
| `schematic.graph.project-workstation` | `/api/v1/graph/project-workstation` | `{input}` |
| `schematic.graph.inspect` | `/api/v1/graph/inspect` | `{package, address?}` |
| `schematic.graph.compare` | `/api/v1/graph/compare` | `{before, after}` |

Browser `SovSchematicAPI.graph.execute(name, arguments)` and HTTP return
`{ok, value, mutates:false}`. MCP uses its existing result envelope: `structuredContent`
contains `value`, and `isError` is the inverse of `ok`. Refusals contain an error code
and message. Supplied packages are not installed as the MCP server's document;
projection, inspection, comparison and refusal do not enter its history or write
its file. No server operation resolves arbitrary source paths or makes network calls.
The existing server launch, listener and access policy are unchanged.

## One topology, separately held readings

`document.meta.graph` contains a `graph-definition@0.1` binding list. Each binding
names a native `component` or `wire`, its stable address, and a domain role:
`system`, `node`, `charge`, `reference`, `dependency`, `transport`, or `provenance`.
Every Component and Wire in a graph-profile document has exactly one binding.
These roles do not create new geometric objects or executable behavior.

Nesting comes from the native hosting surface, not a second hierarchy. A carrier
can host a Component whose interior holds another Component/charge. The core case
`a carrier can hold a subsystem which holds a structured charge` exercises that
construction. Containment cycles, closed hosts, missing bindings and illegal
boundary reach-through refuse. Connections still use the native data/attachment
core; there is no graph-specific reachability algorithm.

`package.meta.graph` contains `graph-snapshot@0.1`:

```text
source      system, revision, capturedAt, consistency, coverage
definition  canonical topology and public subject meaning (compatibility, not auth)
readings    one per bound address; explicitly named fields
gaps        addressed unresolved conditions, never inferred task state
```

Each field has `axis`, `basis`, `status`, `source`, and a `value` only when present.
Bases are `declared`, `observed`, `derived`, `judged`. The WS adapter emits source
record fields as **declared**; it has not independently observed their claims.
The candidate reference's revision remains absent, and dependency delivery remains
absent. Neither the branch name nor an evidence reference supplies that fact.

Absent, explicit null, false, zero, empty list and empty text remain different.
Structured JSON values are bounded by depth 24, 50,000 visited values and two million
text characters; there are at most 1,500 subjects, 128 fields per subject and 3,000 gaps.
These are format admission limits, not process isolation or production quotas.

Topology binding includes subject identity, role, label, hosting scope, dimensional
and boundary semantics, attachment direction/access, and carrier endpoints/direction.
Geometry, camera and presentation can change without changing source meaning.
A semantic edit detaches the old readings: canvas state annotations disappear,
the inspector explains the refusal, and saving a graph package refuses until the
meaning is restored or the source is projected again. Undo/checkpoint restore keeps
the separately held snapshot and rechecks its compatibility. It does not undo WS.
Binding compares canonical content; it is not a signature and cannot prove that
someone has not authored both a diagram and a false history.

A `.sov` exports the authored graph definition without readings. `.sovpak` preserves
both layers. Browser recovery carries package metadata separately from the document.
The existing file lifecycle owns all of this; the inspector never serializes files.
Ordinary non-graph documents and packages keep their previous behavior.

## Snapshot comparison is not execution replay

`compare` requires the same source system and mission identity, then reports added
or removed subjects, exact field changes and whether definition meaning changed.
It does not fill the time between two snapshots or infer causal order, delivery,
progress, completion, or events. A later observation can change a reading without
changing the diagram. A different input ordering cannot change stable subject IDs.

The RSTS correspondence is deliberate but bounded: addresses identify subjects,
axes describe fields, Views inspect scope, and typed Relations preserve meaning.
Snapshots provide input records for a later adapter. No RSTS Series, Transform,
Step execution or kernel-backed Record is claimed here. A future temporal adapter
must reconcile RSTS frontiers with PR #33's event-order semantics explicitly.
The existing BDOS PR #70 is the candidate source-bound JEV observation integration;
this work neither copies it nor calls JEV. Live model output must become a retained
observation rather than replace a source fact or mint operation authority.

## Checks and next boundary

`python scripts/qa.py` includes `work_graph_core_qa.py`, `work_graph_export_qa.py`
and `work_graph_browser_qa.py`. The tests cover deterministic native projection,
structured nesting, boundary refusal, absence, source detachment, undo, package and
recovery custody, source-text injection, independent views, constrained width,
file-export safety and exact Browser/HTTP/MCP parity. Public fixtures are synthetic.
The optional `GRAPH_QA_OUTPUT` directory receives a screenshot. CI runs real-origin
recovery; a local runner may explicitly report it unavailable when an administrator
blocks all browser navigation, but that is not equivalent to passing the case.

Not delivered: live subscriptions, in-place source refresh preserving authored
layout, executable carriers, scheduler/queue persistence, dynamic topology,
operation/grant bindings, live JEV, per-participant visibility authorization, or
collapse/expand semantic zoom on the canvas. The first consuming WS task should
embed this build and call the projector from WS-owned readers. Only after that
inspection is useful should execution/replay be commissioned against its own
refusal cases. No new phase, grant, standing or landing decision is made here.
