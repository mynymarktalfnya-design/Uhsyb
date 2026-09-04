"""Dashboard summary endpoints — MongoDB."""
from datetime import datetime, timezone, timedelta, date as _date
from fastapi import APIRouter, Depends
from database import get_db, C
from utils.deps import get_current_user, require_manager
from utils.alert_settings import get_alert_settings

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _today_range():
    today = _date.today()
    start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
    end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)
    return start, end


def _month_range():
    today = _date.today()
    start = datetime(today.year, today.month, 1, tzinfo=timezone.utc)
    if today.month == 12:
        end = datetime(today.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(today.year, today.month + 1, 1, tzinfo=timezone.utc)
    return start, end


def _sum_sales(db, start, end):
    pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lte": end},
                    "status": "completed", "deleted_at": None}},
        {"$group": {"_id": None, "total": {"$sum": "$total"}, "count": {"$sum": 1}}},
    ]
    a = list(db[C.sales].aggregate(pipeline))
    return (a[0]["total"], a[0]["count"]) if a else (0, 0)


def _sum_returns(db, start, end):
    """Sum approved returns in a date range. Returns (total, count)."""
    pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lte": end},
                    "status": "approved", "deleted_at": None}},
        {"$group": {"_id": None, "total": {"$sum": "$total"}, "count": {"$sum": 1}}},
    ]
    a = list(db[C.sale_returns].aggregate(pipeline))
    return (float(a[0]["total"]), int(a[0]["count"])) if a else (0.0, 0)


def _sum_returns_by_type(db, start, end):
    """Sum approved returns grouped by return_type (cash / credit / etc.)."""
    pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lte": end},
                    "status": "approved", "deleted_at": None}},
        {"$group": {"_id": "$return_type", "total": {"$sum": "$total"}, "count": {"$sum": 1}}},
    ]
    return {r["_id"]: {"total": float(r["total"]), "count": int(r["count"])}
            for r in db[C.sale_returns].aggregate(pipeline)}


def _sum_purchases(db, start, end):
    pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lt": end}, "deleted_at": None}},
        {"$group": {"_id": None, "total": {"$sum": "$total"}, "count": {"$sum": 1}}},
    ]
    a = list(db[C.purchases].aggregate(pipeline))
    return (a[0]["total"], a[0]["count"]) if a else (0, 0)


def _sum_expenses(db, start, end):
    pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lt": end}, "deleted_at": None}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]
    a = list(db[C.expenses].aggregate(pipeline))
    return a[0]["total"] if a else 0


