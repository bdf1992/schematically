from pathlib import Path
import json, subprocess
ROOT=Path(__file__).resolve().parents[1]
examples=sorted((ROOT/'examples').glob('*.sov'))
assert examples
for path in examples:
    doc=json.loads(path.read_text());assert isinstance(doc.get('components'),list);assert isinstance(doc.get('wires'),list)
    print('CASE PASS golden/example-'+path.stem)
tools=json.loads((ROOT/'mcp/tools.json').read_text());assert tools
print('CASE PASS golden/mcp-tool-catalog')
subprocess.run(['node','--check',str(ROOT/'mcp/server.mjs')],check=True)
for f in sorted((ROOT/'src').glob('*.js')):subprocess.run(['node','--check',str(f)],check=True,stdout=subprocess.DEVNULL)
print('STATIC PASS golden/node-syntax')
print(f'GOLDEN PASS: {len(examples)} documents')
