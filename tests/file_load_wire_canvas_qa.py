"""File loading derives a wire's surface from its ends.

A .sov may omit wire.canvasId. On load the carrier surface is derived the way wire.create
does it: the surface both bound ends share, preferring a local surface over the global one.
A written canvasId is kept as written. An unreachable pair stays null and validation reports
it. Node only; no browser.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

JS = r"""
const D=require(process.argv[1]);
const doc=D.documentFromFilePayload({schema:D.DOCUMENT_SCHEMA,id:'t',revision:0,references:[],components:[
  {id:'src',symbolId:'act',x:100,y:300},
  {id:'pl',symbolId:'plane',x:600,y:300},
  {id:'pin',symbolId:'point',x:440,y:300,canvasId:'canvas:component:pl',parentId:'pl',placement:{kind:'edge',hostId:'pl',side:'left',t:.5},config:{ports:{out:{face:'both'}}}},
  {id:'stage',symbolId:'hold',x:640,y:300,canvasId:'canvas:component:pl',parentId:'pl'},
  {id:'sink',symbolId:'receipt',x:1000,y:300},
  {id:'outer',symbolId:'buffer',x:100,y:700,form:{dimension:2,regions:{interior:{state:'open'}}}},
  {id:'inner',symbolId:'act',x:100,y:700,canvasId:'canvas:component:outer',parentId:'outer'}
],wires:[
  {id:'k1',a:'src',aSide:'out',b:'pin',bSide:'out'},
  {id:'k2',a:'pin',aSide:'out',b:'stage',bSide:'in'},
  {id:'k3',a:'stage',aSide:'out',b:'sink',bSide:'in',canvasId:'canvas:component:pl'},
  {id:'k4',a:'inner',aSide:'out',b:'sink',bSide:'in'},
  {id:'k5',aAttachment:{kind:'free',x:10,y:10},bAttachment:{kind:'free',x:90,y:10}}
]});
const out={};for(const w of doc.wires)out[w.id]=w.canvasId??null;out.valid=D.validateDocument(doc);
console.log(JSON.stringify(out));
"""


def main() -> None:
    proc = subprocess.run(['node', '-e', JS, str(ROOT / 'src/05-data-core.js')], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    r = json.loads(proc.stdout)
    # Derived from the ends: outer wire on the global canvas, interior wire on the host's surface.
    assert r['k1'] == 'canvas:global', r
    assert r['k2'] == 'canvas:component:pl', r
    # Written value is kept as written even when the ends do not share it; validation is the judge.
    assert r['k3'] == 'canvas:component:pl', r
    # Reach-through has no shared surface: stays null and is reported.
    assert r['k4'] is None, r
    assert any(e.startswith('wire k4') and 'reach-through' in e for e in r['valid']['errors']), r['valid']
    # Two free ends default to the global canvas.
    assert r['k5'] == 'canvas:global', r
    print('PASS file load wire canvas QA')


if __name__ == '__main__':
    main()
