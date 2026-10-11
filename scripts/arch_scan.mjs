import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const config = JSON.parse(fs.readFileSync(path.join(root, 'arch.config.json'), 'utf8'));
const args = process.argv.slice(2);
const outputIndex = args.indexOf('--out');
if (outputIndex < 0 || !args[outputIndex + 1] || args.some((arg, index) =>
  arg !== '--worker' && index !== outputIndex && index !== outputIndex + 1)) {
  console.error('Usage: node scripts/arch_scan.mjs --out PATH');
  process.exit(2);
}
const out = path.resolve(args[outputIndex + 1]);
const sha256 = text => crypto.createHash('sha256').update(text).digest('hex');
const read = file => fs.readFileSync(path.join(root, file), 'utf8').replace(/\r\n/g, '\n');
const normalize = file => file.replaceAll('\\', '/');
const json = value => `${JSON.stringify(value, null, 2)}\n`;

// A separate worker lets the parent bound even synchronous parser/graph work.
if (!args.includes('--worker')) {
  fs.mkdirSync(out, { recursive: true });
  const child = spawn(process.execPath, [fileURLToPath(import.meta.url), '--worker', '--out', out], {
    cwd: root, stdio: 'inherit'
  });
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    child.kill();
    fs.writeFileSync(path.join(out, 'timeout.json'), json({
      passed: false, reason: 'ARCH deadline exceeded', maximumSeconds: config.maximumSeconds
    }));
  }, config.maximumSeconds * 1000);
  child.once('error', error => { clearTimeout(timer); console.error(error.message); process.exitCode = 2; });
  child.once('exit', (code, signal) => { clearTimeout(timer); process.exitCode = timedOut || signal ? 2 : code ?? 2; });
} else {
  const started = Date.now();
  const findings = [];
  const finding = (rule, severity, file, line, message) =>
    findings.push({ rule, severity, file, line: line ?? 1, message });
  try {
    await scan();
  } catch (error) {
    finding('scan-incomplete', 'error', 'scripts/arch_scan.mjs', 1, error.stack ?? String(error));
    fs.mkdirSync(out, { recursive: true });
    fs.writeFileSync(path.join(out, 'failure.json'), json({ passed: false, findings, elapsedSeconds: (Date.now() - started) / 1000 }));
    process.exitCode = 2;
  }

  async function scan() {
    const [{ ESLint }, espree, scope, { cruise }, { default: globals }] = await Promise.all([
      import('eslint'), import('espree'), import('eslint-scope'), import('dependency-cruiser'), import('globals')
    ]);
    const files = config.sourceScope.flatMap(({ directory, extension }) =>
      fs.readdirSync(path.join(root, directory)).filter(name => name.endsWith(extension))
        .map(name => `${directory}/${name}`)).sort();
    if (files.length > config.maximumFiles) throw new Error(`Scope has ${files.length} files, limit ${config.maximumFiles}`);
    let bytes = 0;
    for (const file of files) {
      const size = fs.statSync(path.join(root, file)).size;
      bytes += size;
      if (size > config.maximumFileBytes) throw new Error(`${file} exceeds file byte ceiling`);
    }
    if (bytes > config.maximumTotalBytes) throw new Error('Scope exceeds total byte ceiling');
    const template = read(config.browserOrderSource);
    const ownershipText = read(config.ownershipSource);
    const concerns = new Map();
    for (const match of ownershipText.matchAll(/^- `([^`]+\.(?:js|mjs))`\s*[—–-]\s*(.+)$/gm)) {
      const file = match[1].includes('/') ? match[1] : `src/${match[1]}`;
      concerns.set(file, match[2]);
    }
    for (const match of ownershipText.matchAll(/^### `([^`]+)`\n([^#]+?)(?=\n###|$)/gm))
      if (match[1].endsWith('.js') || match[1].endsWith('.mjs')) concerns.set(match[1], match[2].trim());
    const order = [...template.matchAll(/<script\s+src="([^"]+)"\s*><\/script>/g)].map(match => match[1]);
    if (new Set(order).size !== order.length) finding('browser-order', 'error', config.browserOrderSource, 1, 'Duplicate script inclusion');
    for (const file of files.filter(name => name.startsWith('src/'))) {
      if (!order.includes(file)) finding('browser-order', 'error', file, 1, 'Scoped browser source missing from script order');
    }
    for (const file of order) if (!files.includes(file)) finding('browser-order', 'error', file, 1, 'Script order contains source outside declared scope');
    const records = [];
    const owners = new Map();
    const propertyOwners = new Map();
    const substantialLines = new Map();
    for (const file of files) {
      const text = read(file);
      const record = { file, concern: concerns.get(file) ?? null, sha256: sha256(fs.readFileSync(path.join(root, file))), bytes: Buffer.byteLength(text),
        lines: text.split('\n').length, codeLines: text.split('\n').filter(line => line.trim() && !line.trim().startsWith('//')).length,
        functions: [], bindings: [], globalReads: [], properties: [] };
      records.push(record);
      if (!record.concern) finding('ownership-undocumented', 'warning', file, 1, 'No direct per-file concern found in MODULES.md');
      let ast;
      try { ast = espree.parse(text, { ecmaVersion: 'latest', sourceType: file.endsWith('.mjs') ? 'module' : 'script', loc: true, range: true }); }
      catch (error) { finding('parse', 'error', file, error.lineNumber, error.message); continue; }
      const manager = scope.analyze(ast, { ecmaVersion: 2024, sourceType: file.endsWith('.mjs') ? 'module' : 'script', optimistic: true, ignoreEval: true });
      if (file.startsWith('src/')) {
        for (const variable of manager.globalScope.variables) {
          if (!variable.defs.length) continue;
          const definition = variable.defs[0];
          const lexical = definition.type === 'ClassName' || definition.kind === 'const' || definition.kind === 'let';
          const binding = { name: variable.name, lexical, line: definition.name.loc.start.line };
          record.bindings.push(binding);
          if (!owners.has(variable.name)) owners.set(variable.name, []);
          owners.get(variable.name).push({ file, ...binding });
        }
      }
      const guarded = new Set();
      walk(ast, node => {
        if (node.type === 'UnaryExpression' && node.operator === 'typeof' && node.argument.type === 'Identifier') guarded.add(node.argument.range[0]);
      });
      record.globalReads = manager.globalScope.through.map(ref => ({ name: ref.identifier.name,
        line: ref.identifier.loc.start.line, write: ref.isWrite(), typeofGuard: guarded.has(ref.identifier.range[0]) }));
      // Recognize this codebase's UMD root parameter and local globalThis aliases.
      // These edges are deliberately inferred and do not claim alias completeness.
      const aliases = new Set(['globalThis', 'window']);
      walk(ast, node => {
        if (node.type === 'CallExpression' && node.callee.type === 'FunctionExpression' &&
          node.callee.params[0]?.type === 'Identifier' && node.arguments[0] && mentionsGlobal(node.arguments[0])) {
          aliases.add(node.callee.params[0].name);
        }
        if (node.type === 'VariableDeclarator' && node.id.type === 'Identifier' && node.init && mentionsGlobal(node.init)) aliases.add(node.id.name);
      });
      walk(ast, (node, parent) => {
        if (['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression'].includes(node.type)) {
          let branches = 1;
          walk(node.body, candidate => {
            if (['IfStatement', 'ForStatement', 'ForInStatement', 'ForOfStatement', 'WhileStatement', 'DoWhileStatement', 'CatchClause', 'ConditionalExpression'].includes(candidate.type) ||
              candidate.type === 'LogicalExpression' || candidate.type === 'SwitchCase' && candidate.test) branches++;
          }, true);
          record.functions.push({ name: node.id?.name ?? '<anonymous>', line: node.loc.start.line, endLine: node.loc.end.line, branchComplexity: branches });
        }
        if (node.type === 'MemberExpression' && node.object.type === 'Identifier' && aliases.has(node.object.name) &&
          (!node.computed || node.property.type === 'Literal')) {
          const name = node.computed ? String(node.property.value) : node.property.name;
          if (!name.startsWith('SovSchematic')) return;
          const write = parent?.type === 'AssignmentExpression' && parent.left === node;
          record.properties.push({ name, line: node.loc.start.line, write });
          if (write) { if (!propertyOwners.has(name)) propertyOwners.set(name, []); propertyOwners.get(name).push(file); }
        }
      });
      for (const [index, line] of text.split('\n').entries()) {
        const normalized = line.trim().replace(/\s+/g, ' ');
        if (normalized.length < 80 || normalized.startsWith('//')) continue;
        const key = sha256(normalized);
        if (!substantialLines.has(key)) substantialLines.set(key, []);
        substantialLines.get(key).push({ file, line: index + 1 });
      }
    }
    for (const [name, declarations] of owners) {
      if (declarations.length > 1 && declarations.some(item => item.lexical))
        finding('duplicate-lexical-owner', 'error', declarations[1].file, declarations[1].line, `${name} declared by ${declarations.map(item => item.file).join(', ')}`);
      else if (declarations.length > 1) finding('shared-global-redeclaration', 'warning', declarations[1].file, declarations[1].line, `${name} has multiple script owners`);
    }
    const inferredEdges = [];
    // HTML named access exposes identifier-shaped element IDs on the browser
    // global. Keep this runtime contract visible as debt, rather than mistaking
    // these actual owners for missing JavaScript declarations.
    const htmlNamedGlobals = [...template.matchAll(/\bid="([A-Za-z_$][\w$]*)"/g)].map(match => match[1]);
    const allowedBrowser = { ...globals.browser, ...globals.es2025,
      ...Object.fromEntries(htmlNamedGlobals.map(name => [name, 'readonly'])) };
    const shared = Object.fromEntries([...owners.keys(), ...propertyOwners.keys(), ...htmlNamedGlobals].map(name => [name, 'writable']));
    const eslint = new ESLint({ cwd: root, allowInlineConfig: false, overrideConfig: [{ files: ['src/*.js'], languageOptions: { globals: shared } }] });
    for (const result of await eslint.lintFiles(files)) {
      for (const message of result.messages) finding(message.ruleId ?? 'parse', message.severity === 2 ? 'error' : 'warning',
        normalize(path.relative(root, result.filePath)), message.line, message.message);
    }
    for (const record of records) {
      const runtimeGlobals = config.domFreeCores.includes(record.file) || config.environmentAdapters.includes(record.file)
        ? {...allowedBrowser, ...globals.node} : allowedBrowser;
      for (const ref of record.globalReads) {
        if (config.domFreeCores.includes(record.file) && config.domGlobals.includes(ref.name))
          finding('dom-free-core', 'error', record.file, ref.line, `Declared DOM-free core references ${ref.name}`);
        if (!record.file.startsWith('src/')) continue;
        if (htmlNamedGlobals.includes(ref.name) && !owners.has(ref.name)) {
          finding('implicit-html-named-access', 'warning', record.file, ref.line,
            `${ref.name} depends on the element ID declared in ${config.browserOrderSource}; explicit DOM bindings would remove this coupling`);
          inferredEdges.push({from:record.file,to:config.browserOrderSource,kind:'html-named-access',symbol:ref.name,line:ref.line});
        }
        const targets = owners.get(ref.name) ?? (propertyOwners.get(ref.name) ?? []).map(file => ({ file }));
        for (const target of targets.filter(item => item.file !== record.file)) inferredEdges.push({
          from: record.file, to: target.file, kind: 'inferred-shared-global', symbol: ref.name, line: ref.line,
          access: ref.write ? 'write' : 'read', laterOwner: order.indexOf(target.file) > order.indexOf(record.file)
        });
        if (!targets.length && !Object.hasOwn(runtimeGlobals, ref.name))
          finding('unresolved-browser-global', ref.typeofGuard ? 'warning' : 'error', record.file, ref.line,
            `${ref.name} has no declared shared or runtime owner${ref.typeofGuard ? '; optional existence probe' : ''}`);
      }
      for (const property of record.properties.filter(item => !item.write)) {
        for (const target of propertyOwners.get(property.name) ?? []) if (target !== record.file)
          inferredEdges.push({ from: record.file, to: target, kind: 'inferred-global-property', symbol: property.name, line: property.line,
            laterOwner: order.indexOf(target) > order.indexOf(record.file) });
      }
    }
    const corePattern = `^(${config.domFreeCores.map(file => file.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})$`;
    const permittedAdapterEdge = (from, to) => (config.permittedAdapterEdges ?? []).some(edge => edge.from === from && edge.to === to);
    const cruiseResult = await cruise(files, {
      baseDir: root, outputType: 'json', includeOnly: '^(src|mcp)/', doNotFollow: { path: 'node_modules' },
      validate: true, ruleSet: { forbidden: [
        { name: 'core-imports-editor', severity: 'error', from: { path: corePattern }, to: { path: '^src/', pathNot: corePattern } },
        { name: 'mcp-imports-editor', severity: 'error', from: { path: '^mcp/' }, to: { path: '^src/', pathNot: corePattern } }
      ] }
    });
    const graph = typeof cruiseResult.output === 'string' ? JSON.parse(cruiseResult.output) : cruiseResult.output;
    const importEdges = [];
    for (const module of graph.modules ?? []) {
      for (const dep of module.dependencies ?? []) {
        importEdges.push({ from: normalize(module.source), to: normalize(dep.resolved ?? dep.module), kind: 'extracted-import',
          specifier: dep.module, dependencyTypes: dep.dependencyTypes, unresolved: dep.couldNotResolve ?? false });
        if (dep.couldNotResolve) finding('unresolved-import', 'error', normalize(module.source), 1, dep.module);
        const allowed = config.mcpNodeImportAllowlist[normalize(module.source)];
        if (allowed && (dep.coreModule || dep.module.startsWith('node:')) && !allowed.includes(dep.module))
          finding('mcp-node-import-owner', 'error', normalize(module.source), 1, `${dep.module} is outside declared import authority`);
      }
    }
    for (const violation of graph.summary?.violations ?? []) {
      const from = normalize(violation.from), to = normalize(violation.to);
      if (['core-imports-editor','mcp-imports-editor'].includes(violation.rule.name) && permittedAdapterEdge(from, to)) continue;
      finding(violation.rule.name, violation.rule.severity, from, 1, `Imports ${violation.to}`);
    }
    // Mirror build.py without writing product/build files; hash every build input.
    const buildInputs = [config.browserOrderSource, 'styles/app.css', 'build.py', ...order,
      ...fs.readdirSync(path.join(root, 'data')).filter(name => name.endsWith('.pack.json')).sort().map(name => `data/${name}`)];
    let generated = template.replace('<link rel="stylesheet" href="styles/app.css">', `<style>\n${read('styles/app.css').trim()}\n</style>`);
    generated = generated.replace(/<script src="([^"]+)"><\/script>/g, (_, file) =>
      `<script data-beta-module="${file}">\n/* BEGIN ${file} */\n${read(file).trim()}\n/* END ${file} */\n</script>`);
    const packTag = '<script type="application/json" id="sov-packs">[]</script>';
    if (generated.split(packTag).length !== 2) finding('build-invalid', 'error', config.browserOrderSource, 1, 'Expected one pack placeholder');
    const packs = buildInputs.filter(file => file.endsWith('.pack.json')).map(file => JSON.parse(read(file)));
    generated = generated.replace(packTag, `<script type="application/json" id="sov-packs">${JSON.stringify(packs).replaceAll('</', '<\\/')}</script>`);
    const docPaths = ['docs/local-core/COWORKING.md', 'API.md', 'DATA-FORMATS.md', 'STATE-SPACE.md', 'MODULES.md'];
    buildInputs.push(...docPaths);
    const docs = Object.fromEntries(docPaths.map(file => [`schematically://docs/${file}`, read(file)]));
    const docsTag = '<script type="application/json" id="sov-docs">{}</script>';
    if (generated.split(docsTag).length !== 2) finding('build-invalid', 'error', config.browserOrderSource, 1, 'Expected one documentation placeholder');
    generated = generated.replace(docsTag, `<script type="application/json" id="sov-docs">${JSON.stringify(docs).replaceAll('</', '<\\/')}</script>`);
    const buildFresh = generated === read('index.html');
    if (!buildFresh) finding('build-stale', 'error', 'index.html', 1, 'Generated document differs from declared sources; run the canonical build before qualification');
    const versions = {};
    for (const name of ['eslint', 'espree', 'eslint-scope', 'dependency-cruiser', 'globals'])
      versions[name] = JSON.parse(fs.readFileSync(path.join(root, 'node_modules', name, 'package.json'), 'utf8')).version;
    const allEdges = [...importEdges, ...inferredEdges];
    for (const edge of inferredEdges) {
      if (config.domFreeCores.includes(edge.from) && edge.to.startsWith('src/') && !config.domFreeCores.includes(edge.to) && !permittedAdapterEdge(edge.from, edge.to))
        finding('core-reads-editor-global', 'error', edge.from, edge.line, `${edge.symbol} belongs to ${edge.to}`);
      if (edge.from.startsWith('mcp/') && edge.to.startsWith('src/') && !config.domFreeCores.includes(edge.to) && !permittedAdapterEdge(edge.from, edge.to))
        finding('mcp-reads-editor-global', 'error', edge.from, edge.line, `${edge.symbol} belongs to ${edge.to}`);
    }
    const manifest = JSON.parse(read('package.json'));
    for (const [name, version] of Object.entries(versions)) if (version !== manifest.devDependencies[name])
      finding('tool-version', 'error', 'package.json', 1, `${name}: loaded ${version}, declared ${manifest.devDependencies[name]}`);
    const report = { schemaVersion: 1, command: process.argv, environment: { node: process.version, platform: process.platform },
      policy: config, tools: versions, elapsedSeconds: (Date.now() - started) / 1000, browserOrder: order, htmlNamedGlobals,
      sourceIdentity: [...files, 'arch.config.json', 'eslint.config.mjs', 'scripts/arch_scan.mjs', 'MODULES.md', 'package.json', 'package-lock.json'].map(file =>
        ({ file, sha256: sha256(fs.readFileSync(path.join(root, file))) })),
      build: { fresh: buildFresh, comparison: 'UTF-8 text with CRLF normalized to LF, matching build.py read_text behavior',
        expectedSha256: sha256(generated), observedSha256: sha256(read('index.html')), observedRawSha256: sha256(fs.readFileSync(path.join(root, 'index.html'))),
        inputs: buildInputs.map(file => ({ file, sha256: sha256(fs.readFileSync(path.join(root, file))) })) },
      files: records, findings, imports: importEdges, inferredEdges,
      cycles: { extractedImports: cycles(files, importEdges), withInferredGlobals: cycles(files, allEdges) },
      repeatedSubstantialLines: [...substantialLines].filter(([, occurrences]) => new Set(occurrences.map(item => item.file)).size > 1)
        .map(([hash, occurrences]) => ({ hash, occurrences })), passed: !findings.some(item => item.severity === 'error') };
    fs.writeFileSync(path.join(out, 'architecture.json'), json(report));
    fs.writeFileSync(path.join(out, 'dependency-cruiser.json'), json(graph));
    const graphFiles = [...files, config.browserOrderSource];
    const nodeId = new Map(graphFiles.map((file, index) => [file, `n${index}`]));
    const pairs = new Map();
    for (const edge of allEdges) if (nodeId.has(edge.from) && nodeId.has(edge.to)) pairs.set(`${edge.from}|${edge.to}|${edge.kind}`, edge);
    fs.writeFileSync(path.join(out, 'dependencies.mmd'), `flowchart LR\n${graphFiles.map(file => `  ${nodeId.get(file)}["${file}"]`).join('\n')}\n${[...pairs.values()].map(edge =>
      `  ${nodeId.get(edge.from)} ${edge.kind === 'extracted-import' ? '-->' : '-.->'} ${nodeId.get(edge.to)}`).join('\n')}\n`);
    fs.writeFileSync(path.join(out, 'dependencies.dot'), `digraph ARCH {\n${graphFiles.map(file => `  ${nodeId.get(file)} [label=${JSON.stringify(file)}];`).join('\n')}\n${[...pairs.values()].map(edge =>
      `  ${nodeId.get(edge.from)} -> ${nodeId.get(edge.to)} [style=${edge.kind === 'extracted-import' ? 'solid' : 'dashed'}, label=${JSON.stringify(edge.kind)}];`).join('\n')}\n}\n`);
    console.log(json({ passed: report.passed, files: files.length, findings: findings.length, elapsedSeconds: report.elapsedSeconds, out }));
    process.exitCode = report.passed ? 0 : 1;
  }
}

function walk(node, visitor, stopNestedFunctions = false, parent = null) {
  if (!node || typeof node !== 'object' || typeof node.type !== 'string') return;
  visitor(node, parent);
  for (const [key, value] of Object.entries(node)) {
    if (['loc', 'range', 'tokens', 'comments'].includes(key)) continue;
    const children = Array.isArray(value) ? value : [value];
    for (const child of children) {
      if (stopNestedFunctions && child && ['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression'].includes(child.type)) continue;
      walk(child, visitor, stopNestedFunctions, node);
    }
  }
}

function mentionsGlobal(node) {
  let found = false;
  walk(node, part => { if (part.type === 'Identifier' && part.name === 'globalThis' || part.type === 'ThisExpression') found = true; });
  return found;
}

// Strongly connected components retain cycles as sets without enumerating every path.
function cycles(files, edges) {
  const adjacency = new Map(files.map(file => [file, new Set()]));
  for (const edge of edges) if (adjacency.has(edge.from) && adjacency.has(edge.to)) adjacency.get(edge.from).add(edge.to);
  const indices = new Map(), low = new Map(), active = new Set(), stack = [], result = [];
  let next = 0;
  function visit(file) {
    indices.set(file, next); low.set(file, next++); stack.push(file); active.add(file);
    for (const target of adjacency.get(file)) {
      if (!indices.has(target)) { visit(target); low.set(file, Math.min(low.get(file), low.get(target))); }
      else if (active.has(target)) low.set(file, Math.min(low.get(file), indices.get(target)));
    }
    if (low.get(file) !== indices.get(file)) return;
    const members = [];
    let target;
    do { target = stack.pop(); active.delete(target); members.push(target); } while (target !== file);
    if (members.length > 1 || adjacency.get(file).has(file)) result.push(members.sort());
  }
  for (const file of files) if (!indices.has(file)) visit(file);
  return result;
}
