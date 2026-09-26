"""Record a run for the visual views: one JSON record per run, and the views only draw it.

A record (soveraeign.schematic/run@0.0-draft) names the document by its semantic fingerprint
and holds exactly what the views in scripts/plot_run.mjs draw, so a picture never computes a
number itself (VISUAL-LANGUAGE.md). Three kinds:

  logic     a state space run (STATE-SPACE.md) of a logic document through a sequence of
            input vectors, one every `period` ticks: every source's and output's changes in
            logical time, buses decoded by name, the event log, and the trace it came from
            (run id, head hash, last tick), so a picture names the run it draws;
  optimize  a two-decision model: the landscape (value and limit slack over a grid, whole-unit
            plans and local optima), gradient climbs and their optima, the proven fractional
            and whole-unit plans, the plan without effects, and the branch-and-bound log;
  simulate  a unit simulation: each unit's span of work, targets, the stall and its reason,
            and the units still in progress.

    python scripts/record_run.py logic examples/logic/adder4.sov --sequence 'A=7:4,B=0:4,Cin=0;B=1:4' --bus S
    python scripts/record_run.py optimize examples/optimization/workshop.sov --model examples/optimization/workshop.learning.opt.json
    python scripts/record_run.py simulate examples/optimization/workshop.sov --model examples/optimization/workshop.learning.opt.json --target chairs=14,tables=2
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from optimize_sov import Refusal, branch_and_bound, build, landscape, load, local_search, solve  # noqa: E402
from sov_fingerprint import document_fingerprint, model_fingerprint  # noqa: E402

SCHEMA = 'soveraeign.schematic/run@0.0-draft'


def _doc_ref(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding='utf-8'))
    return {'path': path.name, 'id': doc.get('id'), 'fingerprint': document_fingerprint(doc)}


# --------------------------------------------------------------------------- logic

def parse_vector(text: str) -> dict[str, int]:
    """'A=13:4,B=9:4,Cin=0' -> bits by source name; ':width' makes a bus, least significant first."""
    out: dict[str, int] = {}
    for part in filter(None, (x.strip() for x in text.split(','))):
        name, _, value = part.partition('=')
        value, _, width = value.partition(':')
        if width:
            v, w = int(value), int(width)
            if not 0 <= v < 2 ** w:
                raise Refusal('OUT_OF_RANGE', f'{name}={v} does not fit in {w} bits')
            out.update({f'{name}{i}': (v >> i) & 1 for i in range(w)})
        else:
            if value not in ('0', '1'):
                raise Refusal('NOT_A_BIT', f'{name}={value}: a source takes 0 or 1 (state space runs binary channels)')
            out[name] = int(value)
    return out


def record_logic(path: Path, steps: list[dict], period: int = 20, buses: list[str] = ()) -> dict:
    """Run a logic document on state space and keep every change at its sources and outputs.

    Step k registers its vector at logical tick k * period. The run goes to quiet; the record
    is read from its trace, so every change is one the engine recorded. Sources and outputs are
    the document's Points; a Point's value is its `self` port's `logic.level`.
    """
    inputs = [{'entity': name, 'value': bool(v), 'at': k * period} for k, vector in enumerate(steps)
              for name, v in sorted(vector.items())]
    out = subprocess.run(['node', str(Path(__file__).resolve().parent / 'run_state.mjs')],
                         input=json.dumps([{'path': str(path), 'inputs': inputs}]), capture_output=True, text=True, check=True)
    result = json.loads(out.stdout)[0]
    if not result['ok']:
        raise Refusal(result['code'], result['message'])
    trace = result['trace']
    doc = json.loads(path.read_text(encoding='utf-8'))
    points = sorted(c['id'] for c in doc['components'] if c.get('symbolId') == 'point')
    signals: dict[str, list] = {n: [] for n in points}
    events: list[dict] = []
    for r in trace['records']:
        sub = r['subject']
        if r['observable'] != 'logic.level' or sub['point'] != 'self' or sub['entity'] not in signals:
            continue
        value, t, lane = int(r['value']), r['time']['logical'], signals[sub['entity']]
        if (lane[-1][1] if lane else 0) == value:
            continue   # a registered input equal to the level already held changes nothing
        lane.append([t, value])
        events.append({'t': t, 'signal': sub['entity'], 'value': value})
    bus_map = {}
    for b in buses:
        bits = sorted((n for n in signals if n.startswith(b) and n[len(b):].isdigit()), key=lambda n: int(n[len(b):]))
        if not bits:
            raise Refusal('NO_BUS', f'no Points named {b}0, {b}1, ... in {path.name}')
        bus_map[b] = bits
    run_id = trace['records'][0]['subject']['run'] if trace['records'] else None
    return {'schema': SCHEMA, 'kind': 'logic', 'document': _doc_ref(path), 'period': period,
            'end': max(len(steps) * period, (trace['through'] or 0) + 1), 'signals': signals, 'buses': bus_map,
            'events': events, 'run': {'id': run_id, 'head': trace['head'], 'through': trace['through']}}


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
    lg.add_argument('--sequence', required=True, help="vectors separated by ';', e.g. 'A=7:4,B=0:4,Cin=0;B=1:4'")
    lg.add_argument('--period', type=int, default=20, help='logical ticks between vectors')
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
            steps = [parse_vector(x) for x in args.sequence.split(';')]
            rec = record_logic(args.document, steps, args.period, args.bus)
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
