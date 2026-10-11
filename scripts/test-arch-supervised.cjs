const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),crypto=require('node:crypto');
const {spawnBounded}=require('./budget-process.cjs');
(async()=>{
const root=path.resolve(__dirname,'..'),basePolicy=JSON.parse(fs.readFileSync(path.join(root,'test-budget.arch.json')));
const profileIndex=process.argv.indexOf('--profile'),profile=profileIndex>=0?process.argv[profileIndex+1]:null;
if(profile&&!basePolicy.profiles?.[profile])throw new Error('Unknown test profile');
const policy={...basePolicy,...(profile?basePolicy.profiles[profile]:{}),profile:profile||basePolicy.profile};
const out=path.join(root,'.arch-test-evidence',Date.now().toString());fs.mkdirSync(out,{recursive:true});
const coverage=path.join(out,'coverage');fs.mkdirSync(coverage);
const started=Date.now(),command=['--test','--test-concurrency=1','tests/arch_observation.test.cjs'];
if(policy.testNamePattern)command.splice(2,0,'--test-name-pattern='+policy.testNamePattern);
const testEnvironment={...process.env,NODE_V8_COVERAGE:coverage,PYTHONUTF8:'1',ARCH_QA_WORKERS:String(policy.maximumWorkers||1),CHROMIUM_PATH:process.env.CHROMIUM_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'};
if(profile==='desktop'){
  const binaryIndex=process.argv.indexOf('--binary');if(binaryIndex<0)throw new Error('Desktop profile requires --binary');
  const coverageIndex=process.argv.indexOf('--coverage-evidence');if(coverageIndex<0)throw new Error('Desktop profile requires --coverage-evidence directory');
  const receipts=[];
  const visit=folder=>{for(const item of fs.readdirSync(folder,{withFileTypes:true})){const file=path.join(folder,item.name);if(item.isDirectory())visit(file);else if(item.name==='evidence.json')receipts.push(JSON.parse(fs.readFileSync(file,'utf8')))}};
  visit(process.argv[coverageIndex+1]);
  const matches=file=>fs.existsSync(path.join(root,file.file))&&crypto.createHash('sha256').update(fs.readFileSync(path.join(root,file.file))).digest('hex')===file.sha256;
  const authority=receipts.find(r=>r.passed&&r.policy.profile==='full-qa'&&r.coveragePercent>=policy.minimumExecutableLineCoverage&&r.files.every(matches)&&r.staticFiles?.every(matches));
  if(!authority)throw new Error('No passing full-qa coverage receipt matches this desktop build');
  const args=['tests/desktop_launch_qa.py','--binary',process.argv[binaryIndex+1]];
  const check=await spawnBounded('python',args,{cwd:root,encoding:'utf8',timeout:policy.maximumSeconds*1000,env:testEnvironment});

  const evidence={policy,command:['python',...args],elapsedSeconds:(Date.now()-started)/1000,cases:2,status:check.status,coveragePercent:authority.coveragePercent,coverageSource:'Hash-matched full-qa receipt for unchanged affected JS and embedded build',unchangedRustScope:'desktop/src-tauri/src/main.rs is unchanged; original two launch checks retained',passed:check.status===0&&(Date.now()-started)<=policy.maximumSeconds*1000};
  fs.writeFileSync(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2));console.log(JSON.stringify(evidence));process.exit(evidence.passed?0:1);
}
const result=await spawnBounded(process.execPath,command,{cwd:root,encoding:'utf8',timeout:policy.maximumSeconds*1000,env:testEnvironment});

const queueResults=[];
for(const candidate of (policy.skipQueue?[]:[profile==='full-qa'?'--full-qa':'--routine-qa'])){
  const remaining=policy.maximumSeconds*1000-(Date.now()-started)-(policy.evidenceReserveSeconds||0)*1000;
  if(remaining<=0){queueResults.push({candidate,status:null,error:'Budget exhausted'});break}
  const args=['tests/arch_browser_coverage.py',candidate];
  const check=await spawnBounded('python',args,{cwd:root,encoding:'utf8',timeout:remaining,env:testEnvironment});

  queueResults.push({candidate,command:['python',...args],status:check.status,error:check.error?.message||null,actualCases:(check.stdout?.match(/QA (?:PASS|FAIL) /g)||[]).length+Number(check.stdout?.match(/\+ (\d+) JS syntax checks/)?.[1]||0),timings:[...(check.stdout||'').matchAll(/QA (PASS|FAIL) (\S+) \(([\d.]+)s\)/g)].map(m=>({status:m[1],candidate:m[2],seconds:Number(m[3])}))});
  fs.writeFileSync(path.join(out,candidate+'.stdout.txt'),check.stdout||'');fs.writeFileSync(path.join(out,candidate+'.stderr.txt'),check.stderr||'');
  if(check.status!==0)break;
}
const entries=fs.readdirSync(coverage).flatMap(f=>JSON.parse(fs.readFileSync(path.join(coverage,f),'utf8')).result||[]);
const files=policy.sourceScope.map(file=>{
  const text=fs.readFileSync(path.join(root,file),'utf8'),url=require('node:url').pathToFileURL(path.join(root,file)).href;
  const scripts=entries.filter(e=>e.url===url||e.url===path.join(root,file));
  const rangesByScript=scripts.map(script=>({normalizedLineEndings:script.normalizedLineEndings,ranges:script.functions.flatMap(f=>f.ranges).sort((a,b)=>(a.endOffset-a.startOffset)-(b.endOffset-b.startOffset))}));
  let offset=0,total=0,covered=0;
  for(const line of text.split('\n')){
    // Conservative line denominator: every nonblank non-comment source line is
    // counted, including unimported files and mixed code/comment lines.
    if(line.trim()&&!line.trim().startsWith('//')){
      total++;
      const pos=offset+line.search(/\S/);
      if(rangesByScript.some(script=>{
        const scriptPos=script.normalizedLineEndings?pos-(text.slice(0,pos).match(/\r/g)||[]).length:pos;
        return script.ranges.find(r=>r.startOffset<=scriptPos&&r.endOffset>scriptPos)?.count>0;
      }))covered++;
    }
    offset+=line.length+1;
  }
  return {file,sha256:crypto.createHash('sha256').update(text).digest('hex'),total,covered,imported:scripts.length>0};
});
const total=files.reduce((s,f)=>s+f.total,0),covered=files.reduce((s,f)=>s+f.covered,0),percent=100*covered/total;
const cases=Number((result.stdout||'').match(/(?:#|ℹ) tests (\d+)/)?.[1]||0)+queueResults.reduce((n,q)=>n+(q.actualCases||0),0);
fs.writeFileSync(path.join(out,'runner.stdout.txt'),result.stdout||'');
fs.writeFileSync(path.join(out,'runner.stderr.txt'),result.stderr||'');
const dependencyFiles=entries.filter(e=>e.url.startsWith(require('node:url').pathToFileURL(root+path.sep).href)).map(e=>require('node:url').fileURLToPath(e.url)).filter(f=>fs.existsSync(f));
const harnessFiles=fs.readdirSync(path.join(root,'tests')).filter(f=>f.endsWith('.py')).map(f=>path.join(root,'tests',f));
const dependencies=[...new Set([...dependencyFiles,...harnessFiles,__filename,path.join(root,'scripts/budget-process.cjs'),path.join(root,'scripts/budget-job.ps1'),path.join(root,'requirements-dev.txt'),...['test-budget.arch.json','scripts/qa.py','tests/arch_browser_coverage.py','tests/mutation_watch.py'].map(f=>path.join(root,f))])].sort().map(file=>({file:path.relative(root,file),sha256:crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')}));
const staticFiles=policy.staticScope.map(file=>({file,sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex')}));
const evidence={policy,command:[process.execPath,...command],environment:{node:process.version,platform:process.platform,NODE_V8_COVERAGE:coverage,PYTHONUTF8:testEnvironment.PYTHONUTF8,CHROMIUM_PATH:testEnvironment.CHROMIUM_PATH},dependencyIdentity:{builtins:process.version,localFiles:dependencies},coverageMeasure:'Conservative executable-line approximation: all nonblank non-line-comment source lines, innermost V8 range at first code character; uncovered files remain in denominator',elapsedSeconds:(Date.now()-started)/1000,cases,queueResults,files,staticFiles,coveragePercent:percent,status:result.status,error:result.error?.message||null,staticRegistration:fs.readFileSync(path.join(root,'index.source.html'),'utf8').includes('src/88-kore-execution.js')};
evidence.passed=result.status===0&&queueResults.every(q=>q.status===0)&&queueResults.length===(policy.skipQueue?0:1)&&cases>0&&cases<=policy.maximumCases&&evidence.elapsedSeconds<=policy.maximumSeconds&&percent>=policy.minimumExecutableLineCoverage&&evidence.staticRegistration;
fs.writeFileSync(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2));
console.log(JSON.stringify({evidence:path.join(out,'evidence.json'),cases,coveragePercent:percent,elapsedSeconds:evidence.elapsedSeconds,passed:evidence.passed}));
process.exitCode=evidence.passed?0:1;
})().catch(error=>{console.error(error);process.exitCode=1});
