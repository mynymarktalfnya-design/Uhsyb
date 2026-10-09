import unittest

from routes.dashboard import _invoice_product_names


class _Collection:
    def __init__(self, rows=None, products=None):
        self.rows = rows or []
        self.products = products or {}

    def find(self, _query):
        return list(self.rows)

    def find_one(self, query, _projection=None):
        return self.products.get(query.get("_id"))


class _Db:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections[name]


class CashierReportProductNamesTest(unittest.TestCase):
    def test_returns_product_names_in_invoice_item_order(self):
        db = _Db()
        db.collections["sale_items"] = _Collection([
            {"sale_id": "sale-1", "product_id": "p-2"},
            {"sale_id": "sale-1", "product_id": "p-1"},
        ])
        db.collections["products"] = _Collection(products={
            "p-1": {"name": "ماء"},
            "p-2": {"name": "أرز"},
        })

        self.assertEqual(_invoice_product_names(db, "sale-1"), ["أرز", "ماء"])

    def test_uses_saved_item_name_when_product_is_missing(self):
        db = _Db()
        db.collections["sale_items"] = _Collection([
            {"sale_id": "sale-2", "product_id": "deleted", "product_name": "منتج سابق"},
            {"sale_id": "sale-2", "product_id": "missing"},
        ])
        db.collections["products"] = _Collection()

        self.assertEqual(_invoice_product_names(db, "sale-2"), ["منتج سابق", "—"])


if __name__ == "__main__":
    unittest.main()
