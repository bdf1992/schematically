const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),os=require('node:os'),cp=require('node:child_process');
test('bounded QA schedule retains checks, exact Unicode ranges and process-tree deadlines',async()=>{
  console.log(cp.execFileSync('python',['tests/qa_scheduler_qa.py'],{cwd:path.resolve(__dirname,'..'),stdio:'pipe',encoding:'utf8'}).trim());
  const {spawnBounded}=require('../scripts/budget-process.cjs');
  const readiness={token:'READY ',maximumStartupMs:30000};
  const gone=async(pid)=>{const started=Date.now();for(;;){try{process.kill(pid,0)}catch(error){assert.equal(error.code,'ESRCH');return Date.now()-started}assert.ok(Date.now()-started<1000,'owned PID '+pid+' must disappear within cleanup settlement');await new Promise(resolve=>setTimeout(resolve,10))}};
  const readyPids=result=>JSON.parse(result.stdout.match(/^READY (.+)$/m)[1]);
  const clean=await spawnBounded(process.execPath,['-e',"console.log('READY '+JSON.stringify({root:process.pid}))"],{stdio:['ignore','pipe','pipe'],env:process.env,timeout:2000,readiness});
  assert.equal(clean.status,0,'a clean short root returns its actual successful status');assert.equal(clean.error,null);const cleanPids=readyPids(clean);assert.ok(cleanPids.root>0);const cleanCleanup=await gone(cleanPids.root);
  const result=await spawnBounded(process.execPath,['-e',"const c=require('node:child_process').spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{stdio:'inherit'});console.log('READY '+JSON.stringify({root:process.pid,child:c.pid}));c.unref()"],{stdio:['ignore','pipe','pipe'],env:process.env,timeout:2000,readiness});
  // Windows closes its owned Job on normal root exit; POSIX waits for the
  // deadline to close pipes retained by descendants. Both must clean up.
  if(result.error)assert.match(result.error.message,/process-tree deadline/);
  else assert.equal(result.status,0);
  const orphanPids=readyPids(result);assert.ok(orphanPids.root>0&&orphanPids.child>0,'owned root and descendant were started');const orphanCleanup=Math.max(await gone(orphanPids.root),await gone(orphanPids.child));
  const hanging=await spawnBounded(process.execPath,['-e',"const c=require('node:child_process').spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{stdio:'inherit'});console.log('READY '+JSON.stringify({root:process.pid,child:c.pid}));setInterval(()=>{},1000)"],{stdio:['ignore','pipe','pipe'],env:process.env,timeout:2000,readiness});
  assert.match(hanging.error?.message||'',/process-tree deadline/);assert.notEqual(hanging.status,0);
  const livePids=readyPids(hanging);assert.ok(livePids.root>0&&livePids.child>0,'live owned root and descendant were started');const liveCleanup=Math.max(await gone(livePids.root),await gone(livePids.child));
  assert.ok(hanging.elapsedMilliseconds-hanging.startupMilliseconds<=3000,'ready work and pipe cleanup stay within two-second deadline plus one-second settlement');
  assert.ok(hanging.elapsedMilliseconds-hanging.startupMilliseconds+liveCleanup<=3000,'deadline and disappearance proof share the one-second cleanup allowance');
  console.log(JSON.stringify({lifecycle:[{kind:'clean',pids:cleanPids,status:clean.status,error:clean.error,startupMilliseconds:clean.startupMilliseconds,cleanupMilliseconds:cleanCleanup},{kind:'exited-root',pids:orphanPids,status:result.status,error:result.error?.message||null,startupMilliseconds:result.startupMilliseconds,cleanupMilliseconds:orphanCleanup},{kind:'live-root',pids:livePids,status:hanging.status,error:hanging.error.message,startupMilliseconds:hanging.startupMilliseconds,cleanupMilliseconds:liveCleanup}],liveDeadlineMilliseconds:2000,cleanupSettlementMilliseconds:1000}));
  const {superviseContainer}=require('../scripts/test-arch-container.cjs');
  for(const failed of [null,'create','start','stop','cp','rm']){
    const seen=[];
    const evidence=await superviseContainer({name:'owned-fixture',image:'declared-fixture',bundle:'/fixture/cut.bundle',out:'/fixture/evidence',revision:'fixture',profile:'full-qa',maximumMs:180000,invoke:async(args,remaining)=>{seen.push(args[0]);assert.ok(remaining>0&&remaining<=180000);return {status:args[0]===failed?1:0,stdout:'retained output',stderr:''}}});
    assert.equal(evidence.passed,failed===null);
    assert.equal(seen.at(-1),'rm','daemon-owned container cleanup is attempted after every failure');
    assert.ok(seen.indexOf('stop')<seen.indexOf('cp'),'stop work before retaining its evidence');
    assert.equal(evidence.commands.find(c=>c.args[0]==='create').stdout,'retained output');
  }
  let reading=0;
  const exhausted=await superviseContainer({name:'owned-fixture',image:'declared',bundle:'bundle',out:'out',revision:'fixture',profile:'full-qa',maximumMs:180000,now:()=>reading++?200000:0,invoke:async()=>assert.fail('expired lifecycle must not start a Docker command')});
  assert.equal(exhausted.passed,false);assert.match(exhausted.error,/budget exhausted/);
  const {main}=require('../scripts/test-arch-container.cjs'),fixture=fs.mkdtempSync(path.join(os.tmpdir(),'arch-container-admission-'));
  fs.mkdirSync(path.join(fixture,'scripts'));
  fs.writeFileSync(path.join(fixture,'test-budget.arch.json'),JSON.stringify({profiles:{'full-qa':{maximumSeconds:180}}}));
  fs.writeFileSync(path.join(fixture,'scripts/qa_linux.Dockerfile'),'declared image');fs.writeFileSync(path.join(fixture,'requirements-dev.txt'),'declared requirements');
  const deps={root:fixture,readGit:args=>args[0]==='status'?'':'frozen-head',bundleGit:filename=>fs.writeFileSync(filename,'frozen bundle'),invoke:async()=>({status:0,stdout:'image-identity'})};
  try{
    const evidence=await main(deps);assert.equal(evidence.passed,false,'missing copied receipt cannot authorize the cut');process.exitCode=0;assert.equal(evidence.revision,'frozen-head');assert.equal(evidence.imageIdentity,'image-identity');
    await assert.rejects(main({...deps,argv:['node','entry','--profile','undeclared']}),/Unknown declared/);
    await assert.rejects(main({...deps,readGit:()=> 'dirty'}),/clean committed/);
    await assert.rejects(main({...deps,invoke:async()=>({status:1})}),/Prepare the declared pinned Linux image/);
  }finally{fs.rmSync(fixture,{recursive:true,force:true});}
  // Constructed receipts exercise admission in memory or temporary controlled
  // copy fixtures; they never authorize an actual desktop build.
  const {admitFullQaReceipt,harnessFiles,parseQueueOutput}=require('../scripts/arch-receipt.cjs'),crypto=require('node:crypto'),root=path.resolve(__dirname,'..');
  const base=JSON.parse(fs.readFileSync(path.join(root,'test-budget.arch.json'))),policy={...base,...base.profiles['full-qa'],profile:'full-qa'};
  const identity=file=>({file,sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex')});
  const declared=JSON.parse(fs.readFileSync(path.join(root,'tests/fixtures/qa-queue.json'))),queue=[...declared.STATIC,...declared.BROWSER,...declared.TAIL];
  const syntaxCases=['src','mcp'].reduce((n,folder)=>n+fs.readdirSync(path.join(root,folder)).filter(file=>file.endsWith(folder==='src'?'.js':'.mjs')).length,0);
  const candidate={command:['/usr/bin/node','--test','--test-concurrency=1','tests/arch_observation.test.cjs'],environment:{platform:'linux',node:process.version,ARCH_TEST_PROFILE:'full-qa',ARCH_QA_WORKERS:String(policy.maximumWorkers)},formatVersion:1,passed:true,status:0,error:null,staticRegistration:true,policy,nodeCases:9,cases:9+queue.length+syntaxCases,elapsedSeconds:100,coveragePercent:100,files:policy.sourceScope.map(file=>{const total=fs.readFileSync(path.join(root,file),'utf8').split('\n').filter(line=>line.trim()&&!line.trim().startsWith('//')).length;return {...identity(file),total,covered:total,imported:true}}),staticFiles:policy.staticScope.map(identity),queueResults:[{command:['python','tests/arch_browser_coverage.py','--full-qa'],candidate:'--full-qa',status:0,error:null,syntaxCases,suiteSummary:queue.length,actualCases:queue.length+syntaxCases,timings:queue.map(candidate=>({candidate,status:'PASS',seconds:1}))}],dependencyIdentity:{builtins:process.version,localFiles:harnessFiles(root).map(identity)}};
  assert.equal(admitFullQaReceipt(candidate,root,base),true,'complete matching receipt is admissible');
  const mutations=[r=>r.environment.platform='win32',r=>delete r.environment,r=>r.environment.ARCH_TEST_PROFILE='routine',r=>r.environment.ARCH_QA_WORKERS='9',r=>r.command.push('--test-name-pattern=one'),r=>r.queueResults[0].command.push('--quick'),r=>r.dependencyIdentity.builtins='different',r=>delete r.formatVersion,r=>r.passed=false,r=>r.status=1,r=>r.error='deadline',r=>r.staticRegistration=false,r=>r.policy.maximumSeconds++,r=>r.policy.sourceScope.pop(),r=>r.policy.staticScope.pop(),r=>r.files=[],r=>r.files.pop(),r=>r.files.push(r.files[0]),r=>r.files[0].file='extra.js',r=>r.files[0].sha256='incorrect',r=>r.staticFiles=[],r=>r.staticFiles.push(r.staticFiles[0]),r=>r.staticFiles[0].sha256='incorrect',r=>r.files[0].total++,r=>r.files[0].covered=-1,r=>r.files[0].covered++,r=>r.files[0].imported=false,r=>r.coveragePercent=NaN,r=>r.coveragePercent=74,r=>r.elapsedSeconds=1201,r=>r.elapsedSeconds=-1,r=>r.nodeCases=8,r=>r.queueResults=[],r=>r.queueResults[0].candidate='--routine-qa',r=>r.queueResults[0].status=1,r=>r.queueResults[0].syntaxCases--,r=>r.queueResults[0].suiteSummary--,r=>r.queueResults[0].actualCases--,r=>r.queueResults[0].timings.pop(),r=>r.queueResults[0].timings[0].status='FAIL',r=>r.queueResults[0].timings[0].seconds=-1,r=>r.queueResults[0].timings[0].candidate=r.queueResults[0].timings[1].candidate,r=>r.cases--,r=>r.dependencyIdentity.localFiles=[],r=>r.dependencyIdentity.localFiles.pop(),r=>r.dependencyIdentity.localFiles.push(r.dependencyIdentity.localFiles[0]),r=>r.dependencyIdentity.localFiles[0].sha256='incorrect'];
  for(const [number,change] of mutations.entries()){const altered=structuredClone(candidate);change(altered);assert.equal(admitFullQaReceipt(altered,root,base),false,'invalid receipt variant '+number+' is refused');}
  assert.equal(admitFullQaReceipt(null,root,base),false,'unreadable evidence is refused');
  const windowsNames=structuredClone(candidate);windowsNames.dependencyIdentity.localFiles.forEach(file=>file.file=file.file.replace(/\//g,'\\'));assert.equal(admitFullQaReceipt(windowsNames,root,base),true,'cross-platform path separators preserve exact byte identity');
  const parsed=parseQueueOutput('CONTRAST QA PASS ignored\nCONCERNS QA FAIL ignored\nQA PASS tests/a.py (1.20s)\r\nQA FAIL tests/b.py (2.30s)\nRC QA PASS: 2 suites + 41 JS syntax checks (3.50s test time)\n');assert.equal(parsed.actualCases,43);assert.equal(parsed.timings.length,2);assert.equal(parsed.suiteSummary,2);assert.equal(parsed.timings[1].status,'FAIL');
  const copiedFixture=fs.mkdtempSync(path.join(os.tmpdir(),'arch-copied-authority-'));
  try{
    for(const file of new Set([...policy.sourceScope,...policy.staticScope,...harnessFiles(root)])){const destination=path.join(copiedFixture,file);fs.mkdirSync(path.dirname(destination),{recursive:true});fs.copyFileSync(path.join(root,file),destination);}
    for(const mode of ['valid','missing','malformed','unmet']){
      const evidence=await main({root:copiedFixture,argv:['node','entry','--profile','full-qa'],readGit:args=>args[0]==='status'?'':'frozen-head',bundleGit:filename=>fs.writeFileSync(filename,'controlled bundle'),invoke:async args=>{
        if(args[0]==='cp'&&mode!=='missing'){const folder=path.join(args[2],'.arch-test-evidence','1');fs.mkdirSync(folder,{recursive:true});fs.writeFileSync(path.join(folder,'evidence.json'),mode==='malformed'?'invalid':JSON.stringify({...candidate,passed:mode==='valid'}));}
        return {status:0,stdout:'controlled-image-identity'};
      }});
      process.exitCode=0;
      assert.equal(evidence.passed,mode==='valid','copied '+mode+' receipt controls outer admission');
      if(mode==='valid'){assert.equal(evidence.innerReceipt.sha256,crypto.createHash('sha256').update(JSON.stringify(candidate)).digest('hex'));assert.match(evidence.innerReceipt.file,/1\/evidence.json$/);}
      else assert.equal(evidence.innerReceipt,undefined);
      assert.equal(evidence.removed,true,'failed evidence admission retains completed container cleanup');
    }
  }finally{fs.rmSync(copiedFixture,{recursive:true,force:true});}
  console.log(JSON.stringify({receiptAdmissionVariants:mutations.length+3,requiredNodeCases:9,requiredSuites:queue.length,requiredSyntaxChecks:syntaxCases,sourceFiles:policy.sourceScope.length,staticFiles:policy.staticScope.length}));
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
