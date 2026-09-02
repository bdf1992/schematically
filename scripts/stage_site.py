#!/usr/bin/env python3
"""Stage the deployable static site into _site/ from QA-verified repository state.

The deployed surface is intentionally small: the standalone editor build plus
the executable example corpus and reference docs. Everything staged here has
already passed scripts/qa.py in the same workflow run (CI) or in the calling
script (scripts/deploy_preview.py).

_site/build.json records which branch and commit this deployment is, so a
deployed URL always says what it is without a trip back to git.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / '_site'

FILES = ['index.html']
DIRS = ['examples', 'formats', 'reference']


def git(*args: str) -> str:
    try:
        return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ''


def build_metadata(qa: str) -> dict:
    return {
        'schema': 'soveraeign.schematic/build@0.1',
        'branch': git('rev-parse', '--abbrev-ref', 'HEAD'),
        'commit': git('rev-parse', 'HEAD'),
        'describe': git('describe', '--tags', '--always', '--dirty'),
        'subject': git('log', '-1', '--format=%s'),
        'built_at': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        'qa': qa,
    }


def stage(qa: str = 'not recorded') -> Path:
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    for name in FILES:
        shutil.copy2(ROOT / name, SITE / name)
    for name in DIRS:
        shutil.copytree(ROOT / name, SITE / name)
    text = json.dumps(build_metadata(qa), indent=2, sort_keys=True) + chr(10)
    (SITE / 'build.json').write_text(text, encoding='utf-8')
    return SITE


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--qa', default='not recorded',
                        help='how this tree was verified, recorded in build.json')
    args = parser.parse_args()
    print(stage(args.qa))
