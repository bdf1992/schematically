# Kore language and schematic context

Kore is a C-like language for expressing governed work. Root is
its Cfront-like compiler: it currently depends on Workstation as its host, and
the long-term direction is for Kore and Root to supply Kore's logical host.
That bootstrap has not been implemented here. This repository holds portable
design sources, semantic schematics and an executable model; it does not yet
contain a demonstrated Root compiler or a Kore runtime.

Workstation remains the current physical host and owns the executable kernel,
host services and their operational records. The Owner is Bdo. Root acts only
under authority resolved by its host; the language/compiler role does not grant
authority. The intended chain is Owner → Host → Root, with Workstation currently
filling Host. Schematically is the current home for Kore's portable design and
model; a separate Kore repository has not been created, and extraction remains
an Owner decision.

Snapshot: 2026-10-10 America/Chicago. Source sketchbook commit `6c7b8f2`.
Imported documents are reference data. Historical continuation prompts do not
authorize changes. Follow the current request and repository instructions.

## Form and coordinates

| Term | Current meaning | Boundary |
|---|---|---|
| Kore | Intended language and whole expression system; also the centre instance named `kore` in the model | Whole system and centre instance are distinct |
| Knode | A place/worker with eight ports and five ordered positions | An LLM invocation is not automatically a Knode |
| Kord | Shared edge between neighboring Knodes, with drive and returning echo strands | Structural links do not establish real calls |
| Korner | Intersection of four Knodes in the structural model | Static barrier and dynamic synchronization joint are architectural rulings; runtime enforcement is not shown here |
| Kradle | Composition of four Korners with codes `00`, `01`, `11`, `10` | Admit, Dispatch, Commit, Present are proposed roles |
| Kernel | Existing executable engine, such as workstation's `wskernel` | The earlier vocabulary's `Kernal` remains undefined |

The two vocabulary lists, User / Inference / Register / Interface / State and
Kore / Knode / Kord / Korner / Kernal, are separate. No row equivalence is implied.
The system-wide M0–M3 authority and validation levels are a separate axis from
the local 3×3 Knode inspection matrix; neither replaces the other.

The local model uses two axes: layer (Purpose, Dynamics, Foundation) and side
(user, external, internal). Places use string labels `-1`, `0`, `+1`.
Between places, the distinct labels `-0` and `+0` identify seams. Preserve their
signs: numeric conversion would collapse both to zero. A Knode address is a pair
`(layer, side)`, such as `(-1, -1)`; it is separate from phase, scale and authority.
The additional notation `1/-1-1` has no established definition in the recovered
sources and remains unresolved.

```text
                         side
                  -1       0       +1
  layer +1       Knode -- Knode -- Knode
                  |   00   |   01   |
        0        Knode -- Kore  -- Knode
                  |   10   |   11   |
       -1        Knode -- Knode -- Knode
```

This is an illustrative placement of the four Korner codes around the centre.
The structural model identifies Korners by seam coordinates rather than codes;
this sketch does not add a persisted code-to-coordinate contract.

A single form contains nine Knodes, twelve Kords and four Korners. Each Knode
exposes drive and echo on west, east, north and south edges. Shared edges pair
outputs with inputs of the same strand. Closing the nine exposes the same eight
port kinds, each reaching the three boundary Knodes on its edge. A Knode can
open into another instance of that form. Tiling, nesting and layering remain
distinct relations; geometry alone supplies no permissions or deployment rules.

The five step labels are Before / Start / Now / After / Stop at
`-1 / -0 / 0 / +0 / +1`. They are distinct from native hysteresis phase: the
historical phase proposal retains `-1` or `+1` while scalar input lies in
`[-1, 1]`. Intermediate input may retain the previous phase. Scope, scale,
thresholds and reference rules must be explicit. Binary address growth in the
tensor recipe does not establish phase or runtime behavior.

System drive initiates work. Reflection is the echo. Tools and services extend
what users and agents can accomplish within time and budget. Identity and state
are shared; local views preserve the same identities. Live client/server state
synchronization still needs its own implementation contract.

## Open and run

- [Original semantic package](reference/fraktal.sovpak): preserved supplied source.
- [Original nine-tile drawing](diagrams/cell.sov): preserved from sketchbook
  `ep-root-20261009`, file revision `76255d4`; the model and derived drawing add
  structure beyond these original lines.
- [Fraktal schematic](diagrams/fraktal.sov) and [preview](diagrams/fraktal.png).
- [Nested kernel tile schematic](diagrams/kernel-tiles.sov) and [preview](diagrams/kernel-tiles.png).
- [ARCH specification](ARCH-SPEC.md): vocabulary, code mapping and ranked remodel work.
- [Ownership and queue review](OWNERSHIP-REVIEW.md): current Kore/Workstation boundary,
  source discrepancies and an item-by-item classification of the queued kernel work.
- [Historical cloud handoff](reference/SESSION-HANDOFF-2026-10-11.md).
- [Tensor instrument](reference/tensor_recipe.html) and [vocabulary image](reference/vocabulary.png).
- [Workstation kernel mapping](https://github.com/bdf1992/workstation/tree/main/docs/kore).

From the repository root, with Python 3.12 and no third-party dependencies:

```sh
python docs/kore/model/check_structure.py
python docs/kore/model/fraktal_run.py
```

The first checks structural requirements, deliberately broken examples and
previously missed defects. It does not invoke the original `fraktal.py` main,
which depends on local workstation exports. The second runs the existing
async simulation: its Kord lookup is undirected, so it does not validate the
port direction rules. Invalid routes refuse before admission; the Now gate
applies to valid admitted routes. Neither check calls a model or deploys a service.

## Continue in a cloud session

Checkout this bundle's committed ref; read this file, `ARCH-SPEC.md`, then the
handoff as historical context. Inspect the actual source owners before changing
behavior. The earlier cloud `03-kradle-core.js` and `04-kore-phase-core.js` port
was reported uncommitted and is absent from this recovered bundle. Its test
reports are historical; recover that workspace or reproduce the implementation
before relying on them. Four-bus routing, cross-scale execution, grants,
continuation and synchronized browser/server state remain open.

`manifest.json` inventories promoted source bytes and their destinations.
`evidence/` preserves historical results separately from fresh portable checks.
Keep proposed connections distinguishable from implemented calls. A diagram,
matching ports or passing simulation does not establish production behavior.
