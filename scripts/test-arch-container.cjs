'use strict';
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),crypto=require('node:crypto');
const {spawnBounded}=require('./budget-process.cjs');
const {admitFullQaReceipt}=require('./arch-receipt.cjs');

// Killing a Docker client never terminates the daemon-owned container.
// Reserve cleanup time, retain logs/evidence, then remove our named container.
async function superviseContainer({name,image,bundle,out,revision,profile,maximumMs,invoke,now=Date.now}){
  const started=now(),commands=[],cleanupReserve=20000;
  let created=false,startStatus=null,copied=false,removed=false,error=null;
  const call=async(args,reserve=cleanupReserve)=>{
    const remaining=maximumMs-(now()-started)-reserve;
    if(remaining<=0)throw new Error('Container lifecycle budget exhausted');
    const result=await invoke(args,remaining);commands.push({args,status:result.status,error:result.error?.message||null,stdout:result.stdout||'',stderr:result.stderr||''});
    if(args[0]==='start')startStatus=result.status;
    if(result.status!==0)throw new Error(result.error?.message||'Docker command failed: '+args[0]);
    return result;
  };
  try{
    const script='git clone /source/cut.bundle /work && cd /work && git checkout --detach "$CUT_REVISION" && node scripts/test-arch-supervised.cjs --profile "$CUT_PROFILE"';
    // Even an interrupted create can have reached the daemon. The unique name
    // remains ours to clean up after an ambiguous client result.
    created=true;
    await call(['create','--name',name,'--init','--ipc=host','--label','arch.cut='+revision,'--mount','type=bind,source='+bundle+',target=/source/cut.bundle,readonly','--env','CUT_REVISION='+revision,'--env','CUT_PROFILE='+profile,image,'sh','-c',script]);
    await call(['start','--attach',name]);
  }catch(failure){error=failure.message}
  finally{
    if(created){
      try{await call(['stop','--time','0',name],15000)}catch(failure){error=error||failure.message}
      try{await call(['cp',name+':/work/.arch-test-evidence',out],5000);copied=true}catch(failure){error=error||failure.message}
      try{await call(['rm','--force',name],0);removed=true}catch(failure){error=error||failure.message}
    }
  }
  const elapsedMilliseconds=now()-started;
  return {name,image,revision,profile,commands,startStatus,copied,removed,error,elapsedMilliseconds,maximumMs,passed:startStatus===0&&copied&&removed&&!error&&elapsedMilliseconds<=maximumMs};
}

async function main(dependencies={}){
  const root=dependencies.root||path.resolve(__dirname,'..'),base=JSON.parse(fs.readFileSync(path.join(root,'test-budget.arch.json')));
  const argv=dependencies.argv||process.argv,position=argv.indexOf('--profile'),profile=position<0?'full-qa':argv[position+1];
  if(!base.profiles?.[profile])throw new Error('Unknown declared container profile');
  const policy={...base,...base.profiles[profile]};
  const read=args=>(dependencies.readGit?dependencies.readGit(args):cp.execFileSync('git',args,{cwd:root,encoding:'utf8',timeout:30000})).trim();
  if(read(['status','--porcelain','--untracked-files=no']))throw new Error('Container proof requires a clean committed cut');
  const revision=read(['rev-parse','HEAD']);
  const folder=path.join(root,'.arch-test-evidence','container-'+Date.now());fs.mkdirSync(folder,{recursive:true});
  const bundle=path.join(folder,'cut.bundle');
  if(dependencies.bundleGit)dependencies.bundleGit(bundle);else cp.execFileSync('git',['bundle','create',bundle,'HEAD'],{cwd:root,timeout:30000});
  const digest=crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'scripts/qa_linux.Dockerfile'))).update(fs.readFileSync(path.join(root,'requirements-dev.txt'))).digest('hex').slice(0,12);
  const image='schematically-qa-linux:'+digest;
  const invoke=dependencies.invoke||((args,timeout)=>spawnBounded('docker',args,{cwd:root,env:process.env,timeout}));
  // Image construction is bounded environment preparation before the test clock.
  const inspected=await invoke(['image','inspect','--format','{{.Id}}',image],30000);
  if(inspected.status!==0)throw new Error('Prepare the declared pinned Linux image before running tests: '+image);
  const imageIdentity=inspected.stdout.trim();
  const executionStarted=Date.now();
  const evidence=await superviseContainer({name:'arch-cut-'+process.pid+'-'+crypto.randomBytes(6).toString('hex'),image:imageIdentity,bundle,out:folder,revision,profile,maximumMs:policy.maximumSeconds*1000,invoke});
  evidence.imageIdentity=imageIdentity;evidence.imageTag=image;evidence.policy=policy;
  if(evidence.passed&&profile==='full-qa'){
    try{
      const copiedRoot=path.join(folder,'.arch-test-evidence'),entries=fs.readdirSync(copiedRoot,{withFileTypes:true});
      if(entries.length>1000)throw new Error('Copied receipt inventory exceeds its bound');
      const receipts=entries.filter(entry=>entry.isDirectory()&&/^\d+$/.test(entry.name)).map(entry=>path.join(copiedRoot,entry.name,'evidence.json'));
      if(receipts.length!==1)throw new Error('Exactly one copied authoritative inner receipt is required');
      const file=receipts[0];if(fs.statSync(file).size>1048576)throw new Error('Copied receipt exceeds one MiB');
      const bytes=fs.readFileSync(file),receipt=JSON.parse(bytes);
      if(!admitFullQaReceipt(receipt,root,base))throw new Error('Copied inner receipt does not authorize this frozen cut');
      evidence.innerReceipt={file:path.relative(folder,file).replace(/\\/g,'/'),sha256:crypto.createHash('sha256').update(bytes).digest('hex')};
    }catch(error){evidence.passed=false;evidence.error=error.message}
  }
  evidence.elapsedMilliseconds=Date.now()-executionStarted;
  evidence.passed=evidence.passed&&evidence.elapsedMilliseconds<=evidence.maximumMs;
  fs.writeFileSync(path.join(folder,'container-evidence.json'),JSON.stringify(evidence,null,2));
  console.log(JSON.stringify({evidence:path.join(folder,'container-evidence.json'),passed:evidence.passed,elapsedSeconds:evidence.elapsedMilliseconds/1000}));
  process.exitCode=evidence.passed?0:1;
  return evidence;
}
module.exports={superviseContainer,main};
if(require.main===module)main().catch(error=>{console.error(error);process.exitCode=1});
