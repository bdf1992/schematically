# concern:schematically/golden-rendered-text — execution report

Branch: `claude/movement-72-hours-2claax`, cut from `origin/dev` at `6e0fe55`.
Nothing pushed, no pull request opened.

## 1. What changed, file by file

**`tests/golden_rendered_text_qa.py`** (new, 144 lines).
The check. It opens every `examples/*.sov` in the standalone build through
`SovSchematicAPI.file.open`, then reads back every `<text>` node the renderer put on the
workspace SVG as a triple `[owner, class, text]` — owner being `component:<id>` or
`wire:<id>` resolved by `closest('[data-id],[data-wire-id]')`. It compares that reading
to `tests/golden-rendered-text.json`, reporting every text node expected and not drawn
and every text node drawn and not expected. It also renders each document a second time
and asserts the reading is unchanged, and it fails on any page error.

Two guards make the comparison hard to satisfy vacuously:

- `CAPTION_ANCHOR` is held by hand in the test file, not derived from any run. It
  asserts that `09-typed-captions.sov` draws `ACT`, `GATE`, `HOLD` and `Receipt` as
  component labels. Regenerating the expectation file from a broken build does not
  silence it.
- The comparison is symmetric over the union of document names, so a corpus document
  missing from the expectation, or an expectation entry with no corpus document, is a
  failure rather than a skip.

`--update` rewrites the expectation file after an intended rendering change.

**`tests/golden-rendered-text.json`** (new, 526 lines).
The expectation: 10 documents, 101 text nodes, generated with `--update` on this branch.

**`examples/09-typed-captions.sov`** (new).
A corpus document that exercises the caption path. Four typed Components — `act`,
`gate`, `hold`, `receipt` — three wires, one wire label on two of them. The first three
Components author `"label": ""` and **author no `labelMode` at all**, so the only text
they can show is the type caption the renderer derives from the symbol. The fourth
authors `"label": "Receipt"`, so an authored label still winning is covered too.

Authoring no `labelMode` is the load-bearing detail. At `1f213c7` the normalizer keeps an
authored mode and `effectiveLabelMode` only falls back when none was authored; a document
that wrote `"labelMode": "boundary"` would have rendered its caption at `1f213c7` too and
the check would not have failed there.

**`scripts/qa.py`** (1 line added).
`tests/golden_rendered_text_qa.py` registered in `BROWSER`, immediately after
`tests/agent_api_mcp_golden_qa.py`. It therefore runs under `python scripts/qa.py`,
under `--quick`, and in `.github/workflows` CI, which invokes `python scripts/qa.py`.

**`examples/README.md`** (1 line added).
Describes `09-typed-captions.sov` and names the suite that reads it.

**`MODULE-QA.md`** (2 lines changed).
The regression gate said `golden corpus: PASS — 7/7 documents`; the corpus already held
nine `.sov` files before this work and holds ten with mine, so that line was already
stale and my change made it staler. Corrected to `10/10` and a
`golden corpus rendered text` line added beside it.

Nothing under `src/` changed. This is a check, not a behavior change.

## 2. Commands and their real output

Environment note: `playwright` was not importable in this container
(`ModuleNotFoundError: No module named 'playwright'`) although the browsers were present
at `/opt/pw-browsers`. I ran `pip install playwright==1.57.0`, the exact pin already in
`requirements-dev.txt`. I did not run `playwright install`.

### (a) Passes on the current tree

```
$ cd /home/user/schematically
$ CHROMIUM_PATH=/opt/pw-browsers/chromium python3 scripts/qa.py --quick
```

Exit status `0`. The relevant lines, verbatim:

```
PASS offline author skill QA (7 json, 0 sov, 2 refused fences; 10 examples)
QA PASS tests/author_offline_qa.py (0.34s)
...
PASS Browser/API/MCP agent golden parity QA
QA PASS tests/agent_api_mcp_golden_qa.py (1.43s)
PASS golden rendered text QA (10 documents, 101 text nodes)
QA PASS tests/golden_rendered_text_qa.py (4.07s)
...
GOLDEN PASS: 10 documents
QA PASS scripts/golden_run.py (0.62s)
RC QA PASS: 37 suites + 17 JS syntax checks (92.42s test time)
```

The suite alone, run three times back to back to show the reading is stable:

```
$ for i in 1 2 3; do CHROMIUM_PATH=/opt/pw-browsers/chromium python3 tests/golden_rendered_text_qa.py; done
PASS golden rendered text QA (10 documents, 101 text nodes)
PASS golden rendered text QA (10 documents, 101 text nodes)
PASS golden rendered text QA (10 documents, 101 text nodes)
```

### (b) Fails at 1f213c7

