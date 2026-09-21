#!/usr/bin/env python3
"""Read a WS mission and its task records into a bounded, non-live graph input.

No kernel import, commands, API credentials, or writes under the WS root. The
consumer explicitly chooses where this potentially private snapshot is saved.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

MISSION_FIELDS = ('id','repository','title','summary','description','lifecycle','standing','waiting_on','estimates','updated')
TASK_FIELDS = ('id','repository','mission','title','objective','standing','workstation_state','repository_state','waiting_on','serves','dependencies','claim','branch','base_ref','worktree','environment','candidate_id','contract','evidence','residuals','promoted_from','updated')
MAX_FILE = 1_000_000


def parse(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f'Invalid JSON number: {x}')))
    if not isinstance(value, dict):
        raise ValueError('A WS record must be an object')
    return value


def collect(root: Path, mission_id: str) -> dict:
    root = root.resolve(strict=True)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,199}', mission_id):
        raise ValueError('Mission must be a record id, not a path')
    files: dict[Path, bytes] = {}

    def read(file: Path) -> dict:
        resolved = file.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError(f'Record escapes the supplied root: {file.name}')
        if resolved.stat().st_size > MAX_FILE:
            raise ValueError(f'Record too large: {file.name}')
        raw = resolved.read_bytes()
        if len(raw) > MAX_FILE:
            raise ValueError(f'Record grew past its limit: {file.name}')
        value = parse(raw)
        files[file] = raw
        return value

    mission_file = root/'control'/'missions'/f'{mission_id}.json'
    mission = read(mission_file)
    if mission.get('id') != mission_id or mission.get('record_type') != 'Mission':
        raise ValueError('Mission identity or record type disagrees with the requested record')
    task_dir = root/'control'/'tasks'
    if not task_dir.resolve(strict=True).is_relative_to(root):
        raise ValueError('Tasks directory escapes the supplied root')
    names = sorted(task_dir.glob('*.json'))
    if len(names) > 10_000:
        raise ValueError('Task census exceeds 10000 files')
    tasks = []
    for file in names:
        record = read(file)
        if record.get('record_type') != 'Task':
            raise ValueError(f'Unexpected task record type: {file.name}')
        if record.get('mission') == mission_id:
            if record.get('repository') != mission.get('repository'):
                raise ValueError(f'Task repository mismatch: {file.name}')
            if file.stem != record.get('id'):
                raise ValueError(f'Task id does not match its filename: {file.name}')
            tasks.append({k: record[k] for k in TASK_FIELDS if k in record})
    if len(tasks) > 100:
        raise ValueError('Work graph profile admits at most 100 tasks per mission')
    # Detect ordinary collection races. This is not a lock or an atomic snapshot:
    # an ABA change between reads is still possible, so consistency stays sampled-files.
    if names != sorted(task_dir.glob('*.json')):
        raise ValueError('Task census changed during collection; retry')
    for file, before in files.items():
        if not file.resolve(strict=True).is_relative_to(root) or file.read_bytes() != before:
            raise ValueError(f'Record changed during collection: {file.name}; retry')
    fingerprint = hashlib.sha256()
    for file, raw in sorted(files.items()):
        fingerprint.update(file.relative_to(root).as_posix().encode())
        fingerprint.update(b'\0')
        fingerprint.update(hashlib.sha256(raw).digest())
    return {
        'mission': {k: mission[k] for k in MISSION_FIELDS if k in mission},
        'tasks': sorted(tasks,key=lambda task: task['id']),
        'source': {
            'system': f'workstation:{root.as_posix()}',
            'revision': 'sha256:'+fingerprint.hexdigest(),
            'capturedAt': datetime.now(timezone.utc).isoformat(),
            'consistency': 'sampled-files',
            'coverage': f'One mission; {len(tasks)} matching tasks from a census of {len(names)} task files. Files reread for drift; not a live or atomic snapshot. No runtime sessions, git probes, receipt resolution, or grants.',
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--mission',required=True)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    try:
        root = args.root.resolve(strict=True)
        output = args.out.resolve()
        if output.is_relative_to(root):
            raise ValueError('Output must be outside the WS root; this exporter never writes to WS')
        packet = collect(root,args.mission)
        with output.open('x',encoding='utf-8',newline='\n') as handle:
            json.dump(packet,handle,ensure_ascii=False,indent=2,allow_nan=False)
            handle.write('\n')
        print(json.dumps({'output':str(output),'tasks':len(packet['tasks']),'consistency':'sampled-files'}))
        return 0
    except (OSError,ValueError,TypeError,KeyError) as error:
        print(json.dumps({'error':'WS_GRAPH_EXPORT','message':str(error)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
