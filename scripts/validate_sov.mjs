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
const RULES = JSON.parse(fs.readFileSync(path.join(HERE, 'sov_rules.json'), 'utf8')).rules;
const RULE = Object.fromEntries(RULES.map(r => [r.code, r]));
const MATCHERS = RULES.filter(r => r.match).map(r => ({code: r.code, re: new RegExp(r.match)}));

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

// The element a message names, the way the marker list names it (src/05-data-core.js markerElementId).
function elementId(docId, message) {
  const named = message.match(/^(?:wire|component|reference) ([^\s:]+)/);
  if (named) return named[1];
  const duplicate = message.match(/^duplicate (?:component|wire|reference) id: (.+)$/);
  if (duplicate) return duplicate[1];
  return docId ?? null;
}
function finding(code, message, id) {
  const rule = RULE[code];
  const detail = (message.match(/\b([A-Z][A-Z]+(?:_[A-Z]+)+)\b/) || [])[1] || null;
  const repair = rule.repair.replaceAll('{id}', id ?? '?').replaceAll('{detail}', detail ?? '-');
  return {code, family: rule.family, severity: rule.severity, id: id ?? null, rule: null, detail, message, repair};
}
function classify(message, docId) {
  const hit = MATCHERS.find(m => m.re.test(message));
  return finding(hit ? hit.code : 'SOV999', message, elementId(docId, message));
}

function check(file) {
  let text, payload, doc;
  try { text = fs.readFileSync(file, 'utf8'); }
  catch (error) { return {file, ok: false, findings: [finding('SOV101', error.message, null)]}; }
  try { payload = JSON.parse(text); }
  catch (error) { return {file, ok: false, findings: [finding('SOV102', error.message, null)]}; }
  try { doc = Data.documentFromFilePayload(payload); }
  catch (error) {
    const hit = MATCHERS.find(m => (m.code === 'SOV103' || m.code === 'SOV104') && m.re.test(error.message));
    return {file, ok: false, findings: [finding(hit ? hit.code : 'SOV105', error.message, payload?.id ?? null)]};
  }
  const errors = [...Data.validateDocument(doc).errors];
  // The browser refuses the document at load time if any bound wire has no shared surface;
  // carrierCanvasId raises the same refusal here so the file cannot pass validation and
  // still fail to open.
  for (const wire of doc.wires) {
    let surface;
    try { surface = Data.carrierCanvasId(doc, wire, wire.canvasId || null); }
    catch (error) { if (!errors.some(e => e.startsWith(`wire ${wire.id}`))) errors.push(`wire ${wire.id}: ${error.message}`); continue; }
    // The loader derives a missing wire.canvasId from the ends; one that is written but names a
    // different surface is kept as written and routes there, so report the disagreement.
    const stored = wire.canvasId || null;
    if (surface !== Data.GLOBAL_CANVAS_ID && stored !== surface) {
      errors.push(`wire ${wire.id}: canvasId ${stored ? `is ${stored}` : 'missing'}; both ends are on ${surface}, set "canvasId": "${surface}"`);
    }
  }
  // The marker rule for each message is the one schematic.markers reports (src/05-data-core.js markerRule).
  const markers = Data.markersFor(doc), ruleOf = new Map(markers.map(m => [m.message, m.rule]));
  const findings = errors.map(message => ({...classify(message, doc.id), rule: ruleOf.get(message) ?? 'boundary-legality'}));
  return {file, ok: !findings.some(f => f.severity === 'error'), components: doc.components.length, wires: doc.wires.length, findings, doc};
}

let failed = 0;
const reports = [];
for (const file of files) {
  const report = check(file);
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
