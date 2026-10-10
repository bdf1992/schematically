"""Access gate QA: the remote listener of mcp/server.mjs admits only Cloudflare Access tokens.

mcp/access.mjs must run where there is no node: module (Node 24 and Cloudflare Workers both have
the WebCrypto, fetch, atob and AbortSignal globals it uses), so this test first asserts it holds no
import line and no require( call. tests/access_gate_unit.mjs then drives the gate's key cache with
an injected clock and an injected certs answer, and tests/access_gate_check.mjs starts
mcp/server.mjs with a remote listener and its own loopback certs server and checks each admission
and refusal on both listeners, and that no request ends the process.
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- the import-free boundary: access.mjs imports nothing at all.
access = ROOT / 'mcp/access.mjs'
assert access.is_file(), 'mcp/access.mjs does not exist'
text = access.read_text(encoding='utf-8')
hit = re.search(r'^[ \t]*import\b.*$', text, re.MULTILINE)
assert not hit, f'mcp/access.mjs holds an import line: {hit.group(0)!r}'
assert 'require(' not in text, 'mcp/access.mjs holds a require( call'
print('PASS mcp/access.mjs imports nothing')

# --- the key cache under an injected clock (no server), then both listeners. Both always run, so
# one run shows every failing line.
exits = {}
for script in ('tests/access_gate_unit.mjs', 'tests/access_gate_check.mjs'):
    proc = subprocess.run(['node', str(ROOT / script)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    exits[script] = proc.returncode
bad = {script: code for script, code in exits.items() if code != 0}
assert not bad, ', '.join(f'{script} exited {code}' for script, code in bad.items())
print('PASS access gate QA')
