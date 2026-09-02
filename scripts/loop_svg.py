"""Make an exported document loop, and record one loop as a file.

A wire's packet travel time comes from its path length and rate, so a document's
animations have periods that do not divide into each other. On screen that is right: the
drawing runs and nothing about it is supposed to repeat. In a file someone embeds in a
README, or watches for ten seconds, it means the picture never returns to where it began.

`quantize_svg` picks one period and snaps every animation to an exact divisor of it, so
after that period every packet is back at its start. It takes the shortest period whose
worst change to a travel time stays inside a budget, because travel time is a rendering
convention rather than a claim the document makes. Rate is a claim, so the budget is small
and stated: two rates within twice the budget of each other can come out equal.

`record` captures one period by stepping the SVG clock (pauseAnimations + setCurrentTime)
instead of sleeping between screenshots, so the frames are exact and the last one joins the
first. It samples the second cycle: at t=0 the browser has not yet applied animateMotion
and every packet still sits at its authored origin.

Usage:
    python scripts/loop_svg.py a.svg b.svg                 # quantize in place
    python scripts/loop_svg.py a.svg --budget 0.05         # tighter travel-time budget
    python scripts/loop_svg.py a.svg --record a.webp       # animated WebP of one loop
    python scripts/loop_svg.py a.svg --record a.gif --fps 15
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DUR = re.compile(r'\bdur="([0-9.]+)s"')
LOOP_MARK = '<!-- loop-period:'
DEFAULT_BUDGET = 0.08


def choose_period(durations: list[float], budget: float = DEFAULT_BUDGET, lo: float = 1.5,
                  hi: float = 12.0, step: float = 0.005) -> tuple[float, float]:
    """Return (period, worst relative change) for the shortest acceptable period.

    Some long period always exists that barely moves any travel time, but nobody watches a
    twelve second loop. So: the shortest period whose worst change is inside the budget,
    and if no period in range meets it, the one that changes the least.
    """
    if not durations:
        return 0.0, 0.0
    fallback: list[tuple[float, float]] = []
    for i in range(int(round((hi - lo) / step)) + 1):
        period = lo + i * step
        worst = 0.0
        for d in durations:
            k = max(1, round(period / d))
            worst = max(worst, abs(period / k - d) / d)
        if worst <= budget:
            return round(period, 4), worst
        fallback.append((period, worst))
    period, worst = min(fallback, key=lambda c: c[1])
    return round(period, 4), worst


def quantize(svg: str, budget: float = DEFAULT_BUDGET) -> tuple[str, float, float, int]:
    """Snap every animation in an SVG string to a divisor of one period.

    Returns (svg, period, worst relative change, animation count).
    """
    durations = [float(m) for m in DUR.findall(svg)]
    if not durations:
        return svg, 0.0, 0.0, 0
    already = re.search(re.escape(LOOP_MARK) + r'\s*([0-9.]+)s', svg)
    if already:
        # Idempotent: a second pass would pick a period for the already-snapped durations
        # and leave the recorded one behind, so the file would claim a period it no longer
        # loops at. Nothing to do.
        return svg, float(already.group(1)), 0.0, len(durations)
    period, worst = choose_period(durations, budget=budget)

    def snap(match: re.Match[str]) -> str:
        k = max(1, round(period / float(match.group(1))))
        return f'dur="{period / k:.6f}s"'

    svg = DUR.sub(snap, svg)
    if LOOP_MARK not in svg:
        svg = svg.replace('</svg>', f'{LOOP_MARK} {period:.4f}s -->\n</svg>', 1)
    return svg, period, worst, len(durations)


def quantize_svg(path: Path, budget: float = DEFAULT_BUDGET) -> tuple[float, float, int]:
    """Quantize a file in place. Returns (period, worst relative change, count)."""
    svg, period, worst, count = quantize(path.read_text(encoding='utf-8'), budget)
    if count:
        path.write_text(svg, encoding='utf-8', newline='\n')
    return period, worst, count


def loop_period(path: Path) -> float:
    """The period a quantized file was built for, or 0 if it was never quantized."""
    m = re.search(re.escape(LOOP_MARK) + r'\s*([0-9.]+)s', path.read_text(encoding='utf-8'))
    return float(m.group(1)) if m else 0.0


def frames_of(path: Path, fps: float = 25, max_width: int = 1600) -> tuple[list, float]:
    """Screenshot one loop of a quantized SVG. Returns (RGB frames, period)."""
    import io

    from PIL import Image
    from playwright.sync_api import sync_playwright

    period = loop_period(path)
    if not period:
        raise SystemExit(f'{path.name} has no loop period; quantize it first')
    count = max(2, int(round(period * fps)))
    images = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**_launch_kwargs())
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        page.goto(path.resolve().as_uri())
        page.wait_for_selector('svg')
        page.evaluate("()=>document.querySelector('svg').pauseAnimations()")
        element = page.query_selector('svg')
        for i in range(count):
            page.evaluate("t=>document.querySelector('svg').setCurrentTime(t)",
                          period + period * i / count)
            images.append(Image.open(io.BytesIO(element.screenshot())).convert('RGB'))
        browser.close()
    if images[0].width > max_width:
        height = round(images[0].height * max_width / images[0].width)
        images = [im.resize((max_width, height), Image.LANCZOS) for im in images]
    return images, period


def record(path: Path, out: Path, fps: float = 25, max_width: int = 1600,
           quality: int = 88) -> Path:
    """Record one loop. The suffix of `out` picks the format: .webp, .png (APNG) or .gif."""
    from PIL import Image

    images, period = frames_of(path, fps=fps, max_width=max_width)
    delay = int(round(1000 * period / len(images)))
    out.parent.mkdir(parents=True, exist_ok=True)
    suffix = out.suffix.lower()

    if suffix == '.gif':
        # One palette across every frame, so the encoder can write each frame as a change
        # against the last. A schematic is a still background with a few moving dots.
        base = _shared_palette(images)
        frames = [im.quantize(palette=base, dither=Image.Dither.NONE) for im in images]
        frames[0].save(out, save_all=True, append_images=frames[1:], duration=delay,
                       loop=0, optimize=True, disposal=1)
    elif suffix == '.png':
        images[0].save(out, save_all=True, append_images=images[1:], duration=delay, loop=0)
    else:
        images[0].save(out, format='WEBP', save_all=True, append_images=images[1:],
                       duration=delay, loop=0, quality=quality, method=6)
    return out


def _shared_palette(images: list, colors: int = 128):
    from PIL import Image

    width, height = images[0].size
    sample = images[:: max(1, len(images) // 8)][:8]
    strip = Image.new('RGB', (width, height * len(sample)))
    for i, im in enumerate(sample):
        strip.paste(im, (0, i * height))
    return strip.convert('P', palette=Image.ADAPTIVE, colors=colors)


def _launch_kwargs() -> dict:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
        from browser_runtime import chromium_launch_kwargs
        return chromium_launch_kwargs(disable_gpu=True)
    except Exception:
        return {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('paths', nargs='+', type=Path, help='exported .svg files')
    ap.add_argument('--budget', type=float, default=DEFAULT_BUDGET,
                    help=f'how far a travel time may move (default {DEFAULT_BUDGET})')
    ap.add_argument('--record', type=Path, default=None,
                    help='write one loop here (.gif, .webp, or .png for APNG); one input only')
    ap.add_argument('--fps', type=float, default=25,
                    help='frames per second; 25 lands on a whole GIF tick (default 25)')
    ap.add_argument('--max-width', type=int, default=1600)
    args = ap.parse_args(argv)

    if args.record and len(args.paths) != 1:
        print('--record takes exactly one input', file=sys.stderr)
        return 2

    for path in args.paths:
        period, worst, count = quantize_svg(path, budget=args.budget)
        if not count:
            print(f'--   {path}  no animation')
            continue
        print(f'loop {path}  {period:.2f}s, {count} animations, '
              f'worst travel-time change {worst * 100:.1f}%')
        if args.record:
            out = record(path, args.record, fps=args.fps, max_width=args.max_width)
            print(f'rec  {out} ({out.stat().st_size} bytes)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
