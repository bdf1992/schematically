"""Export reads a temporary WS root, refuses unsafe output and retains provenance."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('exporter',ROOT/'scripts/export_workstation_mission.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
fixture=json.loads((ROOT/'tests/fixtures/work-graph/mission.json').read_text())
checks=0

def raises(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('Expected export refusal')

with tempfile.TemporaryDirectory() as temp:
    base=Path(temp);root=base/'ws';missions=root/'control/missions';tasks=root/'control/tasks'
    missions.mkdir(parents=True);tasks.mkdir()
    mission={**fixture['mission'],'record_type':'Mission','private_extra':'not exported'}
    mission_file=missions/(mission['id']+'.json');mission_file.write_text(json.dumps(mission))
    for task in fixture['tasks']:
        (tasks/(task['id']+'.json')).write_text(json.dumps({**task,'record_type':'Task','github_authority':{'token':'never export'},'private_extra':'not exported'}))
    before={p:p.read_bytes() for p in root.rglob('*.json')}
    packet=module.collect(root,mission['id'])
    assert packet['source']['consistency']=='sampled-files'
    assert packet['source']['revision'].startswith('sha256:')
    assert 'private_extra' not in packet['mission'] and all('github_authority' not in t for t in packet['tasks'])
    assert all(p.read_bytes()==raw for p,raw in before.items());checks+=1
    second=module.collect(root,mission['id']);assert second['source']['revision']==packet['source']['revision'];checks+=1
    mission_file.write_text(json.dumps({**mission,'summary':'Changed'}));assert module.collect(root,mission['id'])['source']['revision']!=packet['source']['revision'];checks+=1
    raises(lambda:module.collect(root,'../../escape'));raises(lambda:module.parse(b'{"id":1,"id":2}'));raises(lambda:module.parse(b'{"value":NaN}'));checks+=1
    out=base/'input.json'
    def run(output):
        return subprocess.run([sys.executable,str(ROOT/'scripts/export_workstation_mission.py'),'--root',str(root),'--mission',mission['id'],'--out',str(output)],capture_output=True,text=True)
    assert run(out).returncode==0;assert run(out).returncode==2;assert run(root/'bad.json').returncode==2;assert not (root/'bad.json').exists();checks+=1
    package=base/'output.sovpak'
    command=['node',str(ROOT/'scripts/workstation_graph.mjs'),str(out),str(package)]
    assert subprocess.run(command,capture_output=True).returncode==0
    assert json.loads(package.read_text())['meta']['graph']['source']['revision']==module.collect(root,mission['id'])['source']['revision']
    assert subprocess.run(command,capture_output=True).returncode!=0;checks+=1
    broken=tasks/'broken.json';broken.write_text('{broken');raises(lambda:module.collect(root,mission['id']));broken.unlink();checks+=1
    # A symlinked record cannot pull content from outside the supplied root.
    external=base/'external.json';external.write_text(json.dumps({**fixture['tasks'][0],'record_type':'Task'}))
    try:
        (tasks/'outside.json').symlink_to(external)
    except OSError:
        print('UNAVAILABLE symlink case: host did not permit symlink creation')
    else:
        raises(lambda:module.collect(root,mission['id']));checks+=1
print(f'WORK GRAPH EXPORT PASS: {checks} cases')
