"""Backup management — local retention plus optional Google Drive mirroring."""
import gzip
import json
import os
import logging
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from database import get_db, C, init_indexes
from models import new_id
from utils.deps import require_admin
from utils.audit import log_action
from utils.security import verify_password
from utils.google_drive import GoogleDriveClient, GoogleDriveError, upload_backup

router = APIRouter(prefix="/api/admin/backups", tags=["backups"])
logger = logging.getLogger(__name__)

# ── directories & config paths ───────────────────────────────────────────────
_DEFAULT_DIR = Path(os.environ.get("BACKUP_DIR", "")).expanduser() \
               if os.environ.get("BACKUP_DIR") else None
BACKUP_DIR   = _DEFAULT_DIR or Path(__file__).resolve().parent.parent / "data" / "backups"
SETTINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "backup_settings.json"
DRIVE_STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "drive_backup_state.json"

DEFAULT_SETTINGS: dict = {
    "local_interval_hours": 2,
    "daily_midnight": True,
    "retention_count": 30,
    "drive_enabled": False,
    "drive_interval_hours": 4,
}

# ── module-level scheduler state ─────────────────────────────────────────────
_scheduler: Optional[BackgroundScheduler] = None
_last_auto_backup: Optional[str] = None
_last_auto_error: Optional[str] = None
_last_drive_upload: Optional[str] = None
_last_drive_error: Optional[str] = None


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_settings() -> dict:
    try:
        if SETTINGS_FILE.exists():
            settings = {**DEFAULT_SETTINGS, **json.loads(SETTINGS_FILE.read_text())}
            if os.environ.get("OFFLINE_MODE", "false").lower() in ("1", "true", "yes"):
                settings["drive_enabled"] = False
            return settings
    except Exception:
        pass
    settings = dict(DEFAULT_SETTINGS)
    if os.environ.get("OFFLINE_MODE", "false").lower() in ("1", "true", "yes"):
        settings["drive_enabled"] = False
    return settings


def _save_settings(settings: dict):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2))


def _load_drive_state() -> dict:
    try:
        if DRIVE_STATE_FILE.exists():
            value = json.loads(DRIVE_STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                return value
    except (OSError, ValueError):
        pass
    return {"uploads": {}}


def _save_drive_state(state: dict) -> None:
    DRIVE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = DRIVE_STATE_FILE.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(DRIVE_STATE_FILE)


def _drive_upload_record(name: str) -> Optional[dict]:
    record = _load_drive_state().get("uploads", {}).get(name)
    return record if isinstance(record, dict) else None


def _upload_backup_to_drive(filepath: Path) -> bool:
    """Mirror a local backup; local success is never undone by Drive failure."""
    global _last_drive_upload, _last_drive_error
    state = _load_drive_state()
    uploads = state.setdefault("uploads", {})
    try:
        result = upload_backup(filepath, DRIVE_STATE_FILE)
        state = _load_drive_state()
        state.setdefault("uploads", {})[filepath.name] = {
            "status": "uploaded",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "file_id": result.get("id"),
            "web_view_link": result.get("webViewLink"),
            "size": filepath.stat().st_size,
        }
        _save_drive_state(state)
        _last_drive_upload = datetime.now(timezone.utc).isoformat()
        _last_drive_error = None
        logger.info("Backup uploaded to Google Drive: %s", filepath.name)
        return True
    except Exception as exc:
        uploads[filepath.name] = {
            "status": "error",
            "last_attempt_at": datetime.now(timezone.utc).isoformat(),
            "error": str(exc)[:500],
            "size": filepath.stat().st_size if filepath.exists() else 0,
        }
        _save_drive_state(state)
        _last_drive_error = str(exc)[:500]
        logger.error("Google Drive upload failed for %s: %s", filepath.name, exc)
        return False


def _sync_pending_to_drive() -> dict[str, int]:
    cfg = _load_settings()
    if not cfg.get("drive_enabled"):
        return {"uploaded": 0, "failed": 0, "pending": 0}
    state = _load_drive_state()
    uploads = state.get("uploads", {})
    uploaded = failed = pending = 0
    for filepath in reversed(_list_backups()):
        record = uploads.get(filepath.name, {})
        if record.get("status") == "uploaded":
            continue
        pending += 1
        if _upload_backup_to_drive(filepath):
            uploaded += 1
        else:
            failed += 1
    return {"uploaded": uploaded, "failed": failed, "pending": pending}


def _human(n: float) -> str:
    s = float(n)
    for u in ["B", "KB", "MB", "GB"]:
        if s < 1024:
            return f"{s:.1f} {u}"
        s /= 1024
    return f"{s:.1f} TB"


def _valid_name(filename: str) -> bool:
    return (
        "/" not in filename
        and ".." not in filename
        and filename.startswith("market_db_")
        and (filename.endswith(".json.gz") or filename.endswith(".sql.gz") or filename.endswith(".archive.gz"))
    )


def _list_backups():
    BACKUP_DIR.mkdir(exist_ok=True, parents=True)
    files = (
        list(BACKUP_DIR.glob("market_db_*.json.gz"))
        + list(BACKUP_DIR.glob("market_db_*.sql.gz"))
        + list(BACKUP_DIR.glob("market_db_*.archive.gz"))
    )
    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)


