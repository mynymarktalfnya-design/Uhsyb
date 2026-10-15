"""Durable Windows-local operation store.

The store survives browser and Windows restarts. It deliberately stores only
operation envelopes and status metadata; credentials are not written to logs.
A later sync worker claims rows atomically and marks them Synced or Failed.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

STATUSES = ("Pending", "Syncing", "Synced", "Failed")

class OfflineStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS operations (
                  operation_id TEXT PRIMARY KEY,
                  method TEXT NOT NULL,
                  url TEXT NOT NULL,
                  body TEXT,
                  metadata TEXT NOT NULL DEFAULT '{}',
                  status TEXT NOT NULL DEFAULT 'Pending',
                  attempts INTEGER NOT NULL DEFAULT 0,
                  last_error TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  synced_at TEXT
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_operations_status ON operations(status, created_at)")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def enqueue(self, *, method: str, url: str, body=None, metadata=None, operation_id: str | None = None) -> str:
        operation_id = operation_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            db.execute("""INSERT OR IGNORE INTO operations
                (operation_id, method, url, body, metadata, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'Pending', ?, ?)""",
                (operation_id, method.upper(), url, json.dumps(body, ensure_ascii=False) if body is not None else None,
                 json.dumps(metadata or {}, ensure_ascii=False), now, now))
        return operation_id

    def claim(self, limit: int = 20):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT operation_id FROM operations WHERE status IN ('Pending','Failed') ORDER BY created_at LIMIT ?", (limit,)).fetchall()
            ids = [row[0] for row in rows]
            if ids:
                db.executemany("UPDATE operations SET status='Syncing', attempts=attempts+1, updated_at=? WHERE operation_id=?", [(now, item) for item in ids])
            db.commit()
            return [dict(row) for row in db.execute(
                "SELECT operation_id, method, url, body, metadata, status, attempts FROM operations WHERE operation_id IN (%s) ORDER BY created_at" % ",".join("?" * len(ids)), ids
            ).fetchall()] if ids else []

    def mark_synced(self, operation_id: str):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            db.execute("UPDATE operations SET status='Synced', synced_at=?, updated_at=?, last_error=NULL WHERE operation_id=?", (now, now, operation_id))

    def mark_failed(self, operation_id: str, error: str):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            db.execute("UPDATE operations SET status='Failed', last_error=?, updated_at=? WHERE operation_id=?", (str(error)[:1000], now, operation_id))

    def counts(self):
        with self._connect() as db:
            return {status: db.execute("SELECT COUNT(*) FROM operations WHERE status=?", (status,)).fetchone()[0] for status in STATUSES}
