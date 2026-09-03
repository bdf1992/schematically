'use strict';
// 0.1 concern: the editor draws its own dropdown lists.
//
// A `<select>` popup is a window the browser opens, not part of the page. `color-scheme`
// tells the browser which way to paint it and that is as far as the page's say goes:
// the list is drawn outside the document, it cannot carry the app's type, spacing or
// tokens, and on some platforms it stays light over a dark editor whatever the page
// declares. In an editor whose whole job is a dark canvas, that one control is where the
// theme visibly stops.
//
// So the list is drawn here instead. The `<select>` stays exactly where it is and stays
// the source of truth - it holds the value, it fires `change`, every existing listener
// is untouched - and this only replaces the picture of the list. Nothing else in the
// editor knows the difference.
//
// It works by delegation rather than by wiring each control, so a `<select>` whose
// options are built at runtime (the Pattern list) is covered without being registered.

const selectMenu=document.createElement('div');
selectMenu.className='select-menu';
selectMenu.setAttribute('role','listbox');
selectMenu.hidden=true;
document.body.appendChild(selectMenu);

let selectMenuOwner=null;

function closeSelectMenu(){
  if(!selectMenuOwner)return;
  selectMenu.hidden=true;
  selectMenu.replaceChildren();
  selectMenuOwner.classList.remove('menu-open');
  selectMenuOwner=null;
}

function commitSelectMenu(option){
  const owner=selectMenuOwner;
  if(!owner||option.disabled)return;
  closeSelectMenu();
  if(owner.value===option.value){owner.focus({preventScroll:true});return}
  owner.value=option.value;
  // The same events the browser's own list would have fired, so nothing downstream has
  // to know the list was drawn here.
  owner.dispatchEvent(new Event('input',{bubbles:true}));
  owner.dispatchEvent(new Event('change',{bubbles:true}));
  owner.focus({preventScroll:true});
}

function buildSelectMenu(select){
  selectMenu.replaceChildren();
  for(const child of select.children){
    if(child.tagName==='OPTGROUP'){
      const heading=document.createElement('div');
      heading.className='select-menu-group';
      heading.textContent=child.label;
      selectMenu.appendChild(heading);
      for(const option of child.children)selectMenu.appendChild(selectMenuRow(select,option));
      continue;
    }
    if(child.tagName==='OPTION')selectMenu.appendChild(selectMenuRow(select,child));
  }
}

function selectMenuRow(select,option){
  const row=document.createElement('button');
  row.type='button';
  row.className='select-menu-item'+(option.value===select.value?' current':'');
  row.setAttribute('role','option');
  row.setAttribute('aria-selected',option.value===select.value?'true':'false');
  row.disabled=option.disabled;
  row.textContent=option.textContent;
  if(option.title)row.title=option.title;
  row.addEventListener('click',()=>commitSelectMenu(option));
  return row;
}

// Placed under its control, flipped above when there is no room below, and never off
// the right or bottom edge - the same rules the browser's own list follows.
function positionSelectMenu(select){
  const anchor=select.getBoundingClientRect();
  selectMenu.style.visibility='hidden';
  selectMenu.hidden=false;
  selectMenu.style.minWidth=`${Math.round(anchor.width)}px`;
  const menu=selectMenu.getBoundingClientRect();
  const gap=4;
  const below=window.innerHeight-anchor.bottom-gap;
  const flip=menu.height>below&&anchor.top-gap>below;
  const top=flip?Math.max(gap,anchor.top-gap-menu.height):anchor.bottom+gap;
  const left=Math.max(gap,Math.min(window.innerWidth-menu.width-gap,anchor.left));
  selectMenu.style.top=`${Math.round(top)}px`;
  selectMenu.style.left=`${Math.round(left)}px`;
  selectMenu.style.maxHeight=`${Math.round(Math.max(120,(flip?anchor.top:window.innerHeight-anchor.bottom)-gap*2))}px`;
  selectMenu.style.visibility='visible';
}

function openSelectMenu(select){
  closeSelectMenu();
  if(!select.options.length)return;
  selectMenuOwner=select;
  select.classList.add('menu-open');
  buildSelectMenu(select);
  positionSelectMenu(select);
  (selectMenu.querySelector('.select-menu-item.current')||selectMenu.querySelector('.select-menu-item:not(:disabled)'))
    ?.focus({preventScroll:true});
}

// Pointer down rather than click: the browser opens its own list on pointer down, so
// this has to get there first or both lists appear.
document.addEventListener('pointerdown',event=>{
  const select=event.target instanceof Element?event.target.closest('select'):null;
  if(!select||select.disabled){if(!selectMenu.contains(event.target))closeSelectMenu();return}
  event.preventDefault();
  if(selectMenuOwner===select){closeSelectMenu();return}
  openSelectMenu(select);
},true);

// A keyboard user still gets the native list, which is the one their screen reader and
// their platform already know. Only the pointer path is replaced.
document.addEventListener('keydown',event=>{
  if(event.key==='Escape'&&selectMenuOwner){
    const owner=selectMenuOwner;
    closeSelectMenu();
    owner.focus({preventScroll:true});
    event.stopPropagation();
  }
},true);

window.addEventListener('resize',closeSelectMenu);
window.addEventListener('blur',closeSelectMenu);
// Any scroll under an open list, including the palette and the inspector.
document.addEventListener('scroll',closeSelectMenu,true);
