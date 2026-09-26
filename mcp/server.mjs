#!/usr/bin/env node
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';

const HERE=path.dirname(fileURLToPath(import.meta.url));
// Absolute paths are not valid ESM specifiers on Windows; import by file:// URL everywhere.
await import(pathToFileURL(path.join(HERE,'../src/03-canonical.js')).href);
await import(pathToFileURL(path.join(HERE,'../src/03-notation-core.js')).href);
await import(pathToFileURL(path.join(HERE,'../src/06-attachment-core.js')).href);
await import(pathToFileURL(path.join(HERE,'../src/05-data-core.js')).href);
await import(pathToFileURL(path.join(HERE,'../src/07-state-space.js')).href);
await import(pathToFileURL(path.join(HERE,'../src/07-graph-core.js')).href);
await import(pathToFileURL(path.join(HERE,'../src/08-layout-core.js')).href);
const Layout=globalThis.SovSchematicLayout;
const Data=globalThis.SovSchematicData,Graph=globalThis.SovSchematicGraph;
if(!Data)throw new Error('SovSchematicData core failed to load');
const State=globalThis.SovSchematicStateSpace;
if(!State)throw new Error('SovSchematicStateSpace failed to load');
if(!Graph)throw new Error('SovSchematicGraph core failed to load');
// Graph queries and the simulation are read-only over the document; one session per server.
const graphSession=Graph.createSession();

const args=process.argv.slice(2);
const arg=(name,fallback)=>{const i=args.indexOf(name);return i>=0&&args[i+1]?args[i+1]:fallback};
const PORT=Number(arg('--port',8787));
const FILE=path.resolve(arg('--file',path.join(HERE,'../data/schematic.sov')));
const HOST=arg('--host','127.0.0.1');
const MCP_VERSION='2026-07-28';

