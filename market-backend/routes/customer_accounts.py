"""Customer accounts: statement, payments, and detail endpoints. MongoDB."""
from datetime import datetime, timezone, date as _date
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import List, Optional

from database import get_db, C
from models import new_id
from utils.deps import get_current_user, require_manager
from utils.audit import log_action
from utils.accounting import customer_account_totals
from utils.time import BUSINESS_TIMEZONE, day_range_utc

router = APIRouter(prefix="/api", tags=["customer-accounts"])


# ─── Helpers ────────────────────────────────────────────────────────────────

def _user_name(db, user_id: str) -> Optional[str]:
    if not user_id:
        return None
    u = db[C.users].find_one({"_id": user_id}, {"username": 1, "full_name": 1})
    if not u:
        return None
    return u.get("full_name") or u.get("username")


# ─── Customer statement ───────────────────────────────────────────────────────

@router.get("/customers/{customer_id}/statement")
def customer_statement(
    customer_id: str,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db=Depends(get_db),
    _u=Depends(get_current_user),
):
    c = db[C.customers].find_one({"_id": customer_id, "deleted_at": None})
    if not c:
        raise HTTPException(404, "Customer not found")

    def parse_boundary(value: Optional[str], end: bool = False):
        if not value:
            return None
        raw = value.replace("Z", "+00:00")
        if "T" not in raw:
            day = _date.fromisoformat(raw)
            return day_range_utc(day)[1 if end else 0]
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=BUSINESS_TIMEZONE)
        return parsed.astimezone(timezone.utc)

    # Date-only filters represent complete business days and use a half-open
    # interval, so entries at 23:59:59.500 are not accidentally omitted.
    dt_from = parse_boundary(date_from)
    dt_to = parse_boundary(date_to, end=True)

    def normalize_date(value):
        if not value:
            return value
        if value.tzinfo is None:
            value = value.replace(tzinfo=BUSINESS_TIMEZONE)
        return value.astimezone(timezone.utc)

    entries = []

    # Credit sales
    sale_filt = {
        "customer_id": customer_id,
        "payment_method": "credit",
        "status": "completed",
        "deleted_at": None,
    }
    credit_sales = list(db[C.sales].find(sale_filt).sort("created_at", 1))
    credit_sale_ids = [s["_id"] for s in credit_sales]
    for s in credit_sales:
        sale_items = []
        for item in db[C.sale_items].find({"sale_id": s["_id"]}):
            product = db[C.products].find_one(
                {"_id": item.get("product_id")}, {"name": 1, "unit": 1}
            )
            sale_items.append({
                "id": item["_id"],
                "product_name": product.get("name") if product else item.get("product_id"),
                "unit": item.get("sale_unit") or (product.get("unit") if product else "piece"),
                "quantity": float(item.get("quantity", 0) or 0),
                "unit_price": float(item.get("unit_price", 0) or 0),
                "total": float(item.get("total", 0) or 0),
            })
        entries.append({
            "type": "sale",
            "date": normalize_date(s.get("created_at")),
            "op_no": s.get("invoice_no") or s.get("sale_number") or s["_id"],
            "description": "فاتورة آجل",
            "debit": float(s.get("total", 0)),
            "credit": 0.0,
            "ref_id": s["_id"],
            "created_by_name": _user_name(db, s.get("cashier_id") or s.get("created_by", "")),
            "items": sale_items,
            "voided": s.get("status") == "voided",
        })

    # Customer payments
    pay_filt = {"customer_id": customer_id, "deleted_at": None}
    for p in db[C.customer_payments].find(pay_filt).sort("created_at", 1):
        entries.append({
            "type": "payment",
            "date": normalize_date(p.get("created_at")),
            "op_no": p.get("receipt_no") or p["_id"],
            "description": "سند قبض",
            "debit": 0.0,
            "credit": float(p.get("amount", 0)),
            "ref_id": p["_id"],
            "created_by_name": _user_name(db, p.get("received_by") or p.get("created_by", "")),
            "voided": False,
        })

    # Customer sale returns (مرتجعات معتمدة فقط — approved only)
    ret_filt = {
        "sale_id": {"$in": credit_sale_ids},
        "status": "approved",
        "deleted_at": None,
    }
    for r in db[C.sale_returns].find(ret_filt).sort("created_at", 1):
        entries.append({
            "type": "return",
            "date": normalize_date(r.get("created_at")),
            "op_no": r.get("return_no") or r["_id"],
            "description": "مرتجع معتمد",
            "debit": 0.0,
            "credit": float(r.get("total", 0)),
            "ref_id": r["_id"],
            "created_by_name": _user_name(db, r.get("created_by", "")),
            "voided": False,
        })

    entries.sort(key=lambda e: e["date"] or datetime.min.replace(tzinfo=timezone.utc))

    def in_period(entry):
        when = entry.get("date")
        if not when:
            return False
        if dt_from and when < dt_from:
            return False
        if dt_to and when >= dt_to:
            return False
        return True

    opening_balance = round(sum(
        e["debit"] - e["credit"]
        for e in entries
        if dt_from and e.get("date") and e["date"] < dt_from
    ), 2) if dt_from else 0.0
    period_entries = [e for e in entries if in_period(e)]
    balance = opening_balance
    for e in period_entries:
        balance = round(balance + e["debit"] - e["credit"], 2)
        e["balance"] = balance
    totals = customer_account_totals(db, customer_id)

    now = datetime.now(timezone.utc)
    return {
        "customer": {
            "id": c["_id"],
            "full_name": c.get("full_name"),
            "phone": c.get("phone"),
        },
        "opening_balance": opening_balance,
        "closing_balance": balance,
        "current_balance": totals["balance"],
        "period": {
            "from": date_from[:10] if date_from else None,
            "to": date_to[:10] if date_to else None,
        },
        "generated_at": now,
        "entries": period_entries,
        "payment_count": totals["payment_count"],
    }


