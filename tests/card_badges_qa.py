"""Card badges QA (DATA-FORMATS.md "Badges", NOTATION-MODEL.md "Statuses").

A Component's config.badges is an array of at most 4 {label, colorSlot?}: small chips drawn in a row
from the card's top-left corner with the status chip's geometry, no status meaning.

In headless Chromium on index.html, with examples/work-engine/status.sov as the base:
  - a card with badges [{label: 'Record'}, {label: 'Owned by seat', colorSlot: 7}] draws two .card-badge
    chips in order from the top-left, inside the card, overlapping neither each other nor its status chip;
  - six badges are refused with BADGE_INVALID and the document is unchanged; so are the other bad forms;
  - a narrow card with three badges and a status draws a +N chip whose title lists the badges not drawn;
  - a file carrying an invalid badge loads and reports BADGE_INVALID;
  - node scripts/validate_sov.mjs passes on a document with valid badges;
  - every badge's text has no text-contrast finding, in light and in dark;
  - saving and opening keeps the badges; the page logs no errors.
"""
from __future__ import annotations
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/work-engine/status.sov'
BADGES = [{'label': 'Record'}, {'label': 'Owned by seat', 'colorSlot': 7}]

CHIPS = r'''(id)=>{
  const g=document.querySelector(`#nodes > .node[data-id="${id}"]`),box=el=>{const r=el.getBoundingClientRect();return {l:r.left,r:r.right,t:r.top,b:r.bottom}};
  const body=g.querySelector(':scope > .body'),status=g.querySelector(':scope > .status-chip');
  return {body:box(body),status:status?box(status.querySelector('rect')):null,zoom:Number(getComputedStyle(workspace).getPropertyValue('--zoom'))||1,
    chips:[...g.querySelectorAll(':scope > .card-badge')].map(c=>({index:c.dataset.badgeIndex,text:c.textContent.replace(c.querySelector('title')?.textContent||'',''),
      title:c.querySelector('title')?.textContent||null,more:c.dataset.badgeMore||null,rect:box(c.querySelector('rect')),
      fill:c.querySelector('text').style.fill,stroke:c.querySelector('rect').style.stroke}))};
}'''

TEXT_CONTRAST = r'''()=>{
  fitDiagram();
  const c=SovSchematicAPI.layout.contrast({static:true});
  return c.findings.filter(f=>f.kind==='text-contrast').map(f=>f.detail);
}'''


def apart(a: dict, b: dict, gap: float = 0) -> bool:
    return a['r'] + gap <= b['l'] + 1e-6 or b['r'] + gap <= a['l'] + 1e-6 or a['b'] + gap <= b['t'] + 1e-6 or b['b'] + gap <= a['t'] + 1e-6


