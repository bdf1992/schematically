"""One document scale: glyph strokes, labels, stroke weights and marks all follow tokens.scale.

A notation's tokens.scale (default 1, from 0.5 to 4) multiplies every stroke weight, every text
role's base size, the pin length and the marks the renderer draws (port circle, terminal mark,
junction dot, carrying Point, wire hop, chevron). SovSchematicNotation.resolve applies it once
(src/03-notation-core.js), so no reader multiplies. Pictures and snapshots draw labels at base
size times scale; the 12 px screen floor is a live-editor aid only.

No arguments: the assertions below, on headless Chromium over index.html.
  - Four documents at scale 1, each measured in its picture (renderStandaloneSvg, loaded as its
    own page): every wire's base path is tokens.stroke.flow wide, every visible port circle has
    radius 5, every card title without data-shrunk draws at drawnSize(tokens.type,'title') and
    every wire caption at drawnSize(tokens.type,'caption'), and the act glyph's stroke width (the
    stroke of the #sym-act symbol, in its 96 x 64 box) is one value across the four.
  - tests/fixtures/work-engine-sample.sov again, under a carried notation that extends its own
    and sets tokens.scale 2: wire, card outline and glyph strokes, port and junction dot radius
    and the terminal mark's length and thickness are twice their scale 1 values within 0.01; a
    card title without data-shrunk draws at 20 and a wire caption at 18.
  - resolve refuses tokens.scale 0 and tokens.scale 'big' with SCALE_INVALID.
  - docs/workengine/map.sov fitted (camera zoom under 1): SovSchematicAPI.file.svg() draws its
    card titles at the size renderStandaloneSvg does.
  - The page logs no errors.
It prints, without asserting, the count of distinct act glyph box sizes per document: the glyph's
own size still follows its card (a separate task holds that).

--snapshot DIR writes the four pictures into DIR, one file each.
--compare DIR makes them again and reports, per document, identical or the differing lines.
Both also print the title sizes File > Export SVG draws for map.sov at the fitted zoom.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from browser_runtime import chromium_launch_kwargs  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DOCS = ['examples/work-engine/groups.sov', 'tests/fixtures/task-lifecycle.sov',
        'tests/fixtures/work-engine-sample.sov', 'docs/workengine/map.sov']
SAMPLE = 'tests/fixtures/work-engine-sample.sov'
MAP = 'docs/workengine/map.sov'
TOL = 0.01 + 1e-9  # "within 0.01", with room for the last binary digit

PICTURE_JS = "() => renderStandaloneSvg({pad: 48})"
SNAPSHOT_JS = "() => window.SovSchematicAPI.file.svg({pad: 48})"
TOKENS_JS = """() => {const N = SovSchematicNotation, T = N.tokens(diagram);
  return {scale: T.scale, flow: T.stroke.flow, structure: T.stroke.structure, symbol: T.stroke.symbol, pin: T.space.pin,
    screen: T.type.screen, title: N.drawnSize(T.type, 'title'), caption: N.drawnSize(T.type, 'caption'),
    zoom: currentZoom(), cssZoom: parseFloat(workspace.style.getPropertyValue('--zoom'))}}"""

# Run on the picture, loaded as its own page: what a reader of the file sees.
MEASURE_JS = """() => {
  const px = (el, p) => parseFloat(getComputedStyle(el).getPropertyValue(p));
  const num = (el, a) => parseFloat(el.getAttribute(a));
  const cards = {};
  for (const node of document.querySelectorAll('.node[data-id]')) {
    const body = node.querySelector(':scope > .body');
    if (body) cards[node.dataset.id] = px(body, 'stroke-width');
  }
  const sym = document.querySelector('#sym-act > g');
  const marks = [...document.querySelectorAll('.terminal-mark')].map(r => {
    const w = num(r, 'width'), h = num(r, 'height'); return [Math.max(w, h), Math.min(w, h)]});
  return {
    wires: [...document.querySelectorAll('path.wire')].map(el => px(el, 'stroke-width')),
    cards,
    ports: [...document.querySelectorAll('.node .port.attachment-point:not(.dimensional-point-body)')].map(el => num(el, 'r')),
    titles: [...document.querySelectorAll('.node > text.component-label:not(.dimensional-point-label):not([data-shrunk])')]
      .map(el => px(el, 'font-size')),
    shrunk: document.querySelectorAll('.node > text.component-label[data-shrunk]').length,
    captions: [...document.querySelectorAll('.connection-label')].map(el => px(el, 'font-size')),
    junctions: [...document.querySelectorAll('.junction-dot')].map(el => num(el, 'r')),
    marks,
    chevrons: [...document.querySelectorAll('.flow-chevron')].map(el => px(el, 'stroke-width')),
    glyphStroke: sym ? num(sym, 'stroke-width') : null,
    actBoxes: [...document.querySelectorAll('use.glyph')].filter(u => (u.getAttribute('href') || '') === '#sym-act')
      .map(u => `${(+u.getAttribute('width')).toFixed(2)}x${(+u.getAttribute('height')).toFixed(2)}`),
  };
}"""


def distinct(values):
    return sorted({round(v, 4) for v in values})


class Session:
    def __init__(self, p):
        self.browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        self.page = self.browser.new_page(viewport={'width': 1600, 'height': 1000})
        self.errors: list[str] = []
        self.page.on('pageerror', lambda exc: self.errors.append(str(exc)))
        self.page.on('console', lambda msg: self.errors.append(msg.text) if msg.type == 'error' else None)
        self.page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        self.page.wait_for_timeout(300)
        self.page.evaluate("(m)=>window.SovSchematicAPI.view.setAppearance(m)", 'light')

    def open(self, text: str, name: str) -> None:
        self.page.evaluate('([t,n])=>window.SovSchematicAPI.file.open(t,n)', [text, name])
        self.page.evaluate('()=>{ if (typeof fitDiagram === "function") fitDiagram(); }')
        self.page.wait_for_timeout(300)

    def open_path(self, rel: str) -> None:
        self.open((ROOT / rel).read_text(encoding='utf-8'), Path(rel).name)

    def picture(self) -> str:
        return self.page.evaluate(PICTURE_JS)

    def snapshot(self) -> str:
        return self.page.evaluate(SNAPSHOT_JS)

    def tokens(self) -> dict:
        return self.page.evaluate(TOKENS_JS)

    def measure(self, svg: str) -> dict:
        pic = self.browser.new_page(viewport={'width': 1600, 'height': 1000})
        pic.set_content(svg, wait_until='load')
        out = pic.evaluate(MEASURE_JS)
        pic.close()
        return out

    def close(self) -> None:
        self.browser.close()


def picture_name(rel: str) -> str:
    return rel.replace('/', '__').replace('.sov', '.svg')


def fitted_export_titles(s: Session) -> tuple[dict, list, list]:
    """map.sov fitted: the title sizes File > Export SVG draws, and the picture's."""
    s.open_path(MAP)
    tok = s.tokens()
    snap = s.measure(s.snapshot())['titles']
    pic = s.measure(s.picture())['titles']
    return tok, snap, pic


