"""Build whole units through a schematic, one at a time, and save where the work stands.

The optimizer answers how much, over a horizon, as quantities. This answers what actually
gets finished: each unit (a blank, a chair) is a discrete thing with progress, and it counts
only once it is complete. Nothing fractional is ever counted.

A unit in progress holds one progress signal per requirement:

  - materials: for each wire into the stage, how much of `per` has arrived (0..1);
  - work: for each resource the stage uses, how much of this unit's time is done (0..1).

The completion gate reads those signals as binary completions, each either done (1) or not
(0), and fires only when every one is done: an AND over completions. Firing emits one unit.
The unit moves to the next stage's stock, or, when its wires lead to a sink, it is counted
there. The gate is the only place a unit comes into existence, so counts are whole numbers.

Work on a unit starts once its materials are all in. Its time is the step the declared curve
takes for that unit: the n-th chair of a horizon takes use * (f(n) - f(n-1)) hours, so a
learning curve makes later chairs quicker and a congested saw makes later blanks slower,
and the units of a horizon add up to exactly what the optimizer's true curve says.

One worker, so the clock is the work done. Stages are served nearest the market first: a
stage that can take materials or do work does, else the next one upstream. Each step is an
event ordered by (time, sequence), the scheduler Issue #6 describes.

State lives in a `.sav` (soveraeign.schematic/state@0.0-draft), never in the `.sov`: the
document stays authored truth. A `.sav` points at the document and model it belongs to by a
semantic fingerprint (scripts/sov_fingerprint.py), and is refused against any document or
model that differs in meaning; layout and label edits keep it. Loading one and running the next
horizon gives the same state as running both horizons without stopping.

Usage:
    python scripts/simulate_sov.py examples/optimization/workshop.sov                   # one horizon, to the plan
    python scripts/simulate_sov.py examples/optimization/workshop.sov --out week1.sav
    python scripts/simulate_sov.py examples/optimization/workshop.sov --sav week1.sav --out week2.sav
    python scripts/simulate_sov.py a.sov --target chairs=14,tables=2 --horizons 2 --json
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from optimize_sov import Refusal, curve, solve  # noqa: E402
from sov_fingerprint import document_fingerprint, model_fingerprint  # noqa: E402

STATE_SCHEMA = 'soveraeign.schematic/state@0.0-draft'
EPS = 1e-9




class Workshop:
    """The document's topology with the model's quantities, read once."""

    def __init__(self, doc_path: Path, model_path: Path | None = None):
        self.doc_path = doc_path
        self.model_path = model_path or doc_path.with_suffix('.opt.json')
        if not self.model_path.exists():
            raise Refusal('NO_MODEL', f'{self.model_path.name} does not exist; the document holds no quantities')
        self.doc = json.loads(doc_path.read_text(encoding='utf-8'))
        self.model = json.loads(self.model_path.read_text(encoding='utf-8'))
        comps = {c['id']: c for c in self.doc.get('components', [])}
        self.relays = {cid for cid, c in comps.items() if c.get('symbolId') == 'point'}
        self.wires = [{'id': w['id'], 'a': w['a'], 'b': w['b']} for w in self.doc.get('wires', [])]
        spec = self.model.get('stages', {})
        self.role = {cid: spec.get(cid, {}).get('role', 'stage') for cid in spec}
        self.sources = [c for c, r in self.role.items() if r == 'source']
        self.sinks = {c for c, r in self.role.items() if r == 'sink'}
        self.stages = [c for c, r in self.role.items() if r == 'stage']
        self.spec = spec
        # Where a wire's material really comes from, and where a stage's output really goes,
        # looking through boundary Points.
        self.inputs = {s: [(w['id'], self._provider(w), self._per(w)) for w in self.wires if w['b'] == s]
                       for s in self.stages}
        self.delivers = {s: self._sink_wire(s) for s in self.stages}
        for s, ins in self.inputs.items():
            for wid, provider, per in ins:
                if provider in self.stages and abs(per - round(per)) > EPS:
                    raise Refusal('FRACTIONAL_RECIPE', f'{s} takes {per} units from {provider} per unit on {wid}; '
                                  'a unit made upstream cannot be split', f'make flows.{wid}.per whole')
        self.order = sorted(self.stages, key=lambda s: (self._depth(s), s))

    def _per(self, w: dict) -> float:
        per = self.model.get('flows', {}).get(w['id'], {}).get('per')
        if per is None:
            raise Refusal('NO_RECIPE', f'wire {w["id"]} feeds a stage but declares no per-unit amount')
        return float(per)

    def _provider(self, w: dict) -> str:
        seen = set()
        while w['a'] in self.relays and w['a'] not in seen:
            seen.add(w['a'])
            back = [x for x in self.wires if x['b'] == w['a']]
            if not back:
                raise Refusal('FREE_END', f'nothing feeds {w["a"]}')
            w = back[0]
        return w['a']

    def _sink_wire(self, stage: str) -> str | None:
        """The wire into a sink that this stage's output reaches through relays, if any."""
        for w in self.wires:
            if w['a'] != stage:
                continue
            seen = set()
            while w['b'] in self.relays and w['b'] not in seen:
                seen.add(w['b'])
                nxt = [x for x in self.wires if x['a'] == w['b']]
                if not nxt:
                    break
                w = nxt[0]
            if w['b'] in self.sinks:
                return w['id']
        return None

    def _depth(self, stage: str, seen: frozenset = frozenset()) -> int:
        """Stages between this one and the market: 0 for a stage that sells directly."""
        if self.delivers[stage] or stage in seen:
            return 0
        consumers = [s for s in self.stages if any(p == stage for _, p, _ in self.inputs[s])]
        return 1 + min((self._depth(c, seen | {stage}) for c in consumers), default=0)

    def unit_work(self, stage: str, n: int) -> dict[str, float]:
        """Resource time for the n-th unit of a horizon: the declared curve's n-th step."""
        spec = self.spec[stage]
        out = {}
        for rname, use in spec.get('uses', {}).items():
            fn, _ = curve(spec.get('effects', {}).get(rname), spec.get('capacity'))
            out[rname] = float(use) * (fn(n) - fn(n - 1))
        return out


