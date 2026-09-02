#!/usr/bin/env node
// Validate .sov documents without a browser, using the same data core the editor,
// HTTP server, and MCP server run. Exit 0 when every file is valid, 1 otherwise.
//
//   node scripts/validate_sov.mjs file.sov [more.sov ...]
//   node scripts/validate_sov.mjs --compact file.sov     # also print the compact saved form
//
// Sparse authored records are accepted: the loader fills palette presets, form, port
// contracts, wire endpoint references and a wire's surface the same way `file.open` does
// (see skills/author-offline).
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const Data = require(path.join(HERE, '../src/05-data-core.js'));

const args = process.argv.slice(2);
const compact = args.includes('--compact');
const files = args.filter(a => !a.startsWith('--'));
if (!files.length) {
  console.error('usage: node scripts/validate_sov.mjs [--compact] file.sov [...]');
  process.exit(2);
}

let failed = 0;
for (const file of files) {
  let doc;
  try {
    const payload = JSON.parse(fs.readFileSync(file, 'utf8'));
    doc = Data.documentFromFilePayload(payload);
  } catch (error) {
    failed += 1;
    console.log(`FAIL ${file}`);
    console.log(`  ${error.message}`);
    continue;
  }
  const check = Data.validateDocument(doc);
  // The browser refuses the document at load time if any bound wire has no shared surface;
  // carrierCanvasId raises the same refusal here so the file cannot pass validation and
  // still fail to open.
  const errors = [...check.errors];
  for (const wire of doc.wires) {
    let surface;
    try { surface = Data.carrierCanvasId(doc, wire, wire.canvasId || null); }
    catch (error) { if (!errors.some(e => e.startsWith(`wire ${wire.id}`))) errors.push(`wire ${wire.id}: ${error.message}`); continue; }
    // The loader fills a missing canvasId from the ends; one that was written must agree
    // with them, or the wire is routed and drawn on the wrong surface.
    if (wire.canvasId !== surface) {
      errors.push(`wire ${wire.id}: canvasId is ${wire.canvasId}; both ends are on ${surface}, set "canvasId": "${surface}"`);
    }
  }
  if (errors.length) {
    failed += 1;
    console.log(`FAIL ${file}`);
    for (const e of errors) console.log(`  ${e}`);
    continue;
  }
  console.log(`ok   ${file}  (${doc.components.length} components, ${doc.wires.length} wires)`);
  if (compact) console.log(JSON.stringify(Data.compactDocument(doc), null, 1));
}
process.exit(failed ? 1 : 0);
