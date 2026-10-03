#!/usr/bin/env node
// The Node entrypoint: arguments, the cores, packs, the render process, a file store, and the
// http.createServer adapter. All request handling lives in mcp/surface.mjs; this file adds no
// second copy of it.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createSurface} from './surface.mjs';
import {createFileStore} from './store-file.mjs';

const HERE=path.dirname(fileURLToPath(import.meta.url));
// Absolute paths are not valid ESM specifiers on Windows; import by file:// URL everywhere.
await import(pathToFileURL(path.join(HERE,'../src/03-canonical.js')).href);
await import(pathToFileURL(path.join(HERE,'../src/03-notation-core.js')).href);
await import(pathToFileURL(path.join(HERE,'../src/04-signal-model.js')).href);
await import(pathToFileURL(path.join(HERE,'../src/06-attachment-core.js')).href);
await import(pathToFileURL(path.join(HERE,'../src/05-data-core.js')).href);
await import(pathToFileURL(path.join(HERE,'../src/07-state-space.js')).href);
await import(pathToFileURL(path.join(HERE,'../src/07-graph-core.js')).href);
await import(pathToFileURL(path.join(HERE,'../src/08-layout-core.js')).href);
if(!globalThis.SovSchematicData)throw new Error('SovSchematicData core failed to load');
if(!globalThis.SovSchematicStateSpace)throw new Error('SovSchematicStateSpace failed to load');
if(!globalThis.SovSchematicGraph)throw new Error('SovSchematicGraph core failed to load');

const args=process.argv.slice(2);
const arg=(name,fallback)=>{const i=args.indexOf(name);return i>=0&&args[i+1]?args[i+1]:fallback};
const PORT=Number(arg('--port',8787));
const FILE=path.resolve(arg('--file',path.join(HERE,'../data/schematic.sov')));
const HOST=arg('--host','127.0.0.1');
const readRepoText=relative=>fs.readFileSync(path.join(HERE,'..',relative),'utf8');

// Runs read packs from data/*.pack.json (file-name order) at start.
const PACK_DIR=path.join(HERE,'../data');
const packsJson=fs.readdirSync(PACK_DIR).filter(name=>name.endsWith('.pack.json')).sort().map(name=>JSON.parse(fs.readFileSync(path.join(PACK_DIR,name),'utf8')));

// Pictures and layout metrics need a browser; the surface asks scripts/render_service.py, which
// runs the editor's own renderer in headless Chromium. Without one the call is refused, typed.
// Windows installs Python as `python` (there is no python3 on the path).
const RENDER_PYTHON=process.env.SOV_RENDER_PYTHON||(process.platform==='win32'?'python':'python3');
function render(formats,args={}){
  return new Promise(resolve=>{
    let out='',err='';const child=spawn(RENDER_PYTHON,[path.join(HERE,'../scripts/render_service.py')],{cwd:path.join(HERE,'..')});
    const timer=setTimeout(()=>{child.kill();resolve({ok:false,code:'RENDER_TIMEOUT',message:'render took longer than 90s'})},90000);
    child.stdout.on('data',d=>out+=d);child.stderr.on('data',d=>err+=d);
    child.on('error',e=>{clearTimeout(timer);resolve({ok:false,code:'RENDERER_UNAVAILABLE',message:`cannot start ${RENDER_PYTHON}: ${e.message}`})});
    child.on('close',()=>{clearTimeout(timer);try{resolve(JSON.parse(out.trim().split('\n').pop()))}catch(_){resolve({ok:false,code:'RENDER_FAILED',message:(err||out).trim().split('\n').pop()||'no output'})}});
    child.stdin.end(JSON.stringify({document:args.document,formats,appearance:args.appearance||'light',scale:args.scale??2,pad:args.pad??48,view:args.view||null,legend:args.legend===true||args.legend==='true'||args.legend==='1',narration:args.narration!=null&&args.narration!==''&&Number.isInteger(Number(args.narration))?Number(args.narration):null}));
  });
}

const surface=createSurface({
  store:createFileStore(FILE),
  packs:packsJson,
  render,
  readText:readRepoText,
  describe:()=>FILE
});

function readBody(req){
  return new Promise((resolve,reject)=>{
    let chunks='';req.setEncoding('utf8');
    req.on('data',c=>{chunks+=c;if(chunks.length>5_000_000){reject(new Error('request too large'));req.destroy()}});
    req.on('end',()=>resolve(chunks||null));
    req.on('error',reject);
  });
}

const server=http.createServer(async(req,res)=>{
  let body=null;
  try{
    if(req.method!=='GET'&&req.method!=='HEAD'&&req.method!=='OPTIONS')body=await readBody(req);
  }catch(error){
    res.writeHead(400,{'content-type':'application/json; charset=utf-8'});return res.end(JSON.stringify({error:String(error.message||error)}));
  }
  const url=new URL(req.url||'/',`http://${req.headers.host||HOST}`);
  const query=Object.fromEntries(url.searchParams.entries());
  const headers={};for(const [k,v] of Object.entries(req.headers))headers[k.toLowerCase()]=v;
  const response=await surface.handle({method:req.method,path:url.pathname,query,headers,body});
  res.writeHead(response.status,response.headers||{});
  res.end(response.body==null?'':response.body);
});
server.listen(PORT,HOST,()=>console.log(`Soveraeign Schematic API + MCP http://${HOST}:${PORT} · ${FILE}`));
