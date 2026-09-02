# Local setup, deployment, and update pattern

How to run SOV Schematic on your machine, keep a local deployment current with
verified `main`, and reproduce the full QA gate locally.

## 1. One-time machine setup

```bash
git clone https://github.com/bdf1992/schematically.git
cd schematically
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m playwright install chromium   # add --with-deps on a fresh Linux box
```

Node 18+ is required for `node --check` syntax gates and the MCP server.

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

## 4. Deployment pattern

Every branch is deployed, every deployment is QA-gated, and every URL is
behind a login. Hosting is Cloudflare Pages; the login is Cloudflare Access.

1. Every push and PR runs `scripts/qa.py` in `schematic-ci`.
2. On any push, after QA passes, the same run stages `_site/` via
   `scripts/stage_site.py` (standalone `index.html`, `examples/`, `formats/`,
   `reference/`, plus `build.json` naming the branch, commit and QA result) and
   deploys it to Cloudflare Pages under the branch name:
   - `main` → `https://schematically.pages.dev`
   - anything else → `https://<branch-slug>.schematically.pages.dev`
     (lowercased, `/` becomes `-`, e.g. `feature/scale-contracts` →
     `feature-scale-contracts.schematically.pages.dev`)
3. A red QA run deploys nothing; the previous deployment of that branch stays.
4. Open `/build.json` on any deployed URL to see exactly what it is.
5. The Cloudflare dashboard (Workers & Pages → schematically → Deployments)
   lists every live branch with its commit; that is the one place to look.

A branch that never reaches GitHub (a local sandbox) deploys the same way
from the working tree:

```bash
python scripts/deploy_preview.py            # quick QA, stage, deploy under the current branch
python scripts/deploy_preview.py --dry-run  # stage and print the command only
```

It refuses to deploy `main` from a working tree; `main` deploys from CI only.

### One-time setup (account owner)

1. Cloudflare account (free): create Pages project **schematically** with
   *Direct Upload* (no Git integration; CI and the local script upload the
   staged site themselves). Production branch: `main`.
2. API token with **Account → Cloudflare Pages → Edit**. Put it and the
   account id in the GitHub repository secrets `CLOUDFLARE_API_TOKEN` and
   `CLOUDFLARE_ACCOUNT_ID`, and in the local environment for
   `deploy_preview.py`.
3. Cloudflare Zero Trust → Access → Applications → add a self-hosted
   application for `schematically.pages.dev` and `*.schematically.pages.dev`,
   policy *Allow* for the emails that may open it (one-time PIN login is the
   zero-config identity provider; GitHub login can be added later). Free for
   up to 50 users.
4. Optional: GitHub environments `production` and `preview` for the deploy
   history in the repository's Deployments tab. They need no protection rules.

## 5. Local deployment update pattern

To advance a local checkout/deployment only onto verified commits:

```bash
scripts/update_local.sh          # fast-forwards to origin/main iff its CI is green
scripts/update_local.sh --serve  # …then serves on http://localhost:8000
```

The script checks the `schematic-ci` conclusion for the exact `origin/main`
head SHA and refuses to update when that run is missing, pending, or failed.
Set `GITHUB_TOKEN` if the repository is private.
