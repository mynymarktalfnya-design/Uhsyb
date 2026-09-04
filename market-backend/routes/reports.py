"""Reports — MongoDB."""
from datetime import datetime, timezone, timedelta, date as _date
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from database import get_db, C
from utils.deps import require_manager, require_admin, get_current_user
from utils.alert_settings import get_alert_settings

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _date_range(date_from: Optional[str], date_to: Optional[str]):
    rng = {}
    if date_from:
        rng["$gte"] = datetime.combine(_date.fromisoformat(date_from), datetime.min.time())
    if date_to:
        rng["$lte"] = datetime.combine(_date.fromisoformat(date_to), datetime.max.time())
    return rng


def _returns_for_range(db, start, end):
    """Sum approved returns in [start, end] grouped by return_type."""
    pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lte": end},
                    "status": "approved", "deleted_at": None}},
        {"$group": {"_id": "$return_type", "total": {"$sum": "$total"}, "count": {"$sum": 1}}},
    ]
    by_type = {r["_id"]: {"total": float(r["total"]), "count": int(r["count"])}
               for r in db[C.sale_returns].aggregate(pipeline)}
    total_returns = sum(v["total"] for v in by_type.values())
    count_returns = sum(v["count"] for v in by_type.values())
    return total_returns, count_returns, by_type


@router.get("/daily")
def daily_sales(date: Optional[str] = None, db = Depends(get_db), _u = Depends(require_manager)):
    target = _date.fromisoformat(date) if date else _date.today()
    start = datetime.combine(target, datetime.min.time())
    end = datetime.combine(target, datetime.max.time())

    pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lte": end}, "status": "completed", "deleted_at": None}},
        {"$group": {"_id": "$payment_method", "total": {"$sum": "$total"}, "count": {"$sum": 1}}},
    ]
    by_method = {x["_id"]: {"total": float(x["total"]), "count": int(x["count"])}
                 for x in db[C.sales].aggregate(pipeline)}
    grand_total = sum(v["total"] for v in by_method.values())
    grand_count = sum(v["count"] for v in by_method.values())

    total_returns, count_returns, returns_by_type = _returns_for_range(db, start, end)

    # Net by payment method
    by_method_net = {}
    for method, vals in by_method.items():
        ret = returns_by_type.get(method, {}).get("total", 0.0)
        by_method_net[method] = {
            "total": round(vals["total"], 2),
            "count": vals["count"],
            "returns_total": round(ret, 2),
            "net_total": round(max(0.0, vals["total"] - ret), 2),
        }

    return {
        "date": target.isoformat(),
        "total_sales": round(grand_total, 2),
        "total_returns": round(total_returns, 2),
        "net_sales": round(grand_total - total_returns, 2),
        "transactions_count": grand_count,
        "returns_count": count_returns,
        "by_payment_method": by_method,
        "by_payment_method_net": by_method_net,
    }