# ─── Customer payments list ───────────────────────────────────────────────────

@router.get("/customers/{customer_id}/payments")
def list_customer_payments(customer_id: str, db=Depends(get_db), _u=Depends(get_current_user)):
    rows = list(db[C.customer_payments].find({"customer_id": customer_id}).sort("created_at", -1).limit(200))
    out = []
    for p in rows:
        out.append({
            "id": p["_id"],
            "receipt_no": p.get("receipt_no") or p["_id"],
            "amount": p.get("amount", 0),
            "payment_method": p.get("payment_method") or p.get("method", "cash"),
            "notes": p.get("notes"),
            "created_by_name": _user_name(db, p.get("received_by") or p.get("created_by", "")),
            "created_at": p.get("created_at"),
            "customer_id": p.get("customer_id"),
        })
    return out


# ─── Record customer payment ──────────────────────────────────────────────────

class CustomerPaymentIn(BaseModel):
    amount: float = Field(..., gt=0)
    payment_method: str = Field(default="cash")
    notes: Optional[str] = None


@router.post("/customers/{customer_id}/payments", status_code=201)
def record_payment(customer_id: str, payload: CustomerPaymentIn, request: Request,
                   db=Depends(get_db), current=Depends(require_manager)):
    c = db[C.customers].find_one({"_id": customer_id, "deleted_at": None})
    if not c:
        raise HTTPException(404, "Customer not found")
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y%m%d")
    count = db[C.customer_payments].count_documents({"receipt_no": {"$regex": f"^RCP-{today}-"}})
    receipt_no = f"RCP-{today}-{count + 1:05d}"
    pid = new_id()
    db[C.customer_payments].insert_one({
        "_id": pid, "customer_id": customer_id,
        "amount": float(payload.amount),
        "method": payload.payment_method,
        "payment_method": payload.payment_method,
        "receipt_no": receipt_no,
        "notes": payload.notes,
        "received_by": current["_id"],
        "created_by": current["_id"],
        "created_at": now,
    })
    db[C.customers].update_one({"_id": customer_id},
                               {"$set": {
                                   "balance": customer_account_totals(db, customer_id)["balance"],
                                   "updated_at": now,
                               }})
    log_action(db, current["_id"], "customer_payment_received", "customer_payments", pid,
               after={"amount": str(payload.amount), "receipt_no": receipt_no}, request=request)
    return {
        "id": pid, "receipt_no": receipt_no,
        "customer_id": customer_id,
        "customer_name": c.get("full_name"),
        "amount": payload.amount,
        "payment_method": payload.payment_method,
        "notes": payload.notes,
        "created_by_name": _user_name(db, current["_id"]),
        "created_at": now,
    }