function loadDocument(){
  try{return Data.documentFromFilePayload(JSON.parse(fs.readFileSync(FILE,'utf8')))}catch(_){return Data.makeDocument({id:'schematic-1'})}
}
let documentState=loadDocument();
// Runs live beside the document, not in it: an in-memory registry, every run started from the
// current document, packs read from data/*.pack.json (file-name order) at start.
const PACK_DIR=path.join(HERE,'../data');
const packsJson=fs.readdirSync(PACK_DIR).filter(name=>name.endsWith('.pack.json')).sort().map(name=>JSON.parse(fs.readFileSync(path.join(PACK_DIR,name),'utf8')));
const runs=State.createRunRegistry({packs:packsJson,document:()=>Data.clone(documentState)});
const handle={type:'string',minLength:1,description:'the run handle (<runId>.<n>) from schematic.run.start'};
const RUN_TOOLS=[
  {name:'schematic.run.start',description:'Start a run of the current document (never changes it). Returns a run receipt with the new run handle; budget at most 1000000.',inputSchema:{type:'object',properties:{inputs:{type:'array',items:{type:'object',properties:{entity:{type:'string'},point:{type:'string'},channel:{type:'string'},value:{type:'boolean'},at:{type:'integer',minimum:0}},required:['entity','point','value','at'],additionalProperties:false}},seed:{type:'string'},budget:{type:'integer',minimum:0,maximum:1000000},tickMs:{type:'number',exclusiveMinimum:0,description:'milliseconds per tick (default 1); a Wire without a stored delay waits latencyMs / tickMs ticks'}},additionalProperties:false}},
  {name:'schematic.run.step',description:'Process one tick of a run. Returns a run receipt.',inputSchema:{type:'object',properties:{handle},required:['handle'],additionalProperties:false}},
  {name:'schematic.run.settle',description:'Step a run until quiet, oscillating or budget spent. Returns a run receipt.',inputSchema:{type:'object',properties:{handle},required:['handle'],additionalProperties:false}},
  {name:'schematic.run.trace',description:'The trace of a run (.sovtrace), in a run receipt.',inputSchema:{type:'object',properties:{handle},required:['handle'],additionalProperties:false}},
  {name:'schematic.state.query',description:'Records of a run whose subject matches; passive. Returns a run receipt.',inputSchema:{type:'object',properties:{handle,entity:{type:'string',minLength:1},point:{type:'string',minLength:1},channel:{type:'string',minLength:1},observable:{type:'string',minLength:1}},required:['handle','entity','observable'],additionalProperties:false}},
  {name:'schematic.run.replay',description:'Replay a trace against the current document. Returns a run receipt.',inputSchema:{type:'object',properties:{trace:{type:'object'}},required:['trace'],additionalProperties:false}}
];
function runTool(name,args){
  if(name==='schematic.run.start')return runs.start(args);
  if(name==='schematic.run.step')return runs.step(args.handle);
  if(name==='schematic.run.settle')return runs.settle(args.handle);
  if(name==='schematic.run.trace')return runs.trace(args.handle);
  if(name==='schematic.state.query'){const {handle,...subject}=args;return runs.query(handle,subject)}
  if(name==='schematic.run.replay')return runs.replay(args.trace);
  return null;
}
let historyUndo=[],historyRedo=[];
const cloneDoc=()=>Data.makeDocument(Data.clone(documentState));
function recordHistory(snapshot){historyUndo.push(snapshot);if(historyUndo.length>120)historyUndo.shift();historyRedo=[]}
function pushHistory(){recordHistory(cloneDoc())}
function checkpointStore(){documentState.meta=documentState.meta||{};if(!Array.isArray(documentState.meta.checkpoints))documentState.meta.checkpoints=[];return documentState.meta.checkpoints}
function saveDocument(){
  fs.mkdirSync(path.dirname(FILE),{recursive:true});
  const tmp=FILE+'.tmp';fs.writeFileSync(tmp,JSON.stringify(documentState,null,2));fs.renameSync(tmp,FILE);
}
function json(res,status,value,headers={}){
  const body=JSON.stringify(value);
  res.writeHead(status,{'content-type':'application/json; charset=utf-8','content-length':Buffer.byteLength(body),'access-control-allow-origin':'*',...headers});res.end(body);
}
function bodyJson(req){return new Promise((resolve,reject)=>{let chunks='';req.setEncoding('utf8');req.on('data',c=>{chunks+=c;if(chunks.length>5_000_000){reject(new Error('request too large'));req.destroy()}});req.on('end',()=>{try{resolve(chunks?JSON.parse(chunks):{})}catch(e){reject(e)}});req.on('error',reject)})}
function rpcResult(id,result){return {jsonrpc:'2.0',id,result}}
function rpcError(id,code,message,data){return {jsonrpc:'2.0',id,error:{code,message,...(data===undefined?{}:{data})}}}
function toolPayload(value,isError=false,image=null){
  // A picture goes back as image content so an agent that can see receives it as an image.
  if(image){const {png,...rest}=value;return {content:[{type:'image',data:image,mimeType:'image/png'},{type:'text',text:JSON.stringify(rest,null,2)}],structuredContent:rest,isError}}
  return {content:[{type:'text',text:JSON.stringify(value,null,2)}],structuredContent:value,isError}}
