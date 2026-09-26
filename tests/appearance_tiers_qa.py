"""The Appearance section is tiered by frequency of use (issue #23).

Thirteen fields used to sit in one small grid with equal weight. Now: Label, Graphic and Signal
come first; Width, Height and Interior next, with the canvas handles as the primary way to size;
Material, Thickness and the Frame fields sit behind one disclosure; Text and SVG behind a second,
which opens itself when Custom SVG is chosen. Controls read at 12px or more. Every field keeps its
effect, and the section still shows only what the dimension has. Driven through the real controls.
"""
from __future__ import annotations
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')

# The ids of the controls in each tier, in document order, and whether each tier is open.
TIERS = """()=>{
  const ids=root=>[...root.querySelectorAll('input,select,textarea,button.color-slot-chip')].map(el=>el.id);
  const visible=root=>[...root.querySelectorAll('label')].filter(l=>!l.hidden&&!l.closest('[hidden]')).map(l=>l.querySelector('input,select,textarea,button')?.id);
  const s=appearanceSettings;
  return {open:s.open,
    frequent:{ids:ids(appearanceFrequent),visible:visible(appearanceFrequent)},
    geometry:{ids:ids(appearanceGeometry),visible:visible(appearanceGeometry),hidden:appearanceGeometry.hidden},
    form:{ids:ids(appearanceFormTier),open:appearanceFormTier.open},
    advanced:{ids:ids(appearanceAdvancedTier),open:appearanceAdvancedTier.open,svgHidden:visualSvgRow.hidden}}}"""
SIZES = """()=>[...componentSettingsFields.querySelectorAll('input,select,textarea')].filter(el=>el.offsetParent!==null||el.closest('details'))
  .map(el=>[el.id||el.className,parseFloat(getComputedStyle(el).fontSize),parseFloat(getComputedStyle(el.closest('label')||el).fontSize)])"""
RECTS = """()=>{const r=el=>el.getBoundingClientRect();const p=r(selectionSettingsPanel),w=r(document.querySelector('.workspace-wrap'));
  // Every visible control of the two open rows sits inside the panel: nothing is cut off at its edge.
  const cut=[...appearanceFrequent.querySelectorAll('select'),...appearanceGeometry.querySelectorAll('input,button')]
    .filter(el=>!el.closest('label').hidden).map(el=>[el.id,r(el)]).filter(([,b])=>b.width>0&&(b.right>p.right-8||b.left<p.left+8)).map(([id])=>id);
  return {inside:p.left>=w.left-4&&p.right<=w.right+4&&p.top>=w.top-4&&p.bottom<=w.bottom+4,w:p.width,h:p.height,wrapH:w.height,cut,
    scrolls:selectionSettingsPanel.scrollHeight>selectionSettingsPanel.clientHeight,overflow:getComputedStyle(selectionSettingsPanel).overflowY}}"""


def open_appearance(page, cid):
    page.evaluate("(id)=>{selectNode(id);openSelectionSettings('component');appearanceSettings.open=true}", cid)
    page.wait_for_timeout(120)


