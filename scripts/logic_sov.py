"""Run a schematic as a logic circuit: gates from a data pack, composites from other documents.

This is a first slice of Issue #6's logic machine, headless, over ordinary `.sov` files.

What a document says:
  - an input:  a Component with `config.logic = {"kind": "input", "name": "A"}`; it drives
    its `out` point. `"type": "level"` makes it carry a number instead of a bit;
  - an output: `{"kind": "output", "name": "S"}`; it reads its `in` point;
  - a gate:    `{"gate": "and"}`, from the pack (packs/logic/gates.json); the Component
    declares one attachment point per pin (`a`, `b`, `q`) and wires address them. Gates come
    in two types. Combinational (`table`, `threshold`, `compare`) outputs depend only on the
    inputs now. Sequential (`sequential`: latches, flip-flops, the C-element; `hysteresis`:
    the Schmitt trigger) hold state and change it by their own rule, on a clock edge or on
    any input change. An instance may set a gate's params (`{"gate": "schmitt", "low": 10,
    "high": 30}`);
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

The wire's own direction is not consulted: in a net, pin roles decide who drives. A level
may feed only a gate built to read one (threshold, compare, hysteresis); into a truth table
or a flip-flop it is refused. At power-on stateful gates show their declared initial state
and constants their value; nothing else is given a default.

Usage:
    python scripts/logic_sov.py examples/logic/adder4.sov --set A=13:4,B=9:4,Cin=0
    python scripts/logic_sov.py examples/logic/gates.sov --table            # every input vector
    python scripts/logic_sov.py examples/logic/half-adder.sov --table --json
    python scripts/logic_sov.py examples/logic/accumulator4.sov --clock CLK --sequence 'X=3:4;X=5:4;X=9:4'
    python scripts/logic_sov.py examples/logic/schmitt.sov --sequence 'X=0.52;X=0.48;X=0.61;X=0.45;X=0.39'
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

KINDS = ('table', 'sequential', 'threshold', 'compare', 'hysteresis')
LEVEL_KINDS = {'threshold', 'compare', 'hysteresis'}      # gates whose inputs may be levels, not bits


def _rows(name: str, rows: list[str], n_key: int, n_val: int, what: str) -> dict[str, tuple]:
    """Parse 'key:value' bit rows; the key may carry a '|' between state and inputs."""
    table = {}
    for row in rows:
        key, _, val = row.partition(':')
        key = key.replace('|', '')
        if len(key) != n_key or len(val) != n_val or set(key + val) - {'0', '1'}:
            raise Refusal('BAD_ROW', f'gate {name}: {what} row {row!r} does not fit {n_key} bits in and {n_val} out')
        if key in table:
            raise Refusal('DUPLICATE_ROW', f'gate {name}: {what} key {key!r} appears twice')
        table[key] = tuple(int(b) for b in val)
    if len(table) != 2 ** n_key:
        raise Refusal('INCOMPLETE_TABLE', f'gate {name}: {len(table)} {what} rows for {n_key} bits; a table must say '
                      f'what happens for all {2 ** n_key}')
    return table


def load_pack(path: Path = PACK) -> dict:
    """Gates by kind, each checked complete.

    table       combinational: outputs are a truth table of the inputs.
    sequential  state bits, a next-state table over (state, inputs) and an output table over
                state. With `clock` and `edge` the state moves only on that clock edge (a
                flip-flop); without, whenever an input changes (a latch, a C-element).
    threshold   q = 1 when the weighted sum of inputs reaches theta. Majority, AND and OR are
                special cases. Inputs may be levels.
    compare     q = 1 when a level x reaches theta.
    hysteresis  a comparator with memory (a Schmitt trigger): q turns on when x reaches high,
                off when x falls to low, and holds in between.
    """
    pack = json.loads(path.read_text(encoding='utf-8'))
    if pack.get('schema') != PACK_SCHEMA:
        raise Refusal('SCHEMA', f'expected {PACK_SCHEMA}, found {pack.get("schema")!r}')
    gates = {}
    for name, g in pack['gates'].items():
        kind = g.get('kind', 'table')
        if kind not in KINDS:
            raise Refusal('UNKNOWN_KIND', f'gate {name}: kind {kind!r}; expected one of {", ".join(KINDS)}')
        ins, outs = list(g['inputs']), list(g['outputs'])
        gate = {'kind': kind, 'inputs': ins, 'outputs': outs, 'params': dict(g.get('params', {})),
                'delay': int(g.get('delay', pack.get('default_delay', 1)))}
        if kind == 'table':
            gate['table'] = _rows(name, g['table'], len(ins), len(outs), 'truth')
        elif kind == 'sequential':
            state = list(g['state'])
            clock = g.get('clock')
            if clock is not None and clock not in ins:
                raise Refusal('BAD_CLOCK', f'gate {name}: clock {clock!r} is not one of its inputs')
            data = [p for p in ins if p != clock]
            gate.update(state=state, clock=clock, edge=g.get('edge', 'rising'), data=data,
                        next=_rows(name, g['next'], len(state) + len(data), len(state), 'next-state'),
                        out=_rows(name, g['output'], len(state), len(outs), 'output'),
                        initial=tuple(int(b) for b in g.get('initial', '0' * len(state))))
        elif kind == 'hysteresis':
            gate['initial'] = (int(g.get('initial', '0')),)
        gates[name] = gate
    return gates


def resolve_params(name: str, gate: dict, logic: dict) -> dict:
    """The pack's defaults, overridden by what an instance declares; checked."""
    params = {**gate['params'], **{k: v for k, v in logic.items() if k in gate['params']}}
    if gate['kind'] == 'threshold' and len(params.get('weights', [])) != len(gate['inputs']):
        raise Refusal('BAD_PARAMS', f'{name}: {len(params.get("weights", []))} weights for {len(gate["inputs"])} inputs')
    if gate['kind'] == 'hysteresis' and not float(params['low']) <= float(params['high']):
        raise Refusal('BAD_PARAMS', f'{name}: low {params["low"]} is above high {params["high"]}; the band would be empty',
                      'set low <= high (equal makes a plain comparator)')
    return params


