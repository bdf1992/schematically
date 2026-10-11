#!/usr/bin/env node
// Supervisor-owned execution only. Collection must precede every product import and file effect.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

export const CASE_IDS = Object.freeze([
  'headless/file-absent', 'headless/file-directory-refused', 'headless/file-invalid-json',
  'headless/file-invalid-schema', 'headless/file-atomic-roundtrip',
  'headless/mcp-initialize', 'headless/mcp-discovery-notification', 'headless/mcp-tool-schemas',
  'headless/mcp-guide', 'headless/mcp-resources-unsupported', 'headless/mcp-read',
  'headless/mcp-crud', 'headless/mcp-stale-revision', 'headless/mcp-batch-history',
  'headless/mcp-batch-atomic-refusal', 'headless/mcp-history-empty', 'headless/mcp-replace-undo',
  'headless/mcp-checkpoint', 'headless/mcp-concerns', 'headless/mcp-graph',
  'headless/mcp-layout', 'headless/mcp-render-unavailable', 'headless/render-adapter',
  'headless/mcp-runs', 'headless/mcp-run-refusals', 'headless/mcp-replay-tamper',
  'headless/mcp-simulation', 'headless/live-observation',
  'headless/rest-crud', 'headless/rest-document-replacement', 'headless/rest-read-apply',
  'headless/rest-concerns', 'headless/rest-runs', 'headless/rest-run-errors',
  'headless/rest-graph-simulation', 'headless/rest-render-unavailable',
  'headless/rest-validation', 'headless/mcp-method-errors', 'headless/editor-inert-document',
  'headless/root-formats-options', 'headless/persistence-write-failure'
]);

