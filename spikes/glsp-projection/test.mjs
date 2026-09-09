#!/usr/bin/env node
// Plain node assertions for the projection and the routing claim: a legal
// update and a boundary-crossing create both answer through the core's own
// Data.applyOperation receipt, unmodified by anything in this spike.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import WebSocket from 'ws';
import Data, { REPO_ROOT } from './data-core.mjs';
import { projectDocument, findElement } from './adapter.mjs';
import { routeOperation } from './routing.mjs';
import { startServer } from './server.mjs';

const HERE = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));
const FIXTURE = path.join(REPO_ROOT, 'examples/08-gated-service.sov');

function loadFixture() {
  return Data.documentFromFilePayload(JSON.parse(fs.readFileSync(FIXTURE, 'utf8')));
}

let passed = 0;
function check(name, fn) {
  fn();
  passed++;
  console.log(`ok - ${name}`);
}

// 1. Projection counts: 9 nodes, 7 edges, 5 nested, 3 ports.
const doc1 = loadFixture();
const { counts } = projectDocument(doc1);
check('projection counts (9 nodes, 7 edges, 5 nested, 3 ports)', () => {
  assert.deepEqual(counts, { nodes: 9, edges: 7, nested: 5, ports: 3 });
});

// 2. A legal update through the GLSP operation path yields a document
//    deep-equal to Data.applyOperation applied directly.
const docA = loadFixture();
const docB = loadFixture();
const directReceipt = Data.applyOperation(docA, { op: 'update', resource: 'component', resourceId: 'store', patch: { x: 800 } });
const { receipt: routedReceipt } = routeOperation(docB, { kind: 'changeBounds', newBounds: [{ elementId: 'store', newPosition: { x: 800, y: docB.components.find(c => c.id === 'store').y } }] });
check('legal update: routed receipt matches direct Data.applyOperation', () => {
  assert.equal(routedReceipt.ok, true);
  assert.equal(directReceipt.ok, true);
  // meta.updatedAt is a wall-clock stamp Data.touch() sets independently on
  // each call; strip it before the deep-equal since the routed and direct
  // paths run milliseconds apart, not because either mutated the document
  // differently.
  const stripStamp = doc => { const clone = Data.clone(doc); delete clone.meta.updatedAt; return clone; };
  assert.deepEqual(stripStamp(docA), stripStamp(docB));
  assert.deepEqual(routedReceipt.result, directReceipt.result);
});

// 3. A boundary-crossing create returns ok:false carrying the core's reason
//    and leaves the document unchanged.
const docC = loadFixture();
const before = Data.clone(docC);
const { receipt: crossingReceipt } = routeOperation(docC, { kind: 'createEdge', sourceElementId: 'req', targetElementId: 'check' });
check('boundary-crossing create refused with the core\'s own reason, document unchanged', () => {
  assert.equal(crossingReceipt.ok, false);
  assert.equal(crossingReceipt.error.message, 'Boundary blocks implicit reach-through');
  assert.deepEqual(docC, before);
});

// Sanity: a legal create between two components exposed on the same surface
// (req and permit both reach canvas:global -- permit's 'out' port has
// face:'both') succeeds, so the refusal above is about the boundary, not
// about createEdge routing being broken.
const docD = loadFixture();
const { receipt: legalCreateReceipt } = routeOperation(docD, { kind: 'createEdge', sourceElementId: 'grant', targetElementId: 'egress' });
check('legal cross-surface create (exposed on both sides) succeeds', () => {
  assert.equal(legalCreateReceipt.ok, true);
  assert.ok(findElement(projectDocument(docD).gmodel, legalCreateReceipt.result.id));
});

// 4. adapter.mjs and server.mjs contain none of the strings boundary,
//    reachab, locked -- the legality rule stays inside the data core.
check('adapter.mjs and server.mjs decide no boundary/reachability/lock rule', () => {
  for (const file of ['adapter.mjs', 'server.mjs']) {
    const text = fs.readFileSync(path.join(REPO_ROOT, 'spikes/glsp-projection', file), 'utf8').toLowerCase();
    for (const banned of ['boundary', 'reachab', 'locked']) {
      assert.equal(text.includes(banned), false, `${file} contains banned string "${banned}"`);
    }
  }
});

// 5. A real WebSocket round trip through server.mjs's own protocol framing:
//    requestModel -> setModel with the same counts, then the same
//    boundary-crossing createEdge -> setMarkers carrying the core's reason.
async function websocketRoundTrip() {
  const wss = startServer({ port: 0, host: '127.0.0.1' });
  await new Promise(resolve => wss.once('listening', resolve));
  const port = wss.address().port;
  const ws = new WebSocket(`ws://127.0.0.1:${port}`);
  await new Promise((resolve, reject) => { ws.once('open', resolve); ws.once('error', reject); });
  let nextId = 1;
  const pending = new Map();
  const notifications = [];
  const exchange = [];
  ws.on('message', raw => {
    const message = JSON.parse(raw.toString('utf8'));
    exchange.push({ direction: 'server->client', message });
    if (message.id !== undefined && pending.has(message.id)) { pending.get(message.id)(message.result); pending.delete(message.id); return; }
    if (message.method === 'process') notifications.push(message.params.action);
  });
  function request(method, params) {
    const id = nextId++;
    const message = { jsonrpc: '2.0', id, method, params };
    exchange.push({ direction: 'client->server', message });
    return new Promise(resolve => { pending.set(id, resolve); ws.send(JSON.stringify(message)); });
  }
  function notify(method, params) {
    const message = { jsonrpc: '2.0', method, params };
    exchange.push({ direction: 'client->server', message });
    ws.send(JSON.stringify(message));
  }
  function waitForAction() { return new Promise(resolve => { const check = () => { if (notifications.length) resolve(notifications.shift()); else setTimeout(check, 5); }; check(); }); }

  await request('initialize', {});
  await request('initializeClientSession', { clientSessionId: 'test-session' });
  notify('process', { clientId: 'test-session', action: { kind: 'requestModel' } });
  const setModel = await waitForAction();
  assert.equal(setModel.kind, 'setModel');
  assert.deepEqual(setModel.meta.counts, { nodes: 9, edges: 7, nested: 5, ports: 3 });

  notify('process', { clientId: 'test-session', action: { kind: 'createEdge', sourceElementId: 'req', targetElementId: 'check' } });
  const refusal = await waitForAction();
  assert.equal(refusal.kind, 'setMarkers');
  assert.equal(refusal.markers[0].description, 'Boundary blocks implicit reach-through');

  ws.close();
  wss.close();
  fs.writeFileSync(path.join(REPO_ROOT, 'spikes/glsp-projection/evidence/protocol.jsonl'), exchange.map(e => JSON.stringify(e)).join('\n') + '\n');
}
await websocketRoundTrip();
passed++;
console.log('ok - websocket round trip: requestModel and a boundary-crossing createEdge both answer through the wire protocol');

console.log(`\n${passed} checks passed.`);
