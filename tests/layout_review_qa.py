"""Layout review QA: the packet check refuses an unfilled, inconsistent or stale review.

Builds a packet by hand (no browser) and runs scripts/layout_review.py --check against it.
"""
from __future__ import annotations
import hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'layout_review.py'
sha = lambda t: hashlib.sha256(t.encode('utf-8')).hexdigest()[:16]

tmp = Path(tempfile.mkdtemp(prefix='layout-review-qa-'))
try:
    doc = tmp / 'd.sov'
    doc.write_text('{"components":[]}', encoding='utf-8')
    packet = {'build': sha((ROOT / 'index.html').read_text(encoding='utf-8')), 'documents': [{
        'source': str(doc), 'stem': 'd', 'sha': sha(doc.read_text(encoding='utf-8')), 'labels': ['Source', 'Hold'],
        'cast': ['operator', 'the person paged'], 'metrics': {'score': 10, 'counts': {}, 'findings': []}, 'contrast': {'checked': 3}}]}
    (tmp / 'packet.json').write_text(json.dumps(packet), encoding='utf-8')

    def review(**slots):
        base = {'read-cold': 'I see a Source feeding a Hold and nothing else going on here.', 'trace': 'Source then Hold, no hesitation.',
                'score': '9, clean', 'gap': 'none', 'line': 'Keep it.'}
        base.update(slots)
        text = '\n'.join(f'[d/{k}]: {v}\n' for k, v in base.items()) + '\n[packet/ranking]: fine\n\n[packet/next-measure]: none, nothing missed\n'
        (tmp / 'REVIEW.md').write_text(text, encoding='utf-8')
        r = subprocess.run([sys.executable, str(SCRIPT), '--check', str(tmp)], capture_output=True, text=True)
        return r.returncode, r.stdout

    code, out = review()
    assert code == 0 and 'REVIEW COMPLETE' in out and 'calibration: the audit is 1.0' in out, out
    assert json.loads((tmp / 'verdict.json').read_text())['documents'][0]['agent'] == 9
    code, out = review(line='')
    assert code == 1 and 'd/line: unanswered' in out, out
    code, out = review(score='about fine')
    assert code == 1 and 'start with a number' in out, out
    code, out = review(score='6, empty frame', gap='none')
    assert code == 1 and 'name the measure it is missing' in out, out
    code, out = review(score='6, empty frame', gap='A container whose children fill under 20% of it.')
    assert code == 0, out
    code, out = review(trace='I followed the wire and it was fine.')
    assert code == 1 and 'name at least two stops' in out, out
    code, out = review(**{'read-cold': 'A diagram.'})
    assert code == 1 and 'read-cold' in out, out
    doc.write_text('{"components":[{"id":"x"}]}', encoding='utf-8')
    code, out = review()
    assert code == 1 and 'stale' in out, out
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print('PASS layout review QA')
