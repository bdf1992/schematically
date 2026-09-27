'use strict';
// 0.1 concern: layouts in the editor (LAYOUT-MODEL.md). The document's components always hold
// the geometry of the layout on screen; this module projects another layout onto them and folds
// it back. Files, history and every API snapshot see the canonical document: the default
// layout on the components, every other layout in document.layout.views. The layout operations
// themselves live in src/08-layout-core.js, shared with the server.

const layoutState={active:null,stash:null};
const layoutSelect=document.getElementById('layoutSelect');

function activeLayoutId(){return layoutState.active||SovSchematicLayout.defaultId(diagram)}
function entityLayoutGeometry(c){
  if(c.placement?.kind==='edge')return {side:c.placement.side,t:Number(c.placement.t)};
  if(SovSchematicLayout.hosted(c))return null;
  const s=componentForm(c).dimension===0?null:componentConfig(c).presentation.size;
  return s?{x:c.x,y:c.y,w:s.w,h:s.h}:{x:c.x,y:c.y};
}
function applyLayoutGeometry(c,g){
  if(!g)return;
  if(c.placement?.kind==='edge'){if(g.side)c.placement.side=g.side;if(Number.isFinite(Number(g.t)))c.placement.t=Number(g.t);return}
  if(SovSchematicLayout.hosted(c))return;
  if(Number.isFinite(Number(g.x)))c.x=Number(g.x);if(Number.isFinite(Number(g.y)))c.y=Number(g.y);
  if(g.w&&g.h&&componentForm(c).dimension!==0){const p=componentConfig(c).presentation;p.size={...p.size,w:Number(g.w),h:Number(g.h)}}
}
const sameGeometry=(a,b)=>!!a&&!!b&&['x','y','w','h','t','side'].every(k=>a[k]===b[k]||(a[k]==null&&b[k]==null));

// Show a layout: the default's geometry is stashed while another is on screen.
function projectLayout(id){
  const views=SovSchematicLayout.views(diagram);if(!views.some(v=>v.id===id))return false;
  const def=SovSchematicLayout.defaultId(diagram);
  if(layoutState.stash){for(const c of nodes)applyLayoutGeometry(c,layoutState.stash.get(c.id));layoutState.stash=null}
  if(id!==def){
    layoutState.stash=new Map(nodes.map(c=>[c.id,entityLayoutGeometry(c)]));
    const stored=diagram.layout?.views?.[id]?.nodes||{};
    for(const c of nodes)applyLayoutGeometry(c,stored[c.id]);
  }
  layoutState.active=id===def?null:id;
  return true;
}
// The document as saved: the on-screen layout folded back into its view, the default restored.
function canonicalDiagram(){
  const d=SovSchematicData.clone(diagram);if(!layoutState.stash)return d;
  SovSchematicLayout.ensure(d);const v=d.layout.views[layoutState.active];if(!v)return d;
  for(const c of d.components){
    const was=layoutState.stash.get(c.id),now=entityLayoutGeometry(c);
    // Placed in this layout, or moved here since: it belongs to the layout. Otherwise unplaced.
    if(now&&(v.nodes[c.id]||!sameGeometry(now,was)))v.nodes[c.id]=now;
    applyLayoutGeometry(c,was);
  }
  return d;
}
// After a document load (open, undo, redo, checkpoint) the components hold the default: show
// the active layout again, or fall back to the default when it no longer exists.
function layoutAfterDocumentLoad(){
  layoutState.stash=null;const want=layoutState.active;layoutState.active=null;
  if(want&&SovSchematicLayout.views(diagram).some(v=>v.id===want))projectLayout(want);
  refreshLayoutSelect();
}
function layoutUnplacedIds(){
  const id=layoutState.active;if(!id)return [];
  const stored=diagram.layout?.views?.[id]?.nodes||{};
  return nodes.filter(c=>!SovSchematicLayout.hosted(c)&&!stored[c.id]&&sameGeometry(entityLayoutGeometry(c),layoutState.stash?.get(c.id))).map(c=>c.id);
}
function activeRouteSpec(wireId){return diagram.layout?.views?.[activeLayoutId()]?.routes?.[wireId]||null}

// A pinned or guided route: its interior points kept, the ends re-laid to meet moved terminals.
function routeThroughSpec(A,B,w,spec){
  const inner=(spec.mode==='pinned'?spec.points:spec.via)||[];if(!inner.length)return null;
  const a=nodes.find(n=>n.id===w.a),b=nodes.find(n=>n.id===w.b);
  const SA=a?routeLead(A,inner[0],w.aSide,a,wireEndpointInward(w,a)):A,SB=b?routeLead(B,inner.at(-1),w.bSide,b,wireEndpointInward(w,b)):B;
  const seq=[A,SA,...inner.map(p=>({x:p.x,y:p.y})),SB,B],out=[seq[0]];
  for(let i=1;i<seq.length;i++){const P=out.at(-1),Q=seq[i];if(Math.abs(P.x-Q.x)>.5&&Math.abs(P.y-Q.y)>.5)out.push({x:Q.x,y:P.y});out.push(Q)}
  return normalizePoints(out);
}

