# Post-Beta Horizon — Space

**Non-authoritative for 0.1.**

Replace the overloaded root Canvas abstraction with **Space**: the coordinate domain in which dimensional forms live.

- 0D Point: Port-like attachable form; hostable on 1D surfaces or 2D edges.
- 1D Path: line surface; Wires are specialized 1D carriers/materials.
- 2D Surface: plane/sheet/body with edges and optional interior regions.
- 3D Volume: intentionally withheld until Space has XYZ coordinates, depth, camera orbit/projection, spatial hit-testing, faces, and volume semantics.

A Space may admit only part of the grammar (Components, Parts, Wires, Marks, materials, topology, colors, types). An agent can author only within what that Space admits. A 25%-configured Space is therefore a constrained generative environment, not an unconstrained canvas.
