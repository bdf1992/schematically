"""graph_to_sov QA: a graphify-format graph.json becomes a laid-out Schematically document.

Twelve cases, each on a minimal graph.json of its own: cards, id collisions, wires,
wire basis, label length, groups, direction, determinism, the command line's refusals
(a missing graph, no node on PATH), the --no-layout document, and the laid-out result
validated by scripts/validate_sov.mjs. Standalone: plain asserts, no pytest.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / 'scripts/graph_to_sov.py'
VALIDATE = ROOT / 'scripts/validate_sov.mjs'
sys.path.insert(0, str(ROOT / 'scripts'))
from graph_to_sov import LABEL_LENGTH, dumps_sov, edge_label, graph_to_sov  # noqa: E402

PYTHON = sys.executable


def _run(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(PROGRAM)] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        env=env,
    )


def _code(node_id, label, *, community, callable_=None, callable_class=None,
          source_file='pkg/a.py', location='L1'):
    node = {'id': node_id, 'label': label, 'file_type': 'code', 'source_file': source_file,
            'source_location': location, 'community': community}
    if callable_ is not None:
        node['_callable'] = callable_
    if callable_class is not None:
        node['_callable_class'] = callable_class
    return node


def _link(source, target, relation, *, context=None, confidence='EXTRACTED', location='L1'):
    link = {'source': source, 'target': target, 'relation': relation,
            'confidence': confidence, 'source_file': 'pkg/a.py', 'source_location': location}
    if context is not None:
        link['context'] = context
    return link


def _graph() -> dict:
    nodes = [
        _code('pkg_a', 'a.py', community=0, source_file='pkg\\a.py'),
        _code('pkg_a_f', 'f()', community=0, callable_=True, location='L2'),
        _code('pkg_a_g', 'g()', community=0, callable_=True, location='L9'),
        _code('pkg_a_c', 'C', community=1, callable_=True, callable_class=True, location='L20'),
        _code('pkg_a_c_m', '.m()', community=1, callable_=True, location='L21'),
        _code('pkg/a.py::h', 'h()', community=1, callable_=True, location='L30'),
        {'id': 'pkg_a_rationale_2', 'label': 'Why f exists', 'file_type': 'rationale',
         'source_file': 'pkg/a.py', 'source_location': 'L2', 'community': 2},
        {'id': 'idea', 'label': 'An idea', 'file_type': 'concept', 'source_file': '',
         'community': 0},
        _code('os_path', 'os.path', community=1, source_file=''),
    ]
    links = [
        _link('pkg_a', 'pkg_a_f', 'contains'),
        _link('pkg_a_c', 'pkg_a_c_m', 'method'),
        _link('pkg_a_rationale_2', 'pkg_a_f', 'rationale_for'),
        _link('pkg_a_f', 'pkg_a_g', 'calls', context='call', location='L3'),
        _link('pkg_a_f', 'pkg_a_g', 'calls', context='call', location='L4'),
        _link('pkg_a_g', 'pkg_a_g', 'calls', context='call', location='L10'),
        _link('pkg_a_c_m', 'pkg_a_c', 'references', context='parameter_type',
              confidence='INFERRED', location='L21'),
        _link('pkg_a_f', 'os_path', 'imports', context='import'),
        _link('pkg/a.py::h', 'pkg_a_f', 'calls', context='call', confidence='AMBIGUOUS', location='L31'),
    ]
    return {'directed': False, 'multigraph': False, 'graph': {}, 'nodes': nodes, 'links': links}


def _cards(doc: dict) -> dict[str, dict]:
    return {c['id']: c for c in doc['components'] if c['symbolId'] != 'group'}


def _groups(doc: dict) -> list[dict]:
    return [c for c in doc['components'] if c['symbolId'] == 'group']


def _write_graph(tmp_path: Path, data: dict, labels: dict | None = None) -> Path:
    out = tmp_path / 'graphify-out'
    out.mkdir()
    (out / 'graph.json').write_text(json.dumps(data), encoding='utf-8')
    if labels is not None:
        (out / '.graphify_labels.json').write_text(json.dumps(labels), encoding='utf-8')
    return out / 'graph.json'


def cards_are_functions_classes_and_modules() -> None:
    doc = graph_to_sov(_graph())
    cards = _cards(doc)
    assert {cid: c['symbolId'] for cid, c in cards.items()} == {
        'pkg_a': 'ground',
        'pkg_a_f': 'act',
        'pkg_a_g': 'act',
        'pkg_a_c': 'hold',
        'pkg_a_c_m': 'act',
        'pkg-a-py--h': 'act',
    }
    assert cards['pkg_a_f']['config'] == {'label': 'f', 'subtitle': 'function, pkg/a.py L2'}
    assert cards['pkg_a_c']['config']['subtitle'] == 'class, pkg/a.py L20'
    assert cards['pkg_a']['config']['subtitle'] == 'module, pkg\\a.py L1'
    assert cards['pkg_a_c_m']['config']['label'] == '.m'
    for card in cards.values():
        assert 'x' not in card and 'y' not in card
    assert [c['id'] for c in doc['components'][: len(cards)]] == sorted(cards)


def card_id_collision_names_both() -> None:
    data = _graph()
    data['nodes'].append(_code('pkg:a_f', 'f2()', community=0, callable_=True))
    data['nodes'].append(_code('pkg/a_f', 'f3()', community=0, callable_=True))
    try:
        graph_to_sov(data)
    except ValueError as exc:
        assert 'pkg:a_f' in str(exc) and 'pkg/a_f' in str(exc), str(exc)
    else:
        raise AssertionError('a card id collision must raise ValueError')


def one_wire_per_edge_except_structure() -> None:
    doc = graph_to_sov(_graph())
    pairs = [(w['a'], w['b']) for w in doc['wires']]
    assert ('pkg_a', 'pkg_a_f') not in pairs  # contains
    assert ('pkg_a_c', 'pkg_a_c_m') not in pairs  # method
    assert not any(w['id'].endswith(('-contains', '-method', '-rationale_for')) for w in doc['wires'])
    data = _graph()
    data['links'].append(_link('pkg_a_f', 'pkg_a_g', 'contains'))
    data['links'].append(_link('pkg_a_f', 'pkg_a_g', 'method'))
    data['links'].append(_link('pkg_a_f', 'pkg_a_g', 'rationale_for'))
    assert len(graph_to_sov(data)['wires']) == len(doc['wires'])
    assert pairs.count(('pkg_a_f', 'pkg_a_g')) == 2
    assert ('pkg_a_g', 'pkg_a_g') in pairs
    assert len(doc['wires']) == 5
    ids = [w['id'] for w in doc['wires']]
    assert len(set(ids)) == len(ids)
    assert 'w-pkg_a_f-pkg_a_g-calls' in ids and 'w-pkg_a_f-pkg_a_g-calls-2' in ids
    for wire in doc['wires']:
        assert wire['aSide'] == 'out' and wire['bSide'] == 'in'
        assert wire['canvasId'] == 'canvas:global'


def basis_marks_extracted_and_inferred() -> None:
    doc = graph_to_sov(_graph())
    basis = {(w['a'], w['b']): w['config']['basis'] for w in doc['wires']}
    assert basis[('pkg_a_f', 'pkg_a_g')] == 'EXTRACTED'
    assert basis[('pkg_a_c_m', 'pkg_a_c')] == 'INFERRED'
    assert basis[('pkg-a-py--h', 'pkg_a_f')] == 'AMBIGUOUS'
    for wire in doc['wires']:
        assert not any('colo' in key.lower() for key in wire['config']), wire
        assert not any('colo' in key.lower() for key in wire)


def label_rule_and_length() -> None:
    assert LABEL_LENGTH == 28
    assert edge_label('calls', 'call') == 'calls'
    assert edge_label('references', 'parameter_type') == 'references: parameter type'
    assert edge_label('imports_from', 'import') == 'imports from'
    long = edge_label('r' * 40, None)
    assert len(long) == 28 and long.endswith('…') and long[:27] == 'r' * 27
    assert edge_label('references', 'parameter_type', 10) == 'reference…'
    doc = graph_to_sov(_graph(), label_length=10)
    labels = {(w['a'], w['b']): w['config']['label'] for w in doc['wires']}
    assert labels[('pkg_a_c_m', 'pkg_a_c')] == 'reference…'
    assert labels[('pkg_a_f', 'pkg_a_g')] == 'calls'
    full = graph_to_sov(_graph())
    assert {(w['a'], w['b']): w['config']['label'] for w in full['wires']}[
        ('pkg_a_c_m', 'pkg_a_c')] == 'references: parameter type'


def one_group_per_community_with_cards(tmp_path: Path) -> None:
    doc = graph_to_sov(_graph())
    groups = _groups(doc)
    assert [g['id'] for g in groups] == ['community-0', 'community-1']
    assert groups[0]['config'] == {'label': 'Community 0', 'members': ['pkg_a', 'pkg_a_f', 'pkg_a_g']}
    assert groups[1]['config']['members'] == ['pkg-a-py--h', 'pkg_a_c', 'pkg_a_c_m']
    for group in groups:
        assert group['canvasId'] == 'canvas:global'

    graph = _write_graph(tmp_path, _graph())
    labels = tmp_path / 'labels.json'
    labels.write_text(json.dumps({'0': 'Core', '1': 'Shapes', '2': 'Notes'}), encoding='utf-8')
    out = tmp_path / 'labelled.sov'
    r = _run([str(graph), '--out', str(out), '--labels', str(labels), '--no-layout'], tmp_path)
    assert r.returncode == 0, r.stderr
    written = json.loads(out.read_text(encoding='utf-8'))
    assert [g['config']['label'] for g in _groups(written)] == ['Core', 'Shapes']


def direction_follows_graph_json_links() -> None:
    data = _graph()
    data['links'] = [_link('pkg_a_g', 'pkg_a_f', 'calls', context='call'),
                     _link('pkg_a_c', 'pkg_a', 'uses')]
    doc = graph_to_sov(data)
    assert [(w['a'], w['b']) for w in doc['wires']] == [('pkg_a_c', 'pkg_a'), ('pkg_a_g', 'pkg_a_f')]


def output_is_deterministic(tmp_path: Path) -> None:
    first = dumps_sov(graph_to_sov(_graph()))
    assert dumps_sov(graph_to_sov(_graph())) == first
    assert first.endswith('}\n') and not first.endswith('\n\n')
    shuffled = _graph()
    shuffled['nodes'].reverse()
    shuffled['links'].reverse()
    assert dumps_sov(graph_to_sov(shuffled)) == first

    graph = _write_graph(tmp_path, _graph())
    outs = []
    for name in ('one.sov', 'two.sov'):
        r = _run([str(graph), '--out', str(tmp_path / name), '--no-layout'], tmp_path)
        assert r.returncode == 0, r.stderr
        outs.append((tmp_path / name).read_bytes())
    assert outs[0] == outs[1]


def cli_refuses_a_missing_graph(tmp_path: Path) -> None:
    out = tmp_path / 'never.sov'
    r = _run([str(tmp_path / 'no-such-graph.json'), '--out', str(out)], tmp_path)
    assert r.returncode == 2, r.stdout + r.stderr
    assert r.stderr.startswith('graph_to_sov: '), r.stderr
    assert not out.exists()


def cli_refuses_without_node(tmp_path: Path) -> None:
    graph = _write_graph(tmp_path, _graph())
    empty = tmp_path / 'empty-path'
    empty.mkdir()
    env = dict(os.environ)
    env['PATH'] = str(empty)
    out = tmp_path / 'never.sov'
    r = subprocess.run([str(Path(sys.executable).resolve()), str(PROGRAM), str(graph), '--out', str(out)],
                       cwd=tmp_path, capture_output=True, text=True, encoding='utf-8', env=env)
    assert r.returncode == 2, r.stdout + r.stderr
    assert r.stderr.startswith('graph_to_sov: '), r.stderr
    assert not out.exists()


def cli_no_layout_writes_the_document(tmp_path: Path) -> None:
    graph = _write_graph(tmp_path, _graph())
    out = tmp_path / 'plain.sov'
    r = _run([str(graph), '--out', str(out), '--no-layout'], tmp_path)
    assert r.returncode == 0, r.stderr
    counts = json.loads(r.stdout)
    assert counts['cards'] == {'function': 4, 'class': 1, 'module': 1}, counts
    assert counts['wires'] == {'EXTRACTED': 3, 'INFERRED': 1, 'AMBIGUOUS': 1}, counts
    assert counts['groups'] == 2 and counts['skipped'] == 3, counts
    assert counts['output'] == str(out)
    assert r.stdout.strip() == json.dumps(counts, sort_keys=True)
    doc = json.loads(out.read_text(encoding='utf-8'))
    assert doc['schema'] == 'soveraeign.schematic/document@0.1'
    assert doc['id'] == 'code-graph' and doc['revision'] == 0
    assert doc['meta'] == {'title': 'code graph: 6 cards'}
    assert doc['references'] == []
    assert doc == graph_to_sov(_graph())
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_file()) == ['plain.sov'], list(tmp_path.iterdir())


def layout_and_validate(tmp_path: Path) -> None:
    graph = _write_graph(tmp_path, _graph())
    out = tmp_path / 'laid-out.sov'
    r = _run([str(graph), '--out', str(out)], tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    v = subprocess.run(['node', str(VALIDATE), str(out)], cwd=ROOT,
                       capture_output=True, text=True, encoding='utf-8')
    assert v.returncode == 0, v.stdout + v.stderr
    doc = json.loads(out.read_text(encoding='utf-8'))
    assert len(_cards(doc)) == 6
    for c in doc['components']:
        if c['symbolId'] == 'group':
            continue
        assert isinstance(c.get('x'), (int, float)) and isinstance(c.get('y'), (int, float)), c['id']
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_file()) == ['laid-out.sov']


def _cart(node_id, label, kind, source_file, code_community, community=0):
    return {'id': node_id, 'label': label, 'file_type': 'code', 'source_file': source_file,
            'kind': kind, 'code_community': code_community, 'community': community}


def cartographer_nodes_are_read_by_kind() -> None:
    nodes = [
        _cart('f1', 'one()', 'function', 'pkg/a.py', 7),
        _cart('f2', 'two()', 'function', 'pkg/a.py', 7),
        _cart('c1', 'Holder', 'class', 'pkg/a.py', 7),
        _cart('m1', 'b.py', 'file', 'pkg/b.py', 9),
        _cart('s1', 'sym', 'symbol', 'pkg/b.py', 9),
    ]
    links = [_link('f1', 'f2', 'calls', context='call'),
             _link('c1', 'f1', 'calls', context='call')]
    doc = graph_to_sov({'nodes': nodes, 'links': links})
    cards = _cards(doc)
    assert {cid: c['symbolId'] for cid, c in cards.items()} == {
        'f1': 'act', 'f2': 'act', 'c1': 'hold', 'm1': 'ground'}, cards
    assert 's1' not in cards
    groups = _groups(doc)
    assert [g['id'] for g in groups] == ['community-7', 'community-9'], groups
    assert groups[0]['config']['members'] == ['c1', 'f1', 'f2']
    assert groups[1]['config']['members'] == ['m1']
    assert len(doc['wires']) == 2


CASES = [
    cards_are_functions_classes_and_modules,
    card_id_collision_names_both,
    one_wire_per_edge_except_structure,
    basis_marks_extracted_and_inferred,
    label_rule_and_length,
    one_group_per_community_with_cards,
    direction_follows_graph_json_links,
    output_is_deterministic,
    cli_refuses_a_missing_graph,
    cli_refuses_without_node,
    cli_no_layout_writes_the_document,
    layout_and_validate,
    cartographer_nodes_are_read_by_kind,
]


def main() -> None:
    for case in CASES:
        with tempfile.TemporaryDirectory() as td:
            if case.__code__.co_argcount:
                case(Path(td))
            else:
                case()
        print(f'ok {case.__name__}')
    print('graph_to_sov_qa ok')


if __name__ == '__main__':
    main()
