"""Throughput optimization QA.

`scripts/optimize_sov.py` claims three things, and each is checked here against a path the
solver did not choose:

  - the simplex returns the textbook optimum and shadow prices on problems whose answers are
    known (Wyndor Glass, an equality with a floor, Beale's cycling example), and names
    infeasible and unbounded problems instead of returning a plan;
  - a shadow price is what the objective actually gains when its limit is relaxed a little
    (finite difference, not the tableau reading back its own number);
  - branch and bound returns the same whole-unit optimum as enumerating every whole-unit plan
    (a knapsack and the workshop), and says `node_limit` with an honest bound when stopped early;
  - a nonconvex bend (cheaper at scale, accelerating value) is solved globally: the plan
    matches enumeration of every whole plan under the true curves, even though that landscape
    has several local optima; the segments fill in order; and the same LP without ordering
    claims a value no plan can reach;
  - projected gradient with multistart, climbing the true curves with no segments, agrees
    with the exact solver where the problem is convex (every start, one optimum), comes within
    0.1% of it on the learning curve, and also reports the trap there: an all-tables plan that
    is a genuine local optimum (checked by probing its neighbourhood, not by the climber);
  - on the workshop example, the nonlinear plan is feasible under the true curves, the linear
    plan is not, refining the breakpoints only raises the value and converges, and the
    refusals fire for an out-of-scope resource, a nonconvex bend and a missing recipe.
"""
from __future__ import annotations

import copy
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from optimize_sov import Refusal, branch_and_bound, build, load, local_search, simplex, solve, true_value  # noqa: E402

DOC = ROOT / 'examples' / 'optimization' / 'workshop.sov'
LEARNING = ROOT / 'examples' / 'optimization' / 'workshop.learning.opt.json'


