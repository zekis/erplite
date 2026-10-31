"""Loopback-only synthetic application server for browser tests.

Runs the actual Workz service and document guards through the test adapter.
NEVER install this server in a Frappe site or expose it on a public interface.
"""

import json
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fake_site import Site

site = Site()
for name in ("Administrator", "alice", "lead", "approver", "stranger"):
    site.seed("User", name, enabled=1, full_name=name, roles=[])
root = Path(__file__).resolve().parents[2]


class Handler(BaseHTTPRequestHandler):
    def actor(self):
        cookie = self.headers.get("Cookie", "")
        return next(
            (
                c.split("=", 1)[1]
                for c in cookie.split("; ")
                if c.startswith("synthetic_user=")
            ),
            "Administrator",
        )

    def do_GET(self):
        if self.path.startswith("/assets/erplite/"):
            path = (
                root / "erplite/public" / self.path.removeprefix("/assets/erplite/")
            ).resolve()
            if not path.is_relative_to(root / "erplite/public") or not path.is_file():
                self.send_error(404)
                return
            content = path.read_bytes()
            mime = (
                "text/javascript"
                if path.suffix == ".js"
                else "text/css" if path.suffix == ".css" else "image/svg+xml"
            )
        else:
            boot = json.dumps({"user": self.actor(), "csrf_token": "synthetic-only"})
            content = f'<html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="/assets/erplite/workz/index.css"></head><body><div id="root"></div><script>window.workzBoot={boot}</script><script type="module" src="/assets/erplite/workz/app.js"></script></body></html>'.encode()
            mime = "text/html"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        try:
            site.as_user(self.actor())
            result = site.call(payload["action"], payload.get("payload"))
            response = {"message": result}
            status = 200
        except Exception as e:
            response = {"message": str(e), "exc": type(e).__name__}
            status = 403
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        try:
            self.wfile.write(json.dumps(response, default=str).encode())
        except BrokenPipeError:
            pass  # The browser navigated away from an in-flight read.

    def log_message(self, *a):
        pass


HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
