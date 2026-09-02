"""Hand-written files load like API-created documents.

A sparse record (symbolId, position, a few authored fields) takes the same template preset
makeComponent applies through the API: Form, attachmentDefaults, presentation, signal mode.
Authored fields always win over the preset. A wire without a surface takes the one its
ends expose, as makeWire does, so a wire inside a Plane routes on the Plane's surface.
"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
errors=[]
FIELDS='(c)=>({form:c.form,signalMode:c.config.signalMode,presentation:c.config.presentation,attachmentDefaults:c.config.attachmentDefaults??null,ports:Object.keys(c.config.ports||{})})'
SPARSE={
  'schema':'soveraeign.schematic/document@0.1','id':'sparse','components':[
    {'id':'f-point','symbolId':'point','x':200,'y':200},
    {'id':'f-path','symbolId':'path','x':600,'y':200},
    {'id':'f-plane','symbolId':'plane','x':600,'y':560},
    {'id':'f-port','symbolId':'port','x':200,'y':400},
    {'id':'f-src','symbolId':'point','x':300,'y':200,'config':{'signalMode':'source'}},
    {'id':'f-std','symbolId':'plane','x':1000,'y':560,'config':{'attachmentDefaults':'standard','presentation':{'labelMode':'outside'}}},
  ],'wires':[],'references':[]}
with sync_playwright() as p:
    browser=p.chromium.launch(**chromium_launch_kwargs())
    page=browser.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(HTML,wait_until='load');page.wait_for_timeout(120)

    # 1. The same record through the API and through a file.
    api=page.evaluate('''(fields)=>{
      const pick=eval(fields),out={};
      for(const [id,symbolId] of [['a-point','point'],['a-path','path'],['a-plane','plane'],['a-port','port']]){
        const r=SovSchematicAPI.create('component',{id,symbolId,x:100,y:100});if(!r.ok)throw new Error(r.error.message);
        out[symbolId]=pick(nodes.find(n=>n.id===id));
      }
      return out}''',FIELDS)
    loaded=page.evaluate('''([text,fields])=>{
      const pick=eval(fields);SovSchematicAPI.file.open(text,'sparse.sov');
      const out={};for(const id of ['f-point','f-path','f-plane','f-port'])out[id]=pick(nodes.find(n=>n.id===id));
      out.valid=SovSchematicData.validateDocument(SovSchematicAPI.document.get());
      out.src=nodes.find(n=>n.id==='f-src').config.signalMode;
      out.std=pick(nodes.find(n=>n.id==='f-std'));
      return out}''',[json.dumps(SPARSE),FIELDS])
    assert loaded['valid']['ok'],loaded['valid']
    for fid,sym in [('f-point','point'),('f-path','path'),('f-plane','plane'),('f-port','port')]:
        assert loaded[fid]==api[sym],(fid,json.dumps(loaded[fid]),json.dumps(api[sym]))
    assert api['point']['signalMode']=='relay' and api['port']['signalMode']=='relay',api
    assert api['plane']['attachmentDefaults']=='none' and api['plane']['ports']==[],api['plane']
    assert api['plane']['presentation']['size']=={'w':320,'h':220} and api['plane']['presentation']['graphic']['kind']=='none',api['plane']
    # 2. Authored fields win over the preset, survive re-normalization, and are saved per the
    #    file contract: none always, standard only where it overrides a Plane preset.
    assert loaded['src']=='source',loaded['src']
    assert loaded['std']['attachmentDefaults']=='standard' and loaded['std']['ports']==['in','out','control'],loaded['std']
    assert loaded['std']['presentation']['labelMode']=='outside',loaded['std']['presentation']
    kept=page.evaluate('''()=>{
      const r=SovSchematicAPI.create('component',{id:'a-std',symbolId:'plane',x:900,y:100,config:{attachmentDefaults:'standard'}});if(!r.ok)throw new Error(r.error.message);
      SovSchematicAPI.update('component','a-std',{config:{label:'Std'}});
      const a=SovSchematicAPI.create('component',{id:'a-act',symbolId:'act',x:900,y:300,config:{attachmentDefaults:'standard'}});if(!a.ok)throw new Error(a.error.message);
      const saved=SovSchematicData.compactDocument(SovSchematicAPI.document.get());
      const pick=id=>saved.components.find(c=>c.id===id).config.attachmentDefaults??null;
      return {runtime:Object.keys(nodes.find(n=>n.id==='a-std').config.ports),plane:pick('a-std'),act:pick('a-act'),fileStd:pick('f-std'),filePlane:pick('f-plane')}}''')
    assert kept=={'runtime':['in','out','control'],'plane':'standard','act':None,'fileStd':'standard','filePlane':'none'},kept
    # 3. The hand-written example's boundary Points are relays, as the palette makes them.
    example=(ROOT/'examples/08-gated-service.sov').read_text(encoding='utf-8')
    modes=page.evaluate('''(text)=>{SovSchematicAPI.file.open(text,'08.sov');return nodes.filter(n=>n.symbolId==='point').map(n=>[n.id,n.config.signalMode])}''',example)
    assert modes and all(m=='relay' for _,m in modes),modes
    # 4. The pure data core applies the same rule outside the browser runtime.
    core=page.evaluate('''()=>{const d=SovSchematicData.makeDocument({components:[{id:'p',symbolId:'point',x:0,y:0},{id:'pl',symbolId:'plane',x:0,y:0}]});
      const p=d.components[0],pl=d.components[1];return {p:[p.form.dimension,p.config.signalMode,p.config.presentation.labelMode],pl:[pl.form.regions.interior.state,pl.config.attachmentDefaults,pl.config.presentation.size.w]}}''')
    assert core=={'p':[0,'relay','none'],'pl':['open','none',320]},core
    # 5. A wire written without a surface takes the one its ends expose, as makeWire does.
    surfaces=page.evaluate('''(text)=>{SovSchematicAPI.file.open(text,'wires.sov');
      const doc=SovSchematicAPI.document.get();const w=id=>doc.wires.find(w=>w.id===id).canvasId;
      return {valid:SovSchematicData.validateDocument(doc),k1:w('k1'),k2:w('k2'),k3:w('k3'),k4:w('k4'),
        core:SovSchematicData.makeDocument(JSON.parse(text)).wires.map(w=>w.canvasId)}}''',json.dumps({
      'schema':'soveraeign.schematic/document@0.1','id':'wires','components':[
        {'id':'a','symbolId':'act','x':100,'y':300},{'id':'b','symbolId':'hold','x':300,'y':300},
        {'id':'pl','symbolId':'plane','x':700,'y':400},
        {'id':'pin','symbolId':'point','x':540,'y':400,'canvasId':'canvas:component:pl','parentId':'pl','placement':{'kind':'edge','hostId':'pl','side':'left','t':.5},'config':{'ports':{'out':{'face':'both'}}}},
        {'id':'h1','symbolId':'hold','x':700,'y':360,'canvasId':'canvas:component:pl','parentId':'pl'},
        {'id':'h2','symbolId':'hold','x':700,'y':460,'canvasId':'canvas:component:pl','parentId':'pl'},
      ],'wires':[
        {'id':'k1','a':'a','aSide':'out','b':'b','bSide':'in'},
        {'id':'k2','a':'pin','aSide':'out','b':'h1','bSide':'in'},
        {'id':'k3','a':'h1','aSide':'out','b':'h2','bSide':'in'},
        {'id':'k4','a':'b','aSide':'out','b':'pin','bSide':'out','canvasId':'canvas:global'},
      ],'references':[]}))
    assert surfaces['valid']['ok'],surfaces['valid']
    assert surfaces['k1']=='canvas:global' and surfaces['k2']=='canvas:component:pl' and surfaces['k3']=='canvas:component:pl' and surfaces['k4']=='canvas:global',surfaces
    assert surfaces['core']==['canvas:global','canvas:component:pl','canvas:component:pl','canvas:global'],surfaces['core']
    browser.close()
assert not errors,errors
print('PASS file load parity QA')
