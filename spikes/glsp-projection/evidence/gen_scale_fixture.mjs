// Builds a synthetic .sov at roughly the node/wire count of the
// tests/scale-benchmark-results.json "racks=25" step (252 components, 225
// wires) so step 8 has a real fixture to load through the GLSP client.
// tests/scale-benchmark-results.json and SCALE-GATE.md do not exist on this
// branch (only in an orphaned rescue commit, b8b41dc, outside this contract's
// admissible history -- see REPORT.md); this is a flat topology of plain
// components and wires through the real data core's own factories, not a
// reconstruction of that benchmark's nested rack/spine/server model, and is
// used for a load-time data point only, not a scaling verdict (SCALE-GATE.md
// owns that question).
import fs from 'node:fs';
import path from 'node:path';
import Data, { REPO_ROOT } from '../data-core.mjs';

const N = 252;
const document = Data.documentFromFilePayload({
  schema: 'soveraeign.schematic/document@0.1',
  id: 'scale-fixture',
  components: [],
  wires: []
});
for (let i = 0; i < N; i++) {
  const col = i % 20;
  const row = Math.floor(i / 20);
  Data.applyOperation(document, {
    op: 'create', resource: 'component',
    value: { id: `n${i}`, symbolId: 'act', x: 80 + col * 140, y: 80 + row * 120, config: { label: `n${i}` } }
  });
}
let wireCount = 0;
for (let i = 0; i < N - 1 && wireCount < 225; i++, wireCount++) {
  Data.applyOperation(document, {
    op: 'create', resource: 'wire',
    value: { id: `w${i}`, a: `n${i}`, b: `n${i + 1}` }
  });
}

const out = path.join(REPO_ROOT, 'spikes/glsp-projection/evidence/scale-fixture.sov');
fs.writeFileSync(out, JSON.stringify(document, null, 2));
console.log(`wrote ${out}: ${document.components.length} components, ${document.wires.length} wires`);
