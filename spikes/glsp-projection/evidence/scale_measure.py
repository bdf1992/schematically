#!/usr/bin/env python3
"""Step 8: load evidence/scale-fixture.sov (252 components, 225 wires -- the
same node/wire count as the "racks=25" step in the orphaned
tests/scale-benchmark-results.json, see gen_scale_fixture.mjs) through the
real GLSP client and record wall time. Record only -- SCALE-GATE.md owns the
renderer question, not this spike.
"""
import http.server
import json
import os
import socket
import subprocess
import threading
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(HERE, "client", "dist")
FIXTURE = os.path.join(HERE, "evidence", "scale-fixture.sov")


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DIST, **kw)

    def log_message(self, *a):
        pass


def main():
    ws_port = free_port()
    http_port = free_port()
    server_proc = subprocess.Popen(
        ["node", "server.mjs", "--port", str(ws_port), "--file", FIXTURE],
        cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    time.sleep(1)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", http_port), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            start = time.perf_counter()
            page.goto(f"http://127.0.0.1:{http_port}/index.html?port={ws_port}")
            page.wait_for_function("() => !!window.__glspReady", timeout=30000)
            cold_ms = (time.perf_counter() - start) * 1000
            node_count = page.evaluate("() => document.querySelectorAll('[data-svg-metadata-type^=node]').length")
            edge_count = page.evaluate("() => document.querySelectorAll('[data-svg-metadata-type=edge]').length")
            browser.close()
    finally:
        httpd.shutdown()
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except Exception:
            server_proc.kill()

    result = {
        "fixture": "evidence/scale-fixture.sov",
        "components": 252,
        "wires": 225,
        "rendered_nodes": node_count,
        "rendered_edges": edge_count,
        "cold_render_ms_navigate_to_glspReady": cold_ms
    }
    print(json.dumps(result, indent=2))
    with open(os.path.join(HERE, "evidence", "scale-measurement.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
