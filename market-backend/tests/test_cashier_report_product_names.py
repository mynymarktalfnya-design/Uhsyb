import unittest

from routes.dashboard import _invoice_product_lines, _invoice_product_names, _sales_unit_summary


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

    def test_returns_sale_unit_and_quantity_for_daily_summary(self):
        db = _Db()
        db.collections["sale_items"] = _Collection([
            {"sale_id": "sale-3", "product_id": "p-1", "quantity": 2,
             "sale_unit": "carton", "pieces_per_carton": 24},
            {"sale_id": "sale-3", "product_id": "p-2", "quantity": 3,
             "sale_unit": "piece"},
        ])
        db.collections["products"] = _Collection(products={
            "p-1": {"name": "مياه"},
            "p-2": {"name": "خبز"},
        })

        self.assertEqual(_invoice_product_lines(db, "sale-3"), [
            {"name": "مياه", "sale_unit": "carton", "quantity": 2, "pieces_per_carton": 24},
            {"name": "خبز", "sale_unit": "piece", "quantity": 3, "pieces_per_carton": 1},
        ])

    def test_summarizes_realized_value_and_quantity_by_unit(self):
        db = _Db()
        db.collections["sale_items"] = _Collection([
            {"sale_id": "sale-4", "quantity": 2, "sale_unit": "carton", "total": 100, "net_total": 95},
            {"sale_id": "sale-4", "quantity": 3, "sale_unit": "piece", "total": 30},
            {"sale_id": "sale-5", "quantity": 1, "sale_unit": "carton", "total": 50},
        ])

        self.assertEqual(_sales_unit_summary(db, ["sale-4", "sale-5"]), {
            "carton": {"quantity": 3.0, "total": 145.0},
            "piece": {"quantity": 3.0, "total": 30.0},
        })


if __name__ == "__main__":
    unittest.main()
