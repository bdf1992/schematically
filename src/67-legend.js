'use strict';
// 0.1 concern: the legend (NOTATION-MODEL.md §5). Derived, never authored by hand: what the
// notation's marks, colours, glyphs, signal shapes and sections mean, for what this document
// uses. A document may name a colour category or hide an entry; it may not add one it does
// not use. Shown as a panel in the editor and as a block beside a picture, never over it.

const legendPanel=document.getElementById('legendPanel');
const legendState={open:false};

function legendSlotName(slot,doc=diagram,notation=activeNotation()){
  const key=slot>=6?`C${slot-5}`:`M${slot+1}`;
  return doc.legend?.names?.[key]||(notation.categories||[]).find(c=>c.slot===key)?.name||null;
}
function legendEntries(doc=diagram){
  const notation=activeNotation(),hide=new Set(Array.isArray(doc.legend?.hide)?doc.legend.hide.map(String):[]),out=[];
  const add=e=>{if(!hide.has(e.id))out.push(e)};
  const visible=nodes.filter(n=>!isEffectivelyHidden(n));
  // Marks: what the canvas draws on its own.
  const wired=new Set();for(const w of wires){if(w.a)wired.add(`${w.a}|${w.aSide}`);if(w.b)wired.add(`${w.b}|${w.bSide}`)}
  const flows=new Set();
  for(const n of visible)if(componentForm(n).dimension===2)for(const p of componentAttachmentPoints(n))if(wired.has(`${n.id}|${p.compatId}`))flows.add(activePortChannel(p.config||{}).flow||'duplex');
  if(flows.has('out')||flows.has('duplex'))add({id:'mark:out',kind:'mark',sample:{mark:'out'},label:'Out',meaning:'Where work leaves a card'});
  if(flows.has('in')||flows.has('duplex'))add({id:'mark:in',kind:'mark',sample:{mark:'in'},label:'In',meaning:'Where work arrives'});
  if(flows.has('control'))add({id:'mark:control',kind:'mark',sample:{mark:'control'},label:'Control',meaning:'An input that enables or gates'});
  if(workspace.querySelector('.junction-dot'))add({id:'mark:junction',kind:'mark',sample:{mark:'junction'},label:'Junction',meaning:'Wires joined at one point'});
  if(workspace.querySelector('.wire-group path.wire[d*=" A "]'))add({id:'mark:hop',kind:'mark',sample:{mark:'hop'},label:'Crossing',meaning:'Wires cross without joining'});
  // Colours: the categorical slots in use, with their names when the notation or document gives one.
  const slots=new Set();
  for(const n of visible){const c=componentConfig(n);for(const s of [c.colorSlot,c.presentation?.interiorColorSlot])if(Number.isInteger(s)&&s>=6)slots.add(s)}
  for(const w of wires){const s=w.config?.colorSlot;if(Number.isInteger(s)&&s>=6)slots.add(s)}
  for(const s of [...slots].sort((a,b)=>a-b))add({id:`colour:C${s-5}`,kind:'colour',sample:{colour:slotColor(s)},label:legendSlotName(s,doc,notation)||`Colour ${s-5}`,meaning:legendSlotName(s,doc,notation)?'':'Unnamed: name it in document.legend.names'});
  // Glyphs: each one used, as the notation titles and explains it.
  const used=[...new Set(visible.filter(n=>!isPrimitiveSymbol(n.symbolId)&&n.symbolId!=='blank').map(n=>n.symbolId))];
  const clocked=visible.some(n=>componentConfig(n).signal?.clock);
  for(const id of used){if(id==='clock'&&clocked)continue;const g=notation.glyphs?.[id];add({id:`glyph:${id}`,kind:'glyph',sample:{glyph:id},label:g?.title||sentenceCase(byId(id)?.name||id),meaning:g?.meaning||byId(id)?.meaning||''})}
  // Signal shapes: the clock waves and level kinds a run would show.
  const waves=new Set(),kinds=new Set();
  for(const n of visible){const sig=componentConfig(n).signal;if(!sig)continue;if(sig.clock)waves.add(sig.clock.wave||'square');if(sig.kind)kinds.add(sig.kind)}
  for(const w of waves)add({id:`signal:${w}`,kind:'signal',sample:{glyph:w==='square'?'clock':`clock-${w}`},label:`${sentenceCase(w)} clock`,meaning:w==='square'?'Binary: high or low':'Continuous: 0 to 1'});
  if(kinds.has('continuous')&&!waves.size)add({id:'signal:continuous',kind:'signal',sample:{mark:'meter'},label:'Continuous level',meaning:'A value from 0 to 1'});
  // Sections: each preset in use.
  const presets=SovSchematicData.SECTION_PRESETS||{},sections=new Set();
  for(const n of [...visible,...wires]){const sec=n.form?.section;if(!sec)continue;const dim=n.a!==undefined?1:2;
    const name=Object.keys(presets).filter(k=>SovSchematicData.sectionPreset(k,dim)).find(k=>JSON.stringify(SovSchematicData.normalizeSection(SovSchematicData.sectionPreset(k,dim),dim))===JSON.stringify(SovSchematicData.normalizeSection(sec,dim)));sections.add(name||`${sec.lines?.length||1} lines`)}
  const describe={disk:'Solid, no inside',circle:'A line around space',section:'A skin around space',coated:'A skin around solid','double-wall':'Two skins with a gap',line:'One line',strip:'A solid band',lanes:'Two lines with space between',pipe:'Walls around a bore'};
  for(const s of sections)add({id:`section:${s}`,kind:'section',sample:{section:s},label:sentenceCase(s.replace('-',' ')),meaning:describe[s]||''});
  return out;
}
// A sample for an entry, as SVG markup in a 28 x 18 box.
function legendSampleMarkup(e,{ink='currentColor'}={}){
  const s=e.sample||{};
  if(s.glyph)return `<use href="#sym-${s.glyph}" x="0" y="0" width="28" height="18" style="color:${ink}"/>`;
  if(s.colour)return `<rect x="4" y="3" width="20" height="12" rx="3" style="fill:${s.colour}"/>`;
  if(s.mark==='out'||s.mark==='in'||s.mark==='control'){const c=getComputedStyle(document.documentElement).getPropertyValue(s.mark==='out'?'--accent-out':s.mark==='in'?'--accent-in':'--canvas-muted').trim()||ink;return `<line x1="2" y1="9" x2="26" y2="9" style="stroke:${ink};stroke-width:2"/><rect x="12" y="3" width="4" height="12" rx="1.2" style="fill:${c}"/>`}
  if(s.mark==='junction')return `<line x1="2" y1="9" x2="26" y2="9" style="stroke:${ink};stroke-width:2"/><line x1="14" y1="9" x2="14" y2="17" style="stroke:${ink};stroke-width:2"/><circle cx="14" cy="9" r="3.4" style="fill:${ink}"/>`;
  if(s.mark==='hop')return `<line x1="14" y1="1" x2="14" y2="17" style="stroke:${ink};stroke-width:2"/><path d="M2 11 H8 A6 6 0 0 1 20 11 H26" style="fill:none;stroke:${ink};stroke-width:2"/>`;
  if(s.mark==='meter')return `<rect x="3" y="6" width="22" height="6" rx="3" style="fill:none;stroke:${ink}"/><rect x="3" y="6" width="13" height="6" rx="3" style="fill:${ink}"/>`;
  if(s.section){
    // The section itself, scaled into the sample: nested lines with its solid bands filled.
    const two=SovSchematicData.sectionPreset(s.section,2),one=two?null:SovSchematicData.sectionPreset(s.section,1),sec=SovSchematicData.normalizeSection(two||one,two?2:1);
    if(!sec)return `<rect x="3" y="2" width="22" height="14" rx="3" style="fill:none;stroke:${ink};stroke-width:1.5"/>`;
    const solid=dark=>'#BDBAB2',total=sec.bands.reduce((a,b)=>a+b.thickness,0),k=total?Math.min(.22,5/total):0,out=[];
    if(two){let inset=0;const core=sec.core?.fill==='solid';
      out.push(`<rect x="3" y="2" width="22" height="14" rx="4" style="fill:${(sec.bands[0]?.fill||sec.core?.fill)==='solid'?solid():'none'};fill-opacity:.55;stroke:${ink};stroke-width:1.3"/>`);
      sec.bands.forEach((b,i)=>{inset+=b.thickness*k;const next=sec.bands[i+1]?.fill||sec.core?.fill;out.push(`<rect x="${3+inset}" y="${2+inset}" width="${22-2*inset}" height="${14-2*inset}" rx="${Math.max(1,4-inset)}" style="fill:${next==='solid'?solid():'#FFFFFF'};fill-opacity:${next==='solid'?.55:.9};stroke:${ink};stroke-width:1"/>`)});
      if(!sec.bands.length&&core)out[0]=`<rect x="3" y="2" width="22" height="14" rx="4" style="fill:${solid()};fill-opacity:.55;stroke:${ink};stroke-width:1.3"/>`;
    }else{const tk=Math.min(12,Math.max(2,total*.5));let yy=9-tk/2;out.push(`<line x1="2" x2="26" y1="${yy}" y2="${yy}" style="stroke:${ink};stroke-width:1.2"/>`);
      for(const b of sec.bands){const h=tk*(b.thickness/Math.max(1,total));if(b.fill==='solid')out.push(`<rect x="2" y="${yy}" width="24" height="${h}" style="fill:${solid()};fill-opacity:.7"/>`);yy+=h;out.push(`<line x1="2" x2="26" y1="${yy}" y2="${yy}" style="stroke:${ink};stroke-width:1.2"/>`)}
      if(!sec.bands.length)out[0]=`<line x1="2" x2="26" y1="9" y2="9" style="stroke:${ink};stroke-width:2"/>`;}
    return out.join('');
  }
  return '';
}
function renderLegendPanel(){
  if(!legendPanel)return;
  const entries=legendEntries();legendPanel.hidden=!legendState.open||!entries.length;if(legendPanel.hidden)return;
  legendPanel.replaceChildren();
  const head=document.createElement('div');head.className='legend-head';head.textContent=`Legend · ${activeNotation().name||activeNotation().id}`;legendPanel.appendChild(head);
  for(const e of entries){
    const row=document.createElement('div');row.className='legend-row';row.dataset.entry=e.id;
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 28 18');svg.setAttribute('width','28');svg.setAttribute('height','18');svg.innerHTML=legendSampleMarkup(e);
    const label=document.createElement('b');label.textContent=e.label;const meaning=document.createElement('span');meaning.textContent=e.meaning;
    row.append(svg,label,meaning);legendPanel.appendChild(row);
  }
}
function setLegendOpen(open){legendState.open=!!open;document.getElementById('legendBtn')?.classList.toggle('active',legendState.open);renderLegendPanel();return legendState.open}
document.getElementById('legendBtn')?.addEventListener('click',()=>setLegendOpen(!legendState.open));

