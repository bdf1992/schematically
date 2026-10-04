"""A glyph draws at one size wherever its card has room for it.

The glyph token (tokens.glyph, 80.64 by 40.4 at scale 1) is the glyph's box on every card that has
room (SovSchematicNotation.glyphRoom, NOTATION-MODEL.md sections 3 and 4). A card without room keeps
the box that follows the card, the shrink for a lone two-line title included (schematically#95). A
card without room is reported as a glyph-room finding with no weight in the score, and only the
layered layout grows a card to hold its glyph.

On headless Chromium over index.html. This file carries its own copy of the box formula as it was
before the fixed size (REFERENCE_JS) and its own copy of the room rule, so neither is read from the
code under test. It asserts:
  (a) every glyph card in four documents, and act cards built here at 112 by 84, 112 by 90, 260 by
      120 and 280 by 140 with a one-line title, with a subtitle and with the title 'Delivery
      broker': where the room rule holds the drawn use.glyph box is the token within 0.01; where
      it does not, the box is the reference formula's within 0.01. A 112 by 84 card titled 'Web
      booth' has room and its box is the reference formula's too.
  (b) terminalOffset for the act glyph's in terminal is (28 - 48) times the box scale in both cases.
  (c) the pictures of task-lifecycle.sov, work-engine-sample.sov and groups.sov each hold one
      distinct act glyph box.
  (d) 'Web booth' and 'Delivery broker' at 112 by 84: layout.metrics reports one glyph-room finding,
      naming delivery-broker; layout.rubric has no glyph-room key; the score is the score of the
      weighted kinds alone, and the score of the same document without that card.
  (e) after layout.apply({engine: 'layered'}) delivery-broker is stored 112 by 112, web-booth stays
      112 by 84, both boxes are fixed and glyph-room is 0; a pinned card keeps its size.
  (f) opening, rendering and saving a document changes no stored size.
  (g) under a carried notation with tokens.scale 2 the glyph token resolves to 161.28 by 80.8;
      tokens.glyph {w: 0, h: 40} is refused with GLYPH_SIZE_INVALID.
  (h) the page logs no errors.
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

GROUPS = 'examples/work-engine/groups.sov'
LIFECYCLE = 'tests/fixtures/task-lifecycle.sov'
SAMPLE = 'tests/fixtures/work-engine-sample.sov'
MAP = 'docs/workengine/map.sov'
DOCS = [GROUPS, LIFECYCLE, SAMPLE, MAP]
TOKEN = (80.64, 40.4)
TOL = 0.01 + 1e-9

# The box formula before the fixed size (dev d165ee1, src/03-notation-core.js glyphBox), and the
# room rule, both written out here. `many` is a glyph whose terminals are its points.
REFERENCE_JS = """
const REF = (() => {
  const ADVANCE = [['iljI.,:;!|\\'\\u00b7', .3], ['frt ()[]-', .38], ['sJ"', .55], ['mwMW', .88], ['ABCDGHKNOQRUVXY&', .72], ['EFLPSTZ', .64]];
  const titleWidth = title => { let em = 0; for (const c of String(title || '')) { const hit = ADVANCE.find(([cs]) => cs.includes(c)); em += hit ? hit[1] : c >= 'A' && c <= 'Z' ? .68 : .59 } return em * .94 };
  const drawn = (type, role) => { const t = type[role] || {}, lo = t.min ?? type.screen?.min ?? 0, hi = type.screen?.max ?? Infinity; return Math.max(lo, Math.min(hi, t.size || 10)) };
  const parts = (size, subtitle, title, type) => {
    const ts = drawn(type, 'title'), ss = drawn(type, 'subtitle'), avail = Math.max(1, size.w - 12);
    const lines = Math.max(1, Math.min(2, Math.ceil(String(title || '').length * ts * .6 / avail)));
    const foot = 8 + lines * ts * 1.15 + (subtitle ? ss * 1.3 : 0);
    return {ts, avail, lines, foot, two: lines === 2 && !subtitle && titleWidth(title) * ts > avail * .85};
  };
  const box = (many, size, subtitle, title, type) => {
    const {ts, foot, two} = parts(size, subtitle, title, type);
    let w = Math.min(size.w * .72, 108), h = Math.max(24, Math.min(size.h * (many ? .7 : .55), 70, size.h - 2 * foot));
    if (two) { const room = size.h - 2 * (2.6 * ts + 4); if (room < h) { const k = Math.max(.6, room / h); w *= k; h *= k } }
    return {w, h};
  };
  const room = (F, size, subtitle, title, type) => {
    const {ts, foot, two} = parts(size, subtitle, title, type), s = Math.min(F.w / 96, F.h / 64), E = 1e-6;
    return 96 * s <= .72 * size.w + E && 64 * s <= size.h - 2 * foot + E && (!two || 64 * s <= size.h - 2 * (2.6 * ts + 4) + E);
  };
  return {box, room};
})();
"""

# Every card on the canvas that draws a glyph through glyphBox (not a container's title mark).
CARDS_JS = "() => {" + REFERENCE_JS + """
  const T = activeNotation().tokens, N = SovSchematicNotation, out = [];
  for (const el of nodesG.querySelectorAll('.node[data-id]')) {
    const u = el.querySelector(':scope > use.glyph'); if (!u) continue;
    const n = nodes.find(x => x.id === el.dataset.id); if (!n) continue;
    if (componentAcceptsChildren(n) && !componentHostedOnWire(n)) { out.push({id: n.id, skipped: 'container'}); continue }
    const cfg = componentConfig(n), size = cfg.presentation.size, g = componentGlyph(n), shape = componentShapeGeometry(n);
    const many = g?.points === 'terminals';
    const inner = shape.shape === 'rect' || many ? size : {w: shape.inner.r - shape.inner.l, h: shape.shape === 'cylinder' ? size.h - 2 * shape.cap : size.h};
    const title = String(cfg.label || '').trim() || componentTypeCaption(n), subtitle = !!String(cfg.subtitle || '').trim();
    const w = +u.getAttribute('width'), h = +u.getAttribute('height');
    const opts = {subtitle, title, type: T.type, glyph: T.glyph};
    const t = g && (g.terminals || []).find(x => x.id === 'in'), off = t ? N.terminalOffset(g, 'in', inner, opts) : null;
    out.push({id: n.id, symbol: n.symbolId, size: [size.w, size.h], title, subtitle, hosted: !!componentHostedOnWire(n),
      box: [w, h], scale: Math.min(w / 96, h / 64), ref: REF.box(many, inner, subtitle, title, T.type), room: REF.room({w: %s, h: %s}, inner, subtitle, title, T.type),
      fixed: N.glyphBox(g, inner, opts).fixed, inAt: t ? t.at[0] : null, dx: off ? off.dx : null});
  }
  return out;
}""" % TOKEN

ACT_BOXES_JS = """() => [...document.querySelectorAll('use.glyph')].filter(u => (u.getAttribute('href') || '') === '#sym-act')
  .map(u => `${(+u.getAttribute('width')).toFixed(2)}x${(+u.getAttribute('height')).toFixed(2)}`)"""
METRICS_JS = "() => window.SovSchematicAPI.layout.metrics({static: true})"
SIZES_JS = """() => Object.fromEntries(window.SovSchematicAPI.file.document().components
  .filter(c => c.config?.presentation?.size).map(c => [c.id, [c.config.presentation.size.w, c.config.presentation.size.h]]))"""


def card(cid: str, title: str, w: int, h: int, x: int, y: int, subtitle: str = '', pinned: bool = False) -> dict:
    config = {'label': title, 'presentation': {'size': {'w': w, 'h': h}}}
    if subtitle:
        config['subtitle'] = subtitle
    out = {'id': cid, 'symbolId': 'act', 'x': x, 'y': y, 'canvasId': 'canvas:global', 'config': config}
    if pinned:
        out['editor'] = {'pinned': True}
    return out


def document(doc_id: str, components: list, references: list | None = None, notation: str | None = None) -> str:
    doc = {'schema': 'soveraeign.schematic/document@0.1', 'id': doc_id, 'revision': 0, 'meta': {'title': doc_id},
           'components': components, 'wires': [], 'references': references or [], 'layout': {}}
    if notation:
        doc['notation'] = notation
    return json.dumps(doc)


def close(box, wh) -> bool:
    return abs(box[0] - wh[0]) <= TOL and abs(box[1] - wh[1]) <= TOL


def stored_sizes(text: str) -> dict:
    return {c['id']: [c['config']['presentation']['size']['w'], c['config']['presentation']['size']['h']]
            for c in json.loads(text)['components'] if (c.get('config') or {}).get('presentation', {}).get('size')}


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

    def cards(self) -> list:
        return self.page.evaluate(CARDS_JS)

    def act_boxes(self) -> Counter:
        """The act glyph boxes in the picture, loaded as its own page."""
        svg = self.page.evaluate("() => renderStandaloneSvg({pad: 48})")
        pic = self.browser.new_page(viewport={'width': 1600, 'height': 1000})
        pic.set_content(svg, wait_until='load')
        out = Counter(pic.evaluate(ACT_BOXES_JS))
        pic.close()
        return out


def check_cards(where: str, rows: list) -> tuple[int, int]:
    """(a) and (b) over the cards of one document. Returns how many had room and how many had not."""
    with_room = without = 0
    for r in rows:
        if r.get('skipped'):
            continue
        ref = (r['ref']['w'], r['ref']['h'])
        if r['room']:
            with_room += 1
            assert close(r['box'], TOKEN), (where, r['id'], '(a) a card with room draws the glyph token', r['size'], r['title'], r['box'])
            assert r['fixed'] is True, (where, r['id'], '(a) glyphBox says the box is fixed', r)
        else:
            without += 1
            assert close(r['box'], ref), (where, r['id'], '(a) a card without room draws the box that follows the card', r['size'], r['title'], r['box'], ref)
            assert r['fixed'] is False, (where, r['id'], '(a) glyphBox says the box is not fixed', r)
        if r['symbol'] == 'act':
            assert r['inAt'] == 28, (where, r['id'], 'the act glyph\'s in terminal is at x 28', r['inAt'])
            assert abs(r['dx'] - (28 - 48) * r['scale']) < 1e-6, (where, r['id'], '(b) terminalOffset is (28 - 48) times the box scale', r['dx'], r['scale'])
    return with_room, without


def main() -> int:
    with sync_playwright() as p:
        s = Session(p)

        # (a), (b), (c), (f) on the four documents.
        pictures = {}
        for rel in DOCS:
            text = (ROOT / rel).read_text(encoding='utf-8')
            s.open(text, Path(rel).name)
            rows = s.cards()
            measured = [r for r in rows if not r.get('skipped')]
            with_room, without = check_cards(rel, rows)
            boxes = Counter(f"{r['box'][0]:.2f}x{r['box'][1]:.2f}" for r in measured)
            pictures[rel] = s.act_boxes()
            print(f"{rel}: {len(measured)} glyph cards ({len(rows) - len(measured)} container title marks left out); {with_room} with room at "
                  f"{TOKEN[0]}x{TOKEN[1]}, {without} without room at the reference box {sorted({k for k in boxes if k != '80.64x40.40'})}; "
                  f"act glyph boxes in the picture {dict(pictures[rel])}")
            assert measured, (rel, 'draws glyph cards')
            before, after = stored_sizes(text), s.page.evaluate(SIZES_JS)
            assert before, (rel, 'stores card sizes')
            for cid, wh in before.items():
                assert after.get(cid) == wh, (rel, cid, '(f) opening, rendering and saving changes no stored size', wh, after.get(cid))
        for rel in (LIFECYCLE, SAMPLE, GROUPS):
            assert len(pictures[rel]) == 1, (rel, '(c) the picture holds one distinct act glyph box', dict(pictures[rel]))
            assert list(pictures[rel]) == ['80.64x40.40'], (rel, '(c) and it is the glyph token', dict(pictures[rel]))

        # (a), (b) on act cards built here: four sizes, three titles each.
        built, sizes = [], [(112, 84), (112, 90), (260, 120), (280, 140)]
        for i, (w, h) in enumerate(sizes):
            built.append(card(f'one-{w}x{h}', 'Web booth', w, h, 200, 200 + 300 * i))
            built.append(card(f'sub-{w}x{h}', 'Web booth', w, h, 700, 200 + 300 * i, subtitle='serves pages'))
            built.append(card(f'two-{w}x{h}', 'Delivery broker', w, h, 1200, 200 + 300 * i))
        s.open(document('built-cards', built), 'built.sov')
        rows = {r['id']: r for r in s.cards()}
        assert set(rows) == {c['id'] for c in built}, ('every built card draws a glyph', sorted(rows))
        with_room, without = check_cards('built', list(rows.values()))
        for cid, r in rows.items():
            print(f"built {cid}: {r['size'][0]}x{r['size'][1]} {r['title']!r}{' with a subtitle' if r['subtitle'] else ''}: room {r['room']}, "
                  f"box {r['box'][0]:.2f}x{r['box'][1]:.2f}, reference {r['ref']['w']:.2f}x{r['ref']['h']:.2f}, in terminal dx {r['dx']:.4f}")
        assert with_room and without, ('the built cards hold both cases', with_room, without)
        web = rows['one-112x84']
        assert web['room'] and close(web['box'], TOKEN), ('(a) a 112 by 84 card titled Web booth has room', web)
        assert close(web['box'], (web['ref']['w'], web['ref']['h'])), ('(a) and its box is the reference formula\'s too', web)
        broker = rows['two-112x84']
        assert not broker['room'] and broker['box'][1] < 24, ('(a) Delivery broker at 112 by 84 keeps the shrink for a lone two-line title', broker)
        assert rows['two-260x120']['room'] and rows['sub-280x140']['room'], ('the larger cards have room', rows['two-260x120'], rows['sub-280x140'])
        after = s.page.evaluate(SIZES_JS)
        for c in built:
            wh = [c['config']['presentation']['size']['w'], c['config']['presentation']['size']['h']]
            assert after[c['id']] == wh, (c['id'], '(f) opening, rendering and saving changes no stored size', wh, after[c['id']])

        # (d) the finding, with no weight in the score.
        pair = [card('web-booth', 'Web booth', 112, 84, 200, 200), card('delivery-broker', 'Delivery broker', 112, 84, 200, 420)]
        s.open(document('pair', pair), 'pair.sov')
        m = s.page.evaluate(METRICS_JS)
        room = [f for f in m['findings'] if f['kind'] == 'glyph-room']
        rubric = s.page.evaluate("() => window.SovSchematicAPI.layout.rubric()")
        weighted = round(max(0.0, 10 - sum(min(rubric[k][1], n * rubric[k][0]) for k, n in m['counts'].items() if k in rubric)), 1)
        print(f"pair: score {m['score']}, counts {m['counts']}, glyph-room {[(f['ids'], f['detail']) for f in room]}; score of the weighted kinds {weighted}")
        assert len(room) == 1 and room[0]['ids'] == ['delivery-broker'], ('(d) one glyph-room finding, naming delivery-broker', room)
        assert 'Delivery broker' in room[0]['detail'] and '112 by 84' in room[0]['detail'] and '112 by 112' in room[0]['detail'], ('(d) the detail names the title, the size and the size it needs', room[0]['detail'])
        assert m['counts'].get('glyph-room') == 1, ('(d) it is in counts', m['counts'])
        assert 'glyph-room' not in rubric and 'glyph-room' not in m['rubric'], ('(d) glyph-room has no entry in the rubric', sorted(rubric))
        assert m['score'] == weighted, ('(d) the score is the score of the weighted kinds', m['score'], weighted)
        s.open(document('pair-less', pair[:1]), 'pair-less.sov')
        less = s.page.evaluate(METRICS_JS)
        print(f"pair without delivery-broker: score {less['score']}, counts {less['counts']}")
        assert less['counts'].get('glyph-room') is None, ('a card with room has no finding', less['counts'])
        assert m['score'] == less['score'], ('(d) the score is the score of the document without that card', m['score'], less['score'])

        # (e) only the layered layout grows a card; a pinned card keeps its size.
        s.open(document('pair', pair), 'pair.sov')
        applied = s.page.evaluate("() => window.SovSchematicAPI.layout.apply({engine: 'layered'})")
        assert applied.get('ok'), ('layout.apply runs', applied)
        after, rows = s.page.evaluate(SIZES_JS), {r['id']: r for r in s.cards()}
        m = s.page.evaluate(METRICS_JS)
        print(f"pair after layered: stored {after}; boxes { {k: [round(v, 2) for v in r['box']] for k, r in rows.items()} }; counts {m['counts']}")
        assert after['delivery-broker'] == [112, 112], ('(e) delivery-broker is stored 112 by 112', after)
        assert after['web-booth'] == [112, 84], ('(e) web-booth stays 112 by 84', after)
        for cid in ('web-booth', 'delivery-broker'):
            assert rows[cid]['fixed'] is True and close(rows[cid]['box'], TOKEN), (cid, '(e) the box is fixed', rows[cid])
        assert m['counts'].get('glyph-room') is None, ('(e) glyph-room is 0', m['counts'])
        pinned = pair + [card('held', 'Delivery pinned', 112, 84, 200, 640, pinned=True)]
        s.open(document('pinned', pinned), 'pinned.sov')
        applied = s.page.evaluate("() => window.SovSchematicAPI.layout.apply({engine: 'layered'})")
        assert applied.get('ok') and 'held' in applied.get('frozen', []), ('the pinned card is frozen', applied)
        after, m = s.page.evaluate(SIZES_JS), s.page.evaluate(METRICS_JS)
        room = [f['ids'] for f in m['findings'] if f['kind'] == 'glyph-room']
        print(f"pinned after layered: stored {after}; glyph-room {room}")
        assert after['held'] == [112, 84], ('(e) a pinned card keeps its size', after)
        assert after['delivery-broker'] == [112, 112] and after['web-booth'] == [112, 84], ('(e) the others are as before', after)
        assert room == [['held']], ('the pinned card without room is the one finding left', room)

        # (g) the token scales with the document and a bad token is refused.
        def carried(tokens: dict) -> str:
            return document('carried', pair, notation='sized',
                            references=[{'id': 'notation-sized', 'kind': 'notation', 'data': {'id': 'sized', 'extends': 'schematic', 'tokens': tokens}}])
        r = s.page.evaluate("(t) => SovSchematicNotation.resolve(JSON.parse(t))", carried({'scale': 2}))
        print(f"tokens.scale 2: ok {r.get('ok')}, glyph token {r.get('notation', {}).get('tokens', {}).get('glyph')}")
        assert r.get('ok') and r['notation']['tokens']['glyph'] == {'w': 161.28, 'h': 80.8}, ('(g) the glyph token at scale 2 is 161.28 by 80.8', r.get('notation', {}).get('tokens', {}).get('glyph'))
        r = s.page.evaluate("(t) => SovSchematicNotation.resolve(JSON.parse(t))", carried({'glyph': {'w': 0, 'h': 40}}))
        print(f"tokens.glyph {{w: 0, h: 40}}: ok {r.get('ok')} code {r.get('code')} next_operation {r.get('next_operation')!r}")
        assert r.get('ok') is False and r.get('code') == 'GLYPH_SIZE_INVALID', ('(g) a glyph token with w 0 is refused', r)
        assert r.get('message') and r.get('next_operation'), ('the refusal says what to do', r)
        built_in = s.page.evaluate("() => SovSchematicNotation.BUILTIN.schematic.tokens.glyph")
        assert built_in == {'w': TOKEN[0], 'h': TOKEN[1]}, ('the built-in token stays unscaled', built_in)

        errors = s.errors
        s.browser.close()
    assert not errors, f'(h) page errors: {errors}'
    print('PASS glyph fixed size QA')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
