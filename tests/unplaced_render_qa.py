"""Unplaced render QA: a card with no finite position, and every wire that ends on one, are left out
of the drawing; nothing drawn carries NaN; the rest of the document renders and exports
(src/55-render.js render() and renderWires, src/30-canvas.js diagramBounds, scripts/export_svg.py).
src/08-layout-core.js says an entity with no position is unplaced and never put at 0,0; the drawing
takes the same rule: no position, not drawn, and counted on the workspace element
(data-undrawn-cards, data-undrawn-wires; neither attribute when the count is 0).

Browser part (index.html, headless Chromium 1600 x 1000), each number printed beside its value:
  (a) tests/fixtures/booth-record-graphify.sov opened as stored (it holds no x): open does not throw,
      the page logs no error, no wire-group is drawn, data-undrawn-wires is 262, and no attribute of
      any element under the workspace contains NaN;
  (b) SovSchematicAPI.render.svg({pad:48}) on it returns text with no NaN;
  (c) export_documents (scripts/export_svg.py) on it, into a temporary folder: one record, no errors,
      a file with no NaN;
  (d) tests/fixtures/task-lifecycle.sov with the x and y of the card commits removed in memory: that
      card is not drawn, every wire ending on it has no wire-group, data-undrawn-cards is 1, and every
      other wire's path d equals its d in the same document opened whole, within 0.01 per number,
      except wires whose route differs because commits is no longer an obstacle, listed by id;
  (e) task-lifecycle.sov whole carries neither attribute;
  (f) the booth document laid out first with node scripts/layout_sov.mjs --out draws all 262 wires
      and carries neither attribute.

    python tests/unplaced_render_qa.py
    python tests/unplaced_render_qa.py --measure     # print what (a) and (d) read, assert nothing
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'scripts'))

BOOTH = ROOT / 'tests/fixtures/booth-record-graphify.sov'
LIFECYCLE = ROOT / 'tests/fixtures/task-lifecycle.sov'
NUM = re.compile(r'-?\d+(?:\.\d+)?(?:e-?\d+)?|NaN')

OPEN = """([t,n])=>{try{window.SovSchematicAPI.file.open(t,n);return null}catch(e){return String(e&&e.stack||e)}}"""
READ = r"""()=>{
  const nan={};let nanCount=0;
  for(const el of workspace.querySelectorAll('*'))for(const a of el.attributes)if(/NaN/.test(a.value)){
    const k=el.tagName+'.'+(el.getAttribute('class')||'')+'@'+a.name;nan[k]=(nan[k]||0)+1;nanCount++}
  const paths={};
  for(const g of workspace.querySelectorAll('.wire-group')){const p=g.querySelector('path.wire');paths[g.dataset.wireId]=p?p.getAttribute('d'):null}
  return {nanCount,nan,paths,groups:Object.keys(paths).length,
    cards:workspace.querySelectorAll('.node').length,
    nodeIds:[...workspace.querySelectorAll('.node')].map(n=>n.dataset.id),
    attrs:[workspace.getAttribute('data-undrawn-cards'),workspace.getAttribute('data-undrawn-wires')]};
}"""


def open_doc(browser, text: str, name: str) -> tuple[dict, str | None, list[str]]:
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    errors: list[str] = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.set_content(html, wait_until='load')
    page.wait_for_timeout(250)
    thrown = page.evaluate(OPEN, [text, name])
    page.wait_for_timeout(300)
    seen = page.evaluate(READ)
    seen['page'] = page
    return seen, thrown, errors


def numbers(d: str | None) -> list[float]:
    return [float('nan') if m == 'NaN' else float(m) for m in NUM.findall(d or '')]


def same_path(a: str | None, b: str | None) -> bool:
    x, y = numbers(a), numbers(b)
    return len(x) == len(y) and all(abs(p - q) <= 0.01 for p, q in zip(x, y))


def main(argv: list[str]) -> int:
    measure = '--measure' in argv
    from playwright.sync_api import sync_playwright
    from export_svg import export_documents

    booth_text = BOOTH.read_text(encoding='utf-8')
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # export_documents starts its own Playwright, so it runs before this one does.
        records = [] if measure else export_documents([BOOTH], tmp / 'export')
        with sync_playwright() as p:
            return run(p, tmp, measure, booth_text, records)


def run(p, tmp: Path, measure: bool, booth_text: str, records: list[dict]) -> int:
    from browser_runtime import chromium_launch_kwargs
    if True:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))

        # (a) the booth document as stored.
        seen, thrown, errors = open_doc(browser, booth_text, BOOTH.name)
        print(f"(a) booth as stored: open threw {'nothing' if not thrown else thrown.splitlines()[0]}; page errors {len(errors)}; "
              f"wire-groups {seen['groups']}; data-undrawn-cards {seen['attrs'][0]}, data-undrawn-wires {seen['attrs'][1]}; "
              f"attributes with NaN {seen['nanCount']} {dict(list(seen['nan'].items())[:4])}")
        if thrown:
            print('    stack:', ' | '.join(thrown.splitlines()[:6]))
        if not measure:
            assert not thrown, thrown
            assert not errors, errors
            assert seen['groups'] == 0, seen['groups']
            assert seen['attrs'][1] == '262', seen['attrs']
            assert seen['nanCount'] == 0, seen['nan']

        # (b) the picture of it.
        if not measure:
            svg = seen['page'].evaluate("()=>window.SovSchematicAPI.render.svg({pad:48})")
            print(f"(b) render.svg on it: {len(svg)} characters, NaN {svg.count('NaN')}")
            assert svg.count('NaN') == 0, re.findall(r'.{40}NaN.{20}', svg)[:3]
        seen['page'].close()

        # (c) the export script on it.
        if not measure:
            rec = records[0]
            body = rec['target'].read_text(encoding='utf-8')
            print(f"(c) export_documents: {len(records)} record, errors {len(rec['errors'])}, {rec['bytes']} bytes, NaN in the file {body.count('NaN')}")
            assert len(records) == 1 and not rec['errors'], rec['errors']
            assert body.count('NaN') == 0

        # (e) the whole lifecycle document, and (d) with commits unplaced.
        life_text = LIFECYCLE.read_text(encoding='utf-8')
        whole, thrown, errors = open_doc(browser, life_text, LIFECYCLE.name)
        assert not thrown and not errors, (thrown, errors)
        print(f"(e) task-lifecycle whole: {whole['groups']} wire-groups; data-undrawn-cards {whole['attrs'][0]}, data-undrawn-wires {whole['attrs'][1]}")
        whole['page'].close()
        doc = json.loads(life_text)
        for c in doc['components']:
            if c['id'] == 'commits':
                c.pop('x', None)
                c.pop('y', None)
        ends = sorted(w['id'] for w in doc['wires'] if 'commits' in (w.get('a'), w.get('b')))
        part, thrown, errors = open_doc(browser, json.dumps(doc), LIFECYCLE.name)
        part['page'].close()
        drawn_ends = [i for i in ends if i in part['paths']]
        differ = sorted(i for i, d in part['paths'].items() if i in whole['paths'] and not same_path(d, whole['paths'][i]))
        print(f"(d) commits unplaced: open threw {'nothing' if not thrown else thrown.splitlines()[0]}; page errors {len(errors)}; "
              f"card drawn {'commits' in part['nodeIds']}; data-undrawn-cards {part['attrs'][0]}, data-undrawn-wires {part['attrs'][1]}; "
              f"wires ending on commits {len(ends)}, of them with a wire-group {len(drawn_ends)}; "
              f"wire-groups {part['groups']} of {whole['groups']}; NaN attributes {part['nanCount']}")
        print(f"    wires whose route differs because commits is no longer an obstacle: {len(differ)} {differ}")
        if not measure:
            assert not thrown and not errors, (thrown, errors)
            assert 'commits' not in part['nodeIds']
            assert part['attrs'][0] == '1', part['attrs']
            assert not drawn_ends, drawn_ends
            assert part['nanCount'] == 0, part['nan']
            assert part['groups'] == whole['groups'] - len(ends), (part['groups'], whole['groups'], len(ends))
            assert len(differ) * 2 < part['groups'], differ
            assert whole['attrs'] == [None, None], whole['attrs']

            # (f) the booth document laid out first.
            laid = tmp / 'laid.sov'
            proc = subprocess.run(['node', str(ROOT / 'scripts/layout_sov.mjs'), str(BOOTH), '--out', str(laid)],
                                  cwd=ROOT, capture_output=True, text=True)
            assert proc.returncode == 0, proc.stdout + proc.stderr
            full, thrown, errors = open_doc(browser, laid.read_text(encoding='utf-8'), BOOTH.name)
            full['page'].close()
            print(f"(f) booth laid out first: {full['groups']} wire-groups; data-undrawn-cards {full['attrs'][0]}, data-undrawn-wires {full['attrs'][1]}; "
                  f"page errors {len(errors)}; NaN attributes {full['nanCount']}")
            assert not thrown and not errors, (thrown, errors)
            assert full['groups'] == 262, full['groups']
            assert full['attrs'] == [None, None], full['attrs']
            assert full['nanCount'] == 0, full['nan']
        browser.close()
    print('ok' if not measure else 'measured')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
