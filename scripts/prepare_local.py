"""Bounded local qualification preparation; does not execute test scenarios."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from bounded_process import run_bounded

ROOT=Path(__file__).resolve().parents[1]
_allocated_output=None

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dependency_inputs():
    paths=[ROOT/name for name in ['package.json','package-lock.json','desktop/src-tauri/Cargo.lock','desktop/src-tauri/Cargo.toml','desktop/src-tauri/tauri.conf.json','requirements-dev.txt','index.source.html','styles/app.css','test-budget.json']]
    paths += [path for folder in ['src','mcp','tests','scripts','examples','data'] for path in (ROOT/folder).rglob('*') if path.is_file() and path.suffix in ['.js','.mjs','.cjs','.py','.sov','.sovpak','.json'] and '__pycache__' not in path.parts]
    paths += [ROOT/name for name in ['API.md','DATA-FORMATS.md','STATE-SPACE.md','MODULES.md','docs/local-core/COWORKING.md']]
    paths += [ROOT/'skills'/name/'SKILL.md' for name in ['author-offline','reviewer','layout-review']]
    # Tauri gen/schemas and Cargo target are generated outputs, not build inputs.
    paths += [path for path in (ROOT/'desktop/src-tauri').rglob('*') if path.is_file() and not {'target','gen','.git'}.intersection(path.relative_to(ROOT/'desktop/src-tauri').parts)]
    # Bind installed development runtimes as well as their lock: SDK and scan
    # modules execute during qualification, so a modified install is an input.
    paths += [path for path in (ROOT/'node_modules').rglob('*') if path.is_file()]
    return sorted({str(path.resolve()) for path in paths})

def main():
    global _allocated_output
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--llvm-acquisition',type=Path,required=True)
    parser.add_argument('--build-seconds',type=int,default=600)
    options=parser.parse_args()
    if not 1<=options.build_seconds<=600:raise ValueError('Build allowance must be at most 600 seconds')
    output=options.out.resolve()
    if output.exists():raise ValueError('Preparation output must be new')
    output.mkdir(parents=True)
    _allocated_output=output
    source_scope=json.loads((ROOT/'test-budget.json').read_text())['sourceScope']
    identity={name:sha(ROOT/name) for name in source_scope}
    dependency_files=dependency_inputs()
    dependency_before={path:sha(path) for path in dependency_files}
    (output/'frozen-inputs.json').write_text(json.dumps({'sourceIdentity':identity,'dependencyIdentity':dependency_before},indent=2))
    digest=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    stamp=f'local-core {base} source:{digest}'
    env=dict(os.environ)
    # Encoded flags override RUSTFLAGS; retain one explicit coverage authority.
    env.pop('CARGO_ENCODED_RUSTFLAGS',None)
    env.update(SOV_BUILD_REVISION=stamp,RUSTUP_TOOLCHAIN='stable-x86_64-pc-windows-msvc',
               RUSTFLAGS='-C instrument-coverage -C debuginfo=2')
    # instrument-coverage includes unused functions by default. link-dead-code
    # additionally pulls unused Windows foreign imports into the executable,
    # including API sets unavailable on this host, and is not required for maps.
    target_dir=Path(env['WS_STORES'])/'instrumented-msvc-coverage'
    env['CARGO_TARGET_DIR']=str(target_dir)
    node=shutil.which('node')
    cargo=shutil.which('cargo')
    if not node or not cargo:raise ValueError('Missing admitted Node or Cargo')
    commands=[]
    def run(argv,seconds,name,cwd=ROOT):
        record={'command':argv,'log':str(output/f'{name}.log')}
        record.update(run_bounded(argv,cwd,env,record['log'],seconds))
        commands.append(record)
        (output/'preparation-progress.json').write_text(json.dumps({'sourceIdentity':identity,'commands':commands},indent=2))
        if record['exitCode'] or record['timedOut'] or not record['descendantsStopped']:raise RuntimeError(f'{name} failed; inspect retained log')
        return record
    started=time.monotonic()
    run([sys.executable,str(ROOT/'build.py')],30,'build-html')
    # Compilation is separately admitted preparation; cargo build does not run tests.
    run([cargo,'+stable-x86_64-pc-windows-msvc','build','--manifest-path',str(ROOT/'desktop/src-tauri/Cargo.toml'),
         '--locked','--bins','--tests','--target','x86_64-pc-windows-msvc','-j','4','--message-format=json-render-diagnostics'],
         options.build_seconds,'build-native')
    artifacts=[]
    for line in (output/'build-native.log').read_text(encoding='utf-8',errors='replace').splitlines():
        try:value=json.loads(line)
        except json.JSONDecodeError:continue
        if value.get('reason')=='compiler-artifact':
            artifacts.append(value)
    compiler_profiles=[{'target':value['target']['name'],'optLevel':value['profile']['opt_level'],'test':value['profile']['test']} for value in artifacts if value['target']['name'] in ['sov-schematic-desktop','sha2']]
    if not compiler_profiles or any(value['optLevel']!=('3' if value['target']=='sha2' else '0') for value in compiler_profiles) or not any(value['target']=='sha2' for value in compiler_profiles):
        raise ValueError('Required unoptimized production and optimized SHA2 compiler profiles were not retained')
    native=[value['executable'] for value in artifacts if not value['profile']['test'] and value['target']['name']=='sov-schematic-desktop']
    tests=[value['executable'] for value in artifacts if value['profile']['test'] and value['target']['name']=='sov-schematic-desktop']
    if len(native)!=1 or len(tests)!=1:raise ValueError('Native and test artifacts are not uniquely identified')
    copy_root=output/'test-copy'
    copy_root.mkdir()
    # Test-only copy: retain source, drivers and fixtures, omit caches and Git internals.
    for name in ['src','mcp','tests','examples','data','styles','docs/local-core','skills']:
        shutil.copytree(ROOT/name,copy_root/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','journey'))
    for name in ['index.source.html','build.py','package.json','package-lock.json','test-budget.json','API.md','DATA-FORMATS.md','STATE-SPACE.md','MODULES.md','AGENTS.md','MCP.md']:
        shutil.copy2(ROOT/name,copy_root/name)
    js_scope=[name for name in source_scope if name.endswith(('.js','.mjs'))]
    scope_file=output/'js-scope.json';scope_file.write_text(json.dumps(js_scope))
    run([node,str(ROOT/'scripts/js_coverage.mjs'),'prepare','--source-root',str(ROOT),'--copy-root',str(copy_root),'--scope-json',str(scope_file)],30,'instrument-js')
    run([sys.executable,str(copy_root/'build.py')],30,'build-instrumented-html',copy_root)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:browser=Path(playwright.chromium.executable_path)
    if not browser.is_file():raise ValueError('Required Playwright Chromium executable is absent')
    llvm=json.loads(options.llvm_acquisition.read_text())
    if llvm['rustVersion']!='1.92.0' or llvm['target']!='x86_64-pc-windows-msvc':raise ValueError('LLVM compiler identity mismatch')
    for item in llvm['tools'].values():
        if sha(item['path'])!=item['sha256']:raise ValueError('LLVM acquired tool hash mismatch')
    final_identity={name:sha(ROOT/name) for name in source_scope}
    if identity!=final_identity:raise ValueError('Production source changed during preparation')
    # Bind every development driver and the product inputs used by either build.
    dependency_after={path:sha(path) for path in dependency_inputs()}
    if dependency_after!=dependency_before:
        (output/'changed-inputs.json').write_text(json.dumps({'added':sorted(set(dependency_after)-set(dependency_before)),'removed':sorted(set(dependency_before)-set(dependency_after)),'changed':[path for path in dependency_before if path in dependency_after and dependency_after[path]!=dependency_before[path]]},indent=2))
        raise ValueError('Product dependencies or qualification harness changed during preparation')
    result={'schemaVersion':1,'preparedAt':datetime.now(timezone.utc).isoformat(),'sourceRoot':str(ROOT),'testCopyRoot':str(copy_root),
            'sourceIdentity':identity,'baseCommit':base,'buildRevision':stamp,'compilerProfiles':compiler_profiles,'environment':{'RUSTFLAGS':env['RUSTFLAGS'],'RUSTUP_TOOLCHAIN':env['RUSTUP_TOOLCHAIN'],'SOV_BUILD_REVISION':stamp},
            'python':sys.executable,'node':node,'rustTestBinary':tests[0],'nativeBinary':native[0],
            'llvmProfdata':llvm['tools']['llvm-profdata.exe']['path'],'llvmCov':llvm['tools']['llvm-cov.exe']['path'],
            'jsInitial':str(copy_root/'.js-coverage-initial.json'),'browserExecutable':str(browser),'dependencyFiles':dependency_files,
            'dependencyIdentity':dependency_before,
            'binaryIdentity':{path:sha(path) for path in [native[0],tests[0]]},
            'artifactIdentity':{str(Path(path).resolve()):sha(path) for path in [sys.executable,node,native[0],tests[0],str(browser),llvm['tools']['llvm-profdata.exe']['path'],llvm['tools']['llvm-cov.exe']['path']]},
            'testCopyIdentity':{str(path.resolve()):sha(path) for path in copy_root.rglob('*') if path.is_file()},
            'toolVersions':{'python':sys.version,'node':subprocess.check_output([node,'--version'],text=True).strip(),'playwright':version('playwright'),'coverage':version('coverage'),
                            'rustc':subprocess.check_output(['rustup','run','stable-x86_64-pc-windows-msvc','rustc','-vV'],text=True).strip()},
            'commands':commands,'elapsedSeconds':time.monotonic()-started}
    (output/'prepared.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'prepared':str(output/'prepared.json'),'elapsedSeconds':result['elapsedSeconds']}))

if __name__=='__main__':
    try:
        main()
    except Exception as problem:
        import traceback
        if _allocated_output is not None:
            with (_allocated_output/'preparation-error.json').open('x',encoding='utf-8') as failure_file:
                json.dump({'type':type(problem).__name__,'error':str(problem),'traceback':traceback.format_exc()},failure_file,indent=2)
        raise
