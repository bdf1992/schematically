'use strict';
// Entity index — O(1) lookup and O(degree) adjacency over `nodes` / `wires`.
//
// Why this exists: SCALE-GATE.md §2 requires get(id) in O(1) and wires-at-component
// in O(degree). Before this module both were linear scans repeated inside per-node
// loops, which is what made computeSignalState O(passes x N x (N+W)).
//
// Validity model (deliberately conservative for now):
//   Every mutation of `nodes` / `wires`, and every reassignment of an indexed field
//   (id, canvasId, parentId, wire.a, wire.b), calls invalidateModelIndex(). The maps
//   are rebuilt lazily on the next read after an invalidation, once per edit batch —
//   not once per lookup. A length mismatch also forces a rebuild, so a missed
//   invalidation site degrades to correct-but-slow instead of silently wrong.
//
// This satisfies the O(1)/O(degree) read bounds. It does NOT yet satisfy the
// O(affected) write bound in SCALE-GATE.md §2 — a rebuild is O(n) per edit batch.
// Incremental maintenance is the follow-up; correctness first.

let modelIndexEpoch = 0;
let modelIndexBuiltEpoch = -1;
let modelIndexBuiltCounts = {nodes: -1, wires: -1};

const MODEL_INDEX = {
  node: new Map(),        // component id   -> component
  wire: new Map(),        // wire id        -> wire
  wiresAt: new Map(),     // component id   -> [wire, ...]   (either endpoint)
  members: new Map(),     // canvas id      -> [component, ...]
  wireMembers: new Map(), // canvas id      -> [wire, ...]
  children: new Map(),    // parent id      -> [component, ...]
};

function invalidateModelIndex(){ modelIndexEpoch++; }

function pushInto(map, key, value){
  if(key===undefined || key===null) return;
  const bucket = map.get(key);
  if(bucket) bucket.push(value); else map.set(key, [value]);
}

function rebuildModelIndex(){
  const {node, wire, wiresAt, members, wireMembers, children} = MODEL_INDEX;
  node.clear(); wire.clear(); wiresAt.clear(); members.clear(); wireMembers.clear(); children.clear();
  for(const n of nodes){
    node.set(n.id, n);
    pushInto(members, n.canvasId || GLOBAL_CANVAS_ID, n);
    if(n.parentId) pushInto(children, n.parentId, n);
  }
  for(const w of wires){
    wire.set(w.id, w);
    pushInto(wireMembers, w.canvasId || GLOBAL_CANVAS_ID, w);
    pushInto(wiresAt, w.a, w);
    if(w.b !== w.a) pushInto(wiresAt, w.b, w);
  }
  modelIndexBuiltEpoch = modelIndexEpoch;
  modelIndexBuiltCounts = {nodes: nodes.length, wires: wires.length};
}

function modelIndex(){
  if(modelIndexBuiltEpoch !== modelIndexEpoch
     || modelIndexBuiltCounts.nodes !== nodes.length
     || modelIndexBuiltCounts.wires !== wires.length) rebuildModelIndex();
  return MODEL_INDEX;
}

// ---- read API (the shapes the rest of src/ actually asks for) ----

function nodeById(id){ return id==null ? null : (modelIndex().node.get(id) || null) }
function wireById(id){ return id==null ? null : (modelIndex().wire.get(id) || null) }

// Every wire with `componentId` at either endpoint. O(degree).
function wiresAtComponent(componentId){ return modelIndex().wiresAt.get(componentId) || [] }

function nodesOnCanvas(canvasId){ return modelIndex().members.get(canvasId || GLOBAL_CANVAS_ID) || [] }
function wiresOnCanvas(canvasId){ return modelIndex().wireMembers.get(canvasId || GLOBAL_CANVAS_ID) || [] }
function childNodesOf(parentId){ return parentId==null ? [] : (modelIndex().children.get(parentId) || []) }

// Consistency check for the QA gate: the index must agree with the arrays.
function verifyModelIndex(){
  rebuildModelIndex();
  const problems = [];
  if(MODEL_INDEX.node.size !== new Set(nodes.map(n=>n.id)).size) problems.push('duplicate component ids');
  if(MODEL_INDEX.wire.size !== new Set(wires.map(w=>w.id)).size) problems.push('duplicate wire ids');
  for(const n of nodes) if(MODEL_INDEX.node.get(n.id)!==n) problems.push(`component ${n.id} not indexed`);
  for(const w of wires){
    if(MODEL_INDEX.wire.get(w.id)!==w) problems.push(`wire ${w.id} not indexed`);
    if(!wiresAtComponent(w.a).includes(w)) problems.push(`wire ${w.id} missing at endpoint a`);
    if(!wiresAtComponent(w.b).includes(w)) problems.push(`wire ${w.id} missing at endpoint b`);
  }
  return {ok: problems.length===0, problems: problems.slice(0, 20), counts: {
    nodes: nodes.length, wires: wires.length,
    indexedNodes: MODEL_INDEX.node.size, indexedWires: MODEL_INDEX.wire.size,
  }};
}
