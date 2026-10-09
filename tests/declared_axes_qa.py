"""Declared axes QA (DATA-FORMATS.md "Axes"; API.md "Axes").

A document declares up to three ordered axes in `axes`: [{id, name?, values: [{id, name?}]}]. A
Component or a Wire stores its value on each in `config.axis`: {axisId: valueId}. The field is
semantic: it sits on the record, outside document.layout, and nothing is placed or drawn from it.

Node, on src/05-data-core.js:
  (a) an unnamed axis is read by position (Layer, Phase, Depth) and an unnamed value as its axis's
      name and its position (Layer 1, Layer 2; Stage 1 on an axis named Stage); a stored name wins;
      the stored record keeps no default name;
  (b) every bad `axes` list is AXIS_INVALID, naming the entry and the rule, on load and in setAxes,
      and a refused setAxes leaves the document unchanged;
  (c) create and update of a Component and of a Wire, singly and in a batch, refuse an undeclared
      axis with AXIS_UNKNOWN, an unlisted value with AXIS_VALUE_UNKNOWN and a non-object with
      AXIS_INVALID, each UNKNOWN message listing the declared ids, the document unchanged;
  (d) an update sets a value, merges per key, removes one axis with null and the key with axis null;
      no empty object is stored;
  (e) a file carrying a bad config.axis loads as written and validateDocument reports it per record;
  (f) the field is on the record and not in document.layout; compactComponent, compactWire and
      compactDocument keep it; save then open then save is byte-identical and the hash is the same;
      the hash moves when a value moves;
  (g) readScope and a read return config.axis; readScope returns the named axes;
  (h) setAxes refuses dropping an axis or a value a Component or a Wire still names, with the same
      codes, naming the record; once the record lets go it is admitted; rename and reorder are
      admitted; null removes the key; a stale ifRevision is refused;
  (i) every example loads with no `axes` key, no `config.axis`, no AXIS finding and no `axes` in a
      read; and, against the data core of the merge base, every example gives the same stored text,
      the same hash and the same findings; the examples and goldens are unmodified in the tree.
The server (mcp/server.mjs) on a temporary file, over MCP and HTTP:
  (j) schematic.update, schematic.create and schematic.apply write and refuse the same way;
      schematic.get, schematic.read and schematic.document.get return config.axis; the saved file
      holds it; a restarted server reads it back; schematic.document.replace and PUT
      /api/v1/document refuse a list that drops an axis a record names; schematic.axes.set and
      POST /api/v1/axes are listed (tools/list, mcp/tools.json, MCP.md), refuse with the same codes
      changing nothing (400, and 409 for a stale revision), and a set moves one revision, saves, and
      is taken back by one undo.
Headless Chromium on index.html:
  (k) SovSchematicAPI create, update, get, read, document.get and axes.list/axes.set behave the
      same; one undo takes back a set; saving and opening gives the same text; the exported picture
      has the same elements, classes and text with and without a value; the page logs no errors.
"""
from __future__ import annotations
import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))

AXES = [
    {'id': 'layer', 'values': [{'id': 'l1'}, {'id': 'l2', 'name': 'Service'}]},
    {'id': 'phase', 'name': 'Stage', 'values': [{'id': 'plan'}, {'id': 'build'}]},
    {'id': 'depth', 'values': [{'id': 'd1'}, {'id': 'd2'}]},
]
NAMED = [
    {'id': 'layer', 'name': 'Layer', 'values': [{'id': 'l1', 'name': 'Layer 1'}, {'id': 'l2', 'name': 'Service'}]},
    {'id': 'phase', 'name': 'Stage', 'values': [{'id': 'plan', 'name': 'Stage 1'}, {'id': 'build', 'name': 'Stage 2'}]},
    {'id': 'depth', 'name': 'Depth', 'values': [{'id': 'd1', 'name': 'Depth 1'}, {'id': 'd2', 'name': 'Depth 2'}]},
]
DOC = {
    'schema': 'soveraeign.schematic/document@0.1', 'id': 'declared-axes', 'revision': 0,
    'meta': {'title': 'Ore line', 'updatedAt': '2026-10-09T00:00:00.000Z'},
    'components': [
        {'id': 'ore', 'symbolId': 'act', 'x': 200, 'y': 200, 'config': {'label': 'Ore'}},
        {'id': 'bar', 'symbolId': 'act', 'x': 560, 'y': 200, 'config': {'label': 'Bar'}}],
    'wires': [{'id': 'belt', 'a': 'ore', 'aSide': 'out', 'b': 'bar', 'bSide': 'in', 'config': {'label': 'belt'}}],
    'references': [],
    'axes': AXES,
}
# name -> (axes, text the AXIS_INVALID message must hold)
BAD_AXES = {
    'four axes': ([{'id': 'a', 'values': []}, {'id': 'b', 'values': []}, {'id': 'c', 'values': []}, {'id': 'd', 'values': []}], 'axes holds 4 entries; at most 3'),
    'not an array': ({'layer': ['l1']}, 'axes must be an array'),
    'an entry that is not an object': (['layer'], 'axes[0] must be an object'),
    'an axis with no id': ([{'values': []}], 'axes[0].id must be a non-empty string'),
    'an axis id with whitespace': ([{'id': ' layer', 'values': []}], 'axes[0].id must be a non-empty string'),
    'a repeated axis id': ([{'id': 'a', 'values': []}, {'id': 'a', 'values': []}], 'axes[1].id "a" is already used'),
    'an empty axis name': ([{'id': 'a', 'name': '  ', 'values': []}], 'axes[0].name must be a non-empty string'),
    'an axis name that is a number': ([{'id': 'a', 'name': 3, 'values': []}], 'axes[0].name must be a non-empty string'),
    'an axis with no values list': ([{'id': 'a'}], 'axes[0].values must be an array'),
    'a key outside id, name, values': ([{'id': 'a', 'values': [], 'color': 'red'}], 'axes[0].color is not a field of an axis'),
    'a value that is not an object': ([{'id': 'a', 'values': ['one']}], 'axes[0].values[0] must be an object'),
    'a value with no id': ([{'id': 'a', 'values': [{'name': 'One'}]}], 'axes[0].values[0].id must be a non-empty string'),
    'a repeated value id': ([{'id': 'a', 'values': [{'id': 'v'}]}, {'id': 'b', 'values': [{'id': 'v'}, {'id': 'v'}]}], 'axes[1].values[1].id "v" is already used'),
    'an empty value name': ([{'id': 'a', 'values': [{'id': 'v', 'name': ''}]}], 'axes[0].values[0].name must be a non-empty string'),
    'a value key outside id, name': ([{'id': 'a', 'values': [{'id': 'v', 'x': 40}]}], 'axes[0].values[0].x is not a field of a value'),
}
# name -> (config.axis, code, text the message must hold)
BAD_AXIS = {
    'an undeclared axis': ({'tier': 'l1'}, 'AXIS_UNKNOWN', 'declared: layer, phase, depth'),
    'an unlisted value': ({'layer': 'l9'}, 'AXIS_VALUE_UNKNOWN', 'declared: l1, l2'),
    'a value of another axis': ({'layer': 'plan'}, 'AXIS_VALUE_UNKNOWN', 'declared: l1, l2'),
    'a value that is a number': ({'phase': 1}, 'AXIS_VALUE_UNKNOWN', 'declared: plan, build'),
    'a string': ('l1', 'AXIS_INVALID', 'config.axis must be an object'),
    'a list': (['l1'], 'AXIS_INVALID', 'config.axis must be an object'),
}

