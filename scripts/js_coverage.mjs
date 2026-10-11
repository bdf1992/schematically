// AST statement/function coverage only; product source is never instrumented in place.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { createInstrumenter } = require('istanbul-lib-instrument');
const { createCoverageMap } = require('istanbul-lib-coverage');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const clone = value => JSON.parse(JSON.stringify(value));
const json = value => `${JSON.stringify(value, null, 2)}\n`;
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const pins = { 'istanbul-lib-instrument': '6.0.3', 'istanbul-lib-coverage': '3.2.2' };
const versions = Object.fromEntries(Object.keys(pins).map(name => [name, require(`${name}/package.json`).version]));

try {
  for (const [name, version] of Object.entries(versions)) if (pins[name] !== version) throw new Error(`${name}: expected ${pins[name]}, loaded ${version}`);
  const [command, ...args] = process.argv.slice(2);
  const options = parseOptions(args);
  if (command === 'prepare') prepare(options);
  else if (command === 'merge') merge(options);
  else throw new Error('Expected prepare or merge command');
} catch (error) {
  console.error(`JS coverage refused: ${error.message}`);
  process.exitCode = 2;
}

function parseOptions(args) {
  if (args.length % 2) throw new Error('Options require values');
  const options = {};
  for (let index = 0; index < args.length; index += 2) {
    const key = args[index];
    if (!key.startsWith('--') || Object.hasOwn(options, key)) throw new Error(`Invalid/duplicate option: ${key}`);
    options[key] = args[index + 1];
  }
  return options;
}

function exactOptions(options, names) {
  for (const key of Object.keys(options)) if (!names.includes(key)) throw new Error(`Unknown option: ${key}`);
  for (const key of names) if (!options[key]) throw new Error(`Missing ${key}`);
}

function inside(root, target) {
  const relative = path.relative(root, target);
  return relative !== '' && !relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative);
}

function sourcePath(root, relative) {
  if (typeof relative !== 'string' || path.isAbsolute(relative) || !/\.(?:js|mjs)$/.test(relative)) throw new Error(`Invalid scoped source: ${relative}`);
  const target = path.resolve(root, relative);
  if (!inside(root, target) || !inside(root, fs.realpathSync(target))) throw new Error(`Source escapes root: ${relative}`);
  if (!fs.statSync(target).isFile()) throw new Error(`Source is not a regular file: ${relative}`);
  return target;
}

function safeDestination(root, relative) {
  const target = path.resolve(root, relative);
  if (!inside(root, target)) throw new Error(`Copy destination escapes root: ${relative}`);
  let ancestor = path.dirname(target);
  while (!fs.existsSync(ancestor)) ancestor = path.dirname(ancestor);
  const resolved = fs.realpathSync(ancestor);
  if (resolved !== root && !inside(root, resolved)) throw new Error(`Copy ancestor escapes root: ${relative}`);
  if (fs.existsSync(target) && !inside(root, fs.realpathSync(target))) throw new Error(`Copy file escapes root: ${relative}`);
  return target;
}

function mapping(coverage) {
  return { path: coverage.path, statementMap: coverage.statementMap, fnMap: coverage.fnMap, branchMap: coverage.branchMap };
}

// Object-key order in harness serialization is not identity; map values and keys are.
function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, stable(value[key])]));
  return value;
}
function mappingHash(coverage) { return hash(JSON.stringify(stable(mapping(coverage)))); }

