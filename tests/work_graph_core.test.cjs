'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const Data=require('../src/05-data-core.js');
const Graph=require('../src/07-graph-core.js');
const Work=require('../src/08-workstation-graph.js');
const fixture=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/work-graph/mission.json'),'utf8'));
const clone=x=>JSON.parse(JSON.stringify(x));
let count=0;
function test(name,run){run();count++;console.log('PASS '+name);}
function refuses(code,fn){assert.throws(fn,e=>e.code===code,code);}
const original=JSON.stringify(fixture),pack=Work.project(fixture);
const task=Work.address('task','build-candidate');
const field=(p,address,axis)=>Graph.inspect(p.document,p.meta.graph,address).fields.find(f=>f.axis===axis);

test('projection is deterministic, pure, and a native package',()=>{
  assert.equal(JSON.stringify(fixture),original);
  assert.deepEqual(Work.project(clone(fixture)),pack);
  const reordered=clone(fixture);reordered.tasks.reverse();assert.deepEqual(Work.project(reordered),pack);
  assert.equal(pack.schema,Data.PACKAGE_SCHEMA);
  assert.equal(Data.validateDocument(pack.document).ok,true);
  assert.deepEqual(pack,JSON.parse(fs.readFileSync(path.join(__dirname,'../examples/workstation-review.sovpak'),'utf8')));
});
test('public geometry and readings have distinct custody',()=>{
  assert.equal(pack.document.meta.graph.schema,Graph.DEFINITION);
  assert.equal(pack.document.meta.graph.readings,undefined);
  assert.equal(pack.document.meta.graph.source,undefined);
  assert.equal(pack.meta.graph.schema,Graph.SNAPSHOT);
  assert.equal(pack.meta.graph.source.consistency,'fixture');
});
test('three-level containment uses native Components',()=>{
  const root=Graph.inspect(pack.document,pack.meta.graph,Work.address('mission',fixture.mission.id));
  assert.equal(root.children.filter(x=>x.resource==='component').length,3);
  const charge=Graph.inspect(pack.document,pack.meta.graph,task+'/contract');
  assert.equal(charge.ancestors.length,2);assert.equal(charge.parent,task);
  assert.equal(charge.resource,'component');assert.equal(charge.kind,'charge');
  assert.equal(charge.fields.find(f=>f.axis==='steps').source,'control/tasks/build-candidate.json#/contract/steps');
});
test('missing, null, zero, false and empty remain distinct',()=>{
  const input=clone(fixture);input.tasks[0].contract={missing:null,zero:0,flag:false,empty:[],text:''};
  delete input.tasks[0].repository_state;
  const p=Work.project(input);
  assert.equal(field(p,task,'repository_state').status,'absent');
  const values=Graph.inspect(p.document,p.meta.graph,task+'/contract').fields;
  for(const [axis,value] of Object.entries(input.tasks[0].contract)){
    const f=values.find(f=>f.axis===axis);assert.equal(f.status,'present');assert.deepEqual(f.value,value);
  }
  assert.equal(Object.hasOwn(field(p,task,'repository_state'),'value'),false);
});
test('candidate identifiers and evidence are not observations of a revision',()=>{
  assert.equal(field(pack,task+'/candidate','revision').status,'absent');
  assert.equal(field(pack,task,'workstation_state').basis,'declared');
  const edge=pack.document.meta.graph.bindings.find(b=>b.resource==='wire');
  assert.equal(edge.kind,'dependency');assert.equal(field(pack,edge.address,'delivery').status,'absent');
});
test('unresolved text and out-of-snapshot dependencies never become invented edges',()=>{
  assert.equal(pack.document.wires.length,2);
  assert(pack.meta.graph.gaps.some(g=>g.code==='DEPENDENCY_OUTSIDE_SNAPSHOT'));
  assert(pack.meta.graph.gaps.some(g=>g.code==='UNRESOLVED_WAIT'));
  assert(!pack.document.meta.graph.bindings.some(b=>b.address===Work.address('task','external-observation')));
  const input=clone(fixture);delete input.tasks[0].dependencies;
  assert(Work.project(input).meta.graph.gaps.some(g=>g.code==='DEPENDENCIES_ABSENT'));
});
test('identities survive insertions and delimiter-like task identifiers',()=>{
  const input=clone(fixture);const extra={...clone(input.tasks[0]),id:'a:new/task',dependencies:[]};input.tasks.push(extra);
  const p=Work.project(input);
  for(const binding of pack.document.meta.graph.bindings)assert.deepEqual(p.document.meta.graph.bindings.find(b=>b.address===binding.address),binding);
});
test('cycles in requirements are visible rather than mistaken for an executable DAG',()=>{
  const input=clone(fixture);input.tasks[0].dependencies=['review-outcome'];
  const p=Work.project(input);assert.equal(p.document.wires.length,3);assert(Graph.validate(p.document,p.meta.graph).ok);
});
test('duplicate identities and foreign mission members refuse',()=>{
  const input=clone(fixture);input.tasks.push(clone(input.tasks[0]));refuses('GRAPH_DUPLICATE',()=>Work.project(input));
  input.tasks.pop();input.tasks[0].mission='other';refuses('WS_GRAPH_SCOPE',()=>Work.project(input));
  input.tasks[0].mission=fixture.mission.id;input.tasks[0].repository='other';refuses('WS_GRAPH_SCOPE',()=>Work.project(input));
});
test('a source frontier is required, not synthesized from wall time',()=>{
  const input=clone(fixture);delete input.source;refuses('GRAPH_SOURCE',()=>Work.project(input));
  input.source={...fixture.source,capturedAt:'2026-09-21'};refuses('GRAPH_SOURCE',()=>Work.project(input));
  input.source={...fixture.source,consistency:'live'};refuses('GRAPH_SOURCE',()=>Work.project(input));
});
test('diagram geometry can change without altering the source meaning',()=>{
  const p=clone(pack);const c=p.document.components[1];c.x+=71;c.y-=31;c.editor={pinned:true};
  p.document.revision+=1;assert(Graph.validate(p.document,p.meta.graph).ok);
});
test('label, scope, and endpoint meaning changes detach the source reading',()=>{
  const p=clone(pack);p.document.components[1].config.label='Different responsibility';
  refuses('GRAPH_DEFINITION_CHANGED',()=>Graph.validate(p.document,p.meta.graph));
  const q=clone(pack);q.document.meta.graph.bindings[1].address='foreign-subject';
  refuses('GRAPH_DEFINITION_CHANGED',()=>Graph.validate(q.document,q.meta.graph));
  const r=clone(pack);r.document.wires[0].config.direction='reverse';
  refuses('GRAPH_DEFINITION_CHANGED',()=>Graph.validate(r.document,r.meta.graph));
});
test('native boundary legality rejects a child-to-outside reach-through',()=>{
  const p=clone(pack);const doc=Data.makeDocument(p.document);
  const held=doc.components.find(c=>c.id.includes('-contract'));
  const target=doc.components.find(c=>c.id==='task-check-evidence');
  held.config.attachmentDefaults='standard';
  const wire={...clone(doc.wires[0]),id:'escape',a:held.id,aAttachment:{kind:'attachment-ref',componentId:held.id,pointId:'right'}};doc.wires.push(wire);
  doc.meta.graph.bindings.push({resource:'wire',id:'escape',kind:'transport',address:'escape'});
  refuses('GRAPH_TOPOLOGY',()=>Graph.definition(doc));
});
test('closed or cyclic containment refuses',()=>{
  const p=clone(pack);p.document.components[0].form.regions.interior.state='closed';
  assert.throws(()=>Graph.definition(p.document));
  const q=Data.makeDocument(pack.document);const child=q.components.find(c=>c.id==='task-build-candidate');
  q.components[0].canvasId=Data.componentCanvasId(child);q.components[0].parentId=child.id;
  assert.throws(()=>Graph.definition(q));
});
test('a carrier can hold a subsystem which holds a structured charge',()=>{
  const doc=Data.makeDocument({id:'carrier-structure',meta:{graph:{schema:Graph.DEFINITION,bindings:[]}}});
  for(const [id,x] of [['a',100],['b',800]])doc.components.push(Data.makeComponent(doc,{id,symbolId:'buffer',x,y:200}));
  const wire=Data.makeWire(doc,{id:'channel',a:'a',aSide:'out',b:'b',bSide:'in'});doc.wires.push(wire);
  const holder=Data.makeComponent(doc,{id:'delivery',symbolId:'plane',x:400,y:200,wireId:'channel',wireT:.5,canvasId:'canvas:wire:channel',form:{dimension:2,regions:{interior:{state:'open'}}},config:{label:'Delivery',attachmentDefaults:'none'}});
  doc.components.push(holder);
  doc.components.push(Data.makeComponent(doc,{id:'payload',symbolId:'plane',x:400,y:200,parentId:'delivery',canvasId:Data.componentCanvasId(holder),config:{label:'Packet',attachmentDefaults:'none'}}));
  doc.meta.graph.bindings=[...doc.components.map(c=>({resource:'component',id:c.id,address:c.id,kind:c.id==='payload'?'charge':'system'})),{resource:'wire',id:'channel',address:'channel',kind:'transport'}];
  const state=Graph.snapshot(doc,fixture.source,doc.meta.graph.bindings.map(b=>({address:b.address,fields:[{axis:'contents',basis:'declared',status:'present',value:{request:{criteria:['C1','C2']}},source:'fixture'}]})));
  const reading=Graph.inspect(doc,state,'payload');assert.deepEqual(reading.ancestors.map(a=>a.address),['channel','delivery']);
});
test('ambiguous presence, missing subjects and duplicate axes refuse',()=>{
  const p=clone(pack);const f=p.meta.graph.readings[0].fields[0];f.status='absent';
  refuses('GRAPH_READING',()=>Graph.validate(p.document,p.meta.graph));
  const q=clone(pack);q.meta.graph.readings.pop();refuses('GRAPH_READINGS',()=>Graph.validate(q.document,q.meta.graph));
  const r=clone(pack);r.meta.graph.readings[0].fields.push(clone(r.meta.graph.readings[0].fields[0]));refuses('GRAPH_DUPLICATE',()=>Graph.validate(r.document,r.meta.graph));
});
test('unsafe values, large text and nested values are bounded',()=>{
  refuses('GRAPH_SHAPE',()=>Graph.jsonValue(JSON.parse('{"__proto__":{"polluted":true}}')));
  refuses('GRAPH_SHAPE',()=>Graph.jsonValue(Infinity));
  refuses('GRAPH_LIMIT',()=>Graph.jsonValue('x'.repeat(2_000_001)));
  let deep={};for(let i=0;i<26;i++)deep={nested:deep};refuses('GRAPH_LIMIT',()=>Graph.jsonValue(deep));
  assert.equal({}.polluted,undefined);
});
test('comparison reports exact readings, not fabricated completion or replay',()=>{
  const input=clone(fixture);input.source.revision='fixture-2';input.tasks[0].workstation_state='BLOCKED';
  const p=Work.project(input),delta=Graph.compare(pack,p);
  assert.equal(delta.definitionChanged,false);assert.equal(delta.changes.length,1);
  assert.equal(delta.changes[0].axis,'workstation_state');assert.equal(delta.changes[0].before.value,'ACTIVE');assert.equal(delta.changes[0].after.value,'BLOCKED');
  p.meta.graph.source.system='foreign';refuses('GRAPH_SCOPE',()=>Graph.compare(pack,p));
});
test('common tool surface refuses safely and never mutates supplied records',()=>{
  const before=JSON.stringify(pack);
  for(const name of ['schematic.graph.project-workstation','schematic.graph.inspect','schematic.graph.compare'])assert(Work.tools().some(t=>t.name===name));
  const reading=Work.execute('schematic.graph.inspect',{package:pack,address:task});assert(reading.ok);assert.equal(reading.mutates,false);
  assert.equal(Work.execute('schematic.graph.inspect',{package:pack,address:'missing'}).value.error.code,'GRAPH_SUBJECT');
  assert.equal(Work.execute('unknown').value.error.code,'GRAPH_OPERATION');
  assert.equal(JSON.stringify(pack),before);
});
console.log(`WORK GRAPH CORE PASS: ${count} cases`);
