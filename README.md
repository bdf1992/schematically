# Schematically

A spatial and temporal specification of mechanical requirements that becomes a dynamic runtime with rules.

## Status

**0.1 Beta — repository initialization.** The first release-candidate import is tracked separately from this bootstrap commit. Beta is not final and known defects are expected to be logged and closed through repository issues and pull requests.

## Core grammar

- **Parts compose.**
- **Components contain or occupy a form.**
- **Wires connect and carry.**
- **Marks read the drawing.**
- Direction, access, authority, evidence, and spatial placement are separate semantic axes.

The 0.1 runtime only exposes dimensional forms it can mechanically represent: **0D Point, 1D Path, and 2D Surface**. 3D is intentionally deferred until a later Space model earns XYZ/depth/camera semantics.

## Repository workflow

From the first RC forward:

1. defects and regressions are issues;
2. fixes and features are commits / pull requests;
3. CI owns syntax, golden examples, semantic regression, mutation probes, and performance watchers;
4. release-candidate state is documented explicitly rather than inferred from a ZIP filename.

See the incoming RC documentation for API, MCP, data formats, agent skills, reference examples, QA, and the post-Beta Space horizon.
