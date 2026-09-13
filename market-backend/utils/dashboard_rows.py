"""Pure row-normalization helpers used by dashboard responses."""


def top_supplier_rows(supplier_balances):
    """Normalize supplier balance rows for the manager dashboard.

    The balance calculation emits ``id``. Older Mongo-shaped rows may still
    contain ``_id``, so accept both without crashing the dashboard.
    """
    rows = []
    for supplier in supplier_balances:
        supplier_id = supplier.get("id") or supplier.get("_id")
        if not supplier_id:
            continue
        rows.append({
            "id": supplier_id,
            "name": supplier.get("name", ""),
            "balance": float(supplier.get("balance", 0) or 0),
        })
    return sorted(rows, key=lambda item: item["balance"], reverse=True)[:10]
