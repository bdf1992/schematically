#!/usr/bin/env python3
"""Stage the deployable site as release channels built from git refs.

Each channel (main, dev, and the newest rc/* branch when one exists) is
checked out into a temporary worktree and built with its own build.py, so
every channel ships the exact standalone artifact its source defines. The
site root gets a small selector page linking the channels.

Usage:
  python scripts/stage_site.py [--out DIR] [--local]

--local additionally stages the current working tree as a 'local' channel
(used by scripts/channels.sh; CI stages only committed refs).
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_FILES = ['index.html']
PAYLOAD_DIRS = ['examples', 'formats', 'reference']


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(['git', *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


def resolve_ref(name: str) -> str | None:
    # Prefer the remote head: local channel branches may be stale checkouts.
    for candidate in (f'origin/{name}', name):
        try:
            git('rev-parse', '--verify', '--quiet', candidate)
            return candidate
        except subprocess.CalledProcessError:
            continue
    return None


def newest_rc_ref() -> str | None:
    out = subprocess.run(
        ['git', 'for-each-ref', '--sort=-committerdate', '--format=%(refname:short)',
         'refs/heads/rc/*', 'refs/remotes/origin/rc/*'],
        cwd=ROOT, check=True, capture_output=True, text=True).stdout.split()
    return out[0] if out else None


def copy_payload(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True)
    for name in PAYLOAD_FILES:
        shutil.copy2(src / name, dest / name)
    for name in PAYLOAD_DIRS:
        if (src / name).is_dir():
            shutil.copytree(src / name, dest / name)


def stage_ref(channel: str, ref: str, out: Path) -> dict:
    sha = git('rev-parse', ref)
    with tempfile.TemporaryDirectory(prefix=f'sov-{channel}-') as td:
        wt = Path(td) / 'wt'
        git('worktree', 'add', '--detach', str(wt), ref)
        try:
            subprocess.run(['python3', 'build.py'], cwd=wt, check=True,
                           capture_output=True, text=True)
            copy_payload(wt, out / channel)
        finally:
            git('worktree', 'remove', '--force', str(wt))
    info = {'channel': channel, 'ref': ref, 'sha': sha,
            'subject': git('log', '-1', '--format=%s', sha),
            'builtAt': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    (out / channel / 'build.json').write_text(json.dumps(info, indent=2))
    return info


def stage_local(out: Path) -> dict:
    subprocess.run(['python3', 'build.py'], cwd=ROOT, check=True,
                   capture_output=True, text=True)
    copy_payload(ROOT, out / 'local')
    dirty = bool(git('status', '--porcelain'))
    info = {'channel': 'local', 'ref': 'working tree', 'sha': git('rev-parse', 'HEAD'),
            'subject': 'current working tree' + (' (uncommitted changes)' if dirty else ''),
            'builtAt': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    (out / 'local' / 'build.json').write_text(json.dumps(info, indent=2))
    return info


SELECTOR_STYLE = '''
:root{--paper:#f7f6f1;--panel:#fffefb;--ink:#1c1c18;--muted:#6b6a60;--line:#dcdad0;--accent:#31597f}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--paper:#15151a;--panel:#1d1d23;--ink:#e8e6df;--muted:#98968c;--line:#33323b;--accent:#7da7cc}}
:root[data-theme="dark"]{--paper:#15151a;--panel:#1d1d23;--ink:#e8e6df;--muted:#98968c;--line:#33323b;--accent:#7da7cc}
body{background:var(--paper);color:var(--ink);font:15px/1.6 system-ui,sans-serif;margin:0}
.wrap{max-width:640px;margin:0 auto;padding:56px 24px}
h1{font-size:26px;margin:0 0 4px}
p{color:var(--muted);margin:0 0 28px}
a.card{display:flex;justify-content:space-between;align-items:baseline;gap:16px;padding:16px 20px;margin-bottom:12px;background:var(--panel);border:1px solid var(--line);border-radius:8px;text-decoration:none;color:var(--ink)}
a.card:hover{border-color:var(--accent)}
.ch{font-weight:600;font-size:17px}
.meta{font-family:ui-monospace,monospace;font-size:12px;color:var(--muted);text-align:right}
'''


def write_selector(out: Path, channels: list[dict]) -> None:
    rows = '\n'.join(
        f'<a class="card" href="{c["channel"]}/index.html"><span class="ch">{c["channel"]}</span>'
        f'<span class="meta">{c["sha"][:9]}<br>{c["builtAt"]}</span></a>'
        for c in channels)
    (out / 'index.html').write_text(
        f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>SOV Schematic Channels</title><style>{SELECTOR_STYLE}</style>'
        f'<div class="wrap"><h1>SOV Schematic</h1>'
        f'<p>Release channels. Each is the standalone editor built from its branch after the QA gate.</p>'
        f'{rows}</div>')
    (out / 'channels.json').write_text(json.dumps(channels, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(ROOT / '_site'))
    parser.add_argument('--local', action='store_true',
                        help="Also stage the current working tree as the 'local' channel.")
    args = parser.parse_args()
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    channels: list[dict] = []
    for name in ('main', 'dev'):
        ref = resolve_ref(name)
        if ref:
            channels.append(stage_ref(name, ref, out))
        else:
            print(f'channel {name}: no ref found, skipped')
    rc = newest_rc_ref()
    if rc:
        channels.append(stage_ref('rc', rc, out))
    else:
        print('channel rc: no rc/* branch, skipped')
    if args.local:
        channels.append(stage_local(out))

    if not channels:
        raise SystemExit('no channels staged')
    write_selector(out, channels)
    for c in channels:
        print(f"staged {c['channel']:6} {c['sha'][:9]}  {c['subject']}")
    print(out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
