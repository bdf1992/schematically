# Independent finding — the anchor guard and the merged lineage

Subject: the two things on `claude/movement-72-hours-2claax` (PR #35) that no earlier
reading covers — `e51b999`, the guard `check_anchor_documents_stay_unauthored` in
`tests/golden_rendered_text_qa.py`, and `78bcaef`, the merge that brought the reconciled
`dev` and its defect batch onto this branch. Head at reading: `78bcaef`; base `dev` at
`7b45353`.

I did not build any of it, I repaired nothing, and I committed nothing. Every counterfactual
tree was materialised with `git archive` into a scratch directory. Two edits were made to
`examples/09-typed-captions.sov` in the repository itself because the assignment asked for
them, each reverted immediately; the file's digest is
`ddcd1cacd9a2ae7320fba617f96efe8ad50f21b9` before and after both. The tracked test artifacts
the suite rewrites (`tests/beta17-read-write.png`, `tests/beta18-inline-wire.png`,
`tests/file-menu.png`, `tests/saved-test.sov`, `tests/saved-test.sovpak`) were restored.
`git status --porcelain` is empty apart from this file.

## 1. Verdict

**Merged lineage: SOUND.** The merge is complete and honest, and it is what makes the anchor
mean anything at all. `src/`, `styles/` and `index.source.html` at `78bcaef` are byte-identical
to `dev` at `7b45353`; the branch adds only its own nine files; the committed `index.html` is a
fresh build of the merged sources. The suite passes on that lineage.

**Guard: DEFECTIVE. It does not do what it says, and it does not close the finding it answers.**

`check_anchor_documents_stay_unauthored` reads `component['config']['labelMode']`. The format
does not use that key. Every read and write of a label mode in the product — the renderer, the
settings panel, the normaliser, the presets, `effectiveLabelMode` — goes through
`config.presentation.labelMode`. The guard therefore:

- **refuses a document that is still perfectly discriminating**, because the key it reads has
  no effect on anything; and
- **stays silent on the edit that actually disarms the anchor**, which is the exact edit
  `FINDING-WORK.md` performed to raise the finding (`FINDING-WORK.md:243`,
  `c['config']['presentation']['labelMode'] = 'boundary'`).

Its stated reason is also no longer true. `src/10-model.js` does not normalise `labelMode` on
load on this tree; the merge replaced that line, and the file now says the opposite.

## 2. Claims I reproduced

### The whole suite passes on this branch

```
$ cd /home/user/schematically
$ CHROMIUM_PATH=/opt/pw-browsers/chromium python3 scripts/qa.py --quick
...
PASS golden rendered text QA (10 documents, 101 text nodes)
QA PASS tests/golden_rendered_text_qa.py (3.57s)
...
GOLDEN PASS: 10 documents
QA PASS scripts/golden_run.py (0.47s)
RC QA PASS: 43 suites + 17 JS syntax checks (103.09s test time)
[exited with code 0]
```

43 suites, matching the count the PR comment reports on the merged lineage.

### The guard fires — on its own key

Written into the repository document, exactly as the assignment asked, then reverted:

```
$ python3 - <<'PY'
d['components'][0]['config']['labelMode'] = 'boundary'
PY
$ CHROMIUM_PATH=/opt/pw-browsers/chromium python3 tests/golden_rendered_text_qa.py
FAIL 09-typed-captions.sov: component:src authors labelMode 'boundary'; the anchor is disarmed because a component with an authored mode draws its caption on a broken build too. Re-author the document without it rather than blessing this.
EXIT=1
```

### The guard does not fire — on the key the format uses

Same file, same component, one level deeper, where every other `labelMode` in this repository
lives:

```
$ python3 - <<'PY'
d['components'][0]['config']['presentation']['labelMode'] = 'boundary'
PY
$ CHROMIUM_PATH=/opt/pw-browsers/chromium python3 tests/golden_rendered_text_qa.py
PASS golden rendered text QA (10 documents, 101 text nodes)
EXIT=0
```

### No false positive on the correct document

The pristine document passes, and `component:log`'s authored label `Receipt` is admitted. The
guard reads only `labelMode`, never `label`, so the defect the commit message says was found
and removed before commit is genuinely absent:

```
$ python3 -c "import sys; sys.path.insert(0,'tests'); import golden_rendered_text_qa as g; print(g.check_anchor_documents_stay_unauthored())"
[]
```

with the document reading

```
   src   label= ''        presentation.labelMode= None
   check label= ''        presentation.labelMode= None
   store label= ''        presentation.labelMode= None
   log   label= 'Receipt' presentation.labelMode= None
```

The whole `--quick` suite passing above is the same evidence at suite scale.

### The three properties the PR claims

**(1) Passes on this branch.** Quoted above, exit 0.

**(2) Fails at `1f213c7`.** `git archive 1f213c7` into a scratch tree, the suite's three files
and the corpus document copied in, rebuilt from that commit's own `src/`:

```
FAIL 09-typed-captions.sov: expected rendered text ['component:src', 'component-label', 'ACT'] and it was not drawn
FAIL 09-typed-captions.sov: expected rendered text ['component:check', 'component-label', 'GATE'] and it was not drawn
FAIL 09-typed-captions.sov: expected rendered text ['component:store', 'component-label', 'HOLD'] and it was not drawn
FAIL 09-typed-captions.sov: rendered text differs from the expectation
FAIL     expected and not drawn: ['component:src', 'component-label', 'ACT']
FAIL     expected and not drawn: ['component:check', 'component-label', 'GATE']
FAIL     expected and not drawn: ['component:store', 'component-label', 'HOLD']
EXIT=1
```

**(3) Fails when the defect is reintroduced into the current implementation.** On a copy of
`78bcaef` I deleted `src/05-data-core.js:55` — the single line `31bbe4e` added to repair the
regression, `if(!isPrimitiveSymbol(component?.symbolId))return 'boundary';` — and rebuilt:

```
FAIL 09-typed-captions.sov: expected rendered text ['component:src', 'component-label', 'ACT'] and it was not drawn
FAIL 09-typed-captions.sov: expected rendered text ['component:check', 'component-label', 'GATE'] and it was not drawn
FAIL 09-typed-captions.sov: expected rendered text ['component:store', 'component-label', 'HOLD'] and it was not drawn
...
EXIT=1
```

Three of four captions, not four: `component:log` carries `"label": "Receipt"`, so it survives
that mutation. The PR comment's own mutation (`effectiveLabelMode` returning `'none'`
unconditionally) kills all four. Either way the property holds.

