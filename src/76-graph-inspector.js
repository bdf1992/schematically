'use strict';
// Human inspection of the same graph readings returned by HTTP/MCP. Geometry,
// selection and file lifecycle stay with their existing owning modules.
function graphElement(tag,text,cls){const e=document.createElement(tag);if(text!=null)e.textContent=String(text);if(cls)e.className=cls;return e;}
function graphSubject(){
  const bindings=diagram.meta?.graph?.bindings||[];
  if(typeof selected==='string'&&selected.startsWith('wire:'))return bindings.find(b=>b.resource==='wire'&&b.id===wires[Number(selected.slice(5))]?.id)?.address||null;
  if(typeof selected==='string'&&selected.startsWith('point:component:'))return bindings.find(b=>selected.startsWith('point:component:'+b.id+':'))?.address||null;
  return bindings.find(b=>b.resource==='component'&&b.id===selected)?.address||null;
}
function graphGo(address){
  const binding=diagram.meta?.graph?.bindings?.find(b=>b.address===address);if(!binding)return;
  if(binding.resource==='component')focusComponent(nodes.find(n=>n.id===binding.id));
  else selectWire(wires.findIndex(w=>w.id===binding.id),{focus:false});
  renderGraphInspector();
}
function graphCard(row){
  const b=graphElement('button',null,'graph-card');b.type='button';b.dataset.address=row.address;
  b.append(graphElement('strong',row.label),graphElement('small',row.kind));
  if(row.resource==='wire'){const wire=wires.find(w=>w.id===row.id);if(wire){const names=[wire.a,wire.b].map(id=>nodes.find(n=>n.id===id)?.config?.label||id||'Free end');b.append(graphElement('small',names.join(' → ')));}}
  b.addEventListener('click',()=>graphGo(row.address));return b;
}
function graphValue(value,depth=0){
  if(value===null)return graphElement('span','Null (recorded)','graph-null');
  if(typeof value!=='object')return graphElement('span',typeof value==='string'?(value===''?'Empty text':value):String(value),'graph-value');
  const entries=Object.entries(value);
  if(!entries.length)return graphElement('span',Array.isArray(value)?'Empty list':'Empty object','graph-null');
  const group=graphElement('details',null,'graph-value-tree');group.open=depth===0;
  group.append(graphElement('summary',`${entries.length} ${Array.isArray(value)?'items':'fields'}`));
  for(const [key,v] of entries){const item=graphElement('div',null,'graph-value-item');item.append(graphElement('b',Array.isArray(value)?Number(key)+1:key),graphValue(v,depth+1));group.append(item);}
  return group;
}
function graphSourceLink(field,source){
  const label=graphElement('small',field.source,'graph-source');
  if(!source.baseUrl)return label;
  try{
    const url=new URL(field.source,source.baseUrl);
    if(!['http:','https:'].includes(url.protocol))return label;
    const link=graphElement('a','Source','graph-source');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.title=field.source;return link;
  }catch(_){return label;}
}
function setGraphView(enabled){
  const on=!!enabled&&!!currentPackageMeta.graph;
  document.querySelector('.app')?.classList.toggle('graph-view',on);
  document.getElementById('graphViewBtn')?.setAttribute('aria-pressed',String(on));
  render();return on;
}
function renderGraphInspector(){
  const panel=document.getElementById('graphInspector'),toggle=document.getElementById('graphViewBtn');if(!panel)return;
  const state=currentPackageMeta.graph;panel.hidden=!state;if(toggle)toggle.hidden=!state;
  if(!state){document.querySelector('.app')?.classList.remove('graph-view');panel.replaceChildren();delete panel.dataset.reading;return;}
  // Preserve expanded nested values across render/auto-save; selection or source changes
  // create a fresh view, but ordinary re-rendering never closes a user's inspection.
  let reading;
  try{reading=SovSchematicGraph.inspect(snapshotDocument(),state,graphSubject());}
  catch(error){delete panel.dataset.reading;panel.replaceChildren(graphElement('h2','Graph readings detached'),graphElement('p',error.message,'graph-gap'));return;}
  const key=JSON.stringify(reading);if(panel.dataset.reading===key)return;panel.dataset.reading=key;
  panel.replaceChildren();
  const head=graphElement('div',null,'graph-heading');head.append(graphElement('h2','Source graph'));
  const all=graphElement('button','Mission','btn');all.type='button';all.addEventListener('click',()=>{selectNode(null,{focus:false});fitDiagram();});head.append(all);panel.append(head);
  panel.append(graphElement('div',reading.source.consistency==='fixture'?'Fixture · not live work':'Source snapshot · not live state','graph-frontier'));
  const frontier=graphElement('details',null,'graph-frontier');frontier.append(graphElement('summary',reading.source.capturedAt),graphElement('p',reading.source.revision),graphElement('p',reading.source.coverage));panel.append(frontier);
  if(!reading.address){
    panel.append(graphElement('p',`${reading.subjects} addressable subjects`));
    for(const row of reading.roots)panel.append(graphCard(row));
  }else{
    const trail=graphElement('nav',null,'graph-trail');trail.setAttribute('aria-label','Containing systems');
    for(const row of reading.ancestors){const b=graphElement('button',row.label,'graph-crumb');b.type='button';b.addEventListener('click',()=>graphGo(row.address));trail.append(b);}panel.append(trail);
    panel.append(graphElement('h3',reading.label),graphElement('small',reading.address,'graph-address'));
    if(reading.children.length){panel.append(graphElement('h2','Holds'));for(const row of reading.children)panel.append(graphCard(row));}
    if(reading.endpoints?.length){panel.append(graphElement('h2','Endpoints'));for(const endpoint of reading.endpoints){panel.append(graphElement('small',endpoint.end==='a'?'A endpoint':'B endpoint','graph-source'));panel.append(endpoint.free?graphElement('p','Free end'):graphCard(endpoint));}}
    if(reading.relations.length){panel.append(graphElement('h2','Relations'));for(const row of reading.relations)panel.append(graphCard(row));}
    if(reading.kind==='dependency')panel.append(graphElement('p','Declared requirement, not a delivery channel.','graph-frontier'));
    for(const field of reading.fields){
      const block=graphElement('section',null,'graph-field'),label=graphElement('div',null,'graph-field-heading');
      label.append(graphElement('b',field.axis.replaceAll('_',' ')),graphElement('small',field.basis));block.append(label);
      block.append(field.status==='absent'?graphElement('span','Not supplied','graph-absent'):graphValue(field.value));
      block.append(graphSourceLink(field,reading.source));panel.append(block);
    }
  }
  if(reading.gaps.length){panel.append(graphElement('h2','Unresolved'));for(const gap of reading.gaps){const block=graphElement('div',null,'graph-gap');block.append(graphElement('b',gap.code.replaceAll('_',' ')),graphElement('p',gap.message));panel.append(block);}}
}
