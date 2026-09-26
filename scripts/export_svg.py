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
    python scripts/export_svg.py examples/logic/adder4.sov --run 'A=7:4,B=0:4,Cin=0;B0=1' --tick 23
    python scripts/export_svg.py examples/logic/full-adder.sov --run 'A=1,B=0,Cin=1' --monochrome
    python scripts/export_svg.py doc.sov --trace doc.sovtrace          # a trace of this document

With --trace, the export draws a state space run's state at a tick (default: the last one the
trace processed) through the editor's state view (src/57-state-view.js): a high wire in the
signal colour, a low one in ink, a chip at every port; with --monochrome, by weight alone.
The trace must have run this document as the editor holds it; otherwise the view refuses and
the export fails. With --run, the engine runs the open document in the page on those input
vectors (one every --period ticks) and the export draws that run.
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



PACKS = [ROOT / 'data' / 'core.logic.pack.json', ROOT / 'data' / 'logic.gates.pack.json']

# Runs the open document on the engine in the page (its own API; no surface of ours) to quiet,
# and returns the trace, so the trace is of the document exactly as the editor holds it.
RUN_JS = r"""
([packs, inputs]) => {
  const S = window.SovSchematicStateSpace;
  const started = S.startRun({doc: snapshotDocument(), packs, inputs});
  if (!started.ok) return started;
  for (;;) { const r = S.step(started.run); if (!r.ok) return r; if (r.tick === null) break; }
  return {ok: true, trace: S.traceOf(started.run)};
}
"""


def export_documents(paths: list[Path], out_dir: Path | None = None, appearance: str = 'light', pad: int = 48, loop: float | None = None,
                     trace: dict | None = None, tick: int | None = None, monochrome: bool = False,
                     run: list[dict] | None = None) -> list[dict]:
    """Export each .sov to .svg. Returns one record per input: {source, target, bytes, errors, loop}.

    `loop` is a travel-time budget: when given, every animation is snapped to a divisor of
    one period so the file repeats. See scripts/loop_svg.py.

    `trace` is a state space trace of the document: the export then draws the run's state at
    `tick` (default: the trace's last tick); `monochrome` draws it by line weight alone. A
    refusal to show the trace is an error in the result. `run` is a list of state space inputs
    ({entity, point, value, at}): the page runs the open document on them and draws that run.
    """
    from playwright.sync_api import sync_playwright
    if not HTML.exists():
        raise SystemExit('index.html is missing; run python build.py first')
    html = HTML.read_text(encoding='utf-8')
    packs = [__import__('json').loads(p.read_text(encoding='utf-8')) for p in PACKS] if trace is not None or run is not None else None
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
            # An export draws the document at its own scale: full glyphs, whatever the camera.
            page.evaluate('()=>{ if (typeof applyGlyphSizeRule === "function") applyGlyphSizeRule(1); }')
            shown_trace = trace
            if run is not None:
                made = page.evaluate(RUN_JS, [packs, run])
                if not made['ok']:
                    errors.append(f"run refused {made['code']}: {made['message']}")
                shown_trace = made.get('trace')
            if shown_trace is not None:
                shown = page.evaluate('(o)=>window.SovSchematicAPI.view.stateSpace.show(o)',
                                      {'trace': shown_trace, 'packs': packs, 'tick': tick, 'chips': 'all', 'monochrome': monochrome})
                if not shown['ok']:
                    errors.append(f"state view refused {shown['refused']}: {shown['reason']}")
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
    ap.add_argument('--trace', type=Path, default=None, help="draw this state space trace's state (a .sovtrace of the document)")
    ap.add_argument('--run', default=None, help="run the document on these vectors in the page, e.g. 'A=7:4,B=0:4,Cin=0;B0=1'")
    ap.add_argument('--period', type=int, default=20, help='with --run: logical ticks between vectors')
    ap.add_argument('--tick', type=int, default=None, help='with --trace: the logical tick to draw (default: the last)')
    ap.add_argument('--monochrome', action='store_true', help='with --trace: state by line weight, no colour')
    args = ap.parse_args(argv)
    paths = [Path(p) for p in args.paths] or sorted((ROOT / 'examples').glob('*.sov'))
    if not paths:
        print('no .sov inputs', file=sys.stderr)
        return 2
    failed = 0
    trace = __import__('json').loads(args.trace.read_text(encoding='utf-8')) if args.trace else None
    run = None
    if args.run is not None:
        from record_run import parse_vector
        run = [{'entity': name, 'point': 'self', 'value': bool(v), 'at': k * args.period}
               for k, step in enumerate(args.run.split(';')) for name, v in sorted(parse_vector(step).items())]
    for r in export_documents(paths, args.out, args.appearance, args.pad, args.loop, trace, args.tick, args.monochrome, run):
        status = 'ok ' if not r['errors'] else 'ERR'
        loop = f", loops at {r['loop']:.2f}s" if r.get('loop') else ''
        print(f"{status} {r['source']} -> {r['target']} ({r['bytes']} bytes{loop})")
        for e in r['errors']:
            failed += 1
            print(f'    page error: {e}', file=sys.stderr)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
