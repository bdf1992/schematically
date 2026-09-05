# SOV Schematic Beta.24 — Light/Dark Palette Contrast Audit

Tested **432** authored slot realizations across light/dark appearance, 3 themes, 6 palettes, and 12 slots.

| Appearance | Theme | Palette | Floor | Minimum | Maximum | Result |
|---|---|---|---:|---:|---:|---|
| Light | Pastel | Spectrum | 3.25:1 | 3.26:1 | 10.73:1 | PASS |
| Light | Pastel | Cool | 3.25:1 | 3.25:1 | 10.73:1 | PASS |
| Light | Pastel | Warm | 3.25:1 | 3.25:1 | 10.73:1 | PASS |
| Light | Pastel | Earth | 3.25:1 | 3.26:1 | 10.73:1 | PASS |
| Light | Pastel | Mono | 3.25:1 | 3.26:1 | 13.75:1 | PASS |
| Light | Pastel | Custom | 3.25:1 | 3.25:1 | 10.73:1 | PASS |
| Light | Subtle | Spectrum | 3.50:1 | 3.50:1 | 12.10:1 | PASS |
| Light | Subtle | Cool | 3.50:1 | 3.51:1 | 12.10:1 | PASS |
| Light | Subtle | Warm | 3.50:1 | 3.51:1 | 12.10:1 | PASS |
| Light | Subtle | Earth | 3.50:1 | 3.50:1 | 12.10:1 | PASS |
| Light | Subtle | Mono | 3.50:1 | 3.53:1 | 15.05:1 | PASS |
| Light | Subtle | Custom | 3.50:1 | 3.50:1 | 12.10:1 | PASS |
| Light | Reading | Spectrum | 4.00:1 | 4.00:1 | 16.48:1 | PASS |
| Light | Reading | Cool | 4.00:1 | 4.00:1 | 16.48:1 | PASS |
| Light | Reading | Warm | 4.00:1 | 4.00:1 | 16.48:1 | PASS |
| Light | Reading | Earth | 4.00:1 | 4.00:1 | 16.48:1 | PASS |
| Light | Reading | Mono | 4.00:1 | 4.00:1 | 19.44:1 | PASS |
| Light | Reading | Custom | 4.00:1 | 4.00:1 | 16.48:1 | PASS |
| Dark | Pastel | Spectrum | 3.25:1 | 5.86:1 | 15.86:1 | PASS |
| Dark | Pastel | Cool | 3.25:1 | 5.86:1 | 15.86:1 | PASS |
| Dark | Pastel | Warm | 3.25:1 | 5.86:1 | 15.86:1 | PASS |
| Dark | Pastel | Earth | 3.25:1 | 5.86:1 | 15.86:1 | PASS |
| Dark | Pastel | Mono | 3.25:1 | 5.86:1 | 17.63:1 | PASS |
| Dark | Pastel | Custom | 3.25:1 | 4.60:1 | 15.86:1 | PASS |
| Dark | Subtle | Spectrum | 3.50:1 | 5.64:1 | 15.28:1 | PASS |
| Dark | Subtle | Cool | 3.50:1 | 5.64:1 | 15.28:1 | PASS |
| Dark | Subtle | Warm | 3.50:1 | 5.64:1 | 15.28:1 | PASS |
| Dark | Subtle | Earth | 3.50:1 | 5.64:1 | 15.28:1 | PASS |
| Dark | Subtle | Mono | 3.50:1 | 5.64:1 | 16.88:1 | PASS |
| Dark | Subtle | Custom | 3.50:1 | 4.45:1 | 15.28:1 | PASS |
| Dark | Reading | Spectrum | 4.00:1 | 5.68:1 | 16.60:1 | PASS |
| Dark | Reading | Cool | 4.00:1 | 5.68:1 | 16.60:1 | PASS |
| Dark | Reading | Warm | 4.00:1 | 5.68:1 | 16.60:1 | PASS |
| Dark | Reading | Earth | 4.00:1 | 5.68:1 | 16.60:1 | PASS |
| Dark | Reading | Mono | 4.00:1 | 5.68:1 | 18.46:1 | PASS |
| Dark | Reading | Custom | 4.00:1 | 4.38:1 | 16.60:1 | PASS |

**Overall: PASS**

The visible Contrast meter was removed from the editor. Contrast remains an automatic rendering invariant and is release-audited here.

Slot identity is stable across appearance: `M1..M6` and `C1..C6` do not change in saved `.sov` files; only their light/dark realization changes.