"""Theme audit: does the interface hold together in both appearances?

A theme here is eleven CSS variables that get swapped when the appearance changes. That
only works if every surface is actually built out of them, so this suite checks three
things a person would otherwise have to notice by eye, one screen at a time.

1. Decomposition. Every token defined for one appearance is defined for the other, and
   a color written into a rule as a literal hex is theme debt: it cannot follow the
   swap. The literal count is held at a ceiling so it goes down and not up.

2. Native surfaces. A `<select>` popup, a scrollbar and a focus ring are painted by the
   browser, not by this stylesheet, and they only follow the theme if the page declares
   `color-scheme`. A white dropdown over a dark editor is what its absence looks like.

3. Contrast. Every rendered text and every drawn form is measured against the surface it
   is actually sitting on - resolving alpha and walking up to whatever paints an opaque
   background - and reported as a WCAG ratio. Body text needs 4.5, large text and the
   edges of shapes need 3.0.

Run it with `--report` to see the numbers rather than assertions.
"""
import asyncio
import re
import sys
from pathlib import Path

from browser_runtime import chromium_launch_kwargs
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'index.html'
CSS = ROOT / 'styles/app.css'
REPORT = '--report' in sys.argv

# Theme debt, held at a ceiling. Every literal is a color that cannot follow an
# appearance change; lower this number when the count comes down, never raise it.
MAX_LITERAL_COLORS = 35
# Each of these is a rule that patches one surface for one appearance instead of
# building it from tokens. Same rule: it goes down.
MAX_DARK_OVERRIDE_RULES = 11

TEXT_MIN = 4.5      # WCAG AA, body text
LARGE_MIN = 3.0     # WCAG AA, large text and the boundary of a shape
# A region's fill is a modulation of the ground it sits on, not a mark on it: enough of
# a step to read as its own area, and not so much that it out-shouts the boundary and
# the label drawn over it. The same construction has to land inside this band in both
# appearances, which is the check that catches a fill built by moving a colour a long
# way towards the ground instead of moving the ground a little towards the colour.
REGION_MIN, REGION_MAX = 1.08, 2.0
REGION_SPREAD_MAX = 2.0   # how far the two appearances may disagree about one fill

# A seeded canvas with one of everything, so the audit measures real surfaces rather
# than an empty page.
SEED = """()=>{
  nodes.splice(0);wires.splice(0);patternRecords.splice(0);openPatternIds.clear();
  addNode('point',380,180,null,{render:false,select:false});
  addNode('path',380,300,null,{render:false,select:false});
  const plane=addNode('plane',700,220,null,{render:false,select:false});
  {const cfg=componentConfig(plane);cfg.label='Ingest';cfg.presentation.labelMode='inside'}
  addNode('pod',700,520,null,{render:false,select:false});
  render();
  addPattern('pair',330,560);
  return {nodes:nodes.length,patterns:patternRecords.length};
}"""

