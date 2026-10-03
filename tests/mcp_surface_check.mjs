#!/usr/bin/env node
// Loads the cores the way mcp/server.mjs does, builds a surface over a memory store seeded with
// examples/01-source-hold.sov, and prints one JSON object with the bodies of the same sequence
// tests/mcp_surface_qa.py sends over HTTP to mcp/server.mjs, so the two can be compared for
// parity after removing their volatile fields.
import path from 'node:path';
import fs from 'node:fs';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createSurface} from '../mcp/surface.mjs';
import {createMemoryStore} from '../mcp/store-memory.mjs';

const HERE=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.join(HERE,'..');
await import(pathToFileURL(path.join(ROOT,'src/03-canonical.js')).href);
await import(pathToFileURL(path.join(ROOT,'src/03-notation-core.js')).href);
await import(pathToFileURL(path.join(ROOT,'src/04-signal-model.js')).href);
await import(pathToFileURL(path.join(ROOT,'src/06-attachment-core.js')).href);
await import(pathToFileURL(path.join(ROOT,'src/05-data-core.js')).href);
await import(pathToFileURL(path.join(ROOT,'src/07-state-space.js')).href);
await import(pathToFileURL(path.join(ROOT,'src/07-graph-core.js')).href);
await import(pathToFileURL(path.join(ROOT,'src/08-layout-core.js')).href);

const seed=fs.readFileSync(path.join(ROOT,'examples/01-source-hold.sov'),'utf8');
const store=createMemoryStore(seed);
const packDir=path.join(ROOT,'data');
const packs=fs.readdirSync(packDir).filter(n=>n.endsWith('.pack.json')).sort().map(n=>JSON.parse(fs.readFileSync(path.join(packDir,n),'utf8')));
const readText=relative=>fs.readFileSync(path.join(ROOT,relative),'utf8');
const surface=createSurface({store,packs,readText,describe:()=>'memory'});

let nextId=0;
async function mcpCall(method,params){
  nextId+=1;
  const res=await surface.handle({method:'POST',path:'/mcp',query:{},headers:{},body:JSON.stringify({jsonrpc:'2.0',id:nextId,method,params})});
  return JSON.parse(res.body);
}
async function httpCall(method,reqPath,bodyObj){
  const res=await surface.handle({method,path:reqPath,query:{},headers:{},body:bodyObj===undefined?null:JSON.stringify(bodyObj)});
  return {status:res.status,body:res.body?JSON.parse(res.body):null};
}

const initialize=await mcpCall('initialize',{protocolVersion:'2026-07-28'});
const toolsList=await mcpCall('tools/list',{});
const toolNames=toolsList.result.tools.map(t=>t.name).sort();
const guideIndex=await mcpCall('tools/call',{name:'schematic.guide',arguments:{}});
// A whole-document read: an area wide enough to hold anything a document in this suite builds.
const readWhole=await mcpCall('tools/call',{name:'schematic.read',arguments:{area:{x:-1000000,y:-1000000,width:2000000,height:2000000}}});
const apply=await mcpCall('tools/call',{name:'schematic.apply',arguments:{operations:[{op:'create',resource:'component',value:{symbolId:'act',x:900,y:200,config:{label:'mcp-surface-check'}}}]}});
const document=await httpCall('GET','/api/v1/document');
const runStart=await httpCall('POST','/api/v1/runs',{});
const handle=runStart.body.handle;
const runStep=await httpCall('POST',`/api/v1/runs/${encodeURIComponent(handle)}/step`);

console.log(JSON.stringify({
  initialize,
  toolNames,
  guideIndex,
  readWhole,
  apply,
  document,
  runStart,
  runStep,
  writes:store.writes
}));