with sync_playwright() as p:
    browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content(HTML, wait_until='load')
    page.wait_for_timeout(300)
    page.evaluate('newSchematic()')
    page.evaluate("""()=>{const A=SovSchematicAPI;
      A.create('component',{id:'a',symbolId:'act',x:700,y:450});
      A.create('component',{id:'pt',symbolId:'point',x:300,y:450});
      A.create('component',{id:'rail',symbolId:'path',x:700,y:750});render()}""")
    page.wait_for_timeout(150)

    # 1. The tiers, for a 2D Component: frequent three, then size, then two closed disclosures.
    open_appearance(page, 'a')
    t = page.evaluate(TIERS)
    assert t['frequent']['ids'] == ['visualLabelMode', 'visualGraphicMode', 'barComponentSignalMode'], t['frequent']
    assert t['frequent']['visible'] == t['frequent']['ids'], t['frequent']
    assert t['geometry']['ids'] == ['visualWidth', 'visualHeight', 'visualInteriorColor'] and not t['geometry']['hidden'], t['geometry']
    assert t['form']['ids'] == ['formMaterial', 'formBodyThickness', 'formFrameMode', 'formFrameThickness', 'formFrameDepth'] and t['form']['open'] is False, t['form']
    assert t['advanced']['ids'] == ['visualText', 'visualSvgMarkup'] and t['advanced']['open'] is False and t['advanced']['svgHidden'], t['advanced']
    # With Form and Appearance both open the panel would be taller than the workspace; it stays
    # inside and scrolls within itself instead of running off the screen.
    r = page.evaluate(RECTS)
    assert r['inside'] and r['w'] >= 360 and r['h'] <= r['wrapH'] and r['overflow'] == 'auto', r
    assert r['scrolls'] or r['h'] < r['wrapH'] - 16, r
    assert r['cut'] == [], ('a control is cut off at the panel edge', r['cut'])

    # 2. Controls read at 12px or more, their labels at 10px or more.
    sizes = page.evaluate(SIZES)
    assert sizes and all(font >= 12 for _, font, _ in sizes), [s for s in sizes if s[1] < 12]
    assert all(label >= 10 for _, _, label in sizes), [s for s in sizes if s[2] < 10]

    # 3. Choosing Custom SVG opens the Advanced tier and shows the SVG row; Symbol hides the row again.
    page.locator('#visualGraphicMode').select_option('custom')
    page.wait_for_timeout(120)
    t = page.evaluate(TIERS)
    assert t['advanced']['open'] is True and t['advanced']['svgHidden'] is False, t['advanced']
    assert page.evaluate("()=>nodes.find(n=>n.id==='a').config.presentation.graphic.kind") == 'custom'
    page.locator('#visualGraphicMode').select_option('symbol')
    page.wait_for_timeout(120)
    assert page.evaluate(TIERS)['advanced']['svgHidden'] is True

    # 4. Every tier's fields keep their effect, reached through the real controls.
    page.locator('#visualLabelMode').select_option('inside')
    page.locator('#barComponentSignalMode').select_option('relay')
    page.locator('#visualWidth').fill('240')
    page.locator('#visualWidth').dispatch_event('change')
    page.evaluate('()=>{appearanceFormTier.open=true}')
    page.locator('#formMaterial').select_option('metal')
    page.locator('#formFrameMode').select_option('shell')
    page.evaluate('()=>{appearanceAdvancedTier.open=true}')
    page.locator('#visualText').fill('inner')
    page.locator('#visualText').dispatch_event('input')
    page.wait_for_timeout(450)
    got = page.evaluate("""()=>{const n=nodes.find(x=>x.id==='a'),p=n.config.presentation;
      return {label:p.labelMode,signal:n.config.signalMode,w:p.size.w,material:n.form.body.material,frame:n.form.frame.mode,text:p.text}}""")
    assert got == {'label': 'inside', 'signal': 'relay', 'w': 240, 'material': 'metal', 'frame': 'shell', 'text': 'inner'}, got

    # 5. The section shows only what the dimension has: a Point has no graphic, size, interior or
    #    text; a Path has a width but no height, interior, material or frame.
    open_appearance(page, 'pt')
    t = page.evaluate(TIERS)
    assert t['frequent']['visible'] == ['visualLabelMode', 'barComponentSignalMode'], t['frequent']
    assert t['geometry']['hidden'] is True, t['geometry']
    assert page.evaluate("()=>[visualText.closest('label').hidden,formMaterial.closest('label').hidden,formBodyThickness.closest('label').hidden]") == [True, True, False]
    open_appearance(page, 'rail')
    t = page.evaluate(TIERS)
    assert t['geometry']['hidden'] is False and t['geometry']['visible'] == ['visualWidth'], t['geometry']
    assert page.evaluate("()=>[visualText.closest('label').hidden,formMaterial.closest('label').hidden,formFrameMode.closest('label').hidden]") == [False, True, True]

    assert not errors, errors
    browser.close()
    print('PASS appearance tiers QA')
