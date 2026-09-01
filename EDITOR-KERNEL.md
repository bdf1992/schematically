# Editor Kernel — 0.1

The editor kernel is deliberately separate from schematic semantics.

## Primitive utilities

- **History**: debounced semantic snapshots, undo, redo. Pointer-frame noise is not history.
- **Checkpoint**: named persisted version inside a `.sov` document.
- **Selection**: single, Shift multi-select, Shift marquee.
- **Clipboard**: copies selected Component subtrees plus Wires whose endpoints are both inside the copied set.
- **Hosting settle**: containment is established on release with a visible prospective-host ghost.
- **Pin**: geometry cannot move/resize; content/settings remain editable.
- **Lock**: semantic mutation is refused; inspection/copy remain available.
- **Hidden**: removed from canvas hit testing/rendering but retained in Objects.
- **Opacity**: projection only.
- **Search**: blank-canvas typing opens search/command; nonmatches are temporarily desaturated.
- **Objects**: fallback Inspector surface when nothing is selected.
- **Appearance**: Light/Dark/System editor chrome. Authored schematic palette remains document semantics.
- **Rate**: global × source Component × Wire multiplier controls packet travel timing.

## Invariants

1. Contained Components are still ordinary Components. Hosting changes relationship, not implementation.
2. A pointer drag or resize produces one history state, not one state per frame.
3. Lock is stronger than Pin.
4. Hidden is recoverable and is not deletion.
5. Search desaturation never writes opacity/hidden state.
6. Checkpoints persist with the save file; undo/redo stacks are session-local.
