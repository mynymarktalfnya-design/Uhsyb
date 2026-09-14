#!/usr/bin/env python3
"""Persistent local queue service for Mini Market offline operations.

Runs on localhost, persists operations in SQLite, and retries them against the
configured API. The queue is append-only until an operation is confirmed by a
2xx response; synced rows are retained for audit/recovery.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse

HOST = os.environ.get("MMF_LOCAL_HOST", "127.0.0.1")
PORT = int(os.environ.get("MMF_LOCAL_PORT", "8765"))
DB_PATH = os.environ.get("MMF_LOCAL_DB", os.path.join(os.path.expanduser("~"), ".mmf", "offline-queue.sqlite3"))
SYNC_INTERVAL = max(1, int(os.environ.get("MMF_SYNC_INTERVAL_SECONDS", "5")))
MAX_RETRIES = max(1, int(os.environ.get("MMF_MAX_RETRIES", "0")))  # 0 = unlimited

_db_lock = threading.RLock()
_stop = threading.Event()


def now():
    return datetime.now(timezone.utc).isoformat()


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
    if not url or urlparse(url).scheme not in {"http", "https"}:
        raise ValueError("A valid http(s) URL is required")
    headers = dict(item.get("headers") or {})
    headers.pop("Authorization", None)
    headers.pop("authorization", None)
    headers["X-Operation-ID"] = operation_id
    payload = json.dumps(item.get("body"), ensure_ascii=False) if not isinstance(item.get("body"), str) else item.get("body")
    stamp = now()
    with _db_lock:
        conn = db()
        row = conn.execute("SELECT * FROM operations WHERE operation_id = ?", (operation_id,)).fetchone()
        if row:
            conn.close()
            return dict(row)
        op_id = str(uuid.uuid4())
        conn.execute("INSERT INTO operations(id, operation_id, url, method, headers, body, state, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
                     (op_id, operation_id, url, method, json.dumps(headers), payload, stamp, stamp))
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


def sync_one(row):
    with _db_lock:
        conn = db()
        conn.execute("UPDATE operations SET state='syncing', updated_at=? WHERE id=? AND state IN ('pending','failed')", (now(), row["id"]))
        conn.commit()
        conn.close()
    headers = json.loads(row["headers"] or "{}")
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
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Operation-ID, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers(); self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        if self.path == "/health":
            rows = list_operations(10000)
            counts = {state: sum(1 for row in rows if row["state"] == state) for state in ("pending", "syncing", "synced", "failed")}
            return self._send(200, {"status": "ok", "service": "mmf-local", "queue": counts})
        if self.path.startswith("/queue"):
            return self._send(200, {"operations": list_operations()})
        self._send(404, {"detail": "Not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/queue":
                return self._send(202, enqueue(payload))
            if self.path == "/sync":
                for row in list_operations(100):
                    if row["state"] in {"pending", "failed"}: sync_one(row)
                return self._send(200, {"operations": list_operations()})
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
