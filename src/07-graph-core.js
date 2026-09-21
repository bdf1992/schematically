'use strict';
// Read-only graph observations over native Component/Wire topology. No scheduler,
// authority evaluator, CRUD implementation, or network access lives here.
(function(root,factory){
  const Data=root.SovSchematicData||(typeof module!=='undefined'&&module.exports?require('./05-data-core.js'):null);
  const api=factory(Data);root.SovSchematicGraph=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(Data){
  const DEFINITION='soveraeign.schematic/graph-definition@0.1';
  const SNAPSHOT='soveraeign.schematic/graph-snapshot@0.1';
  const BASES=['declared','observed','derived','judged'];
  const KINDS=['system','node','charge','reference','dependency','transport','provenance'];
  const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
  const object=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
  function refuse(code,message){const e=new Error(message);e.code=code;throw e;}
  function demand(test,code,message){if(!test)refuse(code,message);}
  function text(x,label){demand(typeof x==='string'&&x.length>0&&x.length<=4096,'GRAPH_SHAPE',`${label} must be nonempty text (at most 4096 characters)`);return x;}
  function jsonValue(value,depth=0,budget={n:0,characters:0}){
    demand(depth<=24&&++budget.n<=50000,'GRAPH_LIMIT','Graph value exceeds the depth or item budget');
    if(typeof value==='string'){budget.characters+=value.length;demand(budget.characters<=2_000_000,'GRAPH_LIMIT','Graph text exceeds two million characters');return;}
    if(value===null||typeof value==='boolean')return;
    if(typeof value==='number'){demand(Number.isFinite(value),'GRAPH_SHAPE','Non-finite graph number');return;}
    demand(Array.isArray(value)||object(value),'GRAPH_SHAPE','Graph values must be JSON values');
    for(const [key,v] of Object.entries(value)){
      budget.characters+=key.length;demand(budget.characters<=2_000_000,'GRAPH_LIMIT','Graph text exceeds two million characters');
      demand(!['__proto__','prototype','constructor'].includes(key),'GRAPH_SHAPE','Reserved graph object key');
      jsonValue(v,depth+1,budget);
    }
  }
  // Canonical content is a compatibility binding, not an authentication claim.
  function canonical(value){
    if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
    if(object(value))return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';
    return JSON.stringify(value);
  }
  function source(value){
    demand(object(value),'GRAPH_SOURCE','A source frontier is required');
    text(value.system,'source.system');text(value.revision,'source.revision');text(value.coverage,'source.coverage');
    demand(typeof value.capturedAt==='string'&&/T.*(?:Z|[+-]\d\d:\d\d)$/.test(value.capturedAt)&&Number.isFinite(Date.parse(value.capturedAt)),'GRAPH_SOURCE','source.capturedAt must include a timezone');
    demand(['repository-snapshot','sampled-files','provided-snapshot','fixture'].includes(value.consistency),'GRAPH_SOURCE','Name the source consistency; a set of file reads is not a live atomic snapshot');
    return value;
  }
  function index(document){
    jsonValue(document);
    let doc;
    try{doc=Data.makeDocument(Data.clone(document));const check=Data.validateDocument(doc);demand(check.ok,'GRAPH_TOPOLOGY',check.errors.join('; '));}
    catch(error){refuse(error.code||'GRAPH_TOPOLOGY',error.message);}
    const graph=doc.meta?.graph;
    demand(graph?.schema===DEFINITION&&Array.isArray(graph.bindings),'GRAPH_DEFINITION','Missing graph definition');
    demand(graph.bindings.length<=1500,'GRAPH_LIMIT','At most 1500 graph subjects');
    const byRef=new Map(),byAddress=new Map();
    for(const binding of graph.bindings){
      demand(object(binding),'GRAPH_SHAPE','Invalid graph binding');
      text(binding.id,'binding.id');text(binding.address,'binding.address');
      demand(['component','wire'].includes(binding.resource)&&KINDS.includes(binding.kind),'GRAPH_SHAPE','Unknown graph resource or kind');
      const ref=binding.resource+':'+binding.id;
      demand(!byRef.has(ref)&&!byAddress.has(binding.address),'GRAPH_DUPLICATE','Duplicate graph reference or address');
      const entity=Data.read(doc,binding.resource,binding.id);
      demand(entity,'GRAPH_BINDING',`Missing bound ${ref}`);
      const row={...Data.clone(binding),entity,parent:null};byRef.set(ref,row);byAddress.set(binding.address,row);
    }
    demand(byRef.size===doc.components.length+doc.wires.length,'GRAPH_BINDING','Every Component and Wire needs a graph binding');
    for(const row of byRef.values()){
      const canvas=row.entity.canvasId||Data.GLOBAL_CANVAS_ID;
      if(canvas!==Data.GLOBAL_CANVAS_ID){
        const match=/^canvas:(component|wire):(.+)$/.exec(canvas);
        demand(match,'GRAPH_SCOPE',`Unknown surface for ${row.address}`);
        const parent=byRef.get(match[1]+':'+match[2]);
        demand(parent,'GRAPH_SCOPE',`Missing surface owner for ${row.address}`);
        if(parent.resource==='component')demand(parent.entity.form.regions.interior.state==='open','GRAPH_SCOPE','A closed Component cannot host graph subjects');
        row.parent=parent.address;
      }
      if(row.resource==='component'&&row.entity.parentId!=null)demand(row.parent===byRef.get('component:'+row.entity.parentId)?.address,'GRAPH_SCOPE','parentId disagrees with the hosting surface');
    }
    for(const row of byRef.values()){
      const seen=new Set([row.address]);let parent=row.parent;
      while(parent){demand(!seen.has(parent),'GRAPH_SCOPE','Cyclic graph containment');seen.add(parent);parent=byAddress.get(parent).parent;}
    }
    return {doc,byRef,byAddress};
  }
  function definition(document){
    const idx=index(document);
    const subjects=[...idx.byAddress.values()].map(row=>{
      const e=row.entity;
      const common={address:row.address,id:row.id,resource:row.resource,kind:row.kind,parent:row.parent,label:e.config?.label||''};
      if(row.resource==='wire')return {...common,ends:[e.aAttachment,e.bAttachment],direction:e.config.direction,connections:[e.config.aConnectionIndex||0,e.config.bConnectionIndex||0],operations:[e.config.forwardOperation,e.config.reverseOperation]};
      const ports=Data.canonicalPortIdsForComponent(e).sort().map(id=>{
        const p=Data.attachmentPointConfig(idx.doc,e.id,id);
        return {id,face:p.face||'external',connections:(p.connections||[]).map(c=>({flow:c.flow,access:c.access}))};
      });
      return {...common,dimension:e.form.dimension,interior:e.form.regions.interior.state,ports};
    }).sort((a,b)=>a.address<b.address?-1:a.address>b.address?1:0);
    return canonical({schema:DEFINITION,id:idx.doc.id,subjects});
  }
  function snapshot(document,frontier,readings,gaps=[]){
    const state={schema:SNAPSHOT,source:Data.clone(frontier),definition:definition(document),readings:Data.clone(readings),gaps:Data.clone(gaps)};
    validate(document,state);return state;
  }
  function validate(document,state){
    jsonValue(state);demand(state?.schema===SNAPSHOT,'GRAPH_SNAPSHOT','Missing graph snapshot');source(state.source);
    const idx=index(document);
    demand(state.definition===definition(document),'GRAPH_DEFINITION_CHANGED','Diagram meaning changed; these source readings are detached. Re-project the source or restore the diagram.');
    demand(Array.isArray(state.readings)&&state.readings.length===idx.byAddress.size,'GRAPH_READINGS','One reading per bound subject is required');
    const seen=new Set();
    for(const reading of state.readings){
      demand(object(reading)&&idx.byAddress.has(reading.address)&&!seen.has(reading.address),'GRAPH_READINGS','Duplicate or unknown reading subject');seen.add(reading.address);
      demand(Array.isArray(reading.fields)&&reading.fields.length<=128,'GRAPH_LIMIT','A reading has at most 128 fields');
      const fields=new Set();
      for(const field of reading.fields){
        demand(object(field),'GRAPH_SHAPE','Invalid field');text(field.axis,'field.axis');text(field.source,'field.source');
        demand(!fields.has(field.axis),'GRAPH_DUPLICATE','Duplicate reading axis');fields.add(field.axis);
        demand(BASES.includes(field.basis)&&['present','absent'].includes(field.status),'GRAPH_READING','Invalid basis or presence state');
        demand(own(field,'value')===(field.status==='present'),'GRAPH_READING','Absent is not null, zero, false or an empty collection');
      }
    }
    demand(Array.isArray(state.gaps)&&state.gaps.length<=3000,'GRAPH_LIMIT','Invalid gap list');
    for(const gap of state.gaps){demand(object(gap)&&idx.byAddress.has(gap.address),'GRAPH_BINDING','Unknown gap subject');text(gap.code,'gap.code');text(gap.message,'gap.message');}
    return {ok:true,subjects:idx.byAddress.size};
  }
  function inspect(document,state,address=null){
    validate(document,state);const idx=index(document);
    if(address===null)return {source:Data.clone(state.source),roots:[...idx.byAddress.values()].filter(x=>!x.parent).map(summary),gaps:Data.clone(state.gaps),subjects:idx.byAddress.size};
    const row=idx.byAddress.get(address)||idx.byRef.get(address);
    demand(row,'GRAPH_SUBJECT','No such graph subject');
    const ancestors=[];let parent=row.parent;
    while(parent){const p=idx.byAddress.get(parent);ancestors.unshift(summary(p));parent=p.parent;}
    return {...summary(row),source:Data.clone(state.source),ancestors,
      endpoints:row.resource==='wire'?['a','b'].map(end=>{const subject=idx.byRef.get('component:'+row.entity[end]);return subject?{end,...summary(subject)}:{end,free:true};}):[],children:[...idx.byAddress.values()].filter(x=>x.parent===row.address).map(summary),
      fields:Data.clone(state.readings.find(x=>x.address===row.address).fields),gaps:Data.clone(state.gaps.filter(x=>x.address===row.address)),
      relations:[...idx.byAddress.values()].filter(x=>x.resource==='wire'&&(x.entity.a===row.id||x.entity.b===row.id)).map(summary)};
  }
  function summary(row){return {address:row.address,id:row.id,resource:row.resource,kind:row.kind,parent:row.parent,label:row.entity.config?.label||row.address};}
  function compare(before,after){
    validate(before.document,before.meta?.graph);validate(after.document,after.meta?.graph);
    const a=before.meta.graph,b=after.meta.graph;
    demand(a.source.system===b.source.system&&before.document.id===after.document.id,'GRAPH_SCOPE','Compare snapshots of the same system and mission');
    const rows=s=>new Map(s.readings.map(x=>[x.address,x.fields]));const left=rows(a),right=rows(b),changes=[];
    for(const address of [...new Set([...left.keys(),...right.keys()])].sort()){
      if(!left.has(address)||!right.has(address)){changes.push({address,kind:left.has(address)?'removed':'added'});continue;}
      const fields=x=>new Map(x.map(f=>[f.axis,f]));const l=fields(left.get(address)),r=fields(right.get(address));
      for(const axis of [...new Set([...l.keys(),...r.keys()])].sort()){
        if(canonical(l.get(axis)||null)!==canonical(r.get(axis)||null))changes.push({address,axis,before:Data.clone(l.get(axis)||null),after:Data.clone(r.get(axis)||null)});
      }
    }
    return {before:Data.clone(a.source),after:Data.clone(b.source),definitionChanged:a.definition!==b.definition,changes};
  }
  return {DEFINITION,SNAPSHOT,BASES,KINDS,canonical,jsonValue,refuse,demand,text,source,index,definition,snapshot,validate,inspect,compare};
});
