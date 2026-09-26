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
    python scripts/export_svg.py examples/logic/half-adder.sov --logic-state A=1,B=1   # live signal state
    python scripts/export_svg.py examples/logic/half-adder.sov --logic-state A=1,B=1 --monochrome
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



# Runs inside the page after a logic document is open, before serialisation. Draws live
# signal state the way VISUAL-LANGUAGE.md settles it: a high net in the signal colour with the
# voltage glow and 0.6 px heavier, a low net in plain ink, a value chip at each pin; with
# monochrome, weight alone. Packets are removed: a snapshot has no change in flight, and a
# moving dot would say there is one.
STATE_JS = r"""
(opts) => {
  const NS = 'http://www.w3.org/2000/svg';
  const dark = document.documentElement.dataset.appearance === 'dark';
  const hi = dark ? '#3987e5' : '#2a78d6';
  const css = getComputedStyle(document.documentElement);
  const ink = css.getPropertyValue('--canvas-ink').trim() || (dark ? '#E7E8E3' : '#42423E');
  const muted = css.getPropertyValue('--canvas-muted').trim() || (dark ? '#AEB0AA' : '#73736D');
  const panel = css.getPropertyValue('--canvas-tone').trim() || (dark ? '#17191B' : '#FEFEFC');
  const chipped = new Set();
  for (const group of document.querySelectorAll('.wire-group[data-wire-id]')) {
    const st = opts.wires[group.dataset.wireId];
    if (!st) continue;
    group.querySelectorAll('.wire-packet').forEach(x => x.remove());
    group.querySelectorAll('animateMotion,animate').forEach(x => x.remove());
    const high = st.value === 1;
    group.style.setProperty('--wire-ink', opts.monochrome ? (high ? ink : muted) : (high ? hi : ink));
    group.style.setProperty('--voltage-ink', opts.monochrome ? ink : hi);
    group.dataset.logicValue = String(st.value);
    const wire = group.querySelector('path.wire');
    if (wire) {
      wire.style.strokeWidth = opts.monochrome ? (high ? '3.6px' : '1.4px') : (high ? '2.9px' : '2.3px');
      if (opts.monochrome && !high) wire.style.strokeDasharray = '5 5';
    }
    const glow = group.querySelector('path.wire-voltage');
    if (glow) glow.style.opacity = (!opts.monochrome && high) ? '0.18' : '0';
    if (!wire) continue;
    const total = wire.getTotalLength();
    const ends = [[st.a, 12], [st.b, total - 12]];
    for (const [key, at] of ends) {
      if (!key || chipped.has(key)) continue;
      chipped.add(key);
      const p = wire.getPointAtLength(Math.max(0, Math.min(total, at)));
      const g = document.createElementNS(NS, 'g');
      g.setAttribute('class', 'logic-chip'); g.dataset.pin = key; g.dataset.value = String(st.value);
      const r = document.createElementNS(NS, 'rect');
      r.setAttribute('x', p.x - 7); r.setAttribute('y', p.y - 7); r.setAttribute('width', 14); r.setAttribute('height', 14); r.setAttribute('rx', 3);
      const on = high ? (opts.monochrome ? ink : hi) : panel;
      r.setAttribute('fill', on); r.setAttribute('stroke', high ? on : ink); r.setAttribute('stroke-width', '1.2');
      const t = document.createElementNS(NS, 'text');
      t.setAttribute('x', p.x); t.setAttribute('y', p.y + 3.5); t.setAttribute('text-anchor', 'middle');
      t.setAttribute('font-size', '9.5'); t.setAttribute('font-weight', '700'); t.setAttribute('font-family', 'ui-monospace, Menlo, monospace');
      t.setAttribute('fill', high ? panel : ink); t.textContent = String(st.value);
      g.append(r, t); group.appendChild(g);
    }
  }
  return Object.keys(opts.wires).length;
}
"""


def logic_state(path: Path, vector: dict) -> dict:
    """Each top-level wire's net value after applying `vector`, and the pins at its ends."""
    from logic_sov import Circuit
    c = Circuit(path)
    result = c.apply(vector)
    doc = __import__('json').loads(path.read_text(encoding='utf-8'))
    points = {x['id'] for x in doc.get('components', []) if x.get('symbolId') == 'point'}
    wires = {}
    for w in doc.get('wires', []):
        a = (w['a'], 'out' if w['a'] in points else w['aSide'])
        b = (w['b'], 'out' if w['b'] in points else w['bSide'])
        value = c.value[c.net_of[a]] if a in c.net_of else None
        if value is None:
            continue
        wires[w['id']] = {'value': int(value), 'a': f'{a[0]}.{a[1]}', 'b': f'{b[0]}.{b[1]}'}
    return {'wires': wires, 'outputs': result['outputs']}


def export_documents(paths: list[Path], out_dir: Path | None = None, appearance: str = 'light', pad: int = 48, loop: float | None = None,
                     logic: dict | None = None, monochrome: bool = False) -> list[dict]:
    """Export each .sov to .svg. Returns one record per input: {source, target, bytes, errors, loop}.

    `loop` is a travel-time budget: when given, every animation is snapped to a divisor of
    one period so the file repeats. See scripts/loop_svg.py.

    `logic` is an input vector for a logic document: the export then draws the circuit's live
    signal state after that vector settles (`monochrome`: by line weight alone).
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
            # An export draws the document at its own scale: full glyphs, whatever the camera.
            page.evaluate('()=>{ if (typeof applyGlyphSizeRule === "function") applyGlyphSizeRule(1); }')
            if logic is not None:
                state = logic_state(src, logic)
                page.evaluate(STATE_JS, {'wires': state['wires'], 'monochrome': monochrome})
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
    ap.add_argument('--logic-state', default=None, help="draw a logic document's live state after these inputs, e.g. A=1,B=1")
    ap.add_argument('--monochrome', action='store_true', help='with --logic-state: state by line weight, no colour')
    args = ap.parse_args(argv)
    paths = [Path(p) for p in args.paths] or sorted((ROOT / 'examples').glob('*.sov'))
    if not paths:
        print('no .sov inputs', file=sys.stderr)
        return 2
    failed = 0
    logic = None
    if args.logic_state is not None:
        from logic_sov import parse_vector
        logic = parse_vector(args.logic_state)
    for r in export_documents(paths, args.out, args.appearance, args.pad, args.loop, logic, args.monochrome):
        status = 'ok ' if not r['errors'] else 'ERR'
        loop = f", loops at {r['loop']:.2f}s" if r.get('loop') else ''
        print(f"{status} {r['source']} -> {r['target']} ({r['bytes']} bytes{loop})")
        for e in r['errors']:
            failed += 1
            print(f'    page error: {e}', file=sys.stderr)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
