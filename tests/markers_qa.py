from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
EXAMPLE=(ROOT/'examples/08-gated-service.sov').read_text(encoding='utf-8')
errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page()
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.set_content(HTML,wait_until='load');page.wait_for_timeout(150)
    result=page.evaluate('''(exampleText)=>{
      const example=SovSchematicData.makeDocument(JSON.parse(exampleText));
      const cleanMarkers=SovSchematicData.markersFor(example);

      nodes.splice(0);wires.splice(0);
      const parent=SovSchematicData.makeComponent(diagram,{id:'parent',symbolId:'buffer',x:500,y:320,form:{dimension:2,regions:{interior:{state:'open'}}}});
      const child=SovSchematicData.makeComponent(diagram,{id:'child',symbolId:'act',x:500,y:320,canvasId:'canvas:component:parent'});
      nodes.push(parent,child);componentConfig(parent);componentConfig(child);
      // Parent IN port exposed internally, so a legal child->parent wire can be built...
      componentConfig(parent).ports.in.face='internal';
      const legal=SovSchematicData.makeWire(diagram,{id:'k-boundary',a:'child',aSide:'out',b:'parent',bSide:'in'});
      // ...then rebound onto the OUT port (outside-facing only) and inserted into the document
      // object directly, bypassing applyOperation/makeWire's own reachability refusal.
      const badWire=SovSchematicData.clone(legal);
      badWire.bSide='out';
      badWire.bAttachment={kind:'attachment-ref',componentId:'parent',pointId:'out'};
      wires.push(badWire);

      const boundaryMarkers=SovSchematicData.markersFor(diagram);
      render();
      const badgeCount=document.querySelectorAll('.marker-badge').length;
      const countText=document.getElementById('markerCount')?.textContent||'';
      return {cleanMarkers,boundaryMarkers,badgeCount,countText};
    }''',EXAMPLE)
    assert result['cleanMarkers']==[],result
    markers=result['boundaryMarkers']
    assert len(markers)==1,markers
    marker=markers[0]
    assert marker['id']=='k-boundary',marker
    assert marker['severity']=='error',marker
    assert 'Boundary blocks' in marker['message'],marker
    assert marker['rule']=='boundary-legality',marker
    assert result['badgeCount']==1,result
    assert '1' in result['countText'],result
    assert not errors,errors
    browser.close()
print('PASS markers QA')
