"""Concerns on every surface QA (DATA-FORMATS.md "Answers"; MCP.md; API.md).

The concern report and the one verb that sets or removes answers are the data core's
(SovSchematicData.concernReport, answerConcerns). This starts the server on a temporary copy of a
document and speaks MCP and HTTP, then opens index.html in Chromium, and checks that the three
surfaces say the same thing.

The document: two act cards and one wire in a carried notation that extends schematic and declares
the component concern made-by and the wire concern carries, so 4 + 2 * 1 + 1 = 7 rows.

  (a) tools/list holds schematic.concerns and schematic.concerns.answer, each with an inputSchema,
      and equals mcp/tools.json;
  (b) schematic.concerns returns 7 rows, all open, and with open true the same 7;
  (c) schematic.concerns.answer with a document entry for what, a card entry for made-by and a wire
      entry for carries returns ok, moves the revision by exactly 1, and result.report says 3
      answered and 4 open; schematic.concerns with open true now returns 4 rows, none of the three;
  (d) an entry with answer null removes that answer and the row is open again;
  (e) one batch holding a good entry and an entry for concern nope is refused with ANSWER_UNKNOWN
      and the document and its revision are unchanged, the good entry not applied;
  (f) target 'no-such-id' is refused with ANSWER_TARGET_UNKNOWN; an empty answers list and an
      answer of 3 are refused with ANSWER_INVALID;
  (g) a stale ifRevision is refused and HTTP answers 409;
  (h) GET /api/v1/concerns equals the MCP read and GET with open=1 equals the MCP read with open
      true; POST /api/v1/concerns answers 200 with the same receipt shape and 400 for the refusal
      of (e);
  (i) schematic.history.undo after an answer restores the document before it;
  (j) after the answers the saved file opens with node scripts/validate_sov.mjs --concerns, exit 0,
      and its 'concerns:' line carries the same two counts as the MCP report;
  (k) schematic.guide with no step lists concerns between palette and apply, and step concerns
      returns text naming schematic.concerns and schematic.concerns.answer with next apply;
  (l) in headless Chromium on index.html, SovSchematicAPI.concerns.list() gives the same rows for
      the same document, concerns.answer sets one answer, and one undo removes it; the page logs
      no errors.
"""
from __future__ import annotations
import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_runtime import chromium_launch_kwargs  # noqa: E402

NOTATION = {'id': 'notation-plant', 'kind': 'notation', 'label': 'Plant', 'data': {
    'id': 'plant', 'name': 'Plant', 'version': 1, 'extends': 'schematic', 'concerns': [
        {'id': 'made-by', 'applies': 'component', 'title': 'Made by', 'question': 'What makes this, and from what?'},
        {'id': 'carries', 'applies': 'wire', 'title': 'Carries', 'question': 'What moves along this, and how much?'},
    ]}}
DOC = {
    'schema': 'soveraeign.schematic/document@0.1', 'id': 'concerns-surface', 'revision': 0, 'notation': 'plant',
    'meta': {'title': 'Ore line'},
    'components': [
        {'id': 'ore', 'symbolId': 'act', 'x': 200, 'y': 200, 'config': {'label': 'Ore'}},
        {'id': 'bar', 'symbolId': 'act', 'x': 560, 'y': 200, 'config': {'label': 'Bar'}}],
    'wires': [{'id': 'belt', 'a': 'ore', 'aSide': 'out', 'b': 'bar', 'bSide': 'in', 'config': {'label': 'belt'}}],
    'references': [NOTATION],
}
# The rows the report gives for DOC, in order: the document's, each card's, the wire's.
EXPECTED = [('document', None, 'what'), ('document', None, 'why'), ('document', None, 'alternatives'), ('document', None, 'smaller'),
            ('component', 'ore', 'made-by'), ('component', 'bar', 'made-by'), ('wire', 'belt', 'carries')]
THREE = [{'concern': 'what', 'answer': 'An ore line: ore is smelted into bars.'},
         {'concern': 'made-by', 'target': 'ore', 'answer': 'Dug from the pit.'},
         {'concern': 'carries', 'target': 'belt', 'answer': 'Bars, four a minute.'}]
