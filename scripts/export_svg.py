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
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'
sys.path.insert(0, str(ROOT / 'tests'))
from browser_runtime import chromium_launch_kwargs  # noqa: E402

# Runs inside the page. Mirrors exportSvgFile() in src/75-persistence.js, plus:
#  - a content-fitted viewBox with explicit width/height so the file is self-sizing;
#  - computed styles inlined as attributes, because the exported file cannot see app.css;
#  - display:none subtrees dropped instead of carried invisibly.
EXPORT_JS = r"""
(opts) => {
  if (typeof cancelWireDrag === 'function') cancelWireDrag();
  const live = workspace;
  const INHERITED = ['fill','fill-opacity','fill-rule','stroke','stroke-width','stroke-opacity','stroke-dasharray',
    'stroke-dashoffset','stroke-linecap','stroke-linejoin','color','font-family','font-size','font-weight','font-style',
    'letter-spacing','text-anchor','dominant-baseline','visibility','paint-order','text-rendering','shape-rendering'];
  const OWN = {opacity:'1', filter:'none', 'mix-blend-mode':'normal', transform:'none'};
  const VISUAL = new Set(['svg','g','path','rect','circle','ellipse','line','polyline','polygon','text','tspan','use','foreignObject','image']);
  const styleOf = new Map();
  const walk = (el, parentStyle) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none') { styleOf.set(el, null); return; }
    const out = {};
    for (const p of INHERITED) {
      const v = cs.getPropertyValue(p);
      if (!v) continue;
      if (!parentStyle || parentStyle[p] !== v) out[p] = v;
    }
    for (const p in OWN) {
      const v = cs.getPropertyValue(p);
      if (v && v !== OWN[p]) out[p] = v;
    }
    if (out.transform) {
      out['transform-box'] = cs.getPropertyValue('transform-box');
      out['transform-origin'] = cs.getPropertyValue('transform-origin');
    }
    const merged = Object.assign({}, parentStyle || {});
    for (const p of INHERITED) merged[p] = cs.getPropertyValue(p);
    styleOf.set(el, out);
    for (const child of el.children) walk(child, merged);
  };
  walk(live, null);

  const clone = live.cloneNode(true);
  const liveEls = [live, ...live.querySelectorAll('*')];
  const cloneEls = [clone, ...clone.querySelectorAll('*')];
  const drop = [];
  for (let i = 0; i < liveEls.length; i++) {
    const src = liveEls[i], dst = cloneEls[i];
    const st = styleOf.get(src);
    if (st === null) { drop.push(dst); continue; }
    if (st === undefined || !VISUAL.has(dst.tagName)) continue;
    const parts = [];
    for (const p in st) parts.push(`${p}:${st[p]}`);
    dst.removeAttribute('tabindex');
    if (parts.length) dst.setAttribute('style', parts.join(';'));
  }
  for (const el of drop) el.remove();
  clone.querySelector('#ghostLayer')?.replaceChildren();
  clone.querySelector('#paletteDropLayer')?.replaceChildren();
  clone.querySelectorAll('.selected,.snap-target,.wiring-source').forEach(x => x.classList.remove('selected','snap-target','wiring-source'));
  clone.querySelectorAll('.port-hit,.wire-hit').forEach(x => x.remove());

  // A wire on a local surface already sits just after its host in the node layer
  // (renderWires), so the picture shows it above the host body with no lifting here.

  const defs = document.querySelector('.hidden-symbols defs').cloneNode(true);
  clone.insertBefore(defs, clone.firstChild);

  const pad = opts.pad ?? 48;
  const b = typeof diagramBounds === 'function' ? diagramBounds() : null;
  if (b) {
    const w = Math.max(160, b.r - b.l + pad * 2), h = Math.max(120, b.b - b.t + pad * 2);
    clone.setAttribute('viewBox', `${b.l - pad} ${b.t - pad} ${w} ${h}`);
    clone.setAttribute('width', String(Math.round(w)));
    clone.setAttribute('height', String(Math.round(h)));
  }
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  clone.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');
  clone.removeAttribute('tabindex');
  clone.removeAttribute('aria-label');
  const bg = getComputedStyle(live).backgroundColor;
  const own = clone.getAttribute('style') || '';
  clone.setAttribute('style', `${own}${own && !own.endsWith(';') ? ';' : ''}background-color:${bg}`);
  return new XMLSerializer().serializeToString(clone);
}
"""


def export_documents(paths: list[Path], out_dir: Path | None = None, appearance: str = 'light', pad: int = 48) -> list[dict]:
    """Export each .sov to .svg. Returns one record per input: {source, target, bytes, errors}."""
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
            target = (out_dir / f'{src.stem}.svg') if out_dir else src.with_suffix('.svg')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(svg, encoding='utf-8', newline='\n')
            results.append({'source': src, 'target': target, 'bytes': len(svg.encode('utf-8')), 'errors': errors[before:]})
        browser.close()
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('paths', nargs='*', help='.sov files (default: examples/*.sov)')
    ap.add_argument('--out', type=Path, default=None, help='output directory (default: beside each input)')
    ap.add_argument('--appearance', choices=['light', 'dark'], default='light')
    ap.add_argument('--pad', type=int, default=48, help='padding around content in canvas units')
    args = ap.parse_args(argv)
    paths = [Path(p) for p in args.paths] or sorted((ROOT / 'examples').glob('*.sov'))
    if not paths:
        print('no .sov inputs', file=sys.stderr)
        return 2
    failed = 0
    for r in export_documents(paths, args.out, args.appearance, args.pad):
        status = 'ok ' if not r['errors'] else 'ERR'
        print(f"{status} {r['source']} -> {r['target']} ({r['bytes']} bytes)")
        for e in r['errors']:
            failed += 1
            print(f'    page error: {e}', file=sys.stderr)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
