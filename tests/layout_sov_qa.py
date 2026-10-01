"""layout_sov QA: a generated map with no hand coordinates gets a legal placement (G11).

Builds a document the way a data-driven generator would: 38 `hold` cards and 12 `act` cards,
60 wires between them, no x, y, or size on any card. Runs scripts/layout_sov.mjs on it and
checks that the layered engine (src/08-layout-core.js, the one `schematic.layout apply` uses)
placed every card, that no two card rectangles overlap, that the result validates and exports
with no page errors, and that --out leaves the input file untouched.
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / 'scripts/layout_sov.mjs'
VALIDATE = ROOT / 'scripts/validate_sov.mjs'
sys.path.insert(0, str(ROOT / 'scripts'))
from export_svg import export_documents  # noqa: E402

N_HOLD = 38
N_ACT = 12
N_CARDS = N_HOLD + N_ACT
N_WIRES = 60


def build_document() -> dict:
    """38 hold cards, 12 act cards, 60 wires act.out -> hold.in, no coordinates anywhere."""
    components = [{'id': f'c{i}', 'symbolId': 'hold', 'config': {'label': f'Record {i}'}} for i in range(N_HOLD)]
    components += [{'id': f'c{i}', 'symbolId': 'act', 'config': {'label': f'Surface {i}'}} for i in range(N_HOLD, N_CARDS)]
    wires = []
    for i in range(N_WIRES):
        src = N_HOLD + (i % N_ACT)
        dst = (7 * i) % N_HOLD
        wires.append({'id': f'w{i}', 'a': f'c{src}', 'aSide': 'out', 'b': f'c{dst}', 'bSide': 'in'})
    return {
        'schema': 'soveraeign.schematic/document@0.1',
        'id': 'layout-sov-qa',
        'revision': 0,
        'meta': {'title': 'layout_sov QA: generated map'},
        'components': components,
        'wires': wires,
        'references': [],
    }


def run_layout(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(['node', str(LAYOUT), *argv], cwd=ROOT, capture_output=True, text=True)


def run_validate(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(['node', str(VALIDATE), str(path)], cwd=ROOT, capture_output=True, text=True)


def rect(c: dict) -> tuple[float, float, float, float]:
    """Centre x, y; w, h from config.presentation.size when present, else the 112x84 default
    src/08-layout-core.js size() falls back to for a typed card with no size written."""
    size = ((c.get('config') or {}).get('presentation') or {}).get('size') or {}
    return c['x'], c['y'], size.get('w', 112), size.get('h', 84)


def overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return abs(ax - bx) < (aw + bw) / 2 and abs(ay - by) < (ah + bh) / 2


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)

        # In place: the input file becomes the laid-out document.
        target = out / 'generated.sov'
        target.write_text(json.dumps(build_document()), encoding='utf-8')
        proc = run_layout([str(target)])
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert proc.stdout.startswith('ok '), proc.stdout
        assert f'({N_CARDS} placed)' in proc.stdout, proc.stdout

        vproc = run_validate(target)
        assert vproc.returncode == 0, vproc.stdout + vproc.stderr

        doc = json.loads(target.read_text(encoding='utf-8'))
        assert len(doc['components']) == N_CARDS
        for c in doc['components']:
            assert isinstance(c.get('x'), (int, float)) and isinstance(c.get('y'), (int, float)), f"{c.get('id')} has no numeric position"

        rects = [(c['id'], rect(c)) for c in doc['components']]
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                (id_a, ra), (id_b, rb) = rects[i], rects[j]
                assert not overlaps(ra, rb), f'{id_a} overlaps {id_b}: {ra} vs {rb}'

        results = export_documents([target], out)
        assert len(results) == 1
        assert not results[0]['errors'], results[0]['errors']

        # --out: the input is read, never written.
        source = out / 'source.sov'
        original = json.dumps(build_document())
        source.write_text(original, encoding='utf-8')
        dest = out / 'placed.sov'
        proc = run_layout([str(source), '--out', str(dest)])
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert source.read_text(encoding='utf-8') == original, 'the input file must be unchanged with --out'
        assert dest.exists(), '--out must write the result to the named file'
        vproc = run_validate(dest)
        assert vproc.returncode == 0, vproc.stdout + vproc.stderr

    print('PASS layout_sov QA')


if __name__ == '__main__':
    main()
