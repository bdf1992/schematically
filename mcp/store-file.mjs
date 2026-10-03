// A durable document store over the filesystem: the semantics mcp/server.mjs's saveDocument had
// before the split (mkdir, write file.tmp, rename), and the same read-or-null loadDocument relied
// on. The only module here, besides server.mjs, that is allowed to import node:fs/node:path.
import fs from 'node:fs';
import path from 'node:path';

export function createFileStore(file){
  return {
    read(){
      try{return fs.readFileSync(file,'utf8')}catch(_){return null}
    },
    write(text){
      fs.mkdirSync(path.dirname(file),{recursive:true});
      const tmp=file+'.tmp';
      fs.writeFileSync(tmp,text);
      fs.renameSync(tmp,file);
    }
  };
}
