"""A carrier whose two ends are free draws as one straight segment between them.

Orthogonal routing exists to meet a bound attachment point on its normal, and to leave a
boundary without tunnelling through it. Two free ends have neither, so the carrier is the
segment between its own two points - straight even when the ends are not aligned - instead
of an invented elbow. Binding an end brings routing back, because then there is a normal to
meet; a pinned or guided route still wins over the open router either way.

Adapted from the reference at origin/sandbox/c2c40215 (commit 3d48eb9), written against an
older dev whose free check read the source/target node, not carrierEndpoint's own kind.
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'

ROUTE_CALL = (
    "(id)=>{const w=wires.find(x=>x.id===id),i=wires.indexOf(w);"
    "return stableRouteForWire(i,w,carrierEndpointPos(w,'a'),carrierEndpointPos(w,'b'),[])}"
)


def is_orthogonal_only(points):
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        if a['x'] != b['x'] and a['y'] != b['y']:
            return False
    return True


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = await browser.new_page(viewport={'width': 1100, 'height': 750})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.set_content(HTML.read_text(encoding='utf-8'), wait_until='load')
        await page.wait_for_timeout(200)

        # A carrier with free ends at (100,100) and (300,220) draws one segment between them.
        wid = await page.evaluate(
            "()=>window.SovSchematicAPI.create('wire',{aAttachment:{kind:'free',x:100,y:100},"
            "bAttachment:{kind:'free',x:300,y:220}}).result.id"
        )
        ends = await page.evaluate(
            "(id)=>{const w=wires.find(x=>x.id===id);"
            "return {a:carrierEndpoint(w,'a').kind,b:carrierEndpoint(w,'b').kind}}", wid
        )
        assert ends == {'a': 'free', 'b': 'free'}, ends

        flat = await page.evaluate(ROUTE_CALL, wid)
        assert flat == [{'x': 100, 'y': 100}, {'x': 300, 'y': 220}], \
            f'two free ends with unaligned points still draw one straight segment: {flat}'

        # Clear the route cache and move the free end, as the real end-drag gesture does: it
        # invalidates the cache before re-rendering. It stays one segment, not an elbow.
        moved = await page.evaluate(
            "(id)=>{const w=wires.find(x=>x.id===id);routeCache.clear();"
            "freeCarrierEnd(w,'b',{x:320,y:260});render();"
            "const i=wires.indexOf(w);"
            "return stableRouteForWire(i,w,carrierEndpointPos(w,'a'),carrierEndpointPos(w,'b'),[])}",
            wid,
        )
        assert moved == [{'x': 100, 'y': 100}, {'x': 320, 'y': 260}], moved

        # Bind end b to an act card's in port: now there is a normal to meet, and the router
        # returns - horizontal and vertical steps only, never a diagonal.
        target = await page.evaluate(
            "()=>window.SovSchematicAPI.create('component',{symbolId:'act',x:560,y:380}).result.id"
        )
        bound = await page.evaluate(
            "([id,tid])=>{const w=wires.find(x=>x.id===id);bindCarrierEnd(w,'b',tid,'in');"
            "routeCache.clear();render();"
            "const i=wires.indexOf(w);"
            "return stableRouteForWire(i,w,carrierEndpointPos(w,'a'),carrierEndpointPos(w,'b'),[])}",
            [wid, target],
        )
        assert len(bound) > 2, f'a bound end should be approached on its normal: {bound}'
        assert is_orthogonal_only(bound), f'a bound end routes orthogonally, never a diagonal: {bound}'

        # Free that end again: the carrier returns to one straight segment.
        freed = await page.evaluate(
            "(id)=>{const w=wires.find(x=>x.id===id);"
            "freeCarrierEnd(w,'b',{x:320,y:260});routeCache.clear();render();"
            "const i=wires.indexOf(w);"
            "return stableRouteForWire(i,w,carrierEndpointPos(w,'a'),carrierEndpointPos(w,'b'),[])}",
            wid,
        )
        assert freed == [{'x': 100, 'y': 100}, {'x': 320, 'y': 260}], freed

        # A free/free carrier with a pinned route keeps its pinned points.
        pid = await page.evaluate(
            "()=>window.SovSchematicAPI.create('wire',{aAttachment:{kind:'free',x:60,y:60},"
            "bAttachment:{kind:'free',x:400,y:300}}).result.id"
        )
        pin = await page.evaluate(
            "(id)=>SovSchematicAPI.layout.route(id,{mode:'pinned',points:[{x:150,y:260}]})",
            pid,
        )
        assert pin['ok'], pin
        pinned = await page.evaluate(ROUTE_CALL, pid)
        assert any(p['x'] == 150 and p['y'] == 260 for p in pinned), \
            f'a pinned route is kept over the free/free straight segment: {pinned}'

        assert not errors, errors
        await browser.close()
    print('FREE SEGMENT ROUTE PASS')


asyncio.run(main())
