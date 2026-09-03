"""Where does wire time actually go: route computation, or SVG DOM construction?

Not part of the QA gate. Builds the same synthetic floor as scale_benchmark.py at a
fixed size and times the two halves separately.

    python tests/wire_cost_probe.py --racks 50
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')

PROBE_JS = r'''
async ({racks, serversPerRack, racksPerSpine}) => {
  const once = fn => { const s = performance.now(); fn(); return performance.now() - s };

  nodes.splice(0); wires.splice(0); routeCache.clear(); arrowPoseCache.clear();
  if (typeof invalidateModelIndex === 'function') invalidateModelIndex();
  const RACK_W = 320, RACK_H = 220, GAP = 60, COLS = Math.max(1, Math.ceil(Math.sqrt(racks)));
  const spines = Math.max(1, Math.ceil(racks / racksPerSpine));
  const torPorts = Array.from({length: serversPerRack}, (_, k) => ({id:`p${k+1}`, compatId:`p${k+1}`, side:'bottom', t:(k+.5)/serversPerRack, defaultFlow:'in'}));

  for (let s = 0; s < spines; s++)
    nodes.push(SovSchematicData.makeComponent(diagram, {id:`spine${s}`, symbolId:'act', x:200+s*220, y:60, config:{label:`spine-${s}`}}));
  for (let r = 0; r < racks; r++) {
    const rx = 200 + (r % COLS) * (RACK_W + GAP), ry = 260 + Math.floor(r / COLS) * (RACK_H + GAP);
    const rackId = `rack${r}`;
    nodes.push(SovSchematicData.makeComponent(diagram, {id:rackId, symbolId:'plane', x:rx, y:ry, config:{label:`rack-${r}`, attachmentPoints:[{id:'uplink',compatId:'out',side:'top',t:.5,defaultFlow:'out'}]}}));
    const canvasId = `canvas:component:${rackId}`;
    nodes.push(SovSchematicData.makeComponent(diagram, {id:`tor${r}`, symbolId:'act', x:rx, y:ry-70, canvasId, parentId:rackId, config:{label:`tor-${r}`, attachmentPoints:torPorts}}));
    for (let k = 0; k < serversPerRack; k++) {
      const sx = rx - RACK_W/2 + 40 + (k % 4) * 70, sy = ry + 20 + Math.floor(k/4) * 60;
      nodes.push(SovSchematicData.makeComponent(diagram, {id:`srv${r}_${k}`, symbolId:'buffer', x:sx, y:sy, canvasId, parentId:rackId, config:{label:`s${k}`}}));
    }
  }
  const addWire = v => { try { wires.push(SovSchematicData.makeWire(diagram, v)) } catch (e) {} };
  for (let r = 0; r < racks; r++) {
    for (let k = 0; k < serversPerRack; k++)
      addWire({id:`w${r}_${k}`, a:`srv${r}_${k}`, aSide:'out', b:`tor${r}`, bSide:`p${k+1}`, config:{direction:'forward'}});
    addWire({id:`up${r}`, a:`rack${r}`, aSide:'out', b:`spine${Math.floor(r/racksPerSpine)}`, bSide:'in', config:{direction:'forward'}});
  }
  if (typeof invalidateModelIndex === 'function') invalidateModelIndex();

  render();                       // warm caches once
  const t = {};
  t.signal = once(() => computeSignalState());

  // Route computation alone, cache cleared so it is real work, no DOM touched.
  t.routeOnly = once(() => {
    routeCache.clear();
    if (typeof invalidateRouteGrid === 'function') invalidateRouteGrid();
    wires.forEach((w, i) => {
      const A = portPos(nodeById(w.a), w.aSide), B = portPos(nodeById(w.b), w.bSide);
      if (A && B) stableRouteForWire(i, w, A, B, []);
    });
  });

  // Full wire render with the route cache already warm from the line above.
  t.wiresWarmRoutes = once(() => renderWires());

  // Full wire render with cold routes: routing + DOM together.
  t.wiresColdRoutes = once(() => {
    routeCache.clear();
    if (typeof invalidateRouteGrid === 'function') invalidateRouteGrid();
    renderWires();
  });

  t.fullRender = once(() => render());
  return {components: nodes.length, wires: wires.length, svgElements: document.querySelectorAll('#nodes *, #wires *').length, ...t};
}
'''

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--racks', type=int, default=50)
    ap.add_argument('--servers-per-rack', type=int, default=8)
    ap.add_argument('--racks-per-spine', type=int, default=16)
    args = ap.parse_args()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(**chromium_launch_kwargs())
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        page.set_content(HTML)
        page.wait_for_function('typeof render === "function"')
        out = page.evaluate(PROBE_JS, {'racks': args.racks, 'serversPerRack': args.servers_per_rack, 'racksPerSpine': args.racks_per_spine})
        browser.close()

    print(json.dumps(out, indent=2))
    routing = out['routeOnly']
    dom = out['wiresWarmRoutes']
    print(f"\nracks={args.racks} components={out['components']} wires={out['wires']}")
    print(f"  route computation : {routing:8.1f} ms")
    print(f"  wire DOM build    : {dom:8.1f} ms  (routes already cached)")
    print(f"  both together     : {out['wiresColdRoutes']:8.1f} ms")
    print(f"  full render()     : {out['fullRender']:8.1f} ms")
    total = routing + dom
    if total > 0:
        print(f"  -> routing is {100*routing/total:.0f}% of wire cost, DOM is {100*dom/total:.0f}%")

if __name__ == '__main__':
    main()
