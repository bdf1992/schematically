"""Canonical identity: RFC 8785 (JCS) encoding, pure-JS SHA-256, the seeded draw and
`documentHash`.

`03-canonical.js` is the one place the runtime turns a JSON value or a document into
bytes it can hash or draw an order from; every consumer (the data core, the future
state-space engine, the trace format) stands on it staying correct against published
vectors, not against its own prior output. Node only; no browser.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

JS = r"""
const crypto=require('crypto');
const fs=require('fs');
const path=require('path');
const C=require(process.argv[1]);
const D=require(process.argv[2]);
const examplesDir=process.argv[3];

const out={};

// --- SHA-256 against the NIST vectors ---
out.sha_empty=C.sha256Hex('');
out.sha_abc=C.sha256Hex('abc');
out.sha_448=C.sha256Hex('abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq');
out.sha_million_a=C.sha256Hex('a'.repeat(1000000));

// --- SHA-256 against node's crypto, for random strings including non-BMP characters ---
function randomCodePoint(){
  const bucket=Math.random();
  if(bucket<0.6)return Math.floor(Math.random()*0x7F)+1;
  if(bucket<0.85){
    let cp;
    do{cp=Math.floor(Math.random()*0xFFFF)}while(cp>=0xD800&&cp<=0xDFFF);
    return cp;
  }
  return 0x10000+Math.floor(Math.random()*(0x10FFFF-0x10000+1));
}
function randomString(forceNonBmp){
  const len=Math.floor(Math.random()*40);
  let s=forceNonBmp?String.fromCodePoint(0x10000+Math.floor(Math.random()*(0x10FFFF-0x10000+1))):'';
  for(let i=0;i<len;i++)s+=String.fromCodePoint(randomCodePoint());
  return s;
}
let shaMismatches=0,nonBmpCovered=0;
for(let i=0;i<200;i++){
  const s=randomString(i%5===0);
  if(/[\u{10000}-\u{10FFFF}]/u.test(s))nonBmpCovered++;
  const ours=C.sha256Hex(s);
  const theirs=crypto.createHash('sha256').update(Buffer.from(s,'utf8')).digest('hex');
  if(ours!==theirs){shaMismatches++;if(shaMismatches<=3)out['mismatch'+shaMismatches]={s,ours,theirs}}
}
out.shaMismatches=shaMismatches;
out.nonBmpCovered=nonBmpCovered;

// --- canonicalize: RFC 8785 examples ---
// Section 3.2.2/3.2.3 number example, with plain ASCII keys so key order is unambiguous.
out.rfcNumbers=C.canonicalize({numbers:[333333333.33333329,1E30,4.50,2e-3,0.000000000000000000000000001],literals:[null,true,false],extra:'x'});
// Section 3.2.3 property-order example (unicode keys sorted by UTF-16 code unit).
const unicodeKeysObj={};
unicodeKeysObj['€']='Euro Sign';
unicodeKeysObj['\r']='Carriage Return';
unicodeKeysObj['דּ']='Hebrew Letter Dalet With Dagesh';
unicodeKeysObj['1']='One';
unicodeKeysObj['😀']='Emoji: Grinning Face';
unicodeKeysObj['\u0080']='Control';
unicodeKeysObj['ö']='Latin Small Letter O With Diaeresis';
const unicodeCanonical=C.canonicalize(unicodeKeysObj);
out.unicodeCanonical=unicodeCanonical;
out.unicodeKeyOrder=[...unicodeCanonical.matchAll(/"((?:[^"\\]|\\.)*)":"/g)].map(m=>JSON.parse('"'+m[1]+'"'));

// --- canonicalize: unsupported values throw CANONICAL_UNSUPPORTED ---
function code(fn){try{fn();return null}catch(e){return e.code||null}}
out.codes={
  nan:code(()=>C.canonicalize(NaN)),
  posInf:code(()=>C.canonicalize(Infinity)),
  negInf:code(()=>C.canonicalize(-Infinity)),
  undef:code(()=>C.canonicalize(undefined)),
  fn:code(()=>C.canonicalize(function(){})),
  sym:code(()=>C.canonicalize(Symbol('x'))),
  bigint:code(()=>C.canonicalize(1n)),
  date:code(()=>C.canonicalize(new Date())),
  map:code(()=>C.canonicalize(new Map())),
  nested:code(()=>C.canonicalize({a:[1,undefined,2]})),
};

// --- drawOrder ---
out.permutation=C.drawOrder('seed-1',['k'],[1,2,3,4,5]).slice().sort((a,b)=>a-b);
const forward=C.drawOrder('seed-1',['k'],[1,2,3,4,5]);
const reversed=C.drawOrder('seed-1',['k'],[5,4,3,2,1]);
const shuffled=C.drawOrder('seed-1',['k'],[3,1,4,2,5]);
out.orderIndependent=JSON.stringify(forward)===JSON.stringify(reversed)&&JSON.stringify(forward)===JSON.stringify(shuffled);
const variants=new Set();
for(let i=0;i<20;i++)variants.add(JSON.stringify(C.drawOrder('seed-1',[i],[1,2,3,4,5])));
out.distinctForDifferentKeys=variants.size;

