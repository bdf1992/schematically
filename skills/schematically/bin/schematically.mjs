#!/usr/bin/env node
// Schematically from a terminal, with Node 18+ and nothing else installed.
//
//   node bin/schematically.mjs deliver file.sov [out.html] [--open] [--json] [--no-layout]
//   node bin/schematically.mjs validate file.sov [--json]
//   node bin/schematically.mjs demo [dir] [--open] [--json]
//
// deliver checks a .sov with the same data core the editor runs, lays it out with the layered
// engine when its cards carry no coordinates, and writes one .html that opens from disk: the
// document and the editor build travel inside it, and the reader's browser draws the picture once
// at open (scripts/viewer_template.html, sovExtract). The file is written beside its target and
// renamed over it only when everything passed, so a failed run leaves the last good file in place.
// --json prints one object: {ok, ...}, with `findings` from scripts/sov_check.mjs: each
// {code, family, severity, id, rule, detail, message, repair}, code a stable SOVnnn
// (docs/RULE-CODES.md). A warning never fails a document.
// Exit 0 when it delivered or validated, 1 on diagnostics, 2 on a usage error.
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const require = createRequire(import.meta.url);
require(path.join(ROOT, 'src/03-notation-core.js'));
require(path.join(ROOT, 'src/06-attachment-core.js'));
const Data = require(path.join(ROOT, 'src/05-data-core.js'));
const Layout = require(path.join(ROOT, 'src/08-layout-core.js'));
const {checkFile} = await import(new URL('../scripts/sov_check.mjs', import.meta.url));

const EDITOR = path.join(ROOT, 'index.html');
const TEMPLATE = path.join(ROOT, 'scripts/viewer_template.html');
const DATA_PLACEHOLDER = '/*__VIEWER_DATA__*/null';
const EDITOR_PLACEHOLDER = '/*__VIEWER_EDITOR__*/';
const USAGE = `usage:
  schematically deliver file.sov [out.html] [--open] [--json] [--no-layout]
  schematically validate file.sov [--json]
  schematically demo [dir] [--open] [--json]`;

// The demo is the request Archify's README starts from, written the way an agent writes one:
// cards and wires, no coordinates.
const DEMO = {
  schema: 'soveraeign.schematic/document@0.1', id: 'web-request', revision: 0,
  meta: {title: 'A web request with a cache in front of the database'},
  components: [
    {id: 'browser', symbolId: 'act', config: {label: 'Browser', signalMode: 'source'}},
    {id: 'api', symbolId: 'act', config: {label: 'API'}},
    {id: 'cache', symbolId: 'hold', config: {label: 'Redis cache'}},
    {id: 'db', symbolId: 'hold', config: {label: 'PostgreSQL'}},
  ],
  wires: [
    {id: 'w-request', a: 'browser', aSide: 'out', b: 'api', bSide: 'in', config: {label: 'request'}},
    {id: 'w-lookup', a: 'api', aSide: 'out', b: 'cache', bSide: 'in', config: {label: 'lookup', forwardOperation: 'read'}},
    {id: 'w-miss', a: 'cache', aSide: 'out', b: 'db', bSide: 'in', config: {label: 'on miss', forwardOperation: 'read'}},
  ],
  references: [],
};

function scriptSafe(value) {
  return JSON.stringify(value).replace(/&/g, '\\u0026').replace(/</g, '\\u003c').replace(/>/g, '\\u003e');
}

function needsLayout(text) {
  try {
    const payload = JSON.parse(text);
    return (payload.components || []).some(c => !c.parentId && (typeof c.x !== 'number' || typeof c.y !== 'number'));
  } catch { return false; }
}

// A refusal the command itself makes, in the shape the rule table gives every finding.
const refusal = (code, message, repair) => ({code, family: 'deliver', severity: 'error', id: null, rule: null, detail: null, message, repair});

function validate(file) {
  const report = checkFile(Data, file);
  const {doc, ...shown} = report;
  if (!report.ok) return {...shown, ok: false};
  return {...shown, ok: true, text: fs.readFileSync(file, 'utf8'), doc};
}

