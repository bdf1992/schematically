"""Offline author skill QA.

Keeps skills/author-offline/SKILL.md honest against the data core:
  - every ```json fence parses;
  - every ```sov fence is a document that validates;
  - every ```sov-refused <message> fence fails validation with that message;
  - every examples/*.sov validates through scripts/validate_sov.mjs;
  - the palette table names only symbolIds that exist in src/00-state.js SYMBOLS,
    and names every symbol that exists.
Node only; no browser.
"""
from __future__ import annotations
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/author-offline/SKILL.md'
VALIDATE = ROOT / 'scripts/validate_sov.mjs'

FENCE = re.compile(r'^```(\S+)([^\n]*)\n(.*?)^```', re.S | re.M)


def run_validator(paths: list[Path]) -> tuple[int, str]:
    proc = subprocess.run(['node', str(VALIDATE), *map(str, paths)], cwd=ROOT, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def main() -> None:
    text = SKILL.read_text(encoding='utf-8')
    fences = FENCE.findall(text)
    assert fences, 'no fenced blocks found in SKILL.md'
    counts = {'json': 0, 'sov': 0, 'sov-refused': 0}
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        for i, (lang, info, body) in enumerate(fences):
            if lang == 'json':
                json.loads(body)
                counts['json'] += 1
            elif lang == 'sov':
                path = out / f'fence-{i}.sov'
                path.write_text(body, encoding='utf-8')
                code, log = run_validator([path])
                assert code == 0, f'sov fence {i} should validate:\n{log}'
                counts['sov'] += 1
            elif lang == 'sov-refused':
                expected = info.strip()
                assert expected, f'sov-refused fence {i} needs the expected message on the fence line'
                path = out / f'fence-{i}.sov'
                path.write_text(body, encoding='utf-8')
                code, log = run_validator([path])
                assert code == 1, f'sov-refused fence {i} should fail validation:\n{log}'
                assert expected in log, f'sov-refused fence {i} should fail with {expected!r}:\n{log}'
                counts['sov-refused'] += 1
        assert counts['json'] >= 5 and counts['sov-refused'] >= 2, counts

        # Every example is valid through the headless validator.
        examples = sorted((ROOT / 'examples').glob('*.sov'))
        assert examples
        code, log = run_validator(examples)
        assert code == 0, log
        assert '08-gated-service.sov' in log, 'the authored golden example is missing'

        # A wire inside a host without canvasId is reported, and the message names the surface.
        doc = json.loads((ROOT / 'examples/08-gated-service.sov').read_text(encoding='utf-8'))
        inner = [w for w in doc['wires'] if w.get('canvasId', '').startswith('canvas:component:')]
        assert inner, 'example 08 should carry interior wires'
        del inner[0]['canvasId']
        path = out / 'missing-canvas.sov'
        path.write_text(json.dumps(doc), encoding='utf-8')
        code, log = run_validator([path])
        assert code == 1 and 'canvasId missing' in log and 'canvas:component:svc' in log, log

    # Palette table matches SYMBOLS exactly.
    state = (ROOT / 'src/00-state.js').read_text(encoding='utf-8')
    m = re.search(r'const SYMBOLS = (\[.*?\]);', state, re.S)
    assert m, 'SYMBOLS not found in src/00-state.js'
    symbols = {s['id'] for s in json.loads(m.group(1))}
    table = set(re.findall(r'^\| `([a-z-]+)` \|', text, re.M))
    legacy = {'port'}  # documented alias, normalised on load; not for authoring
    assert table <= symbols, f'palette table names unknown symbols: {sorted(table - symbols)}'
    assert symbols - legacy <= table, f'palette table is missing symbols: {sorted(symbols - legacy - table)}'

    print(f"PASS offline author skill QA ({counts['json']} json, {counts['sov']} sov, {counts['sov-refused']} refused fences; {len(examples)} examples)")


if __name__ == '__main__':
    main()