NODE = r"""
const fs=require('fs'),path=require('path');
const D=require(process.argv[1]);
const input=JSON.parse(fs.readFileSync(0,'utf8')),out={};
const fresh=(extra={})=>D.makeDocument({...D.clone(input.doc),...extra});
const text=doc=>JSON.stringify(D.compactDocument(doc),null,2)+'\n';
const message=r=>(r.error&&r.error.message)||'';
const find=(doc,id)=>doc.components.find(c=>c.id===id)||doc.wires.find(w=>w.id===id);

// (a) defaults
{const doc=fresh();out.defaults={named:D.documentAxes(doc),stored:doc.axes,valid:D.validateDocument(doc),words:D.AXIS_DEFAULT_NAMES,none:D.documentAxes(D.makeDocument({}))}}

// (b) bad lists: reported on load, refused by setAxes
out.badAxes={};
for(const [name,[axes]] of Object.entries(input.badAxes)){
  const loaded=fresh({axes}),doc=fresh(),before=JSON.stringify(doc),r=D.setAxes(doc,{axes});
  out.badAxes[name]={errors:D.validateDocument(loaded).errors,kept:JSON.stringify(loaded.axes)===JSON.stringify(axes),ok:r.ok,message:message(r),same:JSON.stringify(doc)===before};
}
{const doc=fresh(),before=JSON.stringify(doc),r=D.setAxes(doc,{});out.badAxes['no axes given']={errors:['AXIS_INVALID: axes must be an array'],kept:true,ok:r.ok,message:message(r),same:JSON.stringify(doc)===before}}

// (c) refusals on create and update, single and batch, Component and Wire
out.badAxis={};
for(const [name,[axis]] of Object.entries(input.badAxis)){
  const rows=[];
  const attempts={
    'create component':doc=>D.applyOperation(doc,{op:'create',resource:'component',value:{id:'new',symbolId:'act',x:900,y:200,config:{label:'New',axis}}}),
    'update component':doc=>D.applyOperation(doc,{op:'update',resource:'component',resourceId:'ore',patch:{config:{axis}}}),
    'create wire':doc=>D.applyOperation(doc,{op:'create',resource:'wire',value:{id:'back',a:'bar',aSide:'out',b:'ore',bSide:'in',config:{axis}}}),
    'update wire':doc=>D.applyOperation(doc,{op:'update',resource:'wire',resourceId:'belt',patch:{config:{axis}}}),
    'batch':doc=>D.applyBatch(doc,{operations:[{op:'update',resource:'component',id:'bar',patch:{config:{axis:{layer:'l1'}}}},{op:'update',resource:'wire',id:'belt',patch:{config:{axis}}}]}),
  };
  for(const [how,run] of Object.entries(attempts)){
    const doc=fresh(),before=JSON.stringify(doc),r=run(doc);
    rows.push({how,ok:r.ok,message:message(r),same:JSON.stringify(doc)===before});
  }
  out.badAxis[name]=rows;
}

// (d) set, merge, remove
{
  const doc=fresh(),steps=[];
  const step=(label,r)=>steps.push({label,ok:r.ok,message:message(r),ore:D.clone(find(doc,'ore').config.axis)??null,belt:D.clone(find(doc,'belt').config.axis)??null,has:['ore','belt'].map(id=>Object.prototype.hasOwnProperty.call(find(doc,id).config,'axis')),revision:doc.revision});
  step('set ore layer',D.applyOperation(doc,{op:'update',resource:'component',resourceId:'ore',patch:{config:{axis:{layer:'l2'}}}}));
  step('merge ore phase',D.applyOperation(doc,{op:'update',resource:'component',resourceId:'ore',patch:{config:{axis:{phase:'build'}}}}));
  step('set belt',D.applyOperation(doc,{op:'update',resource:'wire',resourceId:'belt',patch:{config:{axis:{depth:'d2',layer:'l1'}}}}));
  step('move ore layer',D.applyOperation(doc,{op:'update',resource:'component',resourceId:'ore',patch:{config:{axis:{layer:'l1'}}}}));
  step('null one ore axis',D.applyOperation(doc,{op:'update',resource:'component',resourceId:'ore',patch:{config:{axis:{layer:null}}}}));
  step('null the last ore axis',D.applyOperation(doc,{op:'update',resource:'component',resourceId:'ore',patch:{config:{axis:{phase:null}}}}));
  step('axis null on belt',D.applyOperation(doc,{op:'update',resource:'wire',resourceId:'belt',patch:{config:{axis:null}}}));
  step('null an axis never set',D.applyOperation(doc,{op:'update',resource:'component',resourceId:'bar',patch:{config:{axis:{depth:null}}}}));
  step('null an undeclared axis',D.applyOperation(doc,{op:'update',resource:'component',resourceId:'bar',patch:{config:{axis:{tier:null}}}}));
  const made=D.applyOperation(doc,{op:'create',resource:'component',value:{id:'made',symbolId:'act',x:900,y:200,config:{label:'Made',axis:{layer:'l2',depth:'d1'}}}});
  const empty=D.applyOperation(doc,{op:'create',resource:'component',value:{id:'empty',symbolId:'act',x:900,y:400,config:{label:'Empty',axis:{}}}});
  const wire=D.applyOperation(doc,{op:'create',resource:'wire',value:{id:'back',a:'bar',aSide:'out',b:'ore',bSide:'in',config:{axis:{phase:'plan'}}}});
  const nulled=D.applyOperation(fresh(),{op:'create',resource:'component',value:{id:'n',symbolId:'act',x:900,y:200,config:{axis:null}}});
  out.steps={steps,made:{ok:made.ok,axis:made.result?.config?.axis??null},empty:{ok:empty.ok,has:empty.ok&&Object.prototype.hasOwnProperty.call(empty.result.config,'axis')},wire:{ok:wire.ok,message:message(wire),axis:wire.result?.config?.axis??null},nulled:{ok:nulled.ok,message:message(nulled)},valid:D.validateDocument(doc)};
}

// (e) loading reports and keeps
{
  const raw=D.clone(input.doc);raw.components[0].config.axis={tier:'l1',layer:'l9'};raw.wires[0].config.axis='l1';raw.components[1].config.axis={};
  const doc=D.makeDocument(raw);
  out.load={errors:D.validateDocument(doc).errors,kept:[find(doc,'ore').config.axis,find(doc,'belt').config.axis,find(doc,'bar').config.axis],markers:D.markersFor(doc).map(m=>({id:m.id,rule:m.rule,code:m.message.replace(/^(?:component|wire) \S+: /,'').split(':')[0]})),
    viaFile:(()=>{try{return D.validateDocument(D.documentFromFilePayload(raw)).errors.length}catch(e){return String(e.message)}})()};
  const noAxes=D.clone(input.doc);delete noAxes.axes;noAxes.components[0].config.axis={layer:'l1'};
  out.load.undeclared=D.validateDocument(D.makeDocument(noAxes)).errors;
  const badList=D.clone(input.doc);badList.axes=[{id:'a',values:[]},{id:'a',values:[]}];
  out.load.listMarkers=D.markersFor(D.makeDocument(badList)).map(m=>({id:m.id,rule:m.rule}));
}

// (f) on the record, outside layout, through compaction, save and open
{
  const doc=fresh();
  D.applyBatch(doc,{operations:[{op:'update',resource:'component',id:'ore',patch:{config:{axis:{layer:'l2',phase:'build'}}}},{op:'update',resource:'wire',id:'belt',patch:{config:{axis:{depth:'d1'}}}}]});
  const first=text(doc),opened=D.documentFromFilePayload(JSON.parse(first)),second=text(opened);
  const pkg=D.makePackage({document:JSON.parse(first)}),fromPackage=D.documentFromFilePayload(JSON.parse(JSON.stringify(pkg)));
  const moved=D.clone(doc);D.applyOperation(moved,{op:'update',resource:'component',resourceId:'ore',patch:{config:{axis:{layer:'l1'}}}});
  const renamed=D.clone(doc);D.setAxes(renamed,{axes:input.doc.axes.map((a,i)=>i?a:{...a,name:'Tier'})});
  const stored=JSON.parse(first),target=D.makeDocument({});D.replaceDocument(target,doc);
  out.stored={layout:JSON.stringify(doc.layout),inLayout:/axis|axes/.test(JSON.stringify(doc.layout)),
    compactComponent:D.compactComponent(find(doc,'ore')).config.axis,compactWire:D.compactWire(find(doc,'belt')).config.axis,
    fileAxes:stored.axes,fileOre:stored.components[0].config.axis,fileBelt:stored.wires[0].config.axis,
    geometry:['x','y'].map(k=>find(doc,'ore')[k]===find(fresh(),'ore')[k]),size:JSON.stringify(find(doc,'ore').config.presentation?.size??null)===JSON.stringify(find(fresh(),'ore').config.presentation?.size??null),
    sameText:first===second,sameHash:D.documentHash(doc)===D.documentHash(opened),packageText:text(fromPackage)===first,
    hashMoves:D.documentHash(doc)!==D.documentHash(moved),hashMovesOnAxes:D.documentHash(doc)!==D.documentHash(renamed),hashOfPlain:D.documentHash(doc)!==D.documentHash(fresh()),
    replaced:JSON.stringify(target.axes)===JSON.stringify(doc.axes)&&JSON.stringify(find(target,'ore').config.axis)===JSON.stringify(find(doc,'ore').config.axis)};
  // (g) reads
  const scope=D.readScope(doc,{ids:['ore','belt']}),got=D.applyOperation(doc,{op:'read',resource:'component',resourceId:'ore'}),gotWire=D.applyOperation(doc,{op:'read',resource:'wire',resourceId:'belt'});
  out.read={ok:scope.ok,ore:scope.components.find(c=>c.id==='ore')?.config?.axis,belt:scope.wires.find(w=>w.id==='belt')?.config?.axis,axes:scope.axes,get:got.result?.config?.axis,getWire:gotWire.result?.config?.axis,
    area:D.readScope(doc,{area:{x:0,y:0,width:400,height:400}}).components.map(c=>[c.id,c.config.axis??null])};

  // (h) setAxes
  const tries=[];
  const attempt=(label,request)=>{const before=JSON.stringify(doc),r=D.setAxes(doc,request);tries.push({label,ok:r.ok,message:message(r),same:JSON.stringify(doc)===before,moved:r.revisionAfter-r.revisionBefore,result:r.result});return r};
  const without=(axisId,valueId=null)=>input.doc.axes.filter(a=>valueId||a.id!==axisId).map(a=>a.id===axisId&&valueId?{...a,values:a.values.filter(v=>v.id!==valueId)}:a);
  attempt('drop an axis a component names',{axes:without('layer')});
  attempt('drop an axis a wire names',{axes:without('depth')});
  attempt('drop a value a component names',{axes:without('phase','build')});
  attempt('drop a value a wire names',{axes:without('depth','d1')});
  attempt('remove every axis while named',{axes:null});
  attempt('a stale revision',{axes:input.doc.axes,ifRevision:doc.revision+5});
  attempt('drop a value nothing names',{axes:without('layer','l1')});
  attempt('rename and reorder',{axes:[...input.doc.axes].reverse().map(a=>({...a,name:a.id.toUpperCase()}))});
  D.applyBatch(doc,{operations:[{op:'update',resource:'component',id:'ore',patch:{config:{axis:{layer:null}}}}]});
  attempt('drop an axis once the component let go',{axes:input.doc.axes.filter(a=>a.id!=='layer')});
  D.applyBatch(doc,{operations:[{op:'update',resource:'component',id:'ore',patch:{config:{axis:null}}},{op:'update',resource:'wire',id:'belt',patch:{config:{axis:null}}}]});
  attempt('null removes the key',{axes:null});
  out.setAxes={tries,hasKey:Object.prototype.hasOwnProperty.call(doc,'axes'),valid:D.validateDocument(doc).ok};
  out.setAxes.unnamedReorder=D.setAxes(fresh(),{axes:[...input.doc.axes].reverse()}).result.axes;
  const again=fresh();D.setAxes(again,{axes:[]});out.setAxes.emptyRemoves=!Object.prototype.hasOwnProperty.call(again,'axes');
  const blank=D.makeDocument({});const made=D.setAxes(blank,{axes:[{id:'a',values:[{id:'v'}]},{id:'b',values:[{id:'v'}]},{id:'c',values:[]}]});
  out.setAxes.onBlank={ok:made.ok,axes:made.result?.axes,stored:blank.axes};
}

// (i) every example
{
  const files=[];(function walk(dir){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory())walk(p);else if(e.name.endsWith('.sov'))files.push(p)}})(process.argv[2]);
  out.examples=files.sort().map(file=>{
    const row={file:path.relative(process.argv[2],file).replace(/\\/g,'/')};
    try{
      const doc=D.documentFromFilePayload(JSON.parse(fs.readFileSync(file,'utf8'))),errors=D.validateDocument(doc).errors;
      const scope=D.readScope(doc,{ids:doc.components.slice(0,3).map(c=>c.id)});
      Object.assign(row,{axesKey:Object.prototype.hasOwnProperty.call(doc,'axes'),axisKeys:[...doc.components,...doc.wires].filter(x=>x&&x.config&&Object.prototype.hasOwnProperty.call(x.config,'axis')).length,
        named:D.documentAxes(doc).length,axisErrors:errors.filter(e=>/AXIS_/.test(e)).length,readAxes:Object.prototype.hasOwnProperty.call(scope,'axes'),
        storedKeys:/"axes"|"axis"/.test(text(doc))});
    }catch(e){row.error=String(e.message||e)}
    return row;
  });
}
console.log(JSON.stringify(out));
"""

