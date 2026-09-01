# Form Model · Beta.10

Component Form separates dimensional structure from content and presentation.

```text
Component
├─ content / behavior
├─ Form
│  ├─ dimension: 0 | 1 | 2 | 3
│  ├─ Body: kind · material · thickness
│  ├─ Frame: none | frame | shell · thickness · depth
│  └─ Regions
│     └─ interior.state: closed | open
└─ presentation
```

`interior.state = open` means that region may host Components. Existing `canvas.state` is compatibility-only.

Examples: painting = 2D/surface/material=canvas; wire = 1D/path; enclosure = 3D/volume/shell.