def new_state(ws: Workshop) -> dict:
    return {
        'schema': STATE_SCHEMA,
        'document': {'id': ws.doc.get('id'), 'revision': ws.doc.get('revision'), 'path': ws.doc_path.name,
                     'fingerprint': document_fingerprint(ws.doc)},
        'model': {'path': ws.model_path.name, 'fingerprint': model_fingerprint(ws.model)},
        'clock': {'time': 0.0, 'sequence': 0, 'horizon': 0},
        'sources': {s: 0.0 for s in ws.sources},
        'stages': {s: {'stock': 0, 'completed': 0, 'horizon_completed': 0, 'wip': None} for s in ws.stages},
        'counts': {w: 0 for w in sorted({ws.delivers[s] for s in ws.stages if ws.delivers[s]})},
        'resources': {r: {'used': 0.0, 'limit': float(v['limit'])} for r, v in ws.model.get('resources', {}).items()},
        'events': [],
    }


def load_state(ws: Workshop, path: Path) -> dict:
    state = json.loads(path.read_text(encoding='utf-8'))
    if state.get('schema') != STATE_SCHEMA:
        raise Refusal('SCHEMA', f'expected {STATE_SCHEMA}, found {state.get("schema")!r}')
    # Pinned by meaning, not bytes (scripts/sov_fingerprint.py): moving or relabelling a
    # component keeps a save; changing what exists, connects or flows refuses it.
    if state['document'].get('fingerprint') != document_fingerprint(ws.doc):
        raise Refusal('DOCUMENT_CHANGED', f'{path.name} was saved against a structurally different {ws.doc_path.name}',
                      'run from the document the save names, or start a new save')
    if state['model'].get('fingerprint') != model_fingerprint(ws.model):
        raise Refusal('MODEL_CHANGED', f'{path.name} was saved against different quantities in {ws.model_path.name}',
                      'run from the model the save names, or start a new save')
    return state


def dump_state(state: dict) -> str:
    return json.dumps(state, indent=2, sort_keys=True) + '\n'


def plan_targets(ws: Workshop, segments: int = 32) -> dict[str, int]:
    """Units per stage for one horizon, from the optimizer's whole-unit plan.

    Stages the model holds to whole units come out whole already; any other stage is rounded
    up, so a downstream stage is never starved by a fraction.
    """
    result = solve(ws.doc, ws.model, segments=segments, marginals=False)
    return {s: int(math.ceil(v - 1e-6)) for s, v in result['plan']['activity'].items()}


