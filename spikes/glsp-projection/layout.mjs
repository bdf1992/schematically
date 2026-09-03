#!/usr/bin/env node
// Server-side layout: run the projection through the same ELK engine GLSP's
// @eclipse-glsp/layout-elk wraps (elkjs is its runtime dependency; the GLSP
// module itself is a thin inversify-DI wrapper we don't need to stand up to
// exercise the layout it delegates to). Prints authored .sov positions next
// to ELK's computed ones for 08-gated-service.sov.
import fs from 'node:fs';
import path from 'node:path';
import ELK from 'elkjs';
import Data, { REPO_ROOT } from './data-core.mjs';
import { projectDocument } from './adapter.mjs';

const FILE = path.join(REPO_ROOT, 'examples/08-gated-service.sov');
const document = Data.documentFromFilePayload(JSON.parse(fs.readFileSync(FILE, 'utf8')));
const { gmodel } = projectDocument(document);

function toElkNode(el) {
  if (el.type === 'port') return { id: el.id, width: 8, height: 8 };
  const size = el.size || { width: 112, height: 84 };
  const node = { id: el.id, width: size.width, height: size.height };
  const kids = (el.children || []).filter(c => c.type !== 'port');
  const ports = (el.children || []).filter(c => c.type === 'port').map(toElkNode);
  if (kids.length) node.children = kids.map(toElkNode);
  if (ports.length) node.ports = ports;
  return node;
}

const nodes = gmodel.children.filter(el => el.type !== 'edge').map(toElkNode);
const edges = gmodel.children.filter(el => el.type === 'edge').map(el => ({ id: el.id, sources: [el.sourceId], targets: [el.targetId] }));
const elkGraph = { id: 'root', layoutOptions: { 'elk.algorithm': 'layered' }, children: nodes, edges };

const elk = new ELK();
const laidOut = await elk.layout(elkGraph);

function authoredPosition(id) {
  const component = document.components.find(c => c.id === id);
  return component ? { x: component.x, y: component.y } : null;
}
function collect(nodeList, prefix = '') {
  const rows = [];
  for (const n of nodeList) {
    rows.push({ id: n.id, elk: { x: Math.round(n.x), y: Math.round(n.y) }, authored: authoredPosition(n.id) });
    if (n.children) rows.push(...collect(n.children));
  }
  return rows;
}
const rows = collect(laidOut.children);
console.log('| id | authored x,y | ELK layered x,y |');
console.log('|---|---|---|');
for (const row of rows) {
  console.log(`| ${row.id} | ${row.authored ? `${row.authored.x},${row.authored.y}` : '—'} | ${row.elk.x},${row.elk.y} |`);
}

fs.writeFileSync(path.join(REPO_ROOT, 'spikes/glsp-projection/evidence/elk-layout.json'), JSON.stringify(laidOut, null, 2));
