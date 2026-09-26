// Translates GLSP operations (@eclipse-glsp/protocol action shapes) into
// Data.applyOperation calls against the current document, then re-projects.
// No rule about boundaries, locks, or reachability is decided here -- every
// receipt is the core's own; this module only carries it back and forth.
import Data from './data-core.mjs';
import { projectDocument } from './adapter.mjs';

// ChangeBoundsOperation: newBounds is [{elementId, newPosition:{x,y}, newSize?}]
// GLSP kind: 'changeBounds'. One bound entry -> one component.update.
function applyChangeBounds(document, operation, ifRevision) {
  const [bound] = operation.newBounds;
  const patch = {};
  if (bound.newPosition) { patch.x = bound.newPosition.x; patch.y = bound.newPosition.y; }
  const receipt = Data.applyOperation(document, {
    id: operation.requestId || `op-${Date.now()}`,
    op: 'update', resource: 'component', resourceId: bound.elementId, patch, ifRevision
  });
  return receipt;
}

// CreateEdgeOperation: {sourceElementId, targetElementId, elementTypeId}
// GLSP kind: 'createEdge'. Ids are minted by the caller from the document's
// own id space (nextWireId), never by GLSP.
function nextWireId(document) {
  let max = 0;
  for (const wire of document.wires || []) {
    const m = String(wire.id || '').match(/^k(\d+)$/);
    if (m) max = Math.max(max, Number(m[1]));
  }
  return `k${max + 1}`;
}
function applyCreateEdge(document, operation, ifRevision) {
  const id = nextWireId(document);
  const receipt = Data.applyOperation(document, {
    id: operation.requestId || `op-${Date.now()}`,
    op: 'create', resource: 'wire',
    value: { id, a: operation.sourceElementId, b: operation.targetElementId },
    ifRevision
  });
  return receipt;
}

// CreateNodeOperation: {elementTypeId, location, containerId}
function nextComponentId(document) {
  let max = 0;
  for (const component of document.components || []) {
    const m = String(component.id || '').match(/^c(\d+)$/);
    if (m) max = Math.max(max, Number(m[1]));
  }
  return `c${max + 1}`;
}
function applyCreateNode(document, operation, ifRevision) {
  const id = nextComponentId(document);
  const symbolId = String(operation.elementTypeId || '').replace(/^node:/, '') || 'blank';
  const value = { id, symbolId, x: operation.location?.x ?? 120, y: operation.location?.y ?? 120 };
  if (operation.containerId) value.canvasId = `canvas:component:${operation.containerId}`;
  const receipt = Data.applyOperation(document, {
    id: operation.requestId || `op-${Date.now()}`,
    op: 'create', resource: 'component', value, ifRevision
  });
  return receipt;
}

// DeleteElementOperation: {elementIds}. One id -> one delete; the projection's
// component/wire distinction is resolved by looking the id up in the document.
function applyDeleteElement(document, operation, ifRevision) {
  const [elementId] = operation.elementIds;
  const resource = (document.wires || []).some(w => w.id === elementId) ? 'wire' : 'component';
  return Data.applyOperation(document, {
    id: operation.requestId || `op-${Date.now()}`,
    op: 'delete', resource, resourceId: elementId, ifRevision
  });
}

// ApplyLabelEditOperation: {labelId, text}. labelId is the schematically
// component id (its label lives at config.label, not a separate GModel label
// element) -- one property edit, per the contract's "one property edit" step.
function applyLabelEdit(document, operation, ifRevision) {
  return Data.applyOperation(document, {
    id: operation.requestId || `op-${Date.now()}`,
    op: 'update', resource: 'component', resourceId: operation.labelId,
    patch: { config: { label: operation.text } }, ifRevision
  });
}

const HANDLERS = {
  changeBounds: applyChangeBounds,
  createEdge: applyCreateEdge,
  createNode: applyCreateNode,
  deleteElement: applyDeleteElement,
  applyLabelEdit: applyLabelEdit
};

// Applies one GLSP operation against `document` (mutated in place, matching
// Data.applyOperation's own contract) and returns {receipt, gmodel, counts}.
// The receipt is exactly what Data.applyOperation returned: this function
// invents no success or failure of its own.
function routeOperation(document, operation, ifRevision) {
  const handler = HANDLERS[operation.kind];
  if (!handler) throw new Error(`Unsupported GLSP operation kind: ${operation.kind}`);
  const receipt = handler(document, operation, ifRevision);
  const { gmodel, counts } = projectDocument(document);
  return { receipt, gmodel, counts };
}

// RequestMarkersAction -> SetMarkersAction.markers, straight from
// Data.validateDocument. No legality is re-derived here.
function markersFor(document, elementIds) {
  const check = Data.validateDocument(document);
  if (check.ok) return [];
  const ids = new Set(elementIds && elementIds.length ? elementIds : null);
  const markers = [];
  for (const error of check.errors) {
    const idMatch = error.match(/^(?:wire|component) ([^:]+):?/);
    const elementId = idMatch ? idMatch[1] : document.id;
    if (ids.size && !ids.has(elementId) && !ids.has(document.id)) continue;
    markers.push({ label: 'Boundary legality', description: error, elementId, kind: 'error' });
  }
  return markers;
}

export { routeOperation, markersFor, nextWireId, nextComponentId };
