"""Local fixture site for browser-mode tests. Synthetic data only."""

import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

ROOT = Path(__file__).parent


class Handler(SimpleHTTPRequestHandler):
    submissions = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *args):
        pass

    def do_GET(self):
        parts = urlsplit(self.path)
        if parts.path == "/redirect":
            # Drops gclid on the way to the landing page.
            query = {k: v[0] for k, v in parse_qs(parts.query).items() if k != "gclid"}
            self.send_response(302)
            self.send_header("Location", "/landing.html?" + urlencode(query))
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode()
        if self.path == "/submit-json":
            body = json.loads(raw)
        else:
            body = {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}
        self.submissions.append(body)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<p>thanks</p>")


def start():
    submissions = []
    handler = type("BoundHandler", (Handler,), {"submissions": submissions})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, submissions
