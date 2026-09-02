'use strict';
// 0.1 concern: live link. Publishes a read-only snapshot of this editor session —
// document revision, file identity, camera, appearance and the current selection —
// to a local server so an agent can observe what the operator is looking at.
//
// Off unless asked for. Enable with ?live=1 (or ?live=http://host:port) on the URL,
// or SovSchematicLive.start(). Nothing here mutates the document; the link is
// observation only, and the editor keeps working when the server is absent.

const LIVE_STORAGE_KEY='sov.live.endpoint';
// Served from the server itself, the link is same-origin and needs no port named.
// Opened from a file, there is no origin to infer, so fall back to the usual port.
const LIVE_FALLBACK_ENDPOINT='http://127.0.0.1:8787';
const LIVE_DEFAULT_ENDPOINT=(typeof location!=='undefined'&&/^https?:$/.test(location.protocol))
  ?location.origin
  :LIVE_FALLBACK_ENDPOINT;
const LIVE_MIN_INTERVAL_MS=250;      // floor between pushes while the operator is active
const LIVE_HEARTBEAT_MS=5000;        // idle push so a stale snapshot is detectable
const LIVE_BACKOFF_MS=5000;          // wait after a failed push before trying again

const liveLink={
  enabled:false,
  endpoint:LIVE_DEFAULT_ENDPOINT,
  sessionId:`browser-${Math.random().toString(36).slice(2,10)}`,
  timer:null,
  heartbeat:null,
  inFlight:false,
  lastSignature:'',
  lastPushedAt:null,
  lastError:null,
  failing:false
};

// ---------------------------------------------------------------------------
// Selection description
// ---------------------------------------------------------------------------

function liveSelectionDescriptor(){
  const setIds=[...(typeof selectedComponentIds!=='undefined'?selectedComponentIds:[])];
  // `selected` keeps its last value through a deselect, so the selection bar being
  // hidden — not the variable — is the editor's own answer to "is anything selected".
  const current=selectionBar.hidden?null:(typeof selected==='string'?selected:null);
  if(!current)return {kind:'none',ids:setIds,detail:null};

  if(current.startsWith('wire:')){
    const index=Number(current.slice(5));
    const wire=wires[index];
    if(!wire)return {kind:'none',ids:setIds,detail:null};
    const cfg=connectionConfig(wire);
    const end=(side)=>{
      const ep=carrierEndpoint(wire,side);
      if(!ep)return null;
      if(ep.kind==='bound')return {bound:true,componentId:ep.node.id,pointId:ep.pointId,marker:wireEndpointMarker(wire,side)};
      return {bound:false,x:Math.round(ep.pos.x),y:Math.round(ep.pos.y)};
    };
    return {kind:'wire',ids:[wire.id],detail:{
      id:wire.id,
      label:cfg.label||null,
      direction:cfg.direction,
      reciprocity:cfg.reciprocity,
      forwardOperation:cfg.forwardOperation??null,
      reverseOperation:cfg.reverseOperation??null,
      canvasId:wireCanvas(wire).id,
      a:end('a'),
      b:end('b'),
      record:SovSchematicData.clone(wire)
    }};
  }

  if(current.startsWith('point:component:')){
    const [,,componentId,pointId]=current.split(':');
    const owner=nodes.find(n=>n.id===componentId);
    if(!owner)return {kind:'none',ids:setIds,detail:null};
    const point=Attachment.resolveSpec(owner,pointId);
    const port=point?componentConfig(owner).ports[point.compatId]:null;
    return {kind:'point',ids:[`${componentId}:${pointId}`],detail:{
      componentId,
      componentLabel:componentConfig(owner).label||byId(owner.symbolId).name,
      pointId:point?.id??pointId,
      compatId:point?.compatId??null,
      side:point?.side??null,
      face:port?.face??null,
      label:port?.label??null,
      record:port?SovSchematicData.clone(port):null
    }};
  }

  const node=nodes.find(n=>n.id===current);
  if(!node)return {kind:'none',ids:setIds,detail:null};
  const form=componentForm(node);
  const cfg=componentConfig(node);
  return {kind:'component',ids:setIds.length?setIds:[node.id],detail:{
    id:node.id,
    label:cfg.label||null,
    symbolId:node.symbolId,
    typeName:byId(node.symbolId).name,
    canvasId:componentCanvas(node).id,
    scope:componentScopePath(node),
    dimension:form.dimension,
    interior:form.regions.interior.state,
    attachmentDefaults:cfg.attachmentDefaults??null,
    signalMode:cfg.signalMode??null,
    pointIds:Object.keys(cfg.ports||{}),
    record:SovSchematicData.clone(node)
  }};
}