// The legend as a picture block: rows in columns, under the drawing and any narration. Each
// entry is its sample, its label, and its meaning on the line below, cut to fit its column.
function appendLegendBlock(svg,{x,y,w,ink,muted,dark}){
  const NS='http://www.w3.org/2000/svg',entries=legendEntries();if(!entries.length)return 0;
  const colW=Math.max(230,Math.min(320,(w-48)/Math.max(1,Math.floor((w-48)/260)))),cols=Math.max(1,Math.floor((w-48)/colW)),rowH=34,rows=Math.ceil(entries.length/cols);
  const fit=(text,px)=>{const max=Math.floor((colW-44)/(px*.56));return text.length>max?text.slice(0,Math.max(1,max-1)).replace(/\s+\S*$/,'')+'…':text};
  const g=document.createElementNS(NS,'g');g.setAttribute('class','picture-legend');
  const title=document.createElementNS(NS,'text');title.setAttribute('x',String(x+24));title.setAttribute('y',String(y+14));
  title.setAttribute('style',`font-family:ui-sans-serif,system-ui,sans-serif;font-size:11px;font-weight:600;fill:${muted}`);title.textContent='Legend';g.appendChild(title);
  const rule=document.createElementNS(NS,'line');rule.setAttribute('x1',String(x+24));rule.setAttribute('x2',String(x+w-24));rule.setAttribute('y1',String(y+22));rule.setAttribute('y2',String(y+22));rule.setAttribute('style',`stroke:${muted};stroke-opacity:.35;stroke-width:1`);g.appendChild(rule);
  entries.forEach((e,i)=>{
    const c=Math.floor(i/rows),r=i%rows,ex=x+24+c*colW,ey=y+32+r*rowH;
    const sample=document.createElementNS(NS,'g');sample.setAttribute('transform',`translate(${ex} ${ey+2})`);sample.innerHTML=legendSampleMarkup(e,{ink});g.appendChild(sample);
    const t=document.createElementNS(NS,'text');t.setAttribute('x',String(ex+36));t.setAttribute('y',String(ey+11));
    t.setAttribute('style',`font-family:ui-sans-serif,system-ui,sans-serif;font-size:11px;font-weight:600;fill:${ink}`);t.textContent=fit(e.label,11);g.appendChild(t);
    if(e.meaning){const m=document.createElementNS(NS,'text');m.setAttribute('x',String(ex+36));m.setAttribute('y',String(ey+24));
      m.setAttribute('style',`font-family:ui-sans-serif,system-ui,sans-serif;font-size:9.5px;fill:${muted}`);m.textContent=fit(e.meaning,9.5);g.appendChild(m)}
  });
  svg.appendChild(g);
  return 32+rows*rowH+6;
}
