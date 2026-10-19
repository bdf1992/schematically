"""State space runtime speed (issue #48): the benchmark in examples/state/bench.sov.

Runs bench.sov with bench.inputs.json and budget 20000 under node, three times, each in a fresh
process, and asserts that canonicalize(traceOf(run)) equals examples/state/bench.sovtrace byte for
byte (that trace was recorded by the engine at f676563, before any speed work), that the stored
trace replays, that a refused tick leaves the run exactly as it was, and that the median wall time
of a run (startRun, every step, traceOf and canonicalize) is at most 2.0 s.

Issue #52 adds examples/state/grow.sov: a NOT loop fanning out on two Paths into a queue-merge
Point whose queue grows every period. Its trace at budget 30000 (examples/state/grow.sovtrace) was
recorded by the engine at 6a39efd, before step() stopped copying a queue's items on every tick;
stepping it stays byte-identical, stays linear to budget 100000, and a refused tick leaves it
exactly as it was, the same as the bench.sov case above.

Amendment 1 (round 2): a run is a plain JSON-safe object (STATE-SPACE.md, slice 1b), so it must
keep stepping after a JSON round trip or structuredClone, at any point. ROUND_TRIP runs grow.sov
and bench.sov with a JSON round-trip every 97 steps and a structuredClone every 89 steps, and checks
the resulting trace is still byte-identical to the stored one.
"""
from __future__ import annotations
import json
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'examples/state'
LIMIT_S = 2.0
RUNS = 3
GROW_BUDGET = 100000
# grow.sov's stepping time is held as a multiple of tests/reference_workload.js timed in the same
# process (GROW_TIMED), because GitHub's hosted runners differ by about 2x in raw speed and the CI
# container is slower again: the absolute 3.0 s it replaced passed at 2.3 s and failed at 3.5 s on
# the same engine. The multiple measured on 2026-10-19 (median of three processes):
#   this host (node 24)                       12.6 to 13.8
#   hosted, AMD EPYC 9V74 (node 22)           13.6 to 13.7   (grow.sov 0.99 s)
#   hosted, AMD EPYC 7763 (node 22)           14.9 to 15.7   (grow.sov 1.45 to 1.53 s)
#   hosted CI container, full QA (node 22)    15.75          (grow.sov 3.08 s)
# 20 is the worst of those times 1.27. With a busy-wait in step() adding about 50% to stepping here,
# the multiple measured 21.5 and the test failed; at about +33% it measured 17.5 and passed.
REF = ROOT / 'tests/reference_workload.js'
GROW_RATIO_LIMIT = 20.0

SETUP = r"""
const S=require(process.argv[1]),D=globalThis.SovSchematicData,C=globalThis.SovSchematicCanonical,fs=require('fs');
const dir=process.argv[3];
const pack=S.loadPack(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))).pack,packs=[pack];
const load=()=>D.normalizeDocument(JSON.parse(fs.readFileSync(dir+'/bench.sov','utf8')));
const inputs=JSON.parse(fs.readFileSync(dir+'/bench.inputs.json','utf8'));
const stored=fs.readFileSync(dir+'/bench.sovtrace','utf8');
"""

# One timed run: the same work the before and after figures of #48 measure.
TIMED = SETUP + r"""
const doc=load();
const t0=process.hrtime.bigint();
const s=S.startRun({doc,packs,inputs,budget:20000});if(!s.ok)throw new Error(JSON.stringify(s));
const run=s.run;let last;for(;;){last=S.step(run);if(!last.ok||last.tick===null)break}
const bytes=C.canonicalize(S.traceOf(run));
const ms=Number(process.hrtime.bigint()-t0)/1e6;
process.stdout.write(JSON.stringify({ms,same:bytes===stored,length:bytes.length,last:{ok:last.ok,code:last.code||null,tick:last.tick,left:last.left},through:run.tick,records:run.records.length}));
"""

# Replay of the stored trace, and refused ticks on the benchmark leave the run exactly as it was.
CHECKS = SETUP + r"""
const out={};
const trace=JSON.parse(stored);
const replayed=S.replay({trace,doc:load(),packs});
out.replay={ok:replayed.ok,code:replayed.code||null,same:replayed.ok&&C.canonicalize(replayed.records)===C.canonicalize(trace.records)};
// BUDGET_SPENT in the middle of the run: the refused tick is not applied, twice over.
{
  const run=S.startRun({doc:load(),packs,inputs,budget:5000}).run;let last;
  for(;;){last=S.step(run);if(!last.ok||last.tick===null)break;var text=JSON.stringify(run),canon=C.canonicalize(run)}
  const before=JSON.stringify(run),again=S.step(run);
  out.budget={last:{ok:last.ok,code:last.code},again:JSON.stringify(again)===JSON.stringify(last),exact:JSON.stringify(run)===before,canon:C.canonicalize(run)===canon,sameAsLastCommit:JSON.stringify(run)===text,spent:run.spent};
}
// REPLAY_DIVERGED part way through a tick (a draw is needed and none is recorded): nothing applied.
{
  const run=S.startRun({doc:load(),packs,inputs,budget:20000}).run;run.replayDraws=[];
  let last,before,canon;
  for(let i=0;i<1000;i++){before=JSON.stringify(run);canon=C.canonicalize(run);last=S.step(run);if(!last.ok||last.tick===null)break}
  out.diverged={code:last.code||null,tick:last.tick,exact:JSON.stringify(run)===before,canon:C.canonicalize(run)===canon,through:run.tick};
}
process.stdout.write(JSON.stringify(out));
"""

