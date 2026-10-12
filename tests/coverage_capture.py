"""Retain Chromium precise coverage for source modules embedded by build.py."""
from __future__ import annotations

import json
import os
from pathlib import Path


def start(page):
    session = page.context.new_cdp_session(page)
    session.send('Debugger.enable')
    session.send('Profiler.enable')
    session.send('Profiler.startPreciseCoverage', {'callCount': False, 'detailed': True})
    return session


def finish(session, page) -> None:
    target = os.environ.get('SCHEMATIC_QA_BROWSER_COVERAGE')
    if not target:
        return
    coverage = session.send('Profiler.takePreciseCoverage').get('result', [])
    modules = []
    for entry in coverage:
        try:
            source = session.send('Debugger.getScriptSource', {'scriptId': entry['scriptId']})['scriptSource']
        except Exception:
            continue
        marker = '/* BEGIN '
        pos = 0
        while (start := source.find(marker, pos)) >= 0:
            name_start = start + len(marker)
            name_end = source.find(' */', name_start)
            if name_end < 0:
                break
            name = source[name_start:name_end]
            if not (name.startswith('src/') and name.endswith('.js')):
                pos = name_end + 3
                continue
            body_start = name_end + 3
            while body_start < len(source) and source[body_start] in '\r\n':
                body_start += 1
            end_marker = f'/* END {name} */'
            body_end = source.find(end_marker, body_start)
            if body_end < 0:
                pos = name_end + 3
                continue
            body = source[body_start:body_end].rstrip()
            modules.append({'file': name, 'source': body, 'functions': entry.get('functions', [])})
            pos = body_end + len(end_marker)
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'browserVersion': page.context.browser.version, 'modules': modules}, ensure_ascii=False), encoding='utf-8')
    session.send('Profiler.stopPreciseCoverage')
