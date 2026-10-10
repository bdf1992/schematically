#!/usr/bin/env node
// The key cache of mcp/access.mjs under an injected clock: no server, no socket, no sleep longer
// than a few milliseconds. tests/access_gate_qa.py runs it beside tests/access_gate_check.mjs.
//
// Two clocks are injected and moved apart on purpose:
//   wall  seconds since 1970, what `now` returns. The gate reads it only for exp, iat and nbf.
//   mono  milliseconds from an arbitrary start, what `monotonic` returns (performance.now's shape).
//         The gate reads it only for the age of the key set and the gap between fetches, so a
//         wall clock that is set back or forward neither ages the keys nor makes them young.
// Each check prints one PASS or FAIL line and every check runs; a failure exits 1.
import crypto from 'node:crypto';
import {createAccessGate} from '../mcp/access.mjs';

const HOSTNAME='docs.example.test';
const TEAM='team.example.test';
const WALL_START=1_800_000_000;

const b64url=value=>Buffer.from(value).toString('base64url');
function signToken(header,claims,privateKey){
  const input=b64url(JSON.stringify(header))+'.'+b64url(JSON.stringify(claims));
  return input+'.'+crypto.sign('sha256',Buffer.from(input),privateKey).toString('base64url');
}
function assert(condition,message){if(!condition)throw new Error(message)}
const pairA=crypto.generateKeyPairSync('rsa',{modulusLength:2048});
const pairB=crypto.generateKeyPairSync('rsa',{modulusLength:2048});
const jwk=(pair,kid)=>({...pair.publicKey.export({format:'jwk'}),kid,alg:'RS256',use:'sig'});
const SET_A={keys:[jwk(pairA,'a')]};
const SET_AB={keys:[jwk(pairA,'a'),jwk(pairB,'b')]};
const SET_B={keys:[jwk(pairB,'b')]};

// One gate with its own two clocks and its own certs answer. `serve` is what the next fetch
// answers: a certs document, an Error to throw, or a function returning a promise.
function bench(serve){
  const state={wall:WALL_START,mono:5_000,fetches:0,serve};
  const gate=createAccessGate({
    hostname:HOSTNAME,teamDomain:TEAM,audiences:['aud-1'],
    now:()=>state.wall,
    monotonic:()=>state.mono,
    fetchJson:async()=>{
      state.fetches+=1;
      const answer=typeof state.serve==='function'?await state.serve():state.serve;
      if(answer instanceof Error)throw answer;
      return answer;
    }
  });
  // Both clocks move together unless a check moves one alone.
  state.advance=seconds=>{state.wall+=seconds;state.mono+=seconds*1000};
  // A token made now lasts five minutes, so one is made for each moment it is used.
  state.token=(kid,pair,claims={})=>signToken({alg:'RS256',kid},{iss:`https://${TEAM}`,aud:['aud-1'],exp:state.wall+300,iat:state.wall,sub:'user-1',...claims},pair.privateKey);
  state.admit=(kid,pair,claims)=>gate.admit({host:HOSTNAME,'cf-access-jwt-assertion':state.token(kid,pair,claims)});
  state.gate=gate;
  return state;
}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(condition,what){
  for(let i=0;i<400;i+=1){if(await condition())return;await pause(5)}
  throw new Error(`timed out waiting until ${what}`);
}
function deferred(){let resolve,reject;const promise=new Promise((res,rej)=>{resolve=res;reject=rej});return {promise,resolve,reject}}
const reasonOf=verdict=>verdict.ok?'admitted':verdict.reason;

let failures=0;
async function check(name,fn){
  try{await fn();console.log(`PASS unit: ${name}`)}catch(error){failures+=1;console.log(`FAIL unit: ${name}: ${String(error.message||error)}`)}
}

await check('the first fetch failing with no keys refuses every token as jwks_fetch_failed',async()=>{
  const b=bench(new Error('certs answered 503'));
  const verdicts=[await b.admit('a',pairA),await b.admit('b',pairB),await b.admit('a',pairB)];
  for(const verdict of verdicts){
    assert(verdict.ok===false&&verdict.status===401&&verdict.code==='ACCESS_TOKEN_INVALID',`a token was not refused 401: ${JSON.stringify(verdict)}`);
    assert(verdict.reason==='jwks_fetch_failed',`reason ${verdict.reason}, wanted jwks_fetch_failed`);
  }
  assert(b.fetches===1,`${b.fetches} fetches, wanted 1 (one attempt in 30 s)`);
  b.serve=SET_A;b.advance(30);
  assert((await b.admit('a',pairA)).ok===true,'the token was not admitted once the keys could be fetched');
  assert(b.fetches===2,`${b.fetches} fetches, wanted 2`);
});

await check('keys are refetched after 600 s and not before',async()=>{
  const b=bench(SET_A);
  assert((await b.admit('a',pairA)).ok===true,'not admitted at 0 s');
  for(const at of [1,300,599]){
    b.advance(at-(b.mono-5_000)/1000);
    assert((await b.admit('a',pairA)).ok===true,`not admitted at ${at} s`);
    await pause(10);
    assert(b.fetches===1,`${b.fetches} fetches at ${at} s, wanted 1`);
  }
  b.advance(1);
  assert((await b.admit('a',pairA)).ok===true,'not admitted at 600 s');
  await until(()=>b.fetches===2,'the keys are fetched again at 600 s');
  await pause(10);
  assert(b.fetches===2,`${b.fetches} fetches at 600 s, wanted 2`);
});

