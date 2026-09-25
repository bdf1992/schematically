# Logic gates, composites and binary computation

> **Non-authoritative horizon.** A first headless slice of Issue #6's logic machine over ordinary `.sov` files. Nothing here changes the editor, the file format or 0.1.

## What exists

- **`packs/logic/gates.json`** — gates as data. Every gate is a truth table: one row per input combination, `"inputs:outputs"`. The loader refuses a table that is incomplete, malformed or repeats a row.
- **`scripts/logic_sov.py`** — runs a document as a circuit.
- **`scripts/build_logic_examples.py`** — writes `examples/logic/*.sov` deterministically; `--check` fails if a committed example is stale.
- **`tests/logic_sov_qa.py`** — in the static gate.

### The gates

| Gates | Covers |
| --- | --- |
| `false`, `true` | constants (no inputs) |
| `buffer`, `not` | one input |
| `and`, `or`, `xor`, `nand`, `nor`, `xnor`, `imply`, `nimply`, `cimply`, `ncimply` | two inputs |
| `majority`, `mux` | three inputs |
| `half-adder` | two inputs, two outputs, as a primitive to check the composite against |

With each gate's inputs taken from a and b, these cover **all sixteen Boolean functions of two inputs**. The QA derives that from the tables themselves.

## How a document says it

The existing grammar carries all of it:

- **An input** is a Component with `config.logic: {"kind": "input", "name": "A"}`; it drives its `out` point.
- **An output** is `{"kind": "output", "name": "S"}`; it reads its `in` point.
- **A gate** is a `gate` Component with `config.logic: {"gate": "xor"}`. It declares one attachment point per pin, using the existing `config.attachmentPoints` seam, and wires address the pins by id (`"bSide": "a"`).
- **A composite** is a Component with `config.logic: {"composite": "half-adder.sov"}`: another document used as one part. The inner document's input and output names are the part's pins.
- **A Point** is a junction: everything wired to it is one net.

These documents validate in the data core and export to SVG through the ordinary pipeline.

## How it runs

1. **Flatten.** Composites are expanded recursively, ids prefixed by instance (`fa3.ha2.x`). A composite that uses itself, directly or not, is refused (`COMPOSITE_CYCLE`).
2. **Nets.** Wire ends are joined into nets, through Points and across composite pins. Each net needs exactly one driver: two outputs on one net (`MULTIPLE_DRIVERS`), or a gate input nobody drives (`UNDRIVEN`), is refused, never guessed. Pin roles decide who drives, not the wire's drawn direction.
3. **Events.** Signal state is held per net. A change is an event ordered by `(time, sequence)`, Issue #6's scheduler. When a gate's input changes, the gate reads the current state of all its inputs, looks up its table, and schedules each changed output one gate delay later. The delay comes from `config.logic.delay`, else the pack's default of 1.
4. **Settle or refuse.** A run reports:
   - the settled outputs;
   - how long settling took, in gate delays: the critical path for that change;
   - how many transitions happened, glitches included.

   A circuit that keeps changing past its event budget is refused (`UNSETTLED`), naming the nets still toggling.

## What the QA establishes

Each claim is checked against a definition the runtime does not share:

- **Every gate** in the gallery document (`gates.sov`, all 17 on shared inputs A, B, C) matches Python's own operators, for every input vector, in six different vector orders: plain, reversed, Gray code and three random. Combinational outputs do not depend on history.
- **Composites equal their primitives.** The half adder built from XOR and AND equals the pack's `half-adder` table. XOR built from four NANDs equals XOR (NAND is universal). The multiplexer built from NOT, AND and OR equals the `mux` table.
- **Composites compute.**
  - The full adder (two half adders and an OR): S + 2·Cout = A + B + Cin.
  - The 4-bit adder (four full adders; 20 gates once flattened), over all 512 inputs, in two orders.
  - The 8-bit adder (two 4-bit adders) on edge cases and 1,500 random ones.
  - The 4-bit adder/subtractor: SUB = 1 inverts B through XORs and carries in 1, giving A − B mod 16, with Cout = 1 meaning no borrow; all 512 cases.
- **Carry ripples in linear time.** From A = all ones and B = 0, flipping Cin to 1 settles after **8** gate delays in the 4-bit adder and **16** in the 8-bit: two per bit (the second half adder's AND, then the OR).
- **Feedback makes memory.** The cross-coupled NOR latch resets, holds, sets and holds. Driven to S = R = 1 it gives Q = QN = 0. Released from there with both inputs at once, the two NORs race and never settle, and that is refused. So is a fresh latch never reset, and a ring of three NOTs. These are true behaviours of ideal-delay feedback, not solver failures.
- **Mutations are caught.** Flipping one row of XOR's table breaks the sixteen-function coverage. A default delay of 2 breaks the ripple timing. Composites that drop their inner wires are refused as undriven.

## How this meets the rest of the work

- **The completion gate** in `simulate_sov.py` is this pack's `and`, applied to completion signals: a unit exists when every requirement is done. Moving it onto the pack would let a stage declare another rule (k of n, any-of) as a table.
- **Linear vs nonlinear.** Ripple carry is linear in width, in both gates and delay. Carry-lookahead trades more gates for logarithmic delay. Choosing between them under a gate budget and a delay target is the kind of problem `optimize_sov.py` is for, with gate count as a material and delay as time.
- **Saved state.** A circuit's net values are state like a unit's progress. A latch's contents are exactly what a `.sav` would hold.
- **Fingerprints.** `config.logic` is in the semantic fingerprint's allowlist, so changing a gate's kind changes what the document means. The QA checks this.

## Residuals

| Gap | What closes it |
| --- | --- |
| A composite's inner document is not part of the outer document's fingerprint | fingerprint the flattened circuit, or include each composite's fingerprint by path |
| Composites are referenced by file path in `config.logic` | a document-level reference (the `.sov` already has `references`) or a pack-provided template, per Issue #4 |
| Gates draw with the generic `gate` glyph | gate glyphs (AND, OR, NOT shapes) from a domain pack, Issue #4 |
| No unknown (X) value: nets start at 0 | a third state for uninitialized nets, so an unreset latch shows X instead of oscillating |
| Transport delays only; zero-delay wires | inertial delays (glitch filtering) and wire delays from path length and rate |
| Clocked logic | D flip-flop and a clock source, then counters and registers: the sequential half of Issue #6 |
| Buses are naming conventions (`A0`..`A3`) | a bus as a first-class carrier of width n |
| Headless only | the runtime in the data core with editor, API and MCP parity, and live signal state on the canvas (post-RC) |

## Try it

```
python scripts/logic_sov.py examples/logic/gates.sov --table
python scripts/logic_sov.py examples/logic/adder4.sov --set A=13:4,B=9:4,Cin=0
python scripts/logic_sov.py examples/logic/add-sub4.sov --set A=3:4,B=5:4,SUB=1 --trace
python scripts/logic_sov.py examples/logic/sr-latch.sov --set S=0,R=1
python tests/logic_sov_qa.py
```
