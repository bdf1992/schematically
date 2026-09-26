"""Step-through on the run page (browser).

scripts/plot_run.mjs --page puts step controls on the timing and search figures. Checked here
in a real page against the record, not against the page's own reading:

  - timing opens at the first event; each step forward moves the cursor to the next recorded
    change in time order, lights that change's lane mark and log row, and the status names the
    bus value the record decodes to at that time;
  - stepping past either end stays at the end; arrow keys step like the buttons;
  - search opens complete (no node faded); stepping to node k fades exactly the nodes decided
    after k, in the outline and the tree alike, and lights node k in both;
  - the page raises no script errors.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_runtime import chromium_launch_kwargs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from record_run import parse_vector, record_logic, record_optimize  # noqa: E402


def value_at(changes: list, t: float) -> int:
    v = 0
    for at, x in changes:
        if at <= t:
            v = x
    return v


def build(tmp: Path) -> tuple[str, dict, dict]:
    # A state space run of the 4-bit adder: 7 + 0, then B0 rises and the carry ripples to 8.
    ripple = record_logic(ROOT / 'examples' / 'logic' / 'adder4.sov', [parse_vector('A=7:4,B=0:4,Cin=0'), parse_vector('B0=1')], 20, ['S'])
    op = ROOT / 'examples' / 'optimization'
    learning = record_optimize(op / 'workshop.sov', op / 'workshop.learning.opt.json', segments=12, starts=4, steps=11)
    files = []
    for name, rec in (('ripple', ripple), ('learning', learning)):
        f = tmp / f'{name}.json'
        f.write_text(json.dumps(rec), encoding='utf-8')
        files.append(str(f))
    subprocess.run(['node', str(ROOT / 'scripts' / 'plot_run.mjs'), *files, '--out', str(tmp / 'svg'),
                    '--page', str(tmp / 'page.html')], check=True, stdout=subprocess.DEVNULL)
    return (tmp / 'page.html').read_text(encoding='utf-8'), ripple, learning


TIMING = """(fig)=>{const cur=fig.querySelector('[data-cursor]');
  const lit=[...fig.querySelectorAll('.hl')].map(x=>x.dataset.link);
  return {at:+fig.dataset.at,x:cur.getAttribute('x1'),shown:cur.getAttribute('display')!=='none',
          status:fig.querySelector('.step-status').textContent,lit};}"""

SEARCH = """(fig)=>{const sec=fig.closest('section');
  return [...sec.querySelectorAll('[data-order]')].map(g=>({order:+g.dataset.order,future:g.classList.contains('future'),
          hl:g.classList.contains('hl'),tree:!g.closest('figure').hasAttribute('data-step')}));}"""


def run() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        html, ripple, learning = build(Path(tmp))
    with sync_playwright() as p:
        b = p.chromium.launch(**chromium_launch_kwargs(disable_gpu=True))
        page = b.new_page(viewport={'width': 1200, 'height': 900})
        errors: list[str] = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content(html, wait_until='load')

        # Timing: the full timing view of the adder's run.
        fig = page.locator('figure[data-step="timing"]').first
        handle = fig.element_handle()
        marks = page.evaluate("(fig)=>[...fig.querySelectorAll('.stage [data-t]')].map(m=>({t:+m.dataset.t,x:m.dataset.x,link:m.dataset.link}))", handle)
        marks.sort(key=lambda m: m['t'])
        changes = sorted(c[0] for s, cs in ripple['signals'].items() for c in cs if c[0] > 0)
        assert [m['t'] for m in marks] == changes, 'one step per recorded change, in time order'
        bits = ripple['buses']['S']
        state = page.evaluate(TIMING, handle)
        assert state['at'] == 0 and state['shown'] and state['x'] == marks[0]['x'], state
        forward = fig.locator('.step button[data-step="1"]')
        for k in range(1, min(len(marks), 14)):
            forward.click()
            state = page.evaluate(TIMING, handle)
            m = marks[k]
            assert state['at'] == k and state['x'] == m['x'], (k, state, m)
            assert m['link'] in state['lit'] and state['lit'].count(m['link']) >= 2, ('lane mark and log row lit', k, state)
            q = sum(value_at(ripple['signals'][bit], m['t']) << i for i, bit in enumerate(bits))
            assert f'S = {q}' in state['status'], (k, m['t'], q, state['status'])
            assert state['status'].startswith(f'step {k + 1} of {len(marks)}'), state['status']
        # Ends hold; keys step like the buttons.
        fig.locator('.step button[data-step="-1"]').click()
        fig.focus()
        page.keyboard.press('ArrowRight')
        assert page.evaluate(TIMING, handle)['at'] == min(len(marks), 14) - 1
        for _ in range(len(marks) + 3):
            page.keyboard.press('ArrowLeft')
        assert page.evaluate(TIMING, handle)['at'] == 0
        page.evaluate("(fig)=>{const r=fig.querySelector('.step input');r.value=r.max;r.dispatchEvent(new Event('input'))}", handle)
        forward.click()
        assert page.evaluate(TIMING, handle)['at'] == len(marks) - 1

        # Search: opens complete, then each step fades exactly the later decisions.
        sfig = page.locator('figure[data-step="search"]').first
        shandle = sfig.element_handle()
        log = learning['search']['nodes']
        nodes = page.evaluate(SEARCH, shandle)
        assert len(nodes) == 2 * len(log), (len(nodes), len(log))
        assert not any(n['future'] for n in nodes), 'the search opens at its last step'
        back = sfig.locator('.step button[data-step="-1"]')
        for k in range(len(log) - 1, -1, -1):
            nodes = page.evaluate(SEARCH, shandle)
            for n in nodes:
                assert n['future'] == (n['order'] > k), (k, n)
                assert n['hl'] == (n['order'] == k), (k, n)
            assert sum(1 for n in nodes if n['hl'] and n['tree']) == 1, ('node lit in the tree too', k)
            assert f'node {k + 1} of {len(log)} decided' in sfig.locator('.step-status').text_content()
            back.click()
        assert not errors, errors
        b.close()


if __name__ == '__main__':
    run()
    print('run_page QA PASS')
