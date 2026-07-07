#!/usr/bin/env python3
"""
Bundle the dashboard into a single self-contained index.html at the repo root.

GitHub Pages "deploy from a branch" serves files from the branch root, so this
produces one standalone page (inline CSS, inline JS, data embedded — no fetch)
that works at the plain Pages URL with no build step on GitHub's side.

Run `python3 build_data.py` first (to refresh data.json), then `python3
build_index.py`. Open index.html directly, or serve the repo with any static
server.
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))


def read(path):
    with open(os.path.join(HERE, path), encoding="utf-8") as fh:
        return fh.read()


def main():
    css = read("web/styles.css")
    data = read("data.json")
    app = read("web/app.js")

    # Swap the network loadData() for the embedded snapshot, and drop the
    # server-only Refresh wiring (there is no backend on a static host).
    app = app.replace(
        'async function loadData() {',
        'const EMBEDDED = ' + data + ';\nasync function loadData() {\n  applyData(EMBEDDED);\n  return;\n  // eslint-disable-next-line no-unreachable',
        1,
    )
    # Remove the server-only Refresh button wiring (no backend on a static host).
    app = re.sub(
        r'\n  const btn = document\.getElementById\("refreshBtn"\);.*?\n  \}\);\n',
        "\n",
        app,
        flags=re.S,
    )

    body = read("web/index.html")
    # Strip the standalone-doc scaffolding and the Refresh button + external refs.
    body = body.split("<body>", 1)[1].split("</body>", 1)[0]
    body = body.replace(
        '<button id="refreshBtn" class="btn-ghost" type="button">Refresh</button>', ""
    )
    body = body.replace('<a class="back" href="#">&larr; Back to home</a>', "")
    body = body.replace('<script src="app.js"></script>', "")
    body = body.replace('<link rel="stylesheet" href="styles.css" />', "")

    doc = (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"UTF-8\" />\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />\n"
        "<title>Quantum Technology Companies</title>\n"
        "<meta name=\"description\" content=\"Interactive dashboard of quantum technology companies — hardware and software, pre-seed to public.\" />\n"
        "<style>\n" + css + "\n</style>\n</head>\n<body>\n"
        + body
        + "\n<script>\n" + app + "\n</script>\n</body>\n</html>\n"
    )

    out = os.path.join(HERE, "index.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(doc)
    records = len(json.loads(data)["records"])
    print(f"Wrote {out} ({len(doc):,} bytes, {records} companies embedded)")


if __name__ == "__main__":
    main()
