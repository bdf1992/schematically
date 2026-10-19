"""Deliver a .sov as one interactive HTML file.

The file opens from disk in any browser, with nothing installed. It carries the picture twice
(light and dark, drawn by the editor's own export, render.svg) and the graph core's arcs
(SovSchematicGraph.build: direction, access and blocked wires already applied), and lets a
reader search, open a card's details, trace what a card reaches downstream or is reached from
upstream, find a route between two cards, zoom and pan, switch theme, save a PNG, print to PDF,
and share any of those states as a link (the URL fragment).

Usage:
    python scripts/export_html.py                      # every examples/*.sov -> examples/*.html
    python scripts/export_html.py a.sov --out build/   # into a directory
    python scripts/export_html.py a.sov --open         # and open the result
"""
from __future__ import annotations
import argparse
import json
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'
TEMPLATE = ROOT / 'scripts' / 'viewer_template.html'
sys.path.insert(0, str(ROOT / 'tests'))
from browser_runtime import chromium_launch_kwargs  # noqa: E402

# One card per component, one arc per passable wire leg, exactly as the graph core builds them.
# A control arc is carried with its flag: reach does not follow it (src/07-graph-core.js reach).
GRAPH_JS = """() => {
  const doc = window.SovSchematicAPI.file.document();
  const g = window.SovSchematicGraph.build(doc);
  const nodes = doc.components.map(c => ({
    id: c.id, label: (c.config && c.config.label) || c.id, symbolId: c.symbolId || null,
    parentId: c.parentId || null, note: (c.config && (c.config.note || c.config.description)) || null}));
  const wires = doc.wires.map(w => ({id: w.id, a: w.a || null, b: w.b || null,
    label: (w.config && w.config.label) || null}));
  const arcs = g.arcs.map(a => ({wire: a.wireId, from: a.from, to: a.to, control: !!a.control}));
  return {title: (doc.meta && doc.meta.title) || doc.id, id: doc.id, nodes, wires, arcs,
          blocked: g.blocked.map(b => ({wire: b.wireId, reason: b.reason}))};
}"""
# Both pictures inside one withPictureLabels (src/75-persistence.js): the picture is drawn at label
# zoom 1, and render.svg from any other zoom (opening a document fits the camera) draws the whole
# picture twice. Here the drawing at zoom 1 happens once, and the dark picture is the one redraw.
SVGS_JS = """(opts) => withPictureLabels(() => {
  const api = window.SovSchematicAPI, svg = {};
  for (const appearance of ['light', 'dark']) { api.view.setAppearance(appearance); svg[appearance] = api.render.svg(opts); }
  return svg;
})"""
PLACEHOLDER = '/*__VIEWER_DATA__*/null'


def script_safe(value) -> str:
    """JSON that cannot close the <script> element it sits in."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True).replace('</', '<\\/')


def export_documents(paths: list[Path], out_dir: Path | None = None, pad: int = 48) -> list[dict]:
    """Write one .html per .sov. Returns one record per input: {source, target, bytes, errors}."""
    from playwright.sync_api import sync_playwright
    if not HTML.exists():
        raise SystemExit('index.html is missing; run python build.py first')
    app = HTML.read_text(encoding='utf-8')
    template = TEMPLATE.read_text(encoding='utf-8')
    if template.count(PLACEHOLDER) != 1:
        raise SystemExit(f'{TEMPLATE.name} must hold {PLACEHOLDER} exactly once')
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        page.set_default_timeout(600_000)
        errors: list[str] = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content(app, wait_until='load')
        page.wait_for_timeout(250)
        for src in paths:
            src = Path(src)
            before = len(errors)
            page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [src.read_text(encoding='utf-8'), src.name])
            page.wait_for_timeout(300)
            data = page.evaluate(GRAPH_JS)
            data['svg'] = page.evaluate(SVGS_JS, {'pad': pad, 'packets': False, 'legend': False})
            data['source'] = src.name
            html = template.replace(PLACEHOLDER, script_safe(data))
            target = (out_dir / f'{src.stem}.html') if out_dir else src.with_suffix('.html')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(html, encoding='utf-8', newline='\n')
            results.append({'source': src, 'target': target, 'bytes': len(html.encode('utf-8')),
                            'errors': errors[before:]})
        browser.close()
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('paths', nargs='*', help='.sov files (default: examples/*.sov)')
    ap.add_argument('--out', type=Path, default=None, help='output directory (default: beside each input)')
    ap.add_argument('--pad', type=int, default=48, help='padding around content in canvas units')
    ap.add_argument('--open', action='store_true', help='open each result in the default browser')
    args = ap.parse_args(argv)
    paths = [Path(p) for p in args.paths] or sorted((ROOT / 'examples').glob('*.sov'))
    if not paths:
        print('no .sov inputs', file=sys.stderr)
        return 2
    failed = 0
    for r in export_documents(paths, args.out, args.pad):
        status = 'ok ' if not r['errors'] else 'ERR'
        print(f"{status} {r['source']} -> {r['target']} ({r['bytes']} bytes)")
        for e in r['errors']:
            failed += 1
            print(f'    page error: {e}', file=sys.stderr)
        if args.open and not r['errors']:
            webbrowser.open(r['target'].resolve().as_uri())
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
