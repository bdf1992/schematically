'use strict';
// 0.1 Beta concern: Runtime state, DOM handles, palette/color kernel.

const SYMBOLS = [{"id":"blank","name":"BLANK","family":"UNSET","role":"incomplete","meaning":"Incomplete component. Choose its type.","verbs":[],"properties":["incomplete","type-required"],"diagram_class":"COMPONENT"},{"id":"ground","name":"GROUND","family":"PASSIVE","role":"reference","meaning":"Reference point used to resolve meaning, state, or authority.","verbs":["resolve","reference"],"properties":["non-authoritative-by-itself"],"diagram_class":"REFERENCE"},{"id":"point","name":"POINT","family":"PRIMITIVE","role":"attachment","meaning":"0D attachment. Sticks to a Path, a Plane boundary, or a Wire; Wires end on Points.","verbs":["attach","enter","exit"],"properties":["addressable","0d"],"diagram_class":"BOUNDARY"},{"id":"port","name":"PORT","family":"PASSIVE","role":"boundary","meaning":"Legacy alias of POINT. Documents normalize it to point.","verbs":["enter","exit"],"properties":["addressable","legacy-alias"],"diagram_class":"BOUNDARY"},{"id":"path","name":"PATH","family":"PRIMITIVE","role":"carrier","meaning":"1D route with start and end. Hosts Points along its length. It does not imply permission or success.","verbs":["carry"],"properties":["direction-neutral","1d"],"diagram_class":"CONNECTION"},{"id":"plane","name":"PLANE","family":"PRIMITIVE","role":"surface","meaning":"Bounded 2D region. Hosts Points on its boundary and Components in its interior. A typed Plane is a Component.","verbs":["host","bound"],"properties":["bounded","hosts","2d"],"diagram_class":"SURFACE"},{"id":"join","name":"JOIN","family":"MECHANICAL","role":"connection","meaning":"Paths are connected.","verbs":["join"],"properties":["connected"],"diagram_class":"CONNECTION"},{"id":"cross","name":"CROSS","family":"PASSIVE","role":"connection","meaning":"Paths cross but do not connect.","verbs":["cross"],"properties":["not-connected"],"diagram_class":"CONNECTION"},{"id":"hold","name":"HOLD","family":"PASSIVE","role":"state","meaning":"Keeps bounded state.","verbs":["hold","store"],"properties":["stateful"],"diagram_class":"STATE"},{"id":"buffer","name":"BUFFER","family":"PASSIVE","role":"state","meaning":"Holds flow temporarily, then releases it.","verbs":["buffer","release"],"properties":["temporary-state"],"diagram_class":"STATE"},{"id":"act","name":"ACT","family":"ACTIVE","role":"transform","meaning":"Transforms input into output. Activity does not grant authority.","verbs":["act","transform"],"properties":["agentic","authority-neutral"],"diagram_class":"TRANSFORM"},{"id":"gate","name":"GATE","family":"MECHANICAL","role":"control","meaning":"Passes or refuses flow using a declared condition.","verbs":["check","pass","refuse"],"properties":["conditional","authority-neutral"],"diagram_class":"CONTROL"},{"id":"switch","name":"SWITCH","family":"MECHANICAL","role":"control","meaning":"Opens or closes a path from explicit control.","verbs":["open","close"],"properties":["externally-controlled"],"diagram_class":"CONTROL"},{"id":"limit","name":"LIMIT","family":"PASSIVE","role":"constraint","meaning":"Restricts a flow dimension without judgement.","verbs":["limit"],"properties":["non-judgemental"],"diagram_class":"CONTROL"},{"id":"one-way","name":"ONE-WAY","family":"PASSIVE","role":"direction","meaning":"Allows flow in one direction.","verbs":["pass"],"properties":["directional","non-reciprocal"],"diagram_class":"CONNECTION"},{"id":"return","name":"RETURN","family":"PASSIVE","role":"reciprocity","meaning":"Requires a matching return path.","verbs":["return"],"properties":["reciprocal"],"diagram_class":"CONNECTION"},{"id":"observe","name":"OBSERVE","family":"PASSIVE","role":"evidence","meaning":"Reads evidence from outside the action path.","verbs":["observe"],"properties":["independent-read"],"diagram_class":"EVIDENCE"},{"id":"receipt","name":"RECEIPT","family":"PASSIVE","role":"evidence","meaning":"Durable evidence emitted by a crossing or action.","verbs":["record","return"],"properties":["durable","evidentiary"],"diagram_class":"EVIDENCE"},{"id":"authority","name":"AUTHORITY","family":"PASSIVE","role":"control-reference","meaning":"Typed, scoped permission supplied as a control input.","verbs":["grant","scope"],"properties":["typed","scoped"],"diagram_class":"REFERENCE"},{"id":"refuse","name":"REFUSE","family":"MECHANICAL","role":"termination","meaning":"Ends an attempted path explicitly.","verbs":["refuse","stop"],"properties":["explicit-terminal"],"diagram_class":"TERMINATION"}];
// Primitives are the dimensional basis (0D / 1D / 2D). Components are typed 2D forms
// whose attachment defaults are template data; a typed Plane is an ordinary Component.
const GROUPS = {"Primitives": ["point","path","plane"], "Components": ["blank","act","hold","buffer","gate","switch","limit","receipt","observe"]};
const PRIMITIVE_SYMBOL_IDS=new Set(GROUPS.Primitives);
function isPrimitiveSymbol(id){return PRIMITIVE_SYMBOL_IDS.has(String(id||''))}
const workspace = document.getElementById('workspace');
const nodesG = document.getElementById('nodes');
const wiresG = document.getElementById('wires');
const ghostLayer = document.getElementById('ghostLayer');
const palette = document.getElementById('palette');
const statusEl = document.getElementById('status');
const componentDetail=document.getElementById('componentDetail'),connectionDetail=document.getElementById('connectionDetail'),portDetail=document.getElementById('portDetail');
const paletteDropLayer=document.getElementById('paletteDropLayer');
const selectionBar=document.getElementById('selectionBar');
const componentBarFields=document.getElementById('componentBarFields');
const connectionBarFields=document.getElementById('connectionBarFields');
const barComponentType=document.getElementById('barComponentType');
const barComponentLabel=document.getElementById('barComponentLabel');
const barComponentColorSlot=document.getElementById('barComponentColorSlot');
const barComponentSignalMode=document.getElementById('barComponentSignalMode');
const barFormState=document.getElementById('barFormState');
const barSelectionSettings=document.getElementById('barSelectionSettings');
const selectionSettingsPanel=document.getElementById('selectionSettingsPanel');
const componentSettingsFields=document.getElementById('componentSettingsFields');
const wireSettingsFields=document.getElementById('wireSettingsFields');
const portSettingsFields=document.getElementById('portSettingsFields');
const visualGraphicMode=document.getElementById('visualGraphicMode');
const visualLabelMode=document.getElementById('visualLabelMode');
const visualWidth=document.getElementById('visualWidth');
const visualHeight=document.getElementById('visualHeight');
const visualInteriorColor=document.getElementById('visualInteriorColor');
const visualText=document.getElementById('visualText');
const visualSvgRow=document.getElementById('visualSvgRow');
const visualSvgMarkup=document.getElementById('visualSvgMarkup');
const formSettings=document.getElementById('formSettings');
const formDimension=document.getElementById('formDimension');
const formAttachments=document.getElementById('formAttachments');
const formMaterial=document.getElementById('formMaterial');
const formBodyThickness=document.getElementById('formBodyThickness');
const formInteriorState=document.getElementById('formInteriorState');
const formFrameMode=document.getElementById('formFrameMode');
const formFrameThickness=document.getElementById('formFrameThickness');
const formFrameDepth=document.getElementById('formFrameDepth');
const iForm=document.getElementById('iForm');
const iBody=document.getElementById('iBody');
const iFrame=document.getElementById('iFrame');
const portBarFields=document.getElementById('portBarFields');
const barPortSide=document.getElementById('barPortSide');
const barPortColorSlot=document.getElementById('barPortColorSlot');
const barPortFlow=document.getElementById('barPortFlow');
const barPortAccess=document.getElementById('barPortAccess');
const colorSlotPanel=document.getElementById('colorSlotPanel');
const barConnectionDirection=document.getElementById('barConnectionDirection');
const barConnectionReciprocity=document.getElementById('barConnectionReciprocity');
const barWirePrimaryOperation=document.getElementById('barWirePrimaryOperation');
const barWireReturnOperation=document.getElementById('barWireReturnOperation');
const barWirePrimaryOperationLabel=document.getElementById('barWirePrimaryOperationLabel');
const barWireReturnOperationLabel=document.getElementById('barWireReturnOperationLabel');
const barConnectionLabel=document.getElementById('barConnectionLabel');
const barWireOutLabel=document.getElementById('barWireOutLabel');
const barWireOutMarker=document.getElementById('barWireOutMarker');
const barWireOutColor=document.getElementById('barWireOutColor');
const barWireInLabel=document.getElementById('barWireInLabel');
const barWireInMarker=document.getElementById('barWireInMarker');
const barWireInColor=document.getElementById('barWireInColor');
const barAddWirePortBtn=document.getElementById('barAddWirePortBtn');
const barPortLabel=document.getElementById('barPortLabel');
const barPortFace=document.getElementById('barPortFace');
const barPortMarkers=document.getElementById('barPortMarkers');
const barDeleteSelection=document.getElementById('barDeleteSelection');
const zoomOutBtn = document.getElementById('zoomOutBtn');
const zoomInBtn = document.getElementById('zoomInBtn');
const fitBtn = document.getElementById('fitBtn');
const resetZoomBtn = document.getElementById('resetZoomBtn');
const zoomReadout = document.getElementById('zoomReadout');
const pLabel=document.getElementById('pLabel');
const iSignalMode=document.getElementById('iSignalMode');
const iParent=document.getElementById('iParent');
const iScope=document.getElementById('iScope');
const iContains=document.getElementById('iContains');
const pFace=document.getElementById('pFace');
const pAccess=document.getElementById('pAccess');
const cOperations=document.getElementById('cOperations');
const paletteBtn = document.getElementById('paletteBtn');
const paletteSettings = document.getElementById('paletteSettings');
const colorThemeInput = document.getElementById('colorThemeInput');
const colorPaletteInput = document.getElementById('colorPaletteInput');
const monoPalettePreview = document.getElementById('monoPalettePreview');
const palettePreview = document.getElementById('palettePreview');
const diffuseSignalsInput = document.getElementById('diffuseSignalsInput');
const customPaletteEditor = document.getElementById('customPaletteEditor');
const customPaletteSwatches = document.getElementById('customPaletteSwatches');
const gridBtn = document.getElementById('gridBtn');
const gridSettings = document.getElementById('gridSettings');
const gridVisibleInput = document.getElementById('gridVisibleInput');
const gridSnapInput = document.getElementById('gridSnapInput');
const gridSizeInput = document.getElementById('gridSizeInput');
const flowBtn = document.getElementById('flowBtn');
const fileBtn=document.getElementById('fileBtn');
const fileMenu=document.getElementById('fileMenu');
const fileNameReadout=document.getElementById('fileNameReadout');
const fileStateReadout=document.getElementById('fileStateReadout');
const fileNewBtn=document.getElementById('fileNewBtn');
const fileOpenBtn=document.getElementById('fileOpenBtn');
const fileOpenInput=document.getElementById('fileOpenInput');
const fileSaveBtn=document.getElementById('fileSaveBtn');
const fileSaveAsBtn=document.getElementById('fileSaveAsBtn');
const fileExportSvgBtn=document.getElementById('fileExportSvgBtn');
const fileExportPakBtn=document.getElementById('fileExportPakBtn');
const fileRestoreRecoveryBtn=document.getElementById('fileRestoreRecoveryBtn');
const documentRevisionReadout=document.getElementById('documentRevisionReadout');

