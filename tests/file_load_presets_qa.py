"""File loading applies palette presets.

A sparse Plane or Point record in a .sov must load with the same preset fields that
`makeComponent` gives an API-created one (form, presentation, signalMode, attachmentDefaults),
while anything the record does write is left as written. Node only; no browser.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

JS = r"""
const D=require(process.argv[1]);
const doc=D.documentFromFilePayload({schema:D.DOCUMENT_SCHEMA,id:'t',revision:0,references:[],wires:[],components:[
  {id:'pl',symbolId:'plane',x:600,y:300,config:{label:'Region'}},
  {id:'pt',symbolId:'point',x:440,y:300,canvasId:'canvas:component:pl',parentId:'pl',placement:{kind:'edge',hostId:'pl',side:'left',t:.5},config:{ports:{out:{face:'both'}}}},
  {id:'pa',symbolId:'path',x:200,y:500},
  {id:'closed',symbolId:'plane',x:900,y:300,form:{dimension:2,regions:{interior:{state:'closed'}}},config:{signalMode:'source',attachmentDefaults:'standard',presentation:{size:{w:100,h:80}}}},
  {id:'c',symbolId:'act',x:100,y:100,config:{label:'A'}}
]});
const api=D.makeComponent(D.makeDocument({}),{id:'apl',symbolId:'plane',x:0,y:0});
const pick=c=>({form:c.form,signalMode:c.config.signalMode,presentation:c.config.presentation??null,attachmentDefaults:c.config.attachmentDefaults??null,ports:Object.keys(c.config.ports)});
const out={};for(const c of doc.components)out[c.id]=pick(c);out.api=pick(api);out.valid=D.validateDocument(doc);
// An authored 'standard' on a Plane survives create, a later normalization pass, and save.
const stdApi=D.makeComponent(D.makeDocument({}),{id:'astd',symbolId:'plane',x:0,y:0,config:{attachmentDefaults:'standard'}});
const again=D.normalizeDocument({components:[JSON.parse(JSON.stringify(stdApi))],wires:[]}).components[0];
const saved=D.compactDocument(doc),ad=c=>c.config.attachmentDefaults??null;
out.std={api:ad(stdApi),again:ad(again),againPorts:Object.keys(again.config.ports),savedClosed:ad(saved.components.find(c=>c.id==='closed')),savedPl:ad(saved.components.find(c=>c.id==='pl')),
  actSaved:ad(D.compactComponent(D.makeComponent(D.makeDocument({}),{id:'a',symbolId:'act',x:0,y:0,config:{attachmentDefaults:'standard'}})))};
console.log(JSON.stringify(out));
"""


def main() -> None:
    proc = subprocess.run(['node', '-e', JS, str(ROOT / 'src/05-data-core.js')], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    r = json.loads(proc.stdout)
    assert r['valid']['ok'], r['valid']
    pl, api = r['pl'], r['api']
    # A sparse Plane loads exactly like an API-created Plane.
    assert pl['form'] == api['form'], (pl['form'], api['form'])
    assert pl['form']['regions']['interior']['state'] == 'open'
    assert pl['attachmentDefaults'] == 'none' and pl['ports'] == [], pl
    assert pl['presentation'] == api['presentation'] and pl['presentation']['size'] == {'w': 320, 'h': 220}, pl['presentation']
    # A sparse Point is 0D, relay, one attachment point, and keeps its authored face.
    pt = r['pt']
    assert pt['form']['dimension'] == 0 and pt['signalMode'] == 'relay' and pt['ports'] == ['out'], pt
    assert pt['presentation']['backdrop'] == 'none', pt['presentation']
    # A sparse Path is 1D with endpoint points.
    assert r['pa']['form']['dimension'] == 1 and r['pa']['ports'] == ['in', 'out'], r['pa']
    # Authored fields win over the preset, field by field.
    cl = r['closed']
    assert cl['form']['regions']['interior']['state'] == 'closed', cl['form']
    assert cl['signalMode'] == 'source' and cl['attachmentDefaults'] in (None, 'standard') and cl['ports'] == ['in', 'out', 'control'], cl
    assert cl['presentation'] == {'size': {'w': 100, 'h': 80}}, cl['presentation']
    # A typed Component is untouched: no preset exists for it.
    assert r['c']['form']['dimension'] == 2 and r['c']['ports'] == ['in', 'out', 'control'] and r['c']['presentation'] is None, r['c']
    # An authored 'standard' on a Plane is kept on the runtime record, survives re-normalization,
    # and is saved; 'none' is always saved; a typed Component's 'standard' is the default and is not.
    assert r['std'] == {'api': 'standard', 'again': 'standard', 'againPorts': ['in', 'out', 'control'], 'savedClosed': 'standard', 'savedPl': 'none', 'actSaved': None}, r['std']
    print('PASS file load presets QA')


if __name__ == '__main__':
    main()