def resting(g: dict, values: list) -> list[int]:
    """A gate's outputs without moving its state: what a stateful gate shows at power-on."""
    kind = g['def']['kind']
    if kind == 'sequential':
        return list(g['def']['out'][''.join(map(str, g['state']))])
    if kind == 'hysteresis':
        return [g['state'][0], 1 - g['state'][0]]
    return evaluate(g, values)


def evaluate(g: dict, values: list) -> list[int]:
    """A gate's outputs for its current input values; sequential kinds update their state."""
    d, kind = g['def'], g['def']['kind']
    if kind == 'table':
        return list(d['table'][''.join(str(v) for v in values)])
    if kind == 'threshold':
        return [int(sum(w * v for w, v in zip(g['params']['weights'], values)) >= g['params']['theta'])]
    if kind == 'compare':
        return [int(values[0] >= g['params']['theta'])]
    if kind == 'hysteresis':
        x = values[0]
        if x >= g['params']['high']:
            g['state'] = (1,)
        elif x <= g['params']['low']:
            g['state'] = (0,)
        return [g['state'][0], 1 - g['state'][0]]
    # sequential
    named = dict(zip(d['inputs'], values))
    step = True
    if d['clock'] is not None:
        now, before = named[d['clock']], g['prev_clock']
        g['prev_clock'] = now
        step = (before, now) == ((0, 1) if d['edge'] == 'rising' else (1, 0))
    if step:
        key = ''.join(map(str, g['state'])) + ''.join(str(named[p]) for p in d['data'])
        g['state'] = d['next'][key]
    return list(d['out'][''.join(map(str, g['state']))])


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
        self.levels: dict[str, bool] = {}
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
                    self.levels[logic['name']] = logic.get('type', 'bit') == 'level'
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
                        'outs': [(cid, p) for p in g['outputs']], 'delay': int(logic.get('delay', g['delay'])),
                        'params': resolve_params(cid, g, logic), 'state': g.get('initial', ()), 'prev_clock': 0}
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
        # Bits and levels are different things. A level may feed only a gate built to read
        # one (threshold, compare, hysteresis); into a truth table it is refused, not rounded.
        level_nets = {self.net_of[t] for name, t in self.inputs.items() if self.levels.get(name)}
        for g in self.gates:
            if g['def']['kind'] in LEVEL_KINDS:
                continue
            for t in g['ins']:
                if self.net_of[t] in level_nets:
                    raise Refusal('LEVEL_INTO_BINARY', f'{g["id"]} ({g["gate"]}) reads a level on {t[1]}; '
                                  f'{g["gate"]} takes bits', 'put a compare or hysteresis gate between them')
        self.fanout: dict[int, list[int]] = {}
        for gi, g in enumerate(self.gates):
            g['in_nets'] = [self.net_of[t] for t in g['ins']]
            g['out_nets'] = [self.net_of[t] for t in g['outs']]
            for n in set(g['in_nets']):
                self.fanout.setdefault(n, []).append(gi)
        self.value: list = [0] * self.n_nets
        self._power_on()
        self.time = 0
        self.sequence = 0
        self.started = False
        self.events: list[dict] = []

    # -- running

    def _power_on(self) -> None:
        """Show what is declared before anything runs: stateful gates their initial state,
        constants their value.

        Without this every net starts at 0 and the first timed evaluation would read a
        flip-flop's qn rising from 0 to 1 as a clock edge. Nothing else is settled here.
        Feedback made only of combinational gates (two cross-coupled NORs) declares no state,
        so it gets none by default: it meets its first run as it would on a bench, and races
        unless an input forces it.
        """
        for g in self.gates:
            if g['def']['kind'] in ('sequential', 'hysteresis') or not g['in_nets']:
                for net, out in zip(g['out_nets'], resting(g, [self.value[n] for n in g['in_nets']])):
                    self.value[net] = out
        for g in self.gates:
            clock = g['def'].get('clock')
            if clock is not None:
                g['prev_clock'] = self.value[g['in_nets'][g['def']['inputs'].index(clock)]]

    def apply(self, vector: dict[str, int], record: bool = False) -> dict:
        """Set inputs, run until nothing changes, return outputs and what it took."""
        for name, v in vector.items():
            if name not in self.inputs:
                raise Refusal('UNKNOWN_INPUT', f'{name!r} is not an input of {self.path.name}; inputs are '
                              f'{", ".join(sorted(self.inputs))}')
            if not self.levels.get(name) and v not in (0, 1):
                raise Refusal('NOT_A_BIT', f'{name}={v!r}: {name} is a bit input', f'declare {name} "type": "level"')
        queue: list[tuple] = []
        pending: dict[int, int] = {}
        start = self.time

        def schedule(t: int, net: int, value: int, cause: str) -> None:
            self.sequence += 1
            heapq.heappush(queue, (t, self.sequence, net, value, cause))
            pending[net] = value

        for name, v in sorted(vector.items()):
            net = self.net_of[self.inputs[name]]
            v = float(v) if self.levels.get(name) else int(v)
            if self.value[net] != v or not self.started:
                schedule(self.time, net, v, f'input {name}')
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
                    for net, out in zip(g['out_nets'], evaluate(g, [self.value[n] for n in g['in_nets']])):
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

    def pulse(self, clock: str, vector: dict | None = None) -> dict:
        """Set inputs and let them settle, then raise and lower the clock, settling each time."""
        first = self.apply(vector or {})
        rise = self.apply({clock: 1})
        fall = self.apply({clock: 0})
        return {'outputs': fall['outputs'], 'settle': rise['settle'],
                'transitions': first['transitions'] + rise['transitions'] + fall['transitions'], 'time': self.time}

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