// ---------------------------------------------------------------------------
// Snapshot
// ---------------------------------------------------------------------------

function liveSnapshot(){
  const selection=liveSelectionDescriptor();
  return {
    schema:'soveraeign.schematic/live@0.1',
    sessionId:liveLink.sessionId,
    at:new Date().toISOString(),
    file:{name:currentFileName,format:currentFileFormat,dirty:isFileDirty(),revision:diagram.revision},
    counts:{components:nodes.length,wires:wires.length},
    // The camera is a viewBox; zoom is how much of the base view it shows.
    view:{appearance:appearanceMode,camera:{
      x:Math.round(camera.x),y:Math.round(camera.y),w:Math.round(camera.w),h:Math.round(camera.h),
      zoom:Number((BASE_VIEW.w/camera.w).toFixed(4))
    }},
    selection,
    document:snapshotDocument()
  };
}

// A push is worth making when the operator's selection or the document changed.
// The document body is excluded from the signature: revision already covers it.
function liveSignature(snapshot){
  return JSON.stringify([snapshot.file.revision,snapshot.file.name,snapshot.selection.kind,snapshot.selection.ids,snapshot.view]);
}

// ---------------------------------------------------------------------------
// Transport
// ---------------------------------------------------------------------------

async function livePush({force=false}={}){
  if(!liveLink.enabled||liveLink.inFlight)return;
  let snapshot;
  try{snapshot=liveSnapshot()}catch(error){liveLink.lastError=String(error?.message||error);return}
  const signature=liveSignature(snapshot);
  if(!force&&signature===liveLink.lastSignature)return;
  liveLink.inFlight=true;
  try{
    const response=await fetch(`${liveLink.endpoint}/api/v1/live`,{
      method:'POST',
      headers:{'content-type':'application/json'},
      body:JSON.stringify(snapshot)
    });
    if(!response.ok)throw new Error(`HTTP ${response.status}`);
    liveLink.lastSignature=signature;
    liveLink.lastPushedAt=snapshot.at;
    liveLink.lastError=null;
    liveLink.failing=false;
  }catch(error){
    liveLink.lastError=String(error?.message||error);
    liveLink.failing=true;
  }finally{
    liveLink.inFlight=false;
  }
}

// Coalesce a burst of edits into one push, never faster than LIVE_MIN_INTERVAL_MS,
// and back off after a failure so a missing server costs one request per backoff.
function liveNotifyChanged(){
  if(!liveLink.enabled||liveLink.timer)return;
  const delay=liveLink.failing?LIVE_BACKOFF_MS:LIVE_MIN_INTERVAL_MS;
  liveLink.timer=setTimeout(()=>{liveLink.timer=null;livePush()},delay);
}

// ---------------------------------------------------------------------------
// Reload stream
// ---------------------------------------------------------------------------
// With the server in --watch mode, a change to the authoring inputs rebuilds and
// tells every open editor to reload. The drawing on the canvas is not the server's
// document, so it would be lost: it is stashed here first and picked up on load.
// The stash is separate from File > Restore Recovery, which is a deliberate act by
// a person and keeps its own key and its own meaning.

const LIVE_CARRY_KEY='sov.live.carry';
const LIVE_CARRY_MAX_AGE_MS=20000;
let liveStream=null;

function liveCarryStash(){
  try{
    localStorage.setItem(LIVE_CARRY_KEY,JSON.stringify({
      at:Date.now(),
      selection:typeof selected==='string'?selected:null,
      camera:{x:camera.x,y:camera.y,w:camera.w,h:camera.h},
      document:snapshotDocument()
    }));
  }catch(_){ }
}

