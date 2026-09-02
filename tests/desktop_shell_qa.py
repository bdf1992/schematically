"""Desktop shell QA.

Static checks over the desktop/ Tauri shell and its one seam into the editor:
`tauri.conf.json` registers both file associations, `main.rs` exposes the
`opened_document` command, and `src/75-persistence.js` only reaches
`window.__TAURI__` behind a presence check. No browser, no cargo build.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    conf = json.loads((ROOT / 'desktop/src-tauri/tauri.conf.json').read_text(encoding='utf-8'))
    assocs = conf['bundle']['fileAssociations']
    by_ext = {a['ext'][0] if isinstance(a['ext'], list) else a['ext']: a for a in assocs}
    assert 'sov' in by_ext and 'sovpak' in by_ext, by_ext
    assert by_ext['sov']['role'] == 'Editor' and by_ext['sovpak']['role'] == 'Editor', by_ext
    assert 'SOV Schematic document' in by_ext['sov']['description'], by_ext['sov']
    assert 'SOV Schematic package' in by_ext['sovpak']['description'], by_ext['sovpak']

    main_rs = (ROOT / 'desktop/src-tauri/src/main.rs').read_text(encoding='utf-8')
    assert re.search(r'fn\s+opened_document\s*\(', main_rs), 'opened_document command missing'
    assert 'tauri::command' in main_rs

    persistence = (ROOT / 'src/75-persistence.js').read_text(encoding='utf-8')
    guard = re.search(r'if\s*\(\s*!\s*window\.__TAURI__\s*\)\s*return', persistence)
    assert guard, 'no presence-checked guard for window.__TAURI__'
    first_use = persistence.index('window.__TAURI__')
    assert first_use == guard.start() + persistence[guard.start():].index('window.__TAURI__'), (
        'window.__TAURI__ reached before its presence check'
    )

    print('PASS desktop shell QA')


if __name__ == '__main__':
    main()