GROW_SETUP = r"""
const S=require(process.argv[1]),D=globalThis.SovSchematicData,C=globalThis.SovSchematicCanonical,fs=require('fs');
const dir=process.argv[3];
const pack=S.loadPack(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))).pack,packs=[pack];
const load=()=>D.normalizeDocument(JSON.parse(fs.readFileSync(dir+'/grow.sov','utf8')));
const storedGrow=fs.readFileSync(dir+'/grow.sovtrace','utf8');
"""

# Byte-identical to the trace recorded before step() changed, at the budget it was recorded at.
GROW_TRACE = GROW_SETUP + r"""
const run=S.startRun({doc:load(),packs,budget:30000}).run;
let last;while((last=S.step(run)).ok&&last.tick!==null);
const bytes=C.canonicalize(S.traceOf(run));
process.stdout.write(JSON.stringify({same:bytes===storedGrow,length:bytes.length,last:{ok:last.ok,code:last.code||null},through:run.tick}));
"""

# Linear: stepping alone (no traceOf, no canonicalize) to a budget the queue keeps growing under.
# tests/reference_workload.js (REF) is timed in the same process, once untimed, twice before and twice
# after stepping; the middle two of the four are averaged, and grow_ms / ref_ms is what the test holds:
# it measures the engine, not the runner or the load beside it.
GROW_TIMED = GROW_SETUP + r"""
const R=require(process.argv[4]),refs=[];R.time();for(let i=0;i<2;i++)refs.push(R.time());
const doc=load();
const t0=process.hrtime.bigint();
const s=S.startRun({doc,packs,budget:""" + str(GROW_BUDGET) + r"""});if(!s.ok)throw new Error(JSON.stringify(s));
const run=s.run;let last;for(;;){last=S.step(run);if(!last.ok||last.tick===null)break}
const ms=Number(process.hrtime.bigint()-t0)/1e6;
for(let i=0;i<2;i++)refs.push(R.time());
refs.sort((a,b)=>a-b);const ref=(refs[1]+refs[2])/2;
process.stdout.write(JSON.stringify({ms,ref,refs,ratio:ms/ref,last:{ok:last.ok,code:last.code||null,tick:last.tick},through:run.tick}));
"""

# A refused tick part-way through the growing queue leaves the run exactly as it was, twice over.
GROW_CHECKS = GROW_SETUP + r"""
const out={};
const run=S.startRun({doc:load(),packs,budget:5000}).run;let last;
for(;;){last=S.step(run);if(!last.ok||last.tick===null)break;var text=JSON.stringify(run),canon=C.canonicalize(run)}
const before=JSON.stringify(run),again=S.step(run);
out.budget={last:{ok:last.ok,code:last.code},again:JSON.stringify(again)===JSON.stringify(last),exact:JSON.stringify(run)===before,canon:C.canonicalize(run)===canon,sameAsLastCommit:JSON.stringify(run)===text,spent:run.spent};
process.stdout.write(JSON.stringify(out));
"""

# A run is a plain JSON-safe object (STATE-SPACE.md, slice 1b): a JSON round trip every 97 steps, or
# a structuredClone every 89 (argv[7]: 'json' or 'sc'), and stepping continues to the same trace.
# argv[8], when given, is an inputs file (bench.sov is only byte-identical with bench.inputs.json).
ROUND_TRIP = r"""
const S=require(process.argv[1]),D=globalThis.SovSchematicData,C=globalThis.SovSchematicCanonical,fs=require('fs');
const dir=process.argv[3],sov=process.argv[4],traceFile=process.argv[5],budget=Number(process.argv[6]),mode=process.argv[7],inputsFile=process.argv[8];
const pack=S.loadPack(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))).pack,packs=[pack];
const doc=D.normalizeDocument(JSON.parse(fs.readFileSync(dir+'/'+sov,'utf8')));
const inputs=inputsFile?JSON.parse(fs.readFileSync(dir+'/'+inputsFile,'utf8')):[];
const stored=fs.readFileSync(dir+'/'+traceFile,'utf8');
const s=S.startRun({doc,packs,inputs,budget});if(!s.ok)throw new Error(JSON.stringify(s));
let run=s.run,r,n=0;
do{
  if(mode==='json'&&n%97===5)run=JSON.parse(JSON.stringify(run));
  if(mode==='sc'&&n%89===7)run=structuredClone(run);
  r=S.step(run);n++;
}while(r.ok&&r.tick!==null);
const bytes=C.canonicalize(S.traceOf(run));
process.stdout.write(JSON.stringify({same:bytes===stored,length:bytes.length,last:{ok:r.ok,code:r.code||null},through:run.tick,steps:n}));
"""


