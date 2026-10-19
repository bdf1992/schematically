'use strict';
// A fixed piece of plain JavaScript that timing QA divides by, so a limit measures the code under
// test and not the machine or the load it runs under. It never calls Schematically: per iteration a
// few small records, a Map of Sets, a canonical (sorted-key) encoding, a SHA-256 chained on the
// previous hash (checked against node's crypto), and everything kept so the heap grows. That is the
// shape of stepping a state-space run, which spends about half its time encoding and hashing.
// time() runs it once at N and returns milliseconds; it throws when the final hash is not HEAD, so the
// work cannot change without the tests that divide by it failing. Loaded by require() in node and by
// a script tag in a page (tests/state_space_perf_qa.py, tests/map_render_time_qa.py).
(function(root){
  const N=5000,HEAD='7c63af499fe3963c612d2c4ed2aa3918548dc293d19b9b14b8d7875661b56478';
  const K=new Uint32Array([0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]);
  const W=new Uint32Array(64);
  function sha(b){
    const l=b.length,m=new Uint8Array(((l+9+63)>>6)<<6);m.set(b);m[l]=0x80;const bits=l*8;
    m[m.length-4]=bits>>>24;m[m.length-3]=bits>>>16;m[m.length-2]=bits>>>8;m[m.length-1]=bits;
    let h0=0x6a09e667,h1=0xbb67ae85,h2=0x3c6ef372,h3=0xa54ff53a,h4=0x510e527f,h5=0x9b05688c,h6=0x1f83d9ab,h7=0x5be0cd19;
    for(let o=0;o<m.length;o+=64){
      for(let i=0;i<16;i++)W[i]=m[o+4*i]<<24|m[o+4*i+1]<<16|m[o+4*i+2]<<8|m[o+4*i+3];
      for(let i=16;i<64;i++){const a=W[i-15],c=W[i-2];W[i]=((a>>>7|a<<25)^(a>>>18|a<<14)^a>>>3)+W[i-7]+((c>>>17|c<<15)^(c>>>19|c<<13)^c>>>10)+W[i-16]}
      let a=h0,b2=h1,c=h2,d=h3,e=h4,f=h5,g=h6,h=h7;
      for(let i=0;i<64;i++){const t1=h+((e>>>6|e<<26)^(e>>>11|e<<21)^(e>>>25|e<<7))+(e&f^~e&g)+K[i]+W[i]|0,t2=((a>>>2|a<<30)^(a>>>13|a<<19)^(a>>>22|a<<10))+(a&b2^a&c^b2&c)|0;h=g;g=f;f=e;e=d+t1|0;d=c;c=b2;b2=a;a=t1+t2|0}
      h0=h0+a|0;h1=h1+b2|0;h2=h2+c|0;h3=h3+d|0;h4=h4+e|0;h5=h5+f|0;h6=h6+g|0;h7=h7+h|0;
    }
    return [h0,h1,h2,h3,h4,h5,h6,h7].map(x=>(x>>>0).toString(16).padStart(8,'0')).join('');
  }
  const enc=v=>v===null||typeof v!=='object'?JSON.stringify(v):Array.isArray(v)?'['+v.map(enc).join(',')+']':'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+enc(v[k])).join(',')+'}';
  const utf8=s=>{const b=new Uint8Array(s.length);for(let i=0;i<s.length;i++)b[i]=s.charCodeAt(i)&127;return b};
  function time(){
    const t0=performance.now(),kept=[],seen=new Map();let head='';
    for(let i=0;i<N;i++){
      const recs=[];
      for(let j=0;j<3+(i&1);j++){
        const rec={tick:i,entity:'e'+((i*31+j)%977),point:'p'+j,kind:'signal',value:{n:(i^j)&255,at:[i,j]}};
        if(!seen.has(rec.entity))seen.set(rec.entity,new Set());seen.get(rec.entity).add(rec.point);recs.push(rec);
      }
      head=sha(utf8(enc({after:i,records:recs,prev:head})));kept.push({hash:head,records:recs.map(r=>({...r}))});
    }
    if(head!==HEAD)throw new Error('reference workload head '+head);
    return performance.now()-t0;
  }
  const api={N,HEAD,time,sha};
  root.SovReferenceWorkload=api;
  if(typeof module==='object'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
