#!/usr/bin/env node
// A GLSP 2.8.0 Node server whose model source is examples/08-gated-service.sov
// (or --file), projected through adapter.mjs. Operation handlers translate
// GLSP actions into Data.applyOperation calls (routing.mjs); the document's
// own receipt answers every one of them. Speaks the same JSON-RPC-2.0-over-
// WebSocket wire shape @eclipse-glsp/protocol's JsonrpcGLSPClient uses
// (method 'initialize', 'initializeClientSession', notification 'process'
// carrying {clientId, action}), hand-framed here with the 'ws' package rather
// than vscode-jsonrpc, since nothing in this spike speaks the other side of
// that library.
import { WebSocketServer } from 'ws';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import Data, { REPO_ROOT } from './data-core.mjs';
import { projectDocument } from './adapter.mjs';
import { routeOperation, markersFor } from './routing.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const arg = (name, fallback) => { const i = args.indexOf(name); return i >= 0 && args[i + 1] ? args[i + 1] : fallback; };
const PORT = Number(arg('--port', 8790));
const HOST = arg('--host', '127.0.0.1');
const FILE = path.resolve(arg('--file', path.join(REPO_ROOT, 'examples/08-gated-service.sov')));

let document = Data.documentFromFilePayload(JSON.parse(fs.readFileSync(FILE, 'utf8')));

// Reported to a connecting client as InitializeResult.serverActions['schematic-diagram']:
// GLSPModelSource registers its local ActionDispatcher to forward exactly these action
// kinds to this server (see @eclipse-glsp/client's GLSPModelSource.configureServeActions).
const NODE_TYPES = ['node:authority', 'node:act', 'node:plane', 'node:gate', 'node:hold', 'node:receipt', 'port'];

const HANDLER_KINDS = {
  requestModel: true,
  requestMarkers: true,
  requestTypeHints: true,
  requestContextActions: true,
  changeBounds: true,
  createEdge: true,
  createNode: true,
  deleteElement: true,
  applyLabelEdit: true
};

function currentRevision() { return document.revision; }

function processAction(action) {
  if (action.kind === 'requestModel') {
    const { gmodel, counts } = projectDocument(document);
    return { kind: 'setModel', newRoot: gmodel, meta: { counts, revision: currentRevision() } };
  }
  if (action.kind === 'requestMarkers') {
    return { kind: 'setMarkers', markers: markersFor(document, action.elementsIDs), reason: action.reason || 'batch' };
  }
  // The client's startup sequence requests these two before the model is
  // considered ready. Neither carries a legality decision: type hints just
  // say every projected type is repositionable/deletable (validateDocument,
  // via requestMarkers, is what actually refuses a move or delete), and no
  // context actions (palette items) are offered -- this spike drives GLSP
  // operations directly through the action dispatcher (see client/app.mjs),
  // not through a palette the server would need to populate.
  if (action.kind === 'requestTypeHints') {
    return {
      kind: 'setTypeHints', responseId: action.requestId,
      shapeHints: NODE_TYPES.map(type => ({ elementTypeId: type, repositionable: true, deletable: true, resizable: false, reparentable: false })),
      edgeHints: [{ elementTypeId: 'edge', repositionable: false, deletable: true, routable: false }]
    };
  }
  if (action.kind === 'requestContextActions') {
    return { kind: 'setContextActions', responseId: action.requestId, actions: [] };
  }
  if (['changeBounds', 'createEdge', 'createNode', 'deleteElement', 'applyLabelEdit'].includes(action.kind)) {
    const { receipt, gmodel, counts } = routeOperation(document, action, action.ifRevision);
    if (!receipt.ok) {
      return {
        kind: 'setMarkers',
        markers: [{ label: 'Refused', description: receipt.error.message, elementId: action.elementId || (action.newBounds && action.newBounds[0].elementId) || (action.elementIds && action.elementIds[0]) || document.id, kind: 'error' }],
        reason: 'live',
        receipt
      };
    }
    return { kind: 'setModel', newRoot: gmodel, meta: { counts, revision: currentRevision() }, receipt };
  }
  return { kind: 'setMarkers', markers: [{ label: 'Unsupported', description: `Unsupported action: ${action.kind}`, elementId: document.id, kind: 'error' }] };
}

function respond(ws, id, result) { ws.send(JSON.stringify({ jsonrpc: '2.0', id, result })); }
function notify(ws, method, params) { ws.send(JSON.stringify({ jsonrpc: '2.0', method, params })); }

function startServer({ port = PORT, host = HOST } = {}) {
  const wss = new WebSocketServer({ port, host });
  wss.on('connection', ws => {
    let clientId = null;
    ws.on('message', raw => {
      let message;
      try { message = JSON.parse(raw.toString('utf8')); } catch { return; }
      if (message.method === 'initialize') {
        return respond(ws, message.id, {
          protocolVersion: '2.8.0',
          serverActions: { 'schematic-diagram': Object.keys(HANDLER_KINDS) }
        });
      }
      if (message.method === 'initializeClientSession') {
        clientId = message.params?.clientSessionId || `client-${Date.now()}`;
        return respond(ws, message.id, {});
      }
      if (message.method === 'disposeClientSession') {
        return respond(ws, message.id, {});
      }
      if (message.method === 'process') {
        const { action } = message.params || {};
        if (!action) return;
        const responseAction = processAction(action);
        return notify(ws, 'process', { clientId, action: responseAction });
      }
    });
  });
  return wss;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  startServer();
  console.log(`GLSP projection server listening on ws://${HOST}:${PORT} (model: ${path.relative(REPO_ROOT, FILE)})`);
}

export { processAction, startServer, document, HERE };
