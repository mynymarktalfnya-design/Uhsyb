#!/usr/bin/env python3
"""Persistent local queue service for Mini Market offline operations.

Runs on localhost, persists operations in SQLite, and retries them against the
configured API. The queue is append-only until an operation is confirmed by a
2xx response; synced rows are retained for audit/recovery.
"""
from __future__ import annotations

import json
import hmac
import os
import sqlite3
import threading
import time
import uuid
import base64
from pathlib import Path
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import parse_qsl, urlparse

HOST = os.environ.get("MMF_LOCAL_HOST", "127.0.0.1")
PORT = int(os.environ.get("MMF_LOCAL_PORT", "8765"))
DB_PATH = os.environ.get("MMF_LOCAL_DB", os.path.join(os.path.expanduser("~"), ".mmf", "offline-queue.sqlite3"))
SYNC_INTERVAL = max(1, int(os.environ.get("MMF_SYNC_INTERVAL_SECONDS", "5")))
MAX_RETRIES = max(1, int(os.environ.get("MMF_MAX_RETRIES", "0")))  # 0 = unlimited
ALLOWED_ORIGINS = {
    value.strip().rstrip("/") for value in os.environ.get(
        "MMF_LOCAL_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
    ).split(",") if value.strip()
}
LOCAL_TOKEN_FILE = os.environ.get(
    "MMF_LOCAL_TOKEN_FILE",
    os.path.join(os.environ.get("ProgramData", os.path.expanduser("~/.mmf")), "MMF", "offline", "local-service.token")
    if os.name == "nt" else os.path.join(os.path.expanduser("~/.mmf"), "local-service.token"),
)