def main() -> None:
    from playwright.sync_api import sync_playwright
    from browser_runtime import chromium_launch_kwargs
    text = EXAMPLE.read_text(encoding='utf-8')
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load'); page.wait_for_timeout(150)
        page.evaluate('(t)=>{SovSchematicAPI.file.open(t,"status.sov");fitDiagram()}', text)
        page.wait_for_timeout(200)

        # Two badges on a card that has a status.
        r = page.evaluate('(b)=>SovSchematicAPI.update("component","case",{config:{badges:b,presentation:{size:{w:240}}}})', BADGES)
        assert r.get('ok'), r
        page.evaluate('()=>fitDiagram()'); page.wait_for_timeout(100)
        m = page.evaluate(CHIPS, 'case')
        chips = m['chips']
        assert [c['text'] for c in chips] == ['Record', 'Owned by seat'], chips
        assert [c['index'] for c in chips] == ['0', '1'], chips
        B, z = m['body'], m['zoom']
        assert abs(chips[0]['rect']['l'] - (B['l'] + 6 * z)) < 1.5 and abs(chips[0]['rect']['t'] - (B['t'] + 6 * z)) < 1.5, ('first chip starts 6 in from the top-left', chips[0], B)
        assert abs(chips[1]['rect']['l'] - chips[0]['rect']['r'] - 4 * z) < 1.5, ('chips are 4 apart', chips)
        for c in chips:
            R = c['rect']
            assert R['l'] > B['l'] and R['r'] < B['r'] and R['t'] > B['t'] and R['b'] < B['b'], ('inside the card', c, B)
            assert 'rgb' in c['stroke'] or c['stroke'].startswith('#'), c
        assert apart(chips[0]['rect'], chips[1]['rect']), chips
        assert m['status'] and all(apart(c['rect'], m['status']) for c in chips), ('a chip overlaps the status chip', chips, m['status'])
        assert chips[0]['stroke'] != chips[1]['stroke'], 'colorSlot 7 differs from the default slot 0'

        # Refusals: the document is unchanged.
        before = page.evaluate('()=>JSON.stringify(SovSchematicAPI.file.document())')
        bad = {
            'six': [{'label': str(i)} for i in range(6)],
            'not an array': 'Record',
            'empty label': [{'label': '  '}],
            'missing label': [{'colorSlot': 1}],
            'long label': [{'label': 'x' * 25}],
            'slot high': [{'label': 'a', 'colorSlot': 12}],
            'slot fraction': [{'label': 'a', 'colorSlot': 1.5}],
            'unknown key': [{'label': 'a', 'icon': 'x'}],
            'not an object': ['a'],
        }
        for name, value in bad.items():
            for op in ('update', 'create'):
                if op == 'update':
                    receipt = page.evaluate('(b)=>SovSchematicAPI.update("component","anchor",{config:{badges:b}})', value)
                else:
                    receipt = page.evaluate('(b)=>SovSchematicAPI.create("component",{id:"fresh",symbolId:"we-record",config:{label:"F",badges:b}})', value)
                msg = json.dumps(receipt)
                assert not receipt.get('ok') and 'BADGE_INVALID' in msg, (name, op, receipt)
            if name == 'six':
                assert 'config.badges' in msg and '6' in msg, msg
            if name in ('empty label', 'unknown key', 'slot high'):
                assert 'config.badges[0]' in msg, msg
            assert page.evaluate('()=>JSON.stringify(SovSchematicAPI.file.document())') == before, f'a refused {name} badge list changed the document'

        # A narrow card with three badges and a status draws a +N chip.
        r = page.evaluate('(b)=>SovSchematicAPI.update("component","recording",{config:{badges:b,presentation:{size:{w:132}}}})',
                          [{'label': 'Record'}, {'label': 'Owned by seat'}, {'label': 'Third'}])
        assert r.get('ok'), r
        page.evaluate('()=>fitDiagram()'); page.wait_for_timeout(100)
        n = page.evaluate(CHIPS, 'recording')
        nb = n['body']
        assert n['chips'] and n['chips'][-1]['more'] == 'true', n['chips']
        last = n['chips'][-1]
        hidden = 3 - (len(n['chips']) - 1)
        assert last['text'] == f'+{hidden}', last
        assert last['title'] == ', '.join(['Record', 'Owned by seat', 'Third'][len(n['chips']) - 1:]), last
        for c in n['chips']:
            assert apart(c['rect'], n['status'], 4 * n['zoom'] - 1.5), ('a chip comes within 4 of the status chip', c, n['status'])
            assert c['rect']['r'] <= nb['r'] - 6 * n['zoom'] + 1.5, ('a chip comes within 6 of the right edge', c, nb)

        # A file carrying an invalid badge loads and reports BADGE_INVALID.
        doc = json.loads(text)
        doc['components'][0]['config']['badges'] = [{'label': ''}]
        errs = page.evaluate('''(t)=>SovSchematicData.validateDocument(SovSchematicData.makeDocument(JSON.parse(t))).errors''', json.dumps(doc))
        assert any('BADGE_INVALID' in e and 'config.badges[0].label' in e and e.startswith('component web-booth') for e in errs), errs

        # Valid badges: validate_sov passes, light and dark carry no text-contrast finding, and save/open keeps them.
        doc = json.loads(text)
        doc['components'][0]['config']['badges'] = BADGES
        doc['components'][1]['config']['badges'] = [{'label': 'A', 'colorSlot': 0}, {'label': 'Eleven', 'colorSlot': 11}, {'label': 'Five', 'colorSlot': 5}]
        doc['components'][2]['config']['badges'] = [{'label': 'Queue', 'colorSlot': 3}]
        for c in doc['components'][:3]:
            c['config']['presentation'] = {'size': {'w': 260}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'badges.sov'
            path.write_text(json.dumps(doc, indent=1) + '\n', encoding='utf-8', newline='\n')
            proc = subprocess.run(['node', 'scripts/validate_sov.mjs', str(path)], cwd=ROOT, capture_output=True, text=True)
            assert proc.returncode == 0, proc.stdout + proc.stderr
        for appearance in ('light', 'dark'):
            page.evaluate('(a)=>SovSchematicAPI.view.setAppearance(a)', appearance)
            page.evaluate('(t)=>{SovSchematicAPI.file.open(t,"badges.sov");fitDiagram()}', json.dumps(doc)); page.wait_for_timeout(200)
            found = page.evaluate(TEXT_CONTRAST)
            assert found == [], (appearance, found)
            drawn = page.evaluate('()=>document.querySelectorAll("#nodes .card-badge").length')
            assert drawn >= 4, (appearance, drawn)
        saved = page.evaluate('()=>JSON.stringify(SovSchematicAPI.file.document())')
        page.evaluate('(t)=>SovSchematicAPI.file.open(t,"again.sov")', saved); page.wait_for_timeout(150)
        again = page.evaluate('()=>SovSchematicAPI.file.document().components.map(c=>[c.id,c.config.badges||null])')
        assert dict(again)['web-booth'] == BADGES and dict(again)['case'] == [{'label': 'Queue', 'colorSlot': 3}], again

        assert not errors, errors
        browser.close()
    print('card badges: order, geometry, +N, refusals, load report, contrast in light and dark, save and open')


if __name__ == '__main__':
    main()
    print('PASS card badges QA')
