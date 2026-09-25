'use strict';
// 0.1 concern: layouts — named projections of one document (LAYOUT-MODEL.md). No DOM; shared by
// the browser API and the MCP/HTTP server. The default layout is the components' own geometry,
// so a reader that knows nothing of layouts sees the default. Every other layout lives in
// document.layout.views[id] = {name, audience, nodes: {id: {x, y, w, h}}, routes: {wireId: route}}.
// An entity with no position in a layout is unplaced: reported, never put at (0, 0).
(function(root,factory){
  let Data=root.SovSchematicData;
  if(!Data&&typeof module!=='undefined'&&module.exports){require('./06-attachment-core.js');Data=require('./05-data-core.js')}
  const api=factory(Data);
  root.SovSchematicLayout=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(Data){
  if(!Data)throw new Error('SovSchematicData core is required');
  const clone=Data.clone,isObject=v=>!!v&&typeof v==='object'&&!Array.isArray(v);
  const DEFAULT_ID='main',POINT=24,MAX=4096;
  const ROUTE_MODES=['auto','guided','pinned'];
  const refusal=(code,message,extra={})=>({ok:false,code,message,...extra});
  const num=(v,f)=>Number.isFinite(Number(v))?Number(v):f;

  // ---- Views ------------------------------------------------------------------------------
  function defaultId(doc){return isObject(doc?.layout)&&typeof doc.layout.default==='string'&&doc.layout.default?doc.layout.default:DEFAULT_ID}
  // Reading never writes: a document without layouts has one implicit default layout.
  function views(doc){
    const d=defaultId(doc),stored=isObject(doc?.layout?.views)?doc.layout.views:{};
    const out=[{id:d,name:stored[d]?.name||(d===DEFAULT_ID?'Main':d),audience:stored[d]?.audience||null,default:true}];
    for(const [id,v] of Object.entries(stored))if(id!==d&&isObject(v))out.push({id,name:v.name||id,audience:v.audience||null,default:false});
    return out;
  }
  function ensure(doc){
    if(!isObject(doc.layout))doc.layout={};
    const L=doc.layout;if(typeof L.default!=='string'||!L.default)L.default=DEFAULT_ID;
    if(!isObject(L.views))L.views={};
    if(!isObject(L.views[L.default]))L.views[L.default]={name:L.default===DEFAULT_ID?'Main':L.default};
    for(const [id,v] of Object.entries(L.views)){
      if(!isObject(v)){delete L.views[id];continue}
      if(typeof v.name!=='string'||!v.name)v.name=id;
      if(!isObject(v.routes))v.routes={};
      if(id===L.default)delete v.nodes;else if(!isObject(v.nodes))v.nodes={};
      // A layout never outlives what it arranges.
      if(v.nodes)for(const k of Object.keys(v.nodes))if(!doc.components.some(c=>c.id===k))delete v.nodes[k];
      for(const k of Object.keys(v.routes))if(!doc.wires.some(w=>w.id===k))delete v.routes[k];
    }
    return L;
  }
  function viewRecord(doc,id){const L=ensure(doc),v=L.views[id??L.default];return v?{L,v,id:id??L.default,isDefault:(id??L.default)===L.default}:null}
  function slug(s){return String(s||'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'layout'}

  function createView(doc,{id,name,audience=null,from=null,empty=false}={}){
    const L=ensure(doc);let vid=slug(id||name);let k=2;while(L.views[vid])vid=`${slug(id||name)}-${k++}`;
    const source=from??L.default;if(!empty&&!L.views[source])return refusal('UNKNOWN_LAYOUT',`No layout ${source}`);
    L.views[vid]={name:String(name||id||vid),audience:audience||null,nodes:{},routes:empty?{}:clone(L.views[source].routes||{})};
    if(!empty)for(const c of doc.components)if(!hosted(c)||c.placement?.kind==='edge'){const g=geometry(doc,source,c.id);if(g)L.views[vid].nodes[c.id]=g}
    return {ok:true,id:vid,view:summary(doc,vid)};
  }
  function deleteView(doc,id){
    const L=ensure(doc);if(!L.views[id])return refusal('UNKNOWN_LAYOUT',`No layout ${id}`);
    if(id===L.default)return refusal('DEFAULT_LAYOUT','The default layout is the document\'s own geometry; make another layout the default first');
    delete L.views[id];return {ok:true,id};
  }
  function renameView(doc,id,name){const L=ensure(doc);if(!L.views[id])return refusal('UNKNOWN_LAYOUT',`No layout ${id}`);L.views[id].name=String(name||id);return {ok:true,id,name:L.views[id].name}}
  // The default moves: the old default's geometry becomes a stored layout, the new one's becomes
  // the components' own. An entity the new default never placed keeps its position and is listed.
  function setDefault(doc,id){
    const L=ensure(doc);if(!L.views[id])return refusal('UNKNOWN_LAYOUT',`No layout ${id}`);if(id===L.default)return {ok:true,id,unchanged:true};
    const old=L.default,target=L.views[id],oldNodes={};
    for(const c of doc.components){if(c.placement?.kind==='edge')oldNodes[c.id]={side:c.placement.side,t:num(c.placement.t,.5)};else if(!hosted(c))oldNodes[c.id]=entityGeometry(c)}
    const kept=[];
    for(const c of doc.components){const g=target.nodes?.[c.id];if(c.placement?.kind==='edge'){if(g?.side){c.placement.side=g.side;c.placement.t=num(g.t,c.placement.t)}continue}if(hosted(c))continue;if(g)applyEntity(c,g);else kept.push(c.id)}
    L.views[old].nodes=oldNodes;delete target.nodes;L.default=id;
    return {ok:true,id,previous:old,keptPositions:kept};
  }

  // ---- Geometry -----------------------------------------------------------------------------
  function hosted(c){const k=c?.placement?.kind;return k==='edge'||k==='wire'||k==='path'}
  function size(c){
    if(Number(c?.form?.dimension)===0)return {w:POINT,h:POINT};
    const s=c?.config?.presentation?.size;
    return {w:Math.max(80,Math.min(MAX,num(s?.w,112))),h:Math.max(64,Math.min(MAX,num(s?.h,84)))};
  }
  function entityGeometry(c){const s=size(c);return {x:num(c.x,0),y:num(c.y,0),w:s.w,h:s.h}}
  function applyEntity(c,g){
    c.x=g.x;c.y=g.y;
    if(Number(c?.form?.dimension)!==0&&g.w&&g.h){c.config=c.config||{};c.config.presentation=c.config.presentation||{};c.config.presentation.size={...(c.config.presentation.size||{}),w:g.w,h:g.h}}
  }
  // A boundary Point's position along its host's edge is layout too: {side, t} per layout.
  function edgeGeometry(doc,viewId,c){
    const d=defaultId(doc),own={side:c.placement.side,t:num(c.placement.t,.5)};
    if((viewId??d)===d)return own;const g=doc.layout?.views?.[viewId]?.nodes?.[c.id];return g&&g.side?{side:g.side,t:num(g.t,own.t)}:own;
  }
  function geometry(doc,viewId,id){
    const c=doc.components.find(x=>x.id===id);if(!c)return null;
    if(c.placement?.kind==='edge')return edgeGeometry(doc,viewId,c);
    const d=defaultId(doc);if((viewId??d)===d)return entityGeometry(c);
    const g=doc.layout?.views?.[viewId]?.nodes?.[id];if(!g)return null;
    const s=size(c);return {x:num(g.x,0),y:num(g.y,0),w:num(g.w,s.w),h:num(g.h,s.h)};
  }
  function setGeometry(doc,viewId,id,g){
    const r=viewRecord(doc,viewId);if(!r)return false;const c=doc.components.find(x=>x.id===id);if(!c)return false;
    if(c.placement?.kind==='edge'){const cur=edgeGeometry(doc,r.id,c),next={side:['left','right','top','bottom'].includes(g.side)?g.side:cur.side,t:Math.max(0,Math.min(1,num(g.t,cur.t)))};
      if(r.isDefault){c.placement.side=next.side;c.placement.t=next.t}else r.v.nodes[id]=next;return true}
    const cur=geometry(doc,r.id,id)||entityGeometry(c),next={x:num(g.x,cur.x),y:num(g.y,cur.y),w:num(g.w,cur.w),h:num(g.h,cur.h)};
    if(r.isDefault)applyEntity(c,next);else r.v.nodes[id]=next;
    return true;
  }
  function unplaced(doc,viewId){
    const d=defaultId(doc);if((viewId??d)===d)return [];
    const nodes=doc.layout?.views?.[viewId]?.nodes||{};
    return doc.components.filter(c=>!hosted(c)&&!nodes[c.id]).map(c=>c.id);
  }
  function summary(doc,id){const v=views(doc).find(x=>x.id===id);return v?{...v,unplaced:unplaced(doc,id),routes:Object.keys(doc.layout?.views?.[id]?.routes||{}).length}:null}
  const interiorOf=id=>`canvas:component:${id}`;
  function descendants(doc,id){
    const out=[],queue=[id];
    while(queue.length){const p=queue.shift();for(const c of doc.components)if(c.id!==p&&(c.parentId===p||c.canvasId===interiorOf(p))&&!out.includes(c.id)){out.push(c.id);queue.push(c.id)}}
    return out;
  }

  // ---- Placement verbs ------------------------------------------------------------------------
  function need(doc,viewId,ids){
    for(const id of ids){if(!doc.components.some(c=>c.id===id))return refusal('UNKNOWN_NODE',`No component ${id}`);
      const c=doc.components.find(x=>x.id===id);if(hosted(c))return refusal('HOSTED',`${id} rides on its host (${c.placement.kind}); move the host instead`);
      if(c.editor?.pinned)return refusal('PINNED',`${id} is pinned: its geometry is frozen`);if(c.editor?.locked)return refusal('LOCKED',`${id} is locked`)}
    return null;
  }
  // Moving a container moves what it holds.
  function shift(doc,viewId,id,dx,dy){
    for(const k of [id,...descendants(doc,id)]){
      const c=doc.components.find(x=>x.id===k),g=geometry(doc,viewId,k)||(c?entityGeometry(c):null);if(!g)continue;
      if(hosted(c)){if((viewId??defaultId(doc))===defaultId(doc)){c.x=num(c.x,0)+dx;c.y=num(c.y,0)+dy}continue}
      setGeometry(doc,viewId,k,{x:g.x+dx,y:g.y+dy});
    }
  }
  function move(doc,viewId,id,to={}){
    const r=viewRecord(doc,viewId);if(!r)return refusal('UNKNOWN_LAYOUT',`No layout ${viewId}`);const bad=need(doc,r.id,[id]);if(bad)return bad;
    const c=doc.components.find(x=>x.id===id),g=geometry(doc,r.id,id)||entityGeometry(c);
    const dx=to.dx!=null?num(to.dx,0):to.x!=null?num(to.x,g.x)-g.x:0,dy=to.dy!=null?num(to.dy,0):to.y!=null?num(to.y,g.y)-g.y:0;
    if(!geometry(doc,r.id,id))setGeometry(doc,r.id,id,g); // placing an unplaced entity
    shift(doc,r.id,id,dx,dy);return {ok:true,id,view:r.id,geometry:geometry(doc,r.id,id)};
  }
  const RELATIONS={'right-of':(a,b,gap)=>({x:b.x+b.w/2+gap+a.w/2,y:b.y}),'left-of':(a,b,gap)=>({x:b.x-b.w/2-gap-a.w/2,y:b.y}),
    below:(a,b,gap)=>({x:b.x,y:b.y+b.h/2+gap+a.h/2}),above:(a,b,gap)=>({x:b.x,y:b.y-b.h/2-gap-a.h/2})};
  function place(doc,viewId,id,{relation,of,gap=64}={}){
    const r=viewRecord(doc,viewId);if(!r)return refusal('UNKNOWN_LAYOUT',`No layout ${viewId}`);
    if(!RELATIONS[relation])return refusal('UNKNOWN_RELATION',`relation is one of ${Object.keys(RELATIONS).join(', ')}`);
    const bad=need(doc,r.id,[id]);if(bad)return bad;const b=geometry(doc,r.id,of);if(!b)return refusal(doc.components.some(c=>c.id===of)?'UNPLACED':'UNKNOWN_NODE',`${of} has no position in ${r.id}`);
    const c=doc.components.find(x=>x.id===id),a=geometry(doc,r.id,id)||entityGeometry(c),t=RELATIONS[relation](a,b,num(gap,64));
    return move(doc,r.id,id,{x:t.x,y:t.y});
  }
  function align(doc,viewId,ids,{axis='middle'}={}){
    const r=viewRecord(doc,viewId);if(!r)return refusal('UNKNOWN_LAYOUT',`No layout ${viewId}`);const bad=need(doc,r.id,ids);if(bad)return bad;
    const gs=ids.map(id=>geometry(doc,r.id,id));if(gs.some(g=>!g))return refusal('UNPLACED','Every aligned entity needs a position in this layout');
    const edge={left:g=>g.x-g.w/2,right:g=>g.x+g.w/2,center:g=>g.x,top:g=>g.y-g.h/2,bottom:g=>g.y+g.h/2,middle:g=>g.y}[axis];if(!edge)return refusal('UNKNOWN_AXIS','axis is left, center, right, top, middle or bottom');
    const vals=gs.map(edge),target=axis==='left'||axis==='top'?Math.min(...vals):axis==='right'||axis==='bottom'?Math.max(...vals):vals.reduce((a,b)=>a+b,0)/vals.length;
    const horizontal=['left','center','right'].includes(axis);
    ids.forEach((id,i)=>shift(doc,r.id,id,horizontal?target-vals[i]:0,horizontal?0:target-vals[i]));
    return {ok:true,axis,ids};
  }
  function distribute(doc,viewId,ids,{axis='x',gap=null}={}){
    const r=viewRecord(doc,viewId);if(!r)return refusal('UNKNOWN_LAYOUT',`No layout ${viewId}`);const bad=need(doc,r.id,ids);if(bad)return bad;
    if(ids.length<2)return refusal('TOO_FEW','Distribute needs two or more entities');
    const key=axis==='y'?'y':'x',dim=axis==='y'?'h':'w',items=ids.map(id=>({id,g:geometry(doc,r.id,id)}));if(items.some(i=>!i.g))return refusal('UNPLACED','Every distributed entity needs a position in this layout');
    items.sort((a,b)=>a.g[key]-b.g[key]);
    if(gap!=null){let at=items[0].g[key]+items[0].g[dim]/2;for(const it of items.slice(1)){const want=at+num(gap,48)+it.g[dim]/2;shift(doc,r.id,it.id,key==='x'?want-it.g[key]:0,key==='y'?want-it.g[key]:0);at=want+it.g[dim]/2}}
    else{const a=items[0].g[key],b=items.at(-1).g[key],step=(b-a)/(items.length-1);items.forEach((it,i)=>{const want=a+step*i;shift(doc,r.id,it.id,key==='x'?want-it.g[key]:0,key==='y'?want-it.g[key]:0)})}
    return {ok:true,axis,ids:items.map(i=>i.id)};
  }
  function route(doc,viewId,wireId,spec){
    const r=viewRecord(doc,viewId);if(!r)return refusal('UNKNOWN_LAYOUT',`No layout ${viewId}`);
    if(!doc.wires.some(w=>w.id===wireId))return refusal('UNKNOWN_WIRE',`No wire ${wireId}`);
    if(spec==null||spec.mode==='auto'){delete r.v.routes[wireId];return {ok:true,wireId,mode:'auto'}}
    if(!ROUTE_MODES.includes(spec.mode))return refusal('UNKNOWN_MODE',`mode is ${ROUTE_MODES.join(', ')}`);
    const pts=(spec.mode==='pinned'?spec.points:spec.via)||[];
    if(!Array.isArray(pts)||!pts.length||pts.some(p=>!Number.isFinite(Number(p?.x))||!Number.isFinite(Number(p?.y))))return refusal('BAD_POINTS',`${spec.mode==='pinned'?'points':'via'} must be one or more {x, y}`);
    r.v.routes[wireId]={mode:spec.mode,[spec.mode==='pinned'?'points':'via']:pts.map(p=>({x:Number(p.x),y:Number(p.y)}))};
    return {ok:true,wireId,mode:spec.mode};
  }
  function routeFor(doc,viewId,wireId){return doc?.layout?.views?.[viewId??defaultId(doc)]?.routes?.[wireId]||null}

  // ---- Layered layout -----------------------------------------------------------------------
  // Left to right by wire direction: cycles broken, longest-path layers, barycentre ordering,
  // then each node pulled level with its predecessors where it fits, for straight chains. A
  // container is laid out inside first, sized to fit, then placed as one node of its parent.
  function layered(doc,viewId,{scope=null,gapX=80,gapY=56,pad=44}={}){
    const r=viewRecord(doc,viewId);if(!r)return refusal('UNKNOWN_LAYOUT',`No layout ${viewId}`);
    const scopeCanvas=scope?interiorOf(scope):Data.GLOBAL_CANVAS_ID;
    if(scope&&!doc.components.some(c=>c.id===scope))return refusal('UNKNOWN_NODE',`No component ${scope}`);
    const byId=new Map(doc.components.map(c=>[c.id,c])),frozen=[];
    const inScope=canvas=>doc.components.filter(c=>!hosted(c)&&(c.canvasId||Data.GLOBAL_CANVAS_ID)===canvas);
    const isContainer=c=>c.form?.regions?.interior?.state==='open'&&Number(c.form?.dimension??2)===2;
    function rep(id,canvas){
      let c=byId.get(id),guard=0;
      while(c&&guard++<64){
        if(c.placement?.kind==='edge'){const h=byId.get(c.placement.hostId);if((h?.canvasId||Data.GLOBAL_CANVAS_ID)===canvas)return h.id;c=h;continue}
        if((c.canvasId||Data.GLOBAL_CANVAS_ID)===canvas&&!hosted(c))return c.id;
        const owner=String(c.canvasId||'').startsWith('canvas:component:')?byId.get(String(c.canvasId).slice(17)):null;if(!owner)return null;c=owner;
      }
      return null;
    }
    function layoutCanvas(canvas){
      const members=inScope(canvas),boxes=new Map();
      for(const c of members){
        // Arranging fits a container to what it holds.
        if(isContainer(c)&&inScope(interiorOf(c.id)).length){const inner=layoutCanvas(interiorOf(c.id));boxes.set(c.id,{w:Math.max(160,inner.w+pad*2),h:Math.max(120,inner.h+pad*2+18),inner})}
        else boxes.set(c.id,{...size(c),inner:null});
      }
      const ids=members.map(c=>c.id),succ=new Map(ids.map(i=>[i,new Set()])),pred=new Map(ids.map(i=>[i,new Set()]));
      for(const w of doc.wires){
        let a=rep(w.a,canvas),b=rep(w.b,canvas);if(!a||!b||a===b||!succ.has(a)||!succ.has(b))continue;
        if(w.config?.direction==='reverse')[a,b]=[b,a];
        succ.get(a).add(b);pred.get(b).add(a);
      }
      // Break cycles: drop edges that close a cycle in a DFS from sources.
      const state=new Map(),order=[];
      const visit=u=>{state.set(u,1);for(const v of [...succ.get(u)]){if(state.get(v)===1){succ.get(u).delete(v);pred.get(v).delete(u)}else if(!state.has(v))visit(v)}state.set(u,2);order.push(u)};
      for(const u of ids.filter(i=>!pred.get(i).size))if(!state.has(u))visit(u);
      for(const u of ids)if(!state.has(u))visit(u);
      const layer=new Map();for(const u of order.reverse()){layer.set(u,Math.max(0,...[...pred.get(u)].map(p=>layer.get(p)+1).filter(Number.isFinite)))}
      const layers=[];for(const u of ids){const l=layer.get(u)||0;(layers[l]=layers[l]||[]).push(u)}
      for(let i=0;i<layers.length;i++)if(!layers[i])layers[i]=[];
      // Barycentre sweeps.
      const pos=new Map();const index=()=>layers.forEach(L=>L.forEach((u,i)=>pos.set(u,i)));index();
      for(let sweep=0;sweep<4;sweep++){
        for(let l=1;l<layers.length;l++){const bc=u=>{const p=[...pred.get(u)];return p.length?p.reduce((s,q)=>s+pos.get(q),0)/p.length:pos.get(u)};layers[l].sort((a,b)=>bc(a)-bc(b));index()}
        for(let l=layers.length-2;l>=0;l--){const bc=u=>{const p=[...succ.get(u)];return p.length?p.reduce((s,q)=>s+pos.get(q),0)/p.length:pos.get(u)};layers[l].sort((a,b)=>bc(a)-bc(b));index()}
      }
      // Coordinates: columns by layer; rows stacked, then pulled level with predecessors.
      // A gap between columns is wide enough for the widest wire label crossing it.
      const labelGap=new Map();
      for(const w of doc.wires){
        const text=String(w.config?.label||'');if(!text)continue;
        let a=rep(w.a,canvas),b=rep(w.b,canvas);if(!a||!b||!layer.has(a)||!layer.has(b))continue;
        const la=Math.min(layer.get(a),layer.get(b)),lb=Math.max(layer.get(a),layer.get(b));
        const need=text.length*7+48+(w.config?.direction==='duplex'?14:0);
        for(let l=la;l<lb;l++)labelGap.set(l,Math.max(labelGap.get(l)||0,need));
      }
      const x=new Map(),y=new Map();let cx=0;
      layers.forEach((L,l)=>{const w=Math.max(0,...L.map(u=>boxes.get(u).w));for(const u of L)x.set(u,cx+w/2);cx+=w+Math.max(gapX,labelGap.get(l)||0)});
      for(const L of layers){
        let top=0;
        for(const u of L){
          const h=boxes.get(u).h,p=[...pred.get(u)].filter(q=>y.has(q)),want=p.length?p.map(q=>y.get(q)).sort((a,b)=>a-b)[Math.floor((p.length-1)/2)]:top+h/2;
          const at=Math.max(top+h/2,want);y.set(u,at);top=at+h/2+gapY;
        }
      }
      const minY=Math.min(0,...ids.map(u=>y.get(u)-boxes.get(u).h/2));
      if(minY<0)for(const u of ids)y.set(u,y.get(u)-minY);
      const W=ids.length?Math.max(...ids.map(u=>x.get(u)+boxes.get(u).w/2)):0,H=ids.length?Math.max(...ids.map(u=>y.get(u)+boxes.get(u).h/2)):0;
      return {w:W,h:H,ids,x,y,boxes};
    }
    // Write positions: a canvas is laid out in local coordinates, then translated into place.
    function write(res,originX,originY){
      for(const u of res.ids){
        const c=byId.get(u),b=res.boxes.get(u),X=originX+res.x.get(u),Y=originY+res.y.get(u);
        if(c.editor?.pinned||c.editor?.locked){frozen.push(u);continue}
        const g=geometry(doc,r.id,u)||entityGeometry(c);
        // Hosted children ride along with their host.
        if(r.isDefault)for(const k of doc.components)if(hosted(k)&&k.placement?.hostId===u){k.x=num(k.x,0)+(X-g.x);k.y=num(k.y,0)+(Y-g.y)}
        setGeometry(doc,r.id,u,{x:X,y:Y,w:b.w,h:b.h});
        if(b.inner)write(b.inner,X-b.w/2+pad,Y-b.h/2+pad+18);
      }
    }
    const res=layoutCanvas(scopeCanvas);
    if(scope){const g=geometry(doc,r.id,scope)||entityGeometry(byId.get(scope));const w=Math.max(160,res.w+pad*2),h=Math.max(120,res.h+pad*2+18);setGeometry(doc,r.id,scope,{w,h});write(res,g.x-w/2+pad,g.y-h/2+pad+18)}
    else{
      // Keep the diagram where it was: the new layout starts at the old top-left.
      const placed=res.ids.map(u=>geometry(doc,r.id,u)).filter(Boolean);
      const ox=placed.length?Math.min(...placed.map(g=>g.x-g.w/2)):80,oy=placed.length?Math.min(...placed.map(g=>g.y-g.h/2)):80;
      write(res,ox,oy);
    }
    straighten(doc,r.id,frozen);
    return {ok:true,view:r.id,engine:'layered',placed:res.ids.length,frozen};
  }

  // Straight wires where the layout left a free choice: a boundary Point slides along its edge to
  // meet what it connects to inside, and a single-connection neighbour outside moves level with
  // it when nothing is in the way.
  function straighten(doc,viewId,frozen=[]){
    const byId=new Map(doc.components.map(c=>[c.id,c])),wiresOf=id=>doc.wires.filter(w=>w.a===id||w.b===id),other=(w,id)=>w.a===id?w.b:w.a;
    const box=id=>{const c=byId.get(id);if(!c||hosted(c))return null;return geometry(doc,viewId,id)};
    // Where a wire meets a card: its side decides where a boundary Point should line up.
    const portSide=(c,compat)=>c?.config?.ports?.[compat]?.boundary?.side||({in:'left',out:'right',control:'top'})[compat]||'right';
    const wanted=new Map();
    for(const p of doc.components){
      if(p.placement?.kind!=='edge'||p.editor?.pinned)continue;
      const host=byId.get(p.placement.hostId),H=box(host?.id);if(!H)continue;
      const e=edgeGeometry(doc,viewId,p),vertical=e.side==='left'||e.side==='right';
      const w=wiresOf(p.id).find(x=>{const o=byId.get(other(x,p.id));return o?.canvasId===interiorOf(host.id)&&box(o.id)});
      if(!w)continue;
      const nid=other(w,p.id),N=box(nid),side=portSide(byId.get(nid),w.a===nid?w.aSide:w.bSide);
      // A top or bottom point is met from above or below: line up clear of the card, not with its centre.
      const target=vertical?(side==='top'?N.y-N.h/2-36:side==='bottom'?N.y+N.h/2+36:N.y):(side==='left'?N.x-N.w/2-36:side==='right'?N.x+N.w/2+36:N.x);
      const key=`${host.id}|${e.side}`;if(!wanted.has(key))wanted.set(key,[]);wanted.get(key).push({p,target,H,vertical});
    }
    // Points sharing a side keep their distance, in the order they want to be.
    const GAP=40;
    for(const list of wanted.values()){
      list.sort((a,b)=>a.target-b.target);const H=list[0].H,vertical=list[0].vertical;
      const lo=(vertical?H.y-H.h/2:H.x-H.w/2)+16,hi=(vertical?H.y+H.h/2:H.x+H.w/2)-16;
      let prev=-Infinity;for(const it of list){it.at=Math.max(lo,Math.min(hi,Math.max(it.target,prev+GAP)));prev=it.at}
      for(let i=list.length-2;i>=0;i--)if(list[i+1].at-list[i].at<GAP)list[i].at=Math.max(lo,list[i+1].at-GAP);
      for(const it of list)setGeometry(doc,viewId,it.p.id,{t:(it.at-(vertical?H.y-H.h/2:H.x-H.w/2))/(vertical?H.h:H.w)});
    }
    for(const p of doc.components){
      if(p.placement?.kind!=='edge'||p.editor?.pinned)continue;
      const host=byId.get(p.placement.hostId),H=box(host?.id);if(!H)continue;
      const e=edgeGeometry(doc,viewId,p),vertical=e.side==='left'||e.side==='right';
      const at=vertical?H.y-H.h/2+H.h*edgeGeometry(doc,viewId,p).t:H.x-H.w/2+H.w*edgeGeometry(doc,viewId,p).t;
      for(const w of wiresOf(p.id)){
        const oid=other(w,p.id),o=byId.get(oid),O=box(oid);
        if(!O||o.canvasId!==host.canvasId||wiresOf(oid).length!==1||o.editor?.pinned||o.editor?.locked||frozen.includes(oid))continue;
        const next=vertical?{...O,y:at}:{...O,x:at};
        const clash=doc.components.some(k=>k.id!==oid&&!hosted(k)&&k.canvasId===o.canvasId&&(()=>{const K=box(k.id);return K&&Math.abs(K.x-next.x)<(K.w+next.w)/2+8&&Math.abs(K.y-next.y)<(K.h+next.h)/2+8})());
        if(!clash)shift(doc,viewId,oid,next.x-O.x,next.y-O.y);
      }
    }
  }

  // ---- One dispatch for every surface -----------------------------------------------------------
  const OPS={
    list:(doc)=>({ok:true,default:defaultId(doc),views:views(doc).map(v=>summary(doc,v.id))}),
    unplaced:(doc,a)=>({ok:true,view:a.view??defaultId(doc),unplaced:unplaced(doc,a.view)}),
    create:(doc,a)=>createView(doc,a),
    delete:(doc,a)=>deleteView(doc,a.view),
    rename:(doc,a)=>renameView(doc,a.view,a.name),
    'set-default':(doc,a)=>setDefault(doc,a.view),
    move:(doc,a)=>move(doc,a.view,a.id,a),
    place:(doc,a)=>place(doc,a.view,a.id,a),
    align:(doc,a)=>align(doc,a.view,a.ids||[],a),
    distribute:(doc,a)=>distribute(doc,a.view,a.ids||[],a),
    route:(doc,a)=>route(doc,a.view,a.wireId,a.mode?{mode:a.mode,points:a.points,via:a.via}:null),
    apply:(doc,a)=>{if((a.engine||'layered')!=='layered')return refusal('UNKNOWN_ENGINE','engine is layered');let view=a.view;if(a.into){const made=createView(doc,{name:a.into,from:a.view,audience:a.audience});if(!made.ok)return made;view=made.id}return layered(doc,view,a)}
  };
  const READ_ONLY=new Set(['list','unplaced']);
  function execute(doc,op,args={}){const fn=OPS[op];if(!fn)return refusal('UNKNOWN_OP',`Unknown layout op ${op}`,{ops:Object.keys(OPS)});return fn(doc,isObject(args)?args:{})}
  function tool(){
    return {name:'schematic.layout',description:`Arrange the document without changing what it means. op: ${Object.keys(OPS).join(' | ')}. view names a layout (default: the document's default). move {id, x,y | dx,dy} · place {id, relation: right-of|left-of|above|below, of, gap} · align {ids, axis: left|center|right|top|middle|bottom} · distribute {ids, axis: x|y, gap?} · route {wireId, mode: auto|guided|pinned, points|via} · apply {engine: layered, scope?: containerId, into?: new layout name} · create {name, from?, empty?} · rename {view, name} · delete {view} · set-default {view}. Refusals are typed: PINNED, LOCKED, HOSTED, UNPLACED, UNKNOWN_*.`,
      inputSchema:{type:'object',properties:{op:{type:'string',enum:Object.keys(OPS)},view:{type:'string'},id:{type:'string'},ids:{type:'array',items:{type:'string'}},of:{type:'string'},relation:{type:'string'},gap:{type:'number'},x:{type:'number'},y:{type:'number'},dx:{type:'number'},dy:{type:'number'},axis:{type:'string'},wireId:{type:'string'},mode:{type:'string'},points:{type:'array'},via:{type:'array'},engine:{type:'string'},scope:{type:'string'},into:{type:'string'},name:{type:'string'},from:{type:'string'},empty:{type:'boolean'},audience:{type:'string'}},required:['op'],additionalProperties:false}};
  }
  return {DEFAULT_ID,ROUTE_MODES,views,ensure,defaultId,createView,deleteView,renameView,setDefault,geometry,setGeometry,unplaced,move,place,align,distribute,route,routeFor,layered,execute,isReadOnly:op=>READ_ONLY.has(op),tool,hosted,size};
});
