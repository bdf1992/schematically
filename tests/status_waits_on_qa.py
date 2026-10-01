"""Status and waits-on QA (NOTATION-MODEL.md "Statuses", DATA-FORMATS.md config.status / config.waitsOn).

A Component or Wire may carry config.status, an id from its notation's statuses list (there is no
built-in list), and config.waitsOn, typed references {kind: person | rule | decision, id, label?}.

Node part (the real src files, no browser):
  - examples/work-engine/status.sov validates with scripts/validate_sov.mjs and carries the same
    notation as examples/work-engine/notation.sov (identical references[0]);
  - STATUS_UNKNOWN, STATUS_UNDECLARED and WAITS_ON_INVALID each come from create, update and load,
    on a Component and on a Wire, and a refused edit leaves the document unchanged;
  - an update with status null and waitsOn null removes both keys.
Browser part (index.html in Chromium):
  - file.open of the example raises no page error;
  - each card with a status has one .status-chip whose text is the status title, inside the card;
  - Anchor and the proposed card have a dashed .body; Anchor's node has opacity 0.55;
  - the proposed card's .waits-on reads 'Waits on Bdo, rule R-29, decision D1';
  - the Wire's caption contains Partial;
  - view.legend().entries holds the status entries Exists, Partial, Missing, Proposed in that order;
  - render.svg({}) carries the chip titles and the waits-on text.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/work-engine/status.sov'
NOTATION_EXAMPLE = ROOT / 'examples/work-engine/notation.sov'
CODES = ['STATUS_UNKNOWN', 'STATUS_UNDECLARED', 'WAITS_ON_INVALID']
TITLES = {'web-booth': 'Partial', 'recording': 'Partial', 'case': 'Exists', 'anchor': 'Missing', 'continuity-to-sqlite': 'Proposed'}
WAITS = 'Waits on Bdo, rule R-29, decision D1'

NODE = r'''
const [root, example] = process.argv.slice(1);
const fs = require('fs');
const Data = require(root + '/src/05-data-core.js');
const out = {};
const raw = JSON.parse(fs.readFileSync(example, 'utf8'));
const doc = Data.documentFromFilePayload(raw);
out.validate = Data.validateDocument(doc);

// A small base in the work-engine notation (carried as in the example), or in the plain
// schematic notation, which declares no statuses.
const base = (workEngine = true) => ({schema: Data.DOCUMENT_SCHEMA, id: 'status-base',
  ...(workEngine ? {notation: 'work-engine'} : {}),
  components: [
    {id: 'a', symbolId: workEngine ? 'we-record' : 'act', x: 120, y: 200, config: {label: 'A'}},
    {id: 'b', symbolId: workEngine ? 'we-record' : 'act', x: 420, y: 200, config: {label: 'B'}}
  ],
  wires: [{id: 'ab', a: 'a', aSide: 'out', b: 'b', bSide: 'in', config: {label: 'feeds'}}],
  references: workEngine ? [raw.references[0]] : []});
const codesIn = errors => [...new Set(errors.map(e => (e.match(/\b(STATUS_[A-Z_]+|WAITS_ON_[A-Z_]+):/) || [])[1]).filter(Boolean))];
out.baseErrors = [Data.validateDocument(Data.makeDocument(base())).errors, Data.validateDocument(Data.makeDocument(base(false))).errors];

// The bad config for each code, and which notation it is tried in.
const bad = {
  STATUS_UNKNOWN: {config: {status: 'shipped'}, workEngine: true},
  STATUS_UNDECLARED: {config: {status: 'exists'}, workEngine: false},
  WAITS_ON_INVALID: {config: {waitsOn: [{kind: 'person', id: 'bdo'}, {kind: 'team', id: 'x'}]}, workEngine: true}
};
out.cases = {};
for (const [code, {config, workEngine}] of Object.entries(bad)) {
  const r = {};
  for (const resource of ['component', 'wire']) {
    // At load.
    {
      const d = base(workEngine);
      if (resource === 'component') Object.assign(d.components[0].config, config); else Object.assign(d.wires[0].config, config);
      const errors = Data.validateDocument(Data.makeDocument(d)).errors;
      r[resource + ':load'] = {codes: codesIn(errors), errors};
    }
    // On create.
    {
      const d = Data.makeDocument(base(workEngine)); Data.normalizeDocument(d); const before = JSON.stringify(d);
      const value = resource === 'component'
        ? {id: 'c', symbolId: workEngine ? 'we-record' : 'act', config: {label: 'C', ...config}}
        : {id: 'ba', a: 'b', aSide: 'out', b: 'a', bSide: 'in', config: {label: 'back', ...config}};
      const receipt = Data.applyOperation(d, {op: 'create', resource, value});
      r[resource + ':create'] = {ok: receipt.ok, message: receipt.error?.message || '', unchanged: JSON.stringify(d) === before};
    }
    // On update.
    {
      const d = Data.makeDocument(base(workEngine)); Data.normalizeDocument(d); const before = JSON.stringify(d);
      const receipt = Data.applyOperation(d, {op: 'update', resource, resourceId: resource === 'component' ? 'a' : 'ab', patch: {config}});
      r[resource + ':update'] = {ok: receipt.ok, message: receipt.error?.message || '', unchanged: JSON.stringify(d) === before};
    }
  }
  out.cases[code] = r;
}
// The unknown status's message lists the declared ids.
out.unknownMessage = out.cases.STATUS_UNKNOWN['component:create'].message;
// The waitsOn message names the index and the field.
out.waitsMessage = out.cases.WAITS_ON_INVALID['component:update'].message;

// Accepted edits, then null removes both keys.
{
  const d = Data.makeDocument(base());
  const set = {status: 'proposed', waitsOn: [{kind: 'person', id: 'bdo', label: 'Bdo'}, {kind: 'rule', id: 'R-29'}]};
  const made = Data.applyOperation(d, {op: 'create', resource: 'component', value: {id: 'c', symbolId: 'we-migration', config: {label: 'C', ...set}}});
  const wired = Data.applyOperation(d, {op: 'update', resource: 'wire', resourceId: 'ab', patch: {config: set}});
  out.accepted = {made: made.ok, wired: wired.ok, component: Data.read(d, 'component', 'c').config, wire: Data.read(d, 'wire', 'ab').config,
    errors: Data.validateDocument(d).errors};
  const c1 = Data.applyOperation(d, {op: 'update', resource: 'component', resourceId: 'c', patch: {config: {status: null, waitsOn: null}}});
  const w1 = Data.applyOperation(d, {op: 'update', resource: 'wire', resourceId: 'ab', patch: {config: {status: null, waitsOn: null}}});
  const c = Data.read(d, 'component', 'c').config, w = Data.read(d, 'wire', 'ab').config;
  out.cleared = {ok: c1.ok && w1.ok, componentKeys: ['status', 'waitsOn'].filter(k => k in c), wireKeys: ['status', 'waitsOn'].filter(k => k in w),
    label: c.label, wireLabel: w.label, compact: ['status', 'waitsOn'].filter(k => k in Data.compactComponent(Data.read(d, 'component', 'c')).config)};
}
process.stdout.write(JSON.stringify(out));
'''


def node_part() -> None:
    proc = subprocess.run(['node', 'scripts/validate_sov.mjs', str(EXAMPLE.relative_to(ROOT))], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    example = json.loads(EXAMPLE.read_text(encoding='utf-8'))
    carried = json.loads(NOTATION_EXAMPLE.read_text(encoding='utf-8'))
    assert example['references'][0] == carried['references'][0], 'status.sov must carry the notation of notation.sov unchanged'
    assert example.get('notation') == 'work-engine', example.get('notation')

    proc = subprocess.run(['node', '-e', NODE, str(ROOT), str(EXAMPLE)], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    assert out['validate']['ok'], out['validate']
    assert out['baseErrors'] == [[], []], out['baseErrors']

    for code in CODES:
        for resource in ('component', 'wire'):
            load = out['cases'][code][resource + ':load']
            assert load['codes'] == [code], (code, resource, load['errors'])
            for op in ('create', 'update'):
                r = out['cases'][code][f'{resource}:{op}']
                assert not r['ok'] and r['message'].startswith(code + ':'), (code, resource, op, r)
                assert r['unchanged'], (code, resource, op, 'a refused edit changed the document')
    assert 'exists, partial, missing, proposed' in out['unknownMessage'], out['unknownMessage']
    assert 'config.waitsOn[1].kind' in out['waitsMessage'], out['waitsMessage']

    acc = out['accepted']
    assert acc['made'] and acc['wired'], acc
    for cfg in (acc['component'], acc['wire']):
        assert cfg['status'] == 'proposed' and cfg['waitsOn'] == [{'kind': 'person', 'id': 'bdo', 'label': 'Bdo'}, {'kind': 'rule', 'id': 'R-29'}], cfg
    assert acc['errors'] == [], acc['errors']
    cleared = out['cleared']
    assert cleared['ok'] and cleared['componentKeys'] == [] and cleared['wireKeys'] == [] and cleared['compact'] == [], cleared
    assert cleared['label'] == 'C' and cleared['wireLabel'] == 'feeds', cleared
    print(f"node part: {len(CODES)} codes refused on create, update and load for Components and Wires; null clears both keys")


BROWSER = '''()=>{
  const box=el=>{const r=el.getBoundingClientRect();return {l:r.left,r:r.right,t:r.top,b:r.bottom}};
  const cards={};
  for(const g of document.querySelectorAll('#nodes > .node')){
    const chips=[...g.querySelectorAll(':scope > .status-chip')],body=g.querySelector(':scope > .body'),waits=g.querySelector(':scope > .waits-on');
    cards[g.dataset.id]={chips:chips.map(c=>({text:c.textContent,status:c.dataset.status,box:box(c),rect:box(c.querySelector('rect'))})),
      body:body?box(body):null,dash:body?getComputedStyle(body).strokeDasharray:null,dashAttr:body?.getAttribute('stroke-dasharray')||null,
      opacity:getComputedStyle(g).opacity,waits:waits?waits.textContent:null,waitsBox:waits?box(waits):null};
  }
  const wire=document.querySelector('.wire-group[data-wire-id="w1"]');
  return {cards,caption:wire?.querySelector('.connection-label')?.textContent||null,wireDash:wire?getComputedStyle(wire.querySelector('path.wire')).strokeDasharray:null,
    legend:SovSchematicAPI.view.legend().entries.filter(e=>e.kind==='status')};
}'''


def browser_part() -> None:
    from playwright.sync_api import sync_playwright
    from browser_runtime import chromium_launch_kwargs
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    text = EXAMPLE.read_text(encoding='utf-8')
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.set_content(html, wait_until='load'); page.wait_for_timeout(150)
        opened = page.evaluate('(t)=>{const r=SovSchematicAPI.file.open(t,"status.sov");fitDiagram();return r}', text)
        page.wait_for_timeout(200)
        assert not errors, errors
        assert opened is None or opened.get('ok', True) is not False, opened

        b = page.evaluate(BROWSER)
        cards = b['cards']
        for cid, title in TITLES.items():
            card = cards[cid]
            assert len(card['chips']) == 1, (cid, card['chips'])
            chip = card['chips'][0]
            assert chip['text'] == title, (cid, chip)
            # Inside the card's top-right corner.
            B, C = card['body'], chip['rect']
            assert C['l'] > B['l'] and C['r'] < B['r'] and C['t'] > B['t'] and C['b'] < (B['t'] + B['b']) / 2, (cid, C, B)
            assert C['r'] > (B['l'] + B['r']) / 2, (cid, 'the chip sits on the right half', C, B)
        for cid in ('anchor', 'continuity-to-sqlite'):
            assert cards[cid]['dashAttr'] == '6 4' and cards[cid]['dash'].replace('px', '').replace(',', ' ').split() == ['6', '4'], (cid, cards[cid]['dash'], cards[cid]['dashAttr'])
        for cid in ('case', 'recording', 'web-booth'):
            assert cards[cid]['dash'] in ('none', None, '') and cards[cid]['dashAttr'] is None, (cid, cards[cid]['dash'])
        assert abs(float(cards['anchor']['opacity']) - 0.55) < 1e-6, cards['anchor']['opacity']
        assert abs(float(cards['case']['opacity']) - 1) < 1e-6, cards['case']['opacity']
        assert cards['continuity-to-sqlite']['waits'] == WAITS, cards['continuity-to-sqlite']['waits']
        W, B = cards['continuity-to-sqlite']['waitsBox'], cards['continuity-to-sqlite']['body']
        assert W['t'] >= B['b'], ('waits-on sits under the card', W, B)
        assert all(cards[c]['waits'] is None for c in cards if c != 'continuity-to-sqlite'), cards
        assert b['caption'] and 'Partial' in b['caption'] and b['caption'].startswith('Web booth feeds Recording'), b['caption']
        assert b['wireDash'] in ('none', None, ''), b['wireDash']
        legend = [(e['id'], e['label']) for e in b['legend']]
        assert legend == [('status:exists', 'Exists'), ('status:partial', 'Partial'), ('status:missing', 'Missing'), ('status:proposed', 'Proposed')], legend
        assert all(e['meaning'] for e in b['legend']), b['legend']

        svg = page.evaluate('()=>SovSchematicAPI.render.svg({})')
        for title in sorted(set(TITLES.values())):
            assert f'>{title}<' in svg, f'render.svg lost the chip title {title}'
        assert WAITS in svg and 'status-chip' in svg, 'render.svg lost the waits-on text or the chips'
        assert not errors, errors
        browser.close()
    print(f"browser part: chips {sorted((c, cards[c]['chips'][0]['text']) for c in TITLES)}; caption {b['caption']!r}")


if __name__ == '__main__':
    node_part()
    browser_part()
    print('PASS status and waits-on QA')
