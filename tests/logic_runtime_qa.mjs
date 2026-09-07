import assert from 'node:assert/strict';
import {memoryExample} from '../scripts/logic_examples.mjs';
await import('../src/07-logic-core.js');
const D=globalThis.SovSchematicData,L=globalThis.SovSchematicLogic;
const doc=memoryExample();let s=null;
function call(action,args={},document=doc){const r=L.execute(document,s,{action,...args});assert.equal(r.ok,true,JSON.stringify(r.receipt));s=r.session;return r}
function input(component,value){call('input',{component,value});call('run',{budget:100})}
call('start');call('run');
for(const a of [0,1])for(const b of [0,1]){
  input('request',a);input('enable',b);assert.equal(s.values.condition.outputs.out,a&b);
}
input('request',1);input('enable',1);assert.equal(s.values.memory.memory[0],1);
input('enable',0);input('request',0);assert.equal(s.values.result.inputs.in,1,'disabled latch must retain result');
const authored=JSON.stringify(doc);
input('enable',1);assert.equal(s.values.result.inputs.in,0);
call('input',{component:'request',value:1});call('step');
const checkpoint=structuredClone(s);assert.ok(checkpoint.queue.length);
call('run');const uninterrupted=structuredClone(s);
call('restore',{session:checkpoint});call('run');assert.deepEqual(s,uninterrupted);
call('replay');assert.equal(JSON.stringify(doc),authored,'execution changed authored truth');
const before=structuredClone(s),bad=structuredClone(s);bad.values.memory.memory=[0];
const denied=L.execute(doc,s,{action:'restore',session:bad});assert.equal(denied.ok,false);assert.equal(denied.receipt.error.code,'REPLAY_MISMATCH');assert.deepEqual(s,before);
const changed=structuredClone(doc);changed.components.find(c=>c.id==='condition').config.logic.delay=8;
assert.equal(L.execute(changed,s,{action:'run'}).receipt.error.code,'STALE_DEFINITION');
const moved=structuredClone(doc);moved.components[0].x+=50;assert.equal(L.execute(moved,s,{action:'get'}).ok,true);
for(const request of [{action:'input',component:'result',value:1},{action:'input',component:'request',value:2},{action:'input',component:'request',value:1,time:-1},{action:'run',budget:0}])assert.equal(L.execute(doc,s,request).ok,false);
const broken=structuredClone(doc);broken.meta.logic.definitions.and.table.pop();assert.throws(()=>L.compile(broken),/Complete/);
const doubled=structuredClone(doc);doubled.wires.push({...doubled.wires[0],id:'duplicate-driver'});assert.throws(()=>L.compile(doubled),/\["condition","in"\]/);
const crossing=D.makeDocument(structuredClone(doc));D.create(crossing,'component',{id:'container',symbolId:'plane',x:0,y:0});crossing.components.find(c=>c.id==='memory').canvasId='canvas:component:container';assert.throws(()=>L.compile(crossing),/Boundary/);
const flow=structuredClone(doc);flow.components.find(c=>c.id==='request').config.ports.out.connections[0].flow='none';assert.throws(()=>L.compile(flow),/flow/);
// Long propagation has no six-hop ceiling.
const chain=D.makeDocument({id:'chain',meta:{logic:{schema:'soveraeign.schematic/logic@0.1',definitions:{source:doc.meta.logic.definitions.source,relay:{kind:'table',inputs:['in'],outputs:['out'],state:[],initial:[],table:[[0,0],[1,1]]}}}}});
for(let i=0;i<20;i++)D.create(chain,'component',{id:'n'+i,symbolId:'act',config:{logic:{definition:i?'relay':'source'}}});
for(let i=0;i<19;i++)D.create(chain,'wire',{id:'w'+i,a:'n'+i,aSide:'out',b:'n'+(i+1),bSide:'in'});
s=null;call('start',{},chain);call('input',{component:'n0',value:1},chain);call('run',{budget:1000},chain);assert.equal(s.values.n19.outputs.out,1);
// An inverter feedback loop yields at its budget and resumes deterministically.
const oscillator=D.makeDocument({id:'oscillator',meta:{logic:{schema:'soveraeign.schematic/logic@0.1',definitions:{not:{kind:'table',inputs:['in'],outputs:['out'],state:[],initial:[],table:[[0,1],[1,0]]}}}}});
D.create(oscillator,'component',{id:'inv',symbolId:'gate',config:{logic:{definition:'not'}}});D.create(oscillator,'wire',{id:'feedback',a:'inv',aSide:'out',b:'inv',bSide:'in'});
s=null;call('start',{},oscillator);call('run',{budget:7},oscillator);assert.equal(s.status,'PAUSED_BUDGET');assert.equal(s.processed,7);assert.equal(s.queue.length,1);call('step',{},oscillator);assert.equal(s.processed,8);call('replay',{},oscillator);
console.log('PASS logic truth tables, retained latch, pending-event resume, replay refusals, boundary/flow legality, long chain and bounded cycle');