def node(js: str, *extra: str):
    proc = subprocess.run(['node', '-e', js, str(ROOT / 'src/07-state-space.js'), str(ROOT / 'data/core.logic.pack.json'), str(STATE), *extra],
                          cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def main() -> None:
    runs = [node(TIMED) for _ in range(RUNS)]
    for r in runs:
        assert r['same'], f"the benchmark trace differs from examples/state/bench.sovtrace ({r['length']} bytes)"
        assert r['last'] == {'ok': False, 'code': 'BUDGET_SPENT', 'tick': 496, 'left': 37} and r['through'] == 495 and r['records'] == 19840, r
    median_s = statistics.median(r['ms'] for r in runs) / 1000
    times = ', '.join('%.3f' % (r['ms'] / 1000) for r in runs)
    print(f'bench.sov: {times} s; median {median_s:.3f} s (limit {LIMIT_S} s)')
    assert median_s <= LIMIT_S, f'the benchmark median {median_s:.3f} s exceeds {LIMIT_S} s'

    c = node(CHECKS)
    assert c['replay'] == {'ok': True, 'code': None, 'same': True}, c['replay']
    b = c['budget']
    assert b['last'] == {'ok': False, 'code': 'BUDGET_SPENT'} and b['again'] and b['exact'] and b['canon'] and b['sameAsLastCommit'], b
    d = c['diverged']
    assert d['code'] == 'REPLAY_DIVERGED' and d['exact'] and d['canon'], d

    # Issue #52: grow.sov, the growing-queue case.
    gt = node(GROW_TRACE)
    assert gt['same'], f"the grow trace differs from examples/state/grow.sovtrace ({gt['length']} bytes)"
    assert gt['last'] == {'ok': False, 'code': 'BUDGET_SPENT'}, gt
    grow_runs = [node(GROW_TIMED, str(REF)) for _ in range(RUNS)]
    for r in grow_runs:
        assert r['last']['ok'] is False and r['last']['code'] == 'BUDGET_SPENT', r
    grow_median_s = statistics.median(r['ms'] for r in grow_runs) / 1000
    ref_median_s = statistics.median(r['ref'] for r in grow_runs) / 1000
    ratio = statistics.median(r['ratio'] for r in grow_runs)
    grow_times = ', '.join('%.3f' % (r['ms'] / 1000) for r in grow_runs)
    ratios = ', '.join('%.2f' % r['ratio'] for r in grow_runs)
    print(f'grow.sov: {grow_times} s; median {grow_median_s:.3f} s, through tick {grow_runs[-1]["through"]}')
    print(f'grow.sov / reference ({ref_median_s:.3f} s): {ratios}; median {ratio:.2f} (limit {GROW_RATIO_LIMIT})')
    assert ratio <= GROW_RATIO_LIMIT, (f'stepping grow.sov to budget {GROW_BUDGET} took a median {ratio:.2f} times the reference '
                                       f'workload ({grow_median_s:.3f} s against {ref_median_s:.3f} s), over {GROW_RATIO_LIMIT}')
    gc = node(GROW_CHECKS)
    gb = gc['budget']
    assert gb['last'] == {'ok': False, 'code': 'BUDGET_SPENT'} and gb['again'] and gb['exact'] and gb['canon'] and gb['sameAsLastCommit'], gb

    # Amendment 1: a run stays a plain JSON-safe object through a round trip, at any step.
    for sov, trace_file, budget, inputs_file in (
        ('grow.sov', 'grow.sovtrace', 30000, None),
        ('bench.sov', 'bench.sovtrace', 20000, 'bench.inputs.json'),
    ):
        for mode in ('json', 'sc'):
            rt = node(ROUND_TRIP, sov, trace_file, str(budget), mode, inputs_file or '')
            assert rt['same'], f"{sov} round-tripped through {mode} diverges from {trace_file} ({rt['length']} bytes)"
            print(f"{sov} round-trip ({mode}): byte-identical to {trace_file} through tick {rt['through']} ({rt['steps']} steps)")

    print('PASS state space perf QA')


if __name__ == '__main__':
    main()
