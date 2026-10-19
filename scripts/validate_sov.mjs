#!/usr/bin/env node
// Validate .sov documents without a browser, using the same data core the editor,
// HTTP server, and MCP server run. Exit 0 when every file is valid, 1 otherwise.
//
//   node scripts/validate_sov.mjs file.sov [more.sov ...]
//   node scripts/validate_sov.mjs --compact file.sov     # also print the compact saved form
//   node scripts/validate_sov.mjs --concerns file.sov    # also print the concerns still open
//
// --concerns prints, after a valid file's ok line, one line per concern its notation declares that
// the document has not answered ('open  <applies> <target or -> <concern>: <question>') and then
// 'concerns: <answered> answered, <open> open'. An open concern never fails a file.
//
// Sparse authored records are accepted: the loader applies palette presets and fills form,
// port contracts, and wire endpoint references the same way `file.open` does (see
// skills/author-offline for the authored form).
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const Data = require(path.join(HERE, '../src/05-data-core.js'));
const {checkText} = await import(new URL('./sov_check.mjs', import.meta.url));

const args = process.argv.slice(2);
const compact = args.includes('--compact');
const concerns = args.includes('--concerns');
const files = args.filter(a => !a.startsWith('--'));
if (!files.length) {
  console.error('usage: node scripts/validate_sov.mjs [--compact] [--concerns] file.sov [...]');
  process.exit(2);
}

let failed = 0;
for (const file of files) {
  const {doc, diagnostics} = checkText(Data, fs.readFileSync(file, 'utf8'));
  if (diagnostics.length) {
    failed += 1;
    console.log(`FAIL ${file}`);
    for (const d of diagnostics) console.log(`  ${d.message}`);
    continue;
  }
  console.log(`ok   ${file}  (${doc.components.length} components, ${doc.wires.length} wires)`);
  if (concerns) {
    const report = Data.concernReport(doc);
    for (const row of report.rows) if (!row.answered) console.log(`open  ${row.applies} ${row.target ?? '-'} ${row.concern}: ${row.question}`);
    console.log(`concerns: ${report.answered} answered, ${report.open} open`);
  }
  if (compact) console.log(JSON.stringify(Data.compactDocument(doc), null, 1));
}
process.exit(failed ? 1 : 0);
