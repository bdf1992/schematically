"""A carrier with two free ends is the segment between its two points.

Orthogonal routing exists to meet bound attachment points on their normals. With both ends
free there is no normal to meet and no boundary to leave, so a bend is invented rather than
required — and moving an end then looked like it reset the line's direction.
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = await browser.new_page(viewport={'width': 1100, 'height': 750})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.set_content(HTML.read_text(), wait_until='load')
        await page.wait_for_timeout(200)
        await page.evaluate('newSchematic()')

        # The palette Path is a carrier with two free ends.
        wid = await page.evaluate("()=>{addNode('path',400,320,null,{});render();return wires[0].id}")
        ends = await page.evaluate(
            '(id)=>{const w=wires.find(x=>x.id===id);'
            'return {a:w.aAttachment.kind,b:w.bAttachment.kind}}', wid)
        assert ends == {'a': 'free', 'b': 'free'}, ends

        route = ('(id)=>{const w=wires.find(x=>x.id===id),i=wires.indexOf(w);'
                 "return stableRouteForWire(i,w,carrierEndpointPos(w,'a'),carrierEndpointPos(w,'b'),[])}")

        flat = await page.evaluate(route, wid)
        assert len(flat) == 2, f'a free carrier starts as one segment: {flat}'

        # Move one end well off-axis. It must stay one segment, not gain an elbow.
        moved = await page.evaluate(
            '(id)=>{const w=wires.find(x=>x.id===id);'
            "routeCache.clear();"  # the real end-drag gesture invalidates this before re-rendering
            "SovSchematicData.freeWireEndpoint(diagram,w,'b',520,180);render();"
            "const i=wires.indexOf(w);"
            "return stableRouteForWire(i,w,carrierEndpointPos(w,'a'),carrierEndpointPos(w,'b'),[])}", wid)
        assert len(moved) == 2, f'two free points make a straight line, not a bend: {moved}'
        assert moved[1]['x'] == 520 and moved[1]['y'] == 180, moved

        # Move the other end too; still one segment, and it ends exactly where it was put.
        both = await page.evaluate(
            '(id)=>{const w=wires.find(x=>x.id===id);'
            "routeCache.clear();"  # the real end-drag gesture invalidates this before re-rendering
            "SovSchematicData.freeWireEndpoint(diagram,w,'a',260,470);render();"
            "const i=wires.indexOf(w);"
            "return stableRouteForWire(i,w,carrierEndpointPos(w,'a'),carrierEndpointPos(w,'b'),[])}", wid)
        assert len(both) == 2, both
        assert (both[0]['x'], both[0]['y']) == (260, 470), both
        assert (both[1]['x'], both[1]['y']) == (520, 180), both

        # Binding one end brings routing back: a bound point must be met on its normal, so the
        # carrier is entitled to bend again. This is the line between the two behaviours.
        bound = await page.evaluate('''(id)=>{
          const target=window.SovSchematicAPI.create('component',{symbolId:'act',x:760,y:520}).result;
          const w=wires.find(x=>x.id===id);
          SovSchematicData.bindWireEndpoint(diagram,w,'b',target.id,'left');
          routeCache.clear();render();
          const i=wires.indexOf(w);
          const pts=stableRouteForWire(i,w,carrierEndpointPos(w,'a'),carrierEndpointPos(w,'b'),[]);
          return {count:pts.length,aKind:w.aAttachment.kind,bBound:!!w.b}}''', wid)
        assert bound['aKind'] == 'free' and bound['bBound'], bound
        assert bound['count'] > 2, f'a bound end should be approached on its normal: {bound}'

        assert not errors, errors
        await browser.close()
    print('FREE SEGMENT ROUTE PASS')


asyncio.run(main())
