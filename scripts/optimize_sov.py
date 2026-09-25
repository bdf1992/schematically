"""Plan the throughput of a schematic under time and material limits.

A `.sov` says what exists and what connects. It does not say how much. This script reads the
topology from a document and the quantities from a sidecar (`<name>.opt.json`), and chooses
activity levels that maximize value inside declared limits. Nothing here changes the file
format: the sidecar names Components, Wires and Planes by id, and the document stays authored
truth about structure only.

The model is a Leontief production network (the linear core) with separable effects on top:

  - every non-source, non-sink Component is a stage with an activity level x_c;
  - a Wire a -> b carries x_w units; the wires into a stage are consumed in fixed proportion,
    x_w = per_w * x_c, and the wires out of it share its output, sum(x_out) = yield_c * x_c;
  - a source's outflow is bounded by its supply; a sink's inflow earns value per unit;
  - a resource (labor hours, machine time, a material budget) has a limit, and each stage
    uses some of it per unit of activity; a resource may be scoped to a Plane, in which case
    only the Components inside that Plane draw on it (boundaries are real);
  - an effect bends one term: `saturation` on a value (diminishing returns, concave) or
    `congestion` on a resource use (each unit costs more as the stage nears capacity, convex).

Concave value and convex use are the convex case, and the convex case is solved exactly up
to a stated breakpoint error by turning each bent term into linear segments that the simplex
fills in order. A bend the other way (economies of scale, setup costs) makes the problem
nonconvex; it is refused with a reason rather than solved badly.

A stage marked `integer` is held to whole units by branch and bound over the same simplex.
The result says whether that search proved its plan optimal or stopped at the node limit
with a bound, what whole units cost against the fractional relaxation, and the measured
value of one more unit of each resource (shadow prices belong to the relaxation).

Usage:
    python scripts/optimize_sov.py examples/optimization/workshop.sov
    python scripts/optimize_sov.py examples/optimization/workshop.sov --compare   # linear vs nonlinear
    python scripts/optimize_sov.py examples/optimization/workshop.sov --relax     # fractional units
    python scripts/optimize_sov.py a.sov --model other.opt.json --segments 64 --node-limit 20000 --json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

EPS = 1e-9
SCHEMA = 'soveraeign.schematic/optimization@0.0-draft'


# --------------------------------------------------------------------------- linear program

class LPResult(dict):
    """status: optimal | infeasible | unbounded; x, objective, duals_ub, duals_eq."""


def simplex(c: list[float], A_ub: list[list[float]] = (), b_ub: list[float] = (),
            A_eq: list[list[float]] = (), b_eq: list[float] = (),
            upper: list[float | None] | None = None) -> LPResult:
    """Maximize c.x subject to A_ub x <= b_ub, A_eq x = b_eq, 0 <= x <= upper.

    Dense two-phase tableau simplex with Bland's rule, so it terminates on degenerate
    problems. Upper bounds become ordinary rows. Returns the plan and the shadow price of
    every row: how much the objective rises per unit the row's right-hand side is relaxed.
    Good for the tens to low hundreds of variables a schematic produces; not a general solver.
    """
    n = len(c)
    A_ub, b_ub = [list(r) for r in A_ub], list(b_ub)
    bound_rows = []
    for j, u in enumerate(upper or []):
        if u is not None and math.isfinite(u):
            row = [0.0] * n
            row[j] = 1.0
            A_ub.append(row)
            b_ub.append(float(u))
            bound_rows.append(j)
    rows = [(list(r), float(b), 'ub') for r, b in zip(A_ub, b_ub)] + \
           [(list(r), float(b), 'eq') for r, b in zip(A_eq, b_eq)]
    m = len(rows)
    n_slack = sum(1 for _, _, k in rows if k == 'ub')
    # Columns: x (n), slacks (n_slack), artificials (m, one per row; unused ones stay zero).
    width = n + n_slack + m
    T, basis, sign, slack_col, art_col = [], [], [], [], []
    s = 0
    for i, (r, b, kind) in enumerate(rows):
        row = r + [0.0] * (n_slack + m) + [b]
        if kind == 'ub':
            row[n + s] = 1.0
            slack_col.append(n + s)
            s += 1
        else:
            slack_col.append(None)
        flip = b < 0
        if flip:
            row = [-v for v in row]
        sign.append(-1.0 if flip else 1.0)
        art = n + n_slack + i
        art_col.append(art)
        if kind == 'ub' and not flip:
            basis.append(slack_col[i])
        else:
            row[art] = 1.0
            basis.append(art)
        T.append(row)

    arts = set(art_col)

    def pivot(pr: int, pc: int) -> None:
        pv = T[pr][pc]
        T[pr] = [v / pv for v in T[pr]]
        for i in range(len(T)):
            if i != pr and abs(T[i][pc]) > EPS:
                f = T[i][pc]
                T[i] = [a - f * b for a, b in zip(T[i], T[pr])]
        basis[pr] = pc

    def run(obj: list[float], allowed: set[int]) -> str:
        # obj is the reduced-cost row for maximization: entering column has obj[j] < 0.
        while True:
            enter = next((j for j in range(width) if j in allowed and obj[j] < -EPS), None)
            if enter is None:
                return 'optimal'
            ratios = [(T[i][-1] / T[i][enter], basis[i], i) for i in range(m) if T[i][enter] > EPS]
            if not ratios:
                return 'unbounded'
            best = min(r for r, _, _ in ratios)
            _, _, pr = min((r, b, i) for r, b, i in ratios if r <= best + EPS)
            f = obj[enter]
            pivot(pr, enter)
            for j in range(width + 1):
                obj[j] -= f * T[pr][j]

    def reduced(costs: list[float]) -> list[float]:
        obj = [-v for v in costs] + [0.0]
        for i, bj in enumerate(basis):
            if abs(costs[bj]) > EPS:
                obj = [o + costs[bj] * t for o, t in zip(obj, T[i])]
        return obj

    everything = set(range(width))
    if any(b in arts for b in basis):
        phase1 = [0.0] * width
        for i, bj in enumerate(basis):
            if bj in arts:
                phase1[bj] = -1.0
        obj = reduced(phase1)
        run(obj, everything)
        if obj[-1] < -1e-7:
            return LPResult(status='infeasible')
        # Drive any artificial left in the basis at zero level out, where a real column can.
        for i, bj in enumerate(basis):
            if bj in arts:
                pc = next((j for j in range(n + n_slack) if abs(T[i][j]) > EPS), None)
                if pc is not None:
                    pivot(i, pc)
    costs = list(c) + [0.0] * (n_slack + m)
    obj = reduced(costs)
    status = run(obj, everything - arts)
    if status != 'optimal':
        return LPResult(status=status)
    x = [0.0] * n
    for i, bj in enumerate(basis):
        if bj < n:
            x[bj] = T[i][-1]
    duals = []
    for i in range(m):
        # A slack reads the original row's price directly, flipped or not; an equality
        # reads it through its artificial, in the sign the row was stored with.
        if slack_col[i] is not None:
            duals.append(obj[slack_col[i]])
        else:
            duals.append(obj[art_col[i]] * sign[i])
    n_ub = len(A_ub)
    return LPResult(status='optimal', x=x, objective=obj[-1],
                    duals_ub=duals[:n_ub - len(bound_rows)], duals_bound=dict(zip(bound_rows, duals[n_ub - len(bound_rows):n_ub])),
                    duals_eq=duals[n_ub:])


# --------------------------------------------------------------------------- whole units

INT_TOL = 1e-6


def branch_and_bound(c: list[float], A_ub: list[list[float]], b_ub: list[float], A_eq: list[list[float]],
                     b_eq: list[float], upper: list[float | None], integer: list[int],
                     node_limit: int = 5000, gap: float = 1e-9) -> dict:
    """Maximize c.x as `simplex` does, with the variables in `integer` held to whole numbers.

    Each node is the LP with tightened bounds on some integer variables. Its LP optimum is an
    upper bound on every whole-number plan beneath it, so a node whose bound cannot beat the
    best plan found so far (the incumbent) is pruned without being explored. Nodes are taken
    best bound first, and deeper first among equals, so an incumbent arrives early. The
    variable branched on is the most fractional one: x <= floor(v) on one side, x >= ceil(v)
    on the other.

    Returns status `optimal` (the bound met the incumbent), `node_limit` (stopped with a
    stated gap), `infeasible` or `unbounded`; the relaxation's value; nodes explored.
    """
    import heapq

    n = len(c)
    base_upper = list(upper) + [None] * (n - len(upper))

    def relax(bounds: dict[int, tuple[float, float | None]]) -> LPResult:
        up = list(base_upper)
        rows, rhs = [list(r) for r in A_ub], list(b_ub)
        for j, (lo, hi) in bounds.items():
            if hi is not None:
                up[j] = hi if up[j] is None else min(up[j], hi)
            if lo > 0:
                row = [0.0] * n
                row[j] = -1.0
                rows.append(row)
                rhs.append(-lo)
        return simplex(c, rows, rhs, A_eq, b_eq, up)

    def beats(value: float, incumbent: float) -> bool:
        # No incumbent yet (-inf) means anything beats it; the tolerance would be inf - inf.
        return incumbent == -math.inf or value > incumbent + gap * max(1.0, abs(incumbent))

    root = relax({})
    if root['status'] != 'optimal':
        return {'status': root['status'], 'nodes': 1}
    relaxation = root['objective']
    best, best_x, nodes, counter = -math.inf, None, 0, 0
    heap = [(-root['objective'], 0, counter, {}, root)]
    while heap:
        neg_bound, neg_depth, _, bounds, res = heapq.heappop(heap)
        if not beats(-neg_bound, best):
            continue
        nodes += 1
        x = res['x']
        # Distance to the nearest whole number; the most fractional variable is branched on.
        frac = [(abs(x[j] - round(x[j])), j) for j in integer if abs(x[j] - round(x[j])) > INT_TOL]
        if not frac:
            best, best_x = res['objective'], [round(v) if j in integer else v for j, v in enumerate(x)]
            continue
        if nodes >= node_limit:
            heapq.heappush(heap, (neg_bound, neg_depth, counter, bounds, res))
            break
        _, j = max(frac)
        v = x[j]
        lo, hi = bounds.get(j, (0.0, None))
        for child in ({**bounds, j: (lo, float(math.floor(v)))}, {**bounds, j: (float(math.ceil(v)), hi)}):
            clo, chi = child[j]
            if chi is not None and clo > chi:
                continue
            r = relax(child)
            if r['status'] == 'optimal' and beats(r['objective'], best):
                counter += 1
                heapq.heappush(heap, (-r['objective'], neg_depth - 1, counter, child, r))
    open_bound = max([-h[0] for h in heap], default=-math.inf)
    if best_x is None:
        if heap:
            return {'status': 'node_limit', 'nodes': nodes, 'relaxation': relaxation, 'bound': open_bound}
        return {'status': 'infeasible', 'nodes': nodes, 'relaxation': relaxation}
    bound = max(best, open_bound)
    status = 'node_limit' if beats(bound, best) else 'optimal'
    return {'status': status, 'x': best_x, 'objective': best, 'bound': bound, 'relaxation': relaxation,
            'nodes': nodes}


# --------------------------------------------------------------------------- effects

def saturation(v: float, k: float) -> float:
    """Value of v units when each further unit is worth less: k * (1 - exp(-v / k)).

    The first unit is worth about one full unit; far past k almost nothing. Concave.
    """
    return k * (1.0 - math.exp(-v / k))


def congestion(v: float, cap: float, power: float) -> float:
    """Resource drawn by v units when crowding a capacity: v * (1 + (v / cap) ** power).

    Near empty a unit costs its base use; at capacity it costs twice that. Convex for power >= 0.
    """
    return v * (1.0 + (v / cap) ** power)


def curve(effect: dict | None, cap: float | None):
    kind = (effect or {}).get('kind', 'linear')
    if kind == 'linear':
        return lambda v: v, 'linear'
    if kind == 'saturation':
        k = float(effect['k'])
        return (lambda v: saturation(v, k)), 'concave'
    if kind == 'congestion':
        power = float(effect.get('power', 2))
        c = float(effect.get('capacity', cap or 0))
        if c <= 0:
            raise Refusal('CONGESTION_WITHOUT_CAPACITY', 'congestion bends toward a capacity; declare one')
        if power < 0:
            return (lambda v: congestion(v, c, power)), 'concave'
        return (lambda v: congestion(v, c, power)), 'convex'
    if kind == 'economies':
        p = float(effect['power'])
        return (lambda v: v ** p if v > 0 else 0.0), ('concave' if p < 1 else 'convex')
    raise Refusal('UNKNOWN_EFFECT', f'effect kind {kind!r} is not declared')


class Refusal(Exception):
    def __init__(self, code: str, reason: str, next_operation: str = ''):
        super().__init__(f'{code}: {reason}')
        self.code, self.reason, self.next_operation = code, reason, next_operation

    def as_dict(self) -> dict:
        return {'refused': self.code, 'reason': self.reason, 'next_operation': self.next_operation}


# --------------------------------------------------------------------------- the model

def load(doc_path: Path, model_path: Path | None = None) -> tuple[dict, dict]:
    doc = json.loads(doc_path.read_text(encoding='utf-8'))
    model_path = model_path or doc_path.with_suffix('.opt.json')
    if not model_path.exists():
        raise Refusal('NO_MODEL', f'{model_path.name} does not exist; the document holds no quantities',
                      f'write {model_path.name} naming stages, resources and values')
    model = json.loads(model_path.read_text(encoding='utf-8'))
    if model.get('schema') != SCHEMA:
        raise Refusal('SCHEMA', f'expected {SCHEMA}, found {model.get("schema")!r}')
    return doc, model


def inside(doc: dict, component_id: str, plane_id: str) -> bool:
    parents = {c['id']: c.get('parentId') for c in doc.get('components', [])}
    seen, cur = set(), parents.get(component_id)
    while cur and cur not in seen:
        if cur == plane_id:
            return True
        seen.add(cur)
        cur = parents.get(cur)
    return False


def build(doc: dict, model: dict, segments: int = 32, linear: bool = False) -> dict:
    """Turn document + model into an LP. `linear` drops every effect (the naive model)."""
    comps = {c['id']: c for c in doc.get('components', [])}
    stages = model.get('stages', {})
    for cid in stages:
        if cid not in comps:
            raise Refusal('UNKNOWN_COMPONENT', f'stage {cid!r} is not a Component of the document')
    # Boundary points only relay: a Wire into a Point and a Wire out of it are one flow.
    relays = {cid for cid, c in comps.items() if c.get('symbolId') == 'point'}
    wires = []
    for w in doc.get('wires', []):
        wires.append({'id': w['id'], 'a': w['a'], 'b': w['b']})
    for w in wires:
        for end in ('a', 'b'):
            if w[end] not in comps:
                raise Refusal('FREE_END', f'wire {w["id"]} has a free {end} end; a flow needs two')

    def role(cid: str) -> str:
        if cid in relays:
            return 'relay'
        return stages.get(cid, {}).get('role', 'stage')

    for cid, c in comps.items():
        if role(cid) == 'stage' and cid not in stages and c.get('symbolId') != 'plane':
            raise Refusal('UNQUANTIFIED_STAGE', f'{cid!r} carries flow but the model names no quantities for it',
                          f'add stages.{cid} to the model')

    var_names: list[str] = []
    upper: list[float | None] = []
    c: list[float] = []

    def var(name: str, ub: float | None = None, cost: float = 0.0) -> int:
        var_names.append(name)
        upper.append(ub)
        c.append(cost)
        return len(var_names) - 1

    flow = {w['id']: var(f'flow:{w["id"]}') for w in wires}
    act = {cid: var(f'activity:{cid}', stages[cid].get('capacity')) for cid in stages
           if role(cid) == 'stage'}
    A_eq, b_eq, A_ub, b_ub, rows_ub, rows_eq = [], [], [], [], [], []
    bends: list[dict] = []

    def eq(coefs: dict[int, float], rhs: float, label: str) -> None:
        A_eq.append(coefs)
        b_eq.append(rhs)
        rows_eq.append(label)

    def ub(coefs: dict[int, float], rhs: float, label: str) -> None:
        A_ub.append(coefs)
        b_ub.append(rhs)
        rows_ub.append(label)

    def piecewise(x_index: int, fn, shape: str, hi: float, label: str) -> list[tuple[int, float]]:
        """Split x into `segments` pieces on [0, hi]; returns (segment var, slope) pairs."""
        if hi is None or not math.isfinite(hi) or hi <= 0:
            raise Refusal('UNBOUNDED_BEND', f'{label} bends but has no bound to bend over',
                          'declare a capacity or supply on the stage')
        width = hi / segments
        parts, prev = [], 0.0
        coefs = {x_index: 1.0}
        for k in range(segments):
            val = fn((k + 1) * width)
            slope = (val - prev) / width
            prev = val
            j = var(f'segment:{label}:{k}', width)
            parts.append((j, slope))
            coefs[j] = -1.0
        eq(coefs, 0.0, f'split:{label}')
        bends.append({'label': label, 'shape': shape, 'segments': segments, 'width': width})
        return parts

    # Relays conserve flow.
    for rid in relays:
        ins = [flow[w['id']] for w in wires if w['b'] == rid]
        outs = [flow[w['id']] for w in wires if w['a'] == rid]
        if ins or outs:
            eq({**{j: 1.0 for j in ins}, **{j: -1.0 for j in outs}}, 0.0, f'relay:{rid}')

    def feeding(cid: str) -> list[dict]:
        return [w for w in wires if w['b'] == cid]

    def per_of(w: dict) -> float:
        per = model.get('flows', {}).get(w['id'], {}).get('per')
        if per is None:
            raise Refusal('NO_RECIPE', f'wire {w["id"]} feeds a stage but declares no per-unit amount',
                          f'add flows.{w["id"]}.per')
        return float(per)

    for cid, spec in stages.items():
        r = role(cid)
        outs = [flow[w['id']] for w in wires if w['a'] == cid]
        ins = [flow[w['id']] for w in feeding(cid)]
        if r == 'source':
            cap = spec.get('supply')
            if cap is None:
                raise Refusal('NO_SUPPLY', f'source {cid!r} has no declared supply', f'add stages.{cid}.supply')
            ub({j: 1.0 for j in outs}, float(cap), f'supply:{cid}')
        elif r == 'sink':
            pass
        else:
            x = act[cid]
            for w in feeding(cid):
                eq({flow[w['id']]: 1.0, x: -per_of(w)}, 0.0, f'recipe:{w["id"]}')
            if outs:
                eq({**{j: 1.0 for j in outs}, x: -float(spec.get('yield', 1.0))}, 0.0, f'yield:{cid}')

    # Value: per unit delivered into a sink, optionally saturating.
    for w in wires:
        f = model.get('flows', {}).get(w['id'], {})
        if 'value' not in f:
            continue
        value = float(f['value'])
        fn, shape = curve(None if linear else f.get('effect'), None)
        if shape == 'linear':
            c[flow[w['id']]] += value
            continue
        if shape != 'concave':
            raise Refusal('NONCONVEX', f'value on {w["id"]} grows faster than linear; the optimum may sit at a corner the simplex cannot see',
                          'model it as integer choice (MILP) or drop the effect')
        hi = f.get('effect', {}).get('over') or _flow_bound(w, stages, wires, model)
        for j, slope in piecewise(flow[w['id']], fn, shape, hi, w['id']):
            c[j] += value * slope

    # Resources: limit, optional Plane scope, per-unit use by each stage, optional bend.
    resources = model.get('resources', {})
    for rname, res in resources.items():
        scope = res.get('scope')
        if scope and scope not in comps:
            raise Refusal('UNKNOWN_SCOPE', f'resource {rname!r} is scoped to {scope!r}, which is not in the document')
        coefs: dict[int, float] = {}
        for cid, spec in stages.items():
            use = spec.get('uses', {}).get(rname)
            if use is None:
                continue
            if cid not in act:
                raise Refusal('SOURCE_USES_RESOURCE', f'{cid!r} is a {role(cid)}; only stages draw on resources')
            if scope and not inside(doc, cid, scope):
                raise Refusal('OUT_OF_SCOPE', f'{cid!r} draws on {rname!r}, which is bounded to {scope!r}, from outside it',
                              f'move {cid} inside {scope}, or unscope the resource')
            effect = None if linear else spec.get('effects', {}).get(rname)
            fn, shape = curve(effect, spec.get('capacity'))
            if shape == 'linear':
                coefs[act[cid]] = coefs.get(act[cid], 0.0) + float(use)
                continue
            if shape != 'convex':
                raise Refusal('NONCONVEX', f'{cid} uses {rname!r} less per unit as it grows; cheaper-at-scale needs integer choice',
                              'model it as MILP or drop the effect')
            for j, slope in piecewise(act[cid], fn, shape, spec.get('capacity'), f'{cid}:{rname}'):
                coefs[j] = coefs.get(j, 0.0) + float(use) * slope
        ub(coefs, float(res['limit']), f'resource:{rname}')

    n = len(var_names)
    dense = lambda rows: [[r.get(j, 0.0) for j in range(n)] for r in rows]  # noqa: E731
    return {'c': c, 'A_ub': dense(A_ub), 'b_ub': b_ub, 'A_eq': dense(A_eq), 'b_eq': b_eq, 'upper': upper,
            'names': var_names, 'rows_ub': rows_ub, 'rows_eq': rows_eq, 'act': act, 'flow': flow,
            'bends': bends, 'integer': [act[cid] for cid in act if stages[cid].get('integer')]}


def _flow_bound(w: dict, stages: dict, wires: list[dict], model: dict) -> float | None:
    """A bound on a value-bearing wire, from the capacity of the stage feeding it."""
    spec = stages.get(w['a'], {})
    if 'capacity' in spec:
        return float(spec['capacity']) * float(spec.get('yield', 1.0))
    feeders = [x for x in wires if x['b'] == w['a']]
    for x in feeders:
        b = _flow_bound(x, stages, wires, model)
        if b is not None:
            return b
    return None


def true_value(doc: dict, model: dict, plan: dict) -> dict:
    """Evaluate a plan under the full nonlinear model, whatever model produced it."""
    stages = model.get('stages', {})
    value = 0.0
    for wid, f in model.get('flows', {}).items():
        if 'value' in f:
            fn, _ = curve(f.get('effect'), None)
            value += float(f['value']) * fn(plan['flows'].get(wid, 0.0))
    usage = {}
    for rname, res in model.get('resources', {}).items():
        used = 0.0
        for cid, spec in stages.items():
            use = spec.get('uses', {}).get(rname)
            if use is None:
                continue
            fn, _ = curve(spec.get('effects', {}).get(rname), spec.get('capacity'))
            used += float(use) * fn(plan['activity'].get(cid, 0.0))
        usage[rname] = {'used': used, 'limit': float(res['limit']), 'feasible': used <= float(res['limit']) + 1e-6}
    return {'value': value, 'usage': usage, 'feasible': all(u['feasible'] for u in usage.values())}


def solve(doc: dict, model: dict, segments: int = 32, linear: bool = False, relax: bool = False,
          node_limit: int = 5000, marginals: bool = True) -> dict:
    """Solve the model. Stages marked `integer` are held to whole units unless `relax`."""
    lp = build(doc, model, segments, linear)
    res = simplex(lp['c'], lp['A_ub'], lp['b_ub'], lp['A_eq'], lp['b_eq'], lp['upper'])
    if res['status'] != 'optimal':
        raise Refusal(res['status'].upper(), f'the model is {res["status"]}',
                      'loosen a limit' if res['status'] == 'infeasible' else 'bound a value-bearing flow')
    shadow = {label[len('resource:'):]: d for label, d in zip(lp['rows_ub'], res['duals_ub'])
              if label.startswith('resource:')}
    shadow_supply = {label[len('supply:'):]: d for label, d in zip(lp['rows_ub'], res['duals_ub'])
                     if label.startswith('supply:')}
    capacity = {cid: res['duals_bound'][j] for cid, j in lp['act'].items() if j in res['duals_bound']}
    x, objective, whole = res['x'], res['objective'], None
    if lp['integer'] and not relax:
        bb = branch_and_bound(lp['c'], lp['A_ub'], lp['b_ub'], lp['A_eq'], lp['b_eq'], lp['upper'],
                              lp['integer'], node_limit=node_limit)
        if bb['status'] == 'infeasible' or 'x' not in bb:
            raise Refusal('NO_WHOLE_PLAN', f'no whole-unit plan found ({bb["status"]} after {bb["nodes"]} nodes)',
                          'raise --node-limit, loosen a limit, or solve with --relax')
        x, objective = bb['x'], bb['objective']
        whole = {'status': bb['status'], 'nodes': bb['nodes'], 'relaxation': res['objective'],
                 'bound': bb['bound'], 'price_of_whole_units': res['objective'] - bb['objective'],
                 'stages': [cid for cid, j in lp['act'].items() if j in lp['integer']]}
        if marginals:
            # Shadow prices belong to the relaxation. With whole units the value of one more
            # unit of a limit is lumpy, so it is measured: solve again with the limit raised by one.
            whole['marginal'] = {}
            for rname, r in model.get('resources', {}).items():
                more = json.loads(json.dumps(model))
                more['resources'][rname]['limit'] = float(r['limit']) + 1
                whole['marginal'][rname] = solve(doc, more, segments, linear, node_limit=node_limit,
                                                 marginals=False)['objective'] - objective
    plan = {'activity': {cid: x[j] for cid, j in lp['act'].items()},
            'flows': {wid: x[j] for wid, j in lp['flow'].items()}}
    return {'model': 'linear' if linear else 'nonlinear', 'segments': segments, 'objective': objective,
            'plan': plan, 'shadow_price': {'resource': shadow, 'supply': shadow_supply, 'capacity': capacity},
            'whole_units': whole, 'bends': lp['bends'], 'evaluated': true_value(doc, model, plan),
            'variables': len(lp['names']), 'rows': len(lp['rows_ub']) + len(lp['rows_eq'])}


# --------------------------------------------------------------------------- report

def report(result: dict, unit: str) -> str:
    ev = result['evaluated']
    out = [f"{result['model']} model  ({result['variables']} variables, {result['rows']} rows"
           + (f", {len(result['bends'])} bent terms x {result['segments']} segments" if result['bends'] else '') + ')',
           f"  plan value (as the model sees it) {result['objective']:.2f} {unit}",
           f"  plan value (under the true curves) {ev['value']:.2f} {unit}"
           + ('' if ev['feasible'] else '   <- INFEASIBLE under the true curves'), '  activity:']
    for cid, v in result['plan']['activity'].items():
        out.append(f'    {cid:<14} {v:8.2f}')
    out.append('  resources:')
    for r, u in ev['usage'].items():
        price = result['shadow_price']['resource'].get(r, 0.0)
        mark = '' if u['feasible'] else '  OVER'
        out.append(f"    {r:<14} {u['used']:8.2f} / {u['limit']:<8.2f} shadow {price:7.2f} {unit} per unit{mark}")
    for s, p in result['shadow_price']['supply'].items():
        out.append(f'    supply:{s:<7} shadow {p:7.2f} {unit} per unit')
    for s, p in result['shadow_price']['capacity'].items():
        if abs(p) > 1e-9:
            out.append(f'    capacity:{s:<5} shadow {p:7.2f} {unit} per unit')
    whole = result.get('whole_units')
    if whole:
        out.append(f"  whole units ({', '.join(whole['stages'])}): {whole['status']} after {whole['nodes']} nodes;"
                   f" relaxation {whole['relaxation']:.2f}, price of whole units {whole['price_of_whole_units']:.2f} {unit}")
        if whole['status'] != 'optimal':
            out.append(f"    best bound {whole['bound']:.2f}: the plan may be up to"
                       f" {whole['bound'] - result['objective']:.2f} {unit} short of optimal")
        for r, m in whole.get('marginal', {}).items():
            out.append(f'    one more {r:<8} gains {m:7.2f} {unit} (measured; shadow prices above are the relaxation\'s)')
    return '\n'.join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('document', type=Path)
    ap.add_argument('--model', type=Path, default=None, help='sidecar model (default <document>.opt.json)')
    ap.add_argument('--segments', type=int, default=32, help='linear pieces per bent term')
    ap.add_argument('--linear', action='store_true', help='drop every effect')
    ap.add_argument('--compare', action='store_true', help='solve linear and nonlinear, and judge both by the true curves')
    ap.add_argument('--relax', action='store_true', help='ignore `integer` stages: fractional units allowed')
    ap.add_argument('--node-limit', type=int, default=5000, help='branch-and-bound nodes before stopping with a gap')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    try:
        doc, model = load(args.document, args.model)
        opts = {'relax': args.relax, 'node_limit': args.node_limit}
        runs = [solve(doc, model, args.segments, linear=True, **opts), solve(doc, model, args.segments, **opts)] \
            if args.compare else [solve(doc, model, args.segments, linear=args.linear, **opts)]
    except Refusal as r:
        print(json.dumps(r.as_dict(), indent=2, sort_keys=True) if args.json else f'refused {r.code}: {r.reason}'
              + (f'\n  next: {r.next_operation}' if r.next_operation else ''), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(runs if args.compare else runs[0], indent=2, sort_keys=True))
    else:
        unit = model.get('unit', '')
        print('\n\n'.join(report(r, unit) for r in runs))
        if args.compare:
            lin, non = runs[0]['evaluated'], runs[1]['evaluated']
            print(f"\nthe linear plan, judged by the true curves, is worth {lin['value']:.2f}"
                  + ('' if lin['feasible'] else ' and breaks a limit')
                  + f"; the nonlinear plan {non['value']:.2f}.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