The PR **body** attributes this to "current `src/10-model.js`". That file holds no such logic
on this tree — it neither derives nor writes a label mode any more. The PR comment corrects the
attribution and records the discarded first attempt; the body was never updated.

## 3. The defect, in full

### D-G1 — the guard reads a key nothing in the product uses

Every label-mode read and write in the shipped code is one level deeper than where the guard
looks:

```
src/05-data-core.js:52   const config=..., authored=config.presentation?.labelMode;
src/05-data-core.js:64   config.presentation.labelMode=defaultLabelMode(component.form)
src/10-model.js:326      if(presentation.labelMode!==undefined&&!['boundary',...].includes(...))delete presentation.labelMode;
src/55-render.js:62      labelMode=SovSchematicData.effectiveLabelMode(n)
src/70-editor-controls.js:13  mutateSelectedPresentation(p=>p.labelMode=visualLabelMode.value)
tests/golden_rendered_text_qa.py:78   authored = (component.get('config') or {}).get('labelMode')
```

A repository-wide grep for `labelMode` outside `presentation` returns the renderer's local
variable, the settings-panel writer that assigns into `presentation`, and the guard. Nothing
reads `config.labelMode`. The JSON schemas under `formats/` do not describe `config` at all, so
they neither bless nor forbid either spelling; the code is the only authority, and it is
unambiguous.

The consequence is not that the guard is merely useless. It is inverted, and both halves are
demonstrable at `1f213c7`, where a disarmed anchor is a passing anchor.

**The key the guard reads does not disarm anything.** With `config.labelMode: "boundary"` on
all four components, at `1f213c7`, the captions the regression stopped drawing are still not
drawn:

```
guard says: ["09-typed-captions.sov: component:src authors labelMode 'boundary'; the anchor is disarmed ..."]
captions actually drawn at 1f213c7 with config.labelMode set:
   ['component:log', 'component-label', 'Receipt']
```

The guard refuses the document, and its refusal message states a fact that is false about the
document it is refusing.

**The key the guard ignores disarms completely.** With
`config.presentation.labelMode: "boundary"` on all four components, at `1f213c7`:

```
PASS golden rendered text QA (10 documents, 101 text nodes)
EXIT=0
```

That is `FINDING-WORK.md` D2 reproduced unchanged, on a tree carrying the guard that answers
it. The suite passes on the broken build, and the guard says nothing.

