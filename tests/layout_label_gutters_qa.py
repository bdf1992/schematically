"""Layout label gutters QA: the offline layout sets a column gap from the widest wire label that
crosses it plus a declared margin (src/08-layout-core.js `layered`, LAYOUT-MODEL.md "What layered
does"). The estimate is one formula, used by both the column gap a label crosses and the row gap a
same-column label spans: characters x the notation's caption size x 0.6, plus the margin on both
sides (labelMargin, an `apply` option, default 16).

Two `act` cards with no coordinates, joined by one wire:
- labelled 'anchored at the far gate of the case': `node scripts/layout_sov.mjs` places them with a
  column gap at least the estimate for that label at the default margin;
- the same pair with `--label-margin 32`: the gap grows by exactly 32;
- unlabelled: the gap stays today's default (unwidened).

In the browser, `SovSchematicAPI.layout.apply({engine:'layered'})`'s own receipt names
labelMargin, the layout draws no text-collision finding against the label, and the page logs no
errors.
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / 'scripts/layout_sov.mjs'
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

LABEL = 'anchored at the far gate of the case'
CAPTION_SIZE = 9.0  # SCHEMATIC.tokens.type.caption.size (src/03-notation-core.js), unset here.
DEFAULT_GAP = 80    # layered's own gapX default.


def estimate(text: str, margin: int) -> float:
    """The estimate src/08-layout-core.js `layered` computes for one label."""
    return len(text) * CAPTION_SIZE * .6 + 2 * margin


def build(label: str | None, placed: bool = False) -> dict:
    wire = {'id': 'w1', 'a': 'a', 'aSide': 'out', 'b': 'b', 'bSide': 'in'}
    if label:
        wire['config'] = {'label': label}
    a = {'id': 'a', 'symbolId': 'act', 'config': {'label': 'Act A'}}
    b = {'id': 'b', 'symbolId': 'act', 'config': {'label': 'Act B'}}
    if placed:
        # The browser renders a document as it opens it: give each card a starting position so
        # there is something to route before `layout.apply` rearranges them.
        a.update(x=0, y=0)
        b.update(x=300, y=0)
    return {
        'schema': 'soveraeign.schematic/document@0.1', 'id': 'label-gutters-qa',
        'meta': {'title': 'Label gutters QA'},
        'components': [a, b],
        'wires': [wire],
    }


def run_layout(path: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(['node', str(LAYOUT), str(path), *extra], cwd=ROOT, capture_output=True, text=True)


def column_gap(doc: dict) -> float:
    """The edge-to-edge gap between the two cards, whichever landed on the left."""
    by_id = {c['id']: c for c in doc['components']}
    a, b = by_id['a'], by_id['b']
    aw = a['config']['presentation']['size']['w']
    bw = b['config']['presentation']['size']['w']
    if a['x'] <= b['x']:
        left, lw, right, rw = a, aw, b, bw
    else:
        left, lw, right, rw = b, bw, a, aw
    return (right['x'] - rw / 2) - (left['x'] + lw / 2)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)

        labelled = out / 'labelled.sov'
        labelled.write_text(json.dumps(build(LABEL)), encoding='utf-8')
        proc = run_layout(labelled)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert 'labelMargin 16' in proc.stdout, proc.stdout
        doc = json.loads(labelled.read_text(encoding='utf-8'))
        need = estimate(LABEL, 16)
        gap = column_gap(doc)
        assert gap >= need - .5, (gap, need)

        wide = out / 'wide.sov'
        wide.write_text(json.dumps(build(LABEL)), encoding='utf-8')
        proc = run_layout(wide, '--label-margin', '32')
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert 'labelMargin 32' in proc.stdout, proc.stdout
        doc_wide = json.loads(wide.read_text(encoding='utf-8'))
        gap_wide = column_gap(doc_wide)
        assert abs((gap_wide - gap) - 32) < .5, (gap, gap_wide)

        plain = out / 'plain.sov'
        plain.write_text(json.dumps(build(None)), encoding='utf-8')
        proc = run_layout(plain)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        doc_plain = json.loads(plain.read_text(encoding='utf-8'))
        gap_plain = column_gap(doc_plain)
        assert abs(gap_plain - DEFAULT_GAP) < .5, gap_plain

    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1200, 'height': 800})
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(250)
        page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [json.dumps(build(LABEL, placed=True)), 'label-gutters-qa.sov'])
        receipt = page.evaluate("()=>SovSchematicAPI.layout.apply({engine:'layered'})")
        assert receipt['ok'], receipt
        assert receipt.get('labelMargin') == 16, receipt
        page.evaluate('()=>fitDiagram()')
        page.wait_for_timeout(200)
        metrics = page.evaluate('()=>SovSchematicAPI.layout.metrics({static:true})')
        browser.close()

    assert not errors, errors
    collisions = [f for f in metrics['findings'] if f['kind'] == 'text-collision']
    on_label = [f for f in collisions if 'w1' in f.get('ids', []) or LABEL in f.get('detail', '')]
    assert not on_label, on_label

    print('PASS layout label gutters QA', {'gap': gap, 'gap_wide': gap_wide, 'gap_plain': gap_plain})


if __name__ == '__main__':
    main()