# ─── Customer sale detail ─────────────────────────────────────────────────────

@router.get("/customers/{customer_id}/sales/{sale_id}/detail")
def customer_sale_detail(customer_id: str, sale_id: str,
                         db=Depends(get_db), _u=Depends(get_current_user)):
    s = db[C.sales].find_one({"_id": sale_id, "customer_id": customer_id})
    if not s:
        raise HTTPException(404, "Sale not found")
    items_raw = list(db[C.sale_items].find({"sale_id": sale_id}))
    items_out = []
    for it in items_raw:
        prod = db[C.products].find_one({"_id": it.get("product_id")}, {"name": 1})
        items_out.append({
            "product_name": prod["name"] if prod else it.get("product_id", ""),
            "quantity": it.get("quantity", 0),
            "unit_price": it.get("unit_price", 0),
            "total": it.get("total", 0),
        })
    cashier = db[C.users].find_one({"_id": s.get("cashier_id")}, {"username": 1, "full_name": 1})
    return {
        "id": s["_id"],
        "invoice_no": s.get("invoice_no") or s.get("sale_number"),
        "cashier_name": (cashier.get("full_name") or cashier.get("username")) if cashier else None,
        "payment_method": s.get("payment_method"),
        "status": s.get("status", "completed"),
        "total": s.get("total", 0),
        "created_at": s.get("created_at"),
        "items": items_out,
    }


# ─── Single customer payment detail ──────────────────────────────────────────

@router.get("/customer-payments/{payment_id}")
def get_customer_payment(payment_id: str, db=Depends(get_db), _u=Depends(get_current_user)):
    p = db[C.customer_payments].find_one({"_id": payment_id})
    if not p:
        raise HTTPException(404, "Payment not found")
    customer = db[C.customers].find_one({"_id": p.get("customer_id")}, {"full_name": 1, "phone": 1})
    return {
        "id": p["_id"],
        "customer_id": p.get("customer_id"),
        "customer_name": customer.get("full_name") if customer else None,
        "customer_phone": customer.get("phone") if customer else None,
        "receipt_no": p.get("receipt_no") or p["_id"],
        "amount": p.get("amount", 0),
        "payment_method": p.get("payment_method") or p.get("method", "cash"),
        "notes": p.get("notes"),
        "created_by_name": _user_name(db, p.get("received_by") or p.get("created_by", "")),
        "created_at": p.get("created_at"),
    }


# ─── Legacy endpoint ──────────────────────────────────────────────────────────

@router.get("/customer-accounts")
def list_customer_accounts(db=Depends(get_db), _u=Depends(get_current_user)):
    rows = list(db[C.customers].find({"deleted_at": None}).sort("full_name", 1))
    return [{
        "id": c["_id"], "full_name": c["full_name"], "phone": c.get("phone"),
        "balance": customer_account_totals(db, c["_id"])["balance"],
        "credit_limit": c.get("credit_limit", 0),
    } for c in rows]


@router.get("/customer-accounts/{customer_id}/statement")
def statement_legacy(customer_id: str, db=Depends(get_db), _u=Depends(get_current_user)):
    return customer_statement(customer_id, db=db, _u=_u)


@router.post("/customer-accounts/{customer_id}/payments")
def record_payment_legacy(customer_id: str, payload: CustomerPaymentIn, request: Request,
                          db=Depends(get_db), current=Depends(require_manager)):
    return record_payment(customer_id, payload, request, db, current)