function deliver(file, target, {layout = true} = {}) {
  const checked = validate(file);
  if (!checked.ok) return checked;
  let text = checked.text, laidOut = false;
  if (layout && needsLayout(text)) {
    const result = Layout.execute(checked.doc, 'apply', {engine: 'layered'});
    if (!result.ok) return {ok: false, file, findings: [refusal('LAYOUT_REFUSED', `${result.code}: ${result.message}`, 'write x and y for every card, or remove what the layout engine refuses')]};
    text = JSON.stringify(Data.compactDocument(checked.doc));
    laidOut = true;
  }
  const template = fs.readFileSync(TEMPLATE, 'utf8');
  if (template.split(DATA_PLACEHOLDER).length !== 2 || template.split(EDITOR_PLACEHOLDER).length !== 2) {
    return {ok: false, file, findings: [refusal('TEMPLATE_INVALID', 'the viewer template must hold each placeholder exactly once', 'reinstall the skill')]};
  }
  const editor = zlib.gzipSync(fs.readFileSync(EDITOR), {level: 9}).toString('base64');
  const html = template
    .replace(DATA_PLACEHOLDER, () => scriptSafe({document: text, source: path.basename(file)}))
    .replace(EDITOR_PLACEHOLDER, () => editor);
  const out = path.resolve(target || file.replace(/\.sov$/i, '') + '.html');
  fs.mkdirSync(path.dirname(out), {recursive: true});
  const candidate = `${out}.${process.pid}.tmp`;
  fs.writeFileSync(candidate, html, 'utf8');
  fs.renameSync(candidate, out);
  return {ok: true, file, target: out, bytes: Buffer.byteLength(html), components: checked.components, wires: checked.wires, laidOut, findings: checked.findings};
}

function openFile(file) {
  const [cmd, args] = process.platform === 'win32' ? ['cmd', ['/c', 'start', '', file]]
    : process.platform === 'darwin' ? ['open', [file]] : ['xdg-open', [file]];
  try { spawn(cmd, args, {detached: true, stdio: 'ignore'}).unref(); return true; }
  catch { return false; }
}

function report(result, json) {
  const {text, doc, ...shown} = result;
  if (json) { console.log(JSON.stringify(shown)); return; }
  if (!result.ok) {
    console.log(`FAIL ${result.file}`);
    for (const f of result.findings) console.log(`  ${f.code} ${f.id ?? '-'}: ${f.message}\n    repair: ${f.repair}`);
    return;
  }
  const counts = `${result.components} components, ${result.wires} wires`;
  if (result.target) console.log(`ok   ${result.target}  (${counts}${result.laidOut ? ', laid out' : ''}, ${result.bytes} bytes)`);
  else console.log(`ok   ${result.file}  (${counts})`);
}

const argv = process.argv.slice(2);
const flags = new Set(argv.filter(a => a.startsWith('--')));
const [verb, ...rest] = argv.filter(a => !a.startsWith('--'));
const json = flags.has('--json');
const known = new Set(['--json', '--open', '--no-layout']);
const unknown = [...flags].filter(f => !known.has(f));
if (unknown.length || !verb || verb === 'help') { console.error(USAGE); process.exit(verb === 'help' ? 0 : 2); }

let result;
if (verb === 'validate' && rest.length === 1) result = validate(rest[0]);
else if (verb === 'deliver' && (rest.length === 1 || rest.length === 2)) result = deliver(rest[0], rest[1], {layout: !flags.has('--no-layout')});
else if (verb === 'demo' && rest.length <= 1) {
  const dir = path.resolve(rest[0] || 'schematically-demo');
  fs.mkdirSync(dir, {recursive: true});
  const source = path.join(dir, 'web-request.sov');
  fs.writeFileSync(source, JSON.stringify(DEMO, null, 2) + '\n', 'utf8');
  result = deliver(source, path.join(dir, 'web-request.html'));
} else { console.error(USAGE); process.exit(2); }

if (result.ok && result.target && flags.has('--open')) result.opened = openFile(result.target);
report(result, json);
process.exit(result.ok ? 0 : 1);
