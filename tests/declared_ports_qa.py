"""Declared ports: the data model (contract 0b-1, issue #45).

A 2D Component's ports are declared data. The attachment core holds no port set of its own;
the typed Component template declares the left/right/top trio; stored forms keep their
meaning ('standard' = template ports + authored additions, 'none' = the authored list);
edits are stored in the smallest form and refused when invalid or when they would orphan a
Wire; binding a Wire needs the two ports to share a channel. Node and the HTTP/MCP server
only; no browser.
"""
from __future__ import annotations
import json
import re
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]
TRIO = [
    {'id': 'left', 'compatId': 'in', 'side': 'left', 't': .5, 'flow': 'in', 'channels': [{'id': 'main'}]},
    {'id': 'right', 'compatId': 'out', 'side': 'right', 't': .5, 'flow': 'out', 'channels': [{'id': 'main'}]},
    {'id': 'top', 'compatId': 'control', 'side': 'top', 't': .5, 'flow': 'control', 'channels': [{'id': 'main'}]},
]


def node(js: str, *args: str):
    proc = subprocess.run(['node', '-e', js, *args], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


# Step 1: the attachment core alone (no data core registered) exposes no 2D port set.
CORE_ALONE = r"""
const A=require(process.argv[1]);
const surface={id:'s',symbolId:'act',form:{dimension:2},config:{}};
const authored={id:'t',symbolId:'act',form:{dimension:2},config:{attachmentPoints:[{id:'feed',side:'bottom',t:.3,flow:'in'}]}};
console.log(JSON.stringify({
  bare:A.pointIds(surface),authored:A.pointIds(authored),
  zero:A.pointSpecs({form:{dimension:0}}),one:A.pointSpecs({form:{dimension:1}})
}));
"""

CORE = r"""
const D=require(process.argv[1]),A=globalThis.SovSchematicAttachment,fs=require('fs');
const clone=x=>JSON.parse(JSON.stringify(x));
const out={};
const ids=c=>A.pointIds(c);
const specs=c=>A.pointSpecs(c).map(s=>({id:s.id,compatId:s.compatId,side:s.side,t:s.t,flow:s.flow,channels:s.channels}));
const doc0=()=>D.makeDocument({id:'t'});
const op=(doc,o)=>D.applyOperation(doc,o);
const upd=(doc,id,patch)=>op(doc,{op:'update',resource:'component',resourceId:id,patch});
const mk=(doc,value)=>op(doc,{op:'create',resource:'component',value});
const mkw=(doc,value)=>op(doc,{op:'create',resource:'wire',value});
const reload=doc=>D.documentFromFilePayload(JSON.parse(JSON.stringify(D.compactDocument(doc))));

// Step 2: template data.
out.symbols=JSON.parse(process.argv[2]);
out.templates={};for(const s of out.symbols)out.templates[s]=D.templatePorts(s);
out.planePreset=D.templatePreset('plane');
{const d=doc0();mk(d,{id:'pl',symbolId:'plane',x:0,y:0});mk(d,{id:'ac',symbolId:'act',x:300,y:0});out.planeIds=ids(d.components[0]);out.actSpecs=specs(d.components[1]);}

// Step 4: legacy stored forms, idempotent normalization, nothing written into the array.
{
  const file={schema:D.DOCUMENT_SCHEMA,id:'legacy',revision:0,references:[],components:[
    {id:'plain',symbolId:'act',x:0,y:0},
    {id:'std',symbolId:'buffer',x:300,y:0,config:{attachmentDefaults:'standard',attachmentPoints:[{id:'aux',side:'bottom',t:.25,defaultFlow:'duplex'}]}},
    {id:'imp',symbolId:'gate',x:600,y:0,config:{attachmentPoints:[{id:'aux2',compatId:'aux-2',side:'bottom',t:.75}]}},
    {id:'non',symbolId:'hold',x:900,y:0,config:{attachmentDefaults:'none',attachmentPoints:[{id:'only',side:'left',t:.5,flow:'in'}]}},
    {id:'pls',symbolId:'plane',x:0,y:400,config:{attachmentDefaults:'standard'}}
  ],wires:[
    {id:'k1',a:'plain',aSide:'out',b:'std',bSide:'in'},
    {id:'k2',a:'std',aAttachment:{pointId:'aux'},aSide:'aux',b:'non',bSide:'only'},
    {id:'k3',a:'imp',aSide:'aux-2',b:'pls',bSide:'control'}
  ]};
  const stored=Object.fromEntries(file.components.map(c=>[c.id,clone(c.config||{})]));
  const once=D.documentFromFilePayload(clone(file));
  const twice=D.normalizeDocument(D.normalizeDocument(clone(once)));
  const view=d=>({points:Object.fromEntries(d.components.map(c=>[c.id,ids(c)])),arrays:Object.fromEntries(d.components.map(c=>[c.id,c.config.attachmentPoints??null])),modes:Object.fromEntries(d.components.map(c=>[c.id,c.config.attachmentDefaults??null])),wires:d.wires.map(w=>[w.id,w.aAttachment?.pointId,w.bAttachment?.pointId])});
  out.legacy={stored:Object.fromEntries(Object.entries(stored).map(([k,v])=>[k,v.attachmentPoints??null])),once:view(once),twice:view(twice),again:view(reload(twice)),valid:D.validateDocument(once)};
}

// Step 3 + 6: an edit that sets the complete list, stored in the smallest form.
{
  const d=doc0();mk(d,{id:'a',symbolId:'act',x:0,y:0});mk(d,{id:'b',symbolId:'act',x:400,y:0});
  const w=mkw(d,{id:'k1',a:'a',aSide:'out',b:'b',bSide:'in'});
  const r={wire:w.ok};
  // Additions under 'standard' keep the template: stored as additions only, channels normalized.
  r.add=upd(d,'a',{config:{attachmentPoints:[{id:'x',side:'bottom',t:.4,flow:'out'}]}});
  r.addStored={mode:d.components[0].config.attachmentDefaults??null,points:d.components[0].config.attachmentPoints,ids:ids(d.components[0])};
  // A complete list under 'none' that keeps every template port unchanged collapses to 'standard' + additions.
  r.full=upd(d,'a',{config:{attachmentDefaults:'none',attachmentPoints:[...JSON.parse(process.argv[3]),{id:'x',side:'bottom',t:.4,flow:'out'},{id:'y',side:'bottom',t:.8,flow:'in',label:'Y'}]}});
  r.fullStored={mode:d.components[0].config.attachmentDefaults??null,points:d.components[0].config.attachmentPoints,ids:ids(d.components[0])};
  // Removing a template port (top) that no Wire ends on: stored as 'none' + the full list, and reloads the same.
  r.remove=upd(d,'a',{config:{attachmentDefaults:'none',attachmentPoints:[{id:'left',compatId:'in',side:'left',t:.5,flow:'in'},{id:'right',compatId:'out',side:'right',t:.5,flow:'out'}]}});
  r.removeStored={mode:d.components[0].config.attachmentDefaults??null,points:d.components[0].config.attachmentPoints,ids:ids(d.components[0])};
  const saved=D.compactDocument(d);r.saved=saved.components.find(c=>c.id==='a').config;
  const back=reload(d);r.reloaded={ids:ids(back.components.find(c=>c.id==='a')),wire:[back.wires[0].aAttachment.pointId,back.wires[0].bAttachment.pointId],norm:ids(D.normalizeDocument(clone(back)).components.find(c=>c.id==='a'))};
  // Refusals: receipt not ok, revision and record unchanged.
  const before=JSON.stringify(d.components[0]),rev=d.revision;
  const refusals={
    dupId:[{id:'p',side:'left',t:.1,flow:'in'},{id:'p',side:'right',t:.1,flow:'out'}],
    badSide:[{id:'p',side:'middle',t:.1,flow:'in'}],
    badT:[{id:'p',side:'left',t:1.5,flow:'in'}],
    badFlow:[{id:'p',side:'left',t:.1,flow:'sideways'}],
    dupChannel:[{id:'p',side:'left',t:.1,flow:'in',channels:[{id:'c'},{id:'c'}]}],
    orphan:[{id:'left',compatId:'in',side:'left',t:.5,flow:'in'}]
  };
  r.refused={};
  for(const [k,list] of Object.entries(refusals)){const rc=upd(d,'a',{config:{attachmentDefaults:'none',attachmentPoints:list}});r.refused[k]={ok:rc.ok,msg:rc.error?.message||'',rev:rc.revisionAfter===rev&&d.revision===rev,same:JSON.stringify(d.components[0])===before}}
  out.edit=r;
}

// Step 3 + 7: five ports on four sides, two channels on one; channel matching on binding.
{
  const d=doc0();
  const five=[{id:'w',side:'left',t:.5,flow:'in'},{id:'e',side:'right',t:.5,flow:'out'},{id:'n',side:'top',t:.5,flow:'control'},{id:'s1',side:'bottom',t:.25,flow:'duplex',channels:[{id:'main'},{id:'aux'}]},{id:'s2',side:'bottom',t:.75,flow:'trigger',channels:[{id:'aux'}]}];
  mk(d,{id:'f',symbolId:'act',x:0,y:0});
  const set=upd(d,'f',{config:{attachmentDefaults:'none',attachmentPoints:five}});
  mk(d,{id:'g',symbolId:'act',x:400,y:0});
  const f=d.components.find(c=>c.id==='f');
  const r={set:set.ok,mode:f.config.attachmentDefaults,specs:specs(f),stored:f.config.attachmentPoints};
  r.mismatch=mkw(d,{id:'k1',a:'f',aAttachment:{pointId:'s2'},b:'g',bSide:'in'});
  r.shared=mkw(d,{id:'k2',a:'f',aAttachment:{pointId:'s1'},b:'g',bSide:'in'});
  r.sharedIds=D.sharedChannelIds(d,'f','s1','g','in');
  r.rebind=op(d,{op:'update',resource:'wire',resourceId:'k2',patch:{aAttachment:{kind:'attachment-ref',componentId:'f',pointId:'s2'}}});
  r.k2After=d.wires.find(w=>w.id==='k2').aAttachment.pointId;
  const free=D.makeWire(d,{id:'k3',aAttachment:{kind:'free',x:0,y:0},b:'g',bSide:'in'});d.wires.push(free);
  let bindErr='';try{D.bindWireEndpoint(d,free,'a','f','s2')}catch(e){bindErr=e.message}
  r.bindErr=bindErr;r.k3After=free.aAttachment;
  const bad=clone(D.compactDocument(d));bad.wires.push({id:'k9',a:'f',aSide:'s2',aAttachment:{kind:'attachment-ref',componentId:'f',pointId:'s2'},b:'g',bSide:'in'});
  r.validate=D.validateDocument(D.makeDocument(bad));
  out.channels=r;
}

// Step 5 + 9: every example round-trips with the same port ids, bound ports and stored forms.
out.examples={};
for(const file of JSON.parse(process.argv[4])){
  const raw=JSON.parse(fs.readFileSync(file,'utf8')),rawDoc=raw.document||raw;
  const first=D.documentFromFilePayload(raw),saved=D.compactDocument(first),second=D.documentFromFilePayload(JSON.parse(JSON.stringify({...saved,schema:D.DOCUMENT_SCHEMA})));
  const pv=d=>({points:d.components.map(c=>[c.id,ids(c)]),wires:d.wires.map(w=>[w.id,w.aAttachment?.pointId??null,w.bAttachment?.pointId??null,w.aSide,w.bSide])});
  const stored=cs=>(cs||[]).map(c=>[c.id,c.config?.attachmentDefaults??null,c.config?.attachmentPoints??null]);
  out.examples[file]={first:pv(first),second:pv(second),raw:stored(rawDoc.components),saved:stored(saved.components),valid:D.validateDocument(first).ok};
}
console.log(JSON.stringify(out));
"""


def typed_symbols() -> list[str]:
    text = (ROOT / 'src/00-state.js').read_text(encoding='utf-8')
    symbols = json.loads(re.search(r'const SYMBOLS = (\[.*?\]);\n', text).group(1))
    return [s['id'] for s in symbols if s['family'] != 'PRIMITIVE' and s['id'] != 'port']


def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def http_json(url, method='GET', payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = request.Request(url, data=body, method=method, headers={'content-type': 'application/json'})
    try:
        with request.urlopen(req, timeout=4) as res:
            return res.status, json.loads(res.read())
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def rpc(base, name, args=None, call_id=1):
    status, data = http_json(base + '/mcp', 'POST', {'jsonrpc': '2.0', 'id': call_id, 'method': 'tools/call', 'params': {'name': name, 'arguments': args or {}}})
    assert status == 200, (status, data)
    result = data['result']
    return result['structuredContent'], result.get('isError', False)


def main() -> None:
    # Step 1: no hard-coded 2D port set in the attachment core.
    src = (ROOT / 'src/06-attachment-core.js').read_text(encoding='utf-8')
    for literal in ("id:'left'", "id:'right'", "id:'top'"):
        assert literal not in src, literal
    alone = node(CORE_ALONE, str(ROOT / 'src/06-attachment-core.js'))
    assert alone['bare'] == [] and alone['authored'] == ['feed'], alone
    assert [s['id'] for s in alone['zero']] == ['self'] and [s['id'] for s in alone['one']] == ['start', 'end'], alone
    assert alone['zero'][0] == {'id': 'self', 'compatId': 'out', 'side': 'point', 'role': 'self', 'defaultFlow': 'duplex', 't': .5}, alone['zero']

    examples = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'examples').glob('*.sov'))
    assert examples, 'no examples'
    r = node(CORE, str(ROOT / 'src/05-data-core.js'), json.dumps(typed_symbols()), json.dumps(TRIO), json.dumps(examples))

    # Step 2: every typed template declares the trio; the Plane declares none.
    assert len(r['symbols']) >= 10, r['symbols']
    for sym, ports in r['templates'].items():
        assert ports == TRIO, (sym, ports)
    assert 'ports' not in r['planePreset'] and r['planePreset']['attachmentDefaults'] == 'none', r['planePreset']
    assert r['planeIds'] == [], r['planeIds']
    assert r['actSpecs'] == TRIO, r['actSpecs']

    # Step 4: legacy stored forms keep their meaning; normalization is idempotent and never
    # writes template ports into the stored array; every Wire stays bound to the same port.
    lg = r['legacy']
    assert lg['valid']['ok'], lg['valid']
    exp = {'plain': ['left', 'right', 'top'], 'std': ['left', 'right', 'top', 'aux'], 'imp': ['left', 'right', 'top', 'aux2'], 'non': ['only'], 'pls': ['left', 'right', 'top']}
    for key in ('once', 'twice', 'again'):
        assert lg[key]['points'] == exp, (key, lg[key]['points'])
        assert lg[key]['wires'] == [['k1', 'right', 'left'], ['k2', 'aux', 'only'], ['k3', 'aux2', 'top']], (key, lg[key]['wires'])
    for key in ('once', 'twice'):
        assert lg[key]['arrays'] == lg['stored'], (key, lg[key]['arrays'], lg['stored'])
    assert lg['once']['modes'] == lg['twice']['modes'] == {'plain': None, 'std': 'standard', 'imp': None, 'non': 'none', 'pls': 'standard'}, lg['once']['modes']
    assert lg['again']['modes']['pls'] == 'standard', lg['again']['modes']

    # Steps 3 + 6: edits stored in the smallest form; refusals leave no trace.
    ed = r['edit']
    assert ed['wire'] and ed['add']['ok'], ed
    assert ed['addStored'] == {'mode': None, 'points': [{'id': 'x', 'side': 'bottom', 't': .4, 'flow': 'out', 'channels': [{'id': 'main'}]}], 'ids': ['left', 'right', 'top', 'x']}, ed['addStored']
    assert ed['full']['ok'] and ed['fullStored']['mode'] is None, ed['fullStored']
    assert [p['id'] for p in ed['fullStored']['points']] == ['x', 'y'] and ed['fullStored']['ids'] == ['left', 'right', 'top', 'x', 'y'], ed['fullStored']
    assert ed['fullStored']['points'][1]['label'] == 'Y', ed['fullStored']
    assert ed['remove']['ok'] and ed['removeStored']['mode'] == 'none', ed['removeStored']
    assert [p['id'] for p in ed['removeStored']['points']] == ['left', 'right'] and ed['removeStored']['ids'] == ['left', 'right'], ed['removeStored']
    assert ed['saved']['attachmentDefaults'] == 'none' and [p['id'] for p in ed['saved']['attachmentPoints']] == ['left', 'right'], ed['saved']
    assert ed['reloaded'] == {'ids': ['left', 'right'], 'wire': ['right', 'left'], 'norm': ['left', 'right']}, ed['reloaded']
    for key, want in {'dupId': 'share the id', 'badSide': 'invalid side', 'badT': 'invalid t', 'badFlow': 'invalid flow', 'dupChannel': 'repeats channel', 'orphan': 'PORT_IN_USE'}.items():
        got = ed['refused'][key]
        assert got['ok'] is False and want in got['msg'] and got['rev'] and got['same'], (key, got)

    # Steps 3 + 7: five ports on four sides, two channels on one; channel matching on binding.
    ch = r['channels']
    assert ch['set'] and ch['mode'] == 'none', ch
    assert [(s['id'], s['side']) for s in ch['specs']] == [('w', 'left'), ('e', 'right'), ('n', 'top'), ('s1', 'bottom'), ('s2', 'bottom')], ch['specs']
    assert {s['side'] for s in ch['specs']} == {'left', 'right', 'top', 'bottom'}
    assert ch['specs'][3]['channels'] == [{'id': 'main'}, {'id': 'aux'}] and ch['specs'][0]['channels'] == [{'id': 'main'}], ch['specs']
    assert all('channels' in p for p in ch['stored']), ch['stored']
    assert ch['mismatch']['ok'] is False and 'CHANNEL_MISMATCH' in ch['mismatch']['error']['message'], ch['mismatch']
    assert ch['shared']['ok'] and ch['sharedIds'] == ['main'], (ch['shared'], ch['sharedIds'])
    assert ch['rebind']['ok'] is False and 'CHANNEL_MISMATCH' in ch['rebind']['error']['message'] and ch['k2After'] == 's1', ch
    assert 'CHANNEL_MISMATCH' in ch['bindErr'] and ch['k3After']['kind'] == 'free', ch
    assert not ch['validate']['ok'] and any('k9' in e and 'CHANNEL_MISMATCH' in e for e in ch['validate']['errors']), ch['validate']

    # Steps 5 + 9: every example round-trips unchanged; stored forms are saved as authored.
    for file, ex in r['examples'].items():
        assert ex['valid'], file
        assert ex['first'] == ex['second'], (file, ex['first'], ex['second'])
        assert ex['saved'] == ex['raw'], (file, ex['saved'], ex['raw'])
        assert all(w[1] and w[2] for w in ex['first']['wires']), (file, ex['first']['wires'])

    # Step 6 over HTTP and MCP: the same refusal, no revision, no history entry.
    with tempfile.TemporaryDirectory() as td:
        port = free_port()
        base = f'http://127.0.0.1:{port}'
        proc = subprocess.Popen(['node', str(ROOT / 'mcp/server.mjs'), '--port', str(port), '--file', str(Path(td) / 'ports.sov')], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            for _ in range(80):
                try:
                    if http_json(base + '/api/v1/formats')[0] == 200:
                        break
                except Exception:
                    time.sleep(.05)
            else:
                raise AssertionError('server did not start')
            assert http_json(base + '/api/v1/components', 'POST', {'id': 'a', 'symbolId': 'act', 'x': 0, 'y': 0})[0] == 201
            assert http_json(base + '/api/v1/components', 'POST', {'id': 'b', 'symbolId': 'act', 'x': 400, 'y': 0})[0] == 201
            status, wire = http_json(base + '/api/v1/wires', 'POST', {'id': 'k1', 'a': 'a', 'aSide': 'out', 'b': 'b', 'bSide': 'in'})
            assert status == 201 and wire['ok'], wire
            rev = wire['revisionAfter']
            orphan = {'config': {'attachmentDefaults': 'none', 'attachmentPoints': [{'id': 'left', 'compatId': 'in', 'side': 'left', 't': .5, 'flow': 'in'}]}}
            status, denied = http_json(base + '/api/v1/components/a', 'PATCH', orphan)
            assert status == 400 and not denied['ok'] and 'PORT_IN_USE' in denied['error']['message'] and denied['revisionAfter'] == rev, denied
            mcp, is_error = rpc(base, 'schematic.update', {'resource': 'component', 'id': 'a', 'patch': orphan}, 2)
            assert is_error and not mcp['ok'] and 'PORT_IN_USE' in mcp['error']['message'] and mcp['revisionAfter'] == rev, mcp
            status, mismatch = http_json(base + '/api/v1/components/b', 'PATCH', {'config': {'attachmentPoints': [{'id': 'q', 'side': 'bottom', 't': .5, 'flow': 'in', 'channels': [{'id': 'aux'}]}]}})
            assert status == 200 and mismatch['ok'], mismatch
            status, refused = http_json(base + '/api/v1/wires', 'POST', {'id': 'k2', 'a': 'a', 'aSide': 'out', 'b': 'b', 'bAttachment': {'pointId': 'q'}})
            assert status == 400 and 'CHANNEL_MISMATCH' in refused['error']['message'], refused
            # The refusals entered no history: undo reverts the last successful edit (b's ports), then the Wire.
            undo, is_error = rpc(base, 'schematic.history.undo', {}, 3)
            assert not is_error and not any(p.get('id') == 'q' for c in undo['components'] for p in (c.get('config', {}).get('attachmentPoints') or [])), undo
            assert any(w['id'] == 'k1' for w in undo['wires']), undo
            undo, is_error = rpc(base, 'schematic.history.undo', {}, 4)
            assert not is_error and not undo['wires'], undo
        finally:
            proc.terminate()
            proc.wait(timeout=5)
    print('PASS declared ports QA')


if __name__ == '__main__':
    main()