def _infer_trigger(name: str) -> str:
    if "_auto." in name:  return "auto"
    if "_daily." in name: return "daily"
    if "_safety." in name: return "safety"
    return "manual"


# ── collections to export ─────────────────────────────────────────────────────
_COLLECTIONS = [
    C.users, C.settings, C.categories, C.products, C.barcodes, C.product_batches,
    C.customers, C.suppliers,
    C.customer_accounts, C.supplier_accounts,
    C.customer_payments, C.supplier_payments,
    C.sales, C.sale_items, C.sale_payments, C.sale_returns, C.sale_return_items,
    C.purchases, C.purchase_items,
    C.supplier_returns, C.supplier_return_items,
    C.inventory_movements, C.stock_audits, C.stock_audit_items,
    C.expenses, C.expense_categories,
    C.shifts, C.notifications, C.audit_logs,
    C.devices, C.sync_queue,
    C.product_change_requests, C.day_closes,
]


def _json_default(obj):
    if isinstance(obj, datetime):
        return {"__market_type__": "datetime", "value": obj.isoformat()}
    try:
        from datetime import date
        from decimal import Decimal
        if isinstance(obj, date):
            return {"__market_type__": "date", "value": obj.isoformat()}
        if isinstance(obj, Decimal):
            return {"__market_type__": "decimal", "value": str(obj)}
    except ImportError:
        pass
    return str(obj)


_LEGACY_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def _restore_value(value):
    """Restore tagged values from new backups and timestamps from v1.1 backups."""
    if isinstance(value, dict):
        value_type = value.get("__market_type__")
        if value_type == "datetime":
            try:
                return datetime.fromisoformat(value["value"].replace("Z", "+00:00"))
            except (KeyError, TypeError, ValueError):
                return value.get("value")
        if value_type == "date":
            # MongoDB stores dates as BSON datetimes; midnight UTC preserves the date.
            try:
                return datetime.fromisoformat(value["value"]).replace(tzinfo=timezone.utc)
            except (KeyError, TypeError, ValueError):
                return value.get("value")
        if value_type == "decimal":
            try:
                return float(value["value"])
            except (KeyError, TypeError, ValueError):
                return value.get("value")
        return {key: _restore_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_restore_value(item) for item in value]
    # Backward compatibility with existing format_version 1.1 backups.
    if isinstance(value, str) and _LEGACY_DATETIME.match(value):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return value


def _backup_collection_names(db):
    """Return all known app collections plus any collections created by newer code."""
    return sorted(set(_COLLECTIONS) | set(db.list_collection_names()))


