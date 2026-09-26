"""Render the committed gallery in docs/visual/ from the examples: the views as built.

Each picture is a run record drawn by scripts/plot_run.mjs, so the gallery is what anyone
gets from the same commands. `--check` exits 1 when a committed picture differs from what
this would write, so the gallery cannot drift from the code.

    python scripts/build_visual_gallery.py            # write docs/visual/*.svg
    python scripts/build_visual_gallery.py --check
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'visual'
sys.path.insert(0, str(ROOT / 'scripts'))
from record_run import parse_vector, record_logic, record_optimize, record_simulate  # noqa: E402

LG, OP = ROOT / 'examples' / 'logic', ROOT / 'examples' / 'optimization'
KEEP = {  # record name.view -> gallery file
    'adder.timing-zoom': 'timing-adder-carry.svg',
    'learning.landscape': 'landscape-learning.svg',
    'three.landscape-chairs-tables': 'landscape-slice-chairs-tables.svg',
    'learning.search-outline': 'search-outline.svg',
    'learning.search-tree': 'search-tree.svg',
    'week.timeline': 'timeline-week.svg',
    'glyphs': 'glyphs.svg',
}


def records() -> dict[str, dict]:
    return {
        # A state space run: 7 + 0, then B0 rises and the carry ripples to 8.
        'adder': record_logic(LG / 'adder4.sov', [parse_vector('A=7:4,B=0:4,Cin=0'), parse_vector('B0=1')], 20, ['S']),
        'learning': record_optimize(OP / 'workshop.sov', OP / 'workshop.learning.opt.json', segments=32, starts=24, steps=41),
        'week': record_simulate(OP / 'workshop.sov', OP / 'workshop.learning.opt.json', {'chairs': 14, 'tables': 2}),
        'three': record_optimize(OP / 'workshop3.sov', OP / 'workshop3.opt.json', segments=20, starts=12, steps=41),
    }


def render() -> dict[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        files = []
        for name, rec in records().items():
            f = tmp / f'{name}.json'
            f.write_text(json.dumps(rec), encoding='utf-8')
            files.append(str(f))
        node = str(ROOT / 'scripts' / 'plot_run.mjs')
        subprocess.run(['node', node, *files, '--out', str(tmp / 'svg')], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(['node', node, '--glyphs', '--out', str(tmp / 'svg')], check=True, stdout=subprocess.DEVNULL)
        return {KEEP[f.stem]: f.read_text(encoding='utf-8') for f in (tmp / 'svg').glob('*.svg') if f.stem in KEEP}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    made = render()
    missing = set(KEEP.values()) - set(made)
    if missing:
        raise SystemExit(f'views not produced: {sorted(missing)}')
    stale = [n for n, t in made.items() if not (OUT / n).exists() or (OUT / n).read_text(encoding='utf-8') != t]
    if args.check:
        for n in stale:
            print(f'stale docs/visual/{n}')
        return 1 if stale else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for n, t in made.items():
        (OUT / n).write_text(t, encoding='utf-8', newline='\n')
    print(f'wrote {len(made)} pictures to docs/visual/')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