const GLOBAL_CANVAS_ID=SovSchematicData.GLOBAL_CANVAS_ID;
const diagram=SovSchematicData.makeDocument({id:'schematic-1'});
const nodes=diagram.components,wires=diagram.wires;
let selected=null,seq=1;
let wireDrag=null;
const BASE_VIEW = {x:0,y:0,w:1200,h:760};
let camera = {...BASE_VIEW};
const MIN_ZOOM = .28;
const MAX_ZOOM = 4.0;
let showFlow=true;
const ROUTE_SWITCH_MARGIN = 72;      // alternative must beat latched route by this much
const ROUTE_SNAP_GRID = 12;          // route channels move in coarse increments
const ROUTE_RELEASE_DISTANCE = 18;   // keep an old channel until movement exceeds this
const routeCache = new Map();        // wire index -> {points, score, signature, anchor}
let activeNodeDrag = null;
let settleTimer = null;
const arrowPoseCache = new Map();
const dragRouteSnapshots = new Map();
const wireHostPoseCache = new Map(); // component id -> derived {x,y,angle,wireId,t}; never persisted
const ROUTE_SETTLE_DELAY = 140;

let canvasGridSize = 24;
let canvasGridVisible = true;
let canvasSnapEnabled = true;
let activeNodeDragState = null;
let keyboardMoveNodeId = null;
let keyboardSettleTimer = null;
let canvasKeyboardActive = false;
let spacePanHeld=false;
let panDrag=null;

