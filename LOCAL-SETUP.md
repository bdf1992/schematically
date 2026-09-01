# Local setup, deployment, and update pattern

How to run SOV Schematic on your machine, keep a local deployment current with
verified `main`, and reproduce the full QA gate locally.

## 1. One-time machine setup

```bash
git clone https://github.com/bdf1992/schematically.git
cd schematically
scripts/setup.sh          # venv + QA deps + Chromium + environment doctor
```

The doctor verifies deterministic rebuild, headless Chromium, and Node
(18+ required for `node --check` gates and the MCP server), then prints the
next commands. `scripts/setup.sh --doctor` re-verifies an existing
environment; `--system` skips the venv. Onboarding guidance for humans and
agents lives in `skills/steward/SKILL.md`.

## 2. Running the editor locally

`index.html` is the deterministic standalone build — it opens directly from
disk with no server. After editing anything in `index.source.html`, `src/`, or
`styles/`, rebuild:

```bash
python build.py        # regenerates index.html
python -m http.server 8000   # optional; or just open index.html in a browser
```

For the HTTP/MCP surface:

```bash
node mcp/server.mjs
```

## 3. The QA gate (same command locally and in CI)

```bash
python scripts/qa.py           # full authoritative RC QA
python scripts/qa.py --quick   # skips drag-stress and performance suites
```

This is exactly what `.github/workflows/ci.yml` runs on every push and pull
request. A change is not settled until this passes locally.

If your Playwright wheel and installed Chromium revisions drift (common on
managed machines), point the QA harness at any system Chromium:

```bash
CHROMIUM_PATH=/path/to/chrome python scripts/qa.py
```

Note: several browser suites rewrite tracked byproducts under `tests/`
(screenshots, `saved-test.sov*`, `performance-results.json`). Discard those
with `git checkout -- tests/` unless you intend to re-baseline them.

## 4. Deployment pattern — release channels

Deployment is push-driven, QA-gated, and channelized:

1. Every push and PR runs `scripts/qa.py` in `schematic-ci`.
2. On a push to `main`, `dev`, or any `rc/*` branch — after QA passes —
   `scripts/stage_site.py` builds **each channel from its own branch's
   source** (`_site/main/`, `_site/dev/`, `_site/rc/` when an rc branch
   exists) plus a selector page at the site root, and the whole site deploys
   to GitHub Pages.
3. A red QA run deploys nothing; the previously published site stays live.
4. Cutting an `rc/x.y.z-rcN` branch from `dev` lights up the `rc` channel
   automatically on its first green push; deleting it after merge retires it
   on the next deploy.

One-time repository setting: **Settings → Pages → Source: GitHub Actions**.

## 5. Local channels and version-selected QA

`scripts/channels.sh` mirrors the deployed layout on your machine:

```bash
scripts/channels.sh serve         # build main/dev/rc + working tree into dist/,
                                  # serve the selector on http://localhost:8000
scripts/channels.sh build         # build channels without serving
scripts/channels.sh qa dev        # run dev's own full QA gate headlessly
scripts/channels.sh qa main --quick   # any ref, any qa.py flags
scripts/channels.sh qa v0.1.0     # tags and SHAs work too
```

The `local` channel is your current working tree — edit, rebuild, and diff it
against the committed channels side by side. `qa <ref>` checks the ref out
into a temporary worktree and runs **that ref's** `scripts/qa.py`, so
regression suites always match the version under test.

To advance the checkout itself only onto verified commits:

```bash
scripts/update_local.sh          # fast-forwards to origin/main iff its CI is green
scripts/update_local.sh --serve  # …then serves on http://localhost:8000
```

The script checks the `schematic-ci` conclusion for the exact `origin/main`
head SHA and refuses to update when that run is missing, pending, or failed.
Set `GITHUB_TOKEN` if the repository is private.
