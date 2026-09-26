#!/usr/bin/env node
// Run documents through the shared logic core (src/07-logic-core.js) from Node.
// Reads a JSON array of requests on stdin: {path, ops: [{apply: {...}, record?}, {pulse: clock,
// set: {...}}, {table: true}]}; writes one result per request: {results: [...], events, values}
// or {refused, reason, next_operation}. Composites resolve beside the document that names
// them, as scripts/logic_sov.py resolves them. tests/logic_core_parity_qa.py compares the two.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const Logic = require(path.join(HERE, '../src/07-logic-core.js'));
const PACK = Logic.loadPack(JSON.parse(fs.readFileSync(path.join(HERE, '../packs/logic/gates.json'), 'utf8')));

const read = p => fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : null;
const resolve = (name, from) => { const key = path.resolve(path.dirname(from), name); const document = read(key); return document ? {key, document} : null; };

function run(req) {
  try {
    const key = path.resolve(req.path);
    const doc = read(key);
    const c = new Logic.Circuit(doc, {pack: PACK, resolve, key});
    const results = [];
    for (const op of req.ops || []) {
      if (op.table) results.push(c.truthTable());
      else if (op.pulse) results.push(c.pulse(op.pulse, op.set || {}));
      else results.push(c.apply(op.apply || {}, {record: !!op.record}));
    }
    return {results, events: c.events, values: c.value, nets: c.nNets, wires: c.wireState(doc)};
  } catch (e) {
    if (e instanceof Logic.LogicRefusal) return e.asDict();
    throw e;
  }
}

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => { process.stdout.write(JSON.stringify(JSON.parse(input).map(run))); });