function prepare(options) {
  exactOptions(options, ['--source-root', '--copy-root', '--scope-json']);
  const sourceRoot = fs.realpathSync(path.resolve(options['--source-root']));
  fs.mkdirSync(path.resolve(options['--copy-root']), { recursive: true });
  const copyRoot = fs.realpathSync(path.resolve(options['--copy-root']));
  if (sourceRoot === copyRoot) throw new Error('Original and instrumentation roots must differ');
  const scopeArg = options['--scope-json'].trim();
  const scope = scopeArg.startsWith('[') ? JSON.parse(scopeArg) : readJson(path.resolve(scopeArg));
  if (!Array.isArray(scope) || !scope.length || scope.length > 100) throw new Error('Scope must be an array of 1–100 source paths');
  const prepared = [], seen = new Set(), coverage = {};
  let totalBytes = 0;
  for (const relative of scope) {
    const original = sourcePath(sourceRoot, relative);
    if (seen.has(original)) throw new Error(`Duplicate scoped source: ${relative}`);
    seen.add(original);
    const destination = safeDestination(copyRoot, relative);
    if (destination === original || fs.existsSync(destination) && fs.realpathSync(destination) === fs.realpathSync(original)) throw new Error('Instrumentation would overwrite original source');
    const bytes = fs.readFileSync(original);
    totalBytes += bytes.length;
    if (bytes.length > 1048576 || totalBytes > 5242880) throw new Error('Instrumentation source byte ceiling exceeded');
    const text = bytes.toString('utf8');
    if (/\/\*\s*istanbul\s+ignore|\/\/\s*istanbul\s+ignore/.test(text)) throw new Error(`${relative}: coverage exclusion directive requires disposition; no silent exclusion`);
    const instrumenter = createInstrumenter({
      esModules: relative.endsWith('.mjs'), coverageVariable: '__coverage__',
      coverageGlobalScope: 'globalThis', coverageGlobalScopeFunc: false,
      compact: false, preserveComments: true, produceSourceMap: false,
      ignoreClassMethods: []
    });
    const instrumented = instrumenter.instrumentSync(text, original);
    const initial = clone(instrumenter.lastFileCoverage());
    if (!initial || initial.path !== original) throw new Error(`Missing initial instrumentation map: ${relative}`);
    validateCounters(initial, initial);
    if (Object.values(initial.s).some(count => count !== 0) || Object.values(initial.f).some(count => count !== 0) || Object.values(initial.b).flat().some(count => count !== 0)) throw new Error(`Initial counters are not zero: ${relative}`);
    coverage[original] = initial;
    prepared.push({ relativePath: relative, sourceId: original, sourceHash: hash(bytes),
      instrumentedHash: hash(instrumented), mappingHash: mappingHash(initial), destination, instrumented });
  }
  // Parse/prepare the whole declared scope before writing its instrumented files.
  for (const file of prepared) {
    fs.mkdirSync(path.dirname(file.destination), { recursive: true });
    fs.writeFileSync(file.destination, file.instrumented, 'utf8');
  }
  const initialPath = path.join(copyRoot, '.js-coverage-initial.json');
  fs.writeFileSync(initialPath, json({ schemaVersion: 1, sourceRoot, copyRoot,
    tools: versions, measurement: 'Istanbul AST statement start lines; function counters retained separately',
    files: prepared.map(({ instrumented, destination, ...identity }) => identity), coverage }));
  console.log(json({ initial: initialPath, files: prepared.length, sourceRoot, copyRoot }));
}

function keysMatch(left, right) {
  return JSON.stringify(Object.keys(left).sort()) === JSON.stringify(Object.keys(right).sort());
}

function validateCounters(incoming, expected) {
  if (!incoming || typeof incoming !== 'object' || Array.isArray(incoming)) throw new Error('File coverage must be an object');
  for (const key of ['statementMap', 'fnMap', 'branchMap', 's', 'f', 'b'])
    if (!incoming[key] || typeof incoming[key] !== 'object' || Array.isArray(incoming[key])) throw new Error(`Missing/malformed coverage ${key}`);
  if (mappingHash(incoming) !== mappingHash(expected)) throw new Error(`Instrumentation mapping mismatch: ${incoming.path}`);
  function location(loc) {
    if (!loc || !loc.start || !loc.end ||
      !Number.isSafeInteger(loc.start.line) || loc.start.line < 1 ||
      !Number.isSafeInteger(loc.end.line) || loc.end.line < loc.start.line ||
      !Number.isSafeInteger(loc.start.column) || loc.start.column < 0 ||
      !Number.isSafeInteger(loc.end.column) || loc.end.column < 0)
      throw new Error(`Malformed AST coverage location: ${incoming.path}`);
  }
  for (const loc of Object.values(incoming.statementMap)) location(loc);
  for (const fn of Object.values(incoming.fnMap)) { location(fn.loc); location(fn.decl); }
  for (const branch of Object.values(incoming.branchMap)) {
    if (!Array.isArray(branch.locations)) throw new Error(`Malformed branch locations: ${incoming.path}`);
    // Istanbul's synthetic implicit else branch can have no source location;
    // its exact shape is still bound by mappingHash and contributes no lines.
    branch.locations.forEach(loc => {
      if (loc?.start && loc?.end && Object.keys(loc.start).length === 0 && Object.keys(loc.end).length === 0) return;
      location(loc);
    });
  }
  for (const [map, counts] of [['statementMap', 's'], ['fnMap', 'f'], ['branchMap', 'b']]) {
    if (!keysMatch(incoming[map], incoming[counts])) throw new Error(`Counter keys do not match ${map}: ${incoming.path}`);
    for (const [key, value] of Object.entries(incoming[counts])) {
      if (counts === 'b') {
        if (!Array.isArray(value) || value.length !== expected.b[key].length || value.some(count => !Number.isSafeInteger(count) || count < 0)) throw new Error(`Malformed branch count ${key}`);
      } else if (!Number.isSafeInteger(value) || value < 0) throw new Error(`Malformed ${counts} count ${key}`);
    }
  }
}

