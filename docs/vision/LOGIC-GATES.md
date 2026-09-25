# Logic gates, composites and binary computation

> **Non-authoritative horizon.** A headless slice of Issue #6's logic machine over ordinary `.sov` files. Nothing here changes the editor, the file format or 0.1.

## What exists

- **`packs/logic/gates.json`** — 26 gates as data, in five kinds. The loader refuses a table that is incomplete, malformed or repeats a row.
- **`scripts/logic_sov.py`** — runs a document as a circuit.
- **`scripts/build_logic_examples.py`** — writes the 17 documents in `examples/logic/` deterministically; `--check` fails if a committed one is stale.
- **`tests/logic_sov_qa.py`** — in the static gate.

## Two types of gate

A **combinational** gate's outputs depend only on its inputs now. A **sequential** gate holds state and changes it by its own rule. Its outputs depend on what happened before, which is what makes memory, counting and hysteresis possible.

| Type | Kind | What decides the output | Gates in the pack |
| --- | --- | --- | --- |
| combinational | `table` | a truth table of the inputs | `false` `true` `buffer` `not` `and` `or` `xor` `nand` `nor` `xnor` `imply` `nimply` `cimply` `ncimply` `majority` `mux` `half-adder` |
| combinational | `threshold` | weighted sum of the inputs ≥ θ | `threshold` (defaults make majority; θ = 1 makes OR, θ = 3 AND) |
| combinational | `compare` | a level x ≥ θ | `compare` |
| sequential | `sequential`, clocked | a next-state table, applied only on a clock edge | `dff` (D), `tff` (toggle), `jkff` (JK) flip-flops |
| sequential | `sequential`, level | a next-state table, applied on any input change | `sr-latch`, `d-latch`, `c-element` |
| sequential | `hysteresis` | a level crossing a band: on at `high`, off at `low`, hold between | `schmitt` |

- The ten named two-input tables, with `buffer`, `not`, `true` and `false`, cover **all sixteen Boolean functions of two inputs**. The QA derives this from the tables.
- A sequential gate's table is keyed `"state|inputs"`, clock excluded; a separate output table maps state to outputs. Clocked gates declare their `clock` pin and `edge` (`rising` or `falling`).
- **Params** (threshold weights and θ, compare θ, hysteresis low and high) are defaults an instance overrides in its own `config.logic`. For example, `{"gate": "schmitt", "low": 10, "high": 30}`. Bad params are refused: low above high, or the wrong number of weights.

### Hysteresis is a threshold with memory

A comparator answers "is x above θ right now?". If x is noisy near θ, the answer flips on every wobble: chatter. A Schmitt trigger has two thresholds and one bit of state. It turns on only when x reaches `high`, turns off only when x falls to `low`, and holds in between. Noise smaller than the band cannot flip it.

The QA drives both with a slow swing plus noise: the comparator flips more than four times as often, while the Schmitt trigger flips once per real crossing and matches its definition at every step. This is the same shape as a reorder rule (`reorder.sov`): order when stock falls to 10, stop at 30, and do not dither in between.

### Bits and levels

Nets carry either bits or **levels**: an input declared `"type": "level"` carries a number. A level may feed only a gate built to read one (`threshold`, `compare`, `hysteresis`). Into a truth table or a flip-flop it is refused (`LEVEL_INTO_BINARY`), with the next operation "put a compare or hysteresis gate between them". A non-bit value on a bit input is refused (`NOT_A_BIT`). Crossing from a level to a bit is always a visible gate, never a silent rounding.

### Power-on

Stateful gates start in their declared `initial` state, and constants show their value, before anything runs. Without that, every net would start at 0 and a flip-flop's `qn` rising to 1 at power-on would look like a clock edge to the next stage; the first version of the ripple counter jumped straight to 15 for exactly this reason. **Nothing else gets a default.** Feedback made only of combinational gates, like two cross-coupled NORs, declares no state, so it races on its first run unless an input forces it. An early version settled it silently, in whatever order the gates were listed; that is the kind of default rule R-02 refuses.

