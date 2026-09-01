# File model — 0.1 Beta.24

## File menu

The editor has one File surface. Save/Load/Clear/Export are not independent toolbar modes.

- **New** — creates a new unsaved document; confirms before discarding dirty work.
- **Open…** — accepts `.sov`, `.sovpak`, and legacy schema-tagged `.json`.
- **Save** — writes to the current writable handle when supported; otherwise downloads the current file.
- **Save As…** — selects/creates a new file using the current format.
- **Export SVG…** — presentation export only; it does not become the current editable file.
- **Export Package** — creates a portable `.sovpak`; it does not change the current file identity.
- **Restore Recovery** — restores browser-local recovery and marks the result unsaved.

## `.sov`

The editable source-of-record for one schematic. Semantic document state only.

## `.sovpak`

A portable transparent package:

```text
package
├─ manifest
├─ document        # canonical .sov payload
├─ workspace.view  # optional local presentation state
├─ templates[]
├─ assets[]
└─ meta
```

Beta.24 deliberately keeps the package JSON-readable. Compression can be introduced later as a container encoding without changing these package members.

## Recovery

Recovery is not Save. It is best-effort browser-local state used after interruptions. Browser storage failure must never block normal File Open/Save behavior.