await check('an unknown kid costs at most one fetch per 30 s however many requests arrive',async()=>{
  const b=bench(SET_A);
  assert((await b.admit('a',pairA)).ok===true,'not admitted at 0 s');
  const refusedAll=async count=>{
    const verdicts=await Promise.all(Array.from({length:count},()=>b.admit('zz',pairB)));
    for(const verdict of verdicts)assert(reasonOf(verdict)==='kid_unknown',`reason ${reasonOf(verdict)}, wanted kid_unknown`);
  };
  b.advance(1);await refusedAll(25);
  b.advance(28);await refusedAll(25);
  assert(b.fetches===1,`${b.fetches} fetches before 30 s, wanted 1`);
  b.advance(1);await refusedAll(25);
  assert(b.fetches===2,`${b.fetches} fetches at 30 s, wanted 2`);
  b.advance(29);await refusedAll(25);
  assert(b.fetches===2,`${b.fetches} fetches at 59 s, wanted 2`);
  b.advance(1);await refusedAll(25);
  assert(b.fetches===3,`${b.fetches} fetches at 60 s, wanted 3`);
});

await check('a failed refetch keeps the good keys',async()=>{
  const b=bench(SET_A);
  assert((await b.admit('a',pairA)).ok===true,'not admitted at 0 s');
  b.serve=new Error('certs answered 500');b.advance(700);
  assert((await b.admit('a',pairA)).ok===true,'not admitted at 700 s while the refetch fails');
  await until(()=>b.fetches===2,'the refetch was attempted');
  await pause(10);b.advance(10);
  assert((await b.admit('a',pairA)).ok===true,'not admitted after the failed refetch');
  assert(reasonOf(await b.admit('zz',pairB))==='kid_unknown','an unknown kid is not kid_unknown after a failed refetch');
  b.serve={keys:[]};b.advance(30);
  assert(reasonOf(await b.admit('zz',pairB))==='kid_unknown','an unknown kid is not kid_unknown after an empty refetch');
  assert((await b.admit('a',pairA)).ok===true,'a refetch that yielded no key dropped the good keys');
});

await check('a rotated key set admits the new kid and refuses the old one once it is gone',async()=>{
  const b=bench(SET_A);
  assert((await b.admit('a',pairA)).ok===true,'kid a not admitted from the first set');
  assert(reasonOf(await b.admit('b',pairB))==='kid_unknown','kid b admitted before the team published it');
  b.serve=SET_AB;b.advance(40);
  assert((await b.admit('b',pairB)).ok===true,'kid b not admitted after the team published it');
  assert((await b.admit('a',pairA)).ok===true,'kid a not admitted while the set still holds it');
  b.serve=SET_B;b.advance(700);
  assert((await b.admit('b',pairB)).ok===true,'kid b not admitted at 740 s');
  await until(async()=>reasonOf(await b.admit('a',pairA))==='kid_unknown','kid a is refused as kid_unknown once the set no longer holds it');
  assert((await b.admit('b',pairB)).ok===true,'kid b not admitted from the rotated set');
  assert(b.fetches===3,`${b.fetches} fetches, wanted 3`);
});

await check('no successful fetch for more than 86400 s refuses every token as jwks_stale',async()=>{
  const b=bench(SET_A);
  assert((await b.admit('a',pairA)).ok===true,'not admitted at 0 s');
  b.serve=new Error('certs unreachable');b.advance(86399);
  assert((await b.admit('a',pairA)).ok===true,'not admitted at 86399 s from the held keys');
  await until(()=>b.fetches===2,'the refetch was attempted');
  await pause(10);b.advance(2);
  const known=await b.admit('a',pairA);
  const unknown=await b.admit('zz',pairB);
  assert(known.ok===false&&known.status===401&&known.code==='ACCESS_TOKEN_INVALID',`a known kid was not refused 401 at 86401 s: ${JSON.stringify(known)}`);
  assert(known.reason==='jwks_stale',`known kid: reason ${reasonOf(known)}, wanted jwks_stale`);
  assert(unknown.reason==='jwks_stale',`unknown kid: reason ${reasonOf(unknown)}, wanted jwks_stale and not kid_unknown`);
  b.serve=SET_A;b.advance(30);
  assert((await b.admit('a',pairA)).ok===true,'not admitted once the keys were fetched again');
});

await check('ten concurrent admits during one fetch cause exactly one fetchJson call',async()=>{
  const gateOpen=deferred();
  const b=bench(()=>gateOpen.promise);
  const admits=Array.from({length:10},()=>b.admit('a',pairA));
  await pause(20);
  assert(b.fetches===1,`${b.fetches} fetches while the first is in flight, wanted 1`);
  gateOpen.resolve(SET_A);
  const verdicts=await Promise.all(admits);
  assert(verdicts.every(verdict=>verdict.ok===true),'not all ten were admitted');
  assert(b.fetches===1,`${b.fetches} fetches, wanted 1`);
});

