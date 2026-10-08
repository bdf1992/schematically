"""graph_to_sov --level communities QA: one card per community, one wire per community pair.

Cases on one three-community graph.json: the top document's cards and counted wires, the
per-community documents that together hold every card once, the documentRef of each top card,
the title rule, byte-identical output from a reordered graph, and the laid-out documents
validated by scripts/validate_sov.mjs. Standalone: plain asserts, no pytest.
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / 'scripts/graph_to_sov.py'
VALIDATE = ROOT / 'scripts/validate_sov.mjs'
sys.path.insert(0, str(ROOT / 'scripts'))
from graph_to_sov import (  # noqa: E402
    community_pairs, community_title, graph_to_sov, to_sov_communities,
)

PYTHON = sys.executable


def _code(node_id, label, *, community, source_file, callable_=True):
    node = {'id': node_id, 'label': label, 'file_type': 'code', 'source_file': source_file,
            'source_location': 'L1', 'community': community}
    if callable_:
        node['_callable'] = True
    return node


def _link(source, target, relation='calls'):
    return {'source': source, 'target': target, 'relation': relation,
            'confidence': 'EXTRACTED', 'source_file': 'x', 'source_location': 'L1'}


def _graph() -> dict:
    nodes = [
        _code('s_a', 'a.py', community=0, source_file='src/core/a.py', callable_=False),
        _code('s_f', 'f()', community=0, source_file='src/core/a.py'),
        _code('s_g', 'g()', community=0, source_file='src\\core\\util\\u.py'),
        _code('l_p', 'p()', community=1, source_file='lib/x.py'),
        _code('l_q', 'quux()', community=1, source_file='lib/x.py'),
        _code('z_r', 'r()', community=2, source_file='z.py'),
        _code('z_s', 's()', community=2, source_file='z.py'),
    ]
    links = [
        _link('s_f', 'l_p'), _link('s_f', 'l_q'), _link('s_g', 'l_q'),   # 0-1: 3
        _link('s_f', 'z_r'),                                              # 0-2: 1
        _link('l_p', 'z_r'), _link('l_q', 'z_s'),                         # 1-2: 2
        _link('s_f', 's_g'),                                              # inside 0
        _link('s_a', 's_f', 'contains'), _link('s_a', 'l_p', 'contains'),  # structural
    ]
    return {'directed': False, 'multigraph': False, 'graph': {}, 'nodes': nodes, 'links': links}


def _write_graph(folder: Path, data: dict) -> Path:
    path = folder / 'graph.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def _run(graph: Path, out: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([PYTHON, str(PROGRAM), str(graph), '--out', str(out),
                           '--level', 'communities', *extra],
                          capture_output=True, text=True, encoding='utf-8')


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _cards(doc: dict) -> set[str]:
    return {c['id'] for c in doc['components'] if c['symbolId'] != 'group'}


def _write(tmp: Path, data: dict, *, layout: bool = False, name: str = 'top.sov') -> tuple[Path, dict]:
    folder = tmp / 'in'
    folder.mkdir(exist_ok=True)
    graph = _write_graph(folder, data)
    out = tmp / 'out' / name
    r = _run(graph, out, *([] if layout else ['--no-layout']))
    assert r.returncode == 0, r.stdout + r.stderr
    return out, json.loads(r.stdout)


def top_has_one_card_per_community(tmp: Path) -> None:
    out, counts = _write(tmp, _graph())
    top = _read(out)
    assert [c['id'] for c in top['components']] == ['community-0', 'community-1', 'community-2']
    assert all(c['symbolId'] == 'ground' and 'canvasId' not in c for c in top['components'])
    assert top['meta'] == {'title': 'code graph: 3 communities'}
    assert counts['communities'] == 3 and counts['members'] == 7, counts


def wires_count_cross_community_links(tmp: Path) -> None:
    out, counts = _write(tmp, _graph())
    top = _read(out)
    labels = {w['id']: w['config']['label'] for w in top['wires']}
    assert labels == {'w-community-0-community-1': '3',
                      'w-community-0-community-2': '1',
                      'w-community-1-community-2': '2'}, labels
    assert counts['wires'] == 3
    for wire in top['wires']:
        assert wire['aSide'] == 'out' and wire['bSide'] == 'in'
        assert wire['canvasId'] == 'canvas:global'
    data = _graph()
    card_of = {n['id']: n['id'] for n in data['nodes']}
    community_of = {n['id']: n['community'] for n in data['nodes']}
    assert community_pairs(data, card_of, community_of) == [((0, 1), 3), ((0, 2), 1), ((1, 2), 2)]


def documents_hold_every_card_once(tmp: Path) -> None:
    out, counts = _write(tmp, _graph())
    seen: list[str] = []
    for n in range(3):
        seen.extend(sorted(_cards(_read(out.parent / 'top.communities' / f'community-{n}.sov'))))
    assert len(seen) == len(set(seen)) == 7
    assert set(seen) == _cards(graph_to_sov(_graph()))


def every_document_ref_names_a_written_file(tmp: Path) -> None:
    out, _counts = _write(tmp, _graph())
    for card in _read(out)['components']:
        ref = out.parent / card['config']['documentRef']
        assert ref.is_file(), ref
        assert card['config']['documentRef'] == f"top.communities/{card['id']}.sov"
    written = sorted(p.name for p in (out.parent / 'top.communities').iterdir())
    assert written == ['community-0.sov', 'community-1.sov', 'community-2.sov']


def titles_follow_the_rule(tmp: Path) -> None:
    nodes = _graph()['nodes']
    by_id = {n['id']: n for n in nodes}
    links = _graph()['links']
    assert community_title([by_id['s_a'], by_id['s_f'], by_id['s_g']], links) == 'src/core'
    assert community_title([by_id['l_p'], by_id['l_q']], links) == 'quux'
    assert community_title([by_id['l_p'], by_id['l_q']]) == 'p'
    assert community_title([by_id['z_r'], by_id['z_s']], links) == 'r'
    out, _counts = _write(tmp, _graph())
    assert [c['config']['label'] for c in _read(out)['components']] == ['src/core', 'quux', 'r']


def reordered_graph_writes_identical_bytes(tmp: Path) -> None:
    (tmp / 'one').mkdir()
    (tmp / 'two').mkdir()
    first, _c = _write(tmp / 'one', _graph())
    shuffled = _graph()
    shuffled['nodes'].reverse()
    shuffled['links'].reverse()
    second, _c = _write(tmp / 'two', shuffled)
    assert first.read_bytes() == second.read_bytes()
    for n in range(3):
        name = f'top.communities/community-{n}.sov'
        assert (first.parent / name).read_bytes() == (second.parent / name).read_bytes(), name


def laid_out_documents_validate(tmp: Path) -> None:
    out, _counts = _write(tmp, _graph(), layout=True)
    files = [out] + sorted((out.parent / 'top.communities').iterdir())
    assert len(files) == 4
    for path in files:
        v = subprocess.run(['node', str(VALIDATE), str(path)], cwd=ROOT,
                           capture_output=True, text=True, encoding='utf-8')
        assert v.returncode == 0, f'{path}\n{v.stdout}{v.stderr}'


def nodes_level_is_unchanged(tmp: Path) -> None:
    graph = _write_graph(tmp, _graph())
    out = tmp / 'plain.sov'
    r = subprocess.run([PYTHON, str(PROGRAM), str(graph), '--out', str(out), '--no-layout'],
                       capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0, r.stderr
    assert 'communities' not in json.loads(r.stdout)
    assert not (tmp / 'plain.communities').exists()
    assert callable(to_sov_communities)


CASES = [
    top_has_one_card_per_community,
    wires_count_cross_community_links,
    documents_hold_every_card_once,
    every_document_ref_names_a_written_file,
    titles_follow_the_rule,
    reordered_graph_writes_identical_bytes,
    laid_out_documents_validate,
    nodes_level_is_unchanged,
]


def main() -> None:
    for case in CASES:
        with tempfile.TemporaryDirectory() as td:
            case(Path(td))
        print(f'ok {case.__name__}')
    print('graph_to_sov_communities_qa ok')


if __name__ == '__main__':
    main()
