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

Deployment is push-driven and QA-gated:

1. Every push and PR runs `scripts/qa.py` in `schematic-ci`.
2. On a push to `main` only, the same workflow run — after QA passes — stages
   `_site/` via `scripts/stage_site.py` (standalone `index.html`, `examples/`,
   `formats/`, `reference/`) and deploys it to GitHub Pages.
3. A red QA run deploys nothing; the previously published site stays live.

One-time repository setting: **Settings → Pages → Source: GitHub Actions**.

## 5. Local deployment update pattern

To advance a local checkout/deployment only onto verified commits:

```bash
scripts/update_local.sh          # fast-forwards to origin/main iff its CI is green
scripts/update_local.sh --serve  # …then serves on http://localhost:8000
```

The script checks the `schematic-ci` conclusion for the exact `origin/main`
head SHA and refuses to update when that run is missing, pending, or failed.
Set `GITHUB_TOKEN` if the repository is private.
