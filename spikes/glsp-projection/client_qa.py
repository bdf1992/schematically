#!/usr/bin/env python3
"""Playwright QA for the bundled GLSP 2.8.0 client (client/dist) against the
real server.mjs, both driving and being driven by real @eclipse-glsp/client
and @eclipse-glsp/protocol code -- no mock of either side. The client has no
tool palette wired to the server (server.mjs implements no
RequestContextActions palette provider, out of scope for this spike -- see
REPORT.md), so interactions are driven by dispatching real GLSP actions
through the real action dispatcher exposed at window.__glsp, exercising the
same GModel, command stack and server round trip a palette click would.

Asserts, against examples/08-gated-service.sov, projected through
src/05-data-core.js:
  1. 9 graphical nodes (6 typed + 3 ports) and 7 edges render.
  2. A move (ChangeBoundsOperation on a top-level node) updates both the
     rendered position and the document (the server's own re-projection
     reflects the new position).
  3. A boundary-crossing CreateEdgeOperation leaves the document unchanged
     (the server answers setMarkers, not setModel) and carries the core's
     own refusal reason.
  4. A legal CreateEdgeOperation adds a wire with a schematically id
     (server's own k<N> scheme) to the document.
  5. UndoAction is dispatched after the legal create and the result --
     whichever side, if any, actually reverts -- is recorded, not assumed.
"""
import json
import os
import re
import socket
import subprocess
import sys
import time
import http.server
import threading

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "client", "dist")
EVIDENCE = os.path.join(HERE, "evidence")


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def build_client():
    npx = "npx.cmd" if os.name == "nt" else "npx"
    result = subprocess.run(
        [npx, "webpack", "--config", os.path.join("client", "webpack.config.cjs")],
        cwd=HERE, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit("client build failed")
    index_src = os.path.join(HERE, "client", "index.html")
    index_dst = os.path.join(DIST, "index.html")
    with open(index_src, "r", encoding="utf-8") as f:
        html = f.read()
    with open(index_dst, "w", encoding="utf-8") as f:
        f.write(html)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DIST, **kw)

    def log_message(self, *a):
        pass


