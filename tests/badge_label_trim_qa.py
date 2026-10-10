"""Badge label trim QA (DATA-FORMATS.md "Badges").

A stored badge label is a string of 1 to 24 characters with no whitespace at either end. Create and
update trim the label they are given before the rule is read; badgeProblems holds the stored form
strictly and formats/schematic.document.schema.json holds it with type, minLength, maxLength and pattern.

In headless Chromium on index.html, with examples/work-engine/status.sov as the base:
  - create and update with one space + 24 x + one space store exactly 24 x, which the schema accepts;
  - a label of three spaces is refused by create and update with BADGE_INVALID and the document is unchanged;
  - one space + 25 x + one space is refused by create and update;
  - validateDocument reports a stored label exactly when the schema refuses it;
  - node scripts/validate_sov.mjs exits 1 on a stored label with a leading space and 0 on the trimmed one;
  - saving and opening keeps the trimmed label; the page logs no errors.
No JSON Schema library is used: the schema's label node is read and its type, minLength, maxLength and
pattern are applied here with len and re.search (the schema reading).
"""
from __future__ import annotations
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/work-engine/status.sov'
SCHEMA = ROOT / 'formats/schematic.document.schema.json'
X24 = 'x' * 24
X25 = 'x' * 25
PADDED = ' ' + X24 + ' '


def find_badge_label(node):
    if isinstance(node, dict):
        badges = node.get('badges')
        if isinstance(badges, dict) and 'items' in badges:
            return badges['items']['properties']['label']
        for v in node.values():
            found = find_badge_label(v)
            if found is not None:
                return found
    elif isinstance(node, list):
        for v in node:
            found = find_badge_label(v)
            if found is not None:
                return found
    return None


LABEL_NODE = find_badge_label(json.loads(SCHEMA.read_text(encoding='utf-8')))


def schema_reading(label) -> bool:
    """True when the schema's label node accepts the value: type, minLength, maxLength, pattern."""
    node = LABEL_NODE
    if node.get('type') == 'string' and not isinstance(label, str):
        return False
    if 'minLength' in node and len(label) < node['minLength']:
        return False
    if 'maxLength' in node and len(label) > node['maxLength']:
        return False
    if 'pattern' in node and not re.search(node['pattern'], label):
        return False
    return True


def show(label: str) -> str:
    if len(label) < 12:
        return repr(label)
    return "'" + re.sub(r'x{12,}', lambda m: f'x*{len(m.group())}', label) + f"' ({len(label)} chars)"


def refusal(error: str) -> str:
    found = re.search(r'BADGE_INVALID[^"]*', error)
    return found.group(0) if found else error[:80]


ATTEMPT = r'''([op, label])=>{
  const before=JSON.stringify(SovSchematicAPI.file.document());
  let receipt;
  try{
    if(op==='create')receipt=SovSchematicAPI.create("component",{id:"fresh",symbolId:"we-record",config:{label:"F",badges:[{label}]}});
    else receipt=SovSchematicAPI.update("component","anchor",{config:{badges:[{label}]}});
  }catch(e){receipt={ok:false,error:String(e.message||e)}}
  if(!receipt||!receipt.ok)return {ok:false,error:JSON.stringify(receipt),unchanged:JSON.stringify(SovSchematicAPI.file.document())===before};
  const c=SovSchematicAPI.file.document().components.find(x=>x.id===(op==='create'?'fresh':'anchor'));
  return {ok:true,stored:c.config.badges[0].label,keys:Object.keys(c.config.badges[0])};
}'''