def _do_backup(db, trigger: str = "manual") -> Path:
    """Export every application collection to a gzipped JSON file."""
    global _last_auto_backup, _last_auto_error
    BACKUP_DIR.mkdir(exist_ok=True, parents=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filepath = BACKUP_DIR / f"market_db_{ts}_{trigger}.json.gz"

    data: dict = {}
    for col_name in _backup_collection_names(db):
        rows = list(db[col_name].find())
        data[col_name] = [{k: v for k, v in r.items()} for r in rows]

    meta = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "trigger": trigger,
        "collections": len(data),
        "total_documents": sum(len(v) for v in data.values()),
        "format_version": "1.2",
        "date_encoding": "tagged",
    }
    with gzip.open(str(filepath), "wt", encoding="utf-8") as fh:
        json.dump({"meta": meta, "data": data}, fh,
                  ensure_ascii=False, default=_json_default, indent=None)

    # Enforce retention
    cfg   = _load_settings()
    keep  = int(cfg.get("retention_count", 30))
    for old in _list_backups()[keep:]:
        try: old.unlink()
        except Exception: pass

    if cfg.get("drive_enabled"):
        _upload_backup_to_drive(filepath)

    if trigger not in ("manual", "safety"):
        _last_auto_backup = datetime.now(timezone.utc).isoformat()
        _last_auto_error  = None

    logger.info("Backup created: %s (%.1f KB)", filepath.name,
                filepath.stat().st_size / 1024)
    return filepath


def _restore_collections(db, col_data: dict) -> tuple[int, int, list[str]]:
    """Replace all app collections from a backup and rebuild indexes.

    Returns (collections restored, documents restored, failed collection names).
    """
    if not isinstance(col_data, dict):
        raise ValueError("النسخة لا تحتوي على بيانات مجموعات صحيحة")

    collection_names = set(_COLLECTIONS) | set(col_data.keys())
    restored_collections = 0
    restored_documents = 0
    failures = []

    for col_name in sorted(collection_names):
        if not isinstance(col_name, str) or not col_name or col_name.startswith("$"):
            failures.append(str(col_name))
            continue
        rows = col_data.get(col_name, [])
        if not isinstance(rows, list):
            failures.append(col_name)
            continue
        try:
            db[col_name].drop()
            restored_rows = [_restore_value(row) for row in rows]
            if restored_rows:
                db[col_name].insert_many(restored_rows, ordered=True)
            restored_collections += 1
            restored_documents += len(restored_rows)
        except Exception:
            logger.exception("Failed restoring collection %s", col_name)
            failures.append(col_name)

    try:
        init_indexes()
    except Exception:
        logger.exception("Failed rebuilding database indexes after restore")
        failures.append("_indexes")

    return restored_collections, restored_documents, failures


def _restore_backup_file(
    filename: str,
    filepath: Path,
    payload: "RestorePayload",
    request: Request,
    db,
    current,
    source: str = "local",
):
    """Restore one validated archive while keeping the safety checks in one place."""
    if not _valid_name(filename):
        raise HTTPException(400, "اسم ملف النسخة غير صحيح")
    if payload.confirm != "RESTORE_DATABASE":
        raise HTTPException(400, "عبارة التأكيد غير صحيحة")
    if not verify_password(payload.current_password, current["password_hash"]):
        raise HTTPException(401, "كلمة المرور غير صحيحة")
    if not filename.endswith(".json.gz"):
        raise HTTPException(400, "الاستعادة متاحة فقط لملفات .json.gz")
    if not filepath.exists():
        raise HTTPException(404, "ملف النسخة غير موجود")

    safety_name = "FAILED"
    try:
        safety_name = _do_backup(db, trigger="safety").name
    except Exception:
        pass

    try:
        with gzip.open(str(filepath), "rt", encoding="utf-8") as fh:
            backup = json.load(fh)
    except Exception as exc:
        raise HTTPException(400, f"تعذّر قراءة ملف النسخة الاحتياطية: {exc}")

    col_data = backup.get("data", {})
    try:
        restored, documents_restored, failures = _restore_collections(db, col_data)
    except Exception as exc:
        raise HTTPException(400, f"بيانات النسخة غير صالحة: {exc}")
    if failures:
        raise HTTPException(
            500,
            "تعذّرت استعادة بعض مجموعات البيانات: " + ", ".join(failures)
            + f". تم إنشاء نسخة الأمان: {safety_name}",
        )

    log_action(
        db,
        current["_id"],
        "restore_success",
        "system",
        None,
        after={
            "file": filename,
            "source": source,
            "safety_backup": safety_name,
            "collections_restored": restored,
            "documents_restored": documents_restored,
        },
        request=request,
    )
    return {
        "detail": "✅ تمت استعادة جميع بيانات النظام بنجاح — يرجى تسجيل الدخول من جديد",
        "restored_from": filename,
        "source": source,
        "collections_restored": restored,
        "documents_restored": documents_restored,
        "safety_backup_created": safety_name,
    }


