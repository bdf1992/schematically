#!/usr/bin/env bash
# Local channel builder and version-selectable QA runner.
#
#   scripts/channels.sh build            Build main/dev/rc + working tree into dist/
#   scripts/channels.sh serve [PORT]     Build, then serve dist/ with the channel selector
#   scripts/channels.sh qa <REF> [args]  Run REF's own authoritative QA gate headlessly
#                                        (e.g. `qa dev --quick`, `qa v0.1.0`, `qa origin/main`)
#
# `qa` checks REF out into a temporary worktree and runs the scripts/qa.py that
# ships at that ref, so regression suites always match the version under test.
# CHROMIUM_PATH is passed through for machines whose Playwright/Chromium differ.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
CMD="${1:-serve}"; shift || true

case "$CMD" in
  build)
    python3 scripts/stage_site.py --out dist --local
    ;;
  serve)
    PORT="${1:-8000}"
    python3 scripts/stage_site.py --out dist --local
    echo "Channel selector on http://localhost:$PORT"
    python3 -m http.server "$PORT" -d dist
    ;;
  qa)
    REF="${1:?usage: channels.sh qa <ref> [qa.py args]}"; shift || true
    SHA="$(git rev-parse --verify "$REF^{commit}")"
    WT="$(mktemp -d)/wt"
    git worktree add --detach "$WT" "$SHA" >/dev/null
    trap 'git worktree remove --force "$WT" >/dev/null 2>&1 || true' EXIT
    echo "QA gate for $REF (${SHA:0:9})"
    (cd "$WT" && python3 scripts/qa.py "$@")
    ;;
  *)
    echo "unknown command: $CMD (build | serve | qa)" >&2
    exit 2
    ;;
esac
