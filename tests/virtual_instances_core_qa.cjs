'use strict';
const assert=require('node:assert/strict');
const D=require('../src/05-data-core.js');
const C=globalThis.SovSchematicCanonical;
const seed=()=>({id:'virtual-test',components:[],wires:[],references:[],virtual:{definitions:{kernel:{components:[
  {id:'$node',symbolId:'plane',x:0,y:0,form:{dimension:2,regions:{interior:{state:'open'}}},config:{attachmentDefaults:'none'}},
  {id:'$node-worker',symbolId:'act',x:0,y:10,parentId:'$node',canvasId:'canvas:component:$node',config:{signalMode:'relay',behavior:{handler:'$node-worker'},nested:{values:[1,2]}}},
  {id:'$node-in',symbolId:'point',x:-60,y:0,parentId:'$node',canvasId:'canvas:component:$node',placement:{kind:'edge',hostId:'$node',side:'left',t:.5},form:{dimension:0},config:{ports:{out:{face:'both',connections:[{id:'connection-1',flow:'duplex',access:'read-write'}]}}}}
],wires:[{id:'$node-wire',a:'$node-in',aSide:'out',b:'$node-worker',bSide:'in',canvasId:'canvas:component:$node'}]}},instances:[{id:'a',definitionId:'kernel',x:100,y:200,overrides:{components:[],wires:[]}},{id:'b',definitionId:'kernel',x:500,y:600,overrides:{components:[],wires:[]}}]}});
let doc=D.makeDocument(seed());
assert.equal(doc.components.length,6);assert.equal(doc.wires.length,2);
const by=id=>doc.components.find(c=>c.id===id);
assert.equal(by('a-worker').canvasId,'canvas:component:a');assert.equal(by('a-in').placement.hostId,'a');
assert.equal(by('a-worker').config.behavior.handler,'a-worker');
assert.equal(by('a-worker').x,100);assert.equal(by('a-worker').y,210);
by('a-worker').config.nested.values.push(3);assert.deepEqual(by('b-worker').config.nested.values,[1,2]);
assert.deepEqual(doc.virtual.definitions.kernel.components[1].config.nested.values,[1,2]);
by('a-worker').x+=17;
D.normalizeDocument(doc);assert.equal(by('a-worker').x,117);
const compact=D.compactDocument(doc);assert.equal(compact.components.length,0);assert.equal(compact.wires.length,0);
assert(!('_materializedInstances' in compact.virtual));assert(!('_origins' in compact.virtual));
doc=D.makeDocument(compact);assert.equal(by('a-worker').x,117);assert.deepEqual(by('a-worker').config.nested.values,[1,2,3]);
assert.equal(C.canonicalize(D.compactDocument(doc)),C.canonicalize(compact));
assert.equal(D.documentHash(doc),D.documentHash(D.makeDocument(compact)));
doc.virtual.instances[0].x+=30;D.normalizeDocument(doc);assert.equal(by('a-worker').x,147);assert.equal(by('a').x,130);assert.equal(by('b').x,500);
const moved=D.makeDocument(D.compactDocument(doc));assert.equal(moved.components.find(c=>c.id==='a-worker').x,147);
D.remove(doc,'component','a-worker');assert(!by('a-worker'));D.normalizeDocument(doc);assert(!by('a-worker'));
const deleted=D.compactDocument(doc);assert(deleted.virtual.instances[0].removeComponents.includes('$node-worker'));
doc=D.makeDocument(deleted);assert(!by('a-worker'));assert(by('b-worker'));assert(!doc.wires.some(w=>w.id==='a-wire'));
const extra=seed();extra.virtual.instances[0].overrides.components.push({id:'$node-extra',symbolId:'act',x:20,y:20,parentId:'$node',canvasId:'canvas:component:$node',config:{label:'added'}});
const ed=D.makeDocument(extra),er=D.makeDocument(D.compactDocument(ed));assert(er.components.some(c=>c.id==='a-extra'));
assert.deepEqual(D.instanceMembers(er,'a').components.map(c=>c.id).sort(),['a','a-extra','a-in','a-worker']);
assert.equal(D.instanceMembers(er,'a').wires[0].id,'a-wire');
assert.deepEqual(D.instanceMembers(er,'unknown'),{components:[],wires:[]});
const unknown=seed();unknown.virtual.instances[0].definitionId='missing';assert.throws(()=>D.makeDocument(unknown),/VIRTUAL_DEFINITION_UNKNOWN/);
const duplicate=seed();duplicate.virtual.instances[1].id='a';assert.throws(()=>D.makeDocument(duplicate),/VIRTUAL_DUPLICATE/);
const repeated=seed();repeated.virtual.definitions.kernel.components.push({...repeated.virtual.definitions.kernel.components[0]});assert.throws(()=>D.makeDocument(repeated),/VIRTUAL_DUPLICATE/);
const bad=seed();delete bad.virtual.definitions.kernel.wires;assert.throws(()=>D.makeDocument(bad),/VIRTUAL_INVALID/);
const invalidExpanded=D.makeDocument(seed());invalidExpanded.virtual.instances[0].definitionId='missing';
assert.equal(D.validateDocument(invalidExpanded).ok,false);
const replace=D.makeDocument(seed());D.replaceDocument(replace,compact);assert.equal(replace.virtual.instances.length,2);D.replaceDocument(replace,{components:[],wires:[]});assert(!replace.virtual);
// Compact packages carry definitions once; validation opens a private graph to check
// generated endpoints and surfaces without changing the stored representation.
const packageSource=D.makeDocument(seed()),packed=D.makePackage({document:packageSource});
assert.equal(packed.document.components.length,0);assert.equal(packed.document.wires.length,0);
assert.equal(packageSource.components.length,6);
const packedBefore=JSON.stringify(packed);
assert.deepEqual(D.validatePackage(packed),{ok:true,errors:[]});
assert.deepEqual(D.validateDocument(packed.document),{ok:true,errors:[]});
assert.equal(JSON.stringify(packed),packedBefore);
const unpacked=D.documentFromFilePayload(packed);assert.equal(unpacked.components.length,6);assert.equal(unpacked.wires.length,2);
assert.equal(C.canonicalize(D.compactDocument(unpacked)),C.canonicalize(packed.document));
const illegalPackage=D.clone(packed);illegalPackage.document.virtual.definitions.kernel.wires[0].b='$node-missing';
assert.equal(D.validatePackage(illegalPackage).ok,false);
assert(D.validateDocument(illegalPackage.document).errors.some(e=>e.includes('missing endpoint component')));
const badOperation=D.clone(packed.document);badOperation.virtual.definitions.kernel.wires[0].config={forwardOperation:'invalid'};
assert(D.validateDocument(badOperation).errors.some(e=>e.includes('invalid forwardOperation')));
const ordinary=D.makePackage({document:{components:[{id:'ordinary',symbolId:'act'}],wires:[],references:[]}});
assert.equal(ordinary.document.components.length,1);assert(ordinary.document.components[0].form);
for(const kind of ['components','wires']){
  const collision=seed();collision[kind].push(kind==='components'?{id:'b-worker',symbolId:'act'}:{id:'b-wire',a:'authored-a',b:'authored-b'});
  const authoredBefore=JSON.stringify(collision[kind]);
  assert.throws(()=>D.materializeVirtual(collision),/VIRTUAL_DUPLICATE: authored/);
  assert.equal(JSON.stringify(collision[kind]),authoredBefore);assert.equal(collision[kind].length,1);
  assert.equal(collision[kind==='components'?'wires':'components'].length,0);
  assert.equal(D.validateDocument(collision).ok,false);
}
const expandedClone=D.makeDocument(D.clone(packageSource));assert.equal(expandedClone.components.length,6);assert.equal(expandedClone.wires.length,2);
console.log('virtual instances core QA passed: independent expansion, edit/delete/move factoring, compact package validation, collision rejection, expanded clones');
