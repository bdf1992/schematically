'use strict';
// Read-only projection of the Python Knode runtime. Opening a virtual node is
// still an editor view operation. No execution or inferred Kord lives here.
const koreObservation={snapshot:null,error:null,busy:false,bound:false,observedAt:null,inspection:null,lastSelection:null,recordsOpen:false};
function koreBinding(){return diagram.meta?.koreExecution||null}
function koreCopy(value){return value==null?null:JSON.parse(JSON.stringify(value))}
function koreInspect(node,cell=null){
  const state=koreObservation.snapshot?.nodes?.[node];
  if(!state||(cell&&!state.cells?.[cell]))return {ok:false,message:'Unknown observed address'};
  const shell=Object.keys(koreBinding()?.nodes||{}).find(key=>koreBinding().nodes[key]===node);
  if(shell&&typeof openVirtualNode==='function')openVirtualNode(shell);
  koreObservation.inspection={node,cell};koreProject();return {ok:true,node,cell};
}
function koreDetails(lines,state,accepted=false){
  lines.push('Phase '+state.phase+' / '+state.phase_count+' · position '+state.phase+'/'+state.phase_count,'Work · '+(state.work||'none'),'Waiting · '+(state.waiting||'none'));
  if(state.owner)lines.push('Owner · '+state.owner+' · '+(state.role||'')+' · '+state.row+'/'+state.column);
  if(state.state!=null)lines.push('Attributed local state · '+Object.keys(state.state).length+' fields · expand execution records');
  for(const [label,key] of [['Pending candidates','candidates'],[accepted?'Accepted results':'Returned outcomes / envelopes','results'],['Failures','failures'],['Evidence receipts','receipts']])if(state[key]!=null)lines.push(label+' · '+state[key].length);
  if(state.results?.length)lines.push('Latest return · '+koreOutcome(state.results.at(-1)));
  if(state.failures?.length)lines.push('Latest failure · '+koreOutcome(state.failures.at(-1)));
  if(state.last_check)lines.push('Last check · '+koreOutcome(state.last_check));
  if(!accepted&&state.results?.some(result=>result.semantic_acceptance===false||result.value?.semantic_acceptance===false))lines.push('Candidate envelope · semantic acceptance false · caller verification is required.');
  if(state.gate!=null)lines.push('Gate · '+JSON.stringify(state.gate));
  if(state.authority_version!=null)lines.push('Authority version · '+state.authority_version+' · locked '+!!state.locked);
}
function koreOutcome(outcome){
  const value=outcome.value||outcome;
  return [outcome.status||outcome.decision||outcome.name,value.code||outcome.code,value.action||value.candidate?.action||(typeof value.candidate==='string'?value.candidate:null),value.escalation_holder||outcome.escalation_holder].filter(Boolean).join(' · ')||'recorded';
}
function koreButton(panel,label,action){const button=document.createElement('button');button.textContent=label;button.onclick=action;panel.appendChild(button)}
function koreProject(){
  const binding=koreBinding(),bound=!!binding;
  koreObservation.bound=bound;
  for(const id of ['simPlayBtn','simStepBtn','simResetBtn','simSpeed']){
    const el=document.getElementById(id);
    if(el){el.disabled=bound;if(bound)el.title='Observed Python execution; fixture clock is disabled'}
  }
  let panel=document.getElementById('koreExecutionPanel');
  if(!panel){panel=document.createElement('div');panel.id='koreExecutionPanel';panel.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;padding:8px;font-size:12px';document.getElementById('objectsList')?.before(panel)}
  panel.hidden=!bound;
  const fixturePanel=document.getElementById('virtualStatePanel');
  if(fixturePanel&&bound)fixturePanel.hidden=true;
  const fixtureLayer=document.getElementById('simLayer');
  if(fixtureLayer)fixtureLayer.style.display=bound?'none':'';
  if(!bound)return;
  if(typeof simClock!=='undefined'&&simClock.playing)simPause();
  const snapshot=koreObservation.snapshot;
  const lines=['Observed Python execution · shared runtime'];
  if(koreObservation.error)lines.push('Observation unavailable · '+koreObservation.error);
  if(koreObservation.error&&snapshot)lines.push('Retained last reading · '+koreObservation.observedAt+' · current activity unknown');
  if(!snapshot){panel.textContent=lines.join('\n');return}
  const missing=[],contracts=Array.isArray(snapshot.contracts)?snapshot.contracts:[];
  for(const node of Object.values(binding.nodes||{}))if(!snapshot.nodes[node])missing.push(node);
  for(const address of Object.values(binding.cells||{}))if(!snapshot.nodes[address.node]?.cells?.[address.cell])missing.push(address.node+'/cells/'+address.cell);
  for(const kord of Object.keys(binding.kords||{}))if(!contracts.some(contract=>contract.id===kord))missing.push('Kord '+kord);
  if(binding.contractId&&snapshot.contract_id!==binding.contractId)missing.push('contract '+binding.contractId);
  if(binding.contractVersion&&snapshot.contract_version!==binding.contractVersion)missing.push('contract version '+binding.contractVersion);
  if(missing.length)lines.push('Binding incomplete · '+missing.length+' missing addresses or declarations · expand execution records','This endpoint reading does not establish execution of the displayed governed topology.');
  const map=binding.nodes||{};
  if(typeof selected!=='undefined'&&selected!==koreObservation.lastSelection){
    koreObservation.lastSelection=selected;
    const address=binding.cells?.[selected];
    if(address&&snapshot.nodes[address.node]?.cells?.[address.cell])koreObservation.inspection={node:address.node,cell:address.cell};
    else if(map[selected])koreObservation.inspection={node:map[selected],cell:null};
  }
  const open=virtualView.open;
  const inspection=koreObservation.inspection;
  const id=open?(map[open]||open):inspection?.node;
  if(inspection&&inspection.node!==id)koreObservation.inspection=null;
  const state=id?snapshot.nodes?.[id]:null;
  if(state){
    lines.push(id+' · separate node state');koreDetails(lines,state);
    if(state.parent!=null)lines.push('Declared parent · '+JSON.stringify(state.parent));
    if(state.parent_cell!=null)lines.push('Parent cell · '+JSON.stringify(state.parent_cell));
    for(const [cell,value] of Object.entries(state.cells||{}))lines.push(cell+' · phase '+value.phase+'/'+value.phase_count+' · '+(value.gate||'no gate reading')+' · '+(value.work||'idle'));
    const cell=koreObservation.inspection?.cell,local=cell?state.cells?.[cell]:null;
    if(local){lines.push('\nInspecting '+id+'/cells/'+cell+' · owned state');koreDetails(lines,local,true)}
    const request=state.work?snapshot.requests?.[state.work]:null;
    if(request)lines.push('Return address · '+JSON.stringify(request.return_address||[]));
  }else lines.push('Open a node to inspect its 3×3 and local state.');
  if(snapshot.contracts)lines.push('Declared typed Kords · '+contracts.length);
  if(snapshot.contract_id)lines.push('Contract · '+snapshot.contract_id+' · version '+snapshot.contract_version);
  const gate=[...(snapshot.gates||[])].reverse().find(event=>(!id||event.node===id)&&event.gate);
  if(gate)lines.push('Last named gate · '+gate.gate+' · '+gate.node+'/'+gate.cell);
  const receipt=[...(snapshot.receipts||[])].reverse().find(event=>!id||event.node===id);
  if(receipt)lines.push('Last recorded decision · '+koreOutcome(receipt));
  if(snapshot.attempts)lines.push('Bounded attempts · '+snapshot.attempts.length);
  const events=snapshot.events||[],last=events.at(-1);
  if(last)lines.push('Latest · '+last.kind+' · '+(last.request_id||'')+' · '+(last.node||''));
  const handoff=[...events].reverse().find(e=>e.kind==='handoff');
  if(handoff)lines.push('Last recorded traversal · '+handoff.kord+' · '+handoff.request_id);
  for(const [requestId,request] of Object.entries(snapshot.requests||{}))if(request.outcome)lines.push('Completed · '+requestId+' · '+koreOutcome(request.outcome));
  panel.textContent='';
  for(const node of Object.keys(snapshot.nodes))koreButton(panel,'Open '+node,()=>koreInspect(node));
  for(const cell of Object.keys(state?.cells||{}))koreButton(panel,'Inspect '+cell,()=>koreInspect(id,cell));
  if(state?.parent&&snapshot.nodes[state.parent])koreButton(panel,'Open parent '+state.parent,()=>koreInspect(state.parent));
  for(const contract of contracts){
    if(contract.source===id&&(!koreObservation.inspection?.cell||contract.source_cell===koreObservation.inspection.cell)&&snapshot.nodes[contract.target])koreButton(panel,'Open Kord '+contract.id+' → '+contract.target,()=>koreInspect(contract.target));
  }
  const reading=document.createElement('pre');reading.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;margin:8px 0';reading.textContent=lines.join('\n');panel.appendChild(reading);
  const records=document.createElement('details'),summary=document.createElement('summary'),raw=document.createElement('pre');
  records.open=koreObservation.recordsOpen;records.ontoggle=()=>{koreObservation.recordsOpen=records.open};
  summary.textContent='Execution records · full states, checks, contracts and return history';
  raw.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px';raw.textContent=JSON.stringify({missingBindings:missing,...snapshot},null,2);
  records.appendChild(summary);records.appendChild(raw);panel.appendChild(records);
  for(const el of document.querySelectorAll('.node[data-id]')){
    const address=binding.cells?.[el.dataset.id];
    const node=address?snapshot.nodes?.[address.node]?.cells?.[address.cell]:snapshot.nodes?.[map[el.dataset.id]||el.dataset.id];
    if(node){el.dataset.korePhase=String(node.phase);el.dataset.koreWaiting=String(!!node.waiting);el.style.setProperty('--kore-phase',String(node.phase/node.phase_count));el.style.filter=node.work?'drop-shadow(0 0 5px #268bd2)':''}
  }
  for(const el of document.querySelectorAll('.wire-group')){
    const active=handoff&&!snapshot.requests?.[handoff.request_id]?.outcome&&el.dataset.wireId===(binding.kords?.[handoff.kord]||handoff.kord);
    el.dataset.koreTraversal=String(!!active);el.style.filter=active?'drop-shadow(0 0 4px #268bd2)':'';
  }
}
async function korePoll(){
  koreProject();
  if(!koreBinding()||koreObservation.busy)return;
  koreObservation.busy=true;
  try{
    // A fixed same-origin endpoint; metadata never grants local file access.
    const response=await fetch('/kore/execution',{cache:'no-store'});
    if(!response.ok)throw new Error('HTTP '+response.status);
    const snapshot=await response.json();
    if(!snapshot.nodes||!snapshot.requests||!Array.isArray(snapshot.events))throw new Error('Invalid Knode snapshot');
    koreObservation.snapshot=snapshot;koreObservation.error=null;koreObservation.observedAt=new Date().toISOString();
  }catch(error){koreObservation.error=String(error.message)}
  finally{koreObservation.busy=false;koreProject()}
}
window.SovKoreExecution={state:()=>koreCopy(koreObservation.snapshot),status:()=>({bound:!!koreBinding(),error:koreObservation.error}),inspect:koreInspect,refresh:korePoll};
setInterval(korePoll,500);
korePoll();