# Loads one data core (the tree's, or the merge base's source compiled in place) and prints, for every
# example, the stored text, the hash and the findings.
EXAMPLES = r"""
const fs=require('fs'),path=require('path'),Module=require('module');
const [core,examples,source]=process.argv.slice(1);
let D;
if(source){const m=new Module(core,null);m.filename=core;m.paths=Module._nodeModulePaths(path.dirname(core));m._compile(fs.readFileSync(source,'utf8'),core);D=m.exports}
else D=require(core);
const files=[];(function walk(dir){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory())walk(p);else if(e.name.endsWith('.sov'))files.push(p)}})(examples);
const out={};
for(const file of files.sort()){
  const key=path.relative(examples,file).replace(/\\/g,'/');
  try{
    const doc=D.documentFromFilePayload(JSON.parse(fs.readFileSync(file,'utf8')));
    if(doc.meta)doc.meta.updatedAt='fixed';
    const first=doc.components[0]?D.applyOperation(D.clone(doc),{op:'read',resource:'component',resourceId:doc.components[0].id}).result:null;
    out[key]={text:JSON.stringify(D.compactDocument(doc)),hash:D.documentHash(doc),errors:D.validateDocument(doc).errors,read:JSON.stringify(D.readScope(doc,{ids:doc.components.slice(0,3).map(c=>c.id)})),first:JSON.stringify(first),markers:JSON.stringify(D.markersFor(doc))};
  }catch(e){out[key]={error:String(e.message||e)}}
}
console.log(JSON.stringify(out));
"""


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')


