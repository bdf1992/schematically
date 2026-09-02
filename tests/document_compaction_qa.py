"""Saved documents carry authored truth only.

Runtime projections (local canvas descriptors, boundary/parts, port-level mirrors
of the active connection, realized colors, presentation layout hints) are rebuilt
on load and never written. Default contracts are dimension-specific. Old files that
still carry the full projections load identically.
"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
errors=[]
DERIVED_COMPONENT=('canvas','boundary','parts','type','incomplete')
DERIVED_PORT=('channelCount','activeChannel','channel','channels','colorSlot','color','flow','access','side')
DERIVED_PRESENTATION=('svgRef','internalLayout','portTopology','boundaryColorMode','boundaryShape')
with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(HTML,wait_until='load');page.wait_for_timeout(120)
    state=page.evaluate('''()=>{
      SovSchematicAPI.create('component',{id:'a',symbolId:'buffer',x:220,y:260,config:{label:'A'}});
      SovSchematicAPI.create('component',{id:'pl',symbolId:'plane',x:700,y:300});
      SovSchematicAPI.create('component',{id:'pt',symbolId:'point',x:0,y:0});
      {const n=nodes.find(n=>n.id==='pt'),h=nodes.find(n=>n.id==='pl'),s=componentSize(h);applyComponentHost(n,componentHostCandidateAtPoint(n,h.x+s.w/2-1,h.y));render()}
      const w=SovSchematicAPI.create('wire',{id:'k1',a:'a',aSide:'out',b:'pt',bSide:'self'});
      createCheckpoint('cp');
      const doc=SovSchematicAPI.document.get();
      const text=JSON.stringify(doc);
      const full=JSON.stringify(SovSchematicData.makeDocument(SovSchematicData.clone(diagram))).length;
      const before=semanticFingerprint();
      SovSchematicAPI.document.replace(JSON.parse(text));
      const after=semanticFingerprint();
      const pt=nodes.find(n=>n.id==='pt');
      return {ok:w.ok,doc,size:text.length,full,before,after,reloadedPlacement:pt.placement,reloadedPoints:Object.keys(pt.parts.points),runtimePorts:Object.keys(nodes.find(n=>n.id==='a').parts.ports),wire:{aSide:wires[0].aSide,bSide:wires[0].bSide,a:wires[0].aAttachment.pointId,b:wires[0].bAttachment.pointId}};
    }''')
    assert state['ok'],state
    doc=state['doc'];comp={c['id']:c for c in doc['components']}
    for c in doc['components']:
        for key in DERIVED_COMPONENT:assert key not in c,(c['id'],key)
        for port in c['config'].get('ports',{}).values():
            for key in DERIVED_PORT:assert key not in port,(c['id'],key,port)
        for key in DERIVED_PRESENTATION:assert key not in c['config'].get('presentation',{}),(c['id'],key)
        assert 'color' not in c['config'],c['id']
    for w in doc['wires']:
        assert 'canvas' not in w and 'duplex' not in w and 'attachments' not in w,w
        assert w['aSide'] and w['bSide'] and w['aAttachment']['pointId'],w  # schema-required endpoint names stay
    assert 'canvas' not in doc
    # Default contracts are minimal and dimension-specific.
    assert list(comp['a']['config']['ports'])==['in','out','control'],comp['a']['config']['ports']
    assert comp['pl']['config']['attachmentDefaults']=='none' and comp['pl']['config'].get('ports',{})=={},comp['pl']['config']
    assert list(comp['pt']['config']['ports'])==['out'],comp['pt']['config']['ports']
    assert comp['pt']['placement']['kind']=='edge' and comp['pt']['placement']['hostId']=='pl',comp['pt']['placement']
    assert 'placement' not in comp['a'],comp['a']  # free placement is implied by x/y
    # Checkpoints embedded in the file are compact too.
    cp=doc['meta']['checkpoints'][0]['document']
    assert all('parts' not in c and 'canvas' not in c for c in cp['components']),cp
    # Compact is materially smaller than the projected runtime record, and round-trips losslessly.
    assert state['size']<state['full']*.6,(state['size'],state['full'])
    assert state['before']==state['after'],'compact round trip changed semantics'
    assert state['reloadedPlacement']['kind']=='edge' and state['reloadedPlacement']['hostId']=='pl',state['reloadedPlacement']
    assert state['reloadedPoints']==['self'] and state['runtimePorts']==['in','out','control'],state
    assert state['wire']=={'aSide':'out','bSide':'out','a':'right','b':'self'},state['wire']
    # Old files with full projections still load and validate.
    legacy=json.loads((ROOT/'examples/03-contained-stage.sov').read_text(encoding='utf-8'))
    ok=page.evaluate('(d)=>{SovSchematicAPI.document.replace(d);return {n:nodes.length,w:wires.length,valid:SovSchematicData.validateDocument(SovSchematicAPI.document.get()).ok}}',legacy)
    assert ok['n']==len(legacy['components']) and ok['w']==len(legacy['wires']) and ok['valid'],ok
    assert not errors,errors
    browser.close()
print('PASS document compaction QA')
