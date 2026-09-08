"""Golden-corpus rendered-text QA.

Every `examples/*.sov` is opened in the standalone build and the text the renderer
actually puts on the workspace SVG is read back: component labels and type captions,
wire labels, channel tags, packet tags, reciprocity marks. The reading is compared to
`tests/golden-rendered-text.json`.

The corpus records what a document *says*. Until this suite existed nothing compared
what a document *shows*, so a renderer change could silently stop drawing text and
every other suite stayed green. That is how the typed-Component caption regression at
1f213c7 reached the tree: `effectiveLabelMode` returned 'none' for a typed Component
carrying no label of its own, the ACT / GATE / HOLD captions stopped being drawn, and
nothing failed until a human looked at the picture.

`examples/09-typed-captions.sov` is the corpus document that exercises that path: its
Components author no label and no labelMode, so the only text they can show is the type
caption. CAPTION_ANCHOR below asserts those captions by hand as well, so the suite still
refuses the regression even if the expectation file is regenerated from a broken build.

Run with --update to rewrite the expectation file after an intended rendering change.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_runtime import chromium_launch_kwargs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = Path(__file__).resolve().parent / 'golden-rendered-text.json'

# Read every text node the renderer put on the workspace, with the component or wire that
# owns it and the class that says what kind of text it is. Order is the render order.
READ_TEXT = """
() => [...workspace.querySelectorAll('text')].map(t => {
  const owner = t.closest('[data-id],[data-wire-id]');
  const id = !owner ? '-' : (owner.dataset.id ? 'component:' + owner.dataset.id : 'wire:' + owner.dataset.wireId);
  return [id, t.getAttribute('class') || '', t.textContent || ''];
})
"""

# Held by hand, not derived from a run: a typed Component with no label of its own shows
# its type caption. This is the exact text the 1f213c7 regression stopped drawing.
CAPTION_ANCHOR = {
    '09-typed-captions.sov': [
        ['component:src', 'component-label', 'ACT'],
        ['component:check', 'component-label', 'GATE'],
        ['component:store', 'component-label', 'HOLD'],
        ['component:log', 'component-label', 'Receipt'],
    ]
}


def read_corpus_text() -> dict[str, list[list[str]]]:
    """Open each corpus document in the build and return the text it renders."""
    html_path = ROOT / 'index.html'
    if not html_path.exists():
        raise SystemExit('index.html is missing; run python build.py first')
    html = html_path.read_text(encoding='utf-8')
    documents = sorted((ROOT / 'examples').glob('*.sov'))
    assert documents, 'no corpus documents under examples/'
    errors: list[str] = []
    rendered: dict[str, list[list[str]]] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content(html, wait_until='load')
        page.wait_for_timeout(250)
        page.evaluate('(m)=>window.SovSchematicAPI.view.setAppearance(m)', 'light')
        for path in documents:
            page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)',
                          [path.read_text(encoding='utf-8'), path.name])
            page.wait_for_timeout(200)
            first = page.evaluate(READ_TEXT)
            page.evaluate('()=>render()')
            second = page.evaluate(READ_TEXT)
            assert first == second, f'{path.name}: rendered text is not stable across a repeated render'
            rendered[path.name] = first
        browser.close()
    assert not errors, errors
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--update', action='store_true',
                        help='rewrite the expectation file from this run')
    args = parser.parse_args()

    rendered = read_corpus_text()

    if args.update:
        EXPECTED.write_text(json.dumps(rendered, indent=1, ensure_ascii=False) + '\n',
                            encoding='utf-8', newline='\n')
        print(f'UPDATED {EXPECTED.name} ({len(rendered)} documents)')
        return 0

    expected = json.loads(EXPECTED.read_text(encoding='utf-8'))
    failures: list[str] = []

    # The anchor first: it does not depend on the expectation file, so a regenerated
    # expectation cannot hide a caption that stopped rendering.
    for name, required in CAPTION_ANCHOR.items():
        actual = rendered.get(name)
        if actual is None:
            failures.append(f'{name}: corpus document is missing')
            continue
        for row in required:
            if row not in actual:
                failures.append(f'{name}: expected rendered text {row} and it was not drawn')

    for name in sorted(set(expected) | set(rendered)):
        want, got = expected.get(name), rendered.get(name)
        if want is None:
            failures.append(f'{name}: rendered by the corpus and absent from the expectation')
        elif got is None:
            failures.append(f'{name}: in the expectation and absent from the corpus')
        elif [list(r) for r in want] != [list(r) for r in got]:
            failures.append(f'{name}: rendered text differs from the expectation')
            for row in want:
                if list(row) not in [list(r) for r in got]:
                    failures.append(f'    expected and not drawn: {list(row)}')
            for row in got:
                if list(row) not in [list(r) for r in want]:
                    failures.append(f'    drawn and not expected: {list(row)}')

    if failures:
        for line in failures:
            print(f'FAIL {line}')
        raise SystemExit(1)

    drawn = sum(len(v) for v in rendered.values())
    print(f'PASS golden rendered text QA ({len(rendered)} documents, {drawn} text nodes)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
