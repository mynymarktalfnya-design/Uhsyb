"""Reports — MongoDB."""
from datetime import datetime, timezone, timedelta, date as _date
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import re

from database import get_db, C
from utils.deps import require_manager, require_admin, get_current_user
from utils.alert_settings import get_alert_settings
from utils.time import BUSINESS_TIMEZONE, business_now, business_today, day_range_utc, month_range_utc

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _date_range(date_from: Optional[str], date_to: Optional[str]):
    rng = {}
    if date_from:
        rng["$gte"] = day_range_utc(_date.fromisoformat(date_from))[0]
    if date_to:
        rng["$lt"] = day_range_utc(_date.fromisoformat(date_to))[1]
    return rng


def _returns_for_range(db, start, end):
    """Sum approved returns in [start, end] grouped by return_type."""
    pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lt": end},
                    "status": "approved", "deleted_at": None}},
        {"$group": {"_id": "$return_type", "total": {"$sum": "$total"}, "count": {"$sum": 1}}},
    ]
    by_type = {r["_id"]: {"total": float(r["total"]), "count": int(r["count"])}
               for r in db[C.sale_returns].aggregate(pipeline)}
    total_returns = sum(v["total"] for v in by_type.values())
    count_returns = sum(v["count"] for v in by_type.values())
    return total_returns, count_returns, by_type


def _returns_by_sale_payment_method(db, start, end):
    """Group returns by the original invoice payment method."""
    totals = {}
    for ret in db[C.sale_returns].find({
        "created_at": {"$gte": start, "$lt": end},
        "status": "approved",
        "deleted_at": None,
    }, {"sale_id": 1, "total": 1}):
        sale = db[C.sales].find_one({"_id": ret.get("sale_id")}, {"payment_method": 1})
        method = (sale or {}).get("payment_method") or "cash"
        totals[method] = totals.get(method, 0.0) + float(ret.get("total", 0) or 0)
    return totals


def _business_day_key(value):
    if not value:
        return "غير محدد"
    if isinstance(value, datetime):
        aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(BUSINESS_TIMEZONE).date().isoformat()
    return str(value)[:10]


@router.get("/daily")
def daily_sales(date: Optional[str] = None, db = Depends(get_db), _u = Depends(require_manager)):
    target = _date.fromisoformat(date) if date else business_today()
    start, end = day_range_utc(target)

    pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lt": end}, "status": "completed", "deleted_at": None}},
        {"$group": {"_id": "$payment_method", "total": {"$sum": "$total"}, "count": {"$sum": 1}}},
    ]
    by_method = {x["_id"]: {"total": float(x["total"]), "count": int(x["count"])}
                 for x in db[C.sales].aggregate(pipeline)}
    grand_total = sum(v["total"] for v in by_method.values())
    grand_count = sum(v["count"] for v in by_method.values())

    total_returns, count_returns, _ = _returns_for_range(db, start, end)
    returns_by_method = _returns_by_sale_payment_method(db, start, end)

    # Net by payment method
    by_method_net = {}
    for method, vals in by_method.items():
        ret = returns_by_method.get(method, 0.0)
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
    today = business_today()
    y, m = year or today.year, month or today.month
    start, end = month_range_utc(y, m)

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
    from routes.dashboard import _profit_breakdown

    rng = _date_range(date_from, date_to)
    start = rng.get("$gte") if rng else datetime(2000, 1, 1, tzinfo=timezone.utc)
    end = rng.get("$lt") if rng else datetime.now(timezone.utc)
    detail = _profit_breakdown(db, start, end)

    return {
        "revenue": detail["gross_sales"],
        "cost": detail["net_cogs"],
        "gross_cost": detail["cogs"],
        "returned_cost": detail["returned_cogs"],
        "total_returns": detail["returns"],
        "net_revenue": detail["net_sales"],
        "profit": detail["profit"],
        "items_count": detail["line_count"],
        "missing_cost_lines": detail["missing_cost_lines"],
        "cost_data_complete": detail["cost_data_complete"],
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

    # Returns are reconciled to the original invoice payment method.
    start_dt = rng.get("$gte") if rng else datetime(2000, 1, 1, tzinfo=timezone.utc)
    end_dt   = rng.get("$lt") if rng else datetime.now(timezone.utc)
    if isinstance(start_dt, _date) and not isinstance(start_dt, datetime):
        start_dt = datetime.combine(start_dt, datetime.min.time())
    if isinstance(end_dt, _date) and not isinstance(end_dt, datetime):
        end_dt = datetime.combine(end_dt, datetime.max.time())
    if start_dt is None:
        start_dt = datetime(2000, 1, 1, tzinfo=timezone.utc)
    if end_dt is None:
        end_dt = datetime.now(timezone.utc)
    returns_by_method = _returns_by_sale_payment_method(db, start_dt, end_dt)
    grand_returns = sum(returns_by_method.values())

    items = []
    for r in rows:
        t   = float(r["total"])
        c   = int(r["count"])
        ret = returns_by_method.get(r["_id"], 0.0)
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
        "remaining": round(total - paid, 2),
        "notes": purchase.get("notes"),
        "items": items,
    }