// Pictures and layout metrics need a browser; the server asks scripts/render_service.py, which
// runs the editor's own renderer in headless Chromium. Without one the call is refused, typed.
const RENDER_PYTHON=process.env.SOV_RENDER_PYTHON||'python3';
function renderDocument(formats,args={}){
  return new Promise(resolve=>{
    let out='',err='';const child=spawn(RENDER_PYTHON,[path.join(HERE,'../scripts/render_service.py')],{cwd:path.join(HERE,'..')});
    const timer=setTimeout(()=>{child.kill();resolve({ok:false,code:'RENDER_TIMEOUT',message:'render took longer than 90s'})},90000);
    child.stdout.on('data',d=>out+=d);child.stderr.on('data',d=>err+=d);
    child.on('error',e=>{clearTimeout(timer);resolve({ok:false,code:'RENDERER_UNAVAILABLE',message:`cannot start ${RENDER_PYTHON}: ${e.message}`})});
    child.on('close',()=>{clearTimeout(timer);try{resolve(JSON.parse(out.trim().split('\n').pop()))}catch(_){resolve({ok:false,code:'RENDER_FAILED',message:(err||out).trim().split('\n').pop()||'no output'})}});
    child.stdin.end(JSON.stringify({document:Data.clone(documentState),formats,appearance:args.appearance||'light',scale:args.scale??2,pad:args.pad??48,view:args.view||null,legend:args.legend===true||args.legend==='true'||args.legend==='1',narration:args.narration!=null&&args.narration!==''&&Number.isInteger(Number(args.narration))?Number(args.narration):null}));
  });
}
const RENDER_TOOLS=[
  {name:'schematic.render',description:'Render the document as the editor exports it: format svg (text) or png (an image, returned as image content for agents that can see). appearance light|dark; scale for png.',inputSchema:{type:'object',properties:{format:{type:'string',enum:['svg','png']},appearance:{type:'string',enum:['light','dark']},scale:{type:'number',minimum:.25,maximum:4},view:{type:'string',description:'A layout id (schematic.layout op list); default: the document\'s default layout'},legend:{type:'boolean',description:'Put the legend (what the marks, colours, glyphs and shapes used mean) below the picture'},narration:{type:'integer',minimum:0,description:'Put narration line i below the picture'}},additionalProperties:false}},
  {name:'schematic.layout.metrics',description:'Measure how the document presents (LAYOUT-MODEL.md §5): a 0-10 score and every finding (overflow, collisions, route escapes, crossings, jogs, unmarked junctions...), each naming the ids it measured.',inputSchema:{type:'object',properties:{view:{type:'string'}},additionalProperties:false}}
];
async function executeRenderTool(name,args={}){
  if(name==='schematic.layout.metrics'){const r=await renderDocument(['metrics'],args);return r.ok?{ok:true,value:r.metrics,mutates:false}:{ok:false,value:r,mutates:false}}
  const format=args.format==='png'?'png':'svg';const r=await renderDocument([format,'metrics'],args);
  if(!r.ok)return {ok:false,value:r,mutates:false};
  return {ok:true,value:format==='png'?{format,png:r.png,score:r.metrics.score,counts:r.metrics.counts}:{format,svg:r.svg,score:r.metrics.score,counts:r.metrics.counts},mutates:false,image:format==='png'?r.png:null};
}
function executeTool(name,args={}){
  const ran=runTool(name,args);
  if(ran)return {ok:ran.ok,value:ran,mutates:false};
  if(RENDER_TOOLS.some(t=>t.name===name))return executeRenderTool(name,args);
  if(name==='schematic.layout'){
    const {op,...rest}=args,readOnly=Layout.isReadOnly(op),before=readOnly?null:cloneDoc();
    const value=Layout.execute(documentState,op,rest);
    if(value.ok&&!readOnly){recordHistory(before);Data.touch(documentState)}
    return {ok:value.ok!==false,value,mutates:value.ok!==false&&!readOnly};
  }
  if(graphSession.names.includes(name)){const value=graphSession.execute(name,documentState,args);return {ok:value.ok!==false,value,mutates:false}}
  if(name==='schematic.history.undo'){const prev=historyUndo.pop();if(!prev)return {ok:false,value:{error:'Nothing to undo'},mutates:false};historyRedo.push(cloneDoc());Data.replaceDocument(documentState,prev);return {ok:true,value:Data.clone(documentState),mutates:true}}
  if(name==='schematic.history.redo'){const next=historyRedo.pop();if(!next)return {ok:false,value:{error:'Nothing to redo'},mutates:false};historyUndo.push(cloneDoc());Data.replaceDocument(documentState,next);return {ok:true,value:Data.clone(documentState),mutates:true}}
  if(name==='schematic.checkpoint.list')return {ok:true,value:checkpointStore().map(({document,...meta})=>meta),mutates:false};
  if(name==='schematic.checkpoint.create'){pushHistory();const store=checkpointStore(),snap=cloneDoc();snap.meta=snap.meta||{};snap.meta.checkpoints=[];const cp={id:`cp-${Date.now()}`,name:String(args.name||`Checkpoint ${store.length+1}`),createdAt:new Date().toISOString(),revision:documentState.revision||0,document:snap};store.push(cp);Data.touch(documentState);return {ok:true,value:{...cp,document:undefined},mutates:true}}
  if(name==='schematic.checkpoint.restore'){const cp=checkpointStore().find(x=>x.id===args.id);if(!cp)return {ok:false,value:{error:'Checkpoint not found'},mutates:false};pushHistory();const store=Data.clone(checkpointStore());Data.replaceDocument(documentState,cp.document);documentState.meta=documentState.meta||{};documentState.meta.checkpoints=store;Data.touch(documentState);return {ok:true,value:Data.clone(documentState),mutates:true}}
  if(name==='schematic.document.get')return {ok:true,value:Data.clone(documentState),mutates:false};
  if(name==='schematic.markers')return {ok:true,value:Data.markersFor(documentState),mutates:false};
  if(name==='schematic.document.replace'){
    const incoming=Data.makeDocument(args.document||{}),valid=Data.validateDocument(incoming);
    if(!valid.ok)return {ok:false,value:{error:valid.errors.join('; ')},mutates:false};
    pushHistory();Data.replaceDocument(documentState,incoming);Data.touch(documentState);return {ok:true,value:Data.clone(documentState),mutates:true};
  }
  const map={
    'schematic.list':{op:'list'},'schematic.get':{op:'read'},'schematic.create':{op:'create'},'schematic.update':{op:'update'},'schematic.delete':{op:'delete'}
  }[name];
  if(!map)return {ok:false,value:{error:`Unknown tool: ${name}`},mutates:false};
  const mutates=['create','update','delete'].includes(map.op),before=mutates?cloneDoc():null;
  const receipt=Data.applyOperation(documentState,{schema:Data.OPERATION_SCHEMA,id:`mcp-${Date.now()}`,op:map.op,resource:args.resource,resourceId:args.id??null,value:args.value??null,patch:args.patch??null,query:args.query??{},ifRevision:args.ifRevision});
  if(receipt.ok&&mutates)recordHistory(before);
  return {ok:receipt.ok,value:receipt,mutates:receipt.ok&&mutates};
}
async function handleMcp(req,res){
  let rpc;try{rpc=await bodyJson(req)}catch(e){return json(res,400,rpcError(null,-32700,'Parse error',e.message),{'MCP-Protocol-Version':MCP_VERSION})}
  const id=rpc.id??null,method=rpc.method;
  if(method==='server/discover')return json(res,200,rpcResult(id,{protocolVersion:MCP_VERSION,serverInfo:{name:'soveraeign-schematic',version:'0.1.24'},capabilities:{tools:{listChanged:false}},instructions:'CRUD against SOV Schematic document@0.1. File packages use package@0.1.'}),{'MCP-Protocol-Version':MCP_VERSION});
  if(method==='tools/list'){const extra=[{name:'schematic.markers',description:'List validation markers for the current document, derived from schematic.document validation.',inputSchema:{type:'object',properties:{},additionalProperties:false}},{name:'schematic.history.undo',description:'Undo the most recent server mutation.',inputSchema:{type:'object',properties:{},additionalProperties:false}},{name:'schematic.history.redo',description:'Redo the most recently undone server mutation.',inputSchema:{type:'object',properties:{},additionalProperties:false}},{name:'schematic.checkpoint.list',description:'List persisted checkpoints.',inputSchema:{type:'object',properties:{},additionalProperties:false}},{name:'schematic.checkpoint.create',description:'Create a named checkpoint inside the .sov document.',inputSchema:{type:'object',properties:{name:{type:'string'}},additionalProperties:false}},{name:'schematic.checkpoint.restore',description:'Restore a checkpoint by id.',inputSchema:{type:'object',properties:{id:{type:'string'}},required:['id'],additionalProperties:false}}];return json(res,200,rpcResult(id,{tools:[...Data.operationTools(),...extra,...RUN_TOOLS,...Graph.tools(),...RENDER_TOOLS,Layout.tool()]}),{'MCP-Protocol-Version':MCP_VERSION});}
  if(method==='tools/call'){
    const name=rpc.params?.name,args=rpc.params?.arguments||{};
    const result=await executeTool(name,args);if(result.mutates)saveDocument();
    return json(res,200,rpcResult(id,toolPayload(result.value,!result.ok,result.image||null)),{'MCP-Protocol-Version':MCP_VERSION});
  }
  return json(res,404,rpcError(id,-32601,'Method not found'),{'MCP-Protocol-Version':MCP_VERSION});
}
function resourceFromPath(segment){return ({components:'component',wires:'wire',references:'reference'})[segment]||null}
async function handleApi(req,res,url){
  const parts=url.pathname.split('/').filter(Boolean);
  if(url.pathname==='/api/v1/formats'&&req.method==='GET')return json(res,200,{document:Data.DOCUMENT_SCHEMA,package:Data.PACKAGE_SCHEMA,workspace:Data.WORKSPACE_SCHEMA,operation:Data.OPERATION_SCHEMA,receipt:Data.RECEIPT_SCHEMA,resources:Object.keys(Data.RESOURCE_KEYS)});
  if(url.pathname==='/api/v1/document'){
    if(req.method==='GET')return json(res,200,Data.clone(documentState));
    if(req.method==='PUT'){
      const input=await bodyJson(req),incoming=Data.makeDocument(input),valid=Data.validateDocument(incoming);if(!valid.ok)return json(res,400,{ok:false,errors:valid.errors});
      const before=cloneDoc();Data.replaceDocument(documentState,incoming);Data.touch(documentState);recordHistory(before);saveDocument();return json(res,200,Data.clone(documentState));
    }
  }
  // Runs, addressed by handle: a receipt always; 201 on a start, 404 for an unknown handle, 400 for a
  // body that is not JSON or a path that does not decode, 409 for any other refusal.
  if(parts[0]==='api'&&parts[1]==='v1'&&(parts[2]==='runs'||parts[2]==='replay')){
    const send=(receipt,status=200)=>json(res,receipt.ok?status:receipt.error?.code==='RUN_NOT_FOUND'?404:409,receipt);
    const malformed=(operation,message)=>{json(res,400,State.runReceipt(operation,null,{ok:false,code:'INPUT_INVALID',message}));return true};
    const body=async operation=>{try{return {value:await bodyJson(req)}}catch(e){return {refused:malformed(operation,`the request body is not JSON: ${String(e?.message||e)}`)}}};
    const verb=parts[4],route=parts[2]==='replay'&&parts.length===3&&req.method==='POST'?'schematic.run.replay'
      :parts[2]==='runs'&&parts.length===3&&req.method==='POST'?'schematic.run.start'
      :parts[2]==='runs'&&parts.length===5?({'step:POST':'schematic.run.step','settle:POST':'schematic.run.settle','trace:GET':'schematic.run.trace','query:POST':'schematic.state.query'})[`${verb}:${req.method}`]:undefined;
    if(!route)return json(res,404,{error:'not found'});
    let id;
    if(parts.length===5){try{id=decodeURIComponent(parts[3])}catch(e){malformed(route,`the run handle in the path does not decode: ${String(e?.message||e)}`);return}}
    if(route==='schematic.run.step')return send(runs.step(id));
    if(route==='schematic.run.settle')return send(runs.settle(id));
    if(route==='schematic.run.trace')return send(runs.trace(id));
    const b=await body(route);if(b.refused)return;
    if(route==='schematic.run.replay')return send(runs.replay(b.value));
    if(route==='schematic.run.start')return send(runs.start(b.value),201);
    return send(runs.query(id,b.value));
  }
  if(req.method==='GET'&&(url.pathname==='/api/v1/render.svg'||url.pathname==='/api/v1/render.png')){
    const format=url.pathname.endsWith('.png')?'png':'svg',r=await renderDocument([format],Object.fromEntries(url.searchParams.entries()));
    if(!r.ok)return json(res,r.code==='RENDERER_UNAVAILABLE'?503:500,r);
    const body=format==='png'?Buffer.from(r.png,'base64'):Buffer.from(r.svg,'utf8');
    res.writeHead(200,{'content-type':format==='png'?'image/png':'image/svg+xml; charset=utf-8','content-length':body.length,'access-control-allow-origin':'*'});return res.end(body);
  }
  if(req.method==='GET'&&url.pathname==='/api/v1/layout/metrics'){const r=await renderDocument(['metrics']);return r.ok?json(res,200,r.metrics):json(res,r.code==='RENDERER_UNAVAILABLE'?503:500,r)}
  if(parts[2]==='graph'&&parts[3]&&['GET','POST'].includes(req.method)){
    const args=req.method==='POST'?await bodyJson(req):Object.fromEntries(url.searchParams.entries());
    const value=graphSession.execute('schematic.graph.query',documentState,{verb:parts[3],args});return json(res,value.ok===false?400:200,value);
  }
  if(parts[2]==='sim'&&parts[3]&&req.method==='POST'){
    const value=graphSession.execute(`schematic.sim.${parts[3]}`,documentState,await bodyJson(req));return json(res,value.ok===false?(value.code==='UNKNOWN_TOOL'?404:400):200,value);
  }
  if(parts[2]==='sim'&&parts[3]==='inspect'&&req.method==='GET'){
    const value=graphSession.execute('schematic.sim.inspect',documentState,Object.fromEntries(url.searchParams.entries()));return json(res,value.ok===false?400:200,value);
  }
  if(parts[0]==='api'&&parts[1]==='v1'&&parts[2]){
    const resource=resourceFromPath(parts[2]);if(!resource)return json(res,404,{error:'resource not found'});
    const id=parts[3]||null;
    if(req.method==='GET'&&!id){const query=Object.fromEntries(url.searchParams.entries());return json(res,200,Data.list(documentState,resource,query))}
    if(req.method==='GET'&&id){const value=Data.read(documentState,resource,id);return value?json(res,200,value):json(res,404,{error:'not found'})}
    if(req.method==='POST'&&!id){const before=cloneDoc(),receipt=Data.applyOperation(documentState,{op:'create',resource,value:await bodyJson(req)});if(receipt.ok){recordHistory(before);saveDocument()}return json(res,receipt.ok?201:400,receipt)}
    if(req.method==='PATCH'&&id){const before=cloneDoc(),receipt=Data.applyOperation(documentState,{op:'update',resource,resourceId:id,patch:await bodyJson(req)});if(receipt.ok){recordHistory(before);saveDocument()}return json(res,receipt.ok?200:400,receipt)}
    if(req.method==='DELETE'&&id){const before=cloneDoc(),receipt=Data.applyOperation(documentState,{op:'delete',resource,resourceId:id});if(receipt.ok){recordHistory(before);saveDocument()}return json(res,receipt.ok?200:400,receipt)}
  }
  return json(res,404,{error:'not found'});
}

const server=http.createServer(async(req,res)=>{
  if(req.method==='OPTIONS'){res.writeHead(204,{'access-control-allow-origin':'*','access-control-allow-methods':'GET,POST,PUT,PATCH,DELETE,OPTIONS','access-control-allow-headers':'content-type,mcp-protocol-version,mcp-method,mcp-name'});return res.end()}
  const url=new URL(req.url||'/',`http://${req.headers.host||HOST}`);
  try{
    if(url.pathname==='/mcp'&&req.method==='POST')return await handleMcp(req,res);
    if(url.pathname.startsWith('/api/v1/'))return await handleApi(req,res,url);
    return json(res,200,{name:'soveraeign-schematic',version:'0.1.24',document:FILE,mcp:'/mcp',api:'/api/v1'});
  }catch(error){return json(res,500,{error:String(error.message||error)})}
});
server.listen(PORT,HOST,()=>console.log(`Soveraeign Schematic API + MCP http://${HOST}:${PORT} · ${FILE}`));
