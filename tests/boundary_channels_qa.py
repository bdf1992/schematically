"""Boundary channels (G07, ATTACHMENT-POINT-MODEL.md "A Point's self").

A hosted boundary Point passes through the channels of the Wires bound to it by declaring
its own `self` port (`{id: 'self', channels: [...]}`); an undeclared Point keeps carrying
only the default channel, `main` (absence is refused, never defaulted - R-02), so a Wire
carrying named channels (video, event, narration) is refused crossing it with
CHANNEL_MISMATCH until the Point declares them. `schematic.graph.query`'s `reach` verb takes
an optional `channel` and follows only Wires whose two bound ports share it, independent of
a wire's own `config.accepts` (which still governs simulation routing at a junction).

Runs src/05-data-core.js and src/07-graph-core.js in Node, with no browser.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r"""
require('./src/06-attachment-core.js');
const D=require('./src/05-data-core.js');
const G=require('./src/07-graph-core.js');

const TRACKS=[{id:'video'},{id:'event'},{id:'narration'}];

// A Plane with a Point hosted on its edge (placement kind 'edge'); its self declares the
// three tracks. A Web booth card outside the Plane declares tracks-out carrying the three;
// a Recording card inside declares tracks-in carrying the three.
function build(){
  const d=D.makeDocument({id:'boundary-channels'});
  D.create(d,'component',{id:'plane',symbolId:'plane',x:400,y:300,config:{label:'Plane'}});
  D.create(d,'component',{id:'port',symbolId:'point',x:400,y:160,
    canvasId:'canvas:component:plane',parentId:'plane',
    placement:{kind:'edge',hostId:'plane',side:'top',t:.5},
    config:{ports:{out:{face:'both'}},attachmentPoints:[{id:'self',channels:TRACKS}]}});
  D.create(d,'component',{id:'web-booth',symbolId:'act',x:400,y:0,
    config:{label:'Web booth',attachmentPoints:[{id:'tracks-out',side:'left',t:.25,flow:'out',channels:TRACKS}]}});
  D.create(d,'component',{id:'recording',symbolId:'act',x:400,y:300,
    canvasId:'canvas:component:plane',parentId:'plane',
    config:{label:'Recording',attachmentPoints:[{id:'tracks-in',side:'right',t:.5,flow:'in',channels:TRACKS}]}});
  D.create(d,'wire',{id:'w-outer',a:'web-booth',aAttachment:{pointId:'tracks-out'},b:'port',bAttachment:{pointId:'self'},canvasId:'canvas:global'});
  D.create(d,'wire',{id:'w-inner',a:'port',aAttachment:{pointId:'self'},b:'recording',bAttachment:{pointId:'tracks-in'},canvasId:'canvas:component:plane'});
  return d;
}

const out={};
const doc=build();

// Both Wires validate; each Wire's channels from connectionReachability are exactly the three.
out.valid=D.validateDocument(doc);
out.outerChannels=D.connectionReachability(doc,'web-booth','tracks-out','port','self').channels;
out.innerChannels=D.connectionReachability(doc,'port','self','recording','tracks-in').channels;

// The same document with the Point's declaration removed: an undeclared Point carries only
// main, so both Wires are refused with CHANNEL_MISMATCH.
const undeclared=JSON.parse(JSON.stringify(doc));
undeclared.components.find(c=>c.id==='port').config.attachmentPoints=[];
out.undeclaredValid=D.validateDocument(undeclared);
out.undeclaredOuter=D.connectionReachability(undeclared,'web-booth','tracks-out','port','self');
out.undeclaredInner=D.connectionReachability(undeclared,'port','self','recording','tracks-in');

// Bite check (contract step 7): with every port's shared-channel set forced to ['main'],
// the suite must fail; left in as a comment, not run here (the contract runs it by hand and
// restores the source).

// graph.query reach with a channel argument crosses the boundary Point only on that channel.
out.reachVideo=G.query(doc,'reach',{from:'web-booth',channel:'video'});
out.reachMain=G.query(doc,'reach',{from:'web-booth',channel:'main'});
out.reachNone=G.query(doc,'reach',{from:'web-booth'});

console.log(JSON.stringify(out));
"""


def main():
    proc = subprocess.run(['node', '-e', SCRIPT], cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(proc.stdout + proc.stderr)
    out = json.loads(proc.stdout)

    assert out['valid']['ok'], out['valid']
    assert out['outerChannels'] == ['video', 'event', 'narration'], out['outerChannels']
    assert out['innerChannels'] == ['video', 'event', 'narration'], out['innerChannels']

    assert out['undeclaredValid']['ok'] is False, out['undeclaredValid']
    errors = out['undeclaredValid']['errors']
    assert any('w-outer' in e and 'CHANNEL_MISMATCH' in e for e in errors), errors
    assert any('w-inner' in e and 'CHANNEL_MISMATCH' in e for e in errors), errors
    assert out['undeclaredOuter']['ok'] is False and 'CHANNEL_MISMATCH' in out['undeclaredOuter']['reason'], out['undeclaredOuter']
    assert out['undeclaredInner']['ok'] is False and 'CHANNEL_MISMATCH' in out['undeclaredInner']['reason'], out['undeclaredInner']

    assert out['reachVideo']['ok'] and 'recording' in out['reachVideo']['nodes'], out['reachVideo']
    assert out['reachVideo']['channel'] == 'video', out['reachVideo']
    assert 'recording' not in out['reachMain']['nodes'], out['reachMain']
    assert 'recording' in out['reachNone']['nodes'], out['reachNone']

    print('PASS boundary channels QA')


if __name__ == '__main__':
    main()