def run_horizon(ws: Workshop, state: dict, targets: dict[str, int]) -> dict:
    """Advance one horizon: budgets and supplies refresh; work in progress carries over."""
    clock = state['clock']

    def emit(kind: str, **fields) -> dict:
        clock['sequence'] += 1
        event = {'t': round(clock['time'], 9), 'seq': clock['sequence'], 'horizon': clock['horizon'],
                 'kind': kind, **fields}
        state['events'].append(event)
        return event

    clock['horizon'] += 1
    for r in state['resources'].values():
        r['used'] = 0.0
    for s in ws.stages:
        state['stages'][s]['horizon_completed'] = 0
    for src in ws.sources:
        state['sources'][src] += float(ws.spec[src]['supply'])
    emit('horizon', targets=dict(sorted(targets.items())),
         supply={src: ws.spec[src]['supply'] for src in ws.sources})
    remaining = dict(targets)

    def available(provider: str) -> float:
        if provider in state['sources']:
            return state['sources'][provider]
        return float(state['stages'][provider]['stock'])

    def take(provider: str, amount: float) -> None:
        if provider in state['sources']:
            state['sources'][provider] -= amount
        else:
            state['stages'][provider]['stock'] -= int(round(amount))

    def step() -> bool:
        """One action at the stage nearest the market that can act. False when none can."""
        for s in ws.order:
            st = state['stages'][s]
            if st['wip'] is None and remaining.get(s, 0) <= 0:
                continue
            if st['wip'] is None and any(state['resources'][r]['used'] >= state['resources'][r]['limit'] - EPS
                                         for r in ws.spec[s].get('uses', {})):
                # A new unit is opened only while its stage can still work on it; materials
                # are not drawn into a unit nobody has time to make.
                continue
            wip = st['wip'] or {'materials': {wid: 0.0 for wid, _, _ in ws.inputs[s]}, 'work': None}
            # Materials: pull what is available toward each input's per-unit amount.
            pulled = False
            for wid, provider, per in ws.inputs[s]:
                need = per - wip['materials'][wid]
                if need <= EPS:
                    continue
                have = available(provider)
                amount = min(need, have) if provider in state['sources'] else float(min(int(round(need)), int(have)))
                if amount > EPS:
                    take(provider, amount)
                    wip['materials'][wid] += amount
                    pulled = True
                    emit('material', stage=s, wire=wid, amount=round(amount, 9),
                         progress=round(wip['materials'][wid] / per, 9))
            if pulled and st['wip'] is None:
                st['wip'] = wip
            kitted = all(wip['materials'][wid] >= per - EPS for wid, _, per in ws.inputs[s])
            if not kitted:
                if pulled:
                    return True
                continue
            if st['wip'] is None:
                st['wip'] = wip
            if wip['work'] is None:
                n = st['horizon_completed'] + 1
                wip['work'] = {r: {'done': 0.0, 'need': need} for r, need in ws.unit_work(s, n).items()}
                emit('start', stage=s, unit=st['completed'] + 1, index=n,
                     need={r: round(w['need'], 9) for r, w in wip['work'].items()})
            worked = False
            for rname, w in wip['work'].items():
                left = w['need'] - w['done']
                if left <= EPS:
                    continue
                budget = state['resources'][rname]
                amount = min(left, budget['limit'] - budget['used'])
                if amount > EPS:
                    w['done'] += amount
                    budget['used'] += amount
                    clock['time'] += amount
                    worked = True
            # The completion gate: every requirement is a binary completion, and the gate
            # fires on all of them (AND). Partial progress is state, never a count.
            signals = {f'material:{wid}': int(wip['materials'][wid] >= per - EPS) for wid, _, per in ws.inputs[s]}
            signals.update({f'work:{r}': int(w['done'] >= w['need'] - EPS) for r, w in wip['work'].items()})
            if all(signals.values()):
                st['wip'] = None
                st['completed'] += 1
                st['horizon_completed'] += 1
                remaining[s] = remaining.get(s, 0) - 1
                emit('completed', stage=s, unit=st['completed'], signals=signals)
                sink_wire = ws.delivers[s]
                if sink_wire:
                    state['counts'][sink_wire] += 1
                    emit('counted', wire=sink_wire, count=state['counts'][sink_wire])
                else:
                    st['stock'] += 1
                return True
            if worked:
                emit('work', stage=s, unit=st['completed'] + 1,
                     progress={r: round(w['done'] / w['need'], 9) if w['need'] > EPS else 1.0
                               for r, w in wip['work'].items()})
                return True
        return False

    while step():
        pass
    open_targets = {s: n for s, n in remaining.items() if n > 0}
    if open_targets:
        reasons = {}
        for s in open_targets:
            wip = state['stages'][s]['wip']
            if wip and wip['work']:
                reasons[s] = 'out of ' + ', '.join(r for r, w in wip['work'].items()
                                                   if w['done'] < w['need'] - EPS)
            else:
                reasons[s] = 'waiting on materials'
        emit('stalled', short=open_targets, reasons=reasons)
    else:
        emit('met', targets=dict(sorted(targets.items())))
    return state