def report_fitted(tok: dict, snap: list, pic: list) -> None:
    print(f"{MAP} fitted at camera zoom {tok['zoom']:.4f} (screen scale {tok['cssZoom']:.4f}): "
          f"File > Export SVG draws {len(snap)} titles at {distinct(snap)}; the picture draws {len(pic)} at {distinct(pic)}")


def snapshot_mode(target: Path) -> int:
    target.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        s = Session(p)
        for rel in DOCS:
            s.open_path(rel)
            svg = s.picture()
            (target / picture_name(rel)).write_text(svg, encoding='utf-8', newline='\n')
            print(f'wrote {picture_name(rel)} ({len(svg.encode("utf-8"))} bytes)')
        report_fitted(*fitted_export_titles(s))
        errors = s.errors
        s.close()
    assert not errors, f'page errors: {errors}'
    return 0


def compare_mode(source: Path) -> int:
    differing = 0
    with sync_playwright() as p:
        s = Session(p)
        for rel in DOCS:
            s.open_path(rel)
            now = s.picture()
            before = (source / picture_name(rel)).read_text(encoding='utf-8')
            if now == before:
                print(f'{rel}: identical ({len(now.encode("utf-8"))} bytes)')
                continue
            differing += 1
            # A picture is one long line: cut both at tag ends so a difference names its element.
            a, b = before.replace('><', '>\n<').split('\n'), now.replace('><', '>\n<').split('\n')
            rows = [(i, x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y]
            print(f'{rel}: DIFFERS in {len(rows)} of {len(a)} elements (before {len(a)}, now {len(b)})')
            for i, x, y in rows[:12]:
                print(f'  element {i}\n    before: {x[:400]}\n    now:    {y[:400]}')
        report_fitted(*fitted_export_titles(s))
        errors = s.errors
        s.close()
    assert not errors, f'page errors: {errors}'
    return 1 if differing else 0


def scaled_copy(rel: str, scale) -> str:
    doc = json.loads((ROOT / rel).read_text(encoding='utf-8'))
    own = doc.get('notation') or 'schematic'
    doc['references'] = list(doc.get('references') or []) + [
        {'id': 'notation-scaled', 'kind': 'notation', 'data': {'id': 'scaled', 'extends': own, 'tokens': {'scale': scale}}}]
    doc['notation'] = 'scaled'
    return json.dumps(doc)


def twice(name: str, one: float, two: float) -> None:
    assert abs(two - 2 * one) <= TOL, (f'{name} at scale 2 is twice its scale 1 value', one, two)


def main() -> int:
    with sync_playwright() as p:
        s = Session(p)

        # 1. Four documents at scale 1.
        glyph_strokes, at_one = {}, {}
        for rel in DOCS:
            s.open_path(rel)
            tok, m = s.tokens(), s.measure(s.picture())
            at_one[rel] = (tok, m)
            boxes = Counter(m['actBoxes'])
            print(f"{rel} scale {tok['scale']}: {len(m['wires'])} wires at {distinct(m['wires'])} (stroke.flow {tok['flow']}); "
                  f"{len(m['ports'])} ports r {distinct(m['ports'])}; {len(m['titles'])} titles at {distinct(m['titles'])} "
                  f"(title {tok['title']}, {m['shrunk']} shrunk); {len(m['captions'])} captions at {distinct(m['captions'])} "
                  f"(caption {tok['caption']}); act glyph stroke {m['glyphStroke']}; "
                  f"distinct act glyph box sizes {len(boxes)} {dict(boxes)}")
            assert tok['scale'] == 1, (rel, 'ships at scale 1', tok['scale'])
            assert m['wires'] and m['ports'] and m['titles'], (rel, 'draws wires, ports and titles')
            for w in m['wires']:
                assert abs(w - tok['flow']) < 1e-6, (rel, 'a wire is tokens.stroke.flow wide', w, tok['flow'])
            for r in m['ports']:
                assert r == 5, (rel, 'a visible port circle has radius 5', r)
            for t in m['titles']:
                assert abs(t - tok['title']) < 1e-6, (rel, 'a card title draws at drawnSize(title)', t, tok['title'])
            for c in m['captions']:
                assert abs(c - tok['caption']) < 1e-6, (rel, 'a wire caption draws at drawnSize(caption)', c, tok['caption'])
            assert m['glyphStroke'] is not None, (rel, 'the picture carries the act glyph')
            glyph_strokes[rel] = m['glyphStroke']
        assert len(set(glyph_strokes.values())) == 1, ('the act glyph stroke is one value across documents', glyph_strokes)
        assert any(m['captions'] for _, m in at_one.values()), 'at least one document draws wire captions'

        # 2. The same fixture at scale 2.
        tok1, one = at_one[SAMPLE]
        s.open(scaled_copy(SAMPLE, 2), 'scaled.sov')
        tok2, two = s.tokens(), s.measure(s.picture())
        print(f"{SAMPLE} scale {tok2['scale']}: wires {distinct(two['wires'])}; card outlines {distinct(two['cards'].values())} "
              f"(scale 1 {distinct(one['cards'].values())}); act glyph stroke {two['glyphStroke']}; ports r {distinct(two['ports'])}; "
              f"junction dots r {distinct(two['junctions'])} (scale 1 {distinct(one['junctions'])}); "
              f"terminal marks {sorted({tuple(x) for x in two['marks']})} (scale 1 {sorted({tuple(x) for x in one['marks']})}); "
              f"chevron stroke {distinct(two['chevrons'])} (scale 1 {distinct(one['chevrons'])}); "
              f"{len(two['titles'])} titles at {distinct(two['titles'])} ({two['shrunk']} shrunk); captions at {distinct(two['captions'])}; "
              f"pin {tok2['pin']}; screen {tok2['screen']}")
        assert tok2['scale'] == 2, tok2
        assert tok2['screen']['min'] == tok1['screen']['min'], ('the screen floor does not scale', tok1['screen'], tok2['screen'])
        twice('tokens.type.screen.max', tok1['screen']['max'], tok2['screen']['max'])
        twice('tokens.space.pin', tok1['pin'], tok2['pin'])
        assert len(two['wires']) == len(one['wires']) and two['wires'], 'the scaled copy draws the same wires'
        for a, b in zip(one['wires'], two['wires']):
            twice('wire stroke width', a, b)
        assert set(two['cards']) == set(one['cards']) and two['cards'], 'the scaled copy draws the same cards'
        for cid, a in one['cards'].items():
            twice(f'card outline stroke width ({cid})', a, two['cards'][cid])
        twice('glyph stroke width', one['glyphStroke'], two['glyphStroke'])
        assert len(two['ports']) == len(one['ports'])
        for a, b in zip(one['ports'], two['ports']):
            twice('port radius', a, b)
        assert one['junctions'] and len(two['junctions']) == len(one['junctions']), ('the fixture draws junction dots', one['junctions'], two['junctions'])
        for a, b in zip(one['junctions'], two['junctions']):
            twice('junction dot radius', a, b)
        assert one['marks'] and len(two['marks']) == len(one['marks']), ('the fixture draws terminal marks', len(one['marks']), len(two['marks']))
        for (l1, t1), (l2, t2) in zip(one['marks'], two['marks']):
            twice('terminal mark length', l1, l2)
            twice('terminal mark thickness', t1, t2)
        for a, b in zip(one['chevrons'], two['chevrons']):
            twice('chevron stroke width', a, b)
        # Labels are compared with their scaled base: the scale 1 picture holds both at the 12 floor.
        assert two['titles'], 'the scaled copy draws at least one card title that is not shrunk'
        for t in two['titles']:
            assert abs(t - 20) < 1e-6 and t > tok2['screen']['min'], ('a card title at scale 2 draws at 20', t)
        assert two['captions'], 'the scaled copy draws wire captions'
        for c in two['captions']:
            assert abs(c - 18) < 1e-6 and c > tok2['screen']['min'], ('a wire caption at scale 2 draws at 18', c)

        # 3. A scale outside 0.5 to 4, or not a number, is refused.
        for bad in (0, 'big'):
            r = s.page.evaluate("(text)=>SovSchematicNotation.resolve(JSON.parse(text))", scaled_copy(SAMPLE, bad))
            print(f'resolve with tokens.scale {bad!r}: ok {r.get("ok")} code {r.get("code")} next_operation {r.get("next_operation")!r}')
            assert r.get('ok') is False and r.get('code') == 'SCALE_INVALID', (bad, r)
            assert r.get('message') and r.get('next_operation'), (bad, r)
        unscaled = s.page.evaluate("()=>SovSchematicNotation.BUILTIN.schematic.tokens")
        assert unscaled['scale'] == 1 and unscaled['stroke']['flow'] == tok1['flow'], ('the built-in tokens stay unscaled', unscaled)

        # 4. The snapshot draws titles as the picture does, at any camera zoom.
        tok, snap, pic = fitted_export_titles(s)
        report_fitted(tok, snap, pic)
        assert tok['zoom'] < 1, ('map.sov fitted has a camera zoom under 1', tok['zoom'])
        assert snap and Counter(round(x, 4) for x in snap) == Counter(round(x, 4) for x in pic), \
            ('file.svg draws card titles at the size renderStandaloneSvg does', distinct(snap), distinct(pic))

        errors = s.errors
        s.close()
    assert not errors, f'page errors: {errors}'
    print('PASS size scale QA')
    return 0


if __name__ == '__main__':
    args = sys.argv[1:]
    if args[:1] == ['--snapshot'] and len(args) == 2:
        raise SystemExit(snapshot_mode(Path(args[1])))
    if args[:1] == ['--compare'] and len(args) == 2:
        raise SystemExit(compare_mode(Path(args[1])))
    if args:
        raise SystemExit('usage: python tests/size_scale_qa.py [--snapshot DIR | --compare DIR]')
    raise SystemExit(main())
