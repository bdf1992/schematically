#!/usr/bin/env node
// File-only projection. Reads an explicit exported packet; never discovers private
// records, connects to localhost, executes commands, or writes Workstation state.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
await import(pathToFileURL(path.join(ROOT,'src/08-workstation-graph.js')).href);
const args=process.argv.slice(2);
if(args.length!==2){console.error('Usage: node scripts/workstation_graph.mjs mission-export.json output.sovpak');process.exit(2);}
try{
  const input=path.resolve(args[0]),output=path.resolve(args[1]);
  if(input===output)throw new Error('Input and output must differ');
  if(fs.statSync(input).size>5_000_000)throw new Error('Input exceeds 5 MB');
  const packet=JSON.parse(fs.readFileSync(input,'utf8'));
  const result=globalThis.SovWorkstationGraph.project(packet);
  // Exclusive creation refuses accidental replacement of an existing artifact.
  fs.writeFileSync(output,JSON.stringify(result,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({output,subjects:result.meta.graph.readings.length,gaps:result.meta.graph.gaps.length,source:result.meta.graph.source}));
}catch(error){console.error(`${error.code||'WS_GRAPH_INPUT'}: ${error.message}`);process.exitCode=2;}