def _auto_backup_job(trigger: str = "auto"):
    """Scheduled job — gets its own DB reference."""
    global _last_auto_error
    try:
        from database import db as _db
        _do_backup(_db, trigger=trigger)
    except Exception as exc:
        _last_auto_error = str(exc)
        logger.error("Auto backup (%s) failed: %s", trigger, exc)


def _drive_sync_job():
    try:
        _sync_pending_to_drive()
    except Exception as exc:
        logger.error("Google Drive sync failed: %s", exc)


# ── Scheduler lifecycle (called from server.py) ───────────────────────────────

def _next_run(job_id: str) -> Optional[str]:
    if _scheduler is None:
        return None
    job = _scheduler.get_job(job_id)
    if job is None or job.next_run_time is None:
        return None
    return job.next_run_time.isoformat()


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    cfg = _load_settings()
    _scheduler = BackgroundScheduler(timezone="UTC")
    _add_jobs(cfg)
    _scheduler.start()
    logger.info("Backup scheduler started — interval=%sh midnight=%s",
                cfg.get("local_interval_hours", 2), cfg.get("daily_midnight", True))


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Backup scheduler stopped")


def _add_jobs(cfg: dict):
    assert _scheduler is not None
    interval_h = int(cfg.get("local_interval_hours", 2))
    _scheduler.add_job(
        _auto_backup_job,
        trigger=IntervalTrigger(hours=interval_h),
        id="local_interval",
        kwargs={"trigger": "auto"},
        replace_existing=True,
        misfire_grace_time=300,
    )
    if cfg.get("daily_midnight", True):
        _scheduler.add_job(
            _auto_backup_job,
            trigger=CronTrigger(hour=0, minute=0, timezone="UTC"),
            id="daily_midnight",
            kwargs={"trigger": "daily"},
            replace_existing=True,
            misfire_grace_time=600,
        )
    if cfg.get("drive_enabled"):
        _scheduler.add_job(
            _drive_sync_job,
            trigger=IntervalTrigger(hours=int(cfg.get("drive_interval_hours", 4))),
            id="drive_sync",
            replace_existing=True,
            misfire_grace_time=600,
        )


def _reschedule(cfg: dict):
    if _scheduler is None or not _scheduler.running:
        return
    interval_h = int(cfg.get("local_interval_hours", 2))
    _scheduler.reschedule_job("local_interval",
                               trigger=IntervalTrigger(hours=interval_h))
    if cfg.get("daily_midnight", True):
        try:
            _scheduler.reschedule_job(
                "daily_midnight",
                trigger=CronTrigger(hour=0, minute=0, timezone="UTC"))
        except Exception:
            _scheduler.add_job(
                _auto_backup_job,
                trigger=CronTrigger(hour=0, minute=0, timezone="UTC"),
                id="daily_midnight",
                kwargs={"trigger": "daily"},
                replace_existing=True,
                misfire_grace_time=600,
            )
    else:
        try: _scheduler.remove_job("daily_midnight")
        except Exception: pass
    if cfg.get("drive_enabled"):
        try:
            _scheduler.reschedule_job(
                "drive_sync",
                trigger=IntervalTrigger(hours=int(cfg.get("drive_interval_hours", 4))),
            )
        except Exception:
            _scheduler.add_job(
                _drive_sync_job,
                trigger=IntervalTrigger(hours=int(cfg.get("drive_interval_hours", 4))),
                id="drive_sync",
                replace_existing=True,
                misfire_grace_time=600,
            )
    else:
        try: _scheduler.remove_job("drive_sync")
        except Exception: pass


