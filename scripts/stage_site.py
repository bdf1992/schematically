#!/usr/bin/env python3
"""Stage the deployable static site into _site/ from QA-verified repository state.

The deployed surface is intentionally small: the standalone editor build plus
the executable example corpus and reference docs. Everything staged here has
already passed scripts/qa.py in the same workflow run (release.yml, on a v* tag).

When SOV_BUILD_REVISION ('<tag> <commit>') is set, the staged index.html carries
<meta name="sov-revision"> with it, and _site/build.json names the revision:
{tag, commit, describe}. The committed index.html never carries the meta.
"""
from __future__ import annotations
from pathlib import Path
import html
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / '_site'

FILES = ['index.html']
DIRS = ['examples', 'formats', 'reference']


def git(*args: str) -> str | None:
    done = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else None


def build_info() -> dict:
    return {
        'tag': git('describe', '--tags', '--exact-match'),
        'commit': git('rev-parse', 'HEAD'),
        'describe': git('describe', '--tags', '--always'),
    }


def main() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    for name in FILES:
        shutil.copy2(ROOT / name, SITE / name)
    for name in DIRS:
        shutil.copytree(ROOT / name, SITE / name)
    revision = os.environ.get('SOV_BUILD_REVISION')
    if revision:
        page = SITE / 'index.html'
        text = page.read_text(encoding='utf-8')
        assert text.count('</head>') == 1, 'index.html must hold </head> exactly once'
        meta = f'<meta name="sov-revision" content="{html.escape(revision, quote=True)}">'
        page.write_text(text.replace('</head>', f'{meta}\n</head>'), encoding='utf-8', newline='\n')
    (SITE / 'build.json').write_text(json.dumps(build_info(), indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    print(SITE)


if __name__ == '__main__':
    main()
