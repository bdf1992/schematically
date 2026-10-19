"""Interactive HTML viewer QA (scripts/export_html.py).

Exports every examples/*.sov to a self-contained .html in a temporary directory, opens each one
from disk in headless Chromium with every non-file request refused, and checks:

- the page loads with no error and asks the network for nothing;
- every component is a card the viewer knows, and every card in the picture is one of them;
- for every card, the viewer's downstream set is the graph core's reach (src/07-graph-core.js),
  wire for wire, computed in the editor on the same document;
- upstream is downstream read backwards: B is upstream of A exactly when A is downstream of B;
- a route exists exactly when the graph core's paths finds one, and is never longer than the
  shortest path it lists;
- a deep link restores focus, mode, route and theme, and a click on a card opens its details;
- a label holding </script> neither breaks the page nor runs.
"""
from __future__ import annotations
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
from export_html import export_documents  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

CORE_JS = """() => {
  const doc = window.SovSchematicAPI.file.document(), G = window.SovSchematicGraph;
  const ids = doc.components.map(c => c.id), reach = {}, paths = {};
  for (const a of ids) {
    const r = G.query(doc, 'reach', {from: a});
    reach[a] = {nodes: [...r.nodes].sort(), wires: [...r.wires].sort()};
    for (const b of ids) if (a !== b) {
      const p = G.query(doc, 'paths', {from: a, to: b, limit: 200});
      paths[a + '\\u0000' + b] = {n: p.paths.length, shortest: p.paths.length ? Math.min(...p.paths.map(x => x.wires.length)) : null, truncated: p.truncated};
    }
  }
  return {ids, reach, paths};
}"""
VIEWER_JS = """() => {
  const V = window.SovViewer, ids = V.data.nodes.map(n => n.id), down = {}, up = {}, route = {};
  for (const a of ids) {
    const d = V.downstream(a), u = V.upstream(a);
    down[a] = {nodes: [...d.nodes].sort(), wires: [...d.wires].sort()};
    up[a] = [...u.nodes].sort();
    for (const b of ids) if (a !== b) { const r = V.route(a, b); route[a + '\\u0000' + b] = r ? r.wires.length : null; }
  }
  const drawn = [...document.querySelectorAll('#stage g.node[data-id]')].map(g => g.dataset.id);
  return {ids, down, up, route, drawn};
}"""


def open_viewer(page, path: Path, fragment: str = '') -> list[str]:
    errors: list[str] = []
    requests: list[str] = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('request', lambda req: requests.append(req.url) if not req.url.startswith(('file:', 'data:', 'blob:')) else None)
    page.goto(path.resolve().as_uri() + fragment)
    page.wait_for_function('() => !!window.SovViewer')
    assert not requests, f'{path.name}: asked the network for {requests}'
    return errors


def check_document(app, viewer_page, src: Path, html: Path) -> int:
    app.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [src.read_text(encoding='utf-8'), src.name])
    core = app.evaluate(CORE_JS)
    errors = open_viewer(viewer_page, html)
    v = viewer_page.evaluate(VIEWER_JS)
    assert not errors, f'{html.name}: page errors {errors}'
    themes = viewer_page.evaluate('() => [window.SovViewer.data.svg.light, window.SovViewer.data.svg.dark].map(s => /background-color:\s*([^;"]+)/.exec(s)[1])')
    assert themes[0] != themes[1], f'{html.name}: light and dark pictures share the background {themes[0]}'
    assert sorted(v['ids']) == sorted(core['ids']), f'{html.name}: viewer cards differ from the document'
    assert set(v['drawn']) <= set(v['ids']), f'{html.name}: drawn cards the viewer does not know: {set(v["drawn"]) - set(v["ids"])}'
    for a in core['ids']:
        assert v['down'][a] == core['reach'][a], f'{html.name}: downstream of {a} is {v["down"][a]}, graph core reach is {core["reach"][a]}'
        for b in core['ids']:
            if a != b:
                assert (b in v['up'][a]) == (a in v['down'][b]['nodes']), f'{html.name}: upstream of {a} disagrees with downstream of {b}'
                p, r = core['paths'][a + '\u0000' + b], v['route'][a + '\u0000' + b]
                if not p['truncated']:
                    assert (r is not None) == (p['n'] > 0), f'{html.name}: route {a}->{b} is {r}, graph core finds {p["n"]} paths'
                if r is not None and p['shortest'] is not None:
                    assert r <= p['shortest'], f'{html.name}: route {a}->{b} has {r} wires, a path of {p["shortest"]} exists'
    return len(core['ids'])


