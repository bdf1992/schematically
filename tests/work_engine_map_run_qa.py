"""The Work Engine map runs (docs/workengine/GAPS.md, The map runs).

docs/workengine/run_map.py writes a runnable copy of docs/workengine/map.sov: records are asserted
sources, queries are derived AND cards over their backs wires, and two scenarios are stored in the
document. This test computes the rule from docs/workengine/source/gapmap.json alone and checks:

(a) run_map.py --out writes a file node scripts/validate_sov.mjs accepts, the same bytes on a second
    run, LF only; without config.signal on its we-record and we-specification cards and without the
    two scenario references it is the JSON of map.sov;
(b) the signal of every record and every query is the rule's;
(c) under node, runScenario on each stored scenario returns ok true with every check passing;
(d) under node, after createSimulation and advance(100), every query's level is the rule's; then, for
    the first derived query in map order at level 0, setting each of its off records to 1 and
    advancing 100 turns it to 1 and leaves every query that names none of those records unchanged;
(e) run_map.py --list exits 0 and its DISAGREE lines name exactly the queries the rule gives;
(f) the bytes of docs/workengine/map.sov are the same before and after.

Node and Python only. Starts no browser.
"""
from __future__ import annotations
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'docs' / 'workengine'
MAP = WORK / 'map.sov'
RUN_MAP = WORK / 'run_map.py'
SCENARIOS = ('s-as-read', 's-all-records-exist')

# The cores in the order MODULES.md gives, as tests/run_spectrum_qa.py requires the surface.
NODE_RUN = r'''
const fs=require('fs'),path=require('path');
const root=process.argv[1],doc=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),sets=JSON.parse(process.argv[3]);
let Surface=null;
for(const name of ['03-canonical.js','03-notation-core.js','06-attachment-core.js','05-data-core.js','07-state-space.js','07-state-surface.js'])Surface=require(path.join(root,'src',name));
const scenarios={};
for(const ref of doc.references.filter(r=>r.kind==='scenario')){const r=Surface.runScenario(doc,ref);scenarios[ref.id]={ok:r.ok,code:r.code||null,message:r.message||null,checks:r.checks||[]}}
const made=Surface.createSimulation(doc);if(!made.ok)throw new Error(JSON.stringify(made));
const sim=made.sim,flat=()=>Object.fromEntries(Object.entries(sim.levels()).map(([id,l])=>[id,{value:l.value,mode:l.mode,kind:l.kind}]));
const first=sim.advance(100);if(!first.ok)throw new Error(JSON.stringify(first));
const before=flat();
const setResults=sets.map(id=>sim.set(id,1));
const second=sim.advance(100);if(!second.ok)throw new Error(JSON.stringify(second));
fs.writeFileSync(process.argv[4],JSON.stringify({scenarios,before,setResults,after:flat()}));
'''


def backing(text: str) -> list[str]:
    """The names a query's backing lists: bracketed notes dropped, a field after a dot dropped."""
    names = [part.split('.')[0].strip() for part in re.sub(r'\s*\(.*?\)', '', text).split(',')]
    return [n for n in names if n]


def rule(gap: dict) -> tuple[dict, list[dict]]:
    """From the gap map alone: record name -> on, and per query its names, the records they
    resolve to (None when the gap map holds none), whether it is derived, and its level."""
    on = {r['name']: r['status'] == 'exists' for r in gap['records']}
    before_slash = {r['name'].split(' / ')[0]: r['name'] for r in gap['records'] if ' / ' in r['name']}
    queries = []
    for q in gap['queries']:
        names = backing(q['backing'])
        resolved = []
        for n in names:
            n = before_slash.get(n, n)
            resolved.append(n if n in on else None)
        derived = all(r is not None for r in resolved)
        level = 1 if all(r is not None and on[r] for r in resolved) else 0
        queries.append({'needs': q['needs'], 'status': q['status'], 'names': names, 'resolved': resolved,
                        'derived': derived, 'level': level})
    return on, queries


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')


