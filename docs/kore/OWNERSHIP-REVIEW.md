# Kore and Workstation ownership review

Snapshot: 2026-10-12 America/Chicago. This is a grooming record, not a migration
order. It describes the source and queue observed for this review; native
Workstation tasks retain their current mission, owner, status and contract.

## Current boundary

| Part | Current responsibility | Later direction |
|---|---|---|
| Owner (Bdo) | Sets intended outcome and retains decisions reserved to the Owner. | Same. |
| Host (Workstation) | Supplies physical execution, current `wskernel`, host services, admission and recorded operational outcomes. | Kore may replace parts of the logical host once its language and runtime can express and enforce them. Physical execution still needs a substrate unless a new physical host is built. |
| Root | Not yet demonstrated as a compiler in this repository. The architectural role is Kore's Cfront-like compiler, operating under host-resolved authority. | Implement Root first on Workstation, then express Root and its required logical host in Kore and prove bootstrap/self-compilation in stages. |
| Kore | Portable design, model and language specification; no demonstrated self-hosting compiler or production runtime here. | The language becomes the medium used to implement its compiler and logical host. |

The request path should preserve this boundary:

```text
Owner intent
  → Kore request and constraints
  → Root checks/compiles a candidate plan
  → Host resolves authority and admits or refuses it
  → Host executes admitted effects and attributes observations
  → verifier checks the admitted criteria
  → ledger records success, refusal or safe failure
```

Root can describe and prepare work, but a compiled plan is still only a
proposal. Workstation remains responsible for host admission, access to physical
capabilities, bounded execution, rollback/containment and durable recording.
The Host must return an attributed outcome to Root. Kore may take on logical
host responsibilities over time only when those responsibilities are
expressed, admitted, executed and recorded under the same binding contract.

“Self-hosting” is therefore a direction, not a present capability claim. The
language may become its own logical host; this does not by itself remove the
physical machine or grant the compiler new authority.

## Source hierarchy and design rulings

Use the Kore Shared Contract as binding law for current execution, admission,
verification and recording. Use Kore ARCH as the architecture baseline for
components, known gaps and near-term targets. Use the mathematical/topological
specification as a reference model for long-term reasoning, not as evidence that
the runtime already enforces its equations.

The settled design distinctions are:

- M0–M3 describe empirical ground, operational execution, invariant governance
  and type foundations. The 3×3 matrix describes one Knode's local concerns.
  They are orthogonal views.
- `T={−1,0,+1}` is one carrier with typed interpretations for incidence,
  admission and direction. A value in one interpretation does not silently
  establish another.
- A Korner is a four-Knode synchronization vertex. Statically it blocks
  unmediated traversal or diagonal flow; dynamically it is a joint where
  adjoining perimeter operations must reach the required agreement.
- A Komplex is a closed sequential or concurrent perimeter subject to the
  boundary-conservation condition `∂(∂σ)=0`. The formula is a design obligation,
  not proof of implementation.
- A task is Solved only when an admitted candidate satisfies verification
  criteria and the outcome is recorded. A justified refusal is a successful
  safety result, not task completion.
- Safe failure distinguishes rollback of uncommitted internal state,
  containment of the failed Knode and incident Kords, and durable recorded
  uncertainty with compensating work required.
- Telemetry may tune bounded, Owner-approved heuristics. It cannot change
  invariants, authority, scope, budgets or acceptance criteria.
- Strong normalization is the logical grounding obligation; execution on the
  physical Host is a separate grounding obligation.

## Design and taste discrepancies to resolve in refinement

These are differences in stated intent or presentation, not implementation
defects inferred from diagrams:

1. **Completion language changed.** Earlier descriptions call stable attractors
   or reduced free energy a solved state. The later contractual ruling requires
   admitted verification plus a ledger record. Bring older prose into line with
   the later ruling when it is next edited.
2. **Adaptive governors overstate authority.** Some early summaries describe
   autonomous governors that adapt constraints. The settled boundary permits
   bounded heuristic tuning only; the invariant and authority rules stay fixed.
3. **Failure language is underspecified in older sources.** Fallback and
   containment language does not capture the three settled tiers or the durable
   uncertainty receipt and compensating work.
4. **Korner language has two roles.** Older schematic notes leave its purpose
   provisional or treat it only as a geometric seam. The settled design assigns
   both the static barrier and dynamic synchronization-joint roles. The ARCH
   and README now state this as an architectural ruling while marking runtime
   enforcement as unproven.
5. **Formal notation can read as a proof claim.** Equations, topological terms
   and generated model checks describe obligations or model properties. They
   do not establish host enforcement, arbitrary-graph behavior, concurrency
   safety or compiler correctness.
