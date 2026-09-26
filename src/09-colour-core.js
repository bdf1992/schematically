'use strict';
// 0.1 concern: colour measurement. No DOM; shared by the editor, the audits and the server.
// Contrast is WCAG 2.2's (SC 1.4.3 text 4.5:1, large text 3:1; SC 1.4.11 non-text 3:1).
// Distinctness is measured in OKLab (Ottosson 2020) after simulating colour-vision deficiency
// with Machado, Oliveira & Fernandes 2009 (severity 1.0, applied in linear sRGB).
// A palette is judged as it is realised on screen, never as authored: see auditPalette().
(function(root,factory){
  const api=factory();
  root.SovSchematicColour=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  const WCAG=Object.freeze({text:4.5,largeText:3,nonText:3});
  // OKLab distance a categorical palette keeps between its closest pair under every simulated
  // vision. 0.02 is about one just-noticeable difference (Ottosson); 0.05 asks for two and a half.
  const CVD_FLOOR=.05;
  const VISIONS=['normal','protan','deutan','tritan'];
  const MACHADO={
    protan:[.152286,1.052583,-.204868,.114503,.786281,.099216,-.003882,-.048116,1.051998],
    deutan:[.367322,.860646,-.227968,.280085,.672501,.047413,-.011820,.042940,.968881],
    tritan:[1.255528,-.076749,-.178779,-.078411,.930809,.147602,.004733,.691367,.303900]
  };
  // Research palettes, as published. The editor's own palettes derive from these (00-state.js).
  const REFERENCES=Object.freeze({
    'okabe-ito':{colors:['#E69F00','#56B4E9','#009E73','#F0E442','#0072B2','#D55E00','#CC79A7'],source:'Okabe & Ito (2008), Color Universal Design: https://jfly.uni-koeln.de/color/'},
    'tol-bright':{colors:['#4477AA','#EE6677','#228833','#CCBB44','#66CCEE','#AA3377'],source:'Tol (2021), Colour Schemes, SRON/EPS/TN/09-002: https://personal.sron.nl/~pault/'},
    'tol-muted':{colors:['#CC6677','#332288','#DDCC77','#117733','#88CCEE','#882255','#44AA99','#999933','#AA4499'],source:'Tol (2021), Colour Schemes, SRON/EPS/TN/09-002: https://personal.sron.nl/~pault/'},
    'ibm':{colors:['#648FFF','#785EF0','#DC267F','#FE6100','#FFB000'],source:'IBM Design Library colour-blind safe palette'}
  });
  const SOURCES=Object.freeze([
    'W3C (2023), Web Content Accessibility Guidelines 2.2, SC 1.4.3 Contrast (Minimum) and SC 1.4.11 Non-text Contrast: https://www.w3.org/TR/WCAG22/',
    'Machado, Oliveira & Fernandes (2009), A Physiologically-based Model for Simulation of Color Vision Deficiency, IEEE TVCG 15(6)',
    'Ottosson (2020), A perceptual color space for image processing (OKLab): https://bottosson.github.io/posts/oklab/',
    REFERENCES['okabe-ito'].source,REFERENCES['tol-bright'].source
  ]);

  function parse(css){
    const s=String(css||'').trim();let m;
    if((m=s.match(/^#([0-9a-f]{3})$/i)))return {r:parseInt(m[1][0]+m[1][0],16),g:parseInt(m[1][1]+m[1][1],16),b:parseInt(m[1][2]+m[1][2],16),a:1};
    if((m=s.match(/^#([0-9a-f]{6})([0-9a-f]{2})?$/i)))return {r:parseInt(m[1].slice(0,2),16),g:parseInt(m[1].slice(2,4),16),b:parseInt(m[1].slice(4,6),16),a:m[2]?parseInt(m[2],16)/255:1};
    if((m=s.match(/^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:[\s,/]+([\d.]+%?))?\s*\)$/i))){
      const a=m[4]==null?1:m[4].endsWith('%')?Number(m[4].slice(0,-1))/100:Number(m[4]);
      return {r:Number(m[1]),g:Number(m[2]),b:Number(m[3]),a};
    }
    return null;
  }
  const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
  function hex(c){const h=v=>Math.round(clamp(v,0,255)).toString(16).padStart(2,'0');return '#'+h(c.r)+h(c.g)+h(c.b)}
  const toLinear=v=>{const x=v/255;return x<=.04045?x/12.92:Math.pow((x+.055)/1.055,2.4)};
  const fromLinear=v=>255*(v<=.0031308?v*12.92:1.055*Math.pow(v,1/2.4)-.055);
  function linear(c){const p=typeof c==='string'?parse(c):c;return [toLinear(p.r),toLinear(p.g),toLinear(p.b)]}
  function luminance(c){const [r,g,b]=linear(c);return .2126*r+.7152*g+.0722*b}
  function contrast(a,b){const A=luminance(a),B=luminance(b);return (Math.max(A,B)+.05)/(Math.min(A,B)+.05)}
  // Paint `top` (with its alpha, times `alpha`) over an opaque `under`.
  function over(top,under,alpha=1){
    const t=typeof top==='string'?parse(top):top,u=typeof under==='string'?parse(under):under,a=clamp((t.a??1)*alpha,0,1);
    return {r:t.r*a+u.r*(1-a),g:t.g*a+u.g*(1-a),b:t.b*a+u.b*(1-a),a:1};
  }
  const largeText=(px,weight=400)=>px>=24||(px>=18.66&&Number(weight)>=700);
  function textFloor(px,weight){return largeText(px,weight)?WCAG.largeText:WCAG.text}

  function oklab(c){
    const [r,g,b]=Array.isArray(c)?c:linear(c);
    const l=Math.cbrt(.4122214708*r+.5363325363*g+.0514459929*b),m=Math.cbrt(.2119034982*r+.6806995451*g+.1073969566*b),s=Math.cbrt(.0883024619*r+.2817188376*g+.6299787005*b);
    return [.2104542553*l+.7936177850*m-.0040720468*s,1.9779984951*l-2.4285922050*m+.4505937099*s,.0259040371*l+.7827717662*m-.8086757660*s];
  }
  function simulate(c,vision){
    const v=linear(c),M=MACHADO[vision];if(!M)return v;
    return [0,1,2].map(i=>clamp(M[i*3]*v[0]+M[i*3+1]*v[1]+M[i*3+2]*v[2],0,1));
  }
  function simulateHex(c,vision){const v=simulate(c,vision);return hex({r:fromLinear(v[0]),g:fromLinear(v[1]),b:fromLinear(v[2])})}
  function distance(a,b,vision='normal'){const A=oklab(simulate(a,vision)),B=oklab(simulate(b,vision));return Math.hypot(A[0]-B[0],A[1]-B[1],A[2]-B[2])}

  // A categorical palette as realised on `background`: every colour must reach `floor` against
  // it, and the closest pair must stay `cvdFloor` apart under every simulated vision.
  function auditPalette(colors,{background='#FFFFFF',floor=WCAG.nonText,cvdFloor=CVD_FLOOR}={}){
    const failures=[];
    const contrasts=colors.map(c=>Math.round(contrast(c,background)*100)/100);
    contrasts.forEach((r,i)=>{if(r<floor)failures.push({kind:'contrast',index:i,color:colors[i],ratio:r,need:floor})});
    const closest={};
    for(const vision of VISIONS){
      let best={d:Infinity,pair:null};
      for(let i=0;i<colors.length;i++)for(let j=i+1;j<colors.length;j++){const d=distance(colors[i],colors[j],vision);if(d<best.d)best={d,pair:[i,j]}}
      closest[vision]={distance:Math.round(best.d*1000)/1000,pair:best.pair};
      if(best.pair&&best.d<cvdFloor)failures.push({kind:'distinct',vision,pair:best.pair,colors:best.pair.map(i=>colors[i]),distance:closest[vision].distance,need:cvdFloor});
    }
    const minDistance=Math.min(...VISIONS.map(v=>closest[v].distance));
    return {ok:!failures.length,background,floor,cvdFloor,contrasts,minContrast:Math.min(...contrasts),closest,minDistance,failures};
  }

  return {WCAG,CVD_FLOOR,VISIONS,REFERENCES,SOURCES,parse,hex,luminance,contrast,over,largeText,textFloor,oklab,simulate,simulateHex,distance,auditPalette};
});
