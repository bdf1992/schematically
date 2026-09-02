from pathlib import Path
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
(ROOT/'index.html').write_text(source,encoding='utf-8')
dist_dir=ROOT/'desktop/dist'
dist_dir.mkdir(parents=True,exist_ok=True)
(dist_dir/'index.html').write_text(source,encoding='utf-8')
print(ROOT/'index.html')
