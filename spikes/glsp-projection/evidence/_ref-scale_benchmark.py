"""Scale benchmark: where does the current SVG renderer stop being usable?

Not part of the QA gate (it deliberately runs until the renderer falls over).
Run by hand:

    python tests/scale_benchmark.py            # escalate until a step exceeds the cap
    python tests/scale_benchmark.py --max-racks 50 --cap-ms 5000

Topology per step is a synthetic datacenter built through the real data
factories so containment, ports and wires are all genuine model objects:

    spine switch  (global canvas)          1 per 16 racks
    rack          (2D container, 'plane')  R racks
      tor switch  (inside rack)            1 per rack, SERVERS_PER_RACK authored ports
      server      (inside rack)            SERVERS_PER_RACK per rack, 3 default ports
    wires: server.out -> tor.p<k>  (inside rack)     rack.out -> spine.in  (global)

The product bar this is measured against (stated assumption, edit TARGET_*):
a hyperscale floor of ~200k servers and ~5k switches, ~1.4M ports.
"""
from __future__ import annotations
import argparse, json, math, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright, Error as PlaywrightError
sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')
OUT = ROOT / 'tests' / 'scale-benchmark-results.json'

SERVERS_PER_RACK = 8
RACKS_PER_SPINE = 16
TARGET_SERVERS = 200_000
TARGET_SWITCHES = 5_000
TARGET_PORTS = TARGET_SERVERS * 6 + TARGET_SWITCHES * 48
RACK_STEPS = [1, 2, 5, 10, 25, 50, 100, 200, 400, 800]

BUILD_JS = r'''
async ({racks, serversPerRack, racksPerSpine}) => {
  const t = {};
  const once = fn => { const s = performance.now(); fn(); return performance.now() - s };
  const frame = async fn => {
    fn();
    const s = performance.now();
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    return performance.now() - s;
  };

  // ---- build the model through the real factories ----
  nodes.splice(0); wires.splice(0); routeCache.clear(); arrowPoseCache.clear();
  let wireFailures = 0;
  const RACK_W = 320, RACK_H = 220, GAP = 60, COLS = Math.max(1, Math.ceil(Math.sqrt(racks)));
  const spines = Math.max(1, Math.ceil(racks / racksPerSpine));
  const torPorts = Array.from({length: serversPerRack}, (_, k) => ({id: `p${k+1}`, compatId: `p${k+1}`, side: 'bottom', t: (k + .5) / serversPerRack, defaultFlow: 'in'}));

  t.build = once(() => {
    for (let s = 0; s < spines; s++) {
      nodes.push(SovSchematicData.makeComponent(diagram, {id: `spine${s}`, symbolId: 'act', x: 200 + s * 220, y: 60, config: {label: `spine-${s}`}}));
    }
    for (let r = 0; r < racks; r++) {
      const rx = 200 + (r % COLS) * (RACK_W + GAP), ry = 260 + Math.floor(r / COLS) * (RACK_H + GAP);
      const rackId = `rack${r}`;
      nodes.push(SovSchematicData.makeComponent(diagram, {id: rackId, symbolId: 'plane', x: rx, y: ry, config: {label: `rack-${r}`, attachmentPoints: [{id: 'uplink', compatId: 'out', side: 'top', t: .5, defaultFlow: 'out'}]}}));
      const canvasId = `canvas:component:${rackId}`;
      nodes.push(SovSchematicData.makeComponent(diagram, {id: `tor${r}`, symbolId: 'act', x: rx, y: ry - 70, canvasId, parentId: rackId,
        config: {label: `tor-${r}`, attachmentPoints: torPorts}}));
      for (let k = 0; k < serversPerRack; k++) {
        const sx = rx - RACK_W / 2 + 40 + (k % 4) * 70, sy = ry + 20 + Math.floor(k / 4) * 60;
        nodes.push(SovSchematicData.makeComponent(diagram, {id: `srv${r}_${k}`, symbolId: 'buffer', x: sx, y: sy, canvasId, parentId: rackId, config: {label: `s${k}`}}));
      }
    }
    const addWire = v => { try { wires.push(SovSchematicData.makeWire(diagram, v)) } catch (e) { wireFailures++ } };
    for (let r = 0; r < racks; r++) {
      for (let k = 0; k < serversPerRack; k++) addWire({id: `w${r}_${k}`, a: `srv${r}_${k}`, aSide: 'out', b: `tor${r}`, bSide: `p${k+1}`, config: {direction: 'forward'}});
      addWire({id: `up${r}`, a: `rack${r}`, aSide: 'out', b: `spine${Math.floor(r / racksPerSpine)}`, bSide: 'in', config: {direction: 'forward'}});
    }
  });
  const wiresOnGlobal = wires.filter(w => w.canvasId === 'canvas:global').length;
  const wiresInRacks = wires.length - wiresOnGlobal;
  let ports = 0; for (const n of nodes) ports += Attachment.pointSpecs(n).length;

  // ---- render costs ----
  t.cold = once(() => render());
  t.signal = once(() => computeSignalState());
  t.wiresOnly = once(() => renderWires());
  t.warm = once(() => render());
  const svgElements = workspace.querySelectorAll('*').length;

  // ---- interaction costs ----
  const vb = workspace.getAttribute('viewBox').split(/\s+/).map(Number);
  t.panFrame = await frame(() => workspace.setAttribute('viewBox', `${vb[0] + 40} ${vb[1] + 40} ${vb[2]} ${vb[3]}`));
  t.zoomFrame = await frame(() => workspace.setAttribute('viewBox', `${vb[0]} ${vb[1]} ${vb[2] * 2} ${vb[3] * 2}`));
  workspace.setAttribute('viewBox', vb.join(' '));
  const victim = nodes.find(n => n.id === 'srv0_0');
  t.dragOne = once(() => { victim.x += 5; victim.placement.x = victim.x; routeCache.clear(); arrowPoseCache.clear(); render(); });
  // one "dynamic" overlay: signal propagation with colour diffusion on
  const prevDiffuse = colorEngine.diffuse; colorEngine.diffuse = true;
  t.signalDiffuse = once(() => computeSignalState());
  colorEngine.diffuse = prevDiffuse;

  const heapMB = performance.memory ? performance.memory.usedJSHeapSize / 1048576 : null;
  return {racks, spines, components: nodes.length, wires: wires.length, wiresOnGlobal, wiresInRacks, wireFailures, ports, svgElements, heapMB, ...t};
}
'''


