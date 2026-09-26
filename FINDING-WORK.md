# Independent finding — golden-corpus rendered-text check

Subject: branch `claude/movement-72-hours-2claax` at `fb56f9c`, two commits on top of
`origin/dev` at `6e0fe55`. Builder's account: `LAP-EXECUTION-REPORT.md`.

I did not build this and did not repair it. Everything below is output I produced myself,
in trees I materialised with `git archive` from the subject repository. I created no git
worktrees and changed no tracked file; `git status` in the subject repository is clean
apart from this report.

## 1. Verdict

**MET WITH QUALIFICATION.**

Both halves of the closure condition hold, reproduced exactly.

- (a) The check is registered in `scripts/qa.py` `BROWSER` and
  `CHROMIUM_PATH=/opt/pw-browsers/chromium python3 scripts/qa.py --quick` exits `0` on
  the branch tree.
- (b) The check fails at `1f213c7` with exit `1`, on exactly the three captions the
  regression stopped drawing, and passes again at the repair commit `31bbe4e`.

The defeating condition does not hold. The check does not pass at `1f213c7`, and it is
not vacuous on `dev`: it compares 101 exact `[owner, class, text]` triples, it kills the
`1f213c7` defect **reintroduced into the current `src/`** rather than only the historical
commit, it kills a change to the caption text itself, it refuses a corpus document added
without an expectation and an expectation without a corpus document, and its hand-written
`CAPTION_ANCHOR` survives `--update` run against the broken build.

The qualification has three parts, in descending order of how much they matter.

**Q1 — the check compares the DOM, not the picture.** I made every typed-Component
caption in the corpus invisible while leaving the text nodes in place. The check passed,
and so did the entire `--quick` suite. That is the same user-visible symptom the concern
names — typed captions stop appearing — reached by a different mechanism, and it walks
through green. Section 4 of the builder's report scopes this honestly ("Not text
geometry, font, colour or position"). The commit subject does not: *"the golden corpus is
compared by what it draws, not only what it says"*, and the suite docstring's *"what a
document shows"*, both claim more than the check does. What was closed is a rendered-**text**
check. What the words claim is a rendered-**appearance** check.

**Q2 — the thing that makes (b) true is unguarded, and the product itself erases it.**
`examples/09-typed-captions.sov` discriminates only because its components author no
`labelMode`. Nothing asserts that. I added `"labelMode": "boundary"` to its four
components and the check stayed green on `dev` *and* went green at `1f213c7`. Worse, that
is not a hypothetical edit: I opened the document in the current build and read it back
through `SovSchematicAPI.file.document()`, and the app returns `labelMode: boundary` on
all four. Any routine open-and-resave of the corpus disarms the check's whole reason for
existing, silently, with every suite still passing.

**Q3 — (b) rests on a document shipped in the same change.** Reproduced: at `1f213c7`
against the nine pre-existing documents, with the anchor removed, the check passes. The
builder states this plainly rather than hiding it. I judge it legitimate — argued in
section 5 — but it is the reason this is a qualified verdict rather than a clean one.

## 2. Claims I reproduced

### (a) passes on the branch tree

```
$ cd /home/user/schematically
$ CHROMIUM_PATH=/opt/pw-browsers/chromium python3 scripts/qa.py --quick
...
PASS golden rendered text QA (10 documents, 101 text nodes)
QA PASS tests/golden_rendered_text_qa.py (3.77s)
...
GOLDEN PASS: 10 documents
QA PASS scripts/golden_run.py (0.60s)
RC QA PASS: 37 suites + 17 JS syntax checks (93.12s test time)
EXIT=0
```

### (b) fails at 1f213c7

I did not use a git worktree. I extracted the commit with `git archive`, copied in the
three files under review, and rebuilt `index.html` from that commit's own `src/`.

```
$ git archive 1f213c7 | tar -x -C $S/regr
$ cp tests/golden_rendered_text_qa.py tests/golden-rendered-text.json $S/regr/tests/
$ cp examples/09-typed-captions.sov $S/regr/examples/
$ cd $S/regr && python3 build.py
$ CHROMIUM_PATH=/opt/pw-browsers/chromium python3 tests/golden_rendered_text_qa.py
FAIL 09-typed-captions.sov: expected rendered text ['component:src', 'component-label', 'ACT'] and it was not drawn
FAIL 09-typed-captions.sov: expected rendered text ['component:check', 'component-label', 'GATE'] and it was not drawn
FAIL 09-typed-captions.sov: expected rendered text ['component:store', 'component-label', 'HOLD'] and it was not drawn
FAIL 09-typed-captions.sov: rendered text differs from the expectation
FAIL     expected and not drawn: ['component:src', 'component-label', 'ACT']
FAIL     expected and not drawn: ['component:check', 'component-label', 'GATE']
FAIL     expected and not drawn: ['component:store', 'component-label', 'HOLD']
EXIT=1
```

