import unittest

from utils.dashboard_rows import top_supplier_rows


class SupplierDashboardRowsTest(unittest.TestCase):
    def test_normalizes_id_without_key_error(self):
        rows = top_supplier_rows([
            {"id": "supplier-1", "name": "مورد 1", "balance": 125.5},
            {"_id": "supplier-2", "name": "مورد 2", "balance": 80},
        ])

        self.assertEqual([row["id"] for row in rows], ["supplier-1", "supplier-2"])
        self.assertEqual(rows[0]["balance"], 125.5)


if __name__ == "__main__":
    unittest.main()
