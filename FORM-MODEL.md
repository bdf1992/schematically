# Form model — 0.1

Component Form separates dimensional structure from content and presentation.

```text
Component
├─ content / behavior
├─ Form
│  ├─ dimension: 0 | 1 | 2        # 3 is reserved; the normalizer clamps to 2
│  ├─ Body: kind · material · thickness
│  ├─ Frame: none | frame | shell · thickness · depth
│  └─ Regions
│     └─ interior.state: closed | open
└─ presentation
```

`interior.state = open` means that region may host Components. Existing `canvas.state` is compatibility-only.

Examples: painting = 2D / surface / material=canvas; wire = 1D / path. A 3D enclosure (volume / shell) waits for Space to have real 3D semantics (`HORIZON-SPACE.md`).