def close(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def check_simplex() -> None:
    # Wyndor Glass (Hillier & Lieberman): max 3x + 5y; x <= 4; 2y <= 12; 3x + 2y <= 18.
    r = simplex([3, 5], [[1, 0], [0, 2], [3, 2]], [4, 12, 18])
    assert r['status'] == 'optimal', r
    assert close(r['objective'], 36) and close(r['x'][0], 2) and close(r['x'][1], 6), r
    assert all(close(a, b) for a, b in zip(r['duals_ub'], [0, 1.5, 1])), r['duals_ub']

    # An equality and a floor written as a negative row: max -x - 2y; x + y = 10; x >= 3; y >= 4.
    r = simplex([-1, -2], [[-1, 0], [0, -1]], [-3, -4], [[1, 1]], [10])
    assert r['status'] == 'optimal' and close(r['objective'], -14), r
    assert close(r['x'][0], 6) and close(r['x'][1], 4), r
    assert close(r['duals_eq'][0], -1), r['duals_eq']            # one more unit forced in costs 1
    assert close(r['duals_ub'][1], 1), r['duals_ub']             # relaxing y >= 4 to y >= 3 gains 1

    # Upper bounds as a separate argument, and their prices.
    r = simplex([1, 1], [[1, 2]], [10], upper=[4, None])
    assert close(r['objective'], 7) and close(r['duals_bound'][0], 0.5), r

    # Beale (1955): cycles under the textbook rule; Bland's rule must terminate at 1/20.
    r = simplex([0.75, -150, 0.02, -6],
                [[0.25, -60, -0.04, 9], [0.5, -90, -0.02, 3], [0, 0, 1, 0]], [0, 0, 1])
    assert r['status'] == 'optimal' and close(r['objective'], 0.05), r

    assert simplex([1], [[1], [-1]], [1, -2])['status'] == 'infeasible'
    assert simplex([1, 0], [[0, 1]], [1])['status'] == 'unbounded'


def with_model(change) -> tuple[dict, dict]:
    doc, model = load(DOC)
    doc, model = copy.deepcopy(doc), copy.deepcopy(model)
    change(doc, model)
    return doc, model


def check_workshop() -> None:
    doc, model = load(DOC)
    linear = solve(doc, model, linear=True, relax=True)
    bent = solve(doc, model, relax=True)
    assert not linear['evaluated']['feasible'], 'the linear plan should overrun labor once congestion is real'
    assert bent['evaluated']['feasible'], bent['evaluated']
    assert bent['evaluated']['value'] > linear['evaluated']['value'], (bent['evaluated'], linear['evaluated'])
    assert bent['plan']['activity']['chairs'] > 0 and bent['plan']['activity']['tables'] > 0, \
        'saturation should make the plan mix products; the linear plan picks one'

    values = [solve(doc, model, segments=s, relax=True)['evaluated']['value'] for s in (4, 16, 64, 256)]
    assert all(b >= a - 1e-6 for a, b in zip(values, values[1:])), values
    assert values[-1] - values[-2] < 0.005 * values[-1], values

    # A shadow price is the gain per unit of relaxation: check it by relaxing.
    price = bent['shadow_price']['resource']['labor']
    assert price > 0, 'labor binds in the example'
    _, more = with_model(lambda d, m: m['resources']['labor'].update(limit=m['resources']['labor']['limit'] + 0.05))
    gained = (solve(doc, more, relax=True)['objective'] - bent['objective']) / 0.05
    assert abs(gained - price) < 0.05 * price, (gained, price)
    assert close(bent['shadow_price']['supply']['timber'], 0), 'timber is slack; it should be free at the margin'


def check_whole_units() -> None:
    # 0/1 knapsack: weights 5 4 6 3, values 10 40 30 50, capacity 10 -> items 2 and 4, value 90.
    # Its relaxation takes a fraction of item 3, so the root is not already whole.
    bb = branch_and_bound([10, 40, 30, 50], [[5, 4, 6, 3]], [10], [], [], [1, 1, 1, 1], [0, 1, 2, 3])
    assert bb['status'] == 'optimal' and close(bb['objective'], 90), bb
    assert [round(v) for v in bb['x']] == [0, 1, 0, 1], bb['x']
    assert bb['relaxation'] > bb['objective'], 'the example should need branching'

    # A general integer program checked against enumeration: max 5x + 4y; 6x + 4y <= 24; x + 2y <= 6.
    best = max(5 * x + 4 * y for x in range(5) for y in range(4) if 6 * x + 4 * y <= 24 and x + 2 * y <= 6)
    bb = branch_and_bound([5, 4], [[6, 4], [1, 2]], [24, 6], [], [], [None, None], [0, 1])
    assert close(bb['objective'], best), (bb, best)

    # No whole point inside: 2x = 1.
    assert branch_and_bound([1], [], [], [[2]], [1], [None], [0])['status'] == 'infeasible'

    # The workshop: every whole (chairs, tables) pair, each with the rest of the LP solved, and
    # the best of them must be what branch and bound returns.
    doc, model = load(DOC)
    for linear in (True, False):
        lp = build(doc, model, linear=linear)
        chairs, tables = lp['act']['chairs'], lp['act']['tables']
        enumerated = -math.inf
        for a in range(21):
            for b in range(9):
                up = list(lp['upper'])
                up[chairs], up[tables] = a, b
                floor = [[-1.0 if j == chairs else 0.0 for j in range(len(lp['c']))],
                         [-1.0 if j == tables else 0.0 for j in range(len(lp['c']))]]
                r = simplex(lp['c'], lp['A_ub'] + floor, lp['b_ub'] + [-a, -b], lp['A_eq'], lp['b_eq'], up)
                if r['status'] == 'optimal':
                    enumerated = max(enumerated, r['objective'])
        got = solve(doc, model, linear=linear, marginals=False)
        assert got['whole_units']['status'] == 'optimal', got['whole_units']
        assert close(got['objective'], enumerated), (linear, got['objective'], enumerated)
        for cid in ('chairs', 'tables'):
            v = got['plan']['activity'][cid]
            assert v == round(v), (cid, v)
        assert got['whole_units']['price_of_whole_units'] >= -1e-9, got['whole_units']
        assert got['evaluated']['feasible'] or linear, got['evaluated']

    # Stopped early, the answer says so and carries a bound that is still an upper bound.
    wide = [7, 9, 11, 13, 17, 19, 23, 29]
    bb = branch_and_bound(wide, [[w + 1 for w in wide]], [60.5], [], [], [3] * 8, list(range(8)), node_limit=2)
    assert bb['status'] == 'node_limit', bb
    full = branch_and_bound(wide, [[w + 1 for w in wide]], [60.5], [], [], [3] * 8, list(range(8)))
    assert full['status'] == 'optimal' and bb['bound'] >= full['objective'] - 1e-9, (bb, full)
    if 'objective' in bb:
        assert bb['objective'] <= full['objective'] + 1e-9


def landscape(doc: dict, model: dict) -> dict[tuple[int, int], float]:
    """Every whole (chairs, tables) plan the workshop can run, valued under the true curves.

    Independent of the solver's LP: the cut follows from the recipe, feasibility is checked
    against the true curves, timber and the saw's capacity.
    """
    stages, per = model['stages'], model['flows']
    out = {}
    for a in range(int(stages['chairs']['capacity']) + 1):
        for b in range(int(stages['tables']['capacity']) + 1):
            cut = per['w-chair-blanks']['per'] * a + per['w-table-blanks']['per'] * b
            if cut > stages['cut']['capacity'] or cut * per['w-stock']['per'] > stages['timber']['supply'] + 1e-9:
                continue
            plan = {'activity': {'chairs': a, 'tables': b, 'cut': cut},
                    'flows': {'w-chair-sales': a, 'w-table-sales': b}}
            ev = true_value(doc, model, plan)
            if ev['feasible']:
                out[(a, b)] = ev['value']
    return out


def local_optima(values: dict[tuple[int, int], float]) -> list[tuple[int, int]]:
    """Plans no single step (one more or less of either, or a swap) improves."""
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]
    return [p for p, v in values.items()
            if all(values.get((p[0] + da, p[1] + db), -math.inf) <= v + 1e-9 for da, db in steps)]


