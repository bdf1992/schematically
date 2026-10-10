"""Map render time QA: drawing and measuring the Work Engine map stays inside a time budget.

docs/workengine/map.sov (78 cards, 80 wires, most of them on buses) is opened in headless Chromium
at 1600 x 1000 and fitted. Then:

- render() is timed five times, SovSchematicAPI.layout.metrics({static: true}) five times and
  fitDiagram() five times; the median of each is printed and must be under its budget. (Timing
  stops early once three runs are over the budget: the median is then over it whatever the rest
  would be.)
- Two render() calls in a row draw the same picture: the same d on every wire path and the same x
  and y on every connection label.
- Two diagramBounds() calls in a row return the same four numbers.
- The page logs no errors.

The budgets are three times what this host measured on 2026-10-04 after the fixes below, rounded
up to the next 50 ms:

    render()                         measured  1000 ms   budget  3000 ms
    layout.metrics({static: true})   measured  2438 ms   budget  7350 ms
    fitDiagram()                     measured    92 ms   budget   300 ms

Each measured value is the middle of three sessions' medians of five (render 995, 1000, 1000;
metrics 2393, 2438, 2460; fitDiagram 92, 92, 93). Before the fixes the same host measured 4649 ms,
90241 ms and 4180 ms. GitHub's runner took about 2.1 times this host's seconds on the four slowest
suites that night, so there the budgets leave about 1.4 times, not 3. What the fixes held down:

- src/41-buses.js, src/55-render.js: renderWires asks for the bus routes once and every wire reads
  that answer (withBusRoutes). Before, each wire asked again, and each asking read both ends of
  every bus wire to build its key: wires x wires end readings a render.
- src/30-canvas.js, src/40-routing.js, src/60-interactions.js: every other loop that routes each
  wire (diagramBounds, which fitDiagram calls on every open; captureDragSnapshots and
  settleDraggedRoutes, which run on every press, hold and release of a card; the ghost wire of a
  wire drag and of a carrier end drag) asks once the same way (withBusRoutesOnce). Before,
  diagramBounds asked 79 times and read wire ends 25125 times on the map; now once and 477 times.
- src/57-layout-metrics.js: the crossing count tests a route's sample segment only against the other
  route's segments in the grid cells it touches (layoutCrossIndex), not against all of them.

A budget that fails here means one of those came back, or a new cost of that size arrived: measure
(the Chromium profiler through a CDP session shows it in one run) before raising a number.

A card drag is timed after those. With snap off, the most wired card (rec-surface-registration, 13
wire ends; tests/drag_redraw_parity_qa.py press_most_wired) is pressed and moved down 20 px a step
for five steps; one step is the app's pointermove handler and one frame pass, in one evaluate. Then
the card is released and renderWires() is timed five times. Measured on this host on 2026-10-04:

    drag step                        measured   319 ms   budget  1000 ms   (three times, up to the next 50)
    drag step / renderWires()        measured   0.40     under   1.55      (the line set at 0.76: twice, up to the next 0.05)
    wire groups created per step     measured  13 to 16  under   40        (half of the map's 80)

The step is the middle of three sessions' medians of five (314, 319, 611; the 611 session ran while
the host was busy, its render() at 1291 ms), beside a renderWires() of 800 ms. Before the lanes were
held a step was 594 ms (591, 594, 595, beside a renderWires() of 777 ms, a ratio of 0.76), and before
the keyed pass 1155 ms with all 80 groups created. What holds it down: in src/55-render.js the wire
pass of a move (renderWiresForDrag) computes the signal state once per move and not once per frame
(533 ms a frame on the map), and keeps every wire group whose inputs did not change; in
src/41-buses.js the lane order of every bus is held from the press and ordered again only when the
pointer rests or the move ends (tests/bus_lane_hold_qa.py), which took busRoutesForRender from about
415 ms a step to about 140. What is left in a step: the key of busRoutesForRender (about 58 ms: both
ends of every bus wire and every card's place), the plans of the 79 bus wires (about 76 ms, nearly all
of it routeLead), the keyed wire pass (about 170 ms) and the pointermove handler (about 27 ms). A step
that creates half of the groups or more means the keyed pass stopped keeping them. With
renderWiresForDrag made to call a plain renderWires(), and the lanes not yet held, a step measured
1702 ms, a ratio of 2.18, and created 80 groups. The signal
state computed once per frame and nothing else lost would be a ratio near 1.5, which the 1.55 line
does not catch; the group count does not see it either.
"""
from __future__ import annotations
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402
from drag_redraw_parity_qa import DRAG_STEP, press_most_wired  # noqa: E402

