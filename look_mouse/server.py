"""The web interface, served by the Pi and opened in a browser on the main computer."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, body, ctype="application/json", code=200):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/":
                # Read from disk each time, so interface edits show up on refresh.
                with open(os.path.join(WEB, "index.html"), "rb") as f:
                    self._send(f.read(), "text/html; charset=utf-8")
            elif path == "/api/status":
                self._send(app.status())
            elif path == "/api/config":
                self._send(app.config.data)
            elif path == "/frame.jpg":
                jpeg = app.tracker.jpeg
                self._send(jpeg, "image/jpeg") if jpeg else self._send(b"", "text/plain", 404)
            else:
                self._send({"error": "not found"}, code=404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                self._send(self._route(self.path, body))
            except (KeyError, ValueError, IndexError, TypeError) as e:
                self._send({"ok": False, "reason": f"bad request: {e}"}, code=400)

        def _route(self, path, b):
            if path == "/api/config":
                app.config.update(b)
                return app.config.data
            if path == "/api/jump":
                return app.jump()
            if path == "/api/pointer/send":
                return app.send_to(int(b["monitor"]), float(b.get("u", .5)), float(b.get("v", .5)))
            if path == "/api/pointer/nudge":
                return app.nudge(int(b["counts"]))
            if path == "/api/calibrate/sample":
                return app.add_sample(int(b["monitor"]), float(b["u"]), float(b["v"]))
            if path == "/api/calibrate/clear":
                return app.clear_samples(b.get("monitor"))
            if path == "/api/sim" and app.tracker.simulated:
                app.tracker.f = [float(x) for x in b["f"]]
                app.tracker.face = bool(b.get("face", True))
                return {"ok": True}
            raise KeyError(path)

    return Handler


def serve(app, host, port):
    ThreadingHTTPServer((host, port), make_handler(app)).serve_forever()
