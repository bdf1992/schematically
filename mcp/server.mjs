#!/usr/bin/env node
// The Node entrypoint: arguments, the cores, packs, the render process, file stores, and the
// http.createServer adapter. All request handling lives in mcp/surface.mjs; this file adds no
// second copy of it.
//
// One process serves any number of documents. Each document has its own surface (one document
// state, history, runs and live snapshot), made on first use over a file store, and a call names
// its document in the URL path:
//   --file <f>     the default document: served at the unprefixed paths (/mcp, /api/v1, /editor).
//                  With neither --file nor --root it is data/schematic.sov.
//   --root <dir>   a directory of documents: /d/<id>/... serves <dir>/<id>.sov when that file exists.
//                  Without --file there is no default document.
//   /d/<id>/<rest> strips the prefix and hands /<rest> to that document's surface, createSurface
//                  being given the option base '/d/<id>' so its root description names the prefixed paths.
//   /documents     GET lists {root, default, documents}; POST {id, file} registers an id to an
//                  absolute file path (or to <root>/<id>.sov when file is left out). Two ids that
//                  name one file share one surface.
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
await import(pathToFileURL(path.join(HERE,'../src/07-state-surface.js')).href);
await import(pathToFileURL(path.join(HERE,'../src/07-graph-core.js')).href);
await import(pathToFileURL(path.join(HERE,'../src/08-layout-core.js')).href);
if(!globalThis.SovSchematicData)throw new Error('SovSchematicData core failed to load');
if(!globalThis.SovSchematicStateSpace)throw new Error('SovSchematicStateSpace failed to load');
if(!globalThis.SovSchematicSimSurface)throw new Error('SovSchematicSimSurface failed to load');
if(!globalThis.SovSchematicGraph)throw new Error('SovSchematicGraph core failed to load');

const args=process.argv.slice(2);
const arg=(name,fallback)=>{const i=args.indexOf(name);return i>=0&&args[i+1]?args[i+1]:fallback};
const PORT=Number(arg('--port',8787));
const ROOT_ARG=arg('--root',null);
const ROOT_DIR=ROOT_ARG?path.resolve(ROOT_ARG):null;
const FILE_ARG=arg('--file',null);
// The default document: --file, else data/schematic.sov when --root is not given, else none.
const FILE=FILE_ARG?path.resolve(FILE_ARG):(ROOT_DIR?null:path.resolve(path.join(HERE,'../data/schematic.sov')));
const HOST=arg('--host','127.0.0.1');
const readRepoText=relative=>fs.readFileSync(path.join(HERE,'..',relative),'utf8');
// The editor is served from this origin so the live link is a same-origin request;
// opened from file:// the browser has an opaque origin and the push never lands.
const INDEX_FILE=path.join(HERE,'../index.html');
function editorHtml(){
  try{return fs.readFileSync(INDEX_FILE,'utf8')}catch(_){return null}
}

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

// Two maps for the life of the process. Entries by file (one file never has two surfaces) and
// ids; two ids that name one file share the one entry. The surface is made on first use.
const fileKey=file=>{const resolved=path.resolve(file);return process.platform==='win32'?resolved.toLowerCase():resolved};
const entries=new Map();
const ids=new Map();
function entryFor(file){
  const key=fileKey(file);
  let entry=entries.get(key);
  if(!entry){entry={file:path.resolve(file),surface:null};entries.set(key,entry)}
  return entry;
}
function surfaceOf(entry,base){
  if(!entry.surface){
    entry.surface=createSurface({
      store:createFileStore(entry.file),
      packs:packsJson,
      render,
      readText:readRepoText,
      describe:()=>entry.file,
      editorHtml,
      base
    });
  }
  return entry.surface;
}
const defaultEntry=FILE?entryFor(FILE):null;

const ID_PATTERN=/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
// An id resolves through the ids map, else to <root>/<id>.sov when that file exists.
function resolveId(id){
  if(ids.has(id))return ids.get(id);
  if(ROOT_DIR){
    const file=path.join(ROOT_DIR,id+'.sov');
    let exists=false;try{exists=fs.statSync(file).isFile()}catch(_){}
    if(exists){const entry=entryFor(file);ids.set(id,entry);return entry}
  }
  return null;
}