def node(script: str, *args: str, stdin: str | None = None) -> dict:
    proc = subprocess.run(['node', '-e', script, *args], cwd=ROOT, input=stdin, capture_output=True, text=True, encoding='utf-8')
    assert proc.returncode == 0, proc.stderr[-3000:]
    return json.loads(proc.stdout)


def code(message: str) -> str:
    return message.split(':')[0]


def core_part() -> None:
    r = node(NODE, str(ROOT / 'src/05-data-core.js'), str(ROOT / 'examples'), stdin=json.dumps({'doc': DOC, 'badAxes': BAD_AXES, 'badAxis': BAD_AXIS}))

    # (a) Defaults by position.
    d = r['defaults']
    assert d['words'] == ['Layer', 'Phase', 'Depth'], d['words']
    assert d['named'] == NAMED, ('the names a document reads as', d['named'])
    assert d['stored'] == AXES, ('the stored list gained a default name', d['stored'])
    assert d['valid'] == {'ok': True, 'errors': []}, d['valid']
    assert d['none'] == [], d['none']
    print('(a) defaults by position:', [(a['name'], [v['name'] for v in a['values']]) for a in d['named']], '; the stored list keeps no default name')

    # (b) AXIS_INVALID for every bad list, on load and in setAxes.
    for name, row in r['badAxes'].items():
        want = BAD_AXES[name][1] if name in BAD_AXES else 'axes must be an array'
        found = [e for e in row['errors'] if e.startswith('AXIS_INVALID: ') and want in e]
        assert found, (name, 'is not reported on load as AXIS_INVALID holding', want, row['errors'])
        assert row['kept'], (name, 'loading changed the stored list')
        assert row['ok'] is False and row['message'].startswith('AXIS_INVALID: ') and want in row['message'], (name, 'setAxes', row['message'])
        assert row['same'], (name, 'a refused setAxes changed the document')
    print('(b) AXIS_INVALID on load and in setAxes, the document unchanged:', len(r['badAxes']), 'bad lists, e.g.', r['badAxes']['a repeated value id']['message'])

    # (c) The three refusals on create and update, Component and Wire, single and batch.
    for name, rows in r['badAxis'].items():
        _, want_code, want_text = BAD_AXIS[name]
        assert [row['how'] for row in rows] == ['create component', 'update component', 'create wire', 'update wire', 'batch'], rows
        for row in rows:
            assert row['ok'] is False, (name, row['how'], 'was admitted')
            assert want_code + ': ' in row['message'] and want_text in row['message'], (name, row['how'], row['message'])
            if row['how'] != 'batch':
                assert code(row['message']) == want_code, (name, row['how'], 'the message does not start with the code', row['message'])
            assert row['same'], (name, row['how'], 'a refused write changed the document')
    sample = {name: rows[1]['message'] for name, rows in r['badAxis'].items()}
    print('(c) create and update of a Component and a Wire, and a batch, refuse and change nothing:')
    for name in ('an undeclared axis', 'an unlisted value', 'a string'):
        print('     ', sample[name])

    # (d) Set, merge per key, remove one, remove all.
    s = {step['label']: step for step in r['steps']['steps']}
    assert all(step['ok'] for label, step in s.items() if label != 'null an undeclared axis'), [(k, v['message']) for k, v in s.items() if not v['ok']]
    assert s['set ore layer']['ore'] == {'layer': 'l2'} and s['set ore layer']['revision'] == 1, s['set ore layer']
    assert s['merge ore phase']['ore'] == {'layer': 'l2', 'phase': 'build'}, s['merge ore phase']
    assert s['set belt']['belt'] == {'depth': 'd2', 'layer': 'l1'}, s['set belt']
    assert s['move ore layer']['ore'] == {'layer': 'l1', 'phase': 'build'}, s['move ore layer']
    assert s['null one ore axis']['ore'] == {'phase': 'build'}, s['null one ore axis']
    assert s['null the last ore axis']['ore'] is None and s['null the last ore axis']['has'][0] is False, ('the last value left an empty object', s['null the last ore axis'])
    assert s['axis null on belt']['belt'] is None and s['axis null on belt']['has'][1] is False, s['axis null on belt']
    assert s['null an axis never set']['ok'], s['null an axis never set']
    assert s['null an undeclared axis']['ok'] is False and code(s['null an undeclared axis']['message']) == 'AXIS_UNKNOWN', s['null an undeclared axis']
    assert r['steps']['made'] == {'ok': True, 'axis': {'layer': 'l2', 'depth': 'd1'}}, r['steps']['made']
    assert r['steps']['empty'] == {'ok': True, 'has': False}, ('an empty object on create wrote a key', r['steps']['empty'])
    assert r['steps']['wire']['ok'] and r['steps']['wire']['axis'] == {'phase': 'plan'}, r['steps']['wire']
    assert r['steps']['nulled']['ok'] is False and code(r['steps']['nulled']['message']) == 'AXIS_INVALID', r['steps']['nulled']
    assert r['steps']['valid']['ok'], r['steps']['valid']
    print('(d) update sets and merges per key; {axis: {id: null}} removes one axis, axis null the key; no empty object is stored')

    # (e) Loading keeps the values and reports them.
    L = r['load']
    assert L['kept'] == [{'tier': 'l1', 'layer': 'l9'}, 'l1', {}], ('loading changed a stored config.axis', L['kept'])
    assert any(e.startswith('component ore: AXIS_UNKNOWN: config.axis.tier') and 'declared: layer, phase, depth' in e for e in L['errors']), L['errors']
    assert any(e.startswith('component ore: AXIS_VALUE_UNKNOWN: config.axis.layer "l9"') and 'declared: l1, l2' in e for e in L['errors']), L['errors']
    assert any(e.startswith('wire belt: AXIS_INVALID: config.axis must be an object') for e in L['errors']), L['errors']
    assert len(L['errors']) == 3 and L['viaFile'] == 3, (L['errors'], L['viaFile'])
    assert sorted((m['id'], m['rule'], m['code']) for m in L['markers']) == [('belt', 'status', 'AXIS_INVALID'), ('ore', 'status', 'AXIS_UNKNOWN'), ('ore', 'status', 'AXIS_VALUE_UNKNOWN')], L['markers']
    assert len(L['undeclared']) == 1 and L['undeclared'][0].startswith('component ore: AXIS_UNKNOWN:') and 'declared: none' in L['undeclared'][0], L['undeclared']
    assert L['listMarkers'] == [{'id': 'declared-axes', 'rule': 'status'}], L['listMarkers']
    print('(e) a file with a bad config.axis loads as written and reports:', L['errors'][0][:76], '...')

    # (f) On the record, outside layout, through compaction, save and open.
    S = r['stored']
    assert S['inLayout'] is False, ('document.layout holds an axis', S['layout'])
    assert S['compactComponent'] == {'layer': 'l2', 'phase': 'build'} and S['compactWire'] == {'depth': 'd1'}, (S['compactComponent'], S['compactWire'])
    assert S['fileAxes'] == AXES and S['fileOre'] == {'layer': 'l2', 'phase': 'build'} and S['fileBelt'] == {'depth': 'd1'}, (S['fileAxes'], S['fileOre'], S['fileBelt'])
    assert S['geometry'] == [True, True] and S['size'], ('setting a value moved or resized the card', S['geometry'], S['size'])
    assert S['sameText'], 'save, open, save is not byte-identical'
    assert S['sameHash'] and S['packageText'], (S['sameHash'], S['packageText'])
    assert S['hashMoves'] and S['hashMovesOnAxes'] and S['hashOfPlain'], ('the hash does not read the field', S)
    assert S['replaced'], 'replaceDocument dropped axes or config.axis'
    print('(f) config.axis is on the record and not in document.layout; save, open, save is byte-identical; the hash reads it')

    # (g) Reads.
    R = r['read']
    assert R['ok'] and R['ore'] == {'layer': 'l2', 'phase': 'build'} and R['belt'] == {'depth': 'd1'}, R
    assert R['axes'] == NAMED, R['axes']
    assert R['get'] == {'layer': 'l2', 'phase': 'build'} and R['getWire'] == {'depth': 'd1'}, (R['get'], R['getWire'])
    assert R['area'] == [['ore', {'layer': 'l2', 'phase': 'build'}]], R['area']
    print('(g) readScope and a read return config.axis; readScope returns the named axes')

    # (h) setAxes.
    T = {t['label']: t for t in r['setAxes']['tries']}
    for label, want_code, holder in (('drop an axis a component names', 'AXIS_UNKNOWN', '(component ore still names it)'),
                                     ('drop an axis a wire names', 'AXIS_UNKNOWN', '(wire belt still names it)'),
                                     ('drop a value a component names', 'AXIS_VALUE_UNKNOWN', '(component ore still names it)'),
                                     ('drop a value a wire names', 'AXIS_VALUE_UNKNOWN', '(wire belt still names it)'),
                                     ('remove every axis while named', 'AXIS_UNKNOWN', 'still names it)')):
        t = T[label]
        assert t['ok'] is False and code(t['message']) == want_code and holder in t['message'] and 'declared: ' in t['message'], (label, t['message'])
        assert t['same'] and t['moved'] == 0, (label, 'a refused setAxes changed the document')
    assert T['a stale revision']['ok'] is False and T['a stale revision']['message'].startswith('Stale revision') and T['a stale revision']['same'], T['a stale revision']
    assert T['drop a value nothing names']['ok'] and T['drop a value nothing names']['moved'] == 1, T['drop a value nothing names']
    assert [v['id'] for v in T['drop a value nothing names']['result']['axes'][0]['values']] == ['l2'], T['drop a value nothing names']['result']
    ro = T['rename and reorder']
    assert ro['ok'] and [(a['id'], a['name']) for a in ro['result']['axes']] == [('depth', 'DEPTH'), ('phase', 'PHASE'), ('layer', 'LAYER')], ro
    # An unnamed value takes its own axis's name, wherever the axis sits.
    assert [v['name'] for v in ro['result']['axes'][0]['values']] == ['DEPTH 1', 'DEPTH 2'], ro['result']['axes'][0]
    U = r['setAxes']['unnamedReorder']
    # An unnamed axis is named by its position, and its unnamed values follow that name.
    assert [(a['id'], a['name'], [v['name'] for v in a['values']]) for a in U] == [('depth', 'Layer', ['Layer 1', 'Layer 2']), ('phase', 'Stage', ['Stage 1', 'Stage 2']), ('layer', 'Depth', ['Depth 1', 'Service'])], U
    assert T['drop an axis once the component let go']['ok'], T['drop an axis once the component let go']
    assert T['null removes the key']['ok'] and T['null removes the key']['result'] == {'axes': []} and r['setAxes']['hasKey'] is False, T['null removes the key']
    assert r['setAxes']['valid'] and r['setAxes']['emptyRemoves'], r['setAxes']
    B = r['setAxes']['onBlank']
    assert B['ok'] and [a['name'] for a in B['axes']] == ['Layer', 'Phase', 'Depth'] and B['axes'][1]['values'] == [{'id': 'v', 'name': 'Phase 1'}], B
    assert B['stored'] == [{'id': 'a', 'values': [{'id': 'v'}]}, {'id': 'b', 'values': [{'id': 'v'}]}, {'id': 'c', 'values': []}], B['stored']
    print('(h) setAxes refuses dropping what a record still names:')
    print('     ', T['drop an axis a component names']['message'])
    print('     ', T['drop a value a wire names']['message'])

    # (i) Every example is as it was.
    rows = r['examples']
    assert len(rows) >= 10, ('too few examples found', len(rows))
    for row in rows:
        assert 'error' not in row, row
        assert row['axesKey'] is False and row['axisKeys'] == 0 and row['named'] == 0 and row['axisErrors'] == 0 and row['readAxes'] is False and row['storedKeys'] is False, row
    status = git('status', '--porcelain', '--', 'examples', 'tests/golden', 'tests/fixtures', 'tests/golden-rendered-text.json')
    assert status.returncode == 0 and status.stdout.strip() == '', ('examples or goldens are modified in the tree', status.stdout, status.stderr)
    base = None
    for ref in ('origin/dev', 'origin/main'):
        found = git('merge-base', 'HEAD', ref)
        if found.returncode == 0 and found.stdout.strip():
            base = found.stdout.strip()
            break
    compared = 'no merge base found; the comparison with the earlier data core was not run'
    if base:
        changed = git('diff', '--name-only', base, '--', 'examples', 'tests/golden', 'tests/fixtures', 'tests/golden-rendered-text.json')
        assert changed.returncode == 0 and changed.stdout.strip() == '', ('examples or goldens differ from the merge base', changed.stdout)
        old = git('show', f'{base}:src/05-data-core.js')
        assert old.returncode == 0, old.stderr
        with tempfile.TemporaryDirectory(prefix='sov-axes-base-') as td:
            source = Path(td) / 'data-core.base.js'
            source.write_text(old.stdout, encoding='utf-8', newline='\n')
            core = str(ROOT / 'src/05-data-core.js')
            was = node(EXAMPLES, core, str(ROOT / 'examples'), str(source))
            now = node(EXAMPLES, core, str(ROOT / 'examples'))
        assert sorted(was) == sorted(now) and len(now) == len(rows), (len(was), len(now), len(rows))
        for name in sorted(now):
            assert was[name] == now[name], (name, 'differs from the merge base data core', [k for k in now[name] if was[name].get(k) != now[name].get(k)])
        compared = f'stored text, hash, findings, markers and reads equal those of the data core at {base[:8]}'
    print(f'(i) {len(rows)} examples: no axes key, no config.axis, no AXIS finding; examples and goldens unmodified; {compared}')


