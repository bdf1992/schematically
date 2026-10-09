#!/usr/bin/env node
// Lay out a .sov document in place with the layered engine (LAYOUT-MODEL.md), using the same
// data and layout cores the editor, HTTP server, and MCP server run. A document authored or
// generated with no coordinates — cards and wires only — gets every card placed without an
// editor: source, control and evidence columns left to right, rows levelled with the wires
// that cross them (src/08-layout-core.js, the layered engine).
//
//   node scripts/layout_sov.mjs file.sov [--out other.sov] [--view id] [--no-arrange]
//                                        [--harness groupA,groupB ...] [--lanes port] [--label-margin n]
//                                        [--engine layered|n2] [--into name]
//
// Writes the result back to file.sov (or --out, when given) as the compact saved form, one
// final newline. --view names a layout to arrange; left out, the document's default layout.
// --engine n2 puts the cards on the diagonal and pins each wire between two of them with one
// corner (LAYOUT-MODEL.md "What n2 does"). It writes a stored layout only, so it needs --into (a
// new layout) or --view (a stored one), and the file is written as it was read with only its
// layout replaced. --into also works with layered: the arrangement goes into a new layout.
// --no-arrange keeps every card where it is. --harness (repeatable) runs the harness op
// between two groups after any arranging, in the order given, and prints each receipt: one
// trunk per wire label in the gap between the groups, streets in their row gaps, and the wires
// between them routed on those buses (LAYOUT-MODEL.md "As built: buses").
// A refusal from the layout engine (a boundary Point host missing, an unknown layout, a gap too
// narrow for its trunks, ...) prints FAIL and its code and message, writes nothing, and exits 1.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
require(path.join(HERE, '../src/03-notation-core.js'));
require(path.join(HERE, '../src/06-attachment-core.js'));
const Data = require(path.join(HERE, '../src/05-data-core.js'));
const Layout = require(path.join(HERE, '../src/08-layout-core.js'));

const USAGE = 'usage: node scripts/layout_sov.mjs file.sov [--out other.sov] [--view id] [--no-arrange] [--harness groupA,groupB ...] [--lanes port] [--label-margin n] [--engine layered|n2] [--into name]';

const args = process.argv.slice(2);
let out = null, view = null, arrange = true, labelMargin = null, lanes = null, engine = 'layered', into = null;
const harnesses = [];
const positional = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--out') { out = args[++i]; }
  else if (args[i] === '--view') { view = args[++i]; }
  else if (args[i] === '--no-arrange') { arrange = false; }
  else if (args[i] === '--engine') {
    engine = args[++i];
    if (engine !== 'layered' && engine !== 'n2') { console.error(USAGE); process.exit(2); }
  }
  else if (args[i] === '--into') { into = args[++i]; }
  else if (args[i] === '--label-margin') { labelMargin = Number(args[++i]); }
  else if (args[i] === '--lanes') {
    lanes = args[++i];
    if (lanes !== 'port') { console.error(USAGE); process.exit(2); }
  }
  else if (args[i] === '--harness') {
    const pair = String(args[++i] ?? '').split(',').map(s => s.trim());
    if (pair.length !== 2 || !pair[0] || !pair[1]) { console.error(USAGE); process.exit(2); }
    harnesses.push(pair);
  }
  else positional.push(args[i]);
}
const file = positional[0];
if (!file || out === undefined || view === undefined || into === undefined) {
  console.error(USAGE);
  process.exit(2);
}

const payload = JSON.parse(fs.readFileSync(file, 'utf8'));
const doc = Data.documentFromFilePayload(payload);
const fail = (result) => {
  console.log(`FAIL ${file}`);
  console.log(`  ${result.code}: ${result.message}`);
  process.exit(1);
};
let placed = null, usedLabelMargin = null, bundles = null, channels = null, n2 = null;
if (arrange) {
  const applyArgs = {engine, view, ...(into ? {into} : {})};
  if (labelMargin != null && Number.isFinite(labelMargin)) applyArgs.labelMargin = labelMargin;
  const result = Layout.execute(doc, 'apply', applyArgs);
  if (!result.ok) fail(result);
  placed = result.placed;
  usedLabelMargin = result.labelMargin;
  bundles = result.bundles || null;
  channels = result.channels || null;
  n2 = result.engine === 'n2' ? result : null;
}
const receipts = [];
for (const between of harnesses) {
  const result = Layout.execute(doc, 'harness', {between, view, ...(lanes ? {lanes} : {})});
  if (!result.ok) fail(result);
  receipts.push(result);
}

const target = out || file;
// Arranging rewrites geometry, so the document is written in its compact saved form. Without it
// only the layouts changed: the file is written as it was read with its layout replaced, so the
// loader's filled-in defaults never reach a hand-authored or generated document.
// n2 changes no record either, so its file is written the same way.
const asRead = (!arrange || engine === 'n2') && payload && typeof payload === 'object' && payload.schema === Data.DOCUMENT_SCHEMA;
const written = asRead ? {...payload, layout: doc.layout} : Data.compactDocument(doc);
fs.writeFileSync(target, JSON.stringify(written, null, 1) + '\n');
console.log(`ok ${file}${placed != null ? ` (${placed} placed)${n2 ? '' : ` labelMargin ${usedLabelMargin}`}` : ''}`);
// n2 writes a stored layout: its name, the pitch, and what became of the wires between placed cards.
if (n2) {
  console.log(`  n2: layout ${n2.view}, pitch ${n2.pitch}, ${n2.wires.pinned} wires pinned (${n2.wires.forward} forward, ${n2.wires.feedback} feedback), ${n2.wires.auto} left to the router, ${n2.ports} ports placed`);
  for (const a of n2.autoRouted) console.log(`    auto ${a.wire}: ${a.reason}${a.card ? ` (${a.card} ${a.port} is on the ${a.side})` : ''}`);
}
// A packed canvas routes the wires between its items on channel buses instead of bundling pairs.
if (channels) {
  console.log(`  channels: ${channels.wires} wires on ${channels.buses} buses (${channels.streets} streets), gap ${channels.gap}${channels.skipped > 0 ? `, ${channels.skipped} skipped` : ''}`);
}
// Layered bundles the wires between grouped pairs on harness buses; its receipt, pair by pair.
if (bundles) {
  console.log(`  bundled ${bundles.filter(b => b.kept).length} of ${bundles.length} group pairs`);
  for (const b of bundles) console.log(`    ${b.between.join(',')}: ${b.wires} wires ${b.kept ? 'kept' : b.reason}`);
}
for (const r of receipts) {
  console.log(`  harness ${r.between.join(',')}: ${r.orientation} gap ${r.gap.have} (needs ${r.gap.need}); ${r.wires.length} wires`);
  for (const b of r.buses) console.log(`    ${b.kind} ${b.id}: ${b.lanes} lane${b.lanes === 1 ? '' : 's'}${b.label ? ` "${b.label}"` : ''}`);
  if (r.returnedToAuto.length) console.log(`    returned to auto: ${r.returnedToAuto.join(', ')}`);
}