def main() -> None:
    from playwright.sync_api import sync_playwright
    from browser_runtime import chromium_launch_kwargs
    text = EXAMPLE.read_text(encoding='utf-8')
    rows: list[tuple[str, str, str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load'); page.wait_for_timeout(150)

        def fresh() -> None:
            page.evaluate('(t)=>SovSchematicAPI.file.open(t,"status.sov")', text)
            page.wait_for_timeout(100)

        def attempt(op: str, label: str) -> dict:
            fresh()
            r = page.evaluate(ATTEMPT, [op, label])
            rows.append((f'{op} {show(label)}', f"ok, stored {len(r['stored'])} chars" if r['ok'] else refusal(r['error']), 'accepts' if schema_reading(label) else 'refuses'))
            return r

        # (a) padded 24 characters: stored trimmed, and the schema accepts the stored label.
        assert schema_reading(X24) and not schema_reading(PADDED)
        for op in ('create', 'update'):
            r = attempt(op, PADDED)
            assert r['ok'], (op, r)
            assert r['stored'] == X24, (op, r['stored'], len(r['stored']))
            assert r['keys'] == ['label'], (op, r['keys'])
            assert schema_reading(r['stored'])

        # (b) spaces only: refused, the document unchanged, and the schema refuses it too.
        assert not schema_reading('   ')
        for op in ('create', 'update'):
            r = attempt(op, '   ')
            assert not r['ok'] and 'BADGE_INVALID' in r['error'] and 'config.badges[0].label' in r['error'], (op, r)
            assert r['unchanged'], f'a refused {op} changed the document'

        # (c) 25 characters after trimming: refused, and the schema refuses 25 x.
        assert not schema_reading(X25)
        for op in ('create', 'update'):
            r = attempt(op, ' ' + X25 + ' ')
            assert not r['ok'] and 'BADGE_INVALID' in r['error'] and 'config.badges[0].label' in r['error'], (op, r)
            assert r['unchanged'], f'a refused {op} changed the document'

        # (d) a stored label is reported by validateDocument exactly when the schema refuses it.
        stored = ['a', X24, X25, '', ' ', ' a', 'a ', PADDED, 'a b']
        accepted = []
        for label in stored:
            doc = json.loads(text)
            doc['components'][0]['config']['badges'] = [{'label': label}]
            errs = page.evaluate('(t)=>SovSchematicData.validateDocument(SovSchematicData.makeDocument(JSON.parse(t))).errors', json.dumps(doc))
            reported = any('BADGE_INVALID' in e and 'config.badges[0].label' in e for e in errs)
            schema_ok = schema_reading(label)
            rows.append((f'stored {show(label)}', 'BADGE_INVALID' if reported else 'valid', 'accepts' if schema_ok else 'refuses'))
            assert reported == (not schema_ok), (label, errs, schema_ok)
            if not reported:
                accepted.append(label)
        assert accepted == ['a', X24, 'a b'], accepted

        # (e) validate_sov exits 1 on a stored label with whitespace at an end and 0 on the trimmed label.
        with tempfile.TemporaryDirectory() as tmp:
            codes = {}
            for label in (' a', 'a'):
                doc = json.loads(text)
                doc['components'][0]['config']['badges'] = [{'label': label}]
                path = Path(tmp) / 'label.sov'
                path.write_text(json.dumps(doc, indent=1) + '\n', encoding='utf-8', newline='\n')
                proc = subprocess.run(['node', 'scripts/validate_sov.mjs', str(path)], cwd=ROOT, capture_output=True, text=True)
                codes[label] = (proc.returncode, proc.stdout + proc.stderr)
            assert codes[' a'][0] == 1, codes[' a']
            assert codes['a'][0] == 0, codes['a']

        # (f) saving and opening keeps the trimmed label of (a).
        for op in ('create', 'update'):
            fresh()
            page.evaluate(ATTEMPT, [op, PADDED])
            saved = page.evaluate('()=>JSON.stringify(SovSchematicAPI.file.document())')
            page.evaluate('(t)=>SovSchematicAPI.file.open(t,"again.sov")', saved); page.wait_for_timeout(150)
            kept = page.evaluate('(id)=>SovSchematicAPI.file.document().components.find(c=>c.id===id).config.badges', 'fresh' if op == 'create' else 'anchor')
            assert kept == [{'label': X24}], (op, kept)

        assert not errors, errors
        browser.close()
    width = max(len(r[0]) for r in rows)
    mid = max(len(r[1]) for r in rows)
    print(f'{"label".ljust(width)}  {"app result".ljust(mid)}  schema reading')
    for a, b, c in rows:
        print(f'{a.ljust(width)}  {b.ljust(mid)}  {c}')
    print('badge label trim: create and update trim, the stored form is held by the rule and the schema')


if __name__ == '__main__':
    main()
    print('PASS badge label trim QA')