const LIGHT_SURFACE_MONO=['#202020','#353535','#4B4B4B','#616161','#747474','#878787'];
const LIGHT_SURFACE_MONO_DEEP=['#0D0D0D','#171717','#222222','#2E2E2E','#3A3A3A','#464646'];
const DARK_SURFACE_MONO=['#F2F2EE','#DDDDD8','#C8C8C2','#B3B3AD','#9E9E98','#898984'];
const DARK_SURFACE_MONO_BRIGHT=['#FFFFFF','#F0F0EB','#E1E1DB','#D2D2CC','#C3C3BD','#B4B4AE'];
const BASE_PALETTES={
  spectrum:['#D34E4E','#D99032','#79A948','#3EA7A0','#507CCB','#8A5BC0'],
  cool:['#3C7EA6','#3AA2A0','#54A58B','#6589BF','#6D67B1','#8A69A7'],
  warm:['#C34B48','#D36F3E','#D7983D','#B77A4C','#A85E65','#91546F'],
  earth:['#8A6348','#A3814D','#7E8E55','#5F8677','#687C86','#806C78']
};
const DARK_SURFACE_PALETTES={
  spectrum:['#FF7A7D','#E8AA58','#9AC86C','#62C9C1','#82A9F2','#B88CE5'],
  cool:['#74B8E2','#69D0CB','#82C9AE','#91AFE8','#A19BE1','#B58FC8'],
  warm:['#F37C78','#ED966A','#E8B660','#D6A071','#CE858E','#C77F9E'],
  earth:['#C99B79','#C5A774','#A6B57C','#86AD9D','#91A5AF','#A996A2']
};
const DEFAULT_CUSTOM_PALETTE=['#C84E64','#DB8750','#B7A647','#58A27C','#4E86BE','#8B63B2'];

