#!/usr/bin/env bash
# One-command install and environment doctor.
#
#   scripts/setup.sh            Create .venv, install QA deps + Chromium, run the doctor
#   scripts/setup.sh --system   Install into the current Python environment (no venv)
#   scripts/setup.sh --doctor   Doctor only: verify an existing environment
#
# The doctor proves the environment can do the three things that matter:
# rebuild the standalone artifact deterministically, launch headless
# Chromium, and reach Node for the MCP/syntax gates. It ends by naming the
# next commands (full gate, channels, serve).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

MODE="${1:-}"
PY=python3

if [[ "$MODE" != "--doctor" ]]; then
  if [[ "$MODE" != "--system" ]]; then
    if [[ ! -d .venv ]]; then
      echo "==> Creating .venv"
      $PY -m venv .venv
    fi
    # shellcheck disable=SC1091
    source .venv/bin/activate
    PY=python
  fi
  echo "==> Installing QA dependencies"
  $PY -m pip install --quiet --upgrade pip 2>/dev/null || true  # best-effort; distro-managed pips refuse
  $PY -m pip install --quiet -r requirements-dev.txt
  if [[ -n "${CHROMIUM_PATH:-}" || "${PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD:-}" == "1" ]]; then
    echo "==> Skipping Chromium download (system browser configured)"
  else
    echo "==> Installing Chromium for Playwright"
    $PY -m playwright install chromium
  fi
elif [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  PY=python
fi

echo "==> Doctor"
FAIL=0

if node --version >/dev/null 2>&1; then
  echo "  node        $(node --version)"
else
  echo "  node        MISSING (Node 18+ required for MCP server and syntax gates)"; FAIL=1
fi

echo "  python      $($PY --version 2>&1)"

if $PY build.py >/dev/null 2>&1; then
  if git diff --quiet -- index.html; then
    echo "  build       deterministic (index.html matches committed artifact)"
  else
    echo "  build       WARNING: rebuilt index.html differs from committed artifact"
    echo "              (expected only when src/ has local edits)"
  fi
else
  echo "  build       FAILED (python build.py)"; FAIL=1
fi

if $PY - <<'PYEOF' >/dev/null 2>&1
import os
from playwright.sync_api import sync_playwright
kwargs={'headless':True,'args':['--no-sandbox']}
p=os.environ.get('CHROMIUM_PATH','').strip()
if p: kwargs['executable_path']=p
pw=sync_playwright().start()
b=pw.chromium.launch(**kwargs)
b.close(); pw.stop()
PYEOF
then
  echo "  chromium    launches headless"
else
  echo "  chromium    FAILED to launch — set CHROMIUM_PATH=/path/to/chrome or run: $PY -m playwright install chromium"; FAIL=1
fi

if [[ $FAIL -ne 0 ]]; then
  echo "Doctor found problems above."
  exit 1
fi

cat <<'NEXT'

Environment ready. Next steps:
  python scripts/qa.py            full authoritative QA gate (same as CI)
  python scripts/qa.py --quick    gate minus stress/performance suites
  scripts/channels.sh serve       main/dev/rc + working tree behind a local selector
  scripts/channels.sh qa <ref>    any version's own gate, headless
  open index.html                 the editor itself — no server required

Guides: LOCAL-SETUP.md · skills/steward/SKILL.md · AGENTS.md
NEXT