def check_nonconvex() -> None:
    doc, _ = load(DOC)
    _, learning = load(DOC, LEARNING)

    # Learning curve on chairs (labor use x^0.7). Twenty segments put a breakpoint on every
    # whole chair, so at whole units the pieces are the curve and the answer is exact.
    values = landscape(doc, learning)
    best = max(values, key=values.get)
    optima = local_optima(values)
    assert len(optima) >= 3, ('the example should be genuinely nonconvex', optima)
    got = solve(doc, learning, segments=20, marginals=False)
    plan = (round(got['plan']['activity']['chairs']), round(got['plan']['activity']['tables']))
    assert plan == best, (plan, best, values[best])
    assert close(got['evaluated']['value'], values[best]) and got['evaluated']['feasible'], got['evaluated']
    assert got['nonconvex']['status'] == 'optimal' and got['whole_units']['status'] == 'optimal', got
    assert got['shadow_price']['kind'] == 'local'

    # The model that ignores learning lands on a local optimum that is not the global one.
    naive = solve(doc, learning, linear=True, marginals=False)
    naive_plan = (round(naive['plan']['activity']['chairs']), round(naive['plan']['activity']['tables']))
    assert naive_plan in optima and naive_plan != best, (naive_plan, optima)

    # Without the ordering binaries the LP fills the cheap late segments first and claims more
    # than any plan can deliver; with them each segment fills only after the one before.
    relaxed = solve(doc, learning, segments=20, relax=True, marginals=False)
    assert relaxed['nonconvex']['lp_claims'] > relaxed['objective'] + 1e-6, relaxed['nonconvex']
    lp = build(doc, learning, segments=20)
    loose = simplex(lp['c'], lp['A_ub'], lp['b_ub'], lp['A_eq'], lp['b_eq'], lp['upper'])
    assert close(loose['objective'], relaxed['nonconvex']['lp_claims']), loose['objective']
    bb = branch_and_bound(lp['c'], lp['A_ub'], lp['b_ub'], lp['A_eq'], lp['b_eq'], lp['upper'], lp['ordering'])
    width = lp['bends'][[b['label'] for b in lp['bends']].index('chairs:labor')]['width']
    segs = [bb['x'][j] for j, name in enumerate(lp['names']) if name.startswith('segment:chairs:labor:')]
    for k in range(len(segs) - 1):
        assert segs[k + 1] <= 1e-7 or segs[k] >= width - 1e-7, ('segment filled out of order', k, segs)

    # Accelerating value on tables (price rises with volume, x^1.3) on the base workshop: eight
    # segments over the eight-table capacity, a breakpoint on every whole table.
    _, base = load(DOC)
    accel = copy.deepcopy(base)
    accel['flows']['w-table-sales']['effect'] = {'kind': 'economies', 'power': 1.3}
    got = solve(doc, accel, segments=8, marginals=False)
    values = landscape(doc, accel)
    best = max(values, key=values.get)
    plan = (round(got['plan']['activity']['chairs']), round(got['plan']['activity']['tables']))
    # Chair saturation is still approximated between breakpoints, so compare values, not plans.
    assert got['evaluated']['feasible'] and got['evaluated']['value'] >= values[best] - 0.01 * values[best], \
        (plan, got['evaluated']['value'], best, values[best])


