// The request-handling core, ported out of mcp/server.mjs: every MCP tool, every /api/v1 route,
// history, checkpoints, runs and the root description, with no second copy of the logic for a
// second runtime. This module imports nothing from node: (no node:http, node:fs, node:path,
// node:child_process, node:url); it reads the cores from globalThis (SovSchematicData,
// SovSchematicGraph, SovSchematicStateSpace, SovSchematicSimSurface, SovSchematicLayout),
// which the entrypoint loads first. A hosted entrypoint supplies:
//   store    {read(): string|null, write(text): void}  the document's one durable copy
//   packs    [pack json, ...]                          read at start (data/*.pack.json on Node)
//   render(formats, args) -> Promise<result>           optional; omit it and every render tool
//                                                       and route answers RENDERER_UNAVAILABLE
//   readText(relativePath) -> string                   for schematic.guide's doc sections
//   describe() -> any                                  the root response's `document` field
//   editorHtml                                          the built page; /editor serves it with this
//                                                       document in a sov-served-document tag,
//                                                       /index.html serves it unchanged
//   base     a string, default empty: the path prefix this surface is mounted under (mcp/server.mjs
//            mounts one surface per document at /d/<id> and strips the prefix before handle); it is
//            used only in the root description, so mcp, api and editor read base+'/mcp' and so on
// and gets back {handle(request)}, request being {method, path, query (an object of strings),
// headers (lower-case keys), body (a string or null)}; handle resolves to {status, headers, body}
// where body is a string or a Uint8Array.
import {guide} from './guide.mjs';

