#!/usr/bin/env python3
"""Local production host: static SPA + reverse proxy for /api."""
from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = Path(os.environ.get("MMF_STATIC_ROOT", str(ROOT / "artifacts" / "market-frontend" / "dist" / "public")))
BACKEND = os.environ.get("MMF_BACKEND_URL", "http://127.0.0.1:8080").rstrip("/")
HOST = os.environ.get("MMF_FRONTEND_HOST", "127.0.0.1")
PORT = int(os.environ.get("MMF_FRONTEND_PORT", "5173"))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # Do not log query strings or request bodies: they may contain sensitive values.
        print(f"{self.command} {urlsplit(self.path).path} -> {args[1]}")

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self.proxy()
        return self.serve_static()

    def do_HEAD(self):
        if self.path.startswith("/api/"):
            return self.proxy(head_only=True)
        return self.serve_static(head_only=True)

    def do_POST(self):
        return self.proxy()

    def do_PUT(self):
        return self.proxy()

    def do_PATCH(self):
        return self.proxy()

    def do_DELETE(self):
        return self.proxy()

    def serve_static(self, head_only=False):
        relative = urlsplit(self.path).path.lstrip("/")
        candidate = (STATIC_ROOT / relative).resolve()
        try:
            candidate.relative_to(STATIC_ROOT.resolve())
        except ValueError:
            return self.send_error(403)
        if not candidate.is_file():
            candidate = STATIC_ROOT / "index.html"
        if not candidate.is_file():
            return self.send_error(503, "Production frontend is not built")
        body = candidate.read_bytes()
        content_type = "text/html; charset=utf-8" if candidate.suffix == ".html" else self.guess_type(candidate)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    @staticmethod
    def guess_type(path: Path) -> str:
        return {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json"}.get(path.suffix, "application/octet-stream")

    def proxy(self, head_only=False):
        target = BACKEND + self.path
        body = None
        if self.command not in {"GET", "HEAD"}:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else b""
        headers = {key: value for key, value in self.headers.items() if key.lower() not in {"host", "content-length", "connection"}}
        try:
            request = Request(target, data=body, headers=headers, method=self.command)
            with urlopen(request, timeout=60) as response:
                payload = response.read() if not head_only else b""
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() not in {"transfer-encoding", "connection"}:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if payload:
                    self.wfile.write(payload)
        except HTTPError as error:
            payload = error.read()
            self.send_response(error.code)
            self.send_header("Content-Type", error.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if not head_only:
                self.wfile.write(payload)
        except (URLError, TimeoutError, OSError) as error:
            self.send_error(502, f"Backend unavailable: {type(error).__name__}")


if __name__ == "__main__":
    if not (STATIC_ROOT / "index.html").is_file():
        raise SystemExit(f"Build frontend first: {STATIC_ROOT}")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"MMF local production host: http://{HOST}:{PORT}/login")
    print(f"API backend: {BACKEND}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