6. **Axis vocabulary must stay separate.** The settled M0–M3 and 3×3 axes resolve
   the apparent stack/grid conflict. Other proposed axes (ports, kinematics,
   scale and phase) still need definitions and explicit mappings; do not imply
   they have been adjudicated by that resolution.
7. **Specification status is not implementation status.** A source document
   calling itself ratified or production-ready does not itself confer binding
   authority. The Shared Contract has that operational role; architecture and
   reference documents remain subordinate to it.

## Workstation queue snapshot

The two inspected missions contain 86 task records: 21 queued, 3 active, 1
blocked and 61 closed. The first mission,
`workstation-the-kernel-centre-is-rebuilt-in-place`, has 2 active, 7 closed and
6 queued. The second,
`workstation-the-kernel-maps-its-own-structure`, has 1 active, 1 blocked, 54
closed and 15 queued. These are a queue snapshot, not a live query; recount
before making priority or transfer decisions.

All 21 queued tasks concern Workstation's present executable host, records,
interfaces or CI. Keep their records and current implementation ownership in
Workstation. A future Kore language/compiler item may depend on these host
capabilities, but that is a separate task and contract. In particular,
`workstation-arch-knode-execution` remains a Workstation host prototype; any
Root language semantics should be separately scoped after the bootstrap plan
and host boundary are accepted. No task below is transferred or rewritten.

| Queued task | Disposition and reason |
|---|---|
| `workstation-a-note-is-marked-delivered-after-it-is-printed` — A note is marked delivered only after it is printed | **Keep in Workstation.** Delivery state follows the host's successful print operation. |
| `workstation-a-save-that-cannot-get-the-records-lock-is-typed` — A save that cannot get the records lock is a typed refusal | **Keep in Workstation.** This is a host records-lock and refusal behavior. |
| `workstation-arch-cuts-lists-the-imports-that-hold-the-loop` — ws arch cuts lists the imports that hold the loop together | **Keep in Workstation; defer a possible Kore split.** The current import scanner reads Workstation source. A portable graph language/model could be separate Kore work later. |
| `workstation-arch-knode-execution` — Land ARCH Knode execution | **Keep in Workstation; split a future Kore follow-on.** This is a bounded host prototype with recorded returns. Preserve its contract/location; file Root language semantics separately after the language/host boundary is accepted. |
| `workstation-audit-of-a-task-whose-change-is-already` — Audit of an already-merged task reports landed, not failed | **Keep in Workstation.** It changes the host queue audit. |
| `workstation-contract-audit-runs-each-test-file-once` — Contract audit runs each test file once | **Keep in Workstation.** It governs host contract/test scheduling. |
| `workstation-each-check-function-lives-in-its-compone` — Each doctor check lives beside the rule it checks | **Keep in Workstation.** It reorganizes host doctor checks. |
| `workstation-every-retried-bind-says-so-and-stops-after-three` — Every retried bind says so, and stops saying so after three | **Keep in Workstation.** It governs host session/bind retry behavior. |
| `workstation-every-scanned-module-has-a-test-that-imports-it` — Every scanned module has a test that imports it | **Keep in Workstation.** It governs host CI test selection and module coverage. |
| `workstation-handler-py-holds-a-route-table-of-method` — build_handler is a route table with one function per route | **Keep in Workstation.** This is the host HTTP handler/interface. |
| `workstation-main-passes-the-tests-ci-never-selects` — Main passes the tests pull request CI never selects | **Keep in Workstation.** It fixes host main-suite CI scheduling. |
| `workstation-main-s-tests-pass-on-a-loaded-runner-and-a-clean-tree` — Main's tests pass on a loaded runner and a clean tree | **Keep in Workstation.** It governs host CI runner preflight. |
| `workstation-policy-ops-load-projection-or-file-holds` — The policy projection loader lives in policy_ops, not doctor | **Keep in Workstation.** It reorganizes the host policy projection module. |
| `workstation-preflight-fails-when-an-entry-can-tighten` — Preflight fails when a baseline entry can tighten | **Keep in Workstation.** It changes the host architecture baseline/preflight. |
| `workstation-reading-a-record-does-not-block-its-replace` — Reading a record does not block its replace | **Keep in Workstation.** It is host storage/record replacement behavior. |
| `workstation-retarget-hand-over-and-clear-waits-their` — Queue plan-and-run verbs move out of queue_ops | **Keep in Workstation.** It separates host queue operations. |
| `workstation-task-readers-import-the-records-module` — Callers that only read a task import the records module | **Keep in Workstation.** It changes host task-record storage boundaries. |
| `workstation-task-session-id-from-is-contract-session` — session_ops has fewer than ten importers | **Keep in Workstation.** The actual task concerns the host session module/import structure, not session ID semantics. |
| `workstation-tests-fit-their-process-start-bands-after-moving-in-proc` — Tests fit their process-start bands after moving in-process | **Keep in Workstation.** It changes host test-runner timing. |
| `workstation-the-test-seconds-snapshot-is-current` — The test seconds snapshot is current | **Keep in Workstation.** It maintains the host test-suite budget/selection data. |
| `workstation-ws-arch-also-measures-log-retention-and-what-tests-touch` — ws arch also measures log retention and what tests touch | **Keep in Workstation.** It changes host archive/test-containment tooling. |

