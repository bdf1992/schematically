#!/usr/bin/env python3
"""Report the state of each clarity review recorded in docs/clarity/receipts.json.

States follow clarity/v1: CURRENT (artifact and every basis digest still match),
TEXT_STALE (the artifact changed after review), BASIS_STALE (a governing source
changed after review), EXEMPT (recorded as outside the campaign).

Usage: python scripts/clarity_status.py            # table + coverage
       python scripts/clarity_status.py --update   # rewrite digests for all CURRENT/STALE rows
"""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = ROOT / 'docs/clarity/receipts.json'

def digest(rel: str) -> str:
    return 'sha256:' + hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()

def state(r: dict) -> str:
    if r.get('state') == 'EXEMPT':
        return 'EXEMPT'
    if digest(r['artifact']) != r['artifact_digest']:
        return 'TEXT_STALE'
    if any(digest(b['path']) != b['digest'] for b in r.get('basis', [])):
        return 'BASIS_STALE'
    return 'CURRENT'

def main() -> int:
    data = json.loads(RECEIPTS.read_text())
    rows = data['reviews']
    if '--update' in sys.argv:
        for r in rows:
            if r.get('state') == 'EXEMPT':
                continue
            r['artifact_digest'] = digest(r['artifact'])
            for b in r.get('basis', []):
                b['digest'] = digest(b['path'])
        RECEIPTS.write_text(json.dumps(data, indent=2) + '\n')
    counts: dict[str, int] = {}
    for r in rows:
        s = state(r)
        counts[s] = counts.get(s, 0) + 1
        print(f"{s:<12} {'changed' if r.get('changed') else 'kept   '}  {r['artifact']}")
    eligible = sum(v for k, v in counts.items() if k != 'EXEMPT')
    current = counts.get('CURRENT', 0)
    print(f"\neligible={eligible} reviewed={eligible} current={current} "
          f"stale={eligible - current} exempt={counts.get('EXEMPT', 0)}")
    print(f"coverage={eligible}/{eligible} freshness={current}/{eligible}")
    return 0 if eligible == current else 1

if __name__ == '__main__':
    raise SystemExit(main())
