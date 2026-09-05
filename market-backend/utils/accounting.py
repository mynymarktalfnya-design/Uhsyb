"""Shared accounting calculations for customer ledgers."""

from typing import Any

from database import C


def customer_account_totals(db: Any, customer_id: str) -> dict:
    """Compute a customer's balance from the immutable accounting movements.

    The stored customer.balance is a cache maintained by sale/payment/return
    writes. Reports must derive their answer from the ledger so old or
    interrupted writes cannot make the customer screen disagree with the
    statement.
    """
    sales = list(db[C.sales].find({
        "customer_id": customer_id,
        "payment_method": "credit",
        "status": "completed",
        "deleted_at": None,
    }, {"_id": 1, "total": 1, "created_at": 1}))
    sale_ids = [sale["_id"] for sale in sales]

    total_credit_purchases = sum(float(sale.get("total", 0) or 0) for sale in sales)
    total_paid = sum(
        float(payment.get("amount", 0) or 0)
        for payment in db[C.customer_payments].find({
            "customer_id": customer_id,
            "deleted_at": None,
        }, {"amount": 1})
    )
    total_returns = sum(
        float(ret.get("total", 0) or 0)
        for ret in db[C.sale_returns].find({
            "sale_id": {"$in": sale_ids},
            "customer_id": customer_id,
            "status": "approved",
            "deleted_at": None,
        }, {"total": 1})
    ) if sale_ids else 0.0

    return {
        "total_credit_purchases": round(total_credit_purchases, 2),
        "total_paid": round(total_paid, 2),
        "total_returns": round(total_returns, 2),
        "balance": round(total_credit_purchases - total_paid - total_returns, 2),
        "invoice_count": len(sales),
        "payment_count": db[C.customer_payments].count_documents({
            "customer_id": customer_id,
            "deleted_at": None,
        }),
        "sale_ids": sale_ids,
    }