Byte-identical to the report's quoted failure. Only `09-typed-captions.sov` failed, so
the other nine documents do render identical text at `1f213c7` and on `dev`, as claimed.

### (b′) passes at the repair commit 31bbe4e

```
$ git archive 31bbe4e | tar -x -C $S/repair   # same three files copied in, rebuilt
$ CHROMIUM_PATH=/opt/pw-browsers/chromium python3 tests/golden_rendered_text_qa.py
PASS golden rendered text QA (10 documents, 101 text nodes)
EXIT=0
```

### The regression mechanism is what the report says it is

`git show 1f213c7:src/05-data-core.js` and `git show 31bbe4e:src/05-data-core.js` differ
by one line inside `effectiveLabelMode`:

```
+    // A typed Component always has something to show: its type caption when no label is set.
+    if(!isPrimitiveSymbol(component?.symbolId))return 'boundary';
     return cleanString(config.label,'').trim()?defaultLabelMode(component?.form):'none';
```

and the line above it is `if(LABEL_MODES.includes(authored))return authored;`. So the
report's load-bearing claim is exactly right: a document that authored
`"labelMode": "boundary"` would have rendered its caption at `1f213c7` too, and would not
have failed there.

### `--update` cannot bless the regression away

```
$ cd $S/upd                     # 1f213c7 tree, suite + expectation + doc copied in
$ python3 tests/golden_rendered_text_qa.py --update
UPDATED golden-rendered-text.json (10 documents)
$ python3 tests/golden_rendered_text_qa.py
FAIL 09-typed-captions.sov: expected rendered text ['component:src', 'component-label', 'ACT'] and it was not drawn
FAIL 09-typed-captions.sov: expected rendered text ['component:check', 'component-label', 'GATE'] and it was not drawn
FAIL 09-typed-captions.sov: expected rendered text ['component:store', 'component-label', 'HOLD'] and it was not drawn
EXIT=1
```

`CAPTION_ANCHOR` does the work it is claimed to do.

### The symmetry guards fire

On a copy of the branch tree:

```
$ cp examples/01-source-hold.sov examples/10-extra.sov
FAIL 10-extra.sov: rendered by the corpus and absent from the expectation      EXIT=1
$ rm examples/03-contained-stage.sov
FAIL 03-contained-stage.sov: in the expectation and absent from the corpus     EXIT=1
$ rm examples/09-typed-captions.sov
FAIL 09-typed-captions.sov: corpus document is missing                         EXIT=1
```

Deleting the anchor document is caught by the anchor, not only by the symmetry.

### Stability

Five consecutive standalone runs on the branch tree, no flake:

```
PASS golden rendered text QA (10 documents, 101 text nodes)   x5
```

### File-level claims

All verified against `git diff 6e0fe55..HEAD`.

- `scripts/qa.py`: exactly one line added, `'tests/golden_rendered_text_qa.py',` after
  `agent_api_mcp_golden_qa.py`, inside `BROWSER`. `.github/workflows/ci.yml:27` runs
  `python scripts/qa.py`, so CI picks it up.
- `tests/golden_rendered_text_qa.py`: 144 lines. `tests/golden-rendered-text.json`:
  526 lines, 10 documents, 101 nodes summing exactly.
- `MODULE-QA.md`: `7/7` was stale — `git ls-tree 6e0fe55 examples/` shows **nine** `.sov`
  files at the branch base. The correction to `10/10` is right.
- `examples/README.md`: one line added.
- Nothing under `src/` changed.

### The document is a real corpus member, not a private fixture

Every other corpus-reading suite consumes it and passes: `author_offline_qa` reports
`10 examples`, `svg_export_qa` reports `10 documents`, `golden_run.py` reports
`GOLDEN PASS: 10 documents`.

## 3. Claims I could not reproduce

**One, and it is small.** Report section 6 states that reciprocity marks
(`RETURN!` / `RETURN?`) "are unrepresented in the expectation because no corpus document
produces them." `02-duplex-buffer.sov` produces one and it is in the expectation:

```
['wire:k1', 'reciprocity-mark', 'RETURN?']
```

Only `RETURN!` is absent. The `internal-text` half of the same sentence is correct — no
corpus document produces it.

Everything else in the report reproduced. I found no overstated evidence, no unrun
command presented as run, and no output that differs from what I got.

