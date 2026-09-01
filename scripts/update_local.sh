#!/usr/bin/env bash
# Update a local deployment to the latest *green* main.
#
# Pulls origin/main only when its schematic-ci run concluded successfully,
# so a local deployment can never advance onto an unverified commit.
#
# Usage:
#   scripts/update_local.sh          # update if main is green
#   scripts/update_local.sh --serve  # then serve on http://localhost:8000
#
# For a private repository set GITHUB_TOKEN (a fine-grained read-only
# Actions token is enough); public repositories need no token.
set -euo pipefail

REPO_SLUG="${REPO_SLUG:-bdf1992/schematically}"
BRANCH="${BRANCH:-main}"
PORT="${PORT:-8000}"

cd "$(git rev-parse --show-toplevel)"

git fetch origin "$BRANCH"
SHA="$(git rev-parse "origin/$BRANCH")"

AUTH=()
if [[ -n "${GITHUB_TOKEN:-}" ]]; then AUTH=(-H "Authorization: Bearer $GITHUB_TOKEN"); fi
CONCLUSION="$(curl -sf "${AUTH[@]}" \
  "https://api.github.com/repos/$REPO_SLUG/actions/workflows/ci.yml/runs?head_sha=$SHA&per_page=1" \
  | python3 -c 'import json,sys; runs=json.load(sys.stdin)["workflow_runs"]; print(runs[0]["conclusion"] if runs else "none")')"

if [[ "$CONCLUSION" != "success" ]]; then
  echo "Refusing to update: schematic-ci on origin/$BRANCH@${SHA:0:9} is '$CONCLUSION', not 'success'." >&2
  exit 1
fi

if [[ "$(git rev-parse HEAD)" == "$SHA" ]]; then
  echo "Already at green $BRANCH (${SHA:0:9})."
else
  git merge --ff-only "origin/$BRANCH"
  echo "Updated to green $BRANCH (${SHA:0:9})."
fi

python3 build.py

if [[ "${1:-}" == "--serve" ]]; then
  echo "Serving on http://localhost:$PORT"
  python3 -m http.server "$PORT"
fi
