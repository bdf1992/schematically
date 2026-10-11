"""Collected build checks; original production build runs under coverage.py."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import sys

CASE_IDS=['build-doc-placeholder','build-doc-allowlist','build-script-order','build-deterministic','build-desktop-stamp']
if '--collect' in sys.argv:
    print(json.dumps(CASE_IDS))
    raise SystemExit(0)
parser=argparse.ArgumentParser()
parser.add_argument('--coverage-dir',type=Path,required=True)
options=parser.parse_args()
root=Path(os.environ['SOV_SOURCE_ROOT'])
source=(root/'index.source.html').read_text(encoding='utf-8')
assert source.count('<script type="application/json" id="sov-docs">{}</script>')==1
print('CASE PASS build-doc-placeholder',flush=True)
subprocess.run([sys.executable,'-m','coverage','run','--parallel-mode','--source',str(root),str(root/'build.py')],cwd=root,check=True)
built=(root/'index.html').read_text(encoding='utf-8')
match=re.search(r'<script type="application/json" id="sov-docs">(.*?)</script>',built,re.S)
assert match
docs=json.loads(match.group(1))
expected=['docs/local-core/COWORKING.md','API.md','DATA-FORMATS.md','STATE-SPACE.md','MODULES.md']
assert set(docs)=={f'schematically://docs/{name}' for name in expected}
for name in expected:
    assert docs[f'schematically://docs/{name}']==(root/name).read_text(encoding='utf-8')
print('CASE PASS build-doc-allowlist',flush=True)
order=re.findall(r'<script src="([^"]+)"></script>',source)
assert order.index('src/75-persistence.js')<order.index('src/85-api.js')<order.index('src/89-desktop-mcp.js')
assert all(built.count(f'/* BEGIN {name} */')==1 for name in order)
print('CASE PASS build-script-order',flush=True)
before=hashlib.sha256((root/'index.html').read_bytes()).hexdigest()
subprocess.run([sys.executable,'-m','coverage','run','--parallel-mode','--source',str(root),str(root/'build.py')],cwd=root,check=True)
assert before==hashlib.sha256((root/'index.html').read_bytes()).hexdigest()
print('CASE PASS build-deterministic',flush=True)
desktop=(root/'desktop/dist/index.html').read_text(encoding='utf-8')
class RevisionTags(HTMLParser):
    def __init__(self,text):
        super().__init__();self.revisions=[];self.feed(text)
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='meta' and attrs.get('name')=='sov-revision':self.revisions.append(attrs.get('content'))
assert RevisionTags(built).revisions==[], 'Standalone build contains a revision meta element'
assert RevisionTags(desktop).revisions==[os.environ['SOV_BUILD_REVISION']], 'Desktop revision meta element differs from frozen build'
print('CASE PASS build-desktop-stamp',flush=True)
