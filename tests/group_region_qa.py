"""Group region QA (SECTION-MODEL.md "Groups (reading only)").

A group (symbolId 'group') collects Components for reading. It is not a boundary: it hosts
nothing, has no ports, and a Wire between members of different groups is one Wire on their
shared canvas.

Node part (the real src files, no browser):
  - examples/work-engine/groups.sov validates with scripts/validate_sov.mjs;
  - every Wire in it joins two non-point Components on canvas:global, directly;
  - every refusal code is produced once at load (validateDocument) by a crafted document, and
    once by a create or update through Data.applyOperation, with the document unchanged;
  - groupRect of Records equals the union of its members computed here;
  - deleting a member removes it from the group's members.
Browser part (index.html in Chromium):
  - file.open of the example raises no page error;
  - two .group-region elements, each containing every member's .body box, drawn behind every
    node and wire; no .body inside a .node.group; both titles drawn;
  - render.svg({}) carries both titles;
  - layout.metrics() has no node-overlap or route-through-node finding naming a group.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/work-engine/groups.sov'
CODES = ['GROUP_MEMBER_UNKNOWN', 'GROUP_MEMBER_CANVAS', 'GROUP_MEMBER_HOSTED', 'GROUP_MEMBER_GROUP',
         'GROUP_MEMBER_TWICE', 'GROUP_PORTS', 'GROUP_HOST']
CARD = {'w': 112, 'h': 84}

NODE = r'''
const [root, example] = process.argv.slice(1);
const fs = require('fs');
const Data = require(root + '/src/05-data-core.js');
const out = {};

// The example, loaded the way the validator and file.open load it.
const doc = Data.documentFromFilePayload(JSON.parse(fs.readFileSync(example, 'utf8')));
out.validate = Data.validateDocument(doc);
const byId = new Map(doc.components.map(c => [c.id, c]));
out.wires = doc.wires.map(w => ({id: w.id, canvasId: w.canvasId,
  ends: [w.a, w.b].map(id => ({id, symbolId: byId.get(id)?.symbolId, dimension: byId.get(id) ? Data.effectiveDimension(byId.get(id)) : null, canvasId: byId.get(id)?.canvasId || 'canvas:global'}))}));
out.members = Object.fromEntries(doc.components.filter(c => c.symbolId === 'group').map(c => [c.id, c.config.members]));
out.positions = Object.fromEntries(doc.components.map(c => [c.id, [c.x, c.y]]));
out.records = Data.groupRect(doc, 'records', () => ({w: 112, h: 84}));
out.empty = Data.groupRect(Data.makeDocument({components: [{id: 'lone', symbolId: 'group', x: 50, y: 60}]}), 'lone', () => ({w: 112, h: 84}));

// A small valid base: a group, two cards, a Plane with a card inside and a boundary Point.
const base = () => ({schema: Data.DOCUMENT_SCHEMA, id: 'groups-base', components: [
  {id: 'g1', symbolId: 'group', x: 200, y: 200, config: {label: 'G1', members: ['a']}},
  {id: 'a', symbolId: 'act', x: 120, y: 200, config: {label: 'A'}},
  {id: 'b', symbolId: 'hold', x: 320, y: 200, config: {label: 'B'}},
  {id: 'p', symbolId: 'plane', x: 700, y: 300, form: {dimension: 2, regions: {interior: {state: 'open'}}}, config: {label: 'P'}},
  {id: 'c', symbolId: 'act', x: 700, y: 300, canvasId: 'canvas:component:p', parentId: 'p', config: {label: 'C'}},
  {id: 'pt', symbolId: 'point', x: 540, y: 300, canvasId: 'canvas:component:p', parentId: 'p', placement: {kind: 'edge', hostId: 'p', side: 'left', t: .5}, form: {dimension: 0}}
], wires: [{id: 'ab', a: 'a', aSide: 'out', b: 'b', bSide: 'in'}], references: []});
const codesIn = errors => [...new Set(errors.map(e => (e.match(/\b(GROUP_[A-Z_]+):/) || [])[1]).filter(Boolean))];
out.baseErrors = Data.validateDocument(Data.makeDocument(base())).errors;

// At load: one crafted document per code.
const craft = {
  GROUP_MEMBER_UNKNOWN: d => { d.components[0].config.members = ['nope']; },
  GROUP_MEMBER_CANVAS: d => { d.components[0].config.members = ['c']; },
  GROUP_MEMBER_HOSTED: d => { d.components[0].config.members = ['pt']; },
  GROUP_MEMBER_GROUP: d => { d.components.push({id: 'g2', symbolId: 'group', x: 0, y: 0, config: {members: []}}); d.components[0].config.members = ['g2']; },
  GROUP_MEMBER_TWICE: d => { d.components.push({id: 'g2', symbolId: 'group', x: 0, y: 0, config: {members: ['a']}}); },
  GROUP_PORTS: d => { d.components[0].config.attachmentDefaults = 'standard'; },
  GROUP_HOST: d => { d.components.push({id: 'd', symbolId: 'act', x: 200, y: 200, canvasId: 'canvas:component:g1', config: {label: 'D'}}); }
};
out.load = {};
for (const [code, edit] of Object.entries(craft)) {
  const raw = base(); edit(raw);
  const errors = Data.validateDocument(Data.makeDocument(raw)).errors;
  out.load[code] = {codes: codesIn(errors), errors};
}

// On edit: one create or update per code, through applyOperation; the document is unchanged.
const edits = {
  GROUP_MEMBER_UNKNOWN: {op: 'create', resource: 'component', value: {id: 'g9', symbolId: 'group', config: {members: ['nope']}}},
  GROUP_MEMBER_CANVAS: {op: 'update', resource: 'component', resourceId: 'g1', patch: {config: {members: ['a', 'c']}}},
  GROUP_MEMBER_HOSTED: {op: 'update', resource: 'component', resourceId: 'g1', patch: {config: {members: ['pt']}}},
  GROUP_MEMBER_GROUP: {op: 'create', resource: 'component', value: {id: 'g9', symbolId: 'group', config: {members: ['g1']}}},
  GROUP_MEMBER_TWICE: {op: 'create', resource: 'component', value: {id: 'g9', symbolId: 'group', config: {members: ['b', 'a']}}},
  GROUP_PORTS: {op: 'update', resource: 'component', resourceId: 'g1', patch: {config: {attachmentDefaults: 'standard'}}},
  GROUP_HOST: {op: 'create', resource: 'component', value: {id: 'e', symbolId: 'act', canvasId: 'canvas:component:g1', config: {label: 'E'}}}
};
out.edit = {};
for (const [code, op] of Object.entries(edits)) {
  const d = Data.makeDocument(base()); Data.normalizeDocument(d);
  const before = JSON.stringify(d);
  const receipt = Data.applyOperation(d, op);
  out.edit[code] = {ok: receipt.ok, message: receipt.error?.message || '', unchanged: JSON.stringify(d) === before};
}
// Moving a member off the group's canvas is refused on the member too.
{
  const d = Data.makeDocument(base()); Data.normalizeDocument(d); const before = JSON.stringify(d);
  const receipt = Data.applyOperation(d, {op: 'update', resource: 'component', resourceId: 'a', patch: {canvasId: 'canvas:component:p'}});
  out.memberMove = {ok: receipt.ok, message: receipt.error?.message || '', unchanged: JSON.stringify(d) === before};
}
// An edit that keeps the rules is accepted.
{
  const d = Data.makeDocument(base());
  out.allowed = Data.applyOperation(d, {op: 'update', resource: 'component', resourceId: 'g1', patch: {config: {members: ['a', 'b']}}}).ok
    && Data.applyOperation(d, {op: 'create', resource: 'component', value: {id: 'g9', symbolId: 'group', config: {label: 'G9', members: []}}}).ok;
}
// Deleting a member removes it from members in the same operation.
{
  const d = Data.documentFromFilePayload(JSON.parse(fs.readFileSync(example, 'utf8')));
  const receipt = Data.applyOperation(d, {op: 'delete', resource: 'component', resourceId: 'case'});
  out.afterDelete = {ok: receipt.ok, members: d.components.find(c => c.id === 'records').config.members, wires: d.wires.map(w => w.id), errors: Data.validateDocument(d).errors};
}
process.stdout.write(JSON.stringify(out));
'''


def node_part() -> None:
    proc = subprocess.run(['node', 'scripts/validate_sov.mjs', str(EXAMPLE.relative_to(ROOT))], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    proc = subprocess.run(['node', '-e', NODE, str(ROOT), str(EXAMPLE)], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)

    assert out['validate']['ok'], out['validate']
    assert len(out['wires']) == 3, out['wires']
    for w in out['wires']:
        assert w['canvasId'] == 'canvas:global', w
        for end in w['ends']:
            assert end['symbolId'] not in (None, 'point', 'group') and end['dimension'] == 2 and end['canvasId'] == 'canvas:global', w
    members = out['members']
    assert members == {'records': ['case', 'recording', 'anchor'], 'surfaces': ['web-booth', 'delivery-broker']}, members
    # One Wire from each surface card to a record card, one between two record cards.
    pairs = [tuple(e['id'] for e in w['ends']) for w in out['wires']]
    for surface in members['surfaces']:
        assert any(a == surface and b in members['records'] for a, b in pairs), (surface, pairs)
    assert any(a in members['records'] and b in members['records'] for a, b in pairs), pairs

    # groupRect: the members' union, padded 24 on each side and 28 more on top.
    pos = out['positions']
    xs = [pos[m][0] for m in members['records']]
    ys = [pos[m][1] for m in members['records']]
    l, r = min(xs) - CARD['w'] / 2 - 24, max(xs) + CARD['w'] / 2 + 24
    t, b = min(ys) - CARD['h'] / 2 - 24 - 28, max(ys) + CARD['h'] / 2 + 24
    want = {'x': (l + r) / 2, 'y': (t + b) / 2, 'w': r - l, 'h': b - t, 'l': l, 'r': r, 't': t, 'b': b}
    assert all(abs(out['records'][k] - v) < 1e-9 for k, v in want.items()), (out['records'], want)
    assert out['empty'] == {'x': 50, 'y': 60, 'w': 320, 'h': 220, 'l': -110, 'r': 210, 't': -50, 'b': 170}, out['empty']

    assert out['baseErrors'] == [], out['baseErrors']
    for code in CODES:
        load = out['load'][code]
        assert load['codes'] == [code], (code, load['errors'])
        edit = out['edit'][code]
        assert not edit['ok'] and edit['message'].startswith(code + ':'), (code, edit)
        assert edit['unchanged'], (code, 'a refused edit changed the document')
    assert not out['memberMove']['ok'] and out['memberMove']['message'].startswith('GROUP_MEMBER_CANVAS:') and out['memberMove']['unchanged'], out['memberMove']
    assert out['allowed'], 'an edit that keeps the group rules was refused'

    after = out['afterDelete']
    assert after['ok'] and after['members'] == ['recording', 'anchor'], after
    assert 'booth-to-case' not in after['wires'] and 'case-to-anchor' not in after['wires'], after
    assert after['errors'] == [], after['errors']
    print(f"node part: {len(CODES)} codes refused at load and on edit; groupRect {out['records']}")


BROWSER_GEOMETRY = '''()=>{
  const box=el=>{const r=el.getBoundingClientRect();return {l:r.left,r:r.right,t:r.top,b:r.bottom}};
  const groups=[...document.querySelectorAll('.node.group')].map(g=>{
    const n=nodes.find(x=>x.id===g.dataset.id),region=g.querySelector(':scope > .group-region'),title=g.querySelector(':scope > .group-title');
    return {id:g.dataset.id,regions:g.querySelectorAll('.group-region').length,region:region?box(region):null,
      title:title?{text:title.textContent,box:box(title)}:null,bodies:g.querySelectorAll('.body').length,
      members:(n.config.members||[]).map(id=>{const b=document.querySelector(`#nodes > .node[data-id="${CSS.escape(id)}"] > .body`);return {id,box:b?box(b):null}}),
      pointer:region?getComputedStyle(region).pointerEvents:null};
  });
  const layer=document.getElementById('groupLayer'),before=(a,b)=>!!(a&&b&&(a.compareDocumentPosition(b)&Node.DOCUMENT_POSITION_FOLLOWING));
  return {groups,regionCount:document.querySelectorAll('.group-region').length,
    behind:before(layer,document.getElementById('wires'))&&before(layer,document.getElementById('nodes')),
    groupInNodes:document.querySelectorAll('#nodes .node.group, #wires .node.group').length,
    bodyInGroup:document.querySelectorAll('.node.group .body').length};
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
        opened = page.evaluate('(t)=>{const r=SovSchematicAPI.file.open(t,"groups.sov");fitDiagram();return r}', text)
        page.wait_for_timeout(200)
        assert not errors, errors
        assert opened is None or opened.get('ok', True) is not False, opened

        g = page.evaluate(BROWSER_GEOMETRY)
        assert g['regionCount'] == 2 and len(g['groups']) == 2, g
        assert g['behind'] and g['groupInNodes'] == 0, ('groups must be drawn before every node and wire', g)
        assert g['bodyInGroup'] == 0, g
        titles = sorted(x['title']['text'] for x in g['groups'] if x['title'])
        assert titles == ['Records', 'Surfaces'], titles
        for grp in g['groups']:
            R = grp['region']
            assert grp['regions'] == 1 and R and grp['bodies'] == 0 and grp['pointer'] == 'none', grp
            for m in grp['members']:
                B = m['box']
                assert B, (grp['id'], m)
                assert B['l'] >= R['l'] - .5 and B['r'] <= R['r'] + .5 and B['t'] >= R['t'] - .5 and B['b'] <= R['b'] + .5, (grp['id'], m, R)
            T = grp['title']['box']
            assert T['r'] - T['l'] > 1 and T['b'] - T['t'] > 1, grp['title']
            assert T['l'] > R['l'] and T['r'] < R['r'] and T['t'] >= R['t'] - .5, (grp['title'], R)
            # The title sits in the band above the members.
            top = min(m['box']['t'] for m in grp['members'])
            assert T['b'] <= top, (grp['title'], top)

        svg = page.evaluate('()=>SovSchematicAPI.render.svg({})')
        assert 'Records' in svg and 'Surfaces' in svg and 'group-region' in svg, 'render.svg lost the groups'

        metrics = page.evaluate('()=>SovSchematicAPI.layout.metrics()')
        named = [f for f in metrics['findings'] if f['kind'] in ('node-overlap', 'route-through-node') and any(i in ('records', 'surfaces') for i in (f.get('ids') or []))]
        assert not named, named
        assert not errors, errors
        browser.close()
    print(f"browser part: score {metrics['score']}, findings {[(f['kind'], f.get('ids'), f.get('detail')) for f in metrics['findings']]}")


if __name__ == '__main__':
    node_part()
    browser_part()
    print('PASS group region QA')