### D-G2 — the hazard the commit names walks past the guard in the tree it was committed to

`e51b999`'s message: *"src/10-model.js normalises labelMode on load … any open-and-resave of
the corpus writes one into the file and silently disarms this suite."* That was true of the
pre-merge lineage. `src/10-model.js:325` there read
`if(!['boundary','inside','outside','none'].includes(presentation.labelMode))presentation.labelMode='boundary';`

So I performed the hazard against the guard's own tree — `git archive e51b999`, open the corpus
document in that build, write `file.document()` straight back over it, run the suite:

```
resaved through the build; labelMode now in the file at: [('src','boundary',None), ('check','boundary',None), ('store','boundary',None), ('log','boundary',None)]
=== suite in that resaved tree (guard is present at e51b999) ===
PASS golden rendered text QA (10 documents, 101 text nodes)
EXIT=0
```

The tuples are `(id, presentation.labelMode, config.labelMode)`. The resave writes the mode
where the format keeps it and leaves the guard's key empty, so the guard is silent on the one
event it was written to catch. The commit says the property "is now checked". It is not; a
neighbouring key is.

The proof recorded in that commit — *"writing 'boundary' onto one component and reading the
refusal"* — used the guard's own spelling, so it could only confirm the guard's assumption
about itself. `FINDING-WORK.md:243` states the correct path on the same branch, three commits
earlier.

### D-G3 — the guard's stated reason is no longer true after the merge

`78bcaef` brought in the repair, and with it a `src/10-model.js` that no longer writes a mode.
Line 325 there now reads *"The label mode is read through SovSchematicData.effectiveLabelMode;
an absent one is derived, never written."* I confirmed it against the running build rather than
the source. Opening the corpus document in the current build and reading it back:

```
TREE /home/user/schematically
SAVED-BACK per component (id, symbolId, label, presentation.labelMode, config.labelMode):
   src   act     ''         presentation.labelMode= None config.labelMode= None
   check gate    ''         presentation.labelMode= None config.labelMode= None
   store hold    ''         presentation.labelMode= None config.labelMode= None
   log   receipt 'Receipt'  presentation.labelMode= None config.labelMode= None
  FRESH gate     ''         presentation.labelMode= None config.labelMode= None
```

The same probe at `e51b999` returns `'boundary'` on all five lines. So the docstring in
`tests/golden_rendered_text_qa.py` — *"src/10-model.js normalises labelMode on load, so any
open-and-resave of the corpus writes one in and silently disarms this suite"* — is now false as
a statement about this repository. A reader who checks it will find `10-model.js` saying the
opposite, and may conclude the guard is obsolete rather than misdirected.

This cuts both ways, and I record the half that helps the change: because the automatic hazard
is gone, the guard's blind spot is presently reachable only by a hand edit or by a future
change to the loader. It is a wrong guard against a risk that has shrunk, not a wrong guard
against a live one.

### D-G4 — smaller

- The refusal message overclaims for `"none"`. The check is `authored is not None`, so a
  document authoring `labelMode: "none"` is refused with "a component with an authored mode
  draws its caption on a broken build too". `"none"` does the opposite: it stops the caption
  being drawn and the anchor fails loudly, which is safe. Only a non-`none` mode disarms.
  `skills/author-offline/SKILL.md` tells hand-authors to write `"labelMode": "none"` when they
  write a `presentation` block at all, so this is the spelling a corpus author is most likely
  to reach for.
- The comment says the precondition is checked "first" and the commit says "before the anchor
  itself runs". True of the anchor comparison; `read_corpus_text()` still launches the browser
  and opens all ten documents before the guard is consulted. Cosmetic — no effect on the
  verdict, some effect on the time to a failure.

## 4. The merged lineage

The merge is the more valuable of the two subjects, and it holds up.

- `git diff --stat 7b45353 78bcaef -- src/ styles/ index.source.html` is empty. The branch
  changed nothing under `src/`, so the merged sources are `dev`'s exactly.
- `git diff --stat 7b45353 78bcaef` lists nine files, all the branch's own: the suite, its
  expectation, the corpus document and its README line, the `scripts/qa.py` registration, the
  three reports, and the one `MODULE-QA.md` line.
- `python3 build.py` leaves `index.html` unmodified against the commit, so the committed build
  is the deterministic build of the merged sources.
- `tests/golden-rendered-text.json` was not regenerated across the merge and the suite still
  passes, so the defect batch changed no rendered text in the corpus.

