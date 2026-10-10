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

Note: the read/write-access, wire-host-inline and file-surface suites write their
byproducts (screenshots, `saved-test.sov*`) to the run-artifact directory -
`SCHEMATIC_QA_OUT` when set, else `schematically-qa` under the system temp
directory - not into `tests/`. No checkout of `tests/` is needed after a run.

### Windows: the font-dependent suites in Linux

CI renders text with DejaVu on Ubuntu, which is about 10 percent wider than a
Windows font, so four suites give different answers on Windows. One command
runs them in a Linux container on Docker Desktop and prints what CI would:

```bash
python scripts/qa_linux.py                       # the four suites below, in this order
python scripts/qa_linux.py --suite tests/svg_export_qa.py   # --suite is repeatable and replaces the four
python scripts/qa_linux.py --tree C:\path\to\worktree       # another checkout; default is this one
python scripts/qa_linux.py --print-command       # the docker build and run argv as JSON; calls no docker
```

The default suites are `tests/layouts_qa.py`, `tests/layout_quality_qa.py`,
`tests/authoring_review_qa.py` and `tests/golden_rendered_text_qa.py`. Each
prints `QA PASS path (seconds)` or `QA FAIL path (exit code, seconds)`, then
`LINUX QA PASS: n suites` or `LINUX QA FAIL: k of n suites`.

Exit codes: 0 every suite passed; 1 a suite or `build.py` failed; 2 the
container could not run (missing suite path, no playwright pin in the tree's
`requirements-dev.txt`, Docker engine not reachable, image build failed).

Docker Desktop must be running; the script starts and stops nothing (start it
with `docker desktop start`). The image `schematically-qa-linux` is built once
per Dockerfile and requirements-dev.txt content and reused after. The tree is
mounted read-only and copied inside the container, so a run changes no file on
the host.

A suite that leaves a tracked file under `tests/` changed after a run has a defect: discard the change with `git checkout -- tests/` and file it.

## 4. Deployment pattern

Release is tag-driven and QA-gated: one `v*` tag is the one release path.

1. Every push and PR runs `scripts/qa.py` in `schematic-ci` (`ci.yml`). It
   deploys nothing.
2. Pushing a tag `v*` runs `release.yml` on that commit: `verify` (the same
   `scripts/qa.py`), then `web` (stages `_site/` via `scripts/stage_site.py`:
   standalone `index.html`, `examples/`, `formats/`, `reference/`, `build.json`;
   zips it as `schematically-web-<tag>.zip`), `pages` (deploys `_site/` to
   GitHub Pages), `desktop` (builds the Tauri installers on windows-latest and
   launches the built exe on a document), and `release` (one GitHub release
   carrying the web zip, the `.msi` and `-setup.exe` installers and
   `REVISION.txt`, all from that commit).
3. A red `verify` deploys and releases nothing; the previously published site
   stays live.
4. The revision is named in each artifact: `SOV_BUILD_REVISION` (`<tag> <commit>`)
   becomes `<meta name="sov-revision">` in the desktop page and the staged
   `_site/index.html`; `SovSchematicAPI.file.info().build` returns that content
   (null in a local build) and `_site/build.json` holds `{tag, commit, describe}`.
   The committed `index.html` never carries the meta.

One-time repository settings: **Settings → Pages → Source: GitHub Actions**, and
the `github-pages` environment's deployment rule must allow tags `v*` to deploy.

Out of scope: code signing and a publisher certificate. They cost money and are
Bdo's; the installers are unsigned until he decides.

## 5. Local deployment update pattern

To advance a local checkout/deployment only onto verified commits:

```bash
scripts/update_local.sh          # fast-forwards to origin/main iff its CI is green
scripts/update_local.sh --serve  # …then serves on http://localhost:8000
```

The script checks the `schematic-ci` conclusion for the exact `origin/main`
head SHA and refuses to update when that run is missing, pending, or failed.
Set `GITHUB_TOKEN` if the repository is private.