def check_interaction(page, html: Path) -> None:
    """Deep link, theme and a click, on a document with containment and a route."""
    errors = open_viewer(page, html, '#focus=grant&mode=route&to=store&theme=dark')
    s = page.evaluate('() => ({...window.SovViewer.state, theme_attr: document.documentElement.dataset.theme, hits: [...document.querySelectorAll("#stage g.node.hit")].map(g => g.dataset.id), status: document.getElementById("status").textContent})')
    assert not errors, errors
    assert (s['focus'], s['mode'], s['to'], s['theme'], s['theme_attr']) == ('grant', 'route', 'store', 'dark', 'dark'), s
    assert s['hits'][:1] and 'grant' in s['hits'] and 'store' in s['hits'], f'route not drawn: {s["hits"]}'
    assert s['status'].startswith('Route from Grant to'), s['status']
    page.evaluate('() => window.SovViewer.clear()')
    assert page.evaluate('() => location.hash') == '#theme=dark', 'clearing keeps only the theme in the link'
    box = page.locator('#stage g.node[data-id="req"]').bounding_box()
    page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    assert page.evaluate('() => window.SovViewer.state.focus') == 'req', 'a click on a card focuses it'
    assert page.locator('#panel h2').inner_text() == 'Requester'
    page.keyboard.press('d')
    assert page.evaluate('() => location.hash').startswith('#focus=req&mode=down'), page.evaluate('() => location.hash')
    page.keyboard.press('Escape')
    assert page.evaluate('() => window.SovViewer.state.focus') is None
    page.keyboard.press('/')
    page.keyboard.type('servic')
    page.keyboard.press('Enter')
    assert page.evaluate('() => window.SovViewer.state.focus') == 'svc', 'search finds a card by a part of its label'


def hostile_label(tmp: Path) -> Path:
    doc = json.loads((ROOT / 'examples' / '08-gated-service.sov').read_text(encoding='utf-8'))
    doc['meta']['title'] = 'Hostile </script><script>window.PWNED=1</script>'
    doc['components'][0]['config']['label'] = '</script><img src=x onerror="window.PWNED=2">'
    path = tmp / 'hostile.sov'
    path.write_text(json.dumps(doc), encoding='utf-8')
    return path


def main() -> int:
    from playwright.sync_api import sync_playwright
    examples = sorted((ROOT / 'examples').glob('*.sov'))
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        sources = examples + [hostile_label(tmp)]
        results = export_documents(sources, tmp / 'out')
        for r in results:
            assert not r['errors'], f"{r['source']}: export errors {r['errors']}"
        cards = 0
        with sync_playwright() as p:
            browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
            app = browser.new_page()
            app.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
            app.wait_for_timeout(250)
            for r in results:
                page = browser.new_page(viewport={'width': 1280, 'height': 800})
                cards += check_document(app, page, Path(r['source']), r['target'])
                page.close()
            page = browser.new_page(viewport={'width': 1280, 'height': 800})
            check_interaction(page, tmp / 'out' / '08-gated-service.html')
            page.close()
            page = browser.new_page()
            errors = open_viewer(page, tmp / 'out' / 'hostile.html')
            assert not errors, errors
            assert page.evaluate('() => window.PWNED') is None, 'a label ran as script'
            assert page.title().startswith('Hostile </script>'), page.title()
            page.close()
            browser.close()
    print(f'html viewer QA passed: {len(results)} documents, {cards} cards traced against the graph core')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