const counts={};
for(let i=0;i<60000;i++){
  const order=C.drawOrder(i,[],[10,20,30]);
  const key=order.join(',');
  counts[key]=(counts[key]||0)+1;
}
out.drawCounts=counts;
out.drawOrderKeys=Object.keys(counts).length;

// --- documentHash ---
const base=D.documentFromFilePayload(JSON.parse(fs.readFileSync(path.join(examplesDir,'01-source-hold.sov'),'utf8')));
const h0=D.documentHash(base);
const revBumped=D.clone(base);revBumped.revision=(revBumped.revision||0)+37;
out.hashRevision={before:h0,after:D.documentHash(revBumped)};
const touched=D.clone(base);touched.meta=touched.meta||{};touched.meta.updatedAt='2099-01-01T00:00:00.000Z';
out.hashUpdatedAt={before:h0,after:D.documentHash(touched)};
const saved=D.clone(base);saved.meta=saved.meta||{};saved.meta.savedAt='2099-01-01T00:00:00.000Z';
out.hashSavedAt={before:h0,after:D.documentHash(saved)};
const checkpointed=D.clone(base);checkpointed.meta=checkpointed.meta||{};checkpointed.meta.checkpoints=[{label:'cp',document:D.clone(base)}];
out.hashCheckpoints={before:h0,after:D.documentHash(checkpointed)};
const doNotMutate=D.clone(base);const beforeJson=JSON.stringify(doNotMutate);D.documentHash(doNotMutate);
out.hashDidNotMutate=JSON.stringify(doNotMutate)===beforeJson;
const relabeled=D.clone(base);
if(relabeled.components[0])relabeled.components[0].config=Object.assign({},relabeled.components[0].config,{label:'changed-label-xyz'});
out.hashLabelChanged={before:h0,after:D.documentHash(relabeled)};

const perExample={};
for(const file of fs.readdirSync(examplesDir).filter(f=>f.endsWith('.sov'))){
  const text=fs.readFileSync(path.join(examplesDir,file),'utf8');
  const docA=D.documentFromFilePayload(JSON.parse(text));
  const docB=D.documentFromFilePayload(JSON.parse(text));
  perExample[file]={a:D.documentHash(docA),b:D.documentHash(docB)};
}
out.perExample=perExample;

console.log(JSON.stringify(out));
"""


def main() -> None:
    proc = subprocess.run(
        ['node', '-e', JS, str(ROOT / 'src/03-canonical.js'), str(ROOT / 'src/05-data-core.js'), str(ROOT / 'examples')],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    r = json.loads(proc.stdout)

    # SHA-256 against the NIST vectors.
    assert r['sha_empty'] == 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', r['sha_empty']
    assert r['sha_abc'] == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad', r['sha_abc']
    assert r['sha_448'] == '248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1', r['sha_448']
    assert r['sha_million_a'] == 'cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0', r['sha_million_a']

    # SHA-256 against node's crypto, for >=200 random strings including non-BMP characters.
    assert r['shaMismatches'] == 0, r
    assert r['nonBmpCovered'] >= 30, r['nonBmpCovered']

    # canonicalize against the RFC 8785 examples for key ordering and number forms.
    assert r['rfcNumbers'] == '{"extra":"x","literals":[null,true,false],"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27]}', r['rfcNumbers']
    assert r['unicodeKeyOrder'] == ['\r', '1', '\u0080', 'ö', '€', '\U0001F600', 'דּ'], r['unicodeKeyOrder']

    # Each unsupported value throws CANONICAL_UNSUPPORTED.
    for key in ('nan', 'posInf', 'negInf', 'undef', 'fn', 'sym', 'bigint', 'date', 'map', 'nested'):
        assert r['codes'][key] == 'CANONICAL_UNSUPPORTED', (key, r['codes'])

    # drawOrder: a permutation, identical for the same (seed, keyParts) whatever the input
    # order, differs across key tuples, and near-uniform over the six 3-item orders.
    assert r['permutation'] == [1, 2, 3, 4, 5], r['permutation']
    assert r['orderIndependent'] is True, r
    assert r['distinctForDifferentKeys'] > 1, r['distinctForDifferentKeys']
    assert r['drawOrderKeys'] == 6, r['drawOrderKeys']
    for key, count in r['drawCounts'].items():
        assert 9500 <= count <= 10500, (key, count, r['drawCounts'])

    # documentHash: identical across revision/updatedAt/savedAt/checkpoints, differs on content,
    # never mutates its input, and is identical across two independent loads of every example.
    assert r['hashRevision']['before'] == r['hashRevision']['after'], r['hashRevision']
    assert r['hashUpdatedAt']['before'] == r['hashUpdatedAt']['after'], r['hashUpdatedAt']
    assert r['hashSavedAt']['before'] == r['hashSavedAt']['after'], r['hashSavedAt']
    assert r['hashCheckpoints']['before'] == r['hashCheckpoints']['after'], r['hashCheckpoints']
    assert r['hashDidNotMutate'] is True, r
    assert r['hashLabelChanged']['before'] != r['hashLabelChanged']['after'], r['hashLabelChanged']
    for file, pair in r['perExample'].items():
        assert pair['a'] == pair['b'], (file, pair)

    print('PASS canonical QA')


if __name__ == '__main__':
    main()
