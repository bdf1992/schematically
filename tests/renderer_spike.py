"""Renderer spike: SVG vs Canvas2D vs WebGL2 instanced on the same synthetic floor.

Headed browser on purpose (headless Chromium has no real GPU). Run by hand:
    python tests/renderer_spike.py
"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_runtime import chromium_launch_kwargs
ROOT=Path(__file__).resolve().parents[1]
SIZES=[10_000,100_000,400_000]
SVG_MAX=100_000
with sync_playwright() as p:
    kw=chromium_launch_kwargs(); kw['headless']=False; kw['args']+=['--window-size=1620,1080','--ignore-gpu-blocklist']
    browser=p.chromium.launch(**kw)
    page=browser.new_page(viewport={'width':1600,'height':1000})
    page.set_default_timeout(600_000)
    page.goto((ROOT/'tests'/'renderer_spike.html').as_uri())
    gpu=page.evaluate("()=>{const c=document.createElement('canvas').getContext('webgl2');const d=c&&c.getExtension('WEBGL_debug_renderer_info');return d?c.getParameter(d.UNMASKED_RENDERER_WEBGL):'unknown'}")
    rows=page.evaluate('([s,m])=>runSpike(s,m)',[SIZES,SVG_MAX])
    browser.close()
(ROOT/'tests'/'renderer-spike-results.json').write_text(json.dumps({'gpu':gpu,'rows':rows},indent=2),encoding='utf-8')
print('GPU:',gpu)
print('| components | port marks | zoom | SVG build ms | SVG frame ms | Canvas2D frame ms | WebGL build ms | WebGL frame ms |')
print('|---:|---:|---:|---:|---:|---:|---:|---:|')
for r in rows:
    s=r.get('svg'); print(f"| {r['n']:,} | {r['ports']:,} | {r['zoom']} | {s['build']:,.0f} | {s['frame']:,.1f} | {r['canvas']['frame']:,.1f} | {r['gl']['build']:,.0f} | {r['gl']['frame']:,.1f} |" if s else f"| {r['n']:,} | {r['ports']:,} | {r['zoom']} | — | — | {r['canvas']['frame']:,.1f} | {r['gl']['build']:,.0f} | {r['gl']['frame']:,.1f} |")
