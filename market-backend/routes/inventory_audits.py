"""Inventory audit snapshots. Audits never change product stock."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pymongo.errors import DuplicateKeyError
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import List, Optional

from database import get_db, C
from models import new_id
from utils.deps import get_current_user, require_manager
from utils.audit import log_action
from inventory_audit_report import build_inventory_snapshot, render_inventory_pdf

router = APIRouter(prefix="/api/admin/inventory-audits", tags=["inventory-audits"])

class AuditLine(BaseModel):
    product_id: str
    actual_quantity: float = Field(..., ge=0)

class AuditCreate(BaseModel):
    branch: str = Field(default="ميني ماركت الفنية", max_length=160)
    notes: Optional[str] = Field(default="", max_length=2000)
    items: List[AuditLine] = Field(default_factory=list)


def _next_no(db):
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    count = db[C.stock_audits].count_documents({"audit_no": {"$regex": f"^AUD-{day}-"}})
    return f"AUD-{day}-{count + 1:05d}"


def _out(a):
    return {"id": a["_id"], "audit_no": a["audit_no"], "created_at": a["created_at"], "branch": a.get("branch"), "actor_name": a.get("actor_name"), "notes": a.get("notes", ""), "items": a.get("items", []), "total_items": len(a.get("items", [])), "total_actual": sum(float(x.get("actual_quantity", 0)) for x in a.get("items", [])), "total_system": sum(float(x.get("system_quantity", 0)) for x in a.get("items", []))}

@router.get("")
def list_audits(db=Depends(get_db), _u=Depends(require_manager)):
    return [_out(a) for a in db[C.stock_audits].find({}).sort("created_at", -1).limit(100)]

@router.get("/current")
def current_audit(db=Depends(get_db), current=Depends(require_manager)):
    snap = build_inventory_snapshot(db, audit_no=_next_no(db), actor_name=current.get("full_name") or current.get("username") or "—")
    return snap

@router.post("", status_code=201)
def create_audit(payload: AuditCreate, request: Request, db=Depends(get_db), current=Depends(require_manager), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    key = (idempotency_key or new_id()).strip()
    if len(key) > 200: raise HTTPException(400, "Invalid Idempotency-Key")
    reservation = {"user_id": current["_id"], "key": key}
    try:
        db[C.idempotency_keys].insert_one({"_id": new_id(), **reservation, "operation": "inventory_audit", "status": "processing", "created_at": datetime.now(timezone.utc)})
    except DuplicateKeyError:
        prior = db[C.idempotency_keys].find_one(reservation)
        if prior and prior.get("audit_id"):
            existing = db[C.stock_audits].find_one({"_id": prior["audit_id"]})
            if existing: return _out(existing)
        raise HTTPException(409, "عملية الجرد نفسها قيد التنفيذ، أعد المحاولة لاحقاً")
    now = datetime.now(timezone.utc)
    audit_no = _next_no(db)
    actual_by_product = {line.product_id: line.actual_quantity for line in payload.items}
    snap = build_inventory_snapshot(db, audit_no=audit_no, actor_name=current.get("full_name") or current.get("username") or "—", branch=payload.branch, actual_by_product=actual_by_product, created_at=now)
    items = snap.pop("rows")
    doc = {"_id": new_id(), "audit_no": audit_no, "created_at": now, "branch": payload.branch, "actor_id": current["_id"], "actor_name": current.get("full_name") or current.get("username") or "—", "notes": payload.notes or "", "items": items}
    db[C.stock_audits].insert_one(doc)
    db[C.idempotency_keys].update_one(reservation, {"$set": {"audit_id": doc["_id"], "status": "completed"}})
    for item in items:
        db[C.stock_audit_items].insert_one({"_id": new_id(), "audit_id": doc["_id"], **item})
    log_action(db, current["_id"], "inventory_audit_created", "stock_audits", doc["_id"], after={"audit_no": audit_no, "items": len(items)}, request=request)
    return _out(doc)

@router.get("/{audit_id}")
def get_audit(audit_id: str, db=Depends(get_db), _u=Depends(require_manager)):
    audit = db[C.stock_audits].find_one({"_id": audit_id})
    if not audit: raise HTTPException(404, "الجرد غير موجود")
    return _out(audit)

@router.get("/current/pdf")
def current_audit_pdf(db=Depends(get_db), current=Depends(require_manager)):
    snap = build_inventory_snapshot(db, audit_no=_next_no(db), actor_name=current.get("full_name") or current.get("username") or "—")
    return Response(render_inventory_pdf(snap), media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="inventory-audit-current.pdf"'})

@router.get("/{audit_id}/pdf")
def audit_pdf(audit_id: str, db=Depends(get_db), _u=Depends(require_manager)):
    audit = db[C.stock_audits].find_one({"_id": audit_id})
    if not audit: raise HTTPException(404, "الجرد غير موجود")
    snap = {"audit_no": audit["audit_no"], "created_at": audit["created_at"], "branch": audit.get("branch", "—"), "actor_name": audit.get("actor_name", "—"), "notes": audit.get("notes", ""), "rows": audit.get("items", []), "total_items": len(audit.get("items", [])), "total_actual": sum(float(x.get("actual_quantity", 0)) for x in audit.get("items", [])), "total_system": sum(float(x.get("system_quantity", 0)) for x in audit.get("items", []))}
    return Response(render_inventory_pdf(snap), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="inventory-audit-{audit["audit_no"]}.pdf"'})