# ── Settings endpoints ────────────────────────────────────────────────────────

@router.get("/settings")
def get_settings(_u=Depends(require_admin)):
    return _load_settings()


class BackupSettingsIn(BaseModel):
    local_interval_hours: int = Field(2, ge=1, le=24)
    daily_midnight: bool = True
    retention_count: int = Field(30, ge=5, le=100)
    drive_enabled: bool = False
    drive_interval_hours: int = Field(4, ge=1, le=24)


@router.put("/settings")
def update_settings(payload: BackupSettingsIn, _u=Depends(require_admin)):
    cfg = payload.model_dump()
    _save_settings(cfg)
    try: _reschedule(cfg)
    except Exception as e: logger.warning("Reschedule failed: %s", e)
    if cfg.get("drive_enabled"):
        _sync_pending_to_drive()
    return cfg


# ── Status / List ─────────────────────────────────────────────────────────────

@router.get("/status")
def get_status(_u=Depends(require_admin)):
    files = _list_backups()
    cfg   = _load_settings()
    drive_state = _load_drive_state()
    drive_uploads = drive_state.get("uploads", {})
    uploaded_count = sum(
        1 for record in drive_uploads.values()
        if isinstance(record, dict) and record.get("status") == "uploaded"
    )
    sched = _scheduler is not None and _scheduler.running
    base  = {
        "scheduler_running": sched,
        "next_backup_local": _next_run("local_interval"),
        "next_backup_daily": _next_run("daily_midnight"),
        "last_auto_backup": _last_auto_backup,
        "last_auto_error": _last_auto_error,
        "schedule": f"كل {cfg.get('local_interval_hours', 2)} ساعة تلقائياً",
        "retention_count": cfg.get("retention_count", 30),
        "drive_enabled": cfg.get("drive_enabled", False),
        "drive_folder_name": drive_state.get("folder_name", "Mini Market Backups"),
        "drive_uploaded_count": uploaded_count,
        "last_drive_upload": _last_drive_upload,
        "last_drive_error": _last_drive_error,
    }
    if not files:
        return {**base, "count": 0, "total_size": 0, "total_size_human": "0 B", "latest": None}
    latest = files[0]
    mtime  = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc)
    return {
        **base,
        "count": len(files),
        "total_size": sum(f.stat().st_size for f in files),
        "total_size_human": _human(sum(f.stat().st_size for f in files)),
        "latest": {
            "name": latest.name,
            "created_at": mtime.isoformat(),
            "age_seconds": int((datetime.now(timezone.utc) - mtime).total_seconds()),
        },
    }


@router.get("")
def list_backups(_u=Depends(require_admin)):
    cfg = _load_settings()
    drive_uploads = _load_drive_state().get("uploads", {})
    return [
        {
            "name": f.name,
            "size": f.stat().st_size,
            "size_human": _human(f.stat().st_size),
            "created_at": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            "trigger": _infer_trigger(f.name),
            "drive_status": (
                drive_uploads.get(f.name, {}).get("status")
                if isinstance(drive_uploads.get(f.name), dict)
                else None
            ) or ("pending" if cfg.get("drive_enabled") else "disabled"),
        }
        for f in _list_backups()
    ]


# ── Run / Download / Delete / Restore ────────────────────────────────────────

@router.post("/run")
def run_now(request: Request, db=Depends(get_db), current=Depends(require_admin)):
    try:
        fp  = _do_backup(db, trigger="manual")
        sh  = _human(fp.stat().st_size)
        log_action(db, current["_id"], "backup_run", "system", None,
                   after={"file": fp.name, "size": sh}, request=request)
        drive_record = _drive_upload_record(fp.name)
        return {
            "detail": f"✅ النسخة الاحتياطية تمت بنجاح — {sh}",
            "file": fp.name,
            "size": sh,
            "drive_status": drive_record.get("status") if drive_record else "disabled",
        }
    except Exception as exc:
        log_action(db, current["_id"], "backup_failed", "system", None,
                   after={"error": str(exc)[:400]}, request=request)
        raise HTTPException(500, f"فشل إنشاء النسخة الاحتياطية: {exc}")


