#!/usr/bin/env node
// Print documents the way the editor holds them: loaded through the data core (presets,
// port contracts, wire references filled) and written back in the compact saved form.
// Reads a JSON array of documents on stdin, writes a JSON array of normalized documents.
// scripts/sov_fingerprint.py hashes this, so a hand-authored file and the same file after an
// editor round-trip have one fingerprint.
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const Data = createRequire(import.meta.url)(path.join(HERE, '../src/05-data-core.js'));

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
  const docs = JSON.parse(input);
  const out = docs.map(payload => Data.compactDocument(Data.documentFromFilePayload(payload)));
  process.stdout.write(JSON.stringify(out));
});
