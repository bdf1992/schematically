# QA — 0.1 Beta.24

## Static / build

- modular `src/` restored to artifact: PASS
- modular `styles/` restored to artifact: PASS
- deterministic standalone `index.html` build: PASS
- all JavaScript modules pass `node --check`: PASS
- legacy top-level Save / Load / Data / Clear / Export controls removed: PASS

## Browser file-surface smoke

- File menu boots and opens: PASS
- `.sov` Save fallback produces `document@0.1`: PASS
- `.sovpak` export produces `package@0.1`: PASS
- package contains document, workspace view, templates and assets arrays: PASS
- browser API parses `.sov` and `.sovpak`: PASS
- real `.sov` re-open succeeds: PASS
- recovery storage failure does not break File Open: PASS
- no page errors during tested sequence: PASS

Test: `tests/file_surface_qa.py`.

## MCP / HTTP

- restored `mcp/server.mjs` to artifact: PASS
- default file is `.sov`: PASS
- MCP tools/list: PASS
- HTTP formats advertise `package@0.1`: PASS

- corner transform grip grouped at bottom-right: PASS


## Beta.24 editor kernel

- semantic undo / redo: PASS
- multi-select semantic clipboard / paste: PASS
- Pin + Lock persisted editor state: PASS
- checkpoint creation/list: PASS
- quick search + desaturation: PASS
- Objects fallback panel: PASS
- dark appearance mode: PASS
- global rate state: PASS
- no legacy KEYS badge: PASS
- browser page errors: 0

### Extended kernel invariants

- settle/hosting ghost appears before release: PASS
- release establishes parent/local-surface relationship: PASS
- effectful Form material/body-thickness/frame-depth projection: PASS
- Pin blocks pointer and keyboard geometry changes: PASS
- Lock blocks browser CRUD mutation: PASS
- Hidden object recoverable from Objects panel: PASS
- rate composition = global × source Component × Wire: PASS
- routing cache scope regression (`sourceNode`) fixed: PASS

Test: `tests/editor_kernel_extended_qa.py`.

## Reference/freeze corpus

- Author / Operator / Reviewer skills present: PASS
- `../../AGENTS.md` invariant contract present: PASS
- five classic `.sov` examples validate: PASS
- classic `.sovpak` validates: PASS
- public-beta freeze contract present: PASS


### Beta.24 hardening blockers
- Wire empty-space growth requires dwell ghost before creation: PASS (static/runtime contract)
- Release before growth ghost creates nothing: PASS (runtime contract)
- Component drag cleanup uses try/finally and missed-release recovery: PASS
- Dark canvas/grid surface: PASS
- Dark/light paired palettes including Mono: PASS
- Contrast readout removed while automatic contrast engine remains: PASS
- Dark File/menu surfaces no longer inherit white backgrounds: PASS


### Beta.24 visual QA

- light canvas uses light grid tokens: PASS
- dark canvas uses dark grid tokens: PASS
- canvas label/packet text uses surface-relative ink: PASS
- duplex example renders both forward and reverse packets: PASS
- browser screenshots captured for light and dark appearances: PASS

## Beta.24 host-surface checks

- same Component record across root / interior / Wire hosts
- normalized Wire placement `t`
- automatic no-backdrop projection on Wire hosts
- host Wire deletion re-homes Components



## Beta.24 final engineering gate

- major regression suite: PASS
- boundary legality: PASS
- Read/Write access + packet marks: PASS
- performance regression watcher: PASS
- 9/9 targeted mutants killed: PASS
- concern audit: `MODULE-QA.md`

## Beta.24 inline Wire anchoring

- New host adoption requires a settle dwell before the ghost arms: PASS
- Wire-host ghost aligns to local Wire tangent: PASS
- Wire-hosted Component derives world x/y/angle from `wireId + t`: PASS
- Built-in terminal axis aligns to the host Wire axis: PASS
- Host Wire cut meets inline symbol terminals with zero intentional gap: PASS
- Existing host-surface QA: PASS
- Pre-repo hardening checks: 26/26 PASS

- dimensional form correction (0D/1D/2D, no fake 3D): PASS
- golden-run and CI contract: PASS

- Beta.24 dimensional ports + history quick actions: PASS

## Beta.24 Grid visibility regression

- `Show grid` controls the same `canvasGridVisible` state in Light and Dark: PASS
- theme switching cannot resurrect a hidden grid: PASS
- workspace serialization/restoration preserves hidden state: PASS
- regression source: `tests/grid_visibility_qa.py`


## Beta.24 — 0D attachment refactor

PASS: dedicated attachment-point QA; dimensional/history QA; boundary legality; read/write access; Wire inline hosting; host surfaces; tray settle; grid visibility; pre-repo hardening; editor kernel; extended editor kernel; file surface; performance regression; mutation watcher (9/9 killed); golden corpus (7 documents).

Visual QA confirms: 0D=`self`, 1D=`start/end`, 2D=`left/right/top`, and a 2D Component hosted on a Wire is connectivity-projected to 1D with only `start/end`.

## Beta.24 — 1D/2D attachment interaction parity

- Legacy Wire-owned Port/point records migrate to hosted 0D Components: PASS
- `+Port` creates the same hosted 0D Component model directly: PASS
- Hosted 0D point uses the ordinary Component attachment hit/selection/wiring path: PASS
- 1D-hosted point can source a Wire to a 2D boundary through the same `addConnection` path: PASS
- 2D boundary can source a Wire to the hosted 0D point: PASS
- Host-aware inside/outside exposure maps Wire point external face to the Wire's containing surface: PASS
- Inline 2D Component projected onto a Wire still exposes only `start/end`: PASS
- Boundary, Read/Write, Wire-host, tray, history, grid, editor, file, hardening and performance regressions: PASS
- Golden corpus: 7/7 PASS
- Mutation watcher: 9/9 mutants killed

## Beta.24 — drag lifecycle stress

- 24 repeated root Component drags: PASS
- 12 repeated nested Component drags with containment preserved: PASS
- 10 repeated Wire-hosted Component drags with host preserved: PASS
- stranded `activeNodeDragState`, `wireDrag`, or transform gesture after release: 0
- runtime/page errors: 0

## Beta.24 — deep RC QA additions

- canonical blank-growth direction resolves through attachment descriptors: **PASS**
- canonical/legacy endpoint identity suppresses duplicates and upgrades reverse connection to duplex: **PASS**
- endpoint channel tags use physical attachment side rather than legacy alias strings: **PASS**
- data-declared extra 2D boundary attachment points (`side + t`) work through the shared core/API: **PASS**
- richer 2D Component hosted on a 1D carrier projects connectivity back to `start/end`: **PASS**
- Browser / HTTP / MCP enforce the same locked-entity and locked-endpoint mutation policy: **PASS**
- HTTP and MCP share server mutation history for undo/redo: **PASS**
- refused operations do not advance revision: **PASS**
- render after normalized CRUD is semantically idempotent and does not produce a hidden second revision: **PASS**
- CI/browser runtime is centralized; explicit Chromium path passes locally: **PASS**
- Playwright-managed Chromium install in this container: **UNPROVEN (external DNS blocked download)**
- repository GitHub Actions reproduction: **PENDING exact Beta.24 branch settlement**
- mutation watcher: **9/9 killed**
- golden corpus: **7/7 PASS**

Tests: `attachment_growth_direction_qa.py`, `attachment_terminal_identity_qa.py`, `configurable_attachment_defaults_qa.py`, `agent_api_mcp_golden_qa.py`, `render_idempotence_qa.py`.