MAP = ROOT / 'docs' / 'workengine' / 'map.sov'
RUNS = 5
RENDER_BUDGET_MS = 3000
METRICS_BUDGET_MS = 7350
FIT_BUDGET_MS = 300  # measured 92 ms on this host on 2026-10-04, times three, up to the next 50
DRAG_STEP_BUDGET_MS = 1000  # measured 319 ms on this host on 2026-10-04 with the bus lanes held, times three, up to the next 50
DRAG_STEP_RATIO = 1.55  # measured 0.76 (594 ms beside a 777 ms renderWires()), times two, up to the next 0.05
# A step created 13 to 16 of the map's 80 wire groups; every step must create fewer than half of them.

TIME_RENDER = "()=>{const s=performance.now();render();return performance.now()-s}"
TIME_METRICS = "()=>{const s=performance.now();SovSchematicAPI.layout.metrics({static:true});return performance.now()-s}"
TIME_FIT = "()=>{const s=performance.now();fitDiagram();return performance.now()-s}"
BOUNDS = "()=>{const b=diagramBounds();return b?[b.l,b.r,b.t,b.b]:null}"
TIME_WIRES = "()=>{const s=performance.now();renderWires();return performance.now()-s}"
GROUPS = "()=>workspace.querySelectorAll('.wire-group').length"
# Every wire group in the document is marked before a step; the ones without the mark after it are new.
MARK_GROUPS = "()=>{for(const g of workspace.querySelectorAll('.wire-group'))g.stoodBeforeStep=true}"
NEW_GROUPS = "()=>[...workspace.querySelectorAll('.wire-group')].filter(g=>!g.stoodBeforeStep).length"

# The picture as drawn: every wire path's d and every connection label's place.
PICTURE = r"""()=>({
  wires:[...workspace.querySelectorAll('.wire-group[data-wire-id]')].map(g=>[g.dataset.wireId,g.querySelector('path.wire')?.getAttribute('d')??null]),
  labels:[...workspace.querySelectorAll('.wire-group[data-wire-id] .connection-label')].map(t=>[t.closest('.wire-group').dataset.wireId,t.getAttribute('x'),t.getAttribute('y')]),
})"""


def timed(page, expression: str, budget: float) -> list[float]:
    """Up to RUNS timings. It stops once more than half of RUNS are over the budget: the median of
    all RUNS would be over it too, and a cost that has come back is not paid five times."""
    runs: list[float] = []
    for _ in range(RUNS):
        runs.append(page.evaluate(expression))
        if sum(r >= budget for r in runs) > RUNS // 2:
            break
    return runs