// Run a shared layout operation on the canonical document, then show the active layout again.
function runLayoutOp(op,args={},label=null){
  const canon=canonicalDiagram(),readOnly=SovSchematicLayout.isReadOnly(op);
  const view=args.view??activeLayoutId();
  const result=SovSchematicLayout.execute(canon,op,{...args,view});
  if(readOnly||!result.ok)return result;
  commitHistoryCapture();setHistoryHint(label||`Layout · ${op}`);
  const keep=layoutState.active;layoutState.stash=null;layoutState.active=null;
  SovSchematicData.replaceDocument(diagram,canon);
  if(keep&&SovSchematicLayout.views(diagram).some(v=>v.id===keep))projectLayout(keep);
  if(op==='create'&&args.show!==false&&result.id)projectLayout(result.id);
  if(op==='apply'&&args.into&&result.view)projectLayout(result.view);
  if(op==='set-default')projectLayout(SovSchematicLayout.defaultId(diagram));
  if(typeof normalizeRuntimeAfterCrud==='function')normalizeRuntimeAfterCrud();else render();
  commitHistoryCapture(label||`Layout · ${op}`);refreshLayoutSelect();
  return result;
}
function switchLayout(id){
  if(id===activeLayoutId())return {ok:true,id};
  const canon=canonicalDiagram();layoutState.stash=null;layoutState.active=null;
  SovSchematicData.replaceDocument(diagram,canon);
  if(!projectLayout(id))return {ok:false,code:'UNKNOWN_LAYOUT',message:`No layout ${id}`};
  routeCache.clear();arrowPoseCache.clear();if(typeof normalizeRuntimeAfterCrud==='function')normalizeRuntimeAfterCrud();else render();
  refreshLayoutSelect();const unplaced=layoutUnplacedIds();
  statusEl.textContent=`Layout · ${SovSchematicLayout.views(diagram).find(v=>v.id===id)?.name||id}${unplaced.length?` · ${unplaced.length} unplaced: Arrange places them`:''}`;
  return {ok:true,id,unplaced};
}

function refreshLayoutSelect(){
  if(!layoutSelect)return;const views=SovSchematicLayout.views(diagram),active=activeLayoutId();
  layoutSelect.replaceChildren();
  for(const v of views){const o=document.createElement('option');o.value=v.id;o.textContent=`${v.name}${v.default?' · default':''}`;layoutSelect.appendChild(o)}
  const sep=document.createElement('option');sep.disabled=true;sep.textContent='──────';layoutSelect.appendChild(sep);
  for(const [v,t] of [['__new','New layout (copy of this)'],['__arrange','Arrange left to right'],['__rename','Rename…'],['__default','Make this the default'],['__delete','Delete this layout']]){
    const o=document.createElement('option');o.value=v;o.textContent=t;
    if((v==='__default'||v==='__delete')&&active===SovSchematicLayout.defaultId(diagram))o.disabled=true;layoutSelect.appendChild(o);
  }
  layoutSelect.value=active;
}
layoutSelect?.addEventListener('change',()=>{
  const v=layoutSelect.value,active=activeLayoutId();
  if(v==='__new'){const name=window.prompt('Name the new layout','Overview');if(name)runLayoutOp('create',{name,from:active},'New layout')}
  else if(v==='__arrange')runLayoutOp('apply',{engine:'layered'},'Arrange layout');
  else if(v==='__rename'){const cur=SovSchematicLayout.views(diagram).find(x=>x.id===active);const name=window.prompt('Rename layout',cur?.name||active);if(name)runLayoutOp('rename',{view:active,name},'Rename layout')}
  else if(v==='__default')runLayoutOp('set-default',{view:active},'Make default layout');
  else if(v==='__delete'){const def=SovSchematicLayout.defaultId(diagram);switchLayout(def);runLayoutOp('delete',{view:active},'Delete layout')}
  else if(v&&!v.startsWith('__'))switchLayout(v);
  refreshLayoutSelect();
});
// A wire's Pin freezes its route in the layout on screen; unpinning returns it to the router.
function toggleWireRoutePin(w,pinned){
  if(!pinned)return runLayoutOp('route',{wireId:w.id,mode:'auto'},'Unpin route');
  const d=workspace.querySelector(`.wire-group[data-wire-id="${CSS.escape(w.id)}"] path.wire`)?.getAttribute('d');
  const corners=typeof layoutPathCorners==='function'?layoutPathCorners(d):[];
  const inner=corners.slice(1,-1);if(!inner.length)return {ok:false,code:'NO_ROUTE',message:'Nothing to pin: the wire is straight'};
  return runLayoutOp('route',{wireId:w.id,mode:'pinned',points:inner},'Pin route');
}
refreshLayoutSelect();
