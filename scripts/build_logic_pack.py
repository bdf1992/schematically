"""Write data/logic.gates.pack.json: the gates beyond core.logic, as state space definitions.

State space (STATE-SPACE.md) is the runtime: behaviour is definitions in packs, each an
instance of a pattern. `core.logic` ships NOT, AND, OR and XOR. This pack adds the other
combinational gates and two adders as `truth_table@1` definitions, each table enumerated from
the plain function below, so a table cannot disagree with what the gate is said to do.

Gates with memory or a threshold (flip-flops, latches, the C-element, compare, Schmitt) are
not here: they wait for the patterns that will carry them (`threshold`, slice 2;
`transition`, slice 5). docs/vision/LOGIC-GATES.md keeps their specification for then.

    python scripts/build_logic_pack.py            # write the pack
    python scripts/build_logic_pack.py --check    # exit 1 if the file differs
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'data' / 'logic.gates.pack.json'
PACK_FORMAT = 'soveraeign.schematic/pack@0.1'

# id: (label, inputs, outputs, function of the inputs returning the outputs)
GATES = {
    'logic.buffer': ('BUFFER', ['a'], ['q'], lambda a: (a,)),
    'logic.nand': ('NAND', ['a', 'b'], ['q'], lambda a, b: (1 - (a & b),)),
    'logic.nor': ('NOR', ['a', 'b'], ['q'], lambda a, b: (1 - (a | b),)),
    'logic.xnor': ('XNOR', ['a', 'b'], ['q'], lambda a, b: (1 - (a ^ b),)),
    'logic.imply': ('IMPLY', ['a', 'b'], ['q'], lambda a, b: ((1 - a) | b,)),
    'logic.nimply': ('NIMPLY', ['a', 'b'], ['q'], lambda a, b: (a & (1 - b),)),
    'logic.cimply': ('CIMPLY', ['a', 'b'], ['q'], lambda a, b: (a | (1 - b),)),
    'logic.ncimply': ('NCIMPLY', ['a', 'b'], ['q'], lambda a, b: ((1 - a) & b,)),
    'logic.majority': ('MAJORITY', ['a', 'b', 'c'], ['q'], lambda a, b, c: (int(a + b + c >= 2),)),
    'logic.mux': ('MUX', ['s', 'a', 'b'], ['q'], lambda s, a, b: (b if s else a,)),
    'logic.half_adder': ('HALF ADDER', ['a', 'b'], ['s', 'c'], lambda a, b: ((a + b) & 1, (a + b) >> 1)),
    'logic.full_adder': ('FULL ADDER', ['a', 'b', 'cin'], ['s', 'cout'], lambda a, b, c: ((a + b + c) & 1, (a + b + c) >> 1)),
}


def definition(ident: str) -> dict:
    label, ins, outs, fn = GATES[ident]
    table = [[*bits, *fn(*bits)] for bits in itertools.product((0, 1), repeat=len(ins))]
    return {'id': ident, 'version': 1, 'pattern': 'truth_table@1', 'delay': 0,
            'parameters': {'inputs': ins, 'outputs': outs, 'table': table}, 'projection': {'label': label}}


def text() -> str:
    pack = {'format': PACK_FORMAT, 'id': 'logic.gates', 'version': 1, 'definitions': [definition(i) for i in GATES]}
    return json.dumps(pack, indent=2) + '\n'


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    want = text()
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding='utf-8') != want:
            print(f'stale {TARGET.relative_to(ROOT)}')
            return 1
        return 0
    TARGET.write_text(want, encoding='utf-8', newline='\n')
    print(f'wrote {TARGET.relative_to(ROOT)} ({len(GATES)} definitions)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
