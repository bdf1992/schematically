const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),os=require('node:os'),cp=require('node:child_process');
test('bounded QA schedule retains checks, exact Unicode ranges and process-tree deadlines',async()=>{
  cp.execFileSync('python',['tests/qa_scheduler_qa.py'],{cwd:path.resolve(__dirname,'..'),stdio:'pipe'});
  const {spawnBounded}=require('../scripts/budget-process.cjs');
  const readiness={token:'READY ',maximumStartupMs:30000};
  const result=await spawnBounded(process.execPath,['-e',"const c=require('node:child_process').spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{stdio:'inherit'});console.log('READY '+c.pid);c.unref()"],{stdio:['ignore','pipe','pipe'],env:process.env,timeout:2000,readiness});
  // Windows closes its owned Job on normal root exit; POSIX waits for the
  // deadline to close pipes retained by descendants. Both must clean up.
  if(result.error)assert.match(result.error.message,/process-tree deadline/);
  else assert.equal(result.status,0);
  const child=Number(result.stdout.trim().replace('READY ',''));assert.ok(child>0,'descendant was started');assert.throws(()=>process.kill(child,0),'deadline leaves no child outside supervision');
  const hanging=await spawnBounded(process.execPath,['-e',"const c=require('node:child_process').spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{stdio:'inherit'});console.log('READY '+c.pid);setInterval(()=>{},1000)"],{stdio:['ignore','pipe','pipe'],env:process.env,timeout:2000,readiness});
  assert.match(hanging.error?.message||'',/process-tree deadline/);assert.notEqual(hanging.status,0);
  const descendant=Number(hanging.stdout.trim().replace('READY ',''));assert.ok(descendant>0,'live-root descendant was started');assert.throws(()=>process.kill(descendant,0),'deadline removes live-root descendants');
  assert.ok(hanging.elapsedMilliseconds-hanging.startupMilliseconds<=3000,'ready work and pipe cleanup stay within two-second deadline plus one-second settlement');
  console.log(JSON.stringify({lifecycleStartupMilliseconds:[result.startupMilliseconds,hanging.startupMilliseconds],liveDeadlineMilliseconds:2000,cleanupSettlementMilliseconds:1000}));
});
test('virtual definition editing, validation and package round trips',()=>require('./virtual_instances_core_qa.cjs'));
test('virtual instances own mutable state in one clock',()=>require('./virtual_instance_state_qa.cjs'));
test('authored governed diagram expands separate nine-cell owners and explicit boundaries',()=>{
  const Data=require('../src/05-data-core.js');
  const authored=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/alignment-governance.sov'),'utf8'));
  const document=Data.makeDocument(authored),valid=Data.validateDocument(document);
  assert.equal(valid.ok,true,JSON.stringify(valid.errors));
  for(const id of ['root','governance','child','peer']){
    assert.equal(document.components.filter(c=>c.parentId===id&&/-t\d\d$/.test(c.id)).length,9);
    assert.equal(document.components.filter(c=>c.parentId===id&&/^.+-(N|NE|E|SE|S|SW|W|NW)$/.test(c.id)).length,8);
  }
  assert.equal(document.wires.length,23,'only three boundary and five declared cell crossings per node');
  assert.equal(document.wires.find(w=>w.id==='fallback').a,'governance-SE');
  assert.equal(document.wires.find(w=>w.id==='fallback').b,'peer-NW');
  document.components.find(c=>c.id==='child-t11').config.label='local change';
  assert.notEqual(document.components.find(c=>c.id==='peer-t11').config.label,'local change');
});
test('operator-configured route is read-only, fixed and reports unavailable snapshots',async()=>{
  const {createKoreExecutionRoute}=await import('../mcp/kore-execution.mjs');
  const invoke=(route,method='GET',pathname='/kore/execution')=>{let status,body;const handled=route({method},{writeHead:s=>status=s,end:b=>body=JSON.parse(b)},pathname);return {handled,status,body}};
  assert.equal(invoke(createKoreExecutionRoute(null),'GET','/else').handled,false);
  assert.equal(invoke(createKoreExecutionRoute(null)).status,503);
  assert.equal(invoke(createKoreExecutionRoute(null),'POST').status,405);
  assert.equal(invoke(createKoreExecutionRoute('fixed',()=>'{bad')).status,503);
  let seen;assert.deepEqual(invoke(createKoreExecutionRoute('fixed',(f)=>{seen=f;return '{"nodes":{}}'})).body,{nodes:{}});assert.equal(seen,path.resolve('fixed'));
});
async function withServer(args,action){
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'sov-arch-server-')),port=21000+Math.floor(Math.random()*1000),wrapper=path.join(temp,'wrapper.mjs');
  fs.writeFileSync(wrapper,"process.on('message',()=>process.exit(0)); await import("+JSON.stringify(require('node:url').pathToFileURL(path.resolve(__dirname,'../mcp/server.mjs')).href)+");");
  const server=cp.fork(wrapper,['--port',String(port),...args(temp)],{silent:true,env:process.env});
  const call=async(route,status=200,method='GET',body)=>{const r=await fetch('http://127.0.0.1:'+port+route,{method,...(body===undefined?{}:{body:typeof body==='string'?body:JSON.stringify(body)})});assert.equal(r.status,status,method+' '+route);return r};
  try{
    for(let i=0;i<100;i++){try{await fetch('http://127.0.0.1:'+port+'/documents');break}catch{await new Promise(r=>setTimeout(r,30))}}
    await action(call,temp);
  }finally{server.send('exit');await new Promise(resolve=>server.on('exit',resolve));}
}
function rootFixture(temp){fs.copyFileSync(path.resolve(__dirname,'../data/schematic.sov'),path.join(temp,'example.sov'));fs.writeFileSync(path.join(temp,'ignored.txt'),'');return temp}
test('file registrations and lifecycle preserve document routing',async()=>{
  await withServer(temp=>['--root',rootFixture(temp)],async(call,temp)=>{
    await call('/');await call('/unavailable',404);await call('/documents');await call('/documents',204,'OPTIONS');
    await call('/d/example/api/v1/document');await call('/d/example/editor');await call('/d/missing/api/v1/document',404);await call('/d/%FF/api/v1/document',400);
    await call('/documents',400,'POST','broken');await call('/documents',400,'POST','null');await call('/documents',400,'POST',[]);await call('/documents',400,'POST',{id:'bad id'});await call('/documents',400,'POST',{id:'other',file:'relative'});
    await call('/documents',201,'POST',{id:'alias',file:path.join(temp,'example.sov')});await call('/documents',200,'POST',{id:'alias',file:path.join(temp,'example.sov')});await call('/documents',409,'POST',{id:'alias',file:path.join(temp,'different.sov')});await call('/documents',201,'POST',{id:'new'});
    await call('/documents/example/close',204,'OPTIONS');await call('/documents/example/close',200,'POST');await call('/d/example/api/v1/document');await call('/documents/example/reload',200,'POST');await call('/documents/missing/close',404,'POST');await call('/documents/new/reload',404,'POST');await call('/documents/%FF/close',400,'POST');
  });
});
test('SQLite imports, exports, profiles and lifecycle retain working-copy ownership',async()=>{
  await withServer(temp=>['--root',rootFixture(temp),'--db',path.join(temp,'store.db')],async(call,temp)=>{
    await call('/documents');await call('/profiles');await call('/profiles',204,'OPTIONS');await call('/profiles/bdo/documents');await call('/profiles/missing/documents',404);await call('/profiles/bdo/documents',204,'OPTIONS');
    await call('/d/example/api/v1/document');await call('/d/missing/api/v1/document',404);await call('/documents');
    await call('/documents',400,'POST','broken');await call('/documents',400,'POST','null');await call('/documents',400,'POST',{id:'bad id'});await call('/documents',400,'POST',{id:'a',file:'relative'});
    await call('/documents',201,'POST',{id:'imported',file:path.join(temp,'example.sov')});await call('/documents',200,'POST',{id:'imported'});await call('/documents',409,'POST',{id:'imported',file:path.join(temp,'different.sov')});await call('/documents',201,'POST',{id:'empty'});
    await call('/documents/imported/export',200,'POST',{file:path.join(temp,'export.sov')});assert.ok(fs.existsSync(path.join(temp,'export.sov')));
    await call('/documents/imported/import',200,'POST',{});await call('/documents/imported/import',204,'OPTIONS');await call('/documents/empty/export',409,'POST',{file:path.join(temp,'empty.sov')});await call('/documents/missing/import',404,'POST',{});await call('/documents/imported/import',400,'POST',{file:'relative'});await call('/documents/imported/import',404,'POST',{file:path.join(temp,'missing.sov')});await call('/documents/imported/import',400,'POST','broken');
    fs.writeFileSync(path.join(temp,'bad.sov'),'broken');await call('/documents/imported/import',400,'POST',{file:path.join(temp,'bad.sov')});await call('/documents',400,'POST',{id:'bad',file:path.join(temp,'bad.sov')});
    await call('/documents/imported/close',200,'POST');await call('/documents/imported/reload',409,'POST');await call('/documents/missing/close',404,'POST');
  });
});
test('projection shows actual owned cells, governed lineage and recorded rejection without writes',async()=>{
  const els=new Map(),node={dataset:{id:'root'},style:{setProperty(){}}},cellNode={dataset:{id:'root-t11'},style:{setProperty(){}}},wire={dataset:{wireId:'w'},style:{}};
  for(const id of ['simPlayBtn','simStepBtn','simResetBtn','simSpeed','objectsList'])els.set(id,{style:{},before(el){els.set(el.id,el)}});
  const cell={phase:1,phase_count:3,work:'q',waiting:null,candidates:[{value:'candidate',status:'pending'}],results:[],failures:[],gate:'After',gates:[{name:'typed-output',passed:false}],last_check:{name:'typed-output',accepted:false},receipts:[{request_id:'q',contract:'k',policy_version:1}],attempts:[{request_id:'q',number:1}],authority_version:1,locked:true,owner:'r.t11',role:'inference',row:'Dynamics',column:'External',state:{source:'attributed'}};
  const cells={};for(let row=0;row<3;row++)for(let col=0;col<3;col++)cells['t'+row+col]={phase:0,phase_count:5,work:null,waiting:null,results:[],failures:[]};cells.t11=cell;
  const snapshot={nodes:{r:{phase:1,phase_count:3,work:'q',waiting:'frame',results:[{request_id:'q',status:'success',value:{candidate:'policy.write',semantic_acceptance:false}}],failures:[],cells,parent:'g'},g:{phase:2,phase_count:5,work:null,waiting:null,cells:{}}},contracts:[{id:'k',input_type:'typed',output_type:'checked',governance_node:'g',source:'r',source_cell:'t11',target:'g'}],contract_id:'contract',contract_version:1,gates:[{node:'r',gate:'After',request_id:'q'}],attempts:[{id:'q-1'}],requests:{q:{return_address:['r'],outcome:null}},events:[{kind:'handoff',kord:'k',node:'r',request_id:'q'}]};
  const makeElement=tag=>({tag,style:{},children:[],_text:'',get textContent(){return this._text+this.children.map(c=>c.textContent).join('')},set textContent(value){this._text=value;this.children=[]},appendChild(el){this.children.push(el)}});
  const context={window:{},diagram:{meta:{koreExecution:{nodes:{root:'r',governance:'g'},cells:{'root-t11':{node:'r',cell:'t11'}},kords:{k:'w'}}}},virtualView:{open:'root'},openVirtualNode(id){context.virtualView.open=id;return {ok:true}},document:{getElementById:id=>els.get(id),createElement:makeElement,querySelectorAll:s=>s.startsWith('.node')?[node,cellNode]:[wire]},simClock:{playing:true},simPause(){context.simClock.playing=false},setInterval(){},fetch:async()=>({ok:true,json:async()=>snapshot})};
  vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/88-kore-execution.js'),'utf8'),context,{filename:path.resolve(__dirname,'../src/88-kore-execution.js')});
  await new Promise(r=>setImmediate(r));
  const panel=els.get('koreExecutionPanel');assert.match(panel.textContent,/Phase 1 \/ 3/);assert.equal(node.dataset.koreWaiting,'true');assert.equal(wire.dataset.koreTraversal,'true');assert.equal(els.get('simPlayBtn').disabled,true);
  const detached=context.window.SovKoreExecution.state();detached.nodes.r.phase=9;assert.equal(snapshot.nodes.r.phase,1);
  assert.match(panel.textContent,/Returned outcomes \/ envelopes/);assert.match(panel.textContent,/semantic acceptance false/);assert.match(panel.textContent,/policy.write/);assert.doesNotMatch(panel.textContent,/Accepted results/,'a transport envelope is not accepted cell state');
  const records=panel.children.find(el=>el.tag==='details');assert.equal(records.open,false,'raw execution records start collapsed');assert.ok(panel.children.indexOf(records)>panel.children.findIndex(el=>el.tag==='button'),'navigation precedes raw records');
  const visible=panel.children.find(el=>el.tag==='pre');assert.ok(visible.textContent.length<2500,'summary is bounded and contains no full JSON histories');assert.doesNotMatch(visible.textContent,/input_type|policy_version/);assert.ok(records.textContent.includes('policy_version'),'complete evidence is retained in collapsed records');
  records.open=true;records.ontoggle();await context.window.SovKoreExecution.refresh();assert.equal(panel.children.find(el=>el.tag==='details').open,true,'refresh preserves expanded records');
  const before=JSON.stringify(snapshot);assert.equal(context.window.SovKoreExecution.inspect('r','missing').ok,false);assert.equal(context.window.SovKoreExecution.inspect('missing').ok,false);
  assert.equal(context.window.SovKoreExecution.inspect('r','t11').ok,true);assert.match(panel.textContent,/Inspecting r\/cells\/t11/);assert.match(panel.textContent,/Pending candidates/);assert.match(panel.textContent,/typed-output/);assert.match(panel.textContent,/Evidence receipts/);assert.match(panel.textContent,/Declared typed Kords/);assert.match(panel.textContent,/Attributed local state/);assert.equal(cellNode.dataset.korePhase,'1');
  for(const address of Object.keys(cells))assert.ok(panel.children.some(b=>b.textContent==='Inspect '+address),'every owned cell is inspectable');
  panel.children.find(b=>b.textContent==='Open Kord k \u2192 g'.replace('\\u2192','\u2192')).onclick();assert.equal(context.virtualView.open,'governance');assert.equal(JSON.stringify(snapshot),before,'inspection must not change authoritative state');
  context.window.SovKoreExecution.inspect('r','t11');cell.candidates=[];cell.failures=[{code:'OUTPUT_REFUSED',contract:'k',gate:'After',escalation_holder:'coordinator/root'}];await context.window.SovKoreExecution.refresh();assert.match(panel.textContent,/OUTPUT_REFUSED/);assert.match(panel.children.find(el=>el.tag==='pre').textContent,/coordinator\/root/,'failure holder stays visible outside raw records');assert.equal(cell.results.length,0);
  context.window.SovKoreExecution.inspect('r');context.selected='root-t11';await context.window.SovKoreExecution.refresh();assert.match(panel.textContent,/Inspecting r\/cells\/t11/,'native cell selection reveals owned state');
  snapshot.requests.q.outcome={status:'success'};await context.window.SovKoreExecution.refresh();assert.equal(wire.dataset.koreTraversal,'false');assert.match(panel.textContent,/Last recorded traversal/);
  context.virtualView.open=null;await context.window.SovKoreExecution.refresh();assert.match(panel.textContent,/r \u00b7 separate node state/);
  const prior=context.diagram.meta.koreExecution;context.diagram.meta.koreExecution={nodes:{missing:'absent'},cells:{t00:{node:'absent',cell:'t00'}},kords:{undeclared:'wire'},contractId:'wrong',contractVersion:'wrong'};
  await context.window.SovKoreExecution.refresh();assert.match(panel.textContent,/Binding incomplete/);assert.match(panel.textContent,/does not establish execution/);context.diagram.meta.koreExecution=prior;
  context.fetch=async()=>({ok:false,status:503});await context.window.SovKoreExecution.refresh();assert.equal(context.window.SovKoreExecution.status().error,'HTTP 503');assert.match(panel.textContent,/current activity unknown/);
  context.fetch=async()=>({ok:true,json:async()=>({})});await context.window.SovKoreExecution.refresh();assert.equal(context.window.SovKoreExecution.status().error,'Invalid Knode snapshot');
  context.diagram.meta={};await context.window.SovKoreExecution.refresh();assert.equal(els.get('simPlayBtn').disabled,false);assert.equal(panel.hidden,true);
});
test('native server routes configured snapshots, documents and editor',async()=>{
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'sov-kore-')),state=path.join(temp,'latest.json'),port=19000+Math.floor(Math.random()*1000);
  fs.writeFileSync(state,JSON.stringify({nodes:{root:{}},requests:{},events:[]}));
  // A graceful exit collects native V8 evidence even on Windows.
  const wrapper=path.join(temp,'wrapper.mjs');fs.writeFileSync(wrapper,"process.on('message',()=>process.exit(0)); await import("+JSON.stringify(require('node:url').pathToFileURL(path.resolve(__dirname,'../mcp/server.mjs')).href)+");");
  const server=cp.fork(wrapper,['--port',String(port),'--kore-state',state],{silent:true,env:process.env});
  try{
    let response;for(let i=0;i<100;i++){try{response=await fetch('http://127.0.0.1:'+port+'/kore/execution');break}catch{await new Promise(r=>setTimeout(r,30))}}
    assert.equal(response.status,200);assert.equal((await response.json()).nodes.root!=null,true);
    for(const route of ['/documents','/editor','/api/v1/document','/api/v1/components','/api/v1/wires'])assert.equal((await fetch('http://127.0.0.1:'+port+route)).status,200,route);
    assert.equal((await fetch('http://127.0.0.1:'+port+'/kore/execution',{method:'POST',body:'{}'})).status,405);
  }finally{server.send('exit');await new Promise(resolve=>server.on('exit',resolve));}
});
