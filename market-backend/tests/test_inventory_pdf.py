import os
import sys
from pathlib import Path

os.environ.pop("NEON_DATABASE_URL", None)
os.environ.pop("MONGO_URL", None)
os.environ["ALLOW_MONGOMOCK"] = "true"
sys.path.insert(0, str(Path(__file__).parents[1]))

from routes import telegram


class FakeProducts:
    def find(self, *_args, **_kwargs):
        return self

    def sort(self, *_args, **_kwargs):
        return [
            {
                "_id": "p-1", "sku": "SKU-001", "name": "منتج اختبار 1",
                "cost_price": 10, "sale_price": 15, "current_stock": 4,
                "deleted_at": None,
            },
            {
                "_id": "p-2", "sku": "SKU-002", "name": "منتج اختبار 2",
                "cost_price": 20, "sale_price": 30, "current_stock": 2,
                "deleted_at": None,
            },
        ]


class FakeDb:
    def __getitem__(self, key):
        if key == telegram.C.products:
            return FakeProducts()
        raise AssertionError(f"unexpected collection: {key}")


def test_inventory_pdf_is_nonempty_and_pdf():
    original = telegram.db
    telegram.db = FakeDb()
    try:
        content = telegram._inventory_pdf()
    finally:
        telegram.db = original
    assert content.startswith(b"%PDF")
    assert len(content) > 1200