# Composite an element's own color over whatever actually paints behind it, then
# report the ratio. Elements the audit cannot resolve say so rather than scoring.
MEASURE = r"""(selectors)=>{
  const parse=(value)=>{
    const text=String(value||'');
    // color-mix() computes to color(srgb r g b / a) with 0-1 channels, not to rgb().
    const srgb=text.match(/color\(\s*srgb\s+([^)]+)\)/);
    if(srgb){
      const parts=srgb[1].split(/[\s\/]+/).filter(Boolean).map(Number);
      if(parts.length<3||parts.slice(0,3).some(n=>!Number.isFinite(n)))return null;
      return {r:parts[0]*255,g:parts[1]*255,b:parts[2]*255,
              a:Number.isFinite(parts[3])?parts[3]:1};
    }
    const m=text.match(/rgba?\(([^)]+)\)/);
    if(!m)return null;
    const parts=m[1].split(/[\s,\/]+/).filter(Boolean).map(Number);
    if(parts.length<3||parts.some(n=>!Number.isFinite(n)))return null;
    return {r:parts[0],g:parts[1],b:parts[2],a:parts.length>3?parts[3]:1};
  };
  const over=(top,bottom)=>({
    r:top.r*top.a+bottom.r*(1-top.a),
    g:top.g*top.a+bottom.g*(1-top.a),
    b:top.b*top.a+bottom.b*(1-top.a),a:1
  });
  const channel=(c)=>{const s=c/255;return s<=.03928?s/12.92:Math.pow((s+.055)/1.055,2.4)};
  const luminance=(c)=>.2126*channel(c.r)+.7152*channel(c.g)+.0722*channel(c.b);
  const ratio=(a,b)=>{const l1=luminance(a),l2=luminance(b);
    return (Math.max(l1,l2)+.05)/(Math.min(l1,l2)+.05)};
  // What is actually painted behind this element: walk up until something is opaque,
  // compositing every translucent layer on the way, and end on the page ground.
  const groundOf=(el)=>{
    const layers=[];
    for(let cur=el;cur;cur=cur.parentElement||cur.parentNode?.host||null){
      if(cur.nodeType!==1)break;
      const style=getComputedStyle(cur);
      // background-color only. An SVG container paints nothing behind its children,
      // and its computed `fill` is black by default, which would score every drawn
      // form against a ground that is not on the screen.
      const fill=parse(style.backgroundColor);
      if(!fill||fill.a===0)continue;
      layers.push(fill);
      if(fill.a>=1)break;
    }
    const base=parse(getComputedStyle(document.body).backgroundColor)||{r:255,g:255,b:255,a:1};
    return layers.reduceRight((below,layer)=>over(layer,below),base);
  };
  const rows=[];
  for(const {selector,role,label} of selectors){
    for(const el of document.querySelectorAll(selector)){
      const box=el.getBoundingClientRect();
      const style=getComputedStyle(el);
      if(style.visibility==='hidden'||style.display==='none')continue;
      // A horizontal line and a flat stroke have zero height, and they are exactly the
      // marks worth measuring, so an edge only has to have extent in one direction.
      if(role==='edge'?(!box.width&&!box.height):(!box.width||!box.height))continue;
      const svg=el.namespaceURI==='http://www.w3.org/2000/svg';
      const raw=role==='edge'?style.stroke:(svg||role==='region')?style.fill:style.color;
      // A Wire is painted with a gradient, so there is no one color to score. Take the
      // gradient's stops and report the worst one: the faintest stop is where a Wire
      // stops being visible against the canvas.
      const candidates=[];
      const paintRef=String(raw||'').match(/url\(["']?#([^"')]+)["']?\)/);
      if(paintRef){
        const paint=document.getElementById(paintRef[1]);
        for(const stop of paint?paint.querySelectorAll('stop'):[]){
          const color=parse(getComputedStyle(stop).stopColor);
          if(color){
            const opacity=Number(getComputedStyle(stop).stopOpacity);
            candidates.push({...color,a:color.a*(Number.isFinite(opacity)?opacity:1)});
          }
        }
      }else{
        const own=parse(raw);
        if(own)candidates.push(own);
      }
      const usable=candidates.filter(c=>c.a>0);
      if(!usable.length){rows.push({label,role,ratio:null,note:'no resolvable color'});continue}
      const ground=groundOf(el.parentElement||el);
      let worst=null;
      for(const candidate of usable){
        const front=over(candidate,ground);
        const value=Number(ratio(front,ground).toFixed(2));
        if(!worst||value<worst.ratio)worst={ratio:value,front};
      }
      rows.push({label,role,ratio:worst.ratio,
        fg:`rgb(${[worst.front.r,worst.front.g,worst.front.b].map(Math.round).join(',')})`,
        bg:`rgb(${[ground.r,ground.g,ground.b].map(Math.round).join(',')})`});
    }
  }
  return rows;
}"""

