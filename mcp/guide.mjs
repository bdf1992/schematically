// The authoring guide an agent reads through the MCP surface, one step at a time, so it loads only
// what the step in hand needs. The text is the repository's own skills (skills/*/SKILL.md), cut at
// their sections, plus one step written from the data core so it cannot drift from the code.
// Request handling stays free of the file system: the caller passes readText(relativePath).

const AUTHOR='skills/author-offline/SKILL.md';
const STEPS=[
  {step:'model',from:AUTHOR,sections:['Purpose','What a schematic says','Surfaces and ids','The authored form'],says:'what a schematic says: components, wires, surfaces, ids and the stored form'},
  {step:'palette',from:AUTHOR,sections:['Palette','Signals, clocks and access (optional)','Notation, text and narration (optional)'],says:'the symbols, what each means, and signals, notation and narration'},
  {step:'apply',says:'how to write: one batch of creates, updates and deletes with $refs, one receipt'},
  {step:'layout',from:AUTHOR,sections:['Layout rules','Procedure','Anti-patterns'],says:'where things go and the mistakes to avoid'},
  {step:'check',from:AUTHOR,sections:['Checks','Read/write axis','Golden examples'],says:'how to check the result: markers, render, layout metrics, examples'},
  {step:'review',from:'skills/reviewer/SKILL.md',says:'reviewing a schematic for structure, boundaries and format'},
  {step:'layout-review',from:'skills/layout-review/SKILL.md',says:'judging how a schematic presents by looking at it'}
];

function sections(markdown,names){
  const parts=String(markdown).split(/^(?=## )/m),keep=new Set(names);
  return parts.filter(part=>keep.has(part.slice(3).split('\n')[0].trim())).join('\n').trim();
}

function applyStep(symbols){
  return `# Writing with schematic.apply

One call writes many records. Every operation applies in order or none does; the document moves
one revision; one receipt answers the batch. Read before you write: schematic.read with ids or an
area returns the stored form of just that slice.

  schematic.apply {operations: [...], ifRevision?: <revision you read>}

An operation is one of
  {op: "create", resource: "component"|"wire"|"reference", value: {...}, ref?: "$name"}
  {op: "update", resource, id: "<id or $name>", patch: {...}}     deep-merged into the record
  {op: "delete", resource, id: "<id or $name>"}

Leave id out of a create and the core assigns one (c1, k1, r1...). Name it with ref "$name" and use
"$name" anywhere later in the same batch: a wire's a or b, a canvasId, a parentId. The receipt's
result.ids maps each $name to the id it got; result.applied lists every operation with its id.

A refusal changes nothing: error.index names the operation, error.message says why (a locked
record, a wire that crosses a boundary without a facing port, a stale revision). A batch may not
leave the document with a validation error it did not already have.

Example: a source feeding a hold through a gate.
  {"operations": [
    {"op": "create", "resource": "component", "ref": "$src", "value": {"symbolId": "act", "x": 120, "y": 200, "config": {"label": "Source"}}},
    {"op": "create", "resource": "component", "ref": "$gate", "value": {"symbolId": "gate", "x": 360, "y": 200, "config": {"label": "Check"}}},
    {"op": "create", "resource": "component", "ref": "$hold", "value": {"symbolId": "hold", "x": 600, "y": 200, "config": {"label": "Store"}}},
    {"op": "create", "resource": "wire", "value": {"a": "$src", "aSide": "out", "b": "$gate", "bSide": "in"}},
    {"op": "create", "resource": "wire", "value": {"a": "$gate", "aSide": "out", "b": "$hold", "bSide": "in"}}
  ]}

Symbols the core knows: ${symbols.join(', ')}.
After writing: schematic.markers for legality, schematic.render to see it, schematic.layout.metrics
for how it presents, schematic.run.start to run it.`;
}

export function guide(step,{readText,symbols=[]}){
  if(!step){
    return {ok:true,step:null,next:'model',guide:`# Schematically authoring guide

Schematically draws a system as typed components joined by wires, and can run what it draws.
Read one step at a time with schematic.guide {step}; each answer is short. Start with model, then
palette, then apply to write; layout and check before you call it done.

${STEPS.map(s=>`  ${s.step.padEnd(14)}${s.says}`).join('\n')}`};
  }
  const entry=STEPS.find(s=>s.step===step);
  if(!entry)return {ok:false,error:{code:'GUIDE_STEP_UNKNOWN',message:`no step ${step}; steps are ${STEPS.map(s=>s.step).join(', ')}`}};
  const index=STEPS.indexOf(entry),next=STEPS[index+1]?.step||null;
  if(entry.step==='apply')return {ok:true,step,next,guide:applyStep(symbols)};
  const text=readText(entry.from);
  return {ok:true,step,next,source:entry.from,guide:entry.sections?sections(text,entry.sections):text.trim()};
}

export const GUIDE_STEPS=STEPS.map(s=>s.step);
