// A durable document store over the filesystem: the semantics mcp/server.mjs's saveDocument had
// before the split (mkdir, write file.tmp, rename). Only an absent file reads as null;
// other read failures refuse. This adapter owns node:fs/node:path effects.
import fs from 'node:fs';
import path from 'node:path';

export function createFileStore(file){
  return {
    read(){
      try{return fs.readFileSync(file,'utf8')}catch(error){
        if(error.code==='ENOENT')return null;
        throw new Error(`DOCUMENT_READ_FAILED: ${error.message}`,{cause:error});
      }
    },
    write(text){
      fs.mkdirSync(path.dirname(file),{recursive:true});
      const tmp=file+'.tmp';
      fs.writeFileSync(tmp,text);
      fs.renameSync(tmp,file);
    }
  };
}
