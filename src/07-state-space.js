'use strict';
// State space concern, slice 1a (STATE-SPACE.md): the contract layer only. The state
// record envelope, the closed pattern registry (truth_table@1, merge@1), definitions and
// the minimal pack envelope, contracts generated from pattern + parameters, ports
// generated from a bound definition, and the load checks. No ledger, tick or run.
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

  return {RECORD_FORMAT,PACK_FORMAT,validateRecord,patterns,pattern,checkDefinition,loadPack,resolveDefinition,contractOf,bindDefinition,checkDocument};
});
