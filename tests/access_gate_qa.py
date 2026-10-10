"""Access gate QA: the remote listener of mcp/server.mjs admits only Cloudflare Access tokens.

mcp/access.mjs must run where there is no node: module (Node 24 and Cloudflare Workers both have
the WebCrypto, fetch, atob and AbortSignal globals it uses), so this test first asserts it holds no
import line and no require( call. tests/access_gate_check.mjs then starts mcp/server.mjs with a
remote listener and its own loopback certs server, and checks each admission and refusal on both
listeners.
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

# --- both listeners, driven by access_gate_check.mjs.
proc = subprocess.run(['node', str(ROOT / 'tests/access_gate_check.mjs')], cwd=ROOT, capture_output=True, text=True, timeout=300)
sys.stdout.write(proc.stdout)
sys.stderr.write(proc.stderr)
assert proc.returncode == 0, f'tests/access_gate_check.mjs exited {proc.returncode}'
print('PASS access gate QA')
