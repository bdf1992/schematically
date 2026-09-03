from pathlib import Path
import os
import re
import tempfile

# Write through a temporary file in the same directory and then replace, so a reader
# gets either the whole old build or the whole new one. Watch mode rebuilds while the
# test suite is reading index.html, and a half-written file loads without an error -
# it just silently stops at whatever script the truncation landed in.
def write_atomic(path,text):
    handle,temporary=tempfile.mkstemp(dir=str(path.parent),suffix='.tmp')
    try:
        # Default newline handling, so the build is byte-for-byte what write_text made.
        with os.fdopen(handle,'w',encoding='utf-8') as out:
            out.write(text)
        os.replace(temporary,path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
ROOT=Path(__file__).resolve().parent
source=(ROOT/'index.source.html').read_text(encoding='utf-8')
css=(ROOT/'styles/app.css').read_text(encoding='utf-8').strip()
source=source.replace('<link rel="stylesheet" href="styles/app.css">',f'<style>\n{css}\n</style>')

def inline_script(match):
    rel=match.group(1)
    body=(ROOT/rel).read_text(encoding='utf-8').strip()
    return f'<script data-beta-module="{rel}">\n/* BEGIN {rel} */\n{body}\n/* END {rel} */\n</script>'

source=re.sub(r'<script src="([^"]+)"></script>',inline_script,source)
write_atomic(ROOT/'index.html',source)
dist_dir=ROOT/'desktop/dist'
dist_dir.mkdir(parents=True,exist_ok=True)
write_atomic(dist_dir/'index.html',source)
print(ROOT/'index.html')
