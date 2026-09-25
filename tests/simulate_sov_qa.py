"""Whole-unit simulation and saved state QA.

`scripts/simulate_sov.py` claims:

  - units exist only when the completion gate fires, and it fires only when every material
    and every piece of work is complete; nothing partial is ever counted;
  - executing the optimizer's whole-unit plan completes exactly that plan, and the work it
    takes adds up to the optimizer's true-curve usage (the per-unit steps telescope);
  - counts can be rebuilt from the event log alone, and events are strictly ordered;
  - saving a state and running the next horizon from it equals running both without stopping;
  - a save is refused against a document or model other than the one it names.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from optimize_sov import Refusal, solve  # noqa: E402
from simulate_sov import (Workshop, dump_state, expand_targets, load_state, new_state, plan_targets,  # noqa: E402
                          replay_counts, run_horizon)

DIR = ROOT / 'examples' / 'optimization'
DOC = DIR / 'workshop.sov'
LEARNING = DIR / 'workshop.learning.opt.json'


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def check_plan_executes(model: Path | None) -> None:
    ws = Workshop(DOC, model)
    # Twenty segments put a breakpoint on every whole chair, so the plan is exact at whole units.
    plan = solve(ws.doc, ws.model, segments=20, marginals=False)
    targets = {s: round(v) for s, v in plan['plan']['activity'].items()}
    assert targets == plan_targets(ws, segments=20)
    state = run_horizon(ws, new_state(ws), targets)
    assert state['events'][-1]['kind'] == 'met', state['events'][-1]
    for stage in ('chairs', 'tables'):
        assert state['stages'][stage]['completed'] == round(plan['plan']['activity'][stage]), stage
    assert state['counts']['w-chair-sales'] == round(plan['plan']['flows']['w-chair-sales'])
    assert state['counts']['w-table-sales'] == round(plan['plan']['flows']['w-table-sales'])
    assert all(isinstance(v, int) for v in state['counts'].values())
    # The n-th unit takes the curve's n-th step, so the horizon's work is the curve itself.
    assert close(state['resources']['labor']['used'], plan['evaluated']['usage']['labor']['used']), \
        (state['resources']['labor']['used'], plan['evaluated']['usage']['labor']['used'])
    check_log(state)


def check_log(state: dict) -> None:
    events = state['events']
    assert [e['seq'] for e in events] == list(range(events[0]['seq'], events[0]['seq'] + len(events))), 'gaps in sequence'
    assert all(a['t'] <= b['t'] for a, b in zip(events, events[1:])), 'time went backwards'
    counts, completed = replay_counts(events)
    assert counts == {w: n for w, n in state['counts'].items() if n}, (counts, state['counts'])
    assert completed == {s: st['completed'] for s, st in state['stages'].items() if st['completed']}
    for e in events:
        if e['kind'] == 'completed':
            assert e['signals'] and all(v == 1 for v in e['signals'].values()), e
        if e['kind'] == 'work':
            assert all(0 < p < 1 for p in e['progress'].values() if p < 1), e


def check_partial_is_not_counted() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc, model = copy_pair(Path(tmp))
        m = json.loads(model.read_text())
        m['resources']['labor']['limit'] = 10
        model.write_text(json.dumps(m))
        ws = Workshop(doc, model)
        state = run_horizon(ws, new_state(ws), {'chairs': 2, 'tables': 5, 'cut': 58})
        last = state['events'][-1]
        assert last['kind'] == 'stalled', last
        assert close(state['resources']['labor']['used'], 10.0)
        wip = [(s, st['wip']) for s, st in state['stages'].items() if st['wip'] and st['wip']['work']]
        assert len(wip) == 1, wip
        stage, unit = wip[0]
        done = [w['done'] / w['need'] for w in unit['work'].values()]
        assert all(0 < d < 1 for d in done), done
        # The unit in progress exists as state only: it is not in stock and not counted.
        before = state['stages'][stage]['completed']
        assert replay_counts(state['events'])[1].get(stage, 0) == before
        check_log(state)


def check_save_and_resume() -> None:
    ws = Workshop(DOC, LEARNING)
    targets = expand_targets(ws, {'chairs': 14, 'tables': 2})
    straight = new_state(ws)
    for _ in range(3):
        run_horizon(ws, straight, targets)
    with tempfile.TemporaryDirectory() as tmp:
        sav = Path(tmp) / 'week.sav'
        state = new_state(ws)
        for _ in range(3):
            if sav.exists():
                state = load_state(ws, sav)
            run_horizon(ws, state, targets)
            sav.write_text(dump_state(state), encoding='utf-8', newline='\n')
        resumed = json.loads(sav.read_text(encoding='utf-8'))
    assert dump_state(resumed) == dump_state(straight), 'a save and resume must equal running straight through'
    # These targets need more timber than a week brings: work carries between horizons.
    carried = [e for e in straight['events'] if e['kind'] == 'horizon' and e['horizon'] > 1]
    assert carried and any(e['kind'] == 'stalled' for e in straight['events'])
    check_log(straight)


def check_committed_save() -> None:
    # The example save is week one of the learning workshop at the fractional optimum rounded
    # up: timber runs out with a table part-kitted. It must still load against the committed
    # document and model, and week two must finish that table first.
    ws = Workshop(DOC, LEARNING)
    state = load_state(ws, DIR / 'workshop.learning.week1.sav')
    table = state['stages']['tables']['wip']
    assert table and 0 < table['materials']['w-table-blanks'] < 10, table
    run_horizon(ws, state, expand_targets(ws, {'chairs': 14, 'tables': 2}))
    week2 = [e for e in state['events'] if e['horizon'] == 2]
    first = next(e for e in week2 if e['kind'] == 'completed' and e['stage'] == 'tables')
    assert first['unit'] == 2, first
    check_log(state)


def copy_pair(tmp: Path) -> tuple[Path, Path]:
    doc, model = tmp / 'workshop.sov', tmp / 'workshop.opt.json'
    shutil.copy(DOC, doc)
    shutil.copy(DIR / 'workshop.opt.json', model)
    return doc, model


def refused(fn, code: str) -> None:
    try:
        fn()
    except Refusal as r:
        assert r.code == code, (r.code, code)
        return
    raise AssertionError(f'expected refusal {code}')


def check_refusals() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc, model = copy_pair(Path(tmp))
        ws = Workshop(doc, model)
        sav = Path(tmp) / 'a.sav'
        sav.write_text(dump_state(run_horizon(ws, new_state(ws), plan_targets(ws))))
        m = json.loads(model.read_text())
        m['resources']['labor']['limit'] = 41
        model.write_text(json.dumps(m))
        refused(lambda: load_state(Workshop(doc, model), sav), 'MODEL_CHANGED')
        shutil.copy(DIR / 'workshop.opt.json', model)
        d = json.loads(doc.read_text())
        d['meta']['title'] = 'edited'
        doc.write_text(json.dumps(d))
        refused(lambda: load_state(Workshop(doc, model), sav), 'DOCUMENT_CHANGED')
        shutil.copy(DOC, doc)
        m = json.loads(model.read_text())
        m['flows']['w-chair-blanks']['per'] = 4.5
        model.write_text(json.dumps(m))
        refused(lambda: Workshop(doc, model), 'FRACTIONAL_RECIPE')


def main() -> int:
    check_plan_executes(None)
    check_plan_executes(LEARNING)
    check_partial_is_not_counted()
    check_save_and_resume()
    check_committed_save()
    check_refusals()
    print('simulate_sov QA PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
