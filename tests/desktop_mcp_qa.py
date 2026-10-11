"""Collected active-editor MCP scenarios; run only through the supervised adapter.

--collect loads no browser. Execution reads the built test-copy page and exports
raw Istanbul counters even on failure. Native disk behavior is separately checked
with sdk_consumer.mjs; these scenarios use explicit native-save effects mocks.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import uuid

CASE_NAMES = (
    "initialize", "tool-schemas", "resources", "resource-missing", "live-document",
    "crud", "batch-history", "batch-atomic-refusal", "replace-undo", "stale-revision",
    "wrong-document", "missing-state-token", "state-token-aba", "document-reopen-token",
    "invalid-rpc-ids", "missing-rpc-id", "notifications", "unknown-method-tool",
    "required-arguments", "nested-batch-schema", "read-markers", "concerns-answer",
    "checkpoint", "layout-graph-svg", "run-start-step", "run-settle-trace-query-replay",
    "run-refusals", "no-external-execution", "native-save-success",
    "native-save-cancel", "native-save-failure", "native-save-edited-during-await",
    "relay-expired-request", "all-tools-exercised",
)
CASE_IDS = tuple(f'desktop-mcp/{name}' for name in CASE_NAMES)

SCENARIO = r"""async ({id,runDoc,expectedDocs})=>{
  const API=window.SovSchematicAPI, D=window.SovSchematicData, MCP=window.SovDesktopMcp;
  const check=(value,message)=>{if(!value)throw new Error(message)};
  const clone=value=>JSON.parse(JSON.stringify(value));
  const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  const seen=window.__mcpQaSeen||(window.__mcpQaSeen=new Set());
  let seq=1;
  const rpc=(method,params={})=>MCP.rpc({jsonrpc:'2.0',id:seq++,method,params});
  const tool=async(name,args={})=>{
    seen.add(name);const result=await rpc('tools/call',{name,arguments:args});
    check(result.result,`RPC result absent for ${name}`);return result.result;
  };
  const payload=result=>{
    const content=result.content?.find(item=>item.type==='text');
    check(typeof content?.text==='string','Tool JSON text content absent');
    return JSON.parse(content.text);
  };
  const ok=async(name,args={})=>{const r=await tool(name,args);check(!r.isError,`${name} refused: ${JSON.stringify(r)}`);return payload(r)};
  const info=async()=>ok('schematic.file.info');
  const guarded=async(name,args={})=>{
    const i=await info();return ok(name,{...args,documentId:i.documentId,ifRevision:i.revision,stateToken:i.stateToken});
  };
  const rejected=async(name,args,code)=>{
    const before=JSON.stringify(API.document.get());const result=await tool(name,args);
    check(result.isError,`${name} should refuse`);
    if(code)check(JSON.stringify(result).includes(code),`Expected ${code}: ${JSON.stringify(result)}`);
    check(JSON.stringify(API.document.get())===before,'Refused operation changed the document');return result;
  };
  const component=(name='qa-a')=>({id:name,symbolId:'act',x:200,y:200,config:{label:name}});
  const create=()=>guarded('schematic.create',{resource:'component',value:component()});
  delete window.__TAURI__;
  const base=D.makeDocument({schema:D.DOCUMENT_SCHEMA,id:'desktop-mcp-qa',revision:0,components:[],wires:[],references:[]});
  API.file.open(base,'qualification.sov');

  if(id==='initialize'){
    const response=await rpc('initialize',{protocolVersion:'2025-06-18',capabilities:{},clientInfo:{name:'qa',version:'1'}});
    check(response.result.protocolVersion==='2025-06-18','Protocol negotiation');
    check(response.result.capabilities.tools&&response.result.capabilities.resources,'Capabilities');
    check(response.result.instructions.includes('stateToken'),'Guard instructions');
    check((await rpc('ping')).result,'Ping');
  }else if(id==='tool-schemas'){
    const listed=(await rpc('tools/list')).result.tools;
    check(new Set(listed.map(t=>t.name)).size===listed.length,'Duplicate tool names');
    for(const name of ['schematic.create','schematic.update','schematic.delete','schematic.document.replace','schematic.apply','schematic.file.save','schematic.history.undo','schematic.history.redo','schematic.checkpoint.create','schematic.checkpoint.restore','schematic.layout.apply','schematic.concerns.answer']){
      const schema=listed.find(t=>t.name===name)?.inputSchema;
      check(schema&&['documentId','ifRevision','stateToken'].every(k=>schema.required.includes(k)),`Missing guards ${name}`);
    }
    const start=listed.find(t=>t.name==='schematic.run.start').inputSchema;
    check(start.properties.inputs&&start.properties.budget&&!start.properties.options,'Established run start shape');
  }else if(id==='resources'){
    const resources=(await rpc('resources/list')).result.resources;check(resources.length===Object.keys(expectedDocs).length,'Bundled documentation scope mismatch');
    for(const resource of resources){
      const r=await rpc('resources/read',{uri:resource.uri});check(r.result.contents[0].text===expectedDocs[resource.uri],'Bundled documentation differs from original source');
      const same=await ok('schematic.documentation',{uri:resource.uri});check(equal(r.result,same),'Resource/tool documentation disagree');
    }
  }else if(id==='resource-missing')check((await rpc('resources/read',{uri:'missing://resource'})).error,'Unknown resource not refused');
  else if(id==='live-document'){
    await create();const doc=await ok('schematic.document.get');check(equal(doc,API.document.get()),'MCP and editor differ');
    check(doc.components.some(c=>c.id==='qa-a'),'Created record absent from editor');check((await info()).dirty,'Mutation not dirty');
  }else if(id==='crud'){
    await create();await guarded('schematic.update',{resource:'component',id:'qa-a',patch:{config:{label:'updated'}}});
    const read=await ok('schematic.get',{resource:'component',id:'qa-a'});check(JSON.stringify(read).includes('updated'),'Read did not see update');
    check((await ok('schematic.list',{resource:'component'})).ok,'List receipt');
    await guarded('schematic.delete',{resource:'component',id:'qa-a'});check(API.document.get().components.length===0,'Delete did not reach editor');
  }else if(id==='batch-history'){
    await guarded('schematic.apply',{operations:[{op:'create',resource:'component',value:component()},{op:'create',resource:'component',value:component('qa-b')}]});
    check((await ok('schematic.history.list')).length===1,'Batch should be one history entry');
    await guarded('schematic.history.undo');check(API.document.get().components.length===0,'Undo did not remove batch');
    await guarded('schematic.history.redo');check(API.document.get().components.length===2,'Redo did not restore batch');
  }else if(id==='batch-atomic-refusal'){
    const i=await info();await rejected('schematic.apply',{documentId:i.documentId,ifRevision:i.revision,stateToken:i.stateToken,operations:[{op:'create',resource:'component',value:component()},{op:'update',resource:'component',id:'missing',patch:{config:{label:'bad'}}}]});
    check((await ok('schematic.history.list')).length===0,'Refusal entered history');
  }else if(id==='replace-undo'){
    await create();const before=API.document.get(),replacement=clone(before);replacement.components[0].config.label='replacement';
    await guarded('schematic.document.replace',{document:replacement});
    check(API.document.get().components[0].config.label==='replacement','Replacement did not apply');
    check((await ok('schematic.history.list')).length===2,'Replacement cleared prior history');
    await guarded('schematic.history.undo');check(API.document.get().components[0].config.label===before.components[0].config.label,'Replacement not undoable');
    await guarded('schematic.history.undo');check(API.document.get().components.length===0,'Earlier history lost');
  }else if(id==='stale-revision'){
    const stale=await info();await create();await rejected('schematic.create',{resource:'component',value:component('qa-b'),documentId:stale.documentId,ifRevision:stale.revision,stateToken:stale.stateToken},'REVISION_CONFLICT');
  }else if(id==='wrong-document'){
    const i=await info();await rejected('schematic.create',{resource:'component',value:component(),documentId:'wrong',ifRevision:i.revision,stateToken:i.stateToken},'DOCUMENT_CHANGED');
  }else if(id==='missing-state-token'){
    const i=await info();await rejected('schematic.create',{resource:'component',value:component(),documentId:i.documentId,ifRevision:i.revision},'stateToken');
  }else if(id==='state-token-aba'){
    const old=await info();await create();await guarded('schematic.history.undo');const now=await info();
    check(now.documentId===old.documentId&&now.revision===old.revision,'Fixture did not recreate revision ABA');
    await rejected('schematic.create',{resource:'component',value:component(),documentId:old.documentId,ifRevision:old.revision,stateToken:old.stateToken},'STATE_CHANGED');
  }else if(id==='document-reopen-token'){
    const old=await info();API.file.open(API.document.get(),'same.sov');const now=await info();check(now.stateToken!==old.stateToken,'Reopen token did not change');
    await rejected('schematic.create',{resource:'component',value:component(),documentId:old.documentId,ifRevision:old.revision,stateToken:old.stateToken},'STATE_CHANGED');
  }else if(id==='invalid-rpc-ids'){
    for(const requestId of [null,true,{},[],1.5])check((await MCP.rpc({jsonrpc:'2.0',id:requestId,method:'tools/list'})).error?.code===-32600,'Invalid RPC ID accepted');
    for(const requestId of [0,1,'abc'])check((await MCP.rpc({jsonrpc:'2.0',id:requestId,method:'tools/list'})).id===requestId,'Valid RPC ID not echoed');
  }else if(id==='missing-rpc-id'){
    const before=JSON.stringify(API.document.get()),i=await info();const r=await MCP.rpc({jsonrpc:'2.0',method:'tools/call',params:{name:'schematic.create',arguments:{resource:'component',value:component(),documentId:i.documentId,ifRevision:i.revision,stateToken:i.stateToken}}});
    check(r?.error?.code===-32600,'Missing ID not refused');check(JSON.stringify(API.document.get())===before,'ID-less mutation applied');
  }else if(id==='notifications')check(await MCP.rpc({jsonrpc:'2.0',method:'notifications/initialized'})===null,'Notification should have no response');
  else if(id==='unknown-method-tool'){
    check((await rpc('unknown/method')).error?.code===-32601,'Unknown method');await rejected('schematic.execute.shell',{},'TOOL_NOT_SUPPORTED');
  }else if(id==='required-arguments'){
    for(const name of ['schematic.apply','schematic.concerns.answer','schematic.checkpoint.restore','schematic.graph.query','schematic.run.step','schematic.run.trace','schematic.state.query'])await rejected(name,{},'ARGUMENT_REQUIRED');
  }else if(id==='nested-batch-schema'){
    const i=await info(),guards={documentId:i.documentId,ifRevision:i.revision,stateToken:i.stateToken};
    for(const operations of [[],[{}],[{op:'shell',resource:'component'}],[{op:'create',resource:'component',unknown:1}],[{op:'create',resource:'component',value:[]}]] )await rejected('schematic.apply',{...guards,operations},'ARGUMENT');
  }else if(id==='read-markers'){
    await create();check((await ok('schematic.read',{ids:['qa-a']})).ok,'Read scope');check((await ok('schematic.read',{area:{x:0,y:0,width:1000,height:1000}})).ok,'Area scope');
    check(await ok('schematic.markers'),'Markers missing');await rejected('schematic.read',{});
  }else if(id==='concerns-answer'){
    const report=await ok('schematic.concerns',{open:true});check(report,'Concern report');
    const before=API.document.get();await guarded('schematic.concerns.answer',{answers:[{concern:'what',answer:'qualification answer'}]});
    check(JSON.stringify(API.document.get()).includes('qualification answer'),'Answer did not reach active document');
    await guarded('schematic.history.undo');check(!JSON.stringify(API.document.get()).includes('qualification answer'),'Answer not undoable');
    const i=await info();await rejected('schematic.concerns.answer',{documentId:i.documentId,ifRevision:i.revision,stateToken:i.stateToken,answers:[{concern:'unknown',answer:'no'}]});
  }else if(id==='checkpoint'){
    await create();const cp=await guarded('schematic.checkpoint.create',{name:'before-change'});check(cp.id,'Checkpoint ID');
    check((await ok('schematic.checkpoint.list')).some(item=>item.id===cp.id),'Checkpoint not listed');
    await guarded('schematic.update',{resource:'component',id:'qa-a',patch:{config:{label:'after'}}});
    await guarded('schematic.checkpoint.restore',{id:cp.id});check(API.document.get().components[0].config.label==='qa-a','Checkpoint not restored');
  }else if(id==='layout-graph-svg'){
    await create();check((await guarded('schematic.layout.apply',{engine:'layered'})).ok,'Layout failure');
    check((await ok('schematic.graph.query',{verb:'export'})).ok,'Graph query');check((await ok('schematic.render.svg')).svg.includes('<svg'),'SVG missing');
  }else if(id==='run-start-step'||id==='run-settle-trace-query-replay'){
    API.file.open(runDoc,'not.sov');const before=JSON.stringify(API.document.get());
    const started=await ok('schematic.run.start',{inputs:[{entity:'A',point:'self',value:false,at:0}],seed:'qualification',budget:100,tickMs:1});check(started.ok&&started.handle,'Run start receipt');
    if(id==='run-start-step')check((await ok('schematic.run.step',{handle:started.handle})).ok,'Run step');
    else{
      check((await ok('schematic.run.settle',{handle:started.handle})).ok,'Settle');
      const trace=await ok('schematic.run.trace',{handle:started.handle});check(trace.ok&&trace.result?.ledger,'Trace receipt');
      check((await ok('schematic.state.query',{handle:started.handle,entity:'Q',observable:'signal'})).ok,'State query');
      check((await ok('schematic.run.replay',{trace:trace.result})).ok,'Replay');
    }
    check(JSON.stringify(API.document.get())===before,'Run modified document');check((await ok('schematic.history.list')).length===0,'Run entered history');
  }else if(id==='run-refusals'){
    await rejected('schematic.run.start',{budget:1000001},'ARGUMENT_RANGE');await rejected('schematic.run.start',{options:{}},'ARGUMENT_UNKNOWN');
    await rejected('schematic.run.step',{handle:'missing'});await rejected('schematic.run.start',{inputs:[{entity:'A',point:'self',value:'code',at:0}]},'ARGUMENT_INVALID');
  }else if(id==='no-external-execution'){
    await rejected('schematic.run.start',{handlers:{run:'globalThis.__externalExecuted=true'}},'ARGUMENT_UNKNOWN');
    check(!window.__externalExecuted,'External action executed');
    check(!(await rpc('tools/list')).result.tools.some(t=>/shell|exec|provider/i.test(t.name)),'External execution tool advertised');
  }else if(id.startsWith('native-save-')){
    await create();check((await info()).dirty,'Expected unsaved edit');
    let written=null;
    window.__TAURI__={core:{invoke:async(command,args)=>{
      if(command==='desktop_reset_document')return;
      check(command==='desktop_save_document','Unexpected native command');
      if(id==='native-save-cancel')return null;
      if(id==='native-save-failure')throw new Error('mock disk failure');
      written=args.text;
      if(id==='native-save-edited-during-await')API.update('component','qa-a',{config:{label:'edited-during-save'}});
      return {name:'qualification.sov',token:'mock-file-token'};
    }}};
    try{
      const i=await info();const response=await tool('schematic.file.save',{documentId:i.documentId,ifRevision:i.revision,stateToken:i.stateToken});
      const after=await info();
      if(id==='native-save-failure'){check(response.isError,'Save failure reported as success');check(after.dirty,'Save failure cleared dirty');}
      else if(id==='native-save-cancel'){check(payload(response).mode==='cancelled','Save cancellation lost');check(after.dirty,'Cancellation cleared dirty');}
      else if(id==='native-save-edited-during-await'){check(!response.isError&&after.dirty,'Newer unsaved edit marked clean');check(!written.includes('edited-during-save'),'Saved payload changed after dispatch');}
      else {check(!response.isError&&!after.dirty,'Successful native save not clean');check(JSON.parse(written).components.some(c=>c.id==='qa-a'),'Saved payload missing editor edit');}
    }finally{delete window.__TAURI__}
  }else if(id==='relay-expired-request'){
    let listener,responded=false;
    window.__TAURI__={event:{listen:async(name,callback)=>{listener=callback;return ()=>{}}},core:{invoke:async(command)=>{
      if(command==='desktop_mcp_begin')return false;
      if(command==='desktop_mcp_respond')responded=true;
      return null;
    }}};
    // Reload only the adapter closure to establish this mock relay, not the product state.
    const script=document.querySelector('script[data-beta-module="src/89-desktop-mcp.js"]');check(script,'Adapter module source missing');
    const element=document.createElement('script');element.textContent=script.textContent;document.body.appendChild(element);
    await Promise.resolve();await Promise.resolve();check(listener,'Relay listener not installed');
    const i=await info(),before=JSON.stringify(API.document.get());
    listener({payload:{requestId:'expired',rpc:{jsonrpc:'2.0',id:42,method:'tools/call',params:{name:'schematic.create',arguments:{resource:'component',value:component(),documentId:i.documentId,ifRevision:i.revision,stateToken:i.stateToken}}}}});
    await Promise.resolve();await Promise.resolve();check(JSON.stringify(API.document.get())===before&&!responded,'Expired queued mutation executed');
    delete window.__TAURI__;element.remove();
  }else if(id==='all-tools-exercised'){
    const names=(await rpc('tools/list')).result.tools.map(t=>t.name);const missing=names.filter(name=>!seen.has(name));check(missing.length===0,`Unexercised advertised tools: ${missing.join(', ')}`);
  }else throw new Error(`Unknown case ${id}`);
  return {id,ok:true};
}"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--collect', action='store_true')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--native-binary', type=Path)
    parser.add_argument('--coverage-dir', type=Path)
    options = parser.parse_args()
    if options.collect:
        print(json.dumps(list(CASE_IDS)))
        return 0
    if options.coverage_dir is None:
        parser.error('--coverage-dir is required for execution')
    from playwright.sync_api import sync_playwright
    from browser_runtime import chromium_launch_kwargs
    root = options.root.resolve()
    source_root = (options.source_root or root).resolve()
    html = (root / 'index.html').read_text(encoding='utf-8')
    run_doc = json.loads((root / 'examples/state/not.sov').read_text(encoding='utf-8'))
    doc_paths = ('docs/local-core/COWORKING.md', 'API.md', 'DATA-FORMATS.md', 'STATE-SPACE.md', 'MODULES.md')
    expected_docs = {f'schematically://docs/{name}': (source_root / name).read_text(encoding='utf-8') for name in doc_paths}
    results = []
    options.coverage_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = browser.new_page()
        page.set_default_timeout(10000)
        try:
            page.set_content(html, wait_until='load')
            page.wait_for_function('window.SovDesktopMcp && window.SovSchematicAPI')
            for case_id in CASE_IDS:
                try:
                    page.evaluate(SCENARIO, {'id': case_id.split('/', 1)[1], 'runDoc': run_doc, 'expectedDocs': expected_docs})
                    results.append({'id': case_id, 'status': 'PASS'})
                    print(f'CASE PASS {case_id}', flush=True)
                except Exception as problem:
                    results.append({'id': case_id, 'status': 'FAIL', 'error': str(problem)})
                    print(f'CASE FAIL {case_id}: {problem}', flush=True)
        finally:
            try:
                counters = json.loads(page.evaluate('JSON.stringify(globalThis.__coverage__ || {})'))
                destination = options.coverage_dir / f'desktop-mcp-{os.getpid()}-{uuid.uuid4().hex}.json'
                destination.write_text(json.dumps(counters), encoding='utf-8')
            except Exception as problem:
                results.append({'id': 'desktop-mcp/coverage-export', 'status': 'FAIL', 'error': str(problem)})
            browser.close()
    print(json.dumps({'suite': 'desktop-mcp-browser', 'collected': len(CASE_IDS), 'executed': len(results), 'results': results}))
    return 1 if any(result['status'] != 'PASS' for result in results) else 0


if __name__ == '__main__':
    sys.exit(main())