def main() -> None:
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(250)
        page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [MAP.read_text(encoding='utf-8'), MAP.name])
        page.evaluate('()=>fitDiagram()')
        page.wait_for_timeout(300)

        page.evaluate('()=>render()')
        first = page.evaluate(PICTURE)
        page.evaluate('()=>render()')
        second = page.evaluate(PICTURE)

        renders = timed(page, TIME_RENDER, RENDER_BUDGET_MS)
        metrics = timed(page, TIME_METRICS, METRICS_BUDGET_MS)
        fits = timed(page, TIME_FIT, FIT_BUDGET_MS)
        bounds_first = page.evaluate(BOUNDS)
        bounds_second = page.evaluate(BOUNDS)

        # A card drag: the most wired card is pressed and moved down 20 px a step.
        page.evaluate('()=>{canvasSnapEnabled=false}')
        group_count = page.evaluate(GROUPS)
        card, (x, y) = press_most_wired(page)
        steps, created = [], []
        for k in range(1, RUNS + 1):
            page.evaluate(MARK_GROUPS)
            steps.append(page.evaluate(DRAG_STEP, [x, y + 20 * k]))
            created.append(page.evaluate(NEW_GROUPS))
        page.mouse.up()
        page.wait_for_timeout(300)
        wire_passes = [page.evaluate(TIME_WIRES) for _ in range(RUNS)]
        browser.close()

    render_ms, metrics_ms, fit_ms = statistics.median(renders), statistics.median(metrics), statistics.median(fits)
    print(f"map.sov: {len(first['wires'])} wire paths, {len(first['labels'])} connection labels")
    print(f"render() median of {len(renders)}: {render_ms:.0f} ms (budget {RENDER_BUDGET_MS}); runs {[round(r) for r in renders]}")
    print(f"layout.metrics({{static: true}}) median of {len(metrics)}: {metrics_ms:.0f} ms (budget {METRICS_BUDGET_MS}); runs {[round(r) for r in metrics]}")
    print(f"fitDiagram() median of {len(fits)}: {fit_ms:.0f} ms (budget {FIT_BUDGET_MS}); runs {[round(r) for r in fits]}")
    print(f"diagramBounds() l, r, t, b: {bounds_first}")
    step_ms, wires_ms = statistics.median(steps), statistics.median(wire_passes)
    ratio = step_ms / wires_ms
    print(f"drag step of {card} median of {len(steps)}: {step_ms:.0f} ms (budget {DRAG_STEP_BUDGET_MS}); runs {[round(r) for r in steps]}")
    print(f"drag step / renderWires(): {ratio:.2f} (under {DRAG_STEP_RATIO}); renderWires() median of {len(wire_passes)}: {wires_ms:.0f} ms")
    print(f"wire groups created per drag step: {created} of {group_count} (each under {group_count / 2:.0f})")

    assert not errors, ('the page logs no errors', errors)
    assert len(first['wires']) >= 80 and all(d for _, d in first['wires']), ('every wire of the map is drawn', len(first['wires']))
    assert first['labels'], 'the map draws a connection label'
    moved = [(a, b) for a, b in zip(first['wires'], second['wires']) if a != b]
    assert len(first['wires']) == len(second['wires']) and not moved, ('two renders in a row draw the same wire paths', moved[:3])
    placed = [(a, b) for a, b in zip(first['labels'], second['labels']) if a != b]
    assert len(first['labels']) == len(second['labels']) and not placed, ('two renders in a row place every connection label the same', placed[:3])
    assert render_ms < RENDER_BUDGET_MS, ('render() on the map is over its budget', round(render_ms), RENDER_BUDGET_MS)
    assert metrics_ms < METRICS_BUDGET_MS, ('layout.metrics({static: true}) on the map is over its budget', round(metrics_ms), METRICS_BUDGET_MS)
    assert bounds_first and len(bounds_first) == 4 and bounds_first == bounds_second, ('two diagramBounds() calls in a row return the same four numbers', bounds_first, bounds_second)
    assert fit_ms < FIT_BUDGET_MS, ('fitDiagram() on the map is over its budget', round(fit_ms), FIT_BUDGET_MS)
    assert step_ms < DRAG_STEP_BUDGET_MS, ('a drag step on the map is over its budget', round(step_ms), DRAG_STEP_BUDGET_MS)
    assert ratio < DRAG_STEP_RATIO, ('a drag step on the map costs too much beside one renderWires()', round(ratio, 2), DRAG_STEP_RATIO)
    assert all(n < group_count / 2 for n in created), ('every drag step creates fewer than half of the wire groups', created, group_count)
    print('PASS map render time QA')


if __name__ == '__main__':
    main()
