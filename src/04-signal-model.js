'use strict';
// The signal model both engines read (GRAPH-MODEL.md §7): which way a port passes work (its active
// connection's flow and access), what a card's signal is (signalConfig), the combines and the
// default Wire latency. Pure, no dependencies, loaded before everything that reads it, so a run
// never depends on which other modules happen to be loaded. 07-graph-core.js re-exports it.
(function(root,factory){
  const api=factory();
  root.SovSchematicSignalModel=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  const isObject=v=>!!v&&typeof v==='object'&&!Array.isArray(v);
  const DEFAULT_LATENCY_MS=10;

  // A port authored without connections takes the data core's default for its id, the same
  // default the editor normalizes to, so the simulation and the signal view agree.
  const DEFAULT_FLOW={in:'in',out:'out',control:'control'};
  function activeConnection(port,portId){
    if(isObject(port)&&port.side==='point'&&!(Array.isArray(port.connections)&&port.connections.length))return {flow:port.flow||'duplex',access:port.access||'read-write'};
    if(!isObject(port))return null;
    const list=Array.isArray(port.connections)?port.connections:[];
    return list[Math.max(0,Math.min(list.length-1,Number(port.activeConnection)||0))]||{flow:port.flow||DEFAULT_FLOW[portId]||'duplex',access:port.access||'read-write'};
  }
  const canEmit=(p,id)=>{const c=activeConnection(p,id);return !!c&&(c.flow==='out'||c.flow==='duplex')};
  const canReceive=(p,id)=>{const c=activeConnection(p,id);return !!c&&(c.flow==='in'||c.flow==='duplex'||c.flow==='control')};
  const accessAllows=(p,op)=>{if(op==='none')return true;const a=activeConnection(p)?.access||'read-write';return a==='read-write'||a===op};

  // Signal (SIGNAL-MODEL in GRAPH-MODEL.md §7). A level is binary {0,1} or continuous [0,1].
  // Asserted: declared state, changed only by an operation (a lever, a source, a clock).
  // Derived: computed from inputs as they change over time. Without config.signal the
  // legacy signalMode decides, with the editor's default (absent = source).
  const COMBINES=['or','and','not','max','min','mean','sum','xor','nand','nor','buffer'];
  const WAVES=['square','saw','triangle','sine'];
  // `glyph` is the notation's glyph for this card: a glyph that declares a combine (a logic
  // gate) makes the card derived with that combine unless the card says otherwise.
  function signalConfig(c,glyph=null){
    const glyphCombine=COMBINES.includes(glyph?.signal?.combine)?glyph.signal.combine:null;
    let raw=isObject(c.config?.signal)?c.config.signal:null;const legacy=c.config?.signalMode;
    if(glyphCombine)raw={mode:'derived',combine:glyphCombine,...(raw||{})};
    const clockRaw=isObject(raw?.clock)?raw.clock:null;
    const assertedSymbol=c.symbolId==='lever'||c.symbolId==='clock';
    const mode=raw&&['asserted','derived'].includes(raw.mode)?raw.mode:(clockRaw||assertedSymbol?'asserted':raw?'derived':(legacy==='relay'||legacy==='passive')?'derived':'asserted');
    const wave=clockRaw&&WAVES.includes(clockRaw.wave)?clockRaw.wave:'square';
    const kind=raw&&['binary','continuous'].includes(raw.kind)?raw.kind:(clockRaw&&wave!=='square'?'continuous':'binary');
    const value=Number.isFinite(Number(raw?.value))?Math.max(0,Math.min(1,Number(raw.value))):(raw||assertedSymbol?0:(mode==='asserted'?1:0));
    const combine=raw&&COMBINES.includes(raw.combine)?raw.combine:(kind==='continuous'?'max':'or');
    const clock=clockRaw?{periodMs:Number(clockRaw.periodMs),phaseMs:Math.max(0,Number(clockRaw.phaseMs)||0),duty:Number.isFinite(Number(clockRaw.duty))?Math.max(0,Math.min(1,Number(clockRaw.duty))):.5,wave,
      sampleMs:Number(clockRaw.sampleMs)>0?Number(clockRaw.sampleMs):null,cycles:Number(clockRaw.cycles)>0?Math.floor(Number(clockRaw.cycles)):null}:null;
    return {mode,kind,value,combine,clock,declared:!!raw,
      threshold:Number.isFinite(Number(raw?.threshold))?Number(raw.threshold):.5,
      epsilon:Number(raw?.epsilon)>0?Number(raw.epsilon):.001,
      on:['+','-','±'].includes(raw?.on)?raw.on:null,channel:typeof raw?.channel==='string'?raw.channel:'edge',
      emits:raw?.emits===false?false:!(legacy==='passive'&&!raw)};
  }
  return {DEFAULT_LATENCY_MS,DEFAULT_FLOW,COMBINES,WAVES,activeConnection,canEmit,canReceive,accessAllows,signalConfig};
});