def parse_vector(text: str) -> dict:
    """'A=13:4,B=9:4,Cin=0,X=0.62' -> inputs; ':width' makes a bus, a decimal is a level."""
    out: dict = {}
    for part in filter(None, text.split(',')):
        name, _, value = part.partition('=')
        value, _, width = value.partition(':')
        if width:
            out.update(bits(name.strip(), int(value), int(width)))
        else:
            out[name.strip()] = float(value) if '.' in value else int(value)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('document', type=Path)
    ap.add_argument('--set', default=None, help="inputs, e.g. A=13:4,B=9:4,Cin=0 (':width' makes a bus)")
    ap.add_argument('--table', action='store_true', help='run every input vector')
    ap.add_argument('--clock', default=None, help='with --sequence: the clock input to pulse after each step')
    ap.add_argument('--sequence', default=None, help="steps separated by ';', each like --set, e.g. 'X=3:4;X=5:4'")
    ap.add_argument('--trace', action='store_true', help='print every signal change')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    try:
        circuit = Circuit(args.document)
        if args.table:
            result = circuit.truth_table()
        elif args.sequence is not None:
            result = []
            for step in args.sequence.split(';'):
                vector = parse_vector(step.strip())
                r = circuit.pulse(args.clock, vector) if args.clock else circuit.apply(vector)
                result.append({'set': step.strip(), **r})
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
    if args.sequence is not None:
        for r in result:
            print(f"  {r['set']:<24} -> " + ' '.join(f'{k}={v}' for k, v in r['outputs'].items())
                  + f"   ({r['transitions']} transitions)")
        return 0
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