const CORS={'access-control-allow-origin':'*'};
const JSON_HEADERS={'content-type':'application/json; charset=utf-8',...CORS};
function sendJson(res,status,value){res.writeHead(status,JSON_HEADERS);res.end(JSON.stringify(value))}
function listDocuments(){
  const rows=new Map();
  for(const [id,entry] of ids)rows.set(id,{id,file:entry.file,open:entry.surface!==null});
  if(ROOT_DIR){
    let names=[];try{names=fs.readdirSync(ROOT_DIR)}catch(_){}
    for(const name of names){
      if(!name.endsWith('.sov'))continue;
      const id=name.slice(0,-4);
      if(!ID_PATTERN.test(id)||rows.has(id))continue;
      const file=path.join(ROOT_DIR,name);
      let isFile=false;try{isFile=fs.statSync(file).isFile()}catch(_){}
      if(!isFile)continue;
      const entry=entries.get(fileKey(file));
      rows.set(id,{id,file:path.resolve(file),open:!!(entry&&entry.surface)});
    }
  }
  return {root:ROOT_DIR,default:FILE,documents:[...rows.values()].sort((x,y)=>x.id<y.id?-1:x.id>y.id?1:0)};
}
function registerDocument(res,rawBody){
  let input;
  try{input=rawBody?JSON.parse(rawBody):null}catch(_){return sendJson(res,400,{ok:false,code:'DOCUMENT_FILE_INVALID',message:'the request body is not JSON'})}
  if(input===null||typeof input!=='object'||Array.isArray(input))return sendJson(res,400,{ok:false,code:'DOCUMENT_FILE_INVALID',message:'the request body must be a JSON object {id, file}'});
  const id=input.id;
  if(typeof id!=='string'||!ID_PATTERN.test(id))return sendJson(res,400,{ok:false,code:'DOCUMENT_ID_INVALID',message:'an id matches ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'});
  let file;
  if(input.file!==undefined&&input.file!==null){
    if(typeof input.file!=='string'||!path.isAbsolute(input.file))return sendJson(res,400,{ok:false,code:'DOCUMENT_FILE_INVALID',message:'file must be an absolute path'});
    file=path.resolve(input.file);
  }else{
    if(!ROOT_DIR)return sendJson(res,400,{ok:false,code:'DOCUMENT_FILE_INVALID',message:'file is required when the server has no --root'});
    file=path.join(ROOT_DIR,id+'.sov');
  }
  const existing=resolveId(id);
  if(existing){
    if(fileKey(existing.file)!==fileKey(file))return sendJson(res,409,{ok:false,code:'DOCUMENT_ID_TAKEN',message:`id ${id} already names ${existing.file}`});
    return sendJson(res,200,{ok:true,id,file:existing.file});
  }
  const entry=entryFor(file);
  ids.set(id,entry);
  return sendJson(res,201,{ok:true,id,file:entry.file});
}

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
  const pathname=url.pathname;
  try{
    if(pathname==='/documents'){
      if(req.method==='GET')return sendJson(res,200,listDocuments());
      if(req.method==='POST')return registerDocument(res,body);
      if(req.method==='OPTIONS'){
        res.writeHead(204,{'access-control-allow-origin':'*','access-control-allow-methods':'GET,POST,PUT,PATCH,DELETE,OPTIONS','access-control-allow-headers':'content-type,mcp-protocol-version,mcp-method,mcp-name'});
        return res.end('');
      }
    }
    let target=null,innerPath=pathname,base='';
    if(pathname.startsWith('/d/')){
      const slash=pathname.indexOf('/',3);
      const rawId=slash<0?pathname.slice(3):pathname.slice(3,slash);
      const rest=slash<0?'/':pathname.slice(slash);
      let id=null;
      try{id=decodeURIComponent(rawId)}catch(_){}
      if(id===null||!ID_PATTERN.test(id))return sendJson(res,400,{ok:false,code:'DOCUMENT_ID_INVALID',message:'an id matches ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'});
      const entry=resolveId(id);
      if(!entry)return sendJson(res,404,{ok:false,code:'DOCUMENT_NOT_FOUND',message:`no document is registered or found under id ${id}`});
      target=surfaceOf(entry,'/d/'+encodeURIComponent(id));
      innerPath=rest;
    }else if(defaultEntry){
      target=surfaceOf(defaultEntry,'');
    }else if(pathname==='/'&&req.method==='GET'){
      return sendJson(res,200,{name:'soveraeign-schematic',document:null,documents:'/documents'});
    }else{
      return sendJson(res,404,{ok:false,code:'DOCUMENT_NOT_NAMED',message:'this server has no default document; address one at /d/<id>/..., see /documents'});
    }
    const response=await target.handle({method:req.method,path:innerPath,query,headers,body});
    res.writeHead(response.status,response.headers||{});
    res.end(response.body==null?'':response.body);
  }catch(error){
    sendJson(res,500,{ok:false,error:String(error.message||error)});
  }
});
server.listen(PORT,HOST,()=>{
  if(FILE){
    console.log(`Soveraeign Schematic API + MCP http://${HOST}:${PORT} · ${FILE}`);
    console.log(`Editor http://${HOST}:${PORT}/editor?live=1`);
  }
  if(ROOT_DIR)console.log(`Documents under ${ROOT_DIR} at http://${HOST}:${PORT}/d/<id>/ · list http://${HOST}:${PORT}/documents`);
});