## Root refinement questions held by Bdo

These are the decisions the current sources do not answer. Keep them open until
the Owner chooses, instead of filling them in through implementation:

- What is Kore's smallest initial syntax and semantic core, and which type and
  effect rules must Root reject before producing a plan?
- What stable artifact does Root produce (for example, a typed plan or
  intermediate representation), and what exact interface does the Host accept?
- Which capabilities always belong to the physical Host (identity resolution,
  storage, process launch, clocks, budgets and ledger), even after a Kore
  logical host exists?
- What trusted bootstrap seed may compile the first Root, and what independent
  comparison or proof permits a later Root to compile itself?
- What evidence is enough to say Kore is its own logical host, separately from
  the stronger and currently out-of-scope claim that it replaces Workstation's
  physical execution environment?
- Which proposed port, scale, phase and kinematic axes are language semantics,
  and what explicit typed mapping connects them to the settled M-stack and
  3×3 Knode view?

## Staged Kore work breakdown

Keep these as proposed grooming slices; do not open implementation work until
their contracts and acceptance owners are bound.

| Stage | Deliverable | Observable proof obligation |
|---|---|---|
| 1. Language core | Small syntax, values/types, effects and refusal rules, with versioned examples. | Golden valid/invalid programs yield stable typed outcomes; invalid authority/effect use is rejected before host execution. |
| 2. Root frontend | Cfront-like parser/type checker that emits a documented plan artifact. | Same source and compiler version produce the same inspectable plan; malformed and ill-typed source refuses with attributed diagnostics. |
| 3. Host boundary | Workstation adapter for authority resolution, admission, budgets, capabilities, observations and ledger returns. | Host rejects an unauthorized or over-budget plan without effects; admitted fixture work returns verifiable, attributable evidence and a durable record. |
| 4. Kore-authored slice | Re-express one bounded Root or host-support component in Kore. | The Kore implementation passes the same conformance set as the established implementation, with differences reviewed and recorded. |
| 5. Bootstrap | Compile a later Root from Kore using an earlier trusted Root. | Independent stage-one and stage-two builds agree under declared reproducibility criteria; both compiler identities and outputs are recorded. |
| 6. Logical self-host | Move declared logical host responsibilities into Kore while retaining a physical substrate. | A coverage map shows which host services Kore owns; adversarial admission/failure cases and ledger evidence pass for every claimed service. |

Passing these stages would support a Kore logical-host claim. It would not by
itself prove arbitrary termination, concurrency correctness or physical
independence from Workstation.

## Grooming order

1. Recount and inspect the live native queue before changing priority; this
   document is a snapshot, not the task database.
2. Reconcile the two Workstation Kore architecture records. The local
   Workstation `docs/kore/ARCH-SPEC.md` describes PR #429 as open/held, while
   `docs/kore/alignment/SHARED-CONTRACT.md` records it as merged at
   `86d9aa77330ea478092fd9ef2c38ce23ddd03c1f`. This task does not edit either
   record; their owner should correct the stale statement under a separate
   contract.
3. Groom `workstation-arch-knode-execution` in place against its current
   Workstation contract. Record any Kore-language follow-on as a new task with
   its own acceptance owner, authority, scope, evidence and budget.
4. Write and review the Root bootstrap stages before assigning compiler work:
   language grammar/semantics, frontend, host interface, staged self-compile,
   and the evidence required to claim Kore is its own logical host.
5. Then rank the remaining Workstation queue by user outcome, dependencies,
   observable acceptance checks, authority and cost. Shared-contract binding is
   required before execution, including for resumed tasks.

## Evidence boundary

This review uses the five supplied architecture/specification attachments,
the Kore sources in this repository, and the native Workstation queue queried
at 2026-10-12 19:30 UTC. The supplied documents are design inputs, not runtime
evidence. The Schematically model's structural checker and simulation are not
run here; the WorkContract for this documentation task allows zero tests.
Existing model metadata and prior reports are not promoted to compiler, host or
self-hosting proof. Bdo remains the acceptance owner for this design direction.