`1f213c7` predates the check, so the check, its expectation and its corpus document are
copied into a worktree of that commit. Nothing else is copied — `index.html` is rebuilt
from that commit's own `src/`.

```
$ cd /home/user/schematically
$ git worktree add --detach /tmp/.../regr 1f213c7
Preparing worktree (detached HEAD 1f213c7)
HEAD is now at 1f213c7 fix: a primitive's label is drawn once it exists (#16)
$ cp tests/golden_rendered_text_qa.py tests/golden-rendered-text.json /tmp/.../regr/tests/
$ cp examples/09-typed-captions.sov /tmp/.../regr/examples/
$ cd /tmp/.../regr && python3 build.py
/tmp/.../regr/index.html
$ CHROMIUM_PATH=/opt/pw-browsers/chromium python3 tests/golden_rendered_text_qa.py; echo "EXIT=$?"
FAIL 09-typed-captions.sov: expected rendered text ['component:src', 'component-label', 'ACT'] and it was not drawn
FAIL 09-typed-captions.sov: expected rendered text ['component:check', 'component-label', 'GATE'] and it was not drawn
FAIL 09-typed-captions.sov: expected rendered text ['component:store', 'component-label', 'HOLD'] and it was not drawn
FAIL 09-typed-captions.sov: rendered text differs from the expectation
FAIL     expected and not drawn: ['component:src', 'component-label', 'ACT']
FAIL     expected and not drawn: ['component:check', 'component-label', 'GATE']
FAIL     expected and not drawn: ['component:store', 'component-label', 'HOLD']
EXIT=1
```

That is the whole failure. Every other corpus document renders identical text at
`1f213c7` and on `dev`, so the check is not failing on incidental drift between the two
trees — it is failing on exactly the three captions the regression stopped drawing.

### (b′) Passes again at the repair commit

Same procedure at `31bbe4e`, the commit whose message says it "repairs a regression from
the previous commit: `effectiveLabelMode` returned 'none' for a typed Component with no
label, so the type caption stopped rendering":

```
$ git worktree add --detach /tmp/.../repair 31bbe4e
HEAD is now at 31bbe4e fix: one applySymbol types a component on every surface (#17, #19)
$ cp tests/golden_rendered_text_qa.py tests/golden-rendered-text.json /tmp/.../repair/tests/
$ cp examples/09-typed-captions.sov /tmp/.../repair/examples/
$ cd /tmp/.../repair && python3 build.py >/dev/null
$ CHROMIUM_PATH=/opt/pw-browsers/chromium python3 tests/golden_rendered_text_qa.py; echo "EXIT=$?"
PASS golden rendered text QA (10 documents, 101 text nodes)
EXIT=0
```

Fail at the break, pass at the repair, pass on `dev`. The check tracks the defect, not
the tree.

### Extra: the check kills a label-drop mutant on the current tree

To show it asserts something meaningful about `dev` and not only about a three-day-old
branch, I mutated the renderer in a throwaway worktree of `origin/dev` so component text
is never drawn (`if(false&&p.labelMode!=='none'&&label){`):

```
$ cd /tmp/.../mutant && python3 build.py >/dev/null
$ CHROMIUM_PATH=/opt/pw-browsers/chromium python3 tests/golden_rendered_text_qa.py
FAIL 09-typed-captions.sov: expected rendered text ['component:src', 'component-label', 'ACT'] and it was not drawn
FAIL 09-typed-captions.sov: expected rendered text ['component:check', 'component-label', 'GATE'] and it was not drawn
FAIL 09-typed-captions.sov: expected rendered text ['component:store', 'component-label', 'HOLD'] and it was not drawn
FAIL 09-typed-captions.sov: expected rendered text ['component:log', 'component-label', 'Receipt'] and it was not drawn
FAIL 01-source-hold.sov: rendered text differs from the expectation
FAIL     expected and not drawn: ['component:c1', 'component-label', 'Source']
FAIL     expected and not drawn: ['component:c2', 'component-label', 'Hold']
FAIL 02-duplex-buffer.sov: rendered text differs from the expectation
...
EXIT=1
```

The mutant worktree was discarded; nothing from it is on the branch.

### Reproducing (b) from a clean checkout of this branch

```
git worktree add --detach /tmp/regr 1f213c7
cp tests/golden_rendered_text_qa.py tests/golden-rendered-text.json /tmp/regr/tests/
cp examples/09-typed-captions.sov /tmp/regr/examples/
cd /tmp/regr && python3 build.py
CHROMIUM_PATH=/opt/pw-browsers/chromium python3 tests/golden_rendered_text_qa.py
```

`1f213c7` is on `origin/claude/astra-gtp-scalability-6eus65`, not on `dev`; `git fetch
--all` first if the commit is not local.

