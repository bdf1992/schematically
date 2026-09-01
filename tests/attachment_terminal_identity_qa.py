from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
errors=[]

with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page(viewport={'width':1100,'height':700})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(HTML,wait_until='load');page.wait_for_timeout(120)
    state=page.evaluate('''()=>{
      nodes.splice(0);wires.splice(0);routeCache.clear();arrowPoseCache.clear();
      const a=SovSchematicData.makeComponent(diagram,{id:'a',symbolId:'buffer',x:250,y:300});
      const b=SovSchematicData.makeComponent(diagram,{id:'b',symbolId:'act',x:700,y:300});
      nodes.push(a,b);ensureComponentStructure(a);ensureComponentStructure(b);
      const first=addConnection('a','right','b','left');
      const stored={aSide:wires[0].aSide,bSide:wires[0].bSide,aPoint:wires[0].aAttachment?.pointId,bPoint:wires[0].bAttachment?.pointId};
      const duplicate=addConnection('a','right','b','left');
      const afterDuplicate=wires.length;
      // Use canonical reverse endpoints. This must upgrade the same carrier to duplex,
      // not add a second reverse Wire merely because storage uses in/out aliases.
      const reverse=addConnection('b','left','a','right');
      return {first,duplicate,reverse,afterDuplicate,count:wires.length,stored,direction:connectionConfig(wires[0]).direction,duplex:wires[0].duplex===true};
    }''')
    assert state['first'] and state['duplicate'] and state['reverse'],state
    assert state['stored']=={'aSide':'out','bSide':'in','aPoint':'right','bPoint':'left'},state
    assert state['afterDuplicate']==1,state
    assert state['count']==1,state
    assert state['direction']=='duplex' and state['duplex'],state
    # Endpoint channel tags use physical attachment geometry even though 0.1 storage
    # retains legacy in/out aliases.
    page.evaluate('render()');page.wait_for_timeout(50)
    marker_geometry=page.evaluate('''()=>{
      const w=wires[0],a=nodes.find(n=>n.id===w.a),b=nodes.find(n=>n.id===w.b),A=portPos(a,w.aSide),B=portPos(b,w.bSide);
      const tags=[...document.querySelectorAll('.wire-group[data-wire-id="'+w.id+'"] .endpoint-channel-tag')];
      return {A,B,ax:Number(tags[0].getAttribute('x')),bx:Number(tags[1].getAttribute('x'))};
    }''')
    assert marker_geometry['ax']>marker_geometry['A']['x'],marker_geometry
    assert marker_geometry['bx']<marker_geometry['B']['x'],marker_geometry
    assert not errors,errors
    browser.close()
print('PASS canonical/legacy terminal identity QA')
