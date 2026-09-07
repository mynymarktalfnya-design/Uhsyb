from datetime import datetime, timezone
import os

import mongomock

os.environ.pop("NEON_DATABASE_URL", None)
os.environ.pop("MONGO_URL", None)
os.environ["ALLOW_MONGOMOCK"] = "true"

from database import C
from routes.dashboard import _sales_product_method_breakdown


def test_sales_product_method_breakdown_groups_product_and_payment_method():
    client = mongomock.MongoClient()
    db = client["dashboard_test"]
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 1, tzinfo=timezone.utc)

    db[C.products].insert_one({"_id": "p1", "name": "ماء"})
    db[C.sales].insert_many([
        {"_id": "s-cash", "created_at": datetime(2026, 9, 5, tzinfo=timezone.utc), "status": "completed", "deleted_at": None, "payment_method": "cash"},
        {"_id": "s-credit", "created_at": datetime(2026, 9, 6, tzinfo=timezone.utc), "status": "completed", "deleted_at": None, "payment_method": "credit"},
    ])
    db[C.sale_items].insert_many([
        {"_id": "i1", "sale_id": "s-cash", "product_id": "p1", "quantity": 2, "total": 20},
        {"_id": "i2", "sale_id": "s-credit", "product_id": "p1", "quantity": 3, "total": 30},
    ])

    rows = _sales_product_method_breakdown(db, start, end)

    assert {(row["product_name"], row["payment_method"], row["quantity"], row["total"]) for row in rows} == {
        ("ماء", "cash", 2.0, 20.0),
        ("ماء", "credit", 3.0, 30.0),
    }