function snapshotFiles(directory) {
  const result = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isSymbolicLink()) throw new Error(`Coverage snapshot symlink refused: ${file}`);
    if (entry.isDirectory()) result.push(...snapshotFiles(file));
    else if (entry.isFile() && entry.name.endsWith('.json')) result.push(file);
    if (result.length > 10000) throw new Error('Snapshot file ceiling exceeded');
  }
  return result.sort();
}

function merge(options) {
  exactOptions(options, ['--initial', '--coverage-dir', '--out']);
  const initialFile = path.resolve(options['--initial']);
  const initialBytes = fs.readFileSync(initialFile);
  const initial = JSON.parse(initialBytes.toString('utf8'));
  if (initial.schemaVersion !== 1 || !Array.isArray(initial.files) || !initial.files.length || initial.files.length > 100 || !initial.coverage || !initial.sourceRoot)
    throw new Error('Malformed initial coverage envelope');
  if (JSON.stringify(stable(initial.tools)) !== JSON.stringify(stable(versions))) throw new Error('Instrumentation tool identity changed');
  const identities = new Map();
  for (const file of initial.files) {
    const original = sourcePath(initial.sourceRoot, file.relativePath);
    if (original !== file.sourceId || identities.has(original)) throw new Error('Initial scope/source identity mismatch');
    if (hash(fs.readFileSync(original)) !== file.sourceHash) throw new Error(`Original source hash changed: ${original}`);
    const expected = initial.coverage[original];
    if (!expected || mappingHash(expected) !== file.mappingHash) throw new Error(`Initial map hash mismatch: ${original}`);
    validateCounters(expected, expected);
    if (Object.values(expected.s).some(count => count !== 0) || Object.values(expected.f).some(count => count !== 0) || Object.values(expected.b).flat().some(count => count !== 0))
      throw new Error(`Initial coverage is not zero: ${original}`);
    const instrumented = safeDestination(initial.copyRoot, file.relativePath);
    if (hash(fs.readFileSync(instrumented)) !== file.instrumentedHash) throw new Error(`Instrumented source hash changed: ${instrumented}`);
    identities.set(original, file);
  }
  if (!keysMatch(initial.coverage, Object.fromEntries(identities))) throw new Error('Initial coverage differs from declared source scope');
  const map = createCoverageMap(initial.coverage);
  const directory = fs.realpathSync(path.resolve(options['--coverage-dir']));
  const snapshots = snapshotFiles(directory);
  if (!snapshots.length) throw new Error('No coverage snapshots retained');
  const retained = [];
  for (const file of snapshots) {
    if (file === initialFile || file === path.resolve(options['--out'])) throw new Error('Initial/output evidence must be outside coverage snapshot directory');
    const bytes = fs.readFileSync(file);
    if (bytes.length > 52428800) throw new Error('Coverage snapshot exceeds 50 MiB ceiling');
    const snapshot = JSON.parse(bytes.toString('utf8'));
    if (!snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot)) throw new Error(`Malformed coverage snapshot: ${file}`);
    for (const [sourceId, counters] of Object.entries(snapshot)) {
      if (!identities.has(sourceId) || counters.path !== sourceId) throw new Error(`Unknown/mismatched coverage source: ${sourceId}`);
      validateCounters(counters, initial.coverage[sourceId]);
    }
    map.merge(snapshot);
    retained.push({ file, sha256: hash(bytes), sources: Object.keys(snapshot).length });
  }
  const files = initial.files.map(identity => {
    const coverage = map.fileCoverageFor(identity.sourceId);
    const lines = coverage.getLineCoverage();
    return { file: identity.relativePath, sourceId: identity.sourceId, sourceHash: identity.sourceHash,
      executableLines: Object.keys(lines).map(Number).sort((a, b) => a - b),
      hitLines: Object.entries(lines).filter(([, count]) => count > 0).map(([line]) => Number(line)).sort((a, b) => a - b),
      statements: coverage.toSummary().statements, functions: coverage.toSummary().functions };
  });
  const total = files.reduce((sum, file) => sum + file.executableLines.length, 0);
  const covered = files.reduce((sum, file) => sum + file.hitLines.length, 0);
  const output = path.resolve(options['--out']);
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, json({ schemaVersion: 1, tools: versions,
    initial: { file: initialFile, sha256: hash(initialBytes) }, snapshots: retained,
    measurement: initial.measurement, scope: initial.files.map(file => file.relativePath),
    files, totalExecutableLines: total, totalHitLines: covered,
    executableLineCoverage: total ? 100 * covered / total : 100,
    note: 'Snapshot merge unions covered lines. Summed counters are not claimed as exact execution counts across cumulative snapshots.',
    coverage: map.toJSON() }));
  console.log(json({ out: output, files: files.length, totalExecutableLines: total, totalHitLines: covered }));
}
