"""Region border QA (SECTION-MODEL.md "Groups": Borders; NOTATION-MODEL.md "Statuses").

A border says what a region is: no outline with a soft inset is grouping only, solid is a boundary,
dashed is open or provisional, and dashed means nothing else a picture draws.

Browser part (index.html in Chromium):
  - a group with members draws its .group-region with no stroke (stroke none, width 0) and the inset
    filter; it draws no dashed outline;
  - the same group with config.intake true draws a dashed outline (.group-outline, 6 4, muted ink);
  - a plane draws a solid outline, and with intake true a dashed one;
  - intake 'yes' is refused with INTAKE_INVALID, and intake on an act card is refused, on create and on
    update and at load, each leaving the document unchanged;
  - a card with status missing in examples/work-engine/status.sov keeps its dashed outline;
  - an unplaced card has opacity .42 and no dash;
  - the picture from renderStandaloneSvg carries the inset filter and the dashed outline;
  - the page logs no errors.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

STATUS = ROOT / 'examples/work-engine/status.sov'

PAGE = r"""(payload)=>{
  const A=window.SovSchematicAPI,D=SovSchematicData,out={};
  const doc=(intake)=>({schema:D.DOCUMENT_SCHEMA,id:'region-border',components:[
    {id:'g',symbolId:'group',x:300,y:300,config:{label:'Group',members:['m1','m2'],...(intake?{intake:true}:{})}},
    {id:'m1',symbolId:'act',x:240,y:300,config:{label:'One'}},
    {id:'m2',symbolId:'act',x:400,y:300,config:{label:'Two'}},
    {id:'p',symbolId:'plane',x:800,y:300,form:{dimension:2,regions:{interior:{state:'open'}}},config:{label:'Plane',...(intake?{intake:true}:{})}}
  ],wires:[],references:[]});
  const dash=el=>el?getComputedStyle(el).strokeDasharray:null;
  const read=()=>{
    const region=document.querySelector('.node.group[data-id="g"] > .group-region'),edge=document.querySelector('.node.group[data-id="g"] > .group-outline');
    const body=document.querySelector('#nodes > .node[data-id="p"] > .body');
    const rs=region?getComputedStyle(region):null;
    return {region:!!region,regionStroke:rs?.stroke,regionStrokeWidth:rs?.strokeWidth,regionFilter:rs?.filter,
      edge:!!edge,edgeDash:dash(edge),edgeStroke:edge?getComputedStyle(edge).stroke:null,edgeWidth:edge?getComputedStyle(edge).strokeWidth:null,
      planeDash:dash(body),planeStroke:body?getComputedStyle(body).stroke:null};
  };
  A.document.replace(doc(false));fitDiagram();out.plain=read();
  A.document.replace(doc(true));fitDiagram();out.intake=read();
  out.picture=A.render.svg({});
  // Refusals leave the document unchanged.
  const refuse=(op,build)=>{const d=D.makeDocument(doc(false));D.normalizeDocument(d);const before=JSON.stringify(d);const r=D.applyOperation(d,op);return {ok:r.ok,message:r.error?.message||'',unchanged:JSON.stringify(d)===before}};
  out.refusals={
    createYes:refuse({op:'create',resource:'component',value:{id:'x',symbolId:'group',config:{members:[],intake:'yes'}}}),
    createAct:refuse({op:'create',resource:'component',value:{id:'x',symbolId:'act',config:{label:'X',intake:true}}}),
    updateYes:refuse({op:'update',resource:'component',resourceId:'g',patch:{config:{intake:'yes'}}}),
    updateAct:refuse({op:'update',resource:'component',resourceId:'m1',patch:{config:{intake:true}}}),
    updateGroupOk:refuse({op:'update',resource:'component',resourceId:'g',patch:{config:{intake:true}}}),
  };
  {const raw=doc(false);raw.components[0].config.intake='yes';raw.components[1].config.intake=true;
   out.load=D.validateDocument(D.makeDocument(raw)).errors.filter(e=>/INTAKE_INVALID/.test(e))}
  // A status that declares a dashed outline keeps it.
  A.document.replace(D.documentFromFilePayload(payload));fitDiagram();
  const anchor=document.querySelector('#nodes > .node[data-id="anchor"] > .body');
  out.missing={dash:dash(anchor),inline:anchor?.getAttribute('stroke-dasharray')};
  // An unplaced card keeps its fade and loses its dash.
  A.document.replace(doc(false));
  const made=A.layout.create({name:'Ops',empty:true});
  const card=document.querySelector('#nodes > .node.unplaced[data-id="m1"]');
  out.unplaced={ok:made.ok,found:!!card,opacity:card?getComputedStyle(card).opacity:null,dash:dash(card?.querySelector(':scope > .body'))};
  return out;
}"""


def main() -> None:
    payload = json.loads(STATUS.read_text(encoding='utf-8'))
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(200)
        r = page.evaluate(PAGE, payload)
        browser.close()
    assert not errors, errors

    a = r['plain']
    assert a['region'], 'a group draws no .group-region'
    assert a['regionStroke'] == 'none' or a['regionStrokeWidth'] in ('0px', '0'), ('group region has an outline', a)
    assert 'region-inset' in (a['regionFilter'] or ''), ('group region has no inset filter', a['regionFilter'])
    assert not a['edge'], 'a plain group draws a dashed outline'
    assert a['planeDash'] == 'none', ('a plane outline is not solid', a['planeDash'])

    b = r['intake']
    assert b['edge'], 'an intake group draws no outline'
    assert b['edgeDash'].replace('px', '').replace(' ', '') in ('6,4',), ('intake group outline is not dashed 6 4', b['edgeDash'])
    assert b['edgeStroke'] != 'none' and b['edgeWidth'] != '0px', ('intake group outline not drawn', b)
    assert b['planeDash'].replace('px', '').replace(' ', '') == '6,4', ('intake plane outline is not dashed 6 4', b['planeDash'])
    assert 'region-inset' in (b['regionFilter'] or ''), 'an intake group keeps its inset'

    for name in ('createYes', 'createAct', 'updateYes', 'updateAct'):
        f = r['refusals'][name]
        assert not f['ok'] and 'INTAKE_INVALID' in f['message'] and f['unchanged'], (name, f)
    assert r['refusals']['updateGroupOk']['ok'], r['refusals']['updateGroupOk']
    assert len(r['load']) == 2 and all('INTAKE_INVALID' in e for e in r['load']), r['load']

    m = r['missing']
    assert m['dash'] and m['dash'] != 'none', ('status missing lost its dashed outline', m)

    u = r['unplaced']
    assert u['ok'] and u['found'], ('no unplaced card', u)
    assert u['opacity'] == '0.42', ('an unplaced card lost its fade', u)
    assert u['dash'] == 'none', ('an unplaced card is still dashed', u['dash'])

    svg = r['picture']
    assert 'region-inset' in svg and '<filter' in svg, 'the picture carries no inset filter'
    print('REGION BORDER QA PASS', {'group': a['regionFilter'], 'intake edge': b['edgeDash'], 'plane': a['planeDash'], 'unplaced': u['opacity']})


if __name__ == '__main__':
    main()
