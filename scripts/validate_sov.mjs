#!/usr/bin/env node
// Validate .sov documents without a browser, using the same data core the editor,
// HTTP server, and MCP server run. Exit 0 when every file is valid, 1 otherwise.
//
//   node scripts/validate_sov.mjs file.sov [more.sov ...]
//   node scripts/validate_sov.mjs --compact file.sov     # also print the compact saved form
//   node scripts/validate_sov.mjs --concerns file.sov    # also print the concerns still open
//   node scripts/validate_sov.mjs --json file.sov        # one JSON report: a rule code and a repair per finding
//   node scripts/validate_sov.mjs --rules                # the rule table (scripts/sov_rules.json) as JSON
//
// --concerns prints, after a valid file's ok line, one line per concern its notation declares that
// the document has not answered ('open  <applies> <target or -> <concern>: <question>') and then
// 'concerns: <answered> answered, <open> open'. An open concern never fails a file.
//
// --json prints {schema: 'schematically.validate/1', ok, files: [{file, ok, components, wires,
// findings}]} and nothing else. Each finding is {code, family, severity, id, rule, detail, message,
// repair}: code is a stable SOVnnn from scripts/sov_rules.json (docs/RULE-CODES.md), id the element
// it names (a component, wire or reference id, else the document id), rule the marker rule
// schematic.markers reports for the same message, detail the validator's own upper-case code when
// the message carries one. The findings are the ones schematic.markers reports, plus the wire
// surface checks below; render checks run in scripts/deliver_sov.py, which needs a browser.
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
const {checkFile, RULES} = await import(new URL('./sov_check.mjs', import.meta.url));
const args = process.argv.slice(2);
const compact = args.includes('--compact');
const concerns = args.includes('--concerns');
const json = args.includes('--json');
if (args.includes('--rules')) {
  console.log(JSON.stringify({schema: 'schematically.rules/1', rules: RULES}, null, 2));
  process.exit(0);
}
const files = args.filter(a => !a.startsWith('--'));
if (!files.length) {
  console.error('usage: node scripts/validate_sov.mjs [--compact] [--concerns] [--json] file.sov [...] | --rules');
  process.exit(2);
}

let failed = 0;
const reports = [];
for (const file of files) {
  const report = checkFile(Data, file);
  if (!report.ok) failed += 1;
  const {doc, ...rest} = report;
  reports.push(rest);
  if (json) continue;
  if (!report.ok) {
    console.log(`FAIL ${file}`);
    for (const f of report.findings) console.log(`  ${f.message}`);
    continue;
  }
  console.log(`ok   ${file}  (${doc.components.length} components, ${doc.wires.length} wires)`);
  if (concerns) {
    const c = Data.concernReport(doc);
    for (const row of c.rows) if (!row.answered) console.log(`open  ${row.applies} ${row.target ?? '-'} ${row.concern}: ${row.question}`);
    console.log(`concerns: ${c.answered} answered, ${c.open} open`);
  }
  if (compact) console.log(JSON.stringify(Data.compactDocument(doc), null, 1));
}
if (json) console.log(JSON.stringify({schema: 'schematically.validate/1', ok: failed === 0, files: reports}, null, 2));
process.exit(failed ? 1 : 0);