@router.post("/drive/sync")
def sync_drive(_u=Depends(require_admin)):
    if not _load_settings().get("drive_enabled"):
        raise HTTPException(409, "رفع Google Drive غير مفعّل")
    return _sync_pending_to_drive()


@router.get("/drive")
def list_drive_backups(_u=Depends(require_admin)):
    try:
        state = _load_drive_state()
        files = GoogleDriveClient().list_backup_files(state.get("folder_id"))
        return [
            {
                "id": file.get("id"),
                "name": file.get("name"),
                "size": int(file.get("size") or 0),
                "size_human": _human(int(file.get("size") or 0)),
                "modified_time": file.get("modifiedTime"),
                "web_view_link": file.get("webViewLink"),
            }
            for file in files
        ]
    except GoogleDriveError as exc:
        raise HTTPException(502, str(exc))
    except Exception as exc:
        logger.exception("Google Drive listing failed")
        raise HTTPException(502, f"تعذر تحميل نسخ Google Drive: {str(exc)[:300]}")


@router.post("/drive/restore/{file_id}")
def restore_from_drive(
    file_id: str,
    payload: "RestorePayload",
    request: Request,
    db=Depends(get_db),
    current=Depends(require_admin),
):
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,200}", file_id):
        raise HTTPException(400, "معرّف نسخة Google Drive غير صحيح")
    try:
        state = _load_drive_state()
        client = GoogleDriveClient()
        files = client.list_backup_files(state.get("folder_id"))
        selected = next((file for file in files if file.get("id") == file_id), None)
        if not selected:
            raise HTTPException(404, "النسخة غير موجودة في مجلد النسخ")
        filename = selected.get("name", "")
        if not _valid_name(filename):
            raise HTTPException(400, "اسم ملف النسخة غير مدعوم")
        content = client.download_file(file_id)
        if len(content) > 100 * 1024 * 1024:
            raise HTTPException(413, "حجم النسخة أكبر من الحد المسموح")
        BACKUP_DIR.mkdir(exist_ok=True, parents=True)
        with tempfile.NamedTemporaryFile(
            dir=BACKUP_DIR,
            prefix=f".{filename}.",
            suffix=".download",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        local_path = BACKUP_DIR / filename
        temporary_path.replace(local_path)
        return _restore_backup_file(
            filename,
            local_path,
            payload,
            request,
            db,
            current,
            source="google_drive",
        )
    except HTTPException:
        raise
    except GoogleDriveError as exc:
        raise HTTPException(502, str(exc))
    except Exception as exc:
        logger.exception("Google Drive restore failed")
        raise HTTPException(502, f"تعذر استعادة النسخة من Google Drive: {str(exc)[:300]}")


@router.get("/download/{filename}")
def download(filename: str, _u=Depends(require_admin)):
    if not _valid_name(filename):
        raise HTTPException(400, "اسم ملف غير صحيح")
    fp = BACKUP_DIR / filename
    if not fp.exists():
        raise HTTPException(404, "الملف غير موجود")
    return FileResponse(str(fp), media_type="application/gzip", filename=filename)


@router.delete("/{filename}", status_code=204)
def delete_backup(filename: str, request: Request,
                  db=Depends(get_db), current=Depends(require_admin)):
    if not _valid_name(filename):
        raise HTTPException(400, "اسم ملف غير صحيح")
    fp = BACKUP_DIR / filename
    if not fp.exists():
        raise HTTPException(404, "الملف غير موجود")
    size = fp.stat().st_size
    fp.unlink()
    log_action(db, current["_id"], "backup_deleted", "system", None,
               before={"name": filename, "size": size}, request=request)
    return None


class RestorePayload(BaseModel):
    confirm: str          = Field(..., description="must equal 'RESTORE_DATABASE'")
    current_password: str = Field(..., min_length=1)


@router.post("/restore/{filename}")
def restore(filename: str, payload: RestorePayload,
            request: Request, db=Depends(get_db), current=Depends(require_admin)):
    fp = BACKUP_DIR / filename
    return _restore_backup_file(filename, fp, payload, request, db, current)
