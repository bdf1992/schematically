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
  const ROUTE_MODES=['auto','guided','pinned','bus'];
  // Buses (LAYOUT-MODEL.md "As built: buses"): a route declared once per layout, which wires name
  // instead of each finding a path. The yFiles bus descriptor model: the bus is the record, a wire
  // only names it.
  const BUS_PITCH=6,BUS_TRUNK_GAP=16,BUS_MARGIN=24,STREET_DROP=36,STREET_ROOM=12;
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
      // Buses are kept on every view; an order names only wires that exist, and a route never
      // names a bus that is gone.
      if(!isObject(v.buses))v.buses={};
      for(const [bid,b] of Object.entries(v.buses)){
        if(!isObject(b)||!busPoints(b.points)){delete v.buses[bid];continue}
        if(Array.isArray(b.order))b.order=b.order.filter(id=>doc.wires.some(w=>w.id===id));
      }
      for(const [k,rt] of Object.entries(v.routes))if(rt?.mode==='bus'&&(!Array.isArray(rt.buses)||!rt.buses.length||rt.buses.some(id=>!v.buses[id])))delete v.routes[k];
    }
    return L;
  }
  function viewRecord(doc,id){const L=ensure(doc),v=L.views[id??L.default];return v?{L,v,id:id??L.default,isDefault:(id??L.default)===L.default}:null}
  function slug(s){return String(s||'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'layout'}

  function createView(doc,{id,name,audience=null,from=null,empty=false}={}){
    const L=ensure(doc);let vid=slug(id||name);let k=2;while(L.views[vid])vid=`${slug(id||name)}-${k++}`;
    const source=from??L.default;if(!empty&&!L.views[source])return refusal('UNKNOWN_LAYOUT',`No layout ${source}`);
    L.views[vid]={name:String(name||id||vid),audience:audience||null,nodes:{},routes:empty?{}:clone(L.views[source].routes||{}),buses:empty?{}:clone(L.views[source].buses||{})};
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
  // A group (SECTION-MODEL.md "Groups (reading only)") holds Components for reading; it is never an obstacle.
  function grouping(c){return Data.normalizeSymbolId(c?.symbolId||c?.type)==='group'}
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
    if(spec.mode==='bus'){
      const ids=Array.isArray(spec.buses)?spec.buses.map(String):[];
      if(!ids.length)return refusal('BAD_BUSES','buses must name one or more buses, in the order the wire rides them');
      const missing=ids.find(id=>!r.v.buses[id]);if(missing!=null)return refusal('UNKNOWN_BUS',`No bus ${missing} on layout ${r.id}`);
      for(let i=1;i<ids.length;i++)if(!busMeet(r.v.buses[ids[i-1]].points,r.v.buses[ids[i]].points))return refusal('BUS_GAP',`Buses ${ids[i-1]} and ${ids[i]} neither cross nor touch: a wire cannot pass from one to the other`,{buses:[ids[i-1],ids[i]]});
      r.v.routes[wireId]={mode:'bus',buses:ids};
      return {ok:true,wireId,mode:'bus',buses:ids};
    }
    const pts=(spec.mode==='pinned'?spec.points:spec.via)||[];
    if(!Array.isArray(pts)||!pts.length||pts.some(p=>!Number.isFinite(Number(p?.x))||!Number.isFinite(Number(p?.y))))return refusal('BAD_POINTS',`${spec.mode==='pinned'?'points':'via'} must be one or more {x, y}`);
    r.v.routes[wireId]={mode:spec.mode,[spec.mode==='pinned'?'points':'via']:pts.map(p=>({x:Number(p.x),y:Number(p.y)}))};
    return {ok:true,wireId,mode:spec.mode};
  }
  function routeFor(doc,viewId,wireId){return doc?.layout?.views?.[viewId??defaultId(doc)]?.routes?.[wireId]||null}

  // ---- Buses --------------------------------------------------------------------------------
  // A bus's centreline: 2 or more points, every step horizontal or vertical. Anything else is null.
  function busPoints(points){
    if(!Array.isArray(points)||points.length<2)return null;
    const out=[];
    for(const p of points){
      if(!isObject(p)||p.x==null||p.y==null)return null;
      const x=Number(p.x),y=Number(p.y);if(!Number.isFinite(x)||!Number.isFinite(y))return null;out.push({x,y});
    }
    for(let i=1;i<out.length;i++)if(out[i].x!==out[i-1].x&&out[i].y!==out[i-1].y)return null;
    return out;
  }
  const busPitch=v=>Math.max(4,Math.min(16,num(v,BUS_PITCH)));
  // Where two bus centrelines meet, crossing or touching at an end: the first place found walking
  // the first bus, with the segment of each it lies on; null when they never meet. Axis-aligned
  // segments meet exactly when their boxes do.
  function busMeet(a,b){
    const A=busPoints(a),B=busPoints(b);if(!A||!B)return null;
    for(let i=1;i<A.length;i++)for(let j=1;j<B.length;j++){
      const p=A[i-1],q=A[i],s=B[j-1],t=B[j];
      const l=Math.max(Math.min(p.x,q.x),Math.min(s.x,t.x)),r=Math.min(Math.max(p.x,q.x),Math.max(s.x,t.x));
      const top=Math.max(Math.min(p.y,q.y),Math.min(s.y,t.y)),bottom=Math.min(Math.max(p.y,q.y),Math.max(s.y,t.y));
      if(l<=r+1e-6&&top<=bottom+1e-6)return {x:(l+r)/2,y:(top+bottom)/2,a:i-1,b:j-1};
    }
    return null;
  }
  function wiresOnBus(v,busId){return Object.entries(v.routes||{}).filter(([,rt])=>rt?.mode==='bus'&&Array.isArray(rt.buses)&&rt.buses.includes(busId)).map(([id])=>id).sort()}
  function setBus(doc,viewId,a={}){
    const r=viewRecord(doc,viewId);if(!r)return refusal('UNKNOWN_LAYOUT',`No layout ${viewId}`);
    const id=String(a.id??'').trim();if(!id)return refusal('BAD_BUS','A bus needs an id');
    const pts=busPoints(a.points);if(!pts)return refusal('BAD_POINTS','points must be 2 or more {x, y}, every step horizontal or vertical');
    const bus={points:pts,pitch:busPitch(a.pitch)};
    if(a.label!=null&&String(a.label).trim())bus.label=String(a.label);
    if(Array.isArray(a.between)&&a.between.length===2)bus.between=a.between.map(String);
    if(a.order!=null){
      if(!Array.isArray(a.order))return refusal('BAD_ORDER','order is a list of wire ids');
      const unknown=a.order.find(w=>!doc.wires.some(x=>x.id===String(w)));if(unknown!=null)return refusal('UNKNOWN_WIRE',`No wire ${unknown}`);
      bus.order=[...new Set(a.order.map(String))];
    }
    r.v.buses[id]=bus;
    return {ok:true,id,view:r.id,bus:clone(bus),wires:wiresOnBus(r.v,id)};
  }
  // Removing a bus returns every wire that named it to the router.
  function removeBus(doc,viewId,id){
    const r=viewRecord(doc,viewId);if(!r)return refusal('UNKNOWN_LAYOUT',`No layout ${viewId}`);
    if(!r.v.buses[id])return refusal('UNKNOWN_BUS',`No bus ${id} on layout ${r.id}`);
    const freed=wiresOnBus(r.v,id);delete r.v.buses[id];for(const w of freed)delete r.v.routes[w];
    return {ok:true,id,view:r.id,removed:true,wires:freed};
  }
  function listBuses(doc,viewId){
    const r=viewRecord(doc,viewId);if(!r)return refusal('UNKNOWN_LAYOUT',`No layout ${viewId}`);
    return {ok:true,view:r.id,buses:Object.keys(r.v.buses).sort().map(id=>({id,...clone(r.v.buses[id]),wires:wiresOnBus(r.v,id)}))};
  }

  // ---- Harness: trunks between two groups, streets in their row gaps ---------------------------
  // VLSI standard-cell channel routing: cards sit in rows, wires run in the channels between. One
  // trunk per wire label in the gap between the groups; a card with another card between it and
  // the trunk reaches it along a street in the gap under its row (sending) or above it (receiving).
  const busSlug=s=>String(s||'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'unlabelled';
  function harness(doc,viewId,{between,pitch}={}){
    const r=viewRecord(doc,viewId);if(!r)return refusal('UNKNOWN_LAYOUT',`No layout ${viewId}`);
    if(!Array.isArray(between)||between.length!==2||String(between[0])===String(between[1]))return refusal('BAD_BETWEEN','between names two different groups: [groupA, groupB]');
    const ids=between.map(String),groups=ids.map(id=>doc.components.find(c=>c.id===id));
    for(let k=0;k<2;k++)if(!groups[k]||!grouping(groups[k]))return refusal('UNKNOWN_GROUP',`No group ${ids[k]}`);
    const P=busPitch(pitch);
    // The group regions as this layout draws them.
    const placedDoc=r.isDefault?doc:{...doc,components:doc.components.map(c=>{const g=!hosted(c)&&!grouping(c)?geometry(doc,r.id,c.id):null;return g&&g.w?{...c,x:g.x,y:g.y,config:{...(c.config||{}),presentation:{...(c.config?.presentation||{}),size:{w:g.w,h:g.h}}}}:c})};
    const rects=groups.map(g=>Data.groupRect(placedDoc,g.id,size));
    const members=groups.map(g=>new Set((Array.isArray(g.config?.members)?g.config.members:[]).map(String)));
    // Worked for a vertical trunk (groups side by side); stacked groups swap x and y in and out.
    const gapX=Math.max(rects[1].l-rects[0].r,rects[0].l-rects[1].r),gapY=Math.max(rects[1].t-rects[0].b,rects[0].t-rects[1].b);
    const vertical=gapX>=gapY,sw=p=>vertical?{x:p.x,y:p.y}:{x:p.y,y:p.x};
    const R=rects.map(q=>vertical?{l:q.l,r:q.r,t:q.t,b:q.b}:{l:q.t,r:q.b,t:q.l,b:q.r});
    const left=(R[0].l+R[0].r)<=(R[1].l+R[1].r)?0:1,right=1-left,gapL=R[left].r,gap=R[right].l-gapL;
    const towardTrunkIsRight=k=>k===left;
    const side=id=>members[0].has(id)?0:members[1].has(id)?1:-1,labelOf=w=>String(w.config?.label||'');
    const wires=doc.wires.filter(w=>{const sa=side(w.a),sb=side(w.b);if(sa<0||sb<0||sa===sb)return false;const m=r.v.routes[w.id]?.mode;return m!=='pinned'&&m!=='guided'});
    if(!wires.length)return refusal('NO_WIRES',`No wire free to route runs between ${ids[0]} and ${ids[1]}`);
    const labels=[...new Set(wires.map(labelOf))].sort((a,b)=>a<b?-1:a>b?1:0),lanes=labels.map(l=>wires.filter(w=>labelOf(w)===l).length);
    const total=lanes.reduce((s,n)=>s+n*P,0)+BUS_TRUNK_GAP*(labels.length-1),need=total+2*BUS_MARGIN;
    if(!(gap>=need))return refusal('GAP_TOO_NARROW',`The gap between ${ids[0]} and ${ids[1]} is ${Math.floor(Math.max(0,gap))} wide; ${labels.length} trunk${labels.length===1?'':'s'} carrying ${wires.length} wires need ${Math.ceil(need)}`,{need:Math.ceil(need),have:Math.floor(Math.max(0,gap))});
    const trunkX=new Map(),trunkId=l=>`harness-${ids[0]}-${ids[1]}-${busSlug(l)}`;
    {let at=gapL+(gap-total)/2;labels.forEach((l,i)=>{trunkX.set(l,at+lanes[i]*P/2);at+=lanes[i]*P+BUS_TRUNK_GAP})}
    // Rows: members whose cards overlap vertically, top to bottom.
    const lay=[0,1].map(k=>{
      const items=[...members[k]].map(id=>{const c=doc.components.find(x=>x.id===id);if(!c||hosted(c)||grouping(c))return null;const g=geometry(doc,r.id,id);if(!g||g.w==null)return null;
        const s=sw(g),w=vertical?g.w:g.h,h=vertical?g.h:g.w;return {id,l:s.x-w/2,r:s.x+w/2,t:s.y-h/2,b:s.y+h/2}}).filter(Boolean).sort((a,b)=>a.t-b.t||a.l-b.l||(a.id<b.id?-1:1));
      const rows=[];for(const it of items){const row=rows.at(-1);if(row&&it.t<row.b){row.items.push(it);row.b=Math.max(row.b,it.b)}else rows.push({t:it.t,b:it.b,items:[it]})}
      return {items:new Map(items.map(it=>[it.id,it])),rows};
    });
    // A direct line: no other member of its group between the card and the trunk, inside its row band.
    const direct=(k,id)=>{const m=lay[k].items.get(id);if(!m)return true;return ![...lay[k].items.values()].some(o=>o.id!==id&&o.t<m.b&&o.b>m.t&&(towardTrunkIsRight(k)?o.l>=m.r:o.r<=m.l))};
    const rowOf=(k,id)=>lay[k].rows.findIndex(row=>row.items.some(it=>it.id===id));
    const ours=b=>Array.isArray(b?.between)&&b.between.length===2&&ids.includes(b.between[0])&&ids.includes(b.between[1]);
    // A street id another harness already uses takes the next free suffix.
    const streetId=base=>{let id=base,k=2;while(r.v.buses[id]&&!ours(r.v.buses[id]))id=`${base}-${k++}`;return id};
    const streets=new Map();
    const street=(k,ri,kind,w)=>{const id=streetId(`street-${groups[k].id}-${ri}${kind==='recv'?'-above':''}`);if(!streets.has(id))streets.set(id,{k,row:ri,kind,wires:[],labels:new Set()});const s=streets.get(id);s.wires.push(w.id);s.labels.add(labelOf(w));return id};
    const plan=wires.map(w=>{const sa=side(w.a),sb=side(w.b);
      return {w,trunk:trunkId(labelOf(w)),send:direct(sa,w.a)?null:street(sa,rowOf(sa,w.a),'send',w),recv:direct(sb,w.b)?null:street(sb,rowOf(sb,w.b),'recv',w)}});
    const made=[];let top=Math.min(R[0].t,R[1].t),bottom=Math.max(R[0].b,R[1].b);
    for(const [id,s] of streets){
      const rows=lay[s.k].rows,row=rows[s.row],span=(s.wires.length-1)*P,G=R[s.k];let y;
      if(s.kind==='send'){
        const next=rows[s.row+1],first=row.b+STREET_DROP;y=first+span/2;
        if(next&&first+span+STREET_ROOM>next.t)return refusal('STREET_TOO_NARROW',`Street ${id} under row ${s.row} of ${groups[s.k].id} needs ${Math.ceil(STREET_DROP+span+STREET_ROOM)} between the rows; it has ${Math.floor(next.t-row.b)}`,{street:id,need:Math.ceil(STREET_DROP+span+STREET_ROOM),have:Math.floor(next.t-row.b)});
      }else{
        const prev=rows[s.row-1],last=row.t-STREET_DROP;y=last-span/2;
        if(prev&&last-span-STREET_ROOM<prev.b)return refusal('STREET_TOO_NARROW',`Street ${id} above row ${s.row} of ${groups[s.k].id} needs ${Math.ceil(STREET_DROP+span+STREET_ROOM)} between the rows; it has ${Math.floor(row.t-prev.b)}`,{street:id,need:Math.ceil(STREET_DROP+span+STREET_ROOM),have:Math.floor(row.t-prev.b)});
      }
      const xs=[...s.labels].map(l=>trunkX.get(l)),to=towardTrunkIsRight(s.k)?Math.max(...xs):Math.min(...xs),far=towardTrunkIsRight(s.k)?G.l:G.r;
      made.push({id,kind:'street',lanes:s.wires.length,points:[{x:far,y},{x:to,y}]});
      top=Math.min(top,y-span/2);bottom=Math.max(bottom,y+span/2);
    }
    {const byId=new Intl.Collator('en',{numeric:true}).compare;made.sort((a,b)=>byId(a.id,b.id))}
    labels.forEach((l,i)=>made.splice(i,0,{id:trunkId(l),kind:'trunk',label:l||null,lanes:lanes[i],points:[{x:trunkX.get(l),y:top},{x:trunkX.get(l),y:bottom}]}));
    const pointsOf=new Map(made.map(b=>[b.id,b.points.map(sw)]));
    for(const p of plan){const seq=[p.send,p.trunk,p.recv].filter(Boolean);for(let i=1;i<seq.length;i++)if(!busMeet(pointsOf.get(seq[i-1]),pointsOf.get(seq[i])))return refusal('BUS_GAP',`Buses ${seq[i-1]} and ${seq[i]} would not meet`,{buses:[seq[i-1],seq[i]]})}
    // Write: this pair's earlier harness goes, its wires return to the router unless routed again.
    const old=Object.keys(r.v.buses).filter(id=>ours(r.v.buses[id]));
    for(const id of old)delete r.v.buses[id];
    const freed=[];for(const [wid,rt] of Object.entries(r.v.routes))if(rt?.mode==='bus'&&rt.buses.some(id=>old.includes(id))){delete r.v.routes[wid];if(!plan.some(p=>p.w.id===wid))freed.push(wid)}
    for(const b of made)r.v.buses[b.id]={points:pointsOf.get(b.id),pitch:P,between:ids,...(b.label?{label:b.label}:{})};
    for(const p of plan)r.v.routes[p.w.id]={mode:'bus',buses:[p.send,p.trunk,p.recv].filter(Boolean)};
    return {ok:true,view:r.id,between:ids,orientation:vertical?'vertical':'horizontal',gap:{have:Math.floor(gap),need:Math.ceil(need)},
      buses:made.map(b=>({id:b.id,kind:b.kind,lanes:b.lanes,...(b.label?{label:b.label}:{})})),
      wires:plan.map(p=>({id:p.w.id,buses:[p.send,p.trunk,p.recv].filter(Boolean)})),returnedToAuto:freed.sort()};
  }

  // ---- Layered layout -----------------------------------------------------------------------
  // Left to right by wire direction: cycles broken, longest-path layers, barycentre ordering,
  // then each node pulled level with its predecessors where it fits, for straight chains. A
  // container is laid out inside first, sized to fit, then placed as one node of its parent.
  function layered(doc,viewId,{scope=null,gapX=80,gapY=56,pad=44,labelMargin=16}={}){
    const r=viewRecord(doc,viewId);if(!r)return refusal('UNKNOWN_LAYOUT',`No layout ${viewId}`);
    const scopeCanvas=scope?interiorOf(scope):Data.GLOBAL_CANVAS_ID;
    if(scope&&!doc.components.some(c=>c.id===scope))return refusal('UNKNOWN_NODE',`No component ${scope}`);
    const byId=new Map(doc.components.map(c=>[c.id,c])),frozen=[];
    const N=(typeof globalThis!=='undefined'?globalThis:{}).SovSchematicNotation,resolvedNotation=N?N.resolve(doc):null,notation=resolvedNotation?.ok?resolvedNotation.notation:null;
    // One label width estimate, used for both the column gap a label crosses and the row gap a
    // same-column label spans: characters at the caption size, 0.6 of its size each, plus the
    // margin on both sides. A wire whose label a bus on its route carries draws no label of its
    // own (LAYOUT-MODEL.md "As built: buses"), so it widens nothing here either.
    const capSize=notation&&N?N.drawnSize(notation.tokens.type,'caption'):9;
    const lineHeight=capSize*1.15;
    const labelEstimate=text=>text.length*capSize*.6+2*labelMargin;
    const labelOnBus=w=>{
      const rt=r.v.routes[w.id],text=String(w.config?.label||'');
      if(!text||!rt||rt.mode!=='bus'||!Array.isArray(rt.buses))return false;
      return rt.buses.some(bid=>String(r.v.buses?.[bid]?.label||'')===text);
    };
    // A group is drawn around its members wherever they land, so it is not a card to place.
    const inScope=canvas=>doc.components.filter(c=>!hosted(c)&&!grouping(c)&&(c.canvasId||Data.GLOBAL_CANVAS_ID)===canvas);
    const isContainer=c=>c.form?.regions?.interior?.state==='open'&&Number(c.form?.dimension??2)===2;
    // A container drawing its own symbol keeps it clear of its children; a section's skin counts too.
    const topRoom=c=>{const g=c?.config?.presentation?.graphic?.kind;const s=Data.componentSection?Data.componentSection(c):null;
      return (g&&g!=='none'?64:18)+(s&&s.lines.length>=2?s.bands.reduce((a,b)=>a+b.thickness,0):0)};
    function rep(id,canvas){
      let c=byId.get(id),guard=0;
      while(c&&guard++<64){
        if(c.placement?.kind==='edge'){const h=byId.get(c.placement.hostId);if((h?.canvasId||Data.GLOBAL_CANVAS_ID)===canvas)return h.id;c=h;continue}
        if((c.canvasId||Data.GLOBAL_CANVAS_ID)===canvas&&!hosted(c))return c.id;
        const owner=String(c.canvasId||'').startsWith('canvas:component:')?byId.get(String(c.canvasId).slice(17)):null;if(!owner)return null;c=owner;
      }
      return null;
    }
    // A group on the canvas is placed as one block (SECTION-MODEL.md "Never an obstacle"): its
    // members are laid out by arrange() over the wires among them, exactly as a container's
    // interior is, and the block, padded as groupRect pads a region, is then one node of the
    // canvas. This is the clustered layered drawing: Graphviz dot clusters (Gansner, Koutsofios,
    // North and Vo 1993), ELK Layered SEPARATE_CHILDREN, and Forster (GD 2002) for the order:
    // barycentre over the blocks first, then within each block. A canvas with no group runs
    // arrange() once over its cards, as before groups were placed.
    const GROUP_PAD=24,GROUP_TITLE_BAND=28; // groupRect's padding (src/05-data-core.js)
    function layoutCanvas(canvas){
      const members=inScope(canvas),boxes=new Map();
      for(const c of members){
        // Arranging fits a container to what it holds, with room on top for its own symbol.
        if(isContainer(c)&&inScope(interiorOf(c.id)).length){const inner=layoutCanvas(interiorOf(c.id)),top=topRoom(c);boxes.set(c.id,{w:Math.max(160,inner.w+pad*2),h:Math.max(120,inner.h+pad*2+top),inner,top})}
        else boxes.set(c.id,{...size(c),inner:null});
      }
      const R=id=>rep(id,canvas);
      // Each member in scope belongs to the first group in document order that lists it (the
      // lister groupFindings names); a later group listing it again draws its region into that
      // block. A group with no member of its own here is left out.
      const here=new Set(members.map(c=>c.id)),blockOf=new Map();
      for(const g of doc.components){
        if(!grouping(g)||!Array.isArray(g.config?.members))continue;
        for(const m of g.config.members)if(here.has(m)&&!blockOf.has(m))blockOf.set(m,g.id);
      }
      if(!blockOf.size)return arrange(members.map(c=>c.id),boxes,R,canvas,null);
      const blocks=new Map();
      for(const c of members)if(blockOf.has(c.id)){const k=blockOf.get(c.id);if(!blocks.has(k))blocks.set(k,[]);blocks.get(k).push(c.id)}
      // A block's box is its members' extent padded as the region is drawn.
      const layoutBlock=(ids,startKey)=>{
        const res=arrange(ids,boxes,R,canvas,startKey);let l=Infinity,r=-Infinity,t=Infinity,b=-Infinity;
        for(const u of ids){const B=boxes.get(u),x=res.x.get(u),y=res.y.get(u);l=Math.min(l,x-B.w/2);r=Math.max(r,x+B.w/2);t=Math.min(t,y-B.h/2);b=Math.max(b,y+B.h/2)}
        return {w:r-l+2*GROUP_PAD,h:b-t+2*GROUP_PAD+GROUP_TITLE_BAND,inner:null,block:{res,l,t}};
      };
      // The canvas: blocks and ungrouped cards, in the order their first card comes.
      const top=[];for(const c of members){const u=blockOf.get(c.id)||c.id;if(!top.includes(u))top.push(u)}
      const R2=id=>{const u=R(id);return u&&blockOf.has(u)?blockOf.get(u):u};
      const placeCanvas=made=>{const tb=new Map();for(const u of top)tb.set(u,made.has(u)?made.get(u):boxes.get(u));return arrange(top,tb,R2,canvas,null)};
      const made=new Map();for(const [k,ids] of blocks)made.set(k,layoutBlock(ids,null));
      const first=placeCanvas(made);
      // Within each block: each layer starts in the order of the mean height of the cards its
      // members are wired to outside the block, then the canvas is placed again.
      const atY=new Map();
      for(const u of first.ids){const b=first.boxes.get(u);if(!b.block){atY.set(u,first.y.get(u));continue}
        for(const m of b.block.res.ids)atY.set(m,first.y.get(u)-b.h/2+GROUP_PAD+GROUP_TITLE_BAND+b.block.res.y.get(m)-b.block.t)}
      for(const [k,ids] of blocks){
        const sum=new Map();
        for(const w of doc.wires){const a=R(w.a),b=R(w.b);if(!a||!b||a===b)continue;
          for(const [m,o] of [[a,b],[b,a]])if(blockOf.get(m)===k&&blockOf.get(o)!==k&&atY.has(o)){const s=sum.get(m)||[0,0];s[0]+=atY.get(o);s[1]++;sum.set(m,s)}}
        made.set(k,layoutBlock(ids,new Map([...sum].map(([m,[s,n]])=>[m,s/n]))));
      }
      return placeCanvas(made);
    }
    // The layered steps over one set of nodes: ids in document order, their boxes, and R mapping
    // a wire end to the node it lands on (a wire whose ends land outside ids is not drawn here).
    // startKey, when given, sets each layer's starting order before the barycentre sweeps: keyed
    // nodes sorted by key among their own places, the rest kept where they are.
    function arrange(ids,boxes,R,canvas,startKey){
      const succ=new Map(ids.map(i=>[i,new Set()])),pred=new Map(ids.map(i=>[i,new Set()]));
      // How far below q's centre u's centre sits when the wire between them runs straight:
      // the difference of the two terminals' offsets from their cards' centres.
      const portDy=(q,u)=>{
        const w=doc.wires.find(x=>(x.a===q&&x.b===u)||(x.b===q&&x.a===u));if(!w||!notation)return 0;
        const off=(id,port)=>{const c=byId.get(id);return N.terminalOffset(notation.glyphs?.[c?.symbolId],port,boxes.get(id)||size(c),{subtitle:!!String(c?.config?.subtitle||'').trim(),title:String(c?.config?.label||''),type:notation.tokens?.type})?.dy||0};
        const [qp,up]=w.a===q?[w.aSide,w.bSide]:[w.bSide,w.aSide];
        return off(q,qp)-off(u,up);
      };
      for(const w of doc.wires){
        let a=R(w.a),b=R(w.b);if(!a||!b||a===b||!succ.has(a)||!succ.has(b))continue;
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
      if(startKey)for(const L of layers){
        const slots=L.map((u,i)=>startKey.has(u)?i:-1).filter(i=>i>=0),keyed=slots.map(i=>L[i]).sort((a,b)=>startKey.get(a)-startKey.get(b));
        slots.forEach((i,k)=>{L[i]=keyed[k]});
      }
      // Barycentre sweeps.
      const pos=new Map();const index=()=>layers.forEach(L=>L.forEach((u,i)=>pos.set(u,i)));index();
      for(let sweep=0;sweep<4;sweep++){
        for(let l=1;l<layers.length;l++){const bc=u=>{const p=[...pred.get(u)];return p.length?p.reduce((s,q)=>s+pos.get(q),0)/p.length:pos.get(u)};layers[l].sort((a,b)=>bc(a)-bc(b));index()}
        for(let l=layers.length-2;l>=0;l--){const bc=u=>{const p=[...succ.get(u)];return p.length?p.reduce((s,q)=>s+pos.get(q),0)/p.length:pos.get(u)};layers[l].sort((a,b)=>bc(a)-bc(b));index()}
      }
      // Coordinates: columns by layer; rows stacked, then pulled level with predecessors.
      // A gap between columns is wide enough for the widest wire label that crosses it or has an
      // end on either side of it; a labelled wire landing in one column (both ends the same
      // layer) instead widens the row gap between the rows it joins.
      const labelGap=new Map(),rowNeed=new Map();
      for(const w of doc.wires){
        const text=String(w.config?.label||'');if(!text||labelOnBus(w))continue;
        let a=R(w.a),b=R(w.b);if(!a||!b||a===b||!layer.has(a)||!layer.has(b))continue;
        const la=layer.get(a),lb=layer.get(b);
        if(la===lb){const key=a<b?`${a}|${b}`:`${b}|${a}`;rowNeed.set(key,Math.max(rowNeed.get(key)||0,lineHeight+2*labelMargin));continue}
        const lo=Math.min(la,lb),hi=Math.max(la,lb),need=labelEstimate(text);
        for(let l=lo;l<hi;l++)labelGap.set(l,Math.max(labelGap.get(l)||0,need));
      }
      // A container's boundary Points label the crossing outside its edge: that side needs room too.
      const pointLabel=(hostId,side)=>Math.max(0,...doc.components.filter(k=>k.placement?.kind==='edge'&&k.placement.hostId===hostId&&k.placement.side===side).map(k=>String(k.config?.label||'').length*7+32));
      for(const u of ids){
        const l=layer.get(u),left=pointLabel(u,'left'),right=pointLabel(u,'right');
        if(left&&l>0)labelGap.set(l-1,Math.max(labelGap.get(l-1)||0,left));
        if(right)labelGap.set(l,Math.max(labelGap.get(l)||0,right));
      }
      // A gap wide enough for its wires: each wire beyond two that crosses it needs a channel.
      const crossing=new Map();
      for(const u of ids)for(const v of succ.get(u)){const la=layer.get(u),lb=layer.get(v);for(let l=Math.min(la,lb);l<Math.max(la,lb);l++)crossing.set(l,(crossing.get(l)||0)+doc.wires.filter(w=>(R(w.a)===u&&R(w.b)===v)||(R(w.b)===u&&R(w.a)===v)).length)}
      const x=new Map(),y=new Map();let cx=0;
      layers.forEach((L,l)=>{const w=Math.max(0,...L.map(u=>boxes.get(u).w));for(const u of L)x.set(u,cx+w/2);cx+=w+Math.max(gapX+Math.max(0,(crossing.get(l)||0)-2)*22,labelGap.get(l)||0)});
      for(const L of layers){
        let top=0,prevId=null;
        for(const u of L){
          // Level with its predecessors by the terminals the wires use, not by card centres.
          const h=boxes.get(u).h,p=[...pred.get(u)].filter(q=>y.has(q)),want=p.length?p.map(q=>y.get(q)+portDy(q,u)).sort((a,b)=>a-b)[Math.floor((p.length-1)/2)]:top+h/2;
          const at=Math.max(top+h/2,want);y.set(u,at);
          // A labelled wire joining this card to the one just above it in the same column needs
          // room for the label's line, not just the default row gap.
          const rowKey=prevId!=null?(prevId<u?`${prevId}|${u}`:`${u}|${prevId}`):null;
          const rowGap=rowKey&&rowNeed.has(rowKey)?Math.max(gapY,rowNeed.get(rowKey)):gapY;
          top=at+h/2+rowGap;prevId=u;
        }
      }
      // Back up the layers: a card with no predecessors levels with its successors instead, by the
      // terminals its wires use, where that does not collide with its column.
      for(let l=layers.length-1;l>=0;l--)for(const u of layers[l]){
        if([...pred.get(u)].length||!succ.get(u).size)continue;
        const wants=[...succ.get(u)].filter(v=>y.has(v)).map(v=>y.get(v)-portDy(u,v)).sort((a,b)=>a-b);if(!wants.length)continue;
        const h=boxes.get(u).h,col=layers[l].filter(k=>k!==u);
        const clear=t=>col.every(k=>Math.abs(y.get(k)-t)>=(boxes.get(k).h+h)/2+gapY*.5);
        const pick=[wants[Math.floor((wants.length-1)/2)],wants.at(-1),wants[0]].find(clear);if(pick!=null)y.set(u,pick);
      }
      const minY=Math.min(0,...ids.map(u=>y.get(u)-boxes.get(u).h/2));
      if(minY<0)for(const u of ids)y.set(u,y.get(u)-minY);
      // A canvas is at least as wide as the longest wire label drawn in it (12px captions, bold).
      const labelW=Math.max(0,...doc.wires.filter(w=>(w.canvasId||Data.GLOBAL_CANVAS_ID)===canvas&&w.config?.label).map(w=>String(w.config.label).length*7.4+24+(w.config?.direction==='duplex'?14:0)));
      const W=Math.max(labelW,ids.length?Math.max(...ids.map(u=>x.get(u)+boxes.get(u).w/2)):0),H=ids.length?Math.max(...ids.map(u=>y.get(u)+boxes.get(u).h/2)):0;
      return {w:W,h:H,ids,x,y,boxes};
    }
    // Write positions: a canvas is laid out in local coordinates, then translated into place.
    function write(res,originX,originY){
      for(const u of res.ids){
        const c=byId.get(u),b=res.boxes.get(u),X=originX+res.x.get(u),Y=originY+res.y.get(u);
        // A group's block: each member at the block's place plus its offset inside the block.
        if(b.block){write(b.block.res,X-b.w/2+GROUP_PAD-b.block.l,Y-b.h/2+GROUP_PAD+GROUP_TITLE_BAND-b.block.t);continue}
        if(c.editor?.pinned||c.editor?.locked){frozen.push(u);continue}
        const g=geometry(doc,r.id,u)||entityGeometry(c);
        // Hosted children ride along with their host.
        if(r.isDefault)for(const k of doc.components)if(hosted(k)&&k.placement?.hostId===u){k.x=num(k.x,0)+(X-g.x);k.y=num(k.y,0)+(Y-g.y)}
        setGeometry(doc,r.id,u,{x:X,y:Y,w:b.w,h:b.h});
        if(b.inner)write(b.inner,X-b.w/2+pad,Y-b.h/2+pad+b.top);
      }
    }
    const res=layoutCanvas(scopeCanvas);
    const cards=res=>res.ids.flatMap(u=>{const b=res.boxes.get(u);return b.block?cards(b.block.res):[u]});
    if(scope){const g=geometry(doc,r.id,scope)||entityGeometry(byId.get(scope)),top=topRoom(byId.get(scope));const w=Math.max(160,res.w+pad*2),h=Math.max(120,res.h+pad*2+top);setGeometry(doc,r.id,scope,{w,h});write(res,g.x-w/2+pad,g.y-h/2+pad+top)}
    else{
      // Keep the diagram where it was: the new layout starts at the old top-left.
      const placed=cards(res).map(u=>geometry(doc,r.id,u)).filter(Boolean);
      const ox=placed.length?Math.min(...placed.map(g=>g.x-g.w/2)):80,oy=placed.length?Math.min(...placed.map(g=>g.y-g.h/2)):80;
      write(res,ox,oy);
    }
    straighten(doc,r.id,frozen);
    return {ok:true,view:r.id,engine:'layered',placed:cards(res).length,frozen,labelMargin};
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
        const clash=doc.components.some(k=>k.id!==oid&&!hosted(k)&&!grouping(k)&&k.canvasId===o.canvasId&&(()=>{const K=box(k.id);return K&&Math.abs(K.x-next.x)<(K.w+next.w)/2+8&&Math.abs(K.y-next.y)<(K.h+next.h)/2+8})());
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
    route:(doc,a)=>route(doc,a.view,a.wireId,a.mode?{mode:a.mode,points:a.points,via:a.via,buses:a.buses}:null),
    bus:(doc,a)=>a.remove?removeBus(doc,a.view,String(a.id??'')):setBus(doc,a.view,a),
    buses:(doc,a)=>listBuses(doc,a.view),
    harness:(doc,a)=>harness(doc,a.view,a),
    apply:(doc,a)=>{if((a.engine||'layered')!=='layered')return refusal('UNKNOWN_ENGINE','engine is layered');let view=a.view;if(a.into){const made=createView(doc,{name:a.into,from:a.view,audience:a.audience});if(!made.ok)return made;view=made.id}return layered(doc,view,a)}
  };
  const READ_ONLY=new Set(['list','unplaced','buses']);
  function execute(doc,op,args={}){const fn=OPS[op];if(!fn)return refusal('UNKNOWN_OP',`Unknown layout op ${op}`,{ops:Object.keys(OPS)});return fn(doc,isObject(args)?args:{})}
  function tool(){
    return {name:'schematic.layout',description:`Arrange the document without changing what it means. op: ${Object.keys(OPS).join(' | ')}. view names a layout (default: the document's default). move {id, x,y | dx,dy} · place {id, relation: right-of|left-of|above|below, of, gap} · align {ids, axis: left|center|right|top|middle|bottom} · distribute {ids, axis: x|y, gap?} · route {wireId, mode: auto|guided|pinned|bus, points|via|buses} · bus {id, points: [{x,y}...] 2+ with horizontal or vertical steps, pitch?: 4-16 (6), label?, order?: [wireId...]} sets a bus; bus {id, remove: true} removes it and returns its wires to auto · buses {} lists every bus with the wires that name it · harness {between: [groupA, groupB], pitch?} makes one trunk per wire label in the gap between two groups, and streets in the row gaps for cards with no direct line, and routes the wires between them on those buses · apply {engine: layered, scope?: containerId, into?: new layout name, labelMargin?: margin either side of a crossing wire label's estimated width (16)} · create {name, from?, empty?} · rename {view, name} · delete {view} · set-default {view}. Refusals are typed: PINNED, LOCKED, HOSTED, UNPLACED, BAD_POINTS, UNKNOWN_BUS, BUS_GAP, GAP_TOO_NARROW, STREET_TOO_NARROW, UNKNOWN_*.`,
      inputSchema:{type:'object',properties:{op:{type:'string',enum:Object.keys(OPS)},view:{type:'string'},id:{type:'string'},ids:{type:'array',items:{type:'string'}},of:{type:'string'},relation:{type:'string'},gap:{type:'number'},x:{type:'number'},y:{type:'number'},dx:{type:'number'},dy:{type:'number'},axis:{type:'string'},wireId:{type:'string'},mode:{type:'string'},points:{type:'array'},via:{type:'array'},buses:{type:'array',items:{type:'string'}},pitch:{type:'number'},label:{type:'string'},order:{type:'array',items:{type:'string'}},remove:{type:'boolean'},between:{type:'array',items:{type:'string'},minItems:2,maxItems:2},engine:{type:'string'},scope:{type:'string'},into:{type:'string'},name:{type:'string'},from:{type:'string'},empty:{type:'boolean'},audience:{type:'string'},labelMargin:{type:'number'}},required:['op'],additionalProperties:false}};
  }
  return {DEFAULT_ID,ROUTE_MODES,views,ensure,defaultId,createView,deleteView,renameView,setDefault,geometry,setGeometry,unplaced,move,place,align,distribute,route,routeFor,busPoints,busMeet,setBus,removeBus,listBuses,harness,layered,execute,isReadOnly:op=>READ_ONLY.has(op),tool,hosted,size};
});