@router.get("/monthly")
def monthly_sales(year: Optional[int] = None, month: Optional[int] = None,
                  db = Depends(get_db), _u = Depends(require_manager)):
    today = _date.today()
    y, m = year or today.year, month or today.month
    start = datetime(y, m, 1, tzinfo=timezone.utc)
    end = datetime(y + (m // 12), (m % 12) + 1, 1, tzinfo=timezone.utc)

    pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lt": end}, "status": "completed", "deleted_at": None}},
        {"$group": {"_id": None, "total": {"$sum": "$total"}, "count": {"$sum": 1}}},
    ]
    agg = list(db[C.sales].aggregate(pipeline))
    total_sales = float(agg[0]["total"]) if agg else 0.0
    tx_count    = int(agg[0]["count"])   if agg else 0

    total_returns, count_returns, _ = _returns_for_range(db, start, end)

    return {
        "year": y, "month": m,
        "total_sales": round(total_sales, 2),
        "total_returns": round(total_returns, 2),
        "net_sales": round(total_sales - total_returns, 2),
        "transactions_count": tx_count,
        "returns_count": count_returns,
    }


@router.get("/profits")
def profits(date_from: Optional[str] = None, date_to: Optional[str] = None,
            db = Depends(get_db), _u = Depends(require_admin)):
    """Admin-only profit report (revenue - cost - returns)."""
    rng = _date_range(date_from, date_to)
    sales_filter = {"status": "completed", "deleted_at": None}
    if rng:
        sales_filter["created_at"] = rng
    sale_ids = [s["_id"] for s in db[C.sales].find(sales_filter, {"_id": 1})]
    if not sale_ids:
        return {"revenue": 0, "cost": 0, "total_returns": 0, "net_revenue": 0, "profit": 0, "items_count": 0}

    items = list(db[C.sale_items].find({"sale_id": {"$in": sale_ids}}))
    product_ids = list({it["product_id"] for it in items})
    prod_map = {p["_id"]: p for p in
                db[C.products].find({"_id": {"$in": product_ids}}, {"cost_price": 1})}
    revenue = sum(float(it.get("total", 0)) for it in items)
    cost = sum(float(prod_map.get(it["product_id"], {}).get("cost_price", 0) or 0)
               * float(it.get("quantity", 0)) for it in items)

    # Approved returns in the same period
    ret_filter = {"status": "approved", "deleted_at": None}
    if rng:
        ret_filter["created_at"] = rng
    total_returns = sum(float(r.get("total", 0))
                        for r in db[C.sale_returns].find(ret_filter, {"total": 1}))
    net_revenue = revenue - total_returns

    return {
        "revenue": round(revenue, 2),
        "cost": round(cost, 2),
        "total_returns": round(total_returns, 2),
        "net_revenue": round(net_revenue, 2),
        "profit": round(net_revenue - cost, 2),
        "items_count": len(items),
    }


@router.get("/payment-methods")
def payment_methods_report(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db = Depends(get_db), _u = Depends(require_manager),
):
    """تقرير طرق الدفع مع تجميع وإحصائيات مفصّلة (صافي المرتجعات)."""
    rng = _date_range(date_from, date_to)
    match_f = {"status": "completed", "deleted_at": None}
    if rng:
        match_f["created_at"] = rng

    pipeline = [
        {"$match": match_f},
        {"$group": {
            "_id": "$payment_method",
            "total": {"$sum": "$total"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"total": -1}},
    ]
    rows = list(db[C.sales].aggregate(pipeline))
    grand_total = sum(float(r["total"]) for r in rows)

    # Returns by type
    start_dt = rng.get("$gte") if rng else datetime(2000, 1, 1)
    end_dt   = rng.get("$lte") if rng else datetime.now(timezone.utc)
    if isinstance(start_dt, _date) and not isinstance(start_dt, datetime):
        start_dt = datetime.combine(start_dt, datetime.min.time())
    if isinstance(end_dt, _date) and not isinstance(end_dt, datetime):
        end_dt = datetime.combine(end_dt, datetime.max.time())
    if start_dt is None:
        start_dt = datetime(2000, 1, 1)
    if end_dt is None:
        end_dt = datetime.now(timezone.utc)
    _, _, returns_by_type = _returns_for_range(db, start_dt, end_dt)
    grand_returns = sum(v["total"] for v in returns_by_type.values())

    items = []
    for r in rows:
        t   = float(r["total"])
        c   = int(r["count"])
        ret = returns_by_type.get(r["_id"], {}).get("total", 0.0)
        net = max(0.0, t - ret)
        items.append({
            "method":        r["_id"],
            "total":         round(t, 2),
            "returns_total": round(ret, 2),
            "net_total":     round(net, 2),
            "count":         c,
            "avg":           round(t / c, 2) if c else 0,
            "net_avg":       round(net / c, 2) if c else 0,
            "pct":           round(t / grand_total * 100, 1) if grand_total > 0 else 0,
        })
    return {
        "grand_total":   round(grand_total, 2),
        "grand_returns": round(grand_returns, 2),
        "grand_net":     round(grand_total - grand_returns, 2),
        "items": items,
    }


def _effective_purchase_paid(purchase: dict) -> float:
    """Amount actually paid for a purchase, including legacy records."""
    method = purchase.get("payment_method", "credit")
    paid = float(purchase.get("paid_amount") or 0)
    total = float(purchase.get("total") or 0)
    if paid > 0:
        return paid
    return total if method != "credit" else 0.0


def _purchase_report_row(db, purchase: dict) -> dict:
    supplier = db[C.suppliers].find_one(
        {"_id": purchase.get("supplier_id")}, {"name": 1, "phone": 1}
    )
    creator = db[C.users].find_one(
        {"_id": purchase.get("created_by")},
        {"name": 1, "full_name": 1, "username": 1},
    )
    items = []
    for item in db[C.purchase_items].find({"purchase_id": purchase["_id"]}):
        product = db[C.products].find_one(
            {"_id": item.get("product_id")}, {"name": 1, "unit": 1}
        )
        items.append({
            "id": item["_id"],
            "product_id": item.get("product_id"),
            "product_name": product.get("name") if product else item.get("product_id"),
            "unit": item.get("unit") or (product.get("unit") if product else "piece"),
            "quantity": float(item.get("quantity", 0) or 0),
            "cartons": float(item["cartons"]) if item.get("cartons") is not None else None,
            "pieces_per_carton": float(item["pieces_per_carton"]) if item.get("pieces_per_carton") is not None else None,
            "unit_cost": float(item.get("unit_cost", 0) or 0),
            "carton_cost": float(item["carton_cost"]) if item.get("carton_cost") is not None else None,
            "total": float(item.get("total", 0) or 0),
        })
    total = float(purchase.get("total", 0) or 0)
    paid = _effective_purchase_paid(purchase)
    created_at = purchase.get("created_at")
    return {
        "id": purchase["_id"],
        "date": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
        "ref_no": purchase.get("ref_no") or purchase.get("invoice_no") or purchase["_id"],
        "supplier_invoice_no": purchase.get("supplier_invoice_no"),
        "supplier_id": purchase.get("supplier_id"),
        "supplier_name": supplier.get("name") if supplier else "غير محدد",
        "supplier_phone": supplier.get("phone") if supplier else None,
        "created_by_name": (
            (creator.get("full_name") or creator.get("username"))
            if creator else "غير محدد"
        ),
        "total": total,
        "payment_method": purchase.get("payment_method", "credit"),
        "paid_amount": paid,
        "remaining": max(0.0, total - paid),
        "notes": purchase.get("notes"),
        "items": items,
    }


def _month_start(year: int, month: int) -> datetime:
    return datetime(year, month, 1, tzinfo=timezone.utc)


def _next_month(year: int, month: int) -> datetime:
    return datetime(year + (month // 12), (month % 12) + 1, 1, tzinfo=timezone.utc)


def _previous_month(year: int, month: int, offset: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) - offset
    return index // 12, index % 12 + 1


@router.get("/purchases-daily")
def purchases_daily(
    date: Optional[str] = None,
    days: int = Query(30, ge=1, le=366),
    db = Depends(get_db),
    _u = Depends(require_manager),
):
    today = _date.fromisoformat(date) if date else _date.today()
    first_day = today if date else today - timedelta(days=days - 1)
    start = datetime.combine(first_day, datetime.min.time()).replace(tzinfo=timezone.utc)
    end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)
    rows = list(db[C.purchases].find({
        "created_at": {"$gte": start, "$lte": end},
        "deleted_at": None,
    }).sort("created_at", -1))
    invoices = [_purchase_report_row(db, purchase) for purchase in rows]
    totals_by_day = {}
    for invoice in invoices:
        day = str(invoice["date"])[:10] if invoice["date"] else "غير محدد"
        bucket = totals_by_day.setdefault(day, {"date": day, "invoices_count": 0, "total": 0.0})
        bucket["invoices_count"] += 1
        bucket["total"] += invoice["total"]
    daily_totals = sorted(totals_by_day.values(), key=lambda x: x["date"], reverse=True)
    return {
        "date": today.isoformat(),
        "from": first_day.isoformat(),
        "to": today.isoformat(),
        "days": 1 if date else days,
        "grand_total": round(sum(invoice["total"] for invoice in invoices), 2),
        "grand_invoices_count": len(invoices),
        "daily_totals": daily_totals,
        "invoices": invoices,
    }


@router.get("/purchases-monthly")
def purchases_monthly(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    months: int = Query(12, ge=1, le=24),
    db = Depends(get_db),
    _u = Depends(require_manager),
):
    today = _date.today()
    selected_year, selected_month = year or today.year, month or today.month

    month_rows = []
    for offset in range(months - 1, -1, -1):
        y, m = _previous_month(today.year, today.month, offset)
        start = _month_start(y, m)
        end = _next_month(y, m)
        rows = list(db[C.purchases].find({
            "created_at": {"$gte": start, "$lt": end},
            "deleted_at": None,
        }))
        invoices = [_purchase_report_row(db, purchase) for purchase in rows]
        by_supplier = {}
        for invoice in invoices:
            supplier = by_supplier.setdefault(invoice["supplier_name"], {"name": invoice["supplier_name"], "total": 0.0, "count": 0})
            supplier["total"] += invoice["total"]
            supplier["count"] += 1
        top_supplier = max(by_supplier.values(), key=lambda x: x["total"]) if by_supplier else None
        month_rows.append({
            "year": y,
            "month": m,
            "month_label": f"{y:04d}-{m:02d}",
            "invoices_count": len(invoices),
            "products_added": sum(len(invoice["items"]) for invoice in invoices),
            "total": round(sum(invoice["total"] for invoice in invoices), 2),
            "top_supplier": top_supplier,
        })

    selected_start = _month_start(selected_year, selected_month)
    selected_end = _next_month(selected_year, selected_month)
    selected_rows = list(db[C.purchases].find({
        "created_at": {"$gte": selected_start, "$lt": selected_end},
        "deleted_at": None,
    }).sort("created_at", -1))
    selected_invoices = [_purchase_report_row(db, purchase) for purchase in selected_rows]
    daily_map = {}
    for invoice in selected_invoices:
        day = str(invoice["date"])[:10] if invoice["date"] else "غير محدد"
        bucket = daily_map.setdefault(day, {"date": day, "invoices_count": 0, "total": 0.0})
        bucket["invoices_count"] += 1
        bucket["total"] += invoice["total"]
    selected_summary = {
        "year": selected_year,
        "month": selected_month,
        "invoices_count": len(selected_invoices),
        "total": round(sum(invoice["total"] for invoice in selected_invoices), 2),
        "paid_total": round(sum(invoice["paid_amount"] for invoice in selected_invoices), 2),
        "remaining_total": round(sum(invoice["remaining"] for invoice in selected_invoices), 2),
        "returns_total": 0.0,
    }
    return {
        "year": selected_year,
        "month": selected_month,
        "months_requested": months,
        "months": month_rows,
        "grand_total": round(sum(row["total"] for row in month_rows), 2),
        "grand_invoices_count": sum(row["invoices_count"] for row in month_rows),
        "selected": selected_summary,
        "invoices": selected_invoices,
        "daily_totals": sorted(daily_map.values(), key=lambda x: x["date"], reverse=True),
    }


@router.get("/monthly-financial")
def monthly_financial(
    months: int = Query(12, ge=1, le=24),
    db = Depends(get_db),
    _u = Depends(require_manager),
):
    """Monthly financial statements: sales - returns - purchases - expenses."""
    today = _date.today()

    def iso_day(value):
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).date().isoformat() if value.tzinfo else value.date().isoformat()
        return str(value)[:10] if value else None

    expenses_by_day = {}
    for expense in db[C.expenses].find(
        {"deleted_at": None},
        {"amount": 1, "expense_date": 1, "created_at": 1},
    ):
        day = expense.get("expense_date") or iso_day(expense.get("created_at"))
        if day:
            expenses_by_day[day] = expenses_by_day.get(day, 0.0) + float(expense.get("amount", 0) or 0)

    month_rows = []
    for offset in range(months - 1, -1, -1):
        year, month = _previous_month(today.year, today.month, offset)
        start = _month_start(year, month)
        end = _next_month(year, month)

        sales = list(db[C.sales].find({
            "created_at": {"$gte": start, "$lt": end},
            "status": "completed",
            "deleted_at": None,
        }, {"total": 1, "created_at": 1}))
        returns = list(db[C.sale_returns].find({
            "created_at": {"$gte": start, "$lt": end},
            "status": "approved",
            "deleted_at": None,
        }, {"total": 1, "created_at": 1}))
        purchases = list(db[C.purchases].find({
            "created_at": {"$gte": start, "$lt": end},
            "deleted_at": None,
        }, {"total": 1, "created_at": 1}))

        sales_by_day = {}
        returns_by_day = {}
        purchases_by_day = {}
        for row in sales:
            day = iso_day(row.get("created_at"))
            if day:
                sales_by_day[day] = sales_by_day.get(day, 0.0) + float(row.get("total", 0) or 0)
        for row in returns:
            day = iso_day(row.get("created_at"))
            if day:
                returns_by_day[day] = returns_by_day.get(day, 0.0) + float(row.get("total", 0) or 0)
        for row in purchases:
            day = iso_day(row.get("created_at"))
            if day:
                purchases_by_day[day] = purchases_by_day.get(day, 0.0) + float(row.get("total", 0) or 0)

        month_prefix = f"{year:04d}-{month:02d}"
        month_expenses = {
            day: total for day, total in expenses_by_day.items()
            if day.startswith(month_prefix)
        }
        days = sorted(set(sales_by_day) | set(returns_by_day) | set(purchases_by_day) | set(month_expenses), reverse=True)
        daily = []
        for day in days:
            gross_sales = sales_by_day.get(day, 0.0)
            returned = returns_by_day.get(day, 0.0)
            net_sales = gross_sales - returned
            purchase_total = purchases_by_day.get(day, 0.0)
            expense_total = month_expenses.get(day, 0.0)
            daily.append({
                "date": day,
                "sales": round(gross_sales, 2),
                "returns": round(returned, 2),
                "net_sales": round(net_sales, 2),
                "purchases": round(purchase_total, 2),
                "expenses": round(expense_total, 2),
                "profit_remaining": round(net_sales - purchase_total - expense_total, 2),
            })

        sales_total = sum(sales_by_day.values())
        returns_total = sum(returns_by_day.values())
        purchases_total = sum(purchases_by_day.values())
        expenses_total = sum(month_expenses.values())
        net_sales_total = sales_total - returns_total
        month_rows.append({
            "year": year,
            "month": month,
            "month_label": f"{year:04d}-{month:02d}",
            "sales_total": round(sales_total, 2),
            "returns_total": round(returns_total, 2),
            "net_sales_total": round(net_sales_total, 2),
            "purchases_total": round(purchases_total, 2),
            "expenses_total": round(expenses_total, 2),
            "profit_remaining": round(net_sales_total - purchases_total - expenses_total, 2),
            "daily": daily,
        })

    return {
        "months_requested": months,
        "months": month_rows,
        "grand_sales": round(sum(row["sales_total"] for row in month_rows), 2),
        "grand_purchases": round(sum(row["purchases_total"] for row in month_rows), 2),
        "grand_expenses": round(sum(row["expenses_total"] for row in month_rows), 2),
        "grand_profit_remaining": round(sum(row["profit_remaining"] for row in month_rows), 2),
    }


@router.get("/low-stock")
def low_stock(db = Depends(get_db), _u = Depends(require_manager)):
    rows = list(db[C.products].find({"deleted_at": None, "is_active": True}))
    threshold = get_alert_settings(db)["low_stock_threshold"]
    out = [{"id": p["_id"], "name": p["name"], "current_stock": p.get("current_stock", 0),
            "min_stock_level": p.get("min_stock_level", 0)}
           for p in rows
           if float(p.get("current_stock", 0) or 0) <= threshold or
           float(p.get("current_stock", 0) or 0) <= float(p.get("min_stock_level", 0) or 0)]
    return out


@router.get("/sales-by-day")
def sales_by_day(days: int = 30, db = Depends(get_db), _u = Depends(require_manager)):
    """Return last N days of total sales + returns + net sales for charts."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    sales_pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lte": end},
                    "status": "completed", "deleted_at": None}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                     "total": {"$sum": "$total"}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    ret_pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lte": end},
                    "status": "approved", "deleted_at": None}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                     "returns": {"$sum": "$total"}, "returns_count": {"$sum": 1}}},
    ]
    sales_by_d   = {r["_id"]: {"total": float(r["total"]), "count": int(r["count"])}
                    for r in db[C.sales].aggregate(sales_pipeline)}
    returns_by_d = {r["_id"]: {"returns": float(r["returns"]), "count": int(r["returns_count"])}
                    for r in db[C.sale_returns].aggregate(ret_pipeline)}

    all_days = sorted(set(list(sales_by_d.keys()) + list(returns_by_d.keys())))
    result = []
    for d in all_days:
        s = sales_by_d.get(d, {}).get("total", 0.0)
        r = returns_by_d.get(d, {}).get("returns", 0.0)
        sc = sales_by_d.get(d, {}).get("count", 0)
        rc = returns_by_d.get(d, {}).get("count", 0)
        result.append({
            "date": d,
            "total": round(s, 2),
            "count": sc,
            "returns": round(r, 2),
            "returns_count": rc,
            "net_sales": round(s - r, 2),
        })
    return result
