"""Throughput optimization QA.

`scripts/optimize_sov.py` claims three things, and each is checked here against a path the
solver did not choose:

  - the simplex returns the textbook optimum and shadow prices on problems whose answers are
    known (Wyndor Glass, an equality with a floor, Beale's cycling example), and names
    infeasible and unbounded problems instead of returning a plan;
  - a shadow price is what the objective actually gains when its limit is relaxed a little
    (finite difference, not the tableau reading back its own number);
  - on the workshop example, the nonlinear plan is feasible under the true curves, the linear
    plan is not, refining the breakpoints only raises the value and converges, and the
    refusals fire for an out-of-scope resource, a nonconvex bend and a missing recipe.
"""
from __future__ import annotations

import copy
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from optimize_sov import Refusal, load, simplex, solve  # noqa: E402

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
    linear = solve(doc, model, linear=True)
    bent = solve(doc, model)
    assert not linear['evaluated']['feasible'], 'the linear plan should overrun labor once congestion is real'
    assert bent['evaluated']['feasible'], bent['evaluated']
    assert bent['evaluated']['value'] > linear['evaluated']['value'], (bent['evaluated'], linear['evaluated'])
    assert bent['plan']['activity']['chairs'] > 0 and bent['plan']['activity']['tables'] > 0, \
        'saturation should make the plan mix products; the linear plan picks one'

    values = [solve(doc, model, segments=s)['evaluated']['value'] for s in (4, 16, 64, 256)]
    assert all(b >= a - 1e-6 for a, b in zip(values, values[1:])), values
    assert values[-1] - values[-2] < 0.005 * values[-1], values

    # A shadow price is the gain per unit of relaxation: check it by relaxing.
    price = bent['shadow_price']['resource']['labor']
    assert price > 0, 'labor binds in the example'
    _, more = with_model(lambda d, m: m['resources']['labor'].update(limit=m['resources']['labor']['limit'] + 0.05))
    gained = (solve(doc, more)['objective'] - bent['objective']) / 0.05
    assert abs(gained - price) < 0.05 * price, (gained, price)
    assert close(bent['shadow_price']['supply']['timber'], 0), 'timber is slack; it should be free at the margin'


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
    check_refusals()
    check_document_valid()
    print('optimize_sov QA PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
