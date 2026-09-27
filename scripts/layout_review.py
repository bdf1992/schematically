"""Review how documents present: the audit's numbers beside the agent's own reading of the pictures.

The audit (layout.metrics, layout.contrast) only counts what it was taught to count. This
script renders each document, runs the audit, and writes a review packet whose REVIEW.md has
slots only the reviewing agent can fill: lines spoken in the voice of a cast reader, a score
from the pictures alone, and, where that score and the audit's disagree, the defect the audit
missed, phrased as a rule a script could measure. `--check` refuses the packet until every slot
is filled, consistent and current. The skill that drives it is skills/layout-review/SKILL.md.

Usage:
    python scripts/layout_review.py                          # every examples/*.sov -> review/
    python scripts/layout_review.py a.sov b.sov --out rv/    # chosen documents
    python scripts/layout_review.py --check review/          # exit 1 until the packet is complete
"""
from __future__ import annotations
import argparse, base64, hashlib, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))

# Readers the reviewer plays. A document whose layouts name an audience casts that audience.
CAST = [
    ('newcomer', 'someone who has never seen this system and has one minute with the picture'),
    ('operator', 'the person paged at 3am who must find where work stops and why'),
    ('auditor', 'someone who must say who can reach what, and point to it'),
    ('author', 'the person who drew it, seeing it cold a week later'),
]
# (slot, prompt). {reader} and {who} name the cast reader; {audit} is the audit's verdict.
DOC_SLOTS = [
    ('read-cold', 'In the voice of the {reader} ({who}), looking at light.png only: what does this diagram say? First person, one or two sentences. Not the file name.'),
    ('trace', 'Still as the {reader}: follow one path you care about from start to end, naming each stop by the label the picture shows. Say where your eye hesitated.'),
    ('score', 'Out of character now. Your score 0-10 from the pictures alone, before re-reading the audit: a number, then one clause why.'),
    ('gap', 'The audit says {audit}. If your score differs from it by 2 or more, name what it did not count as a rule a script could measure ("a wire label sits closer to another wire than its own"), not a feeling ("looks busy"). Otherwise write: none.'),
    ('line', 'The one line you would say to this diagram\'s author.'),
]
PACKET_SLOTS = [
    ('ranking', 'Across every document here: does the audit rank them the way you would? Name the document it overrates most, and by how much.'),
    ('next-measure', 'The one measure to add to src/57-layout-metrics.js first, as a rule with a planted failing case; or none, with why.'),
]
SLOT_RE = re.compile(r'^\[([\w.-]+)/([\w-]+)\]:[ \t]*(.*)$')
PLACEHOLDER = re.compile(r'^(|none yet|todo|tbd|\.\.\.|…|<.*>)$', re.I)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def cast_for(doc: dict, index: int) -> tuple[str, str]:
    for v in ((doc.get('layout') or {}).get('views') or {}).values():
        if v.get('audience'):
            return (v['audience'], f"the reader the layout '{v.get('name', '')}' was drawn for")
    return CAST[index % len(CAST)]


def labels_of(doc: dict) -> list[str]:
    out = []
    for c in doc.get('components', []):
        label = ((c.get('config') or {}).get('label') or '').strip()
        if label:
            out.append(label)
    for w in doc.get('wires', []):
        label = ((w.get('config') or {}).get('label') or '').strip()
        if label:
            out.append(label)
    return out


def verdict(m: dict, c: dict) -> str:
    counts = ', '.join(f'{k} {v}' for k, v in sorted(m['counts'].items())) or 'no findings'
    return f"{m['score']}/10 ({counts}); contrast measured {c['checked']} items"


