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
import re
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'
TEMPLATE = ROOT / 'scripts' / 'viewer_template.html'
sys.path.insert(0, str(ROOT / 'tests'))
from browser_runtime import chromium_launch_kwargs  # noqa: E402

# What the viewer shows is read out of the editor by sovExtract, which lives in the template (between
# the SOV-EXTRACT markers) so this script and bin/schematically.mjs, which runs it in the reader's
# browser, draw the same file from one function.
EXTRACT_RE = re.compile(r'/\*SOV-EXTRACT-BEGIN\*/(.*?)/\*SOV-EXTRACT-END\*/', re.S)
PLACEHOLDER = '/*__VIEWER_DATA__*/null'
EDITOR_PLACEHOLDER = '/*__VIEWER_EDITOR__*/'


def script_safe(value) -> str:
    """JSON the HTML parser reads as plain script data: no <, > or & survives, so neither </script>
    nor <!--<script> can end or swallow the element (the escaping Django's json_script uses)."""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')


def export_documents(paths: list[Path], out_dir: Path | None = None, pad: int = 48) -> list[dict]:
    """Write one .html per .sov. Returns one record per input: {source, target, bytes, errors}."""
    from playwright.sync_api import sync_playwright
    if not HTML.exists():
        raise SystemExit('index.html is missing; run python build.py first')
    app = HTML.read_text(encoding='utf-8')
    template = TEMPLATE.read_text(encoding='utf-8')
    if template.count(PLACEHOLDER) != 1:
        raise SystemExit(f'{TEMPLATE.name} must hold {PLACEHOLDER} exactly once')
    extract = EXTRACT_RE.search(template)
    if not extract or template.count(EDITOR_PLACEHOLDER) != 1:
        raise SystemExit(f'{TEMPLATE.name} must hold sovExtract and {EDITOR_PLACEHOLDER} exactly once')
    extract_js = f'(opts) => {{ {extract.group(1)}; return sovExtract(window, opts); }}'
    template = template.replace(EDITOR_PLACEHOLDER, '')
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
            data = page.evaluate(extract_js, {'pad': pad, 'packets': False, 'legend': False})
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
