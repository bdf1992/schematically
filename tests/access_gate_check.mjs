#!/usr/bin/env node
// Drives the two listeners of mcp/server.mjs: the remote one (--remote-port), which admits a
// request only with the declared Host and a Cloudflare Access token signed by the declared team
// for a declared audience, and the first one (--port), which refuses anything that came through a
// tunnel. Everything is on loopback: this script is the certs server, and it signs its own tokens.
// tests/access_gate_qa.py runs it. Each check prints one PASS or FAIL line and every check runs; a
// failure exits 1. The server and the certs server this script started are always stopped, and no
// other process is touched: both listen on ports this script found free.
import http from 'node:http';
import net from 'node:net';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const HERE=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.join(HERE,'..');
const SERVER=path.join(ROOT,'mcp/server.mjs');
const HOSTNAME='docs.example.test';
const TEAM='team.example.test';

function freePort(){
  return new Promise((resolve,reject)=>{
    const probe=net.createServer();
    probe.on('error',reject);
    probe.listen(0,'127.0.0.1',()=>{const {port}=probe.address();probe.close(()=>resolve(port))});
  });
}
// Every request goes through http.request so the Host header is the one the check names and the
// request target is sent as written (nothing normalises `//` or `/%`). noHost sends no Host line.
function call(port,{method='GET',path:requestPath='/documents',headers={},body=null,noHost=false}={}){
  return new Promise((resolve,reject)=>{
    const sent={...headers};
    if(body!==null){sent['content-type']='application/json';sent['content-length']=Buffer.byteLength(body)}
    const req=http.request({host:'127.0.0.1',port,method,path:requestPath,headers:sent,agent:false,setHost:!noHost},res=>{
      let text='';res.setEncoding('utf8');
      res.on('data',chunk=>text+=chunk);
      res.on('end',()=>{let json=null;try{json=JSON.parse(text)}catch(_){}resolve({status:res.statusCode,headers:res.headers,text,json})});
    });
    req.on('error',reject);
    req.setTimeout(15000,()=>req.destroy(new Error('request timed out')));
    if(body!==null)req.write(body);
    req.end();
  });
}
const b64url=value=>Buffer.from(value).toString('base64url');
function signToken(header,claims,privateKey){
  const input=b64url(JSON.stringify(header))+'.'+b64url(JSON.stringify(claims));
  return input+'.'+crypto.sign('sha256',Buffer.from(input),privateKey).toString('base64url');
}
function assert(condition,message){if(!condition)throw new Error(message)}

const keyA=crypto.generateKeyPairSync('rsa',{modulusLength:2048});
const keyB=crypto.generateKeyPairSync('rsa',{modulusLength:2048});
const jwkA={...keyA.publicKey.export({format:'jwk'}),kid:'a',alg:'RS256',use:'sig'};

let certsRequests=0;
const certs=http.createServer((req,res)=>{
  certsRequests+=1;
  if(req.url==='/certs'){res.writeHead(200,{'content-type':'application/json'});return res.end(JSON.stringify({keys:[jwkA]}))}
  res.writeHead(404);res.end('');
});

let server=null,serverOutput='',tempDir=null,failed=false;
const sentTokens=[];
const refusals=[];

// Every check runs, so one run shows each failing line; any failure exits 1.
let failures=0;
async function check(name,fn){
  try{await fn()}catch(error){
    failures+=1;
    console.log(`FAIL ${name}: ${String(error.message||error)}`);
    return;
  }
  console.log(`PASS ${name}`);
}

