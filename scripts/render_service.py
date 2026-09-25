"""Render one document for a caller that has no browser (the MCP/HTTP server).

Reads JSON on stdin: {document, formats: [svg|png|metrics], appearance: light|dark, scale, pad, view}.
Writes JSON on stdout: {ok, svg?, png? (base64), metrics?} or {ok: false, code, message}.
Uses the editor's own renderStandaloneSvg / renderStandalonePng / layout.metrics in headless
Chromium, so a picture from the server is the picture the editor exports.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))


def fail(code: str, message: str) -> int:
    print(json.dumps({'ok': False, 'code': code, 'message': message}))
    return 0


def main() -> int:
    try:
        req = json.loads(sys.stdin.read() or '{}')
    except json.JSONDecodeError as e:
        return fail('BAD_REQUEST', f'request is not JSON: {e}')
    formats = [f for f in req.get('formats', ['svg']) if f in ('svg', 'png', 'metrics')] or ['svg']
    try:
        from playwright.sync_api import sync_playwright
        from browser_runtime import chromium_launch_kwargs
    except Exception as e:  # noqa: BLE001
        return fail('RENDERER_UNAVAILABLE', f'headless Chromium via Playwright is not installed: {e}')
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    out = {'ok': True}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
            page = browser.new_page(viewport={'width': 1600, 'height': 1000})
            errors: list[str] = []
            page.on('pageerror', lambda exc: errors.append(str(exc)))
            page.set_content(html, wait_until='load')
            page.wait_for_timeout(200)
            page.evaluate('(m)=>window.SovSchematicAPI.view.setAppearance(m)', req.get('appearance', 'light'))
            page.evaluate('(d)=>{window.SovSchematicAPI.document.replace(d);fitDiagram()}', req.get('document') or {})
            if req.get('view'):
                switched = page.evaluate('(v)=>{const r=window.SovSchematicAPI.layout.switch(v);fitDiagram();return r}', req['view'])
                if not switched.get('ok'):
                    return fail(switched.get('code', 'UNKNOWN_LAYOUT'), switched.get('message', 'no such layout'))
            page.wait_for_timeout(250)
            opts = {'pad': req.get('pad', 48), 'scale': req.get('scale', 2)}
            if 'svg' in formats:
                out['svg'] = page.evaluate('(o)=>window.SovSchematicAPI.render.svg(o)', opts)
            if 'png' in formats:
                data_url = page.evaluate('(o)=>window.SovSchematicAPI.render.png(o)', opts)
                out['png'] = data_url.split(',', 1)[1]
            if 'metrics' in formats:
                out['metrics'] = page.evaluate('()=>window.SovSchematicAPI.layout.metrics({static:true})')
            browser.close()
            if errors:
                return fail('RENDER_FAILED', '; '.join(errors))
    except Exception as e:  # noqa: BLE001
        return fail('RENDERER_UNAVAILABLE', str(e).splitlines()[0])
    print(json.dumps(out))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