# What gets measured, and how hard each one has to work. `text` is read; `edge` is the
# stroke of a shape; `large` is display type that only needs to be distinguishable.
TARGETS = [
    {'selector': '.palette h2', 'role': 'large', 'label': 'palette section heading'},
    {'selector': '.symbol-card b', 'role': 'large', 'label': 'palette card name'},
    {'selector': '.pattern-card small', 'role': 'text', 'label': 'palette card "made of"'},
    {'selector': '.brand', 'role': 'large', 'label': 'header brand'},
    {'selector': '.tag', 'role': 'text', 'label': 'header tag'},
    {'selector': '#status', 'role': 'text', 'label': 'status line'},
    {'selector': '.inspector .kv dt', 'role': 'text', 'label': 'inspector key'},
    {'selector': '.inspector .kv dd', 'role': 'text', 'label': 'inspector value'},
    {'selector': '.kind-badge', 'role': 'text', 'label': 'inspector kind badge'},
    {'selector': '.bar-select', 'role': 'text', 'label': 'selection bar select'},
    {'selector': '.bar-input', 'role': 'text', 'label': 'selection bar input'},
    {'selector': '.bar-form-state', 'role': 'text', 'label': 'dimension button'},
    {'selector': '.bar-pattern-open', 'role': 'text', 'label': 'pattern OPEN button'},
    {'selector': '.btn', 'role': 'text', 'label': 'toolbar button'},
    {'selector': '.node .dimensional-point-body', 'role': 'edge', 'label': 'Point boundary'},
    {'selector': '.node .dimensional-path-body', 'role': 'edge', 'label': 'Path body'},
    {'selector': '.node .body', 'role': 'edge', 'label': 'Plane / Pod boundary'},
    {'selector': '.node .component-label', 'role': 'large', 'label': 'form label'},
    {'selector': '.wire-group .wire', 'role': 'edge', 'label': 'Wire'},
    {'selector': '.pattern-hull-label', 'role': 'text', 'label': 'pattern hull label'},
    {'selector': '.node .body', 'role': 'region', 'label': 'Plane / Pod interior'},
    # A Point's fill is deliberately the ground: it is a ring, and the fill is what
    # makes the ring read as an outline rather than a dot. Its visibility is carried by
    # its stroke, which is measured above as an edge.
    {'selector': '.pattern-hull rect', 'role': 'region', 'label': 'pattern hull'},
]


def read_tokens():
    """The declared token sets, and every color literal written outside them."""
    css = CSS.read_text(encoding='utf-8')
    blocks = {}
    for name, pattern in (
        ('light', r':root\s*\{([^}]*)\}'),
        ('dark', r':root\[data-appearance="dark"\]\s*\{([^}]*)\}'),
    ):
        match = re.search(pattern, css)
        assert match, f'no {name} token block in styles/app.css'
        blocks[name] = dict(re.findall(r'(--[\w-]+)\s*:\s*([^;]+);', match.group(1)))
    stripped = css
    for pattern in (r':root\s*\{[^}]*\}', r':root\[data-appearance="dark"\]\s*\{[^}]*\}'):
        stripped = re.sub(pattern, '', stripped, count=1)
    literals = re.findall(r'#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b', stripped)
    overrides = re.findall(r':root\[data-appearance="dark"\]\s+[^{]+\{', css)
    return blocks, literals, overrides


