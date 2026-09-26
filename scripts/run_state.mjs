#!/usr/bin/env node
// Run documents through the state space engine (src/07-state-space.js) from scripts, the way
// normalize_sov.mjs runs the data core. Not a surface of its own: the run operations are the
// engine's (schematic.run.*, STATE-SPACE.md "Surfaces"); this only drives them to quiet.
//
// Reads a JSON array of requests on stdin, each
//   {path, inputs: [{entity, point?, channel?, value, at}], packs?: [path], budget?, seed?}
// (point defaults to "self": a source is a Point), steps one tick at a time until nothing is
// scheduled, and writes one result per request: {ok: true, trace} with the full trace
// (records included), or the engine's typed refusal {ok: false, code, message, ...}.
// Packs default to data/core.logic.pack.json and data/logic.gates.pack.json.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
require(path.join(HERE, '../src/03-canonical.js'));
require(path.join(HERE, '../src/06-attachment-core.js'));
require(path.join(HERE, '../src/05-data-core.js'));
const State = require(path.join(HERE, '../src/07-state-space.js'));
const DEFAULT_PACKS = ['../data/core.logic.pack.json', '../data/logic.gates.pack.json'].map(p => path.join(HERE, p));
const read = p => JSON.parse(fs.readFileSync(p, 'utf8'));

function run(req) {
  const doc = read(req.path);
  const packs = (req.packs || DEFAULT_PACKS).map(read);
  const inputs = (req.inputs || []).map(x => ({point: 'self', ...x}));
  const started = State.startRun({doc, packs, inputs, budget: req.budget, seed: req.seed});
  if (!started.ok) return started;
  for (;;) {
    const r = State.step(started.run);
    if (!r.ok) return {...r, trace: State.traceOf(started.run)};
    if (r.tick === null) return {ok: true, trace: State.traceOf(started.run)};
  }
}

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => { process.stdout.write(JSON.stringify(JSON.parse(input).map(run))); });