## Gates interacting and adding

Composites are documents used as parts, and they nest. The ones that add, from bottom to top:

| Document | Built from | Checked |
| --- | --- | --- |
| `half-adder.sov` | XOR, AND | equals the pack's `half-adder` table |
| `full-adder.sov` | two half adders, OR | S + 2·Cout = A + B + Cin |
| `adder4.sov` | four full adders (20 gates flattened) | all 512 inputs, two orders |
| `adder8.sov` | two 4-bit adders | edge cases and 1,500 random |
| `add-sub4.sov` | 4 XORs + `adder4` | A − B mod 16, Cout = no borrow, all 512 |
| `register4.sov` | four D flip-flops on one clock | never changes without an edge; loads on one |
| `accumulator4.sov` | `adder4` + `register4` + a constant, the sum fed back | 200 random steps: ACC is the running sum mod 16, Carry says whether this step wraps |
| `sync-counter4.sov` | `accumulator4` with X held at 1 | counts 1 … 15, 0, 1 … over 40 pulses |
| `ripple-counter4.sov` | four T flip-flops, each clocked by the last one's `qn` | counts the same |

The accumulator is where the two types meet. The adder is combinational and the register sequential; the register's output feeds the adder, and the adder's output feeds the register. The loop is stable because the register moves only on a clock edge, so every clock adds X once.

**Ripple versus synchronous** shows why that matters. Both counters count correctly, but their outputs get there differently:
- **Ripple counter:** each bit is clocked by the bit before it. Going from 7 to 8 its outputs change one after another and pass through **6, 4 and 0** first. The QA requires four distinct change times at 7 → 8 and 15 → 0.
- **Synchronous counter:** all bits share one clock, so its outputs change at the same instant. The QA requires one change time.

Anything that reads the ripple counter mid-change reads a wrong number.

Also checked:
- XOR from four NANDs equals XOR, since NAND is universal.
- The multiplexer built from gates equals the `mux` primitive.
- The window comparator (two comparators and NIMPLY, with thresholds set per instance) gives 0.3 ≤ x < 0.7.
- Every gate matches Python's operators in six input orders.
- Every sequential gate matches a textbook reference model over 400 random single-input changes.
- Random weighted threshold gates on levels match the weighted sum.
- Carry ripple is linear in time: 8 gate delays at 4 bits, 16 at 8.
- The NOR latch sets, resets, holds, and races when released from S = R = 1; so does a ring of three NOTs, and both are refused.

Mutations are caught:
- a flipped XOR row;
- a gate delay of 2;
- composites that drop their inner wires;
- hysteresis without memory;
- flip-flops on the falling edge;
- power-on switched off.

## Completion, again

`completion.sov` puts the simulator's completion gate beside the C-element on the same two signals, MATERIALS and WORK:

- **AND** says "both are done *now*". It drops the moment either resets.
- **The C-element** says "both have finished". It rises when both are 1, then holds until both have gone back to 0.

That is the completion detector of asynchronous (self-timed) circuits. It is the right gate when "done" has to survive one side being cleared for the next unit before the other has caught up.

## Other complex gates worth having

Grouped by type. **Bold** marks the ones that would fit this project soonest.

**Combinational**
- **Decoder / demultiplexer** (n bits → one of 2ⁿ lines) and **encoder / priority encoder** (which request wins). A priority encoder is what the simulator's fixed "nearest the market first" dispatch rule is.
- **Magnitude comparator** (A < B, A = B, A > B over buses) and **parity** (XOR tree).
- **Lookup table (LUT)**: any n-input function as data. This is what the `table` kind already is; FPGAs are built from them.
- ALU (add, subtract, AND, OR by an opcode); barrel shifter.
- **Carry-lookahead adder**: more gates, logarithmic delay instead of linear. The natural first optimization target (below).

