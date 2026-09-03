// Projects a soveraeign.schematic/document@0.1 into a GLSP GModel tree.
// Every GModel id is the schematically id unchanged. No state beyond the
// current document object; this file decides no legality of its own -- that
// stays inside src/05-data-core.js.
'use strict';

const GLOBAL_CANVAS_ID = 'canvas:global';

function isHostedAttachment(component) {
  const placementKind = component?.placement?.kind;
  return component.symbolId === 'point' && (placementKind === 'edge' || placementKind === 'wire' || placementKind === 'path');
}

function sizeOf(component) {
  const size = component?.config?.presentation?.size;
  if (size && Number.isFinite(size.w) && Number.isFinite(size.h)) return { width: size.w, height: size.h };
  return { width: 112, height: 84 };
}

// Counts the projection produces, so test.mjs can assert them without
// re-walking the tree.
function projectDocument(document) {
  const components = document.components || [];
  const wires = document.wires || [];
  const childrenByCanvas = new Map();
  for (const component of components) {
    const canvasId = component.canvasId || GLOBAL_CANVAS_ID;
    if (!childrenByCanvas.has(canvasId)) childrenByCanvas.set(canvasId, []);
    childrenByCanvas.get(canvasId).push(component);
  }
  const childrenOfHost = hostId => childrenByCanvas.get(hostId ? `canvas:component:${hostId}` : GLOBAL_CANVAS_ID) || [];

  let portCount = 0;
  let nestedCount = 0;

  function portFor(component) {
    portCount++;
    nestedCount++;
    return { id: component.id, type: 'port', position: { x: component.x, y: component.y } };
  }

  function nodeFor(component, nested) {
    if (nested) nestedCount++;
    const kids = childrenOfHost(component.id);
    const children = kids.map(kid => (isHostedAttachment(kid) ? portFor(kid) : nodeFor(kid, true)));
    return {
      id: component.id,
      type: `node:${component.symbolId}`,
      position: { x: component.x, y: component.y },
      size: sizeOf(component),
      children
    };
  }

  const topLevel = childrenOfHost(null).filter(component => !isHostedAttachment(component));
  const nodes = topLevel.map(component => nodeFor(component, false));
  const edges = wires.map(wire => ({
    id: wire.id,
    type: 'edge',
    sourceId: wire.a,
    targetId: wire.b
  }));

  const gmodel = {
    id: document.id || 'sov',
    type: 'graph',
    children: [...nodes, ...edges]
  };

  function countNodes(list) {
    let n = 0;
    for (const el of list) {
      if (el.type === 'edge') continue;
      n++;
      if (el.children) n += countNodes(el.children);
    }
    return n;
  }

  return {
    gmodel,
    counts: {
      nodes: countNodes(gmodel.children),
      edges: edges.length,
      nested: nestedCount,
      ports: portCount
    }
  };
}

function findElement(gmodel, id) {
  const stack = [gmodel];
  while (stack.length) {
    const el = stack.pop();
    if (el.id === id) return el;
    if (el.children) stack.push(...el.children);
  }
  return null;
}

export { projectDocument, findElement, isHostedAttachment };