def replay_counts(events: list[dict]) -> tuple[dict[str, int], dict[str, int]]:
    """Counts and completions rebuilt from the event log alone."""
    counts: dict[str, int] = {}
    completed: dict[str, int] = {}
    for e in events:
        if e['kind'] == 'counted':
            counts[e['wire']] = counts.get(e['wire'], 0) + 1
        elif e['kind'] == 'completed':
            completed[e['stage']] = completed.get(e['stage'], 0) + 1
    return counts, completed


def summary(ws: Workshop, state: dict, targets: dict[str, int]) -> str:
    h = state['clock']['horizon']
    last = state['events'][-1]
    out = [f"horizon {h}  (clock {state['clock']['time']:.2f} h, {state['clock']['sequence']} events)",
           '  targets    ' + '  '.join(f'{s} {n}' for s, n in sorted(targets.items()))]
    for s in ws.order:
        st = state['stages'][s]
        line = f"  {s:<10} completed {st['horizon_completed']:>3} this horizon ({st['completed']} total), stock {st['stock']}"
        wip = st['wip']
        if wip:
            mats = ', '.join(f"{wid} {wip['materials'][wid] / per:.0%}" for wid, _, per in ws.inputs[s])
            work = ', '.join(f"{r} {w['done'] / w['need']:.0%}" for r, w in (wip['work'] or {}).items())
            line += f"; in progress: materials [{mats}]" + (f", work [{work}]" if work else '')
        out.append(line)
    out.append('  counted    ' + '  '.join(f'{w} {n}' for w, n in state['counts'].items()))
    out.append('  resources  ' + '  '.join(f"{r} {v['used']:.2f}/{v['limit']:.0f}" for r, v in state['resources'].items())
               + '  ' + '  '.join(f'{s} left {v:.2f}' for s, v in state['sources'].items()))
    if last['kind'] == 'stalled':
        out.append('  stalled: ' + '; '.join(f"{s} short {n} ({last['reasons'][s]})" for s, n in last['short'].items()))
    else:
        out.append('  every target met')
    return '\n'.join(out)


def parse_targets(text: str) -> dict[str, int]:
    out = {}
    for part in filter(None, text.split(',')):
        key, _, value = part.partition('=')
        out[key.strip()] = int(value)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('document', type=Path)
    ap.add_argument('--model', type=Path, default=None, help='sidecar model (default <document>.opt.json)')
    ap.add_argument('--sav', type=Path, default=None, help='continue from this saved state')
    ap.add_argument('--out', type=Path, default=None, help='write the state here (.sav)')
    ap.add_argument('--horizons', type=int, default=1)
    ap.add_argument('--target', default=None, help='units per stage per horizon, e.g. chairs=14,tables=2 '
                                                   '(default: the optimizer\'s whole-unit plan)')
    ap.add_argument('--segments', type=int, default=32, help='segments for the plan the default targets come from')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    try:
        ws = Workshop(args.document, args.model)
        state = load_state(ws, args.sav) if args.sav else new_state(ws)
        targets = plan_targets(ws, args.segments) if args.target is None else parse_targets(args.target)
        for name in targets:
            if name not in ws.stages:
                raise Refusal('UNKNOWN_STAGE', f'{name!r} is not a stage of the model')
        if args.target is not None:
            # A named target covers only what it names; upstream stages make what it needs.
            targets = expand_targets(ws, targets)
        reports = []
        for _ in range(args.horizons):
            run_horizon(ws, state, targets)
            reports.append(summary(ws, state, targets))
    except Refusal as r:
        print(json.dumps(r.as_dict(), indent=2, sort_keys=True) if args.json else f'refused {r.code}: {r.reason}'
              + (f'\n  next: {r.next_operation}' if r.next_operation else ''), file=sys.stderr)
        return 2
    if args.out:
        args.out.write_text(dump_state(state), encoding='utf-8', newline='\n')
    print(dump_state(state) if args.json else '\n\n'.join(reports))
    return 0


def expand_targets(ws: Workshop, targets: dict[str, int]) -> dict[str, int]:
    """Fill in upstream stages from the recipes: enough blanks for the chairs and tables named."""
    out = dict(targets)
    for s in sorted(ws.stages, key=lambda x: ws._depth(x)):
        for _, provider, per in ws.inputs[s]:
            if provider in ws.stages and provider not in targets:
                out[provider] = out.get(provider, 0) + int(math.ceil(per * out.get(s, 0) - EPS))
    return out


if __name__ == '__main__':
    raise SystemExit(main())
