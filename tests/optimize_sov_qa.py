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
from optimize_sov import Refusal, branch_and_bound, build, load, simplex, solve  # noqa: E402

DOC = ROOT / 'examples' / 'optimization' / 'workshop.sov'


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
    refused(*with_model(lambda d, m: m['flows']['w-table-sales'].update(effect={'kind': 'economies', 'power': 1.3})),
            'NONCONVEX')
    refused(*with_model(lambda d, m: m['stages']['cut']['effects'].update(labor={'kind': 'economies', 'power': 0.8})),
            'NONCONVEX')
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
    check_refusals()
    check_document_valid()
    print('optimize_sov QA PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
