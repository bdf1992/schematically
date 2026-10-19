// The one headless check of a .sov file, shared by scripts/validate_sov.mjs and
// bin/schematically.mjs. It runs the data core's validateDocument, the refusal the browser makes
// at load time when a bound wire has no shared surface (carrierCanvasId), and classifies every
// message by the rule table in scripts/sov_rules.json (docs/RULE-CODES.md), so a file that passes
// here also opens in the editor and every failure carries a stable SOVnnn code and a repair.
//
//   checkFile(Data, file) -> {file, ok, components?, wires?, findings, doc?}
//   RULES                 -> the rule table
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
let Data = null;

export const RULES = JSON.parse(fs.readFileSync(path.join(HERE, 'sov_rules.json'), 'utf8')).rules;
const RULE = Object.fromEntries(RULES.map(r => [r.code, r]));
const MATCHERS = RULES.filter(r => r.match).map(r => ({code: r.code, re: new RegExp(r.match)}));

// The element a message names, the way the marker list names it (src/05-data-core.js markerElementId).
function elementId(docId, message) {
  if (/^(?:wire|component|reference) missing id$/.test(message)) return null;
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

export function checkFile(data, file) {
  Data = data;
  let text, payload, doc;
  try { text = fs.readFileSync(file, 'utf8'); }
  catch (error) { return {file, ok: false, findings: [finding('SOV101', error.message, null)]}; }
  try { payload = JSON.parse(text); }
  catch (error) { return {file, ok: false, findings: [finding('SOV102', error.message, null)]}; }
  try { doc = Data.documentFromFilePayload(payload); }
  catch (error) {
    // A package's own check joins its document's errors; any other throw is the loader refusing a
    // plain document, classified by the table when its message carries a known code.
    if (payload?.schema === Data.PACKAGE_SCHEMA) return {file, ok: false, findings: [finding('SOV105', error.message, payload?.id ?? null)]};
    const hit = MATCHERS.find(m => m.re.test(error.message));
    return {file, ok: false, findings: [finding(hit ? hit.code : 'SOV106', error.message, elementId(payload?.id ?? null, error.message))]};
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