def _load_local_auth_token():
    configured = os.environ.get("MMF_LOCAL_AUTH_TOKEN", "").strip()
    if configured:
        return configured
    try:
        return Path(LOCAL_TOKEN_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


LOCAL_AUTH_TOKEN = _load_local_auth_token()

_db_lock = threading.RLock()
_stop = threading.Event()


def now():
    return datetime.now(timezone.utc).isoformat()


def _protect_auth(value):
    """Protect JWT at rest on Windows; never write the raw token to SQLite."""
    if not value:
        return None
    if os.name != "nt":
        return None
    try:
        import win32crypt
        encrypted = win32crypt.CryptProtectData(value.encode("utf-8"), "MMF JWT", None, None, None, 0)[1]
        return base64.b64encode(encrypted).decode("ascii")
    except Exception as exc:
        raise RuntimeError(f"Windows DPAPI unavailable: {exc}")


def _unprotect_auth(value):
    if not value or os.name != "nt":
        return None
    import win32crypt
    encrypted = base64.b64decode(value.encode("ascii"))
    return win32crypt.CryptUnprotectData(encrypted, None, None, None, 0)[1].decode("utf-8")


def db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", mode=0o700, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("""CREATE TABLE IF NOT EXISTS operations (
        id TEXT PRIMARY KEY,
        operation_id TEXT NOT NULL UNIQUE,
        url TEXT NOT NULL,
        method TEXT NOT NULL,
        headers TEXT NOT NULL,
        body TEXT,
        state TEXT NOT NULL CHECK(state IN ('pending','syncing','synced','failed')),
        retries INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        synced_at TEXT
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_operations_state ON operations(state, created_at)")
    conn.commit()
    return conn


def enqueue(item):
    operation_id = str(item.get("operation_id") or uuid.uuid4())
    url = str(item.get("url") or "")
    method = str(item.get("method") or "POST").upper()
    parsed_url = urlparse(url)
    if not url or parsed_url.scheme not in {"http", "https"}:
        raise ValueError("A valid http(s) URL is required")
    if any(key.lower() in {"token", "access_token", "refresh_token", "password", "secret", "api_key"} for key, _ in parse_qsl(parsed_url.query)):
        raise ValueError("Sensitive query parameters are not allowed in offline requests")
    headers = dict(item.get("headers") or {})
    auth = headers.pop("Authorization", None) or headers.pop("authorization", None)
    auth_protected = _protect_auth(auth)
    headers["X-Operation-ID"] = operation_id
    body = item.get("body")
    def has_sensitive_key(value):
        if isinstance(value, dict):
            if any(str(key).lower() in {"authorization", "cookie", "password", "access_token", "refresh_token", "secret", "api_key"} for key in value):
                return True
            return any(has_sensitive_key(child) for child in value.values())
        if isinstance(value, list):
            return any(has_sensitive_key(child) for child in value)
        return False
    body_for_check = body
    if isinstance(body, str):
        try:
            body_for_check = json.loads(body)
        except json.JSONDecodeError:
            body_for_check = None
    if has_sensitive_key(body_for_check):
        raise ValueError("Sensitive fields are not allowed in offline request bodies")
    payload = json.dumps(body, ensure_ascii=False) if not isinstance(body, str) else body
    stamp = now()
    with _db_lock:
        conn = db()
        row = conn.execute("SELECT * FROM operations WHERE operation_id = ?", (operation_id,)).fetchone()
        if row:
            conn.close()
            return dict(row)
        op_id = str(uuid.uuid4())
        conn.execute("INSERT INTO operations(id, operation_id, url, method, headers, body, state, last_error, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)",
                     (op_id, operation_id, url, method, json.dumps({"headers": headers, "auth_protected": auth_protected}), payload, None, stamp, stamp))
        conn.commit()
        row = conn.execute("SELECT * FROM operations WHERE id = ?", (op_id,)).fetchone()
        conn.close()
        return dict(row)


def list_operations(limit=100):
    with _db_lock:
        conn = db()
        rows = [dict(x) for x in conn.execute("SELECT * FROM operations ORDER BY created_at LIMIT ?", (limit,))]
        conn.close()
        return rows


def operation_summary(row):
    """Expose queue state only; never return headers, auth, or operation body."""
    return {
        "id": row.get("id"),
        "operation_id": row.get("operation_id"),
        "state": row.get("state"),
        "retries": int(row.get("retries") or 0),
        "last_error": row.get("last_error"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "synced_at": row.get("synced_at"),
    }


def sync_one(row, transient_auth=None):
    with _db_lock:
        conn = db()
        claimed = conn.execute(
            "UPDATE operations SET state='syncing', updated_at=? WHERE id=? AND state IN ('pending','failed')",
            (now(), row["id"]),
        ).rowcount
        conn.commit()
        conn.close()
    # Another worker/request may have claimed this row between listing and
    # sending. Never send an operation unless this worker owns the claim.
    if claimed != 1:
        return None
    saved = json.loads(row["headers"] or "{}")
    headers = dict(saved.get("headers") or {})
    auth = transient_auth or _unprotect_auth(saved.get("auth_protected"))
    if auth:
        headers["Authorization"] = auth
    # The browser stores the JWT in the queued request only in memory; the
    # service accepts a refreshed Authorization header on /sync when supplied.
    body = row["body"].encode("utf-8") if row["body"] is not None else None
    req = Request(row["url"], data=body, headers=headers, method=row["method"])
    try:
        with urlopen(req, timeout=30) as response:
            status = response.status
            response.read(1024)
        if 200 <= status < 300:
            with _db_lock:
                conn = db()
                conn.execute("UPDATE operations SET state='synced', synced_at=?, updated_at=?, last_error=NULL WHERE id=?", (now(), now(), row["id"]))
                conn.commit(); conn.close()
            return True
        raise RuntimeError(f"HTTP {status}")
    except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
        with _db_lock:
            conn = db()
            retries = int(row.get("retries") or 0) + 1
            conn.execute("UPDATE operations SET state='failed', retries=?, last_error=?, updated_at=? WHERE id=?", (retries, str(exc)[:500], now(), row["id"]))
            conn.commit(); conn.close()
        return False


def sync_loop():
    while not _stop.wait(SYNC_INTERVAL):
        for row in list_operations(100):
            if row["state"] not in {"pending", "failed"}:
                continue
            if MAX_RETRIES and int(row["retries"] or 0) >= MAX_RETRIES:
                continue
            if not sync_one(row):
                break


class Handler(BaseHTTPRequestHandler):
    server_version = "MMFLocalService/1.0"

    def log_message(self, *_args):
        return

    def _send(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        origin = self.headers.get("Origin", "").rstrip("/")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Operation-ID, Authorization, X-MMF-Local-Auth")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers(); self.wfile.write(data)

    def _authorized(self):
        if not LOCAL_AUTH_TOKEN:
            return True  # Development/standalone mode; packaged Electron sets this token.
        supplied = self.headers.get("X-MMF-Local-Auth", "")
        return bool(supplied) and hmac.compare_digest(supplied, LOCAL_AUTH_TOKEN)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        if self.path == "/health":
            rows = list_operations(10000)
            counts = {state: sum(1 for row in rows if row["state"] == state) for state in ("pending", "syncing", "synced", "failed")}
            return self._send(200, {"status": "ok", "service": "mmf-local", "queue": counts})
        if self.path.startswith("/queue"):
            if not self._authorized():
                return self._send(403, {"detail": "Local authentication required"})
            return self._send(200, {"operations": [operation_summary(row) for row in list_operations()]})
        self._send(404, {"detail": "Not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/queue":
                if not self._authorized():
                    return self._send(403, {"detail": "Local authentication required"})
                return self._send(202, operation_summary(enqueue(payload)))
            if self.path == "/sync":
                if not self._authorized():
                    return self._send(403, {"detail": "Local authentication required"})
                transient_auth = self.headers.get("Authorization") or self.headers.get("authorization")
                for row in list_operations(100):
                    if row["state"] in {"pending", "failed"}: sync_one(row, transient_auth=transient_auth)
                return self._send(200, {"operations": [operation_summary(row) for row in list_operations()]})
        except Exception as exc:
            return self._send(400, {"detail": str(exc)[:300]})
        self._send(404, {"detail": "Not found"})


def main():
    db().close()
    thread = threading.Thread(target=sync_loop, daemon=True)
    thread.start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _stop.set(); server.server_close()


if __name__ == "__main__":
    main()