One limit on my independence: `playwright==1.57.0` is already installed in this container
at `/usr/local/lib/python3.11/dist-packages/playwright`, put there by the builder. My runs
are independent of the builder's *tree* — I rebuilt every tree from `git archive` — but
they share the builder's *container*. I did not run `playwright install`, and I did not
need to install anything.

## 4. Defects

### D1 — the check passes with every caption invisible (evidence: a surviving mutant)

Applied to a clean copy of the branch tree, `src/55-render.js`, one line:

```
-    t.textContent=label;g.appendChild(t);
+    t.textContent=label;if(!customLabel)t.setAttribute('opacity','0');g.appendChild(t);
```

That renders every type caption — ACT, GATE, HOLD, and every caption in the other nine
documents — completely invisible on the canvas, while authored labels stay visible. Then:

```
$ python3 build.py && CHROMIUM_PATH=... python3 tests/golden_rendered_text_qa.py
PASS golden rendered text QA (10 documents, 101 text nodes)
$ CHROMIUM_PATH=... python3 scripts/qa.py --quick
RC QA PASS: 37 suites + 17 JS syntax checks (92.39s test time)
M3_QA_EXIT=0
```

The whole suite is green with the concern's own symptom present.

The neighbouring suite does not cover it either. `tests/svg_export_qa.py:33` builds its
expectation as `labels = [c.get('config', {}).get('label') ...]` filtered to truthy — it
asserts **authored labels only** and never asserts a type caption. I confirmed the
boundary: a blunter mutant that hides *all* component text via `.component-label{display:none}`
in `styles/app.css` *is* caught, by `svg_export_qa` (`AssertionError: 01-source-hold.svg:
label 'Source' not rendered`), not by the new check — which also passed that one. So the
suite catches "no component text at all" and misses "captions specifically, invisible."

This does not defeat the stated closure condition, which asks for a rendered-text check.
It defeats the commit message's stronger claim.

### D2 — the discriminating property of the new corpus document is asserted nowhere

`09-typed-captions.sov` is discriminating only because its four components author no
`labelMode`. I added the key back:

```
for c in d['components']: c['config']['presentation']['labelMode'] = 'boundary'
```

Result on the branch tree: `PASS golden rendered text QA (10 documents, 101 text nodes)`,
exit `0`. Result with that same edited document at `1f213c7`:
`PASS golden rendered text QA (10 documents, 101 text nodes)`, exit `0`.

The check keeps passing on `dev` while losing the entire property (b) rests on, and
nothing anywhere says so. `CAPTION_ANCHOR` asserts the caption *text*; it does not assert
the *authoring shape* that makes the text discriminating.

This is not a hypothetical hand edit. The current build writes that key itself. I opened
the document in the build and read it back through the agent surface:

```
$ python3 probe2.py
SAVED-BACK per component (symbolId, label, labelMode):
   act '' boundary
   gate '' boundary
   hold '' boundary
   receipt 'Receipt' boundary
  FRESH: gate '' boundary
```

`src/10-model.js:325` normalises an absent `labelMode` to `'boundary'` on load, so an
open-and-resave of the corpus — or any future corpus regeneration through the app —
neuters the check silently. A one-line guard in the suite (assert the caption components
of `09-typed-captions.sov` author no `labelMode`) would close it; I did not add one,
because repairing is not mine to do here.

The same probe shows the document does not represent output the product produces today —
every document the current build saves carries `labelMode`. It represents hand-authored
or older-build input. That is a supported category here (`skills/author-offline/SKILL.md`,
and `examples/08-gated-service.sov` is itself hand-authored), but it is worth stating
plainly rather than leaving implied.

### D3 — the report's reciprocity-mark claim is wrong

Detailed in section 3. One sentence in "What I did not do", contradicted by the
expectation file committed alongside it.

### D4 — staleness repair in `MODULE-QA.md` stopped one line short

The change corrects `golden corpus: PASS — 7/7 documents` to `10/10`. Two lines below, in
the same block, `mutation watcher: **PASS — 9/9 targeted mutants killed**` is also stale:
my run reports fourteen.

```
PASS mutation watch [('model-access-always-allows', 'test-killed'), ... 14 entries ...]
```

Minor, and arguably outside the concern. I record it because the change claims to have
repaired staleness in exactly that block.

### D5 — running the suite standalone does not rebuild (caveat, not a fault)

`scripts/qa.py` runs `build.py` before the suites, so under CI the check reads a fresh
`index.html`. Run on its own, `golden_rendered_text_qa.py` reads whatever `index.html` is
committed and would report on a stale build without saying so. The report's own
reproduction recipe includes `python build.py`, so the documented path is correct.