def main():
    build_client()

    ws_port = free_port()
    http_port = free_port()

    server_proc = subprocess.Popen(
        ["node", "server.mjs", "--port", str(ws_port)],
        cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    time.sleep(1)
    if server_proc.poll() is not None:
        print(server_proc.stdout.read())
        raise SystemExit("server.mjs exited before the client could connect")

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", http_port), QuietHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    frames = []
    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))
        print(("ok" if cond else "FAIL") + " - " + name)
        if not cond:
            raise SystemExit(1)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            console_errors = []
            page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
            page.on("websocket", lambda ws: ws.on("framereceived", lambda payload: frames.append(payload if isinstance(payload, str) else None)))

            page.goto(f"http://127.0.0.1:{http_port}/index.html?port={ws_port}")
            page.wait_for_function("() => !!window.__glspReady", timeout=15000)

            def actions():
                out = []
                for raw in frames:
                    if not raw:
                        continue
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    if msg.get("method") == "process" and "action" in msg.get("params", {}):
                        out.append(msg["params"]["action"])
                return out

            # 1. counts
            node_count = page.evaluate("() => document.querySelectorAll('[data-svg-metadata-type^=node]').length")
            port_count = page.evaluate("() => document.querySelectorAll('[data-svg-metadata-type=port]').length")
            edge_count = page.evaluate("() => document.querySelectorAll('[data-svg-metadata-type=edge]').length")
            check("9 graphical nodes render (6 typed + 3 ports)", node_count + port_count == 9)
            check("7 edges render", edge_count == 7)

            initial_setmodel = [a for a in actions() if a.get("kind") == "setModel"][-1]
            grant_before = next(c for c in initial_setmodel["newRoot"]["children"] if c["id"] == "grant")
            check("initial model carries grant's authored position", grant_before["position"] == {"x": 160, "y": 290})

            # 2. move: ChangeBoundsOperation on a top-level node (grant, not nested,
            # so the client's local coordinate equals the document's absolute one --
            # see adapter.mjs on nested-child coordinates).
            page.evaluate("""() => window.__glsp.dispatch({
                kind: 'changeBounds',
                newBounds: [{ elementId: 'grant', newPosition: { x: 240, y: 290 }, newSize: { width: 112, height: 84 } }]
            })""")
            page.wait_for_timeout(500)
            moved = [a for a in actions() if a.get("kind") == "setModel"][-1]
            grant_after = next(c for c in moved["newRoot"]["children"] if c["id"] == "grant")
            check("move: server's re-projection reflects the new position (document was patched)", grant_after["position"] == {"x": 240, "y": 290})
            rendered_x = page.evaluate("() => document.getElementById('sprotty_grant').getAttribute('transform')")
            check("move: the DOM element itself re-renders at the new position", "240" in (rendered_x or ""))

            # 3. boundary-crossing create: req -> check, refused by the core.
            page.evaluate("""() => window.__glsp.dispatch({
                kind: 'createEdge', elementTypeId: 'edge', sourceElementId: 'req', targetElementId: 'check'
            })""")
            page.wait_for_timeout(500)
            refusal = [a for a in actions() if a.get("kind") == "setMarkers"][-1]
            check("boundary-crossing create refused, not applied (server answered setMarkers, not setModel)", refusal["markers"][0]["description"] == "Boundary blocks implicit reach-through")
            still_seven = page.evaluate("() => document.querySelectorAll('[data-svg-metadata-type=edge]').length")
            check("boundary-crossing create left the rendered document at 7 edges", still_seven == 7)

            # 4. legal create: grant -> egress (both reach canvas:global).
            page.evaluate("""() => window.__glsp.dispatch({
                kind: 'createEdge', elementTypeId: 'edge', sourceElementId: 'grant', targetElementId: 'egress'
            })""")
            page.wait_for_timeout(500)
            created = [a for a in actions() if a.get("kind") == "setModel"][-1]
            new_edge_ids = [c["id"] for c in created["newRoot"]["children"] if c.get("type") == "edge"]
            check("legal create added an 8th wire", len(new_edge_ids) == 8)
            new_id = [i for i in new_edge_ids if i not in ("k1", "k2", "k3", "k4", "k5", "k6", "k7")][0]
            check("the new wire carries a schematically id (server's own k<N> scheme, not a GLSP-minted id)", re.match(r"^k\d+$", new_id) is not None)
            eight_rendered = page.evaluate("() => document.querySelectorAll('[data-svg-metadata-type=edge]').length")
            check("the 8th edge actually rendered", eight_rendered == 8)

            # 5. undo: dispatch UndoAction and record -- not assume -- what happens.
            # @eclipse-glsp/protocol's UndoAction.KIND is 'glspUndo' (distinct from
            # sprotty-protocol's client-local 'undo'): GLSP 2.8.0 models undo/redo as
            # actions *forwarded to the server* (see node_modules/@eclipse-glsp/
            # protocol/lib/action-protocol/undo-redo.d.ts) -- the command stack GLSP's
            # own client ships for is the server's, not sprotty's local one. This
            # spike's server implements no operation history, so glspUndo has nothing
            # to answer; that refusal (not a crash) is the recorded finding.
            frame_count_before_undo = len(frames)
            undo_error = None
            try:
                page.evaluate("() => window.__glsp.undo()")
            except Exception as exc:
                undo_error = str(exc)
            page.wait_for_timeout(500)
            undo_produced_new_frame = len(frames) > frame_count_before_undo
            edges_after_undo = page.evaluate("() => document.querySelectorAll('[data-svg-metadata-type=edge]').length")
            print("undo: dispatched @eclipse-glsp/protocol UndoAction.create() (kind 'glspUndo')")
            print(f"undo: dispatcher error: {undo_error!r}" if undo_error else "undo: no dispatcher error")
            print(f"undo: {'a wire-protocol frame followed' if undo_produced_new_frame else 'no wire-protocol frame followed'} the UndoAction")
            print(f"undo: rendered edge count after UndoAction: {edges_after_undo} (was 8 before undo)")

            check("no console errors during the whole sequence", len(console_errors) == 0)

            # Step 7: drive GLSP's own ExportSvgAction (the "unified export
            # pipeline" -- exportModule alone only wires the request/command side;
            # standaloneExportModule, added in client/app.mjs, is what actually
            # triggers the file-saver download) and save the result to evidence/
            # for comparison against scripts/export_svg.py on the same fixture.
            page.goto(f"http://127.0.0.1:{http_port}/index.html?port={ws_port}")
            page.wait_for_function("() => !!window.__glspReady", timeout=15000)
            with page.expect_download(timeout=8000) as dl_info:
                page.evaluate("() => window.__glsp.exportSvg()")
            svg_path = dl_info.value.path()
            with open(svg_path, "r", encoding="utf-8") as f:
                svg_content = f.read()
            os.makedirs(EVIDENCE, exist_ok=True)
            with open(os.path.join(EVIDENCE, "glsp-export.svg"), "w", encoding="utf-8") as f:
                f.write(svg_content)
            check("GLSP's ExportSvgAction produced a real SVG document", svg_content.strip().startswith("<svg"))
            print(f"GLSP export: {len(svg_content)} bytes, saved to evidence/glsp-export.svg")

            browser.close()

            summary = {
                "checks": checks,
                "counts": {"nodes": node_count, "ports": port_count, "edges": edge_count},
                "undo": {
                    "action_kind_dispatched": "glspUndo",
                    "dispatcher_error": undo_error,
                    "produced_server_round_trip": undo_produced_new_frame,
                    "rendered_edges_after_undo": edges_after_undo
                }
            }
            os.makedirs(EVIDENCE, exist_ok=True)
            with open(os.path.join(EVIDENCE, "client_qa_result.json"), "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
    finally:
        httpd.shutdown()
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except Exception:
            server_proc.kill()

    print(f"\n{len(checks)} checks passed.")


if __name__ == "__main__":
    main()
