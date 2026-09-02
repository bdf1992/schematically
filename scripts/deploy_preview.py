#!/usr/bin/env python3
"""Deploy the current working tree as a Cloudflare Pages preview, without pushing.

For sandbox and feature branches that never reach GitHub. Runs the quick QA
gate first (skip with --no-qa), stages _site/, then deploys it under the
current branch name, so the URL is the same one CI would produce for a push:

    https://<branch-slug>.schematically.pages.dev

Needs CLOUDFLARE_API_TOKEN (Pages: Edit) and CLOUDFLARE_ACCOUNT_ID in the
environment, and Node (wrangler runs through npx). Refuses to deploy the main
branch from a working tree: main deploys only from CI after the full gate.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from stage_site import stage, git  # noqa: E402

PROJECT = 'schematically'


def slug(branch: str) -> str:
    return re.sub(r'[^a-z0-9-]', '-', branch.lower())[:28].strip('-')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--no-qa', action='store_true', help='skip scripts/qa.py --quick')
    parser.add_argument('--branch', help='deploy under this branch name instead of the checked-out one')
    parser.add_argument('--dry-run', action='store_true', help='stage and print the command, do not deploy')
    args = parser.parse_args()

    missing = [k for k in ('CLOUDFLARE_API_TOKEN', 'CLOUDFLARE_ACCOUNT_ID') if not os.environ.get(k)]
    if missing and not args.dry_run:
        print(f'refused: set {", ".join(missing)} in the environment', file=sys.stderr)
        return 2

    branch = args.branch or git('rev-parse', '--abbrev-ref', 'HEAD')
    if branch in ('main', 'HEAD'):
        print('refused: main deploys from CI only; detached HEAD needs --branch', file=sys.stderr)
        return 2

    qa = 'skipped (--no-qa)'
    if not args.no_qa:
        result = subprocess.run([sys.executable, 'scripts/qa.py', '--quick'], cwd=ROOT)
        if result.returncode != 0:
            print('refused: scripts/qa.py --quick failed; not deploying', file=sys.stderr)
            return result.returncode
        qa = 'scripts/qa.py --quick PASS (local)'
    if git('status', '--porcelain'):
        qa += ', working tree dirty'

    site = stage(qa)
    cmd = ['npx', '--yes', 'wrangler', 'pages', 'deploy', str(site),
           f'--project-name={PROJECT}', f'--branch={branch}',
           f'--commit-hash={git("rev-parse", "HEAD")}',
           f'--commit-message={git("log", "-1", "--format=%s")}',
           '--commit-dirty=true']
    print(' '.join(cmd))
    print(f'expected url: https://{slug(branch)}.{PROJECT}.pages.dev')
    if args.dry_run:
        return 0
    return subprocess.run(cmd, cwd=ROOT, shell=(os.name == 'nt')).returncode


if __name__ == '__main__':
    raise SystemExit(main())