@router.get("/summary")
def dashboard_summary(db = Depends(get_db), current = Depends(get_current_user)):
    today_start, today_end = _today_range()
    month_start, month_end = _month_range()

    sales_today, invoices_today = _sum_sales(db, today_start, today_end)
    sales_month, invoices_month = _sum_sales(db, month_start, month_end)
    purchases_today, _ = _sum_purchases(db, today_start, today_end + timedelta(microseconds=1))
    purchases_month, _ = _sum_purchases(db, month_start, month_end)
    expenses_month = _sum_expenses(db, month_start, month_end)

    # Returns (approved only)
    returns_today, returns_today_count = _sum_returns(db, today_start, today_end)
    returns_month, returns_month_count = _sum_returns(db, month_start, month_end)
    returns_by_type_today = _sum_returns_by_type(db, today_start, today_end)
    cash_returns_today = returns_by_type_today.get("cash", {}).get("total", 0.0)
    credit_returns_today = returns_by_type_today.get("credit", {}).get("total", 0.0)

    # Sales breakdown: cash (all non-credit methods) vs credit (آجل) — net of returns
    by_method_today = list(db[C.sales].aggregate([
        {"$match": {"created_at": {"$gte": today_start, "$lte": today_end},
                    "status": "completed", "deleted_at": None}},
        {"$group": {"_id": "$payment_method",
                    "total": {"$sum": "$total"}, "count": {"$sum": 1}}},
    ]))
    gross_today_cash   = sum(float(x["total"]) for x in by_method_today if x["_id"] != "credit")
    gross_today_credit = sum(float(x["total"]) for x in by_method_today if x["_id"] == "credit")
    # Net = gross − returns by type
    sales_today_cash   = max(0.0, gross_today_cash - cash_returns_today)
    sales_today_credit = max(0.0, gross_today_credit - credit_returns_today)

    # Payment-method constants
    WALLET_METHODS = {"jaib", "fluusak", "hasib"}
    BANK_METHODS   = {"banki", "bank_transfer"}

    gross_today_wallets = sum(float(x["total"]) for x in by_method_today if x["_id"] in WALLET_METHODS)
    gross_today_banks   = sum(float(x["total"]) for x in by_method_today if x["_id"] in BANK_METHODS)
    wallet_returns_today = sum(returns_by_type_today.get(m, {}).get("total", 0.0) for m in WALLET_METHODS)
    bank_returns_today   = sum(returns_by_type_today.get(m, {}).get("total", 0.0) for m in BANK_METHODS)
    sales_today_wallets  = max(0.0, gross_today_wallets - wallet_returns_today)
    sales_today_banks    = max(0.0, gross_today_banks - bank_returns_today)

    products_count = db[C.products].count_documents({"deleted_at": None, "is_active": True})
    customers_count = db[C.customers].count_documents({"deleted_at": None})
    suppliers_count = db[C.suppliers].count_documents({"deleted_at": None})
    alert_settings = get_alert_settings(db)
    low_stock_threshold = alert_settings["low_stock_threshold"]
    # A product is low when it reaches the global threshold or its own threshold.
    low_stock_count = db[C.products].count_documents({
        "deleted_at": None, "is_active": True,
        "$or": [
            {"$expr": {"$lte": ["$current_stock", low_stock_threshold]}},
            {"$expr": {"$lte": ["$current_stock", "$min_stock_level"]}},
        ],
    })

    # Expiring within the configured number of days
    soon = datetime.now(timezone.utc) + timedelta(days=alert_settings["expiry_alert_days"])
    expiring_soon = db[C.products].count_documents({
        "deleted_at": None, "is_active": True,
        "expiry_date": {"$ne": None, "$lte": soon},
    })

    return {
        # Gross sales
        "sales_today": sales_today, "invoices_today": invoices_today,
        "sales_today_cash": round(sales_today_cash, 2),
        "sales_today_credit": round(sales_today_credit, 2),
        "sales_today_wallets": round(sales_today_wallets, 2),
        "sales_today_banks": round(sales_today_banks, 2),
        "sales_month": sales_month, "invoices_month": invoices_month,
        # Returns (approved)
        "returns_today": round(returns_today, 2),
        "returns_today_count": returns_today_count,
        "returns_month": round(returns_month, 2),
        "returns_month_count": returns_month_count,
        # Net sales = gross − returns
        "net_sales_today": round(sales_today - returns_today, 2),
        "net_sales_month": round(sales_month - returns_month, 2),
        # Purchases / expenses
        "purchases_today": purchases_today, "purchases_month": purchases_month,
        "expenses_month": expenses_month,
        "products_count": products_count,
        "customers_count": customers_count,
        "suppliers_count": suppliers_count,
        "low_stock_count": low_stock_count,
        "expiring_soon_count": expiring_soon,
        "alert_settings": alert_settings,
    }


