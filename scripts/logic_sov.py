"""Run a schematic as a logic circuit: gates from a data pack, composites from other documents.

This is a first slice of Issue #6's logic machine, headless, over ordinary `.sov` files.

What a document says:
  - an input:  a Component with `config.logic = {"kind": "input", "name": "A"}`; it drives
    its `out` point;
  - an output: `{"kind": "output", "name": "S"}`; it reads its `in` point;
  - a gate:    `{"gate": "and"}`, a truth table from the pack (packs/logic/gates.json); the
    Component declares one attachment point per pin (`a`, `b`, `q`) and wires address them;
  - a composite: `{"composite": "half-adder.sov"}`, another document used as one part. Its
    inputs and outputs, by name, are the part's pins. Composites nest (a full adder is two
    half adders and an OR; a 4-bit adder is four full adders);
  - a Point is a junction: everything wired to it is one net.

What it does:
  - flattens composites into one circuit, prefixing ids by instance (`fa2.ha1.x`);
  - joins wire ends into nets and requires each net to have exactly one driver: two outputs
    on one net, or an input nobody drives, is refused, not guessed;
  - keeps signal state per net and moves changes as events ordered by (time, sequence), the
    scheduler Issue #6 describes. When an input of a gate changes, the gate reads the current
    state of all its inputs, looks up its table, and schedules any output change one gate
    delay later (per gate: `config.logic.delay`, else the pack's default);
  - reports the settled outputs, the time it took to settle (the circuit's critical path for
    that change) and how many transitions happened, including glitches;
  - refuses a circuit that does not settle within its event budget (an oscillator, or a
    latch released from its forbidden state) and names the nets still changing.

The wire's own direction is not consulted: in a net, pin roles decide who drives.

Usage:
    python scripts/logic_sov.py examples/logic/adder4.sov --set A=13:4,B=9:4,Cin=0
    python scripts/logic_sov.py examples/logic/gates.sov --table            # every input vector
    python scripts/logic_sov.py examples/logic/half-adder.sov --table --json
"""
from __future__ import annotations

import argparse
import heapq
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from optimize_sov import Refusal  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'packs' / 'logic' / 'gates.json'
PACK_SCHEMA = 'soveraeign.schematic/logic-pack@0.0-draft'


# --------------------------------------------------------------------------- the pack

def load_pack(path: Path = PACK) -> dict:
    """Gates as truth tables, checked complete: one row per input combination, no repeats."""
    pack = json.loads(path.read_text(encoding='utf-8'))
    if pack.get('schema') != PACK_SCHEMA:
        raise Refusal('SCHEMA', f'expected {PACK_SCHEMA}, found {pack.get("schema")!r}')
    gates = {}
    for name, g in pack['gates'].items():
        n_in, n_out = len(g['inputs']), len(g['outputs'])
        table = {}
        for row in g['table']:
            ins, _, outs = row.partition(':')
            if len(ins) != n_in or len(outs) != n_out or set(ins + outs) - {'0', '1'}:
                raise Refusal('BAD_ROW', f'gate {name}: row {row!r} does not fit {n_in} inputs and {n_out} outputs')
            if ins in table:
                raise Refusal('DUPLICATE_ROW', f'gate {name}: inputs {ins!r} appear twice')
            table[ins] = tuple(int(b) for b in outs)
        if len(table) != 2 ** n_in:
            raise Refusal('INCOMPLETE_TABLE', f'gate {name}: {len(table)} rows for {n_in} inputs; a table must say '
                          f'what happens for all {2 ** n_in}')
        gates[name] = {'inputs': list(g['inputs']), 'outputs': list(g['outputs']), 'table': table,
                       'delay': int(g.get('delay', pack.get('default_delay', 1)))}
    return gates


# --------------------------------------------------------------------------- flattening

