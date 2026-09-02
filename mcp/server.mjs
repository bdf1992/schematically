#!/usr/bin/env node
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const HERE=path.dirname(fileURLToPath(import.meta.url));
// Absolute paths are not valid ESM specifiers on Windows; import by file:// URL everywhere.
await import(pathToFileURL(path.join(HERE,'../src/06-attachment-core.js')).href);
await import(pathToFileURL(path.join(HERE,'../src/05-data-core.js')).href);
const Data=globalThis.SovSchematicData;
if(!Data)throw new Error('SovSchematicData core failed to load');

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
function toolPayload(value,isError=false){return {content:[{type:'text',text:JSON.stringify(value,null,2)}],structuredContent:value,isError}}
function executeTool(name,args={}){
  if(name==='schematic.history.undo'){const prev=historyUndo.pop();if(!prev)return {ok:false,value:{error:'Nothing to undo'},mutates:false};historyRedo.push(cloneDoc());Data.replaceDocument(documentState,prev);return {ok:true,value:Data.clone(documentState),mutates:true}}
  if(name==='schematic.history.redo'){const next=historyRedo.pop();if(!next)return {ok:false,value:{error:'Nothing to redo'},mutates:false};historyUndo.push(cloneDoc());Data.replaceDocument(documentState,next);return {ok:true,value:Data.clone(documentState),mutates:true}}
  if(name==='schematic.checkpoint.list')return {ok:true,value:checkpointStore().map(({document,...meta})=>meta),mutates:false};
  if(name==='schematic.checkpoint.create'){pushHistory();const store=checkpointStore(),snap=cloneDoc();snap.meta=snap.meta||{};snap.meta.checkpoints=[];const cp={id:`cp-${Date.now()}`,name:String(args.name||`Checkpoint ${store.length+1}`),createdAt:new Date().toISOString(),revision:documentState.revision||0,document:snap};store.push(cp);Data.touch(documentState);return {ok:true,value:{...cp,document:undefined},mutates:true}}
  if(name==='schematic.checkpoint.restore'){const cp=checkpointStore().find(x=>x.id===args.id);if(!cp)return {ok:false,value:{error:'Checkpoint not found'},mutates:false};pushHistory();const store=Data.clone(checkpointStore());Data.replaceDocument(documentState,cp.document);documentState.meta=documentState.meta||{};documentState.meta.checkpoints=store;Data.touch(documentState);return {ok:true,value:Data.clone(documentState),mutates:true}}
  if(name==='schematic.document.get')return {ok:true,value:Data.clone(documentState),mutates:false};
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
  if(method==='tools/list'){const extra=[{name:'schematic.history.undo',description:'Undo the most recent server mutation.',inputSchema:{type:'object',properties:{},additionalProperties:false}},{name:'schematic.history.redo',description:'Redo the most recently undone server mutation.',inputSchema:{type:'object',properties:{},additionalProperties:false}},{name:'schematic.checkpoint.list',description:'List persisted checkpoints.',inputSchema:{type:'object',properties:{},additionalProperties:false}},{name:'schematic.checkpoint.create',description:'Create a named checkpoint inside the .sov document.',inputSchema:{type:'object',properties:{name:{type:'string'}},additionalProperties:false}},{name:'schematic.checkpoint.restore',description:'Restore a checkpoint by id.',inputSchema:{type:'object',properties:{id:{type:'string'}},required:['id'],additionalProperties:false}}];return json(res,200,rpcResult(id,{tools:[...Data.operationTools(),...extra]}),{'MCP-Protocol-Version':MCP_VERSION});}
  if(method==='tools/call'){
    const name=rpc.params?.name,args=rpc.params?.arguments||{};
    const result=executeTool(name,args);if(result.mutates)saveDocument();
    return json(res,200,rpcResult(id,toolPayload(result.value,!result.ok)),{'MCP-Protocol-Version':MCP_VERSION});
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
