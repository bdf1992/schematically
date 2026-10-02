'use strict';
// State space concern (STATE-SPACE.md). Slice 1a, the contract layer: the state record
// envelope, the closed pattern registry (truth_table@1, merge@1), definitions and the minimal
// pack envelope, contracts generated from pattern + parameters, ports generated from a bound
// definition, and the load checks. Slice 1b, the first runs: the hash-chained ledger, the
// replay key, two-phase ticks with merges, the trace and replay. Slice 1c: settle, the passive
// state query, the run receipt and the run registry each surface keeps beside its document, never in it.
// Pure: no DOM, no pack data (packs are passed in), validation hand-written.
(function(root,factory){
  let Canonical=root.SovSchematicCanonical;
  if(!Canonical&&typeof module!=='undefined'&&module.exports)Canonical=require('./03-canonical.js');
  let Model=root.SovSchematicSignalModel;
  if(!Model&&typeof module!=='undefined'&&module.exports)Model=require('./04-signal-model.js');
  let Data=root.SovSchematicData;
  if(!Data&&typeof module!=='undefined'&&module.exports)Data=require('./05-data-core.js');
  const api=factory(Canonical,Data,Model);
  root.SovSchematicStateSpace=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(Canonical,Data,Model){
  if(!Canonical)throw new Error('SovSchematicCanonical core is required');
  if(!Data)throw new Error('SovSchematicData core is required');
  if(!Model)throw new Error('SovSchematicSignalModel (src/04-signal-model.js) is required');
  const RECORD_FORMAT='soveraeign.schematic/state-record@0.1';
  const PACK_FORMAT='soveraeign.schematic/pack@0.1';
  const clone=value=>value==null?value:JSON.parse(JSON.stringify(value));
  const isObject=value=>!!value&&typeof value==='object'&&!Array.isArray(value);
  const nonEmpty=value=>typeof value==='string'&&value.length>0;
  const natural=value=>Number.isInteger(value)&&value>=0;
  const same=(x,y)=>{try{return Canonical.canonicalize(x)===Canonical.canonicalize(y)}catch(_){return false}};
  function unknownKeys(value,allowed,where,errors){
    for(const key of Object.keys(value))if(!allowed.includes(key))errors.push(`${where}: unknown key ${key}`);
  }

  // --- The state record (STATE-SPACE.md "The state record"). Any other key, at any level, is refused.
  const VANTAGES=['space','point','relative'];
  const KINDS=['registered','measured','derived','predicted'];
  // `state` is a device's memory (observable device.state, vantage point): a JSON object whose numbers are safe integers.
  const FORMS=['binary','continuous','categorical','message','state'];
  const TIME_MODES=['observed','predicted'];
  const PERTURBATIONS=['none','disturbed','created'];
  const RECORD_KEYS=['format','id','subject','vantage','reference','observable','kind','form','value','time','certainty','observer','provenance','perturbation','principal','hop','level'];
  // A message is a recorded value on the message channel: its value names it ({id, root, parent,
  // channel, payload, origin}); the record's principal says who it acts for and its hop what
  // happened to it here. The hop events are the graph core's (src/07-graph-core.js).
  const MESSAGE_KEYS=['id','root','parent','channel','payload','origin'];
  const HOP_EVENTS=['injected','arrived','sent','crossed','forwarded','delivered','refused','handled','absorbed','observed','buffered','released','waiting','joined','parked','resumed','replayed','ambiguous','controlled','asserted','edge'];
  const HOP_KEYS=['event','wire','to','reason','parkId','effectKey'];
  // The first number in a JSON value that is not a safe integer, as {path, value}, or null.
  function firstFraction(value,path){
    if(typeof value==='number')return Number.isSafeInteger(value)?null:{path,value};
    if(Array.isArray(value)){for(let i=0;i<value.length;i++){const f=firstFraction(value[i],`${path}[${i}]`);if(f)return f}return null}
    if(isObject(value)){for(const key of Object.keys(value).sort()){const f=firstFraction(value[key],`${path}.${key}`);if(f)return f}return null}
    return null;
  }
  function checkMessageValue(v,errors){
    if(!isObject(v)){errors.push('value must be an object {id, root, parent, channel, payload, origin} for form message');return}
    unknownKeys(v,MESSAGE_KEYS,'value',errors);
    for(const key of ['id','root','origin'])if(!nonEmpty(v[key]))errors.push(`value.${key} must be a non-empty string`);
    if(v.parent!==null&&!nonEmpty(v.parent))errors.push('value.parent must be null or a non-empty string');
    if(v.channel!==null&&typeof v.channel!=='string')errors.push('value.channel must be null or a string');
    if(v.payload===undefined)errors.push('value.payload must be present (null when empty)');
    else{
      try{Canonical.canonicalize(v.payload)}catch(_){errors.push('value.payload must be JSON')}
      const fraction=firstFraction(v.payload,'value.payload');
      if(fraction)errors.push(`${fraction.path} must be a safe integer (no floating point), not ${JSON.stringify(fraction.value)}`);
    }
  }
  function validateRecord(record){
    const errors=[];
    if(!isObject(record))return {ok:false,errors:['record must be an object']};
    unknownKeys(record,RECORD_KEYS,'record',errors);
    if(record.format!==RECORD_FORMAT)errors.push(`format must equal ${RECORD_FORMAT}`);
    if(!nonEmpty(record.id))errors.push('id must be a non-empty string');
    const subject=record.subject;
    if(!isObject(subject))errors.push('subject must be an object');
    else{
      unknownKeys(subject,['entity','run','point','channel','attempt'],'subject',errors);
      for(const key of ['entity','run'])if(!nonEmpty(subject[key]))errors.push(`subject.${key} must be a non-empty string`);
      for(const key of ['point','channel'])if(subject[key]!==undefined&&!nonEmpty(subject[key]))errors.push(`subject.${key} must be a non-empty string`);
      if(subject.attempt!==undefined&&!natural(subject.attempt))errors.push('subject.attempt must be an integer >= 0');
    }
    if(!VANTAGES.includes(record.vantage))errors.push(`vantage must be one of ${VANTAGES.join(', ')}`);
    if(record.vantage==='relative'){if(!nonEmpty(record.reference))errors.push('reference must be a non-empty string when vantage is relative')}
    else if(record.reference!==undefined)errors.push('reference is only allowed when vantage is relative');
    if(!nonEmpty(record.observable))errors.push('observable must be a non-empty string');
    if(!KINDS.includes(record.kind))errors.push(`kind must be one of ${KINDS.join(', ')}`);
    if(!FORMS.includes(record.form))errors.push(`form must be one of ${FORMS.join(', ')}`);
    else{
      const v=record.value;
      if(record.form==='binary'&&typeof v!=='boolean')errors.push('value must be a boolean for form binary');
      if(record.form==='continuous'&&!(typeof v==='number'&&Number.isFinite(v)))errors.push('value must be a finite number for form continuous');
      if(record.form==='categorical'&&typeof v!=='string')errors.push('value must be a string for form categorical');
      if(record.form==='message')checkMessageValue(v,errors);
      if(record.form==='state'){
        if(!isObject(v))errors.push('value must be an object for form state');
        else{
          try{Canonical.canonicalize(v)}catch(_){errors.push('value must be JSON for form state')}
          const fraction=firstFraction(v,'value');
          if(fraction)errors.push(`${fraction.path} must be a safe integer (no floating point), not ${JSON.stringify(fraction.value)}`);
        }
      }
    }
    if(record.principal!==undefined&&record.principal!==null&&!nonEmpty(record.principal))errors.push('principal must be null or a non-empty string');
    // A plane crossing's own refusal (STATE-SPACE.md, access control): level true marks it apart
    // from a message's hop refused, the same acl: reason text the graph core gives.
    if(record.level!==undefined&&typeof record.level!=='boolean')errors.push('level must be a boolean');
    if(record.hop!==undefined){
      const hop=record.hop;
      if(record.form!=='message')errors.push('hop is only allowed on a record of form message');
      if(!isObject(hop))errors.push('hop must be an object');
      else{
        unknownKeys(hop,HOP_KEYS,'hop',errors);
        if(!HOP_EVENTS.includes(hop.event))errors.push(`hop.event must be one of ${HOP_EVENTS.join(', ')}`);
        for(const key of HOP_KEYS.slice(1))if(hop[key]!==undefined&&!nonEmpty(hop[key]))errors.push(`hop.${key} must be a non-empty string`);
      }
    }
    const time=record.time;
    if(!isObject(time))errors.push('time must be an object');
    else{
      unknownKeys(time,['logical','sequence','mode'],'time',errors);
      for(const key of ['logical','sequence'])if(!natural(time[key]))errors.push(`time.${key} must be an integer >= 0`);
      if(!TIME_MODES.includes(time.mode))errors.push(`time.mode must be one of ${TIME_MODES.join(', ')}`);
    }
    const certainty=record.certainty;
    if(!isObject(certainty))errors.push('certainty must be an object');
    else{unknownKeys(certainty,['kind'],'certainty',errors);if(certainty.kind!=='exact')errors.push('certainty.kind must be exact')}
    if(!nonEmpty(record.observer))errors.push('observer must be a non-empty string');
    const provenance=record.provenance;
    if(!isObject(provenance))errors.push('provenance must be an object');
    else{
      unknownKeys(provenance,['rule','inputs','threshold'],'provenance',errors);
      if(provenance.threshold!==undefined&&!(typeof provenance.threshold==='number'&&Number.isFinite(provenance.threshold)))errors.push('provenance.threshold must be a finite number');
      if(!nonEmpty(provenance.rule))errors.push('provenance.rule must be a non-empty string');
      if(!Array.isArray(provenance.inputs)||!provenance.inputs.every(nonEmpty))errors.push('provenance.inputs must be an array of non-empty strings');
    }
    if(!PERTURBATIONS.includes(record.perturbation))errors.push(`perturbation must be one of ${PERTURBATIONS.join(', ')}`);
    return {ok:errors.length===0,errors};
  }

  // --- Patterns: a small closed set; a definition instantiates one with parameters.
  const NAME=/^[a-z][a-z0-9_]*$/;
  function checkNames(value,key,errors){
    if(!Array.isArray(value)||value.length<1||value.length>8){errors.push(`${key} must be an array of 1 to 8 names`);return false}
    let ok=true;
    for(const name of value)if(typeof name!=='string'||!NAME.test(name)){errors.push(`${key}: ${JSON.stringify(name)} is not a name matching ${NAME.source}`);ok=false}
    if(ok&&new Set(value).size!==value.length){errors.push(`${key} repeats a name`);ok=false}
    return ok;
  }
  const truthTable={
    id:'truth_table',version:1,class:'exact',stateful:false,blastRadius:'local',
    validate(parameters){
      const errors=[];
      if(!isObject(parameters))return ['parameters must be an object'];
      unknownKeys(parameters,['inputs','outputs','table'],'parameters',errors);
      const inputsOk=checkNames(parameters.inputs,'inputs',errors),outputsOk=checkNames(parameters.outputs,'outputs',errors);
      if(inputsOk&&outputsOk){
        const overlap=parameters.outputs.filter(name=>parameters.inputs.includes(name));
        if(overlap.length)errors.push(`outputs overlap inputs: ${overlap.join(', ')}`);
      }
      const table=parameters.table;
      if(!Array.isArray(table)){errors.push('table must be an array of rows');return errors}
      if(!inputsOk||!outputsOk)return errors;
      const n=parameters.inputs.length,width=n+parameters.outputs.length,seen=new Set();
      table.forEach((row,i)=>{
        if(!Array.isArray(row)||row.length!==width){errors.push(`table row ${i} must be an array of ${width} cells`);return}
        if(!row.every(cell=>cell===0||cell===1)){errors.push(`table row ${i} must hold only 0 and 1`);return}
        const key=row.slice(0,n).join('');
        if(seen.has(key))errors.push(`table row ${i} repeats the input combination ${key}`);
        seen.add(key);
      });
      if(!errors.length&&seen.size!==2**n)errors.push(`table covers ${seen.size} of the ${2**n} input combinations`);
      return errors;
    },
    derive(parameters){
      const port=flow=>id=>({id,flow,channels:[{id:'main'}],observable:'logic.level',form:'binary'});
      return {
        inputs:parameters.inputs.map(port('in')),
        outputs:parameters.outputs.map(port('out')),
        state:null,
        observables:[{id:'logic.level',form:'binary',unit:null,blastRadius:'local',staleness:0}]
      };
    },
    evaluate(parameters,inputValues){
      const n=parameters.inputs.length;
      const key=parameters.inputs.map(name=>{
        const v=inputValues?.[name];
        if(typeof v!=='boolean')throw new Error(`EVALUATE_INPUT: input ${name} must be a boolean`);
        return v?1:0;
      }).join('');
      const row=parameters.table.find(r=>r.slice(0,n).join('')===key);
      if(!row)throw new Error(`EVALUATE_INPUT: the table has no row for ${key}`);
      const out={};parameters.outputs.forEach((name,i)=>{out[name]=row[n+i]===1});
      return out;
    }
  };
  const merge={
    id:'merge',version:1,class:'exact',stateful:false,blastRadius:'local',
    // One validator for a channel merge, shared with the data core's edit check.
    validate(parameters){return Data.validateMerge(parameters)},
    derive(parameters){
      const orderDependent=!['or','and','min','max','sum'].includes(parameters.combine);
      return {orderDependent,order:orderDependent?clone(parameters.order??{kind:'stochastic'}):null};
    }
  };
  // No floating point in a run. A level is a boolean on a binary channel and an integer 0..LEVEL on a
  // continuous one, LEVEL being 2^20: binary fractions (a half, a quarter turn) are exact and halving is
  // a shift. Every combine, threshold, wave and time is integer arithmetic, so a run is the same bytes
  // on every engine. An authored fraction (a threshold of .5, a latency of 2.5 ms) is converted to an
  // integer once, where the document is read.
  const LEVEL=1<<20;
  const toLevel=x=>Math.max(0,Math.min(LEVEL,Math.round(Number(x)*LEVEL)||0));
  const levelOf=v=>v===true?LEVEL:Number.isSafeInteger(v)?Math.max(0,Math.min(LEVEL,v)):0;
  const idiv=(a,b)=>(a-a%b)/b;
  // An output equals what its port holds: booleans exactly (absent is false), levels within epsilon (absent is 0).
  const sameLevel=(value,held,epsilon)=>typeof value==='number'?Math.abs(value-levelOf(held))<=epsilon:value===(held===true);
  // cos(2*pi*u/LEVEL) in LEVEL units, from integers only: fold u into the first quarter turn (exact,
  // LEVEL being a power of two), then the Taylor series at scale LEVEL; every product stays far below
  // 2^53 and every division is an exact integer division. TWO_PI is 2*pi*2^20, rounded once.
  const TWO_PI=6588397;
  function cosLevel(u){
    u=((u%LEVEL)+LEVEL)%LEVEL;if(u>LEVEL/2)u=LEVEL-u;
    let sign=1;if(u>LEVEL/4){u=LEVEL/2-u;sign=-1}
    const x=idiv(u*TWO_PI,LEVEL),x2=idiv(x*x,LEVEL);
    let term=LEVEL,sum=LEVEL;
    for(let k=1;k<=7;k++){term=-idiv(idiv(term*x2,LEVEL),(2*k-1)*(2*k));sum+=term}
    return sign*Math.max(-LEVEL,Math.min(LEVEL,sum));
  }
  // combine@1: the graph core's level model as a pattern. Every incoming Wire is its own input (the
  // latest level it delivered); control inputs gate: open when any is at or over the threshold. The
  // output is the combine over the data inputs, 0 while closed. COMBINES are the graph core's.
  const COMBINE_OPS={or:v=>Math.max(0,...v),max:v=>Math.max(0,...v),and:v=>v.length?Math.min(...v):0,min:v=>v.length?Math.min(...v):0,
    not:v=>LEVEL-Math.max(0,...v),nand:v=>LEVEL-(v.length?Math.min(...v):0),nor:v=>LEVEL-Math.max(0,...v),buffer:v=>Math.max(0,...v),
    xor:v=>v.filter(x=>x>=LEVEL/2).length%2*LEVEL,mean:v=>v.length?idiv(v.reduce((a,b)=>a+b,0),v.length):0,sum:v=>Math.min(LEVEL,v.reduce((a,b)=>a+b,0))};
  const combinePattern={
    id:'combine',version:1,class:'exact',stateful:false,blastRadius:'local',
    validate(parameters){
      const errors=[];
      if(!isObject(parameters))return ['parameters must be an object'];
      unknownKeys(parameters,['combine','kind','threshold','epsilon','data','control','outputs'],'parameters',errors);
      if(!Object.keys(COMBINE_OPS).includes(parameters.combine))errors.push(`combine must be one of ${Object.keys(COMBINE_OPS).join(', ')}`);
      if(!['binary','continuous'].includes(parameters.kind))errors.push('kind must be binary or continuous');
      for(const key of ['threshold','epsilon'])if(!Number.isSafeInteger(parameters[key])||parameters[key]<0||parameters[key]>LEVEL)errors.push(`${key} must be an integer 0..${LEVEL} (millionths)`);
      for(const key of ['data','control','outputs'])if(!Array.isArray(parameters[key])||!parameters[key].every(nonEmpty))errors.push(`${key} must be an array of port names`);
      return errors;
    },
    derive(parameters){
      const port=flow=>id=>({id,flow,channels:[{id:'main'}],observable:'logic.level',form:'binary'});
      return {inputs:[...parameters.data.map(port('in')),...parameters.control.map(port('control'))],outputs:parameters.outputs.map(port('out')),state:null,
        observables:[{id:'logic.level',form:'binary',unit:null,blastRadius:'local',staleness:0}]};
    },
    // A binary card quantizes at its threshold (a boolean); a continuous one keeps the level.
    evaluate(parameters,inputValues){
      const open=!parameters.control.length||Math.max(...parameters.control.map(name=>levelOf(inputValues?.[name])))>=parameters.threshold;
      const v=Math.max(0,Math.min(LEVEL,open?COMBINE_OPS[parameters.combine](parameters.data.map(name=>levelOf(inputValues?.[name]))):0)),out={};
      for(const name of parameters.outputs)out[name]=parameters.kind==='continuous'?v:v>=parameters.threshold;
      return out;
    }
  };
  // --- Flow patterns: what a card does with a message (the graph core's arrive and forward,
  // src/07-graph-core.js at 7b939e3, lines cited per pattern). They act on the message channel only;
  // a card's level is still its signal model or its bound definition, so one card may have both. A
  // flow pattern generates no ports, so no Component binds one through config.definition: a card
  // reaches one only through the binding lookup (flowBindingOf below). A stateful one reads its own
  // device.state and the engine commits what it leaves as a device.state record at the end of the
  // tick. Instance settings (by, key, capacity, releaseMs, rate, handler) are the card's config.flow
  // and config.behavior, read once at start by flowSettings, as the graph core's flowConfig reads them.
  // Each method works on the state it is handed; the engine writes every record.
  const DEVICE_STATE={id:'device.state',form:'state',unit:null,blastRadius:'local',staleness:0};
  function readPath(obj,path){if(!path)return undefined;let v=obj;for(const k of String(path).split('.')){if(v==null)return undefined;v=v[k]}return v}
  // The graph core's fnv (src/07-graph-core.js:265 at 7b939e3), over the key's canonical text.
  function fnv(s){let h=0x811c9dc5;for(const ch of String(s)){h^=ch.charCodeAt(0);h=Math.imul(h,0x01000193)>>>0}return h}
  function flowPattern(id,{kinds=null,key='policy',stateful=true,initial=()=>null,...methods}){
    return {id,version:1,class:'exact',stateful,blastRadius:'local',messages:true,...methods,
      validate(parameters){
        const errors=[];
        if(!isObject(parameters))return ['parameters must be an object'];
        unknownKeys(parameters,kinds?[key]:[],'parameters',errors);
        if(kinds&&!kinds.includes(parameters[key]))errors.push(`${key} must be one of ${kinds.join(', ')}`);
        return errors;
      },
      initial,
      derive(parameters){return {state:initial(parameters),observables:stateful?[clone(DEVICE_STATE)]:[]}}
    };
  }
  // route@1 (334-352): fanout to every open end; distribute to one, by round-robin (the counter is
  // device.state), by channel or by the fnv of the canonical key; select refuses without a handler.
  const routePattern=flowPattern('route',{kinds:['fanout','distribute','select'],initial:()=>({rr:0}),
    choose(parameters,state,settings,message,open){
      if(parameters.policy==='select')return {refuse:'select needs a handler (config.behavior.handler)'};
      if(parameters.policy!=='distribute')return {legs:open.map((_,i)=>i)};
      if(settings.by==='channel'){
        const i=open.findIndex(leg=>leg.accepts&&message.value.channel&&leg.accepts.includes(message.value.channel));
        return i<0?{refuse:`no end declares channel ${message.value.channel}`}:{legs:[i]};
      }
      if(settings.by==='key'){
        const k=readPath({...message.value,principal:message.principal},settings.key);
        if(k===undefined)return {refuse:`message has no key ${settings.key}`};
        return {legs:[fnv(Canonical.canonicalize(k))%open.length]};
      }
      const i=state.rr%open.length;state.rr++;
      return {legs:[i]};
    }});
  // join@1 (412-421): one FIFO per incoming Path in device.state; when every Path has one, the joined
  // message's payload is {parts: {wireId: payload}}.
  const joinPattern=flowPattern('join',{initial:()=>({fifos:{}}),
    intake(parameters,state,settings,message){
      const w=message.via??'',item={message:copy(message.value),principal:message.principal??null};
      (state.fifos[w]=state.fifos[w]||[]).push(item);
      return {wait:'waiting',item,ready:settings.incoming.every(x=>(state.fifos[x]||[]).length>0)};
    },
    take(parameters,state,settings){
      const parts={},taken=[];
      for(const w of settings.incoming){const item=state.fifos[w].shift();if(!state.fifos[w].length)delete state.fifos[w];parts[w]=copy(item.message.payload);taken.push(item)}
      return {parts,taken};
    }});
  // buffer@1 (405-410, 455-459): capacity refusal; the queue in device.state, one released every
  // releaseMs (default 10 ms) in ticks. Timed: a cycle through a buffer is not a zero-delay cycle.
  const bufferPattern=flowPattern('buffer',{timed:true,initial:()=>({queue:[],releasing:false}),
    intake(parameters,state,settings,message){
      if(settings.capacity!=null&&state.queue.length>=settings.capacity)return {refuse:`buffer full (${settings.capacity})`};
      const item={message:copy(message.value),principal:message.principal??null,via:message.via??null};
      state.queue.push(item);
      const release=state.releasing?null:settings.releaseTicks;state.releasing=true;
      return {wait:'buffered',item,release};
    },
    release(parameters,state,settings){
      const item=state.queue.shift()||null;
      let next=null;if(state.queue.length)next=settings.releaseTicks;else state.releasing=false;
      return {item,next};
    }});
  // limit@1 (399-404): the arrival ticks still inside the rate's span, in device.state.
  // The span's key, config.flow.rate's `${SPAN}`, is spelled in two parts because
  // tests/state_space_contracts_qa.py refuses the name of the browser's global object anywhere in this file.
  const SPAN='win'+'dowMs';
  const limitPattern=flowPattern('limit',{initial:()=>({arrivals:[]}),
    intake(parameters,state,settings,message){
      const r=settings.rate;
      if(!r||!(r.count>0)||!(r.spanMs>0))return {refuse:`limit has no rate (config.flow.rate {count, ${SPAN}})`};
      state.arrivals=state.arrivals.filter(x=>x>message.t-settings.spanTicks);
      if(state.arrivals.length>=r.count)return {refuse:`limit ${r.count} per ${r.spanMs}ms exceeded`};
      state.arrivals.push(message.t);
      return {pass:true};
    }});
  // gate@1 (380-383, 393-398, 449): a message on a control Path sets open from payload.open (default
  // true); a switch passes only while open; a service gate needs a condition (a control Path or a
  // handler) and passes only while open.
  const gatePattern=flowPattern('gate',{kinds:['switch','gate'],key:'kind',initial:()=>({open:false}),
    control(parameters,state,payload){state.open=isObject(payload)&&'open' in payload?!!payload.open:true},
    intake(parameters,state,settings){
      if(parameters.kind==='switch')return state.open?{pass:true}:{refuse:'switch is closed'};
      if(settings.handler)return {pass:true};
      if(!settings.controlled)return {refuse:'gate has no condition: wire its control point or name a handler'};
      return state.open?{pass:true}:{refuse:'gate is closed: no control has opened it'};
    }});
  // terminal@1 (389-391): observe ends the message and records an observation; receipt records a
  // receipt and passes it on; refuse refuses it.
  const terminalPattern=flowPattern('terminal',{kinds:['observe','receipt','refuse'],key:'kind',stateful:false,
    intake(parameters){
      if(parameters.kind==='refuse')return {refuse:'REFUSE terminal'};
      if(parameters.kind==='observe')return {end:'observed',rule:'observation'};
      return {pass:true,receipt:true};
    }});
  // hold@1 (392): keeps the payload in device.state, then forwards.
  const holdPattern=flowPattern('hold',{initial:()=>({value:null}),
    intake(parameters,state,settings,message){state.value=copy(message.value.payload);return {pass:true}}});
  const PATTERNS=[truthTable,merge,combinePattern].map(p=>Object.freeze(p));
  const FLOW_PATTERNS=[routePattern,joinPattern,bufferPattern,limitPattern,gatePattern,terminalPattern,holdPattern].map(p=>Object.freeze(p));
  const refOf=p=>`${p.id}@${p.version}`;
  // patterns() is the level registry (each a contract over ports); flowPatterns() the message one. pattern() finds either.
  function patterns(){return PATTERNS.slice()}
  function flowPatterns(){return FLOW_PATTERNS.slice()}
  function pattern(ref){return PATTERNS.find(p=>refOf(p)===ref)||FLOW_PATTERNS.find(p=>refOf(p)===ref)||null}

  // --- Definitions and packs (STATE-SPACE.md "Definitions").
  const AUTHORED_KEYS=['id','version','pattern','parameters','delay','ports','projection'];
  const DERIVED_KEYS=['inputs','outputs','state','observables'];
  const SIDES=['left','right','top','bottom'];
  const refusal=(code,subject,message)=>({code,subject,message});
  function definitionRef(definition){return `${definition?.id}@${definition?.version}`}
  // A definition's refusals, [] when it is valid.
  function checkDefinition(definition){
    const subject=isObject(definition)&&nonEmpty(definition.id)?definitionRef(definition):'definition';
    if(!isObject(definition))return [refusal('DEFINITION_INVALID',subject,'a definition must be an object')];
    const out=[],bad=message=>out.push(refusal('DEFINITION_INVALID',subject,message));
    for(const key of Object.keys(definition))if(!AUTHORED_KEYS.includes(key)&&!DERIVED_KEYS.includes(key))bad(`unknown key ${key}`);
    if(!nonEmpty(definition.id))bad('id must be a non-empty string');
    if(!(Number.isInteger(definition.version)&&definition.version>=1))bad('version must be an integer >= 1');
    if(definition.delay!==undefined&&!natural(definition.delay))bad('delay must be an integer >= 0');
    if(definition.projection!==undefined&&!isObject(definition.projection))bad('projection must be an object');
    if(definition.ports!==undefined){
      if(!isObject(definition.ports))bad('ports must be an object of port id to {side, t, label?}');
      else for(const [id,place] of Object.entries(definition.ports)){
        if(!isObject(place)){bad(`ports.${id} must be an object`);continue}
        for(const key of Object.keys(place))if(!['side','t','label'].includes(key))bad(`ports.${id}: unknown key ${key}`);
        if(!SIDES.includes(place.side))bad(`ports.${id}.side must be one of ${SIDES.join(', ')}`);
        if(!(typeof place.t==='number'&&place.t>=0&&place.t<=1))bad(`ports.${id}.t must be a number in 0..1`);
        if(place.label!==undefined&&typeof place.label!=='string')bad(`ports.${id}.label must be a string`);
      }
    }
    const p=typeof definition.pattern==='string'?pattern(definition.pattern):null;
    if(!p){out.push(refusal('PATTERN_UNKNOWN',subject,`pattern ${JSON.stringify(definition.pattern)} is not registered`));return out}
    const paramErrors=p.validate(definition.parameters);
    if(paramErrors.length){out.push(refusal('PARAMETERS_INVALID',subject,paramErrors.join('; ')));return out}
    const derived=p.derive(definition.parameters);
    for(const key of DERIVED_KEYS)if(definition[key]!==undefined&&!same(definition[key],derived[key]))out.push(refusal('CONTRACT_MISMATCH',subject,`stated ${key} differs from what ${definition.pattern} derives`));
    if(isObject(definition.ports)){
      const ids=new Set([...(derived.inputs||[]),...(derived.outputs||[])].map(x=>x.id));
      for(const id of Object.keys(definition.ports))if(!ids.has(id))bad(`ports.${id} names no port of the contract`);
    }
    return out;
  }
  function loadPack(json){
    const errors=[];
    if(!isObject(json))return {ok:false,pack:null,errors:[refusal('PACK_INVALID','pack','a pack must be an object')]};
    const subject=nonEmpty(json.id)?json.id:'pack';
    for(const key of Object.keys(json))if(!['format','id','version','definitions','bindings'].includes(key))errors.push(refusal('PACK_INVALID',subject,`unknown key ${key}`));
    // bindings (optional): symbol id -> id@version of a flow definition in this pack, read by flowBindingOf.
    if(json.bindings!==undefined){
      if(!isObject(json.bindings))errors.push(refusal('PACK_INVALID',subject,'bindings must be an object of symbol id to id@version'));
      else for(const [symbol,ref] of Object.entries(json.bindings)){
        const definition=Array.isArray(json.definitions)?json.definitions.find(x=>isObject(x)&&definitionRef(x)===ref):null;
        if(!definition)errors.push(refusal('PACK_INVALID',subject,`bindings.${symbol} names ${JSON.stringify(ref)}, which this pack does not define`));
        else if(!pattern(definition.pattern)?.messages)errors.push(refusal('PACK_INVALID',subject,`bindings.${symbol} names ${ref}, whose pattern ${definition.pattern} is not a flow pattern`));
      }
    }
    if(json.format!==PACK_FORMAT)errors.push(refusal('PACK_INVALID',subject,`format must equal ${PACK_FORMAT}`));
    if(!nonEmpty(json.id))errors.push(refusal('PACK_INVALID',subject,'id must be a non-empty string'));
    if(!(Number.isInteger(json.version)&&json.version>=1))errors.push(refusal('PACK_INVALID',subject,'version must be an integer >= 1'));
    if(!Array.isArray(json.definitions))errors.push(refusal('PACK_INVALID',subject,'definitions must be an array'));
    else{
      const refs=new Set();
      for(const definition of json.definitions){
        errors.push(...checkDefinition(definition));
        if(isObject(definition)){const ref=definitionRef(definition);if(refs.has(ref))errors.push(refusal('DEFINITION_INVALID',ref,'the pack defines this id@version twice'));refs.add(ref)}
      }
    }
    if(errors.length)return {ok:false,pack:null,errors};
    const pack=clone(json);
    for(const definition of pack.definitions)if(definition.delay===undefined)definition.delay=0;
    return {ok:true,pack,errors:[]};
  }
  function packList(packs){return Array.isArray(packs)?packs:isObject(packs)?[packs]:[]}
  function resolveDefinition(ref,packs){
    if(typeof ref!=='string')return null;
    for(const pack of packList(packs))for(const definition of Array.isArray(pack?.definitions)?pack.definitions:[]){
      if(isObject(definition)&&definitionRef(definition)===ref)return clone(definition);
    }
    return null;
  }
  // The derived contract, with each generated port's placement: from `ports[id]` when the
  // definition gives it, else inputs spread evenly on the left and outputs on the right.
  function contractOf(definition){
    const p=pattern(definition?.pattern);if(!p)throw new Error(`PATTERN_UNKNOWN: ${definition?.pattern}`);
    const contract=p.derive(definition.parameters),placed=isObject(definition.ports)?definition.ports:{};
    const place=(list,side)=>list.map((port,i)=>{
      const given=placed[port.id],out={...port,side:given?given.side:side,t:given?given.t:(i+1)/(list.length+1)};
      if(given&&typeof given.label==='string')out.label=given.label;
      return out;
    });
    if(Array.isArray(contract.inputs))contract.inputs=place(contract.inputs,'left');
    if(Array.isArray(contract.outputs))contract.outputs=place(contract.outputs,'right');
    return contract;
  }
  function contractPorts(contract){return [...(contract.inputs||[]),...(contract.outputs||[])]}

  // --- Binding. `bindDefinition` builds the binding patch for inspection and applies nothing;
  // `applyBind` builds it the same way, checks it and applies it through the data core's binding
  // path (`Data.applyBinding`), the only way `config.definition` becomes non-null.
  // A contract with no inputs and no outputs (merge@1's, for one) generates no ports: nothing binds to it.
  function bindable(contract){return contractPorts(contract).length>0}
  // Only a 2D Component binds: a Point, a Path, or a Component hosted on a Path exposes no declared ports.
  function bindDefinition(doc,componentId,ref,packs){
    const definition=resolveDefinition(ref,packs);
    if(!definition)return {ok:false,code:'DEFINITION_UNRESOLVED',message:`definition ${ref} is not in the packs`};
    const component=(doc?.components||[]).find(c=>c?.id===componentId);
    if(!component)return {ok:false,code:'COMPONENT_NOT_FOUND',message:`component ${componentId} not found`};
    const dimension=Data.effectiveDimension(component);
    if(dimension!==2)return {ok:false,code:'DEFINITION_NOT_BINDABLE',message:`${componentId} is ${dimension}D; only a 2D Component binds a definition`};
    const problems=checkDefinition(definition);
    if(problems.length)return {ok:false,code:problems[0].code,message:problems[0].message};
    const contract=contractOf(definition);
    if(!bindable(contract))return {ok:false,code:'DEFINITION_NOT_BINDABLE',message:`definition ${ref} (${definition.pattern}) generates no ports`};
    const attachmentPoints=contractPorts(contract).map(port=>{
      const stored={id:port.id,side:port.side,t:port.t,flow:port.flow,channels:port.channels.map(c=>({id:c.id}))};
      if(port.label)stored.label=port.label;
      return stored;
    });
    // Rebinding carries each existing channel merge to the same port id and channel id, and
    // is refused when the new contract drops a port or channel that holds one.
    const byId=new Map(attachmentPoints.map(p=>[p.id,p]));
    for(const spec of Data.canonicalAttachmentPointDescriptors(component)){
      for(const channel of spec?.channels||[]){
        if(channel.merge===undefined)continue;
        const target=byId.get(spec.id)?.channels.find(c=>c.id===channel.id);
        if(!target)return {ok:false,code:'MERGE_IN_USE',message:`port ${spec.id} channel ${channel.id} of ${componentId} holds a merge, and ${ref} has no such port and channel`};
        target.merge=clone(channel.merge);
      }
    }
    return {schema:Data.OPERATION_SCHEMA,op:'update',resource:'component',resourceId:componentId,patch:{config:{definition:ref,attachmentDefaults:'none',attachmentPoints}}};
  }
  // Binds `ref` to the Component: resolves the definition, builds the patch as bindDefinition
  // does, verifies its ports equal the contract, and applies it through the binding path.
  // Returns a receipt: ok, or refused with `error.code` (nothing changed, no revision).
  const contractPortKey=port=>[port.id,port.flow||port.defaultFlow||'duplex',(port.channels||[{id:'main'}]).map(c=>c.id)];
  function applyBind(doc,componentId,ref,packs){
    const revision=Number.isInteger(doc?.revision)?doc.revision:0;
    const refused=(code,message)=>({schema:Data.RECEIPT_SCHEMA,operationId:null,ok:false,revisionBefore:revision,revisionAfter:revision,result:null,error:{code,message:`${code}: ${message}`}});
    if(!isObject(doc))return refused('DOCUMENT_INVALID','a document must be an object');
    const operation=bindDefinition(doc,componentId,ref,packs);
    if(operation.ok===false)return refused(operation.code,operation.message);
    const want=contractPorts(contractOf(resolveDefinition(ref,packs))).map(contractPortKey).sort();
    const have=operation.patch.config.attachmentPoints.map(contractPortKey).sort();
    if(!same(want,have))return refused('DEFINITION_PORTS',`the binding patch's ports ${JSON.stringify(have)} differ from the contract of ${ref} ${JSON.stringify(want)}`);
    return Data.applyBinding(doc,componentId,operation.patch);
  }

  // --- Load checks (STATE-SPACE.md "Invariants", at load). Never throws, never mutates doc.
  function checkDocument(doc,packs){
    const refusals=[];
    const refuse=(code,subject,message)=>refusals.push(refusal(code,subject,message));
    if(!isObject(doc))return {ok:false,refusals:[refusal('DOCUMENT_INVALID','document','a document must be an object')]};
    let d;
    try{d=Data.normalizeDocument(clone(doc))}
    catch(error){return {ok:false,refusals:[refusal('DOCUMENT_INVALID','document',String(error?.message||error))]}}
    const components=new Map(d.components.map(c=>[c.id,c]));
    const specOf=(componentId,pointId)=>{
      const component=components.get(componentId);if(!component)return null;
      try{return Data.canonicalAttachmentPointDescriptors(component).find(s=>s&&(s.id===pointId||s.compatId===pointId))||null}catch(_){return null}
    };
    const endPoint=(wire,end)=>Data.wireEndBound(wire,end)?(wire[end+'Attachment']?.pointId||wire[end+'Side']):null;
    for(const wire of d.wires){
      try{
        const subject=`wire:${wire.id}`,config=isObject(wire.config)?wire.config:{};
        // Delay 0 is a zero-delay Path (a cycle of them is refused when the run starts).
        if(config.delay!==undefined&&!(Number.isInteger(config.delay)&&config.delay>=0))refuse('PATH_DELAY_INVALID',subject,`config.delay must be an integer >= 0, not ${JSON.stringify(config.delay)}`);
        const aPoint=endPoint(wire,'a'),bPoint=endPoint(wire,'b');
        if(!aPoint||!bPoint)continue; // a free end binds nothing
        const aSpec=specOf(wire.a,aPoint),bSpec=specOf(wire.b,bPoint);
        if(!aSpec||!bSpec)continue; // an unreachable end is the data core's validation
        // A Wire whose directions no port flow admits is not refused: the run blocks it and records
        // it with the graph core's reason, as the graph core does.
        const theirs=new Set((bSpec.channels||[{id:'main'}]).map(c=>c.id));
        if(!(aSpec.channels||[{id:'main'}]).some(c=>theirs.has(c.id)))refuse('CHANNEL_MISMATCH',subject,`ports ${wire.a}.${aSpec.id} and ${wire.b}.${bSpec.id} share no channel`);
      }catch(error){refuse('DOCUMENT_INVALID',`wire:${wire?.id}`,String(error?.message||error))}
    }
    for(const component of d.components){
      try{
        const config=isObject(component.config)?component.config:{};
        if(config.definition!==undefined&&config.definition!==null){ // null is unbound
          const subject=`component:${component.id}`;
          const definition=resolveDefinition(config.definition,packs);
          const problems=definition?checkDefinition(definition):[];
          if(!definition)refuse('DEFINITION_UNRESOLVED',subject,`definition ${JSON.stringify(config.definition)} is not in the packs`);
          else if(problems.length)refuse('DEFINITION_INVALID',subject,`definition ${config.definition} does not validate: ${problems.map(x=>`${x.code} ${x.message}`).join('; ')}`);
          else if(!bindable(contractOf(definition)))refuse('DEFINITION_NOT_BINDABLE',subject,`definition ${config.definition} (${definition.pattern}) generates no ports`);
          else{
            const key=port=>[port.id,port.flow||port.defaultFlow||'duplex',(port.channels||[{id:'main'}]).map(c=>c.id)];
            const want=contractPorts(contractOf(definition)).map(key).sort();
            const have=Data.canonicalAttachmentPointDescriptors(component).map(key).sort();
            if(!same(want,have))refuse('DEFINITION_PORTS',subject,`ports ${JSON.stringify(have)} differ from the contract of ${config.definition} ${JSON.stringify(want)}`);
          }
        }
        for(const port of Array.isArray(config.attachmentPoints)?config.attachmentPoints:[]){
          for(const channel of Array.isArray(port?.channels)?port.channels:[]){
            if(!isObject(channel)||channel.merge===undefined)continue;
            const subject=`component:${component.id}:${port.id}:${channel.id}`;
            const errors=merge.validate(channel.merge);
            if(errors.length){refuse('MERGE_INVALID',subject,errors.join('; '));continue}
            if(channel.merge.order?.kind!=='declared')continue;
            const ending=new Set(d.wires.filter(w=>['a','b'].some(end=>w[end]===component.id&&endPoint(w,end)!=null&&(endPoint(w,end)===port.id||endPoint(w,end)===port.compatId))).map(w=>w.id));
            const strangers=channel.merge.order.paths.filter(id=>!ending.has(id));
            if(strangers.length)refuse('MERGE_INVALID',subject,`declared order names wires that do not end on this port: ${strangers.join(', ')}`);
          }
        }
      }catch(error){refuse('DOCUMENT_INVALID',`component:${component?.id}`,String(error?.message||error))}
    }
    return {ok:refusals.length===0,refusals};
  }

  // --- Runtime, slice 1b (STATE-SPACE.md "Runtime semantics (slice 1b)", "Two-phase ticks",
  // "Merge and ordering"): the hash-chained ledger, the replay key, two-phase ticks with merges,
  // recorded stochastic order draws, the trace and replay. A run is a plain JSON-safe object;
  // step() advances it in place and nothing else is touched. Binary channels only.
  const RUNTIME_VERSION='state-space@1';
  const TRACE_FORMAT='soveraeign.schematic/trace@0.1';
  const ZERO_HASH='0'.repeat(64);
  const LEDGER_KINDS=['start','input','draw'];
  const REPLAY_KEY_FIELDS=['documentId','documentHash','definitions','runtimeVersion','traceFormat','inputs','seed','tickMs'];
  const INPUT_KEYS=['entity','point','channel','value','at'];
  const DEFAULT_MERGE=Object.freeze({combine:'last',order:Object.freeze({kind:'stochastic'})});
  // The message channel queues by default: every message that reaches a port is delivered, one per
  // tick, in merge order; nothing is merged away.
  const MESSAGE='message';
  const MESSAGE_MERGE=Object.freeze({combine:'queue',order:Object.freeze({kind:'stochastic'})});
  // Within a tick a message's own records sort by what happened first to it.
  const HOP_RANK={injected:0,arrived:1,forwarded:2,delivered:2,absorbed:2,refused:2,sent:3};
  const cmp=(x,y)=>x<y?-1:x>y?1:0;
  const cmpList=(x,y)=>{for(let i=0;i<Math.max(x.length,y.length);i++){const c=cmp(x[i],y[i]);if(c)return c}return 0};
  const portKey=(entity,point,channel)=>JSON.stringify([entity,point,channel]);
  const TMP='\u0000tmp:';
  const walked=(run,list)=>run.walk==='reverse'?list.slice().reverse():list;
  // A deep copy of JSON-safe data (what clone gives, without the text round trip).
  function copy(value){
    if(value===null||typeof value!=='object')return value;
    if(Array.isArray(value)){const out=new Array(value.length);for(let i=0;i<value.length;i++){const v=value[i];out[i]=v===undefined?null:copy(v)}return out}
    const out={};for(const k in value){const v=value[k];if(v!==undefined)out[k]=copy(v)}return out;
  }
  // Indexes derived from a run's read-only topology, kept beside the run (never in it, so a run
  // stays plain JSON): each port's outgoing Wire ends, and the devices with their port keys.
  const INDEX=new WeakMap();
  function indexOf(run){
    let index=INDEX.get(run.wires);
    if(index&&index.components===run.components)return index;
    const out=new Map();
    for(const wire of run.wires)for(const [end,other,dir] of [['a','b','forward'],['b','a','reverse']]){
      if(!wire[dir])continue;
      const key=wire[end].entity+'\u0000'+wire[end].point;
      if(!out.has(key))out.set(key,[]);
      out.get(key).push({wire,to:wire[other]});
    }
    const devices=Object.keys(run.components).filter(id=>run.components[id].role==='device').sort()
      .map(id=>({id,inputs:run.components[id].inputs.map(name=>portKey(id,name,'main'))}));
    // Each component's carried legs for messages, in (wire id, direction) order: a message leaves by
    // the component, not by one port, as the graph core's forward does.
    const legs=new Map();
    for(const wire of run.wires)for(const [dir,from,fromPoint,to,toPoint] of [['forward','a','aPoint','b','bPoint'],['reverse','b','bPoint','a','aPoint']]){
      if(!wire[dir])continue;
      const entity=wire[from].entity;
      if(!legs.has(entity))legs.set(entity,[]);
      legs.get(entity).push({wire:wire.id,point:wire[fromPoint],to:{entity:wire[to].entity,point:wire[toPoint]},accepts:wire.accepts??null,delay:wire.delay,
        operation:dir==='forward'?wire.forwardOperation:wire.reverseOperation});
    }
    index={components:run.components,out,devices,legs};
    INDEX.set(run.wires,index);
    return index;
  }
  // Pending items are never changed once scheduled, so each one's canonical text is computed once.
  const PENDING_KEY=new WeakMap();
  function pendingKey(item){let k=PENDING_KEY.get(item);if(k===undefined){k=Canonical.canonicalize(item);PENDING_KEY.set(item,k)}return k}
  function ledgerHash(seq,kind,body,prev){return Canonical.sha256Hex(Canonical.canonicalize({seq,kind,body,prev}))}
  function appendEntry(run,kind,body){
    const seq=run.ledger.length,prev=seq?run.ledger[seq-1].hash:ZERO_HASH;
    run.ledger.push({seq,kind,body,prev,hash:ledgerHash(seq,kind,body,prev)});
  }
  const specChannels=spec=>(Array.isArray(spec?.channels)&&spec.channels.length?spec.channels:[{id:'main'}]).map(c=>c.id);
  const specFlow=spec=>spec.flow||spec.defaultFlow||'duplex';
  // The document's signal model is behaviour too. A non-Point Component with no bound definition is
  // read through the signal model's signalConfig (src/04-signal-model.js: its declared signal, a gate
  // glyph's combine, or the editor's default): a derived card becomes a combine@1 device over the Wires
  // that reach it, an asserted one drives its level onto its out ports at power-on, a square clock
  // schedules its edges.
  // The one binding lookup for what a card does with a message (STATE-SPACE.md, Flow cards): a
  // declared config.flow.policy other than fanout names flow.<policy>@1; else the first pack whose
  // bindings name the card's symbol id gives its definition. A candidate the packs do not define, or
  // one that is not a flow pattern, is passed over; with none the card relays by fanout as before.
  // A Point is looked up like any card, so a Point with config.flow relays with that policy.
  function flowBindingOf(c,packs){
    const policy=isObject(c?.config?.flow)?c.config.flow.policy:undefined,candidates=[];
    if(typeof policy==='string'&&policy&&policy!=='fanout')candidates.push(`flow.${policy}@1`);
    for(const pack of packList(packs))if(isObject(pack?.bindings)&&typeof c?.symbolId==='string'&&Object.prototype.hasOwnProperty.call(pack.bindings,c.symbolId)){candidates.push(pack.bindings[c.symbolId]);break}
    for(const ref of candidates){const def=resolveDefinition(ref,packs);if(def&&pattern(def.pattern)?.messages)return ref}
    return null;
  }
  // A card's flow settings, as the graph core's flowConfig reads them (src/07-graph-core.js:34-37 at
  // 7b939e3), times converted to ticks once: releaseMs (default the signal model's 10 ms) and the rate's
  // span (rate {count, SPAN}, as authored, kept as {count, spanMs} for the refusal text), a time above 0
  // never under one tick.
  function flowSettings(c,tickMs){
    const f=isObject(c.config?.flow)?c.config.flow:{},b=isObject(c.config?.behavior)?c.config.behavior:{};
    const ticks=ms=>ms>0?Math.max(1,msToTick(Math.round(ms),tickMs)):0;
    const releaseMs=Number.isFinite(Number(f.releaseMs))?Math.max(0,Number(f.releaseMs)):Model.DEFAULT_LATENCY_MS;
    const rate=isObject(f.rate)?{count:clone(f.rate.count)??null,spanMs:clone(f.rate[SPAN])??null}:null;
    return {by:['round-robin','channel','key'].includes(f.by)?f.by:'round-robin',key:typeof f.key==='string'?f.key:null,
      capacity:Number.isFinite(Number(f.capacity))?Number(f.capacity):null,releaseTicks:ticks(releaseMs),rate,
      spanTicks:rate&&Number(rate.spanMs)>0?ticks(Number(rate.spanMs)):0,handler:typeof b.handler==='string'&&b.handler?b.handler:null};
  }
  function impliedDevices(d,packs){
    const g=typeof globalThis!=='undefined'?globalThis:{},N=g.SovSchematicNotation,out={definitions:{},bind:{},sources:[],clocks:[],flow:{},asserted:{},edges:{}};
    let glyphs={};try{const r=N?N.resolve(d):null;glyphs=r?.ok?(r.notation?.glyphs||{}):{}}catch(_){glyphs={}}
    for(const c of d.components){
      const config=isObject(c.config)?c.config:{};
      const flow=flowBindingOf(c,packs);
      if(flow)out.flow[c.id]=flow;
      if(config.definition!==undefined&&config.definition!==null)continue;
      const glyph=glyphs[c.symbolId]||null;
      // A Point relays what reaches it (the engine's own 'point' role); every card has a signal,
      // declared or the editor's default (STATE-SPACE.md, What signalMode becomes).
      if(c.symbolId==='point')continue;
      const sig=Model.signalConfig(c,glyph);
      let specs=[];try{specs=Data.canonicalAttachmentPointDescriptors(c).filter(Boolean)}catch(_){specs=[]}
      const named=specs.filter(s=>NAME.test(s.id));
      const ins=named.filter(s=>specFlow(s)==='in').map(s=>s.id),outs=named.filter(s=>specFlow(s)==='out').map(s=>s.id);
      // An asserted card's level is set by a message carrying set or toggle (src/07-graph-core.js:384-388
      // at 7b939e3); a card with config.signal.on starts a message when its level crosses that way (469-473).
      if(sig.mode==='asserted')out.asserted[c.id]={outs,kind:sig.kind,threshold:toLevel(sig.threshold)};
      if(sig.on&&outs.length)out.edges[c.id]={on:sig.on,channel:sig.channel,point:outs[0],kind:sig.kind};
      // A clock drives its out ports with scheduled samples (see clockEdge): edges for a square wave,
      // levels every sampleMs for the continuous ones.
      if(sig.clock){
        // Clock times are whole milliseconds and its duty a level, fixed here.
        const k=sig.clock,ms=x=>Math.max(0,Math.round(Number(x)||0));
        const clock={wave:k.wave,periodMs:ms(k.periodMs),phaseMs:ms(k.phaseMs),duty:toLevel(k.duty),sampleMs:k.sampleMs?Math.max(1,ms(k.sampleMs)):null,cycles:k.cycles};
        if(clock.periodMs>0)for(const point of outs)out.clocks.push({entity:c.id,point,clock});
        continue;
      }
      if(sig.mode==='derived'){
        if(!outs.length)continue;
        // One definition per card: its inputs are the Wires that reach it (topology fills data/control).
        const ref=`implied.${sig.combine}[${c.id}]@1`;
        out.definitions[ref]={id:ref.slice(0,-2),version:1,pattern:'combine@1',delay:0,
          parameters:{combine:sig.combine,kind:sig.kind,threshold:toLevel(sig.threshold),epsilon:toLevel(sig.epsilon),data:[],control:[],outputs:outs}};
        out.bind[c.id]=ref;
      }else for(const point of outs)out.sources.push({entity:c.id,point,channel:'main',value:sig.kind==='continuous'?toLevel(sig.value):toLevel(sig.value)>=toLevel(sig.threshold),at:0});
    }
    return out;
  }
  // A square clock's edges in ticks: rise at phase + k*period, fall duty*period later; after `cycles`
  // periods it falls and stops. Each processed edge schedules the next, always at least a tick on.
  // The graph core's waves, sampled at whole milliseconds: saw, triangle and sine as levels.
  function waveAt(c,ms){
    if(ms<c.phaseMs)return 0;
    const u=idiv(((ms-c.phaseMs)%c.periodMs)*LEVEL,c.periodMs);
    return c.wave==='saw'?u:c.wave==='triangle'?(u<LEVEL/2?2*u:2*LEVEL-2*u):idiv(LEVEL-cosLevel(u),2);
  }
  // Whole milliseconds to ticks, rounding half up, in integers.
  const msToTick=(ms,tickMs)=>idiv(2*ms+tickMs,2*tickMs);
  function clockEdge(source,tickMs,k,rising,after){
    const c=source.clock,tick=ms=>Math.max(0,msToTick(ms,tickMs));
    if(c.wave!=='square'){
      // Sample k of a continuous wave, every sampleMs (default a sixteenth of the period) from the phase.
      const step=c.sampleMs||Math.max(1,idiv(c.periodMs,16)),ms=c.phaseMs+k*step;
      if(c.cycles&&ms>=c.phaseMs+c.cycles*c.periodMs)return null;
      const at=tick(ms);
      return {kind:'clock',at:after===null?at:Math.max(after+1,at),entity:source.entity,point:source.point,channel:'main',value:waveAt(c,ms),k};
    }
    if(c.cycles&&k>=c.cycles)return null;
    const at=tick(c.phaseMs+k*c.periodMs+(rising?0:idiv(c.duty*c.periodMs,LEVEL)));
    return {kind:'clock',at:after===null?at:Math.max(after+1,at),entity:source.entity,point:source.point,channel:'main',value:rising,k};
  }
  // What the run reads of the document, resolved once at start: each Wire's two ports, delay,
  // the directions it carries and the channels it shares; each Component's role; each merge.
  // Time: one tick is tickMs milliseconds (default 1). A Wire's stored delay is in ticks; without one,
  // its latencyMs (the signal model's default when absent) is converted, rounding half up, and a latency
  // above 0 is never less than one tick; only 0 ms is a zero-delay Path, run in delta rounds within its
  // tick (a cycle of them is refused at start).
  function wireDelay(config,tickMs){
    if(config.delay!==undefined)return config.delay;
    const raw=Number.isFinite(Number(config.latencyMs))?Math.max(0,Number(config.latencyMs)):Model.DEFAULT_LATENCY_MS;
    return raw>0?Math.max(1,msToTick(Math.round(raw),tickMs)):0;
  }
  // Which legs of a Wire carry is the graph core's passability (src/07-graph-core.js build): the
  // Wire's direction, then each leg's emit and receive flows (legacy config.ports connections
  // included) and its operation against the ports' access, read through the rule in
  // src/04-signal-model.js that both engines share. A leg that does not carry is blocked with the
  // graph core's reason, recorded once at start; a Wire that carries nothing is blocked, never refused.
  function passability(d,wire,G=Model){
    const byId=new Map(d.components.map(c=>[c.id,c]));
    const bound=end=>!!wire[end]&&byId.has(wire[end])&&!Data.isFreeEndpoint(wire[end+'Attachment']);
    if(!bound('a')||!bound('b'))return {forward:false,reverse:false,blocked:[{wire:wire.id,reason:'free end'}]};
    const config=isObject(wire.config)?wire.config:{};
    const direction=['none','forward','reverse','duplex'].includes(config.direction)?config.direction:wire.duplex?'duplex':'forward';
    const out={forward:false,reverse:false,blocked:[]};
    if(direction==='none')out.blocked.push({wire:wire.id,reason:'direction none'});
    const legs=[];
    if(direction==='forward'||direction==='duplex')legs.push(['a','b','forwardOperation','forward']);
    if(direction==='reverse'||direction==='duplex')legs.push(['b','a','reverseOperation','reverse']);
    const portsOf=id=>{const c=byId.get(id);return isObject(c.config?.ports)?c.config.ports:{}};
    for(const [s,t,opKey,dir] of legs){
      const from=wire[s],to=wire[t],fromPort=wire[s+'Side'],toPort=wire[t+'Side'];
      const fp=portsOf(from)[fromPort],tp=portsOf(to)[toPort];
      const op=['read','write'].includes(config[opKey])?config[opKey]:'none';
      const reason=!G.canEmit(fp,fromPort)?`${from}.${fromPort} cannot emit`:!G.canReceive(tp,toPort)?`${to}.${toPort} cannot receive`:(!G.accessAllows(fp,op)||!G.accessAllows(tp,op))?`access refuses ${op}`:null;
      if(reason)out.blocked.push({wire:wire.id,reason});else out[dir]=true;
    }
    return out;
  }
  function topology(d,definitions,bind={},tickMs=1){
    const components={},merges={},wires=[],blocked=[],landings={};
    const specOf=(component,pointId)=>{try{return Data.canonicalAttachmentPointDescriptors(component).find(s=>s&&(s.id===pointId||s.compatId===pointId))||null}catch(_){return null}};
    const byId=new Map(d.components.map(c=>[c.id,c]));
    for(const component of d.components){
      const config=isObject(component.config)?component.config:{};
      const ref=config.definition!==undefined&&config.definition!==null?config.definition:(bind[component.id]??null);
      if(ref){const def=definitions[ref],combine=def.pattern==='combine@1';
        components[component.id]={role:'device',definition:ref,combine,inputs:combine?[]:def.parameters.inputs.slice(),outputs:def.parameters.outputs.slice()}}
      else components[component.id]={role:component.symbolId==='point'?'point':'absorb'};
      // What a message does here is read as the graph core reads it: a passive card absorbs, and a
      // participant with a principal acts in its own name.
      if(config.signalMode==='passive')components[component.id].passive=true;
      if(typeof config.principal==='string'&&config.principal)components[component.id].principal=config.principal;
      // A channel merge is read where checkDocument reads it: the stored port list, by port id.
      for(const port of Array.isArray(config.attachmentPoints)?config.attachmentPoints:[]){
        for(const channel of Array.isArray(port?.channels)?port.channels:[]){
          if(isObject(channel)&&channel.merge!==undefined)merges[portKey(component.id,port.id,channel.id)]=clone(channel.merge);
        }
      }
    }
    for(const wire of d.wires){
      const passable=passability(d,wire);
      blocked.push(...passable.blocked);
      if(!Data.wireEndBound(wire,'a')||!Data.wireEndBound(wire,'b'))continue;
      const ends={};
      for(const end of ['a','b']){
        const component=byId.get(wire[end]),spec=component?specOf(component,wire[end+'Attachment']?.pointId||wire[end+'Side']):null;
        if(!spec)break;
        ends[end]={entity:component.id,point:spec.id,flow:specFlow(spec),channels:specChannels(spec)};
      }
      if(!ends.a||!ends.b)continue;
      const config=isObject(wire.config)?wire.config:{};
      const theirs=new Set(ends.b.channels);
      const {forward,reverse}=passable;
      // A Wire that reaches a combine device lands on its own input, `<port>:<wire>`: the device reads
      // each Wire's latest level, as the graph core does, and never a merge of them.
      const land=(end,into)=>{
        const c=components[ends[end].entity];
        if(!into||!c?.combine)return {entity:ends[end].entity,point:ends[end].point};
        const name=`${ends[end].point}:${wire.id}`,params=definitions[c.definition].parameters;
        (ends[end].flow==='control'||ends[end].point==='control'?params.control:params.data).push(name);c.inputs.push(name);
        return {entity:ends[end].entity,point:name};
      };
      // Every Path carries a second channel, message, in each direction it carries; no port declares
      // it. A message stays on the port it reaches (aPoint, bPoint), and config.accepts filters it.
      const channels=ends.a.channels.filter(c=>theirs.has(c));
      if(!channels.includes(MESSAGE))channels.push(MESSAGE);
      // Where each carried leg lands: on a control port (the graph core's arc.control) or as one of
      // the card's incoming Paths (a join waits for one message on each).
      for(const [carried,end] of [[forward,'b'],[reverse,'a']]){
        if(!carried)continue;
        const at=landings[ends[end].entity]||(landings[ends[end].entity]={control:[],incoming:[]});
        const list=ends[end].flow==='control'||ends[end].point==='control'?at.control:at.incoming;
        if(!list.includes(wire.id))list.push(wire.id);
      }
      wires.push({id:wire.id,a:land('a',reverse),b:land('b',forward),aPoint:ends.a.point,bPoint:ends.b.point,delay:wireDelay(config,tickMs),forward,reverse,
        channels,accepts:Array.isArray(config.accepts)?config.accepts.map(String):null,
        // A leg's own read/write operation, the graph core's forwardOperation/reverseOperation
        // (src/07-graph-core.js build), checked after a crossing on the message channel.
        forwardOperation:['read','write'].includes(config.forwardOperation)?config.forwardOperation:'none',
        reverseOperation:['read','write'].includes(config.reverseOperation)?config.reverseOperation:'none'});
    }
    wires.sort((x,y)=>cmp(x.id,y.id));
    for(const c of Object.values(components))if(c.combine){const p=definitions[c.definition].parameters;p.data.sort();p.control.sort();c.inputs.sort()}
    for(const at of Object.values(landings)){at.control.sort();at.incoming.sort()}
    return {components,merges,wires,blocked,landings};
  }
  // Every cycle made only of zero-delay legs, as its strongly connected component: the components in
  // it and the Wires whose zero-delay legs join them, both sorted; [] when there is none. Such a cycle
  // would run forever inside one tick, so the run refuses it at start (the graph core's
  // ZERO_LATENCY_CYCLE).
  // A card whose flow pattern is timed (buffer@1) takes time itself, so no cycle through it is zero-delay.
  function zeroDelayCycles(wires,timed=new Set()){
    const edges=new Map(),add=(from,to,wire)=>{if(timed.has(from)||timed.has(to))return;if(!edges.has(from))edges.set(from,[]);edges.get(from).push({to,wire})};
    for(const w of wires)if(w.delay===0){if(w.forward)add(w.a.entity,w.b.entity,w.id);if(w.reverse)add(w.b.entity,w.a.entity,w.id)}
    const nodes=[...new Set([...edges.keys(),...[...edges.values()].flat().map(e=>e.to)])].sort();
    const index=new Map(),low=new Map(),stack=[],on=new Set(),out=[];let n=0;
    const visit=v=>{
      index.set(v,n);low.set(v,n);n++;stack.push(v);on.add(v);
      for(const {to} of edges.get(v)||[]){if(!index.has(to)){visit(to);low.set(v,Math.min(low.get(v),low.get(to)))}else if(on.has(to))low.set(v,Math.min(low.get(v),index.get(to)))}
      if(low.get(v)!==index.get(v))return;
      const members=[];let x;do{x=stack.pop();on.delete(x);members.push(x)}while(x!==v);
      const inside=new Set(members),joined=[...new Set(members.flatMap(m=>(edges.get(m)||[]).filter(e=>inside.has(e.to)).map(e=>e.wire)))].sort();
      if(members.length>1||joined.length)out.push({nodes:members.sort(),wires:joined});
    };
    for(const v of nodes)if(!index.has(v))visit(v);
    return out.sort((x,y)=>cmp(x.nodes[0],y.nodes[0]));
  }
  function inputRefusal(message){return {ok:false,code:'INPUT_INVALID',message}}
  // A run: startRun({doc, packs, inputs, seed, budget}). `walk: 'reverse'` reverses the order in
  // which the engine walks ports, devices and Wires within a phase; no outcome depends on it.
  function startRun(options){
    const o=isObject(options)?options:{};
    const checked=checkDocument(o.doc,o.packs);
    if(!checked.ok)return {ok:false,code:'RUN_REFUSED',message:`the document does not pass its load checks: ${checked.refusals.map(r=>r.code).join(', ')}`,refusals:checked.refusals};
    const d=Data.normalizeDocument(clone(o.doc));
    for(const component of d.components){
      for(const port of Array.isArray(component.config?.attachmentPoints)?component.config.attachmentPoints:[]){
        for(const channel of Array.isArray(port?.channels)?port.channels:[]){
          if(channel?.id===MESSAGE&&channel?.merge!==undefined&&channel.merge?.combine!=='queue')return {ok:false,code:'MERGE_FORM',subject:`component:${component.id}:${port.id}:${channel.id}`,message:`channel message merges by queue only: every message is delivered, none is merged away (${component.id}.${port.id}.${channel.id})`};
          if(channel?.merge?.combine==='sum')return {ok:false,code:'MERGE_FORM',subject:`component:${component.id}:${port.id}:${channel.id}`,message:`combine sum is not defined on binary channels (${component.id}.${port.id}.${channel.id}); slice 1b runs binary channels only`};
        }
      }
    }
    const seed=o.seed===undefined?'0':o.seed;
    if(typeof seed!=='string')return inputRefusal('seed must be a string');
    const budget=o.budget===undefined?10000:o.budget;
    if(!natural(budget))return inputRefusal('budget must be an integer >= 0');
    if(o.walk!==undefined&&!['forward','reverse'].includes(o.walk))return inputRefusal('walk must be forward or reverse');
    const tickMs=o.tickMs===undefined?1:o.tickMs;
    if(!(Number.isSafeInteger(tickMs)&&tickMs>0))return inputRefusal('tickMs must be an integer above 0 (whole milliseconds)');
    const rawInputs=o.inputs===undefined?[]:o.inputs;
    if(!Array.isArray(rawInputs))return inputRefusal('inputs must be an array');
    const inputs=[],seen=new Set();
    for(let i=0;i<rawInputs.length;i++){
      const raw=rawInputs[i];
      if(!isObject(raw))return inputRefusal(`input ${i} must be an object`);
      const extra=Object.keys(raw).filter(k=>!INPUT_KEYS.includes(k));
      if(extra.length)return inputRefusal(`input ${i}: unknown key ${extra[0]}`);
      const component=d.components.find(c=>c.id===raw.entity);
      if(!component)return inputRefusal(`input ${i}: unknown entity ${JSON.stringify(raw.entity)}`);
      let spec=null;try{spec=Data.canonicalAttachmentPointDescriptors(component).find(s=>s&&typeof raw.point==='string'&&(s.id===raw.point||s.compatId===raw.point))||null}catch(_){spec=null}
      if(!spec)return inputRefusal(`input ${i}: ${raw.entity} has no port ${JSON.stringify(raw.point)}`);
      const channel=raw.channel===undefined?'main':raw.channel;
      if(channel===MESSAGE){
        // An inject: a message {channel, payload, principal} put in at a port; several may share a port and tick.
        if(!natural(raw.at))return inputRefusal(`input ${i}: at must be an integer >= 0`);
        const v=raw.value;
        if(!isObject(v))return inputRefusal(`input ${i}: a message input's value must be an object {channel, payload, principal}`);
        const extra=Object.keys(v).filter(k=>!['channel','payload','principal'].includes(k));
        if(extra.length)return inputRefusal(`input ${i}: unknown key value.${extra[0]}`);
        if(v.channel!==undefined&&v.channel!==null&&typeof v.channel!=='string')return inputRefusal(`input ${i}: value.channel must be a string or null`);
        if(v.principal!==undefined&&v.principal!==null&&!nonEmpty(v.principal))return inputRefusal(`input ${i}: value.principal must be a non-empty string or null`);
        try{Canonical.canonicalize(v.payload??null)}catch(_){return inputRefusal(`input ${i}: value.payload must be JSON`)}
        // No floating point anywhere a run records, payloads included: every number is a safe integer.
        const fraction=firstFraction(v.payload??null,`inputs[${i}].value.payload`);
        if(fraction)return {ok:false,code:'PAYLOAD_FRACTION',path:fraction.path,message:`input ${i}: ${fraction.path} is ${JSON.stringify(fraction.value)}, not a safe integer; a run records no floating point`,next_operation:'state the number in integer units (e.g. 1.5 kg as 1500 g, 0.25 as 250 thousandths) and name the unit in the payload'};
        inputs.push({entity:component.id,point:spec.id,channel,value:{channel:v.channel??null,payload:clone(v.payload??null),principal:v.principal??null},at:raw.at});
        continue;
      }
      const bound=component.config?.definition;
      if(bound!==undefined&&bound!==null&&(resolveDefinition(bound,o.packs)?.parameters?.outputs||[]).includes(spec.id))return inputRefusal(`input ${i}: ${component.id}.${spec.id} is an output of ${bound}; a device's output is the device's`);
      if(!specChannels(spec).includes(channel))return inputRefusal(`input ${i}: port ${raw.entity}.${spec.id} has no channel ${JSON.stringify(channel)}`);
      const fraction=firstFraction(raw.value,`inputs[${i}].value`);
      if(fraction)return {ok:false,code:'PAYLOAD_FRACTION',path:fraction.path,message:`input ${i}: ${fraction.path} is ${JSON.stringify(fraction.value)}, not a safe integer; a run records no floating point`,next_operation:'state the value in integer units (a level as a boolean on a binary channel)'};
      if(typeof raw.value!=='boolean')return inputRefusal(`input ${i}: value must be a boolean (binary channels only)`);
      if(!natural(raw.at))return inputRefusal(`input ${i}: at must be an integer >= 0`);
      const input={entity:component.id,point:spec.id,channel,value:raw.value,at:raw.at};
      const key=JSON.stringify([input.at,input.entity,input.point,input.channel]);
      if(seen.has(key))return inputRefusal(`input ${i}: a second input at (${input.entity}, ${input.point}, ${input.channel}, ${input.at})`);
      seen.add(key);inputs.push(input);
    }
    // Message inputs at one port and tick are ordered by their canonical value, so the order is the caller's no more.
    const tie=x=>x.channel===MESSAGE?Canonical.canonicalize(x.value):'';
    inputs.sort((x,y)=>cmpList([x.at,x.entity,x.point,x.channel,tie(x)],[y.at,y.entity,y.point,y.channel,tie(y)]));
    const implied=impliedDevices(d,o.packs);
    const bound=[...new Set(d.components.map(c=>c.config?.definition).filter(ref=>ref!==undefined&&ref!==null))];
    // Flow definitions a card reaches through the binding lookup are resolved definitions of the run too.
    const flowRefs=[...new Set(Object.values(implied.flow))];
    const refs=[...new Set([...bound,...Object.keys(implied.definitions),...flowRefs])].sort();
    const definitions={};
    for(const ref of [...bound,...flowRefs]){const def=resolveDefinition(ref,o.packs);if(def.delay===undefined)def.delay=0;definitions[ref]=def}
    Object.assign(definitions,clone(implied.definitions));
    const replayKey={documentId:d.id,documentHash:Data.documentHash(d),definitions:refs,runtimeVersion:RUNTIME_VERSION,traceFormat:TRACE_FORMAT,inputs,seed};
    if(tickMs!==1)replayKey.tickMs=tickMs;
    const shape=topology(d,definitions,implied.bind,tickMs);
    // What a card does with messages, levels set by messages, and edges that start messages: read once here.
    const byId=new Map(d.components.map(c=>[c.id,c])),timed=new Set();
    for(const [id,ref] of Object.entries(implied.flow)){
      const def=definitions[ref],at=shape.landings[id]||{control:[],incoming:[]};
      shape.components[id].flow={ref,pattern:def.pattern,parameters:clone(def.parameters),control:at.control.slice(),
        settings:{...flowSettings(byId.get(id),tickMs),controlled:at.control.length>0,incoming:at.incoming.slice()}};
      if(pattern(def.pattern).timed)timed.add(id);
    }
    for(const [id,a] of Object.entries(implied.asserted))shape.components[id].asserted=a;
    for(const [id,e] of Object.entries(implied.edges))shape.components[id].edge=e;
    const loops=zeroDelayCycles(shape.wires,timed);
    if(loops.length)return {ok:false,code:'ZERO_DELAY_CYCLE',message:`a cycle must take time: give one of its Paths a delay of at least 1 or a latencyMs above 0 (${loops.map(c=>c.wires.join(', ')).join('; ')})`,cycles:loops};
    // A declared level is an input the document makes: a caller's input on the same port and tick wins.
    const sources=implied.sources.filter(x=>!seen.has(JSON.stringify([x.at,x.entity,x.point,x.channel])));
    const run={
      id:Canonical.sha256Hex(Canonical.canonicalize(replayKey)).slice(0,12),
      runtimeVersion:RUNTIME_VERSION,doc:d,definitions,components:shape.components,merges:shape.merges,wires:shape.wires,
      seed,budget,tickMs,spent:0,tick:null,walk:o.walk||'forward',
      // levelPrincipal mirrors signal/lastRecord for the level channel's own principal (STATE-SPACE.md,
      // access control): a side cache, never part of the trace or a replay comparison, so a device's
      // own wire-named inputs can read what last set them, the way a Point reads its own arrivals.
      // deviceState: each stateful flow card's committed device.state, by entity (absent = the pattern's initial state).
      signal:{},lastRecord:{},levelPrincipal:{},queues:{},deviceState:{},sequence:0,ledger:[],records:[],replayDraws:null,
      clocks:Object.fromEntries(implied.clocks.map(c=>[portKey(c.entity,c.point,'main'),c])),
      blocked:shape.blocked,
      // A message input carries the ledger seq of its input entry: its message is m-<seq>.
      pending:[...inputs.map((x,i)=>x.channel===MESSAGE?{kind:'input',...clone(x),seq:i+1}:{kind:'input',...x}),...sources.map(x=>({kind:'input',...x})),...implied.clocks.map(c=>clockEdge(c,tickMs,0,true,null)).filter(Boolean)]
        .sort((x,y)=>cmpList([x.at,x.entity,x.point,x.channel],[y.at,y.entity,y.point,y.channel]))
    };
    appendEntry(run,'start',{replayKey:clone(replayKey),budget});
    for(const input of inputs)appendEntry(run,'input',clone(input));
    return {ok:true,run};
  }
  // Power-on: tick 0 is always processed, even with nothing scheduled at it.
  function nextTick(run){
    let t=run.tick===null?0:null;
    for(const item of run.pending)if(t===null||item.at<t)t=item.at;
    for(const q of Object.values(run.queues))if(q.items.length>q.head&&(t===null||q.next<t))t=q.next;
    return t;
  }
  function queuedCount(run){return run.pending.length+Object.values(run.queues).reduce((n,q)=>n+(q.items.length-q.head),0)}
  // A queue merge is plain JSON data — {next, items, head} — so a run stays a plain JSON-safe
  // object through JSON.stringify/parse or structuredClone (STATE-SPACE.md, slice 1b). `items` is
  // append-only (never spliced) and `head` counts how many of its front items are delivered, so
  // appending is `items.push` and delivering is `head++`: both O(1), neither ever shifts or copies
  // the array. `head` items of history accumulate at the front rather than being dropped, which
  // `queueItems` (the one exported reader) skips past; nothing else reads `items`/`head` from
  // outside this file (see step 7 of contract #52's amendment).
  function makeQueue(next){return {next,items:[],head:0}}
  function queueItems(q){return q.items.slice(q.head)}
  // First access of a queue merge's key within a tick records what undoing it needs (never a copy
  // of its items): whether the key existed, and if so its `next`, `head` and item count before this
  // tick touches it. Every push, delivery and `next` update after this within the same tick reuses
  // the same queue object, so one record per key per tick is enough.
  function ensureQueue(run,ctx,key){
    let q=run.queues[key];
    if(q){
      if(!ctx.queueUndo.has(key))ctx.queueUndo.set(key,{existed:true,queue:q,next:q.next,head:q.head,length:q.items.length});
      return q;
    }
    q=makeQueue(ctx.t+1);
    ctx.queueUndo.set(key,{existed:false,queue:q});
    run.queues[key]=q;
    return q;
  }
  // Undo a tick's queue merges from the per-key record: a queue this tick created is dropped
  // entirely; one it found already there has its items truncated back to its length before the
  // tick (discarding only what the tick appended) and its head and `next` put back, whether or not
  // the tick's own cleanup already deleted it for running dry.
  function undoQueues(run,log){
    for(const [key,entry] of log){
      if(!entry.existed){delete run.queues[key];continue}
      const q=entry.queue;
      q.items.length=entry.length;q.head=entry.head;q.next=entry.next;
      run.queues[key]=q;
    }
  }
  // A record carries its principal when one applies (STATE-SPACE.md, access control): the key is
  // left out entirely otherwise, so a document with no ACL and no principal records exactly as
  // before (examples/state, tests/golden stay byte-unchanged).
  function makeRecord(run,ctx,{entity,point,channel,kind,value,observer,rule,inputs,phase,rank=0,principal}){
    const id=`${TMP}${ctx.tmp++}`;
    ctx.records.push({round:ctx.round,phase,rank,record:{format:RECORD_FORMAT,id,subject:{entity,point,channel,run:run.id},vantage:'space',observable:'logic.level',kind,form:typeof value==='number'?'continuous':'binary',value,time:{logical:ctx.t,sequence:0,mode:'observed'},certainty:{kind:'exact'},observer,provenance:{rule,inputs:inputs.slice()},perturbation:'none',...(principal?{principal}:{})}});
    return id;
  }
  // Emission: one arrival per bound Wire, per direction it carries out of this port, per shared
  // channel, at t + path delay; never back onto a Wire in `exclude`. `via` is the wire this value
  // itself arrived by (null at a source); an emission that crosses a plane is checked under
  // `principal` and the crossing op (src/07-graph-core.js setLevel, 439-444): a refusal is a level
  // record (rule refused, level true, the graph core's reason) and that Wire carries nothing this tick.
  function emit(run,ctx,entity,point,channel,value,exclude,from,phase,principal=null,via=null){
    const ends=indexOf(run).out.get(entity+'\u0000'+point);
    if(!ends)return;
    for(const {wire,to} of walked(run,ends)){
      if(exclude.includes(wire.id)||!wire.channels.includes(channel))continue;
      const crossing=aclCheck(run,entity,via,wire.id,principal,null);
      if(!crossing.ok){levelRefusalRecord(run,ctx,{entity,point,channel,principal,reason:crossing.reason});continue}
      // principal is left out when it is null, so a document with no ACL hashes and records
      // exactly as before (stateHash spreads a pending item's own keys; see slice 1c below).
      const item={kind:'arrival',at:ctx.t+wire.delay,entity:to.entity,point:to.point,channel,value,wire:wire.id,phase,from,...(principal?{principal}:{})};
      run.pending.push(item);ctx.fresh.push(item);
    }
  }
  // Merge order: the declared Paths first (in their declared order), the rest by a seeded draw
  // keyed by (seed, tick, entity, port, channel), recorded in the ledger (and, in replay, read from it).
  // A message arrival is tagged by its Wire and its message id, since one Wire may bring several.
  function mergeOrder(run,ctx,g,merge){
    const tag=g.channel===MESSAGE?a=>`${a.wire}#${a.value.id}`:a=>g.arrivals.filter(x=>x.wire===a.wire).length>1?`${a.wire}#${a.phase}`:a.wire;
    const items=g.arrivals.map(a=>({a,id:tag(a)})).sort((x,y)=>cmp(x.id,y.id));
    const declared=merge.order?.kind==='declared'?merge.order.paths:[];
    const first=[];for(const path of declared)for(const item of items)if(item.a.wire===path)first.push(item);
    const rest=items.filter(item=>!declared.includes(item.a.wire));
    let restOrder=rest.map(item=>item.id);
    if(rest.length>1){
      // A delta round after the first is part of the draw key, and of the recorded draw.
      const paths=restOrder.slice(),drawn=Canonical.drawOrder(run.seed,ctx.round?['merge',ctx.t,ctx.round,g.entity,g.point,g.channel]:['merge',ctx.t,g.entity,g.point,g.channel],paths);
      if(run.replayDraws){
        const recorded=run.replayDraws.find(e=>e.body.tick===ctx.t&&(e.body.round??0)===ctx.round&&e.body.entity===g.entity&&e.body.point===g.point&&e.body.channel===g.channel);
        if(!recorded||!same(recorded.body.paths,paths)||!same(recorded.body.order,drawn)){
          ctx.diverged={code:'REPLAY_DIVERGED',entry:recorded?recorded.seq:null,message:recorded?`the draw recorded at ledger entry ${recorded.seq} (${g.entity}.${g.point}.${g.channel}, tick ${ctx.t}) does not re-derive from the seed: recorded ${JSON.stringify(recorded.body.order)}, derived ${JSON.stringify(drawn)}`:`no draw is recorded for ${g.entity}.${g.point}.${g.channel} at tick ${ctx.t}`};
          return null;
        }
        restOrder=recorded.body.order.slice();
      }else restOrder=drawn;
      ctx.draws.push({tick:ctx.t,...(ctx.round?{round:ctx.round}:{}),entity:g.entity,point:g.point,channel:g.channel,paths,order:restOrder.slice()});
    }
    return [...first,...restOrder.map(id=>rest.find(item=>item.id===id))].map(item=>item.a);
  }
  // Update phase for one (entity, port, channel): input, else a device's delayed output, else the
  // merged arrivals (or a queue's head). What loses is recorded with rule `overridden`.
  // --- Access control (STATE-SPACE.md, GRAPH-MODEL.md): a plane's config.acl, the crossing a value
  // makes at a boundary point (placement.kind edge) or a plane's own open interior, and the
  // decision a principal gets there — the same algorithm the graph core specifies and exports
  // (src/07-graph-core.js aclConfig/aclDecide/crossingAt, 31-55, 99-105), read fresh here over this
  // run's own document instead of through that module, so a run's behaviour never depends on
  // whether something else happens to have loaded the graph core (tests/state_space_message_qa.py's
  // load-order check requires exactly that).
  const ACL_OPS=['enter','exit','read','write'];
  function aclConfigOf(c){
    const a=c?.config?.acl;if(!isObject(a))return null;
    const list=v=>Array.isArray(v)?v.map(String).filter(x=>ACL_OPS.includes(x)):[];
    return {default:a.default==='allow'?'allow':'deny',entries:(Array.isArray(a.entries)?a.entries:[]).filter(isObject).map(e=>({principal:String(e.principal??''),allow:list(e.allow),deny:list(e.deny)}))};
  }
  function aclPrincipalMatches(pattern,principal){
    if(principal==null||principal==='')return false;
    if(pattern==='*')return true;
    return pattern.endsWith('*')?String(principal).startsWith(pattern.slice(0,-1)):pattern===String(principal);
  }
  function aclDecideLocal(plane,principal,op){
    const acl=plane.acl;if(!acl)return {ok:true};
    const name=plane.label||plane.id;
    if(principal==null||principal==='')return {ok:false,reason:`acl: no principal may ${op} ${name} anonymously`};
    const matching=acl.entries.filter(e=>aclPrincipalMatches(e.principal,principal));
    if(matching.some(e=>e.deny.includes(op)))return {ok:false,reason:`acl: ${principal} is denied ${op} on ${name}`};
    if(matching.some(e=>e.allow.includes(op)))return {ok:true};
    return acl.default==='allow'?{ok:true}:{ok:false,reason:`acl: ${principal} may not ${op} ${name}`};
  }
  const ACL_INDEX=new WeakMap();
  function aclIndexOf(run){
    let idx=ACL_INDEX.get(run.doc);
    if(idx)return idx;
    idx={byId:new Map(run.doc.components.map(c=>[c.id,c])),wireCanvas:new Map(run.doc.wires.map(w=>[w.id,w.canvasId||Data.GLOBAL_CANVAS_ID]))};
    ACL_INDEX.set(run.doc,idx);
    return idx;
  }
  function aclPlaneInfo(byId,id){
    const c=byId.get(id);if(!c)return null;
    return {id:c.id,label:c.config?.label||c.id,acl:aclConfigOf(c),interior:Data.componentCanvasId(c)};
  }
  // The plane a value crosses at `entity`, turning from the wire it arrived by (`via`, null at a
  // source: a source cannot cross) to the one it leaves by (`toWire`): null off a boundary, else
  // {plane, op: enter|exit}.
  function aclCrossing(run,entity,via,toWire){
    if(via==null)return null;
    const {byId,wireCanvas}=aclIndexOf(run);
    const n=byId.get(entity);if(!n)return null;
    const plane=n.placement?.kind==='edge'?aclPlaneInfo(byId,n.placement.hostId):(n.form?.regions?.interior?.state==='open'?aclPlaneInfo(byId,n.id):null);
    if(!plane)return null;
    const side=c=>c===plane.interior?'in':'out',a=side(wireCanvas.get(via)),b=side(wireCanvas.get(toWire));
    return a===b?null:{plane,op:a==='out'?'enter':'exit'};
  }
  // {ok:true, crossed} when there is no boundary or the principal clears it; {ok:false, crossed:true,
  // reason} with the same acl: reason text the graph core gives otherwise. extraOp is the Wire's
  // own read/write operation, checked after the crossing's enter/exit (messages only; levels pass null).
  function aclCheck(run,entity,via,toWire,principal,extraOp){
    const cross=aclCrossing(run,entity,via,toWire);
    if(!cross)return {ok:true,crossed:false};
    for(const op of [cross.op,...(extraOp&&extraOp!=='none'?[extraOp]:[])]){
      const d=aclDecideLocal(cross.plane,principal,op);
      if(!d.ok)return {ok:false,crossed:true,reason:d.reason};
    }
    return {ok:true,crossed:true};
  }
  // A level's own crossing refusal: rule refused, level true, the graph core's reason as the
  // record's value (STATE-SPACE.md), apart from a message's hop refused.
  function levelRefusalRecord(run,ctx,{entity,point,channel,principal,reason}){
    const id=`${TMP}${ctx.tmp++}`;
    ctx.records.push({round:ctx.round,phase:0,rank:0,record:{format:RECORD_FORMAT,id,subject:{entity,point,channel,run:run.id},vantage:'space',observable:'logic.level',kind:'derived',form:'categorical',value:reason,level:true,
      time:{logical:ctx.t,sequence:0,mode:'observed'},certainty:{kind:'exact'},observer:'engine:acl',provenance:{rule:'refused',inputs:[]},perturbation:'none',...(principal?{principal}:{})}});
    return id;
  }
  // --- Messages (the graph core's inject, forward and send, src/07-graph-core.js 299-352, 429-454).
  // Each thing that happens to a message is one record of form message on the message channel: its
  // value names the message, principal says who it acts for, hop what happened. A message's hops are
  // its records in sequence order; its lineage is the records that share its root.
  // A record about a message: observable message with a hop, or (a receipt) its own observable and no hop.
  function messageRecord(run,ctx,{entity,point,kind='derived',observer,rule,inputs,message,principal,hop,observable='message'}){
    const id=`${TMP}${ctx.tmp++}`;
    const record={format:RECORD_FORMAT,id,subject:{entity,point,channel:MESSAGE,run:run.id},vantage:'space',observable,kind,form:'message',value:copy(message),
      time:{logical:ctx.t,sequence:0,mode:'observed'},certainty:{kind:'exact'},observer,provenance:{rule,inputs:inputs.slice()},perturbation:'none',principal:principal??null,...(hop?{hop}:{})};
    // Records at one port sort by delivery (injects, then arrivals in merge order), then by message.
    ctx.records.push({round:ctx.round,phase:0,rank:0,record,key:[entity,point,MESSAGE,'message',ctx.delivery,message.id,hop?HOP_RANK[hop.event]??4:4]});
    return id;
  }
  // A stateful flow card's working state for this tick: its committed device.state (the pattern's
  // initial state before the first one), copied once per tick through the undo log. Messages reaching
  // one card in a tick are handled one after another in delivery order, each seeing the state the one
  // before it left; what the card holds at the end of the tick is committed as one record.
  function flowState(run,ctx,entity){
    const flow=run.components[entity].flow,p=pattern(flow.pattern);
    if(!p.stateful)return null;
    if(!ctx.stateTouched.has(entity)){
      const had=own(run.deviceState,entity),before=had?run.deviceState[entity]:p.initial(flow.parameters);
      ctx.stateTouched.set(entity,{had,before:Canonical.canonicalize(before),inputs:[],round:ctx.round});
      put(run.deviceState,ctx.undoState,entity,copy(before));
    }
    return run.deviceState[entity];
  }
  const stateCause=(ctx,entity,id)=>{const t=ctx.stateTouched.get(entity);if(t){t.inputs.push(id);t.round=ctx.round}};
  // A message at a component, after it arrived by `via` at `point` (via null for an inject or an
  // edge), in the graph core's order (src/07-graph-core.js arrive and continueAt, 375-454 at 7b939e3):
  // a flow card's control Path sets it; an asserted card takes set or toggle as its new level; a flow
  // card's pattern takes it in (refuse, end, hold it, or pass); then continueAt.
  function messageAt(run,ctx,entity,point,message,principal,via,from){
    const component=run.components[entity]||{},flow=component.flow||null,p=flow?pattern(flow.pattern):null;
    let prev=from;
    const rec=(event,{reason=null,rule=null,observer=null,observable}={})=>{
      prev=messageRecord(run,ctx,{entity,point,observer:observer||(flow?`rule:${flow.ref}`:'engine:message'),rule:rule||(flow?flow.ref:event),inputs:[prev],message,principal,hop:{event,...(reason?{reason}:{})},observable});
      if(flow)stateCause(ctx,entity,prev);
      return prev;
    };
    if(flow&&p.control&&via!==null&&flow.control.includes(via)){
      p.control(flow.parameters,flowState(run,ctx,entity),message.payload);
      return rec('controlled');
    }
    const asserted=component.asserted;
    if(asserted&&isObject(message.payload)&&('set' in message.payload||message.payload.toggle)){
      const id=rec('asserted',{rule:'asserted',observer:'rule:asserted'});
      const current=asserted.outs.length?levelOf(run.signal[portKey(entity,asserted.outs[0],'main')]):0;
      const level=message.payload.toggle?LEVEL-current:toLevel(Number(message.payload.set));
      const value=asserted.kind==='continuous'?level:level>=asserted.threshold;
      // The new level is written in the next delta round of this tick, like any zero-delay change.
      for(const out of asserted.outs){const item={kind:'assert',at:ctx.t,entity,point:out,channel:'main',value,from:id};run.pending.push(item);ctx.fresh.push(item)}
      return;
    }
    if(flow&&p.intake){
      const d=p.intake(flow.parameters,flowState(run,ctx,entity),flow.settings,{value:message,principal:principal??null,via,t:ctx.t});
      if(d.refuse)return rec('refused',{reason:d.refuse});
      if(d.end)return rec(d.end,{rule:d.rule});
      if(d.wait){
        const id=rec(d.wait);d.item.from=id;d.item.point=point;
        if(d.release!=null){const item={kind:'release',at:ctx.t+d.release,entity,point,channel:MESSAGE};run.pending.push(item);ctx.fresh.push(item)}
        if(!d.ready)return;
        const {parts,taken}=p.take(flow.parameters,run.deviceState[entity],flow.settings);
        const joined={id:`${message.id}.j`,root:message.root,parent:message.id,channel:message.channel,payload:{parts},origin:message.origin};
        const jid=messageRecord(run,ctx,{entity,point,observer:`rule:${flow.ref}`,rule:flow.ref,inputs:taken.map(x=>x.from).filter(Boolean),message:joined,principal,hop:{event:'joined'}});
        stateCause(ctx,entity,jid);
        return continueAt(run,ctx,entity,point,joined,principal,null,jid);
      }
      if(d.receipt)prev=messageRecord(run,ctx,{entity,point,observer:`rule:${flow.ref}`,rule:'receipt',inputs:[prev],message,principal,observable:'receipt'});
    }
    return continueAt(run,ctx,entity,point,message,principal,via,prev);
  }
  // After intake (the graph core's continueAt): a flow card naming a handler refuses, since a run has
  // no handler registry (the graph core's answer with no handlers registered); a passive card absorbs
  // the message; otherwise it leaves by every carried leg of the component but `via` whose Wire
  // accepts its channel, one child per leg (<id>.<n>, n in leg order), or by the legs the card's flow
  // pattern chooses among those; with no such leg it is delivered, unless legs exist and all refuse
  // its channel, when it is refused, never dropped. A leg that crosses a plane is checked under the
  // message's principal, the crossing op then the Wire's own operation (src/07-graph-core.js send,
  // 283-297): refused writes a hop refused record with the graph core's reason and that leg is not
  // taken; admitted writes a crossed hop first.
  function continueAt(run,ctx,entity,point,message,principal,via,from){
    const component=run.components[entity]||{},flow=component.flow||null,p=flow?pattern(flow.pattern):null;
    const observer=flow?`rule:${flow.ref}`:null;
    const end=(event,reason)=>{const id=messageRecord(run,ctx,{entity,point,observer:observer||'engine:message',rule:flow?flow.ref:event,inputs:[from],message,principal,hop:reason?{event,reason}:{event}});if(flow)stateCause(ctx,entity,id);return id};
    if(flow&&flow.settings.handler)return end('refused',`no handler registered: ${flow.settings.handler}`);
    if(component.passive)return end('absorbed');
    const legs=(indexOf(run).legs.get(entity)||[]).filter(leg=>leg.wire!==via);
    const open=legs.filter(leg=>!message.channel||!leg.accepts||leg.accepts.includes(message.channel));
    if(!open.length)return legs.length?end('refused',`no end accepts channel ${message.channel}`):end('delivered');
    let chosen=open.map((_,n)=>n);
    if(flow&&p.choose){
      const c=p.choose(flow.parameters,flowState(run,ctx,entity),flow.settings,{value:message,principal:principal??null},open);
      if(c.refuse)return end('refused',c.refuse);
      chosen=c.legs;
    }
    if(component.principal)principal=component.principal;
    const rule=flow?flow.ref:'fanout',by=observer||'engine:fanout';
    const forwarded=messageRecord(run,ctx,{entity,point,observer:by,rule,inputs:[from],message,principal,hop:{event:'forwarded'}});
    if(flow)stateCause(ctx,entity,forwarded);
    for(const n of chosen){
      const leg=open[n];
      const child={...copy(message),id:`${message.id}.${n}`,parent:message.id};
      const crossing=aclCheck(run,entity,via,leg.wire,principal,leg.operation);
      if(!crossing.ok){
        messageRecord(run,ctx,{entity,point:leg.point,observer:by,rule,inputs:[forwarded],message:child,principal,hop:{event:'sent',wire:leg.wire,to:leg.to.entity}});
        messageRecord(run,ctx,{entity,point:leg.point,observer:'engine:acl',rule,inputs:[forwarded],message:child,principal,hop:{event:'refused',reason:crossing.reason}});
        continue;
      }
      if(crossing.crossed)messageRecord(run,ctx,{entity,point:leg.point,observer:'engine:acl',rule,inputs:[forwarded],message:child,principal,hop:{event:'crossed',wire:leg.wire,to:leg.to.entity}});
      const sent=messageRecord(run,ctx,{entity,point:leg.point,observer:by,rule,inputs:[forwarded],message:child,principal,hop:{event:'sent',wire:leg.wire,to:leg.to.entity}});
      const item={kind:'arrival',at:ctx.t+leg.delay,entity:leg.to.entity,point:leg.to.point,channel:MESSAGE,value:child,principal:principal??null,wire:leg.wire,phase:0,from:sent};
      run.pending.push(item);ctx.fresh.push(item);
    }
  }
  // A buffer's release (the graph core's release, 455-459): the head of its queue goes on from the
  // card (continueAt) by the Path it came by; the next release is scheduled while the queue holds more.
  function releaseAt(run,ctx,entity){
    const flow=run.components[entity].flow,p=pattern(flow.pattern);
    const r=p.release(flow.parameters,flowState(run,ctx,entity),flow.settings);
    if(!r.item)return;
    if(r.next!=null){const item={kind:'release',at:ctx.t+r.next,entity,point:r.item.point,channel:MESSAGE};run.pending.push(item);ctx.fresh.push(item)}
    const it=r.item;
    const id=messageRecord(run,ctx,{entity,point:it.point,observer:`rule:${flow.ref}`,rule:flow.ref,inputs:it.from?[it.from]:[],message:it.message,principal:it.principal,hop:{event:'released'}});
    stateCause(ctx,entity,id);
    continueAt(run,ctx,entity,it.point,it.message,it.principal,it.via,id);
  }
  // An edge that starts work (src/07-graph-core.js:469-473 at 7b939e3): a level change on a card whose
  // config.signal.on matches its polarity starts a message on config.signal.channel, payload {node,
  // polarity, from, to, at} (at in ms; from and to 0/1 on a binary card, levels on a continuous one),
  // origin the card and principal the card's own, and it goes on from that card.
  // A level written at a card's edge port is noted here and its message started at the end of the round.
  function noteEdge(run,ctx,entity,point,before,after,record){
    const edge=run.components[entity]?.edge;if(!edge||edge.point!==point)return;
    const from=levelOf(before),to=levelOf(after);
    if(from!==to)ctx.edges.push({entity,from,to,record});
  }
  function edgeAt(run,ctx,{entity,from,to,record}){
    const component=run.components[entity],edge=component.edge,polarity=to>from?'+':'-';
    if(!(edge.on==='±'||edge.on===polarity))return;
    const scale=x=>edge.kind==='continuous'?x:(x>=LEVEL?1:0);
    const id=`e-${entity}-${ctx.t}${ctx.round?`-${ctx.round}`:''}`;
    const message={id,root:id,parent:null,channel:edge.channel,payload:{node:entity,polarity,from:scale(from),to:scale(to),at:ctx.t*run.tickMs},origin:entity};
    const principal=component.principal??null;
    const rid=messageRecord(run,ctx,{entity,point:edge.point,observer:'rule:edge',rule:'edge',inputs:[record],message,principal,hop:{event:'edge'}});
    messageAt(run,ctx,entity,edge.point,message,principal,null,rid);
  }
  // Update phase on the message channel of one port: injects start their messages; arrivals are put in
  // merge order (the declared Paths first, the rest a draw recorded like any merge) and every one is
  // delivered in this tick, in that order, as the graph core delivers same-time arrivals. (One per
  // tick is the level channel's queue merge only.)
  function messagePort(run,ctx,g){
    ctx.delivery=0;
    // A buffer's releases due now come first, then injects, then arrivals.
    for(let i=0;i<g.releases.length;i++){ctx.delivery++;releaseAt(run,ctx,g.entity)}
    for(const input of g.injects.slice().sort((x,y)=>x.seq-y.seq)){
      ctx.delivery++;
      const id=`m-${input.seq}`,message={id,root:id,parent:null,channel:input.value.channel,payload:copy(input.value.payload),origin:g.entity};
      const at=messageRecord(run,ctx,{entity:g.entity,point:g.point,kind:'registered',observer:'input',rule:'input',inputs:[],message,principal:input.value.principal,hop:{event:'injected'}});
      messageAt(run,ctx,g.entity,g.point,message,input.value.principal,null,at);
    }
    if(!g.arrivals.length)return;
    const key=portKey(g.entity,g.point,MESSAGE);
    const ordered=g.arrivals.length>1?mergeOrder(run,ctx,g,run.merges[key]||MESSAGE_MERGE):g.arrivals;if(!ordered)return;
    for(const item of ordered){
      ctx.delivery++;
      const id=messageRecord(run,ctx,{entity:g.entity,point:g.point,observer:`path:${item.wire}`,rule:'merge@1',inputs:[item.from],message:item.value,principal:item.principal??null,hop:{event:'arrived',wire:item.wire}});
      messageAt(run,ctx,g.entity,g.point,item.value,item.principal??null,item.wire,id);
    }
  }
  // Blocked legs are recorded once, at the first tick, with the graph core's reason.
  function blockedRecords(run,ctx){
    for(const b of run.blocked||[]){
      const id=`${TMP}${ctx.tmp++}`;
      ctx.records.push({round:0,phase:0,rank:0,key:[b.wire,'','','path.carries',b.reason],record:{format:RECORD_FORMAT,id,subject:{entity:b.wire,run:run.id},vantage:'space',observable:'path.carries',kind:'derived',form:'categorical',value:b.reason,
        time:{logical:ctx.t,sequence:0,mode:'observed'},certainty:{kind:'exact'},observer:'engine:passability',provenance:{rule:'blocked',inputs:[]},perturbation:'none'}});
    }
  }
  // A level record's own principal (STATE-SPACE.md, access control): the node's own, else the
  // principal of the arrival that set it, the first in wire-id order whose value equals the
  // winning one (several may share a tick). `source` carries that arrival's wire too, the `via`
  // an emission is later checked under; a node's own principal does not change it, since the
  // crossing is about which side of a boundary the value came from, not who speaks for the node.
  function pickArrivalSource(arrivals,value){
    const sorted=arrivals.slice().sort((x,y)=>cmp(x.wire,y.wire));
    const hit=sorted.find(a=>a.value===value);
    return hit?{wire:hit.wire,principal:hit.principal??null}:null;
  }
  function updatePort(run,ctx,g){
    if(g.channel===MESSAGE)return messagePort(run,ctx,g);
    const key=portKey(g.entity,g.point,g.channel),old=run.signal[key]===true,role=run.components[g.entity]?.role;
    const nodePrincipal=run.components[g.entity]?.principal??null;
    const merge=run.merges[key]||DEFAULT_MERGE,queue=merge.combine==='queue'?ensureQueue(run,ctx,key):null;
    const base={entity:g.entity,point:g.point,channel:g.channel,phase:0};
    let win=null;
    if(g.input&&g.input.kind==='assert')win={value:g.input.value,kind:'derived',observer:'rule:asserted',rule:'asserted',inputs:[g.input.from],emits:true,exclude:[],source:null};
    else if(g.input&&g.input.kind==='clock')win={value:g.input.value,kind:'derived',observer:'rule:clock',rule:'clock',inputs:[],always:true,exclude:[],source:null};
    else if(g.input)win={value:g.input.value,kind:'registered',observer:'input',rule:'input',inputs:[],always:true,exclude:[],source:null};
    else if(g.output)win={value:g.output.value,kind:'derived',observer:`rule:${g.output.rule}`,rule:g.output.rule,inputs:g.output.inputs,emits:true,exclude:[],source:null};
    if(win){
      for(const a of g.arrivals)makeRecord(run,ctx,{...base,kind:'derived',value:a.value,observer:`path:${a.wire}`,rule:'overridden',inputs:[a.from],rank:a.phase,principal:a.principal??null});
    }else{
      const arrived=g.arrivals.map(a=>a.wire);
      const orderFree=['or','and','min','max'].includes(merge.combine);
      if(orderFree&&g.arrivals.length){
        const sorted=g.arrivals.slice().sort((x,y)=>cmpList([x.wire,x.phase],[y.wire,y.phase]));
        const value=merge.combine==='or'||merge.combine==='max'?sorted.some(a=>a.value):sorted.every(a=>a.value);
        win=sorted.length===1?{value,observer:`path:${sorted[0].wire}`,rule:'path',inputs:[sorted[0].from]}:{value,observer:'engine:merge@1',rule:'merge@1',inputs:sorted.map(a=>a.from)};
        win.source=pickArrivalSource(sorted,value);
      }else if(queue){
        if(g.arrivals.length){const ordered=g.arrivals.length>1?mergeOrder(run,ctx,g,merge):g.arrivals;if(!ordered)return;for(const a of ordered)queue.items.push({value:a.value,wire:a.wire,phase:a.phase,from:a.from,principal:a.principal??null})}
        // A queue delivers once per tick, whatever delta round its arrivals come in.
        if(queue.items.length>queue.head&&!ctx.delivered.has(key)){ctx.delivered.add(key);const item=queue.items[queue.head++];win={value:item.value,observer:'engine:merge@1',rule:'merge@1',inputs:[item.from],source:{wire:item.wire,principal:item.principal??null}};if(!arrived.includes(item.wire))arrived.push(item.wire)}
      }else if(g.arrivals.length===1){
        const a=g.arrivals[0];win={value:a.value,observer:`path:${a.wire}`,rule:'path',inputs:[a.from],source:{wire:a.wire,principal:a.principal??null}};
      }else if(g.arrivals.length){
        const ordered=mergeOrder(run,ctx,g,merge);if(!ordered)return;
        const pick=merge.combine==='first'?ordered[0]:ordered[ordered.length-1];
        win={value:pick.value,observer:'engine:merge@1',rule:'merge@1',inputs:ordered.map(a=>a.from),source:{wire:pick.wire,principal:pick.principal??null}};
      }
      if(!win){if(queue)queue.next=ctx.t+1;return}
      win.kind='derived';win.exclude=arrived;win.emits=role==='point';
    }
    if(queue)queue.next=ctx.t+1;
    const principal=nodePrincipal??win.source?.principal??null,via=win.source?win.source.wire:null;
    const id=makeRecord(run,ctx,{...base,kind:win.kind,value:win.value,observer:win.observer,rule:win.rule,inputs:win.inputs,principal});
    noteEdge(run,ctx,g.entity,g.point,run.signal[key],win.value,id);
    put(run.signal,ctx.undoSignal,key,win.value);put(run.lastRecord,ctx.undoLast,key,id);put(run.levelPrincipal,ctx.undoPrincipal,key,principal);ctx.written.push(key);
    const changed=win.value!==old;
    if(changed)ctx.changed.add(key);
    if(win.always||(changed&&win.emits))emit(run,ctx,g.entity,g.point,g.channel,win.value,win.exclude,id,0,principal,via);
  }
  // Evaluate phase: a device whose input port changed reads committed state only.
  // A combine@1 device's own named input is `<port>:<wireId>` (topology's land): the wire is the
  // tail after the last colon. A device from a definition carries no such name (its ports are its
  // own, not one Wire's), so it has no via either, the way an asserted source has none.
  function deviceWire(name){const i=name.lastIndexOf(':');return i<0?null:name.slice(i+1)}
  function evaluateDevice(run,ctx,entity,committed){
    const component=run.components[entity],definition=run.definitions[component.definition],p=pattern(definition.pattern);
    const nodePrincipal=component.principal??null;
    const values={},inputs=[];
    for(const name of component.inputs){const key=portKey(entity,name,'main');values[name]=component.combine?committed(key):committed(key)===true;if(run.lastRecord[key])inputs.push(run.lastRecord[key])}
    const out=p.evaluate(definition.parameters,values),delay=definition.delay||0,epsilon=definition.parameters.epsilon||0;
    // A combine@1 device relays its own Wires into one value, the way a Point's arrivals merge
    // (STATE-SPACE.md, access control): the node's own principal, else the first input in wire-id
    // order whose value equals the output, same as `pickArrivalSource`. A device from an authored
    // definition (truth_table, merge) has no Wire-named ports to pick from and so no via either.
    for(const name of component.outputs){
      const key=portKey(entity,name,'main'),value=out[name];
      let source=null;
      if(component.combine){
        const named=component.inputs.map(n=>({wire:deviceWire(n),principal:run.levelPrincipal[portKey(entity,n,'main')]??null,value:values[n]})).filter(x=>x.wire).sort((x,y)=>cmp(x.wire,y.wire));
        source=named.find(x=>x.value===value)||null;
      }
      const principal=nodePrincipal??source?.principal??null,via=source?source.wire:null;
      if(delay===0){
        if(sameLevel(value,run.signal[key],epsilon))continue;
        ctx.cost++;
        const id=makeRecord(run,ctx,{entity,point:name,channel:'main',kind:'derived',value,observer:`rule:${component.definition}`,rule:component.definition,inputs,phase:1,principal});
        if(!ctx.evaluated.has(key))ctx.evaluated.set(key,run.signal[key]);
        noteEdge(run,ctx,entity,name,run.signal[key],value,id);
        put(run.signal,ctx.undoSignal,key,value);put(run.lastRecord,ctx.undoLast,key,id);put(run.levelPrincipal,ctx.undoPrincipal,key,principal);ctx.written.push(key);
        emit(run,ctx,entity,name,'main',value,[],id,1,principal,via);
      }else{
        // Transport delay: schedule every change from the latest value already on its way.
        let latest=run.signal[key],at=-1;
        for(const item of run.pending)if(item.kind==='output'&&item.entity===entity&&item.point===name&&item.channel==='main'&&item.at>at){at=item.at;latest=item.value}
        if(!sameLevel(value,latest,epsilon)){const item={kind:'output',at:ctx.t+delay,entity,point:name,channel:'main',value,rule:component.definition,inputs:inputs.slice(),...(principal?{principal}:{})};run.pending.push(item);ctx.fresh.push(item)}
      }
    }
  }
  function resolveTmp(value,map){
    if(typeof value==='string')return value.startsWith(TMP)?map.get(value):value;
    if(Array.isArray(value))return value.map(x=>resolveTmp(x,map));
    if(isObject(value)){const out={};for(const [k,v] of Object.entries(value))out[k]=resolveTmp(v,map);return out}
    return value;
  }
  // Every `from` key of a flow card's state that holds a provisional id, mapped; a message value is left as it is.
  function resolveFrom(value,map){
    if(Array.isArray(value))return value.map(x=>resolveFrom(x,map));
    if(!isObject(value))return value;
    const out={};
    for(const [k,v] of Object.entries(value))out[k]=k==='message'?v:k==='from'&&typeof v==='string'&&v.startsWith(TMP)?map.get(v):resolveFrom(v,map);
    return out;
  }
  // A flow card's state without the record ids it keeps: provenance names the past and changes no value.
  function stripFrom(value){
    if(Array.isArray(value))return value.map(stripFrom);
    if(!isObject(value))return value;
    const out={};for(const [k,v] of Object.entries(value))if(k!=='from')out[k]=k==='message'?v:stripFrom(v);
    return out;
  }
  // Writes to signal and lastRecord go through put, which keeps each key's value from before the
  // tick, so a refused tick is undone in place (a key the tick added is removed again).
  const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
  function put(obj,undo,key,value){if(!undo.has(key))undo.set(key,own(obj,key)?[true,obj[key]]:[false]);obj[key]=value}
  function undo(obj,log){for(const [key,[had,value]] of log)if(had)obj[key]=value;else delete obj[key]}
  // A record never precedes its cause: the key-sorted records of one tick, reordered only as far as
  // needed so that every record comes after the records of this tick it names in provenance.inputs
  // (always the lowest-keyed record whose causes are placed next; a list already in causal order is
  // returned as it is). Causes are acyclic, since a record can only name records made before it.
  function causalOrder(sorted){
    const at=new Map(sorted.map((x,i)=>[x.record.id,i])),need=new Array(sorted.length).fill(0),next=sorted.map(()=>[]);
    sorted.forEach((x,i)=>{for(const id of x.record.provenance.inputs){const j=at.get(id);if(j!==undefined&&j!==i){need[i]++;next[j].push(i)}}});
    const heap=[],push=i=>{heap.push(i);let k=heap.length-1;while(k>0){const p=(k-1)>>1;if(heap[p]<=heap[k])break;[heap[p],heap[k]]=[heap[k],heap[p]];k=p}};
    const pop=()=>{const top=heap[0],last=heap.pop();if(heap.length){heap[0]=last;let k=0;for(;;){const l=2*k+1,r=l+1;let m=k;if(l<heap.length&&heap[l]<heap[m])m=l;if(r<heap.length&&heap[r]<heap[m])m=r;if(m===k)break;[heap[m],heap[k]]=[heap[k],heap[m]];k=m}}return top};
    need.forEach((n,i)=>{if(!n)push(i)});
    const out=[];
    while(heap.length){const i=pop();out.push(sorted[i]);for(const j of next[i])if(--need[j]===0)push(j)}
    return out;
  }
  // A tick runs in delta rounds: round 0 takes what was scheduled for it; what a zero-delay Path or a
  // delay-0 device output schedules for the same tick is the next round, two-phase like the first,
  // until nothing more is due at t. A cycle of zero-delay legs is refused at start, so the rounds end;
  // the budget bounds them besides.
  function processTick(run,t,ctx){
    if(run.tick===null)blockedRecords(run,ctx);
    for(ctx.round=0;;ctx.round++){
      if(ctx.round>0){ctx.changed=new Set();ctx.evaluated=new Map()}
      const due=run.pending.filter(x=>x.at===t);run.pending=run.pending.filter(x=>x.at!==t);
      const groups=new Map();
      const group=(entity,point,channel)=>{const key=portKey(entity,point,channel);if(!groups.has(key))groups.set(key,{entity,point,channel,input:null,output:null,arrivals:[],injects:[],releases:[]});return groups.get(key)};
      for(const item of due){
        const g=group(item.entity,item.point,item.channel);ctx.cost++;
        if(item.channel===MESSAGE)(item.kind==='input'?g.injects:item.kind==='release'?g.releases:g.arrivals).push(item);
        else if(item.kind==='input'||item.kind==='clock'||item.kind==='assert')g.input=item;else if(item.kind==='output')g.output=item;else g.arrivals.push(item);
        if(item.kind==='clock'){
          const source=run.clocks[portKey(item.entity,item.point,item.channel)];
          const next=source&&(source.clock.wave==='square'?clockEdge(source,run.tickMs,item.value?item.k:item.k+1,!item.value,t):clockEdge(source,run.tickMs,item.k+1,null,t));
          if(next){run.pending.push(next);ctx.fresh.push(next)}
        }
      }
      if(ctx.round===0)for(const [key,q] of Object.entries(run.queues))if(q.items.length>q.head&&q.next===t){const [entity,point,channel]=JSON.parse(key);group(entity,point,channel)}
      // Levels first, in the walk's order; then messages, always in port order, since a flow card's
      // state threads through the messages it handles and no outcome may depend on the walk.
      const keys=[...groups.keys()].sort(),levelKeys=keys.filter(k=>groups.get(k).channel!==MESSAGE),messageKeys=keys.filter(k=>groups.get(k).channel===MESSAGE);
      for(const key of [...walked(run,levelKeys),...messageKeys]){updatePort(run,ctx,groups.get(key));if(ctx.diverged)return {ok:false,...ctx.diverged}}
      // Committed state is the signal after the update phase: what the evaluate phase overwrites is read from before it.
      const committed=key=>ctx.evaluated.has(key)?ctx.evaluated.get(key):run.signal[key];
      const devices=indexOf(run).devices.filter(x=>(t===0&&ctx.round===0)||x.inputs.some(key=>ctx.changed.has(key))).map(x=>x.id);
      for(const entity of walked(run,devices))evaluateDevice(run,ctx,entity,committed);
      // Edges noted this round start their messages, by card.
      const edges=ctx.edges.splice(0).sort((x,y)=>cmp(x.entity,y.entity));
      for(const edge of edges){ctx.delivery=1e6;edgeAt(run,ctx,edge)}
      if(!run.pending.some(x=>x.at===t)||run.spent+ctx.cost>run.budget)break;
    }
    // Commit: each flow card whose state this tick changed gets one device.state record (vantage point).
    for(const [entity,touched] of [...ctx.stateTouched].sort((x,y)=>cmp(x[0],y[0]))){
      const now=run.deviceState[entity];
      if(Canonical.canonicalize(now)===touched.before){if(!touched.had)delete run.deviceState[entity];continue}
      const ref=run.components[entity].flow.ref,id=`${TMP}${ctx.tmp++}`;
      const record={format:RECORD_FORMAT,id,subject:{entity,run:run.id},vantage:'point',observable:'device.state',kind:'derived',form:'state',value:null,
        time:{logical:t,sequence:0,mode:'observed'},certainty:{kind:'exact'},observer:`rule:${ref}`,provenance:{rule:ref,inputs:touched.inputs.slice()},perturbation:'none'};
      ctx.stateRecords.push({entity,record});
      ctx.records.push({round:touched.round,phase:0,rank:0,key:[entity,'￿','device.state'],record});
    }
    // Sequence is assigned after the tick, from stable ids only, then put in causal order (no record
    // before a record it names); then every provisional id is resolved.
    // A provisional id is only ever held by what this tick made: its records, the pending items it
    // scheduled and the lastRecord entries it wrote (queue items come from arrivals of earlier ticks).
    const sortKey=x=>[x.round,...(x.key||[x.record.subject.entity,x.record.subject.point,x.record.subject.channel,x.record.observable,x.record.kind,x.phase,x.record.observer,x.rank,x.record.value?1:0])];
    const sorted=causalOrder(ctx.records.map(x=>({x,k:sortKey(x)})).sort((x,y)=>cmpList(x.k,y.k)).map(d=>d.x));
    const map=new Map();
    for(const x of sorted){const seq=run.sequence++;map.set(x.record.id,`sr-${run.id}-${String(seq).padStart(6,'0')}`);x.record.id=map.get(x.record.id);x.record.time.sequence=seq}
    const records=sorted.map(x=>{x.record.provenance.inputs=resolveTmp(x.record.provenance.inputs,map);return x.record});
    for(const item of ctx.fresh){if(item.from!==undefined)item.from=resolveTmp(item.from,map);if(item.inputs!==undefined)item.inputs=resolveTmp(item.inputs,map)}
    for(const key of ctx.written)put(run.lastRecord,ctx.undoLast,key,resolveTmp(run.lastRecord[key],map));
    // A flow card's state names the records that put a message in it (`from`): resolved now, then recorded.
    for(const {entity,record} of ctx.stateRecords){run.deviceState[entity]=resolveFrom(run.deviceState[entity],map);record.value=copy(run.deviceState[entity])}
    // Only the queues this tick touched can hold a fresh (TMP) id or have run dry: resolve just the
    // items this tick appended (never the ones already resolved by an earlier tick), by buffer index.
    for(const [key,entry] of ctx.queueUndo){
      const q=entry.queue,from=entry.existed?entry.length:0;
      for(let i=from;i<q.items.length;i++){const item=q.items[i];if(typeof item.from==='string'&&item.from.startsWith(TMP))item.from=map.get(item.from)}
      if(q.items.length===q.head)delete run.queues[key];
    }
    run.pending=run.pending.map(x=>({x,k:pendingKey(x)})).sort((x,y)=>cmp(x.k,y.k)).map(d=>d.x);
    ctx.draws.sort((x,y)=>cmpList([x.round??0,x.entity,x.point,x.channel],[y.round??0,y.entity,y.point,y.channel]));
    return {ok:true,cost:ctx.cost,records,draws:ctx.draws};
  }
  // One step is the earliest tick with scheduled work. Signal and lastRecord writes go through an
  // undo log (`put`/`undo`); a queue merge's buffer is appended and delivered in place, its own undo
  // log (`queueUndo`) holding only what changed (see `ensureQueue`/`undoQueues`) — never a copy of a
  // queue's items. Pending and sequence are restored from a reference kept before the tick. So a
  // refused tick (BUDGET_SPENT, REPLAY_DIVERGED) leaves the run exactly as it was. The rest of the
  // run is read-only during a tick and is shared, not copied.
  function step(run){
    if(!isObject(run)||run.runtimeVersion!==RUNTIME_VERSION)return {ok:false,code:'RUN_INVALID',message:`not a ${RUNTIME_VERSION} run`};
    const t=nextTick(run);
    if(t===null)return {ok:true,tick:null,records:[]};
    const before={pending:run.pending,sequence:run.sequence};
    const ctx={t,round:0,delivery:0,delivered:new Set(),cost:0,tmp:0,records:[],draws:[],changed:new Set(),diverged:null,fresh:[],written:[],evaluated:new Map(),undoSignal:new Map(),undoLast:new Map(),undoPrincipal:new Map(),queueUndo:new Map(),
      undoState:new Map(),stateTouched:new Map(),stateRecords:[],edges:[]};
    if(!isObject(run.deviceState))run.deviceState={};
    const result=processTick(run,t,ctx);
    const refused=!result.ok?result:run.spent+result.cost>run.budget?{ok:false,code:'BUDGET_SPENT',tick:t,left:null,message:`processing tick ${t} takes ${result.cost} events; ${run.budget-run.spent} of the budget ${run.budget} remain`}:null;
    if(refused){
      undo(run.signal,ctx.undoSignal);undo(run.lastRecord,ctx.undoLast);undo(run.levelPrincipal,ctx.undoPrincipal);undo(run.deviceState,ctx.undoState);Object.assign(run,before);
      undoQueues(run,ctx.queueUndo);
      if(refused.code==='BUDGET_SPENT')refused.left=queuedCount(run);
      return refused;
    }
    for(const draw of result.draws)appendEntry(run,'draw',draw);
    for(const record of result.records)run.records.push(record);
    run.tick=t;run.spent+=result.cost;
    return {ok:true,tick:t,records:copy(result.records)};
  }
  function traceOf(run){
    return {format:TRACE_FORMAT,replayKey:copy(run.ledger[0].body.replayKey),documentRevision:run.doc.revision,budget:run.budget,through:run.tick,head:run.ledger[run.ledger.length-1].hash,ledger:copy(run.ledger),records:copy(run.records)};
  }
  // Shape and every hash link. The chain is recomputed from the start, so a change to any byte
  // of an entry fails that entry and every entry after it.
  function validateTrace(trace){
    const errors=[];let entry=null;
    const fail=(i,message)=>{errors.push(i===null?message:`ledger ${i}: ${message}`);if(i!==null&&entry===null)entry=i};
    if(!isObject(trace))return {ok:false,entry,errors:['trace must be an object']};
    unknownKeys(trace,['format','replayKey','documentRevision','budget','through','head','ledger','records'],'trace',errors);
    if(trace.through!==null&&!natural(trace.through))errors.push('through must be null or an integer >= 0');
    if(typeof trace.head!=='string'||!/^[0-9a-f]{64}$/.test(trace.head))errors.push('head must be a 64-digit hex hash');
    if(trace.format!==TRACE_FORMAT)errors.push(`format must equal ${TRACE_FORMAT}`);
    if(!natural(trace.documentRevision))errors.push('documentRevision must be an integer >= 0');
    if(!natural(trace.budget))errors.push('budget must be an integer >= 0');
    const key=trace.replayKey;
    if(!isObject(key))errors.push('replayKey must be an object');
    else{
      unknownKeys(key,REPLAY_KEY_FIELDS,'replayKey',errors);
      for(const field of ['documentId','documentHash','runtimeVersion','traceFormat','seed'])if(typeof key[field]!=='string')errors.push(`replayKey.${field} must be a string`);
      if(!Array.isArray(key.definitions)||!key.definitions.every(nonEmpty))errors.push('replayKey.definitions must be an array of id@version strings');
      if(!Array.isArray(key.inputs))errors.push('replayKey.inputs must be an array');
    }
    if(!Array.isArray(trace.ledger)||!trace.ledger.length)errors.push('ledger must be a non-empty array');
    else{
      let running=ZERO_HASH,broken=null;
      trace.ledger.forEach((e,i)=>{
        if(broken!==null){fail(i,`follows the broken link at entry ${broken}`);return}
        if(!isObject(e)){fail(i,'an entry must be an object');broken=i;return}
        const extra=Object.keys(e).filter(k=>!['seq','kind','body','prev','hash'].includes(k));
        let bad=extra.length?`unknown key ${extra[0]}`:null;
        if(!bad&&e.seq!==i)bad=`seq must be ${i}`;
        if(!bad&&!LEDGER_KINDS.includes(e.kind))bad=`kind must be one of ${LEDGER_KINDS.join(', ')}`;
        if(!bad&&(i===0)!==(e.kind==='start'))bad=i===0?'the first entry must be start':'only the first entry is start';
        if(!bad&&e.prev!==running)bad='prev does not link to the entry before';
        let hash=null;
        if(!bad){try{hash=ledgerHash(e.seq,e.kind,e.body,e.prev)}catch(_){bad='body is not canonical JSON'}}
        if(!bad&&e.hash!==hash)bad='hash does not match the entry';
        if(bad){fail(i,bad);broken=i;return}
        running=hash;
      });
      if(entry===null&&isObject(key)&&!same(trace.ledger[0].body,{replayKey:key,budget:trace.budget}))fail(0,'the start entry does not carry the replayKey and budget');
      // A consistently truncated (or extended) ledger fails here: head names the entry the trace ends on.
      if(entry===null&&trace.head!==trace.ledger[trace.ledger.length-1].hash){errors.push(`head does not equal the hash of the last ledger entry (${trace.ledger.length-1})`);entry=trace.ledger.length}
    }
    if(trace.records!==undefined&&!Array.isArray(trace.records))errors.push('records must be an array when present');
    else if(trace.records!==undefined)trace.records.forEach((r,i)=>{const v=validateRecord(r);if(!v.ok)errors.push(`record ${i}: ${v.errors.join('; ')}`)});
    return {ok:errors.length===0,entry,errors};
  }
  // Replay: the trace's replay key recomputed from doc, packs, its inputs and seed; the fold re-run
  // through the trace's `through` tick, reading draws from the ledger; the ledger compared byte for
  // byte, and the records too when the trace carries them.
  function replay(options){
    const o=isObject(options)?options:{};
    const trace=o.trace,checked=validateTrace(trace);
    if(!checked.ok)return {ok:false,code:'TRACE_INVALID',entry:checked.entry,errors:checked.errors,message:checked.entry===null?checked.errors[0]:`the trace fails at ledger entry ${checked.entry}: ${checked.errors[0]}`};
    const key=trace.replayKey;
    const started=startRun({doc:o.doc,packs:o.packs,inputs:key.inputs,seed:key.seed,budget:trace.budget,tickMs:key.tickMs});
    if(!started.ok)return started;
    const run=started.run,mine=run.ledger[0].body.replayKey;
    const fields=REPLAY_KEY_FIELDS.filter(field=>(mine[field]!==undefined||key[field]!==undefined)&&!same(mine[field],key[field]));
    if(fields.length)return {ok:false,code:'REPLAY_KEY_MISMATCH',fields,message:`the replay key differs in ${fields.join(', ')}`};
    run.replayDraws=trace.ledger.filter(e=>e.kind==='draw').map(e=>({seq:e.seq,body:e.body}));
    // Exactly the ticks up to `through`.
    while(trace.through!==null){
      const next=nextTick(run);
      if(next===null||next>trace.through)break;
      const r=step(run);
      if(!r.ok){if(r.code==='BUDGET_SPENT')return {ok:false,code:'REPLAY_DIVERGED',tick:r.tick,message:`the trace processed tick ${r.tick}, which the recomputed run cannot within the budget ${trace.budget}`};return r}
    }
    run.replayDraws=null;
    if(run.tick!==trace.through)return {ok:false,code:'REPLAY_DIVERGED',tick:run.tick,message:`the recomputed run ends at tick ${run.tick}, the trace at ${trace.through}`};
    const n=Math.max(run.ledger.length,trace.ledger.length);
    for(let i=0;i<n;i++)if(Canonical.canonicalize(run.ledger[i]??null)!==Canonical.canonicalize(trace.ledger[i]??null))return {ok:false,code:'REPLAY_DIVERGED',entry:i,message:`ledger entry ${i} differs from the recomputed run`};
    if(trace.records===undefined)return {ok:true,records:run.records,run};
    const m=Math.max(run.records.length,trace.records.length);
    for(let i=0;i<m;i++)if(Canonical.canonicalize(run.records[i]??null)!==Canonical.canonicalize(trace.records[i]??null))return {ok:false,code:'REPLAY_DIVERGED',record:i,message:`record ${i} differs from the recomputed run`};
    return {ok:true,records:run.records,run};
  }

  // --- Slice 1c (STATE-SPACE.md "Stepping and settling", "Surfaces").
  // The state that determines the future, hashed after a processed tick: committed signal state (a
  // key absent is false, so only the true keys are listed), the queue buffers and the pending
  // schedule, every time taken relative to that tick. Provenance (record ids) names the past and
  // changes no value, so it is left out; with it no state could ever repeat.
  // Every device.state is part of it, as canonical text without the record ids it keeps (`dev`, '{}' when there is none).
  function stateHash(t,signal,queues,pending,dev='{}'){
    const q=queues.map(([k,next,items])=>[k,next-t,items.map(x=>[x.value,x.wire,x.phase])]);
    const p=pending.map(x=>{const {from,inputs,at,...rest}=x;rest.at=at-t;return Canonical.canonicalize(rest)}).sort();
    return Canonical.sha256Hex(Canonical.canonicalize({signal,queues:q,pending:p,...(dev!=='{}'?{device:dev}:{})}));
  }
  const trueKeys=signal=>Object.keys(signal).filter(k=>signal[k]===true).sort();
  const deviceText=run=>Canonical.canonicalize(stripFrom(isObject(run.deviceState)?run.deviceState:{}));
  function futureHash(run){return stateHash(run.tick,trueKeys(run.signal),Object.keys(run.queues).sort().map(k=>[k,run.queues[k].next,queueItems(run.queues[k])]),run.pending,deviceText(run))}
  // A cheap 32-bit code (FNV-1a) of a string, and of a pending or queue item's future-determining
  // part, cached per item (items are never changed once scheduled). Codes only decide when the full
  // hash is worth computing; a collision costs a full hash, never a wrong result.
  function code32(text){let h=0x811c9dc5;for(let i=0;i<text.length;i++){h^=text.charCodeAt(i);h=Math.imul(h,0x01000193)}return h|0}
  const ITEM_CODE=new WeakMap();
  function pendingCode(x){let c=ITEM_CODE.get(x);if(c===undefined){const {from,inputs,at,...rest}=x;c=code32(Canonical.canonicalize(rest));ITEM_CODE.set(x,c)}return c}
  function queueCode(x){let c=ITEM_CODE.get(x);if(c===undefined){c=code32(Canonical.canonicalize([x.value,x.wire,x.phase]));ITEM_CODE.set(x,c)}return c}
  // settle(run): steps until quiet ({kind: 'quiet'}), a repeated future-state hash ({kind:
  // 'oscillating', period, subjects}: period the ticks between the repeat and its first occurrence,
  // subjects the sorted `entity.port.channel` whose committed value changed within that period), or
  // a step refused with BUDGET_SPENT ({kind: 'budget', left}). Any other refusal is returned as is.
  // Linear: each processed tick costs a summary (true-key count and code sum, each queue's length,
  // relative next and positional code sum, the pending count and code sums with relative times),
  // kept incrementally. Equal states have equal summaries, so the full hash is computed only when a
  // summary repeats, for the current tick and for each earlier tick with that summary, whose state
  // is rebuilt from what was kept: its pending list (never changed once replaced), each queue as a
  // span of an append-only log of its items, and the signal by undoing the later flips.
  function settle(run){
    if(!isObject(run)||run.runtimeVersion!==RUNTIME_VERSION)return {ok:false,code:'RUN_INVALID',message:`not a ${RUNTIME_VERSION} run`};
    const I=Math.imul,changes=[],shadow={},keyCodes=new Map(),logs=new Map(),seen=new Map();
    let sigCount=0,sigSum=0;
    const keyCode=k=>{let c=keyCodes.get(k);if(c===undefined){c=code32(k);keyCodes.set(k,c)}return c};
    for(const key of Object.keys(run.signal))if(run.signal[key]===true){shadow[key]=true;sigCount++;sigSum=(sigSum+keyCode(key))|0}
    // Each queue's items as an append-only log with prefix sums of code and code x position.
    const logOf=key=>{let l=logs.get(key);if(!l){l={items:[],sum:[0],pos:[0],head:0};logs.set(key,l)}return l};
    const append=(l,x)=>{const n=l.items.length,c=queueCode(x);l.items.push(x);l.sum.push((l.sum[n]+c)|0);l.pos.push((l.pos[n]+I(c,n))|0)};
    const syncQueues=()=>{
      for(const [key,l] of logs)if(!run.queues[key])l.head=l.items.length;
      for(const key of Object.keys(run.queues)){
        // Read the engine's own `items`/`head` by index, not `queueItems`: this runs every tick, and
        // materializing a queue's live items here would copy them just as step() must not.
        const q=run.queues[key],items=q.items,qh=q.head,liveLen=items.length-qh,at=i=>items[qh+i];
        const l=logOf(key),had=l.items.length-l.head;
        let shift=had>0&&at(0)!==l.items[l.head]?1:0,add=liveLen-(had-shift);
        const fits=add>=0&&(had-shift===0||(at(0)===l.items[l.head+shift]&&at(had-shift-1)===l.items[l.items.length-1]));
        if(!fits){l.head=l.items.length;shift=0;add=liveLen}
        l.head+=shift;
        for(let i=liveLen-add;i<liveLen;i++)append(l,at(i));
      }
    };
    const summary=t=>{
      const parts=[sigCount,sigSum];
      for(const key of Object.keys(run.queues).sort()){
        const l=logs.get(key),h=l.head,n=l.items.length,sum=(l.sum[n]-l.sum[h])|0;
        parts.push(key,n-h,run.queues[key].next-t,sum,(l.pos[n]-l.pos[h]-I(h,sum))|0);
      }
      let pc=0,pa=0,pm=0;
      for(const x of run.pending){const c=pendingCode(x);pc=(pc+c)|0;pa=(pa+x.at-t)|0;pm=(pm+I(c,x.at-t))|0}
      parts.push(run.pending.length,pc,pa,pm,dev);
      return parts.join('\u0000');
    };
    // The flow cards' state, as text, once per processed tick ('{}' with none, so documents without flow cards pay nothing more).
    let dev='{}';
    const snapshot=t=>({tick:t,hash:null,pending:run.pending,dev,queues:Object.keys(run.queues).sort().map(k=>{const l=logs.get(k);return [k,run.queues[k].next,l.head,l.items.length]}),flips:changes.length});
    // The signal's true keys at an earlier snapshot: the current ones with every later flip undone.
    const hashOf=entry=>{
      if(entry.hash!==null)return entry.hash;
      const set=new Set(trueKeys(run.signal));
      for(let i=changes.length-1;i>=entry.flips;i--)for(const k of changes[i][2])if(set.has(k))set.delete(k);else set.add(k);
      entry.hash=stateHash(entry.tick,[...set].sort(),entry.queues.map(([k,next,h,n])=>[k,next,logs.get(k).items.slice(h,n)]),entry.pending,entry.dev);
      entry.pending=entry.queues=null;
      return entry.hash;
    };
    const visit=t=>{
      dev=isObject(run.deviceState)&&Object.keys(run.deviceState).length?deviceText(run):'{}';
      const key=summary(t),list=seen.get(key),entry=snapshot(t);
      if(list){
        entry.hash=futureHash(run);
        for(const earlier of list)if(hashOf(earlier)===entry.hash)return earlier.tick;
        list.push(entry);
      }else seen.set(key,[entry]);
      return null;
    };
    if(run.tick!==null){syncQueues();visit(run.tick)}
    for(;;){
      const r=step(run);
      if(!r.ok)return r.code==='BUDGET_SPENT'?{kind:'budget',left:r.left}:r;
      if(r.tick===null)return {kind:'quiet'};
      const changed=new Set(),flipped=[];
      for(const record of r.records){
        if(record.provenance.rule==='overridden')continue;
        const s=record.subject,key=portKey(s.entity,s.point,s.channel),now=run.signal[key]===true;
        if(now!==(shadow[key]===true)){
          changed.add(`${s.entity}.${s.point}.${s.channel}`);flipped.push(key);
          if(now){shadow[key]=true;sigCount++;sigSum=(sigSum+keyCode(key))|0}else{delete shadow[key];sigCount--;sigSum=(sigSum-keyCode(key))|0}
        }
      }
      changes.push([r.tick,changed,flipped]);
      syncQueues();
      const first=visit(r.tick);
      if(first!==null){
        const subjects=new Set();
        for(const [tick,set] of changes)if(tick>first&&tick<=r.tick)for(const x of set)subjects.add(x);
        return {kind:'oscillating',period:r.tick-first,subjects:[...subjects].sort()};
      }
    }
  }
  // query(run, {entity, point?, channel?, observable}): every record of the run whose subject
  // matches (an omitted point or channel matches any) and whose observable is the one asked, in
  // record order, as copies. Passive: it reads the run and writes nothing.
  const QUERY_KEYS=['entity','point','channel','observable'];
  function query(run,subject){
    if(!isObject(run)||run.runtimeVersion!==RUNTIME_VERSION)return {ok:false,code:'RUN_INVALID',message:`not a ${RUNTIME_VERSION} run`};
    const bad=message=>({ok:false,code:'QUERY_INVALID',message});
    if(!isObject(subject))return bad('the query must be an object {entity, point?, channel?, observable}');
    const extra=Object.keys(subject).filter(k=>!QUERY_KEYS.includes(k));
    if(extra.length)return bad(`unknown key ${extra[0]}`);
    for(const key of ['entity','observable'])if(!nonEmpty(subject[key]))return bad(`${key} must be a non-empty string`);
    for(const key of ['point','channel'])if(subject[key]!==undefined&&!nonEmpty(subject[key]))return bad(`${key} must be a non-empty string when given`);
    const out=[];
    for(const record of run.records){
      const s=record.subject;
      if(s.entity===subject.entity&&(subject.point===undefined||s.point===subject.point)&&(subject.channel===undefined||s.channel===subject.channel)&&record.observable===subject.observable)out.push(copy(record));
    }
    return out;
  }
  // The one receipt for run operations: {schema, operation, runId, handle, ok, tickBefore, tickAfter,
  // head, result, error}. `runId` is the content-derived run id and `handle` the registry's address
  // for the run (null outside a registry, and for a replay); `head` is the ledger head after the
  // operation; `error` is {code, message, details?} on a refusal (`result` null), `details` holding
  // what the refusal names besides its code and message; runId, ticks and head are null when there is
  // no run. `tickBefore` defaults to the run's tick (an operation that processes no tick).
  const RUN_RECEIPT_FORMAT='soveraeign.schematic/run-receipt@0.1';
  const RUN_OPERATIONS=['schematic.run.start','schematic.run.step','schematic.run.settle','schematic.run.trace','schematic.state.query','schematic.run.replay'];
  function runReceipt(operation,run,result,tickBefore,handle){
    if(!RUN_OPERATIONS.includes(operation))throw new Error(`RUN_OPERATION_UNKNOWN: ${operation}`);
    const has=isObject(run)&&run.runtimeVersion===RUNTIME_VERSION&&Array.isArray(run.ledger)&&run.ledger.length>0;
    const refused=isObject(result)&&result.ok===false,tickAfter=has?run.tick:null;
    let value=null,error=null;
    if(!refused){
      if(operation==='schematic.run.start')value=has?copy(run.ledger[0].body):null;
      else if(isObject(result)){value={};for(const k of Object.keys(result))if(k!=='ok'&&k!=='run'&&result[k]!==undefined)value[k]=copy(result[k])}
      else value=result===undefined?null:copy(result);
    }else{
      error={code:String(result.code),message:String(result.message??result.code)};
      const details={};for(const k of Object.keys(result))if(!['ok','code','message'].includes(k)&&result[k]!==undefined)details[k]=copy(result[k]);
      if(Object.keys(details).length)error.details=details;
    }
    return {schema:RUN_RECEIPT_FORMAT,operation,runId:has?run.id:null,handle:has&&typeof handle==='string'?handle:null,ok:!refused,tickBefore:tickBefore===undefined?tickAfter:tickBefore,tickAfter,
      head:has?run.ledger[run.ledger.length-1].hash:null,result:value,error};
  }
  // A surface's run registry, kept beside its document and never in it. Each successful start is
  // registered under a new handle, `<runId>.<n>` with n counting starts from 1, so two starts with
  // the same replay key are two runs; step, settle, trace and query address a run by its handle
  // (RUN_NOT_FOUND otherwise), and a replay is not registered. Every run starts from the function
  // `document`, the surface's current document; packs are the raw pack JSON the surface was given
  // (one that does not load refuses every start and replay with PACK_INVALID; an empty list refuses a
  // document that references a definition, saying so). A surface start is capped at BUDGET_LIMIT
  // (the engine's startRun is not). Every method returns a run receipt, and none of them touches the
  // document, its revision, history or recovery.
  const START_KEYS=['inputs','seed','budget','tickMs'],BUDGET_LIMIT=1000000;
  function createRunRegistry(options){
    const o=isObject(options)?options:{};
    const loaded=Array.isArray(o.packs)?o.packs.map(p=>loadPack(p)):null;
    const packs=loaded?loaded.filter(x=>x.ok).map(x=>x.pack):[];
    const packErrors=loaded?loaded.flatMap(x=>x.errors):[refusal('PACK_INVALID','packs','the surface was given no pack list')];
    const packRefusal=packErrors.length?{ok:false,code:'PACK_INVALID',message:`the surface's packs do not load: ${packErrors.map(e=>`${e.subject}: ${e.message}`).join('; ')}`,refusals:packErrors}:null;
    const current=typeof o.document==='function'?o.document:()=>null;
    // With no packs at all, a document that references a definition cannot run: say so plainly.
    const noPacks=doc=>{
      if(packs.length||!isObject(doc)||!Array.isArray(doc.components))return null;
      const definitions=[...new Set(doc.components.map(c=>c?.config?.definition).filter(ref=>ref!==undefined&&ref!==null))].sort();
      return definitions.length?{ok:false,code:'PACK_INVALID',message:'this page carries no packs',definitions}:null;
    };
    const runs=new Map();let count=0;
    const found=(operation,handle,act)=>{
      const run=typeof handle==='string'?runs.get(handle):undefined;
      return run?act(run,handle):runReceipt(operation,null,{ok:false,code:'RUN_NOT_FOUND',message:`no run with handle ${JSON.stringify(handle===undefined?null:handle)} on this surface`});
    };
    return {
      start(args){
        const op='schematic.run.start';
        if(packRefusal)return runReceipt(op,null,packRefusal);
        const a=args===undefined?{}:args;
        if(!isObject(a))return runReceipt(op,null,inputRefusal('start takes an object {inputs?, seed?, budget?}'));
        const extra=Object.keys(a).filter(k=>!START_KEYS.includes(k));
        if(extra.length)return runReceipt(op,null,inputRefusal(`unknown key ${extra[0]}`));
        if(typeof a.budget==='number'&&a.budget>BUDGET_LIMIT)return runReceipt(op,null,inputRefusal(`budget ${a.budget} is over the surface limit ${BUDGET_LIMIT}`));
        const doc=current(),empty=noPacks(doc);
        if(empty)return runReceipt(op,null,empty);
        const started=startRun({doc,packs,inputs:a.inputs,seed:a.seed,budget:a.budget,tickMs:a.tickMs});
        if(!started.ok)return runReceipt(op,null,started);
        const handle=`${started.run.id}.${++count}`;
        runs.set(handle,started.run);
        return runReceipt(op,started.run,started,undefined,handle);
      },
      step:handle=>found('schematic.run.step',handle,(run,h)=>{const before=run.tick;return runReceipt('schematic.run.step',run,step(run),before,h)}),
      settle:handle=>found('schematic.run.settle',handle,(run,h)=>{const before=run.tick;return runReceipt('schematic.run.settle',run,settle(run),before,h)}),
      trace:handle=>found('schematic.run.trace',handle,(run,h)=>runReceipt('schematic.run.trace',run,traceOf(run),undefined,h)),
      query:(handle,subject)=>found('schematic.state.query',handle,(run,h)=>runReceipt('schematic.state.query',run,query(run,subject),undefined,h)),
      replay(trace){
        const op='schematic.run.replay';
        if(packRefusal)return runReceipt(op,null,packRefusal);
        const doc=current(),empty=noPacks(doc);
        if(empty)return runReceipt(op,null,empty);
        const r=replay({trace,doc,packs});
        return runReceipt(op,r.ok?r.run:null,r,null);
      }
    };
  }

  return {RECORD_FORMAT,PACK_FORMAT,RUNTIME_VERSION,TRACE_FORMAT,RUN_RECEIPT_FORMAT,RUN_OPERATIONS,BUDGET_LIMIT,validateRecord,patterns,flowPatterns,flowBindingOf,pattern,checkDefinition,loadPack,resolveDefinition,contractOf,bindDefinition,applyBind,checkDocument,startRun,step,settle,query,runReceipt,createRunRegistry,traceOf,replay,validateTrace,queueItems};
});