try{
  await new Promise((resolve,reject)=>{certs.on('error',reject);certs.listen(0,'127.0.0.1',resolve)});
  const certsUrl=`http://127.0.0.1:${certs.address().port}/certs`;
  tempDir=fs.mkdtempSync(path.join(os.tmpdir(),'access-gate-'));
  const rootDir=path.join(tempDir,'root');
  fs.mkdirSync(rootDir);
  fs.copyFileSync(path.join(ROOT,'examples/01-source-hold.sov'),path.join(rootDir,'one.sov'));
  const P=await freePort();
  const R=await freePort();
  server=spawn(process.execPath,[SERVER,'--root',rootDir,'--port',String(P),'--remote-port',String(R),'--access-hostname',HOSTNAME,'--access-team',TEAM,'--access-aud','aud-1,aud-2','--access-certs-url',certsUrl],{cwd:ROOT,stdio:['ignore','pipe','pipe']});
  server.stdout.on('data',chunk=>serverOutput+=chunk);
  server.stderr.on('data',chunk=>serverOutput+=chunk);
  let up=false;
  for(let i=0;i<300&&!up;i+=1){
    if(server.exitCode!==null)break;
    try{up=(await call(P)).status===200}catch(_){}
    if(!up)await new Promise(resolve=>setTimeout(resolve,50));
  }
  if(!up){console.log('FAIL server start: GET /documents on the first port never answered 200\n'+serverOutput);throw new Error('check failed')}

  const now=Math.floor(Date.now()/1000);
  const goodHeader={alg:'RS256',kid:'a'};
  const goodClaims={iss:`https://${TEAM}`,aud:['aud-1'],exp:now+300,iat:now,sub:'user-1'};
  const good=signToken(goodHeader,goodClaims,keyA.privateKey);
  // One GET /documents on the remote port; a refusal is kept with the token it was sent.
  async function remote({token=null,host=HOSTNAME,origin=null,method='GET',path:requestPath='/documents',body=null,extra={}}={}){
    const headers=host===null?{...extra}:{host,...extra};
    if(token!==null){headers['cf-access-jwt-assertion']=token;sentTokens.push(token)}
    if(origin!==null)headers.origin=origin;
    const res=await call(R,{method,path:requestPath,headers,body,noHost:host===null});
    if(res.status!==200)refusals.push({token,res});
    return res;
  }
  function refused(res,status,code,reason){
    assert(res.status===status,`status ${res.status}, wanted ${status}: ${res.text.slice(0,200)}`);
    assert(res.json&&res.json.ok===false&&res.json.code===code,`code ${res.json&&res.json.code}, wanted ${code}: ${res.text.slice(0,200)}`);
    if(reason!==undefined)assert(res.json.reason===reason,`reason ${res.json.reason}, wanted ${reason}`);
    assert(JSON.stringify(Object.keys(res.json).sort())==='["code","ok","reason"]',`a refusal holds ok, code and reason only: ${res.text}`);
    assert(res.headers['content-type']==='application/json; charset=utf-8',`content-type ${res.headers['content-type']}`);
    assert(!Object.keys(res.headers).some(name=>name.startsWith('access-control-')),'a refusal carries an access-control header');
  }
  const invalid=(res,reason)=>refused(res,401,'ACCESS_TOKEN_INVALID',reason);

  await check('remote: good token with Host docs.example.test is 200 with a documents array',async()=>{
    const res=await remote({token:good});
    assert(res.status===200,`status ${res.status}: ${res.text}`);
    assert(res.json&&Array.isArray(res.json.documents),'no documents array');
  });
  await check('remote: no token is 401 ACCESS_TOKEN_MISSING',async()=>{
    refused(await remote(),401,'ACCESS_TOKEN_MISSING','token_missing');
  });
  await check('remote: good token with Host 127.0.0.1:R is 403 ACCESS_HOST_REFUSED',async()=>{
    refused(await remote({token:good,host:`127.0.0.1:${R}`}),403,'ACCESS_HOST_REFUSED','host_not_remote_hostname');
  });
  await check('remote: Origin https://evil.example is 403',async()=>{
    refused(await remote({token:good,origin:'https://evil.example'}),403,'ACCESS_HOST_REFUSED','origin_refused');
  });
  await check('remote: Origin https://docs.example.test is 200',async()=>{
    const res=await remote({token:good,origin:`https://${HOSTNAME}`});
    assert(res.status===200,`status ${res.status}: ${res.text}`);
  });
  await check('remote: kid a signed by key B is 401 signature_invalid',async()=>{
    invalid(await remote({token:signToken(goodHeader,goodClaims,keyB.privateKey)}),'signature_invalid');
  });
  await check('remote: kid b signed by key B is 401 kid_unknown',async()=>{
    invalid(await remote({token:signToken({alg:'RS256',kid:'b'},goodClaims,keyB.privateKey)}),'kid_unknown');
  });
  await check('remote: aud [other] is audience_refused',async()=>{
    invalid(await remote({token:signToken(goodHeader,{...goodClaims,aud:['other']},keyA.privateKey)}),'audience_refused');
  });
  await check('remote: aud [x, aud-2] is 200',async()=>{
    const res=await remote({token:signToken(goodHeader,{...goodClaims,aud:['x','aud-2']},keyA.privateKey)});
    assert(res.status===200,`status ${res.status}: ${res.text}`);
  });
  await check('remote: iss https://other.example.test is issuer_refused',async()=>{
    invalid(await remote({token:signToken(goodHeader,{...goodClaims,iss:'https://other.example.test'},keyA.privateKey)}),'issuer_refused');
  });
  await check('remote: exp now-120 is token_expired',async()=>{
    invalid(await remote({token:signToken(goodHeader,{...goodClaims,exp:now-120},keyA.privateKey)}),'token_expired');
  });
  await check('remote: alg none with an empty third part is alg_refused',async()=>{
    const token=b64url(JSON.stringify({alg:'none',kid:'a'}))+'.'+b64url(JSON.stringify(goodClaims))+'.';
    invalid(await remote({token}),'alg_refused');
  });
  await check('remote: alg HS256 keyed with the PEM of public key A is alg_refused',async()=>{
    const pem=keyA.publicKey.export({type:'spki',format:'pem'});
    const input=b64url(JSON.stringify({alg:'HS256',kid:'a'}))+'.'+b64url(JSON.stringify(goodClaims));
    const token=input+'.'+crypto.createHmac('sha256',pem).update(input).digest('base64url');
    invalid(await remote({token}),'alg_refused');
  });
  const toolsList=JSON.stringify({jsonrpc:'2.0',id:1,method:'tools/list',params:{}});
  await check('remote: POST /d/one/mcp tools/list with the good token is 200 with tools',async()=>{
    const res=await remote({token:good,method:'POST',path:'/d/one/mcp',body:toolsList});
    assert(res.status===200,`status ${res.status}: ${res.text}`);
    assert(res.json&&res.json.result&&Array.isArray(res.json.result.tools)&&res.json.result.tools.length>0,'result.tools is empty');
  });
  await check('remote: POST /d/one/mcp without a token is 401',async()=>{
    refused(await remote({method:'POST',path:'/d/one/mcp',body:toolsList}),401,'ACCESS_TOKEN_MISSING','token_missing');
  });
  // --- the token cases the first pass left untested: each changes one thing on the good token.
  const signed=(claims,header=goodHeader)=>signToken(header,claims,keyA.privateKey);
  const without=(claims,name)=>{const copy={...claims};delete copy[name];return copy};
  const ok200=async(name,options)=>check(name,async()=>{
    const res=await remote(options);
    assert(res.status===200,`status ${res.status}: ${res.text}`);
  });
  await ok200('remote: aud as the plain string aud-1 is 200',{token:signed({...goodClaims,aud:'aud-1'})});
  await check('remote: aud aud-1x (one character more) is audience_refused, as a string and in an array',async()=>{
    invalid(await remote({token:signed({...goodClaims,aud:'aud-1x'})}),'audience_refused');
    invalid(await remote({token:signed({...goodClaims,aud:['aud-1x']})}),'audience_refused');
  });
  await check('remote: aud aud- (a prefix) is audience_refused, as a string and in an array',async()=>{
    invalid(await remote({token:signed({...goodClaims,aud:'aud-'})}),'audience_refused');
    invalid(await remote({token:signed({...goodClaims,aud:['aud-']})}),'audience_refused');
  });
  await check('remote: iss with a trailing slash is issuer_refused',async()=>{
    invalid(await remote({token:signed({...goodClaims,iss:`https://${TEAM}/`})}),'issuer_refused');
  });
  await check('remote: iss in another case is issuer_refused',async()=>{
    invalid(await remote({token:signed({...goodClaims,iss:`https://${TEAM.toUpperCase()}`})}),'issuer_refused');
    invalid(await remote({token:signed({...goodClaims,iss:`HTTPS://${TEAM}`})}),'issuer_refused');
  });
  await check('remote: exp as a string is token_expired',async()=>{
    invalid(await remote({token:signed({...goodClaims,exp:String(now+300)})}),'token_expired');
  });
  await check('remote: exp missing is token_expired',async()=>{
    invalid(await remote({token:signed(without(goodClaims,'exp'))}),'token_expired');
  });
  await check('remote: iat missing is iat_refused',async()=>{
    invalid(await remote({token:signed(without(goodClaims,'iat'))}),'iat_refused');
  });
  await check('remote: iat 10 minutes in the future is iat_refused',async()=>{
    invalid(await remote({token:signed({...goodClaims,iat:now+600,exp:now+900})}),'iat_refused');
  });
  await check('remote: nbf 10 minutes in the future is not_yet_valid',async()=>{
    invalid(await remote({token:signed({...goodClaims,nbf:now+600,exp:now+900})}),'not_yet_valid');
  });
  await ok200('remote: nbf now is 200',{token:signed({...goodClaims,nbf:now})});
  await check('remote: a token with two parts is token_unreadable',async()=>{
    invalid(await remote({token:good.split('.').slice(0,2).join('.')}),'token_unreadable');
  });
  await check('remote: a token with four parts is token_unreadable',async()=>{
    invalid(await remote({token:good+'.'+good.split('.')[2]}),'token_unreadable');
  });
  await check('remote: a header with no kid is kid_missing',async()=>{
    invalid(await remote({token:signed(goodClaims,{alg:'RS256'})}),'kid_missing');
  });
  await check('remote: Host docs.example.test. (a trailing dot) is 403 host_not_remote_hostname',async()=>{
    refused(await remote({token:good,host:HOSTNAME+'.'}),403,'ACCESS_HOST_REFUSED','host_not_remote_hostname');
  });
  await check('remote: Host docs.example.test:443 (a port) is 403 host_not_remote_hostname',async()=>{
    refused(await remote({token:good,host:HOSTNAME+':443'}),403,'ACCESS_HOST_REFUSED','host_not_remote_hostname');
  });
  await ok200('remote: Host DOCS.Example.Test (another case) is 200',{token:good,host:'DOCS.Example.Test'});
  await check('remote: no Host line at all is 403 host_not_remote_hostname',async()=>{
    refused(await remote({token:good,host:null}),403,'ACCESS_HOST_REFUSED','host_not_remote_hostname');
  });
  await check('remote: Origin null is 403 origin_refused',async()=>{
    refused(await remote({token:good,origin:'null'}),403,'ACCESS_HOST_REFUSED','origin_refused');
  });
  await check('remote: OPTIONS without a token is 401 and not 204',async()=>{
    refused(await remote({method:'OPTIONS'}),401,'ACCESS_TOKEN_MISSING','token_missing');
    refused(await remote({method:'OPTIONS',path:'/d/one/mcp',origin:`https://${HOSTNAME}`,extra:{'access-control-request-method':'POST'}}),401,'ACCESS_TOKEN_MISSING','token_missing');
  });
  // --- a browser request from another site that carries no Origin.
  await check('remote: good token with Sec-Fetch-Site cross-site and no Origin is 403 cross_site',async()=>{
    refused(await remote({token:good,extra:{'sec-fetch-site':'cross-site'}}),403,'ACCESS_HOST_REFUSED','cross_site');
  });
  await check('remote: good token with Sec-Fetch-Site same-site is 403 cross_site',async()=>{
    refused(await remote({token:good,extra:{'sec-fetch-site':'same-site'}}),403,'ACCESS_HOST_REFUSED','cross_site');
  });
  await check('remote: Sec-Fetch-Site cross-site with the hostname as Origin is still 403 cross_site',async()=>{
    refused(await remote({token:good,origin:`https://${HOSTNAME}`,extra:{'sec-fetch-site':'cross-site'}}),403,'ACCESS_HOST_REFUSED','cross_site');
  });
  await ok200('remote: good token with Sec-Fetch-Site same-origin is 200',{token:good,extra:{'sec-fetch-site':'same-origin'}});
  await ok200('remote: good token with Sec-Fetch-Site none is 200',{token:good,extra:{'sec-fetch-site':'none'}});
  await ok200('remote: good token with no Sec-Fetch-Site header is 200',{token:good});

  await check('no refusal body contains the token that was sent',async()=>{
    const withToken=refusals.filter(entry=>entry.token!==null);
    assert(withToken.length>=9,`only ${withToken.length} refusals carried a token`);
    for(const {token,res} of withToken){
      assert(!res.text.includes(token),'a refusal body holds the whole token');
      for(const part of token.split('.'))if(part.length>=16)assert(!res.text.includes(part),'a refusal body holds a part of the token');
      assert(!res.text.includes('user-1'),'a refusal body holds a claim');
    }
  });
  await check('local: GET /documents with no extra header is 200',async()=>{
    const res=await call(P);
    assert(res.status===200&&res.json&&Array.isArray(res.json.documents),`status ${res.status}: ${res.text}`);
  });
  await check('local: a cf-ray header is 403 tunnel_mark_on_local_surface',async()=>{
    refused(await call(P,{headers:{'cf-ray':'8f0000000000abcd-SEA'}}),403,'ACCESS_HOST_REFUSED','tunnel_mark_on_local_surface');
  });
  await check('local: the good token in cf-access-jwt-assertion is 403',async()=>{
    const res=await call(P,{headers:{'cf-access-jwt-assertion':good}});
    refused(res,403,'ACCESS_HOST_REFUSED','tunnel_mark_on_local_surface');
    assert(!res.text.includes(good),'the refusal body holds the token');
  });
  // --- the first listener answers only a request addressed to loopback on its own port.
  const localOk=name=>async()=>{
    const res=await call(P,{headers:{host:name}});
    assert(res.status===200&&res.json&&Array.isArray(res.json.documents),`status ${res.status}: ${res.text}`);
  };
  const localRefused=(options)=>async()=>{
    const res=await call(P,options);
    refused(res,403,'LOCAL_HOST_REFUSED','host_not_loopback');
    assert(!res.text.includes('evil'),'the refusal body repeats the Host it was sent');
  };
  await check('local: Host 127.0.0.1:P is 200',localOk(`127.0.0.1:${P}`));
  await check('local: Host localhost:P is 200',localOk(`localhost:${P}`));
  await check('local: Host [::1]:P is 200',localOk(`[::1]:${P}`));
  await check('local: Host LocalHost:P (another case) is 200',localOk(`LocalHost:${P}`));
  await check('local: Host evil.example is 403 LOCAL_HOST_REFUSED',localRefused({headers:{host:'evil.example'}}));
  await check('local: Host evil.example:P is 403 LOCAL_HOST_REFUSED',localRefused({headers:{host:`evil.example:${P}`}}));
  await check('local: no Host line at all is 403 LOCAL_HOST_REFUSED',localRefused({noHost:true}));
  await check('local: an empty Host is 403 LOCAL_HOST_REFUSED',async()=>{
    // http.request replaces an empty Host with its own, so this one request is written by hand.
    const text=await new Promise((resolve,reject)=>{
      const socket=net.connect(P,'127.0.0.1',()=>socket.write('GET /documents HTTP/1.1\r\nHost:\r\nConnection: close\r\n\r\n'));
      let got='';socket.setEncoding('utf8');
      socket.on('data',chunk=>got+=chunk);
      socket.on('end',()=>resolve(got));
      socket.on('error',reject);
      socket.setTimeout(15000,()=>socket.destroy(new Error('request timed out')));
    });
    assert(text.startsWith('HTTP/1.1 403 '),`status line ${text.split('\r\n')[0]}`);
    assert(text.includes('"code":"LOCAL_HOST_REFUSED"'),'the body does not hold LOCAL_HOST_REFUSED: '+text.slice(0,300));
  });
  await check('local: Host 127.0.0.1 with no port is 403 LOCAL_HOST_REFUSED',localRefused({headers:{host:'127.0.0.1'}}));
  await check('local: Host 127.0.0.1:R (the other listener\'s port) is 403 LOCAL_HOST_REFUSED',localRefused({headers:{host:`127.0.0.1:${R}`}}));
  await check('local: Host 127.0.0.1.evil.example:P is 403 LOCAL_HOST_REFUSED',localRefused({headers:{host:`127.0.0.1.evil.example:${P}`}}));
  await check('local: Host localhost.:P (a trailing dot) is 403 LOCAL_HOST_REFUSED',localRefused({headers:{host:`localhost.:${P}`}}));
  await check('local: POST /d/one/mcp with Host evil.example is 403 and reads no body',localRefused({method:'POST',path:'/d/one/mcp',headers:{host:'evil.example'},body:toolsList}));
  await check('local: OPTIONS with Host evil.example is 403 and not 204',localRefused({method:'OPTIONS',headers:{host:'evil.example',origin:'https://evil.example','access-control-request-method':'POST'}}));

  // --- no request takes the process down. Each target is sent as written, on both listeners;
  // after each one the same server still answers an ordinary request with 200.
  const LONG='/'+'a'.repeat(8999);
  const targets=[
    ['//','//',400],
    ['/%','/%',null],
    ['/d/%zz/mcp','/d/%zz/mcp',400],
    ['a target of 9000 characters',LONG,null],
    ['///evil.example/documents','///evil.example/documents',400],
    ['//evil.example/documents','//evil.example/documents',400],
    ['http://evil.example/documents (absolute form)','http://evil.example/documents',400],
    ['/documents?%=%zz&a=%','/documents?%=%zz&a=%',null]
  ];
  const stillServing=async()=>{
    assert(server.exitCode===null,`the server exited with code ${server.exitCode}`);
    const local=await call(P);
    assert(local.status===200,`the next ordinary request on the first listener answered ${local.status}`);
    const far=await call(R,{headers:{host:HOSTNAME,'cf-access-jwt-assertion':good}});
    assert(far.status===200,`the next ordinary request on the remote listener answered ${far.status}`);
  };
  const answered=(res,label,status)=>{
    if(label==='/documents?%=%zz&a=%'){assert(res.status===200,`status ${res.status}, wanted 200: a query that does not decode is not a malformed target`);return}
    assert(res.status>=400&&res.status<500,`status ${res.status}, wanted 4xx: ${res.text.slice(0,200)}`);
    if(status!==null)assert(res.status===status,`status ${res.status}, wanted ${status}: ${res.text.slice(0,200)}`);
    assert(res.json&&res.json.ok===false&&typeof res.json.code==='string',`the answer is not a typed refusal: ${res.text.slice(0,200)}`);
    if(label.startsWith('//')||label.startsWith('http')){
      assert(res.json.code==='REQUEST_MALFORMED',`code ${res.json.code}, wanted REQUEST_MALFORMED`);
      assert(typeof res.json.message==='string'&&res.json.message!=='','REQUEST_MALFORMED carries no message');
    }
    assert(!res.text.includes('evil')&&!res.text.includes('aaaaaaaaaaaaaaaa')&&!res.text.includes('%zz'),`the answer repeats the request target: ${res.text.slice(0,200)}`);
  };
  for(const [label,target,status] of targets){
    await check(`local: GET ${label} is answered and the server still serves`,async()=>{
      let res;
      try{res=await call(P,{path:target})}catch(error){throw new Error(`no answer (${String(error.message||error)}); the server ${server.exitCode===null?'is running':'exited with code '+server.exitCode}`)}
      answered(res,label,status);
      await stillServing();
    });
    await check(`remote: GET ${label} with the good token is answered and the server still serves`,async()=>{
      let res;
      try{res=await call(R,{path:target,headers:{host:HOSTNAME,'cf-access-jwt-assertion':good}})}catch(error){throw new Error(`no answer (${String(error.message||error)}); the server ${server.exitCode===null?'is running':'exited with code '+server.exitCode}`)}
      answered(res,label,status);
      await stillServing();
    });
  }
  await check('remote: GET // without a token is 401 before the target is read',async()=>{
    refused(await call(R,{path:'//',headers:{host:HOSTNAME}}),401,'ACCESS_TOKEN_MISSING','token_missing');
  });
  await check('local: POST // with a body is 400 REQUEST_MALFORMED and the server still serves',async()=>{
    const res=await call(P,{method:'POST',path:'//',body:toolsList});
    assert(res.status===400&&res.json&&res.json.code==='REQUEST_MALFORMED',`status ${res.status}: ${res.text.slice(0,200)}`);
    await stillServing();
  });

  await check('the certs server was requested exactly once',async()=>{
    assert(certsRequests===1,`requested ${certsRequests} times`);
  });
  await check('the server printed no token and no claim',async()=>{
    for(const token of sentTokens){
      for(const part of token.split('.'))if(part.length>=16)assert(!serverOutput.includes(part),'the server output holds a part of a token');
    }
    assert(!serverOutput.includes('user-1'),'the server output holds a claim');
    assert(serverOutput.includes(`Remote listener http://127.0.0.1:${R}, host ${HOSTNAME}, Access team ${TEAM}`),'the remote listener line is missing: '+serverOutput);
  });
  await check('the start-up line names the hostname, the team, the audiences and the certs URL',async()=>{
    const line=serverOutput.split(/\r?\n/).find(text=>text.startsWith('Remote listener '))||'';
    assert(line===`Remote listener http://127.0.0.1:${R}, host ${HOSTNAME}, Access team ${TEAM}, audiences aud-1,aud-2, keys from ${certsUrl}`,'the remote listener line is: '+line);
  });
  await check('the server logged no unhandled error while it was sent malformed requests',async()=>{
    assert(!/unhandledRejection|uncaughtException/.test(serverOutput),'the server output holds: '+serverOutput.split(/\r?\n/).filter(text=>/unhandledRejection|uncaughtException/.test(text)).join(' | '));
    assert(server.exitCode===null,`the server exited with code ${server.exitCode}`);
  });
  // A server that must refuse its arguments: its exit code and what it printed, within 5 seconds.
  // It is this script's own child and is stopped only if it outlives the 5 seconds.
  const startAndExit=extraArgs=>new Promise(resolve=>{
    const child=spawn(process.execPath,[SERVER,...extraArgs],{cwd:ROOT,stdio:['ignore','pipe','pipe']});
    let output='';
    child.stdout.on('data',chunk=>output+=chunk);
    child.stderr.on('data',chunk=>output+=chunk);
    const timer=setTimeout(()=>{child.kill();resolve({code:'still running after 5 seconds',output})},5000);
    child.on('close',exitCode=>{clearTimeout(timer);resolve({code:exitCode,output})});
    child.on('error',error=>{clearTimeout(timer);resolve({code:String(error.message||error),output})});
  });
  await check('--remote-port alone exits with code 1 within 5 seconds',async()=>{
    const {code}=await startAndExit(['--remote-port',String(R)]);
    assert(code===1,`exit ${code}`);
  });
  const P2=await freePort();
  const R2=await freePort();
  const withCerts=url=>['--root',rootDir,'--port',String(P2),'--remote-port',String(R2),'--access-hostname',HOSTNAME,'--access-team',TEAM,'--access-aud','aud-1','--access-certs-url',url];
  for(const url of ['http://example.test/certs','http://127.0.0.1.example.test/certs','http://localhost.example.test/certs','ftp://127.0.0.1/certs','file:///C:/certs.json','certs','https://user:pw@example.test/certs']){
    await check(`--access-certs-url ${url} exits with code 1 within 5 seconds and one line`,async()=>{
      const {code,output}=await startAndExit(withCerts(url));
      assert(code===1,`exit ${code}: ${output}`);
      const lines=output.split(/\r?\n/).filter(text=>text!=='');
      assert(lines.length===1&&lines[0].includes('--access-certs-url'),`printed ${lines.length} lines: ${output}`);
      assert(!lines[0].includes('pw@'),'the message repeats the credentials in the address');
    });
  }
  // The accepted forms start: the server answers on its first port, then this script stops it.
  for(const url of ['https://example.test/certs','http://localhost:9/certs','http://[::1]:9/certs']){
    await check(`--access-certs-url ${url} is accepted`,async()=>{
      const child=spawn(process.execPath,[SERVER,...withCerts(url)],{cwd:ROOT,stdio:['ignore','pipe','pipe']});
      let output='';
      child.stdout.on('data',chunk=>output+=chunk);
      child.stderr.on('data',chunk=>output+=chunk);
      try{
        let up=false;
        for(let i=0;i<300&&!up&&child.exitCode===null;i+=1){
          try{up=(await call(P2)).status===200}catch(_){}
          if(!up)await new Promise(resolve=>setTimeout(resolve,50));
        }
        assert(up,`the server did not start (exit ${child.exitCode}): ${output}`);
        assert(output.includes(`keys from ${url}`),'the start-up line does not name the certs URL: '+output);
      }finally{
        if(child.exitCode===null){child.kill();await new Promise(resolve=>child.on('close',resolve))}
      }
    });
  }
  // A server with a default document and no remote listener: the unprefixed routes and a query
  // are read as before, and the loopback Host rule and the malformed-target answer hold there too.
  await check('a --file server answers /editor?live=1, POST /mcp and a query, refuses Host evil.example, and survives GET //',async()=>{
    const file=path.join(tempDir,'default.sov');
    fs.copyFileSync(path.join(ROOT,'examples/01-source-hold.sov'),file);
    const child=spawn(process.execPath,[SERVER,'--file',file,'--port',String(P2)],{cwd:ROOT,stdio:['ignore','pipe','pipe']});
    let output='';
    child.stdout.on('data',chunk=>output+=chunk);
    child.stderr.on('data',chunk=>output+=chunk);
    try{
      let up=false;
      for(let i=0;i<300&&!up&&child.exitCode===null;i+=1){
        try{up=(await call(P2,{path:'/editor?live=1'})).status===200}catch(_){}
        if(!up)await new Promise(resolve=>setTimeout(resolve,50));
      }
      assert(up,`GET /editor?live=1 never answered 200 (exit ${child.exitCode}): ${output.slice(0,300)}`);
      const editor=await call(P2,{path:'/editor?live=1'});
      assert(String(editor.headers['content-type']).startsWith('text/html'),`/editor content-type ${editor.headers['content-type']}`);
      const tools=await call(P2,{method:'POST',path:'/mcp',body:toolsList});
      assert(tools.status===200&&tools.json&&tools.json.result&&tools.json.result.tools.length>0,`POST /mcp status ${tools.status}`);
      const listed=await call(P2,{path:'/documents?a=1&b=%zz'});
      assert(listed.status===200&&listed.json&&Array.isArray(listed.json.documents),`GET /documents?a=1&b=%zz status ${listed.status}`);
      refused(await call(P2,{path:'/editor?live=1',headers:{host:'evil.example'}}),403,'LOCAL_HOST_REFUSED','host_not_loopback');
      for(const target of ['//','/%','/%zz/mcp','/api/v1/%zz',LONG]){
        const res=await call(P2,{path:target});
        // The default document's surface answers a GET it has no route for with its own index
        // (200), so only `//` has one right status here; the others must not be a server error.
        if(target==='//')assert(res.status===400&&res.json&&res.json.code==='REQUEST_MALFORMED',`GET // status ${res.status}: ${res.text.slice(0,200)}`);
        assert(res.status<500,`GET ${target.slice(0,20)} status ${res.status}, wanted under 500: ${res.text.slice(0,200)}`);
        assert((await call(P2,{path:'/documents'})).status===200,`the server stopped serving after GET ${target.slice(0,20)}`);
      }
      assert(!/unhandledRejection|uncaughtException/.test(output),'the server logged an unhandled error: '+output.slice(-300));
    }finally{
      if(child.exitCode===null){child.kill();await new Promise(resolve=>child.on('close',resolve))}
    }
  });
}catch(error){
  failed=true;
  if(String(error.message)!=='check failed')console.log('FAIL '+String(error.stack||error));
}finally{
  if(server&&server.exitCode===null)server.kill();
  await new Promise(resolve=>certs.close(resolve));
  if(tempDir){try{fs.rmSync(tempDir,{recursive:true,force:true})}catch(_){}}
}
if(failures>0)console.log(`FAIL access gate check: ${failures} failed`);
process.exit(failed||failures>0?1:0);
