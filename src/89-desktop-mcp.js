'use strict';
// The desktop's MCP adapter delegates into the active editor. It owns no document.
(function desktopMcpAdapter(){
  const api=window.SovSchematicAPI;
  const data=window.SovSchematicData;
  const empty={type:'object',properties:{},additionalProperties:false};
  const schema=(properties,required=[])=>({type:'object',properties,required,additionalProperties:false});
  const resource={type:'string',enum:['component','wire','reference']};
  const text={type:'string'};
  const guarded=new Set(['schematic.create','schematic.update','schematic.delete','schematic.document.replace','schematic.apply','schematic.file.save','schematic.history.undo','schematic.history.redo','schematic.concerns.answer','schematic.checkpoint.create','schematic.checkpoint.restore','schematic.layout.apply']);
  const extra=[
    ['schematic.file.info','Read active file identity, revision, dirty state and build.',empty],
    ['schematic.file.save','Durably save the active native file; opens Save As when unassociated.',schema({saveAs:{type:'boolean'}})],
    ['schematic.read','Read a scoped slice of the active document.',schema({ids:{type:'array',items:text},area:{type:'object'}})],
    ['schematic.apply','Apply an atomic batch using the editor history and shared data core.',schema({operations:{type:'array',minItems:1,items:schema({op:{type:'string',enum:['create','update','delete']},resource,id:text,ref:{type:'string',pattern:'^\\$.+'},value:{type:'object'},patch:{type:'object'}},['op','resource'])}},['operations'])],
    ['schematic.markers','Read validation findings for the active document.',empty],
    ['schematic.concerns','Read the active document questions and answers.',schema({open:{type:'boolean'}})],
    ['schematic.concerns.answer','Answer declared questions atomically.',schema({answers:{type:'array',items:{type:'object'}}},['answers'])],
    ['schematic.history.list','Read active editor history.',empty],
    ['schematic.history.undo','Undo one active editor history entry.',empty],
    ['schematic.history.redo','Redo one active editor history entry.',empty],
    ['schematic.checkpoint.list','Read persisted checkpoints.',empty],
    ['schematic.checkpoint.create','Create a named checkpoint.',schema({name:text},['name'])],
    ['schematic.checkpoint.restore','Restore a named checkpoint.',schema({id:text},['id'])],
    ['schematic.layout.apply','Apply an existing layout engine to the active document.',schema({engine:text,scope:text,view:text})],
    ['schematic.graph.query','Query the active document graph.',schema({verb:text,args:{type:'object'}},['verb'])],
    ['schematic.render.svg','Render the active document as SVG.',schema({options:{type:'object'}})],
    ['schematic.run.start','Start the existing validated local state-space runtime; no external code execution.',schema({inputs:{type:'array',items:schema({entity:text,point:text,channel:text,value:{type:'boolean'},at:{type:'integer',minimum:0}},['entity','point','value','at'])},seed:text,budget:{type:'integer',minimum:0,maximum:1000000},tickMs:{type:'integer',minimum:1}})],
    ['schematic.run.step','Step a local run.',schema({handle:text},['handle'])],
    ['schematic.run.settle','Settle a local run.',schema({handle:text},['handle'])],
    ['schematic.run.trace','Read a local run trace.',schema({handle:text},['handle'])],
    ['schematic.state.query','Read records matching a local run subject.',schema({handle:text,entity:text,point:text,channel:text,observable:text},['handle','entity','observable'])],
    ['schematic.run.replay','Replay a trace against the active document.',schema({trace:{type:'object'}},['trace'])],
    ['schematic.documentation','Read bundled consumer documentation.',schema({uri:text},['uri'])]
  ].map(([name,description,inputSchema])=>({name,description,inputSchema}));
  function tools(){
    return [...data.operationTools(),...extra].map(tool=>{
      if(!guarded.has(tool.name))return tool;
      return {...tool,inputSchema:{...tool.inputSchema,properties:{...tool.inputSchema.properties,documentId:text,ifRevision:{type:'integer',minimum:0},stateToken:text},required:[...new Set([...(tool.inputSchema.required||[]),'documentId','ifRevision','stateToken'])]}};
    });
  }
  function docs(){
    const tag=document.getElementById('sov-docs');
    return tag?JSON.parse(tag.textContent):{};
  }
  function readResource(uri){
    const body=docs()[uri];
    if(typeof body!=='string')throw new Error(`RESOURCE_NOT_FOUND: ${uri}`);
    return {contents:[{uri,mimeType:'text/markdown',text:body}]};
  }
  function identityGuard(name,args){
    if(!guarded.has(name))return;
    const doc=api.document.get(),info=api.file.info();
    if(args.documentId!==doc.id)throw new Error('DOCUMENT_CHANGED: read the active document identity before writing');
    if(!Number.isInteger(args.ifRevision)||args.ifRevision!==info.revision)throw new Error('REVISION_CONFLICT: read the active revision before writing');
    if(args.stateToken!==stateToken())throw new Error('STATE_CHANGED: read file.info again before writing');
  }
  function stateToken(){
    return `${documentLifecycleGeneration}:${window.SovSchematicCanonical.sha256Hex(window.SovSchematicCanonical.canonicalize(api.document.get()))}`;
  }
  function admittedArgs(tool,args){
    function validate(rule,value,key){
      const type=rule.type;
      if(type==='array'&&!Array.isArray(value)||type==='object'&&(!value||typeof value!=='object'||Array.isArray(value))||type==='integer'&&!Number.isInteger(value)||type==='number'&&(typeof value!=='number'||!Number.isFinite(value))||type==='string'&&typeof value!=='string'||type==='boolean'&&typeof value!=='boolean')throw new Error(`ARGUMENT_INVALID: ${key}`);
      if(rule.enum&&!rule.enum.includes(value))throw new Error(`ARGUMENT_INVALID: ${key}`);
      if(typeof value==='number'&&(rule.minimum!==undefined&&value<rule.minimum||rule.maximum!==undefined&&value>rule.maximum))throw new Error(`ARGUMENT_RANGE: ${key}`);
      if(typeof value==='string'&&(rule.minLength!==undefined&&value.length<rule.minLength||rule.pattern&&!new RegExp(rule.pattern).test(value)))throw new Error(`ARGUMENT_INVALID: ${key}`);
      if(Array.isArray(value)){
        if(rule.minItems!==undefined&&value.length<rule.minItems)throw new Error(`ARGUMENT_INVALID: ${key}`);
        if(rule.items)value.forEach((item,index)=>validate(rule.items,item,`${key}[${index}]`));
      }
      if(type==='object'){
        for(const required of rule.required||[])if(value[required]===undefined)throw new Error(`ARGUMENT_REQUIRED: ${key}.${required}`);
        for(const [field,item] of Object.entries(value)){
          const child=rule.properties?.[field];
          if(child)validate(child,item,`${key}.${field}`);
          else if(rule.additionalProperties===false)throw new Error(`ARGUMENT_UNKNOWN: ${key}.${field}`);
        }
      }
    }
    validate(tool.inputSchema,args,'arguments');
  }
  async function call(name,args={}){
    const tool=tools().find(value=>value.name===name);
    if(!tool)throw new Error(`TOOL_NOT_SUPPORTED: ${name}`);
    admittedArgs(tool,args);identityGuard(name,args);
    const writes={
      'schematic.list':'list','schematic.get':'read','schematic.create':'create','schematic.update':'update','schematic.delete':'delete'
    };
    if(writes[name])return api.execute({schema:data.OPERATION_SCHEMA,id:`desktop-${Date.now()}`,op:writes[name],resource:args.resource,resourceId:args.id??null,value:args.value??null,patch:args.patch??null,query:args.query??{},ifRevision:args.ifRevision});
    if(name==='schematic.document.get')return api.document.get();
    if(name==='schematic.document.replace'){
      const incoming=data.makeDocument(data.clone(args.document)),check=data.validateDocument(incoming);
      if(!check.ok)throw new Error(`DOCUMENT_INVALID: ${check.errors.join('; ')}`);
      return api.document.replace(incoming,{history:true});
    }
    if(name==='schematic.file.info')return {...api.file.info(),documentId:api.document.get().id,stateToken:stateToken()};
    if(name==='schematic.file.save')return saveSchematicFile({saveAs:args.saveAs===true});
    if(name==='schematic.read')return api.read({ids:args.ids,area:args.area});
    if(name==='schematic.apply')return api.apply({operations:args.operations,ifRevision:args.ifRevision});
    if(name==='schematic.markers')return api.markers();
    if(name==='schematic.concerns')return api.concerns.list(args);
    if(name==='schematic.concerns.answer')return api.concerns.answer({answers:args.answers,ifRevision:args.ifRevision});
    if(name==='schematic.history.list')return api.history.list();
    if(name==='schematic.history.undo')return api.history.undo();
    if(name==='schematic.history.redo')return api.history.redo();
    if(name==='schematic.checkpoint.list')return api.checkpoints.list();
    if(name==='schematic.checkpoint.create')return api.checkpoints.create(args.name);
    if(name==='schematic.checkpoint.restore')return api.checkpoints.restore(args.id);
    if(name==='schematic.layout.apply'){
      const {documentId,ifRevision,stateToken:observedState,...options}=args;
      return api.layout.apply(options);
    }
    if(name==='schematic.graph.query')return api.graph.query(args.verb,args.args);
    if(name==='schematic.render.svg')return {svg:api.render.svg(args.options)};
    if(name==='schematic.run.start')return api.run.start(args);
    if(name==='schematic.run.step')return api.run.step(args.handle);
    if(name==='schematic.run.settle')return api.run.settle(args.handle);
    if(name==='schematic.run.trace')return api.run.trace(args.handle);
    if(name==='schematic.state.query'){const {handle,...subject}=args;return api.run.query(handle,subject)}
    if(name==='schematic.run.replay')return api.run.replay(args.trace);
    if(name==='schematic.documentation')return readResource(args.uri);
    throw new Error(`TOOL_NOT_SUPPORTED: ${name}`);
  }
  async function rpc(request){
    const id=request?.id??null;
    const result=value=>({jsonrpc:'2.0',id,result:value});
    const error=(code,message)=>({jsonrpc:'2.0',id,error:{code,message}});
    if(!request||Array.isArray(request)||request.jsonrpc!=='2.0'||typeof request.method!=='string')return error(-32600,'Invalid Request');
    if(!Object.hasOwn(request,'id')){
      if(request.method.startsWith('notifications/'))return null;
      return error(-32600,'A tool request requires a non-null string or integer ID');
    }
    if(typeof request.id!=='string'&&!Number.isSafeInteger(request.id))return error(-32600,'Invalid Request ID');
    if(request.method==='initialize'){
      const supported=['2025-03-26','2025-06-18'];
      const asked=request.params?.protocolVersion;
      return result({protocolVersion:supported.includes(asked)?asked:'2025-06-18',capabilities:{tools:{listChanged:false},resources:{listChanged:false}},serverInfo:{name:'schematically-desktop',version:'0.1'},instructions:'Co-work on the active desktop document. Read bundled documentation and schematic.file.info first. Mutations require documentId, ifRevision and stateToken from file.info. Document edits share editor history. Changes remain unsaved until schematic.file.save succeeds. Document edits and declarative logic do not grant external execution authority.'});
    }
    if(request.method==='ping')return result({});
    if(request.method==='tools/list')return result({tools:tools()});
    if(request.method==='resources/list')return result({resources:Object.keys(docs()).map(uri=>({uri,name:uri.split('/').pop(),mimeType:'text/markdown'}))});
    if(request.method==='resources/read'){
      try{return result(readResource(request.params?.uri))}catch(problem){return error(-32002,problem.message)}
    }
    if(request.method!=='tools/call')return error(-32601,`Method not supported: ${request.method}`);
    try{
      const value=await call(request.params?.name,request.params?.arguments||{});
      const payload=value===undefined?{ok:true}:value;
      return result({content:[{type:'text',text:JSON.stringify(payload)}],structuredContent:typeof payload==='object'&&payload!==null&&!Array.isArray(payload)?payload:{value:payload},isError:payload?.ok===false});
    }catch(problem){return result({content:[{type:'text',text:problem.message}],structuredContent:{ok:false,error:problem.message},isError:true})}
  }
  window.SovDesktopMcp={rpc,tools};
  let queue=Promise.resolve();
  async function connect(){
    const tauri=window.__TAURI__;
    if(!tauri?.event?.listen||!tauri?.core?.invoke)return;
    await tauri.event.listen('desktop-mcp-request',event=>{
      queue=queue.then(async()=>{
        const admitted=await tauri.core.invoke('desktop_mcp_begin',{requestId:event.payload.requestId});
        if(!admitted)return;
        const response=await rpc(event.payload.rpc);
        await tauri.core.invoke('desktop_mcp_respond',{requestId:event.payload.requestId,response});
      }).catch(problem=>console.error('Desktop MCP relay failed',problem));
    });
    await window.SovDesktopPersistenceReady;
    await tauri.core.invoke('desktop_mcp_ready');
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>connect().catch(console.error),{once:true});
  else connect().catch(console.error);
})();
