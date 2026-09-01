import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_runtime import chromium_launch_kwargs

ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'index.html'

async def main():
  async with async_playwright() as p:
    browser=await p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page=await browser.new_page(viewport={'width':1200,'height':800})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    await page.set_content(HTML.read_text(),wait_until='load')
    await page.wait_for_timeout(150)
    await page.evaluate('newSchematic()')

    # Current dimensional points are built-in defaults, not a hard cardinality ceiling.
    surface=await page.evaluate("""() => window.SovSchematicAPI.create('component',{
      symbolId:'buffer',x:420,y:280,
      form:{dimension:2,body:{kind:'surface'}},
      config:{
        attachmentPoints:[
          {id:'bottom-a',compatId:'aux-a',side:'bottom',t:.25,defaultFlow:'duplex'},
          {id:'bottom-b',compatId:'aux-b',side:'bottom',t:.75,defaultFlow:'out'}
        ],
        ports:{'aux-a':{label:'AUX A',face:'external'},'aux-b':{label:'AUX B',face:'external'}}
      }
    }).result""")
    sid=surface['id']
    point_ids=await page.evaluate('(id)=>Object.keys(nodes.find(n=>n.id===id).parts.points)',sid)
    assert point_ids==['left','right','top','bottom-a','bottom-b'],point_ids
    assert await page.locator(f'.node[data-id="{sid}"] .attachment-point').count()==5

    # Parametric positions are derived from the 2D boundary, not free world coordinates.
    pos=await page.evaluate("""(id)=>{
      const n=nodes.find(n=>n.id===id);
      return {a:componentPortLocalPosition(n,'bottom-a'),b:componentPortLocalPosition(n,'bottom-b'),size:componentSize(n)};
    }""",sid)
    assert pos['a']['y']>0 and pos['b']['y']>0,pos
    assert pos['a']['x']<0<pos['b']['x'],pos
    expected_delta=pos['size']['w']*.5
    assert abs((pos['b']['x']-pos['a']['x'])-expected_delta)<1.5,pos

    # Shared data core/API can use a data-declared point without a renderer-only normalization step.
    target=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'hold',x:760,y:500}).result")
    wire_receipt=await page.evaluate("""(ids)=>window.SovSchematicAPI.create('wire',{
      a:ids[0],aAttachment:{pointId:'bottom-b'},b:ids[1],bAttachment:{pointId:'left'}
    })""",[sid,target['id']])
    assert wire_receipt['ok'],wire_receipt
    wid=wire_receipt['result']['id']
    ref=await page.evaluate('(id)=>{const w=wires.find(x=>x.id===id);return {a:w.aAttachment,aSide:w.aSide}}',wid)
    assert ref['a']['pointId']=='bottom-b' and ref['aSide']=='aux-b',ref

    # Hosting the same richer component on a 1D carrier projects connectivity down to start/end.
    left=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:150,y:650}).result")
    right=await page.evaluate("window.SovSchematicAPI.create('component',{symbolId:'act',x:1000,y:650}).result")
    carrier=await page.evaluate('(ids)=>window.SovSchematicAPI.create("wire",{a:ids[0],aSide:"out",b:ids[1],bSide:"in"}).result',[left['id'],right['id']])
    hosted=await page.evaluate("""(args)=>{
      const n=SovSchematicData.makeComponent(diagram,{
        symbolId:'gate',x:560,y:650,
        form:{dimension:2,body:{kind:'surface'}},
        canvasId:`canvas:wire:${args.wid}`,
        placement:{kind:'wire',wireId:args.wid,t:.5},
        config:{attachmentPoints:[{id:'extra',side:'bottom',t:.5}]}
      });
      nodes.push(n);syncAllNodeBoundaryContext();render();return n.id;
    }""",{'wid':carrier['id']})
    hosted_points=await page.evaluate('(id)=>Object.keys(nodes.find(n=>n.id===id).parts.points)',hosted)
    assert hosted_points==['start','end'],hosted_points

    assert not errors,errors
    await browser.close()
    print('PASS Beta.24 configurable attachment-default seam QA')

asyncio.run(main())