def _month_start(year: int, month: int) -> datetime:
    return month_range_utc(year, month)[0]


def _next_month(year: int, month: int) -> datetime:
    return month_range_utc(year, month)[1]


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
    today = _date.fromisoformat(date) if date else business_today()
    first_day = today if date else today - timedelta(days=days - 1)
    start = day_range_utc(first_day)[0]
    end = day_range_utc(today)[1]
    rows = list(db[C.purchases].find({
        "created_at": {"$gte": start, "$lt": end},
        "deleted_at": None,
    }).sort("created_at", -1))
    invoices = [_purchase_report_row(db, purchase) for purchase in rows]
    totals_by_day = {}
    for invoice in invoices:
        day = _business_day_key(invoice["date"])
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
    today = business_today()
    selected_year, selected_month = year or today.year, month or today.month

    month_rows = []
    for offset in range(months - 1, -1, -1):
        y, m = _previous_month(selected_year, selected_month, offset)
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
        day = _business_day_key(invoice["date"])
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


@router.get("/purchases-search")
def search_purchases(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    db = Depends(get_db),
    _u = Depends(require_manager),
):
    """Live search for a supplier's printed purchase invoice number."""
    query = q.strip()
    if not query:
        return []
    rows = list(db[C.purchases].find({
        "deleted_at": None,
        "supplier_invoice_no": {"$regex": re.escape(query), "$options": "i"},
    }).sort("created_at", -1).limit(limit))
    return [_purchase_report_row(db, purchase) for purchase in rows]