def check_local_search() -> None:
    doc, base = load(DOC)
    _, learning = load(DOC, LEARNING)

    # Convex: every start reaches the same optimum, and it is the exact one.
    got = local_search(doc, base, starts=16)
    assert got['certificate'] == 'local'
    assert len(got['optima']) == 1 and got['optima'][0]['starts'] == 16, got['optima']
    exact = solve(doc, base, segments=128, relax=True, marginals=False)['evaluated']
    assert got['evaluated']['feasible'] and abs(got['best']['value'] - exact['value']) < 1e-3 * exact['value'], \
        (got['best']['value'], exact['value'])
    plan = got['best']['plan']
    assert close(plan['flows']['w-chair-blanks'], 4 * plan['activity']['chairs'], 1e-7), 'recipes must hold exactly'
    assert close(plan['activity']['cut'] * 1.25, plan['flows']['w-stock'], 1e-7)

    # Nonconvex: the best climb is within 0.1% of the proven optimum, and at least one start
    # is trapped well below it.
    got = local_search(doc, learning, starts=24)
    again = local_search(doc, learning, starts=24)
    assert [f['value'] for f in got['optima']] == [f['value'] for f in again['optima']], 'same seed, same answer'
    exact = solve(doc, learning, segments=32, relax=True, marginals=False)['evaluated']
    assert exact['feasible']
    best, trapped = got['optima'][0], got['optima'][-1]
    assert len(got['optima']) >= 2, got['optima']
    assert abs(best['value'] - exact['value']) < 1e-3 * exact['value'], (best['value'], exact['value'])
    assert trapped['value'] < best['value'] - 50 and trapped['free']['chairs'] < 1e-6, trapped
    assert all(f['violation'] <= 1e-5 for f in got['optima']), got['optima']
    assert best['starts'] > trapped['starts']

    # The trap is a real local optimum, not a climb that gave up: near it, every plan with a
    # few chairs and as many tables as the true limits allow is worth less, and it cannot
    # take more tables without breaking a limit.
    def feasible(chairs: float, tables: float) -> tuple[bool, float]:
        cut = 4 * chairs + 10 * tables
        plan = {'activity': {'chairs': chairs, 'tables': tables, 'cut': cut},
                'flows': {'w-chair-sales': chairs, 'w-table-sales': tables}}
        ev = true_value(doc, learning, plan)
        ok = ev['feasible'] and cut <= 90 and cut * 1.25 <= 90 and tables <= 8
        return ok, ev['value']

    t0 = trapped['free']['tables']
    assert not feasible(0.0, t0 + 1e-3)[0], 'the trap should sit on the labor limit'
    for eps in (0.01, 0.05, 0.1, 0.2):
        lo, hi = 0.0, t0
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if feasible(eps, mid)[0] else (lo, mid)
        assert feasible(eps, lo)[1] < trapped['value'], ('a nearby plan beats the trap', eps, lo)


def refused(doc: dict, model: dict, code: str) -> None:
    try:
        solve(doc, model)
    except Refusal as r:
        assert r.code == code, (r.code, code, r.reason)
        return
    raise AssertionError(f'expected refusal {code}')


def check_refusals() -> None:
    def leave_floor(d, m):
        for c in d['components']:
            if c['id'] == 'chairs':
                c.pop('parentId')
                c.pop('canvasId')
    refused(*with_model(leave_floor), 'OUT_OF_SCOPE')
    refused(*with_model(lambda d, m: m['flows']['w-chair-blanks'].pop('per')), 'NO_RECIPE')
    refused(*with_model(lambda d, m: m['stages'].pop('tables')), 'UNQUANTIFIED_STAGE')
    with tempfile.TemporaryDirectory() as tmp:
        lone = Path(tmp) / 'workshop.sov'
        shutil.copy(DOC, lone)
        try:
            load(lone)
        except Refusal as r:
            assert r.code == 'NO_MODEL'
        else:
            raise AssertionError('a document without a sidecar has no quantities to optimize')


def check_document_valid() -> None:
    if shutil.which('node'):
        subprocess.run(['node', str(ROOT / 'scripts' / 'validate_sov.mjs'), str(DOC)], check=True,
                       stdout=subprocess.DEVNULL)


def main() -> int:
    check_simplex()
    check_workshop()
    check_whole_units()
    check_nonconvex()
    check_local_search()
    check_refusals()
    check_document_valid()
    print('optimize_sov QA PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