def http_json(url, method='GET', payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = request.Request(url, data=body, method=method, headers={'content-type': 'application/json'})
    try:
        with request.urlopen(req, timeout=6) as res:
            return res.status, json.loads(res.read())
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def rpc(base, method, params=None, _id=[0]):
    _id[0] += 1
    status, data = http_json(base + '/mcp', 'POST', {'jsonrpc': '2.0', 'id': _id[0], 'method': method, **({'params': params} if params is not None else {})})
    assert status == 200, (status, data)
    return data['result']


def tool(base, name, args=None):
    r = rpc(base, 'tools/call', {'name': name, 'arguments': args or {}})
    return r['structuredContent'], r.get('isError', False)


class Server:
    def __init__(self, file: Path):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            self.port = s.getsockname()[1]
        self.base = f'http://127.0.0.1:{self.port}'
        self.proc = subprocess.Popen(['node', str(ROOT / 'mcp/server.mjs'), '--port', str(self.port), '--file', str(file)],
                                     cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def __enter__(self) -> str:
        for _ in range(100):
            try:
                if http_json(self.base + '/api/v1/formats')[0] == 200:
                    return self.base
            except Exception:
                time.sleep(.05)
        self.__exit__()
        raise AssertionError('server did not start')

    def __exit__(self, *exc) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def server_part() -> None:
    with tempfile.TemporaryDirectory(prefix='sov-declared-axes-') as td:
        file = Path(td) / 'axes.sov'
        file.write_text(json.dumps(DOC, indent=2), encoding='utf-8', newline='\n')
        with Server(file) as base:
            document = lambda: tool(base, 'schematic.document.get')[0]
            pick = lambda doc, key, ident: [x for x in doc[key] if x['id'] == ident][0]

            # Writes.
            receipt, is_error = tool(base, 'schematic.update', {'resource': 'component', 'id': 'ore', 'patch': {'config': {'axis': {'layer': 'l2', 'phase': 'build'}}}})
            assert not is_error and receipt['ok'], receipt
            receipt, is_error = tool(base, 'schematic.apply', {'operations': [
                {'op': 'update', 'resource': 'wire', 'id': 'belt', 'patch': {'config': {'axis': {'depth': 'd1'}}}},
                {'op': 'create', 'resource': 'component', 'ref': '$slag', 'value': {'symbolId': 'act', 'x': 900, 'y': 200, 'config': {'label': 'Slag', 'axis': {'layer': 'l1'}}}}]})
            assert not is_error and receipt['ok'], receipt
            slag = receipt['result']['ids']['$slag']

            # Reads: get, read, document.get, HTTP, the file.
            got, _ = tool(base, 'schematic.get', {'resource': 'component', 'id': 'ore'})
            assert got['result']['config']['axis'] == {'layer': 'l2', 'phase': 'build'}, got['result']['config']
            got, _ = tool(base, 'schematic.get', {'resource': 'wire', 'id': 'belt'})
            assert got['result']['config']['axis'] == {'depth': 'd1'}, got['result']['config']
            scope, is_error = tool(base, 'schematic.read', {'ids': ['ore', 'belt', slag]})
            assert not is_error and scope['axes'] == NAMED, scope.get('axes')
            assert {c['id']: c['config'].get('axis') for c in scope['components']} == {'ore': {'layer': 'l2', 'phase': 'build'}, slag: {'layer': 'l1'}}, scope['components']
            assert scope['wires'][0]['config']['axis'] == {'depth': 'd1'}, scope['wires']
            doc = document()
            assert doc['axes'] == AXES and pick(doc, 'components', 'ore')['config']['axis'] == {'layer': 'l2', 'phase': 'build'} and pick(doc, 'wires', 'belt')['config']['axis'] == {'depth': 'd1'}, doc.get('axes')
            assert 'axis' not in json.dumps(doc.get('layout', {})) and 'axes' not in json.dumps(doc.get('layout', {})), doc.get('layout')
            status, over_http = http_json(base + '/api/v1/document')
            assert status == 200 and over_http == doc, 'GET /api/v1/document differs from schematic.document.get'
            status, posted = http_json(base + '/api/v1/read', 'POST', {'ids': ['ore']})
            assert status == 200 and posted['components'][0]['config']['axis'] == {'layer': 'l2', 'phase': 'build'} and posted['axes'] == NAMED, posted
            on_disk = json.loads(file.read_text(encoding='utf-8'))
            assert on_disk['axes'] == AXES and pick(on_disk, 'components', 'ore')['config']['axis'] == {'layer': 'l2', 'phase': 'build'} and pick(on_disk, 'wires', 'belt')['config']['axis'] == {'depth': 'd1'}, 'the saved file does not hold the field'

            # Refusals, each changing nothing.
            before, before_text = document(), file.read_text(encoding='utf-8')
            for name, (axis, want_code, want_text) in BAD_AXIS.items():
                for label, call in (
                        ('schematic.update component', ('schematic.update', {'resource': 'component', 'id': 'bar', 'patch': {'config': {'axis': axis}}})),
                        ('schematic.update wire', ('schematic.update', {'resource': 'wire', 'id': 'belt', 'patch': {'config': {'axis': axis}}})),
                        ('schematic.create component', ('schematic.create', {'resource': 'component', 'value': {'symbolId': 'act', 'x': 900, 'y': 500, 'config': {'axis': axis}}})),
                        ('schematic.create wire', ('schematic.create', {'resource': 'wire', 'value': {'a': 'bar', 'aSide': 'out', 'b': 'ore', 'bSide': 'in', 'config': {'axis': axis}}})),
                        ('schematic.apply', ('schematic.apply', {'operations': [{'op': 'update', 'resource': 'component', 'id': 'bar', 'patch': {'config': {'axis': axis}}}]}))):
                    refused, is_error = tool(base, *call)
                    msg = (refused.get('error') or {}).get('message', '')
                    assert is_error and refused['ok'] is False and code(msg) == want_code and want_text in msg, (name, label, refused)
                    assert document() == before and file.read_text(encoding='utf-8') == before_text, (name, label, 'a refused write changed the document or the file')

            # Replacing the document with a list that drops what a record names is refused the same way.
            dropped = json.loads(json.dumps(before))
            dropped['axes'] = [a for a in AXES if a['id'] != 'layer']
            refused, is_error = tool(base, 'schematic.document.replace', {'document': dropped})
            assert is_error and 'component ore: AXIS_UNKNOWN: config.axis.layer' in refused['error'], refused
            status, body = http_json(base + '/api/v1/document', 'PUT', dropped)
            assert status == 400 and any(e.startswith('component ore: AXIS_UNKNOWN:') for e in body['errors']), (status, body)
            thinner = json.loads(json.dumps(before))
            thinner['axes'] = [{**a, 'values': [v for v in a['values'] if v['id'] != 'd1']} for a in AXES]
            status, body = http_json(base + '/api/v1/document', 'PUT', thinner)
            assert status == 400 and any(e.startswith('wire belt: AXIS_VALUE_UNKNOWN:') for e in body['errors']), (status, body)
            four = json.loads(json.dumps(before))
            four['axes'] = AXES + [{'id': 'fourth', 'values': []}]
            status, body = http_json(base + '/api/v1/document', 'PUT', four)
            assert status == 400 and any(e.startswith('AXIS_INVALID: axes holds 4 entries') for e in body['errors']), (status, body)
            assert document() == before and file.read_text(encoding='utf-8') == before_text, 'a refused replace changed the document or the file'
            markers, _ = tool(base, 'schematic.markers')
            assert markers == [], markers

            # schematic.axes.set and POST /api/v1/axes: listed, refused with the same codes, one revision
            # and one history entry per call.
            tools = rpc(base, 'tools/list')['tools']
            by_name = {t['name']: t for t in tools}
            assert 'schematic.axes.set' in by_name and by_name['schematic.axes.set']['inputSchema'].get('type') == 'object' and by_name['schematic.axes.set'].get('description'), sorted(by_name)
            assert by_name['schematic.axes.set']['inputSchema']['required'] == ['axes'], by_name['schematic.axes.set']['inputSchema']
            manifest = json.loads((ROOT / 'mcp/tools.json').read_text(encoding='utf-8'))['tools']
            assert sorted(by_name) == sorted(manifest) and len(tools) == len(manifest), ('tools/list differs from mcp/tools.json', sorted(set(by_name) ^ set(manifest)))
            assert '`schematic.axes.set`' in (ROOT / 'MCP.md').read_text(encoding='utf-8') and 'POST /api/v1/axes' in (ROOT / 'MCP.md').read_text(encoding='utf-8'), 'MCP.md does not list the verb'
            for label, axes, want_code, want_text in (
                    ('drop an axis a component names', dropped['axes'], 'AXIS_UNKNOWN', '(component ore still names it)'),
                    ('drop a value a wire names', thinner['axes'], 'AXIS_VALUE_UNKNOWN', '(wire belt still names it)'),
                    ('four axes', four['axes'], 'AXIS_INVALID', 'axes holds 4 entries; at most 3'),
                    ('a repeated value id', BAD_AXES['a repeated value id'][0], 'AXIS_INVALID', 'axes[1].values[1].id "v" is already used'),
                    ('not a list', 'layer', 'AXIS_INVALID', 'axes must be an array'),
                    ('remove every axis while named', None, 'AXIS_UNKNOWN', 'still names it)')):
                refused, is_error = tool(base, 'schematic.axes.set', {'axes': axes})
                msg = (refused.get('error') or {}).get('message', '')
                assert is_error and refused['ok'] is False and refused['result'] is None and code(msg) == want_code and want_text in msg, (label, refused)
                assert refused['revisionAfter'] == refused['revisionBefore'] == before['revision'], (label, refused)
                status, body = http_json(base + '/api/v1/axes', 'POST', {'axes': axes})
                assert status == 400 and body['ok'] is False and body['error']['message'] == msg, (label, status, body)
                assert document() == before and file.read_text(encoding='utf-8') == before_text, (label, 'a refused axes.set changed the document or the file')
            refused, is_error = tool(base, 'schematic.axes.set', {})
            assert is_error and code(refused['error']['message']) == 'AXIS_INVALID', refused
            stale = {'axes': AXES, 'ifRevision': before['revision'] - 1}
            refused, is_error = tool(base, 'schematic.axes.set', stale)
            assert is_error and refused['error']['message'].startswith('Stale revision'), refused
            status, body = http_json(base + '/api/v1/axes', 'POST', stale)
            assert status == 409 and body['ok'] is False and body['error']['message'].startswith('Stale revision'), (status, body)
            assert document() == before and file.read_text(encoding='utf-8') == before_text, 'a stale axes.set changed the document or the file'

            renamed = [dict(AXES[0], name='Tier'), {'id': 'phase', 'values': [{'id': 'plan'}, {'id': 'build', 'name': 'Make'}]}, AXES[2]]
            receipt, is_error = tool(base, 'schematic.axes.set', {'axes': renamed, 'ifRevision': before['revision']})
            assert not is_error and receipt['ok'] and receipt['error'] is None, receipt
            assert receipt['revisionBefore'] == before['revision'] and receipt['revisionAfter'] == before['revision'] + 1, ('the revision did not move by exactly 1', receipt)
            assert [(a['name'], [v['name'] for v in a['values']]) for a in receipt['result']['axes']] == [('Tier', ['Tier 1', 'Service']), ('Phase', ['Phase 1', 'Make']), ('Depth', ['Depth 1', 'Depth 2'])], receipt['result']
            after = document()
            assert after['axes'] == renamed and after['revision'] == before['revision'] + 1, (after['axes'], after['revision'])
            assert {**after, 'axes': None, 'revision': None, 'meta': None} == {**before, 'axes': None, 'revision': None, 'meta': None}, 'axes.set changed something other than axes'
            assert json.loads(file.read_text(encoding='utf-8'))['axes'] == renamed, 'axes.set was not saved'
            assert tool(base, 'schematic.read', {'ids': ['ore']})[0]['axes'] == receipt['result']['axes']
            undone, is_error = tool(base, 'schematic.history.undo')
            assert not is_error and document() == before, 'one schematic.history.undo did not restore the document before axes.set'
            status, posted = http_json(base + '/api/v1/axes', 'POST', {'axes': renamed, 'ifRevision': before['revision']})
            assert status == 200 and posted['ok'] and set(posted) == set(receipt) and posted['result'] == receipt['result'], (status, posted)
            assert posted['revisionAfter'] == before['revision'] + 1 and json.loads(file.read_text(encoding='utf-8'))['axes'] == renamed, 'POST /api/v1/axes did not move one revision and save'
            undone, is_error = tool(base, 'schematic.history.undo')
            assert not is_error and document() == before, 'one schematic.history.undo did not restore the document before POST /api/v1/axes'
            print('     schematic.axes.set and POST /api/v1/axes: listed in tools/list, mcp/tools.json and MCP.md; six refusals with the same codes, 400 and 409 over HTTP, nothing changed; a set moves one revision, saves, and one undo restores')

            # null removes, over MCP.
            receipt, is_error = tool(base, 'schematic.update', {'resource': 'component', 'id': slag, 'patch': {'config': {'axis': None}}})
            assert not is_error and receipt['ok'] and 'axis' not in receipt['result']['config'], receipt
            last = document()
        # A restarted server reads the same document back from the file.
        with Server(file) as base:
            again = tool(base, 'schematic.document.get')[0]
            assert again == last, 'a restarted server reads a different document'
            assert again['axes'] == AXES and [c for c in again['components'] if c['id'] == 'ore'][0]['config']['axis'] == {'layer': 'l2', 'phase': 'build'}
    print('(j) MCP and HTTP: update, create and apply write and refuse; get, read and document.get return config.axis; the file holds it and a restarted server reads it back; replace and PUT refuse a list that drops what a record names')


PAGE = r"""async ([doc,badAxis,axes])=>{
  const A=window.SovSchematicAPI,out={};
  A.document.replace(doc);
  const pick=()=>{const d=A.document.get();return {axes:d.axes??null,ore:d.components.find(c=>c.id==='ore')?.config?.axis??null,belt:d.wires.find(w=>w.id==='belt')?.config?.axis??null}};
  // Two exports of one document differ in their numbers (a gradient id's render counter, a moving
  // label's x in the fifth decimal), so the picture is compared with every number struck out:
  // its elements, classes, attributes and text.
  const picture=async()=>String(await A.file.svg()).replace(/-?\d+(?:\.\d+)?(?:e-?\d+)?/g,'#');
  out.pictureSize=(await picture()).length;
  out.list=A.axes.list();
  const plain=await picture();
  out.pictureStable=(await picture())===plain;
  const set=A.update('component','ore',{config:{axis:{layer:'l2',phase:'build'}}}),wire=A.update('wire','belt',{config:{axis:{depth:'d1'}}});
  out.set={ok:set.ok&&wire.ok,message:(set.error||wire.error||{}).message||'',state:pick()};
  out.samePicture=(await picture())===plain;
  out.get=A.get('component','ore').result?.config?.axis??null;
  const scope=A.read({ids:['ore','belt']});
  out.read={ore:scope.components[0]?.config?.axis??null,belt:scope.wires[0]?.config?.axis??null,axes:scope.axes??null};
  out.inLayout=/axis|axes/.test(JSON.stringify(A.document.get().layout||{}));
  out.refused=[];
  const text=()=>{const d=A.document.get();delete d.meta.updatedAt;return JSON.stringify(d)};
  for(const [name,[axis]] of Object.entries(badAxis)){
    const before=text();
    for(const [how,run] of [['update component',()=>A.update('component','bar',{config:{axis}})],['update wire',()=>A.update('wire','belt',{config:{axis}})],['create component',()=>A.create('component',{symbolId:'act',x:900,y:500,config:{axis}})],['create wire',()=>A.create('wire',{a:'bar',aSide:'out',b:'ore',bSide:'in',config:{axis}})],['apply',()=>A.apply({operations:[{op:'update',resource:'component',id:'bar',patch:{config:{axis}}}]})]]){
      const r=run();out.refused.push({name,how,ok:r.ok,message:r.error?.message||'',same:text()===before});
    }
  }
  const before=text();
  const drop=A.axes.set(axes.filter(a=>a.id!=='layer')),thin=A.axes.set({axes:axes.map(a=>({...a,values:a.values.filter(v=>v.id!=='d1')}))}),four=A.axes.set([...axes,{id:'fourth',values:[]}]);
  out.setRefused=[drop,thin,four].map(r=>({ok:r.ok,message:r.error?.message||''}));out.setSame=text()===before;
  const revision=A.file.info().revision;
  const renamed=A.axes.set(axes.map((a,i)=>i?a:{...a,name:'Tier'}));
  out.renamed={ok:renamed.ok,moved:A.file.info().revision-revision,names:A.axes.list().map(a=>a.name),result:renamed.result?.axes?.map(a=>a.name)};
  out.undo=A.history.undo();out.afterUndo=A.axes.list().map(a=>a.name);
  const saved=JSON.stringify(A.file.document(),null,2);
  A.file.open(saved,'again.sov');
  const reopened=JSON.stringify(A.file.document(),null,2);
  out.round={same:saved===reopened,state:pick(),where:saved===reopened?null:(()=>{let i=0;while(saved[i]===reopened[i])i++;return [saved.slice(Math.max(0,i-60),i+60),reopened.slice(Math.max(0,i-60),i+60)]})()};
  const cleared=A.update('component','ore',{config:{axis:{layer:null,phase:null}}});
  out.cleared={ok:cleared.ok,has:Object.prototype.hasOwnProperty.call(A.get('component','ore').result.config,'axis')};
  return out;
}"""


def browser_part() -> None:
    from playwright.sync_api import sync_playwright
    from browser_runtime import chromium_launch_kwargs
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(200)
        r = page.evaluate(PAGE, [DOC, BAD_AXIS, AXES])
        page.wait_for_timeout(100)
        browser.close()
    assert r['list'] == NAMED, ('SovSchematicAPI.axes.list()', r['list'])
    assert r['set']['ok'], r['set']['message']
    assert r['set']['state'] == {'axes': AXES, 'ore': {'layer': 'l2', 'phase': 'build'}, 'belt': {'depth': 'd1'}}, r['set']['state']
    assert r['pictureSize'] > 1000 and r['pictureStable'], ('two exports of one document differ beyond their numbers', r['pictureSize'])
    assert r['samePicture'], 'setting config.axis changed the elements, classes or text of the exported picture'
    assert r['get'] == {'layer': 'l2', 'phase': 'build'}, r['get']
    assert r['read'] == {'ore': {'layer': 'l2', 'phase': 'build'}, 'belt': {'depth': 'd1'}, 'axes': NAMED}, r['read']
    assert r['inLayout'] is False, 'document.layout holds an axis'
    assert len(r['refused']) == len(BAD_AXIS) * 5, len(r['refused'])
    for row in r['refused']:
        _, want_code, want_text = BAD_AXIS[row['name']]
        assert row['ok'] is False and code(row['message']) == want_code and want_text in row['message'], row
        assert row['same'], (row['name'], row['how'], 'a refused write changed the document')
    assert [(x['ok'], code(x['message'])) for x in r['setRefused']] == [(False, 'AXIS_UNKNOWN'), (False, 'AXIS_VALUE_UNKNOWN'), (False, 'AXIS_INVALID')], r['setRefused']
    assert r['setSame'], 'a refused axes.set changed the document'
    assert r['renamed'] == {'ok': True, 'moved': 1, 'names': ['Tier', 'Stage', 'Depth'], 'result': ['Tier', 'Stage', 'Depth']}, r['renamed']
    assert r['undo'] is True and r['afterUndo'] == ['Layer', 'Stage', 'Depth'], ('one undo did not take back the set', r['undo'], r['afterUndo'])
    assert r['round']['same'], ('saving and opening changed the text', r['round']['where'])
    assert r['round']['state'] == {'axes': AXES, 'ore': {'layer': 'l2', 'phase': 'build'}, 'belt': {'depth': 'd1'}}, r['round']['state']
    assert r['cleared'] == {'ok': True, 'has': False}, r['cleared']
    assert not errors, errors
    print('(k) browser: create, update, get, read, document.get and axes.list/axes.set agree with the data core; one undo takes back a set; save and open give the same text; the exported picture keeps its elements, classes and text; no page errors')


def main() -> None:
    core_part()
    server_part()
    browser_part()
    print('PASS declared axes QA')


if __name__ == '__main__':
    main()
