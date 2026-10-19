"""Front door QA (site/build.mjs).

Builds the site twice into temporary directories, with Node only, and checks:

- every example in site/gallery.json has its .sov, is delivered by bin/schematically.mjs into
  examples/<id>.html, and ships its .sov beside it; build.json counts the same cards and wires as
  the .sov;
- every relative href and src on every built page names a file the build wrote, and every page
  links the gallery and the getting-started pages;
- each agent's start page installs for that agent (--agent <id>) with the source the build was
  given, names the folder the skills installer writes for it, and the landing page links all four;
- a --stage build marks every page noindex and serves _headers and robots.txt that refuse crawlers,
  and a plain build carries none of them.
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'site' / 'build.mjs'
AGENTS = {'claude-code': '.claude/skills/schematically', 'codex': '.agents/skills/schematically',
          'cursor': '.agents/skills/schematically', 'opencode': '.agents/skills/schematically'}
LINK = re.compile(r'''(?:href|src)="([^"]+)"''')
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    if not ok:
        failures.append(message)


def build(out: Path, *extra: str) -> dict:
    done = subprocess.run(['node', str(BUILD), '--out', str(out), *extra], capture_output=True, text=True, cwd=ROOT)
    if done.returncode != 0:
        raise SystemExit(f'site build failed ({done.returncode}): {done.stdout}{done.stderr}')
    return json.loads(done.stdout.strip().splitlines()[-1])


def pages(out: Path) -> list[Path]:
    return sorted(out.rglob('*.html'))


def site_pages(out: Path) -> list[Path]:
    return [p for p in pages(out) if 'examples' not in p.relative_to(out).parts]


def main() -> None:
    examples = json.loads((ROOT / 'site' / 'gallery.json').read_text(encoding='utf-8'))['examples']
    with tempfile.TemporaryDirectory() as tmp:
        stage, plain = Path(tmp) / 'stage', Path(tmp) / 'plain'
        source = 'https://github.com/bdf1992/schematically/tree/dev'
        result = build(stage, '--stage', '--skill-source', source)
        build(plain)
        check(result['examples'] == len(examples), f'build delivered {result["examples"]} examples, gallery.json lists {len(examples)}')

        record = json.loads((stage / 'build.json').read_text(encoding='utf-8'))
        counted = {e['id']: e for e in record['examples']}
        for example in examples:
            sid = example['id']
            sov = ROOT / 'site' / 'gallery' / f'{sid}.sov'
            check(sov.is_file(), f'{sid}: site/gallery/{sid}.sov is missing')
            html = stage / 'examples' / f'{sid}.html'
            check(html.is_file() and html.stat().st_size > 100_000, f'{sid}: delivered HTML missing or too small')
            check((stage / 'examples' / f'{sid}.sov').read_bytes() == sov.read_bytes(), f'{sid}: shipped .sov differs from its source')
            doc = json.loads(sov.read_text(encoding='utf-8'))
            got = counted.get(sid, {})
            check(got.get('cards') == len(doc['components']) and got.get('wires') == len(doc['wires']),
                  f'{sid}: build.json counts {got.get("cards")}/{got.get("wires")}, the .sov has {len(doc["components"])}/{len(doc["wires"])}')
            check('/*__VIEWER_DATA__*/' not in html.read_text(encoding='utf-8', errors='replace'), f'{sid}: viewer data was not filled in')

        for out in (stage, plain):
            for page in site_pages(out):
                text = page.read_text(encoding='utf-8')
                rel = page.relative_to(out).as_posix()
                for target in LINK.findall(text):
                    if re.match(r'^(https?:|mailto:|data:|#)', target):
                        continue
                    path = target.split('#')[0].split('?')[0]
                    if not path:
                        continue
                    check((page.parent / path).resolve().is_file(), f'{out.name}/{rel}: link {target} names no built file')
                check('gallery.html"' in text and 'start/index.html"' in text, f'{out.name}/{rel}: does not link the gallery and the start pages')
                staged = '<meta name="robots" content="noindex,nofollow">' in text
                check(staged == (out is stage), f'{out.name}/{rel}: noindex is {staged} in a {"stage" if out is stage else "plain"} build')

        landing = (stage / 'index.html').read_text(encoding='utf-8')
        for agent, folder in AGENTS.items():
            check(f'start/{agent}.html' in landing, f'landing page does not link start/{agent}.html')
            text = (stage / 'start' / f'{agent}.html').read_text(encoding='utf-8')
            check(f'npx skills add {source} --skill schematically --agent {agent} -g -y' in text, f'{agent}: global install command missing')
            check(f'npx skills add {source} --skill schematically --agent {agent} -y' in text, f'{agent}: project install command missing')
            check(f'~/{folder}' in text, f'{agent}: install folder ~/{folder} not named')
        check('X-Robots-Tag: noindex' in (stage / '_headers').read_text(encoding='utf-8'), 'stage build has no noindex header')
        check('Disallow: /' in (stage / 'robots.txt').read_text(encoding='utf-8'), 'stage build robots.txt allows crawlers')
        check(not (plain / '_headers').exists() and not (plain / 'robots.txt').exists(), 'plain build carries stage-only files')
        check('npx skills add bdf1992/schematically --skill schematically' in (plain / 'index.html').read_text(encoding='utf-8'),
              'plain build does not default to bdf1992/schematically')

    if failures:
        print('FAIL site_qa')
        for f in failures:
            print('  ' + f)
        sys.exit(1)
    print(f'PASS site_qa: {len(examples)} examples delivered, {3 + len(AGENTS)} pages per build, links and install commands checked')


if __name__ == '__main__':
    main()
