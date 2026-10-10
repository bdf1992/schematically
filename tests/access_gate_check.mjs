#!/usr/bin/env node
// Drives the two listeners of mcp/server.mjs: the remote one (--remote-port), which admits a
// request only with the declared Host and a Cloudflare Access token signed by the declared team
// for a declared audience, and the first one (--port), which refuses anything that came through a
// tunnel. Everything is on loopback: this script is the certs server, and it signs its own tokens.
// tests/access_gate_qa.py runs it. Each check prints one PASS line; the first failure prints its
// name and exits 1. The server and the certs server this script started are always stopped.
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
// Every request goes through http.request so the Host header is the one the check names.
function call(port,{method='GET',path:requestPath='/documents',headers={},body=null}={}){
  return new Promise((resolve,reject)=>{
    const sent={...headers};
    if(body!==null){sent['content-type']='application/json';sent['content-length']=Buffer.byteLength(body)}
    const req=http.request({host:'127.0.0.1',port,method,path:requestPath,headers:sent,agent:false},res=>{
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

async function check(name,fn){
  try{await fn()}catch(error){
    console.log(`FAIL ${name}: ${String(error.message||error)}`);
    throw new Error('check failed');
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
  async function remote({token=null,host=HOSTNAME,origin=null,method='GET',path:requestPath='/documents',body=null}={}){
    const headers={host};
    if(token!==null){headers['cf-access-jwt-assertion']=token;sentTokens.push(token)}
    if(origin!==null)headers.origin=origin;
    const res=await call(R,{method,path:requestPath,headers,body});
    if(res.status!==200)refusals.push({token,res});
    return res;
  }
  function refused(res,status,code,reason){
    assert(res.status===status,`status ${res.status}, wanted ${status}: ${res.text}`);
    assert(res.json&&res.json.ok===false&&res.json.code===code,`code ${res.json&&res.json.code}, wanted ${code}: ${res.text}`);
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
  await check('--remote-port alone exits with code 1 within 5 seconds',async()=>{
    const lone=spawn(process.execPath,[SERVER,'--remote-port',String(R)],{cwd:ROOT,stdio:'ignore'});
    const code=await new Promise(resolve=>{
      const timer=setTimeout(()=>{lone.kill();resolve('still running after 5 seconds')},5000);
      lone.on('exit',exitCode=>{clearTimeout(timer);resolve(exitCode)});
      lone.on('error',error=>{clearTimeout(timer);resolve(String(error.message||error))});
    });
    assert(code===1,`exit ${code}`);
  });
}catch(error){
  failed=true;
  if(String(error.message)!=='check failed')console.log('FAIL '+String(error.stack||error));
}finally{
  if(server&&server.exitCode===null)server.kill();
  await new Promise(resolve=>certs.close(resolve));
  if(tempDir){try{fs.rmSync(tempDir,{recursive:true,force:true})}catch(_){}}
}
process.exit(failed?1:0);