def render(paths: list[Path], out: Path) -> dict:
    from playwright.sync_api import sync_playwright
    from browser_runtime import chromium_launch_kwargs
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    packet = {'build': sha(html), 'documents': []}
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        errors: list[str] = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content(html, wait_until='load')
        page.wait_for_timeout(250)
        for i, src in enumerate(paths):
            text = src.read_text(encoding='utf-8')
            doc = json.loads(text)
            stem = src.stem
            (out / stem).mkdir(parents=True, exist_ok=True)
            entry = {'source': str(src.relative_to(ROOT)) if src.is_relative_to(ROOT) else str(src), 'stem': stem, 'sha': sha(text), 'labels': labels_of(doc)}
            for appearance in ('light', 'dark'):
                page.evaluate('(m)=>SovSchematicAPI.view.setAppearance(m)', appearance)
                page.evaluate('([t,n])=>SovSchematicAPI.file.open(t,n)', [text, src.name])
                page.evaluate('()=>{ if (typeof fitDiagram === "function") fitDiagram(); }')
                page.wait_for_timeout(250)
                png = page.evaluate('async()=>await SovSchematicAPI.render.png({scale:1.5})')
                (out / stem / f'{appearance}.png').write_bytes(base64.b64decode(png.split(',', 1)[1]))
                if appearance == 'light':
                    entry['metrics'] = page.evaluate('()=>SovSchematicAPI.layout.metrics({static:true})')
                    entry['contrast'] = page.evaluate('()=>SovSchematicAPI.layout.contrast({static:true})')
            entry['cast'] = list(cast_for(doc, i))
            packet['documents'].append(entry)
        page.evaluate('()=>SovSchematicAPI.view.setAppearance("light")')
        browser.close()
        if errors:
            raise SystemExit('page errors: ' + '; '.join(errors))
    return packet