## 3. Is the closure condition met

Yes, on the evidence above.

- (a) The check is in the QA suite (`scripts/qa.py` `BROWSER`) and passes on
  `origin/dev` plus my three added files. `python scripts/qa.py --quick` exits `0`.
- (b) The check fails at `1f213c7` with exit `1`, and the failure is the three typed
  captions.
- The defeating condition does not hold: the check does not pass at `1f213c7`, and it
  asserts real rendered text — 101 text nodes across ten documents, plus a hand-written
  caption anchor independent of the generated expectation, and it kills a mutant that
  stops drawing component text on the current tree.

One honest qualification. The gap was not that the corpus was rendered and uncompared;
it was that nothing compared rendered text **and** the corpus contained no document that
could expose the caption path — every existing example labels every component, so at
`1f213c7` all eight of them render exactly the text they render on `dev`. Closing the
gap therefore required extending the corpus, not only adding a comparison. A reviewer who
runs the check at `1f213c7` against the eight pre-existing documents alone will see it
pass. `examples/09-typed-captions.sov` is what makes (b) true, and it is part of the
change under review rather than a pre-existing artifact.

## 4. Decisions the definition did not settle

- **Extend the corpus rather than only compare it.** Reasoning above. The alternative —
  comparing only the eight existing documents — cannot satisfy (b).
- **What "rendered text" means.** Every `<text>` node under the workspace SVG: component
  labels and captions, wire connection labels, endpoint channel tags, packet tags,
  reciprocity marks, duplex badges. Not the palette, inspector or any chrome outside the
  canvas. Not text geometry, font, colour or position — this is a text check, and
  `tests/visual_theme_duplex_qa.py` and the screenshot suites already own appearance.
- **Compare with owner and class, not a flat string.** `['component:src',
  'component-label', 'ACT']` fails loudly if the same text moves to a different element
  or a different owner; a flat bag of strings would not.
- **Where the expectation lives.** A checked-in JSON beside the suite, matching how the
  repository already stores `tests/beta15-visual-results.json` and
  `tests/performance-results.json`.
- **`--update` exists.** A rendering change that is intended must be cheap to bless, or
  the suite gets deleted the first time it is inconvenient. The caption anchor is the
  counterweight: `--update` cannot bless away the regression this concern is about.
- **A stability assertion inside the suite.** Each document is read, re-rendered, and
  read again; the two readings must match. Packet tags are animated, and I wanted the
  suite to say so rather than flake in CI. It has been stable across every run here.
- **Correcting `MODULE-QA.md`.** Judgement call; the count was already wrong and I made
  it wronger. I changed two lines and nothing else in that file.

## 5. What blocked me, was missing, or was wrong

- **`playwright` was not installed** in this container even though
  `/opt/pw-browsers/chromium` was. Every browser suite dies at import. I installed the
  pinned `playwright==1.57.0` from `requirements-dev.txt`. Not a repository defect, but a
  reviewer re-running these commands in a fresh container will hit it first.
- **`MODULE-QA.md` regression gate was stale** before I touched it: `golden corpus: PASS
  — 7/7 documents` against a corpus of nine `.sov` files. Corrected as part of this change.
- **`scripts/golden_run.py` is thin.** It parses each example as JSON, asserts
  `components` and `wires` are lists, checks `mcp/tools.json` is non-empty, and runs
  `node --check`. It never loads a document into the app. That is the shape of the gap
  this concern names, and I left `golden_run.py` alone rather than growing it — the new
  suite needs a browser and belongs in `BROWSER`, not in `TAIL`.
- Nothing blocked the work. Both halves of the closure condition were demonstrable.

## 6. What I did not do

- Did not push, did not open a pull request, did not touch `dev` or `main`.
- Did not change any file under `src/`. No product behavior changed.
- Did not add a mutant to `tests/mutation_watch.py`. The label-drop mutant in section 2
  was a throwaway demonstration; making it a permanent entry in the mutation gate is a
  reasonable follow-on and is not in this change.
- Did not compare rendered geometry, style, colour or layout — only text, its owner and
  its class.
- Did not extend the check to `.sovpak` packages (`examples/blank.sovpak`,
  `examples/classic-reference.sovpak`). It reads `examples/*.sov` only.
- Did not backfill corpus documents for other rendered-text paths that no example
  currently exercises: reciprocity marks (`RETURN!` / `RETURN?`), the internal annotation
  text, and inline components hosted on a wire are unrepresented in the expectation
  because no corpus document produces them.
- Did not run the non-`--quick` suite. `--quick` skips `drag_lifecycle_stress_qa.py` and
  `performance_regression_qa.py`, neither of which this change touches.
- Did not re-generate `examples/*.svg` exports.