const argv = process.argv.slice(2);
if (argv.includes('--collect')) {
  process.stdout.write(JSON.stringify(CASE_IDS) + '\n');
} else {
  const options = {};
  for (let i = 0; i < argv.length; i += 2) {
    assert.ok(['--coverage-dir', '--source-root', '--native-binary'].includes(argv[i]), `Unknown option ${argv[i]}`);
    assert.ok(argv[i + 1] && !argv[i + 1].startsWith('--'), `Missing value for ${argv[i]}`);
    options[argv[i]] = argv[i + 1];
  }
  assert.ok(options['--coverage-dir'], '--coverage-dir is required');
  const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const coverageDir = path.resolve(options['--coverage-dir']);
  const started = Date.now();
  const results = [];
  let temporary;
  let fatal;
  try {
    for (const relative of [
      'src/03-canonical.js', 'src/03-notation-core.js', 'src/04-signal-model.js',
      'src/06-attachment-core.js', 'src/05-data-core.js', 'src/07-state-space.js',
      'src/07-state-surface.js', 'src/07-graph-core.js', 'src/08-layout-core.js'
    ]) await import(pathToFileURL(path.join(ROOT, relative)).href);
    const {createSurface} = await import('../mcp/surface.mjs');
    const {createFileStore} = await import('../mcp/store-file.mjs');
    const {createMemoryStore} = await import('../mcp/store-memory.mjs');
    const Data = globalThis.SovSchematicData;
    temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'schematically-headless-'));
    const readText = relative => fs.readFileSync(path.join(ROOT, relative), 'utf8');
    const sourceReadText = relative => fs.readFileSync(path.join(options['--source-root'] || ROOT, relative), 'utf8');
    const packs = fs.readdirSync(path.join(ROOT, 'data')).filter(n => n.endsWith('.pack.json')).sort()
      .map(n => JSON.parse(readText('data/' + n)));
    const seed = readText('examples/01-source-hold.sov');
    const andSeed = readText('examples/state/and.sov');
    const area = {x:-1000000, y:-1000000, width:2000000, height:2000000};
    const clone = value => JSON.parse(JSON.stringify(value));
    const blank = () => Data.makeDocument({id:'headless-qualification'});
    const component = (id = 'qa-card') => ({id, symbolId:'act', x:900, y:200, config:{label:id}});
    const batch = (id = 'qa-card') => ({operations:[{op:'create', resource:'component', value:component(id)}]});
    const inputs = [{entity:'A', point:'self', value:true, at:0}, {entity:'B', point:'self', value:true, at:0}];
    const failures = value => assert.equal(value.ok, false, JSON.stringify(value));
    const receipt = value => { assert.equal(value.ok, true, JSON.stringify(value)); return value; };
    function sameAuthored(actual, expected) {
      // Port-level mirrors are regenerated projections, not saved truth.
      // Compare the complete canonical authored record, including revisions/meta.
      assert.deepEqual(Data.compactDocument(actual), Data.compactDocument(expected));
      for (const component of actual.components) for (const port of Object.values(component.config?.ports || {})) {
        const active=port.connections?.[port.activeConnection || 0];
        if (active && port.access !== undefined) assert.equal(port.access, active.access);
      }
    }
    function setup(text = seed, overrides = {}) {
      const store = overrides.store || createMemoryStore(text);
      const surface = createSurface({store, packs, readText, describe:()=>'qualification.sov', ...overrides});
      let id = 0;
      async function raw(method, reqPath, body, query = {}) {
        const r = await surface.handle({method, path:reqPath, query, headers:{}, body});
        const json = typeof r.body === 'string' && (r.body.startsWith('{') || r.body.startsWith('['));
        return {...r, value:json ? JSON.parse(r.body) : null};
      }
      const http = (method, reqPath, body, query) => raw(method, reqPath, body === undefined ? null : JSON.stringify(body), query);
      const rpc = (method, params = {}) => http('POST', '/mcp', {jsonrpc:'2.0', id:++id, method, params});
      async function tool(name, args = {}, ok = true) {
        const response = await rpc('tools/call', {name, arguments:args});
        assert.equal(response.status, 200, JSON.stringify(response.value));
        assert.equal(response.value.result.isError, !ok, JSON.stringify(response.value));
        const result=response.value.result;
        assert.ok(result.structuredContent && !Array.isArray(result.structuredContent), 'MCP structured content must be an object');
        return JSON.parse(result.content.find(item=>item.type==='text').text);
      }
      const doc = () => tool('schematic.document.get');
      return {store, surface, raw, http, rpc, tool, doc};
    }
    const cases = new Map();
    const add = (name, fn) => cases.set('headless/' + name, fn);
    function fileCase(name) { return path.join(temporary, name, 'document.sov'); }

    add('file-absent', async () => {
      const file = fileCase('absent'), store = createFileStore(file);
      assert.equal(store.read(), null);
      const s = setup(null, {store}); const d = await s.doc();
      assert.equal(d.components.length, 0); assert.equal(d.revision, 0); assert.ok(!fs.existsSync(file));
    });
    add('file-directory-refused', () => {
      const directory = path.join(temporary, 'unreadable'); fs.mkdirSync(directory);
      const marker = path.join(directory, 'preserve'); fs.writeFileSync(marker, 'original');
      const store = createFileStore(directory);
      assert.throws(() => store.read(), /DOCUMENT_READ_FAILED/);
      assert.throws(() => setup(null, {store}), /DOCUMENT_READ_FAILED/);
      assert.equal(fs.readFileSync(marker, 'utf8'), 'original'); assert.ok(fs.statSync(directory).isDirectory());
    });
    for (const [name, text] of [['file-invalid-json', '{broken'], ['file-invalid-schema', '{"schema":"unknown/document@9"}']]) {
      add(name, () => {
        const file = fileCase(name); fs.mkdirSync(path.dirname(file), {recursive:true}); fs.writeFileSync(file, text);
        assert.throws(() => setup(null, {store:createFileStore(file)}), /DOCUMENT_INVALID/);
        assert.equal(fs.readFileSync(file, 'utf8'), text); assert.ok(!fs.existsSync(file + '.tmp'));
      });
    }
    add('file-atomic-roundtrip', async () => {
      const file = fileCase('atomic'), store = createFileStore(file);
      store.write(JSON.stringify(blank())); assert.ok(!fs.existsSync(file + '.tmp'));
      const s = setup(null, {store}), authored=batch();
      authored.operations[0].value.config.ports={out:{face:'external',connectionCount:1,activeConnection:0,connections:[{id:'connection-1',flow:'out',access:'read'}]}};
      receipt(await s.tool('schematic.apply', authored));
      const disk = JSON.parse(store.read()); assert.ok(disk.components.some(c => c.id === 'qa-card'));
      const reopened=await setup(null, {store:createFileStore(file)}).doc();
      sameAuthored(reopened, await s.doc());
      assert.equal(reopened.components.find(c=>c.id==='qa-card').config.ports.out.connections[0].access,'read');
      assert.ok(!fs.existsSync(file + '.tmp'));
    });
    add('mcp-initialize', async () => {
      const s = setup();
      for (const version of ['2024-11-05', '2025-03-26', '2025-06-18', '2026-07-28', 'unsupported']) {
        const r = await s.rpc('initialize', {protocolVersion:version}); assert.equal(r.status, 200);
        assert.equal(r.value.result.protocolVersion, version === 'unsupported' ? '2026-07-28' : version);
        assert.equal(r.headers['mcp-protocol-version'], r.value.result.protocolVersion);
        assert.ok(r.value.result.capabilities.tools); assert.match(r.value.result.instructions, /schematic\.guide/);
      }
      assert.equal(s.store.writes, 0);
    });
    add('mcp-discovery-notification', async () => {
      const s = setup(); assert.deepEqual((await s.rpc('ping')).value.result, {});
      assert.equal((await s.rpc('server/discover')).value.result.serverInfo.name, 'soveraeign-schematic');
      const r = await s.http('POST', '/mcp', {jsonrpc:'2.0', method:'notifications/initialized'});
      assert.equal(r.status, 202); assert.equal(r.body, ''); assert.equal(s.store.writes, 0);
    });
    add('mcp-tool-schemas', async () => {
      const s = setup(), tools = (await s.rpc('tools/list')).value.result.tools;
      assert.equal(new Set(tools.map(t => t.name)).size, tools.length);
      for (const t of tools) { assert.equal(t.inputSchema.type, 'object'); assert.ok(t.description); }
      for (const name of ['schematic.apply','schematic.document.replace','schematic.history.undo','schematic.run.replay','schematic.state.query','schematic.layout','schematic.render']) assert.ok(tools.some(t => t.name === name));
      assert.deepEqual(tools.find(t => t.name === 'schematic.apply').inputSchema.required, ['operations']);
    });
    add('mcp-guide', async () => {
      const s = setup(); assert.equal((await s.tool('schematic.guide')).next, 'model');
      for (const step of ['model','palette','concerns','apply','layout','check','review','layout-review']) {
        const r = await s.tool('schematic.guide', {step}); receipt(r); assert.ok(r.guide.trim().length > 30);
        if (r.source) { const source = sourceReadText(r.source); assert.ok(source.length > 30); assert.ok(r.guide.split('\n').filter(l => l.trim()).every(l => source.includes(l))); }
      }
      assert.equal((await s.tool('schematic.guide', {step:'missing'}, false)).error.code, 'GUIDE_STEP_UNKNOWN');
      assert.equal(s.store.writes, 0);
    });
    add('mcp-resources-unsupported', async () => {
      const s = setup();
      for (const method of ['resources/list','resources/read']) { const r = await s.rpc(method, {uri:'schematically://docs/API.md'}); assert.equal(r.status, 404); assert.equal(r.value.error.code, -32601); }
      assert.equal((await s.rpc('initialize')).value.result.capabilities.resources, undefined);
    });
    add('mcp-read', async () => {
      const s = setup(), before = await s.doc();
      const r = await s.tool('schematic.read', {area}); receipt(r);
      assert.deepEqual(r.components.map(c => c.id).sort(), before.components.map(c => c.id).sort());
      const one = await s.tool('schematic.read', {ids:[before.components[0].id]}); receipt(one); assert.equal(one.components.length, 1);
      assert.deepEqual(await s.tool('schematic.markers'), Data.markersFor(before));
      await s.tool('schematic.read', {}, false); assert.equal(s.store.writes, 0);
    });
    add('mcp-crud', async () => {
      const s = setup(), rev = (await s.doc()).revision;
      const made = receipt(await s.tool('schematic.create', {resource:'component', value:component()})); assert.equal(made.revisionAfter, rev + 1);
      assert.equal((await s.tool('schematic.get', {resource:'component', id:'qa-card'})).result.id, 'qa-card');
      assert.ok((await s.tool('schematic.list', {resource:'component'})).result.some(c => c.id === 'qa-card'));
      receipt(await s.tool('schematic.update', {resource:'component', id:'qa-card', patch:{config:{label:'changed'}}}));
      assert.equal((await s.doc()).components.find(c => c.id === 'qa-card').config.label, 'changed');
      receipt(await s.tool('schematic.delete', {resource:'component', id:'qa-card'}));
      assert.ok(!(await s.doc()).components.some(c => c.id === 'qa-card')); assert.equal(s.store.writes, 3);
    });
    add('mcp-stale-revision', async () => {
      const s = setup(), before = await s.doc(); receipt(await s.tool('schematic.apply', batch()));
      const changed = await s.doc(), bytes = s.store.read(), writes = s.store.writes;
      for (const [name, args] of [['schematic.create',{resource:'component',value:component('stale')}],['schematic.update',{resource:'component',id:'qa-card',patch:{x:100}}],['schematic.delete',{resource:'component',id:'qa-card'}],['schematic.apply',batch('stale')]]) {
        const r = await s.tool(name, {...args, ifRevision:before.revision}, false); assert.match(r.error.message, /^Stale revision/);
      }
      assert.deepEqual(await s.doc(), changed); assert.equal(s.store.read(), bytes); assert.equal(s.store.writes, writes);
    });
    add('mcp-batch-history', async () => {
      const s = setup(), before = await s.doc();
      const r = receipt(await s.tool('schematic.apply', {operations:[
        {op:'create',resource:'component',ref:'$first',value:{symbolId:'act',x:100,y:100}},
        {op:'create',resource:'component',ref:'$second',value:{symbolId:'hold',x:400,y:100}},
        {op:'create',resource:'wire',value:{a:'$first',aSide:'out',b:'$second',bSide:'in'}}]}));
      assert.ok(r.result.ids.$first); assert.equal(r.revisionAfter, before.revision + 1);
      const after = await s.doc(); assert.equal(after.wires.length, before.wires.length + 1);
      sameAuthored(await s.tool('schematic.history.undo'), before);
      sameAuthored(await s.tool('schematic.history.redo'), after); assert.equal(s.store.writes, 3);
    });
    add('mcp-batch-atomic-refusal', async () => {
      const s = setup(), before = await s.doc(), text = s.store.read();
      const r = await s.tool('schematic.apply', {operations:[...batch().operations,{op:'create',resource:'wire',value:{a:'missing-a',b:'missing-b'}}]}, false);
      failures(r); assert.equal(r.error.index, 1); assert.deepEqual(await s.doc(), before);
      assert.equal(s.store.read(), text); assert.equal(s.store.writes, 0); await s.tool('schematic.history.undo', {}, false);
    });
    add('mcp-history-empty', async () => {
      const s = setup(); assert.match((await s.tool('schematic.history.undo', {}, false)).error, /Nothing to undo/);
      assert.match((await s.tool('schematic.history.redo', {}, false)).error, /Nothing to redo/);
      assert.equal(s.store.writes, 0);
    });
    add('mcp-replace-undo', async () => {
      const s = setup(), before = await s.doc(); const replaced = await s.tool('schematic.document.replace', {document:blank()});
      assert.equal(replaced.id, 'headless-qualification'); assert.equal(replaced.components.length, 0);
      assert.deepEqual(await s.tool('schematic.history.undo'), before);
      assert.deepEqual(await s.tool('schematic.history.redo'), replaced);
      const bytes = s.store.read(); await s.tool('schematic.document.replace', {document:{...blank(),components:[component(),component()]}}, false);
      assert.equal(s.store.read(), bytes);
    });
    add('mcp-checkpoint', async () => {
      const s = setup(), before = await s.doc(); assert.deepEqual(await s.tool('schematic.checkpoint.list'), []);
      const cp = await s.tool('schematic.checkpoint.create', {name:'Before edit'}); assert.equal(cp.name, 'Before edit'); assert.equal(cp.document, undefined);
      receipt(await s.tool('schematic.apply', batch()));
      const r = await s.tool('schematic.checkpoint.restore', {id:cp.id}); assert.deepEqual(r.components, before.components);
      assert.equal((await s.tool('schematic.checkpoint.list'))[0].id, cp.id);
      const bytes = s.store.read(); await s.tool('schematic.checkpoint.restore', {id:'missing'}, false); assert.equal(s.store.read(), bytes);
      const reopened = setup(s.store.read()); assert.equal((await reopened.tool('schematic.checkpoint.list'))[0].id, cp.id);
    });
    add('mcp-concerns', async () => {
      const s = setup(), before = await s.doc(), report = await s.tool('schematic.concerns');
      const row = report.rows.find(r => r.target === null); assert.ok(row);
      receipt(await s.tool('schematic.concerns.answer', {answers:[{concern:row.concern,answer:'Qualification fixture purpose'}]}));
      const answered = await s.tool('schematic.concerns'); assert.equal(answered.answered, report.answered + 1);
      assert.ok(!(await s.tool('schematic.concerns', {open:true})).rows.some(r => r.concern === row.concern && r.target === null));
      assert.deepEqual(await s.tool('schematic.history.undo'), before);
      const bytes = s.store.read(); await s.tool('schematic.concerns.answer', {answers:[{concern:'undeclared-qa',answer:'refuse'}]}, false); assert.equal(s.store.read(), bytes);
      receipt(await s.tool('schematic.concerns.answer', {answers:[{concern:row.concern,answer:null}]}));
    });
    add('mcp-graph', async () => {
      const s = setup(), before = await s.doc();
      const jgf = await s.tool('schematic.graph.query', {verb:'export'}); receipt(jgf);
      assert.deepEqual(Object.keys(jgf.graph.graph.nodes).sort(), before.components.map(c => c.id).sort());
      assert.match((await s.tool('schematic.graph.query',{verb:'export',args:{format:'dot'}})).text,/digraph/);
      await s.tool('schematic.graph.query', {verb:'unknown'}, false);
      assert.deepEqual(await s.doc(), before); assert.equal(s.store.writes, 0);
    });
    add('mcp-layout', async () => {
      const s = setup(), before = await s.doc(); receipt(await s.tool('schematic.layout',{op:'list'})); assert.equal(s.store.writes, 0);
      const made = receipt(await s.tool('schematic.layout',{op:'create',name:'Qualification view'})); assert.ok(made.id);
      receipt(await s.tool('schematic.layout',{op:'rename',view:made.id,name:'Renamed'}));
      assert.equal((await s.doc()).components.length, before.components.length);
      const bytes = s.store.read(); await s.tool('schematic.layout',{op:'unsupported'},false); assert.equal(s.store.read(),bytes);
      receipt(await s.tool('schematic.layout',{op:'delete',view:made.id}));
    });
    add('mcp-render-unavailable', async () => {
      const s = setup(); for (const name of ['schematic.render','schematic.layout.metrics']) assert.equal((await s.tool(name,{},false)).code,'RENDERER_UNAVAILABLE');
      assert.equal(s.store.writes,0);
    });
    add('render-adapter', async () => {
      const calls=[]; const s=setup(seed,{render:async(formats,args)=>{
        calls.push({formats,document:clone(args.document)}); args.document.id='adapter-must-not-mutate';
        return {ok:true,svg:'<svg>qualification</svg>',png:Buffer.from('fixture-png').toString('base64'),metrics:{score:9,counts:{nodes:3}}};
      }}); const before=await s.doc();
      assert.equal((await s.tool('schematic.render',{format:'svg'})).svg,'<svg>qualification</svg>');
      const png=await s.rpc('tools/call',{name:'schematic.render',arguments:{format:'png'}});
      assert.equal(png.value.result.content[0].mimeType,'image/png'); assert.equal(png.value.result.structuredContent.png,undefined);
      assert.equal((await s.tool('schematic.layout.metrics')).score,9);
      assert.equal((await s.http('GET','/api/v1/render.svg')).body.toString(),'<svg>qualification</svg>');
      assert.equal((await s.http('GET','/api/v1/render.png')).body.toString(),'fixture-png');
      assert.equal((await s.http('GET','/api/v1/layout/metrics')).value.score,9);
      assert.equal(calls.length,6); assert.deepEqual(await s.doc(),before); assert.equal(s.store.writes,0);
    });
    add('mcp-runs', async () => {
      const s=setup(andSeed), before=await s.doc();
      const run=receipt(await s.tool('schematic.run.start',{inputs,seed:'qualification',budget:100})); assert.ok(run.handle);
      receipt(await s.tool('schematic.run.step',{handle:run.handle})); receipt(await s.tool('schematic.run.settle',{handle:run.handle}));
      const query=receipt(await s.tool('schematic.state.query',{handle:run.handle,entity:'Q',observable:'logic.level'})); assert.ok(Array.isArray(query.result)); assert.ok(query.result.length);
      const trace=receipt(await s.tool('schematic.run.trace',{handle:run.handle})); assert.ok(trace.result.ledger.length);
      receipt(await s.tool('schematic.run.replay',{trace:trace.result}));
      assert.deepEqual(await s.doc(),before); assert.equal(s.store.writes,0); await s.tool('schematic.history.undo',{},false);
    });
    add('mcp-run-refusals', async () => {
      const s=setup(andSeed); for (const args of [{budget:1000001},{budget:-1},{inputs:[{entity:'A',point:'self',value:'wrong',at:0}]},{extra:true}]) failures(await s.tool('schematic.run.start',args,false));
      for (const name of ['schematic.run.step','schematic.run.settle','schematic.run.trace']) assert.equal((await s.tool(name,{handle:'no-such-run'},false)).error.code,'RUN_NOT_FOUND');
      failures(await s.tool('schematic.state.query',{handle:'missing',entity:'Q',observable:'logic.level'},false)); assert.equal(s.store.writes,0);
    });
    add('mcp-replay-tamper', async () => {
      const s=setup(andSeed), run=receipt(await s.tool('schematic.run.start',{inputs})); receipt(await s.tool('schematic.run.settle',{handle:run.handle}));
      const trace=clone((await s.tool('schematic.run.trace',{handle:run.handle})).result); assert.ok(trace.ledger.length>1);
      trace.ledger[1].hash=(trace.ledger[1].hash[0]==='1'?'0':'1')+trace.ledger[1].hash.slice(1);
      assert.equal((await s.tool('schematic.run.replay',{trace},false)).error.code,'TRACE_INVALID');
      failures(await s.tool('schematic.run.replay',{trace:{}},false)); assert.equal(s.store.writes,0);
    });
    add('mcp-simulation', async () => {
      const s=setup(), before=await s.doc(); assert.equal((await s.tool('schematic.sim.inspect',{},false)).code,'NO_SIMULATION');
      receipt(await s.tool('schematic.sim.start')); receipt(await s.tool('schematic.sim.inspect',{what:'state'}));
      assert.ok(Array.isArray((await s.tool('schematic.sim.scenarios')).scenarios));
      await s.tool('schematic.sim.inspect',{what:'unsupported'},false); await s.tool('schematic.sim.scenario',{id:'missing'},false);
      assert.equal((await s.tool('schematic.sim.stop')).stopped,true); assert.equal((await s.tool('schematic.sim.stop')).stopped,false);
      assert.deepEqual(await s.doc(),before); assert.equal(s.store.writes,0);
    });
    add('live-observation', async () => {
      const s=setup(), before=await s.doc(); assert.equal((await s.tool('schematic.live.get')).connected,false);
      assert.equal((await s.raw('POST','/api/v1/live','{bad')).status,400); assert.equal((await s.http('POST','/api/v1/live',{})).status,400);
      const snapshot={schema:'soveraeign.schematic/live@0.1',document:{id:'unsaved-browser'},selection:{ids:['qa']},revision:42};
      assert.equal((await s.http('POST','/api/v1/live',snapshot)).status,202);
      const full=await s.tool('schematic.live.get'); assert.equal(full.connected,true); assert.deepEqual(full.snapshot,snapshot);
      assert.equal((await s.tool('schematic.live.selection')).snapshot.document,undefined);
      assert.equal((await s.http('GET','/api/v1/live',undefined,{selection:'1'})).value.snapshot.document,undefined);
      assert.deepEqual(await s.doc(),before); assert.equal(s.store.writes,0);
    });
    add('rest-crud', async () => {
      const s=setup(); assert.equal((await s.http('POST','/api/v1/components',component())).status,201);
      assert.equal((await s.http('GET','/api/v1/components/qa-card')).value.id,'qa-card');
      assert.ok((await s.http('GET','/api/v1/components')).value.some(c=>c.id==='qa-card'));
      assert.equal((await s.http('PATCH','/api/v1/components/qa-card',{config:{label:'REST edit'}})).status,200);
      assert.equal((await s.tool('schematic.get',{resource:'component',id:'qa-card'})).result.config.label,'REST edit');
      assert.equal((await s.http('DELETE','/api/v1/components/qa-card')).status,200);
      assert.equal((await s.http('GET','/api/v1/components/qa-card')).status,404); assert.equal(s.store.writes,3);
    });
    add('rest-document-replacement', async () => {
      const s=setup(), before=await s.doc(); const r=await s.http('PUT','/api/v1/document',blank()); assert.equal(r.status,200);
      assert.deepEqual((await s.http('GET','/api/v1/document')).value,await s.doc()); assert.deepEqual(await s.tool('schematic.history.undo'),before);
      const bytes=s.store.read(); assert.equal((await s.http('PUT','/api/v1/document',{...blank(),components:[component(),component()]})).status,400); assert.equal(s.store.read(),bytes);
    });
    add('rest-read-apply', async () => {
      const s=setup(), before=await s.doc(); assert.equal((await s.http('POST','/api/v1/apply',batch())).status,200);
      const r=await s.http('POST','/api/v1/read',{ids:['qa-card']}); assert.equal(r.status,200); assert.equal(r.value.components[0].id,'qa-card');
      assert.equal((await s.http('POST','/api/v1/read',{})).status,400);
      const bytes=s.store.read(); assert.equal((await s.http('POST','/api/v1/apply',{...batch('stale'),ifRevision:before.revision})).status,409);
      assert.equal((await s.http('POST','/api/v1/apply',{operations:[]})).status,400); assert.equal(s.store.read(),bytes);
      assert.deepEqual((await s.http('POST','/api/v1/read',{area})).value,await s.tool('schematic.read',{area}));
    });
    add('rest-concerns', async () => {
      const s=setup(), before=await s.doc(); assert.deepEqual((await s.http('GET','/api/v1/concerns')).value,await s.tool('schematic.concerns'));
      assert.equal((await s.http('POST','/api/v1/concerns',{answers:[{concern:'what',answer:'REST qualification'}]})).status,200);
      assert.deepEqual((await s.http('GET','/api/v1/concerns',undefined,{open:'1'})).value,await s.tool('schematic.concerns',{open:true}));
      const bytes=s.store.read(); assert.equal((await s.http('POST','/api/v1/concerns',{answers:[{concern:'why',answer:'stale'}],ifRevision:before.revision})).status,409);
      assert.equal((await s.http('POST','/api/v1/concerns',{answers:[{concern:'unknown',answer:'refuse'}]})).status,400); assert.equal(s.store.read(),bytes);
    });
    add('rest-runs', async () => {
      const s=setup(andSeed), before=await s.doc(); const start=await s.http('POST','/api/v1/runs',{inputs,budget:100}); assert.equal(start.status,201); receipt(start.value);
      const prefix='/api/v1/runs/'+encodeURIComponent(start.value.handle);
      receipt((await s.http('POST',prefix+'/step')).value); receipt((await s.http('POST',prefix+'/settle')).value);
      const query=await s.http('POST',prefix+'/query',{entity:'Q',observable:'logic.level'}); receipt(query.value); assert.ok(query.value.result.length);
      const trace=await s.http('GET',prefix+'/trace'); receipt(trace.value); receipt((await s.http('POST','/api/v1/replay',trace.value.result)).value);
      assert.deepEqual(await s.doc(),before); assert.equal(s.store.writes,0);
    });
    add('rest-run-errors', async () => {
      const s=setup(andSeed);
      for (const route of ['/api/v1/runs','/api/v1/replay','/api/v1/runs/missing/query']) { const r=await s.raw('POST',route,'{bad'); assert.equal(r.status,400); assert.equal(r.value.error.code,'INPUT_INVALID'); }
      assert.equal((await s.http('POST','/api/v1/runs/%zz/step')).status,400);
      assert.equal((await s.http('POST','/api/v1/runs/missing/step')).status,404);
      assert.equal((await s.http('POST','/api/v1/runs',{budget:1000001})).status,409);
      assert.equal((await s.http('GET','/api/v1/runs')).status,404); assert.equal((await s.http('POST','/api/v1/runs/missing/unsupported')).status,404);
      assert.equal(s.store.writes,0);
    });
    add('rest-graph-simulation', async () => {
      const s=setup(); const graph=await s.http('GET','/api/v1/graph/export'); assert.equal(graph.status,200);
      assert.deepEqual(graph.value,await s.tool('schematic.graph.query',{verb:'export'}));
      assert.equal((await s.http('POST','/api/v1/graph/export',{format:'dot'})).status,200);
      assert.equal((await s.http('GET','/api/v1/graph/missing')).status,400);
      assert.equal((await s.http('POST','/api/v1/sim/start',{})).status,200);
      assert.equal((await s.http('GET','/api/v1/sim/inspect')).value.ok,true);
      assert.equal((await s.http('POST','/api/v1/sim/missing',{})).status,404);
      assert.equal((await s.http('POST','/api/v1/sim/stop',{})).value.stopped,true); assert.equal(s.store.writes,0);
    });
    add('rest-render-unavailable', async () => {
      const s=setup(); for(const route of ['/api/v1/render.svg','/api/v1/render.png','/api/v1/layout/metrics']) {
        const r=await s.http('GET',route); assert.equal(r.status,503); assert.equal(r.value.code,'RENDERER_UNAVAILABLE');
      }
    });
    add('rest-validation', async () => {
      const s=setup(); const bytes=s.store.read();
      assert.equal((await s.http('POST','/api/v1/components',component())).status,201);
      const changed=s.store.read(); assert.equal((await s.http('POST','/api/v1/components',component())).status,400);
      assert.equal((await s.http('PATCH','/api/v1/components/missing',{x:100})).status,400);
      assert.equal((await s.http('GET','/api/v1/unknown')).status,404);
      assert.equal((await s.http('PUT','/api/v1/components')).status,404); assert.equal(s.store.read(),changed); assert.notEqual(changed,bytes);
      assert.equal((await s.http('GET','/api/v1/guide',undefined,{step:'missing'})).status,404);
      assert.equal((await s.http('GET','/api/v1/guide')).value.next,'model');
    });
    add('mcp-method-errors', async () => {
      const s=setup(); const r=await s.raw('POST','/mcp','{broken'); assert.equal(r.status,400); assert.equal(r.value.error.code,-32700); assert.equal(r.value.id,null);
      const unknown=await s.rpc('not-a-method'); assert.equal(unknown.status,404); assert.equal(unknown.value.error.code,-32601);
      assert.match((await s.tool('not-a-tool',{},false)).error,/Unknown tool/);
      await s.tool('schematic.create',{resource:'unsupported',value:{}},false); assert.equal(s.store.writes,0);
    });
    add('editor-inert-document', async () => {
      const document=blank(); document.meta={title:'</script><script>unexpected()</script>'};
      const html='<html><body>fixture</body></html>', s=setup(JSON.stringify(document),{editorHtml:()=>html,describe:()=>'<qa&".sov'});
      const r=await s.http('GET','/editor'); assert.equal(r.status,200); assert.match(r.body,/id="sov-served-document"/);
      assert.ok(!r.body.includes('</script><script>unexpected()')); assert.match(r.body,/\\u003c\/script>/); assert.match(r.body,/&lt;qa&amp;&quot;\.sov/);
      const embedded=r.body.match(/id="sov-served-document"[^>]*>(.*?)<\/script>/s); assert.deepEqual(JSON.parse(embedded[1]),await s.doc());
      assert.equal((await s.http('GET','/index.html')).body,html);
      assert.equal((await setup().http('GET','/editor')).status,404);
      assert.equal((await setup(seed,{editorHtml:()=>'<html>no body</html>'}).http('GET','/editor')).body,'<html>no body</html>');
    });
    add('root-formats-options', async () => {
      const s=setup(seed,{base:'/d/qa'}); const root=await s.http('GET','/'); assert.equal(root.value.mcp,'/d/qa/mcp'); assert.equal(root.value.editor,'/d/qa/editor');
      const formats=(await s.http('GET','/api/v1/formats')).value; assert.equal(formats.document,Data.DOCUMENT_SCHEMA); assert.ok(formats.resources.includes('component'));
      const optionsResponse=await s.http('OPTIONS','/mcp'); assert.equal(optionsResponse.status,204); assert.equal(optionsResponse.body,''); assert.match(optionsResponse.headers['access-control-allow-methods'],/PATCH/);
    });
    add('persistence-write-failure', async () => {
      const original=seed; const store={read:()=>original,write:()=>{throw new Error('qualification disk failure');}};
      const s=setup(null,{store}); const r=await s.rpc('tools/call',{name:'schematic.apply',arguments:batch()}); assert.equal(r.status,500); assert.match(r.value.error,/qualification disk failure/);
      assert.equal(store.read(),original); assert.ok((await s.doc()).components.some(c=>c.id==='qa-card'), 'failed persistence leaves an in-memory mutation; report failure, never claim durability');
    });

    assert.deepEqual([...cases.keys()], [...CASE_IDS], 'Collection and execution manifests differ');
    for (const id of CASE_IDS) {
      try { await cases.get(id)(); results.push({id,pass:true}); console.log('CASE PASS '+id); }
      catch(error) { results.push({id,pass:false,error:String(error.stack || error)}); console.log('CASE FAIL '+id); }
    }
  } catch(error) { fatal = String(error.stack || error); }
  finally {
    try {
      assert.ok(globalThis.__coverage__ && Object.keys(globalThis.__coverage__).length, 'Instrumented JavaScript coverage was not exported');
      fs.mkdirSync(coverageDir,{recursive:true});
      fs.writeFileSync(path.join(coverageDir, `headless-${process.pid}-${Date.now()}.json`), JSON.stringify(globalThis.__coverage__));
    } catch(error) { fatal = [fatal, 'Coverage export: '+String(error.stack || error)].filter(Boolean).join('\n'); }
    if (temporary) {
      try { fs.rmSync(temporary,{recursive:true,force:true}); }
      catch(error) { fatal = [fatal, 'Temporary cleanup: '+String(error.stack || error)].filter(Boolean).join('\n'); }
    }
  }
  const summary={driver:'headless_local_qa',declared:CASE_IDS.length,executed:results.length,passed:results.filter(r=>r.pass).length,failed:results.filter(r=>!r.pass),elapsedMs:Date.now()-started,fatal:fatal || null};
  console.log(JSON.stringify(summary));
  if(fatal || summary.failed.length || results.length!==CASE_IDS.length) process.exitCode=1;
}
