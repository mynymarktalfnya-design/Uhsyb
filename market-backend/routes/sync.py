"""Offline-first synchronization between the local Windows store and Neon."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from database import C, get_db
from models import new_id
from utils.deps import get_current_user, require_admin

router = APIRouter(prefix="/api/sync", tags=["sync"])
logger = logging.getLogger(__name__)
_SYNC_STOP = threading.Event()
_SYNC_THREAD: threading.Thread | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _state_path() -> Path:
    return Path(os.environ.get(
        "SYNC_STATE_FILE",
        str(Path(__file__).resolve().parent.parent / "data" / "sync_state.json"),
    )).expanduser()


def _load_state() -> dict[str, Any]:
    try:
        value = json.loads(_state_path().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(value: dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _json_default(value: Any):
    if isinstance(value, datetime):
        return {"__market_type__": "datetime", "value": value.isoformat()}
    return str(value)


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, default=_json_default, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _decode(value):
    if isinstance(value, dict):
        if value.get("__market_type__") == "datetime":
            try:
                return datetime.fromisoformat(value["value"].replace("Z", "+00:00"))
            except (KeyError, TypeError, ValueError):
                return value.get("value")
        return {key: _decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode(item) for item in value]
    return value


def _timestamp(document: dict) -> datetime | None:
    for key in ("updated_at", "last_login_at", "created_at"):
        value = document.get(key)
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                continue
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


def _export_database(db) -> bytes:
    collections = sorted(set(vars(C).values()) - {"__dict__", "__module__", "__weakref__"})
    data: dict[str, list[dict]] = {}
    for name in collections:
        if not isinstance(name, str) or name.startswith("_"):
            continue
        try:
            data[name] = list(db[name].find({}))
        except Exception:
            continue
    payload = {
        "meta": {"created_at": _now().isoformat(), "trigger": "windows_sync", "format_version": "1.0"},
        "data": data,
    }
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb") as archive:
        archive.write(json.dumps(payload, ensure_ascii=False, default=_json_default).encode("utf-8"))
    return output.getvalue()


def _record_conflict(db, collection: str, document: dict, existing: dict) -> bool:
    local_document = _decode(document)
    remote_document = _decode(existing)
    fingerprint = _fingerprint({
        "collection": collection,
        "id": document.get("_id"),
        "local": local_document,
        "remote": remote_document,
    })
    conflicts = db[C.sync_conflicts]
    if conflicts.find_one({"fingerprint": fingerprint, "status": "pending"}):
        return False
    incoming_time = _timestamp(local_document)
    existing_time = _timestamp(remote_document)
    preferred = "local" if not existing_time or (incoming_time and incoming_time >= existing_time) else "remote"
    conflicts.insert_one({
        "_id": new_id(), "fingerprint": fingerprint, "collection": collection,
        "document_id": document.get("_id"), "local_document": local_document,
        "remote_document": remote_document, "suggested_resolution": preferred,
        "status": "pending", "created_at": _now(),
    })
    return True


def _merge_database(db, data: dict) -> tuple[int, int, int, int]:
    """Insert new local documents and log differing IDs for manual review."""
    inserted = updated = skipped = conflicts = 0
    for collection, rows in data.items():
        if not isinstance(collection, str) or not isinstance(rows, list):
            continue
        for raw in rows:
            document = _decode(raw)
            if not isinstance(document, dict):
                continue
            document.setdefault("_id", new_id())
            existing = db[collection].find_one({"_id": document["_id"]})
            if existing:
                if _fingerprint(document) == _fingerprint(existing):
                    continue
                if _record_conflict(db, collection, document, existing):
                    conflicts += 1
                skipped += 1
            else:
                db[collection].insert_one(document)
                inserted += 1
    return inserted, updated, skipped, conflicts


@router.get("/status")
def sync_status(db=Depends(get_db), _u=Depends(get_current_user)):
    pending = db[C.sync_queue].count_documents({"status": "pending"})
    conflict_count = db[C.sync_conflicts].count_documents({"status": "pending"})
    state = _load_state()
    return {
        "pending": pending, "conflicts": conflict_count, "server_time": _now().isoformat(),
        "remote_configured": bool(os.environ.get("SYNC_REMOTE_URL")),
        "last_sync_at": state.get("last_sync_at"), "last_sync_error": state.get("last_sync_error"),
        "last_sync_inserted": state.get("last_sync_inserted", 0),
        "last_sync_updated": state.get("last_sync_updated", 0),
    }


@router.post("/queue")
def enqueue(payload: dict, db=Depends(get_db), current=Depends(get_current_user)):
    qid = new_id()
    db[C.sync_queue].insert_one({
        "_id": qid, "user_id": current["_id"], "payload": payload,
        "status": "pending", "created_at": _now(),
    })
    return {"id": qid, "status": "queued"}


@router.post("/import")
def import_local_backup(file: UploadFile = File(...), db=Depends(get_db), _u=Depends(require_admin)):
    """Merge a local Windows export into Neon; remote-only records are retained."""
    if file.content_type not in ("application/gzip", "application/octet-stream", "application/x-gzip"):
        raise HTTPException(400, "صيغة النسخة يجب أن تكون gzip")
    content = file.file.read(100 * 1024 * 1024 + 1)
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(413, "حجم النسخة أكبر من الحد المسموح")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(content), mode="rb") as archive:
            payload = json.loads(archive.read().decode("utf-8"))
        inserted, updated, skipped, conflicts = _merge_database(db, payload.get("data", {}))
        return {"status": "merged", "inserted": inserted, "updated": updated, "skipped": skipped, "conflicts": conflicts}
    except Exception as exc:
        logger.exception("Local database merge failed")
        raise HTTPException(400, f"تعذر دمج النسخة المحلية: {str(exc)[:300]}")


@router.get("/conflicts")
def list_conflicts(status: str = "pending", db=Depends(get_db), _u=Depends(require_admin)):
    query = {} if status == "all" else {"status": status}
    return list(db[C.sync_conflicts].find(query).sort("created_at", -1).limit(200))


@router.post("/conflicts/{conflict_id}/resolve")
def resolve_conflict(conflict_id: str, payload: dict, db=Depends(get_db), current=Depends(require_admin)):
    resolution = payload.get("resolution")
    if resolution not in ("local", "remote"):
        raise HTTPException(400, "القرار يجب أن يكون local أو remote")
    conflict = db[C.sync_conflicts].find_one({"_id": conflict_id, "status": "pending"})
    if not conflict:
        raise HTTPException(404, "التعارض غير موجود أو تمت معالجته مسبقاً")
    if resolution == "local":
        document = _decode(conflict.get("local_document", {}))
        db[conflict["collection"]].replace_one({"_id": conflict["document_id"]}, document, upsert=True)
    db[C.sync_conflicts].update_one({"_id": conflict_id}, {"$set": {
        "status": "resolved", "resolution": resolution, "resolved_by": current.get("_id"), "resolved_at": _now(),
    }})
    return {"status": "resolved", "resolution": resolution, "id": conflict_id}


def sync_once() -> dict[str, Any]:
    remote = os.environ.get("SYNC_REMOTE_URL", "").strip().rstrip("/")
    username = os.environ.get("SYNC_USERNAME", "").strip()
    password = os.environ.get("SYNC_PASSWORD", "")
    if not remote or not username or not password:
        return {"status": "not_configured"}
    from database import db
    state = _load_state()
    try:
        with requests.Session() as session:
            login = session.post(f"{remote}/api/auth/login", json={"email_or_username": username, "password": password}, timeout=20)
            login.raise_for_status()
            token = login.json().get("access_token")
            if not token:
                raise RuntimeError("لم يتم الحصول على رمز دخول للموقع")
            content = _export_database(db)
            response = session.post(
                f"{remote}/api/sync/import",
                files={"file": ("windows-sync.json.gz", content, "application/gzip")},
                headers={"Authorization": f"Bearer {token}"}, timeout=120,
            )
            response.raise_for_status()
            result = response.json()
        state.update({
            "last_sync_at": _now().isoformat(), "last_sync_error": None,
            "last_sync_inserted": result.get("inserted", 0), "last_sync_updated": result.get("updated", 0),
            "last_sync_conflicts": result.get("conflicts", 0),
        })
        _save_state(state)
        return {"status": "synced", **result}
    except Exception as exc:
        state["last_sync_error"] = str(exc)[:500]
        _save_state(state)
        logger.warning("Automatic Windows → Neon sync failed: %s", exc)
        return {"status": "failed", "error": str(exc)[:300]}


def _sync_loop() -> None:
    interval = max(60, int(os.environ.get("SYNC_INTERVAL_SECONDS", "120")))
    while not _SYNC_STOP.wait(interval):
        sync_once()


def start_sync_worker() -> None:
    global _SYNC_THREAD
    if _SYNC_THREAD and _SYNC_THREAD.is_alive():
        return
    if os.environ.get("SYNC_REMOTE_URL") and os.environ.get("SYNC_USERNAME") and os.environ.get("SYNC_PASSWORD"):
        _SYNC_STOP.clear()
        _SYNC_THREAD = threading.Thread(target=_sync_loop, name="neon-sync", daemon=True)
        _SYNC_THREAD.start()
        logger.info("Automatic Windows → Neon sync worker started")


def stop_sync_worker() -> None:
    _SYNC_STOP.set()


@router.post("/now")
def sync_now(_u=Depends(require_admin)):
    return sync_once()
