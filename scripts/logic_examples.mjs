// Rebuild the portable logic example using the same authoring core as MCP.
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
await import('../src/06-attachment-core.js');
await import('../src/05-data-core.js');
const D=globalThis.SovSchematicData;
const table=(inputs,outputs,state,initial,fn)=>({kind:'table',inputs,outputs,state,initial,
  table:Array.from({length:2**(inputs.length+state.length)},(_,i)=>{
    const bits=Array.from({length:inputs.length+state.length},(_,j)=>(i>>(inputs.length+state.length-j-1))&1);
    return [...bits,...fn(...bits)];
  })});
export function memoryExample(){
  const doc=D.makeDocument({id:'logic-memory',meta:{title:'Request → condition → retained result',updatedAt:'2026-09-07T00:00:00Z',logic:{schema:'soveraeign.schematic/logic@0.1',definitions:{
    source:{kind:'source',inputs:[],outputs:['out'],state:[],initial:[0]},
    and:table(['in','control'],['out'],[],[],(a,b)=>[a&b]),
    latch:table(['in','control'],['out'],['held'],[0],(data,enable,held)=>{const next=enable?data:held;return [next,next]}),
    sink:table(['in'],[],[],[],()=>[])
  }}}});
  for(const [id,label,symbolId,definition,x,y,delay] of [
    ['request','Request','act','source',170,260,0],['enable','Enable / retain','switch','source',400,100,0],
    ['condition','Condition AND','gate','and',430,300,2],['memory','Retained result','hold','latch',690,300,0],
    ['result','Result','receipt','sink',940,300,0]
  ])D.create(doc,'component',{id,symbolId,x,y,config:{label,logic:{definition,delay}}});
  for(const [id,a,b,bSide] of [
    ['request-condition','request','condition','in'],['enable-condition','enable','condition','control'],
    ['condition-memory','condition','memory','in'],['enable-memory','enable','memory','control'],
    ['memory-result','memory','result','in']
  ])D.create(doc,'wire',{id,a,aSide:'out',b,bSide,config:{direction:'forward',logic:{delay:1}}});
  doc.meta.updatedAt='2026-09-07T00:00:00Z';return D.compactDocument(doc);
}
if(process.argv[1]===fileURLToPath(import.meta.url)){
  fs.writeFileSync(new URL('../examples/logic-memory.sov',import.meta.url),JSON.stringify(memoryExample(),null,2)+'\n');
}
