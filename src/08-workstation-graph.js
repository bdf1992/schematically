'use strict';
// WS record projection only. Workstation owns these records; no status inference,
// command execution, permission expansion, or network collection occurs here.
(function(root,factory){
  const node=typeof module!=='undefined'&&module.exports;
  const api=factory(root.SovSchematicData||(node?require('./05-data-core.js'):null),root.SovSchematicGraph||(node?require('./07-graph-core.js'):null));
  root.SovWorkstationGraph=api;if(node)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(Data,Graph){
  const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
  const address=(kind,id)=>`ws:${kind}:${encodeURIComponent(id)}`;
  const compareId=(a,b)=>a.id<b.id?-1:a.id>b.id?1:0;
  function project(input){
    Graph.jsonValue(input);Graph.demand(input&&input.mission&&Array.isArray(input.tasks),'WS_GRAPH_INPUT','Provide mission, tasks, and source');
    const {mission,source}=input;Graph.source(source);
    Graph.text(mission.id,'mission.id');Graph.text(mission.repository,'mission.repository');Graph.text(mission.title,'mission.title');
    Graph.demand(input.tasks.length<=100,'GRAPH_LIMIT','This profile admits at most 100 tasks per mission');
    const tasks=Data.clone(input.tasks).sort(compareId),ids=new Set();
    for(const task of tasks){
      Graph.text(task.id,'task.id');Graph.demand(!ids.has(task.id),'GRAPH_DUPLICATE','Duplicate WS task id');ids.add(task.id);
      Graph.demand(task.mission===mission.id&&task.repository===mission.repository,'WS_GRAPH_SCOPE','Every supplied task must name this mission and repository');
      if(own(task,'dependencies'))Graph.demand(Array.isArray(task.dependencies)&&task.dependencies.every(d=>typeof d==='string'&&d.length>0)&&new Set(task.dependencies).size===task.dependencies.length,'WS_GRAPH_INPUT','Dependencies must be distinct task IDs');
      Graph.demand(task.contract==null||(typeof task.contract==='object'&&!Array.isArray(task.contract)),'WS_GRAPH_INPUT','Contract must be an object or null');
    }
    const doc=Data.makeDocument({id:address('mission',mission.id),meta:{title:mission.title,updatedAt:source.capturedAt,graph:{schema:Graph.DEFINITION,bindings:[]}}});
    const readings=[],gaps=[],taskNodes=new Map();
    const columns=Math.min(3,Math.max(1,tasks.length)),rows=Math.ceil(Math.max(1,tasks.length)/columns);
    const width=columns*420+120,height=rows*380+200;
    function field(record,key,path,basis='declared'){
      return {axis:key,basis,status:own(record,key)?'present':'absent',...(own(record,key)?{value:Data.clone(record[key])}:{}),source:`${path}${path.includes('#')?'/':'#/'}${key.replaceAll('~','~0').replaceAll('/','~1')}`};
    }
    function add(id,label,kind,addr,parent,x,y,w,h,fields,ports=false){
      const component=Data.makeComponent(doc,{id,symbolId:'plane',x,y,parentId:parent?.id||null,canvasId:parent?Data.componentCanvasId(parent):Data.GLOBAL_CANVAS_ID,
        form:{dimension:2,regions:{interior:{state:'open'}}},
        config:{label,signalMode:'passive',attachmentDefaults:ports?'standard':'none',presentation:{graphic:{kind:'none'},labelMode:'boundary',backdrop:'solid',size:{w,h}},
          ...(ports?{ports:{in:{face:'external',connections:[{flow:'in',access:'none'}]},out:{face:'external',connections:[{flow:'out',access:'none'}]},control:{face:'external',connections:[{flow:'control',access:'none'}]}}}:{})}});
      doc.components.push(component);doc.meta.graph.bindings.push({resource:'component',id,kind,address:addr});readings.push({address:addr,fields});return component;
    }
    const missionPath=`control/missions/${mission.id}.json`;
    const root=add('mission',mission.title,'system',address('mission',mission.id),null,width/2+80,height/2+60,width,height,
      ['repository','lifecycle','standing','summary','description','waiting_on','estimates','updated'].map(k=>field(mission,k,missionPath)));
    tasks.forEach((task,i)=>{
      const x=80+270+(i%columns)*420,y=60+230+Math.floor(i/columns)*380,path=`control/tasks/${task.id}.json`;
      const addr=address('task',task.id);
      const node=add(`task-${encodeURIComponent(task.id)}`,task.title||task.id,'node',addr,root,x,y,340,280,
        ['objective','standing','workstation_state','repository_state','waiting_on','serves','dependencies','claim','branch','base_ref','worktree','environment','candidate_id','evidence','residuals','promoted_from','updated'].map(k=>field(task,k,path)),true);
      taskNodes.set(task.id,node);
      if(task.waiting_on&&task.waiting_on!=='nobody')gaps.push({address:addr,code:'UNRESOLVED_WAIT',message:task.waiting_on});
      if(!own(task,'dependencies'))gaps.push({address:addr,code:'DEPENDENCIES_ABSENT',message:'Dependency field absent; do not infer that this task is independent.'});
      const held=[];
      if(task.contract)held.push({key:'contract',label:'Work contract',fields:Object.keys(task.contract).sort().map(k=>field(task.contract,k,path+'#/contract'))});
      if(task.candidate_id)held.push({key:'candidate',label:'Candidate reference',fields:[field(task,'candidate_id',path),{axis:'revision',basis:'observed',status:'absent',source:path+'#/candidate_id'}]});
      if(Array.isArray(task.evidence)&&task.evidence.length)held.push({key:'evidence',label:'Evidence references',fields:[field(task,'evidence',path)]});
      if(Array.isArray(task.residuals)&&task.residuals.length)held.push({key:'residuals',label:'Unresolved obligations',fields:[field(task,'residuals',path)]});
      held.forEach((charge,j)=>add(`held-${encodeURIComponent(task.id)}-${charge.key}`,charge.label,'charge',addr+'/'+charge.key,node,x+(j%2===0?-80:80),y-30+Math.floor(j/2)*90,140,68,charge.fields));
    });
    const missing=[...new Set(tasks.flatMap(t=>t.dependencies||[]).filter(id=>!ids.has(id)))].sort();
    // Missing endpoints remain explicit gaps, never invented tasks or default state.
    for(const task of tasks)for(const dependency of task.dependencies||[]){
      const target=taskNodes.get(task.id),predecessor=taskNodes.get(dependency),addr=address('dependency',JSON.stringify([dependency,task.id]));
      if(!predecessor){gaps.push({address:address('task',task.id),code:'DEPENDENCY_OUTSIDE_SNAPSHOT',message:`Dependency ${dependency} is outside this snapshot.`});continue;}
      const wire=Data.makeWire(doc,{id:`dependency-${encodeURIComponent(JSON.stringify([dependency,task.id]))}`,a:predecessor.id,aSide:'out',b:target.id,bSide:'in',config:{label:'requires',direction:'forward',forwardOperation:'none',reverseOperation:'none'}});
      doc.wires.push(wire);doc.meta.graph.bindings.push({resource:'wire',id:wire.id,kind:'dependency',address:addr});
      readings.push({address:addr,fields:[{axis:'required_task',basis:'declared',status:'present',value:dependency,source:`control/tasks/${task.id}.json#/dependencies`},{axis:'delivery',basis:'observed',status:'absent',source:'not-a-transport-observation'}]});
    }
    const document=Data.compactDocument(doc),state=Graph.snapshot(document,source,readings,gaps);
    // An existing package holds the observation separately from the .sov definition.
    // Supplied timestamps make repeated projections byte-identical.
    return {schema:Data.PACKAGE_SCHEMA,version:1,manifest:{id:doc.id+'-snapshot',title:mission.title,entry:'document',createdAt:source.capturedAt,updatedAt:source.capturedAt,generator:'SOV Workstation graph profile 0.1'},
      document,workspace:{view:{showFlow:false}},templates:[],assets:[],meta:{graph:state,coverage:{tasks:tasks.length,missingDependencies:missing}}};
  }
  function tools(){
    const object={type:'object'};
    return [
      {name:'schematic.graph.project-workstation',description:'Project supplied WS mission records to a native .sovpak with separate source readings. No network calls, task writes, or authority.',inputSchema:{type:'object',properties:{input:object},required:['input'],additionalProperties:false}},
      {name:'schematic.graph.inspect',description:'Inspect a source-bound graph snapshot or one address. Refuses detached readings. Does not mutate the server document.',inputSchema:{type:'object',properties:{package:object,address:{type:'string'}},required:['package'],additionalProperties:false}},
      {name:'schematic.graph.compare',description:'Compare two source snapshots of the same mission. Reports readings, not execution history or progress.',inputSchema:{type:'object',properties:{before:object,after:object},required:['before','after'],additionalProperties:false}}
    ];
  }
  function execute(name,args={}){
    try{
      let value;
      if(name==='schematic.graph.project-workstation')value=project(args.input);
      else if(name==='schematic.graph.inspect')value=Graph.inspect(args.package?.document,args.package?.meta?.graph,args.address??null);
      else if(name==='schematic.graph.compare')value=Graph.compare(args.before,args.after);
      else Graph.refuse('GRAPH_OPERATION','Unknown graph operation');
      return {ok:true,value,mutates:false};
    }catch(e){return {ok:false,value:{error:{code:e.code||'GRAPH_INPUT',message:String(e.message||e)}},mutates:false};}
  }
  return {project,address,tools,execute};
});
