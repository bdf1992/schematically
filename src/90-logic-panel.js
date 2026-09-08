'use strict';
// Human runtime binding. The event runner owns all execution semantics.
(function(){
  const panel=document.createElement('details');panel.id='logicPanel';panel.className='logic-panel';
  panel.innerHTML=`<summary>Logic runner</summary>
    <p>Step through the diagram. Save a run to keep its memory and pending events.</p>
    <div class="logic-actions"><button id="logicStart">Start new run</button><button id="logicStep">Step</button><button id="logicRun">Run 100 events</button><button id="logicReplay">Check replay</button></div>
    <div class="logic-actions"><label>Source <select id="logicSource" aria-label="Logic source"></select></label><button id="logicLow">Set 0</button><button id="logicHigh">Set 1</button></div>
    <div class="logic-actions"><button id="logicSave">Save run</button><button id="logicOpen">Open run</button><input id="logicRunFile" type="file" accept=".sovrun,application/json" hidden></div>
    <output id="logicStatus" aria-live="polite">Open a logic diagram, then start a run.</output>
    <div id="logicValues"></div><details><summary>Recent events</summary><pre id="logicTrace"></pre></details>`;
  document.querySelector('.inspector').prepend(panel);
  const el=id=>document.getElementById(id);
  const showError=e=>{el('logicStatus').textContent=e.message||String(e)};
  function act(action,extra={}){return executeLogic({action,...extra})}
  el('logicStart').onclick=()=>act('start');el('logicStep').onclick=()=>act('step');
  el('logicRun').onclick=()=>act('run',{budget:100});el('logicReplay').onclick=()=>act('replay');
  el('logicLow').onclick=()=>act('input',{component:el('logicSource').value,value:0});
  el('logicHigh').onclick=()=>act('input',{component:el('logicSource').value,value:1});
  el('logicSave').onclick=()=>{try{saveLogicRun()}catch(e){showError(e)}};
  el('logicOpen').onclick=()=>el('logicRunFile').click();
  el('logicRunFile').onchange=async event=>{
    try{await openFileObject(event.target.files[0]);panel.open=true}catch(e){showError(e)}
    event.target.value='';
  };
  window.addEventListener('schematic-runtime',event=>{
    const result=event.detail;
    if(!result.ok){showError(result.receipt.error);return}
    const s=result.session;
    el('logicStatus').textContent=`${s.status} · tick ${s.time} · ${s.processed} events · ${s.queue.length} pending`;
    const chosen=el('logicSource').value;
    el('logicSource').replaceChildren(...s.program.nodes.filter(n=>n.definition.kind==='source').map(n=>{
      const option=document.createElement('option');option.value=n.id;option.textContent=nodes.find(c=>c.id===n.id)?.config?.label||n.id;return option;
    }));
    if([...el('logicSource').options].some(o=>o.value===chosen))el('logicSource').value=chosen;
    const table=document.createElement('div');
    for(const n of s.program.nodes){
      const state=s.values[n.id],row=document.createElement('div');row.className='logic-value';
      row.appendChild(Object.assign(document.createElement('strong'),{textContent:nodes.find(c=>c.id===n.id)?.config?.label||n.id}));
      const bits=value=>Object.entries(value).map(([key,bit])=>`${key}=${bit}`).join(' · ');
      for(const [label,value] of [['Input',bits(state.inputs)],['Output',bits(state.outputs)],['Memory',state.memory.join('')]])if(value)row.appendChild(Object.assign(document.createElement('div'),{textContent:`${label}: ${value}`}));
      table.appendChild(row);
    }
    el('logicValues').replaceChildren(table);
    el('logicTrace').textContent=s.trace.slice(-12).map(t=>`${t.event.time}:${t.event.sequence} ${t.event.wire||'input'} → ${t.event.component}.${t.event.port} = ${t.event.value}`).join('\n');
    // Visible emphasis is a transient projection; never writes the diagram or history.
    prepareLogicProjection();renderLogicProjection();
  });
})();
