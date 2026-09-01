# SOV Schematic Steward Skill — 0.1

## Purpose

Install, onboard, and manage this system as a product: environments, release
channels, quality gates, and the defect lifecycle. The author, operator, and
reviewer skills work *inside* a schematic; the steward gets people and agents
*into* the system and keeps its releases trustworthy.

## Installation

One command from a fresh clone:

```bash
scripts/setup.sh            # venv + QA deps + Chromium + environment doctor
scripts/setup.sh --doctor   # re-verify an existing environment
```

The doctor proves three things before declaring the environment ready:
deterministic rebuild of `index.html`, headless Chromium launch, and Node
availability. A machine whose Playwright/Chromium revisions drift points
`CHROMIUM_PATH` at any system Chrome instead of downloading.

The editor itself needs no installation: `index.html` opens from disk.
Installation exists for the QA gate, the channels, and the agent surfaces.

## Onboarding sequence

1. `scripts/setup.sh` — environment ready.
2. Open `index.html`; open a golden example from `examples/` via File → Open.
3. Read `AGENTS.md` (invariants) and `MODULES.md` (concern ownership).
4. Run `python scripts/qa.py --quick` once, to see the gate green before
   touching anything.
5. Pick the skill matching the work: `author` to build schematics,
   `operator` to drive API/HTTP/MCP, `reviewer` to audit, this skill to
   manage releases and process.

## Release channels

Three channels, one QA gate:

- **main** — accepted, deployable state. Green pushes deploy all channels
  to the published site.
- **dev** — integration line. Feature branches merge here through PRs.
- **rc** — lit automatically while an `rc/x.y.z-rcN` branch exists; the
  stabilization line described in `docs/BRANCHING.md`.

Locally, `scripts/channels.sh serve` mirrors the deployed selector plus a
`local` channel for the working tree; `scripts/channels.sh qa <ref>` runs any
version's own gate headlessly for regression comparison.

## Quality process

- `python scripts/qa.py` is the single authority, identical locally and in CI.
  A change is not settled until it passes.
- A defect found by hand or by a journey gets an Issue before a fix, and a
  regression suite inside the gate with the fix. Close the Issue only after
  the fix is on its target branch and CI reproduced it from repository state.
- Deployment is a consequence of a green gate, never a separate ambition:
  a red run deploys nothing and the previous site stays live.
- Version-handle noise stays out of living docs: README and model docs
  describe the current form; historical acceptance records keep their
  handles and are labeled as records.

## Refusals

Refuse or repair:

- skipping, weakening, or quarantining a gate suite to get green;
- deploying or advancing a channel from a red or unverified state;
- fixing a manually found defect without an Issue and regression test;
- adding a second implementation path where a concern already has an owner
  (`MODULES.md` decides);
- letting release-line stabilization absorb NEXT/post-line feature work.
