#!/usr/bin/env python3
"""
Tiny zero-dependency dev server for the Quantum Companies dashboard.

    python3 server.py            # serve on http://localhost:8000
    python3 server.py 9000       # pick a port

It serves the static files in ./web and exposes one extra endpoint,
POST /api/refresh, which re-runs build_data.py so the dashboard's
"Refresh" button rebuilds data.json from companies.csv.
"""

import os
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/web/")
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/refresh":
            self.refresh()
            return
        self.send_error(404, "Not found")

    def refresh(self):
        try:
            subprocess.run(
                [sys.executable, os.path.join(HERE, "build_data.py")],
                cwd=HERE,
                check=True,
                timeout=60,
            )
            body = b'{"ok": true}'
            code = 200
        except Exception as exc:  # noqa: BLE001
            body = ('{"ok": false, "error": %r}' % str(exc)).encode()
            code = 500
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # quieter logs
        sys.stderr.write("  %s\n" % (fmt % args))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Serving npm concentration dashboard on http://localhost:{port}")
    print("Open the browser there, or Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBye.")


if __name__ == "__main__":
    main()
