'use strict';
const assert=require('node:assert/strict');
const D=require('../src/05-data-core.js');
const S=require('../src/07-state-surface.js');
const doc=D.makeDocument({id:'virtual-state-test',virtual:{definitions:{kernel:{components:[
  {id:'$node',symbolId:'plane',x:0,y:0},
  {id:'$node-value',symbolId:'lever',x:0,y:0,parentId:'$node',canvasId:'canvas:component:$node',config:{signal:{value:0}}}
],wires:[]}},instances:[{id:'a',definitionId:'kernel',x:0,y:0},{id:'b',definitionId:'kernel',x:500,y:0}]}});
const made=S.createSimulation(doc);assert(made.ok,JSON.stringify(made));const sim=made.sim;
assert(sim.set('a-value',1).ok);sim.advance(100);
assert.equal(sim.levels()['a-value'].value,1);assert.equal(sim.levels()['b-value'].value,0);
const a=sim.instance('a'),b=sim.instance('b');
assert(a.ok&&b.ok);assert.equal(a.time,b.time);
assert(a.records.length>0);assert(b.records.length>0);
assert(a.records.every(r=>r.subject.entity.startsWith('a')));assert(b.records.every(r=>r.subject.entity.startsWith('b')));
assert(Object.keys(a.state.signal).every(k=>JSON.parse(k)[0].startsWith('a')));
assert(Object.keys(b.state.signal).every(k=>JSON.parse(k)[0].startsWith('b')));
const before=JSON.stringify(sim.snapshot());
a.state.signal.injected=true;a.records[0].value='mutated';assert.equal(JSON.stringify(sim.snapshot()),before);
const restored=S.createSimulation(doc,{restore:sim.snapshot()});assert(restored.ok);
assert.equal(restored.sim.levels()['a-value'].value,1);assert.equal(restored.sim.levels()['b-value'].value,0);
assert.equal(sim.instance('missing').ok,false);
console.log('PASS virtual instance runtime state: shared clock, independent values, scoped records, detached queries, restore');