const colorEngine={
  theme:'pastel',
  palette:'spectrum',
  custom:[...DEFAULT_CUSTOM_PALETTE],
  diffuse:true
};
diagram.colorEngine=colorEngine;

function hexRgb(hex){
  const h=(hex||'#000000').replace('#','');
  return {r:parseInt(h.slice(0,2),16)||0,g:parseInt(h.slice(2,4),16)||0,b:parseInt(h.slice(4,6),16)||0};
}
function rgbHex({r,g,b}){
  const c=v=>Math.max(0,Math.min(255,Math.round(v))).toString(16).padStart(2,'0');
  return '#'+c(r)+c(g)+c(b);
}
function mixHex(colors,weights=null){
  if(!colors.length)return '#777777';
  let rs=0,gs=0,bs=0,total=0;
  colors.forEach((hex,i)=>{
    const w=weights?.[i]??1,{r,g,b}=hexRgb(hex);
    rs+=r*w;gs+=g*w;bs+=b*w;total+=w;
  });
  return rgbHex({r:rs/Math.max(total,.0001),g:gs/Math.max(total,.0001),b:bs/Math.max(total,.0001)});
}
function surfaceAppearance(){
  const explicit=document.documentElement?.dataset?.appearance;
  if(explicit==='dark'||explicit==='light')return explicit;
  try{return matchMedia?.('(prefers-color-scheme: dark)')?.matches?'dark':'light'}catch(_){return 'light'}
}
function canvasTone(theme=colorEngine.theme,appearance=surfaceAppearance()){
  if(appearance==='dark')return theme==='reading'?'#121416':'#17191B';
  if(theme==='pastel')return '#FBFAF7';
  if(theme==='subtle')return '#FAFAF8';
  return '#FFFFFF';
}
function channelLuminance(v){
  const x=v/255;
  return x<=.04045?x/12.92:Math.pow((x+.055)/1.055,2.4);
}
function relativeLuminance(hex){
  const {r,g,b}=hexRgb(hex);
  return .2126*channelLuminance(r)+.7152*channelLuminance(g)+.0722*channelLuminance(b);
}
function contrastRatio(a,b){
  const A=relativeLuminance(a),B=relativeLuminance(b);
  return (Math.max(A,B)+.05)/(Math.min(A,B)+.05);
}
function themeContrastFloor(theme=colorEngine.theme){
  if(theme==='pastel')return 3.25;
  if(theme==='subtle')return 3.5;
  return 4.0;
}
function ensureContrast(hex,bg=canvasTone(),minimum=themeContrastFloor()){
  if(contrastRatio(hex,bg)>=minimum)return hex;
  const toward=relativeLuminance(bg)<.35?'#FFFFFF':'#111111';
  let lo=0,hi=1,best=hex;
  for(let i=0;i<28;i++){
    const t=(lo+hi)/2;
    const candidate=mixHex([hex,toward],[1-t,t]);
    if(contrastRatio(candidate,bg)>=minimum){best=candidate;hi=t}
    else lo=t;
  }
  return best;
}
function themeColor(hex,theme=colorEngine.theme,appearance=surfaceAppearance()){
  let candidate,minimum;
  if(appearance==='dark'){
    if(theme==='pastel')candidate=mixHex([hex,'#FFFFFF'],[.90,.10]);
    else if(theme==='subtle')candidate=mixHex([hex,'#D5D5D0'],[.88,.12]);
    else candidate=mixHex([hex,'#FFFFFF'],[.95,.05]);
  }else if(theme==='pastel')candidate=mixHex([hex,'#FFFFFF'],[.88,.12]);
  else if(theme==='subtle')candidate=mixHex([hex,'#7D7D78'],[.80,.20]);
  else candidate=mixHex([hex,'#111111'],[.94,.06]);
  minimum=themeContrastFloor(theme);
  return ensureContrast(candidate,canvasTone(theme,appearance),minimum);
}
function activeMonoPalette(){
  const base=surfaceAppearance()==='dark'?DARK_SURFACE_MONO:LIGHT_SURFACE_MONO;
  return base.map(c=>themeColor(c));
}
function activeColorPalette(){
  const dark=surfaceAppearance()==='dark';
  const base=colorEngine.palette==='mono'
    ? (dark?DARK_SURFACE_MONO_BRIGHT:LIGHT_SURFACE_MONO_DEEP)
    : colorEngine.palette==='custom'
      ? colorEngine.custom
      : (dark?(DARK_SURFACE_PALETTES[colorEngine.palette]||DARK_SURFACE_PALETTES.spectrum):(BASE_PALETTES[colorEngine.palette]||BASE_PALETTES.spectrum));
  return base.map(c=>themeColor(c));
}
let activePaletteCacheKey=null;
let activePaletteCacheValue=null;
function activePalette(){
  const key=[surfaceAppearance(),colorEngine.theme,colorEngine.palette,...colorEngine.custom].join('|');
  if(activePaletteCacheKey===key&&activePaletteCacheValue)return activePaletteCacheValue;
  activePaletteCacheKey=key;
  activePaletteCacheValue=Object.freeze([...activeMonoPalette(),...activeColorPalette()]);
  return activePaletteCacheValue;
}
function normalizeSlot(v,fallback=0){
  const n=Number(v);
  return Number.isInteger(n)?Math.max(0,Math.min(11,n)):fallback;
}
function slotColor(slot){return activePalette()[normalizeSlot(slot)]}
function nearestSlot(hex){
  const c=hexRgb(hex);let best=0,bestD=Infinity;
  activePalette().forEach((h,i)=>{
    const q=hexRgb(h),d=(c.r-q.r)**2+(c.g-q.g)**2+(c.b-q.b)**2;
    if(d<bestD){bestD=d;best=i}
  });
  return best;
}
function lighten(hex,amount=.88){return mixHex([hex,'#FFFFFF'],[1-amount,amount])}
function darken(hex,amount=.72){return mixHex([hex,'#111315'],[1-amount,amount])}
function componentSurfaceFill(hex,amount=.86){return surfaceAppearance()==='dark'?darken(hex,Math.min(.88,amount*.82)):lighten(hex,amount)}

const DEFAULT_COMPONENT_COLOR='#171715';
const DEFAULT_WIRE_COLOR='#171715';
const DEFAULT_CHANNEL='signal';
let wirePartSeq=1;
let renderEpoch=1;
const PALETTE_DRAG_THRESHOLD=10,PALETTE_HOLD_DELAY=220;
let paletteDrag=null;
const PORT_DRAG_THRESHOLD=14;
const PORT_DRAG_ARM_DELAY=130;
const BG_PAN_THRESHOLD=6;
const SNAP_RADIUS=34;
