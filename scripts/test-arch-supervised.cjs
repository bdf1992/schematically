const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),policy=JSON.parse(fs.readFileSync(path.join(root,'test-budget.arch.json')));
const out=path.join(root,'.arch-test-evidence',Date.now().toString());fs.mkdirSync(out,{recursive:true});
const coverage=path.join(out,'coverage');fs.mkdirSync(coverage);
const started=Date.now(),command=['--test','--test-concurrency=1','tests/arch_observation.test.cjs'];
const result=cp.spawnSync(process.execPath,command,{cwd:root,encoding:'utf8',timeout:policy.maximumSeconds*1000,env:{...process.env,NODE_V8_COVERAGE:coverage}});
process.stdout.write(result.stdout||'');process.stderr.write(result.stderr||'');
const entries=fs.readdirSync(coverage).flatMap(f=>JSON.parse(fs.readFileSync(path.join(coverage,f),'utf8')).result||[]);
const files=policy.sourceScope.map(file=>{
  const text=fs.readFileSync(path.join(root,file),'utf8'),url=require('node:url').pathToFileURL(path.join(root,file)).href;
  const scripts=entries.filter(e=>e.url===url||e.url===path.join(root,file));
  let offset=0,total=0,covered=0;
  for(const line of text.split('\n')){
    // Conservative line denominator: every nonblank non-comment source line is
    // counted, including unimported files and mixed code/comment lines.
    if(line.trim()&&!line.trim().startsWith('//')){
      total++;
      const pos=offset+line.search(/\S/);
      if(scripts.some(script=>{
        const ranges=script.functions.flatMap(f=>f.ranges).filter(r=>r.startOffset<=pos&&r.endOffset>pos).sort((a,b)=>(a.endOffset-a.startOffset)-(b.endOffset-b.startOffset));
        return ranges[0]?.count>0;
      }))covered++;
    }
    offset+=line.length+1;
  }
  return {file,sha256:crypto.createHash('sha256').update(text).digest('hex'),total,covered,imported:scripts.length>0};
});
const total=files.reduce((s,f)=>s+f.total,0),covered=files.reduce((s,f)=>s+f.covered,0),percent=100*covered/total;
const cases=Number((result.stdout||'').match(/(?:#|ℹ) tests (\d+)/)?.[1]||0);
fs.writeFileSync(path.join(out,'runner.stdout.txt'),result.stdout||'');
fs.writeFileSync(path.join(out,'runner.stderr.txt'),result.stderr||'');
const dependencyFiles=entries.filter(e=>e.url.startsWith(require('node:url').pathToFileURL(root+path.sep).href)).map(e=>require('node:url').fileURLToPath(e.url)).filter(f=>fs.existsSync(f));
const dependencies=[...new Set([...dependencyFiles,__filename,path.join(root,'test-budget.arch.json')])].sort().map(file=>({file:path.relative(root,file),sha256:crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')}));
const staticFiles=policy.staticScope.map(file=>({file,sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex')}));
const evidence={policy,command:[process.execPath,...command],environment:{node:process.version,platform:process.platform,NODE_V8_COVERAGE:coverage},dependencyIdentity:{builtins:process.version,localFiles:dependencies},coverageMeasure:'Conservative executable-line approximation: all nonblank non-line-comment source lines, innermost V8 range at first code character; uncovered files remain in denominator',elapsedSeconds:(Date.now()-started)/1000,cases,files,coveragePercent:percent,status:result.status,error:result.error?.message||null,staticRegistration:fs.readFileSync(path.join(root,'index.source.html'),'utf8').includes('src/88-kore-execution.js')};
evidence.passed=result.status===0&&cases>0&&cases<=policy.maximumCases&&evidence.elapsedSeconds<=policy.maximumSeconds&&percent>=policy.minimumExecutableLineCoverage&&evidence.staticRegistration;
evidence.staticFiles=staticFiles;
fs.writeFileSync(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2));
console.log(JSON.stringify({evidence:path.join(out,'evidence.json'),cases,coveragePercent:percent,elapsedSeconds:evidence.elapsedSeconds,passed:evidence.passed}));
process.exitCode=evidence.passed?0:1;
