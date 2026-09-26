"""Measure how well each document presents (LAYOUT-MODEL.md §5).

Opens each .sov in the standalone build, fits the camera as the SVG export does, and runs
`SovSchematicAPI.layout.metrics({static: true})`: the view a reader of an exported picture
gets. Prints a score per document and, with --findings, every finding.

Usage:
    python scripts/layout_audit.py                    # every examples/*.sov
    python scripts/layout_audit.py a.sov --findings
    python scripts/layout_audit.py --json out.json
    python scripts/layout_audit.py --min 7            # exit 1 when any document scores below 7
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from browser_runtime import chromium_launch_kwargs  # noqa: E402


def audit(paths: list[Path], appearance: str = 'light') -> list[dict]:
    from playwright.sync_api import sync_playwright
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    out = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        errors: list[str] = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content(html, wait_until='load')
        page.wait_for_timeout(250)
        page.evaluate('(m)=>window.SovSchematicAPI.view.setAppearance(m)', appearance)
        for src in paths:
            page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [Path(src).read_text(encoding='utf-8'), Path(src).name])
            page.evaluate('()=>{ if (typeof fitDiagram === "function") fitDiagram(); }')
            page.wait_for_timeout(300)
            result = page.evaluate('()=>window.SovSchematicAPI.layout.metrics({static:true})')
            result['source'] = str(Path(src).relative_to(ROOT) if Path(src).resolve().is_relative_to(ROOT) else src)
            out.append(result)
        browser.close()
        if errors:
            raise SystemExit('page errors: ' + '; '.join(errors))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='*')
    ap.add_argument('--findings', action='store_true')
    ap.add_argument('--json')
    ap.add_argument('--min', type=float)
    ap.add_argument('--appearance', default='light')
    a = ap.parse_args()
    paths = [Path(f).resolve() for f in a.files] or sorted((ROOT / 'examples').glob('*.sov'))
    results = audit(paths, a.appearance)
    for r in results:
        counts = ', '.join(f'{k} {v}' for k, v in sorted(r['counts'].items())) or 'no findings'
        print(f"{r['score']:>4}/10  {r['source']}  ({counts})")
        if a.findings:
            for f in r['findings']:
                print(f"         {f['kind']:<19} {','.join(str(i) for i in f['ids'] if i)}: {f['detail']}")
    if results:
        print(f"mean {sum(r['score'] for r in results) / len(results):.1f}/10 over {len(results)} documents")
    if a.json:
        Path(a.json).write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    if a.min is not None and any(r['score'] < a.min for r in results):
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