export function createSurface({store,packs,render,readText,describe,editorHtml,base=''}){
  const Data=globalThis.SovSchematicData;
  const State=globalThis.SovSchematicStateSpace,Layout=globalThis.SovSchematicLayout;
  const SimSurface=globalThis.SovSchematicSimSurface;
  const MCP_VERSION='2026-07-28';
  // A standard client opens with initialize and names the protocol it speaks; the server answers in
  // that version when it is one it knows, else in its own.
  const MCP_KNOWN=['2024-11-05','2025-03-26','2025-06-18',MCP_VERSION];
  const SERVER_INFO={name:'soveraeign-schematic',version:'0.1.24'};
  const INSTRUCTIONS=`Schematically: a system drawn as typed components joined by wires, which can also run.
Read schematic.guide first (no step, then the step it names). Read a slice with schematic.read
(ids or an area); write many records at once with schematic.apply (one receipt, all or nothing,
$refs for new ids); read schematic.concerns after writing and answer what is open; check with
schematic.markers and schematic.render; run with schematic.run.*.`;

  function loadDocument(){
    const text=store.read();
    if(text===null)return Data.makeDocument({id:'schematic-1'});
    try{return Data.documentFromFilePayload(JSON.parse(text))}catch(_){return Data.makeDocument({id:'schematic-1'})}
  }
  let documentState=loadDocument();
  // Graph queries and the simulation are read-only over the document; one session per surface.
  // The simulation side is the sim surface (src/07-state-surface.js, over the state-space
  // engine, contract 09 of the one-runtime plan); schematic.graph.query still reaches
  // src/07-graph-core.js's graph reading.
  const graphSession=SimSurface.createSession();
  // Runs live beside the document, not in it: an in-memory registry, every run started from the
  // current document, packs read from data/*.pack.json (file-name order) at start.
  const runs=State.createRunRegistry({packs:packs||[],document:()=>Data.clone(documentState)});
  let historyUndo=[],historyRedo=[];
  // Live link (read-only): the browser editor pushes a snapshot of what its operator
  // is looking at. It is observation, never authority - nothing here touches the
  // document, and a snapshot is only ever served back with its own age attached.
  const LIVE_STALE_AFTER_MS=15_000;
  let liveSnapshot=null,liveReceivedAt=null;
  function liveState(){
    if(!liveSnapshot)return {connected:false,reason:'no editor session has pushed a snapshot',ageMs:null,receivedAt:null,stale:null,snapshot:null};
    const ageMs=Date.now()-liveReceivedAt;
    return {connected:ageMs<=LIVE_STALE_AFTER_MS,ageMs,receivedAt:new Date(liveReceivedAt).toISOString(),stale:ageMs>LIVE_STALE_AFTER_MS,snapshot:liveSnapshot};
  }
  function liveSelectionState(){
    const state=liveState();
    if(!state.snapshot)return state;
    const {document:_document,...rest}=state.snapshot;
    return {...state,snapshot:rest};
  }
  const cloneDoc=()=>Data.makeDocument(Data.clone(documentState));
  function recordHistory(snapshot){historyUndo.push(snapshot);if(historyUndo.length>120)historyUndo.shift();historyRedo=[]}
  function pushHistory(){recordHistory(cloneDoc())}
  function checkpointStore(){documentState.meta=documentState.meta||{};if(!Array.isArray(documentState.meta.checkpoints))documentState.meta.checkpoints=[];return documentState.meta.checkpoints}
  function saveDocument(){store.write(JSON.stringify(documentState,null,2))}

  function jsonResponse(status,value,headers={}){
    return {status,headers:{'content-type':'application/json; charset=utf-8','access-control-allow-origin':'*',...headers},body:JSON.stringify(value)};
  }
  function parseBody(body){return body?JSON.parse(body):{}}
  function rpcResult(id,result){return {jsonrpc:'2.0',id,result}}
  function rpcError(id,code,message,data){return {jsonrpc:'2.0',id,error:{code,message,...(data===undefined?{}:{data})}}}
  function toolPayload(value,isError=false,image=null){
    // A picture goes back as image content so an agent that can see receives it as an image.
    if(image){const {png,...rest}=value;return {content:[{type:'image',data:image,mimeType:'image/png'},{type:'text',text:JSON.stringify(rest,null,2)}],structuredContent:rest,isError}}
    return {content:[{type:'text',text:JSON.stringify(value,null,2)}],structuredContent:value,isError}}

  const HANDLE_SCHEMA={type:'string',minLength:1,description:'the run handle (<runId>.<n>) from schematic.run.start'};
  const RUN_TOOLS=[
    {name:'schematic.run.start',description:'Start a run of the current document (never changes it). Returns a run receipt with the new run handle; budget at most 1000000.',inputSchema:{type:'object',properties:{inputs:{type:'array',items:{type:'object',properties:{entity:{type:'string'},point:{type:'string'},channel:{type:'string'},value:{type:'boolean'},at:{type:'integer',minimum:0}},required:['entity','point','value','at'],additionalProperties:false}},seed:{type:'string'},budget:{type:'integer',minimum:0,maximum:1000000},tickMs:{type:'integer',minimum:1,description:'whole milliseconds per tick (default 1); a Wire without a stored delay waits latencyMs / tickMs ticks, rounded'}},additionalProperties:false}},
    {name:'schematic.run.step',description:'Process one tick of a run. Returns a run receipt.',inputSchema:{type:'object',properties:{handle:HANDLE_SCHEMA},required:['handle'],additionalProperties:false}},
    {name:'schematic.run.settle',description:'Step a run until quiet, oscillating or budget spent. Returns a run receipt.',inputSchema:{type:'object',properties:{handle:HANDLE_SCHEMA},required:['handle'],additionalProperties:false}},
    {name:'schematic.run.trace',description:'The trace of a run (.sovtrace), in a run receipt.',inputSchema:{type:'object',properties:{handle:HANDLE_SCHEMA},required:['handle'],additionalProperties:false}},
    {name:'schematic.state.query',description:'Records of a run whose subject matches; passive. Returns a run receipt.',inputSchema:{type:'object',properties:{handle:HANDLE_SCHEMA,entity:{type:'string',minLength:1},point:{type:'string',minLength:1},channel:{type:'string',minLength:1},observable:{type:'string',minLength:1}},required:['handle','entity','observable'],additionalProperties:false}},
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

  function renderUnavailable(){return {ok:false,code:'RENDERER_UNAVAILABLE',message:render?'render refused':'no render adapter configured for this surface'}}
  async function renderDocument(formats,args={}){
    if(!render)return renderUnavailable();
    return render(formats,{...args,document:Data.clone(documentState)});
  }
  const RENDER_TOOLS=[
    {name:'schematic.render',description:'Render the document as the editor exports it: format svg (text) or png (an image, returned as image content for agents that can see). appearance light|dark; scale for png.',inputSchema:{type:'object',properties:{format:{type:'string',enum:['svg','png']},appearance:{type:'string',enum:['light','dark']},scale:{type:'number',minimum:.25,maximum:4},view:{type:'string',description:'A layout id (schematic.layout op list); default: the document\'s default layout'},legend:{type:'boolean',description:'Put the legend (what the marks, colours, glyphs and shapes used mean) below the picture'},narration:{type:'integer',minimum:0,description:'Put narration line i below the picture'}},additionalProperties:false}},
    {name:'schematic.layout.metrics',description:'Measure how the document presents (LAYOUT-MODEL.md §5): a 0-10 score and every finding (overflow, collisions, route escapes, crossings, jogs, unmarked junctions...), each naming the ids it measured.',inputSchema:{type:'object',properties:{view:{type:'string'}},additionalProperties:false}}
  ];
  const AUTHOR_TOOLS=[
    {name:'schematic.guide',description:'The authoring guide, one step at a time: call with no step for the index, then the step it names (model, palette, concerns, apply, layout, check, review, layout-review).',inputSchema:{type:'object',properties:{step:{type:'string'}},additionalProperties:false}},
    {name:'schematic.read',description:'Read a slice of the document in its stored form: the components and wires named by ids, or every component placed inside an area (with what sits on their interiors) and the wires among them; crossing lists wires that leave the slice.',inputSchema:{type:'object',properties:{ids:{type:'array',items:{type:'string'}},area:{type:'object',properties:{x:{type:'number'},y:{type:'number'},width:{type:'number'},height:{type:'number'}},required:['x','y','width','height'],additionalProperties:false}},additionalProperties:false}},
    {name:'schematic.apply',description:'Write many records as one: creates, updates and deletes applied in order, all or none, one revision and one receipt. A create may omit its id and name itself ref "$name" for later operations; result.ids maps each $name to its id. See schematic.guide step apply.',inputSchema:{type:'object',properties:{operations:{type:'array',minItems:1,items:{type:'object',properties:{op:{type:'string',enum:['create','update','delete']},resource:{type:'string',enum:['component','wire','reference']},id:{type:'string'},ref:{type:'string',pattern:'^\\$.+'},value:{type:'object'},patch:{type:'object'}},required:['op','resource'],additionalProperties:false}},ifRevision:{type:'number',description:'Document revision the caller observed; refused if the document has moved on.'}},required:['operations'],additionalProperties:false}}
  ];
  function executeAuthorTool(name,args={}){
    if(name==='schematic.guide'){const value=guide(args.step||null,{readText,symbols:Data.symbolIds()});return {ok:value.ok,value,mutates:false}}
    if(name==='schematic.read'){const value=Data.readScope(documentState,args);return {ok:value.ok,value,mutates:false}}
    if(name==='schematic.apply'){
      const before=cloneDoc(),receipt=Data.applyBatch(documentState,{id:`mcp-${Date.now()}`,operations:args.operations,ifRevision:args.ifRevision});
      if(receipt.ok)recordHistory(before);
      return {ok:receipt.ok,value:receipt,mutates:receipt.ok};
    }
    // Concerns: the report and the one verb that answers are the data core's; nothing is decided here.
    if(name==='schematic.concerns')return {ok:true,value:Data.concernReport(documentState,{open:args.open===true}),mutates:false};
    if(name==='schematic.concerns.answer'){
      const before=cloneDoc(),receipt=Data.answerConcerns(documentState,{id:`mcp-${Date.now()}`,answers:args.answers,ifRevision:args.ifRevision});
      if(receipt.ok)recordHistory(before);
      return {ok:receipt.ok,value:receipt,mutates:receipt.ok};
    }
    return null;
  }
  async function executeRenderTool(name,args={}){
    if(name==='schematic.layout.metrics'){const r=await renderDocument(['metrics'],args);return r.ok?{ok:true,value:r.metrics,mutates:false}:{ok:false,value:r,mutates:false}}
    const format=args.format==='png'?'png':'svg';const r=await renderDocument([format,'metrics'],args);
    if(!r.ok)return {ok:false,value:r,mutates:false};
    return {ok:true,value:format==='png'?{format,png:r.png,score:r.metrics.score,counts:r.metrics.counts}:{format,svg:r.svg,score:r.metrics.score,counts:r.metrics.counts},mutates:false,image:format==='png'?r.png:null};
  }
  function executeTool(name,args={}){
    if(name==='schematic.live.get')return {ok:true,value:liveState(),mutates:false};
    if(name==='schematic.live.selection')return {ok:true,value:liveSelectionState(),mutates:false};
    const ran=runTool(name,args);
    if(ran)return {ok:ran.ok,value:ran,mutates:false};
    const authored=executeAuthorTool(name,args);if(authored)return authored;
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
  async function handleMcp(request){
    let rpc;try{rpc=parseBody(request.body)}catch(e){return jsonResponse(400,rpcError(null,-32700,'Parse error',e.message),{'mcp-protocol-version':MCP_VERSION})}
    const id=rpc.id??null,method=rpc.method;
    if(method==='initialize'){
      const asked=rpc.params?.protocolVersion,version=MCP_KNOWN.includes(asked)?asked:MCP_VERSION;
      return jsonResponse(200,rpcResult(id,{protocolVersion:version,serverInfo:SERVER_INFO,capabilities:{tools:{listChanged:false}},instructions:INSTRUCTIONS}),{'mcp-protocol-version':version});
    }
    // A notification has no id and wants no answer.
    if(typeof method==='string'&&method.startsWith('notifications/'))return {status:202,headers:{'access-control-allow-origin':'*'},body:''};
    if(method==='ping')return jsonResponse(200,rpcResult(id,{}),{'mcp-protocol-version':MCP_VERSION});
    if(method==='server/discover')return jsonResponse(200,rpcResult(id,{protocolVersion:MCP_VERSION,serverInfo:SERVER_INFO,capabilities:{tools:{listChanged:false}},instructions:INSTRUCTIONS}),{'mcp-protocol-version':MCP_VERSION});
    if(method==='tools/list'){const extra=[{name:'schematic.markers',description:'List validation markers for the current document, derived from schematic.document validation.',inputSchema:{type:'object',properties:{},additionalProperties:false}},{name:'schematic.concerns',description:'The questions the document\'s notation declares for the document, its components and its wires, each row answered or open with the question to answer; open true returns only the open rows.',inputSchema:{type:'object',properties:{open:{type:'boolean',description:'Only the rows still open; the answered and open counts stay those of every row.'}},additionalProperties:false}},{name:'schematic.concerns.answer',description:'Set or remove answers to declared concerns on the document, components and wires in one call: all or none, one revision and one receipt whose result.report counts answered and open.',inputSchema:{type:'object',properties:{answers:{type:'array',minItems:1,items:{type:'object',properties:{concern:{type:'string',minLength:1,description:'A concern id from a schematic.concerns row'},target:{type:['string','null'],description:'The row\'s target: the id of a component or a wire; absent or null for the document'},answer:{type:['string','null'],description:'A non-empty string sets the answer; null removes it'}},required:['concern','answer'],additionalProperties:false}},ifRevision:{type:'number',description:'Document revision the caller observed; refused if the document has moved on.'}},required:['answers'],additionalProperties:false}},{name:'schematic.history.undo',description:'Undo the most recent server mutation.',inputSchema:{type:'object',properties:{},additionalProperties:false}},{name:'schematic.history.redo',description:'Redo the most recently undone server mutation.',inputSchema:{type:'object',properties:{},additionalProperties:false}},{name:'schematic.checkpoint.list',description:'List persisted checkpoints.',inputSchema:{type:'object',properties:{},additionalProperties:false}},{name:'schematic.checkpoint.create',description:'Create a named checkpoint inside the .sov document.',inputSchema:{type:'object',properties:{name:{type:'string'}},additionalProperties:false}},{name:'schematic.checkpoint.restore',description:'Restore a checkpoint by id.',inputSchema:{type:'object',properties:{id:{type:'string'}},required:['id'],additionalProperties:false}},{name:'schematic.live.selection',description:'What the live browser editor currently has selected, with the selected record and no document body. Returns connected:false when no editor is pushing.',inputSchema:{type:'object',properties:{},additionalProperties:false}},{name:'schematic.live.get',description:'The full live editor snapshot: file identity, revision, camera, appearance, selection, and the in-browser document. Reflects unsaved editor state, not the server file.',inputSchema:{type:'object',properties:{},additionalProperties:false}}];return jsonResponse(200,rpcResult(id,{tools:[...AUTHOR_TOOLS,...Data.operationTools(),...extra,...RUN_TOOLS,...SimSurface.tools(),...RENDER_TOOLS,Layout.tool()]}),{'mcp-protocol-version':MCP_VERSION});}
    if(method==='tools/call'){
      const name=rpc.params?.name,args=rpc.params?.arguments||{};
      const result=await executeTool(name,args);if(result.mutates)saveDocument();
      return jsonResponse(200,rpcResult(id,toolPayload(result.value,!result.ok,result.image||null)),{'mcp-protocol-version':MCP_VERSION});
    }
    return jsonResponse(404,rpcError(id,-32601,'Method not found'),{'mcp-protocol-version':MCP_VERSION});
  }
  function resourceFromPath(segment){return ({components:'component',wires:'wire',references:'reference'})[segment]||null}
  async function handleApi(request){
    const parts=request.path.split('/').filter(Boolean),query=request.query||{};
    if(request.path==='/api/v1/formats'&&request.method==='GET')return jsonResponse(200,{document:Data.DOCUMENT_SCHEMA,package:Data.PACKAGE_SCHEMA,workspace:Data.WORKSPACE_SCHEMA,operation:Data.OPERATION_SCHEMA,receipt:Data.RECEIPT_SCHEMA,resources:Object.keys(Data.RESOURCE_KEYS)});
    if(request.path==='/api/v1/live'){
      if(request.method==='GET')return jsonResponse(200,query.selection==='1'?liveSelectionState():liveState());
      if(request.method==='POST'){
        let body;try{body=parseBody(request.body)}catch(e){return jsonResponse(400,{ok:false,error:`the request body is not JSON: ${String(e?.message||e)}`})}
        if(body?.schema!=='soveraeign.schematic/live@0.1')return jsonResponse(400,{ok:false,error:'expected schema soveraeign.schematic/live@0.1'});
        liveSnapshot=body;liveReceivedAt=Date.now();
        return jsonResponse(202,{ok:true,receivedAt:new Date(liveReceivedAt).toISOString()});
      }
    }
    if(request.path==='/api/v1/document'){
      if(request.method==='GET')return jsonResponse(200,Data.clone(documentState));
      if(request.method==='PUT'){
        const input=parseBody(request.body),incoming=Data.makeDocument(input),valid=Data.validateDocument(incoming);if(!valid.ok)return jsonResponse(400,{ok:false,errors:valid.errors});
        const before=cloneDoc();Data.replaceDocument(documentState,incoming);Data.touch(documentState);recordHistory(before);saveDocument();return jsonResponse(200,Data.clone(documentState));
      }
    }
    if(request.path==='/api/v1/guide'&&request.method==='GET'){const r=executeAuthorTool('schematic.guide',{step:query.step||null});return jsonResponse(r.ok?200:404,r.value)}
    if(request.path==='/api/v1/read'&&request.method==='POST'){const r=executeAuthorTool('schematic.read',parseBody(request.body));return jsonResponse(r.ok?200:400,r.value)}
    if(request.path==='/api/v1/apply'&&request.method==='POST'){const r=executeAuthorTool('schematic.apply',parseBody(request.body));if(r.mutates)saveDocument();return jsonResponse(r.ok?200:(r.value.error?.message||'').startsWith('Stale revision')?409:400,r.value)}
    // Concerns: GET the report (open=1 for the open rows); POST {answers, ifRevision} answers 200
    // with the receipt, 409 for a stale revision, 400 for any other refusal.
    if(request.path==='/api/v1/concerns'&&request.method==='GET')return jsonResponse(200,executeAuthorTool('schematic.concerns',{open:query.open==='1'}).value);
    if(request.path==='/api/v1/concerns'&&request.method==='POST'){const r=executeAuthorTool('schematic.concerns.answer',parseBody(request.body));if(r.mutates)saveDocument();return jsonResponse(r.ok?200:(r.value.error?.message||'').startsWith('Stale revision')?409:400,r.value)}
    // Runs, addressed by handle: a receipt always; 201 on a start, 404 for an unknown handle, 400 for a
    // body that is not JSON or a path that does not decode, 409 for any other refusal.
    if(parts[0]==='api'&&parts[1]==='v1'&&(parts[2]==='runs'||parts[2]==='replay')){
      const send=(receipt,status=200)=>jsonResponse(receipt.ok?status:receipt.error?.code==='RUN_NOT_FOUND'?404:409,receipt);
      const malformed=(operation,message)=>jsonResponse(400,State.runReceipt(operation,null,{ok:false,code:'INPUT_INVALID',message}));
      const body=operation=>{try{return {value:parseBody(request.body)}}catch(e){return {refused:malformed(operation,`the request body is not JSON: ${String(e?.message||e)}`)}}};
      const verb=parts[4],route=parts[2]==='replay'&&parts.length===3&&request.method==='POST'?'schematic.run.replay'
        :parts[2]==='runs'&&parts.length===3&&request.method==='POST'?'schematic.run.start'
        :parts[2]==='runs'&&parts.length===5?({'step:POST':'schematic.run.step','settle:POST':'schematic.run.settle','trace:GET':'schematic.run.trace','query:POST':'schematic.state.query'})[`${verb}:${request.method}`]:undefined;
      if(!route)return jsonResponse(404,{error:'not found'});
      let id;
      if(parts.length===5){try{id=decodeURIComponent(parts[3])}catch(e){return malformed(route,`the run handle in the path does not decode: ${String(e?.message||e)}`)}}
      if(route==='schematic.run.step')return send(runs.step(id));
      if(route==='schematic.run.settle')return send(runs.settle(id));
      if(route==='schematic.run.trace')return send(runs.trace(id));
      const b=body(route);if(b.refused)return b.refused;
      if(route==='schematic.run.replay')return send(runs.replay(b.value));
      if(route==='schematic.run.start')return send(runs.start(b.value),201);
      return send(runs.query(id,b.value));
    }
    if(request.method==='GET'&&(request.path==='/api/v1/render.svg'||request.path==='/api/v1/render.png')){
      const format=request.path.endsWith('.png')?'png':'svg',r=await renderDocument([format],query);
      if(!r.ok)return jsonResponse(r.code==='RENDERER_UNAVAILABLE'?503:500,r);
      const body=format==='png'?Buffer.from(r.png,'base64'):Buffer.from(r.svg,'utf8');
      return {status:200,headers:{'content-type':format==='png'?'image/png':'image/svg+xml; charset=utf-8','access-control-allow-origin':'*'},body};
    }
    if(request.method==='GET'&&request.path==='/api/v1/layout/metrics'){const r=await renderDocument(['metrics']);return r.ok?jsonResponse(200,r.metrics):jsonResponse(r.code==='RENDERER_UNAVAILABLE'?503:500,r)}
    if(parts[2]==='graph'&&parts[3]&&['GET','POST'].includes(request.method)){
      const args=request.method==='POST'?parseBody(request.body):query;
      const value=graphSession.execute('schematic.graph.query',documentState,{verb:parts[3],args});return jsonResponse(value.ok===false?400:200,value);
    }
    if(parts[2]==='sim'&&parts[3]&&request.method==='POST'){
      const value=graphSession.execute(`schematic.sim.${parts[3]}`,documentState,parseBody(request.body));return jsonResponse(value.ok===false?(value.code==='UNKNOWN_TOOL'?404:400):200,value);
    }
    if(parts[2]==='sim'&&parts[3]==='inspect'&&request.method==='GET'){
      const value=graphSession.execute('schematic.sim.inspect',documentState,query);return jsonResponse(value.ok===false?400:200,value);
    }
    if(parts[0]==='api'&&parts[1]==='v1'&&parts[2]){
      const resource=resourceFromPath(parts[2]);if(!resource)return jsonResponse(404,{error:'resource not found'});
      const id=parts[3]||null;
      if(request.method==='GET'&&!id)return jsonResponse(200,Data.list(documentState,resource,query));
      if(request.method==='GET'&&id){const value=Data.read(documentState,resource,id);return value?jsonResponse(200,value):jsonResponse(404,{error:'not found'})}
      if(request.method==='POST'&&!id){const before=cloneDoc(),receipt=Data.applyOperation(documentState,{op:'create',resource,value:parseBody(request.body)});if(receipt.ok){recordHistory(before);saveDocument()}return jsonResponse(receipt.ok?201:400,receipt)}
      if(request.method==='PATCH'&&id){const before=cloneDoc(),receipt=Data.applyOperation(documentState,{op:'update',resource,resourceId:id,patch:parseBody(request.body)});if(receipt.ok){recordHistory(before);saveDocument()}return jsonResponse(receipt.ok?200:400,receipt)}
      if(request.method==='DELETE'&&id){const before=cloneDoc(),receipt=Data.applyOperation(documentState,{op:'delete',resource,resourceId:id});if(receipt.ok){recordHistory(before);saveDocument()}return jsonResponse(receipt.ok?200:400,receipt)}
    }
    return jsonResponse(404,{error:'not found'});
  }
  // /editor carries this server's document as an inert JSON script element just before the last
  // closing body tag; every less-than sign is escaped so no document text can end the element.
  function withServedDocument(html){
    const at=html.lastIndexOf('</body>');
    if(at<0)return html;
    const described=describe();
    const base=typeof described==='string'&&described?described.split(/[\\/]/).pop():'';
    const name=(base||'document.sov').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
    const json=JSON.stringify(Data.clone(documentState)).replace(/</g,'\\u003c');
    return html.slice(0,at)+`<script type="application/json" id="sov-served-document" data-name="${name}">${json}</script>`+html.slice(at);
  }
  async function handle(request){
    if(request.method==='OPTIONS')return {status:204,headers:{'access-control-allow-origin':'*','access-control-allow-methods':'GET,POST,PUT,PATCH,DELETE,OPTIONS','access-control-allow-headers':'content-type,mcp-protocol-version,mcp-method,mcp-name'},body:''};
    try{
      if((request.path==='/editor'||request.path==='/index.html')&&request.method==='GET'){
        const html=editorHtml?editorHtml():null;
        if(html==null)return jsonResponse(404,{error:'no build at index.html; run python build.py'});
        return {status:200,headers:{'content-type':'text/html; charset=utf-8','cache-control':'no-store','access-control-allow-origin':'*'},body:request.path==='/editor'?withServedDocument(html):html};
      }
      if(request.path==='/mcp'&&request.method==='POST')return await handleMcp(request);
      if(request.path.startsWith('/api/v1/'))return await handleApi(request);
      return jsonResponse(200,{name:'soveraeign-schematic',version:'0.1.24',document:describe(),mcp:base+'/mcp',api:base+'/api/v1',editor:base+'/editor'});
    }catch(error){return jsonResponse(500,{error:String(error.message||error)})}
  }
  return {handle};
}
