"""Headless SVG export for .sov documents.

Loads the standalone build (index.html) in headless Chromium, opens each document through
the browser API, fits the camera to the diagram, and serialises the rendered workspace SVG
with computed styles inlined so the file renders faithfully outside the editor (markdown
image tags, GitHub, image viewers), where the app stylesheet is not available.

Usage:
    python scripts/export_svg.py                      # every examples/*.sov -> examples/*.svg
    python scripts/export_svg.py a.sov b.sov          # next to each input
    python scripts/export_svg.py a.sov --out build/   # into a directory
    python scripts/export_svg.py --appearance dark    # force light|dark (default: light)
    python scripts/export_svg.py a.sov --loop         # also make the packet animation repeat
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'scripts'))
from browser_runtime import chromium_launch_kwargs  # noqa: E402

# File-menu, browser API and headless export share the persistence implementation.
EXPORT_JS = "(opts) => window.SovSchematicAPI.file.svg(opts)"



def export_documents(paths: list[Path], out_dir: Path | None = None, appearance: str = 'light', pad: int = 48, loop: float | None = None) -> list[dict]:
    """Export each .sov to .svg. Returns one record per input: {source, target, bytes, errors, loop}.

    `loop` is a travel-time budget: when given, every animation is snapped to a divisor of
    one period so the file repeats. See scripts/loop_svg.py.
    """
    from playwright.sync_api import sync_playwright
    if not HTML.exists():
        raise SystemExit('index.html is missing; run python build.py first')
    html = HTML.read_text(encoding='utf-8')
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        errors: list[str] = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content(html, wait_until='load')
        page.wait_for_timeout(250)
        page.evaluate('(m)=>window.SovSchematicAPI.view.setAppearance(m)', appearance)
        for src in paths:
            src = Path(src)
            before = len(errors)
            text = src.read_text(encoding='utf-8')
            page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [text, src.name])
            page.evaluate('()=>{ if (typeof fitDiagram === "function") fitDiagram(); }')
            page.wait_for_timeout(300)
            svg = page.evaluate(EXPORT_JS, {'pad': pad})
            period = 0.0
            if loop is not None:
                from loop_svg import quantize
                svg, period, _worst, _count = quantize(svg, budget=loop)
            target = (out_dir / f'{src.stem}.svg') if out_dir else src.with_suffix('.svg')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(svg, encoding='utf-8', newline='\n')
            results.append({'source': src, 'target': target, 'bytes': len(svg.encode('utf-8')),
                            'errors': errors[before:], 'loop': period})
        browser.close()
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('paths', nargs='*', help='.sov files (default: examples/*.sov)')
    ap.add_argument('--out', type=Path, default=None, help='output directory (default: beside each input)')
    ap.add_argument('--appearance', choices=['light', 'dark'], default='light')
    ap.add_argument('--pad', type=int, default=48, help='padding around content in canvas units')
    ap.add_argument('--loop', nargs='?', type=float, const=0.08, default=None,
                    metavar='BUDGET',
                    help='make the animation repeat; optional travel-time budget (default 0.08)')
    args = ap.parse_args(argv)
    paths = [Path(p) for p in args.paths] or sorted((ROOT / 'examples').glob('*.sov'))
    if not paths:
        print('no .sov inputs', file=sys.stderr)
        return 2
    failed = 0
    for r in export_documents(paths, args.out, args.appearance, args.pad, args.loop):
        status = 'ok ' if not r['errors'] else 'ERR'
        loop = f", loops at {r['loop']:.2f}s" if r.get('loop') else ''
        print(f"{status} {r['source']} -> {r['target']} ({r['bytes']} bytes{loop})")
        for e in r['errors']:
            failed += 1
            print(f'    page error: {e}', file=sys.stderr)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