def fmt(v):
    if v is None: return '—'
    if isinstance(v, float):
        return f'{v:,.0f}' if v >= 100 else f'{v:.1f}'
    return f'{v:,}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-racks', type=int, default=RACK_STEPS[-1])
    ap.add_argument('--cap-ms', type=float, default=10_000, help='Stop escalating once cold render exceeds this.')
    ap.add_argument('--step-timeout-s', type=float, default=180)
    args = ap.parse_args()

    kwargs = chromium_launch_kwargs()
    kwargs['args'] = kwargs.get('args', []) + ['--enable-precise-memory-info']
    results, stopped = [], None
    with sync_playwright() as p:
        browser = p.chromium.launch(**kwargs)
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        page.set_default_timeout(args.step_timeout_s * 1000)
        page.set_content(HTML, wait_until='load'); page.wait_for_timeout(200)
        for racks in RACK_STEPS:
            if racks > args.max_racks: break
            t0 = time.time()
            try:
                r = page.evaluate(BUILD_JS, {'racks': racks, 'serversPerRack': SERVERS_PER_RACK, 'racksPerSpine': RACKS_PER_SPINE})
            except PlaywrightError as e:
                stopped = f'racks={racks}: browser step failed after {time.time()-t0:.0f}s: {str(e).splitlines()[0]}'
                print(stopped); break
            r['wallS'] = round(time.time() - t0, 1)
            results.append(r)
            print(f"racks={racks:<4} components={r['components']:<6} wires={r['wires']:<6} ports={r['ports']:<7} cold={r['cold']:.0f}ms warm={r['warm']:.0f}ms drag={r['dragOne']:.0f}ms pan={r['panFrame']:.1f}ms svg={r['svgElements']} wireFail={r['wireFailures']}", flush=True)
            if r['cold'] > args.cap_ms:
                stopped = f"racks={racks}: cold render {r['cold']:.0f} ms exceeded cap {args.cap_ms:.0f} ms"
                break
        browser.close()

    # ---- extrapolation from the last two steps (power-law fit on component count) ----
    projection = {}
    if len(results) >= 2:
        a, b = results[-2], results[-1]
        for key in ('warm', 'dragOne', 'cold'):
            k = math.log(b[key] / a[key]) / math.log(b['components'] / a['components'])
            projection[key] = {'exponent': round(k, 2),
                               **{f'at_{n}': b[key] * (n / b['components']) ** k for n in (10_000, 100_000, 1_000_000)}}
        ppc = b['ports'] / b['components']
        projection['components_for_target_ports'] = TARGET_PORTS / ppc
    report = {'servers_per_rack': SERVERS_PER_RACK, 'target': {'servers': TARGET_SERVERS, 'switches': TARGET_SWITCHES, 'ports': TARGET_PORTS},
              'stopped': stopped, 'steps': results, 'projection': projection}
    OUT.write_text(json.dumps(report, indent=2), encoding='utf-8')

    print('\n| racks | components | wires | ports | SVG elems | heap MB | cold ms | warm ms | wires ms | signal ms | drag ms | pan ms | zoom ms |')
    print('|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
    for r in results:
        print('| ' + ' | '.join(fmt(r[k]) for k in ('racks', 'components', 'wires', 'ports', 'svgElements', 'heapMB', 'cold', 'warm', 'wiresOnly', 'signal', 'dragOne', 'panFrame', 'zoomFrame')) + ' |')
    if stopped: print(f'\nStopped: {stopped}')
    if projection:
        print(f"\nTarget: {TARGET_PORTS:,} ports ≈ {projection['components_for_target_ports']:,.0f} components at this topology's ports/component.")
        for key, pr in projection.items():
            if not isinstance(pr, dict): continue
            print(f"{key}: grows ~n^{pr['exponent']}; projected {pr['at_10000']/1000:,.1f} s @10k, {pr['at_100000']/1000:,.0f} s @100k, {pr['at_1000000']/1000:,.0f} s @1M components")
    print(f'\nWrote {OUT}')


if __name__ == '__main__':
    main()
