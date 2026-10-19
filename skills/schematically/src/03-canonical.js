'use strict';
// 0.1 Beta concern: canonical JSON encoding (RFC 8785 / JCS for the value set in use),
// a synchronous pure-JS SHA-256, and the seeded draw used by merges and QA.
// This module is intentionally pure: no DOM, no dependencies, no async.
(function(root,factory){
  const api=factory();
  root.SovSchematicCanonical=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  function unsupported(){
    const e=new Error('CANONICAL_UNSUPPORTED: value is not a canonicalizable JSON value');
    e.code='CANONICAL_UNSUPPORTED';
    return e;
  }
  function isPlainObject(value){
    if(value===null||typeof value!=='object'||Array.isArray(value))return false;
    const proto=Object.getPrototypeOf(value);
    return proto===Object.prototype||proto===null;
  }
  // RFC 8785: object keys sorted by UTF-16 code unit; JS's default string
  // comparison (and Array#sort's default comparator on strings) is exactly that.
  function encodeValue(value){
    if(value===null)return 'null';
    const t=typeof value;
    if(t==='boolean')return value?'true':'false';
    if(t==='number'){
      if(!Number.isFinite(value))throw unsupported();
      return JSON.stringify(value); // -0 -> '0', 1e21 -> '1e+21', matches JCS number form
    }
    if(t==='string')return JSON.stringify(value);
    if(t==='undefined'||t==='function'||t==='symbol'||t==='bigint')throw unsupported();
    if(Array.isArray(value))return '['+value.map(encodeValue).join(',')+']';
    if(t==='object'){
      if(!isPlainObject(value))throw unsupported();
      const keys=Object.keys(value).sort();
      return '{'+keys.map(k=>JSON.stringify(k)+':'+encodeValue(value[k])).join(',')+'}';
    }
    throw unsupported();
  }
  function canonicalize(value){return encodeValue(value)}

  // --- SHA-256 (FIPS 180-4), synchronous, no dependencies ---
  const K=[
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
  ];
  function rotr(n,x){return ((x>>>n)|(x<<(32-n)))>>>0}
  function utf8Bytes(str){
    const bytes=[];
    for(let i=0;i<str.length;i++){
      let code=str.charCodeAt(i);
      if(code>=0xd800&&code<=0xdbff&&i+1<str.length){
        const next=str.charCodeAt(i+1);
        if(next>=0xdc00&&next<=0xdfff){
          code=0x10000+(code-0xd800)*0x400+(next-0xdc00);
          i++;
        }
      }
      if(code<0x80)bytes.push(code);
      else if(code<0x800)bytes.push(0xc0|(code>>6),0x80|(code&0x3f));
      else if(code<0x10000)bytes.push(0xe0|(code>>12),0x80|((code>>6)&0x3f),0x80|(code&0x3f));
      else bytes.push(0xf0|(code>>18),0x80|((code>>12)&0x3f),0x80|((code>>6)&0x3f),0x80|(code&0x3f));
    }
    return bytes;
  }
  function sha256Bytes(bytes){
    let h0=0x6a09e667,h1=0xbb67ae85,h2=0x3c6ef372,h3=0xa54ff53a,h4=0x510e527f,h5=0x9b05688c,h6=0x1f83d9ab,h7=0x5be0cd19;
    const msgLen=bytes.length;
    const padded=bytes.slice();
    padded.push(0x80);
    while(padded.length%64!==56)padded.push(0);
    const bitLen=msgLen*8;
    const lenHigh=Math.floor(bitLen/0x100000000)>>>0;
    const lenLow=bitLen>>>0;
    for(let i=3;i>=0;i--)padded.push((lenHigh>>>(i*8))&0xff);
    for(let i=3;i>=0;i--)padded.push((lenLow>>>(i*8))&0xff);
    const w=new Array(64);
    for(let base=0;base<padded.length;base+=64){
      for(let t=0;t<16;t++){
        const o=base+t*4;
        w[t]=((padded[o]<<24)|(padded[o+1]<<16)|(padded[o+2]<<8)|padded[o+3])>>>0;
      }
      for(let t=16;t<64;t++){
        const s0=rotr(7,w[t-15])^rotr(18,w[t-15])^(w[t-15]>>>3);
        const s1=rotr(17,w[t-2])^rotr(19,w[t-2])^(w[t-2]>>>10);
        w[t]=(w[t-16]+s0+w[t-7]+s1)>>>0;
      }
      let a=h0,b=h1,c=h2,d=h3,e=h4,f=h5,g=h6,h=h7;
      for(let t=0;t<64;t++){
        const S1=rotr(6,e)^rotr(11,e)^rotr(25,e);
        const ch=(e&f)^((~e)&g);
        const temp1=(h+S1+ch+K[t]+w[t])>>>0;
        const S0=rotr(2,a)^rotr(13,a)^rotr(22,a);
        const maj=(a&b)^(a&c)^(b&c);
        const temp2=(S0+maj)>>>0;
        h=g;g=f;f=e;e=(d+temp1)>>>0;d=c;c=b;b=a;a=(temp1+temp2)>>>0;
      }
      h0=(h0+a)>>>0;h1=(h1+b)>>>0;h2=(h2+c)>>>0;h3=(h3+d)>>>0;
      h4=(h4+e)>>>0;h5=(h5+f)>>>0;h6=(h6+g)>>>0;h7=(h7+h)>>>0;
    }
    return [h0,h1,h2,h3,h4,h5,h6,h7];
  }
  function toHex(words){return words.map(w=>w.toString(16).padStart(8,'0')).join('')}
  function sha256Hex(text){return toHex(sha256Bytes(utf8Bytes(String(text))))}

  // --- Seeded draw: rejection-sampled Fisher-Yates over a SHA-256 word stream ---
  function drawOrder(seed,keyParts,items){
    const decorated=items.map(item=>({item,key:canonicalize(item)}));
    decorated.sort((a,b)=>a.key<b.key?-1:a.key>b.key?1:0);
    const out=decorated.map(d=>d.item);
    let counter=0,words=[],idx=0;
    function nextWord(){
      if(idx>=words.length){
        const hex=sha256Hex(canonicalize([seed,...keyParts,counter]));
        counter++;
        words=[];
        for(let i=0;i<8;i++)words.push(parseInt(hex.slice(i*8,i*8+8),16)>>>0);
        idx=0;
      }
      return words[idx++];
    }
    function drawIndex(i){
      const range=i+1;
      const limit=Math.floor(4294967296/range)*range;
      let w;
      do{w=nextWord()}while(w>=limit);
      return w%range;
    }
    for(let i=out.length-1;i>0;i--){
      const j=drawIndex(i);
      const tmp=out[i];out[i]=out[j];out[j]=tmp;
    }
    return out;
  }

  return {canonicalize,sha256Hex,drawOrder};
});
