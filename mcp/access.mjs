// The gate in front of the remote listener: a request is admitted only when its Host is the
// declared hostname and its Cf-Access-Jwt-Assertion token is signed by the declared Cloudflare
// Access team for a declared audience. The method is the one Cloudflare documents for an origin
// behind Access ("Validate JWTs"): an RS256 signature against the team's keys at
// /cdn-cgi/access/certs, then iss, aud and exp. Token handling follows RFC 8725: the algorithm is
// fixed here and never taken from the token, and neither are the keys' address, the issuer or the
// audience.
//
// This module loads nothing: it uses the globals crypto.subtle, fetch, atob, TextEncoder,
// TextDecoder and AbortSignal, which Node 24 and Cloudflare Workers both have.
//
// createAccessGate({hostname, teamDomain, audiences, certsUrl, fetchJson, now}) -> {admit(headers)}
//   admit resolves to {ok:true, claims} or {ok:false, status, code, reason} and never throws.
//   A refusal holds neither the token nor any claim.

const DNS_NAME=/^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$/;
const BASE64URL=/^[A-Za-z0-9_-]*$/;
const ALGORITHM={name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'};
const FRESH_SECONDS=600;      // a held key younger than this is served with no fetch
const RETRY_SECONDS=30;       // at most one fetch attempt in this long
const STALE_SECONDS=86400;    // a key set older than this admits nothing
const LEEWAY_SECONDS=30;      // clock difference allowed on exp, iat and nbf

function base64urlBytes(text){
  if(typeof text!=='string'||!BASE64URL.test(text)||text.length%4===1)return null;
  let binary;
  try{binary=atob(text.replace(/-/g,'+').replace(/_/g,'/')+'='.repeat((4-text.length%4)%4))}catch(_){return null}
  const bytes=new Uint8Array(binary.length);
  for(let i=0;i<binary.length;i+=1)bytes[i]=binary.charCodeAt(i);
  return bytes;
}
function base64urlObject(text){
  const bytes=base64urlBytes(text);
  if(bytes===null||bytes.length===0)return null;
  try{
    const value=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
    return value!==null&&typeof value==='object'&&!Array.isArray(value)?value:null;
  }catch(_){return null}
}
async function defaultFetchJson(url){
  const response=await fetch(url,{redirect:'error',signal:AbortSignal.timeout(10000)});
  if(!response.ok)throw new Error(`certs answered ${response.status}`);
  return response.json();
}
// The usable keys of a certs document, by kid. An entry that fails to import is skipped.
async function keySet(document){
  const set=new Map();
  const entries=document!==null&&typeof document==='object'&&Array.isArray(document.keys)?document.keys:[];
  for(const entry of entries){
    if(entry===null||typeof entry!=='object'||entry.kty!=='RSA')continue;
    if(typeof entry.kid!=='string'||entry.kid===''||set.has(entry.kid))continue;
    if(entry.use!==undefined&&entry.use!=='sig')continue;
    if(entry.alg!==undefined&&entry.alg!=='RS256')continue;
    try{
      set.set(entry.kid,await crypto.subtle.importKey('jwk',{kty:'RSA',n:entry.n,e:entry.e},ALGORITHM,false,['verify']));
    }catch(_){}
  }
  return set;
}

export function createAccessGate({hostname,teamDomain,audiences,certsUrl,fetchJson,now}={}){
  if(typeof hostname!=='string'||!DNS_NAME.test(hostname))throw new Error('hostname must be a lowercase bare DNS name');
  if(typeof teamDomain!=='string'||!DNS_NAME.test(teamDomain))throw new Error('teamDomain must be a lowercase bare DNS name');
  if(!Array.isArray(audiences)||audiences.length===0||!audiences.every(tag=>typeof tag==='string'&&tag!==''))throw new Error('audiences must be a non-empty array of strings');
  const allowed=new Set(audiences);
  const issuer=`https://${teamDomain}`;
  const origin=`https://${hostname}`;
  const certs=certsUrl||`https://${teamDomain}/cdn-cgi/access/certs`;
  const getJson=fetchJson||defaultFetchJson;
  const clock=now||(()=>Date.now()/1000);

  // The key cache: the set, when it was fetched, when a fetch was last attempted.
  let keys=new Map(),fetchedAt=-Infinity,attemptedAt=-Infinity,pending=null;
  async function refresh(){
    try{
      const set=await keySet(await getJson(certs));
      if(set.size>0){keys=set;fetchedAt=clock()}
    }catch(_){}
  }
  // The key for a kid, or null. A kid the set lacks is fetched for at most once per
  // RETRY_SECONDS, and requests that arrive during a fetch wait for that one fetch.
  async function keyFor(kid){
    if(keys.has(kid)&&clock()-fetchedAt<FRESH_SECONDS)return keys.get(kid);
    if(pending===null&&clock()-attemptedAt>=RETRY_SECONDS){
      attemptedAt=clock();
      pending=refresh().finally(()=>{pending=null});
    }
    if(pending!==null)await pending;
    return keys.has(kid)&&clock()-fetchedAt<STALE_SECONDS?keys.get(kid):null;
  }

  const refuse=(status,code,reason)=>({ok:false,status,code,reason});
  const invalid=reason=>refuse(401,'ACCESS_TOKEN_INVALID',reason);

  async function decide(headers){
    const given=headers!==null&&typeof headers==='object'?headers:{};
    if(String(given.host).toLowerCase()!==hostname)return refuse(403,'ACCESS_HOST_REFUSED','host_not_remote_hostname');
    if(given.origin!==undefined&&given.origin!==origin)return refuse(403,'ACCESS_HOST_REFUSED','origin_refused');
    const raw=given['cf-access-jwt-assertion'];
    const token=typeof raw==='string'?raw.trim():'';
    if(token==='')return refuse(401,'ACCESS_TOKEN_MISSING','token_missing');
    const parts=token.split('.');
    if(parts.length!==3)return invalid('token_unreadable');
    const header=base64urlObject(parts[0]);
    const claims=base64urlObject(parts[1]);
    if(header===null||claims===null)return invalid('token_unreadable');
    if(header.alg!=='RS256')return invalid('alg_refused');
    if(typeof header.kid!=='string'||header.kid==='')return invalid('kid_missing');
    const key=await keyFor(header.kid);
    if(key===null)return invalid(keys.size===0?'jwks_fetch_failed':'kid_unknown');
    let verified=false;
    try{
      const signature=base64urlBytes(parts[2]);
      verified=signature!==null&&await crypto.subtle.verify(ALGORITHM.name,key,signature,new TextEncoder().encode(parts[0]+'.'+parts[1]));
    }catch(_){verified=false}
    if(verified!==true)return invalid('signature_invalid');
    if(claims.iss!==issuer)return invalid('issuer_refused');
    const named=typeof claims.aud==='string'?[claims.aud]:Array.isArray(claims.aud)&&claims.aud.every(tag=>typeof tag==='string')?claims.aud:[];
    if(!named.some(tag=>allowed.has(tag)))return invalid('audience_refused');
    const time=clock();
    if(!Number.isFinite(claims.exp)||claims.exp<=time-LEEWAY_SECONDS)return invalid('token_expired');
    if(!Number.isFinite(claims.iat)||claims.iat>time+LEEWAY_SECONDS)return invalid('iat_refused');
    if(claims.nbf!==undefined&&!(Number.isFinite(claims.nbf)&&claims.nbf<=time+LEEWAY_SECONDS))return invalid('not_yet_valid');
    return {ok:true,claims};
  }

  return {
    async admit(headers){
      try{return await decide(headers)}catch(_){return invalid('token_unreadable')}
    }
  };
}