The merge note claims the branch previously "sat on a lineage that did not contain the caption
fix it was written to protect". That is true and understates it. On the pre-merge lineage the
anchor could not have discriminated at all: `10-model.js` forced `presentation.labelMode` to
`'boundary'` on every component at load, and `55-render.js` read that field directly, so
"authors no `labelMode`" — the property the suite's docstring calls load-bearing and the guard
exists to protect — had no bearing on what was drawn. Every component got a mode whether it
authored one or not. The suite was green there for a reason unrelated to the defect it names.

After the merge the property is real: `effectiveLabelMode` derives the mode, an authored mode
wins, and authoring one is exactly what would hide the regression. So the merge is what turned
the anchor from a coincidence into a test — and it also turned the guard from harmless into
wrong, because it is only now that authoring a mode at the real key matters, and only now that
reading the wrong key costs something.

## 5. The `opacity: 0` disclosure

**Confirmed.** On a copy of `78bcaef` I changed one line of `src/55-render.js` so a type caption
is emitted with `opacity="0"` while an authored label is untouched, rebuilt, and ran the whole
quick suite:

```
$ grep -c "if(!customLabel)t.setAttribute('opacity','0')" index.html
1
  caption ['ACT', '0', '0']
  caption ['GATE', '0', '0']
  caption ['HOLD', '0', '0']
  caption ['Receipt', None, '1']
...
PASS golden rendered text QA (10 documents, 101 text nodes)
...
RC QA PASS: 43 suites + 17 JS syntax checks (89.88s test time)
EXIT=0
```

The three captions the original regression stopped drawing have computed opacity `0` — the same
user-visible symptom, reached by another mechanism — and 43 suites are green.

**Placement: adequate in the pull request, buried in the code.** The PR body carries it under
its own heading, `## Disclosed, not fixed`, as the first sentence, bolded, above the smaller
residuals, and concedes that `3f652a7`'s subject line overstates the check. The `e51b999`
commit body repeats it under "Not addressed, disclosed rather than fixed". The PR comment
confirms it still stands. A reviewer cannot miss it.

The code says the opposite. `tests/golden_rendered_text_qa.py:8-9` still reads *"Until this
suite existed nothing compared what a document shows"*, which is the overstatement the
disclosure retracts. Nobody reading the
suite — the person most likely to trust it in six months, and the person most likely to be
looking after a caption goes invisible again — is told that an invisible caption passes. The
retraction lives only in artifacts that are not the artifact. One sentence in that docstring
would fix it, and the same commit that added the guard could have carried it.

## 6. What would defeat this finding

- **A real use of `config.labelMode`.** If a schema, loader branch, migration, older format
  version, or `.sovpak` path reads or writes a top-level `config.labelMode`, the guard is
  reading a genuine second location and my central claim collapses to "it checks one of two".
  I searched `src/`, `mcp/`, `scripts/`, `formats/`, `skills/`, `docs/`, `data/` and the test
  suite; the schemas under `formats/` do not describe `config` at all, so they are silent
  rather than confirming. A location I did not search would defeat this.
- **A path that still writes `presentation.labelMode` into a corpus file on the merged tree.**
  I probed one: open and read back through `file.document()`, which no longer writes it. If
  some other route — the desktop shell's save, `.sovpak` packaging, recovery restore — still
  writes a mode into a saved document, then D-G1 is not a shrunken risk but a live one, and the
  guard's failure is more serious than I have graded it, not less.
- **A different reading of what the guard is for.** If it was only ever meant to catch a
  careless hand edit that spells the key at the top level, it does that. I judge that reading
  unavailable, because the commit message names the resave hazard explicitly and the resave
  writes the other key.
- **My mutation of `effectiveLabelMode` being the wrong defect class.** I deleted precisely the
  line `31bbe4e` added, which is the narrowest possible reintroduction; the PR comment used a
  broader one. If neither is the defect class of interest, property (3) is unproven by me.
- **Host variance.** One machine, one Chromium at `/opt/pw-browsers/chromium`, one run of each
  counterfactual. A caption that draws differently elsewhere would change the readings, not the
  source reading of which key the product uses.

## 7. What I did not do

I did not repair the guard, did not touch `tests/golden_rendered_text_qa.py`, did not commit,
did not push, did not create a git worktree, did not run `playwright install`, and did not
evaluate the parts of this branch the two earlier readings already cover. I did not run the
non-`--quick` stress and performance suites. I did not test `.sovpak` corpus coverage, the
desktop save path, or any document outside `examples/`.
