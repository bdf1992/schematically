# Performance — 0.1 Beta.24

## Decision

Keep vanilla JavaScript + SVG for the 0.1 public beta. The severe small-diagram lag was a repeated-computation defect rather than evidence that the stack itself must be replaced.

## Current regression measurements

- 5 Components / 4 Wires: warm full render **8.3 ms**, wire-only **9.2 ms**.
- 10 Components / 9 Wires: warm full render **18.0 ms**, wire-only **17.1 ms**.

Measurements are environment-sensitive and are regression guards, not product guarantees.

## Known scaling boundary

The renderer still rebuilds whole SVG projections and all Wires for several mutation paths. Larger diagrams therefore cross the frame budget. The next performance upgrade should be dirty-object/incremental projection before any framework, Canvas2D, or WebGL rewrite is justified.
