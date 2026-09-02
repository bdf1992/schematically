'use strict';
// 0.1 Beta concern: Derived signal/voltage activation and diffusion state.

function incomingSignals(componentId,signalState){
  const colors=[],component=nodes.find(n=>n.id===componentId),placement=component?.placement||{};
  if(placement.kind==='wire'&&placement.wireId){
    const host=wires.find(w=>w.id===placement.wireId);
    if(host){
      if(wireDirectionActive(host,'forward',signalState))colors.push(signalState.colors.get(host.a));
      if((connectionConfig(host).direction==='duplex'||connectionConfig(host).direction==='reverse')&&wireDirectionActive(host,'reverse',signalState))colors.push(signalState.colors.get(host.b));
    }
  }
  for(const w of wires){
    const cfg=connectionConfig(w);
    if(cfg.direction==='forward' && w.b===componentId && wireDirectionActive(w,'forward',signalState)) colors.push(signalState.colors.get(w.a));
    else if(cfg.direction==='reverse' && w.a===componentId && wireDirectionActive(w,'reverse',signalState)) colors.push(signalState.colors.get(w.b));
    else if(cfg.direction==='duplex'){
      if(w.a===componentId && wireDirectionActive(w,'reverse',signalState)) colors.push(signalState.colors.get(w.b));
      if(w.b===componentId && wireDirectionActive(w,'forward',signalState)) colors.push(signalState.colors.get(w.a));
    }
  }
  return colors.filter(Boolean);
}
function hasValidIncoming(componentId,signalState){
  return incomingSignals(componentId,signalState).length>0;
}
function wireDirectionActive(w,direction,signalState){
  const sourceEnd=direction==='forward'?'a':'b';
  const targetEnd=direction==='forward'?'b':'a';
  const sourceComponent=sourceEnd==='a'?w.a:w.b;
  if(!signalState.active.has(sourceComponent))return false;
  if(!endpointAllowsEmit(w,sourceEnd))return false;
  if(!endpointAllowsReceive(w,targetEnd))return false;
  const operation=wireOperation(w,direction);
  if(operation!=='none'&&(!endpointAllowsAccess(w,sourceEnd,operation)||!endpointAllowsAccess(w,targetEnd,operation)))return false;
  return true;
}
function computeSignalState(){
  let active=new Set();
  nodes.forEach(n=>{ if(normalizeSignalMode(componentConfig(n))==='source') active.add(n.id); });
  for(let pass=0;pass<6;pass++){
    const probe={active,colors:new Map(nodes.map(n=>[n.id,componentConfig(n).color]))};
    const next=new Set(active);
    for(const n of nodes){
      const mode=normalizeSignalMode(componentConfig(n));
      if(mode==='source'){ next.add(n.id); continue; }
      if(mode==='relay' && hasValidIncoming(n.id,probe)) next.add(n.id);
    }
    if(next.size===active.size && [...next].every(id=>active.has(id))) break;
    active=next;
  }
  let colors=new Map();
  nodes.forEach(n=>colors.set(n.id,componentConfig(n).color));
  if(colorEngine.diffuse){
    for(let pass=0;pass<5;pass++){
      const probe={active,colors};
      const next=new Map();
      for(const n of nodes){
        const local=componentConfig(n).color;
        const incoming=incomingSignals(n.id,probe);
        next.set(n.id,mixHex([local,...incoming],[1.45,...incoming.map(()=>1)]));
      }
      colors=next;
    }
  }
  return {active,colors};
}
function wireSignalColors(w,signalState){
  const cfg=connectionConfig(w);
  const aConnection=endpointConnection(w,'a');
  const bConnection=endpointConnection(w,'b');
  // A free end has no source Component; its side of the carrier takes the connection color.
  const aSignal=signalState.colors.get(w.a)||aConnection.color;
  const bSignal=signalState.colors.get(w.b)||bConnection.color;
  const forwardLive=cfg.direction!=='none' && wireDirectionActive(w,'forward',signalState);
  const reverseLive=cfg.direction==='duplex' ? wireDirectionActive(w,'reverse',signalState) : (cfg.direction==='reverse' && wireDirectionActive(w,'reverse',signalState));
  return {
    aColor:aConnection.color,
    bColor:bConnection.color,
    carrier:mixHex([aConnection.color,bConnection.color],[1,1]),
    forwardBody:aSignal,
    reverseBody:bSignal,
    forwardLive,
    reverseLive,
    forwardBoundary:aConnection.color,
    reverseBoundary:bConnection.color,
    field:cfg.direction==='duplex'
      ? mixHex([aSignal,bSignal,aConnection.color,bConnection.color],[.32,.32,.18,.18])
      : mixHex([
          cfg.direction==='reverse'?bSignal:aSignal,
          cfg.direction==='reverse'?bConnection.color:aConnection.color,
          cfg.direction==='reverse'?aConnection.color:bConnection.color
        ],[.64,.22,.14])
  };
}
