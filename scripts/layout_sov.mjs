#!/usr/bin/env node
// Lay out a .sov document in place with the layered engine (LAYOUT-MODEL.md), using the same
// data and layout cores the editor, HTTP server, and MCP server run. A document authored or
// generated with no coordinates — cards and wires only — gets every card placed without an
// editor: source, control and evidence columns left to right, rows levelled with the wires
// that cross them (src/08-layout-core.js, the layered engine).
//
//   node scripts/layout_sov.mjs file.sov [--out other.sov] [--view id]
//
// Writes the result back to file.sov (or --out, when given) as the compact saved form, one
// final newline. --view names a layout to arrange; left out, the document's default layout.
// A refusal from the layout engine (a boundary Point host missing, an unknown layout, ...)
// prints FAIL and its code and message, and exits 1.
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

const USAGE = 'usage: node scripts/layout_sov.mjs file.sov [--out other.sov] [--view id]';

const args = process.argv.slice(2);
let out = null, view = null;
const positional = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--out') { out = args[++i]; }
  else if (args[i] === '--view') { view = args[++i]; }
  else positional.push(args[i]);
}
const file = positional[0];
if (!file || out === undefined || view === undefined) {
  console.error(USAGE);
  process.exit(2);
}

const payload = JSON.parse(fs.readFileSync(file, 'utf8'));
const doc = Data.documentFromFilePayload(payload);
const result = Layout.execute(doc, 'apply', {engine: 'layered', view});
if (!result.ok) {
  console.log(`FAIL ${file}`);
  console.log(`  ${result.code}: ${result.message}`);
  process.exit(1);
}

const target = out || file;
fs.writeFileSync(target, JSON.stringify(Data.compactDocument(doc), null, 1) + '\n');
console.log(`ok ${file} (${result.placed} placed)`);