await check('a known kid in a set older than 600 s and younger than 86400 s is admitted without waiting on the refetch',async()=>{
  const b=bench(SET_A);
  assert((await b.admit('a',pairA)).ok===true,'not admitted at 0 s');
  const hung=deferred();
  b.serve=()=>hung.promise;b.advance(700);
  const verdict=await Promise.race([b.admit('a',pairA),pause(1000).then(()=>'waited')]);
  assert(verdict!=='waited','the admit waited on a refetch that had not answered');
  assert(verdict.ok===true,`not admitted: ${JSON.stringify(verdict)}`);
  assert(b.fetches===2,`${b.fetches} fetches, wanted 2 (the refetch started)`);
  b.advance(50000);
  const later=await Promise.race([b.admit('a',pairA),pause(1000).then(()=>'waited')]);
  assert(later!=='waited'&&later.ok===true,'not admitted at 50700 s while the same refetch is still in flight');
  assert(b.fetches===2,`${b.fetches} fetches, wanted 2 (one fetch at a time)`);
  hung.resolve(SET_A);
  await pause(20);
});

await check('the age of the keys follows the monotonic clock, the claims follow the wall clock',async()=>{
  const b=bench(SET_A);
  assert((await b.admit('a',pairA)).ok===true,'not admitted at 0 s');
  const early=b.token('a',pairA);
  // The wall clock is set a day ahead: the old token is expired, the keys are no older.
  b.wall+=90000;
  assert(reasonOf(await b.gate.admit({host:HOSTNAME,'cf-access-jwt-assertion':early}))==='token_expired','a token made before the wall clock moved a day is not token_expired');
  assert((await b.admit('a',pairA)).ok===true,'a token made after the wall clock moved is not admitted: the keys were aged by the wall clock');
  await pause(10);
  assert(b.fetches===1,`${b.fetches} fetches after the wall clock moved alone, wanted 1`);
  // The wall clock is set back two days: still no fetch, and a token of that time is admitted.
  b.wall-=180000;
  assert((await b.admit('a',pairA)).ok===true,'not admitted after the wall clock was set back');
  await pause(10);
  assert(b.fetches===1,`${b.fetches} fetches after the wall clock was set back, wanted 1`);
  // The monotonic clock alone passes 600 s: the keys are fetched again.
  b.mono+=600_000;
  assert((await b.admit('a',pairA)).ok===true,'not admitted at 600 monotonic seconds');
  await until(()=>b.fetches===2,'the keys are fetched again by monotonic age');
});

await check('with only `now` injected the one clock drives both',async()=>{
  let wall=WALL_START,fetches=0;
  const gate=createAccessGate({hostname:HOSTNAME,teamDomain:TEAM,audiences:['aud-1'],now:()=>wall,fetchJson:async()=>{fetches+=1;return SET_A}});
  const admit=()=>gate.admit({host:HOSTNAME,'cf-access-jwt-assertion':signToken({alg:'RS256',kid:'a'},{iss:`https://${TEAM}`,aud:'aud-1',exp:wall+300,iat:wall},pairA.privateKey)});
  assert((await admit()).ok===true,'not admitted at 0 s');
  wall+=599;assert((await admit()).ok===true,'not admitted at 599 s');
  await pause(10);assert(fetches===1,`${fetches} fetches at 599 s, wanted 1`);
  wall+=1;assert((await admit()).ok===true,'not admitted at 600 s');
  await until(()=>fetches===2,'the keys are fetched again at 600 s');
});

await check('Sec-Fetch-Site other than same-origin or none is cross_site, with or without an Origin',async()=>{
  const b=bench(SET_A);
  const send=extra=>b.gate.admit({host:HOSTNAME,'cf-access-jwt-assertion':b.token('a',pairA),...extra});
  for(const value of ['cross-site','same-site','CROSS-SITE','','same-origin, cross-site']){
    const verdict=await send({'sec-fetch-site':value});
    assert(verdict.ok===false&&verdict.status===403&&verdict.code==='ACCESS_HOST_REFUSED'&&verdict.reason==='cross_site',`Sec-Fetch-Site ${JSON.stringify(value)}: ${JSON.stringify(verdict)}`);
  }
  const withOrigin=await send({'sec-fetch-site':'cross-site',origin:`https://${HOSTNAME}`});
  assert(withOrigin.reason==='cross_site',`with the hostname's own Origin: ${reasonOf(withOrigin)}, wanted cross_site`);
  for(const extra of [{},{'sec-fetch-site':'same-origin'},{'sec-fetch-site':'none'},{'sec-fetch-site':'Same-Origin'}]){
    assert((await send(extra)).ok===true,`not admitted with ${JSON.stringify(extra)}`);
  }
  assert(b.fetches===1,`${b.fetches} fetches, wanted 1: a refused request reached the keys`);
});

console.log(failures===0?'PASS access gate unit':`FAIL access gate unit: ${failures} failed`);
process.exit(failures===0?0:1);
