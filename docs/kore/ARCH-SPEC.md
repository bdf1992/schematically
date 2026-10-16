# Kore architecture baseline

Baseline date: 2026-10-12. This revision establishes Kore's identity, ownership boundary and long-term compiler direction. It supersedes earlier descriptions of Kore as a tool for remodeling the Workstation kernel wherever those descriptions conflict with this baseline. Earlier diagrams, source packages and implementation reports remain evidence at their stated scope; they do not become implementation proof by appearing here.

Kore is a C-like language and system for expressing bounded work. Root is Kore's Cfront-like compiler. Workstation is the present physical host and lower-level execution substrate. The intended direction is for Root to become expressible in Kore and for Kore to provide its own logical environment for further Kore development. That self-hosting target is not implemented by the schematic model or the current Workstation proof.

The layer analogy is useful at the boundary: Workstation supplies lower-level machine and host facilities; Kore provides the language; Root translates and checks Kore programs. It does not mean every Workstation module is compiler assembly, or that a Kore program can perform host effects without Workstation's authority and checks.

## 1. Authority and source standing

The architecture has three documents with different jobs:

| Source | Standing | Governs |
|---|---|---|
| [Kore Shared Contract](https://github.com/bdf1992/workstation/blob/main/docs/kore/alignment/SHARED-CONTRACT.md) | Binding law for shared work on the current Workstation host | Admission, host-resolved authority, scope, budgets, verification, recording, refusal, recovery and release holds |
| This Kore ARCH specification | Architecture baseline | Kore's language/compiler/host boundary, the observed implementation, known gaps and the next proof targets |
| Mathematical and topological material | Epistemic reference model, or north star | Terms and properties for reasoning about structure and long-term guarantees; a formula or diagram becomes an operational obligation only when a contract maps it to an implementation and evidence |

The technical source supplied with the design calls itself a ratified engineering standard. That label records the source's intent; it does not ratify its claims in the current repositories. The executive summaries and diagrams also include proposed mechanisms and analogy. This baseline distinguishes those proposals from the user's later adjudications and from inspected runtime evidence.

## 2. Responsibility chain: Owner, Host, Root

These are distinct responsibilities. Authority originates with the Owner, is resolved and enforced at the Host, and constrains what Root may compile or request. Results return through the Host for verification and recording before the Owner accepts the requested outcome.

| Responsibility | Current occupant | Owns | Does not imply |
|---|---|---|---|
| Owner | Bdo | Intended outcome, taste decisions, permitted authority, acceptance and changes to the mandate | That an agent role, model proposal or observation grants permission |
| Host | Workstation | Physical execution on this machine; source and repository access; process, file, CLI, network, test and resource boundaries; host-side admission, records and receipts | That Kore's language rules or portable program model are Workstation implementation details |
| Root | Kore's intended Cfront-like compiler | Reading Kore programs, resolving names/types/contracts, rejecting invalid programs and lowering admitted programs to a host request or bounded execution plan | Direct access to files, processes, credentials or other host effects |

The currently inspected homes are split: Schematically holds Kore's portable diagrams, model and design sources; Workstation holds its own executable kernel, host adapter and bounded Kore execution proof. No dedicated Kore repository exists in the observed registry. Repository extraction is a separate Owner decision; until then, this split is deliberate, not proof that Schematically or Workstation owns the other one's code.

Workstation retains its host-specific monolith and ARCH maintenance: records, locking, sessions, process control, CLI and HTTP surfaces, architecture scanner, CI selection, test budgets, receipts and host policy. Kore Root may own a portable architecture language or compiler representation later. Workstation still owns scanning its source and admitting or executing any resulting host change. A Workstation refactor does not become Kore work merely because it uses Knodes, Kords or ARCH terminology.

## 3. The epistemic authority stack and a Knode's local anatomy

The `M0–M3` stack and the `3×3` matrix measure different things. They are orthogonal projections, not competing hierarchies.

| Level | Name | Responsibility |
|---|---|---|
| M0 | Empirical ground | External environment and attributed observations returned from it |
| M1 | Operational complex | The executing runtime graph and its current work |
| M2 | Invariant governor | Rules, schemas and constraints that admit or refuse transitions in M1 |
| M3 | Type foundation | Type-level foundations that establish M1 and M2 as well-formed |

M3 has two separate grounding obligations: a logical account that reaches strong normalization, and a physical account that reaches the Host execution runtime. Neither proof currently follows from the diagrams or Python simulation. The Host supplies physical execution; it does not replace the logical proof. M1 observes and acts on M0; M2 constrains M1; M3 constrains the well-formedness of M1 and M2. Observation never promotes itself into authority.

Each Knode in M1 is inspected locally through this matrix:

| Concern × side | User | External | Internal |
|---|---|---|---|
| Purpose | User purpose | External purpose | Internal purpose |
| Dynamics | User dynamics | External dynamics | Internal dynamics |
| Foundation | User foundation | External foundation | Internal foundation |

The 3×3 is a responsibility and inspection view of one state owner. It does not describe the system-wide M-level ladder. A local cell does not gain authority from its position. Phase, address, scale, topology, kinematic direction, port availability and permission remain separate properties.

The supplied five-axis coordinate proposal (compass, vertical, direction, lateral and boundary) is a separate candidate coordinate system. No row-by-row mapping from it to M0–M3 or to the local 3×3 has been established. Keep each coordinate typed and explicit; geometry does not create a Kord, permission or schedule.

## 4. Kore terms and the settled structural rulings

| Term | Kore reading | Evidence limit |
|---|---|---|
| Knode | Addressable state owner with a phase, outcome record and local 3×3 concern matrix | The portable Python model has workers/places and ports; it does not make every model call a Knode |
| Kord | Declared directed traversal between Knodes, with typed crossing, preconditions, admission, cost, return mapping and recorded outcome | A drawn edge or matching port does not prove an executing traversal |
| Korner | Zero-dimensional synchronization vertex shared by four adjacent Knodes | Semantics are settled below; enforcement in the structural model is incomplete |
| Komplex | A closed perimeter, sequential loop or concurrent operation group | The boundary-conservation rule is a required check, not an observed universal runtime property |
| Kore | The language and system; a model may also name its central Knode `kore` | Whole-system identity and one node instance are distinct |
| Root | Kore's Cfront-like compiler and, at the long-term target, the Kore implementation that compiles and hosts later Kore work | A compiler/runtime implementation has not been established by the current schematic model |
| Kernal | A term present in supplied vocabulary | Its intended definition and spelling remain unresolved |

### Korner

A Korner is a synchronization vertex for four Knodes. Its static rule is a non-traversable barrier: no diagonal import or flow crosses it directly. Its dynamic rule is a consensus joint: adjoining perimeter operations must agree before a surrounding operation can commit. The two rules describe one structure under static and dynamic inspection. The old image's non-carrying intersection and the newer synchronization/consensus role are not alternate choices: the Korner carries no traversal, but its joint is checked by adjoining operations. A model showing the vertex does not prove either rule is enforced in Workstation or Schematically.

### Balanced ternary and boundary conservation

Use one carrier algebra, `T = {−1, 0, +1}`, through three typed projections:

1. Incidence: source (`−1`), uninvolved (`0`), target (`+1`).
2. Contract admission: refusal (`−1`), quiescent (`0`), admission (`+1`).
3. Kinematic direction: reverse (`−1`), stationary (`0`), forward (`+1`).

These projections share values, not meanings. A value without its projection/type is ambiguous. The separate dissipative flux is a monotonic work-budget decrement: finite tokens, attempts or time are spent and cannot increase inside an admitted request. Do not encode cumulative cost as an overloaded `−1` or infer a budget from ternary direction.

A Komplex is any closed topological perimeter, whether sequential or concurrent, whose boundary conservation check satisfies `∂(∂σ) = 0` before commit. The equation names the check; it is not proof that every current Workstation or Kore operation satisfies it.

## 5. Outcomes, telemetry and safe failure

**Solved** means both that a candidate output satisfies the admitted verification criteria and that the outcome is recorded in the ledger. It is not an attractor, low free energy, a model score, transport success or a visually stable state.

A justified refusal is a successful contract outcome when the system lacks authority or evidence, violates an invariant, or exhausts its declared budget. It must carry the reason and attribution. Refusal does not mean the user's requested operation was completed.

Safe failure has three cases:

1. **Rollback:** discard uncommitted internal memory.
2. **Containment:** isolate the failed Knode and its incident Kords from further propagation.
3. **Recorded uncertainty:** write a durable receipt that preserves what may have happened and requires explicit forward compensating work.

A safe failure halts the relevant state machine, accounts for spent budget, contains or compensates for mutations, and records the result. A timeout does not prove that a remote effect did not occur.

Telemetry may tune only bounded heuristics on an Owner-approved list. It may report drift and propose a change; it cannot rewrite invariants, grant authority, raise budgets, widen scope, alter acceptance or ratify its own changes. Those changes require the Owner's decision and a new host-resolved contract.

## 6. Bootstrap and the self-hosting target

Self-hosting is a staged language/compiler property, not a claim that a diagram runs itself and not a promise that Workstation's physical machine disappears.

| Stage | Required result | Status in the inspected material |
|---|---|---|
| 0. Portable model | Names, topology and bounded simulations make the proposed form inspectable | Present in Schematically's Python model and diagrams; model checks do not prove a host runtime |
| 1. Root frontend | A Root compiler reads a small Kore source subset, checks typed forms and emits a deterministic, inspectable host plan with errors/refusals | Not established by the inspected Schematically sources |
| 2. Host boundary | Workstation resolves authority and capabilities, executes only the admitted plan, and returns attributed observations and receipts | Bounded host-side Kore/Knode proof exists in Workstation; see [Workstation evidence](https://github.com/bdf1992/workstation/tree/main/docs/kore) and its shared contract for exact limits |
| 3. Kore implementation | Root's source and relevant runtime are expressed in Kore and compiled by the bootstrap Root | Future proof obligation |
| 4. Self-compilation | Root compiles its own Kore source reproducibly; the result is checked against the bootstrap behavior and records source/build identity | Future proof obligation |
| 5. Logical self-host | Kore's Root provides the compiler and logical work environment used to describe, build and evolve Kore itself | Long-term target; still relies on an underlying physical machine/OS unless a separate claim is proved |

The compiler becomes the language in this sense: Root ceases to be only an external translator and becomes the Kore implementation that can describe and compile its own future. The exact grammar, type calculus, intermediate representation, host ABI and milestone for each stage remain open. Do not schedule monolith rewrites as language work until their outcomes can be expressed at this boundary.

## 7. Present implementation and evidence boundaries

Schematically's local model includes `model/fraktal.py`, `model/fraktal_run.py` and structural checks. Workstation's host-side Kore interfaces and bounded execution evidence are described separately below. The model's declared shapes and simulation are useful design evidence; they are not Root compiler evidence. The runtime simulation has an undirected Kord lookup and does not prove the stated port-direction rules. The current editor's 3×3 view is a projection, not an enforcement mechanism.

The diagrams have different standing:

| Artifact | Standing | Does not establish |
|---|---|---|
| `diagrams/kernel-tiles.sov` | Explicit proposal for a tileable/nested form | Implemented tiling, authority, or a Kore compiler |
| `diagrams/fraktal.sov` | Model-generated structural view; its metadata says 8 of 8 model requirements hold, with three only partly checked | Full Korner enforcement, all twelve Kord strands, four-bus execution or runtime parity |
| `model/check_structure.py` and retained `evidence/` files | Checks and historical records for their exact model/source revision | Fresh results for a later tree or Workstation runtime proof |
| Workstation `ws weigh --kore` and governed Knode paths | Bounded host-side executable evidence, with explicit release and evidence limits in Workstation's shared contract | Root compiler, arbitrary work graphs, complete self-hosting, physical process isolation or unrestricted Kore execution |

The earlier executive sources describe telemetry loops, probabilistic attractors, wavefronts, entropic drag and multi-order adaptation. Treat these as explanatory or research concepts unless they have a typed operational definition, declared observation, bounded authority and retained evidence. In particular, the latest completion and telemetry rulings in sections 5 and 2 govern over earlier attractor and autonomous-policy language.

## 8. Refinement path and held decisions

Refine work in this order:

1. Settle the minimal Kore source form, type rules, invalid-program behavior and the distinction between a program, a compiled host plan and a recorded result.
2. Specify Root's frontend and compiler output, including how authority references, typed Kords, phase mappings, budgets, returns and uncertainty appear in a plan.
3. Specify the Workstation host interface: which effects it accepts, how it resolves Owner authority, what it observes, how it verifies and records results, and how refusal or uncertain outcomes return.
4. Build one small Root-to-Host example whose passing result is checked and recorded, plus one denied/uncertain result that cannot commit as success.
5. Express a bounded part of Root in Kore and prove self-compilation before widening the supported language or moving ownership of more execution.
6. Extend nesting, concurrent Komplexes and logical self-hosting only after each smaller obligation has source identity, failure behavior and evidence.

Questions still held by Bdo:

- What exact syntax and type calculus define the first useful Kore programs?
- What compiler output is the stable boundary between Root and Workstation Host?
- How is Korner consensus calculated and recorded for a real perimeter operation?
- Which independently typed rules complete the older five-axis coordinate proposal, and how do they relate to ports without being confused with M-level authority or the local 3×3?
- What evidence is enough to call each bootstrap/self-hosting stage complete, and when should Kore receive a dedicated repository?
- What formal argument and executable proof will establish M3's strong-normalization grounding, separately from its physical Host grounding?

These questions block later refinements that depend on them; they do not undo the rulings already settled in this baseline. The [ownership review](OWNERSHIP-REVIEW.md) records how the current Workstation queue fits the boundary and which work should remain host-owned.

## 9. Retained host example and history

The Workstation `ws weigh` path remains a useful source-backed example of inference, transport, usage metadata, privacy and logging. It demonstrates a Workstation-owned inference path and a bounded Kore projection around one operation. It does not show that Kore source was compiled by Root or that Root owns the request's host effects. Provider retry is not application idempotency; a remote timeout may leave the outcome unknown; a post-inference log failure can prevent the caller receiving a result after the provider has succeeded.

The Workstation record-write square remains a proposed host integration example. Its earlier reading of Korner as an invariant joint is now refined by the settled static barrier and dynamic consensus definition above. The example documents a host repair; it is not a universal Kore runtime or a proof of all Komplex conservation claims.

Older consolidation material and implementation reports remain available in the linked Schematically and Workstation documentation. Read their dates, source revisions and evidence limits literally. The current baseline owns the architectural distinctions; historical recommendations and open questions do not override the rulings recorded here.
