# Residuals: the state-space runtime on dev

Task `schematically-sandbox-23b6ad5a`, branch `feature/state-space-runtime-lands-on-dev`, 2026-09-26.
The branch merges `dev` at `0cd9831` into the state-space runtime at `f6e312d`. Both runtimes load side
by side; nothing was migrated between them. Everything below is known and not finished. Each item
names where it comes from and what would close it.

## 1. A dev example was not saved as authored (closed on this branch)

`tests/declared_ports_qa.py` (the runtime's round-trip check, "stored forms are saved as authored")
failed on dev's new `examples/09-proposed-service-review.sov`:

```
AssertionError: ('examples/09-proposed-service-review.sov', [['service', 'none', None], ...], [['service', None, None], ...])
```

The Plane `service` authors no `attachmentDefaults`. Loading fills in the Plane preset's `'none'`
(`src/05-data-core.js`, `applyTemplatePreset`), and `compactDocument` always stores `'none'`, so the
saved file gains `"attachmentDefaults": "none"`. The runtime at `f6e312d` and `dev` at `0cd9831` save it
the same way (checked on exports of both), so the merge did not cause it: the runtime's rule meets a
file it never saw. Every other Plane in `examples/` authors `"attachmentDefaults": "none"` and passes.

Closed by the launcher's ruling of 2026-09-26: `service` now authors `"attachmentDefaults": "none"`, the
value load already filled in, and nothing else in the file changed. Its pin was recomputed with the
unchanged pin code and did not move (`24814d24173f6be4a4260f48986ee259b05b64ec896289511d27152d31f70296`
before and after the edit), because the saved form already carried `'none'`; the file now matches it.
The other route, not writing a Plane's preset mode on save, was not taken: it would change
`compactDocument` for every Plane and so every pin that has one.

## 2. Unmigrated overlap

| Overlap | Where | Close by |
|---|---|---|
| Gates. The state-space runtime's gates are `truth_table@1` definitions in a pack (`data/core.logic.pack.json:28` `logic.and`, bound through `config.definition`). Dev's gates are notation glyphs that declare a `combine` (`src/03-notation-core.js:66`, `and2`, `or2`, ... `buf`), read by the graph simulation (`src/07-graph-core.js:48`), and the `gate` symbol with a control point (`src/07-graph-core.js:394`). | #43 | Re-express dev's gates as `truth_table@1` definitions. Not done here by contract. |
| Clocks. The state-space runtime has no clock: time is the integer logical tick of a run (`src/07-state-space.js:707`, `step`). Dev's `clock` and `lever` symbols assert levels over real-time latency (`src/07-graph-core.js:51-52`). | #43 | Re-express dev's clocks as `transition@1`. Not done here by contract. |
| The simulation half of `src/07-graph-core.js`: `createSimulation` (`:285`), `runScenario` (`:608`), `createSession` (`:647`) and the `schematic.sim.*` tools, beside the graph queries (`build` `:93`, `query` `:258`). Both runtimes are served: `schematic.run.*` / `schematic.state.query` and `schematic.sim.*` / `schematic.graph.query` (`mcp/tools.json`, `mcp/server.mjs`, `src/85-api.js`). | #43, PR #51 residual 1 | Retire the simulation half once gates and clocks are migrated; keep the graph queries. |

## 3. Words both runtimes use for different things

| Word | State-space runtime | Dev's graph runtime |
|---|---|---|
| `step` | one two-phase logical tick of a run, `src/07-state-space.js:707` | process one queued message event, `src/07-graph-core.js:535` |
| `tick` | the logical time of a run (`run.tick`), `src/07-state-space.js:707` | process every event at the next real-time instant, `src/07-graph-core.js:556` |
| `run` | a run object started from a document, `startRun` `src/07-state-space.js:454` | drain the event queue, `sim.run` `src/07-graph-core.js:548` |
| `trace` | the hash-chained `.sovtrace` of a run, `traceOf` `src/07-state-space.js:726` (format `:366`) | one message's path, `sim.trace` `src/07-graph-core.js:590` |
| `query` | passive read of a run's state records, `src/07-state-space.js:916` | a graph query verb over the document, `src/07-graph-core.js:258` |
| `receipt` | the run receipt every run operation returns, `runReceipt` `src/07-state-space.js:939` | a `receipt` card's record of a message, `src/07-graph-core.js:390-391` |
| `merge` | the `merge@1` pattern and a channel's declared merge (`combine` + `order`), `src/07-state-space.js:371`, `:611` | a junction policy, one of `fanout / distribute / merge / join / select`, `src/07-graph-core.js:16` |
| `combine` | how a merge folds values on a channel (`last`, `or`, `and`, `sum` ...), `src/07-state-space.js:148`, `:371` | how a derived card or gate folds its input levels, `src/07-graph-core.js:43` (`COMBINES`), `src/03-notation-core.js:66` |
| `signal` | the binary value on a port channel, `run.signal`, `src/07-state-space.js:597` | continuous levels and the derived signal view, `src/07-graph-core.js:40`, `:464` (`levels`) |
| `replay` | re-run a trace and compare records, `src/07-state-space.js:778` | not used |

## 4. The two-way Point ruling, traces and pins

Bdo ruled on 2026-09-26 that dev `8e4892a` stands: a Point's own point is two-way (`duplex`) by default
(`src/05-data-core.js`, `defaultPortForSpec`). That changes the compact form of the `examples/state`
documents, so their document hash, run id, record ids and hash chain moved. The traces were re-recorded
through the calls the state-space tests make (the `state_space_run_qa.py` jobs; `state_space_perf_qa.py`
bench at budget 20000 with `bench.inputs.json`, and grow at budget 30000). The trace guard
(`contracts/trace_guard.py`, blanking only hash-derived fields and comparing with `f6e312d`) prints
`12/12 traces pass the guard`.

| Trace | Old head | New head |
|---|---|---|
| `and.00` | `c29c7842f3fc215f1e3f29dc04dfdf80245bc0c3945114d7e2324264f6d020cd` | `03cc6f9bbac534166753fe4d761812ae50c962ac278b4be521b2083388a36ad3` |
| `and.01` | `06085debd9619285c4fdbe4d1de7311447b0b43721bb87902da7d512590eb6a9` | `1b7baa407d18f16885871eae7b67ce8445adc80ae75c8a02f865c4baf443349e` |
| `and.10` | `79d967ecdf9e27c7f25a64964eef4881c094ddb2a744a63ddb1528339e3586c2` | `de429e78cd5e697d1692a6bd24897dafc344cf3a86061ea42215597a4a49bc84` |
| `and.11` | `ebbe386b5ebe5fb83c63fa47bc0534a4f96c35581970d5bd6aa3fce2a87338d8` | `581f3c798aed779827f82a13c79a4c18286ec6d2763e5406c54fe1617fd7e9ec` |
| `bench` | `b8f10cc8c36b9ebd41d6fbd363fd5f2dd13400c5da29fc670d1198cfc26136dc` | `dbe9fdf4f4ab7cf0c961579dd75704f0bcbaa2fac73f9fd02de76fc5247e2d9c` |
| `grow` | `10684bd2a76cc682e7580586f4e6611e2fb5a613b3bd191a7389781b9d71745e` | `dd5c7e4eba170ce7e0d6483e473858d25eae4eb1f234634ad727acedb8d837cc` |
| `merge.declared` | `a160412cfd857c74ea4b45115026f9e11ce878bd7b9689ef5726cb27fadcb3f6` | `3082730a147ce93b57b7f37d40e4beaf470b4b1bce6e62a53c5023fff70b259d` |
| `merge.or` | `bb314bde6417b6f0bd0bb446c672cfbc163a1644026b479627d3eb68fc28d27e` | `9d1ee4be174de61c74ce100f65fb6c5fa28b7451291b1287853668c424bf38cc` |
| `merge.stochastic` | `42643bcdecfd533efed8cb64d3d75f5c1ef32607c40481a5569b30471f6b603f` | `f3e3fdf3fca44c695a7fc8c450500501cfec1ed1386fdf031a96691e318d5957` |
| `not-loop` | `154864b00b5f09b2997f88fef70c20415ad0d6aa31e99ae4ee4982c55131087d` | unchanged (no Point without declared flow) |
| `not.0` | `bcbede2b33c7eabd26620ad8059ee003ff5482955da193384be80d21c7e6bd96` | `df5e0de5f73a961130552fd7cb54a89a944115296c9f69ae43c6864e51a07b01` |
| `not.1` | `87eafd9217a46af56ae077d1f2eb96d2203b308f4a075cefc242b91b05a9e108` | `d632b252d779111ceb523729bfdbc8e5d0e64066e31fd8513e315ed66f08746a` |

Pins recomputed in `tests/declared_ports_qa.py` `COMPACT_HASHES`, with the unchanged pin code. Every
other pin (01, 02, 05, `blank`, `state/not-loop`) kept its value and still matches. `examples/swarm/*`
has no pin: the pin set is `examples/*.sov` and `examples/state/*.sov`, and dev's own
`tests/swarm_originals_qa.py` pins pass unchanged.

| Example | Why | Old | New |
|---|---|---|---|
| `03-contained-stage` | modified on dev | `967a85e9c65922b7acc2b7059d064f49411f1c247b8467aae15764d693ea497a` | `7ce534e8f8667c8607aeda6a2d43218c55960d22b65bd43f1e4e26cc4afac76e` |
| `04-boundary-port` | modified on dev | `07c55423ef8cd7f64782846913904d76fed7aae85c13d2b13558164ce793bff3` | `cb4b5855386a9134d6c760ad5f005d315b26b46ec25238a1af520624263ed771` |
| `06-read-write-evidence` | modified on dev | `9dd86dd27f104d07f7e621a33895dad6f7be4ae0c9e6ad35670f0444e5e202fd` | `a7421e628c6768a88486f8563357a4dbd1999942d03a0e0247123c1c600f8974` |
| `07-plane-with-points` | modified on dev | `f4b02c71f1325791cd31c96461ade1352c14edd8f6ab38fce2c100b2c1ca5362` | `2f1b0581d0023af090348c99f3068ef1f321b4bd81a38cb4387218ff05efd7cf` |
| `08-gated-service` | modified on dev | `8533d19c195e349fcc583372b6f92c65fd9b3ecd3c9b39249d2acdfa96c80933` | `ed2e6c8878e672fb67c175b6c75d726fe5195879a6ede7a68cc09aaee28fc4a1` |
| `09-print-ai-proof-run` | added on dev | none | `1df300a574a517cc0650283cfe3b9dada19c52ef9ec2898560ffb4a28d1516b8` |
| `09-proposed-service-review` | added on dev | none | `24814d24173f6be4a4260f48986ee259b05b64ec896289511d27152d31f70296` |
| `10-clocked-signals` | added on dev | none | `a9a88907e855171c205d6fb221f96334eaf5b510e310585205c5b576e8646919` |
| `11-sections` | added on dev | none | `cf375a292c5d2f419fc581f5b49986ba968db8cb177441a42f8dec80885c92a0` |
| `12-membrane` | added on dev | none | `1c6e3971833dd6dc65281a5e91c0e67f489005a139eb59d18292fb62455a642f` |
| `13-half-adder` | added on dev | none | `a3e71695182edee932682b330b472c4459b49f195603bc0f561c538c47da0a86` |
| `state/and` | two-way Point | `c8db904a557ff9c2b5f53b8edcbf06f984472685c9a33fa5dc3e92c4138a1b4f` | `390703c8dd0b25a52cc09f2ccda372428af5e28c3b7a740af0273a0cb6b6479a` |
| `state/merge` | two-way Point | `ac82f767cd90b6bf6628f24ec480c0099288fc4e259062b7d666167842ec2d38` | `689afb77532fb9e25cc676458643f8348b7a3871a26894494517416bb2b749ed` |
| `state/merge.or` | two-way Point | `1faa851f526622cf44bbf66398a52dcc077bf92a4daf56d94d1996bc4dcb417b` | `3b684d32315c30c03201e36fd43519dc6dfbcc26e17b2feded411f01a2073cf8` |
| `state/merge.stochastic` | two-way Point | `1a6ef98b5fcd3228571d11d6e96da8425959da7ebf68aec713c88113a46c0c10` | `66d44b0cdbe2208ab8e37aaa91a054101c3032115f3096fcbe7074f50e0235eb` |
| `state/not` | two-way Point | `b2a3cfece5eec2af2e4696bec7b15ebdd148b90e58b682f78e71852222a1c2fd` | `76331308e3a671751161c2cadf075da79dfc5a2ec0e2e0706afd6fc6e3b0aa05` |

## 5. Portability fixes (Windows)

From `892eb64`, before the merge:

- `build.py`: `index.html` and `desktop/dist/index.html` are written with `newline='\n'`; text mode on
  Windows turned every LF into CRLF, so each build rewrote `index.html` whole.
- `tests/declared_ports_qa.py`, `tests/state_space_contracts_qa.py`: example keys are
  `relative_to(ROOT).as_posix()`; `str()` gave `examples\01-source-hold.sov` on Windows, which never
  matched the `COMPACT_HASHES` keys.
- `tests/author_offline_qa.py`, `tests/mutation_watch.py`, `tests/performance_regression_qa.py`,
  `tests/state_space_surfaces_qa.py`, `tests/visual_journey_map.py`, `tests/visual_theme_duplex_qa.py`:
  every `write_text` passes `newline='\n'`.

After the merge:

- `tests/server_render_qa.py`: `mcp/server.mjs` spawns `python3` unless `SOV_RENDER_PYTHON` is set, and
  this machine has no `python3` (`spawn python3 ENOENT`); the test now sets it to `sys.executable` when
  unset.

## 6. Three suites fail on Windows font metrics

These fail on `dev` at `0cd9831` itself on this Windows machine (checked on a plain export of dev) and
pass on CI (`ubuntu-latest`). They and their thresholds are untouched.

- `tests/layout_quality_qa.py`: `examples/13-half-adder.sov` scores 8.8 (`text-collision: 2, crossing: 1`).
- `tests/layouts_qa.py`: the same example, `"Sum gate" overlaps "a ⊕ b"`, `"Carry gate" overlaps "a · b"`.
- `tests/authoring_review_qa.py`: `(768, 'light', [['labels', 'submit', 'request']])`.

`tests/layout_quality_qa.py` also builds its example keys with `str()`, so on Windows it reports
`examples\13-half-adder.sov`; that is only a label.

## 7. No .gitattributes

The repository has no `.gitattributes`. A checkout with `core.autocrlf=true` rewrites the text files
as CRLF, and every byte-hash golden (the `.sovtrace` files, which tests compare byte for byte, and any
hash over file bytes) then fails. This task's worktree uses `core.autocrlf=false`. Only
`tests/fixtures/swarm-originals/.gitattributes` exists (from dev). Close by adding a root
`.gitattributes` that pins `*.sov`, `*.sovtrace`, `*.json` and the sources to LF.

## 8. Glyph terminals now count as template ports (unchecked)

In the merge, dev's glyph terminal points (a gate card's `a`, `b`, `y`) are returned by
`templatePointSpecs` in `src/06-attachment-core.js`, beside the runtime's declared template ports. So
the runtime's load cleaning (`cleanStoredPorts` in `src/05-data-core.js`) treats glyph terminals as
template ports: an authored port that collides with a terminal is dropped on load unless a bound Wire
still needs it.

No example in the repository has a gate card with authored ports, so this is unchecked against real
data. A synthetic probe (an `and2` card with authored `extra` on the bottom and a colliding `a` on the
top, and a Wire bound to `a`) gave: points `a`, `b`, `y`, `extra`; the colliding `a` dropped; the Wire
stays on the terminal `a`; `extra` saved as authored. That is the runtime's collision rule applied to
terminals, which is our reading of the intent, not a tested requirement.