class _Nets:
    """Union-find over terminals (component id, pin)."""

    def __init__(self):
        self.parent: dict[tuple, tuple] = {}

    def find(self, t: tuple) -> tuple:
        self.parent.setdefault(t, t)
        while self.parent[t] != t:
            self.parent[t] = self.parent[self.parent[t]]
            t = self.parent[t]
        return t

    def join(self, a: tuple, b: tuple) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _pins_of_document(doc: dict) -> tuple[list[str], list[str]]:
    ins, outs = [], []
    for c in doc.get('components', []):
        logic = (c.get('config') or {}).get('logic') or {}
        if logic.get('kind') == 'input':
            ins.append(logic['name'])
        elif logic.get('kind') == 'output':
            outs.append(logic['name'])
    return ins, outs


class Circuit:
    """A flattened circuit: nets, gates, named inputs and outputs, and live signal state."""

    def __init__(self, path: Path, pack: dict | None = None, event_budget: int = 200000):
        self.pack = pack or load_pack()
        self.path = path
        self.nets = _Nets()
        self.gates: list[dict] = []           # {id, def, ins: [terminal], outs: [terminal], delay}
        self.inputs: dict[str, tuple] = {}
        self.outputs: dict[str, tuple] = {}
        self.drivers: dict[tuple, list[str]] = {}
        self.event_budget = event_budget
        self._add_document(path, prefix='', stack=(), top=True)
        self._finish()

    # -- building

    def _add_document(self, path: Path, prefix: str, stack: tuple, top: bool) -> dict[str, tuple]:
        """Add one document's parts; returns its named pins as terminals for the parent to join."""
        key = str(path.resolve())
        if key in stack:
            raise Refusal('COMPOSITE_CYCLE', ' -> '.join(Path(s).name for s in (*stack, key)) + ' uses itself')
        if not path.exists():
            raise Refusal('NO_COMPOSITE', f'{path.name} does not exist')
        doc = json.loads(path.read_text(encoding='utf-8'))
        stack = (*stack, key)
        pins: dict[str, tuple] = {}
        points: dict[str, set] = {}
        for c in doc.get('components', []):
            cid, cfg = prefix + c['id'], c.get('config') or {}
            logic = cfg.get('logic')
            declared = {p.get('id') for p in cfg.get('attachmentPoints') or [] if isinstance(p, dict)}
            if c.get('symbolId') == 'point':
                points[cid] = set()
                continue
            if not logic:
                continue
            if logic.get('kind') == 'input':
                pins[logic['name']] = (cid, 'out')
                if top:
                    self.inputs[logic['name']] = (cid, 'out')
                    self.drivers.setdefault((cid, 'out'), []).append(f'input {logic["name"]}')
            elif logic.get('kind') == 'output':
                pins[logic['name']] = (cid, 'in')
                if top:
                    self.outputs[logic['name']] = (cid, 'in')
            elif 'gate' in logic:
                name = logic['gate']
                if name not in self.pack:
                    raise Refusal('UNKNOWN_GATE', f'{cid} names gate {name!r}, which the pack does not define',
                                  f'add {name} to packs/logic/gates.json or use one of: {", ".join(sorted(self.pack))}')
                g = self.pack[name]
                missing = [p for p in g['inputs'] + g['outputs'] if p not in declared]
                if missing:
                    raise Refusal('MISSING_PIN', f'{cid} is a {name} gate but declares no attachment point for '
                                  f'{", ".join(missing)}', f'add config.attachmentPoints with ids {missing}')
                gate = {'id': cid, 'gate': name, 'def': g, 'ins': [(cid, p) for p in g['inputs']],
                        'outs': [(cid, p) for p in g['outputs']], 'delay': int(logic.get('delay', g['delay']))}
                self.gates.append(gate)
                for t in gate['outs']:
                    self.drivers.setdefault(t, []).append(f'{name} {cid}')
            elif 'composite' in logic:
                sub = (path.parent / logic['composite'])
                sub_doc = json.loads(sub.read_text(encoding='utf-8')) if sub.exists() else {}
                ins, outs = _pins_of_document(sub_doc)
                missing = [p for p in ins + outs if p not in declared]
                if sub.exists() and missing:
                    raise Refusal('MISSING_PIN', f'{cid} uses {logic["composite"]} but declares no attachment point '
                                  f'for {", ".join(missing)}', f'add config.attachmentPoints with ids {missing}')
                inner = self._add_document(sub, prefix=cid + '.', stack=stack, top=False)
                for name, terminal in inner.items():
                    # The part's pin and the inner document's input or output node are one net.
                    self.nets.join((cid, name), terminal)
            else:
                raise Refusal('UNKNOWN_LOGIC', f'{cid} has logic {logic!r}; expected kind input/output, gate or composite')
        for w in doc.get('wires', []):
            a = (prefix + w['a'], 'out' if prefix + w['a'] in points else w['aSide'])
            b = (prefix + w['b'], 'out' if prefix + w['b'] in points else w['bSide'])
            self.nets.join(a, b)
        return pins

    def _finish(self) -> None:
        self.net_of: dict[tuple, int] = {}
        roots: dict[tuple, int] = {}
        for t in list(self.nets.parent) + [t for g in self.gates for t in g['ins'] + g['outs']] + \
                list(self.inputs.values()) + list(self.outputs.values()):
            r = self.nets.find(t)
            self.net_of[t] = roots.setdefault(r, len(roots))
        self.n_nets = len(roots)
        self.net_names = {}
        for t, i in sorted(self.net_of.items()):
            self.net_names.setdefault(i, f'{t[0]}.{t[1]}')
        driven: dict[int, list[str]] = {}
        for t, who in self.drivers.items():
            driven.setdefault(self.net_of[t], []).extend(who)
        for net, who in driven.items():
            if len(who) > 1:
                raise Refusal('MULTIPLE_DRIVERS', f'net {self.net_names[net]} is driven by {" and ".join(who)}',
                              'give each output its own net')
        loads = [(g['id'], t) for g in self.gates for t in g['ins']] + [(f'output {n}', t) for n, t in self.outputs.items()]
        for who, t in loads:
            if self.net_of[t] not in driven:
                raise Refusal('UNDRIVEN', f'{who} reads {t[0]}.{t[1]}, which nothing drives',
                              'wire an input, a gate output or a constant (true/false) to it')
        self.fanout: dict[int, list[int]] = {}
        for gi, g in enumerate(self.gates):
            g['in_nets'] = [self.net_of[t] for t in g['ins']]
            g['out_nets'] = [self.net_of[t] for t in g['outs']]
            for n in set(g['in_nets']):
                self.fanout.setdefault(n, []).append(gi)
        self.value = [0] * self.n_nets
        self.time = 0
        self.sequence = 0
        self.started = False
        self.events: list[dict] = []

    # -- running

    def apply(self, vector: dict[str, int], record: bool = False) -> dict:
        """Set inputs, run until nothing changes, return outputs and what it took."""
        for name in vector:
            if name not in self.inputs:
                raise Refusal('UNKNOWN_INPUT', f'{name!r} is not an input of {self.path.name}; inputs are '
                              f'{", ".join(sorted(self.inputs))}')
        queue: list[tuple] = []
        pending: dict[int, int] = {}
        start = self.time

        def schedule(t: int, net: int, value: int, cause: str) -> None:
            self.sequence += 1
            heapq.heappush(queue, (t, self.sequence, net, value, cause))
            pending[net] = value

        for name, v in sorted(vector.items()):
            net = self.net_of[self.inputs[name]]
            if self.value[net] != int(v) or not self.started:
                schedule(self.time, net, int(v), f'input {name}')
        to_eval = set(range(len(self.gates))) if not self.started else set()
        self.started = True
        transitions = 0
        seen = 0
        last_change = start
        toggles: dict[int, int] = {}
        while queue or to_eval:
            if to_eval and (not queue or queue[0][0] > self.time):
                for gi in sorted(to_eval):
                    g = self.gates[gi]
                    key = ''.join(str(self.value[n]) for n in g['in_nets'])
                    for net, out in zip(g['out_nets'], g['def']['table'][key]):
                        if pending.get(net, self.value[net]) != out:
                            schedule(self.time + g['delay'], net, out, g['id'])
                to_eval.clear()
                continue
            t, _, net, value, cause = heapq.heappop(queue)
            self.time = t
            if pending.get(net) == value and all(q[2] != net for q in queue):
                pending.pop(net, None)
            seen += 1
            if seen > self.event_budget:
                busy = sorted((n for n in toggles if toggles[n] > 2), key=lambda n: (-toggles[n], self.net_names[n]))[:6]
                raise Refusal('UNSETTLED', f'{self.path.name} did not settle within {self.event_budget} events; still '
                              f'changing: {", ".join(self.net_names[n] for n in busy)}',
                              'break the feedback loop, or drive a latch out of its forbidden state one input at a time')
            if self.value[net] == value:
                continue
            self.value[net] = value
            transitions += 1
            toggles[net] = toggles.get(net, 0) + 1
            last_change = t
            if record:
                self.events.append({'t': t, 'seq': self.sequence, 'net': self.net_names[net], 'value': value,
                                    'cause': cause})
            to_eval.update(self.fanout.get(net, []))
        outputs = {name: self.value[self.net_of[t]] for name, t in sorted(self.outputs.items())}
        return {'outputs': outputs, 'settle': last_change - start, 'transitions': transitions, 'time': self.time}

    def truth_table(self) -> list[dict]:
        names = sorted(self.inputs)
        rows = []
        for bits in itertools.product((0, 1), repeat=len(names)):
            result = self.apply(dict(zip(names, bits)))
            rows.append({'inputs': dict(zip(names, bits)), **result})
        return rows