function liveCarryRestore(){
  let carried=null;
  try{
    const raw=localStorage.getItem(LIVE_CARRY_KEY);
    if(!raw)return false;
    localStorage.removeItem(LIVE_CARRY_KEY);
    carried=JSON.parse(raw);
  }catch(_){return false}
  // Only a stash from the reload that just happened; anything older is somebody
  // else's tab or a stale key, and silently replacing a document would be worse
  // than losing one.
  if(!carried||Date.now()-Number(carried.at||0)>LIVE_CARRY_MAX_AGE_MS)return false;
  try{
    replaceRuntimeDocument(carried.document);
    if(carried.camera){camera.x=carried.camera.x;camera.y=carried.camera.y;camera.w=carried.camera.w;camera.h=carried.camera.h;applyCamera()}
    if(carried.selection){
      if(carried.selection.startsWith('wire:'))selectWire(Number(carried.selection.slice(5)),{focus:false});
      else if(carried.selection.startsWith('point:component:')){const [,,id,pointId]=carried.selection.split(':');selectPort(id,pointId)}
      else selectNode(carried.selection,{focus:false});
    }
    statusEl.textContent='Reloaded on rebuild';
    return true;
  }catch(error){
    statusEl.textContent=`Could not carry the document across the reload: ${error.message}`;
    return false;
  }
}

function liveOpenStream(){
  if(liveStream||typeof EventSource!=='function')return;
  try{liveStream=new EventSource(`${liveLink.endpoint}/api/v1/live/stream`)}catch(_){return}
  liveStream.addEventListener('reload',()=>{liveCarryStash();location.reload()});
  liveStream.addEventListener('build-failed',event=>{
    let detail='';
    try{detail=JSON.parse(event.data)?.error||''}catch(_){ }
    statusEl.textContent=`Build failed${detail?`: ${detail}`:''}`;
  });
  // EventSource reconnects on its own; a closed stream is not an editor error.
  liveStream.onerror=()=>{};
}

function liveCloseStream(){
  if(!liveStream)return;
  liveStream.close();liveStream=null;
}

function liveStart(endpoint){
  if(endpoint)liveLink.endpoint=String(endpoint).replace(/\/+$/,'');
  liveLink.enabled=true;
  try{localStorage.setItem(LIVE_STORAGE_KEY,liveLink.endpoint)}catch(_){ }
  if(!liveLink.heartbeat)liveLink.heartbeat=setInterval(()=>livePush({force:true}),LIVE_HEARTBEAT_MS);
  liveOpenStream();
  livePush({force:true});
  return liveStatus();
}

function liveStop(){
  liveLink.enabled=false;
  liveCloseStream();
  if(liveLink.heartbeat){clearInterval(liveLink.heartbeat);liveLink.heartbeat=null}
  if(liveLink.timer){clearTimeout(liveLink.timer);liveLink.timer=null}
  try{localStorage.removeItem(LIVE_STORAGE_KEY)}catch(_){ }
  return liveStatus();
}

function liveStatus(){
  return {
    enabled:liveLink.enabled,
    endpoint:liveLink.endpoint,
    sessionId:liveLink.sessionId,
    lastPushedAt:liveLink.lastPushedAt,
    lastError:liveLink.lastError
  };
}

// ---------------------------------------------------------------------------
// Change hooks
// ---------------------------------------------------------------------------

// The live concern stays in this file: rather than scattering notification calls
// through selection, UI and persistence, wrap the functions that mark the end of a
// selection change or a revision change. Each wrapper is transparent — same
// arguments, same return value — and installed only once, from the last module in
// the build order.
function liveWatch(name){
  const original=globalThis[name];
  if(typeof original!=='function')return;
  globalThis[name]=function(...args){
    const result=original.apply(this,args);
    liveNotifyChanged();
    return result;
  };
}
['showComponentBar','showConnectionBar','showPortBar','hideSelectionBar','updateRevisionReadout'].forEach(liveWatch);

const SovSchematicLive={
  start:liveStart,
  stop:liveStop,
  status:liveStatus,
  push:()=>livePush({force:true}),
  snapshot:liveSnapshot,
  stash:liveCarryStash,
  restore:liveCarryRestore
};
window.SovSchematicLive=SovSchematicLive;

// Autostart: ?live=1 uses the default endpoint, ?live=<url> names one, and an
// endpoint remembered from a previous session on this origin resumes the link.
(function initializeLiveLink(){
  let requested=null;
  try{
    const param=new URLSearchParams(location.search).get('live');
    if(param!==null)requested=param===''||param==='1'||param==='true'?LIVE_DEFAULT_ENDPOINT:param;
    else requested=localStorage.getItem(LIVE_STORAGE_KEY);
  }catch(_){ }
  if(!requested)return;
  liveStart(requested);
  liveCarryRestore();
})();
