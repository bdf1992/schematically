'use strict';
const cp=require('node:child_process'),path=require('node:path');

// The budget owner awaits every child. A deadline terminates its whole process
// tree even after its original root exits and descendants retain its pipes.
function spawnBounded(command,args,options){
  return new Promise(resolve=>{
    const {timeout,readiness,...spawnOptions}=options;
    if(readiness&&(!(readiness.maximumStartupMs>0)||!readiness.token))throw new Error('Readiness requires an explicit startup bound and token');
    const windows=process.platform==='win32';
    // PowerShell 7 compiles Add-Type in-process. Classic Windows PowerShell
    // starts a compiler child before the Job Object can own native work.
    const launch=windows?['pwsh.exe',['-NoLogo','-NoProfile','-NonInteractive','-File',path.join(__dirname,'budget-job.ps1'),'-Command',command,'-ArgumentsJsonBase64',Buffer.from(JSON.stringify(args),'utf8').toString('base64')]]:[command,args];
    const child=cp.spawn(...launch,{...spawnOptions,windowsHide:true,detached:!windows});
    const started=Date.now();
    let stdout='',stderr='',error=null,settled=false,cleanupTimer,timer,ready=!readiness,startupMilliseconds=0;
    const finish=status=>{if(settled)return;settled=true;clearTimeout(timer);clearTimeout(cleanupTimer);resolve({stdout,stderr,status,error,startupMilliseconds,elapsedMilliseconds:Date.now()-started})};
    child.stdout?.on('data',data=>{stdout+=data;process.stdout.write(data);if(!ready&&stdout.includes(readiness.token)){ready=true;startupMilliseconds=Date.now()-started;clearTimeout(timer);timer=setTimeout(expire,timeout)}});
    child.stderr?.on('data',data=>{stderr+=data;process.stderr.write(data)});
    child.on('error',failure=>{error=failure});
    const expire=()=>{
      error=new Error(ready?'Supervised process-tree deadline exceeded':'Supervised readiness startup deadline exceeded');
      // Windows launcher owns a kill-on-close Job Object before native work
      // starts. POSIX retains the process group even if its leader has exited.
      if(windows){if(child.exitCode===null&&!child.kill())error=new Error('Supervised Job Object launcher termination failed');}
      else{try{process.kill(-child.pid,'SIGKILL')}catch(failure){if(failure.code!=='ESRCH')error=failure}}
      cleanupTimer=setTimeout(()=>{child.stdout?.destroy();child.stderr?.destroy();finish(null)},1000);
    };
    timer=setTimeout(expire,readiness?readiness.maximumStartupMs:timeout);
    child.on('close',finish);
  });
}
module.exports={spawnBounded};
