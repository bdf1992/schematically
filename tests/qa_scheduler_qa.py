"""Scheduler preserves the queue, bounds overlap and waits before exclusive work."""
import ast, json, os, runpy, tempfile, threading, time, shutil, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
qa=runpy.run_path(str(ROOT/'scripts/qa.py'),run_name='scheduler_check')
expected=json.loads((ROOT/'tests/fixtures/qa-queue.json').read_text(encoding='utf-8'))
assert {key:qa[key] for key in expected}==expected, 'no authoritative check was removed or reordered'
assert not qa['parallel_safe']('tests/performance_regression_qa.py')
assert not qa['parallel_safe']('tests/served_editor_qa.py')
assert qa['parallel_safe']('tests/ports_panel_qa.py')

run_browser=qa['run_browser']
lock=threading.Lock()
active=0
maximum=0
seen=[]
def check(path):
    global active,maximum
    with lock:
        if path=='exclusive':assert active==0
        active+=1;maximum=max(maximum,active);seen.append(path)
    time.sleep(.02)
    with lock:active-=1
    return .02
run_browser.__globals__['run']=check
run_browser.__globals__['parallel_safe']=lambda path:path!='exclusive'
queue=['a','b','exclusive','c','d','e']
run_browser(queue,2)
assert sorted(seen)==sorted(queue) and maximum==2 and active==0
try:run_browser(queue,9)
except ValueError:pass
else:raise AssertionError('worker ceiling bypassed')
def failure(path):
    seen.append(path)
    if path=='bad':raise RuntimeError('retained failure')
    return 0
run_browser.__globals__['run']=failure
try:run_browser(['good','bad','other'],2)
except RuntimeError:pass
else:raise AssertionError('failure became a pass')
assert 'other' in seen, 'all started peers settle before failure leaves the batch'
collector=runpy.run_path(str(ROOT/'tests/arch_browser_coverage.py'),run_name='coverage_offset_check')
with tempfile.TemporaryDirectory() as temporary:
    base=Path(temporary);(base/'src').mkdir();(base/'coverage').mkdir()
    source="const emoji='\U0001f600';\nuncovered();\ncovered();"
    (base/'src/unicode.js').write_text(source,encoding='utf-8')
    prefix='// \U0001f600 prefix\n/* BEGIN src/unicode.js */\n'
    units=collector['utf16_length'];offset=units(prefix);start=units(source.split('\n')[0]+'\n')
    ranges=[{'startOffset':0,'endOffset':units(prefix+source),'count':1},{'startOffset':offset+start,'endOffset':offset+start+units('uncovered();'),'count':0}]
    save=collector['save'];save.__globals__['ROOT']=base
    original=os.environ['NODE_V8_COVERAGE'];os.environ['NODE_V8_COVERAGE']=str(base/'coverage')
    try:save({'result':[{'scriptId':'unicode','functions':[{'functionName':'','ranges':ranges}]}]},{'unicode':prefix+source})
    finally:os.environ['NODE_V8_COVERAGE']=original
    record=json.loads(next((base/'coverage').glob('*.json')).read_text())['result'][0]
    actual=record['functions'][0]['ranges']
    assert actual[0]['endOffset']==units(source), 'non-BMP tail must not be truncated'
    assert actual[1]['startOffset']==start and actual[1]['count']==0, 'UTF-16 refusal range must retain its exact address'
collector['coverage_command'].__globals__['ROOT']=ROOT
canonical=[sys.executable,str(ROOT/'tests/canonical_qa.py')]
assert collector['coverage_command'](canonical)==[sys.executable,str(ROOT/'tests/arch_browser_coverage.py'),str(Path('tests/canonical_qa.py'))]
with tempfile.TemporaryDirectory(prefix='owned-access-mutant-') as temporary:
    clone=Path(temporary)/'repo';clone.mkdir()
    for folder in ['src','styles','data','examples']:shutil.copytree(ROOT/folder,clone/folder)
    for file in ['build.py','index.source.html','tests/read_write_access_qa.py','tests/browser_runtime.py']:
        destination=clone/file;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/file,destination)
    model=clone/'src/10-model.js';source=model.read_text(encoding='utf-8');old="return access==='read-write'||access===operation;"
    assert old in source
    model.write_text(source.replace(old,'return true;',1),encoding='utf-8',newline='\n')
    subprocess.run([sys.executable,str(clone/'build.py')],cwd=clone,check=True,capture_output=True,text=True)
    external=[sys.executable,str(clone/'tests/read_write_access_qa.py')]
    assert collector['coverage_command'](external)==external, 'owned mutant paths remain executable outside canonical root'
    refused=subprocess.run(collector['coverage_command'](external),cwd=clone,capture_output=True,text=True)
    assert refused.returncode!=0 and 'AssertionError' in refused.stderr and "'W' not in blocked" in refused.stderr,refused.stdout+refused.stderr
    print(refused.stderr,end='')
    print('PASS original access mutant refused by original assertion; external source uninstrumented')
print('PASS bounded QA scheduling and complete queue identity')
