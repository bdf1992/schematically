"""Export picture fit QA.

scripts/export_svg.py makes the picture (render.svg): every label draws at its base size,
with no overflow past its own card and no caption overlapping another caption or a card
(src/75-persistence.js). This checks both guarantees against two documents:

- tests/fixtures/work-engine-sample.sov, a real document that overflows under the snapshot
  (file.svg, drawn at the fitted zoom's clamped screen size): three titles run past their
  cards, two 'declares' captions overlap and 'anchored at' sits under two cards (measured on
  dev 64f1fd6). The picture must draw it with none of that.
- a small document built here, with a 70-character title on a 300 x 140 act card and a wire
  running to a card 3000 units away, captioned 'feeds': a title wide enough to force the
  card to grow or wrap, and a caption with room to sit clear of both cards.

Each export is loaded into a page and measured with getBoundingClientRect: a component's
label (`text.component-label`) must lie inside its own node's `.body` horizontally within
1px; no two wire captions (`.connection-label`) may overlap by more than 0.5px; no caption
may overlap the `.body` of a node that is not a container (`.is-container`) by more than
0.5px. A failure names the ids involved.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
from export_svg import export_documents  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

TITLE_70 = 'This title has exactly seventy characters so the card must grow or wra'

SECOND_DOCUMENT = {
    'schema': 'soveraeign.schematic/document@0.1',
    'id': 'picture-fit-check',
    'revision': 0,
    'meta': {'updatedAt': '2026-10-01T00:00:00.000Z', 'title': 'Picture fit check'},
    'canvas': {'id': 'canvas:global', 'scope': 'global', 'dimension': 2, 'state': 'open'},
    'components': [
        {'id': 'wide-act', 'type': 'act', 'symbolId': 'act', 'x': 0, 'y': 0,
         'config': {'label': TITLE_70, 'colorSlot': 6, 'presentation': {'size': {'w': 300, 'h': 140}}}},
        {'id': 'far-hold', 'type': 'hold', 'symbolId': 'hold', 'x': 3000, 'y': 0,
         'config': {'label': 'Far hold', 'colorSlot': 7}},
    ],
    'wires': [
        {'id': 'w-feeds', 'a': 'wide-act', 'aSide': 'out', 'b': 'far-hold', 'bSide': 'in',
         'canvasId': 'canvas:global', 'config': {'label': 'feeds'}},
    ],
    'references': [],
    'layout': {},
}

# Returns a list of violations, each a short tuple naming the ids involved.
MEASURE_JS = """
() => {
  const bad = [];
  const overlap = (a, b, tol) =>
    a.left < b.right - tol && a.right > b.left + tol && a.top < b.bottom - tol && a.bottom > b.top + tol;
  for (const node of document.querySelectorAll('.node[data-id]')) {
    const label = node.querySelector(':scope > text.component-label');
    const body = node.querySelector(':scope > .body');
    if (!label || !body) continue;
    const lr = label.getBoundingClientRect(), br = body.getBoundingClientRect();
    if (lr.left < br.left - 1 || lr.right > br.right + 1) {
      bad.push(['label-overflow', node.dataset.id, lr.left, lr.right, br.left, br.right]);
    }
  }
  const captions = [...document.querySelectorAll('.wire-group[data-wire-id] .connection-label')]
    .map(t => ({ id: t.closest('.wire-group').dataset.wireId, r: t.getBoundingClientRect() }));
  for (let i = 0; i < captions.length; i++) {
    for (let j = i + 1; j < captions.length; j++) {
      if (overlap(captions[i].r, captions[j].r, 0.5)) {
        bad.push(['caption-overlap', captions[i].id, captions[j].id]);
      }
    }
  }
  const cards = [...document.querySelectorAll('.node:not(.is-container)[data-id] > .body')]
    .map(el => ({ id: el.parentElement.dataset.id, r: el.getBoundingClientRect() }));
  for (const c of captions) {
    for (const card of cards) {
      if (overlap(c.r, card.r, 0.5)) {
        bad.push(['caption-over-card', c.id, card.id]);
      }
    }
  }
  return bad;
}
"""


def check(svg_path: Path, browser) -> list:
    page = browser.new_page()
    page.set_content(svg_path.read_text(encoding='utf-8'), wait_until='load')
    bad = page.evaluate(MEASURE_JS)
    page.close()
    return bad


def main() -> None:
    assert len(TITLE_70) == 70, f'TITLE_70 is {len(TITLE_70)} characters, not 70'
    sample = ROOT / 'tests/fixtures/work-engine-sample.sov'
    assert sample.exists(), f'missing fixture: {sample}'
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        second = out / 'picture-fit-check.sov'
        second.write_text(__import__('json').dumps(SECOND_DOCUMENT), encoding='utf-8')
        results = export_documents([sample, second], out)
        assert len(results) == 2
        for r in results:
            assert not r['errors'], f"{r['source'].name}: page errors {r['errors']}"
        with sync_playwright() as p:
            browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
            for r in results:
                bad = check(r['target'], browser)
                assert not bad, f"{r['source'].name}: {bad}"
            browser.close()
    print('PASS export picture fit QA')


if __name__ == '__main__':
    main()
