from pathlib import Path
import json
import re
ROOT=Path(__file__).resolve().parent
source=(ROOT/'index.source.html').read_text(encoding='utf-8')
css=(ROOT/'styles/app.css').read_text(encoding='utf-8').strip()
source=source.replace('<link rel="stylesheet" href="styles/app.css">',f'<style>\n{css}\n</style>')

def inline_script(match):
    rel=match.group(1)
    body=(ROOT/rel).read_text(encoding='utf-8').strip()
    return f'<script data-beta-module="{rel}">\n/* BEGIN {rel} */\n{body}\n/* END {rel} */\n</script>'

source=re.sub(r'<script src="([^"]+)"></script>',inline_script,source)
# Packs reach the browser through the build: every data/*.pack.json, in file-name order, as one JSON
# array in <script type="application/json" id="sov-packs"> (read by the browser API's run registry).
PACKS_TAG='<script type="application/json" id="sov-packs">[]</script>'
assert source.count(PACKS_TAG)==1,'index.source.html must hold the sov-packs tag exactly once'
packs=[json.loads(path.read_text(encoding='utf-8')) for path in sorted((ROOT/'data').glob('*.pack.json'),key=lambda p:p.name)]
packs_json=json.dumps(packs,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
source=source.replace(PACKS_TAG,f'<script type="application/json" id="sov-packs">{packs_json}</script>')
(ROOT/'index.html').write_text(source,encoding='utf-8',newline='\n')
dist_dir=ROOT/'desktop/dist'
dist_dir.mkdir(parents=True,exist_ok=True)
(dist_dir/'index.html').write_text(source,encoding='utf-8',newline='\n')
print(ROOT/'index.html')
