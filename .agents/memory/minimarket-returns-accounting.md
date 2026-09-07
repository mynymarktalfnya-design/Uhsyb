---
name: MiniMarket Returns Accounting — Full Fix Log
description: Documents all bugs found in the returns system and how they were fixed, so future work stays consistent.
---

## Rule: Customer balance must be reduced based on ORIGINAL SALE payment method, not return_type

**Why:** `return_type` describes HOW the refund is given back (cash or credit note). But the customer's debt was recorded against the original آجل sale. Both refund types clear the debt — so balance must always be reduced when `sale.payment_method == "credit"`.

**How to apply:** In any function that approves a return, look up the original sale and check `sale.payment_method == "credit"`, not `ret.return_type == "credit"`.

## Bug fixed: `instant_return` never updated customer balance

**Why:** The instant return endpoint (POST /api/sales-returns/instant) called `_apply_return_stock` but omitted the customer balance update entirely. The `approve_return` path had partial logic (wrong condition). Both paths now update balance correctly.

**How to apply:** Always audit both return paths (instant + approve) when changing balance logic.

## Bug fixed: customer statement included pending/rejected returns

**Why:** `customer_accounts.py` statement query had no `status` filter on `sale_returns`, so pending and rejected returns inflated the credit column.

**Fix:** Added `"status": "approved"` to the returns filter in the statement query.

## Bug fixed: Sales.jsx showed gross totals only

**Why:** The page fetched `/sales` only, no returns. KPI cards showed gross sales ignoring any returns.

**Fix:** Now fetches `/sales-returns?status=approved` in parallel and computes `netAmt = totalAmt - returnsAmt`. Added dedicated KPI cards for total returns and net sales.

## Bug fixed: parties.py customer detail had hardcoded `total_returns: 0`

**Why:** The GET /customers/{id} endpoint returned `"total_returns": 0` always.

**Fix:** Now queries `sale_returns` collection for approved returns and returns `total_returns` + `net_credit_balance`.

## Net sales formula everywhere
`net_sales = gross_sales − approved_returns`
This applies to: dashboard /summary, dashboard /manager, reports /daily /monthly /profits /payment-methods /sales-by-day, Sales.jsx, SalesDaily.jsx, Reports.jsx, ManagerDashboard.jsx.