## 5. On whether the new corpus document is legitimate closure

The strongest case against: (b) is true only because of a file introduced by the same
change. The demonstration commit and the instrument that demonstrates against it were
authored together, so the test was, in a literal sense, built to fail where it was asked
to fail. I reproduced that dependency directly — at `1f213c7` with the nine pre-existing
documents and no anchor, `PASS golden rendered text QA (9 documents, 86 text nodes)`,
exit `0`.

The case for, which I find stronger:

1. **The corpus could not express the defect.** Every pre-existing example labels every
   component it renders text for. I checked all nine: `03`, `04` and `08` do already omit
   `labelMode` on some components, but all of those carry a non-empty `label`, so
   `effectiveLabelMode` at `1f213c7` still returned a drawing mode. No pre-existing
   document has both an empty label and no authored mode. A corpus that cannot reach a
   code path cannot be the instrument that guards it. Extending the corpus is building
   the check, not rigging it.
2. **The shape it exercises is real, not invented.** `TEMPLATE_PRESETS` in
   `src/05-data-core.js` covers `point`, `path` and `plane` only, so a typed component
   authored by hand has no preset `labelMode` and naturally carries none. `1f213c7`'s own
   commit message treats records that authored nothing as a category it deliberately
   supports ("a loaded record stays exactly as saved").
3. **The check is not tuned to one SHA.** I reintroduced the defect into the *current*
   `src/` — `src/10-model.js:325`, changing the absent-mode normalisation to
   `presentation.labelMode=(String(n.config.label||'').trim()?'boundary':'none')` — rebuilt,
   and got the identical three-caption failure with exit `1`. A test constructed only to
   pass its own historical demonstration would not catch tomorrow's reintroduction. This
   one does.
4. **It is disclosed.** The builder states the dependency in the report and again in the
   commit message rather than presenting (b) as though the pre-existing corpus produced it.

Decision: legitimate. The qualification is D2 — the document is load-bearing and its
load-bearing property is unprotected — not the fact that it was added.

## 6. What would defeat this finding

- **On (a) and (b):** a run of `scripts/qa.py --quick` on the branch tree that does not
  exit `0`, or a run of the suite at `1f213c7` (three files copied in, `build.py` run)
  that exits `0`. I got `0` and `1` respectively; a different container, a different
  Chromium, or a `--quick`-less full run could in principle differ. I did not run the
  full non-`--quick` suite — I checked that neither skipped suite
  (`drag_lifecycle_stress_qa.py`, `performance_regression_qa.py`) reads `examples/`, so I
  judge the risk low, but I did not prove it.
- **On D1:** a demonstration that the `opacity='0'` mutant is caught by some check I did
  not run — the manual visual suites (`tests/visual_theme_duplex_qa.py`,
  `tests/visual_journey_map.py`) are not in `scripts/qa.py` and I did not run them. If one
  of them catches it, D1 shrinks from "the suite misses this" to "the automated suite
  misses this."
- **On D2:** a rule elsewhere in the repository that forbids regenerating `examples/*.sov`
  through the app, or a check I did not find that pins the authored shape of corpus
  documents. I grepped the consumers of `examples/` and found none.
- **On my legitimacy ruling:** evidence that hand-authored documents omitting `labelMode`
  are not a supported input class — for instance a decision to normalise the corpus to
  app-saved form — would turn `09-typed-captions.sov` from a corpus document into a
  fixture, and the ruling in section 5 with it.
- **Generally:** I read the builder's report before running anything. I re-derived every
  number and every failure line from my own runs, but I cannot claim I would have looked
  in the same places without it.

## 7. Commands, for anyone re-taking this reading

```
cd /home/user/schematically
CHROMIUM_PATH=/opt/pw-browsers/chromium python3 scripts/qa.py --quick

S=$(mktemp -d)
git archive 1f213c7 | tar -x -C $S
cp tests/golden_rendered_text_qa.py tests/golden-rendered-text.json $S/tests/
cp examples/09-typed-captions.sov $S/examples/
cd $S && python3 build.py && CHROMIUM_PATH=/opt/pw-browsers/chromium python3 tests/golden_rendered_text_qa.py
```

For D1, on a copy of the branch tree, edit `src/55-render.js` line 71 to
`t.textContent=label;if(!customLabel)t.setAttribute('opacity','0');g.appendChild(t);`,
run `python3 build.py`, then `python3 scripts/qa.py --quick`.

For D2, on a copy of the branch tree, set `config.presentation.labelMode = "boundary"` on
all four components of `examples/09-typed-captions.sov` and run the suite on the branch
tree and at `1f213c7`. Both pass.
