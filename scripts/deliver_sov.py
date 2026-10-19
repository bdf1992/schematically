"""Check a .sov and deliver it as the interactive HTML viewer, keeping the last good viewer.

Three stages, each of which can refuse:
  validate  node scripts/validate_sov.mjs --json: schema and marker findings, each with a stable
            rule code (scripts/sov_rules.json, docs/RULE-CODES.md) and a repair hint;
  render    scripts/export_html.py draws the viewer into the system temp folder, then the render
            checks: the editor raised nothing (SOV601), both pictures are drawn (SOV602), the viewer
            holds the checked document's id and card count (SOV603);
  write     the viewer is copied beside the target and renamed over it in one step; a failure
            here (a read-only target, a folder of that name) is SOV701.
A refusal at any stage leaves an existing target exactly as it was. Warnings (SOV605) never refuse.

Usage:
    python scripts/deliver_sov.py a.sov                    # -> a.html beside it
    python scripts/deliver_sov.py a.sov --out site/a.html  # to a named .html
    python scripts/deliver_sov.py a.sov --json             # one JSON report on stdout
    python scripts/deliver_sov.py a.sov --open             # and open the delivered file

The report is {schema: 'schematically.deliver/1', ok, delivered, stage, source, target, previous,
bytes, findings}: stage is where it stopped (validate, render or write; write when delivered),
previous is none (no target before), kept (a target existed and was left untouched) or replaced.
Exit 0 when delivered, 1 when refused, 2 for a usage error.
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = {r['code']: r for r in json.loads((ROOT / 'scripts' / 'sov_rules.json').read_text(encoding='utf-8'))['rules']}
NODE = os.environ.get('SOV_NODE', 'node')


def finding(code: str, message: str, id_: str | None = None, detail: str | None = None) -> dict:
    rule = RULES[code]
    repair = rule['repair'].replace('{id}', id_ or '?').replace('{detail}', detail or '-')
    return {'code': code, 'family': rule['family'], 'severity': rule['severity'], 'id': id_, 'rule': None,
            'detail': detail, 'message': message, 'repair': repair}


def validate(src: Path) -> dict:
    """The validator's report for one file: {ok, components, wires, findings}."""
    proc = subprocess.run([NODE, str(ROOT / 'scripts' / 'validate_sov.mjs'), '--json', str(src)],
                          capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
    try:
        return json.loads(proc.stdout)['files'][0]
    except (json.JSONDecodeError, KeyError, IndexError):
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ['no output']
        return {'ok': False, 'findings': [finding('SOV999', f'validator did not report: {tail[0]}')]}


def render_checks(record: dict, checked: dict, doc_id: str | None) -> list[dict]:
    out = [finding('SOV601', e) for e in record['errors']]
    for appearance, size in sorted(record['svg_bytes'].items()):
        if size < 64:
            out.append(finding('SOV602', f'the {appearance} picture is {size} bytes'))
    if record['id'] != doc_id or record['nodes'] != checked.get('components'):
        out.append(finding('SOV603', f"viewer holds {record['id']} with {record['nodes']} cards; "
                                     f"the checked file is {doc_id} with {checked.get('components')} components", record['id']))
    for b in record['blocked']:
        out.append(finding('SOV605', f"wire {b['wire']} is blocked for tracing: {b['reason']}", b['wire'], b['reason']))
    return out


def deliver(src: Path, target: Path | None = None) -> dict:
    src = Path(src)
    target = Path(target) if target else src.with_suffix('.html')
    previous_exists = target.is_file()
    report = {'schema': 'schematically.deliver/1', 'ok': False, 'delivered': False, 'stage': 'validate',
              'source': str(src), 'target': str(target), 'previous': 'kept' if previous_exists else 'none',
              'bytes': None, 'findings': []}
    checked = validate(src)
    report['findings'] = list(checked['findings'])
    if not checked['ok']:
        return report
    report['stage'] = 'render'
    try:
        doc_id = json.loads(src.read_text(encoding='utf-8')).get('id')
    except (OSError, json.JSONDecodeError, AttributeError) as e:
        report['findings'].append(finding('SOV999', f'could not read the checked file again: {e}'))
        return report
    # The viewer is drawn in the system temp folder, so a run killed while drawing leaves nothing
    # beside the target. The write copies it to one fixed sibling name and renames that over the
    # target; a sibling left by a killed copy is overwritten by the next run, never accumulated.
    scratch = Path(tempfile.mkdtemp(prefix='sov-deliver-'))
    sibling = target.with_name(f'.{target.name}.deliver-tmp')
    try:
        try:
            sys.path.insert(0, str(ROOT / 'scripts'))
            from export_html import export_documents
            [record] = export_documents([src], scratch)
        except SystemExit as e:  # export_html refuses with SystemExit when index.html is missing
            report['findings'].append(finding('SOV604', str(e)))
            return report
        except ImportError as e:
            report['findings'].append(finding('SOV604', f'Playwright is not installed: {e}'))
            return report
        except Exception as e:  # noqa: BLE001 - an editor refusal surfaces as a Playwright error
            report['findings'].append(finding('SOV601', str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__))
            return report
        rendered = render_checks(record, checked, doc_id)
        report['findings'] += rendered
        if any(f['severity'] == 'error' for f in rendered):
            return report
        report['stage'] = 'write'
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(record['target'], sibling)
            os.replace(sibling, target)
        except OSError as e:
            try:
                sibling.unlink(missing_ok=True)
            except OSError:
                pass
            report['findings'].append(finding('SOV701', str(e)))
            return report
        report.update(ok=True, delivered=True, bytes=record['bytes'],
                      previous='replaced' if previous_exists else 'none')
        return report
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('source', type=Path, help='the .sov to check and deliver')
    ap.add_argument('--out', type=Path, default=None, help='the .html to write (default: beside the source)')
    ap.add_argument('--json', action='store_true', help='print one JSON report')
    ap.add_argument('--open', action='store_true', help='open the delivered file in the default browser')
    args = ap.parse_args(argv)
    if args.out is not None and args.out.suffix.lower() != '.html':
        print('--out must name a .html file', file=sys.stderr)
        return 2
    report = deliver(args.source, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        verb = 'delivered' if report['delivered'] else f"refused at {report['stage']}; previous viewer {report['previous']}"
        print(f"{verb}: {report['source']} -> {report['target']}")
        for f in report['findings']:
            print(f"  {f['code']} {f['severity']} {f['id'] or '-'}: {f['message']}\n    repair: {f['repair']}")
    if args.open and report['delivered']:
        webbrowser.open(Path(report['target']).resolve().as_uri())
    return 0 if report['delivered'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
