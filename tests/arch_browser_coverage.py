"""Run one existing native QA under CDP coverage without changing its assertions."""
import json, os, runpy, sys, uuid, subprocess
from pathlib import Path
from playwright.sync_api import Page as SyncPage, Browser as SyncBrowser
from playwright.async_api import Page as AsyncPage, Browser as AsyncBrowser

ROOT=Path(__file__).resolve().parents[1]
sessions={}
def utf16_length(text):
    return len(text.encode('utf-16-le','surrogatepass'))//2
def save(result,sources):
    records=[]
    for script in result['result']:
        text=sources.get(script['scriptId'],'')
        if '/* BEGIN src/' not in text: continue
        name=text.split('/* BEGIN ',1)[1].split(' */',1)[0]
        source=(ROOT/name).read_text(encoding='utf-8')
        start=text.find(source.strip())
        if start<0: raise RuntimeError('Coverage source mismatch: '+name)
        leading=len(source)-len(source.lstrip())
        offset=utf16_length(text[:start])-utf16_length(source[:leading])
        source_length=utf16_length(source)
        functions=[]
        for function in script['functions']:
            ranges=[{**r,'startOffset':max(0,r['startOffset']-offset),'endOffset':min(source_length,r['endOffset']-offset)} for r in function['ranges'] if r['endOffset']>offset and r['startOffset']<offset+source_length]
            if ranges: functions.append({**function,'ranges':ranges})
        records.append({'url':(ROOT/name).as_uri(),'functions':functions,'normalizedLineEndings':True})
    (Path(os.environ['NODE_V8_COVERAGE'])/('browser-'+str(uuid.uuid4())+'.json')).write_text(json.dumps({'result':records}),encoding='utf-8')

old_sync_set=SyncPage.set_content
def sync_set(page,*args,**kwargs):
    if page not in sessions:
        session=page.context.new_cdp_session(page)
        session.send('Debugger.enable');session.send('Profiler.enable');session.send('Profiler.startPreciseCoverage',{'callCount':True,'detailed':True})
        sessions[page]=(session,{})
    result=old_sync_set(page,*args,**kwargs)
    session,sources=sessions[page]
    initial=session.send('Profiler.takePreciseCoverage')
    for script in initial['result']:
        if script['scriptId'] not in sources:sources[script['scriptId']]=session.send('Debugger.getScriptSource',{'scriptId':script['scriptId']})['scriptSource']
    save(initial,sources)
    return result
SyncPage.set_content=sync_set
old_sync_close=SyncBrowser.close
def sync_close(browser,*args,**kwargs):
    for page,(session,sources) in list(sessions.items()):
        if isinstance(page,SyncPage) and not page.is_closed():
            save(session.send('Profiler.takePreciseCoverage'),sources);del sessions[page]
    return old_sync_close(browser,*args,**kwargs)
SyncBrowser.close=sync_close

old_async_set=AsyncPage.set_content
async def async_set(page,*args,**kwargs):
    if page not in sessions:
        session=await page.context.new_cdp_session(page)
        await session.send('Debugger.enable');await session.send('Profiler.enable');await session.send('Profiler.startPreciseCoverage',{'callCount':True,'detailed':True})
        sessions[page]=(session,{})
    result=await old_async_set(page,*args,**kwargs)
    session,sources=sessions[page]
    initial=await session.send('Profiler.takePreciseCoverage')
    for script in initial['result']:
        if script['scriptId'] not in sources:sources[script['scriptId']]=(await session.send('Debugger.getScriptSource',{'scriptId':script['scriptId']}))['scriptSource']
    save(initial,sources)
    return result
AsyncPage.set_content=async_set
old_async_close=AsyncBrowser.close
async def async_close(browser,*args,**kwargs):
    for page,(session,sources) in list(sessions.items()):
        if isinstance(page,AsyncPage) and not page.is_closed():
            save(await session.send('Profiler.takePreciseCoverage'),sources);del sessions[page]
    return await old_async_close(browser,*args,**kwargs)
AsyncBrowser.close=async_close
def main():
    if sys.argv[1] in ('--full-qa','--routine-qa'):
        mode=sys.argv[1]
        original_run=subprocess.run
        def supervised_child(command,*args,**kwargs):
            if isinstance(command,list) and len(command)>1 and str(command[1]).endswith('.py') and ('tests' in Path(command[1]).parts or 'golden_run.py' in str(command[1])):
                relative=Path(command[1]).resolve().relative_to(ROOT)
                command=[command[0],str(Path(__file__)),str(relative),*command[2:]]
            return original_run(command,*args,**kwargs)
        subprocess.run=supervised_child
        workers=int(os.environ.get('ARCH_QA_WORKERS','1'))
        if mode=='--full-qa':
            sys.argv=[str(ROOT/'scripts/qa.py'),'--workers',str(workers)]
            runpy.run_path(sys.argv[0],run_name='__main__')
        else:
            policy=json.loads((ROOT/'test-budget.arch.json').read_text(encoding='utf-8'))
            qa=runpy.run_path(str(ROOT/'scripts/qa.py'),run_name='arch_routine')
            qa['run_browser'](['tests/'+path for path in policy['suiteQueue']],workers)
    else:
        candidate=Path(sys.argv[1]);candidate=ROOT/candidate if len(candidate.parts)>1 else ROOT/'tests'/candidate
        sys.argv=[str(candidate),*sys.argv[2:]]
        runpy.run_path(str(candidate),run_name='__main__')

if __name__=='__main__':main()
