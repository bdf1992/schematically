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
    index={components:run.components,out,devices};
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
      const bound=component.config?.definition;
      if(bound!==undefined&&bound!==null&&(resolveDefinition(bound,o.packs)?.parameters?.outputs||[]).includes(spec.id))return inputRefusal(`input ${i}: ${component.id}.${spec.id} is an output of ${bound}; a device's output is the device's`);
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
  function makeRecord(run,ctx,{entity,point,channel,kind,value,observer,rule,inputs,phase,rank=0}){
    const id=`${TMP}${ctx.tmp++}`;
    ctx.records.push({phase,rank,record:{format:RECORD_FORMAT,id,subject:{entity,point,channel,run:run.id},vantage:'space',observable:'logic.level',kind,form:'binary',value,time:{logical:ctx.t,sequence:0,mode:'observed'},certainty:{kind:'exact'},observer,provenance:{rule,inputs:inputs.slice()},perturbation:'none'}});
    return id;
  }
  // Emission: one arrival per bound Wire, per direction it carries out of this port, per shared
  // channel, at t + path delay; never back onto a Wire in `exclude`.
  function emit(run,ctx,entity,point,channel,value,exclude,from,phase){
    const ends=indexOf(run).out.get(entity+'\u0000'+point);
    if(!ends)return;
    for(const {wire,to} of walked(run,ends)){
      if(exclude.includes(wire.id)||!wire.channels.includes(channel))continue;
      const item={kind:'arrival',at:ctx.t+wire.delay,entity:to.entity,point:to.point,channel,value,wire:wire.id,phase,from};
      run.pending.push(item);ctx.fresh.push(item);
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
    const merge=run.merges[key]||DEFAULT_MERGE,queue=merge.combine==='queue'?ensureQueue(run,ctx,key):null;
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
        if(g.arrivals.length){const ordered=g.arrivals.length>1?mergeOrder(run,ctx,g,merge):g.arrivals;if(!ordered)return;for(const a of ordered)queue.items.push({value:a.value,wire:a.wire,phase:a.phase,from:a.from})}
        if(queue.items.length>queue.head){const item=queue.items[queue.head++];win={value:item.value,observer:'engine:merge@1',rule:'merge@1',inputs:[item.from]};if(!arrived.includes(item.wire))arrived.push(item.wire)}
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
    put(run.signal,ctx.undoSignal,key,win.value);put(run.lastRecord,ctx.undoLast,key,id);ctx.written.push(key);
    const changed=win.value!==old;
    if(changed)ctx.changed.add(key);
    if(win.always||(changed&&win.emits))emit(run,ctx,g.entity,g.point,g.channel,win.value,win.exclude,id,0);
  }
  // Evaluate phase: a device whose input port changed reads committed state only.
  function evaluateDevice(run,ctx,entity,committed){
    const component=run.components[entity],definition=run.definitions[component.definition],p=pattern(definition.pattern);
    const values={},inputs=[];
    for(const name of component.inputs){const key=portKey(entity,name,'main');values[name]=committed(key)===true;if(run.lastRecord[key])inputs.push(run.lastRecord[key])}
    const out=p.evaluate(definition.parameters,values),delay=definition.delay||0;
    for(const name of component.outputs){
      const key=portKey(entity,name,'main'),value=out[name];
      if(delay===0){
        if(value===(run.signal[key]===true))continue;
        ctx.cost++;
        const id=makeRecord(run,ctx,{entity,point:name,channel:'main',kind:'derived',value,observer:`rule:${component.definition}`,rule:component.definition,inputs,phase:1});
        if(!ctx.evaluated.has(key))ctx.evaluated.set(key,run.signal[key]);
        put(run.signal,ctx.undoSignal,key,value);put(run.lastRecord,ctx.undoLast,key,id);ctx.written.push(key);
        emit(run,ctx,entity,name,'main',value,[],id,1);
      }else{
        // Transport delay: schedule every change from the latest value already on its way.
        let latest=run.signal[key]===true,at=-1;
        for(const item of run.pending)if(item.kind==='output'&&item.entity===entity&&item.point===name&&item.channel==='main'&&item.at>at){at=item.at;latest=item.value}
        if(value!==latest){const item={kind:'output',at:ctx.t+delay,entity,point:name,channel:'main',value,rule:component.definition,inputs:inputs.slice()};run.pending.push(item);ctx.fresh.push(item)}
      }
    }
  }
  function resolveTmp(value,map){
    if(typeof value==='string')return value.startsWith(TMP)?map.get(value):value;
    if(Array.isArray(value))return value.map(x=>resolveTmp(x,map));
    if(isObject(value)){const out={};for(const [k,v] of Object.entries(value))out[k]=resolveTmp(v,map);return out}
    return value;
  }
  // Writes to signal and lastRecord go through put, which keeps each key's value from before the
  // tick, so a refused tick is undone in place (a key the tick added is removed again).
  const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
  function put(obj,undo,key,value){if(!undo.has(key))undo.set(key,own(obj,key)?[true,obj[key]]:[false]);obj[key]=value}
  function undo(obj,log){for(const [key,[had,value]] of log)if(had)obj[key]=value;else delete obj[key]}
  function processTick(run,t,ctx){
    const due=run.pending.filter(x=>x.at===t);run.pending=run.pending.filter(x=>x.at!==t);
    const groups=new Map();
    const group=(entity,point,channel)=>{const key=portKey(entity,point,channel);if(!groups.has(key))groups.set(key,{entity,point,channel,input:null,output:null,arrivals:[]});return groups.get(key)};
    for(const item of due){
      const g=group(item.entity,item.point,item.channel);ctx.cost++;
      if(item.kind==='input')g.input=item;else if(item.kind==='output')g.output=item;else g.arrivals.push(item);
    }
    for(const [key,q] of Object.entries(run.queues))if(q.items.length>q.head&&q.next===t){const [entity,point,channel]=JSON.parse(key);group(entity,point,channel)}
    for(const key of walked(run,[...groups.keys()].sort())){updatePort(run,ctx,groups.get(key));if(ctx.diverged)return {ok:false,...ctx.diverged}}
    // Committed state is the signal after the update phase: what the evaluate phase overwrites is read from before it.
    const committed=key=>ctx.evaluated.has(key)?ctx.evaluated.get(key):run.signal[key];
    const devices=indexOf(run).devices.filter(x=>t===0||x.inputs.some(key=>ctx.changed.has(key))).map(x=>x.id);
    for(const entity of walked(run,devices))evaluateDevice(run,ctx,entity,committed);
    // Sequence is assigned after the tick, from stable ids only; then every provisional id is resolved.
    // A provisional id is only ever held by what this tick made: its records, the pending items it
    // scheduled and the lastRecord entries it wrote (queue items come from arrivals of earlier ticks).
    const sortKey=x=>[x.record.subject.entity,x.record.subject.point,x.record.subject.channel,x.record.observable,x.record.kind,x.phase,x.record.observer,x.rank,x.record.value?1:0];
    const sorted=ctx.records.map(x=>({x,k:sortKey(x)})).sort((x,y)=>cmpList(x.k,y.k)).map(d=>d.x);
    const map=new Map();
    for(const x of sorted){const seq=run.sequence++;map.set(x.record.id,`sr-${run.id}-${String(seq).padStart(6,'0')}`);x.record.id=map.get(x.record.id);x.record.time.sequence=seq}
    const records=sorted.map(x=>{x.record.provenance.inputs=resolveTmp(x.record.provenance.inputs,map);return x.record});
    for(const item of ctx.fresh){if(item.from!==undefined)item.from=resolveTmp(item.from,map);if(item.inputs!==undefined)item.inputs=resolveTmp(item.inputs,map)}
    for(const key of ctx.written)put(run.lastRecord,ctx.undoLast,key,resolveTmp(run.lastRecord[key],map));
    // Only the queues this tick touched can hold a fresh (TMP) id or have run dry: resolve just the
    // items this tick appended (never the ones already resolved by an earlier tick), by buffer index.
    for(const [key,entry] of ctx.queueUndo){
      const q=entry.queue,from=entry.existed?entry.length:0;
      for(let i=from;i<q.items.length;i++){const item=q.items[i];if(typeof item.from==='string'&&item.from.startsWith(TMP))item.from=map.get(item.from)}
      if(q.items.length===q.head)delete run.queues[key];
    }
    run.pending=run.pending.map(x=>({x,k:pendingKey(x)})).sort((x,y)=>cmp(x.k,y.k)).map(d=>d.x);
    ctx.draws.sort((x,y)=>cmpList([x.entity,x.point,x.channel],[y.entity,y.point,y.channel]));
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
    const ctx={t,cost:0,tmp:0,records:[],draws:[],changed:new Set(),diverged:null,fresh:[],written:[],evaluated:new Map(),undoSignal:new Map(),undoLast:new Map(),queueUndo:new Map()};
    const result=processTick(run,t,ctx);
    const refused=!result.ok?result:run.spent+result.cost>run.budget?{ok:false,code:'BUDGET_SPENT',tick:t,left:null,message:`processing tick ${t} takes ${result.cost} events; ${run.budget-run.spent} of the budget ${run.budget} remain`}:null;
    if(refused){
      undo(run.signal,ctx.undoSignal);undo(run.lastRecord,ctx.undoLast);Object.assign(run,before);
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
    const started=startRun({doc:o.doc,packs:o.packs,inputs:key.inputs,seed:key.seed,budget:trace.budget});
    if(!started.ok)return started;
    const run=started.run,mine=run.ledger[0].body.replayKey;
    const fields=REPLAY_KEY_FIELDS.filter(field=>!same(mine[field],key[field]));
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
  function stateHash(t,signal,queues,pending){
    const q=queues.map(([k,next,items])=>[k,next-t,items.map(x=>[x.value,x.wire,x.phase])]);
    const p=pending.map(x=>{const {from,inputs,at,...rest}=x;rest.at=at-t;return Canonical.canonicalize(rest)}).sort();
    return Canonical.sha256Hex(Canonical.canonicalize({signal,queues:q,pending:p}));
  }
  const trueKeys=signal=>Object.keys(signal).filter(k=>signal[k]===true).sort();
  function futureHash(run){return stateHash(run.tick,trueKeys(run.signal),Object.keys(run.queues).sort().map(k=>[k,run.queues[k].next,queueItems(run.queues[k])]),run.pending)}
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
      parts.push(run.pending.length,pc,pa,pm);
      return parts.join('\u0000');
    };
    const snapshot=t=>({tick:t,hash:null,pending:run.pending,queues:Object.keys(run.queues).sort().map(k=>{const l=logs.get(k);return [k,run.queues[k].next,l.head,l.items.length]}),flips:changes.length});
    // The signal's true keys at an earlier snapshot: the current ones with every later flip undone.
    const hashOf=entry=>{
      if(entry.hash!==null)return entry.hash;
      const set=new Set(trueKeys(run.signal));
      for(let i=changes.length-1;i>=entry.flips;i--)for(const k of changes[i][2])if(set.has(k))set.delete(k);else set.add(k);
      entry.hash=stateHash(entry.tick,[...set].sort(),entry.queues.map(([k,next,h,n])=>[k,next,logs.get(k).items.slice(h,n)]),entry.pending);
      entry.pending=entry.queues=null;
      return entry.hash;
    };
    const visit=t=>{
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
  // document, its revision, history or recovery. A registry holds at most RUN_LIMIT runs: a start
  // beyond that is refused with RUN_LIMIT, and nothing is evicted; `drop(handle)` removes a run and
  // returns its receipt as it stood (result null), so a later start can take its place.
  const START_KEYS=['inputs','seed','budget'],BUDGET_LIMIT=1000000,RUN_LIMIT=64;
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
        if(runs.size>=RUN_LIMIT)return runReceipt(op,null,{ok:false,code:'RUN_LIMIT',message:`this surface holds ${RUN_LIMIT} runs, its limit; drop one (schematic.run.drop) before starting another`});
        const doc=current(),empty=noPacks(doc);
        if(empty)return runReceipt(op,null,empty);
        const started=startRun({doc,packs,inputs:a.inputs,seed:a.seed,budget:a.budget});
        if(!started.ok)return runReceipt(op,null,started);
        const handle=`${started.run.id}.${++count}`;
        runs.set(handle,started.run);
        return runReceipt(op,started.run,started,undefined,handle);
      },
      step:handle=>found('schematic.run.step',handle,(run,h)=>{const before=run.tick;return runReceipt('schematic.run.step',run,step(run),before,h)}),
      settle:handle=>found('schematic.run.settle',handle,(run,h)=>{const before=run.tick;return runReceipt('schematic.run.settle',run,settle(run),before,h)}),
      trace:handle=>found('schematic.run.trace',handle,(run,h)=>runReceipt('schematic.run.trace',run,traceOf(run),undefined,h)),
      query:(handle,subject)=>found('schematic.state.query',handle,(run,h)=>runReceipt('schematic.state.query',run,query(run,subject),undefined,h)),
      // RUN_OPERATIONS names the six operations runReceipt builds; a drop's receipt is that receipt
      // for the dropped run, named schematic.run.drop.
      drop:handle=>{
        const op='schematic.run.drop',receipt=found('schematic.run.trace',handle,(run,h)=>{runs.delete(h);return runReceipt('schematic.run.trace',run,null,undefined,h)});
        return {...receipt,operation:op};
      },
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

  return {RECORD_FORMAT,PACK_FORMAT,RUNTIME_VERSION,TRACE_FORMAT,RUN_RECEIPT_FORMAT,RUN_OPERATIONS,BUDGET_LIMIT,validateRecord,patterns,pattern,checkDefinition,loadPack,resolveDefinition,contractOf,bindDefinition,applyBind,checkDocument,startRun,step,settle,query,runReceipt,createRunRegistry,traceOf,replay,validateTrace,queueItems};
});