MIXED = [{'concern': 'why', 'answer': 'To make bars.'}, {'concern': 'nope', 'target': 'bar', 'answer': 'x'}]


def http_json(url, method='GET', payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = request.Request(url, data=body, method=method, headers={'content-type': 'application/json'})
    try:
        with request.urlopen(req, timeout=6) as res:
            return res.status, json.loads(res.read())
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def rpc(base, method, params=None, _id=[0]):
    _id[0] += 1
    status, data = http_json(base + '/mcp', 'POST', {'jsonrpc': '2.0', 'id': _id[0], 'method': method, **({'params': params} if params is not None else {})})
    assert status == 200, (status, data)
    return data['result']


def tool(base, name, args=None):
    r = rpc(base, 'tools/call', {'name': name, 'arguments': args or {}})
    return r['structuredContent'], r.get('isError', False)


def key(row):
    return (row['applies'], row['target'], row['concern'])


def code(receipt):
    return (receipt.get('error') or {}).get('message', '').split(':')[0]


def server_part() -> list:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='sov-concerns-surface-') as td:
        file = Path(td) / 'concerns.sov'
        file.write_text(json.dumps(DOC, indent=2), encoding='utf-8', newline='\n')
        base = f'http://127.0.0.1:{port}'
        proc = subprocess.Popen(['node', str(ROOT / 'mcp/server.mjs'), '--port', str(port), '--file', str(file)],
                                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            for _ in range(100):
                try:
                    if http_json(base + '/api/v1/formats')[0] == 200:
                        break
                except Exception:
                    time.sleep(.05)
            else:
                raise AssertionError('server did not start')
            document = lambda: tool(base, 'schematic.document.get')[0]
            saved = lambda: file.read_text(encoding='utf-8')

            # (a) The two tools are listed, each with an inputSchema, and the list is the manifest.
            tools = rpc(base, 'tools/list')['tools']
            by_name = {t['name']: t for t in tools}
            for name in ('schematic.concerns', 'schematic.concerns.answer'):
                assert name in by_name, (name, 'is not in tools/list', sorted(by_name))
                assert isinstance(by_name[name].get('inputSchema'), dict) and by_name[name]['inputSchema'].get('type') == 'object', (name, by_name[name])
                assert by_name[name].get('description'), (name, 'has no description')
            manifest = json.loads((ROOT / 'mcp/tools.json').read_text(encoding='utf-8'))['tools']
            assert sorted(by_name) == sorted(manifest) and len(tools) == len(manifest), ('tools/list differs from mcp/tools.json', sorted(set(by_name) ^ set(manifest)))
            print('(a) tools/list holds schematic.concerns and schematic.concerns.answer with an inputSchema each and equals mcp/tools.json:', len(tools), 'tools')

            # (b) Seven rows, all open; open true gives the same seven.
            report, is_error = tool(base, 'schematic.concerns')
            assert not is_error and report['notation'] == 'plant', report
            assert [key(r) for r in report['rows']] == EXPECTED, ('the rows', [key(r) for r in report['rows']])
            assert all(r['answered'] is False and 'answer' not in r and r['question'] for r in report['rows']), report['rows']
            assert (report['answered'], report['open']) == (0, 7), (report['answered'], report['open'])
            opened, is_error = tool(base, 'schematic.concerns', {'open': True})
            assert not is_error and opened == report, ('open true differs when every row is open', opened)
            fresh_rows = report['rows']
            print('(b) schematic.concerns: 7 rows, all open; open true returns the same 7:', [f"{a}:{t or '-'}:{c}" for a, t, c in EXPECTED])

            # (c) Three answers in one call: one revision, three answered, four open.
            before = document()
            receipt, is_error = tool(base, 'schematic.concerns.answer', {'answers': THREE})
            assert not is_error and receipt['ok'] and receipt['error'] is None, receipt
            assert receipt['revisionBefore'] == before['revision'] and receipt['revisionAfter'] == before['revision'] + 1, ('the revision did not move by exactly 1', before['revision'], receipt)
            after = document()
            assert after['revision'] == before['revision'] + 1, (before['revision'], after['revision'])
            assert receipt['result']['report'] == {'answered': 3, 'open': 4}, receipt['result']
            assert after['meta']['answers'] == {'what': THREE[0]['answer']}, after['meta']
            assert [c for c in after['components'] if c['id'] == 'ore'][0]['config']['answers'] == {'made-by': THREE[1]['answer']}, 'ore'
            assert after['wires'][0]['config']['answers'] == {'carries': THREE[2]['answer']}, after['wires'][0]['config']
            assert json.loads(saved())['revision'] == after['revision'], 'the answers were not saved'
            opened, _ = tool(base, 'schematic.concerns', {'open': True})
            three = [('document', None, 'what'), ('component', 'ore', 'made-by'), ('wire', 'belt', 'carries')]
            assert [key(r) for r in opened['rows']] == [k for k in EXPECTED if k not in three], [key(r) for r in opened['rows']]
            assert len(opened['rows']) == 4 and (opened['answered'], opened['open']) == (3, 4), (len(opened['rows']), opened['answered'], opened['open'])
            full, _ = tool(base, 'schematic.concerns')
            assert [(key(r), r['answer']) for r in full['rows'] if r['answered']] == list(zip(three, [e['answer'] for e in THREE])), full['rows']
            print('(c) schematic.concerns.answer with a document, a card and a wire entry: ok, revision', before['revision'], '->', after['revision'], 'report', receipt['result']['report'], 'open rows', len(opened['rows']))

            # (d) An answer of null removes that one answer.
            receipt, is_error = tool(base, 'schematic.concerns.answer', {'answers': [{'concern': 'made-by', 'target': 'ore', 'answer': None}]})
            assert not is_error and receipt['ok'] and receipt['result']['report'] == {'answered': 2, 'open': 5}, receipt
            now = document()
            assert 'answers' not in [c for c in now['components'] if c['id'] == 'ore'][0]['config'], 'removing the last answer left an answers key'
            opened, _ = tool(base, 'schematic.concerns', {'open': True})
            assert ('component', 'ore', 'made-by') in [key(r) for r in opened['rows']] and len(opened['rows']) == 5, [key(r) for r in opened['rows']]
            again, is_error = tool(base, 'schematic.concerns.answer', {'answers': [{'concern': 'made-by', 'target': 'ore', 'answer': None}]})
            assert not is_error and again['ok'] and again['result']['report'] == {'answered': 2, 'open': 5}, ('removing an answer that is not set is admitted', again)
            print('(d) answer null removes that answer: the row is open again, report', receipt['result']['report'])

            # (e) A good entry beside a bad one: refused whole, nothing applied.
            before, before_text = document(), saved()
            refused, is_error = tool(base, 'schematic.concerns.answer', {'answers': MIXED})
            after = document()
            assert is_error and refused['ok'] is False and code(refused) == 'ANSWER_UNKNOWN', ('expected ANSWER_UNKNOWN, got', refused)
            assert refused['error']['index'] == 1 and refused['result'] is None, refused
            why = [r for r in tool(base, 'schematic.concerns')[0]['rows'] if key(r) == ('document', None, 'why')][0]
            assert after == before and after['revision'] == before['revision'] and why['answered'] is False and saved() == before_text, (
                'a refused batch changed the document: the good entry was applied',
                {'revision before': before['revision'], 'revision after': after['revision'], 'meta.answers before': before['meta'].get('answers'), 'meta.answers after': after['meta'].get('answers'), 'why answered': why['answered']})
            print('(e) a good entry with an entry for concern nope: refused with', code(refused), 'at index', refused['error']['index'], '; document and revision', after['revision'], 'unchanged')

            # (f) The other refusals, each changing nothing.
            for label, answers, expect in (
                    ('target no-such-id', [{'concern': 'made-by', 'target': 'no-such-id', 'answer': 'x'}], 'ANSWER_TARGET_UNKNOWN'),
                    ('an empty list', [], 'ANSWER_INVALID'),
                    ('an answer of 3', [{'concern': 'what', 'answer': 3}], 'ANSWER_INVALID'),
                    ('an empty answer', [{'concern': 'what', 'answer': '  '}], 'ANSWER_INVALID'),
                    ('answers that is not a list', {'what': 'x'}, 'ANSWER_INVALID'),
                    ('an entry that is not an object', ['what'], 'ANSWER_INVALID'),
                    ('a key outside concern, target, answer', [{'concern': 'what', 'answer': 'x', 'note': 'y'}], 'ANSWER_INVALID'),
                    ('a card concern on the document', [{'concern': 'made-by', 'answer': 'x'}], 'ANSWER_UNKNOWN'),
                    ('removing an undeclared concern', [{'concern': 'nope', 'target': 'belt', 'answer': None}], 'ANSWER_UNKNOWN')):
                refused, is_error = tool(base, 'schematic.concerns.answer', {'answers': answers})
                assert is_error and refused['ok'] is False and code(refused) == expect, (label, 'expected', expect, 'got', refused)
                assert document() == before, (label, 'changed the document')
            print('(f) ANSWER_TARGET_UNKNOWN for target no-such-id; ANSWER_INVALID for an empty list and an answer of 3; nothing changed')

            # (g) A stale revision.
            stale = {'answers': [{'concern': 'why', 'answer': 'To make bars.'}], 'ifRevision': before['revision'] - 1}
            refused, is_error = tool(base, 'schematic.concerns.answer', stale)
            assert is_error and refused['ok'] is False and refused['error']['message'].startswith('Stale revision'), refused
            status, body = http_json(base + '/api/v1/concerns', 'POST', stale)
            assert status == 409 and body['ok'] is False and body['error']['message'].startswith('Stale revision'), (status, body)
            assert document() == before, 'a stale write changed the document'
            print('(g) a stale ifRevision is refused over MCP and HTTP answers', status)

            # (h) HTTP gives what MCP gives.
            status, got = http_json(base + '/api/v1/concerns')
            assert status == 200 and got == tool(base, 'schematic.concerns')[0], ('GET /api/v1/concerns differs from schematic.concerns', status)
            status, got = http_json(base + '/api/v1/concerns?open=1')
            mcp_open = tool(base, 'schematic.concerns', {'open': True})[0]
            assert status == 200 and got == mcp_open and len(got['rows']) == 5, ('GET /api/v1/concerns?open=1 differs', status, len(got.get('rows', [])))
            status, bad = http_json(base + '/api/v1/concerns', 'POST', {'answers': MIXED})
            assert status == 400 and bad['ok'] is False and code(bad) == 'ANSWER_UNKNOWN' and document() == before, (status, bad)
            status, posted = http_json(base + '/api/v1/concerns', 'POST', {'answers': [{'concern': 'made-by', 'target': 'ore', 'answer': 'Dug from the pit.'}], 'ifRevision': before['revision']})
            assert status == 200 and posted['ok'] and set(posted) == set(receipt) and set(posted['result']) == set(receipt['result']) == {'ids', 'applied', 'report'}, (status, posted)
            assert posted['revisionAfter'] == before['revision'] + 1 and posted['result']['report'] == {'answered': 3, 'open': 4}, posted
            assert json.loads(saved())['revision'] == posted['revisionAfter'], 'POST /api/v1/concerns did not save'
            print('(h) GET /api/v1/concerns and ?open=1 equal the MCP reads; POST answers 200 with the receipt', sorted(posted['result']), 'and 400 for the refusal of (e)')

            # (i) Undo restores the document before the answer.
            before = document()
            receipt, is_error = tool(base, 'schematic.concerns.answer', {'answers': [{'concern': 'why', 'answer': 'To make bars.'}, {'concern': 'made-by', 'target': 'bar', 'answer': 'Smelted from ore.'}]})
            assert not is_error and receipt['result']['report'] == {'answered': 5, 'open': 2}, receipt
            undone, is_error = tool(base, 'schematic.history.undo')
            assert not is_error and document() == before, 'schematic.history.undo did not restore the document before the answer'
            assert tool(base, 'schematic.concerns')[0]['answered'] == 3
            print('(i) schematic.history.undo after an answer restores the document: answered 5 -> 3, revision', before['revision'])

            # (j) The saved file passes the validator, with the same counts.
            final = tool(base, 'schematic.concerns')[0]
            run = subprocess.run(['node', 'scripts/validate_sov.mjs', '--concerns', str(file)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
            lines = run.stdout.splitlines()
            assert run.returncode == 0 and lines and lines[0].startswith('ok   '), run.stdout + run.stderr
            assert lines[-1] == f"concerns: {final['answered']} answered, {final['open']} open", (lines[-1], final['answered'], final['open'])
            assert len([x for x in lines if x.startswith('open')]) == final['open'], lines
            print("(j) validate_sov.mjs --concerns on the saved file: exit 0, '" + lines[-1] + "'")

            # (k) The guide.
            index, is_error = tool(base, 'schematic.guide')
            steps = [line.split()[0] for line in index['guide'].splitlines() if line.startswith('  ')]
            assert not is_error and 'concerns' in steps and steps[steps.index('concerns') - 1] == 'palette' and steps[steps.index('concerns') + 1] == 'apply', steps
            assert 'then palette, then concerns, then apply' in ' '.join(index['guide'].split()), index['guide']
            assert tool(base, 'schematic.guide', {'step': 'palette'})[0]['next'] == 'concerns'
            step, is_error = tool(base, 'schematic.guide', {'step': 'concerns'})
            assert not is_error and step['next'] == 'apply' and 'schematic.concerns.answer' in step['guide'] and 'schematic.concerns {open: true}' in step['guide'], step
            apply_step = tool(base, 'schematic.guide', {'step': 'apply'})[0]['guide']
            assert apply_step.index('schematic.markers') < apply_step.index('schematic.concerns') < apply_step.index('schematic.render'), apply_step[-300:]
            assert 'schematic.concerns' in rpc(base, 'initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'qa', 'version': '0'}})['instructions']
            print('(k) schematic.guide lists', steps[:4], '; step concerns names both tools and its next is', step['next'])
            return fresh_rows
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()


PAGE = r"""([doc])=>{
  const A=window.SovSchematicAPI,out={};
  A.document.replace(doc);
  out.rows=A.concerns.list().rows;
  out.open=A.concerns.list({open:true});
  const revision=A.file.info().revision;
  const receipt=A.concerns.answer([{concern:'what',answer:'An ore line.'},{concern:'made-by',target:'ore',answer:'Dug from the pit.'}]);
  out.receipt={ok:receipt.ok,moved:receipt.revisionAfter-receipt.revisionBefore,report:receipt.result&&receipt.result.report,revision:A.file.info().revision-revision};
  const pick=()=>{const d=A.document.get();return {meta:d.meta?.answers??null,ore:d.components.find(c=>c.id==='ore')?.config?.answers??null,answered:A.concerns.list().answered}};
  out.set=pick();
  const refused=A.concerns.answer([{concern:'why',answer:'x'},{concern:'nope',answer:'x'}]);
  out.refused={ok:refused.ok,message:refused.error?.message||'',same:JSON.stringify(pick())===JSON.stringify(out.set)};
  out.undo=A.history.undo();
  out.undone=pick();
  return out;
}"""


def browser_part(fresh_rows: list) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.set_content((ROOT / 'index.html').read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_timeout(200)
        r = page.evaluate(PAGE, [DOC])
        page.wait_for_timeout(100)
        browser.close()
    assert r['rows'] == fresh_rows, ('SovSchematicAPI.concerns.list() differs from schematic.concerns for the same document', r['rows'])
    assert r['open']['rows'] == fresh_rows and (r['open']['answered'], r['open']['open']) == (0, 7), r['open']
    assert r['receipt'] == {'ok': True, 'moved': 1, 'report': {'answered': 2, 'open': 5}, 'revision': 1}, r['receipt']
    assert r['set'] == {'meta': {'what': 'An ore line.'}, 'ore': {'made-by': 'Dug from the pit.'}, 'answered': 2}, r['set']
    assert r['refused']['ok'] is False and r['refused']['message'].startswith('ANSWER_UNKNOWN:') and r['refused']['same'], r['refused']
    assert r['undo'] is True and r['undone'] == {'meta': None, 'ore': None, 'answered': 0}, ('one undo did not remove the answers', r['undo'], r['undone'])
    assert not errors, errors
    print('(l) SovSchematicAPI.concerns.list() gives the same 7 rows; concerns.answer sets the answers and one undo removes them; the page logged no errors')


def main() -> None:
    fresh_rows = server_part()
    browser_part(fresh_rows)
    print('PASS concerns on every surface QA')


if __name__ == '__main__':
    main()
