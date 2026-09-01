from pathlib import Path
import re, subprocess
ROOT=Path(__file__).resolve().parents[1]
checks=[]
def check(name,cond):
    checks.append((name,bool(cond)))
    if not cond: raise AssertionError(name)
state=(ROOT/'src/00-state.js').read_text()
ui=(ROOT/'src/20-ui.js').read_text()
inter=(ROOT/'src/60-interactions.js').read_text()
css=(ROOT/'styles/app.css').read_text()
html=(ROOT/'index.source.html').read_text()
check('paired dark mono', 'DARK_SURFACE_MONO' in state and 'DARK_SURFACE_MONO_BRIGHT' in state)
check('paired dark colors', 'DARK_SURFACE_PALETTES' in state)
check('contrast chooses light/dark direction', "relativeLuminance(bg)<.35?'#FFFFFF':'#111111'" in state)
check('contrast UI removed', 'paletteContrastStatus' not in html and 'paletteContrastStatus' not in state and 'paletteContrastStatus' not in ui)
check('dark canvas', '--canvas-tone:#17191B' in css and '--grid:#2B2E31' in css)
check('wire dwell', 'WIRE_BLANK_DWELL_MS=360' in inter and 'blankReady' in inter and 'wire-blank-ghost' in css)
check('release before ghost refuses growth', 'droppedOnCanvas&&blankReady' in inter)
check('drag exception-safe', "finally{" in inter and 'Recovered Component drag failure' in inter)
check('missed release recovery', 'missed release recovered' in inter and "e.buttons===0" in inter)
check('file menu surface variable', '.file-menu{background:var(--panel)' in css or 'background:var(--panel);padding:6px' in css)
for js in sorted((ROOT/'src').glob('*.js')):
    r=subprocess.run(['node','--check',str(js)],capture_output=True,text=True)
    check(f'node --check {js.name}',r.returncode==0)
print(f'PASS {len(checks)} checks')
