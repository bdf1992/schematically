"""Record a run for the visual views: one JSON record per run, and the views only draw it.

A record (soveraeign.schematic/run@0.0-draft) names the document by its semantic fingerprint
and holds exactly what the views in scripts/plot_run.mjs draw, so a picture never computes a
number itself (VISUAL-LANGUAGE.md). Three kinds:

  logic     a circuit driven through a sequence of input vectors, optionally clocked:
            every signal's changes in time, buses decoded by name, the event log, and for
            gates that read a level their thresholds;
  optimize  a two-decision model: the landscape (value and limit slack over a grid, whole-unit
            plans and local optima), gradient climbs and their optima, the proven fractional
            and whole-unit plans, the plan without effects, and the branch-and-bound log;
  simulate  a unit simulation: each unit's span of work, targets, the stall and its reason,
            and the units still in progress.

    python scripts/record_run.py logic examples/logic/ripple-counter4.sov --clock CLK --pulses 17 --bus Q
    python scripts/record_run.py logic examples/logic/schmitt.sov --wave X --samples 240
    python scripts/record_run.py optimize examples/optimization/workshop.sov --model examples/optimization/workshop.learning.opt.json
    python scripts/record_run.py simulate examples/optimization/workshop.sov --model examples/optimization/workshop.learning.opt.json --target chairs=14,tables=2
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from logic_sov import Circuit, parse_vector  # noqa: E402
from optimize_sov import Refusal, branch_and_bound, build, landscape, load, local_search, solve  # noqa: E402
from sov_fingerprint import document_fingerprint, model_fingerprint  # noqa: E402

SCHEMA = 'soveraeign.schematic/run@0.0-draft'


def _doc_ref(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding='utf-8'))
    return {'path': path.name, 'id': doc.get('id'), 'fingerprint': document_fingerprint(doc)}


# --------------------------------------------------------------------------- logic

def record_logic(path: Path, steps: list[dict], clock: str | None = None, period: int = 24,
                 buses: list[str] = (), wave: str | None = None) -> dict:
    """Drive a circuit and keep every change of every named input and output.

    With a clock, each step sets its vector and then raises the clock at k*period and lowers it
    half a period later. Without, each step is applied at k*period. Time is in gate delays.
    """
    c = Circuit(path)
    named = {c.net_names[c.net_of[t]]: n for n, t in c.inputs.items()}
    named.update({c.net_names[c.net_of[t]]: n for n, t in c.outputs.items()})
    signals: dict[str, list] = {n: [] for n in sorted(set(named.values()))}
    events: list[dict] = []
    c.apply({}, record=True)
    for e in c.events:
        if e['net'] in named:
            signals[named[e['net']]].append([e['t'], e['value']])
    c.events.clear()
    for k, vector in enumerate(steps):
        c.time = k * period
        c.apply(vector, record=True)
        if clock:
            c.apply({clock: 1}, record=True)
            c.time = k * period + period // 2
            c.apply({clock: 0}, record=True)
        for e in c.events:
            if e['net'] in named:
                signals[named[e['net']]].append([e['t'], e['value']])
                events.append({'t': e['t'], 'signal': named[e['net']], 'value': e['value']})
        c.events.clear()
    bus_map = {}
    for b in buses:
        bits = sorted((n for n in signals if n.startswith(b) and n[len(b):].isdigit()), key=lambda n: int(n[len(b):]))
        if not bits:
            raise Refusal('NO_BUS', f'no signals named {b}0, {b}1, ... in {path.name}')
        bus_map[b] = bits
    readers = []
    for g in c.gates:
        if g['def']['kind'] in ('compare', 'hysteresis') and wave:
            src = [n for n, t in c.inputs.items() if c.net_of[t] == g['in_nets'][0]]
            if src:
                out_names = [n for n, t in c.outputs.items() if c.net_of[t] in g['out_nets']]
                readers.append({'gate': g['id'], 'kind': g['def']['kind'], 'reads': src[0], 'params': g['params'],
                                'outputs': out_names})
    return {'schema': SCHEMA, 'kind': 'logic', 'document': _doc_ref(path), 'clock': clock, 'period': period,
            'end': len(steps) * period, 'signals': signals, 'buses': bus_map, 'events': events,
            'levels': sorted(n for n in c.inputs if c.levels.get(n)), 'readers': readers}


def noisy_wave(samples: int, seed: int = 6) -> list[float]:
    """A slow swing across 0.5 with noise smaller than a 0.2 band: the hysteresis test signal."""
    rng = random.Random(seed)
    return [round(0.5 + 0.3 * math.sin(k / (samples / 8)) + rng.uniform(-0.08, 0.08), 4) for k in range(samples)]


# --------------------------------------------------------------------------- optimize

def record_optimize(doc_path: Path, model_path: Path | None, segments: int = 32, starts: int = 24,
                    steps: int = 81) -> dict:
    import itertools
    doc, model = load(doc_path, model_path)
    ls = local_search(doc, model, starts=starts, record=True)
    names = ls['free']
    at = lambda plan: {n: plan['activity'][n] for n in names}  # noqa: E731
    frac = solve(doc, model, segments=segments, relax=True, marginals=False)
    whole = solve(doc, model, segments=segments, marginals=False)
    naive = solve(doc, model, segments=segments, linear=True, marginals=False)
    # Two decisions: the landscape is the whole problem. More: one slice per pair, the other
    # decisions held at the proven whole-unit plan (so whole-unit dots in a slice are real plans),
    # or at the fractional optimum when there are no whole units.
    anchor = at(whole['plan'] if whole.get('whole_units') else frac['plan'])
    landscapes = []
    for i, j in itertools.combinations(range(len(names)), 2):
        held = {n: anchor[n] for k, n in enumerate(names) if k not in (i, j)}
        landscapes.append(landscape(doc, model, steps=steps, pair=(i, j), held=held))
    lp = build(doc, model, segments=segments)
    log: list = []
    bb = branch_and_bound(lp['c'], lp['A_ub'], lp['b_ub'], lp['A_eq'], lp['b_eq'], lp['upper'],
                          lp['ordering'] + lp['integer'], log=log)

    def label(branch: dict | None) -> str:
        if not branch:
            return 'root'
        name = lp['names'][branch['var']]
        if name.startswith('order:'):
            curve, k = name.split(':')[1], int(name.split(':')[-1]) + 1
            return f'{curve}: piece {k} full' if branch['side'] == '>=' else f'{curve}: pieces after {k} unused'
        return f"{name.split(':', 1)[1]} {'≤' if branch['side'] == '<=' else '≥'} {int(branch['value'])}"

    return {
        'schema': SCHEMA, 'kind': 'optimize', 'document': _doc_ref(doc_path),
        'model': {'path': (model_path or doc_path.with_suffix('.opt.json')).name, 'fingerprint': model_fingerprint(model)},
        'unit': model.get('unit', ''), 'decisions': names, 'landscapes': landscapes,
        'climbs': [{'path': [[round(v, 4) for v in p] for p in c['path']], 'optimum': c['optimum']} for c in ls['climbs']],
        'optima': [{'at': dict(o['free']), 'value': o['value'], 'starts': o['starts'],
                    'certificate': 'local'} for o in ls['optima']],
        'plans': [
            {'name': 'fractional optimum', 'at': at(frac['plan']), 'value': frac['evaluated']['value'], 'certificate': 'proven',
             'feasible': frac['evaluated']['feasible']},
            {'name': 'whole-unit optimum', 'at': at(whole['plan']), 'value': whole['evaluated']['value'], 'certificate': 'proven',
             'feasible': whole['evaluated']['feasible']},
            {'name': 'without effects', 'at': at(naive['plan']), 'value': naive['evaluated']['value'], 'certificate': 'naive',
             'feasible': naive['evaluated']['feasible']},
        ],
        'search': {'nodes': [{**e, 'label': label(e['branch'])} for e in log], 'objective': bb['objective'],
                   'relaxation': bb['relaxation'], 'status': bb['status']},
    }


# --------------------------------------------------------------------------- simulate

def record_simulate(doc_path: Path, model_path: Path | None, targets: dict | None = None, horizons: int = 1) -> dict:
    from simulate_sov import Workshop, expand_targets, new_state, plan_targets, run_horizon
    ws = Workshop(doc_path, model_path)
    t = plan_targets(ws) if targets is None else expand_targets(ws, targets)
    st = new_state(ws)
    for _ in range(horizons):
        run_horizon(ws, st, t)
    spans, open_ = [], {}
    for e in st['events']:
        if e['kind'] == 'start':
            open_[e['stage']] = e['t']
        elif e['kind'] == 'completed':
            spans.append({'stage': e['stage'], 'unit': e['unit'], 'start': open_.pop(e['stage']), 'end': e['t'],
                          'horizon': e['horizon']})
    stops = [{'horizon': e['horizon'], 't': e['t'], 'kind': e['kind'], 'short': e.get('short', {}),
              'reasons': e.get('reasons', {})} for e in st['events'] if e['kind'] in ('stalled', 'met')]
    wip = {}
    for s, v in st['stages'].items():
        if v['wip']:
            per = {wid: p for wid, _, p in ws.inputs[s]}
            wip[s] = {'materials': {w: got / per[w] for w, got in v['wip']['materials'].items()},
                      'work': {r: w['done'] / w['need'] for r, w in (v['wip']['work'] or {}).items()}}
    limits = {r: v['limit'] for r, v in st['resources'].items()}
    return {'schema': SCHEMA, 'kind': 'simulate', 'document': _doc_ref(doc_path),
            'model': {'path': ws.model_path.name, 'fingerprint': model_fingerprint(ws.model)},
            'stages': ws.order, 'targets': t, 'limits': limits, 'horizons': horizons,
            'spans': spans, 'stops': stops, 'wip': wip, 'counts': st['counts'], 'clock': st['clock']['time']}


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='kind', required=True)
    lg = sub.add_parser('logic')
    lg.add_argument('document', type=Path)
    lg.add_argument('--clock')
    lg.add_argument('--pulses', type=int, default=0, help='with --clock and no --sequence: this many empty steps')
    lg.add_argument('--sequence', default=None, help="steps separated by ';', each like logic_sov --set")
    lg.add_argument('--wave', default=None, help='drive this level input with the noisy test swing')
    lg.add_argument('--samples', type=int, default=240)
    lg.add_argument('--period', type=int, default=24)
    lg.add_argument('--bus', action='append', default=[])
    op = sub.add_parser('optimize')
    op.add_argument('document', type=Path)
    op.add_argument('--model', type=Path)
    op.add_argument('--segments', type=int, default=32)
    op.add_argument('--starts', type=int, default=24)
    op.add_argument('--steps', type=int, default=81)
    sm = sub.add_parser('simulate')
    sm.add_argument('document', type=Path)
    sm.add_argument('--model', type=Path)
    sm.add_argument('--target', default=None)
    sm.add_argument('--horizons', type=int, default=1)
    for p in (lg, op, sm):
        p.add_argument('--out', type=Path, default=None)
    args = ap.parse_args(argv)
    try:
        if args.kind == 'logic':
            if args.wave:
                steps = [{args.wave: x} for x in noisy_wave(args.samples)]
                period = 1 if args.period == 24 else args.period
            else:
                steps = [parse_vector(s.strip()) for s in args.sequence.split(';')] if args.sequence \
                    else [{} for _ in range(args.pulses)]
                period = args.period
            rec = record_logic(args.document, steps, args.clock, period, args.bus, args.wave)
        elif args.kind == 'optimize':
            rec = record_optimize(args.document, args.model, args.segments, args.starts, args.steps)
        else:
            targets = None
            if args.target:
                targets = {k: int(v) for k, v in (p.split('=') for p in args.target.split(','))}
            rec = record_simulate(args.document, args.model, targets, args.horizons)
    except Refusal as r:
        print(f'refused {r.code}: {r.reason}', file=sys.stderr)
        return 2
    text = json.dumps(rec, sort_keys=True, ensure_ascii=False) + '\n'
    if args.out:
        args.out.write_text(text, encoding='utf-8', newline='\n')
        print(f'wrote {args.out} ({len(text)} bytes)')
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
