'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const syntaxFiles=root=>['src','mcp'].flatMap(folder=>fs.readdirSync(path.join(root,folder)).filter(file=>file.endsWith(folder==='src'?'.js':'.mjs')).map(file=>folder+'/'+file));
const harnessFiles=root=>[...syntaxFiles(root),...fs.readdirSync(path.join(root,'tests')).filter(file=>file.endsWith('.py')||file.endsWith('.cjs')).map(file=>'tests/'+file),'build.py','scripts/golden_run.py','scripts/qa_linux.py','scripts/test-arch-supervised.cjs','scripts/budget-process.cjs','scripts/budget-job.ps1','scripts/test-arch-container.cjs','scripts/arch-receipt.cjs','scripts/qa_linux.Dockerfile','requirements-dev.txt','test-budget.arch.json','scripts/qa.py'];
function parseQueueOutput(stdout){
  const timings=[...stdout.matchAll(/^QA (PASS|FAIL) (\S+) \(([\d.]+)s\)\r?$/gm)].map(m=>({status:m[1],candidate:m[2],seconds:Number(m[3])}));
  const summary=stdout.match(/^RC QA PASS: (\d+) suites \+ (\d+) JS syntax checks \([\d.]+s test time\)\r?$/m),syntaxCases=Number(summary?.[2]||0);
  return {timings,syntaxCases,suiteSummary:Number(summary?.[1]||0),actualCases:timings.length+syntaxCases};
}
const exact=(actual,expected)=>Array.isArray(actual)&&actual.length===expected.length&&new Set(actual).size===actual.length&&actual.every(value=>expected.includes(value));
function admitFullQaReceipt(receipt,root,base){
  try{
    const policy={...base,...base.profiles['full-qa'],profile:'full-qa'},r=receipt;
    if(r.formatVersion!==1||!r.passed||r.status!==0||r.error!==null||!r.staticRegistration)return false;
    if(r.environment?.platform!=='linux'||typeof r.environment.node!=='string'||r.dependencyIdentity?.builtins!==r.environment.node||r.environment.ARCH_TEST_PROFILE!=='full-qa'||r.environment.ARCH_QA_WORKERS!==String(policy.maximumWorkers))return false;
    if(!Array.isArray(r.command)||r.command.length!==4||path.posix.basename(r.command[0].replace(/\\/g,'/'))!=='node'||r.command[1]!=='--test'||r.command[2]!=='--test-concurrency=1'||r.command[3]!=='tests/arch_observation.test.cjs')return false;
    for(const key of ['version','profile','maximumCases','maximumSeconds','minimumExecutableLineCoverage','maximumWorkers','expectedNodeCases'])if(r.policy[key]!==policy[key])return false;
    if(!exact(r.policy.sourceScope,policy.sourceScope)||!exact(r.policy.staticScope,policy.staticScope))return false;
    const inventory=(files,scope)=>exact(files?.map(file=>file.file),scope)&&files.every(file=>file.sha256===sha(path.join(root,file.file)));
    if(!inventory(r.files,policy.sourceScope)||!inventory(r.staticFiles,policy.staticScope))return false;
    let total=0,covered=0;
    for(const file of r.files){
      const denominator=fs.readFileSync(path.join(root,file.file),'utf8').split('\n').filter(line=>line.trim()&&!line.trim().startsWith('//')).length;
      if(file.total!==denominator||!Number.isInteger(file.covered)||file.covered<0||file.covered>denominator||(!file.imported&&file.covered))return false;
      total+=denominator;covered+=file.covered;
    }
    const percent=100*covered/total;
    if(!Number.isFinite(r.coveragePercent)||Math.abs(r.coveragePercent-percent)>1e-9||percent<policy.minimumExecutableLineCoverage)return false;
    if(!Number.isFinite(r.elapsedSeconds)||r.elapsedSeconds<0||r.elapsedSeconds>policy.maximumSeconds)return false;
    const declared=JSON.parse(fs.readFileSync(path.join(root,'tests/fixtures/qa-queue.json'),'utf8')),queue=[...declared.STATIC,...declared.BROWSER,...declared.TAIL];
    if(r.nodeCases!==policy.expectedNodeCases||r.queueResults?.length!==1)return false;
    const q=r.queueResults[0],syntaxCount=syntaxFiles(root).length;
    if(q.candidate!=='--full-qa'||q.status!==0||q.error!==null||q.suiteSummary!==queue.length||q.syntaxCases!==syntaxCount||q.actualCases!==queue.length+syntaxCount)return false;
    if(JSON.stringify(q.command)!==JSON.stringify(['python','tests/arch_browser_coverage.py','--full-qa']))return false;
    if(!exact(q.timings?.map(check=>check.candidate),queue)||q.timings.some(check=>check.status!=='PASS'||!Number.isFinite(check.seconds)||check.seconds<0))return false;
    if(r.cases!==policy.expectedNodeCases+queue.length+syntaxCount||r.cases>policy.maximumCases)return false;
    const dependencies=r.dependencyIdentity?.localFiles;
    if(!Array.isArray(dependencies)||!dependencies.length)return false;
    const names=dependencies.map(file=>file.file.replace(/\\/g,'/'));
    if(new Set(names).size!==names.length||harnessFiles(root).some(file=>!names.includes(file)))return false;
    if(dependencies.some((file,index)=>names[index].startsWith('/')||names[index].split('/').includes('..')||file.sha256!==sha(path.join(root,names[index]))))return false;
    return true;
  }catch{return false}
}
module.exports={admitFullQaReceipt,harnessFiles,parseQueueOutput};