def write_packet(packet: dict, out: Path) -> list[str]:
    calls = []
    lines = ['# Layout review', '',
             'Filled by the reviewing agent (skills/layout-review/SKILL.md). Every `[doc/slot]:` line is yours:',
             'the audit wrote the numbers, you write the reading. `python scripts/layout_review.py --check` refuses',
             'this file until every slot is answered, every score is a number, and every disagreement names a measure.',
             '']
    for d in packet['documents']:
        reader, who = d['cast']
        audit = verdict(d['metrics'], d['contrast'])
        lines += [f"## {d['stem']}", '', f"![light]({d['stem']}/light.png) ![dark]({d['stem']}/dark.png)", '',
                  f"Audit: {audit}.", f"Cast: **the {reader}**, {who}.", '']
        for f in d['metrics']['findings'][:12]:
            lines.append(f"- audit found {f['kind']} {','.join(i for i in f['ids'] if i)}: {f['detail']}")
        if d['metrics']['findings']:
            lines.append('')
        for slot, prompt in DOC_SLOTS:
            ask = prompt.format(reader=reader, who=who, audit=audit)
            lines += [f'<!-- {ask} -->', f"[{d['stem']}/{slot}]: ", '']
            calls.append(f"IMPROV {d['stem']}/{slot}: {ask}")
    lines += ['## The packet', '']
    for slot, prompt in PACKET_SLOTS:
        lines += [f'<!-- {prompt} -->', f'[packet/{slot}]: ', '']
        calls.append(f'IMPROV packet/{slot}: {prompt}')
    (out / 'REVIEW.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    (out / 'packet.json').write_text(json.dumps(packet, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    return calls


def read_slots(text: str) -> dict[tuple[str, str], str]:
    slots, key = {}, None
    for raw in text.splitlines():
        m = SLOT_RE.match(raw)
        if m:
            key = (m.group(1), m.group(2))
            slots[key] = m.group(3).strip()
        elif key and raw.strip() and not raw.startswith(('<!--', '#', '![', '- audit found', 'Audit:', 'Cast:')):
            slots[key] = (slots[key] + ' ' + raw.strip()).strip()
        elif not raw.strip():
            key = None
    return slots


def check(out: Path) -> int:
    packet = json.loads((out / 'packet.json').read_text(encoding='utf-8'))
    slots = read_slots((out / 'REVIEW.md').read_text(encoding='utf-8'))
    problems, table = [], []
    if sha((ROOT / 'index.html').read_text(encoding='utf-8')) != packet['build']:
        problems.append('stale: the editor build changed since the packet was rendered; run the review again')
    for d in packet['documents']:
        src = ROOT / d['source'] if not Path(d['source']).is_absolute() else Path(d['source'])
        if src.exists() and sha(src.read_text(encoding='utf-8')) != d['sha']:
            problems.append(f"stale: {d['source']} changed since it was rendered")
        got = {s: slots.get((d['stem'], s), '') for s, _ in DOC_SLOTS}
        for s, v in got.items():
            if PLACEHOLDER.match(v):
                problems.append(f"{d['stem']}/{s}: unanswered")
        if got['read-cold'] and len(got['read-cold'].split()) < 8:
            problems.append(f"{d['stem']}/read-cold: say what the diagram says, in a sentence, as the {d['cast'][0]}")
        named = [l for l in d['labels'] if l.lower() in got['trace'].lower()]
        if got['trace'] and len(d['labels']) >= 2 and len(named) < 2:
            problems.append(f"{d['stem']}/trace: name at least two stops by the labels the picture shows (it shows: {', '.join(d['labels'][:8])})")
        m = re.match(r'^\s*(\d+(?:\.\d+)?)', got['score'])
        mine = float(m.group(1)) if m else None
        if got['score'] and (mine is None or not 0 <= mine <= 10):
            problems.append(f"{d['stem']}/score: start with a number from 0 to 10")
        audit = d['metrics']['score']
        if mine is not None and abs(mine - audit) >= 2 and re.match(r'^\s*none\b', got['gap'], re.I):
            problems.append(f"{d['stem']}/gap: you scored {mine:g}, the audit {audit:g}; name the measure it is missing")
        table.append((d['stem'], audit, mine, got['gap']))
    for s, _ in PACKET_SLOTS:
        if PLACEHOLDER.match(slots.get(('packet', s), '')):
            problems.append(f'packet/{s}: unanswered')
    if problems:
        print('REVIEW INCOMPLETE')
        for p in problems:
            print(' -', p)
        return 1
    print('REVIEW COMPLETE')
    print(f"{'document':<32} audit  agent  gap")
    for stem, audit, mine, gap in table:
        print(f'{stem:<32} {audit:>5}  {mine:>5g}  {gap[:90]}')
    mae = sum(abs(a - m) for _, a, m, _ in table) / max(1, len(table))
    print(f'calibration: the audit is {mae:.1f} points from your reading on average; a gap above 1 means the rubric under-weights what you saw')
    gaps = [(stem, gap) for stem, _, _, gap in table if not re.match(r'^\s*none\b', gap, re.I)]
    (out / 'verdict.json').write_text(json.dumps({'documents': [{'stem': s, 'audit': a, 'agent': m, 'gap': g} for s, a, m, g in table],
                                                  'gaps': [{'stem': s, 'gap': g} for s, g in gaps],
                                                  'calibration': round(mae, 2), 'ranking': slots[('packet', 'ranking')], 'next_measure': slots[('packet', 'next-measure')]},
                                                 indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='*')
    ap.add_argument('--out', default=str(ROOT / 'review'))
    ap.add_argument('--check', nargs='?', const='', metavar='DIR')
    a = ap.parse_args()
    if a.check is not None:
        return check(Path(a.check or a.out).resolve())
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    paths = [Path(f).resolve() for f in a.files] or [p for p in sorted((ROOT / 'examples').glob('*.sov')) if p.stem != 'blank']
    calls = write_packet(render(paths, out), out)
    print(f'Packet: {out / "REVIEW.md"} ({len(paths)} documents, pictures beside it)')
    print('Look at every picture, then answer each call in REVIEW.md:')
    for c in calls:
        print(' ', c)
    print(f'Then: python scripts/layout_review.py --check {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
