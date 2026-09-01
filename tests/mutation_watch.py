from pathlib import Path
import tempfile, shutil, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]

MUTANTS=[
    {
      'name':'model-access-always-allows',
      'file':'src/10-model.js',
      'old':"return access==='read-write'||access===operation;",
      'new':'return true;',
      'test':'tests/read_write_access_qa.py'
    },
    {
      'name':'signal-skips-access-check',
      'file':'src/25-signal.js',
      'old':"if(operation!=='none'&&(!endpointAllowsAccess(w,sourceEnd,operation)||!endpointAllowsAccess(w,targetEnd,operation)))return false;",
      'new':"if(false)return false;",
      'test':'tests/read_write_access_qa.py'
    },
    {
      'name':'boundary-becomes-porous',
      'file':'src/05-data-core.js',
      'old':"if(!shared.length)return {ok:false,canvasId:null,reason:'Boundary blocks implicit reach-through'};",
      'new':"if(false)return {ok:false,canvasId:null,reason:'Boundary blocks implicit reach-through'};",
      'test':'tests/boundary_legality_qa.py'
    },
    {
      'name':'palette-cache-removed',
      'file':'src/00-state.js',
      'old':"if(activePaletteCacheKey===key&&activePaletteCacheValue)return activePaletteCacheValue;",
      'new':"if(false)return activePaletteCacheValue;",
      'test':'tests/performance_regression_qa.py'
    },
    {
      'name':'terminal-identity-uses-raw-alias',
      'file':'src/40-routing.js',
      'old':"return n1===n2 && terminalPointId(n1,s1)===terminalPointId(n2,s2);",
      'new':"return n1===n2 && s1===s2;",
      'test':'tests/attachment_terminal_identity_qa.py'
    },
    {
      'name':'growth-skips-canonical-attachment-alias',
      'file':'src/60-interactions.js',
      'old':"const sourceCompat=sourceSpec.compatId;",
      'new':"const sourceCompat=sourcePointId;",
      'test':'tests/attachment_growth_direction_qa.py'
    },
    {
      'name':'locked-update-delete-policy-removed',
      'file':'src/05-data-core.js',
      'old':"const current=arr[index];assertUnlocked(current,resource);",
      'new':"const current=arr[index];",
      'test':'tests/agent_api_mcp_golden_qa.py'
    },
    {
      'name':'locked-endpoint-admission-removed',
      'file':'src/05-data-core.js',
      'old':"if(resource==='wire'){assertCarrierEndpointAccepts(doc,value?.a);assertCarrierEndpointAccepts(doc,value?.b)}",
      'new':"if(false){assertCarrierEndpointAccepts(doc,value?.a);assertCarrierEndpointAccepts(doc,value?.b)}",
      'test':'tests/agent_api_mcp_golden_qa.py'
    },
    {
      'name':'attachment-defaults-become-hard-cardinality',
      'file':'src/06-attachment-core.js',
      'old':'return [...base,...customPointSpecs(entity,d,base)];',
      'new':'return base;',
      'test':'tests/configurable_attachment_defaults_qa.py'
    },
]

killed=[]
for mutant in MUTANTS:
    with tempfile.TemporaryDirectory(prefix='sov-mutant-') as tmp:
        dst=Path(tmp)/'repo'
        shutil.copytree(ROOT,dst)
        fp=dst/mutant['file']
        text=fp.read_text(encoding='utf-8')
        if mutant['old'] not in text:
            raise AssertionError(f"mutation target missing: {mutant['name']}")
        fp.write_text(text.replace(mutant['old'],mutant['new'],1),encoding='utf-8')
        build=subprocess.run([sys.executable,str(dst/'build.py')],cwd=dst,capture_output=True,text=True,timeout=20)
        if build.returncode!=0:
            killed.append((mutant['name'],'build-failed'))
            continue
        run=subprocess.run([sys.executable,str(dst/mutant['test'])],cwd=dst,capture_output=True,text=True,timeout=35)
        if run.returncode==0:
            print(run.stdout)
            raise AssertionError(f"SURVIVED: {mutant['name']} via {mutant['test']}")
        killed.append((mutant['name'],'test-killed'))
        print('KILLED',mutant['name'])
assert len(killed)==len(MUTANTS),killed
print('PASS mutation watch',killed)
