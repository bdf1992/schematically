#!/usr/bin/env python3
"""Stage the deployable static site into _site/ from QA-verified repository state.

The deployed surface is intentionally small: the standalone editor build plus
the executable example corpus and reference docs. Everything staged here has
already passed scripts/qa.py in the same workflow run.
"""
from __future__ import annotations
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / '_site'

FILES = ['index.html']
DIRS = ['examples', 'formats', 'reference']

if SITE.exists():
    shutil.rmtree(SITE)
SITE.mkdir()
for name in FILES:
    shutil.copy2(ROOT / name, SITE / name)
for name in DIRS:
    shutil.copytree(ROOT / name, SITE / name)
print(SITE)
