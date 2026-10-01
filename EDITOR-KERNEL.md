# Editor Kernel — 0.1

The editor kernel is deliberately separate from schematic semantics.

## Primitive utilities

- **History**: debounced semantic snapshots, undo, redo. Pointer-frame noise is not history.
- **Checkpoint**: named persisted version inside a `.sov` document.
- **Selection**: single, Shift multi-select, Shift marquee. Pressing a selected member and dragging moves the whole selection as one transition; a press that does not drag selects that member alone.
- **Type**: one list, Point, Path, Plane, then the Component types, the Signals and the active notation's glyphs, each entry carrying its dimension. The palette and the selection bar's type control read the same list. Dimension comes with the type and has no control of its own; the bar badge and the Form section read it out.
- **Clipboard**: copies selected Component subtrees plus Wires whose endpoints are both inside the copied set.
- **Hosting settle**: containment is established on release with a visible prospective-host ghost.
- **Pin**: geometry cannot move/resize; content/settings remain editable.
- **Lock**: semantic mutation is refused; inspection/copy remain available.
- **Hidden**: removed from canvas hit testing/rendering but retained in Objects.
- **Opacity**: projection only.
- **Search**: blank-canvas typing opens search/command; nonmatches are temporarily desaturated.
- **Objects**: fallback Inspector surface when nothing is selected.
- **Appearance**: Light/Dark/System editor chrome. Authored schematic palette remains document semantics.
- **Attached**: a 2D Component's Form section lists what is attached, not a switch over a template rule: every port with the Wires that end on it, then every Point hosted on the boundary, each row selecting its point. "Reset to template ports" is the one control over the template's ports (added ports stay); `config.attachmentDefaults` stays in the file and out of the UI.
- **Component settings**: the Appearance section is tiered by how often a field is reached for. Label, Graphic and Signal come first; Width, Height and Interior next, with the canvas handles as the primary way to size; Material, Thickness and the Frame fields sit behind one disclosure; Text and SVG behind a second, which opens itself when Custom SVG is chosen. Controls are 12px or larger.
- **Rate**: global × source Component × Wire multiplier controls packet travel timing.

## Invariants

1. Contained Components are still ordinary Components. Hosting changes relationship, not implementation.
2. A pointer drag or resize produces one history state, not one state per frame.
3. Lock is stronger than Pin.
4. Hidden is recoverable and is not deletion.
5. Search desaturation never writes opacity/hidden state.
6. Checkpoints persist with the save file; undo/redo stacks are session-local.


### Access axis
Port Connections may carry `access: none | read | write | read-write`. Wire config may carry `forwardOperation` / `reverseOperation: none | read | write`. Direction, access, and authority are independent.