@router.get("/manager")
def manager_dashboard(db = Depends(get_db), _u = Depends(require_manager)):
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    today = _date.today()
    week_start = datetime.combine(today - timedelta(days=today.weekday()),
                                   datetime.min.time()).replace(tzinfo=timezone.utc)
    month_start, month_end = _month_range()
    year_start = datetime(today.year, 1, 1, tzinfo=timezone.utc)
    year_end = datetime(today.year + 1, 1, 1, tzinfo=timezone.utc)
    today_start, today_end = _today_range()

    def sum_sales(start, end):
        return _sum_sales(db, start, end)[0]

    def sum_purchases(start, end):
        return _sum_purchases(db, start, end)[0]

    def count_purchases(start, end):
        return db[C.purchases].count_documents({
            "created_at": {"$gte": start, "$lt": end}, "deleted_at": None,
        })

    def sum_expenses(start, end):
        return _sum_expenses(db, start, end)

    def sum_ret(start, end):
        return _sum_returns(db, start, end)[0]

    # Sales today: cash (all non-credit methods) vs credit (آجل)
    today_invoices_count = _sum_sales(db, today_start, today_end)[1]
    by_method_today = list(db[C.sales].aggregate([
        {"$match": {"created_at": {"$gte": today_start, "$lte": today_end},
                    "status": "completed", "deleted_at": None}},
        {"$group": {"_id": "$payment_method",
                    "total": {"$sum": "$total"}, "count": {"$sum": 1}}},
    ]))
    today_cash_total   = round(sum(float(x["total"]) for x in by_method_today if x["_id"] != "credit"), 2)
    today_credit_total = round(sum(float(x["total"]) for x in by_method_today if x["_id"] == "credit"), 2)

    # Returns by period
    ret_today = sum_ret(today_start, today_end)
    ret_week  = sum_ret(week_start, today_end)
    ret_month = sum_ret(month_start, month_end)
    ret_year  = sum_ret(year_start, year_end)
    ret_by_type_today = _sum_returns_by_type(db, today_start, today_end)
    cash_ret_today   = ret_by_type_today.get("cash", {}).get("total", 0.0)
    credit_ret_today = ret_by_type_today.get("credit", {}).get("total", 0.0)

    gross_today = sum_sales(today_start, today_end)
    gross_week  = sum_sales(week_start, today_end)
    gross_month = sum_sales(month_start, month_end)
    gross_year  = sum_sales(year_start, year_end)

    # Sales by period (gross + net)
    sales = {
        "today": gross_today,
        "week":  gross_week,
        "month": gross_month,
        "year":  gross_year,
        "today_cash":   round(today_cash_total, 2),
        "today_credit": round(today_credit_total, 2),
        "invoices_today": today_invoices_count,
        # Returns
        "returns_today": round(ret_today, 2),
        "returns_week":  round(ret_week, 2),
        "returns_month": round(ret_month, 2),
        "returns_year":  round(ret_year, 2),
        # Net = gross − returns
        "net_today": round(gross_today - ret_today, 2),
        "net_week":  round(gross_week  - ret_week,  2),
        "net_month": round(gross_month - ret_month, 2),
        "net_year":  round(gross_year  - ret_year,  2),
        "net_today_cash":   round(max(0.0, today_cash_total   - cash_ret_today),   2),
        "net_today_credit": round(max(0.0, today_credit_total - credit_ret_today), 2),
    }

    # Profits = revenue - cost (approximate, per item) - returns
    def profit_for(start, end):
        sale_ids = [s["_id"] for s in db[C.sales].find({
            "created_at": {"$gte": start, "$lte": end},
            "status": "completed", "deleted_at": None,
        }, {"_id": 1})]
        if not sale_ids:
            return 0
        items = list(db[C.sale_items].find({"sale_id": {"$in": sale_ids}}))
        if not items:
            return 0
        product_ids = list({it["product_id"] for it in items})
        prod_map = {p["_id"]: p for p in
                    db[C.products].find({"_id": {"$in": product_ids}}, {"cost_price": 1})}
        rev = sum(float(it.get("total", 0)) for it in items)
        cost = sum(float(prod_map.get(it["product_id"], {}).get("cost_price", 0) or 0)
                   * float(it.get("quantity", 0)) for it in items)
        # Subtract approved returns from profit
        ret_total = _sum_returns(db, start, end)[0]
        return (rev - ret_total) - cost

    profits = {
        "today": profit_for(today_start, today_end),
        "week": profit_for(week_start, today_end),
        "month": profit_for(month_start, month_end),
        "year": profit_for(year_start, year_end),
    }

    purchases = {
        "today_total": sum_purchases(today_start, today_end + timedelta(microseconds=1)),
        "week_total": sum_purchases(week_start, today_end + timedelta(microseconds=1)),
        "month_total": sum_purchases(month_start, month_end),
        "year_total": sum_purchases(year_start, year_end),
        "today_count": count_purchases(today_start, today_end + timedelta(microseconds=1)),
        "month_count": count_purchases(month_start, month_end),
        "today_products_added": 0,
        "month_products_added": 0,
    }
    # Distinct products purchased today
    purchases["today_products_added"] = len(set(
        i["product_id"] for s in db[C.purchases].find({
            "created_at": {"$gte": today_start, "$lte": today_end}, "deleted_at": None,
        }, {"_id": 1})
        for i in db[C.purchase_items].find({"purchase_id": s["_id"]}, {"product_id": 1})
    ))
    purchases["month_products_added"] = len(set(
        i["product_id"] for s in db[C.purchases].find({
            "created_at": {"$gte": month_start, "$lt": month_end}, "deleted_at": None,
        }, {"_id": 1})
        for i in db[C.purchase_items].find({"purchase_id": s["_id"]}, {"product_id": 1})
    ))

    # Cash box (simplified)
    cash_sales_today = 0.0
    for s in db[C.sales].find({
        "created_at": {"$gte": today_start, "$lte": today_end},
        "status": "completed", "payment_method": "cash", "deleted_at": None,
    }, {"total": 1}):
        cash_sales_today += float(s.get("total", 0))
    customer_receipts = sum(float(p.get("amount", 0)) for p in db[C.customer_payments].find({
        "created_at": {"$gte": today_start, "$lte": today_end},
    }, {"amount": 1}))
    expenses_paid_today = sum_expenses(today_start, today_end + timedelta(microseconds=1))
    supplier_paid_today = sum(float(p.get("amount", 0)) for p in db[C.supplier_payments].find({
        "created_at": {"$gte": today_start, "$lte": today_end},
    }, {"amount": 1}))
    # Cash returns — approved returns refunded in cash
    cash_returns_today = _sum_returns_by_type(db, today_start, today_end).get("cash", {}).get("total", 0.0)
    cash_box = {
        "current_balance": cash_sales_today + customer_receipts - expenses_paid_today - supplier_paid_today - cash_returns_today,
        "total_received_today": cash_sales_today + customer_receipts,
        "sales_cash": cash_sales_today,
        "customer_receipts": customer_receipts,
        "total_paid_today": expenses_paid_today + supplier_paid_today + cash_returns_today,
        "expenses_paid": expenses_paid_today,
        "supplier_paid": supplier_paid_today,
        "cash_returns": round(cash_returns_today, 2),
    }

    # Alerts
    over_credit = []
    for c in db[C.customers].find({"deleted_at": None,
                                    "credit_limit": {"$gt": 0}}, {"_id": 1, "full_name": 1, "balance": 1, "credit_limit": 1}):
        if float(c.get("balance", 0)) > float(c.get("credit_limit", 0)):
            over_credit.append({"id": c["_id"], "full_name": c["full_name"],
                                 "balance": c.get("balance", 0),
                                 "credit_limit": c.get("credit_limit", 0)})
    suppliers_overdue = []
    for s in db[C.suppliers].find({"deleted_at": None, "balance": {"$gt": 0}},
                                   {"_id": 1, "name": 1, "balance": 1}):
        suppliers_overdue.append({"id": s["_id"], "name": s["name"],
                                   "balance": s.get("balance", 0)})

    low_stock = []
    out_of_stock = []
    alert_settings = get_alert_settings(db)
    low_stock_threshold = alert_settings["low_stock_threshold"]
    # Server-side filter for low-stock / out-of-stock products
    low_or_out = list(db[C.products].find({
        "deleted_at": None, "is_active": True,
        "$or": [
            {"$expr": {"$lte": ["$current_stock", low_stock_threshold]}},
            {"$expr": {"$lte": ["$current_stock", "$min_stock_level"]}},
        ],
    }, {"_id": 1, "name": 1, "current_stock": 1, "min_stock_level": 1}).limit(100))
    for p in low_or_out:
        cs = float(p.get("current_stock", 0) or 0)
        ms = float(p.get("min_stock_level", 0) or 0)
        if cs <= 0:
            out_of_stock.append({"id": p["_id"], "name": p["name"]})
        else:
            low_stock.append({"id": p["_id"], "name": p["name"],
                               "current_stock": cs, "min_stock_level": ms})

    soon = now + timedelta(days=alert_settings["expiry_alert_days"])
    expiring_soon = []
    for p in db[C.products].find({
        "deleted_at": None, "is_active": True,
        "expiry_date": {"$ne": None, "$lte": soon},
    }, {"_id": 1, "name": 1, "expiry_date": 1}):
        ed = p["expiry_date"]
        ed_d = ed.date() if hasattr(ed, "date") else ed
        expiring_soon.append({"id": p["_id"], "name": p["name"],
                               "expiry_date": ed_d.isoformat()})

    # Counts + top
    top_debtors = sorted(
        [{"id": c["_id"], "full_name": c["full_name"], "balance": float(c.get("balance", 0))}
         for c in db[C.customers].find({"deleted_at": None, "balance": {"$gt": 0}},
                                        {"_id": 1, "full_name": 1, "balance": 1})],
        key=lambda x: x["balance"], reverse=True,
    )[:10]
    customers_total_debt = round(sum(c["balance"] for c in top_debtors), 2)
    customers = {
        "count": db[C.customers].count_documents({"deleted_at": None}),
        "balance_total": customers_total_debt,
        # aliases expected by ManagerDashboard.jsx
        "total_debt": customers_total_debt,
        "debtors_count": len(top_debtors),
        "top_debtors": top_debtors,
    }
    top_suppliers = sorted(
        [{"id": s["_id"], "name": s["name"], "balance": float(s.get("balance", 0))}
         for s in db[C.suppliers].find({"deleted_at": None, "balance": {"$gt": 0}},
                                        {"_id": 1, "name": 1, "balance": 1})],
        key=lambda x: x["balance"], reverse=True,
    )[:10]
    suppliers_total_due = round(sum(s["balance"] for s in top_suppliers), 2)
    suppliers = {
        "count": db[C.suppliers].count_documents({"deleted_at": None}),
        "balance_total": suppliers_total_due,
        # aliases expected by ManagerDashboard.jsx
        "total_due": suppliers_total_due,
        "due_count": len(top_suppliers),
        "top_suppliers": top_suppliers,
    }
    # Top selling / top profit / least selling for ManagerDashboard product lists
    top_pipeline = [
        {"$lookup": {"from": "sales", "localField": "sale_id",
                      "foreignField": "_id", "as": "sale"}},
        {"$unwind": "$sale"},
        {"$match": {"sale.created_at": {"$gte": month_start, "$lt": month_end},
                    "sale.status": "completed", "sale.deleted_at": None}},
        {"$group": {"_id": "$product_id",
                     "quantity": {"$sum": "$quantity"},
                     "revenue": {"$sum": "$total"}}},
    ]
    sold = list(db[C.sale_items].aggregate(top_pipeline))
    # Pre-fetch all products needed for sold-item resolution (avoids N+1)
    sold_ids = [r["_id"] for r in sold]
    prod_meta = {p["_id"]: p for p in db[C.products].find(
        {"_id": {"$in": sold_ids}}, {"name": 1, "cost_price": 1, "sale_price": 1})}

    def _resolve(rows, key, desc=True, limit=10):
        rows = sorted(rows, key=lambda r: r.get(key, 0) or 0, reverse=desc)[:limit]
        out = []
        for r in rows:
            p = prod_meta.get(r["_id"], {})
            profit = r.get("revenue", 0) - float(p.get("cost_price", 0) or 0) * float(r.get("quantity", 0))
            out.append({
                "id": r["_id"], "name": p.get("name", "?"),
                "quantity": r.get("quantity", 0),
                "revenue": r.get("revenue", 0), "profit": profit,
            })
        return out
    top_selling = _resolve(sold, "quantity", desc=True)
    # For top_profit we need to compute profit per row first, then sort by it.
    sold_with_profit = []
    for s in sold:
        p = prod_meta.get(s["_id"], {})
        profit = s.get("revenue", 0) - float(p.get("cost_price", 0) or 0) * float(s.get("quantity", 0))
        sold_with_profit.append({**s, "profit": profit})
    top_profit = _resolve(sold_with_profit, "profit", desc=True)
    # Least selling = sold items with lowest qty (Phase B candidate: include never-sold)
    least_selling = _resolve(sold, "quantity", desc=False)
    products = {
        "count": db[C.products].count_documents({"deleted_at": None, "is_active": True}),
        "top_selling": top_selling,
        "top_profit": top_profit,
        "least_selling": least_selling,
    }

    # Returns summary — pending/approved/rejected counts + today/month totals
    returns_today_agg = list(db[C.sale_returns].aggregate([
        {"$match": {"created_at": {"$gte": today_start, "$lte": today_end}, "deleted_at": None}},
        {"$group": {"_id": None, "total": {"$sum": "$total"}, "count": {"$sum": 1}}},
    ]))
    returns_month_agg = list(db[C.sale_returns].aggregate([
        {"$match": {"created_at": {"$gte": month_start, "$lt": month_end}, "deleted_at": None}},
        {"$group": {"_id": None, "total": {"$sum": "$total"}, "count": {"$sum": 1}}},
    ]))
    returns = {
        "today_total": returns_today_agg[0]["total"] if returns_today_agg else 0,
        "today_count": returns_today_agg[0]["count"] if returns_today_agg else 0,
        "month_total": returns_month_agg[0]["total"] if returns_month_agg else 0,
        "month_count": returns_month_agg[0]["count"] if returns_month_agg else 0,
        "pending_count": db[C.sale_returns].count_documents({"status": "pending", "deleted_at": None}),
        "approved_count": db[C.sale_returns].count_documents({"status": "approved", "deleted_at": None}),
        "rejected_count": db[C.sale_returns].count_documents({"status": "rejected", "deleted_at": None}),
    }

    # Expenses summary + by-category breakdown for pie chart
    exp_cat_pipeline = [
        {"$match": {"created_at": {"$gte": month_start, "$lt": month_end}, "deleted_at": None}},
        {"$group": {"_id": "$category_id", "total": {"$sum": "$amount"}}},
        {"$sort": {"total": -1}},
    ]
    exp_categories = []
    exp_raw = list(db[C.expenses].aggregate(exp_cat_pipeline))
    if exp_raw:
        exp_cat_ids = [r["_id"] for r in exp_raw if r["_id"]]
        cat_map = {c["_id"]: c for c in
                   db[C.expense_categories].find({"_id": {"$in": exp_cat_ids}})}
        for r in exp_raw:
            cat = cat_map.get(r["_id"]) if r["_id"] else None
            exp_categories.append({"name": cat["name"] if cat else "بدون تصنيف",
                                    "category": cat["name"] if cat else "بدون تصنيف",
                                    "total": r["total"]})
    expenses_today = sum_expenses(today_start, today_end + timedelta(microseconds=1))
    expenses_month = sum_expenses(month_start, month_end)
    expenses_total = sum_expenses(
        datetime(2000, 1, 1, tzinfo=timezone.utc), now
    )
    expenses = {
        "today": expenses_today,
        "month": expenses_month,
        "total": expenses_total,
        "categories": exp_categories,
    }

    # Sales chart — last 30 days (renamed to chart_30d to match frontend)
    chart_pipeline = [
        {"$match": {"created_at": {"$gte": now - timedelta(days=30), "$lte": now},
                    "status": "completed", "deleted_at": None}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "sales": {"$sum": "$total"},
        }},
        {"$sort": {"_id": 1}},
    ]
    # Expenses chart — last 30 days
    exp_chart_pipeline = [
        {"$match": {"created_at": {"$gte": now - timedelta(days=30), "$lte": now},
                    "deleted_at": None}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "expenses": {"$sum": "$amount"},
        }},
    ]
    # Returns chart — last 30 days (approved only)
    ret_chart_pipeline = [
        {"$match": {"created_at": {"$gte": now - timedelta(days=30), "$lte": now},
                    "status": "approved", "deleted_at": None}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "returns": {"$sum": "$total"},
        }},
    ]
    sales_by_day   = {r["_id"]: float(r["sales"])   for r in db[C.sales].aggregate(chart_pipeline)}
    exp_by_day     = {r["_id"]: float(r["expenses"]) for r in db[C.expenses].aggregate(exp_chart_pipeline)}
    ret_by_day     = {r["_id"]: float(r["returns"])  for r in db[C.sale_returns].aggregate(ret_chart_pipeline)}
    # Build a complete 30-day series
    all_days = sorted(set(list(sales_by_day.keys()) + list(exp_by_day.keys()) + list(ret_by_day.keys())))
    chart_30d = []
    for d in all_days:
        s = float(sales_by_day.get(d, 0))
        e = float(exp_by_day.get(d, 0))
        r = float(ret_by_day.get(d, 0))
        net = s - r
        chart_30d.append({"date": d, "sales": s, "expenses": e, "returns": r,
                           "net_sales": net, "profit": net - e})

    # Payment methods breakdown — current month (net of returns)
    pm_pipeline = [
        {"$match": {"created_at": {"$gte": month_start, "$lt": month_end},
                    "status": "completed", "deleted_at": None}},
        {"$group": {"_id": "$payment_method", "total": {"$sum": "$total"}, "count": {"$sum": 1}}},
    ]
    pm_returns_by_type = _sum_returns_by_type(db, month_start, month_end)
    payment_methods = []
    for r in db[C.sales].aggregate(pm_pipeline):
        gross = float(r["total"])
        ret   = pm_returns_by_type.get(r["_id"], {}).get("total", 0.0)
        payment_methods.append({
            "method":        r["_id"],
            "total":         round(gross, 2),
            "returns_total": round(ret, 2),
            "net_total":     round(max(0.0, gross - ret), 2),
            "count":         int(r["count"]),
        })

    return {
        "as_of": now.isoformat(),
        "alerts": {
            "over_credit_limit": over_credit,
            "suppliers_overdue": suppliers_overdue,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "expiring_soon": expiring_soon,
        },
        "sales": sales, "profits": profits, "purchases": purchases,
        "cash_box": cash_box,
        "customers": customers, "suppliers": suppliers, "products": products,
        "returns": returns, "expenses": expenses,
        "chart_30d": chart_30d,
        "payment_methods": payment_methods,
    }
