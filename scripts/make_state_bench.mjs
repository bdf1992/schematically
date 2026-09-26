#!/usr/bin/env node
// Regenerates the state space runtime benchmark (issue #48): examples/state/bench.sov and
// examples/state/bench.inputs.json. Deterministic: a fixed-seed integer PRNG, no clock, no
// Math.random. It never touches examples/state/bench.sovtrace, which is the engine's output.
//
// The document: 24 Point sources S00..S23; a mesh of 120 core.logic devices G000..G119 (AND,
// OR, XOR, NOT) in 10 layers of 12, fed by forward Paths with delays 1-3; 8 Point junctions
// J0..J7 with two or three incoming Paths each (declared merges on J0-J4 and J6, stochastic on
// J4, J5, J7); three feedback loops, each through a NOT. A Point's self is declared as
// {id: 'self', channels} only, with no flow key.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const OUT=path.join(ROOT,'examples/state');
let s=0x5eed0048>>>0;
const rand=()=>{s=(s+0x6d2b79f5)>>>0;let t=s;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)};
const pick=n=>rand()%n;
const pad=(n,w)=>String(n).padStart(w,'0');

const components=[],wires=[];
const channel=merge=>merge?[{id:'main',merge}]:[{id:'main'}];
const point=(id,x,y,merge)=>{const config={label:id};if(merge)config.attachmentPoints=[{id:'self',channels:channel(merge)}];components.push({id,symbolId:'point',x,y,config})};
const DEFS={and:['logic.and@1','AND',['a','b']],or:['logic.or@1','OR',['a','b']],xor:['logic.xor@1','XOR',['a','b']],not:['logic.not@1','NOT',['a']]};
const device=(id,kind,x,y)=>{
  const [definition,label,inputs]=DEFS[kind];
  const ports=inputs.map((p,i)=>({id:p,side:'left',t:(i+1)/(inputs.length+1),flow:'in',channels:[{id:'main'}]}));
  ports.push({id:'q',side:'right',t:.5,flow:'out',channels:[{id:'main'}]});
  components.push({id,symbolId:'act',x,y,config:{label,definition,attachmentDefaults:'none',attachmentPoints:ports}});
};
const ref=(c,p)=>({kind:'attachment-ref',componentId:c,pointId:p});
const wire=(from,to,delay)=>{
  const id=`w${pad(wires.length,4)}`;
  wires.push({id,a:from[0],aSide:from[1],aAttachment:ref(from[0],from[1]),b:to[0],bSide:to[1],bAttachment:ref(to[0],to[1]),config:{direction:'forward',delay:delay===undefined?1+pick(3):delay}});
  return id;
};

