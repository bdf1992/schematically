'use strict';
// State space concern (STATE-SPACE.md). Slice 1a, the contract layer: the state record
// envelope, the closed pattern registry (truth_table@1, merge@1), definitions and the minimal
// pack envelope, contracts generated from pattern + parameters, ports generated from a bound
// definition, and the load checks. Slice 1b, the first runs: the hash-chained ledger, the
// replay key, two-phase ticks with merges, the trace and replay. No settle, no surfaces.
// Pure: no DOM, no pack data (packs are passed in), validation hand-written.
(function(root,factory){
  let Canonical=root.SovSchematicCanonical;
  if(!Canonical&&typeof module!=='undefined'&&module.exports)Canonical=require('./03-canonical.js');
  let Data=root.SovSchematicData;
  if(!Data&&typeof module!=='undefined'&&module.exports)Data=require('./05-data-core.js');
  const api=factory(Canonical,Data);
  root.SovSchematicStateSpace=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(Canonical,Data){
  if(!Canonical)throw new Error('SovSchematicCanonical core is required');
  if(!Data)throw new Error('SovSchematicData core is required');
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
  const FORMS=['binary','continuous','categorical'];
  const TIME_MODES=['observed','predicted'];
  const PERTURBATIONS=['none','disturbed','created'];
  const RECORD_KEYS=['format','id','subject','vantage','reference','observable','kind','form','value','time','certainty','observer','provenance','perturbation'];
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
  const PATTERNS=[truthTable,merge].map(p=>Object.freeze(p));
  const refOf=p=>`${p.id}@${p.version}`;
  function patterns(){return PATTERNS.slice()}
  function pattern(ref){return PATTERNS.find(p=>refOf(p)===ref)||null}

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
    for(const key of Object.keys(json))if(!['format','id','version','definitions'].includes(key))errors.push(refusal('PACK_INVALID',subject,`unknown key ${key}`));
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

  // --- Binding: an `update` operation for the data core; nothing is applied here.
  // A contract with no inputs and no outputs (merge@1's, for one) generates no ports: nothing binds to it.
  function bindable(contract){return contractPorts(contract).length>0}
  function bindDefinition(doc,componentId,ref,packs){
    const definition=resolveDefinition(ref,packs);
    if(!definition)return {ok:false,code:'DEFINITION_UNRESOLVED',message:`definition ${ref} is not in the packs`};
    const component=(doc?.components||[]).find(c=>c?.id===componentId);
    if(!component)return {ok:false,code:'COMPONENT_NOT_FOUND',message:`component ${componentId} not found`};
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

  // --- Load checks (STATE-SPACE.md "Invariants", at load). Never throws, never mutates doc.
  const EMITS=['out','duplex'],RECEIVES=['in','duplex','control','trigger'];
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
        if(config.delay!==undefined&&!(Number.isInteger(config.delay)&&config.delay>=1))refuse('PATH_DELAY_INVALID',subject,`config.delay must be an integer >= 1, not ${JSON.stringify(config.delay)}`);
        const aPoint=endPoint(wire,'a'),bPoint=endPoint(wire,'b');
        if(!aPoint||!bPoint)continue; // a free end binds nothing
        const aSpec=specOf(wire.a,aPoint),bSpec=specOf(wire.b,bPoint);
        if(!aSpec||!bSpec)continue; // an unreachable end is the data core's validation
        const flow=spec=>spec.flow||spec.defaultFlow||'duplex';
        const direction=['none','forward','reverse','duplex'].includes(config.direction)?config.direction:wire.duplex?'duplex':'forward';
        const aFlow=flow(aSpec),bFlow=flow(bSpec);
        // Refused only when none of the Wire's declared directions is admitted by both flows:
        // a duplex Wire from an out port to an in port carries forward only.
        const carries={forward:EMITS.includes(aFlow)&&RECEIVES.includes(bFlow),reverse:EMITS.includes(bFlow)&&RECEIVES.includes(aFlow)};
        const declared=direction==='none'?[]:direction==='duplex'?['forward','reverse']:[direction];
        const admitted=!declared.length||declared.some(x=>carries[x]);
        if(!admitted)refuse('PATH_DIRECTION_FLOW',subject,`direction ${direction} is not admitted by ports ${wire.a}.${aSpec.id} (${aFlow}) and ${wire.b}.${bSpec.id} (${bFlow})`);
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
  const REPLAY_KEY_FIELDS=['documentId','documentHash','definitions','runtimeVersion','traceFormat','inputs','seed'];
  const INPUT_KEYS=['entity','point','channel','value','at'];
  const DEFAULT_MERGE=Object.freeze({combine:'last',order:Object.freeze({kind:'stochastic'})});
  const cmp=(x,y)=>x<y?-1:x>y?1:0;
  const cmpList=(x,y)=>{for(let i=0;i<Math.max(x.length,y.length);i++){const c=cmp(x[i],y[i]);if(c)return c}return 0};
  const portKey=(entity,point,channel)=>JSON.stringify([entity,point,channel]);
  const TMP='\u0000tmp:';
  const walked=(run,list)=>run.walk==='reverse'?list.slice().reverse():list;
  function ledgerHash(seq,kind,body,prev){return Canonical.sha256Hex(Canonical.canonicalize({seq,kind,body,prev}))}
  function appendEntry(run,kind,body){
    const seq=run.ledger.length,prev=seq?run.ledger[seq-1].hash:ZERO_HASH;
    run.ledger.push({seq,kind,body,prev,hash:ledgerHash(seq,kind,body,prev)});
  }
  const specChannels=spec=>(Array.isArray(spec?.channels)&&spec.channels.length?spec.channels:[{id:'main'}]).map(c=>c.id);
  const specFlow=spec=>spec.flow||spec.defaultFlow||'duplex';
  // What the run reads of the document, resolved once at start: each Wire's two ports, delay,
  // the directions it carries and the channels it shares; each Component's role; each merge.
  function topology(d,definitions){
    const components={},merges={},wires=[];
    const specOf=(component,pointId)=>{try{return Data.canonicalAttachmentPointDescriptors(component).find(s=>s&&(s.id===pointId||s.compatId===pointId))||null}catch(_){return null}};
    const byId=new Map(d.components.map(c=>[c.id,c]));
    for(const component of d.components){
      const config=isObject(component.config)?component.config:{};
      const ref=config.definition!==undefined&&config.definition!==null?config.definition:null;
      if(ref){const def=definitions[ref];components[component.id]={role:'device',definition:ref,inputs:def.parameters.inputs.slice(),outputs:def.parameters.outputs.slice()}}
      else components[component.id]={role:component.symbolId==='point'?'point':'absorb'};
      // A channel merge is read where checkDocument reads it: the stored port list, by port id.
      for(const port of Array.isArray(config.attachmentPoints)?config.attachmentPoints:[]){
        for(const channel of Array.isArray(port?.channels)?port.channels:[]){
          if(isObject(channel)&&channel.merge!==undefined)merges[portKey(component.id,port.id,channel.id)]=clone(channel.merge);
        }
      }
    }
    for(const wire of d.wires){
      if(!Data.wireEndBound(wire,'a')||!Data.wireEndBound(wire,'b'))continue;
      const ends={};
      for(const end of ['a','b']){
        const component=byId.get(wire[end]),spec=component?specOf(component,wire[end+'Attachment']?.pointId||wire[end+'Side']):null;
        if(!spec)break;
        ends[end]={entity:component.id,point:spec.id,flow:specFlow(spec),channels:specChannels(spec)};
      }
      if(!ends.a||!ends.b)continue;
      const config=isObject(wire.config)?wire.config:{};
      const direction=['none','forward','reverse','duplex'].includes(config.direction)?config.direction:wire.duplex?'duplex':'forward';
      const declared=direction==='none'?[]:direction==='duplex'?['forward','reverse']:[direction];
      const theirs=new Set(ends.b.channels);
      wires.push({id:wire.id,a:{entity:ends.a.entity,point:ends.a.point},b:{entity:ends.b.entity,point:ends.b.point},delay:config.delay===undefined?1:config.delay,
        forward:declared.includes('forward')&&EMITS.includes(ends.a.flow)&&RECEIVES.includes(ends.b.flow),
        reverse:declared.includes('reverse')&&EMITS.includes(ends.b.flow)&&RECEIVES.includes(ends.a.flow),
        channels:ends.a.channels.filter(c=>theirs.has(c))});
    }
    wires.sort((x,y)=>cmp(x.id,y.id));
    return {components,merges,wires};
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
          if(channel?.merge?.combine==='sum')return {ok:false,code:'MERGE_FORM',subject:`component:${component.id}:${port.id}:${channel.id}`,message:`combine sum is not defined on binary channels (${component.id}.${port.id}.${channel.id}); slice 1b runs binary channels only`};
        }
      }
    }
    const seed=o.seed===undefined?'0':o.seed;
    if(typeof seed!=='string')return inputRefusal('seed must be a string');
    const budget=o.budget===undefined?10000:o.budget;
    if(!natural(budget))return inputRefusal('budget must be an integer >= 0');
    if(o.walk!==undefined&&!['forward','reverse'].includes(o.walk))return inputRefusal('walk must be forward or reverse');
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
      if(!specChannels(spec).includes(channel))return inputRefusal(`input ${i}: port ${raw.entity}.${spec.id} has no channel ${JSON.stringify(channel)}`);
      if(typeof raw.value!=='boolean')return inputRefusal(`input ${i}: value must be a boolean (binary channels only)`);
      if(!natural(raw.at))return inputRefusal(`input ${i}: at must be an integer >= 0`);
      const input={entity:component.id,point:spec.id,channel,value:raw.value,at:raw.at};
      const key=JSON.stringify([input.at,input.entity,input.point,input.channel]);
      if(seen.has(key))return inputRefusal(`input ${i}: a second input at (${input.entity}, ${input.point}, ${input.channel}, ${input.at})`);
      seen.add(key);inputs.push(input);
    }
    inputs.sort((x,y)=>cmpList([x.at,x.entity,x.point,x.channel],[y.at,y.entity,y.point,y.channel]));
    const refs=[...new Set(d.components.map(c=>c.config?.definition).filter(ref=>ref!==undefined&&ref!==null))].sort();
    const definitions={};
    for(const ref of refs){const def=resolveDefinition(ref,o.packs);if(def.delay===undefined)def.delay=0;definitions[ref]=def}
    const replayKey={documentId:d.id,documentHash:Data.documentHash(d),definitions:refs,runtimeVersion:RUNTIME_VERSION,traceFormat:TRACE_FORMAT,inputs,seed};
    const shape=topology(d,definitions);
    const run={
      id:Canonical.sha256Hex(Canonical.canonicalize(replayKey)).slice(0,12),
      runtimeVersion:RUNTIME_VERSION,doc:d,definitions,components:shape.components,merges:shape.merges,wires:shape.wires,
      seed,budget,spent:0,tick:null,walk:o.walk||'forward',
      signal:{},lastRecord:{},queues:{},sequence:0,ledger:[],records:[],replayDraws:null,
      pending:inputs.map(x=>({kind:'input',...x}))
    };
    appendEntry(run,'start',clone(replayKey));
    for(const input of inputs)appendEntry(run,'input',clone(input));
    return {ok:true,run};
  }
  function nextTick(run){
    let t=null;
    for(const item of run.pending)if(t===null||item.at<t)t=item.at;
    for(const q of Object.values(run.queues))if(q.items.length&&(t===null||q.next<t))t=q.next;
    return t;
  }
  function queuedCount(run){return run.pending.length+Object.values(run.queues).reduce((n,q)=>n+q.items.length,0)}
  function makeRecord(run,ctx,{entity,point,channel,kind,value,observer,rule,inputs,phase,rank=0}){
    const id=`${TMP}${ctx.tmp++}`;
    ctx.records.push({phase,rank,record:{format:RECORD_FORMAT,id,subject:{entity,point,channel,run:run.id},vantage:'space',observable:'logic.level',kind,form:'binary',value,time:{logical:ctx.t,sequence:0,mode:'observed'},certainty:{kind:'exact'},observer,provenance:{rule,inputs:inputs.slice()},perturbation:'none'}});
    return id;
  }
  // Emission: one arrival per bound Wire, per direction it carries out of this port, per shared
  // channel, at t + path delay; never back onto a Wire in `exclude`.
  function emit(run,ctx,entity,point,channel,value,exclude,from,phase){
    for(const wire of walked(run,run.wires)){
      if(exclude.includes(wire.id)||!wire.channels.includes(channel))continue;
      for(const [end,other,dir] of [['a','b','forward'],['b','a','reverse']]){
        if(!wire[dir]||wire[end].entity!==entity||wire[end].point!==point)continue;
        run.pending.push({kind:'arrival',at:ctx.t+wire.delay,entity:wire[other].entity,point:wire[other].point,channel,value,wire:wire.id,phase,from});
      }
    }
  }
  // Merge order: the declared Paths first (in their declared order), the rest by a seeded draw
  // keyed by (seed, tick, entity, port, channel), recorded in the ledger (and, in replay, read from it).
  function mergeOrder(run,ctx,g,merge){
    const tag=a=>g.arrivals.filter(x=>x.wire===a.wire).length>1?`${a.wire}#${a.phase}`:a.wire;
    const items=g.arrivals.map(a=>({a,id:tag(a)})).sort((x,y)=>cmp(x.id,y.id));
    const declared=merge.order?.kind==='declared'?merge.order.paths:[];
    const first=[];for(const path of declared)for(const item of items)if(item.a.wire===path)first.push(item);
    const rest=items.filter(item=>!declared.includes(item.a.wire));
    let restOrder=rest.map(item=>item.id);
    if(rest.length>1){
      const paths=restOrder.slice(),drawn=Canonical.drawOrder(run.seed,['merge',ctx.t,g.entity,g.point,g.channel],paths);
      if(run.replayDraws){
        const recorded=run.replayDraws.find(e=>e.body.tick===ctx.t&&e.body.entity===g.entity&&e.body.point===g.point&&e.body.channel===g.channel);
        if(!recorded||!same(recorded.body.paths,paths)||!same(recorded.body.order,drawn)){
          ctx.diverged={code:'REPLAY_DIVERGED',entry:recorded?recorded.seq:null,message:recorded?`the draw recorded at ledger entry ${recorded.seq} (${g.entity}.${g.point}.${g.channel}, tick ${ctx.t}) does not re-derive from the seed: recorded ${JSON.stringify(recorded.body.order)}, derived ${JSON.stringify(drawn)}`:`no draw is recorded for ${g.entity}.${g.point}.${g.channel} at tick ${ctx.t}`};
          return null;
        }
        restOrder=recorded.body.order.slice();
      }else restOrder=drawn;
      ctx.draws.push({tick:ctx.t,entity:g.entity,point:g.point,channel:g.channel,paths,order:restOrder.slice()});
    }
    return [...first,...restOrder.map(id=>rest.find(item=>item.id===id))].map(item=>item.a);
  }
  // Update phase for one (entity, port, channel): input, else a device's delayed output, else the
  // merged arrivals (or a queue's head). What loses is recorded with rule `overridden`.
  function updatePort(run,ctx,g){
    const key=portKey(g.entity,g.point,g.channel),old=run.signal[key]===true,role=run.components[g.entity]?.role;
    const merge=run.merges[key]||DEFAULT_MERGE,queue=merge.combine==='queue'?(run.queues[key]||(run.queues[key]={next:ctx.t+1,items:[]})):null;
    const base={entity:g.entity,point:g.point,channel:g.channel,phase:0};
    let win=null;
    if(g.input)win={value:g.input.value,kind:'registered',observer:'input',rule:'input',inputs:[],always:true,exclude:[]};
    else if(g.output)win={value:g.output.value,kind:'derived',observer:`rule:${g.output.rule}`,rule:g.output.rule,inputs:g.output.inputs,emits:true,exclude:[]};
    if(win){
      for(const a of g.arrivals)makeRecord(run,ctx,{...base,kind:'derived',value:a.value,observer:`path:${a.wire}`,rule:'overridden',inputs:[a.from],rank:a.phase});
    }else{
      const arrived=g.arrivals.map(a=>a.wire);
      const orderFree=['or','and','min','max'].includes(merge.combine);
      if(orderFree&&g.arrivals.length){
        const sorted=g.arrivals.slice().sort((x,y)=>cmpList([x.wire,x.phase],[y.wire,y.phase]));
        const value=merge.combine==='or'||merge.combine==='max'?sorted.some(a=>a.value):sorted.every(a=>a.value);
        win=sorted.length===1?{value,observer:`path:${sorted[0].wire}`,rule:'path',inputs:[sorted[0].from]}:{value,observer:'engine:merge@1',rule:'merge@1',inputs:sorted.map(a=>a.from)};
      }else if(queue){
        if(g.arrivals.length){const ordered=g.arrivals.length>1?mergeOrder(run,ctx,g,merge):g.arrivals;if(!ordered)return;queue.items.push(...ordered.map(a=>({value:a.value,wire:a.wire,phase:a.phase,from:a.from})))}
        if(queue.items.length){const head=queue.items.shift();win={value:head.value,observer:'engine:merge@1',rule:'merge@1',inputs:[head.from]};if(!arrived.includes(head.wire))arrived.push(head.wire)}
      }else if(g.arrivals.length===1){
        const a=g.arrivals[0];win={value:a.value,observer:`path:${a.wire}`,rule:'path',inputs:[a.from]};
      }else if(g.arrivals.length){
        const ordered=mergeOrder(run,ctx,g,merge);if(!ordered)return;
        const pick=merge.combine==='first'?ordered[0]:ordered[ordered.length-1];
        win={value:pick.value,observer:'engine:merge@1',rule:'merge@1',inputs:ordered.map(a=>a.from)};
      }
      if(!win)return;
      win.kind='derived';win.exclude=arrived;win.emits=role==='point';
    }
    if(queue)queue.next=ctx.t+1;
    const id=makeRecord(run,ctx,{...base,kind:win.kind,value:win.value,observer:win.observer,rule:win.rule,inputs:win.inputs});
    run.signal[key]=win.value;run.lastRecord[key]=id;
    const changed=win.value!==old;
    if(changed)ctx.changed.add(key);
    if(win.always||(changed&&win.emits))emit(run,ctx,g.entity,g.point,g.channel,win.value,win.exclude,id,0);
  }
  // Evaluate phase: a device whose input port changed reads committed state only.
  function evaluateDevice(run,ctx,entity,committed){
    const component=run.components[entity],definition=run.definitions[component.definition],p=pattern(definition.pattern);
    const values={},inputs=[];
    for(const name of component.inputs){const key=portKey(entity,name,'main');values[name]=committed[key]===true;if(run.lastRecord[key])inputs.push(run.lastRecord[key])}
    const out=p.evaluate(definition.parameters,values),delay=definition.delay||0;
    for(const name of component.outputs){
      const key=portKey(entity,name,'main'),value=out[name];
      if(delay===0){
        if(value===(run.signal[key]===true))continue;
        ctx.cost++;
        const id=makeRecord(run,ctx,{entity,point:name,channel:'main',kind:'derived',value,observer:`rule:${component.definition}`,rule:component.definition,inputs,phase:1});
        run.signal[key]=value;run.lastRecord[key]=id;
        emit(run,ctx,entity,name,'main',value,[],id,1);
      }else{
        // Transport delay: schedule every change from the latest value already on its way.
        let latest=run.signal[key]===true,at=-1;
        for(const item of run.pending)if(item.kind==='output'&&item.entity===entity&&item.point===name&&item.channel==='main'&&item.at>at){at=item.at;latest=item.value}
        if(value!==latest)run.pending.push({kind:'output',at:ctx.t+delay,entity,point:name,channel:'main',value,rule:component.definition,inputs:inputs.slice()});
      }
    }
  }
  function resolveTmp(value,map){
    if(typeof value==='string')return value.startsWith(TMP)?map.get(value):value;
    if(Array.isArray(value))return value.map(x=>resolveTmp(x,map));
    if(isObject(value)){const out={};for(const [k,v] of Object.entries(value))out[k]=resolveTmp(v,map);return out}
    return value;
  }
  function processTick(run,t){
    const ctx={t,cost:0,tmp:0,records:[],draws:[],changed:new Set(),diverged:null};
    const due=run.pending.filter(x=>x.at===t);run.pending=run.pending.filter(x=>x.at!==t);
    const groups=new Map();
    const group=(entity,point,channel)=>{const key=portKey(entity,point,channel);if(!groups.has(key))groups.set(key,{entity,point,channel,input:null,output:null,arrivals:[]});return groups.get(key)};
    for(const item of due){
      const g=group(item.entity,item.point,item.channel);ctx.cost++;
      if(item.kind==='input')g.input=item;else if(item.kind==='output')g.output=item;else g.arrivals.push(item);
    }
    for(const [key,q] of Object.entries(run.queues))if(q.items.length&&q.next===t){const [entity,point,channel]=JSON.parse(key);group(entity,point,channel)}
    for(const key of walked(run,[...groups.keys()].sort())){updatePort(run,ctx,groups.get(key));if(ctx.diverged)return {ok:false,...ctx.diverged}}
    const committed=clone(run.signal);
    const devices=Object.keys(run.components).filter(id=>run.components[id].role==='device'&&run.components[id].inputs.some(name=>ctx.changed.has(portKey(id,name,'main')))).sort();
    for(const entity of walked(run,devices))evaluateDevice(run,ctx,entity,committed);
    // Sequence is assigned after the tick, from stable ids only; then every provisional id is resolved.
    const sortKey=x=>[x.record.subject.entity,x.record.subject.point,x.record.subject.channel,x.record.observable,x.record.kind,x.phase,x.record.observer,x.rank,x.record.value?1:0];
    ctx.records.sort((x,y)=>cmpList(sortKey(x),sortKey(y)));
    const map=new Map();
    for(const x of ctx.records){const seq=run.sequence++;map.set(x.record.id,`sr-${run.id}-${String(seq).padStart(6,'0')}`);x.record.id=map.get(x.record.id);x.record.time.sequence=seq}
    const records=ctx.records.map(x=>{x.record.provenance.inputs=resolveTmp(x.record.provenance.inputs,map);return x.record});
    run.pending=resolveTmp(run.pending,map);run.lastRecord=resolveTmp(run.lastRecord,map);run.queues=resolveTmp(run.queues,map);
    for(const [key,q] of Object.entries(run.queues))if(!q.items.length)delete run.queues[key];
    run.pending.sort((x,y)=>cmp(Canonical.canonicalize(x),Canonical.canonicalize(y)));
    ctx.draws.sort((x,y)=>cmpList([x.entity,x.point,x.channel],[y.entity,y.point,y.channel]));
    for(const draw of ctx.draws)appendEntry(run,'draw',draw);
    run.records.push(...records);
    run.tick=t;run.spent+=ctx.cost;
    return {ok:true,cost:ctx.cost,records};
  }
  // One step is the earliest tick with scheduled work. Worked on a copy: a refused tick
  // (BUDGET_SPENT, REPLAY_DIVERGED) leaves the run exactly as it was.
  function step(run){
    if(!isObject(run)||run.runtimeVersion!==RUNTIME_VERSION)return {ok:false,code:'RUN_INVALID',message:`not a ${RUNTIME_VERSION} run`};
    const t=nextTick(run);
    if(t===null)return {ok:true,tick:null,records:[]};
    const {doc,...rest}=run,work=clone(rest);work.doc=doc;
    const result=processTick(work,t);
    if(!result.ok)return result;
    if(run.spent+result.cost>run.budget)return {ok:false,code:'BUDGET_SPENT',tick:t,left:queuedCount(run),message:`processing tick ${t} takes ${result.cost} events; ${run.budget-run.spent} of the budget ${run.budget} remain`};
    for(const key of Object.keys(work))run[key]=work[key];
    return {ok:true,tick:t,records:clone(result.records)};
  }
  function traceOf(run){
    return {format:TRACE_FORMAT,replayKey:clone(run.ledger[0].body),documentRevision:run.doc.revision,budget:run.budget,ledger:clone(run.ledger),records:clone(run.records)};
  }
  // Shape and every hash link. The chain is recomputed from the start, so a change to any byte
  // of an entry fails that entry and every entry after it.
  function validateTrace(trace){
    const errors=[];let entry=null;
    const fail=(i,message)=>{errors.push(i===null?message:`ledger ${i}: ${message}`);if(i!==null&&entry===null)entry=i};
    if(!isObject(trace))return {ok:false,entry,errors:['trace must be an object']};
    unknownKeys(trace,['format','replayKey','documentRevision','budget','ledger','records'],'trace',errors);
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
      if(entry===null&&isObject(key)&&!same(trace.ledger[0].body,key))fail(0,'the start entry does not carry the replayKey');
    }
    if(!Array.isArray(trace.records))errors.push('records must be an array');
    else trace.records.forEach((r,i)=>{const v=validateRecord(r);if(!v.ok)errors.push(`record ${i}: ${v.errors.join('; ')}`)});
    return {ok:errors.length===0,entry,errors};
  }
  // Replay: the trace's replay key recomputed from doc, packs, its inputs and seed; the fold re-run
  // to quiet or budget, reading draws from the ledger; ledger and records compared byte for byte.
  function replay(options){
    const o=isObject(options)?options:{};
    const trace=o.trace,checked=validateTrace(trace);
    if(!checked.ok)return {ok:false,code:'TRACE_INVALID',entry:checked.entry,errors:checked.errors,message:checked.entry===null?checked.errors[0]:`the trace fails at ledger entry ${checked.entry}: ${checked.errors[0]}`};
    const key=trace.replayKey;
    const started=startRun({doc:o.doc,packs:o.packs,inputs:key.inputs,seed:key.seed,budget:trace.budget});
    if(!started.ok)return started;
    const run=started.run,mine=run.ledger[0].body;
    const fields=REPLAY_KEY_FIELDS.filter(field=>!same(mine[field],key[field]));
    if(fields.length)return {ok:false,code:'REPLAY_KEY_MISMATCH',fields,message:`the replay key differs in ${fields.join(', ')}`};
    run.replayDraws=trace.ledger.filter(e=>e.kind==='draw').map(e=>({seq:e.seq,body:e.body}));
    for(;;){
      const r=step(run);
      if(!r.ok){if(r.code==='BUDGET_SPENT')break;return r}
      if(r.tick===null)break;
    }
    run.replayDraws=null;
    const n=Math.max(run.ledger.length,trace.ledger.length);
    for(let i=0;i<n;i++)if(Canonical.canonicalize(run.ledger[i]??null)!==Canonical.canonicalize(trace.ledger[i]??null))return {ok:false,code:'REPLAY_DIVERGED',entry:i,message:`ledger entry ${i} differs from the recomputed run`};
    const m=Math.max(run.records.length,trace.records.length);
    for(let i=0;i<m;i++)if(Canonical.canonicalize(run.records[i]??null)!==Canonical.canonicalize(trace.records[i]??null))return {ok:false,code:'REPLAY_DIVERGED',record:i,message:`record ${i} differs from the recomputed run`};
    return {ok:true,records:run.records};
  }

  return {RECORD_FORMAT,PACK_FORMAT,RUNTIME_VERSION,TRACE_FORMAT,validateRecord,patterns,pattern,checkDefinition,loadPack,resolveDefinition,contractOf,bindDefinition,checkDocument,startRun,step,traceOf,replay,validateTrace};
});