def main() -> None:
    map_bytes = MAP.read_bytes()
    map_hash = hashlib.sha256(map_bytes).hexdigest()
    source = json.loads(map_bytes.decode('utf-8'))
    gap = json.loads((WORK / 'source' / 'gapmap.json').read_text(encoding='utf-8'))
    on, queries = rule(gap)

    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        out_file, again = td / 'map-run.sov', td / 'map-run-again.sov'
        for target in (out_file, again):
            made = run([sys.executable, str(RUN_MAP), '--out', str(target)])
            assert made.returncode == 0, made.stdout + made.stderr
        raw = out_file.read_bytes()
        assert raw == again.read_bytes(), '(a) two runs of run_map.py --out wrote different bytes'
        assert b'\r' not in raw and raw.endswith(b'\n'), '(a) the copy is not LF with a final newline'
        doc = json.loads(raw.decode('utf-8'))
        assert raw.decode('utf-8') == json.dumps(doc, indent=1, ensure_ascii=False) + '\n', '(a) the copy is not json.dumps indent 1'

        # (a) the validator accepts it, and without the signals and scenarios it is map.sov.
        valid = run(['node', str(ROOT / 'scripts' / 'validate_sov.mjs'), str(out_file)])
        assert valid.returncode == 0, '(a) validate_sov.mjs refuses the copy: ' + valid.stdout + valid.stderr
        stripped = json.loads(raw.decode('utf-8'))
        signalled = 0
        for c in stripped['components']:
            if c.get('symbolId') in ('we-record', 'we-specification'):
                assert 'signal' in c['config'], f"(a) {c['id']} carries no config.signal"
                del c['config']['signal']
                signalled += 1
        assert [r['id'] for r in stripped['references'][-2:]] == list(SCENARIOS), '(a) the last two references are not the two scenarios'
        assert all(r['kind'] == 'scenario' for r in stripped['references'][-2:])
        del stripped['references'][-2:]
        assert stripped == source, '(a) the copy differs from map.sov beyond the signals and the two scenarios'
        assert signalled == len(gap['records']) + len(gap['queries']), signalled
        print(f"(a) validate_sov accepts the copy; {signalled} signals and 2 scenarios removed give map.sov")

        cards = lambda symbol: {c['config']['label']: c for c in doc['components'] if c.get('symbolId') == symbol}
        record_cards, query_cards = cards('we-record'), cards('we-specification')
        assert len(record_cards) == len(gap['records']) and len(query_cards) == len(gap['queries'])
        for q in queries:
            q['id'] = query_cards[q['needs']]['id']
        record_id = {name: record_cards[name]['id'] for name in on}

        # Map order: the order of the we-specification cards in the document.
        by_id = {q['id']: q for q in queries}
        in_map = [by_id[c['id']] for c in doc['components'] if c.get('symbolId') == 'we-specification']
        target = next(q for q in in_map if q['derived'] and q['level'] == 0)
        off_records = [r for r in dict.fromkeys(target['resolved']) if not on[r]]
        node_out = td / 'node.json'
        proc = subprocess.run(['node', '-e', NODE_RUN, str(ROOT), str(out_file), json.dumps([record_id[r] for r in off_records]), str(node_out)],
                              cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        assert proc.returncode == 0, proc.stdout + proc.stderr
        ran = json.loads(node_out.read_text(encoding='utf-8'))

    # (b) to (e) are each run whatever the others found, so a failure names every assertion it breaks.
    def signals():
        for name, high in on.items():
            want = {'mode': 'asserted', 'kind': 'binary', 'value': 1 if high else 0}
            got = record_cards[name]['config']['signal']
            assert got == want, f'(b) record {name!r} has signal {got}, the rule gives {want}'
        for q in queries:
            want = {'mode': 'derived', 'kind': 'binary', 'combine': 'and'} if q['derived'] else {'mode': 'asserted', 'kind': 'binary', 'value': 0}
            got = query_cards[q['needs']]['config']['signal']
            assert got == want, f"(b) query {q['needs']!r} has signal {got}, the rule gives {want}"
        derived = [q for q in queries if q['derived']]
        print(f"(b) signals follow the rule: {sum(on.values())} records on, {len(on) - sum(on.values())} off; "
              f"{len(derived)} queries derived, {len(queries) - len(derived)} asserted at 0")

    def scenarios():
        assert sorted(ran['scenarios']) == sorted(SCENARIOS), sorted(ran['scenarios'])
        checks = 0
        for sid in SCENARIOS:
            sc = ran['scenarios'][sid]
            failed = [c for c in sc['checks'] if not c['pass']]
            assert sc['ok'] is True and not failed, (f"(c) scenario {sid} does not pass: {sc['code']} {sc['message']}; "
                                                     f"{len(failed)} of {len(sc['checks'])} checks fail, first {failed[:3]}")
            assert len(sc['checks']) == len(queries), f"(c) scenario {sid} checks {len(sc['checks'])} levels, not {len(queries)}"
            checks += len(sc['checks'])
        print(f"(c) runScenario: {len(SCENARIOS)} scenarios ok, {checks} checks pass")

    def levels():
        before, after = ran['before'], ran['after']
        for q in queries:
            got = before[q['id']]
            assert got['value'] == q['level'], f"(d) {q['id']} runs at {got['value']}, the rule gives {q['level']}"
            assert got['mode'] == ('derived' if q['derived'] else 'asserted') and got['kind'] == 'binary', (q['id'], got)
        for name, high in on.items():
            assert before[record_id[name]]['value'] == (1 if high else 0), f'(d) record {name!r} runs at {before[record_id[name]]}'
        assert off_records, target
        assert all(r['ok'] and r['value'] == 1 and r['changed'] for r in ran['setResults']), ran['setResults']
        assert before[target['id']]['value'] == 0 and after[target['id']]['value'] == 1, f"(d) {target['id']} did not turn on: {before[target['id']]} -> {after[target['id']]}"
        apart = [q for q in queries if not set(q['resolved']) & set(off_records)]
        assert apart and len(apart) < len(queries)
        for q in apart:
            assert after[q['id']]['value'] == before[q['id']]['value'], f"(d) {q['id']} names none of {off_records} and moved"
        print(f"(d) {len(queries)} query levels equal the rule ({sum(q['level'] for q in queries)} on); "
              f"{target['id']} turns on when {', '.join(off_records)} is set; {len(apart)} queries naming none of them hold")

    def listing():
        want = [q['id'] for q in in_map
                if (q['status'] == 'exists' and q['level'] == 0) or (q['status'] in ('partial', 'missing') and q['level'] == 1)]
        listed = run([sys.executable, str(RUN_MAP), '--list'])
        assert listed.returncode == 0, '(e) run_map.py --list exits ' + str(listed.returncode) + ': ' + listed.stdout + listed.stderr
        lines = listed.stdout.splitlines()
        rows = lines[:-1]
        assert len(rows) == len(queries) and [r.split()[1] for r in rows] == [q['id'] for q in in_map], '(e) the listing is not one line per query in map order'
        assert all(r.split()[0] in ('agree', 'DISAGREE') for r in rows)
        got = [r.split()[1] for r in rows if r.startswith('DISAGREE ')]
        assert got == want, f'(e) the listing disagrees on {got}, the rule gives {want}'
        assert lines[-1] == f'disagreements: {len(want)} of {len(queries)}', lines[-1]
        for r in rows:
            if r.startswith('DISAGREE '):
                print('    ' + r)
        print(f"(e) run_map.py --list: {lines[-1]}")

    failures = []
    for letter, check in (('b', signals), ('c', scenarios), ('d', levels), ('e', listing)):
        try:
            check()
        except AssertionError as exc:
            failures.append(letter)
            print(f'FAIL ({letter}) {exc}')

    # (f) map.sov is untouched.
    assert hashlib.sha256(MAP.read_bytes()).hexdigest() == map_hash, '(f) docs/workengine/map.sov changed during the test'
    print(f"(f) map.sov unchanged: sha256 {map_hash[:16]}")
    assert not failures, 'assertions failed: ' + ', '.join(f'({x})' for x in failures)
    print('PASS work engine map run QA')


if __name__ == '__main__':
    main()
