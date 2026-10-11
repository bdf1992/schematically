import fs from 'node:fs';
import path from 'node:path';

// The operator names one snapshot file at process startup. Diagram data cannot
// select a file, and this observation endpoint cannot change the runtime.
export function createKoreExecutionRoute(file,read=fs.readFileSync){
  const source=file?path.resolve(file):null;
  return function koreExecution(req,res,pathname){
    if(pathname!=='/kore/execution')return false;
    let status=200,value;
    if(req.method!=='GET'){status=405;value={ok:false,code:'READ_ONLY'}}
    else if(!source){status=503;value={ok:false,code:'KORE_SOURCE_NOT_CONFIGURED'}}
    else{
      try{value=JSON.parse(read(source,'utf8'))}
      catch(error){status=503;value={ok:false,code:'KORE_SNAPSHOT_UNAVAILABLE',message:String(error.message)}}
    }
    res.writeHead(status,{'content-type':'application/json; charset=utf-8','cache-control':'no-store','allow':'GET'});
    res.end(JSON.stringify(value));
    return true;
  };
}