# --------------------------------------------------------------------------- buses

def bits(name: str, value: int, width: int) -> dict[str, int]:
    """A number as named bits, least significant first: A=13 over 4 -> A0=1 A1=0 A2=1 A3=1."""
    if not 0 <= value < 2 ** width:
        raise Refusal('OUT_OF_RANGE', f'{name}={value} does not fit in {width} bits')
    return {f'{name}{i}': (value >> i) & 1 for i in range(width)}


def number(outputs: dict[str, int], name: str, width: int) -> int:
    return sum(outputs[f'{name}{i}'] << i for i in range(width))


def parse_vector(text: str) -> dict[str, int]:
    """'A=13:4,B=9:4,Cin=0' -> bits; a value with ':width' is a bus."""
    out: dict[str, int] = {}
    for part in filter(None, text.split(',')):
        name, _, value = part.partition('=')
        value, _, width = value.partition(':')
        if width:
            out.update(bits(name.strip(), int(value), int(width)))
        else:
            out[name.strip()] = int(value)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('document', type=Path)
    ap.add_argument('--set', default=None, help="inputs, e.g. A=13:4,B=9:4,Cin=0 (':width' makes a bus)")
    ap.add_argument('--table', action='store_true', help='run every input vector')
    ap.add_argument('--trace', action='store_true', help='print every signal change')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    try:
        circuit = Circuit(args.document)
        if args.table:
            result = circuit.truth_table()
        else:
            result = circuit.apply(parse_vector(args.set or ''), record=args.trace)
    except Refusal as r:
        print(json.dumps(r.as_dict(), indent=2, sort_keys=True) if args.json else f'refused {r.code}: {r.reason}'
              + (f'\n  next: {r.next_operation}' if r.next_operation else ''), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    print(f'{args.document.name}: {len(circuit.gates)} gates, {circuit.n_nets} nets, inputs {", ".join(sorted(circuit.inputs))}')
    if args.table:
        outs = sorted(circuit.outputs)
        print('  ' + ' '.join(sorted(circuit.inputs)) + ' | ' + ' '.join(outs) + ' | settle')
        for row in result:
            print('  ' + ' '.join(str(row['inputs'][n]).rjust(len(n)) for n in sorted(circuit.inputs)) + ' | '
                  + ' '.join(str(row['outputs'][n]).rjust(len(n)) for n in outs) + f" | {row['settle']}")
    else:
        if args.trace:
            for e in circuit.events:
                print(f"  t={e['t']:<4} {e['net']:<28} -> {e['value']}   ({e['cause']})")
        print('  outputs  ' + ' '.join(f'{k}={v}' for k, v in result['outputs'].items()))
        print(f"  settled after {result['settle']} gate delays, {result['transitions']} transitions")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