// Sources.
const SOURCES=24,LAYERS=10,WIDTH=12;
for(let i=0;i<SOURCES;i++)point(`S${pad(i,2)}`,0,40*i);
// Devices: kinds by layer and slot; the loop NOTs are forced.
const G=(layer,slot)=>`G${pad(layer*WIDTH+slot,3)}`;
const KINDS=['and','or','xor','not'];
const kind={};
for(let l=0;l<LAYERS;l++)for(let k=0;k<WIDTH;k++)kind[G(l,k)]=KINDS[pick(4)];
const LOOPS=[[G(2,0),G(3,1),G(4,2)],[G(2,6),G(3,7),G(4,8),G(5,9)],[G(6,3),'J7',G(7,4)]];
for(const loop of LOOPS)kind[loop[0]]='not';
for(let l=0;l<LAYERS;l++)for(let k=0;k<WIDTH;k++)device(G(l,k),kind[G(l,k)],200+160*l,60*k);
// Junctions: J at layer L is fed from sources and devices before L and feeds devices at L and after.
const JUNCTIONS=[
  ['J0',2,2,{combine:'last',order:{kind:'declared',paths:[]}}],
  ['J1',3,2,{combine:'or'}],
  ['J2',4,3,{combine:'and'}],
  ['J3',5,3,{combine:'first',order:{kind:'declared',paths:[]}}],
  ['J4',6,2,{combine:'last',order:{kind:'stochastic'}}],
  ['J5',7,3,null],
  ['J6',8,2,{combine:'queue',order:{kind:'declared',paths:[]}}],
  ['J7',7,2,null]
];
const junctionLayer={};
for(const [id,layer,,merge] of JUNCTIONS){point(id,120+160*layer,60*WIDTH+40,merge?JSON.parse(JSON.stringify(merge)):null);junctionLayer[id]=layer}
// A driver for something at layer L: a source, a junction of layer <= L (< L when it feeds a
// junction), or a device output before L.
const driver=(layer,strict)=>{
  const r=pick(10);
  if(layer===0||r<2)return [`S${pad(pick(SOURCES),2)}`,'self'];
  if(r<4){const js=JUNCTIONS.filter(j=>(strict?j[1]<layer:j[1]<=layer)&&j[0]!=='J7');if(js.length)return [js[pick(js.length)][0],'self']}
  const l=Math.max(0,layer-1-pick(Math.min(layer,3)));
  return [G(l,pick(WIDTH)),'q'];
};
// Junction feeds first, so a declared order can name the Paths it is fed by.
for(const [id,layer,fanIn,merge] of JUNCTIONS){
  if(id==='J7')continue;
  const fed=[];
  for(let i=0;i<fanIn;i++){const from=driver(layer,true);fed.push(wire(from,[id,'self']))}
  if(merge&&merge.order&&merge.order.kind==='declared'){
    const pts=components.find(c=>c.id===id).config.attachmentPoints[0].channels[0].merge.order;
    pts.paths=id==='J3'?[fed[fed.length-1]]:fed.slice().reverse();
  }
}
// Loop wiring: each loop is a chain from its NOT back to the NOT's input.
const fixed={};
for(const loop of LOOPS){
  for(let i=0;i<loop.length;i++){
    const from=loop[i],to=loop[(i+1)%loop.length];
    const fromPort=from.startsWith('J')?'self':'q';
    if(to.startsWith('J'))wire([from,fromPort],[to,'self']);
    else fixed[to+'.a']=[from,fromPort];
  }
}
// J7 gets a second feed besides the loop.
wire(driver(7,true),['J7','self']);
// Every device input is fed by exactly one Path.
for(let l=0;l<LAYERS;l++)for(let k=0;k<WIDTH;k++){
  const id=G(l,k);
  for(const p of DEFS[kind[id]][2])wire(fixed[`${id}.${p}`]||driver(l),[id,p]);
}
// A few outputs fan out to Point sinks, so late layers are observed.
for(let k=0;k<WIDTH;k++){point(`O${pad(k,2)}`,200+160*LAYERS,60*k);wire([G(LAYERS-1,k),'q'],[`O${pad(k,2)}`,'self'])}

const doc={schema:'soveraeign.schematic/document@0.1',id:'state-bench',revision:0,meta:{title:'State space runtime benchmark (#48): 24 sources, 120 core.logic devices, 8 junctions, 3 NOT loops'},components,wires,references:[],layout:{}};
// Inputs: every source is set at tick 0 and toggles at pseudo-random ticks through 60.
const inputs=[];
for(let i=0;i<SOURCES;i++){
  let value=pick(2)===1;
  inputs.push({entity:`S${pad(i,2)}`,point:'self',value,at:0});
  for(let t=1;t<=60;t++)if(pick(5)===0){value=!value;inputs.push({entity:`S${pad(i,2)}`,point:'self',value,at:t})}
}
fs.writeFileSync(path.join(OUT,'bench.sov'),JSON.stringify(doc,null,2)+'\n');
fs.writeFileSync(path.join(OUT,'bench.inputs.json'),JSON.stringify(inputs,null,2)+'\n');
console.log(`bench.sov: ${components.length} components, ${wires.length} wires; bench.inputs.json: ${inputs.length} inputs`);
