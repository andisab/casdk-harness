#!/usr/bin/env python3
"""Tiny webhook receiver that logs AlertManager payloads to stdout.

Used by docker-compose's alertmanager-webhook service so dev users can
observe alert delivery without configuring Slack/email/PagerDuty.

Listens on :5001, accepts POST with a JSON body, logs everything to
stdout (visible via `docker compose logs alertmanager-webhook`).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        ts = datetime.now(timezone.utc).isoformat()
        print(f"=== AlertManager webhook @ {ts} ===", flush=True)
        try:
            parsed = json.loads(body)
            print(json.dumps(parsed, indent=2), flush=True)
        except json.JSONDecodeError:
            print(body, flush=True)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK\n")

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"alertmanager-webhook-debug listening on :5001\n")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002, ARG002
        # Suppress default access logs — we already log payloads ourselves.
        pass


def main() -> None:
    port = 5001
    server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    print(f"alertmanager-webhook-debug listening on 0.0.0.0:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("shutting down", flush=True)
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
