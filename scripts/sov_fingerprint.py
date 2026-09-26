"""Semantic fingerprints: what makes two documents, or two models, the same for saved state.

A `.sav` belongs to one document and one model. Pinning their exact bytes would make moving
a component on the canvas, or fixing a label, refuse every save. So a save pins a fingerprint
of the meaning instead: what exists, what it is, what contains or hosts it, what connects to
what and through which points, which way things flow, and what behaviour it runs: the state
space definition a Component is bound to (`config.definition`), each port's flow, channels and
merge, and each Wire's logical delay (STATE-SPACE.md). Position, size, labels, colors, titles,
editor flags and revision counters are left out. A field that is absent adds nothing, so a
document that uses none of these fingerprints as it did before they were counted.

A document is first normalized through the editor's own data core (scripts/normalize_sov.mjs):
a hand-authored file leaves defaults unwritten that the editor writes on save, and the
fingerprint must not tell them apart.

The rule is an allowlist. A field counts only if it is named here, so a new presentation
field never invalidates saves by accident. A new semantic field has to be added on purpose,
which is the change a reviewer should see.

    python scripts/sov_fingerprint.py a.sov            # the fingerprint
    python scripts/sov_fingerprint.py a.sov --show     # the canonical record it hashes
"""
from __future__ import annotations

import functools
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

GLOBAL = 'canvas:global'
LEGACY_SYMBOL = {'port': 'point'}


def _component(c: dict) -> dict:
    cfg = c.get('config') or {}
    placement = c.get('placement') or {}
    form = c.get('form') or {}
    out = {
        'id': c['id'],
        'symbolId': LEGACY_SYMBOL.get(c.get('symbolId') or c.get('type'), c.get('symbolId') or c.get('type')),
        'parentId': c.get('parentId'),
        'canvasId': c.get('canvasId') or GLOBAL,
    }
    if placement.get('kind') not in (None, 'surface'):
        # Which host a thing sticks to is structure; where along it (t, side) is layout.
        out['placement'] = {k: placement[k] for k in ('kind', 'hostId', 'wireId') if k in placement}
    if 'dimension' in form:
        out['dimension'] = form['dimension']
    interior = (form.get('regions') or {}).get('interior') or {}
    if 'state' in interior:
        out['interior'] = interior['state']
    for key in ('signalMode', 'attachmentDefaults', 'definition'):
        if key in cfg:
            out[key] = cfg[key]
    if isinstance(cfg.get('ports'), dict):
        # A port's face decides legality (crossing or not); its label and colors do not.
        faces = {name: p.get('face') for name, p in cfg['ports'].items() if isinstance(p, dict) and 'face' in p}
        if faces:
            out['faces'] = faces
    if isinstance(cfg.get('attachmentPoints'), list):
        def point(p: dict) -> dict:
            out_p = {'id': p.get('id'), 'defaultFlow': p.get('defaultFlow')}
            if 'flow' in p:
                out_p['flow'] = p['flow']
            if isinstance(p.get('channels'), list):
                # A channel's id and merge decide what a Path carries and how arrivals combine.
                out_p['channels'] = [{k: c[k] for k in ('id', 'merge') if k in c} for c in p['channels'] if isinstance(c, dict)]
            return out_p
        out['attachmentPoints'] = sorted((point(p) for p in cfg['attachmentPoints'] if isinstance(p, dict)),
                                         key=lambda p: str(p['id']))
    return out


def _wire(w: dict) -> dict:
    cfg = w.get('config') or {}
    out = {k: w.get(k) for k in ('id', 'a', 'aSide', 'b', 'bSide')}
    for key in ('direction', 'forwardOperation', 'reverseOperation', 'delay'):
        if key in cfg:
            out[key] = cfg[key]
    return out


@functools.lru_cache(maxsize=64)
def _normalized(text: str) -> str:
    node = shutil.which('node')
    if not node:
        raise RuntimeError('node is required to fingerprint a document (the data core is JavaScript)')
    done = subprocess.run([node, str(HERE / 'normalize_sov.mjs')], input='[' + text + ']', capture_output=True,
                          text=True, check=True)
    return json.dumps(json.loads(done.stdout)[0], sort_keys=True)


def normalize(doc: dict) -> dict:
    """The document as the editor holds it: loaded through the data core, then compacted."""
    return json.loads(_normalized(json.dumps(doc, sort_keys=True)))


def document_record(doc: dict) -> dict:
    """The canonical record a document's fingerprint hashes."""
    doc = normalize(doc)
    return {
        'schema': doc.get('schema'),
        'id': doc.get('id'),
        'components': sorted((_component(c) for c in doc.get('components', [])), key=lambda c: c['id']),
        'wires': sorted((_wire(w) for w in doc.get('wires', [])), key=lambda w: w['id']),
    }


def model_record(model: dict) -> object:
    """A model means its numbers and structure; `note` fields are prose for people."""
    def strip(value: object) -> object:
        if isinstance(value, dict):
            return {k: strip(v) for k, v in value.items() if k != 'note'}
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value
    return strip(model)


def _hash(record: object) -> str:
    text = json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return 'sem1:' + hashlib.sha256(text.encode('utf-8')).hexdigest()


def document_fingerprint(doc: dict) -> str:
    return _hash(document_record(doc))


def model_fingerprint(model: dict) -> str:
    return _hash(model_record(model))


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    show = '--show' in args
    for name in [a for a in args if not a.startswith('--')]:
        doc = json.loads(Path(name).read_text(encoding='utf-8'))
        if show:
            print(json.dumps(document_record(doc), indent=2, sort_keys=True))
        print(f'{document_fingerprint(doc)}  {name}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
