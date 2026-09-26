"""State space runtime speed (issue #48): the benchmark in examples/state/bench.sov.

Runs bench.sov with bench.inputs.json and budget 20000 under node, three times, each in a fresh
process, and asserts that canonicalize(traceOf(run)) equals examples/state/bench.sovtrace byte for
byte (that trace was recorded by the engine at f676563, before any speed work), that the stored
trace replays, that a refused tick leaves the run exactly as it was, and that the median wall time
of a run (startRun, every step, traceOf and canonicalize) is at most 2.0 s.
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


def node(js: str):
    proc = subprocess.run(['node', '-e', js, str(ROOT / 'src/07-state-space.js'), str(ROOT / 'data/core.logic.pack.json'), str(STATE)],
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
    print('PASS state space perf QA')


if __name__ == '__main__':
    main()