**Sequential**
- **Shift register**, and counters with **enable, load and reset**: the working parts of registers and timers.
- **Generic finite-state machine**: Moore and Mealy tables with named states. The `sequential` kind is one step from this.
- **Edge detector / one-shot (monostable)**: a pulse of fixed width on a rising edge.
- **Debouncer**: ignore changes shorter than a hold time. Hysteresis in time, where the Schmitt trigger is hysteresis in level.
- **Timer / watchdog**, clock divider, rate limiter.
- **Arbiter / mutex**: grants one of two simultaneous requests and never both. The honest answer to two stages wanting the same input at once, a residual in `WHOLE-UNITS-AND-STATE.md`.
- **Muller C-element with more inputs**, and asymmetric C-elements: the family around completion.

**Level and multi-valued**
- **Window comparator** (built here as a composite), dead-band, clamp, quantizer (level → n bits, an ADC).
- **Three-valued logic with X (unknown)**: Kleene AND and OR. This removes the NOR latch's power-on race by saying "unknown" instead of oscillating, and lets a tri-state bus say "nobody is driving" instead of refusing.
- **Tri-state buffer and wired-AND (open-drain)**: legal ways for several outputs to share a net, where today that is refused as `MULTIPLE_DRIVERS`.
- Fuzzy gates (AND = min, OR = max) and stochastic gates, for when truth is a degree or a probability.

**Recommended next, in order:**
1. **Three-valued X**, because it removes a class of false races.
2. **Edge detector, one-shot and debouncer**, because they finish the time-domain family that hysteresis started.
3. **Generic finite-state machine**.
4. **Arbiter**, because it closes the simulator's contention residual.
5. **Carry-lookahead**, as the first gate-count-against-delay optimization problem for `optimize_sov.py`.

## How this meets the rest of the work

- **Completion** (above): the simulator's AND over completions, and the C-element when completion has to hold through a reset.
- **Linear vs nonlinear.** Ripple carry is linear in width, in gates and in delay. Carry-lookahead trades more gates for logarithmic delay. Choosing between them under a gate budget and a delay target is an `optimize_sov.py` problem, with gates as material and delay as time.
- **Saved state.** Flip-flop and Schmitt states are exactly what a `.sav` should hold for a circuit.
- **Fingerprints.** `config.logic`, params included, is in the semantic fingerprint's allowlist, so retuning a Schmitt band or swapping a gate changes what the document means.

## Residuals

| Gap | What closes it |
| --- | --- |
| A composite's inner document is not part of the outer document's fingerprint | fingerprint the flattened circuit, or include each composite's fingerprint by path |
| Composites are referenced by file path in `config.logic` | a document-level reference (the `.sov` already has `references`) or a pack template, per Issue #4 |
| Gates draw with the generic `gate` glyph | gate glyphs (AND, OR, NOT, flip-flop shapes) from a domain pack, Issue #4 |
| No X value | three-valued logic, above |
| A clock produced by combinational logic can see a power-on edge | X, or power-on settling of combinational paths that declare it |
| Transport delays only; no setup or hold time; zero-delay wires | inertial delays, setup/hold checks on flip-flops, wire delays from path length and rate |
| Circuit state is not saved | a `.sav` for circuits: flip-flop and Schmitt state, net values, time |
| Buses are naming conventions (`A0`..`A3`) | a bus as a first-class carrier of width n |
| Headless only | the runtime in the data core with editor, API and MCP parity, and live signal state on the canvas (post-RC) |

## Try it

```
python scripts/logic_sov.py examples/logic/gates.sov --table
python scripts/logic_sov.py examples/logic/adder4.sov --set A=13:4,B=9:4,Cin=0
python scripts/logic_sov.py examples/logic/accumulator4.sov --clock CLK --sequence 'X=3:4;X=5:4;X=9:4;X=15:4'
python scripts/logic_sov.py examples/logic/ripple-counter4.sov --clock CLK --sequence ';;;;;;;;'
python scripts/logic_sov.py examples/logic/schmitt.sov --sequence 'X=0.52;X=0.48;X=0.61;X=0.45;X=0.39'
python scripts/logic_sov.py examples/logic/completion.sov --sequence 'MATERIALS=1;WORK=1;MATERIALS=0;WORK=0'
python tests/logic_sov_qa.py
```