async def main():
    blocks, literals, overrides = read_tokens()
    findings = []

    # 1. Decomposition -------------------------------------------------------
    light, dark = set(blocks['light']), set(blocks['dark'])
    # --canvas-grid-size is a length, not a color, and does not change with appearance.
    colorish = {t for t in light | dark if not t.endswith('-size')}
    for token in sorted(colorish - dark):
        findings.append(f'token {token} has no dark value')
    for token in sorted(colorish - light):
        findings.append(f'token {token} has no light value')

    if REPORT:
        print(f'tokens: {len(colorish)} color tokens defined in both appearances')
        print(f'literal colors written into rules: {len(literals)} (ceiling {MAX_LITERAL_COLORS})')
        print(f'dark-only override rules: {len(overrides)} (ceiling {MAX_DARK_OVERRIDE_RULES})')

    if len(literals) > MAX_LITERAL_COLORS:
        findings.append(
            f'{len(literals)} literal colors in rules, ceiling is {MAX_LITERAL_COLORS}: '
            'a literal cannot follow an appearance change')
    if len(overrides) > MAX_DARK_OVERRIDE_RULES:
        findings.append(
            f'{len(overrides)} dark-only override rules, ceiling is {MAX_DARK_OVERRIDE_RULES}: '
            'a surface patched per appearance is a surface not built from tokens')

    regions = {}

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = await browser.new_page(viewport={'width': 1500, 'height': 950})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.set_content(HTML.read_text(encoding='utf-8'), wait_until='load')
        await page.wait_for_timeout(200)

        for appearance in ('light', 'dark'):
            await page.evaluate('(mode)=>{appearanceMode=mode;applyAppearanceMode()}', appearance)
            await page.evaluate(SEED)
            await page.evaluate("()=>selectNode(nodes.find(n=>n.symbolId==='plane').id)")
            await page.wait_for_timeout(220)
            rows = await page.evaluate(MEASURE, TARGETS)
            # The Pattern bar replaces the Component bar, so its controls are only on
            # screen while a Pattern is selected. Measure both states, not one.
            await page.evaluate('()=>selectPattern(patternRecords[0].id)')
            await page.wait_for_timeout(220)

            # 2. Native surfaces ---------------------------------------------
            # The browser paints selects, scrollbars and autofill itself. Without a
            # declared color-scheme it paints them light whatever the page says.
            scheme = await page.evaluate(
                "()=>getComputedStyle(document.documentElement).colorScheme")
            if REPORT:
                print(f'\n[{appearance}] color-scheme: {scheme!r}')
            if appearance not in str(scheme):
                findings.append(
                    f'{appearance}: color-scheme is {scheme!r}, so the browser paints '
                    'selects, scrollbars and focus rings for the wrong appearance')

            # 3. Contrast ----------------------------------------------------
            rows = rows + await page.evaluate(MEASURE, TARGETS)
            seen = {}
            for row in rows:
                if row['ratio'] is None:
                    continue
                key = (row['label'], row['role'])
                if key not in seen or row['ratio'] < seen[key]['ratio']:
                    seen[key] = row
            if REPORT:
                print(f'[{appearance}] contrast')
                for (label, role), row in sorted(seen.items(), key=lambda kv: kv[1]['ratio']):
                    need = TEXT_MIN if role == 'text' else LARGE_MIN
                    flag = ' FAIL' if row['ratio'] < need else ''
                    print(f'  {row["ratio"]:>5}  need {need}  {label} ({role})'
                          f'  {row["fg"]} on {row["bg"]}{flag}')
            for (label, role), row in seen.items():
                if role == 'region':
                    regions.setdefault(label, {})[appearance] = row
                    if not (REGION_MIN <= row['ratio'] <= REGION_MAX):
                        findings.append(
                            f'{appearance}: {label} sits at {row["ratio"]}:1 against its '
                            f'ground, outside {REGION_MIN}-{REGION_MAX} - a region should '
                            f'be a step from the ground, not a mark on it '
                            f'({row["fg"]} on {row["bg"]})')
                    continue
                need = TEXT_MIN if role == 'text' else LARGE_MIN
                if row['ratio'] < need:
                    findings.append(
                        f'{appearance}: {label} ({role}) is {row["ratio"]}:1, needs {need}:1 '
                        f'({row["fg"]} on {row["bg"]})')

            unresolved = sorted({row['label'] for row in rows if row['ratio'] is None}
                                - {label for label, _ in seen})
            if unresolved:
                findings.append(
                    f'{appearance}: no resolvable color for {", ".join(unresolved)} - '
                    'the audit cannot say whether it is visible')
            missing = {t['label'] for t in TARGETS} - {label for label, _ in seen}
            if missing and REPORT:
                print(f'[{appearance}] not on screen, not measured: {sorted(missing)}')

        assert not errors, errors
        await browser.close()

    # The same fill, measured in both appearances. A construction that only works in one
    # of them shows up here rather than as a screenshot somebody happens to look at.
    for label, byAppearance in regions.items():
        if len(byAppearance) < 2:
            continue
        low = min(row['ratio'] for row in byAppearance.values())
        high = max(row['ratio'] for row in byAppearance.values())
        if REPORT:
            print(f'region {label}: '
                  + ', '.join(f'{name} {row["ratio"]}' for name, row in byAppearance.items()))
        if low > 0 and high / low > REGION_SPREAD_MAX:
            findings.append(
                f'{label} reads differently by appearance: '
                + ' vs '.join(f'{name} {row["ratio"]}:1' for name, row in byAppearance.items())
                + f' - more than {REGION_SPREAD_MAX}x apart')

    if REPORT:
        print('\nfindings:')
        for finding in findings:
            print(f'  - {finding}')
        print(f'{len(findings)} finding(s)')
        return 0

    assert not findings, 'theme audit:\n  - ' + '\n  - '.join(findings)
    print('theme_audit_qa ok')
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()) or 0)