@router.get("/monthly-financial")
def monthly_financial(
    months: int = Query(12, ge=1, le=24),
    db = Depends(get_db),
    _u = Depends(require_manager),
):
    """Monthly financial statements: sales - returns - purchases - expenses."""
    today = business_today()

    def iso_day(value):
        if isinstance(value, datetime):
            aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return aware.astimezone(BUSINESS_TIMEZONE).date().isoformat()
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
        }, {"_id": 1, "total": 1, "created_at": 1, "subtotal": 1}))
        returns = list(db[C.sale_returns].find({
            "created_at": {"$gte": start, "$lt": end},
            "status": "approved",
            "deleted_at": None,
        }, {"_id": 1, "total": 1, "created_at": 1}))
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

        # إجمالي الأرباح = صافي المبيعات - تكلفة البضاعة المباعة.
        # نستخدم تكلفة المنتج المسجلة وقت إعداد التقرير، مثل endpoint الأرباح العام.
        sale_dates = {sale["_id"]: iso_day(sale.get("created_at")) for sale in sales}
        sale_ids = list(sale_dates)
        sale_items = list(db[C.sale_items].find({"sale_id": {"$in": sale_ids}})) if sale_ids else []
        product_ids = list({item.get("product_id") for item in sale_items if item.get("product_id")})
        products = {
            product["_id"]: product
            for product in db[C.products].find(
                {"_id": {"$in": product_ids}},
                {"cost_price": 1, "pieces_per_carton": 1},
            )
        } if product_ids else {}
        cost_by_day = {}
        for item in sale_items:
            day = sale_dates.get(item.get("sale_id"))
            if not day:
                continue
            product = products.get(item.get("product_id"), {})
            if item.get("cost_total") is not None:
                cost = float(item.get("cost_total") or 0)
            else:
                ppc = (
                    int(item.get("pieces_per_carton", 1) or 1)
                    if item.get("sale_unit") == "carton" else 1
                )
                cost = (
                    float(item.get("cost_price", product.get("cost_price", 0)) or 0)
                    * float(item.get("quantity", 0) or 0)
                    * ppc
                )
            cost_by_day[day] = cost_by_day.get(day, 0.0) + cost

        returned_cost_by_day = {}
        for ret in returns:
            return_day = iso_day(ret.get("created_at"))
            if not return_day:
                continue
            for returned in db[C.sale_return_items].find(
                {"return_id": ret["_id"]},
                {"sale_item_id": 1, "quantity": 1},
            ):
                original = db[C.sale_items].find_one(
                    {"_id": returned.get("sale_item_id")}
                ) or {}
                sold_qty = float(original.get("quantity", 0) or 0)
                returned_qty = float(returned.get("quantity", 0) or 0)
                if sold_qty <= 0:
                    continue
                if original.get("cost_total") is not None:
                    returned_cost = (
                        float(original.get("cost_total") or 0)
                        * returned_qty / sold_qty
                    )
                else:
                    original_product = products.get(original.get("product_id")) or db[
                        C.products
                    ].find_one(
                        {"_id": original.get("product_id")},
                        {"cost_price": 1},
                    ) or {}
                    ppc = (
                        int(original.get("pieces_per_carton", 1) or 1)
                        if original.get("sale_unit") == "carton" else 1
                    )
                    returned_cost = (
                        float(original_product.get("cost_price", 0) or 0)
                        * returned_qty * ppc
                    )
                returned_cost_by_day[return_day] = (
                    returned_cost_by_day.get(return_day, 0.0) + returned_cost
                )

        month_prefix = f"{year:04d}-{month:02d}"
        month_expenses = {
            day: total for day, total in expenses_by_day.items()
            if day.startswith(month_prefix)
        }
        days = sorted(
            set(sales_by_day)
            | set(returns_by_day)
            | set(purchases_by_day)
            | set(month_expenses)
            | set(returned_cost_by_day),
            reverse=True,
        )
        daily = []
        for day in days:
            gross_sales = sales_by_day.get(day, 0.0)
            returned = returns_by_day.get(day, 0.0)
            net_sales = gross_sales - returned
            purchase_total = purchases_by_day.get(day, 0.0)
            expense_total = month_expenses.get(day, 0.0)
            cost_total = cost_by_day.get(day, 0.0) - returned_cost_by_day.get(day, 0.0)
            daily.append({
                "date": day,
                "sales": round(gross_sales, 2),
                "returns": round(returned, 2),
                "net_sales": round(net_sales, 2),
                "purchases": round(purchase_total, 2),
                "expenses": round(expense_total, 2),
                "cost_of_goods_sold": round(cost_total, 2),
                "profit_total": round(net_sales - cost_total, 2),
                "profit_remaining": round(net_sales - purchase_total - expense_total, 2),
            })

        sales_total = sum(sales_by_day.values())
        returns_total = sum(returns_by_day.values())
        purchases_total = sum(purchases_by_day.values())
        expenses_total = sum(month_expenses.values())
        cost_of_goods_sold = sum(cost_by_day.values()) - sum(returned_cost_by_day.values())
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
            "cost_of_goods_sold": round(cost_of_goods_sold, 2),
            "profit_total": round(net_sales_total - cost_of_goods_sold, 2),
            "profit_remaining": round(net_sales_total - purchases_total - expenses_total, 2),
            "daily": daily,
        })

    return {
        "months_requested": months,
        "months": month_rows,
        "grand_sales": round(sum(row["sales_total"] for row in month_rows), 2),
        "grand_purchases": round(sum(row["purchases_total"] for row in month_rows), 2),
        "grand_expenses": round(sum(row["expenses_total"] for row in month_rows), 2),
        "grand_cost_of_goods_sold": round(sum(row["cost_of_goods_sold"] for row in month_rows), 2),
        "grand_profit_total": round(sum(row["profit_total"] for row in month_rows), 2),
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
    today = business_today()
    first_day = today - timedelta(days=max(1, days) - 1)
    start = day_range_utc(first_day)[0]
    end = day_range_utc(today)[1]
    sales_by_d = {}
    for sale in db[C.sales].find({
        "created_at": {"$gte": start, "$lt": end},
        "status": "completed",
        "deleted_at": None,
    }, {"created_at": 1, "total": 1}):
        day = _business_day_key(sale.get("created_at"))
        bucket = sales_by_d.setdefault(day, {"total": 0.0, "count": 0})
        bucket["total"] += float(sale.get("total", 0) or 0)
        bucket["count"] += 1
    returns_by_d = {}
    for ret in db[C.sale_returns].find({
        "created_at": {"$gte": start, "$lt": end},
        "status": "approved",
        "deleted_at": None,
    }, {"created_at": 1, "total": 1}):
        day = _business_day_key(ret.get("created_at"))
        bucket = returns_by_d.setdefault(day, {"returns": 0.0, "count": 0})
        bucket["returns"] += float(ret.get("total", 0) or 0)
        bucket["count"] += 1

    all_days = sorted(set(sales_by_d) | set(returns_by_d))
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
