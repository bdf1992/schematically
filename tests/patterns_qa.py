"""Patterns: a record of its own, and one thing while its parts are inside it.

A Pattern behaves the way a Component behaves. One click on any part selects the
Pattern; one drag moves it; one Delete takes it; its kind, name and color live in one
bar; it is written to the file and read back. What it is made of stays ordinary forms,
so OPEN steps inside and the parts answer for themselves, and RELEASE drops the record
and leaves the forms exactly where they are.

PATH is the 1D form and behaves like every other rung. A loose carrier, which is what
PATH used to drop, is an arrangement rather than a form and lives in the Pattern list.
"""
import asyncio
import sys
from pathlib import Path

from browser_runtime import chromium_launch_kwargs
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'

# Clearing outside history would leave the undo baseline stale, so the reset commits
# itself as a step before a Pattern is dropped on top of it.
RESET = """()=>{nodes.splice(0);wires.splice(0);patternRecords.splice(0);openPatternIds.clear();
  routeCache.clear();arrowPoseCache.clear();clearComponentSelectionSet();selected=null;
  hideSelectionBar();render();commitHistoryCapture('Clear')}"""


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = await browser.new_page(viewport={'width': 1500, 'height': 950})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.set_content(HTML.read_text(encoding='utf-8'), wait_until='load')
        await page.wait_for_timeout(220)

        # Two sections, because the vocabulary has two ladders.
        sections = await page.evaluate(
            "[...document.querySelectorAll('#palette .section h2')].map(h=>h.textContent)")
        assert sections == ['Form', 'Pattern'], sections

        # Every Pattern kind has a card, a one-line "made of", and a glyph that resolves.
        cards = await page.evaluate(
            "[...document.querySelectorAll('.pattern-card')].map(b=>({"
            "id:b.dataset.patternId,name:b.querySelector('b').textContent,"
            "sense:b.querySelector('small').textContent,"
            "glyph:b.querySelector('use')?.getAttribute('href')}))")
        declared = await page.evaluate(
            "PATTERN_KINDS.map(k=>({id:k.id,name:k.name,sense:k.sense,meaning:k.meaning}))")
        assert [c['id'] for c in cards] == [k['id'] for k in declared], (cards, declared)
        for card, kind in zip(cards, declared):
            assert card['name'] == kind['name'] and card['sense'] == kind['sense'], card
            assert card['glyph'] == f'#pat-{kind["id"]}', card
            assert await page.evaluate('(id)=>!!document.getElementById(id)', f'pat-{kind["id"]}')
            assert card['sense'], f'{kind["id"]} does not say what it is made of'
            assert kind['meaning'], f'{kind["id"]} has no meaning to show in the inspector'

        # --- Dropping one makes a record -----------------------------------
        expected = {
            'pair':    {'nodes': 2, 'wires': 1, 'kinds': ['point'] * 2, 'hosted': 0},
            'chain':   {'nodes': 3, 'wires': 2, 'kinds': ['point'] * 3, 'hosted': 0},
            'hub':     {'nodes': 4, 'wires': 3, 'kinds': ['point'] * 4, 'hosted': 0},
            'rail':    {'nodes': 4, 'wires': 0, 'kinds': ['path'] + ['point'] * 3, 'hosted': 3},
            'carrier': {'nodes': 0, 'wires': 1, 'kinds': [], 'hosted': 0},
            'block':   {'nodes': 1, 'wires': 0, 'kinds': ['plane'], 'hosted': 0},
            'nest':    {'nodes': 2, 'wires': 0, 'kinds': ['plane'] * 2, 'hosted': 0},
        }
        for kind_id, want in expected.items():
            await page.evaluate(RESET)
            got = await page.evaluate("""(id)=>{
                addPattern(id,600,400);
                const record=patternRecords[0];
                return {records:patternRecords.length,kind:record&&record.kind,
                        nodes:nodes.length,wires:wires.length,kinds:nodes.map(n=>n.symbolId),
                        hosted:nodes.filter(n=>n.placement&&n.placement.kind!=='surface').length,
                        members:record?patternMemberCount(record.id):0,
                        allBelong:[...nodes,...wires].every(m=>m.patternId===(record&&record.id)),
                        selected:selected,barShown:!patternBarFields.hidden,
                        hulls:document.querySelectorAll('.pattern-hull').length};
            }""", kind_id)
            assert got['records'] == 1, (kind_id, got)
            assert got['kind'] == kind_id, (kind_id, got)
            assert got['nodes'] == want['nodes'] and got['wires'] == want['wires'], (kind_id, got, want)
            assert got['kinds'] == want['kinds'], (kind_id, got, want)
            assert got['hosted'] == want['hosted'], (kind_id, got, want)
            assert got['members'] == want['nodes'] + want['wires'], (kind_id, got, want)
            assert got['allBelong'], f'{kind_id}: a part was left outside its own Pattern'
            # The Pattern is what was added, so the Pattern is what is selected.
            assert got['selected'] == 'pattern:q1', (kind_id, got)
            assert got['barShown'], f'{kind_id}: the Pattern bar did not open'
            assert got['hulls'] == 1, (kind_id, got)

        # --- One click selects the Pattern, not the part -------------------
        await page.evaluate(RESET)
        made = await page.evaluate(
            "()=>{addPattern('chain',600,400);return {record:patternRecords[0].id,ids:nodes.map(n=>n.id)}}")
        await page.evaluate('()=>selectNode(null)')
        picked = await page.evaluate(
            "(id)=>{selectNode(id);return {selected,inSet:[...selectedComponentIds].length,"
            "detail:!patternDetail.hidden,kind:selectedSurfaceKind(),name:qName.textContent}}",
            made['ids'][0])
        assert picked['selected'] == f'pattern:{made["record"]}', picked
        assert picked['inSet'] == 3, picked
        assert picked['detail'] and picked['kind'] == 'pattern', picked
        assert picked['name'] == 'CHAIN', picked

        # --- One drag moves the whole thing --------------------------------
        before = await page.evaluate('nodes.map(n=>({x:n.x,y:n.y}))')
        grip = await page.locator(f'.node[data-id="{made["ids"][1]}"] .point-grip').bounding_box()
        cx, cy = grip['x'] + grip['width'] / 2, grip['y'] + grip['height'] / 2
        await page.mouse.move(cx, cy)
        await page.mouse.down()
        for i in range(1, 9):
            await page.mouse.move(cx + 120 * i / 8, cy + 70 * i / 8)
            await page.wait_for_timeout(18)
        await page.mouse.up()
        await page.wait_for_timeout(260)
        after = await page.evaluate('nodes.map(n=>({x:n.x,y:n.y}))')
        deltas = {(round(a['x'] - b['x']), round(a['y'] - b['y'])) for a, b in zip(after, before)}
        assert len(deltas) == 1, f'the parts did not move together: {deltas}'
        assert deltas != {(0, 0)}, 'dragging a part did not move the Pattern'

        # --- Name and color live on the record -----------------------------
        named = await page.evaluate("""(id)=>{
            renamePattern(id,'Ingest');
            patternRecord(id).colorSlot=8;
            selectPattern(id);
            return {label:patternRecord(id).label,slot:patternRecord(id).colorSlot,
                    field:barPatternLabel.value,kindField:barPatternKind.value,
                    kindLocked:barPatternKind.disabled,
                    hullLabel:document.querySelector('.pattern-hull-label').textContent};
        }""", made['record'])
        assert named['label'] == 'Ingest' and named['field'] == 'Ingest', named
        assert named['slot'] == 8, named
        assert named['kindField'] == 'chain', named
        # The kind is what it was built from; changing it would have to rebuild the parts.
        assert named['kindLocked'], named
        assert named['hullLabel'].startswith('INGEST'), named

        # --- OPEN lets the parts answer for themselves ---------------------
        opened = await page.evaluate("""(ids)=>{
            togglePatternOpen(ids.record);
            const first=selected;
            selectNode(ids.parts[2]);
            return {open:patternIsOpen(ids.record),first,selected,kind:selectedSurfaceKind()};
        }""", {'record': made['record'], 'parts': made['ids']})
        assert opened['open'] is True, opened
        assert opened['selected'] == made['ids'][2], opened
        assert opened['kind'] == 'component', opened
        closed = await page.evaluate(
            "(id)=>{togglePatternOpen(id);return {open:patternIsOpen(id),selected}}", made['record'])
        assert closed['open'] is False and closed['selected'] == f'pattern:{made["record"]}', closed

        # --- The file carries it -------------------------------------------
        document = await page.evaluate('window.SovSchematicAPI.document.get()')
        assert [p['id'] for p in document['patterns']] == [made['record']], document['patterns']
        assert document['patterns'][0]['kind'] == 'chain', document['patterns']
        assert document['patterns'][0]['label'] == 'Ingest', document['patterns']
        assert all(c['patternId'] == made['record'] for c in document['components']), document['components']
        assert all(w['patternId'] == made['record'] for w in document['wires']), document['wires']
        reloaded = await page.evaluate("""(doc)=>{
            window.SovSchematicAPI.document.replace(doc);
            const record=patternRecords[0];
            return {patterns:patternRecords.length,label:record.label,
                    members:patternMemberCount(record.id)};
        }""", document)
        assert reloaded == {'patterns': 1, 'label': 'Ingest', 'members': 5}, reloaded

        # A member naming a Pattern nothing declares is loose, and a Pattern nothing
        # names is nothing. Loading settles both instead of carrying half of one.
        dangling = await page.evaluate("""(doc)=>{
            const copy=JSON.parse(JSON.stringify(doc));
            copy.patterns=[{id:'q9',kind:'pair',label:'Empty',colorSlot:0}];
            const normalized=SovSchematicData.normalizeDocument(copy);
            return {patterns:normalized.patterns,refs:normalized.components.map(c=>c.patternId)};
        }""", document)
        assert dangling['patterns'] == [], dangling
        assert all(ref is None for ref in dangling['refs']), dangling

        # --- Copy makes a second Pattern, not a bigger first one -----------
        await page.evaluate(RESET)
        copied = await page.evaluate("""()=>{
            addPattern('pair',500,400);
            const source=patternRecords[0].id;
            copySelection();pasteClipboard({offset:60});
            return {patterns:patternRecords.length,kinds:patternRecords.map(p=>p.kind),
                    inSource:patternMemberCount(source),
                    loose:nodes.filter(n=>!n.patternId).length};
        }""")
        assert copied['patterns'] == 2, copied
        assert copied['kinds'] == ['pair', 'pair'], copied
        assert copied['inSource'] == 3, f'pasting enlarged the original Pattern: {copied}'
        assert copied['loose'] == 0, f'pasted parts landed outside any Pattern: {copied}'

        # --- RELEASE keeps the forms; DELETE takes them --------------------
        await page.evaluate(RESET)
        released = await page.evaluate("""()=>{
            addPattern('chain',600,400);
            const id=patternRecords[0].id;
            const freed=releasePattern(id);
            return {patterns:patternRecords.length,nodes:nodes.length,wires:wires.length,
                    loose:[...nodes,...wires].every(m=>!m.patternId),freed:freed.length,
                    selectedSet:[...selectedComponentIds].length};
        }""")
        assert released == {'patterns': 0, 'nodes': 3, 'wires': 2, 'loose': True,
                            'freed': 3, 'selectedSet': 3}, released

        await page.evaluate(RESET)
        await page.evaluate("()=>addPattern('hub',600,400)")
        deleted = await page.evaluate(
            "()=>{deleteSelected();return {nodes:nodes.length,wires:wires.length,patterns:patternRecords.length}}")
        assert deleted == {'nodes': 0, 'wires': 0, 'patterns': 0}, deleted

        # --- One drop is one undoable step ---------------------------------
        await page.evaluate(RESET)
        await page.evaluate("()=>addPattern('rail',600,400)")
        await page.wait_for_timeout(160)
        assert await page.evaluate('nodes.length') == 4
        await page.evaluate('window.SovSchematicAPI.history.undo()')
        await page.wait_for_timeout(220)
        assert await page.evaluate('nodes.length') == 0, 'undo did not take the whole arrangement'
        assert await page.evaluate('patternRecords.length') == 0, 'undo left the Pattern record behind'

        # --- What each arrangement actually is -----------------------------
        await page.evaluate(RESET)
        await page.evaluate("()=>addPattern('rail',600,400)")
        document = await page.evaluate('window.SovSchematicAPI.document.get()')
        rail = next(c for c in document['components'] if c['symbolId'] == 'path')
        riders = [c for c in document['components'] if c['symbolId'] == 'point']
        assert len(riders) == 3, riders
        for rider in riders:
            assert rider['placement']['kind'] == 'path', rider
            assert rider['placement']['hostId'] == rail['id'], rider
        assert sorted(round(r['placement']['t'], 2) for r in riders) == [0.2, 0.5, 0.8], riders

        await page.evaluate(RESET)
        block = await page.evaluate("()=>{addPattern('block',600,400);return nodes[0].id}")
        assert await page.evaluate(
            '(id)=>componentAttachmentPointIds(nodes.find(n=>n.id===id))', block) == \
            ['left', 'right', 'top']
        assert await page.evaluate('(id)=>nodes.find(n=>n.id===id).symbolId', block) == 'plane'

        await page.evaluate(RESET)
        nest = await page.evaluate("()=>{addPattern('nest',600,400);return nodes.map(n=>n.id)}")
        assert await page.evaluate('(id)=>nodes.find(n=>n.id===id).canvasId', nest[1]) == \
            f'canvas:component:{nest[0]}'

        # --- The resource surface knows about them -------------------------
        listed = await page.evaluate("window.SovSchematicAPI.list('pattern')")
        assert listed['ok'] and len(listed['result']) == 1, listed
        kinds = await page.evaluate('window.SovSchematicAPI.patterns.kinds()')
        assert [k['id'] for k in kinds] == [k['id'] for k in declared], kinds
        members = await page.evaluate(
            "(id)=>window.SovSchematicAPI.patterns.members(id)", listed['result'][0]['id'])
        assert sorted(members['components']) == sorted(nest), members

        # --- PATH is a form and behaves like one ---------------------------
        await page.evaluate(RESET)
        path = await page.evaluate("()=>addNode('path',600,400,null,{select:false}).id")
        assert await page.evaluate('(id)=>nodes.some(n=>n.id===id)', path), \
            'the palette PATH did not drop a Component'
        assert await page.evaluate('wires.length') == 0, 'the palette PATH dropped a Wire'
        assert await page.evaluate('(id)=>!nodes.find(n=>n.id===id).patternId', path), \
            'a form dropped on its own belongs to no Pattern'

        # A 1D form is drawn thin, so it carries a band that makes it grabbable.
        band = f'.node[data-id="{path}"] .dimensional-path-hit'
        assert await page.locator(band).count() == 1
        box = await page.locator(band).bounding_box()
        assert box['height'] >= 16, box

        # Clicking the body selects it, and dragging the body moves it. The band is
        # re-measured because selecting reflows the bar above the canvas.
        await page.mouse.click(box['x'] + box['width'] * 0.35, box['y'] + box['height'] / 2)
        await page.wait_for_timeout(420)
        assert await page.evaluate('selected') == path, await page.evaluate('selected')
        box = await page.locator(band).bounding_box()
        cx, cy = box['x'] + box['width'] * 0.35, box['y'] + box['height'] / 2
        before = await page.evaluate('(id)=>{const n=nodes.find(n=>n.id===id);return {x:n.x,y:n.y}}', path)
        await page.mouse.move(cx, cy)
        await page.mouse.down()
        for i in range(1, 10):
            await page.mouse.move(cx + 140 * i / 9, cy + 90 * i / 9)
            await page.wait_for_timeout(18)
        await page.mouse.up()
        await page.wait_for_timeout(220)
        after = await page.evaluate('(id)=>{const n=nodes.find(n=>n.id===id);return {x:n.x,y:n.y}}', path)
        assert after != before, f'a Path did not move when dragged by its body: {before}'

        assert not errors, errors
        await browser.close()
    print('patterns_qa ok')


if __name__ == '__main__':
    sys.exit(asyncio.run(main()) or 0)
