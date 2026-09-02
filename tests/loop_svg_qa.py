"""Looping SVG export QA.

A looped export claims one thing: after the period written into the file, every packet is
back where it started. This checks that claim the only way it can be checked — by stepping
the SVG clock and comparing frames — plus the arithmetic underneath it.

  - choose_period returns a period every duration divides into, inside the budget;
  - quantize is idempotent, so a second pass cannot leave a stale period behind;
  - an export with --loop carries a period and durations that divide it exactly;
  - the rendered frame at one period matches the frame at two, and differs in between.

The frame check runs on the second and third cycles: at t=0 the browser has not yet applied
animateMotion and every packet still sits at its authored origin.
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
from browser_runtime import chromium_launch_kwargs  # noqa: E402
from export_svg import export_documents  # noqa: E402
from loop_svg import DUR, LOOP_MARK, choose_period, loop_period, quantize  # noqa: E402

# Two of the golden documents: one flat chain, one with a plane, boundary points and an
# authority into a control port, so the wires differ in length and the periods differ too.
DOCUMENTS = ['01-source-hold.sov', '08-gated-service.sov']
BUDGET = 0.08


def check_period_arithmetic() -> None:
    durations = [0.72, 1.52, 1.2571428, 2.5371428, 1.1428571]
    period, worst = choose_period(durations, budget=BUDGET)
    assert worst <= BUDGET, f'worst change {worst} exceeds budget {BUDGET}'
    for d in durations:
        k = max(1, round(period / d))
        assert abs(period / k - d) / d <= BUDGET, f'{d} does not fit {period}'

    # A duration longer than any candidate period still gets k=1 rather than k=0.
    period, _ = choose_period([30.0], budget=BUDGET)
    assert period > 0, 'a long duration produced no period'


def check_idempotent() -> None:
    svg = ('<svg><animateMotion dur="1.3s"/><animateMotion dur="2.1s"/></svg>')
    once, period, _worst, count = quantize(svg, budget=BUDGET)
    assert count == 2 and period > 0, (count, period)
    twice, period2, _w2, _c2 = quantize(once, budget=BUDGET)
    assert twice == once, 'a second pass changed the file'
    assert period2 == period, f'a second pass reported {period2}, not {period}'


def frame_hash(page, t: float) -> str:
    page.evaluate("t => document.querySelector('svg').setCurrentTime(t)", t)
    return hashlib.sha256(page.query_selector('svg').screenshot()).hexdigest()


def main() -> None:
    check_period_arithmetic()
    check_idempotent()

    from playwright.sync_api import sync_playwright

    sources = [ROOT / 'examples' / name for name in DOCUMENTS]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        results = export_documents(sources, out, 'light', 48, BUDGET)
        checked = 0
        with sync_playwright() as p:
            browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
            page = browser.new_page(viewport={'width': 1600, 'height': 1000})
            for r in results:
                assert not r['errors'], f"{r['source'].name}: {r['errors']}"
                target = r['target']
                text = target.read_text(encoding='utf-8')
                durations = [float(d) for d in DUR.findall(text)]
                if not durations:
                    continue
                assert LOOP_MARK in text, f'{target.name}: no loop period recorded'
                period = loop_period(target)
                assert abs(period - r['loop']) < 1e-6, f'{target.name}: period disagrees with report'
                for d in durations:
                    k = round(period / d)
                    assert k >= 1 and abs(period / k - d) < 1e-3, \
                        f'{target.name}: {d}s is not a divisor of {period}s'

                page.goto(target.resolve().as_uri())
                page.wait_for_selector('svg')
                page.evaluate("() => document.querySelector('svg').pauseAnimations()")
                start = frame_hash(page, period)
                end = frame_hash(page, period * 2)
                # Half a period is the wrong place to look for movement: an animation whose
                # duration divides the period evenly is back at the same phase there. Half
                # of the shortest duration always is not.
                moved = frame_hash(page, period + min(durations) / 2)
                assert start == end, f'{target.name}: not back at the start after {period}s'
                assert start != moved, f'{target.name}: nothing moved half a packet-trip in'
                checked += 1
            browser.close()

    assert checked, 'no document under test had an animation'
    print(f'PASS looping SVG export QA ({checked} looped document(s))')


if __name__ == '__main__':
    main()
