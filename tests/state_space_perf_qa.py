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
# grow.sov's stepping time is held as a multiple of REF (see GROW_TIMED), because GitHub's hosted
# runners differ from each other by about 2x in raw speed. The limit and its evidence are below main().
REF_N = 22222
REF_HEAD = '2182e55791ba9beba28caf0436391a73b56df744edd3d2b99c2d097ab295425e'
GROW_RATIO_LIMIT = 4.0

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
# REF is a fixed piece of plain JavaScript shaped like stepping grow.sov, and it never calls the
# engine: per tick a few small records, a Map of Sets, a canonical (sorted-key) encoding, a SHA-256
# chained on the previous hash, and everything kept, so the heap grows as a run's does. It is timed in the same
# process three times before and three times after stepping, after one untimed warm-up, and its
# median is the yardstick: grow_ms / ref_ms measures the engine, not the machine it runs on.
GROW_TIMED = GROW_SETUP + r"""
const REF=n=>{
const K=new Uint32Array([0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]);
const W=new Uint32Array(64);
const sha=b=>{const l=b.length,m=new Uint8Array(((l+9+63)>>6)<<6);m.set(b);m[l]=0x80;const bits=l*8;m[m.length-4]=bits>>>24;m[m.length-3]=bits>>>16;m[m.length-2]=bits>>>8;m[m.length-1]=bits;
let h0=0x6a09e667,h1=0xbb67ae85,h2=0x3c6ef372,h3=0xa54ff53a,h4=0x510e527f,h5=0x9b05688c,h6=0x1f83d9ab,h7=0x5be0cd19;
for(let o=0;o<m.length;o+=64){for(let i=0;i<16;i++)W[i]=m[o+4*i]<<24|m[o+4*i+1]<<16|m[o+4*i+2]<<8|m[o+4*i+3];
for(let i=16;i<64;i++){const a=W[i-15],c=W[i-2];W[i]=((a>>>7|a<<25)^(a>>>18|a<<14)^a>>>3)+W[i-7]+((c>>>17|c<<15)^(c>>>19|c<<13)^c>>>10)+W[i-16]}
let a=h0,b2=h1,c=h2,d=h3,e=h4,f=h5,g=h6,h=h7;
for(let i=0;i<64;i++){const t1=h+((e>>>6|e<<26)^(e>>>11|e<<21)^(e>>>25|e<<7))+(e&f^~e&g)+K[i]+W[i]|0,t2=((a>>>2|a<<30)^(a>>>13|a<<19)^(a>>>22|a<<10))+(a&b2^a&c^b2&c)|0;h=g;g=f;f=e;e=d+t1|0;d=c;c=b2;b2=a;a=t1+t2|0}
h0=h0+a|0;h1=h1+b2|0;h2=h2+c|0;h3=h3+d|0;h4=h4+e|0;h5=h5+f|0;h6=h6+g|0;h7=h7+h|0}
return [h0,h1,h2,h3,h4,h5,h6,h7].map(x=>(x>>>0).toString(16).padStart(8,'0')).join('')};
const enc=v=>v===null||typeof v!=='object'?JSON.stringify(v):Array.isArray(v)?'['+v.map(enc).join(',')+']':'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+enc(v[k])).join(',')+'}';
const utf8=s=>{const b=new Uint8Array(s.length);for(let i=0;i<s.length;i++)b[i]=s.charCodeAt(i)&127;return b};
let t0=process.hrtime.bigint();const kept=[];let head='',seen=new Map();
for(let i=0;i<n;i++){const recs=[];for(let j=0;j<3+(i&1);j++){const rec={tick:i,entity:'e'+((i*31+j)%977),point:'p'+j,kind:'signal',value:{n:(i^j)&255,at:[i,j]}};
if(!seen.has(rec.entity))seen.set(rec.entity,new Set());seen.get(rec.entity).add(rec.point);recs.push(rec)}
const body=enc({after:i,records:recs,prev:head});head=sha(utf8(body));kept.push({hash:head,records:recs.map(r=>({...r}))})}
if(head!==""" + json.dumps(REF_HEAD) + r""")throw new Error('reference workload head '+head);
return Number(process.hrtime.bigint()-t0)/1e6};
const refs=[];REF(""" + str(REF_N) + r""");for(let i=0;i<3;i++)refs.push(REF(""" + str(REF_N) + r"""));
const doc=load();
const t0=process.hrtime.bigint();
const s=S.startRun({doc,packs,budget:""" + str(GROW_BUDGET) + r"""});if(!s.ok)throw new Error(JSON.stringify(s));
const run=s.run;let last;for(;;){last=S.step(run);if(!last.ok||last.tick===null)break}
const ms=Number(process.hrtime.bigint()-t0)/1e6;
for(let i=0;i<3;i++)refs.push(REF(""" + str(REF_N) + r"""));
refs.sort((a,b)=>a-b);const ref=(refs[2]+refs[3])/2;
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
    grow_runs = [node(GROW_TIMED) for _ in range(RUNS)]
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
