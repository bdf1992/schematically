"""Map keyboard move QA: what a one-step keyboard move of a card costs on the Work Engine map.

The map of the Work Engine (map.sov) (78 cards, 80 wires, most of them on buses) is opened in headless Chromium
at 1600 x 1000 and fitted, snap off. The most wired card (rec-surface-registration, 13 wire ends;
the first of CANDIDATES in the drag redraw parity test) is selected and moved down one unit by the
ArrowDown key, five times. One move is the app's own keydown handler (moveSelectedByArrow) and then
the settle its timer would run (finishKeyboardMove), in one evaluate: the 140 ms the timer waits
(ROUTE_SETTLE_DELAY) is a declared rest, not work, and is not counted.

Printed for every move, and the median over the five: the milliseconds of the move. No time is
asserted: a time on a shared runner is not a fact about the product.

Counted for every move, and held at what dev measured on 2026-10-08, so they cannot grow:

    wire groups added to the document         173   (80 by the keydown pass, 93 by the settle)
    routes computed by the open router          5   (calls of routePoints)
    bus route sets built                        2   (answers of busRoutesForRender that are a new object)
    wire passes                                 3   (calls of renderWiresOnce)

Printed and not held: the wire groups standing after a move that did not stand before it (80 of 80),
and the routes asked for (calls of stableRouteForWire, 387).

A count over its ceiling means a move started to do more work: find the pass that grew before
raising a number. A count under its ceiling is the wanted direction: lower the ceiling to it in the
change that brought it down.
"""
from __future__ import annotations
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402
from drag_redraw_parity_qa import CANDIDATES  # noqa: E402

MAP = ROOT / 'docs' / 'workengine' / 'map.sov'
MOVES = 5
GROUPS_ADDED_CEILING = 173
OPEN_ROUTES_CEILING = 5
BUS_ROUTE_SETS_CEILING = 2
WIRE_PASSES_CEILING = 3

# Counters around the app's own functions, and an observer that sees every wire group added.
COUNT = r"""()=>{
  const n=window.moveCounts={openRoutes:0,asked:0,passes:0,busSets:0};
  const rp=routePoints;routePoints=function(){n.openRoutes++;return rp.apply(this,arguments)};
  const sr=stableRouteForWire;stableRouteForWire=function(){n.asked++;return sr.apply(this,arguments)};
  const rw=renderWiresOnce;renderWiresOnce=function(){n.passes++;return rw.apply(this,arguments)};
  const br=busRoutesForRender;let last=busRouteState;
  busRoutesForRender=function(){const s=br.apply(this,arguments);if(s!==last){n.busSets++;last=s}return s};
  const seen=new MutationObserver(()=>{});seen.observe(workspace,{childList:true,subtree:true});
  window.wireGroupsAdded=()=>seen.takeRecords().reduce((sum,r)=>sum+[...r.addedNodes].filter(x=>x.classList?.contains('wire-group')).length,0);
}"""
# One move: the keydown, then the settle its timer would run. Returns its milliseconds and counts.
MOVE = r"""(card)=>{
  const n=window.moveCounts;for(const k in n)n[k]=0;window.wireGroupsAdded();
  for(const g of workspace.querySelectorAll('.wire-group'))g.stoodBeforeMove=true;
  const node=nodes.find(q=>q.id===card),y=node.y,start=performance.now();
  document.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',code:'ArrowDown',bubbles:true,cancelable:true}));
  const keyed=performance.now(),moving=keyboardMoveNodeId,addedByKey=window.wireGroupsAdded();
  finishKeyboardMove({});
  const ms=performance.now()-start,groups=[...workspace.querySelectorAll('.wire-group')];
  return {ms,keyMs:keyed-start,dy:node.y-y,moving,after:keyboardMoveNodeId,addedByKey,addedBySettle:window.wireGroupsAdded(),
    groups:groups.length,rebuilt:groups.filter(g=>!g.stoodBeforeMove).length,...n};
}"""


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
        page.evaluate('()=>{canvasSnapEnabled=false}')
        card = page.evaluate(CANDIDATES)[0]
        page.evaluate('(id)=>selectNode(id)', card)
        page.evaluate(COUNT)
        moves = []
        for _ in range(MOVES):
            moves.append(page.evaluate(MOVE, card))
            page.wait_for_timeout(300)
        browser.close()

    added = [m['addedByKey'] + m['addedBySettle'] for m in moves]
    print(f"one-step keyboard move of {card} on {MAP.name}: median of {len(moves)}: {statistics.median(m['ms'] for m in moves):.0f} ms; runs {[round(m['ms']) for m in moves]} (keydown part {[round(m['keyMs']) for m in moves]})")
    print(f"wire groups added per move: {added} (keydown pass {[m['addedByKey'] for m in moves]}, settle {[m['addedBySettle'] for m in moves]}; each at most {GROUPS_ADDED_CEILING})")
    print(f"wire groups rebuilt per move: {[m['rebuilt'] for m in moves]} of {moves[0]['groups']}")
    print(f"routes computed by the open router per move: {[m['openRoutes'] for m in moves]} (each at most {OPEN_ROUTES_CEILING}); routes asked for: {[m['asked'] for m in moves]}")
    print(f"bus route sets built per move: {[m['busSets'] for m in moves]} (each at most {BUS_ROUTE_SETS_CEILING}); wire passes: {[m['passes'] for m in moves]} (each at most {WIRE_PASSES_CEILING})")

    assert not errors, ('the page logs no errors', errors)
    assert all(m['moving'] == card and m['dy'] == 1 and m['after'] is None for m in moves), ('each key moves the card one unit inside a keyboard move that then settles', [(m['moving'], m['dy'], m['after']) for m in moves])
    assert all(n <= GROUPS_ADDED_CEILING for n in added), ('a one-step move adds more wire groups than it did', added, GROUPS_ADDED_CEILING)
    assert all(m['openRoutes'] <= OPEN_ROUTES_CEILING for m in moves), ('a one-step move runs the open router more than it did', [m['openRoutes'] for m in moves], OPEN_ROUTES_CEILING)
    assert all(m['busSets'] <= BUS_ROUTE_SETS_CEILING for m in moves), ('a one-step move builds more bus route sets than it did', [m['busSets'] for m in moves], BUS_ROUTE_SETS_CEILING)
    assert all(m['passes'] <= WIRE_PASSES_CEILING for m in moves), ('a one-step move makes more wire passes than it did', [m['passes'] for m in moves], WIRE_PASSES_CEILING)
    print('PASS map keyboard move QA')


if __name__ == '__main__':
    main()
