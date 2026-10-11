// Actual native endpoint qualification, requiring an explicitly supplied disposable fixture.
import fs from 'node:fs';
import path from 'node:path';
const CASE_IDS = ['native-sdk/connect', 'native-sdk/tools', 'native-sdk/docs', 'native-sdk/live-read', 'native-sdk/guarded-edit', 'native-sdk/save-durable'];
if (process.argv.includes('--collect')) {
  console.log(JSON.stringify(CASE_IDS));
} else {
  let token = '';
  let client;
  const results = [];
  try {
    const args = process.argv.slice(2);
    const options = {};
    if (args.length !== 4) throw new Error('Usage: node tests/sdk_consumer.mjs --descriptor PATH --fixture PATH');
    for (let index = 0; index < args.length; index += 2) {
      if (!['--descriptor', '--fixture'].includes(args[index]) || options[args[index]]) throw new Error('Invalid options');
      options[args[index]] = args[index + 1];
    }
    if (!options['--descriptor'] || !options['--fixture']) throw new Error('Descriptor and copied fixture are required');
    const descriptor = JSON.parse(fs.readFileSync(path.resolve(options['--descriptor']), 'utf8'));
    const fixture = path.resolve(options['--fixture']);
    const diskBefore = JSON.parse(fs.readFileSync(fixture, 'utf8'));
    const endpoint = new URL(descriptor.endpoint);
    if (endpoint.protocol !== 'http:' || endpoint.hostname !== '127.0.0.1' || endpoint.pathname !== '/mcp') throw new Error('Descriptor endpoint is not native loopback MCP');
    if (typeof descriptor.token !== 'string' || descriptor.token.length < 32) throw new Error('Descriptor token is missing');
    token = descriptor.token;
    const [{ Client }, { StreamableHTTPClientTransport }] = await Promise.all([
      import('@modelcontextprotocol/sdk/client/index.js'),
      import('@modelcontextprotocol/sdk/client/streamableHttp.js')
    ]);
    client = new Client({ name: 'schematically-qualification', version: '1' }, { capabilities: {} });
    const check = (condition, message) => { if (!condition) throw new Error(message); };
    const passed = id => { results.push({ id, status: 'PASS' }); console.log(`CASE PASS ${id}`); };
    await client.connect(new StreamableHTTPClientTransport(endpoint, {
      requestInit: { headers: { Authorization: `Bearer ${token}` } }
    }));
    passed('native-sdk/connect');
    const tools = await client.listTools();
    check(tools.tools.some(tool => tool.name === 'schematic.file.save'), 'Native save tool absent');
    check(tools.tools.find(tool => tool.name === 'schematic.create')?.inputSchema.required.includes('stateToken'), 'Guard schema missing');
    passed('native-sdk/tools');
    const resources = await client.listResources();
    check(resources.resources.length >= 2, 'Bundled consumer docs missing');
    const docs = await client.readResource({ uri: resources.resources[0].uri });
    check(docs.contents.some(content => typeof content.text === 'string' && content.text.length > 40), 'Consumer docs empty');
    passed('native-sdk/docs');
    async function call(name, args = {}) {
      const result = await client.callTool({ name, arguments: args });
      check(!result.isError, `${name} returned a refusal`);
      return result.structuredContent ?? JSON.parse(result.content.find(item => item.type === 'text').text);
    }
    const info = await call('schematic.file.info');
    const doc = await call('schematic.document.get');
    check(doc.id === diskBefore.id && info.documentId === diskBefore.id, 'Endpoint does not operate the launched fixture');
    check(info.name === path.basename(fixture), 'Active filename differs from supplied copied fixture');
    check(info.revision === doc.revision && typeof info.stateToken === 'string', 'Live identity receipt incomplete');
    passed('native-sdk/live-read');
    const id = `sdk-qualification-${Date.now()}`;
    const receipt = await call('schematic.create', {
      documentId: info.documentId, ifRevision: info.revision, stateToken: info.stateToken,
      resource: 'component', value: { id, symbolId: 'act', x: 900, y: 200, config: { label: id } }
    });
    check(receipt.ok && receipt.revisionAfter > info.revision, 'Mutation receipt incomplete');
    const changed = await call('schematic.document.get');
    check(changed.components.some(component => component.id === id), 'Mutation did not reach active document');
    const dirty = await call('schematic.file.info');
    check(dirty.dirty, 'Mutation not marked unsaved');
    passed('native-sdk/guarded-edit');
    const saved = await call('schematic.file.save', { documentId: dirty.documentId, ifRevision: dirty.revision, stateToken: dirty.stateToken });
    check(saved.mode === 'native', 'Native save did not complete');
    const diskAfter = JSON.parse(fs.readFileSync(fixture, 'utf8'));
    const savedDoc = diskAfter.document ?? diskAfter;
    check(savedDoc.components.some(component => component.id === id), 'Saved disk fixture omits MCP mutation');
    check(!(await call('schematic.file.info')).dirty, 'Successful durable save remains dirty');
    passed('native-sdk/save-durable');
  } catch (error) {
    const message = String(error.message).replaceAll(token || '\u0000', '[redacted]');
    results.push({ id: CASE_IDS[results.length] ?? 'sdk-cleanup', status: 'FAIL', error: message });
    console.error(`CASE FAIL ${results.at(-1).id}: ${message}`);
    process.exitCode = 1;
  } finally {
    if (client) try { await client.close(); } catch { process.exitCode = 1; }
    console.log(JSON.stringify({ suite: 'native-sdk-consumer', collected: CASE_IDS.length, executed: results.length, results }));
  }
}
